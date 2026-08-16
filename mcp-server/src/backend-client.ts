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
