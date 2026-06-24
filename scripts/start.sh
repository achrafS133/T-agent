#!/usr/bin/env bash
# Start T-AGENT PRO — API + Dashboard
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Starting T-AGENT PRO..."
cd "$ROOT"

if [ -f venv/bin/activate ]; then
  source venv/bin/activate
fi

python serve.py &
API_PID=$!

sleep 2
cd apps/web && npm run dev &
WEB_PID=$!

echo ""
echo "API:       http://localhost:8000"
echo "Dashboard: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both servers"

trap "kill $API_PID $WEB_PID 2>/dev/null" EXIT
wait
