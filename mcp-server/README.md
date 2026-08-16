# Reel Automation MCP server

A remote [Model Context Protocol](https://modelcontextprotocol.io/introduction) server
that lets Claude (Cowork, claude.ai, Claude Desktop) drive the Reel Automation app —
list reels, get caption suggestions, run the posting assistant, and schedule or
publish a post — without opening the web app.

Built on Cloudflare Workers using [`workers-oauth-provider`](https://github.com/cloudflare/workers-oauth-provider),
following [Cloudflare's remote MCP + OAuth pattern](https://developers.cloudflare.com/agents/model-context-protocol/guides/remote-mcp-server/).
Free tier: no idle-sleep, unlike Render's free web services.

## What it is not

This does **not** give every GitHub user access to your LinkedIn account. Two
separate things are true at once:

- **GitHub OAuth** gates *who may call these tools at all* — only usernames in
  `ALLOWED_GITHUB_USERNAMES` get real tools; everyone else gets a single
  `not_authorized` tool explaining why.
- Every tool call, from any allowed caller, acts as **one fixed backend account**
  — `BACKEND_USER_ID` — using the Flask API's own bearer-token auth
  (`BACKEND_API_KEY`, the same `API_ACCESS_KEY` the rest of the app uses). There
  is no per-caller identity mapping into the app's own user model.

`publish_reel` is a real, irreversible publish to a real LinkedIn profile. Its
tool description says so; nothing here prompts for a second confirmation
beyond whatever the calling client does.

## Tools

| Tool | Does |
|---|---|
| `list_reels` | Uploaded reels available to post |
| `suggest_captions` | Three caption drafts from a one-line brief |
| `draft_post` | Talks to the same composer the web app's Assistant uses — picks a reel, writes a caption, proposes a time. Fills a draft only; never publishes |
| `schedule_reel` | Creates a post and schedules it for a future time |
| `publish_reel` | Creates a post and **publishes it to LinkedIn immediately** |

## Setup

### 1. GitHub OAuth App

Create one at [github.com/settings/developers](https://github.com/settings/developers):

- Homepage URL: `https://reel-automation-mcp.<your-subdomain>.workers.dev`
- Authorization callback URL: `https://reel-automation-mcp.<your-subdomain>.workers.dev/callback`

### 2. KV namespace

```bash
npx wrangler kv namespace create OAUTH_KV
```

Paste the returned id into `wrangler.jsonc`'s `kv_namespaces[0].id`.

### 3. Secrets

```bash
npx wrangler secret put GITHUB_CLIENT_ID
npx wrangler secret put GITHUB_CLIENT_SECRET
npx wrangler secret put COOKIE_ENCRYPTION_KEY        # openssl rand -hex 32
npx wrangler secret put BACKEND_API_URL              # e.g. https://social-media-manager-api-wk5g.onrender.com
npx wrangler secret put BACKEND_API_KEY              # same value as API_ACCESS_KEY on the Render service
npx wrangler secret put BACKEND_USER_ID              # the numeric id of the LinkedIn-connected account to act as
npx wrangler secret put ALLOWED_GITHUB_USERNAMES     # comma-separated GitHub usernames, e.g. "you,teammate"
```

### 4. Deploy

```bash
npm install
npx wrangler deploy
```

### 5. Register as a connector

In Claude Cowork or claude.ai's connector settings, add:

```
https://reel-automation-mcp.<your-subdomain>.workers.dev/mcp
```

The first connection triggers the GitHub OAuth flow; only allowlisted usernames
get real tools past that point.

## Local development

```bash
npx wrangler dev
```

Needs a second GitHub OAuth App with callback `http://localhost:8788/callback`,
and a `.dev.vars` file (gitignored) with the same secrets as above, plus
`GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` for the local app. Point it at the
Render backend or a local `python -m backend.app` via `BACKEND_API_URL`.

Test with the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector@latest
```

Enter `http://localhost:8788/mcp` and connect.
