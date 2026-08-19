# GitHub Actions Workflows

Three workflows, matching how this project is actually deployed:

- **Render** and **Vercel** auto-deploy the backend and frontend on every
  push to `main` via their own native GitHub integration - not through
  anything in this directory.
- **Cloudflare Workers** (the MCP server) has no such native integration,
  so `deploy-mcp.yml` is what deploys it.

## ci.yml — Continuous Integration

Runs on every push/PR to `main` or `develop`.

- Backend lint (flake8) + type check (mypy, informational only - not gated)
- Frontend lint (ESLint) + type check
- Backend unit tests (pytest, plain file-based SQLite - no service
  container needed)
- Frontend unit tests (vitest)
- Dependency vulnerability scan (Trivy → SARIF → Security tab)

## codeql.yml — CodeQL Analysis

Static analysis for the Security tab's code scanning alerts. Scheduled and
on push/PR to `main`.

## deploy-mcp.yml — Deploy MCP to Cloudflare Workers

Runs on pushes to `main` that touch `mcp-server/**`. Type-checks, then
deploys via `wrangler deploy`. Needs `CLOUDFLARE_API_TOKEN` and
`CLOUDFLARE_ACCOUNT_ID` set as repository secrets.

## Debugging a failed run

1. Open the failed job in the Actions tab and expand the failed step.
2. `ci.yml`'s mypy and ESLint/type-check steps are non-blocking
   (`|| true` / `continue-on-error`) - a genuinely broken build will fail
   at pytest, the frontend build, or the Trivy scan instead.
3. If `deploy-mcp.yml` fails on the deploy step, check that the two
   Cloudflare secrets above are still valid (`npx wrangler whoami` locally
   with the same token is the fastest way to confirm).
