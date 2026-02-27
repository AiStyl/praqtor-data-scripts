#!/bin/bash
# PRAQTOR DATΔ — RunPod Session v4
# T-pose fix session
# Usage: bash /workspace/praqtor-data-scripts/runpod_session_v4.sh

set -e
echo "=============================================="
echo "[PRAQTOR DATΔ v4] RunPod Session Starting"
echo "=============================================="
date

# Config
PAT="YOUR_PAT_HERE"
REPO="praqtor-data-scripts"
REPO_URL="https://${PAT}@github.com/AiStyl/${REPO}.git"

# Step 1: Install git if needed
if ! command -v git &> /dev/null; then
    echo "[SETUP] Installing git..."
    apt-get update -qq && apt-get install -y -qq git > /dev/null 2>&1
fi
git config --global user.email "ai.style@outlook.com"
git config --global user.name "AiStyl"

# Step 2: Clone/update repo
cd /workspace
if [ -d "$REPO" ]; then
    echo "[SETUP] Updating existing repo..."
    cd $REPO
    git pull || { rm -rf /workspace/$REPO && git clone $REPO_URL && cd $REPO; }
else
    echo "[SETUP] Cloning repo..."
    git clone $REPO_URL
    cd $REPO
fi

# Step 3: Check disk space
echo ""
echo "[DISK] Space check:"
df -h /workspace | tail -1
echo ""

# Step 4: Run diagnostic FIRST
echo "=============================================="
echo "[PHASE 1] Running animation diagnostic..."
echo "=============================================="
/isaac-sim/python.sh anim_diagnostic_v4.py 2>&1 | tee /workspace/diag_v4_log.txt

# Check diagnostic results
if [ -f /workspace/diagnostic_v4.json ]; then
    echo ""
    echo "[DIAG] Results saved. Key findings:"
    python3 -c "
import json
with open('/workspace/diagnostic_v4.json') as f:
    d = json.load(f)
print(f'  Skeleton found: {d.get(\"skeleton_found\", \"unknown\")}')
print(f'  Animation bound: {d.get(\"animation_bound\", \"unknown\")}')
tests = d.get('tests', {})
passed = sum(1 for v in tests.values() if v)
print(f'  Tests: {passed}/{len(tests)} passed')
" 2>/dev/null || echo "  (could not parse results)"
    echo ""
    echo "Review diagnostic output above."
    echo "To proceed with full render, run:"
    echo "  /isaac-sim/python.sh /workspace/$REPO/photoreal_scene_v4.py 2>&1 | tee /workspace/scene_v4_log.txt"
    echo ""
    echo "To push results to GitHub:"
    echo "  cd /workspace/$REPO && cp /workspace/output_v4 . -r && cp /workspace/diagnostic_v4.json . && git add -A && git commit -m 'v4: T-pose fix session' && git push"
else
    echo "[WARN] Diagnostic did not produce results file"
fi

echo ""
echo "[PRAQTOR DATΔ v4] Diagnostic phase complete."
echo "=============================================="
