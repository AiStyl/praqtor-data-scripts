# PRAQTOR DATΔ — V3 Scene Improvements: Multi-LLM Validation Prompt

## Context

We are building **PRAQTOR DATΔ**, a synthetic data generation platform using NVIDIA Isaac Sim 4.2.0 running headless on a RunPod RTX 4090 GPU ($0.59/hr). We have **successfully generated photorealistic warehouse images** with real NVIDIA assets and need to improve the quality for buyer demos.

## What Works (Proven in v2)

- Isaac Sim 4.2.0 headless on RTX 4090 via `SimulationApp({"headless": True, "renderer": "RayTracedLighting"})`
- Asset root resolves to: `http://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/4.2`
- `open_stage()` loads full warehouse USD from S3
- `rep.create.from_usd()` spawns forklifts, traffic cones, pallets, cardboard boxes with semantics
- `rep.create.from_usd()` loads real human character models (construction worker, police, medical)
- BasicWriter outputs RGB (1.4MB each) + bounding_box_2d_tight + semantic_segmentation
- `rep.orchestrator.run_until_complete()` for blocking execution
- 25-frame warm-up via `simulation_app.update()` loop
- `rep.modify.pose()` with `rep.distribution.uniform()` for randomization
- Camera randomization with `look_at` parameter

## Confirmed Available Assets (from discovery)

**Warehouse Environments:**
- `/Isaac/Environments/Simple_Warehouse/full_warehouse.usd`
- `/Isaac/Environments/Simple_Warehouse/warehouse.usd`
- `/Isaac/Environments/Simple_Warehouse/warehouse_with_forklifts.usd`
- `/Isaac/Environments/Simple_Warehouse/warehouse_multiple_shelves.usd`

**People (all load successfully but appear in T-pose):**
- `/Isaac/People/Characters/original_male_adult_construction_03/male_adult_construction_03.usd`
- `/Isaac/People/Characters/original_female_adult_police_01/female_adult_police_01.usd`
- `/Isaac/People/Characters/original_male_adult_police_04/male_adult_police_04.usd`
- `/Isaac/People/Characters/original_male_adult_medical_01/male_adult_medical_01.usd`

**Props:**
- `/Isaac/Props/Forklift/forklift.usd`
- `/Isaac/Environments/Simple_Warehouse/Props/S_TrafficCone.usd`
- `/Isaac/Environments/Simple_Warehouse/Props/SM_PaletteA_01.usd`
- `/Isaac/Environments/Simple_Warehouse/Props/SM_CardBoxD_04.usd`
- `/Isaac/Environments/Simple_Warehouse/Props/SM_CardBoxA_01.usd`
- `/Isaac/Environments/Simple_Warehouse/Props/SM_CardBoxB_01.usd`
- `/Isaac/Environments/Simple_Warehouse/Props/SM_RackShelf_01.usd`

## Current v2 Script Pattern (simplified)

```python
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True, "renderer": "RayTracedLighting", "width": 1280, "height": 720})

import omni.replicator.core as rep
from omni.isaac.core.utils.stage import open_stage
from omni.isaac.nucleus import get_assets_root_path

assets_root = get_assets_root_path()
open_stage(assets_root + "/Isaac/Environments/Simple_Warehouse/full_warehouse.usd")

# Wait for streaming
for i in range(50):
    simulation_app.update()
    time.sleep(0.3)

with rep.new_layer():
    dome = rep.create.light(light_type="Dome", intensity=1500)
    sun = rep.create.light(light_type="Distant", intensity=4000, rotation=(60, 30, 0))

    vehicles = rep.create.from_usd(
        assets_root + "/Isaac/Props/Forklift/forklift.usd",
        semantics=[("class", "forklift")], count=2)

    pedestrians = rep.create.from_usd(
        assets_root + "/Isaac/People/Characters/original_male_adult_construction_03/male_adult_construction_03.usd",
        semantics=[("class", "person")], count=2)

    cam = rep.create.camera(position=(5, -8, 3), look_at=(0, 5, 1), focal_length=28.0)
    rp = rep.create.render_product(cam, (1280, 720))

    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(output_dir="/workspace/output_v2", rgb=True, bounding_box_2d_tight=True, semantic_segmentation=True)
    writer.attach([rp])

    with rep.trigger.on_frame(max_execs=10):
        with vehicles:
            rep.modify.pose(position=rep.distribution.uniform((-5,-5,0),(5,5,0)),
                           rotation=(0,0,rep.distribution.uniform(-180,180)))
        with pedestrians:
            rep.modify.pose(position=rep.distribution.uniform((-8,-8,0),(8,8,0)))
        with cam:
            rep.modify.pose(position=rep.distribution.uniform((3,-12,2),(8,-5,5)), look_at=(0,5,1))

rep.orchestrator.run_until_complete()
simulation_app.close()
```

## Problems to Solve (Priority Order)

### Problem 1: T-Pose (CRITICAL)
Human characters load in T-pose (arms straight out). This is a known issue when loading character USDs via Python API in standalone/headless mode — the animation graph doesn't get triggered. 

**What I've found so far:**
- NVIDIA forum confirms T-pose in standalone: https://forums.developer.nvidia.com/t/people-animations-in-standalone-app/282800
- GitHub discussion shows a PeopleGenerator pattern using UsdSkelBindingAPI: https://github.com/isaac-sim/IsaacSim/discussions/464
- The approach involves: find SkelRoot → create animation prim → add reference to .skelanim clip → bind via UsdSkelBindingAPI
- BUT: the forum poster said "i could play animations that were attached to biped_setup.usd but none of the other characters"
- The character USDs have retargeted skeletons — the ManRoot hierarchy contains the skeleton

**What I need from you:**
1. In Isaac Sim 4.2.0 headless standalone, what is the correct way to apply a standing idle or walking animation to `/Isaac/People/Characters/original_male_adult_construction_03/male_adult_construction_03.usd`?
2. Is there a `.skelanim` file on the S3 asset server that contains idle/walk animations for these characters?
3. If animation binding is too complex for headless mode, is there a simpler approach — like manually rotating the shoulder joints via USD transforms to bring arms down from T-pose?
4. Would it work to use `omni.anim.people` extension in headless standalone mode, or does it require the GUI?

### Problem 2: Object Clipping
People's feet clip through pallets. The randomizer places both at Z=0. 

**Question:** What's the best approach — offset person Z by pallet height, use `rep.randomizer.scatter_2d()` to place objects on surfaces, or enable physics collision?

### Problem 3: Scene Variety
We want to rotate between multiple warehouse layouts across a batch.

**Question:** Can we call `open_stage()` multiple times within a Replicator session to swap environments mid-batch? Or do we need separate runs per environment?

### Problem 4: Scaling to 50+ Frames
Currently generating 10 frames. Want to scale to 50-100 per run.

**Question:** Any performance considerations? Does VRAM accumulate across frames, or is each frame independent? Our RTX 4090 has 24GB.

### Problem 5: Multiple Character Models
We have 4 character USDs. Want to load different characters in different frames.

**Question:** Can `rep.create.from_usd()` accept a list of USDs and randomly select per frame? Or do we need to load all 4 and randomize visibility?

## Additional Suggestions Welcome

- Any other improvements to make these images more realistic for warehouse safety training data buyers?
- Are there additional free assets on the S3 server we might have missed?
- Recommended camera angles and lighting setups for warehouse surveillance training data?
- Any Replicator features we should be using (depth output, instance segmentation, normals)?

## Response Format

Please provide:
1. Working code snippets for each solution (tested against Isaac Sim 4.2 APIs if possible)
2. Confidence level (high/medium/low) for each approach
3. Known pitfalls or alternative approaches if your primary suggestion doesn't work
4. Any corrections to my understanding of the APIs
