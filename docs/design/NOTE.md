# Archived from linkedin-posting-system-design

These files were migrated verbatim from the separate `linkedin-posting-system-design`
GitHub repo, which existed only to hold planning/design documentation with no
code of its own. They're kept here for historical reference.

**They describe the system as originally planned, not as it currently exists.**
For current, accurate documentation, see:

- [`LINKEDIN_SYSTEM_DESIGN_DOCS.md`](../../LINKEDIN_SYSTEM_DESIGN_DOCS.md) - current architecture, written after Google Drive integration, delete/edit, and list_posts shipped
- [`README.md`](../../README.md) and [`mcp-server/README.md`](../../mcp-server/README.md) - current setup and usage
- [`SECRETS_GUIDE.md`](../../SECRETS_GUIDE.md) - current secrets (the design repo had its own copy of this file with an older, stale `BACKEND_API_KEY` - deliberately not migrated to avoid two diverging copies of live secrets)

Known-stale in these archived files: `DATABASE_SCHEMA.md` and `API_ENDPOINTS.md`
predate several backend changes (e.g. the unified delete/edit routes in
`backend/api/publish_routes.py`); `SYSTEM_DESIGN.md` / `SYSTEM_ARCHITECTURE.md`
predate the Google Drive URL-upload fix and the multi-tenant MCP work.
