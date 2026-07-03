# Service Persistence Guide

## Overview

The MongoDB Load Test Platform has **two types of scheduling**:

### 1. In-App Scheduler (APScheduler)
- **Location**: Tab 3 → "In-app" mode
- **Persistence**: ❌ **Does NOT survive restart**
- **Use Case**: Temporary schedules, testing
- **How it works**: Runs in Python process memory

### 2. OS-Level Scheduler (Persistent)
- **Location**: Tab 3 → "Permanent" mode
- **Persistence**: ✅ **SURVIVES restart**
- **Use Case**: Production schedules, long-term testing
- **How it works**: Creates OS-level cron/launchd jobs

---

## Making the Web Service Persistent

By default, running `bash 01_deploy.sh` starts the service as a **background process** which:
- ❌ Will NOT survive system restart
- ❌ Will NOT survive logout
- ✅ Can be stopped with `kill <PID>`

### Option 1: Manual Restart (Simplest)

After every reboot:
```bash
bash 01_deploy.sh
```

**Pros**: Simple, no configuration  
**Cons**: Manual step after reboot

---

### Option 2: Auto-Start on Boot (macOS - launchd)

#### Step 1: Edit launchd.plist
```bash
nano scripts/launchd.plist
```

Replace `YOUR_ENCRYPTION_KEY_HERE` with your actual encryption key:
```bash
# Get your key
cat .env | grep LOADGEN_ENCRYPTION_KEY
```

#### Step 2: Install Service
```bash
sudo cp scripts/launchd.plist /Library/LaunchDaemons/com.mongodb.loadtest.plist
sudo chown root:wheel /Library/LaunchDaemons/com.mongodb.loadtest.plist
sudo chmod 644 /Library/LaunchDaemons/com.mongodb.loadtest.plist
```

#### Step 3: Start Service
```bash
sudo launchctl load /Library/LaunchDaemons/com.mongodb.loadtest.plist
```

#### Managing the Service
```bash
# Check status
sudo launchctl list | grep mongodb.loadtest

# Stop service
sudo launchctl unload /Library/LaunchDaemons/com.mongodb.loadtest.plist

# Restart service
sudo launchctl unload /Library/LaunchDaemons/com.mongodb.loadtest.plist
sudo launchctl load /Library/LaunchDaemons/com.mongodb.loadtest.plist

# View logs
tail -f server.log
tail -f server.error.log
```

**Pros**: Auto-starts on boot, persistent  
**Cons**: Requires sudo, more complex setup

---

### Option 3: Auto-Start on Boot (Linux - systemd)

#### Step 1: Edit systemd.service
```bash
nano scripts/systemd.service
```

Replace:
- `YOUR_ENCRYPTION_KEY_HERE` with your actual encryption key
- User and WorkingDirectory paths if needed
- uvicorn path (`which uvicorn`)

#### Step 2: Install Service
```bash
sudo cp scripts/systemd.service /etc/systemd/system/loadtest.service
sudo systemctl daemon-reload
```

#### Step 3: Enable and Start
```bash
sudo systemctl enable loadtest.service
sudo systemctl start loadtest.service
```

#### Managing the Service
```bash
# Check status
sudo systemctl status loadtest.service

# Stop service
sudo systemctl stop loadtest.service

# Restart service
sudo systemctl restart loadtest.service

# View logs
sudo journalctl -u loadtest.service -f

# Or
tail -f server.log
```

**Pros**: Auto-starts on boot, persistent, standard Linux approach  
**Cons**: Requires sudo, Linux-specific

---

## Scheduler Persistence Comparison

| Feature | In-App Scheduler | OS-Level Scheduler |
|---------|-----------------|-------------------|
| Survives app restart | ❌ No | ✅ Yes |
| Survives system reboot | ❌ No | ✅ Yes |
| Setup complexity | ✅ Simple | ⚠️ Moderate |
| Requires sudo | ❌ No | ✅ Yes |
| Best for | Testing, temporary | Production, long-term |
| Access to logs | ✅ In-app logs | ⚠️ System logs |

---

## Recommendations

### Development / Testing
Use **Option 1** (Manual Restart):
- Run `bash 01_deploy.sh` when needed
- Use in-app scheduler for temporary schedules

### Production / Long-Term
Use **Option 2 or 3** (Auto-Start):
- Install launchd (macOS) or systemd (Linux) service
- Use OS-level scheduler (Permanent mode in Tab 3)
- Service auto-starts on boot
- Schedules survive restart

---

## Troubleshooting

### Service won't start
```bash
# Check if port is in use
lsof -i :8001

# Kill existing process
kill $(lsof -t -i :8001)

# Check logs
tail -50 server.log
tail -50 server.error.log
```

### Encryption key error
```bash
# Verify key is set
echo $LOADGEN_ENCRYPTION_KEY

# Or check .env file
cat .env

# Regenerate if needed
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Database locked error
```bash
# Check permissions
ls -l loadtest.db

# Fix permissions
chmod 600 loadtest.db
```

---

## FAQ

**Q: Does the web UI work after restart?**  
A: Only if you use Option 2 or 3 (auto-start service)

**Q: Do scheduled tests work after restart?**  
A: Only if you use "Permanent" mode in Tab 3 (OS-level scheduler)

**Q: Can I use both in-app and OS-level schedulers?**  
A: Yes! Use in-app for quick tests, OS-level for production schedules

**Q: How do I migrate from in-app to OS-level scheduler?**  
A: Recreate schedules in Tab 3 using "Permanent" mode instead of "In-app"

---

**Generated**: 2026-07-03  
**Version**: 2.0.0
