"""
PRAQTOR DATΔ — Blender Synthetic Data Generator v2
====================================================
Blender 4.2.0 | Cycles GPU | RTX 4090 | RunPod
Target: 5/10 image quality

Changes from v1:
- Camera lower and closer (4m high vs 8m, angled 55 deg down)
- Objects bigger and more prominent
- Better warehouse aesthetic (darker walls, concrete floor texture)
- More boxes per pallet
- Forklift-style yellow markings on floor
- Better color variety on boxes
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
# SETUP
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

prefs = bpy.context.preferences
cprefs = prefs.addons['cycles'].preferences
cprefs.refresh_devices()
for device in cprefs.devices:
    device.use = True

print("[PRAQTOR DATδ v2] Cycles GPU ready.")

# ============================================================
# MATERIALS
# ============================================================

def make_mat(name, color, roughness=0.8, metallic=0.0, emission=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (*color, 1.0)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    out = nodes.new('ShaderNodeOutputMaterial')
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat

# Procedural concrete floor with noise texture
def make_concrete_mat():
    mat = bpy.data.materials.new("Concrete")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    tex_coord = nodes.new('ShaderNodeTexCoord')
    mapping = nodes.new('ShaderNodeMapping')
    mapping.inputs['Scale'].default_value = (8, 8, 8)

    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 12.0
    noise.inputs['Detail'].default_value = 8.0
    noise.inputs['Roughness'].default_value = 0.7
    noise.inputs['Distortion'].default_value = 0.2

    color_ramp = nodes.new('ShaderNodeValToRGB')
    color_ramp.color_ramp.elements[0].color = (0.28, 0.27, 0.25, 1.0)
    color_ramp.color_ramp.elements[1].color = (0.45, 0.43, 0.40, 1.0)

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.88
    out = nodes.new('ShaderNodeOutputMaterial')

    links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])
    links.new(mapping.outputs['Vector'], noise.inputs['Vector'])
    links.new(noise.outputs['Fac'], color_ramp.inputs['Fac'])
    links.new(color_ramp.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat

# Procedural wood with grain
def make_wood_mat():
    mat = bpy.data.materials.new("Wood")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    tex_coord = nodes.new('ShaderNodeTexCoord')
    wave = nodes.new('ShaderNodeTexWave')
    wave.wave_type = 'BANDS'
    wave.inputs['Scale'].default_value = 8.0
    wave.inputs['Distortion'].default_value = 2.0
    wave.inputs['Detail'].default_value = 4.0

    color_ramp = nodes.new('ShaderNodeValToRGB')
    color_ramp.color_ramp.elements[0].color = (0.38, 0.22, 0.08, 1.0)
    color_ramp.color_ramp.elements[1].color = (0.62, 0.42, 0.18, 1.0)

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.72
    out = nodes.new('ShaderNodeOutputMaterial')

    links.new(tex_coord.outputs['Generated'], wave.inputs['Vector'])
    links.new(wave.outputs['Fac'], color_ramp.inputs['Fac'])
    links.new(color_ramp.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat

concrete_mat = make_concrete_mat()
wood_mat = make_wood_mat()
cardboard_mats = [
    make_mat("Cardboard_A", (0.72, 0.55, 0.32), 0.90),
    make_mat("Cardboard_B", (0.65, 0.50, 0.28), 0.85),
    make_mat("Cardboard_C", (0.78, 0.60, 0.35), 0.88),
]
metal_mat = make_mat("Metal", (0.7, 0.7, 0.72), 0.3, 0.9)
wall_mat = make_mat("Wall", (0.55, 0.52, 0.48), 0.92)
yellow_mat = make_mat("Yellow", (0.95, 0.75, 0.02), 0.7)
stripe_mat = make_mat("Stripe", (0.15, 0.15, 0.15), 0.9)

# ============================================================
# SCENE GEOMETRY
# ============================================================

def add_floor():
    bpy.ops.mesh.primitive_plane_add(size=24, location=(0, 0, 0))
    floor = bpy.context.active_object
    floor.name = "Floor"
    floor.data.materials.append(concrete_mat)
    return floor

def add_warehouse_structure():
    # Back wall
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 10, 3.5))
    w = bpy.context.active_object
    w.scale = (12, 1, 7)
    w.rotation_euler = (math.radians(90), 0, 0)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    w.data.materials.append(wall_mat)

    # Left wall
    bpy.ops.mesh.primitive_plane_add(size=1, location=(-10, 0, 3.5))
    w2 = bpy.context.active_object
    w2.scale = (1, 12, 7)
    w2.rotation_euler = (0, math.radians(90), 0)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    w2.data.materials.append(wall_mat)

    # Ceiling
    bpy.ops.mesh.primitive_plane_add(size=24, location=(0, 0, 7))
    ceil = bpy.context.active_object
    ceil.name = "Ceiling"
    ceil.rotation_euler = (math.radians(180), 0, 0)
    bpy.ops.object.transform_apply(rotation=True)
    ceil.data.materials.append(make_mat("Ceiling", (0.6, 0.6, 0.6), 0.9))

    # Floor safety stripes
    for i, x in enumerate([-3, 0, 3]):
        bpy.ops.mesh.primitive_plane_add(size=1, location=(x, 2, 0.001))
        stripe = bpy.context.active_object
        stripe.scale = (0.15, 8, 1)
        bpy.ops.object.transform_apply(scale=True)
        stripe.data.materials.append(yellow_mat if i % 2 == 0 else stripe_mat)

def add_pallet(x, y, rot_z=0):
    group = []
    # Bottom runners
    for rx in [-0.55, 0, 0.55]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x+rx, y, 0.05))
        b = bpy.context.active_object
        b.scale = (0.1, 1.2, 0.05)
        b.rotation_euler = (0, 0, rot_z)
        bpy.ops.object.transform_apply(scale=True)
        b.data.materials.append(wood_mat)
        group.append(b)
    # Top planks
    for i in range(8):
        px = x + (-0.6 + i * 0.17)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(px, y, 0.13))
        p = bpy.context.active_object
        p.scale = (0.07, 1.2, 0.03)
        p.rotation_euler = (0, 0, rot_z)
        bpy.ops.object.transform_apply(scale=True)
        p.data.materials.append(wood_mat)
        group.append(p)
    return group

def add_box(x, y, z, w=0.45, d=0.35, h=0.38, rot_z=0, mat_idx=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z + h/2))
    box = bpy.context.active_object
    box.scale = (w/2, d/2, h/2)
    box.rotation_euler = (0, 0, rot_z)
    bpy.ops.object.transform_apply(scale=True)
    box.data.materials.append(cardboard_mats[mat_idx % len(cardboard_mats)])
    return box

def add_rack(x, y):
    for px, py in [(x-1.0, y-0.5), (x+1.0, y-0.5), (x-1.0, y+0.5), (x+1.0, y+0.5)]:
        bpy.ops.mesh.primitive_cylinder_add(radius=0.04, depth=3.5, location=(px, py, 1.75))
        bpy.context.active_object.data.materials.append(metal_mat)
    for h in [0.6, 1.4, 2.2]:
        for fy in [y-0.5, y+0.5]:
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x, fy, h))
            b = bpy.context.active_object
            b.scale = (1.05, 0.04, 0.04)
            bpy.ops.object.transform_apply(scale=True)
            b.data.materials.append(metal_mat)
    # Shelf boards
    for h in [0.6, 1.4]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, h+0.05))
        shelf = bpy.context.active_object
        shelf.scale = (1.0, 0.48, 0.02)
        bpy.ops.object.transform_apply(scale=True)
        shelf.data.materials.append(make_mat("Shelf", (0.4, 0.35, 0.3), 0.8))

# ============================================================
# LIGHTING — warehouse fluorescent style
# ============================================================
def setup_lighting():
    # 4 overhead area lights simulating fluorescent tubes
    for x, y in [(-3, -2), (3, -2), (-3, 4), (3, 4)]:
        bpy.ops.object.light_add(type='AREA', location=(x, y, 6.5))
        light = bpy.context.active_object
        light.data.energy = 1500
        light.data.size = 3.0
        light.data.size_y = 0.3
        light.data.color = (1.0, 0.97, 0.88)
        light.rotation_euler = (0, 0, 0)

    # Ambient world light
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.04, 0.05, 0.08, 1.0)
    bg.inputs['Strength'].default_value = 0.15

# ============================================================
# CAMERA — lower, closer, better angle
# ============================================================
def setup_camera():
    # Position: 4.5m high, 5m back — looking down at 55 degrees
    bpy.ops.object.camera_add(location=(4.5, -5.0, 4.5))
    cam = bpy.context.active_object
    cam.name = "SDGCamera"
    cam.rotation_euler = (math.radians(58), 0, math.radians(35))
    cam.data.lens = 28
    cam.data.clip_start = 0.1
    cam.data.clip_end = 50
    scene.camera = cam
    return cam

# ============================================================
# BUILD BASE SCENE
# ============================================================
print("[PRAQTOR DATδ v2] Building scene...")
add_floor()
add_warehouse_structure()
setup_lighting()
cam = setup_camera()

# Static background racks
add_rack(-7, 7)
add_rack(0, 9)
add_rack(7, 7)

print("[PRAQTOR DATδ v2] Base scene built. Starting render loop...")

# ============================================================
# RENDER LOOP
# ============================================================
random.seed(99)

# Fixed pallet grid positions in camera view
grid = [
    (-2.0, 0.5), (0.5, 0.5), (2.5, 1.5),
    (-1.5, 3.0), (1.0, 3.5), (3.0, 3.5),
]

for frame_idx in range(NUM_FRAMES):
    print(f"\n[PRAQTOR DATδ v2] Frame {frame_idx+1}/{NUM_FRAMES}...")

    # Remove previous dynamic objects
    for obj in list(bpy.data.objects):
        if obj.name.startswith("DYN_"):
            bpy.data.objects.remove(obj, do_unlink=True)

    # Place 3-5 pallets with boxes
    num_pallets = random.randint(3, 5)
    positions = random.sample(grid, num_pallets)

    for pos in positions:
        px = pos[0] + random.uniform(-0.3, 0.3)
        py = pos[1] + random.uniform(-0.3, 0.3)
        rot = random.uniform(-math.pi/6, math.pi/6)

        pallet_objs = add_pallet(px, py, rot)
        for i, obj in enumerate(pallet_objs):
            obj.name = f"DYN_pallet_{frame_idx}_{i}"

        # Stack 2-4 boxes
        num_boxes = random.randint(2, 4)
        for layer in range(num_boxes):
            bx = px + random.uniform(-0.15, 0.15)
            by = py + random.uniform(-0.08, 0.08)
            bz = 0.16 + layer * 0.38
            bw = random.uniform(0.35, 0.52)
            bd = random.uniform(0.28, 0.42)
            bh = random.uniform(0.30, 0.40)
            box = add_box(bx, by, bz, bw, bd, bh,
                         random.uniform(-0.25, 0.25),
                         random.randint(0, 2))
            box.name = f"DYN_box_{frame_idx}_{layer}"

    # Small camera shake
    cam.location.x = 4.5 + random.uniform(-0.3, 0.3)
    cam.location.y = -5.0 + random.uniform(-0.3, 0.3)
    cam.location.z = 4.5 + random.uniform(-0.2, 0.2)
    cam.rotation_euler[2] = math.radians(35) + random.uniform(-0.05, 0.05)

    output_path = os.path.join(OUTPUT_DIR, f"rgb_{frame_idx:04d}.png")
    scene.render.filepath = output_path
    bpy.ops.render.render(write_still=True)
    print(f"[PRAQTOR DATδ v2] Saved: {output_path}")

print(f"\n[PRAQTOR DATδ v2] Done! {NUM_FRAMES} frames in {OUTPUT_DIR}")
