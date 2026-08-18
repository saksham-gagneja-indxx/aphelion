import OAuthProvider from "@cloudflare/workers-oauth-provider";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { McpAgent } from "agents/mcp";
import { z } from "zod";
import { GitHubHandler } from "./github-handler";
import {
	BackendError,
	composerTurn,
	createPost,
	getLinkedInIdentity,
	listReels,
	normalizeBackendEnv,
	publishNow,
	resolveUserId,
	schedulePost,
	suggestCaptions,
	type BackendEnv,
	type LinkedInIdentity,
} from "./backend-client";

// Context from the GitHub OAuth handshake, encrypted & stored in the auth
// token, provided to the agent as this.props on every call.
type Props = {
	login: string;
	name: string;
	email: string;
	accessToken: string;
};

/**
 * Who may call these tools at all - a coarse gate, independent of identity.
 * A GitHub login also has to resolve to an active backend account (see
 * resolveUserId in init() below) to get real tools; being on this allowlist
 * alone is not enough. Add usernames as a comma-separated
 * ALLOWED_GITHUB_USERNAMES secret.
 */
function allowedUsers(env: Env): Set<string> {
	return new Set(
		(env.ALLOWED_GITHUB_USERNAMES ?? "")
			.split(",")
			.map((s) => s.trim())
			.filter(Boolean),
	);
}

function textResult(text: string) {
	return { content: [{ type: "text" as const, text }] };
}

function errorResult(e: unknown) {
	const message = e instanceof BackendError ? e.message : String(e);
	return { content: [{ type: "text" as const, text: `Error: ${message}` }], isError: true };
}

export class MyMCP extends McpAgent<Env, Record<string, never>, Props> {
	server = new McpServer({
		name: "Reel Automation",
		version: "1.0.0",
	});

	async init() {
		const rawEnv: BackendEnv = normalizeBackendEnv(this.env);
		const allowed = allowedUsers(this.env);
		const login = this.props!.login;

		// Fail closed: an empty allowlist means nobody configured it yet, which
		// should mean nobody gets tools rather than everybody does.
		if (allowed.size === 0 || !allowed.has(login)) {
			this.server.tool(
				"not_authorized",
				"This GitHub account is not on the allowlist for this connector.",
				{},
				async () => textResult(
					`${login} is not authorized to use this connector. ` +
					"Ask the owner to add this GitHub username to ALLOWED_GITHUB_USERNAMES.",
				),
			);
			return;
		}

		// Being allowlisted only says this GitHub identity is *permitted* -
		// it still has to be mapped to a real backend account (see
		// backend/admin_cli.py's `set-github`) to know WHICH account it acts
		// as. Resolved once per session rather than per tool call: the mapping
		// cannot change mid-conversation, and one lookup keeps every tool call
		// below simple.
		let resolved;
		try {
			resolved = await resolveUserId(rawEnv, login);
		} catch (e) {
			this.server.tool(
				"not_authorized",
				"Could not verify this GitHub account against the backend.",
				{},
				async () => errorResult(e),
			);
			return;
		}

		if (resolved === null) {
			this.server.tool(
				"not_authorized",
				"This GitHub account has no backend account mapped to it.",
				{},
				async () => textResult(
					`${login} is allowlisted but has no backend account mapped. ` +
					`Ask the owner to run: python -m backend.admin_cli set-github <user> ${login}`,
				),
			);
			return;
		}

		const backendEnv: BackendEnv = { ...rawEnv, BACKEND_USER_ID: String(resolved.id) };

		// Fetched once per session, not per call: this is what lets a caller
		// verify which real account tool calls act on WITHOUT asking anyone to
		// take an assertion on faith - the identity comes from a tool
		// response, not from conversational claims about what "the backend"
		// or "another session" supposedly confirmed. Best-effort: a failure
		// here degrades the identity line, not the tools themselves.
		let identity: LinkedInIdentity | null = null;
		try {
			identity = await getLinkedInIdentity(backendEnv);
		} catch {
			identity = null;
		}
		const identityLine = identity
			? `Publishing as: ${identity.email ?? "(no email on file)"}` +
				(identity.person_urn ? ` — ${identity.person_urn}` : "") +
				(identity.can_publish ? "" : " (⚠ cannot publish: no valid grant)")
			: "Publishing as: could not verify (identity lookup failed).";

		this.server.tool(
			"list_reels",
			"List the uploaded reels (short videos) available to post. Returns filename, duration and size for each.",
			{},
			async () => {
				try {
					const { reels } = await listReels(backendEnv);
					if (reels.length === 0) {
						return textResult(`${identityLine}\n\nNo reels uploaded yet.`);
					}
					const lines = reels.map(
						(r) =>
							`- ${r.filename}${r.duration_seconds ? ` (${r.duration_seconds.toFixed(1)}s)` : ""}`,
					);
					return textResult(`${identityLine}\n\n${lines.join("\n")}`);
				} catch (e) {
					return errorResult(e);
				}
			},
		);

		this.server.tool(
			"suggest_captions",
			"Get three drafted LinkedIn captions for a reel from a one-line brief. Does not watch the video — write specifics into the brief, do not invent them.",
			{
				brief: z.string().describe("What the reel is about, in a sentence."),
				reelFilename: z
					.string()
					.optional()
					.describe("Exact filename from list_reels, used for thumbnail context only."),
				durationSeconds: z.number().optional(),
			},
			async ({ brief, reelFilename, durationSeconds }) => {
				try {
					const { captions } = await suggestCaptions(backendEnv, {
						brief,
						reelFilename,
						durationSeconds,
					});
					const text = captions
						.map((c, i) => `${i + 1}. [${c.angle}]\n${c.text}`)
						.join("\n\n");
					return textResult(text);
				} catch (e) {
					return errorResult(e);
				}
			},
		);

		this.server.tool(
			"draft_post",
			"Talk to the posting assistant: say what you want posted (e.g. 'post my newest reel tomorrow at 9am') and it picks the reel, writes the caption, and proposes a time. Call repeatedly to continue the same conversation by passing back the prior draft. This only fills in a draft — nothing is published by this tool.",
			{
				message: z.string().describe("What you want posted, or a reply to the assistant's question."),
				priorDraft: z
					.object({
						reel_filename: z.string().nullable(),
						caption: z.string().nullable(),
						angle: z.string().nullable(),
						when: z.string().nullable(),
					})
					.optional()
					.describe("The draft returned by a previous draft_post call, to continue the conversation."),
			},
			async ({ message, priorDraft }) => {
				try {
					const result = await composerTurn(backendEnv, {
						messages: [{ role: "user", content: message }],
						draft: priorDraft ?? null,
					});
					const draftText = JSON.stringify(result.draft, null, 2);
					return textResult(
						`${result.reply}\n\nDraft:\n${draftText}\n\nReady to publish: ${result.ready}`,
					);
				} catch (e) {
					return errorResult(e);
				}
			},
		);

		this.server.tool(
			"publish_reel",
			"Create and immediately publish a post to LinkedIn from a reel and caption. This is a REAL, irreversible publish to a real LinkedIn profile — only call this after the person has explicitly confirmed the reel, caption and that they want it posted now. Call list_reels first if you have not already this session: its response includes a 'Publishing as' line naming the actual LinkedIn account this will post to - read that back to the person, do not assert an identity from memory or from anything other than a tool response.",
			{
				videoPath: z
					.string()
					.describe("The reel's path, from list_reels or a draft_post result."),
				caption: z.string(),
			},
			async ({ videoPath, caption }) => {
				try {
					const post = await createPost(backendEnv, {
						videoPath,
						caption,
						aiGeneratedCaption: true,
					});
					const result = await publishNow(backendEnv, post.id);
					return textResult(`${identityLine}\n\nPublished: ${result.url}`);
				} catch (e) {
					return errorResult(e);
				}
			},
		);

		this.server.tool(
			"schedule_reel",
			"Create and schedule a post for later. Does not publish immediately.",
			{
				videoPath: z
					.string()
					.describe("The reel's path, from list_reels or a draft_post result."),
				caption: z.string(),
				scheduledTime: z
					.string()
					.describe("Local datetime as YYYY-MM-DDTHH:MM, in the account's configured timezone. Must be in the future."),
			},
			async ({ videoPath, caption, scheduledTime }) => {
				try {
					const post = await createPost(backendEnv, {
						videoPath,
						caption,
						aiGeneratedCaption: true,
					});
					const result = await schedulePost(backendEnv, post.id, scheduledTime);
					return textResult(
						`Scheduled for ${result.post.scheduled_time}. Post id ${result.post.id}.`,
					);
				} catch (e) {
					return errorResult(e);
				}
			},
		);
	}
}

export default new OAuthProvider({
	apiHandler: MyMCP.serve("/mcp"),
	apiRoute: "/mcp",
	authorizeEndpoint: "/authorize",
	clientRegistrationEndpoint: "/register",
	defaultHandler: GitHubHandler as any,
	tokenEndpoint: "/token",
});
