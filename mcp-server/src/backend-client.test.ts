import { describe, expect, it, vi, beforeEach } from "vitest";
import {
	BackendError,
	deletePost,
	editPost,
	listPosts,
	normalizeBackendEnv,
	uploadReel,
	uploadReelFromUrl,
	type BackendEnv,
} from "./backend-client";

const env: BackendEnv = {
	BACKEND_API_URL: "https://backend.example.com",
	BACKEND_API_KEY: "test-key",
	BACKEND_USER_ID: "15",
};

describe("normalizeBackendEnv", () => {
	it("strips a UTF-8 BOM and surrounding whitespace from every field", () => {
		const dirty: BackendEnv = {
			BACKEND_API_URL: "﻿https://backend.example.com \n",
			BACKEND_API_KEY: " test-key﻿",
			BACKEND_USER_ID: "﻿15﻿",
		};
		expect(normalizeBackendEnv(dirty)).toEqual(env);
	});
});

describe("uploadReel", () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	// A minimal valid base64 payload standing in for real video bytes - the
	// size guard cares about the encoded string's length, not whether it
	// actually decodes to a playable video.
	const smallBase64 = Buffer.from("x".repeat(1000)).toString("base64");

	it("rejects an attachment over the decoded-size cap before ever calling fetch", async () => {
		const fetchSpy = vi.fn();
		vi.stubGlobal("fetch", fetchSpy);

		// ~30MB of raw bytes, comfortably over the 20MB cap.
		const hugeBase64 = Buffer.from("x".repeat(30 * 1024 * 1024)).toString("base64");

		await expect(
			uploadReel(env, { filename: "big.mp4", base64Data: hugeBase64 }),
		).rejects.toMatchObject({ status: 413 });
		expect(fetchSpy).not.toHaveBeenCalled();
	});

	it("rejects invalid base64 with a clean error, not a thrown TypeError", async () => {
		vi.stubGlobal("fetch", vi.fn());
		await expect(
			uploadReel(env, { filename: "bad.mp4", base64Data: "not-valid-base64!!!" }),
		).rejects.toBeInstanceOf(BackendError);
	});

	it("posts a multipart form with the decoded bytes and user id", async () => {
		const fetchSpy = vi.fn().mockResolvedValue(
			new Response(
				JSON.stringify({
					success: true,
					message: "ok",
					reel: { filename: "clip.mp4", path: "data/reels/15/clip.mp4", duration_seconds: 5, size_bytes: 750 },
				}),
				{ status: 201 },
			),
		);
		vi.stubGlobal("fetch", fetchSpy);

		const result = await uploadReel(env, { filename: "clip.mp4", base64Data: smallBase64 });

		expect(result.reel.filename).toBe("clip.mp4");
		expect(fetchSpy).toHaveBeenCalledTimes(1);
		const [url, init] = fetchSpy.mock.calls[0];
		expect(url).toBe("https://backend.example.com/api/upload");
		expect(init.method).toBe("POST");
		expect(init.headers.Authorization).toBe("Bearer test-key");
		expect(init.body).toBeInstanceOf(FormData);
		expect(init.body.get("user_id")).toBe("15");
		const file = init.body.get("file") as File;
		expect(file.name).toBe("clip.mp4");
		expect(file.size).toBe(1000);
	});

	it("surfaces the backend's error message on a non-2xx response", async () => {
		vi.stubGlobal(
			"fetch",
			vi.fn().mockResolvedValue(
				new Response(JSON.stringify({ error: "File is too small" }), { status: 400 }),
			),
		);
		await expect(
			uploadReel(env, { filename: "tiny.mp4", base64Data: smallBase64 }),
		).rejects.toMatchObject({ message: "File is too small", status: 400 });
	});
});

describe("uploadReelFromUrl", () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	const videoBytes = new Uint8Array(2000).fill(1);

	it("fetches the URL server-side and forwards it to /api/upload", async () => {
		const fetchSpy = vi.fn().mockImplementation((url: string) => {
			if (url === "https://cdn.example.com/clips/reel.mp4") {
				return Promise.resolve(
					new Response(videoBytes, {
						status: 200,
						headers: { "content-length": String(videoBytes.length) },
					}),
				);
			}
			if (url === "https://backend.example.com/api/upload") {
				return Promise.resolve(
					new Response(
						JSON.stringify({
							success: true,
							message: "ok",
							reel: { filename: "reel.mp4", path: "data/reels/15/reel.mp4", duration_seconds: 3, size_bytes: 2000 },
						}),
						{ status: 201 },
					),
				);
			}
			throw new Error(`unexpected fetch to ${url}`);
		});
		vi.stubGlobal("fetch", fetchSpy);

		const result = await uploadReelFromUrl(env, { url: "https://cdn.example.com/clips/reel.mp4" });

		expect(result.reel.filename).toBe("reel.mp4");
		expect(fetchSpy).toHaveBeenCalledTimes(2);
		const uploadCall = fetchSpy.mock.calls.find(([u]) => u === "https://backend.example.com/api/upload");
		expect(uploadCall).toBeTruthy();
		const uploadInit = uploadCall![1];
		expect(uploadInit.body.get("user_id")).toBe("15");
		const file = uploadInit.body.get("file") as File;
		expect(file.name).toBe("reel.mp4");
		expect(file.size).toBe(2000);
	});

	it("guesses the filename from the URL path when none is given", async () => {
		const fetchSpy = vi.fn().mockImplementation((url: string) => {
			if (url.includes("my_clip.mov")) {
				return Promise.resolve(new Response(videoBytes, { status: 200 }));
			}
			return Promise.resolve(
				new Response(JSON.stringify({ success: true, message: "ok", reel: { filename: "x", path: "x", duration_seconds: null, size_bytes: 2000 } }), { status: 201 }),
			);
		});
		vi.stubGlobal("fetch", fetchSpy);

		await uploadReelFromUrl(env, { url: "https://cdn.example.com/videos/my_clip.mov?token=abc" });

		const uploadCall = fetchSpy.mock.calls.find(([u]) => u === "https://backend.example.com/api/upload");
		const file = uploadCall![1].body.get("file") as File;
		expect(file.name).toBe("my_clip.mov");
	});

	it("rejects when the source URL is unreachable", async () => {
		vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));
		await expect(
			uploadReelFromUrl(env, { url: "https://cdn.example.com/gone.mp4" }),
		).rejects.toBeInstanceOf(BackendError);
	});

	it("rejects when the source URL doesn't return 2xx, without ever calling /api/upload", async () => {
		const fetchSpy = vi.fn().mockResolvedValue(new Response("not found", { status: 404 }));
		vi.stubGlobal("fetch", fetchSpy);

		await expect(
			uploadReelFromUrl(env, { url: "https://cdn.example.com/missing.mp4" }),
		).rejects.toMatchObject({ status: 400 });
		expect(fetchSpy).toHaveBeenCalledTimes(1);
	});

	it("rejects a declared content-length over the cap before downloading the body", async () => {
		const fetchSpy = vi.fn().mockResolvedValue(
			new Response(videoBytes, {
				status: 200,
				headers: { "content-length": String(200 * 1024 * 1024) },
			}),
		);
		vi.stubGlobal("fetch", fetchSpy);

		await expect(
			uploadReelFromUrl(env, { url: "https://cdn.example.com/huge.mp4" }),
		).rejects.toMatchObject({ status: 413 });
		expect(fetchSpy).toHaveBeenCalledTimes(1);
	});

	it("rewrites a Google Drive share link to the direct-download form before fetching", async () => {
		const fetchSpy = vi.fn().mockImplementation((url: string) => {
			if (url === "https://drive.google.com/uc?export=download&id=ABC123xyz") {
				return Promise.resolve(
					new Response(videoBytes, { status: 200, headers: { "content-type": "video/mp4" } }),
				);
			}
			if (url === "https://backend.example.com/api/upload") {
				return Promise.resolve(
					new Response(
						JSON.stringify({ success: true, message: "ok", reel: { filename: "reel.mp4", path: "x", duration_seconds: null, size_bytes: 2000 } }),
						{ status: 201 },
					),
				);
			}
			throw new Error(`unexpected fetch to ${url}`);
		});
		vi.stubGlobal("fetch", fetchSpy);

		await uploadReelFromUrl(env, {
			url: "https://drive.google.com/file/d/ABC123xyz/view?usp=sharing",
		});

		expect(fetchSpy).toHaveBeenCalledWith(
			"https://drive.google.com/uc?export=download&id=ABC123xyz",
		);
	});

	it("rejects an HTML response (share page or Drive virus-scan interstitial) instead of uploading it", async () => {
		const fetchSpy = vi.fn().mockResolvedValue(
			new Response("<html>not a video</html>", {
				status: 200,
				headers: { "content-type": "text/html; charset=utf-8" },
			}),
		);
		vi.stubGlobal("fetch", fetchSpy);

		await expect(
			uploadReelFromUrl(env, { url: "https://cdn.example.com/actually-a-page.mp4" }),
		).rejects.toMatchObject({ status: 400 });
		expect(fetchSpy).toHaveBeenCalledTimes(1);
	});
});

describe("deletePost", () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	it("POSTs to /api/posts/<id>/delete and returns the updated post", async () => {
		const fetchSpy = vi.fn().mockResolvedValue(
			new Response(
				JSON.stringify({ message: "Deleted", post: { id: 7, status: "cancelled", caption: null, scheduled_time: null, video_path: "x" } }),
				{ status: 200 },
			),
		);
		vi.stubGlobal("fetch", fetchSpy);

		const result = await deletePost(env, 7);

		expect(result.post.status).toBe("cancelled");
		const [url, init] = fetchSpy.mock.calls[0];
		expect(url).toBe("https://backend.example.com/api/posts/7/delete");
		expect(init.method).toBe("POST");
	});

	it("surfaces a 409 as a BackendError instead of throwing something opaque", async () => {
		vi.stubGlobal(
			"fetch",
			vi.fn().mockResolvedValue(
				new Response(JSON.stringify({ error: "This post was already deleted." }), { status: 409 }),
			),
		);
		await expect(deletePost(env, 7)).rejects.toMatchObject({
			message: "This post was already deleted.",
			status: 409,
		});
	});
});

describe("listPosts", () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	it("GETs the user's posts, newest first per the backend's own ordering", async () => {
		const fetchSpy = vi.fn().mockResolvedValue(
			new Response(
				JSON.stringify({
					count: 2,
					posts: [
						{ id: 12, status: "scheduled", caption: "newest", scheduled_time: "2099-01-01T10:00:00", video_path: "a.mp4" },
						{ id: 11, status: "posted", caption: "older", scheduled_time: null, video_path: "b.mp4" },
					],
				}),
				{ status: 200 },
			),
		);
		vi.stubGlobal("fetch", fetchSpy);

		const result = await listPosts(env);

		expect(result.posts[0].id).toBe(12);
		const [url] = fetchSpy.mock.calls[0];
		expect(url).toBe("https://backend.example.com/api/users/15/posts");
	});

	it("appends a status filter as a query param when given", async () => {
		const fetchSpy = vi.fn().mockResolvedValue(
			new Response(JSON.stringify({ count: 0, posts: [] }), { status: 200 }),
		);
		vi.stubGlobal("fetch", fetchSpy);

		await listPosts(env, "scheduled");

		const [url] = fetchSpy.mock.calls[0];
		expect(url).toBe("https://backend.example.com/api/users/15/posts?status=scheduled");
	});
});

describe("editPost", () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	it("PATCHes /api/posts/<id> with caption and scheduledTime", async () => {
		const fetchSpy = vi.fn().mockResolvedValue(
			new Response(
				JSON.stringify({ message: "Updated", post: { id: 9, status: "scheduled", caption: "new", scheduled_time: "2099-01-01T10:00:00", video_path: "x" } }),
				{ status: 200 },
			),
		);
		vi.stubGlobal("fetch", fetchSpy);

		const result = await editPost(env, 9, { caption: "new", scheduledTime: "2099-01-01T10:00" });

		expect(result.post.caption).toBe("new");
		const [url, init] = fetchSpy.mock.calls[0];
		expect(url).toBe("https://backend.example.com/api/posts/9");
		expect(init.method).toBe("PATCH");
		expect(JSON.parse(init.body)).toEqual({ caption: "new", scheduled_time: "2099-01-01T10:00" });
	});

	it("surfaces the backend's refusal to edit a published post", async () => {
		vi.stubGlobal(
			"fetch",
			vi.fn().mockResolvedValue(
				new Response(
					JSON.stringify({ error: "LinkedIn does not support editing a published post." }),
					{ status: 409 },
				),
			),
		);
		await expect(editPost(env, 9, { caption: "x" })).rejects.toMatchObject({ status: 409 });
	});
});
