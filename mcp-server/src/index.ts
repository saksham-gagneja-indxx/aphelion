import OAuthProvider from "@cloudflare/workers-oauth-provider";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { McpAgent } from "agents/mcp";
import { z } from "zod";
import { GitHubHandler } from "./github-handler";
import {
	BackendError,
	composerTurn,
	createPost,
	listReels,
	normalizeBackendEnv,
	publishNow,
	schedulePost,
	suggestCaptions,
	type BackendEnv,
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
 * Who may call these tools at all. This is a GATE, not an identity mapping —
 * every tool always acts against BACKEND_USER_ID (see backend-client.ts),
 * regardless of which allowed GitHub user is currently connected. Add
 * usernames as a comma-separated ALLOWED_GITHUB_USERNAMES secret.
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
		const backendEnv: BackendEnv = normalizeBackendEnv(this.env);
		const allowed = allowedUsers(this.env);

		// Fail closed: an empty allowlist means nobody configured it yet, which
		// should mean nobody gets tools rather than everybody does.
		if (allowed.size === 0 || !allowed.has(this.props!.login)) {
			this.server.tool(
				"not_authorized",
				"This GitHub account is not on the allowlist for this connector.",
				{},
				async () => textResult(
					`${this.props!.login} is not authorized to use this connector. ` +
					"Ask the owner to add this GitHub username to ALLOWED_GITHUB_USERNAMES.",
				),
			);
			return;
		}

		this.server.tool(
			"list_reels",
			"List the uploaded reels (short videos) available to post. Returns filename, duration and size for each.",
			{},
			async () => {
				try {
					const { reels } = await listReels(backendEnv);
					if (reels.length === 0) {
						return textResult("No reels uploaded yet.");
					}
					const lines = reels.map(
						(r) =>
							`- ${r.filename}${r.duration_seconds ? ` (${r.duration_seconds.toFixed(1)}s)` : ""}`,
					);
					return textResult(lines.join("\n"));
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
			"Create and immediately publish a post to LinkedIn from a reel and caption. This is a REAL, irreversible publish to a real LinkedIn profile — only call this after the person has explicitly confirmed the reel, caption and that they want it posted now.",
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
					return textResult(`Published: ${result.url}`);
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
