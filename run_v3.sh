#!/bin/bash
echo "🤖 Starting Autonomous System v3.0"
echo "Features: No trade limit, Adaptive quality, Defensive sizing"
echo ""
python3 -u auto_monitor_v3.py 2>&1 | tee -a trading_v3_live.log
