/**
 * Thin client for the Reel Automation Flask API.
 *
 * The Worker authenticates as a "machine caller" — a bearer token
 * (BACKEND_API_KEY) with no session — which the backend already supports on
 * every route that takes an explicit user_id (see backend/utils/security.py,
 * require_user_access). BACKEND_USER_ID is fixed per deployment: this
 * connector always acts as the one LinkedIn-connected account it is
 * configured for, never on behalf of whoever happens to be signed in via
 * GitHub. GitHub OAuth gates *who may call these tools at all*; it has no
 * relationship to the backend's own user model.
 */

export interface BackendEnv {
	BACKEND_API_URL: string;
	BACKEND_API_KEY: string;
	BACKEND_USER_ID: string;
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
