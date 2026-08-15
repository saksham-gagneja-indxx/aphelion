# 🚀 Setup Guide - Social Media Automation Agent

## Quick Start (5 Minutes)

### Step 1: Clone & Setup
```bash
git clone https://github.com/saksham-gagneja-indxx/social-media-manager.git
cd social-media-manager
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Configure
```bash
cp .env.example .env
# Edit .env with your local TIMEZONE.
# Instagram/Claude credentials can be added but are NOT currently wired to posting.
```

### Step 3: Run
```bash
# Terminal 1: Backend
python -m backend.app

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
# Visit http://localhost:5173
```

---

## 📋 Prerequisites

### Required
- Python 3.9+
- pip (Python package manager)
- Git (optional but recommended)

### API Keys & Credentials (You have these!)
- ✅ Claude API Key (Anthropic)
- ✅ Instagram username & password
- ✅ LinkedIn email & password

### System Requirements
- 4GB RAM minimum
- 500MB disk space
- Internet connection

---

## 📁 Directory Structure Guide

```
social-media-automation/
├── backend/                          # All Python code
│   ├── core/                         # Core functionality
│   │   ├── agent.py                  # Instagram agent
│   │   ├── scheduler.py              # APScheduler integration
│   │   └── reel_manager.py           # Reel handling
│   │
│   ├── ai/                           # AI features
│   │   ├── caption_generator.py      # Claude API captions
│   │   ├── comment_manager.py        # Comment handling
│   │   └── hashtag_engine.py         # Hashtag recommendations
│   │
│   ├── platforms/                    # Social platforms
│   │   ├── instagram_platform.py     # Instagram specific
│   │   └── linkedin_platform.py      # LinkedIn specific
│   │
│   ├── api/                          # Flask API
│   │   ├── routes.py                 # API endpoints
│   │   ├── auth.py                   # Authentication
│   │   └── middleware.py             # Request middleware
│   │
│   ├── models/                       # Database models
│   │   ├── user.py                   # User model
│   │   ├── post.py                   # Post model
│   │   ├── analytics.py              # Analytics model
│   │   └── schemas.py                # Pydantic schemas
│   │
│   ├── utils/                        # Utilities
│   │   ├── config.py                 # Configuration
│   │   ├── logger.py                 # Logging setup
│   │   ├── database.py               # Database connection
│   │   ├── validators.py             # Input validators
│   │   └── helpers.py                # Helper functions
│   │
│   ├── app.py                        # Main Flask app
│   └── requirements.txt               # Dependencies
│
├── frontend/                         # Web interface
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── queue.html
│   │   ├── analytics.html
│   │   ├── schedule.html
│   │   ├── settings.html
│   │   └── caption_studio.html
│   │
│   └── static/
│       ├── css/
│       │   └── style.css
│       └── js/
│           ├── main.js
│           └── charts.js
│
├── database/                         # Database setup
│   ├── schemas.sql                   # SQL schema
│   └── migrations/                   # Alembic migrations
│
├── data/                             # Runtime data
│   ├── reels/                        # Uploaded reels
│   ├── uploads/                      # Temp uploads
│   └── logs/                         # Application logs
│
├── tests/                            # Test files
│   ├── test_agent.py
│   ├── test_scheduler.py
│   └── test_api.py
│
├── docs/                             # Documentation
│   ├── TIMELINE.md                   # Project timeline
│   ├── SETUP.md                      # This file
│   ├── API.md                        # API documentation
│   ├── ARCHITECTURE.md               # Architecture guide
│   └── PHASE_IMPLEMENTATION.md       # Phase details
│
├── .env.example                      # Env template
├── .gitignore                        # Git ignore
├── requirements.txt                  # Dependencies
└── README.md                         # Project README
```

---

## 🔧 Configuration Guide

### .env File Setup

```bash
# Copy template
cp .env.example .env

# Edit with your values
nano .env
```

### Essential Configuration

**1. Flask Settings**
```env
FLASK_ENV=development
FLASK_PORT=5000
SECRET_KEY=your_secret_key_here
```

**2. Claude API**
```env
CLAUDE_API_KEY=sk-ant-xxxxxxxxxx
```

**3. Instagram**
```env
INSTAGRAM_USERNAME=your_username
INSTAGRAM_PASSWORD=your_password
```

**4. LinkedIn** (for Phase 3)
```env
LINKEDIN_EMAIL=your_email@example.com
LINKEDIN_PASSWORD=your_password
```

**5. Timezone** (IMPORTANT!)
```env
TIMEZONE=Asia/Kolkata  # Change to your timezone
```

---

## 🐍 Python Virtual Environment

### Create Virtual Environment
```bash
# Create venv
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Verify activation (should show venv in terminal)
which python  # or: where python (Windows)
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Deactivate When Done
```bash
deactivate
```

---

## 🚀 Running the Application

### Start the Server
```bash
cd social-media-manager
source venv/bin/activate
python -m backend.app
```

### Expected Output
```
 * Running on http://0.0.0.0:5000
 * Debug mode: on
 * WARNING: This is a development server
```

### Access Dashboard
```
The React frontend handles the dashboard. Start it in a second terminal:
cd frontend
npm install
npm run dev

Then visit: http://localhost:5173
```

---

## 🧪 Testing

### Run Tests
```bash
pytest tests/ -v
```

### Run with Coverage
```bash
pytest tests/ --cov=backend
```

### Run Specific Test
```bash
pytest tests/test_agent.py -v
```

---

## 📝 Database Setup

### Initialize Database
```bash
# Create tables
python -c "from backend.utils.database import init_db; init_db()"

# Or use migrations
alembic upgrade head
```

### Reset Database (Development)
```bash
rm data/automation.db
python -c "from backend.utils.database import init_db; init_db()"
```

---

## 🐛 Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'flask'"
**Solution:**
```bash
pip install -r requirements.txt
```

### Issue: "Port 5000 already in use"
**Solution:**
```bash
# Linux/Mac
lsof -i :5000
kill -9 <PID>

# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F
```

### Issue: "Instagram login failed"
**Solutions:**
1. Check credentials in .env
2. Try Instagram account in browser first
3. Disable 2FA temporarily
4. Use app-specific password if available

### Issue: "Claude API key not working"
**Solutions:**
1. Verify key in .env (no spaces or quotes)
2. Check key format (sk-ant-...)
3. Verify API has quota
4. Test with curl:
```bash
curl https://api.anthropic.com/v1/models \
  -H "x-api-key: $CLAUDE_API_KEY"
```

### Issue: Database errors
**Solution:**
```bash
# Check database file
ls -la data/automation.db

# Reset if needed
rm data/automation.db
python -c "from backend.utils.database import init_db; init_db()"
```

---

## 📊 Project Structure Commands

### Create New Module
```bash
touch backend/core/new_module.py
```

### Add New API Route
Edit `backend/api/routes.py` and add:
```python
@app.route('/api/endpoint', methods=['GET', 'POST'])
def endpoint():
    return {'status': 'ok'}
```

### Create Migration
```bash
alembic revision --autogenerate -m "description"
```

---

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| TIMELINE.md | 8-week project timeline |
| SETUP.md | This file - setup guide |
| API.md | API endpoint documentation |
| ARCHITECTURE.md | System design & flow |
| PHASE_IMPLEMENTATION.md | Detailed phase guides |

---

## 🔄 Development Workflow

### Daily Workflow
```
1. Activate venv
2. Run backend: python -m backend.app
3. Run frontend: cd frontend && npm run dev
4. Make changes
5. Test changes
```

### Before Committing
```bash
# Format code
black backend/

# Check style
flake8 backend/

# Run tests
pytest tests/

# Commit
git commit -m "description"
```

---

## 📋 Checklist for First Run

- [ ] Python 3.12+ installed
- [ ] Node.js 20+ and npm installed
- [ ] Virtual environment created
- [ ] Dependencies installed (Python and Node)
- [ ] .env configured with timezone (Instagram credentials can be skipped for now)
- [ ] Database initialized
- [ ] Flask backend running on localhost:5000
- [ ] Vite frontend running on localhost:5173
- [ ] Dashboard accessible in browser

---

## 🎯 What's Next?

After successful setup:

1. **Phase 1 (Week 1-2):** Instagram automation core
2. **Phase 2 (Week 3-4):** AI features
3. **Phase 3 (Week 5-6):** LinkedIn integration
4. **Phase 4 (Week 7-8):** Ideation engine

See TIMELINE.md for detailed schedule.

---

## 💡 Quick Reference Commands

```bash
# Activate environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run backend
python -m backend.app

# Run frontend
cd frontend
npm run dev

# Run tests
pytest tests/ -v

# Format code
black backend/

# Check code style
flake8 backend/

# Deactivate environment
deactivate
```

---

## 📞 Getting Help

1. Check TIMELINE.md for timeline questions
2. Check API.md for API questions
3. Check ARCHITECTURE.md for design questions
4. Check logs in data/logs/ for errors
5. Review test files for usage examples

---

**Ready to start?** See TIMELINE.md to begin Phase 1! 🚀
