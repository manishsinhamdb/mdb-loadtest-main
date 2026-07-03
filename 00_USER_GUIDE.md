# MongoDB Load Test Platform - User Guide
**Version:** 2.0.0  
**Last Updated:** 2026-07-03

---

## Quick Start

### 1. Deploy (First Time)
```bash
bash 01_deploy.sh
```
This will:
- Create Python virtual environment
- Install all dependencies
- Initialize database
- Run tests
- Start the server on port 8001

### 2. Update (Already Deployed)
```bash
bash 03_update.sh
```
This will:
- Pull latest code from git
- Stop running server gracefully
- Update dependencies (if changed)
- Migrate database (if schema changed)
- Restart server
- Preserve all data and configuration

### 3. Teardown (Remove Everything)
```bash
bash 02_teardown.sh
```
This will:
- Stop all running processes
- Remove virtual environment
- Optionally remove database, logs, .env
- Clean up orphan files
- No orphan processes or files left behind

---

## Management Scripts

### 01_deploy.sh
**Purpose:** Complete one-click deployment from scratch

**When to Use:**
- First time installation
- Fresh start after teardown
- Setting up on a new machine

**What It Does:**
1. Checks Python 3.14+ and pip
2. Creates virtual environment
3. Installs dependencies from requirements.txt
4. Generates encryption key → .env
5. Initializes SQLite database (loadtest.db)
6. Creates output directory (runs/)
7. Runs unit tests + integration tests
8. Starts server on port 8001

**Output:**
- Server running at http://localhost:8001
- Database: ./loadtest.db
- Logs: ./server.log
- Runs: ./runs/

---

### 02_teardown.sh
**Purpose:** Safely remove the platform without orphan files/processes

**When to Use:**
- Complete uninstallation
- Clean slate before reinstall
- Free up disk space

**What It Does:**
1. **Stops Processes:**
   - Finds all processes on ports 8000, 8001
   - Graceful shutdown (SIGTERM)
   - Force kill if needed (SIGKILL)
   - Stops background Python processes

2. **Removes Virtual Environment:**
   - Deletes venv/ directory
   - Frees ~500MB disk space

3. **Cleans Data (Interactive):**
   - Asks before removing loadtest.db
   - Asks before removing runs/
   - Asks before removing .env

4. **Removes Orphan Files:**
   - Python cache (__pycache__, *.pyc)
   - Log files (*.log)
   - Temporary files

5. **Optional Full Removal:**
   - Deletes entire project directory
   - 5-second countdown to cancel

**Safety Features:**
- Interactive prompts before deleting data
- Clear warnings for irreversible actions
- Backup suggestion before full removal

---

### 03_update.sh
**Purpose:** Update deployed system without data loss

**When to Use:**
- Pull latest features from git
- Apply bug fixes
- Update dependencies

**What It Does:**
1. **Prerequisites Check:**
   - Verifies git is installed
   - Checks if inside git repository
   - Fails if uncommitted changes exist

2. **Creates Backup:**
   - Backup directory: backups/YYYYMMDD_HHMMSS/
   - Backs up loadtest.db
   - Backs up .env
   - Backs up runs/ (if < 100MB)

3. **Stops Server Gracefully:**
   - Finds PIDs on ports 8000, 8001
   - Sends SIGTERM (graceful shutdown)
   - Waits 2 seconds
   - Force kill if still running

4. **Pulls Latest Code:**
   - Checks current branch
   - Verifies no uncommitted changes
   - Runs `git pull --rebase`
   - Aborts if conflicts detected

5. **Updates Dependencies:**
   - Detects if requirements.txt changed
   - Creates venv if missing
   - Upgrades pip
   - Installs/updates packages

6. **Migrates Database:**
   - Detects if db/models.py changed
   - Runs SQLAlchemy auto-migration
   - Creates new tables if needed

7. **Restarts Server:**
   - Starts uvicorn in background
   - Tests API endpoint
   - Reports PID and log location

**Output:**
- Updated server running
- Backup in backups/ directory
- Summary of changes applied

**Rollback (if needed):**
```bash
# If update fails, restore from backup:
cp backups/YYYYMMDD_HHMMSS/loadtest.db .
cp backups/YYYYMMDD_HHMMSS/.env .
bash 01_deploy.sh
```

---

## Service Persistence

### Does the Service Survive Restart?
**NO** - By default, the service stops when:
- Terminal closes
- SSH session disconnects
- System restarts

### How to Make It Persistent?

#### Option 1: systemd (Linux)
```bash
sudo tee /etc/systemd/system/loadtest.service > /dev/null << 'EOF'
[Unit]
Description=MongoDB Load Test Platform
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/path/to/mdb-loadtest-main
Environment="LOADGEN_ENCRYPTION_KEY=<your-key>"
ExecStart=/path/to/venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable loadtest
sudo systemctl start loadtest
```

#### Option 2: launchd (macOS)
```bash
tee ~/Library/LaunchAgents/com.mongodb.loadtest.plist > /dev/null << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mongodb.loadtest</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/venv/bin/python</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>app:app</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8001</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/mdb-loadtest-main</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>LOADGEN_ENCRYPTION_KEY</key>
        <string>your-key-here</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/path/to/mdb-loadtest-main/server.log</string>
    <key>StandardErrorPath</key>
    <string>/path/to/mdb-loadtest-main/server.log</string>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.mongodb.loadtest.plist
```

#### Option 3: Manual Restart
```bash
# Start manually after reboot
cd /path/to/mdb-loadtest-main
bash 01_deploy.sh
```

---

## Workflow Examples

### Example 1: First-Time Setup
```bash
# Clone repository
git clone https://github.com/manishsinhamdb/mdb-loadtest-main.git
cd mdb-loadtest-main

# Deploy
bash 01_deploy.sh

# Open browser
open http://localhost:8001
```

### Example 2: Update Existing Deployment
```bash
cd mdb-loadtest-main

# Update (pulls latest code, restarts server)
bash 03_update.sh

# Verify
curl http://localhost:8001/api/catalog
```

### Example 3: Reinstall from Scratch
```bash
cd mdb-loadtest-main

# Teardown (keeps database)
bash 02_teardown.sh
# Answer 'n' to keep database
# Answer 'y' to remove venv

# Redeploy
bash 01_deploy.sh
```

### Example 4: Complete Removal
```bash
cd mdb-loadtest-main

# Full teardown
bash 02_teardown.sh
# Answer 'y' to remove database
# Answer 'y' to remove runs
# Answer 'y' to remove .env
# Answer 'y' to remove project directory
```

---

## Troubleshooting

### Port Already in Use
```bash
# Find process on port 8001
lsof -ti:8001

# Kill it
lsof -ti:8001 | xargs kill -9

# Restart
bash 01_deploy.sh
```

### Database Locked
```bash
# Stop all processes
bash 02_teardown.sh

# Check for locks
lsof | grep loadtest.db

# Remove lock if found
rm -f loadtest.db-lock

# Restart
bash 01_deploy.sh
```

### Update Failed with Conflicts
```bash
# Check git status
git status

# Stash local changes
git stash

# Try update again
bash 03_update.sh

# Re-apply stashed changes
git stash pop
```

### Server Won't Start
```bash
# Check logs
tail -50 server.log

# Check Python errors
source venv/bin/activate
python -c "import app; print('OK')"

# Reinstall dependencies
pip install -r requirements.txt

# Try again
bash 01_deploy.sh
```

---

## File Structure

```
mdb-loadtest-main/
├── 00_USER_GUIDE.md          ← You are here
├── 01_deploy.sh              ← First-time deployment
├── 02_teardown.sh            ← Safe removal
├── 03_update.sh              ← Update deployed system
├── 02_QUICKSTART.md          ← Quick start guide
├── 03_DESIGN.md              ← Architecture details
├── 04_RELEASE_NOTES.md       ← Version history
├── 09_V2_COMPLETE.md         ← V2 completion report
│
├── app.py                    ← FastAPI main application
├── intent_api.py             ← Intent-based testing logic
├── config.py                 ← Configuration
├── requirements.txt          ← Python dependencies
│
├── venv/                     ← Virtual environment (created by deploy)
├── loadtest.db               ← SQLite database (created by deploy)
├── runs/                     ← Test run outputs (created by deploy)
├── backups/                  ← Update backups (created by update)
├── server.log                ← Server logs
│
├── static/                   ← Web UI
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── components/
│       ├── connection-manager.js
│       └── intent-designer-v2.js
│
├── db/                       ← Database models
│   ├── __init__.py
│   └── models.py
│
└── api/                      ← API routes
    ├── connections.py
    ├── discovery.py
    └── intent.py
```

---

## Support

### Get Help
- GitHub Issues: https://github.com/manishsinhamdb/mdb-loadtest-main/issues
- Read: 03_DESIGN.md for architecture
- Read: 09_V2_COMPLETE.md for latest features

### Common Commands
```bash
# Check server status
ps aux | grep uvicorn

# View logs
tail -f server.log

# Test API
curl http://localhost:8001/api/catalog | jq

# Check database
sqlite3 loadtest.db "SELECT COUNT(*) FROM connection_profiles;"

# Restart server
bash 03_update.sh
```

---

## Best Practices

1. **Before Updates:**
   - Commit your local changes
   - Run `bash 03_update.sh` (auto-creates backup)

2. **Before Teardown:**
   - Export connection profiles (if needed)
   - Backup runs/ directory manually if > 100MB

3. **Service Persistence:**
   - Use systemd/launchd for production
   - Manual restart is fine for development

4. **Monitoring:**
   - Check server.log for errors
   - Monitor disk space (runs/ can grow large)

5. **Security:**
   - Keep .env file secure (contains encryption key)
   - Don't commit .env to git (already in .gitignore)
   - Rotate encryption key periodically

---

**Version:** 2.0.0  
**Last Updated:** 2026-07-03  
**Scripts:** 01_deploy.sh, 02_teardown.sh, 03_update.sh
