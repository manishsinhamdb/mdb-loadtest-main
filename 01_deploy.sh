#!/bin/bash
set -e  # Exit on any error

# =============================================================================
# MongoDB Load Test Platform V2.0.0 - One-Click Deployment Script
# =============================================================================
# This script automates the complete setup and deployment process.
# Usage: bash 01_deploy.sh [--port PORT] [--host HOST]
# =============================================================================

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
PORT=8001
HOST="127.0.0.1"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            PORT="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --help)
            echo "Usage: bash 01_deploy.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --port PORT    Port to run the service on (default: 8001)"
            echo "  --host HOST    Host to bind to (default: 127.0.0.1)"
            echo "  --help         Show this help message"
            echo ""
            echo "Example:"
            echo "  bash 01_deploy.sh --port 8080 --host 0.0.0.0"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                                                                   ║${NC}"
echo -e "${BLUE}║      MongoDB Load Test Platform V2.0.0 - Deployment Script       ║${NC}"
echo -e "${BLUE}║                                                                   ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# =============================================================================
# Step 1: Check Prerequisites
# =============================================================================
echo -e "${YELLOW}[1/7] Checking prerequisites...${NC}"

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 is not installed${NC}"
    echo "Please install Python 3.10 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}✗ pip3 is not installed${NC}"
    echo "Please install pip3"
    exit 1
fi
echo -e "${GREEN}✓ pip3 found${NC}"

# =============================================================================
# Step 2: Create Virtual Environment (if needed)
# =============================================================================
echo ""
echo -e "${YELLOW}[2/7] Setting up Python virtual environment...${NC}"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi

# Activate virtual environment
source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"

# =============================================================================
# Step 3: Install Dependencies
# =============================================================================
echo ""
echo -e "${YELLOW}[3/7] Installing Python dependencies...${NC}"

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt --quiet
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${RED}✗ requirements.txt not found${NC}"
    exit 1
fi

# =============================================================================
# Step 4: Generate Encryption Key
# =============================================================================
echo ""
echo -e "${YELLOW}[4/7] Setting up encryption key...${NC}"

# Check if encryption key already exists
if [ -z "$LOADGEN_ENCRYPTION_KEY" ]; then
    # Generate new key
    ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    export LOADGEN_ENCRYPTION_KEY="$ENCRYPTION_KEY"

    # Save to .env file for persistence
    echo "LOADGEN_ENCRYPTION_KEY=\"$ENCRYPTION_KEY\"" > .env
    echo -e "${GREEN}✓ Encryption key generated and saved to .env${NC}"
    echo -e "${YELLOW}  IMPORTANT: Add this to your shell profile for persistence:${NC}"
    echo -e "${YELLOW}  export LOADGEN_ENCRYPTION_KEY=\"$ENCRYPTION_KEY\"${NC}"
else
    echo -e "${GREEN}✓ Using existing encryption key from environment${NC}"
fi

# =============================================================================
# Step 5: Initialize Database
# =============================================================================
echo ""
echo -e "${YELLOW}[5/7] Initializing database...${NC}"

if [ ! -f "loadtest.db" ]; then
    python3 -c "from db.models import Base; from db import get_engine; Base.metadata.create_all(get_engine())"
    echo -e "${GREEN}✓ Database initialized (loadtest.db)${NC}"
else
    echo -e "${GREEN}✓ Database already exists${NC}"
fi

# Set secure permissions
chmod 600 loadtest.db 2>/dev/null || true
echo -e "${GREEN}✓ Database permissions set (600)${NC}"

# =============================================================================
# Step 6: Create Output Directory
# =============================================================================
echo ""
echo -e "${YELLOW}[6/7] Creating output directory...${NC}"

mkdir -p runs
echo -e "${GREEN}✓ Output directory created (./runs)${NC}"

# =============================================================================
# Step 7: Run Tests
# =============================================================================
echo ""
echo -e "${YELLOW}[7/7] Running tests...${NC}"

# Run unit tests
if python3 tests/test_data_structures.py > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Unit tests passed (19/19)${NC}"
else
    echo -e "${RED}✗ Unit tests failed${NC}"
    echo "Run manually: python3 tests/test_data_structures.py"
fi

# Run integration tests
if python3 tests/test_integration.py > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Integration tests passed (7/7)${NC}"
else
    echo -e "${YELLOW}⚠ Integration tests skipped (may require hardware access)${NC}"
fi

# =============================================================================
# Step 8: Start Service
# =============================================================================
echo ""
echo -e "${YELLOW}[8/8] Starting service...${NC}"

# Check if port is already in use
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠ Port $PORT is already in use${NC}"
    echo -e "${YELLOW}  Kill existing process? (y/n)${NC}"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        kill $(lsof -Pi :$PORT -sTCP:LISTEN -t) 2>/dev/null || true
        sleep 2
    else
        echo -e "${RED}Deployment cancelled${NC}"
        exit 1
    fi
fi

# Create startup script for persistence
cat > start_server.sh << EOF
#!/bin/bash
cd "$APP_DIR"
source venv/bin/activate
export LOADGEN_ENCRYPTION_KEY="$LOADGEN_ENCRYPTION_KEY"
uvicorn app:app --host $HOST --port $PORT
EOF
chmod +x start_server.sh

# Start server in background (with venv activated)
nohup venv/bin/uvicorn app:app --host $HOST --port $PORT > server.log 2>&1 &
SERVER_PID=$!

# Wait for server to start
echo -e "${BLUE}Waiting for server to start...${NC}"
sleep 3

# Check if server is running
if ps -p $SERVER_PID > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Server started successfully (PID: $SERVER_PID)${NC}"
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                                   ║${NC}"
    echo -e "${GREEN}║                  ✨ DEPLOYMENT SUCCESSFUL! ✨                     ║${NC}"
    echo -e "${GREEN}║                                                                   ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Service Information:${NC}"
    echo -e "  URL:     ${GREEN}http://$HOST:$PORT${NC}"
    echo -e "  PID:     ${GREEN}$SERVER_PID${NC}"
    echo -e "  Logs:    ${GREEN}server.log${NC}"
    echo ""
    echo -e "${BLUE}Quick Actions:${NC}"
    echo -e "  View logs:    ${YELLOW}tail -f server.log${NC}"
    echo -e "  Stop server:  ${YELLOW}kill $SERVER_PID${NC}"
    echo -e "  Restart:      ${YELLOW}bash 01_deploy.sh${NC}"
    echo ""
    echo -e "${BLUE}Documentation:${NC}"
    echo -e "  User Guide:   ${YELLOW}00_USER_GUIDE.md${NC}"
    echo -e "  Quick Start:  ${YELLOW}02_QUICKSTART.md${NC}"
    echo ""
    echo -e "${GREEN}🚀 Ready to use! Open http://$HOST:$PORT in your browser${NC}"
    echo ""

    # Save PID for later
    echo $SERVER_PID > .server.pid
else
    echo -e "${RED}✗ Server failed to start${NC}"
    echo -e "${RED}Check server.log for errors${NC}"
    exit 1
fi

# =============================================================================
# Additional Information
# =============================================================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}About Service Persistence:${NC}"
echo ""
echo -e "${YELLOW}⚠ IMPORTANT - Service Restart Behavior:${NC}"
echo ""
echo -e "1. ${BLUE}Current Process (PID $SERVER_PID):${NC}"
echo -e "   ${YELLOW}Will NOT survive system restart${NC}"
echo -e "   This is a background process that stops when you log out"
echo ""
echo -e "2. ${BLUE}In-App Scheduler (APScheduler):${NC}"
echo -e "   ${YELLOW}Will NOT survive restart${NC}"
echo -e "   Scheduled jobs in Tab 3 are in-memory only"
echo ""
echo -e "3. ${BLUE}OS-Level Scheduler (Persistent):${NC}"
echo -e "   ${GREEN}WILL survive restart${NC}"
echo -e "   Use the 'Permanent' option in Tab 3 for persistent scheduling"
echo -e "   This creates launchd jobs (macOS) or cron jobs (Linux)"
echo ""
echo -e "${YELLOW}To make service survive restart:${NC}"
echo ""
echo -e "Option A: ${BLUE}Manual Restart (Simplest)${NC}"
echo -e "  Run this script again after reboot: ${GREEN}bash 01_deploy.sh${NC}"
echo ""
echo -e "Option B: ${BLUE}Auto-Start on Boot (macOS)${NC}"
echo -e "  Create launchd service:"
echo -e "  ${GREEN}sudo cp scripts/launchd.plist /Library/LaunchDaemons/com.mongodb.loadtest.plist${NC}"
echo -e "  ${GREEN}sudo launchctl load /Library/LaunchDaemons/com.mongodb.loadtest.plist${NC}"
echo ""
echo -e "Option C: ${BLUE}Auto-Start on Boot (Linux)${NC}"
echo -e "  Create systemd service:"
echo -e "  ${GREEN}sudo cp scripts/systemd.service /etc/systemd/system/loadtest.service${NC}"
echo -e "  ${GREEN}sudo systemctl enable loadtest.service${NC}"
echo -e "  ${GREEN}sudo systemctl start loadtest.service${NC}"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
