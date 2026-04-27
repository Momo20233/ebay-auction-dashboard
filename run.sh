#!/bin/bash
cd "$(dirname "$0")"

echo "==================================="
echo " eBay Auction Dashboard"
echo "==================================="

# Install dependencies silently
echo "▸ Checking dependencies..."
pip install -r requirements.txt -q

echo "▸ Starting server at http://localhost:8000"
echo "  (Monte Carlo simulation runs in background on first launch)"
echo "  Press Ctrl+C to stop."
echo ""

python3 app.py
