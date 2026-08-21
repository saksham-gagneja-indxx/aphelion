import type { AuthRequest, OAuthHelpers } from "@cloudflare/workers-oauth-provider";
import { Hono } from "hono";
import {
	addApprovedClient,
	bindStateToSession,
	createOAuthState,
	generateCSRFProtection,
	isClientApproved,
	OAuthError,
	renderApprovalDialog,
	validateCSRFToken,
	validateOAuthState,
} from "./workers-oauth-utils";

/**
 * Identity handed to MyMCP as this.props once the connector is authorized.
 * Carries the backend account directly - no separate GitHub-login-to-account
 * resolution step exists in this flow, unlike the login-carries-nothing-but-
 * a-username shape a third-party OAuth handler would produce.
 */
export type SiteProps = {
	userId: number;
	name: string;
	role: string;
};

const app = new Hono<{ Bindings: Env & { OAUTH_PROVIDER: OAuthHelpers } }>();

/**
 * Same approval dialog as any OAuth provider ("does Claude get to talk to
 * this server at all") - unrelated to WHO is signing in, which is what
 * makes this reusable unchanged from the GitHub-based flow it replaces.
 */
app.get("/authorize", async (c) => {
	const oauthReqInfo = await c.env.OAUTH_PROVIDER.parseAuthRequest(c.req.raw);
	const { clientId } = oauthReqInfo;
	if (!clientId) {
		return c.text("Invalid request", 400);
	}

	if (await isClientApproved(c.req.raw, clientId, c.env.COOKIE_ENCRYPTION_KEY)) {
		const { stateToken } = await createOAuthState(oauthReqInfo, c.env.OAUTH_KV);
		const { setCookie: sessionBindingCookie } = await bindStateToSession(stateToken);
		return redirectToSite(c.req.raw, c.env, stateToken, { "Set-Cookie": sessionBindingCookie });
	}

	const { token: csrfToken, setCookie } = generateCSRFProtection();

	return renderApprovalDialog(c.req.raw, {
		client: await c.env.OAUTH_PROVIDER.lookupClient(clientId),
		csrfToken,
		server: {
			description:
				"Lets Claude list your reels, draft LinkedIn posts, and schedule or publish them. You'll sign in on the Aphelion website - no GitHub account needed.",
			logo: "https://postpilot-sandy.vercel.app/logo.png",
			name: "Aphelion",
		},
		setCookie,
		state: { oauthReqInfo },
	});
});

app.post("/authorize", async (c) => {
	try {
		const formData = await c.req.raw.formData();
		validateCSRFToken(formData, c.req.raw);

		const encodedState = formData.get("state");
		if (!encodedState || typeof encodedState !== "string") {
			return c.text("Missing state in form data", 400);
		}

		let state: { oauthReqInfo?: AuthRequest };
		try {
			state = JSON.parse(atob(encodedState));
		} catch (_e) {
			return c.text("Invalid state data", 400);
		}

		if (!state.oauthReqInfo || !state.oauthReqInfo.clientId) {
			return c.text("Invalid request", 400);
		}

		const approvedClientCookie = await addApprovedClient(
			c.req.raw,
			state.oauthReqInfo.clientId,
			c.env.COOKIE_ENCRYPTION_KEY,
		);

		const { stateToken } = await createOAuthState(state.oauthReqInfo, c.env.OAUTH_KV);
		const { setCookie: sessionBindingCookie } = await bindStateToSession(stateToken);

		const headers = new Headers();
		headers.append("Set-Cookie", approvedClientCookie);
		headers.append("Set-Cookie", sessionBindingCookie);

		return redirectToSite(c.req.raw, c.env, stateToken, Object.fromEntries(headers));
	} catch (error: any) {
		console.error("POST /authorize error:", error);
		if (error instanceof OAuthError) {
			return error.toResponse();
		}
		return c.text(`Internal server error: ${error.message}`, 500);
	}
});

/**
 * Sends the browser to the WEBSITE instead of a third-party OAuth screen.
 * `return_to` is this Worker's own callback - the website redirects there
 * once the person has approved, with `state` and a signed `grant` (see
 * backend/api/auth_routes.py's mcp_authorize_connector) appended. Passing it
 * explicitly rather than hardcoding it on the website's side keeps this
 * Worker's own URL out of the website's configuration entirely.
 */
function redirectToSite(
	request: Request,
	env: Env,
	stateToken: string,
	headers: Record<string, string> = {},
) {
	const site = new URL("/mcp-authorize", env.WEBSITE_URL);
	site.searchParams.set("state", stateToken);
	site.searchParams.set("return_to", new URL("/callback", request.url).href);

	return new Response(null, {
		headers: { ...headers, location: site.href },
		status: 302,
	});
}

/**
 * Callback endpoint - reached when the website redirects back after the
 * person approved. Same state/session-binding validation as the GitHub-based
 * flow (proves this browser is the one that started the request); the
 * difference is what proves IDENTITY - a signed grant from our own backend
 * instead of an upstream token exchange with a third party.
 */
app.get("/callback", async (c) => {
	let oauthReqInfo: AuthRequest;
	let clearSessionCookie: string;

	try {
		const result = await validateOAuthState(c.req.raw, c.env.OAUTH_KV);
		oauthReqInfo = result.oauthReqInfo;
		clearSessionCookie = result.clearCookie;
	} catch (error: any) {
		if (error instanceof OAuthError) {
			return error.toResponse();
		}
		return c.text("Internal server error", 500);
	}

	if (!oauthReqInfo.clientId) {
		return c.text("Invalid OAuth request data", 400);
	}

	const workerState = c.req.query("state");
	const grant = c.req.query("grant");
	if (!workerState || !grant) {
		return c.text("Missing state or grant", 400);
	}

	const verifyRes = await fetch(`${c.env.BACKEND_API_URL}/api/mcp/verify-connector-grant`, {
		method: "POST",
		headers: {
			Authorization: `Bearer ${c.env.BACKEND_API_KEY}`,
			"Content-Type": "application/json",
		},
		body: JSON.stringify({ grant, worker_state: workerState }),
	});
	if (!verifyRes.ok) {
		return c.text("Could not verify authorization with the backend", 401);
	}
	const account = (await verifyRes.json()) as { id: number; name: string; role: string };

	const { redirectTo } = await c.env.OAUTH_PROVIDER.completeAuthorization({
		metadata: {
			label: account.name,
		},
		// Available on this.props inside MyMCP.
		props: {
			userId: account.id,
			name: account.name,
			role: account.role,
		} as SiteProps,
		request: oauthReqInfo,
		scope: oauthReqInfo.scope,
		userId: String(account.id),
	});

	const headers = new Headers({ Location: redirectTo });
	if (clearSessionCookie) {
		headers.set("Set-Cookie", clearSessionCookie);
	}

	return new Response(null, { status: 302, headers });
});

export { app as SiteHandler };
