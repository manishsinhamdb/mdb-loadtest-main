#!/usr/bin/env bash
#
# teardown.sh - Safely remove MongoDB Load Test Platform
#
# Features:
# - Stops all running processes (server, background tasks)
# - Removes virtual environment
# - Optionally removes database and logs
# - Optionally removes git repository
# - No orphan processes or files
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
echo -e "${BLUE}║      MongoDB Load Test Platform - Safe Teardown Script           ║${NC}"
echo -e "${BLUE}║                                                                   ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# STEP 1: Stop All Running Processes
# ============================================================================
echo -e "${YELLOW}[1/5] Stopping all running processes...${NC}"

# Stop uvicorn server (port 8000, 8001)
for PORT in 8000 8001; do
    PIDS=$(lsof -ti:$PORT 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        echo "  Stopping server on port $PORT (PIDs: $PIDS)"
        kill -TERM $PIDS 2>/dev/null || true
        sleep 1
        # Force kill if still running
        kill -9 $PIDS 2>/dev/null || true
    fi
done

# Stop any background Python processes from this project
PYTHON_PIDS=$(ps aux | grep "[p]ython.*app:app" | awk '{print $2}' || true)
if [ -n "$PYTHON_PIDS" ]; then
    echo "  Stopping background Python processes: $PYTHON_PIDS"
    echo "$PYTHON_PIDS" | xargs kill -TERM 2>/dev/null || true
    sleep 1
    echo "$PYTHON_PIDS" | xargs kill -9 2>/dev/null || true
fi

echo -e "${GREEN}✓ All processes stopped${NC}"
echo ""

# ============================================================================
# STEP 2: Remove Virtual Environment
# ============================================================================
echo -e "${YELLOW}[2/5] Removing virtual environment...${NC}"

if [ -d "venv" ]; then
    rm -rf venv
    echo -e "${GREEN}✓ Virtual environment removed${NC}"
else
    echo -e "${GREEN}✓ No virtual environment found${NC}"
fi
echo ""

# ============================================================================
# STEP 3: Clean Up Data (Optional - Ask User)
# ============================================================================
echo -e "${YELLOW}[3/5] Cleaning up data...${NC}"

# Ask about database
if [ -f "loadtest.db" ]; then
    read -p "  Remove database (loadtest.db)? This will delete all connection profiles and run history. (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -f loadtest.db
        echo -e "${GREEN}✓ Database removed${NC}"
    else
        echo -e "${YELLOW}  Keeping database${NC}"
    fi
fi

# Ask about runs directory
if [ -d "runs" ]; then
    read -p "  Remove runs directory? This will delete all test manifests and logs. (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf runs
        echo -e "${GREEN}✓ Runs directory removed${NC}"
    else
        echo -e "${YELLOW}  Keeping runs directory${NC}"
    fi
fi

# Ask about .env file
if [ -f ".env" ]; then
    read -p "  Remove .env file? This will delete encryption keys. (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -f .env
        echo -e "${GREEN}✓ .env file removed${NC}"
    else
        echo -e "${YELLOW}  Keeping .env file${NC}"
    fi
fi

echo ""

# ============================================================================
# STEP 4: Remove Orphan Files
# ============================================================================
echo -e "${YELLOW}[4/5] Removing orphan files...${NC}"

# Remove Python cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true

# Remove logs
rm -f server.log uvicorn.log *.log 2>/dev/null || true

# Remove temporary files
rm -rf /tmp/claude-*/**/tasks/*.output 2>/dev/null || true

echo -e "${GREEN}✓ Orphan files cleaned${NC}"
echo ""

# ============================================================================
# STEP 5: Optional Full Removal
# ============================================================================
echo -e "${YELLOW}[5/5] Complete removal (optional)...${NC}"

read -p "  Do you want to remove the entire project directory? This cannot be undone! (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}⚠️  This will DELETE the entire project directory in 5 seconds...${NC}"
    echo "  Press Ctrl+C to cancel"
    sleep 5

    cd ..
    rm -rf "$PROJECT_ROOT"
    echo -e "${GREEN}✓ Project directory removed${NC}"
    echo ""
    echo -e "${BLUE}Teardown complete. Goodbye!${NC}"
    exit 0
fi

echo ""

# ============================================================================
# Summary
# ============================================================================
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                                                                   ║${NC}"
echo -e "${BLUE}║                    Teardown Complete                              ║${NC}"
echo -e "${BLUE}║                                                                   ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✓ All processes stopped${NC}"
echo -e "${GREEN}✓ Virtual environment removed${NC}"
echo -e "${GREEN}✓ Orphan files cleaned${NC}"
echo ""
echo -e "${YELLOW}Kept files (if not removed):${NC}"
echo "  • loadtest.db (connection profiles, run history)"
echo "  • runs/ (test manifests and logs)"
echo "  • .env (encryption keys)"
echo "  • Source code files"
echo ""
echo -e "${BLUE}To reinstall: bash 01_deploy.sh${NC}"
echo ""
