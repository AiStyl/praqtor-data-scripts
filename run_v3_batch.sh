#!/bin/bash
# ============================================================
# PRAQTOR DATΔ — V3 RunPod Session Runner
# ============================================================
# Runs diagnostic + 3 warehouse environments sequentially
# Total cost: ~$0.50-0.80 | Time: ~15-25 minutes
#
# Usage: bash /workspace/praqtor-data-scripts/run_v3_batch.sh
# ============================================================

set -e  # Exit on error

SCRIPT_DIR="/workspace/praqtor-data-scripts"
OUTPUT_BASE="/workspace/output_v3"
FRAMES=25

echo "================================================================"
echo "  PRAQTOR DATΔ V3 — Batch Runner"
echo "  Frames per env: $FRAMES"
echo "  Total frames: $((FRAMES * 3))"
echo "================================================================"

# Step 1: Diagnostic
echo ""
echo "=== STEP 1: DIAGNOSTIC ==="
/isaac-sim/python.sh $SCRIPT_DIR/diagnostic_v3.py
echo "=== DIAGNOSTIC COMPLETE ==="

# Step 2: Render each environment
ENVIRONMENTS=("full_warehouse" "warehouse_shelves" "warehouse_forklifts")

for env in "${ENVIRONMENTS[@]}"; do
    echo ""
    echo "=== RENDERING: $env ($FRAMES frames) ==="
    /isaac-sim/python.sh $SCRIPT_DIR/photoreal_scene_v3.py \
        --env "$env" \
        --frames $FRAMES \
        --output "$OUTPUT_BASE"
    echo "=== DONE: $env ==="
done

# Step 3: Summary
echo ""
echo "================================================================"
echo "  BATCH COMPLETE — Output Summary"
echo "================================================================"
for env in "${ENVIRONMENTS[@]}"; do
    echo ""
    echo "--- $env ---"
    if [ -d "$OUTPUT_BASE/$env" ]; then
        ls -lh "$OUTPUT_BASE/$env/" | head -5
        RGB_COUNT=$(find "$OUTPUT_BASE/$env" -name "*rgb*.png" 2>/dev/null | wc -l)
        TOTAL_SIZE=$(du -sh "$OUTPUT_BASE/$env" 2>/dev/null | cut -f1)
        echo "  RGB images: $RGB_COUNT | Total size: $TOTAL_SIZE"
    else
        echo "  [NO OUTPUT]"
    fi
done

echo ""
echo "================================================================"
echo "  Total output:"
du -sh "$OUTPUT_BASE" 2>/dev/null
echo ""
echo "  NEXT: git add + commit + push"
echo "  THEN: STOP THE POD!"
echo "================================================================"
