#!/bin/bash
# FE-Analyst Dashboard — Start API, Frontend, and Analysis Watcher
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
echo "=========================================="
echo "  FE-Analyst Dashboard"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# 1. Start API server
echo -e "${BLUE}[1/3] Starting API server on http://localhost:8050${NC}"
cd "$DIR/api"
if [ ! -d "venv" ]; then
  echo "  Creating Python venv..."
  python3 -m venv venv
  source venv/bin/activate
  pip install -q -r requirements.txt
else
  source venv/bin/activate
fi
uvicorn server:app --host 0.0.0.0 --port 8050 --reload &
API_PID=$!

# 2. Start analysis watcher (Claude Code thesis generator)
echo -e "${BLUE}[2/3] Starting analysis watcher${NC}"
cd "$DIR/api"
python analysis_watcher.py &
WATCHER_PID=$!

# 3. Start frontend
echo -e "${BLUE}[3/3] Starting frontend on http://localhost:3050${NC}"
cd "$DIR/frontend"
if [ ! -d "node_modules" ]; then
  echo "  Installing npm packages..."
  npm install
fi
npm run dev &
FE_PID=$!

echo ""
echo -e "${GREEN}=========================================="
echo -e "  Dashboard ready!"
echo -e "  Frontend:  http://localhost:3050"
echo -e "  API:       http://localhost:8050"
echo -e "  API Docs:  http://localhost:8050/docs"
echo -e "  Watcher:   analysis_watcher.py (PID $WATCHER_PID)"
echo -e "==========================================${NC}"
echo ""
echo "Press Ctrl+C to stop all services."

trap "kill $API_PID $FE_PID $WATCHER_PID 2>/dev/null; exit" INT TERM
wait
