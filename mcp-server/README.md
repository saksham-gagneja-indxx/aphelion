# Post Pilot MCP Server

**Let Claude manage your social media.** 📱

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that connects Claude to Post Pilot, giving Claude the power to:

- 📋 **List your reels** — see what's available to post
- ✍️ **Generate captions** — AI-powered caption suggestions from a brief
- 📝 **Draft posts** — multi-turn conversations with Claude for full post composition
- 📅 **Schedule reels** — set up posts for future times
- 🚀 **Publish immediately** — push reels live to LinkedIn (with confirmation)

Use it in **Claude Desktop**, **claude.ai**, or **Claude Code** to control Post Pilot entirely through conversation.

---

## Why This Matters

**No UI context switching.** Stay in Claude and say:
```
Schedule my latest reel for tomorrow at 9am with a caption about our new feature launch
```

Claude will:
1. List your reels
2. Draft a caption  
3. Schedule it
4. Confirm completion

All without leaving the chat.

---

## Quick Start

**Install in 5 minutes:** [👉 INSTALLATION.md](INSTALLATION.md)

**Technical details:** [👉 SETUP.md](SETUP.md)

---

## Built On

- [Cloudflare Workers](https://workers.cloudflare.com) — free, always-on (no idle sleep)
- [Model Context Protocol](https://modelcontextprotocol.io/) — Anthropic's open standard for tool integration
- [GitHub OAuth](https://docs.github.com/en/developers/apps/building-oauth-apps) — secure authentication
- [Post Pilot Backend API](https://github.com/saksham-gagneja-indxx/Social-Media-Manager)

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
