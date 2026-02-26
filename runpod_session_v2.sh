#!/bin/bash
# ============================================================
# PRAQTOR DATΔ — RunPod Session Script v2
# ============================================================
# Paste this ENTIRE block into the RunPod terminal.
# Replace YOUR_PAT with your GitHub personal access token.
#
# What it does:
#   1. Installs git (if needed)
#   2. Clones/pulls the repo
#   3. Runs asset discovery (~2 min)
#   4. IF discovery succeeds → runs photorealistic scene (~5-10 min)
#   5. Pushes ALL output to GitHub
#   6. Prints "DONE — STOP THE POD"
#
# Budget: ~15 min max = ~$0.15
# ============================================================

# ---- CONFIGURATION (edit these) ----
PAT="YOUR_PAT"
REPO="https://${PAT}@github.com/AiStyl/praqtor-data-scripts.git"
WORK="/workspace/praqtor-data-scripts"

echo "============================================================"
echo "  PRAQTOR DATΔ — RunPod Session v2"
echo "  $(date -u)"
echo "============================================================"

# ---- Step 1: Install git if missing ----
if ! command -v git &> /dev/null; then
    echo "[1/5] Installing git..."
    apt-get update -qq && apt-get install -y -qq git > /dev/null 2>&1
    echo "  Done."
else
    echo "[1/5] Git already installed."
fi

# ---- Step 2: Clone or pull repo ----
echo "[2/5] Setting up repo..."
git config --global user.email "ai.style@outlook.com"
git config --global user.name "AiStyl"

if [ -d "$WORK/.git" ]; then
    cd "$WORK" && git pull
else
    cd /workspace && git clone "$REPO"
    cd "$WORK"
fi
echo "  Repo ready at $WORK"

# ---- Step 3: Run asset discovery ----
echo ""
echo "[3/5] Running asset discovery..."
echo "  This takes ~2 minutes. DO NOT INTERRUPT."
echo ""

/isaac-sim/python.sh "$WORK/discover_assets_v2.py" 2>&1 | tee /workspace/discovery_log.txt

# Check if discovery found a viable strategy
STRATEGY=$(python3 -c "
import json
try:
    with open('/workspace/asset_inventory.json') as f:
        d = json.load(f)
    print(d.get('strategy', 'unknown'))
except:
    print('no_inventory')
" 2>/dev/null)

echo ""
echo "  Discovery strategy: $STRATEGY"

if [ "$STRATEGY" = "none_found" ] || [ "$STRATEGY" = "no_inventory" ]; then
    echo ""
    echo "============================================================"
    echo "  [STOP] No viable assets found."
    echo "  Pushing discovery results to GitHub, then STOP THE POD."
    echo "============================================================"

    cp /workspace/asset_inventory.json "$WORK/" 2>/dev/null
    cp /workspace/asset_inventory.txt "$WORK/" 2>/dev/null
    cp /workspace/discovery_log.txt "$WORK/" 2>/dev/null
    git add -A && git commit -m "Asset discovery v2 — no assets found" && git push

    echo ""
    echo "  Results pushed. STOP THE POD NOW."
    exit 0
fi

# ---- Step 4: Run photorealistic scene generation ----
echo ""
echo "[4/5] Running photorealistic scene generation..."
echo "  This takes 5-10 minutes. DO NOT INTERRUPT."
echo ""

/isaac-sim/python.sh "$WORK/photoreal_scene_v2.py" 2>&1 | tee /workspace/scene_log.txt

# ---- Step 5: Push everything to GitHub ----
echo ""
echo "[5/5] Pushing results to GitHub..."

# Copy outputs into repo
cp -r /workspace/output_v2 "$WORK/output_v2" 2>/dev/null
cp /workspace/asset_inventory.json "$WORK/" 2>/dev/null
cp /workspace/asset_inventory.txt "$WORK/" 2>/dev/null
cp /workspace/discovery_log.txt "$WORK/" 2>/dev/null
cp /workspace/scene_log.txt "$WORK/" 2>/dev/null

cd "$WORK"
git add -A
git commit -m "PRAQTOR DATΔ v2 — discovery + photorealistic scene $(date -u +%Y-%m-%d)"
git push

echo ""
echo "============================================================"
echo "  DONE — STOP THE POD NOW"
echo "  Pull on your PC:"
echo "  cd C:\\Users\\utrdsweaeqwvbgf\\Documents\\PROJECTS\\PraqtorData\\Repo-praqtor-data-scripts"
echo "  git pull"
echo "============================================================"
