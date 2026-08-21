# Publishing Aphelion MCP

Guide for publishing the Aphelion MCP to registries and making it globally discoverable.

---

## Option 1: Anthropic MCP Registry (Official)

The official registry at https://registry.modelcontextprotocol.io allows anyone to discover and use your MCP.

### Steps

1. **Fork Anthropic's MCP Registry**
   - https://github.com/modelcontextprotocol/servers
   - Click "Fork" → create your fork

2. **Add Your MCP Entry**
   - Clone your fork locally
   - Create file: `src/post-pilot.ts` with:

   ```typescript
   export const Aphelion: Implementation = {
     name: "aphelion",
     source: "https://github.com/saksham-gagneja-indxx/aphelion/tree/feat/mcp-deployment/mcp-server",
     description: "Control Aphelion social media management from Claude — list reels, draft posts, schedule uploads, publish to LinkedIn",
     repo: "https://github.com/saksham-gagneja-indxx/aphelion",
     tags: ["social-media", "linkedin", "posting", "ai-assistant"],
     author: "saksham-gagneja-indxx",
     homepage: "https://github.com/saksham-gagneja-indxx/aphelion",
     contact: "sgagneja@indxx.com",
     license: "MIT",
     requirements: ["cloudflare-account", "github-account", "aphelion-backend"],
     setupTimeEstimate: "5-15 minutes",
     type: "remote-http",
     transport: {
       type: "http",
       url: "https://post-pilot.{your-workers-subdomain}.workers.dev",
       authentication: {
         type: "oauth",
         provider: "github"
       }
     }
   };
   ```

3. **Update `src/servers.ts`**
   - Add: `import { Aphelion } from './post-pilot';`
   - Add to exports array: `Aphelion,`

4. **Create Pull Request**
   - Commit & push to your fork
   - Open PR to `modelcontextprotocol/servers` main
   - Title: "Add Aphelion MCP (social media management for Claude)"
   - Description:
     ```
     # Aphelion MCP
     
     **What:** Control Aphelion social media management entirely through Claude
     
     **Features:**
     - List uploaded reels
     - Generate AI captions
     - Draft posts with multi-turn conversation
     - Schedule posts for future times
     - Publish to LinkedIn immediately
     
     **Setup:** 5-15 minutes (Cloudflare + GitHub OAuth)
     
     **Demo:** Deploy to any Cloudflare Workers account using the installation guide
     ```

5. **Anthropic Reviews & Merges**
   - Review typically takes 1-2 weeks
   - Once merged, appears in the official registry

---

## Option 2: Self-Hosted Discovery (GitHub Releases)

Create a GitHub release so people can install directly from your repo.

### Steps

1. **Create GitHub Release**

   ```bash
   cd ~/aphelion
   git tag v1.0.0
   git push origin v1.0.0
   ```

   Then on GitHub:
   - Go to https://github.com/saksham-gagneja-indxx/aphelion/releases
   - Click "Draft a new release"
   - Choose tag: `v1.0.0`
   - Title: `Aphelion MCP v1.0.0 — Live`
   - Description:

   ```markdown
   # Aphelion MCP v1.0.0

   **Claude can now manage your social media!**

   The Aphelion MCP server is ready for production use. Deploy to Cloudflare Workers in 5 minutes.

   ## What's New

   - ✅ Full Cloudflare Workers deployment (free tier, no idle sleep)
   - ✅ GitHub OAuth authentication
   - ✅ 5 tools: list reels, suggest captions, draft posts, schedule, publish
   - ✅ Production-ready with error handling & logging
   - ✅ Comprehensive setup & troubleshooting guides

   ## Installation

   **[👉 Quick Start Guide](./mcp-server/INSTALLATION.md)**

   Takes 5-15 minutes. Needs:
   - Cloudflare account (free)
   - GitHub account
   - Aphelion backend running

   ## Try It

   Once deployed, ask Claude:
   ```
   List my reels
   ```

   Then:
   ```
   Draft a post about [your topic] and schedule it for tomorrow at 9am
   ```

   ## Docs

   - [INSTALLATION.md](./mcp-server/INSTALLATION.md) — Step-by-step setup
   - [SETUP.md](./mcp-server/SETUP.md) — Technical details
   - [README.md](./mcp-server/README.md) — Feature overview

   ## Support

   Questions? Open an issue or contact sgagneja@indxx.com

   ---

   **Deployed at:** https://aphelion.reel-automation-mcp.workers.dev
   ```

   - Click "Publish release"

2. **Announce on Social Media**

   Share on LinkedIn/Twitter:
   ```
   🚀 Aphelion MCP is live!

   Let Claude manage your LinkedIn posting. No UI switching — just ask Claude:
   "Schedule my latest reel for tomorrow at 9am"

   Deploy free on Cloudflare → takes 5 minutes.

   📖 Install: [link to INSTALLATION.md]
   🔗 Repo: [GitHub link]

   #Claude #MCP #LinkedIn #SocialMedia #AI
   ```

---

## Option 3: npm Package (Future)

Once stable, publish to npm:

```bash
npm publish --registry https://registry.npmjs.org/

# or as scoped package:
npm publish --registry https://registry.npmjs.org/ --scope @saksham-gagneja-indxx
```

Add to `package.json`:
```json
{
  "name": "@saksham-gagneja-indxx/aphelion-mcp",
  "version": "1.0.0",
  "description": "MCP server for controlling Aphelion social media management from Claude",
  "keywords": ["mcp", "claude", "social-media", "linkedin", "ai"],
  "repository": "https://github.com/saksham-gagneja-indxx/aphelion",
  "main": "dist/index.js"
}
```

Then users can install & deploy via:
```bash
npx @saksham-gagneja-indxx/aphelion-mcp deploy
```

---

## Metrics to Track

Once published, monitor:

- **GitHub stars** — community interest
- **Deploy count** — how many people are using it
- **Issues/PRs** — feedback & contributions
- **MCP registry listing** — official recognition

---

## Promotion Checklist

- [ ] GitHub release published
- [ ] PR submitted to MCP registry
- [ ] Social media announcement (LinkedIn/Twitter)
- [ ] Update GitHub repo description to mention MCP
- [ ] Add MCP badge to README
- [ ] Documentation complete & polished

---

## MCP Registry Badge

Add to your main README.md:

```markdown
[![MCP Registry](https://img.shields.io/badge/MCP-Registry-blue)](https://registry.modelcontextprotocol.io/)
```

---

## Next Steps

1. **Immediate:** Publish GitHub release (Option 2 above)
2. **This week:** Submit to MCP registry (Option 1 above)
3. **Next month:** Monitor adoption & iterate based on feedback
4. **Future:** npm package (Option 3) when ready

---

## Questions?

- 📚 [MCP Registry Docs](https://modelcontextprotocol.io/)
- 🔧 [Cloudflare MCP Guide](https://developers.cloudflare.com/agents/model-context-protocol/)
- 💬 Contact: sgagneja@indxx.com
