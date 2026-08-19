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
	deletePost,
	editPost,
	getLinkedInIdentity,
	linkGithubStart,
	listPosts,
	listReels,
	normalizeBackendEnv,
	publishNow,
	resolveUserId,
	schedulePost,
	uploadReel,
	uploadReelFromUrl,
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
 * alone is not enough.
 *
 * Empty/unset ALLOWED_GITHUB_USERNAMES means OPEN, not closed: anyone who
 * completes GitHub OAuth may attempt to connect. The real access control is
 * downstream - resolveUserId + account approval (User.is_active, see
 * backend/api/auth_routes.py's _resolve_user) - so an open front door here
 * does not mean an open account; it means a stranger can reach the self-serve
 * LinkedIn-link flow (see init() below) instead of being turned away before
 * ever getting the chance to ask for access. Set ALLOWED_GITHUB_USERNAMES to
 * go back to invite-only: a non-empty list is still enforced exactly as
 * before.
 */
function allowedUsers(env: Env): Set<string> | null {
	const configured = (env.ALLOWED_GITHUB_USERNAMES ?? "")
		.split(",")
		.map((s) => s.trim())
		.filter(Boolean);
	return configured.length > 0 ? new Set(configured) : null;
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

		// null allowed = open (see allowedUsers). A configured, non-empty list
		// is still a hard invite-only gate, same as before.
		if (allowed !== null && !allowed.has(login)) {
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
			// No backend account is mapped to this GitHub login yet - which
			// covers both "never connected" and "connected but still pending
			// approval" (the backend deliberately doesn't distinguish those to
			// this caller, see resolveUserId). Either way, hand back a real
			// LinkedIn sign-in link rather than a dead end: on success it maps
			// this GitHub login to whichever account signs in, automatically -
			// no admin_cli step. Account approval (is_active) is untouched by
			// this; a brand new signup still needs approving before real tools
			// work, same as the web app.
			let linkUrl: string | null = null;
			let linkError: unknown = null;
			try {
				linkUrl = (await linkGithubStart(rawEnv, login)).url;
			} catch (e) {
				linkError = e;
			}

			this.server.tool(
				"not_authorized",
				"This GitHub account has no backend account mapped to it yet - connect LinkedIn to set one up.",
				{},
				async () => {
					if (linkUrl) {
						return textResult(
							`${login} isn't connected to a Post Pilot account yet.\n\n` +
							`👉 Sign in with LinkedIn here to connect this GitHub login to your account:\n${linkUrl}\n\n` +
							`That page brings you back here on its own once it's done - just try your request again ` +
							`after. New accounts need the owner's approval before tools work for real - if it's been ` +
							`a bit, ask them to approve you.`,
						);
					}
					return textResult(
						`${login} has no backend account mapped, and starting LinkedIn sign-in failed ` +
						`(${linkError instanceof BackendError ? linkError.message : String(linkError)}). ` +
						`Ask the owner to run: python -m backend.admin_cli set-github <user> ${login}`,
					);
				},
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
			"🎬 Get started with reel management! Shows available commands and quick workflow. READ THIS if the person attaches a video: do not try to pass its raw content into any tool call, and follow the upload guidance in this response instead.",
			{},
			async () => {
				return textResult(
					`${identityLine}\n\n` +
					`🎯 **Welcome to Reel Management!**\n\n` +
					`**If someone attaches a video in this chat, do NOT try to read or re-encode its raw bytes into any tool call - that reliably fails or hangs for anything but a trivially small file. Instead:**\n` +
					`1. If a Google Drive connector is also connected, try uploading the attached file to their Drive through it, turn on link sharing ("Anyone with the link"), then pass that resulting shareable link to upload_reel_from_url.\n` +
					`2. If there's no Drive connector, or that doesn't produce a working link, say so plainly and ask them to host the video somewhere (Drive/Dropbox/etc. with a shareable link) and paste the link, or upload it directly through the Post Pilot web app. Don't silently retry the same failing approach.\n\n` +
					`Here's what you can do right now:\n\n` +
					`📤 **upload_reel_from_url** - Give a direct video link (Drive/Dropbox/S3/etc.) - the reliable way to get any real reel in\n` +
					`📎 **upload_reel** - Attach a video right here in chat (tiny clips only, a few MB at most - not for real reels)\n` +
					`📽️ **list_reels** - See all your uploaded reels\n` +
					`💬 **draft_post** - Plan and prepare a post\n` +
					`🚀 **publish_reel** - Post to LinkedIn NOW (irreversible)\n` +
					`⏰ **schedule_reel** - Schedule a post for later\n\n` +
					`**Quick Workflow:**\n` +
					`1️⃣ upload_reel_from_url (via a Drive link if needed) or list_reels if it's already uploaded → See what you have\n` +
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
					`1. **upload_reel_from_url**\n   Upload a reel from a direct video link - the reliable way to get a real reel in, any reasonable size\n\n` +
					`2. **upload_reel**\n   Attach a video directly in this chat (only works for tiny clips, a few MB at most - prefer upload_reel_from_url otherwise)\n\n` +
					`3. **list_reels**\n   See all your uploaded reels ready to post\n\n` +
					`4. **draft_post**\n   Plan and prepare a post (pick reel, write caption, set time)\n\n` +
					`5. **publish_reel**\n   Immediately publish a reel to LinkedIn (⚠️ LIVE and irreversible)\n\n` +
					`6. **schedule_reel**\n   Schedule a reel to post later\n\n` +
					`7. **list_posts**\n   See your posts (draft/scheduled/published/cancelled) with their ids - say "delete it" or "the last one" and this gets called automatically, no need to look up an id yourself\n\n` +
					`8. **delete_reel_post**\n   Delete a post - retracts it from LinkedIn first if it's already live\n\n` +
					`9. **edit_reel_post**\n   Change a not-yet-published post's caption or scheduled time\n\n` +
					`**⚡ Pro Tips:**\n` +
					`• Start with "getting_started" for a quick guide\n` +
					`• If someone attaches a video: don't try to read/re-encode it yourself. If Google Drive is connected, upload it there first, share the link, then use upload_reel_from_url. Otherwise ask them for a link or point them to the web app.\n` +
					`• Use "draft_post" to prepare before publishing\n` +
					`• Always check the 'Publishing as' line before publishing\n`
				);
			},
		);

		this.server.tool(
			"upload_reel_from_url",
			"📤 Upload a new reel from a direct video link (Google Drive/Dropbox/S3/any URL that serves the raw file). This is the RELIABLE way to get a real reel into the library - the video is fetched server-side and never has to pass through this conversation, so there's no practical size limit tied to chat. Use this instead of upload_reel for anything beyond a tiny test clip. If the person attached a video in chat rather than giving a link: if a Google Drive connector is available, try uploading it to their Drive through that connector, enable link sharing, and pass the resulting shareable link here - do not attempt to read/re-encode the attachment's bytes yourself. The link must point directly at the video file itself, not a share/preview page (e.g. a Google Drive share link needs converting to a direct-download link first).",
			{
				url: z.string().describe("A direct, publicly (or presigned-privately) reachable URL to the video file."),
				filename: z.string().optional().describe("Filename to store it as. Guessed from the URL if omitted."),
			},
			async ({ url, filename }) => {
				try {
					const result = await uploadReelFromUrl(backendEnv, { url, filename });
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
			"upload_reel",
			"📎 Upload a new reel by attaching a video file directly in this chat, encoded as base64. Only works reliably for TINY clips (a few MB at most) - the file has to be generated as literal text to fill this argument, which is slow and unreliable for anything reel-sized and can fail outright on larger files. For any real reel, use upload_reel_from_url instead (host it somewhere and pass a link) - don't attempt this tool for a file you don't already know is very small.",
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
					return textResult(`${identityLine}\n\nPublished: ${result.url}\nPost id: ${post.id}`);
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

		this.server.tool(
			"list_posts",
			"📋 List this account's posts (drafts, scheduled, published, cancelled) - newest first - each with its numeric id, status, caption, and video filename. Call this BEFORE delete_reel_post or edit_reel_post whenever the person hasn't given you a numeric post id (e.g. 'delete it', 'delete the last one', 'edit my most recent post', 'cancel the one I just scheduled'): the first entry in the list is the most recent post, so match on that or on caption/filename instead of asking the person to look up an id themselves - they generally don't know it and shouldn't need to.",
			{
				status: z.string().optional().describe("Filter to one status: draft, queued, scheduled, posted, failed, cancelled. Omit to list all."),
			},
			async ({ status }) => {
				try {
					const { posts } = await listPosts(backendEnv, status);
					if (posts.length === 0) {
						return textResult("No posts found.");
					}
					const lines = posts.map((p) => {
						const filename = p.video_path.split(/[\\/]/).pop();
						const captionPreview = p.caption ? `"${p.caption.slice(0, 60)}${p.caption.length > 60 ? "…" : ""}"` : "(no caption)";
						return `- Post id ${p.id} [${p.status}] ${filename} ${captionPreview}` +
							(p.scheduled_time ? ` — scheduled ${p.scheduled_time}` : "");
					});
					return textResult(lines.join("\n"));
				} catch (e) {
					return errorResult(e);
				}
			},
		);

		this.server.tool(
			"delete_reel_post",
			"🗑️ Delete a post by its numeric id. If it's already live on LinkedIn, this retracts it from the platform too - not just the local record. If it's still scheduled, this cancels the pending job so it won't fire. Irreversible. If you don't already have the numeric id from this conversation (e.g. the person just says 'delete it' or 'delete the last one'), call list_posts first and use the matching post's id - don't ask the person to look up an id themselves.",
			{
				postId: z.number().describe("The post's numeric id - from list_posts, or a 'Post id: 28' line earlier in this conversation."),
			},
			async ({ postId }) => {
				try {
					const result = await deletePost(backendEnv, postId);
					return textResult(`${result.message}. Post id ${result.post.id}, status: ${result.post.status}.`);
				} catch (e) {
					return errorResult(e);
				}
			},
		);

		this.server.tool(
			"edit_reel_post",
			"✏️ Edit a not-yet-published post's caption and/or scheduled time, by its numeric id. LinkedIn has no way to edit a post that's already live - this will refuse with an error for a POSTED post; delete_reel_post it and publish_reel a new one instead. Changing scheduledTime on an already-scheduled post correctly re-registers the timer, it doesn't just relabel it. If you don't already have the numeric id (e.g. 'edit my last post's caption'), call list_posts first and use the matching post's id - don't ask the person to look up an id themselves.",
			{
				postId: z.number().describe("The post's numeric id - from list_posts, or a 'Post id: 28' line earlier in this conversation."),
				caption: z.string().optional().describe("New caption text, if changing it."),
				scheduledTime: z
					.string()
					.optional()
					.describe("New local datetime as YYYY-MM-DDTHH:MM, in the account's configured timezone. Must be in the future."),
			},
			async ({ postId, caption, scheduledTime }) => {
				try {
					const result = await editPost(backendEnv, postId, { caption, scheduledTime });
					return textResult(`${result.message}. Post id ${result.post.id}, status: ${result.post.status}, scheduled_time: ${result.post.scheduled_time ?? "n/a"}.`);
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
