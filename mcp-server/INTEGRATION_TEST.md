# MCP Integration Test — 2026-08-18

## Could not run
- **Live MCP tool calls via the `post-pilot` connector** — this session has no interactive OAuth flow, and the connector needs GitHub authorization first. Fix: run `/mcp` (or the connector's settings) in an interactive session and authorize.
- **`wrangler deployments list` / secret inspection** — no `CLOUDFLARE_API_TOKEN` in this shell. Could not confirm which git commit is actually live, or read `ALLOWED_GITHUB_USERNAMES` (can't verify "two registered" logins without it).

## Tested directly (backend endpoints the tools call)
| Check | Result |
|---|---|
| `GET /api/users/15/reels` | 200, `{"count":0,"reels":[]}` — empty because Render's free tier has no persistent disk (known, pre-existing) |
| `POST /api/captions/suggest` | 200, real captions returned — confirms the earlier NVIDIA model-prefix 502 bug is still fixed |
| `GET /api/auth/linkedin/status?user_id=15` | `can_publish:false` despite `granted_scopes: ["openid,profile,w_member_social"]` and `token_expired:false` |
| `GET /api/users/by-github/<unmapped>` | 404, generic message — correct, doesn't leak account existence |

## Errors found

1. **`can_publish: false` for account 15 even though `w_member_social` is present.**
   Look at the scope value: `"openid,profile,w_member_social"` is stored as **one comma-joined string inside a single-element list**, not three separate scope strings. Whatever check backs `can_publish` (`w_member_social in granted_scopes`) is doing an exact-membership test against that list, so it never matches. This is a stored-format bug, not an expired/missing grant — re-connecting LinkedIn won't fix it unless the scope-parsing/storage is also fixed. **Needs a code fix in the backend** (wherever `granted_scopes`/`linkedin_scope` is parsed from LinkedIn's token response — likely splits on space but LinkedIn returned/stored it comma-joined, or it was stored pre-split incorrectly).

2. **Branch divergence: `main` does not have the multi-tenant / identity-line work.**
   `git log main..origin/feat/mcp-deployment` shows 9 unmerged commits, including `3851419` (identity line) and `c43e86b` (multi-tenant `resolveUserId`). The `mcp-server/src/index.ts` on `main` is still the original single-tenant version with none of `getLinkedInIdentity`/`identityLine`. If whatever deploys the live Worker builds from `main`, the identity-line feature the last session verified live is **not actually what's deployed now** — it only exists on the unmerged branch. Needs the user to decide: merge `feat/mcp-deployment` into `main`, or confirm deploys are pinned to that branch.

3. **CI secrets still stale** (carried over, unresolved): `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` in GitHub Actions need updating — still can't verify from here.

## Not tested (by design)
`publish_reel` / `schedule_reel` — both perform a real, irreversible LinkedIn action. Not invoked per standing instruction to never publish without your explicit live confirmation.
