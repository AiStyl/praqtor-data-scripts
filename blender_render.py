"""
PRAQTOR DATΔ — Blender Synthetic Data Generator v1
====================================================
Blender 4.2.0 | Cycles GPU | RTX 4090 | RunPod
Run: /workspace/blender/blender --background --python blender_render.py

Generates photorealistic warehouse floor scenes with:
- Concrete floor with texture
- Wooden pallets
- Cardboard boxes
- Proper overhead lighting
- Camera looking DOWN at 45 degrees
- 10 randomized frames
"""

import bpy
import math
import random
import os

OUTPUT_DIR = "/workspace/output"
NUM_FRAMES = 10
RESOLUTION = 1024

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# SETUP: Clean scene
# ============================================================
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU'
scene.cycles.samples = 128
scene.cycles.use_denoising = True
scene.render.resolution_x = RESOLUTION
scene.render.resolution_y = RESOLUTION
scene.render.image_settings.file_format = 'PNG'

# Enable GPU rendering
prefs = bpy.context.preferences
cprefs = prefs.addons['cycles'].preferences
cprefs.refresh_devices()
for device in cprefs.devices:
    device.use = True
    print(f"  Device: {device.name} ({device.type}) - enabled")

print("[PRAQTOR DATΔ] Scene initialized with Cycles GPU.")

# ============================================================
# MATERIALS
# ============================================================

def make_concrete_material():
    mat = bpy.data.materials.new("Concrete")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.45, 0.43, 0.40, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.85
    bsdf.inputs['Metallic'].default_value = 0.0
    out = nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat

def make_wood_material():
    mat = bpy.data.materials.new("Wood")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.55, 0.38, 0.18, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.75
    out = nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat

def make_cardboard_material():
    mat = bpy.data.materials.new("Cardboard")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.72, 0.55, 0.32, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.90
    out = nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat

def make_metal_material():
    mat = bpy.data.materials.new("Metal")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.7, 0.7, 0.72, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.3
    bsdf.inputs['Metallic'].default_value = 0.95
    out = nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat

concrete_mat = make_concrete_material()
wood_mat = make_wood_material()
cardboard_mat = make_cardboard_material()
metal_mat = make_metal_material()

# ============================================================
# SCENE GEOMETRY
# ============================================================

def add_floor():
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
    floor = bpy.context.active_object
    floor.name = "Floor"
    floor.data.materials.append(concrete_mat)
    return floor

def add_warehouse_walls():
    """Simple warehouse walls for background context."""
    # Back wall
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 12, 4))
    wall = bpy.context.active_object
    wall.name = "BackWall"
    wall.scale = (15, 1, 8)
    wall.rotation_euler = (math.radians(90), 0, 0)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    wall_mat = bpy.data.materials.new("WallMat")
    wall_mat.use_nodes = True
    wall_mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.85, 0.82, 0.75, 1.0)
    wall_mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9
    wall.data.materials.append(wall_mat)

    # Left wall
    bpy.ops.mesh.primitive_plane_add(size=1, location=(-12, 0, 4))
    lwall = bpy.context.active_object
    lwall.name = "LeftWall"
    lwall.scale = (1, 15, 8)
    lwall.rotation_euler = (0, math.radians(90), 0)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    lwall.data.materials.append(wall_mat)

def add_pallet(location, rotation_z=0):
    """Create a simple wooden pallet."""
    x, y = location
    objects = []

    # Pallet base boards (3 bottom runners)
    for i, rx in enumerate([-0.5, 0, 0.5]):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x + rx, y, 0.04))
        board = bpy.context.active_object
        board.scale = (0.08, 1.1, 0.04)
        board.rotation_euler = (0, 0, rotation_z)
        bpy.ops.object.transform_apply(scale=True)
        board.data.materials.append(wood_mat)
        objects.append(board)

    # Top deck boards (7 planks)
    for i in range(7):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x + (-0.55 + i * 0.18), y, 0.10))
        plank = bpy.context.active_object
        plank.scale = (0.08, 1.1, 0.025)
        plank.rotation_euler = (0, 0, rotation_z)
        bpy.ops.object.transform_apply(scale=True)
        plank.data.materials.append(wood_mat)
        objects.append(plank)

    return objects

def add_box(location, size=(0.4, 0.3, 0.35), rotation_z=0):
    """Cardboard box."""
    x, y, z = location
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
    box = bpy.context.active_object
    box.scale = (size[0]/2, size[1]/2, size[2]/2)
    box.rotation_euler = (0, 0, rotation_z)
    bpy.ops.object.transform_apply(scale=True)
    box.data.materials.append(cardboard_mat)
    return box

def add_rack(location):
    """Simple metal rack frame."""
    x, y = location
    mat = metal_mat

    # Vertical posts
    for px, py in [(x-0.9, y-0.4), (x+0.9, y-0.4), (x-0.9, y+0.4), (x+0.9, y+0.4)]:
        bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=2.5, location=(px, py, 1.25))
        post = bpy.context.active_object
        post.data.materials.append(mat)

    # Horizontal beams
    for height in [0.5, 1.2, 1.9]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y-0.4, height))
        beam = bpy.context.active_object
        beam.scale = (0.95, 0.03, 0.03)
        bpy.ops.object.transform_apply(scale=True)
        beam.data.materials.append(mat)

        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y+0.4, height))
        beam2 = bpy.context.active_object
        beam2.scale = (0.95, 0.03, 0.03)
        bpy.ops.object.transform_apply(scale=True)
        beam2.data.materials.append(mat)

# ============================================================
# LIGHTING
# ============================================================

def setup_lighting():
    # Main overhead area lights (warehouse fluorescent style)
    for x, y in [(-4, 0), (4, 0), (0, -4), (0, 4)]:
        bpy.ops.object.light_add(type='AREA', location=(x, y, 8))
        light = bpy.context.active_object
        light.data.energy = 2000
        light.data.size = 4.0
        light.data.color = (1.0, 0.97, 0.90)
        light.rotation_euler = (0, 0, 0)

    # Sky/ambient via world HDRI simulation
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.05, 0.07, 0.12, 1.0)
    bg.inputs['Strength'].default_value = 0.3

    print("[PRAQTOR DATΔ] Lighting setup complete.")

# ============================================================
# CAMERA
# ============================================================

def setup_camera():
    bpy.ops.object.camera_add(location=(6, -6, 8))
    cam = bpy.context.active_object
    cam.name = "SDGCamera"

    # Point camera at scene center, angled down ~45 degrees
    cam.rotation_euler = (math.radians(52), 0, math.radians(45))

    cam.data.lens = 35
    cam.data.clip_start = 0.1
    cam.data.clip_end = 100

    scene.camera = cam
    print(f"[PRAQTOR DATΔ] Camera at {cam.location}, rotation {[math.degrees(r) for r in cam.rotation_euler]}")
    return cam

# ============================================================
# BUILD BASE SCENE
# ============================================================
print("[PRAQTOR DATΔ] Building scene...")
add_floor()
add_warehouse_walls()
setup_lighting()
cam = setup_camera()

# Add static racks in background
add_rack((-6, 8))
add_rack((6, 8))

print("[PRAQTOR DATΔ] Base scene built.")

# ============================================================
# RENDER LOOP — randomize and render each frame
# ============================================================
random.seed(42)

pallet_positions = [
    (-1.5, 1.0), (1.5, 0.5), (0.0, -1.5), (-2.5, -0.5), (2.5, 1.5)
]

for frame_idx in range(NUM_FRAMES):
    print(f"\n[PRAQTOR DATΔ] Rendering frame {frame_idx+1}/{NUM_FRAMES}...")

    # Remove previous frame objects
    for obj in list(bpy.data.objects):
        if obj.name.startswith("Frame_"):
            bpy.data.objects.remove(obj, do_unlink=True)

    # Randomize pallet placement
    num_pallets = random.randint(2, 4)
    used_positions = random.sample(pallet_positions, num_pallets)

    for pos in used_positions:
        rot_z = random.uniform(-math.pi/4, math.pi/4)
        pallet_objs = add_pallet(pos, rot_z)
        for obj in pallet_objs:
            obj.name = f"Frame_{frame_idx}_" + obj.name

        # Stack 1-3 boxes on pallet
        num_boxes = random.randint(1, 3)
        for layer in range(num_boxes):
            bx = pos[0] + random.uniform(-0.2, 0.2)
            by = pos[1] + random.uniform(-0.1, 0.1)
            bz = 0.13 + layer * 0.36
            bsize = (
                random.uniform(0.3, 0.55),
                random.uniform(0.25, 0.45),
                random.uniform(0.28, 0.40)
            )
            box = add_box((bx, by, bz), bsize, random.uniform(-0.3, 0.3))
            box.name = f"Frame_{frame_idx}_Box_{layer}"

    # Slight camera variation
    cam.location.x = 6 + random.uniform(-0.5, 0.5)
    cam.location.y = -6 + random.uniform(-0.5, 0.5)
    cam.location.z = 8 + random.uniform(-0.3, 0.3)

    # Render
    output_path = os.path.join(OUTPUT_DIR, f"rgb_{frame_idx:04d}.png")
    scene.render.filepath = output_path
    bpy.ops.render.render(write_still=True)
    print(f"[PRAQTOR DATΔ] Saved: {output_path}")

print(f"\n[PRAQTOR DATΔ] Done! {NUM_FRAMES} frames saved to {OUTPUT_DIR}")
