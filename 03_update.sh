#!/usr/bin/env bash
#
# update.sh - Update deployed MongoDB Load Test Platform
#
# Features:
# - Pulls latest code from git
# - Stops running processes gracefully
# - Updates dependencies (if requirements.txt changed)
# - Migrates database (if models changed)
# - Restarts service
# - Preserves data, logs, and configuration
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                                                                   ║${NC}"
echo -e "${BLUE}║      MongoDB Load Test Platform - Update Script                  ║${NC}"
echo -e "${BLUE}║                                                                   ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# STEP 1: Check Prerequisites
# ============================================================================
echo -e "${YELLOW}[1/7] Checking prerequisites...${NC}"

if ! command -v git &> /dev/null; then
    echo -e "${RED}✗ git not found. Please install git first.${NC}"
    exit 1
fi

if [ ! -d ".git" ]; then
    echo -e "${RED}✗ Not a git repository. Cannot update.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites met${NC}"
echo ""

# ============================================================================
# STEP 2: Backup Critical Files
# ============================================================================
echo -e "${YELLOW}[2/7] Creating backup...${NC}"

BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup database
if [ -f "loadtest.db" ]; then
    cp loadtest.db "$BACKUP_DIR/"
    echo "  ✓ Database backed up"
fi

# Backup .env
if [ -f ".env" ]; then
    cp .env "$BACKUP_DIR/"
    echo "  ✓ .env backed up"
fi

# Backup runs (if exists and not huge)
if [ -d "runs" ]; then
    RUNS_SIZE=$(du -sm runs | cut -f1)
    if [ "$RUNS_SIZE" -lt 100 ]; then
        cp -r runs "$BACKUP_DIR/" 2>/dev/null || echo "  ⚠ Could not backup runs/"
    else
        echo "  ⚠ runs/ too large ($RUNS_SIZE MB), skipping backup"
    fi
fi

echo -e "${GREEN}✓ Backup created: $BACKUP_DIR${NC}"
echo ""

# ============================================================================
# STEP 3: Stop Running Processes
# ============================================================================
echo -e "${YELLOW}[3/7] Stopping running processes...${NC}"

# Find PIDs on ports 8000, 8001
PIDS=""
for PORT in 8000 8001; do
    PORT_PIDS=$(lsof -ti:$PORT 2>/dev/null || true)
    if [ -n "$PORT_PIDS" ]; then
        PIDS="$PIDS $PORT_PIDS"
    fi
done

if [ -n "$PIDS" ]; then
    echo "  Stopping server (PIDs:$PIDS)..."
    echo $PIDS | xargs kill -TERM 2>/dev/null || true
    sleep 2

    # Check if still running
    STILL_RUNNING=""
    for PID in $PIDS; do
        if ps -p $PID > /dev/null 2>&1; then
            STILL_RUNNING="$STILL_RUNNING $PID"
        fi
    done

    if [ -n "$STILL_RUNNING" ]; then
        echo "  Force stopping remaining processes..."
        echo $STILL_RUNNING | xargs kill -9 2>/dev/null || true
    fi

    echo -e "${GREEN}✓ Server stopped${NC}"
else
    echo -e "${GREEN}✓ No running server found${NC}"
fi
echo ""

# ============================================================================
# STEP 4: Pull Latest Code
# ============================================================================
echo -e "${YELLOW}[4/7] Pulling latest code from git...${NC}"

# Check current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "  Current branch: $CURRENT_BRANCH"

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo -e "${RED}✗ You have uncommitted changes. Please commit or stash them first.${NC}"
    git status --short
    exit 1
fi

# Pull latest
git pull --rebase
PULL_STATUS=$?

if [ $PULL_STATUS -ne 0 ]; then
    echo -e "${RED}✗ Git pull failed. Please resolve conflicts manually.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Code updated${NC}"
echo ""

# ============================================================================
# STEP 5: Update Dependencies
# ============================================================================
echo -e "${YELLOW}[5/7] Updating dependencies...${NC}"

# Check if requirements.txt changed
REQUIREMENTS_CHANGED=$(git diff HEAD@{1} HEAD -- requirements.txt | wc -l)

if [ "$REQUIREMENTS_CHANGED" -gt 0 ] || [ ! -d "venv" ]; then
    echo "  requirements.txt changed or venv missing, updating dependencies..."

    # Activate venv
    if [ ! -d "venv" ]; then
        echo "  Creating virtual environment..."
        python3 -m venv venv
    fi

    source venv/bin/activate

    # Upgrade pip
    pip install --upgrade pip --quiet

    # Install dependencies
    pip install -r requirements.txt --quiet

    echo -e "${GREEN}✓ Dependencies updated${NC}"
else
    echo -e "${GREEN}✓ No dependency changes${NC}"
fi
echo ""

# ============================================================================
# STEP 6: Migrate Database
# ============================================================================
echo -e "${YELLOW}[6/7] Checking database migrations...${NC}"

# Check if db/models.py changed
MODELS_CHANGED=$(git diff HEAD@{1} HEAD -- db/models.py | wc -l)

if [ "$MODELS_CHANGED" -gt 0 ]; then
    echo "  Database models changed, running migration..."

    # Activate venv if not already
    [ -z "$VIRTUAL_ENV" ] && source venv/bin/activate

    # Run migration (SQLAlchemy auto-creates new tables)
    python3 -c "from db import init_db; init_db(); print('✓ Database migrated')"

    echo -e "${GREEN}✓ Database migrated${NC}"
else
    echo -e "${GREEN}✓ No database changes${NC}"
fi
echo ""

# ============================================================================
# STEP 7: Restart Service
# ============================================================================
echo -e "${YELLOW}[7/7] Restarting service...${NC}"

# Activate venv if not already
[ -z "$VIRTUAL_ENV" ] && source venv/bin/activate

# Start server in background
nohup python -m uvicorn app:app --host 0.0.0.0 --port 8001 > server.log 2>&1 &
SERVER_PID=$!

# Wait for server to start
echo "  Waiting for server to start..."
sleep 3

# Check if server is running
if ps -p $SERVER_PID > /dev/null; then
    # Test API endpoint
    if curl -s -f http://localhost:8001/api/catalog > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Server started successfully (PID: $SERVER_PID)${NC}"
    else
        echo -e "${YELLOW}⚠ Server started but API not responding. Check server.log${NC}"
    fi
else
    echo -e "${RED}✗ Server failed to start. Check server.log for errors.${NC}"
    tail -20 server.log
    exit 1
fi
echo ""

# ============================================================================
# Summary
# ============================================================================
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                                                                   ║${NC}"
echo -e "${BLUE}║                    Update Complete                                ║${NC}"
echo -e "${BLUE}║                                                                   ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✓ Code updated from git${NC}"
echo -e "${GREEN}✓ Dependencies updated (if needed)${NC}"
echo -e "${GREEN}✓ Database migrated (if needed)${NC}"
echo -e "${GREEN}✓ Server restarted${NC}"
echo ""
echo -e "${BLUE}Service running at: http://localhost:8001${NC}"
echo -e "${BLUE}Server PID: $SERVER_PID${NC}"
echo -e "${BLUE}Logs: tail -f server.log${NC}"
echo ""
echo -e "${YELLOW}Backup location: $BACKUP_DIR${NC}"
echo "  (Restore if needed: cp $BACKUP_DIR/loadtest.db .)"
echo ""
echo -e "${GREEN}To stop: kill $SERVER_PID${NC}"
echo ""
