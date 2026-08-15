# Branching and deployment

## The branches

| Branch | Purpose | Deploys to |
|---|---|---|
| `main` | Production. Always deployable. | Render, automatically on push |
| `dev` | Integration. Where parallel work is merged and reviewed. | Nothing |

`main` is the GitHub default branch. `master` was renamed to `main` and deleted.

```
dev  ──●──●──●──┐
                 ├─ merge ─→  main  ──→  Render  ──→  live
feature ──●──●───┘
```

## Why not a branch per service

A branch per component (`backend`, `frontend`, `database`) was considered and
rejected. Two concrete reasons:

**They are one deployable unit.** The Dockerfile builds the SPA and the API
into a single image from a single commit. Split across branches, no commit
would represent a working system, and there would be nothing coherent to
deploy or roll back to.

**The API contract spans both.** When `/api/me` changes shape, the frontend
change must ship in the same commit. Separated, there is always a window where
production is broken, and a revert fixes only half of it.

Branches model *changes over time*, not *components*. For component isolation
the right tools are directories (already in use) or separate repositories.

## Working with parallel sessions

Two agents work on this repo concurrently and own different files:

| Owner | Files |
|---|---|
| Main session | `backend/**`, `frontend/src/api/{client,schedule,types,validation}.ts`, `Upload.tsx`, `Schedule.tsx`, deployment config |
| Antigravity | `App.tsx`, `main.tsx`, `components/**`, `Analytics.tsx`, `Settings.tsx`, `Queue.tsx`, `Admin.tsx`, `Login.tsx`, `api/auth.ts`, `api/admin.ts` |

The split exists so both can work without stepping on each other. When a change
crosses the boundary - a new endpoint plus the UI that calls it - agree the
response shape first, then each side builds to it. `docs/API.md` is the record
of those shapes.

## Everyday flow

```bash
# work on dev
git checkout dev
git pull
# ... make changes ...
git commit
git push

# ship it
git checkout main
git merge dev
git push            # Render deploys automatically
```

For anything risky, branch off `dev`, then merge back:

```bash
git checkout dev && git checkout -b fix/thing
# ... work ...
git checkout dev && git merge fix/thing
```

## Before merging into main

`main` deploys straight to production, so it should stay green.

```bash
pytest tests/ -q                    # backend
cd frontend && npx tsc --noEmit     # types
cd frontend && npx vitest run       # frontend
cd frontend && npm run build        # the build Docker will run
```

A failing build on `main` means the live service is running the previous image
until it is fixed - Render will not replace a healthy deploy with a broken one,
which is a useful safety net but not a substitute for checking first.

## Deployment specifics

- Render watches `main` and rebuilds on every push
- Builds run from `./Dockerfile` (multi-stage: Node builds the SPA, Python runs it)
- `/health` is the health check path
- Secrets live in Render's environment, never in the repo. `.env` is gitignored.
- Environment changes made in Render's dashboard trigger a redeploy on their own

## Rolling back

Render keeps previous deploys and can redeploy any of them from the dashboard -
faster than a git revert when production is broken, because it skips the build.

For a permanent revert:

```bash
git checkout main
git revert <bad-commit>
git push
```
