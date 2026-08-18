import { describe, expect, it, vi, beforeEach } from "vitest";
import {
	BackendError,
	normalizeBackendEnv,
	resolveUserId,
	uploadReel,
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

describe("resolveUserId", () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	it("returns the resolved user on a 200", async () => {
		vi.stubGlobal(
			"fetch",
			vi.fn().mockResolvedValue(
				new Response(JSON.stringify({ id: 15, name: "Ada", role: "admin" }), {
					status: 200,
				}),
			),
		);
		const result = await resolveUserId(env, "ada");
		expect(result).toEqual({ id: 15, name: "Ada", role: "admin" });
	});

	it("returns null for an unmapped login (404), not an error", async () => {
		vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 404 })));
		const result = await resolveUserId(env, "nobody");
		expect(result).toBeNull();
	});

	it("throws BackendError on a real backend failure", async () => {
		vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 500 })));
		await expect(resolveUserId(env, "ada")).rejects.toBeInstanceOf(BackendError);
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
