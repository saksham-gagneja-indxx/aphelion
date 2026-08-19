/**
 * Thin client for the Reel Automation Flask API.
 *
 * The Worker authenticates as a "machine caller" — a bearer token
 * (BACKEND_API_KEY) with no session — which the backend already supports on
 * every route that takes an explicit user_id (see backend/utils/security.py,
 * require_user_access).
 *
 * BACKEND_USER_ID in a BackendEnv is resolved PER SESSION, not read as a
 * fixed secret - see resolveUserId() and index.ts's init(), which looks up
 * the signed-in GitHub login against /api/users/by-github/<login> and builds
 * a BackendEnv carrying whichever account that login is mapped to. Multiple
 * people can use the same deployed connector, each acting as their own
 * backend account, rather than every GitHub sign-in acting as one hardcoded
 * user. ALLOWED_GITHUB_USERNAMES (see index.ts) is a separate, independent
 * gate on top of this - a GitHub login must both be allowlisted AND mapped
 * to an active account to get real tools instead of the not_authorized one.
 */

export interface BackendEnv {
	BACKEND_API_URL: string;
	BACKEND_API_KEY: string;
	BACKEND_USER_ID: string;
}

export interface ResolvedUser {
	id: number;
	name: string | null;
	role: string;
}

/**
 * Look up which backend account a GitHub login acts as.
 *
 * Returns null for "no mapping" or "account inactive" alike - deliberately
 * not distinguished to the MCP caller, same as the backend route itself
 * folds both into one 404 (see routes.py's user_by_github): a deactivated
 * account should look exactly like an unmapped one, not leak that it once
 * existed.
 */
export async function resolveUserId(
	env: Pick<BackendEnv, "BACKEND_API_URL" | "BACKEND_API_KEY">,
	githubLogin: string,
): Promise<ResolvedUser | null> {
	const res = await fetch(
		`${env.BACKEND_API_URL}/api/users/by-github/${encodeURIComponent(githubLogin)}`,
		{ headers: { Authorization: `Bearer ${env.BACKEND_API_KEY}` } },
	);
	if (res.status === 404) return null;
	if (!res.ok) {
		throw new BackendError(`Could not resolve GitHub identity (${res.status}).`, res.status);
	}
	return (await res.json()) as ResolvedUser;
}

export class BackendError extends Error {
	status: number;
	constructor(message: string, status: number) {
		super(message);
		this.status = status;
	}
}

/**
 * `wrangler secret put` has bitten this project twice: a value copy-pasted
 * from a source saved as "UTF-8 with BOM" (Windows Notepad's default) carries
 * an invisible U+FEFF at the front, which `wrangler secret put` uploads
 * byte-for-byte. That broke `new URL()` outright when it landed in
 * BACKEND_API_URL, and silently corrupted a path segment when it landed in
 * BACKEND_USER_ID - both shipped once already (see git history).
 *
 * Normalized once here, at the boundary where Cloudflare's raw env crosses
 * into this module (see index.ts's `backendEnv: BackendEnv = normalizeBackendEnv(this.env)`),
 * rather than at every call site - every function below can then trust
 * `BackendEnv`'s fields are clean. `.trim()` strips U+FEFF along with
 * ordinary whitespace per the WhiteSpace production in the ECMAScript spec,
 * so this is cheap insurance against the same class of mistake happening a
 * third time, not just a fix for the two it's already caused.
 */
export function normalizeBackendEnv(env: BackendEnv): BackendEnv {
	return {
		BACKEND_API_URL: env.BACKEND_API_URL.trim(),
		BACKEND_API_KEY: env.BACKEND_API_KEY.trim(),
		BACKEND_USER_ID: env.BACKEND_USER_ID.trim(),
	};
}

async function call<T>(
	env: BackendEnv,
	method: string,
	path: string,
	body?: unknown,
): Promise<T> {
	const res = await fetch(`${env.BACKEND_API_URL}${path}`, {
		method,
		headers: {
			Authorization: `Bearer ${env.BACKEND_API_KEY}`,
			"Content-Type": "application/json",
		},
		body: body === undefined ? undefined : JSON.stringify(body),
	});

	const text = await res.text();
	let json: any = null;
	try {
		json = text ? JSON.parse(text) : null;
	} catch {
		// non-JSON body, handled below via res.ok
	}

	if (!res.ok) {
		const message = json?.error || `Backend request failed (${res.status})`;
		throw new BackendError(message, res.status);
	}
	return json as T;
}

export interface Reel {
	filename: string;
	path: string;
	duration_seconds: number | null;
	size_bytes: number;
	has_thumbnail: boolean;
}

export const listReels = (env: BackendEnv) =>
	call<{ count: number; reels: Reel[] }>(
		env,
		"GET",
		`/api/users/${env.BACKEND_USER_ID}/reels`,
	);

/**
 * Cap on the DECODED size of an upload_reel attachment.
 *
 * Base64 has no way through this tool but as a plain string argument in the
 * tool call, which means it rides through the same context/payload budget as
 * everything else in the conversation - there is no separate binary channel.
 * 20MB decoded (~27MB of base64 text) is picked as a "short vertical clip"
 * ceiling, not a hard platform limit: it is comfortably clear of practical
 * tool-call size trouble while still fitting a real reel, not just a
 * few-second test clip.
 */
const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;

function base64ToBytes(base64: string): Uint8Array {
	const binary = atob(base64);
	const bytes = new Uint8Array(binary.length);
	for (let i = 0; i < binary.length; i++) {
		bytes[i] = binary.charCodeAt(i);
	}
	return bytes;
}

export interface UploadedReel {
	filename: string;
	path: string;
	duration_seconds: number | null;
	size_bytes: number;
}

/**
 * Upload a reel whose bytes arrived as a base64 tool argument - i.e. a file
 * attached directly in the chat, rather than one already sitting in the
 * user's reel library via the web app's own upload page (untouched by this:
 * it POSTs to the exact same /api/upload the web app uses).
 */
export async function uploadReel(
	env: BackendEnv,
	input: { filename: string; base64Data: string },
): Promise<{ success: true; message: string; reel: UploadedReel }> {
	// Roughly 4/3 expansion; checking the encoded string's length avoids
	// decoding a huge blob just to reject it.
	const approxBytes = (input.base64Data.length * 3) / 4;
	if (approxBytes > MAX_UPLOAD_BYTES) {
		throw new BackendError(
			`That file is too large to attach directly (~${Math.round(approxBytes / 1024 / 1024)}MB, ` +
				`limit is ${MAX_UPLOAD_BYTES / 1024 / 1024}MB). Trim the clip or upload it from the web app instead.`,
			413,
		);
	}

	let bytes: Uint8Array;
	try {
		bytes = base64ToBytes(input.base64Data);
	} catch {
		throw new BackendError("Could not decode the attached file - it was not valid base64.", 400);
	}

	const form = new FormData();
	form.append("user_id", env.BACKEND_USER_ID);
	form.append("file", new Blob([bytes], { type: "video/mp4" }), input.filename);

	const res = await fetch(`${env.BACKEND_API_URL}/api/upload`, {
		method: "POST",
		headers: { Authorization: `Bearer ${env.BACKEND_API_KEY}` },
		body: form,
	});

	const text = await res.text();
	let json: any = null;
	try {
		json = text ? JSON.parse(text) : null;
	} catch {
		// non-JSON body, handled below via res.ok
	}

	if (!res.ok) {
		const message = json?.error || `Upload failed (${res.status})`;
		throw new BackendError(message, res.status);
	}
	return json;
}

/**
 * Cap for a URL-sourced upload. Much higher than the base64 tool's cap
 * because nothing here rides through model-generated text or the
 * conversation's token budget - the Worker fetches the bytes directly and
 * streams them to the backend. The real ceiling is Workers' own memory
 * limit, not anything token-related; 100MB is comfortably under that while
 * covering any real reel.
 */
const MAX_URL_UPLOAD_BYTES = 100 * 1024 * 1024;

function filenameFromUrl(url: string): string {
	try {
		const path = new URL(url).pathname;
		const last = path.split("/").filter(Boolean).pop();
		if (last && /\.[a-z0-9]{2,4}$/i.test(last)) return last;
	} catch {
		// fall through to the default below
	}
	return "reel.mp4";
}

/**
 * Upload a reel by having the Worker fetch it server-side from a direct,
 * publicly (or presigned-privately) reachable URL - the counterpart to
 * uploadReel() for files too large to pass through as base64. The model
 * never sees or generates the binary content; it only ever handles a URL
 * string, so there is no context/tool-call size limit tied to the video's
 * size, only this function's own byte cap.
 */
export async function uploadReelFromUrl(
	env: BackendEnv,
	input: { url: string; filename?: string },
): Promise<{ success: true; message: string; reel: UploadedReel }> {
	let sourceRes: Response;
	try {
		sourceRes = await fetch(input.url);
	} catch (e) {
		throw new BackendError(
			`Could not fetch that URL: ${e instanceof Error ? e.message : String(e)}`,
			400,
		);
	}

	if (!sourceRes.ok) {
		throw new BackendError(
			`That URL returned HTTP ${sourceRes.status}. It needs to be a direct link to the video ` +
				`file itself (not a share/preview page) and publicly reachable without login.`,
			400,
		);
	}

	const declaredLength = sourceRes.headers.get("content-length");
	if (declaredLength && Number(declaredLength) > MAX_URL_UPLOAD_BYTES) {
		throw new BackendError(
			`That file is too large (~${Math.round(Number(declaredLength) / 1024 / 1024)}MB, ` +
				`limit is ${MAX_URL_UPLOAD_BYTES / 1024 / 1024}MB).`,
			413,
		);
	}

	const blob = await sourceRes.blob();
	if (blob.size > MAX_URL_UPLOAD_BYTES) {
		throw new BackendError(
			`That file is too large (~${Math.round(blob.size / 1024 / 1024)}MB, ` +
				`limit is ${MAX_URL_UPLOAD_BYTES / 1024 / 1024}MB).`,
			413,
		);
	}

	const filename = input.filename || filenameFromUrl(input.url);

	const form = new FormData();
	form.append("user_id", env.BACKEND_USER_ID);
	form.append("file", blob, filename);

	const res = await fetch(`${env.BACKEND_API_URL}/api/upload`, {
		method: "POST",
		headers: { Authorization: `Bearer ${env.BACKEND_API_KEY}` },
		body: form,
	});

	const text = await res.text();
	let json: any = null;
	try {
		json = text ? JSON.parse(text) : null;
	} catch {
		// non-JSON body, handled below via res.ok
	}

	if (!res.ok) {
		const message = json?.error || `Upload failed (${res.status})`;
		throw new BackendError(message, res.status);
	}
	return json;
}

export interface LinkedInIdentity {
	connected: boolean;
	email: string | null;
	person_urn: string | null;
	can_publish: boolean;
}

/**
 * Which LinkedIn account this session's tool calls would actually publish
 * to, if anything got called.
 *
 * Added specifically because a caller with no other way to verify identity
 * (an MCP client only ever sees this backend through this API, never a
 * dashboard) has no path to trust "this session acts as account N" without
 * it - "trust me" from an assistant relaying an unverifiable claim is
 * exactly the failure mode that should be refused, not talked past. Real
 * identity data has to come from a tool response, not a conversational
 * assertion.
 */
export const getLinkedInIdentity = (env: BackendEnv) =>
	call<LinkedInIdentity>(
		env,
		"GET",
		`/api/auth/linkedin/status?user_id=${env.BACKEND_USER_ID}`,
	);

export const suggestCaptions = (
	env: BackendEnv,
	input: { brief: string; reelFilename?: string; durationSeconds?: number },
) =>
	call<{ captions: { angle: string; text: string }[]; used_thumbnail: boolean }>(
		env,
		"POST",
		"/api/captions/suggest",
		{
			brief: input.brief,
			reel_filename: input.reelFilename,
			duration_seconds: input.durationSeconds,
			user_id: env.BACKEND_USER_ID,
		},
	);

export interface ComposerDraft {
	reel_filename: string | null;
	caption: string | null;
	angle: string | null;
	when: string | null;
}

export const composerTurn = (
	env: BackendEnv,
	input: {
		messages: { role: "user" | "assistant"; content: string }[];
		draft?: ComposerDraft | null;
	},
) =>
	call<{ reply: string; draft: ComposerDraft; ready: boolean; actions: string[] }>(
		env,
		"POST",
		"/api/composer/turn",
		{
			messages: input.messages,
			draft: input.draft ?? null,
			user_id: env.BACKEND_USER_ID,
		},
	);

export interface Post {
	id: number;
	status: string;
	caption: string | null;
	scheduled_time: string | null;
	video_path: string;
}

export const createPost = (
	env: BackendEnv,
	input: { videoPath: string; caption?: string; aiGeneratedCaption?: boolean },
) =>
	call<Post>(env, "POST", "/api/posts", {
		user_id: env.BACKEND_USER_ID,
		video_path: input.videoPath,
		caption: input.caption ?? null,
		ai_generated_caption: input.aiGeneratedCaption ?? false,
		platform: "linkedin",
	});

export const schedulePost = (env: BackendEnv, postId: number, scheduledTime: string) =>
	call<{ success: true; job_id: string; post: Post }>(
		env,
		"POST",
		`/api/posts/${postId}/schedule`,
		{ scheduled_time: scheduledTime },
	);

export const publishNow = (env: BackendEnv, postId: number) =>
	call<{ message: string; post: Post; url: string; platform_post_id: string }>(
		env,
		"POST",
		`/api/posts/${postId}/publish`,
	);
