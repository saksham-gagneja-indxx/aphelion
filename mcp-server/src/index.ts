import OAuthProvider from "@cloudflare/workers-oauth-provider";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { McpAgent } from "agents/mcp";
import { z } from "zod";
import { GitHubHandler } from "./github-handler";

// Strip UTF-8 BOM from environment variables
function stripBOM(str: string): string {
	return str.charCodeAt(0) === 0xfeff ? str.slice(1) : str;
}
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
	uploadReel,
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
		description: "LinkedIn reel automation: upload, caption, schedule, and publish videos. Use 'show_available_commands' to see what you can do.",
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

		// Getting started guide - Claude will show this first
		this.server.tool(
			"getting_started",
			"🎬 Get started with reel management! Shows available commands and quick workflow.",
			{},
			async () => {
				return textResult(
					`${identityLine}\n\n` +
					`🎯 **Welcome to Reel Management!**\n\n` +
					`Here's what you can do right now:\n\n` +
					`📤 **upload_reel** - Attach a video right here in chat to upload it\n` +
					`📽️ **list_reels** - See all your uploaded reels\n` +
					`💬 **draft_post** - Plan and prepare a post\n` +
					`🚀 **publish_reel** - Post to LinkedIn NOW (irreversible)\n` +
					`⏰ **schedule_reel** - Schedule a post for later\n\n` +
					`**Quick Workflow:**\n` +
					`1️⃣ upload_reel (if it's not already in your library) or list_reels → See what you have\n` +
					`2️⃣ draft_post → Prepare your post\n` +
					`3️⃣ publish_reel or schedule_reel → Make it live\n\n` +
					`👉 **Try this now:** Pick a reel and prepare it for posting. What would you like to do?\n`
				);
			},
		);

		// Help command - detailed reference
		this.server.tool(
			"show_available_commands",
			"📋 Show all available commands and detailed descriptions.",
			{},
			async () => {
				return textResult(
					`${identityLine}\n\n` +
					`**📋 All Available Commands:\n\n` +
					`1. **upload_reel**\n   Attach a video directly in this chat to add it to your reel library (short clips only, roughly under 20MB)\n\n` +
					`2. **list_reels**\n   See all your uploaded reels ready to post\n\n` +
					`3. **draft_post**\n   Plan and prepare a post (pick reel, write caption, set time)\n\n` +
					`4. **publish_reel**\n   Immediately publish a reel to LinkedIn (⚠️ LIVE and irreversible)\n\n` +
					`5. **schedule_reel**\n   Schedule a reel to post later\n\n` +
					`**⚡ Pro Tips:**\n` +
					`• Start with "getting_started" for a quick guide\n` +
					`• Use "draft_post" to prepare before publishing\n` +
					`• Always check the 'Publishing as' line before publishing\n`
				);
			},
		);

		this.server.tool(
			"upload_reel",
			"📤 Upload a new reel by attaching a video file directly in this chat. Ask the person to attach/drag their video into the conversation, then pass its raw bytes here as base64 along with the original filename. Keep clips short - roughly under 20MB decoded (~27MB of base64 text); for anything bigger, they should use the web app's upload page instead. Once uploaded, it shows up in list_reels immediately.",
			{
				filename: z.string().describe("The original filename, e.g. 'my_reel.mp4'."),
				base64Data: z
					.string()
					.describe("The attached video file's raw bytes, base64-encoded."),
			},
			async ({ filename, base64Data }) => {
				try {
					const result = await uploadReel(backendEnv, { filename, base64Data });
					const r = result.reel;
					return textResult(
						`${identityLine}\n\nUploaded: ${r.filename}` +
							(r.duration_seconds ? ` (${r.duration_seconds.toFixed(1)}s)` : ""),
					);
				} catch (e) {
					return errorResult(e);
				}
			},
		);

		this.server.tool(
			"list_reels",
			"📽️ List all your uploaded reels (short videos) ready to post. Shows filename, duration, and file size. Start here to see what's available.",
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
			"draft_post",
			"💬 Chat with AI to plan a post: tell it what you want (e.g. 'post my best reel about AI tomorrow at 9am'). AI picks the reel, writes the caption, and suggests timing. Multi-turn conversation until you're happy. Draft only—nothing posts until you confirm.",
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
			"🚀 Publish a reel NOW to LinkedIn—this is LIVE and irreversible! Only use after confirming the reel, caption, and that user wants it posted immediately. Always read back the 'Publishing as' line showing which LinkedIn account it's going to.",
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
			"⏰ Schedule a reel to post later (e.g., tomorrow, next week). Safe—drafts first, then schedules. Give a time like 'tomorrow at 9am' and the AI will post at the right moment.",
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
