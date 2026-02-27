"""PRAQTOR DATΔ — Step 1: Patch Kit Config for Animation Support
Run this ONCE per pod session before running the main render script.
Uncomments omni.anim.graph.core in the kit config file so that
CharacterManager initializes properly in headless/standalone mode.
Reference: https://forums.developer.nvidia.com/t/people-animations-in-standalone-app/282800/10
"""
import re, shutil, sys

KIT_FILE = "/isaac-sim/apps/omni.isaac.sim.python.kit"
BACKUP = KIT_FILE + ".backup"

# Read current config
with open(KIT_FILE, "r") as f:
    content = f.read()

# Check if already patched
if '"omni.anim.graph.core" = {}' in content:
    # Check if it's commented out
    lines = content.split("\n")
    patched = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") and "omni.anim.graph.core" in stripped:
            # Found commented line - uncomment it
            lines[i] = line.replace("#", "", 1)
            patched = True
            print(f"[PATCH] Uncommented omni.anim.graph.core on line {i+1}")
            break
        elif not stripped.startswith("#") and '"omni.anim.graph.core"' in stripped:
            print("[PATCH] omni.anim.graph.core already enabled - no patch needed")
            sys.exit(0)

    if patched:
        # Backup original
        shutil.copy2(KIT_FILE, BACKUP)
        print(f"[PATCH] Backup saved to {BACKUP}")
        # Write patched config
        with open(KIT_FILE, "w") as f:
            f.write("\n".join(lines))
        print("[PATCH] Kit config patched successfully!")
    else:
        # Not found at all - add it to [dependencies] section
        print("[PATCH] omni.anim.graph.core not found in config, adding it...")
        shutil.copy2(KIT_FILE, BACKUP)
        # Find [dependencies] section and add after it
        new_content = content.replace(
            '[dependencies]',
            '[dependencies]\n"omni.anim.graph.core" = {}'
        )
        with open(KIT_FILE, "w") as f:
            f.write(new_content)
        print("[PATCH] Added omni.anim.graph.core to [dependencies]")
else:
    # Try to find any reference to anim.graph.core
    if "anim.graph.core" in content:
        print("[PATCH] Found anim.graph.core reference but in unexpected format")
        print("[PATCH] Adding explicit entry...")
        shutil.copy2(KIT_FILE, BACKUP)
        new_content = content.replace(
            '[dependencies]',
            '[dependencies]\n"omni.anim.graph.core" = {}'
        )
        with open(KIT_FILE, "w") as f:
            f.write(new_content)
        print("[PATCH] Added omni.anim.graph.core to [dependencies]")
    else:
        print("[PATCH] No anim.graph.core found at all - adding it...")
        shutil.copy2(KIT_FILE, BACKUP)
        new_content = content.replace(
            '[dependencies]',
            '[dependencies]\n"omni.anim.graph.core" = {}'
        )
        with open(KIT_FILE, "w") as f:
            f.write(new_content)
        print("[PATCH] Added omni.anim.graph.core to [dependencies]")

# Verify patch
with open(KIT_FILE, "r") as f:
    verify = f.read()
found = False
for line in verify.split("\n"):
    s = line.strip()
    if not s.startswith("#") and '"omni.anim.graph.core"' in s:
        found = True
        break
if found:
    print("[PATCH] VERIFIED: omni.anim.graph.core is now enabled")
    print("[PATCH] You can now run photoreal_v5.py")
else:
    print("[PATCH] WARNING: Verification failed - check the kit file manually")
    print(f"[PATCH] File: {KIT_FILE}")
