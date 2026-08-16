# Post Pilot MCP server

A remote [Model Context Protocol](https://modelcontextprotocol.io/introduction) server
that lets Claude (Cowork, claude.ai, Claude Desktop) drive the Post Pilot app —
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

**[👉 Follow SETUP.md](SETUP.md)** for step-by-step instructions.

Takes 15 minutes. Covers:
- Cloudflare login & KV namespace
- GitHub OAuth app creation
- Setting 7 secrets
- Deploying the Worker
- Registering in Claude Code / Desktop / Cowork

## Local development

```bash
npx wrangler dev
```

Needs a second GitHub OAuth App with callback `http://localhost:8788/callback`,
and a `.dev.vars` file (gitignored) with the same secrets listed in SETUP.md.

Test with the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector@latest
```

Enter `http://localhost:8788/mcp` and connect.
