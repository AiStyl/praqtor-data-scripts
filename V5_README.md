# PRAQTOR DATΔ — V5 Animation Fix Pipeline

## The Problem
Isaac Sim 4.2 disables `omni.anim.graph.core` in headless/standalone mode by default.
This means `CharacterManager` never initializes, so skeletal animations never evaluate,
and all characters render in T-pose regardless of animation bindings.

## The Fix
Uncomment `"omni.anim.graph.core" = {}` in the kit config file. This is the confirmed
fix from NVIDIA Developer Forums (user 555kd, May 2024).

## Files
- `patch_kit_config.py` — Patches kit config (run ONCE per pod)
- `verify_v5.py` — Quick verification (~90 sec, confirms patch works)
- `photoreal_v5.py` — Full render pipeline (3 warehouses, animated characters)

## Pod Commands (copy-paste these in order)

### Step 1: Pull latest code
```
cd /workspace/praqtor-data-scripts && git pull
```

### Step 2: Patch kit config (run once per pod)
```
python3 patch_kit_config.py
```

### Step 3: Verify patch works
```
/isaac-sim/python.sh verify_v5.py 2>/dev/null; cat /workspace/v5_verify.txt
```
Look for: `PASS - Kit config patch is working!`

### Step 4: Run full render (if verify passed)
```
/isaac-sim/python.sh photoreal_v5.py 2>/dev/null; cat /workspace/v5_log.txt
```

### Step 5: Push preview + download
```
cd /workspace/praqtor-data-scripts && git add v5_*.png && git commit -m "v5 renders" && git push
```

## Expected Output
- 3 warehouse scenes × 4 camera angles = ~12 unique viewpoints
- 1920×1080 photorealistic renders with semantic segmentation
- Characters in natural poses (idle, looking around) — NOT T-pose
- Tarball at /workspace/output_v5.tar.gz

## Cost Estimate
- Patch + Verify: ~2 min = $0.03
- Full render: ~5-8 min = $0.10-0.15
- Total: ~$0.20

## References
- Fix source: https://forums.developer.nvidia.com/t/people-animations-in-standalone-app/282800/10
- omni.anim.people docs: Isaac Sim 4.2 > Warehouse Logistics > Omni.Anim.People
- Kit config: /isaac-sim/apps/omni.isaac.sim.python.kit
