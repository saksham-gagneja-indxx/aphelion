# Security Policy

## Reporting a Vulnerability

Thank you for helping us keep Aphelion secure! If you discover a security vulnerability, please report it responsibly.

### How to Report

**Please do NOT open a public issue for security vulnerabilities.**

Instead, email us at: **sgagneja@indxx.com**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any proof-of-concept code (if applicable)

### Response Timeline

We aim to:
- Acknowledge receipt within 24 hours
- Provide a fix within 7 days (for critical vulnerabilities)
- Coordinate responsible disclosure

### Security Best Practices

When using Aphelion:

1. **GitHub OAuth Credentials**
   - Only grant necessary permissions
   - Revoke access if you stop using the tool

2. **LinkedIn OAuth Tokens**
   - Tokens are encrypted at rest in the database
   - Never share your LinkedIn password (we never ask for it)

3. **API Keys**
   - Store API keys in environment variables
   - Never commit secrets to Git
   - Rotate keys regularly

4. **Google Drive Links**
   - Only share videos with "Anyone with the link" access
   - Consider expiring shared links after use

### Known Security Measures

✅ **GitHub OAuth** — Two-factor authentication gate  
✅ **Bearer Tokens** — Encrypted API authentication  
✅ **LinkedIn Credentials** — AES-128 encryption at rest  
✅ **Session Management** — Signed, httponly cookies  
✅ **Server-Side Processing** — No sensitive data in chat  
✅ **Secret Scanning** — GitHub notifies on exposed secrets  

### Supported Versions

| Version | Status |
|---------|--------|
| 0.0.1+ | ✅ Supported |
| < 0.0.1 | ❌ Unsupported |

### Security Advisories

We publish security advisories on GitHub when vulnerabilities are discovered and fixed:
https://github.com/saksham-gagneja-indxx/aphelion/security/advisories

### Contact

- **Security Issues**: sgagneja@indxx.com
- **General Questions**: GitHub Issues
- **Feature Requests**: GitHub Discussions

Thank you for your responsible disclosure and support of Aphelion! 🙏

---

**Last Updated**: 2026-08-19  
**Policy Version**: 1.0
