# LinkedIn Posting System - Design & Implementation

Complete documentation for POST_PILOT: a production-ready LinkedIn social media automation system powered by Claude AI.

This repository contains both the **original system design** and the **complete implementation** (MCP Server).

---

## 🚀 Quick Start

**For Users:** [→ MCP_INSTALLATION.md](MCP_INSTALLATION.md) (5-minute setup)  
**For Developers:** [→ SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) (Architecture & implementation)  
**For Architects:** [→ Original Design Docs](#original-design-documentation) (Below)

---

## 📦 POST_PILOT Implementation

POST_PILOT is a **production-ready MCP server** that integrates Claude with LinkedIn automation.

### What's Included
- **MCP_INSTALLATION.md** — Installation guide for Claude Desktop/Web/Code
- **MCP_SERVER_README.md** — Tool reference and usage examples
- **MCP_SETUP.md** — Cloudflare Worker configuration
- **SYSTEM_DESIGN.md** — Complete technical architecture including:
  - Google Drive integration details
  - Backend API design (Flask)
  - Security model & authentication
  - All 7 available MCP tools with examples
  - Troubleshooting guide

### Features
✅ Upload videos from Google Drive directly to Claude  
✅ AI-powered caption generation  
✅ Schedule posts for optimal timing  
✅ Publish immediately with one command  
✅ Two-factor authentication (GitHub OAuth + bearer token)  
✅ Server-side video processing (no chat limits)  
✅ Production-ready on Cloudflare Workers

### Deployment Status
- ✅ MCP Server live on Cloudflare Workers
- ✅ Backend API running on Render
- ✅ Database: Supabase PostgreSQL
- ✅ Storage: AWS S3
- ✅ Published to npm: [@sakshamgagneja/post-pilot-mcp](https://www.npmjs.com/package/@sakshamgagneja/post-pilot-mcp)
- ✅ Listed in [MCP Server Registry](https://registry.modelcontextprotocol.io/)

---

## 📚 Documentation Structure

### Implementation (POST_PILOT)
| Document | Purpose |
|----------|---------|
| [MCP_INSTALLATION.md](MCP_INSTALLATION.md) | 5-minute setup for Claude |
| [MCP_SERVER_README.md](MCP_SERVER_README.md) | Features, tools, and examples |
| [MCP_SETUP.md](MCP_SETUP.md) | Technical configuration |
| [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) | Complete architecture & API |

### Original Design Documentation
| Document | Purpose |
|----------|---------|
| [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | Original system design |
| [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) | Database design with SQL |
| [API_ENDPOINTS.md](API_ENDPOINTS.md) | REST API specification |
| [DESIGN_SUMMARY.md](DESIGN_SUMMARY.md) | Executive summary |

---

## 📖 Original Design Documentation

## Quick Overview

### User Flow

**Setup (One-time, ~5 minutes):**
```
User → Login (Clerk) → Connect LinkedIn (OAuth) → Ready
```

**Daily Usage:**
```
Upload video → Get captions → Say "Post it!" → Published
```

**Scheduling:**
```
"Post tomorrow at 10 AM" → Backend queues → Auto-posts
```

## Implementation Roadmap

- **Phase 1** (Weeks 1-2): Foundation - Database, Flask setup, auth
- **Phase 2** (Weeks 3-4): LinkedIn OAuth, encryption, token management
- **Phase 3** (Weeks 5-6): Media upload, caption generation
- **Phase 4** (Weeks 7-8): Post publishing, scheduling, job scheduler
- **Phase 5** (Weeks 9-10): Dashboard UI (React, Clerk integration)
- **Phase 6** (Weeks 11-12): MCP integration with Claude
- **Phase 7** (Weeks 13-14): Testing, security audit, deployment

**Total Effort:** 109-145 hours (~3-4 months, one developer)

## Key Features

✅ One-time setup (5 minutes)  
✅ Encrypted credential storage (Fernet AES-128)  
✅ No passwords stored by us (OAuth only)  
✅ AI caption generation via Claude  
✅ Immediate publishing to LinkedIn  
✅ Post scheduling with timezone support  
✅ Audit logging of all actions  
✅ 3-layer authentication  

## Security

- **Layer 1**: Clerk OAuth (user login)
- **Layer 2**: JWT session tokens (API access)
- **Layer 3**: Bearer tokens (MCP access)

Credentials encrypted at rest, decrypted only when posting, auto-refresh on expiration.

## Technology Stack

- **Frontend**: React/Next.js, Tailwind CSS, Clerk Auth
- **Backend**: Python Flask, SQLAlchemy ORM
- **Database**: PostgreSQL (prod) / SQLite (dev)
- **Encryption**: Fernet AES-128
- **MCP**: TypeScript on Cloudflare Workers
- **Storage**: AWS S3 or local filesystem
- **Auth**: Clerk
- **Deployment**: Render (backend), Vercel (frontend), Cloudflare (MCP)

## Status

Design phase: ✅ COMPLETE

Ready for:
1. Stakeholder approval
2. Phase 1 implementation
3. Team allocation

---

**Created**: 2026-08-18  
**Version**: 1.0  
**Author**: Design Team

For questions or feedback, refer to the specific design documents above.
