# Reel Automation MCP - User Guide

Welcome to **Reel Automation** – your AI-powered LinkedIn reel management assistant!

## Quick Start (2 minutes)

### 1. Connect the MCP to Claude
1. Open Claude Code or Claude.ai
2. Go to **Settings → MCP Servers**
3. Click **+ Add MCP Server**
4. Name: `Reel Automation`
5. Select **GitHub Login** authentication
6. Follow the GitHub OAuth flow
7. ✅ Connected!

### 2. See What You Can Do
Once connected, type:
```
Can you show me what I can do?
```

Or ask Claude directly:
```
What commands are available?
```

Claude will suggest the available tools and help you get started.

---

## Available Commands

### 📽️ **list_reels**
**See all your uploaded reels ready to post**

Shows:
- Filename of each reel
- Duration (in seconds)
- File size

**Use when:**
- You want to see what's available to post
- You're planning which video to use

**Example:**
```
Claude, show me all my available reels
```

---

### ✍️ **suggest_captions**
**Get 3 AI-drafted LinkedIn captions**

Provide:
- A brief description of what the reel shows
- (Optional) The exact filename from list_reels
- (Optional) Duration in seconds

Gets:
- 3 different caption angles
- Each with a unique perspective/tone

**Use when:**
- You need caption ideas fast
- You want multiple angles to choose from

**Example:**
```
Claude, I have a reel about AI in healthcare. 
Please suggest captions for it.
```

**Pro tip:** Be specific about content since AI doesn't watch the video!

---

### 💬 **draft_post**
**Chat with AI to plan a complete post**

Tell Claude:
- What you want to post about
- When you want to post it
- Any specific requirements

Claude will:
- Pick the best reel for you
- Write a caption
- Suggest optimal posting time
- Let you refine everything in conversation

**Use when:**
- You want end-to-end help planning
- You're not sure which reel to use
- You want AI to write and pick everything

**Example:**
```
Claude, I want to post about my latest 
AI project update tomorrow at 9am. Can you help me pick a reel and write a caption?
```

**Multi-turn:** Keep chatting with Claude to refine the draft until it's perfect!

---

### 🚀 **publish_reel**
**Publish a reel to LinkedIn RIGHT NOW**

⚠️ **WARNING:** This is **LIVE and IRREVERSIBLE**

Requires:
- Reel file path (from list_reels or draft_post)
- Caption text
- Your explicit confirmation

Always check:
- The "Publishing as" line showing your LinkedIn account
- Reel and caption before confirming

**Use when:**
- You've finalized your post
- You want to publish immediately
- You're 100% sure about the content

**Example:**
```
Claude, publish this reel to LinkedIn right now:
- Reel: my-ai-demo.mp4
- Caption: [your caption text]
```

---

### ⏰ **schedule_reel**
**Schedule a reel to post later**

Provide:
- Reel file path
- Caption
- When to post (e.g., "tomorrow at 9am", "next Monday at 2pm")

System will:
- Save the post as a draft
- Automatically publish at the scheduled time
- Post to your LinkedIn account

**Use when:**
- You want to batch-plan posts
- You need to post at specific times
- You want a safety net before publishing

**Example:**
```
Claude, schedule this reel:
- Reel: product-demo.mp4
- Caption: Check out our new feature!
- Time: Thursday at 10am
```

---

## Recommended Workflow

### The Safe Path 🛡️

1. **See what you have**
   ```
   list_reels
   ```

2. **Plan your post**
   ```
   draft_post - I want to post about [topic] [when]
   ```

3. **Refine with Claude**
   - Chat back-and-forth until perfect
   - Review the draft

4. **Schedule or publish**
   ```
   schedule_reel (safer, batch-friendly) 
   OR 
   publish_reel (if you're ready NOW)
   ```

---

## Tips & Tricks

### ⚡ Save Time
- Use `draft_post` to handle everything in one conversation
- Let AI pick the best reel for your topic
- Get captions without separate tool calls

### 🎯 Get Better Results
- Be specific about your reel content in descriptions
- Include context (e.g., "it's a demo of our new feature")
- Tell Claude your LinkedIn audience/style

### 🔍 Check Before Publishing
- Always read the "Publishing as" line
- Review the caption before confirming
- Use `schedule_reel` if you're unsure

### 📋 Batch Planning
- Schedule 3-5 posts at once
- Plan a week's content in one session
- Let the system publish automatically

---

## Common Questions

### Q: Can I edit a post after scheduling?
A: Not yet. Schedule only when you're happy with the content.

### Q: What if I publish by mistake?
A: LinkedIn deletes are permanent. Be careful with `publish_reel`!

### Q: Can I see scheduled posts?
A: Check your LinkedIn dashboard. They'll appear as scheduled.

### Q: Can I use the same reel multiple times?
A: Yes! You can post the same video with different captions.

### Q: Who sees "Publishing as: [account]"?
A: Only you (and Claude). LinkedIn users just see your post.

### Q: Can I publish to multiple accounts?
A: Not in this version. Each account gets their own connection.

---

## Troubleshooting

### "This GitHub account is not authorized"
→ Ask the admin to add your GitHub username to ALLOWED_GITHUB_USERNAMES

### "No backend account mapped"
→ Ask the admin to run: `python -m backend.admin_cli set-github <user> <your-github-login>`

### "Could not verify LinkedIn account"
→ Go sign in to the app first to connect LinkedIn, then come back to Claude

### Claude doesn't suggest commands
→ Try: `What can I do with this connector?` or `show_available_commands`

---

## Need Help?

- **See available commands:** Ask Claude directly
- **Not sure which tool to use:** Start with `draft_post`
- **Contact admin:** Reach out if something's broken

---

**Happy posting! 🚀**

*Last updated: 2026-08-18*
