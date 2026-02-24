"""
PRAQTOR DATΔ — Blender Synthetic Data Generator v3
====================================================
Blender 4.2.0 | Cycles GPU | RTX 4090 | RunPod
Target: 7/10 image quality

Key upgrades from v2:
- Polyhaven PBR textures on all surfaces (concrete, wood, metal)
- Industrial HDRI lighting for realistic ambient
- Orange industrial rack colors
- Proper cardboard box colors with tape details
- Darker warehouse walls with proper texture
- Better object scale and density
"""

import bpy
import math
import random
import os

OUTPUT_DIR = "/workspace/output"
NUM_FRAMES = 10
RESOLUTION = 1024
TEX = "/workspace/polyhaven/textures"
HDRI = "/workspace/polyhaven/hdri/industrial.hdr"

os.makedirs(OUTPUT_DIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU'
scene.cycles.samples = 256
scene.cycles.use_denoising = True
scene.render.resolution_x = RESOLUTION
scene.render.resolution_y = RESOLUTION
scene.render.image_settings.file_format = 'PNG'

prefs = bpy.context.preferences
cprefs = prefs.addons['cycles'].preferences
cprefs.refresh_devices()
for device in cprefs.devices:
    device.use = True

print("[PRAQTOR DATδ v3] Cycles GPU ready.")

# ============================================================
# PBR MATERIAL BUILDER
# ============================================================

def make_pbr_mat(name, diff_path=None, rough_path=None, normal_path=None,
                 metal_path=None, base_color=(0.5,0.5,0.5),
                 roughness=0.8, metallic=0.0, scale=4.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out = nodes.new('ShaderNodeOutputMaterial')
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    tex_coord = nodes.new('ShaderNodeTexCoord')
    mapping = nodes.new('ShaderNodeMapping')
    mapping.inputs['Scale'].default_value = (scale, scale, scale)
    links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

    if diff_path and os.path.exists(diff_path):
        img = bpy.data.images.load(diff_path)
        diff_node = nodes.new('ShaderNodeTexImage')
        diff_node.image = img
        links.new(mapping.outputs['Vector'], diff_node.inputs['Vector'])
        links.new(diff_node.outputs['Color'], bsdf.inputs['Base Color'])
    else:
        bsdf.inputs['Base Color'].default_value = (*base_color, 1.0)

    if rough_path and os.path.exists(rough_path):
        img = bpy.data.images.load(rough_path)
        img.colorspace_settings.name = 'Non-Color'
        rough_node = nodes.new('ShaderNodeTexImage')
        rough_node.image = img
        links.new(mapping.outputs['Vector'], rough_node.inputs['Vector'])
        links.new(rough_node.outputs['Color'], bsdf.inputs['Roughness'])
    else:
        bsdf.inputs['Roughness'].default_value = roughness

    if metal_path and os.path.exists(metal_path):
        img = bpy.data.images.load(metal_path)
        img.colorspace_settings.name = 'Non-Color'
        metal_node = nodes.new('ShaderNodeTexImage')
        metal_node.image = img
        links.new(mapping.outputs['Vector'], metal_node.inputs['Vector'])
        links.new(metal_node.outputs['Color'], bsdf.inputs['Metallic'])
    else:
        bsdf.inputs['Metallic'].default_value = metallic

    if normal_path and os.path.exists(normal_path):
        img = bpy.data.images.load(normal_path)
        img.colorspace_settings.name = 'Non-Color'
        norm_node = nodes.new('ShaderNodeTexImage')
        norm_node.image = img
        norm_map = nodes.new('ShaderNodeNormalMap')
        norm_map.inputs['Strength'].default_value = 1.2
        links.new(mapping.outputs['Vector'], norm_node.inputs['Vector'])
        links.new(norm_node.outputs['Color'], norm_map.inputs['Color'])
        links.new(norm_map.outputs['Normal'], bsdf.inputs['Normal'])

    return mat

def make_flat_mat(name, color, roughness=0.8, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (*color, 1.0)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    out = nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat

# Build materials
print("[PRAQTOR DATδ v3] Building PBR materials...")
concrete_mat = make_pbr_mat("Concrete",
    diff_path=f"{TEX}/concrete/diff.jpg",
    rough_path=f"{TEX}/concrete/rough.jpg",
    normal_path=f"{TEX}/concrete/normal.jpg",
    scale=6.0)

wood_mat = make_pbr_mat("Wood",
    diff_path=f"{TEX}/wood_planks/diff.jpg",
    rough_path=f"{TEX}/wood_planks/rough.jpg",
    normal_path=f"{TEX}/wood_planks/normal.jpg",
    scale=3.0)

metal_mat = make_pbr_mat("Metal",
    diff_path=f"{TEX}/metal_plate/diff.jpg",
    rough_path=f"{TEX}/metal_plate/rough.jpg",
    normal_path=f"{TEX}/metal_plate/normal.jpg",
    metal_path=f"{TEX}/metal_plate/metal.jpg",
    scale=2.0)

cardboard_mats = [
    make_flat_mat("Cardboard_A", (0.68, 0.50, 0.28), 0.90),
    make_flat_mat("Cardboard_B", (0.60, 0.44, 0.24), 0.88),
    make_flat_mat("Cardboard_C", (0.75, 0.56, 0.32), 0.85),
]
tape_mat = make_flat_mat("Tape", (0.85, 0.80, 0.55), 0.5)
rack_mat = make_flat_mat("RackOrange", (0.85, 0.35, 0.05), 0.6, 0.3)
rack_beam_mat = make_flat_mat("RackBeam", (0.75, 0.65, 0.10), 0.5, 0.4)
wall_mat = make_flat_mat("Wall", (0.52, 0.50, 0.46), 0.92)
ceiling_mat = make_flat_mat("Ceiling", (0.55, 0.55, 0.55), 0.9)
yellow_mat = make_flat_mat("Yellow", (0.95, 0.75, 0.02), 0.6)
print("[PRAQTOR DATδ v3] Materials ready.")

# ============================================================
# SCENE GEOMETRY
# ============================================================

def add_floor():
    bpy.ops.mesh.primitive_plane_add(size=28, location=(0, 2, 0))
    f = bpy.context.active_object
    f.name = "Floor"
    f.data.materials.append(concrete_mat)

def add_warehouse_structure():
    # Back wall
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 12, 4))
    w = bpy.context.active_object
    w.scale = (14, 1, 8)
    w.rotation_euler = (math.radians(90), 0, 0)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    w.data.materials.append(wall_mat)

    # Left wall
    bpy.ops.mesh.primitive_plane_add(size=1, location=(-12, 2, 4))
    w2 = bpy.context.active_object
    w2.scale = (1, 14, 8)
    w2.rotation_euler = (0, math.radians(90), 0)
    bpy.ops.object.transform_apply(scale=True, rotation=True)
    w2.data.materials.append(wall_mat)

    # Ceiling
    bpy.ops.mesh.primitive_plane_add(size=28, location=(0, 2, 7.5))
    c = bpy.context.active_object
    c.rotation_euler = (math.radians(180), 0, 0)
    bpy.ops.object.transform_apply(rotation=True)
    c.data.materials.append(ceiling_mat)

    # Floor safety stripes
    stripe_positions = [(-4, 2), (0, 2), (4, 2)]
    for i, (sx, sy) in enumerate(stripe_positions):
        bpy.ops.mesh.primitive_plane_add(size=1, location=(sx, sy, 0.002))
        s = bpy.context.active_object
        s.scale = (0.2, 10, 1)
        bpy.ops.object.transform_apply(scale=True)
        s.data.materials.append(yellow_mat)

def add_pallet(x, y, rot_z=0):
    group = []
    # Bottom runners (3)
    for rx in [-0.55, 0.0, 0.55]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x+rx, y, 0.06))
        b = bpy.context.active_object
        b.scale = (0.1, 1.2, 0.06)
        b.rotation_euler = (0, 0, rot_z)
        bpy.ops.object.transform_apply(scale=True)
        b.data.materials.append(wood_mat)
        group.append(b)
    # Top deck planks (9)
    for i in range(9):
        px = x + (-0.64 + i * 0.16)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(px, y, 0.145))
        p = bpy.context.active_object
        p.scale = (0.065, 1.2, 0.04)
        p.rotation_euler = (0, 0, rot_z)
        bpy.ops.object.transform_apply(scale=True)
        p.data.materials.append(wood_mat)
        group.append(p)
    return group

def add_box(x, y, z, w=0.45, d=0.38, h=0.40, rot_z=0, mat_idx=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z + h/2))
    box = bpy.context.active_object
    box.scale = (w/2, d/2, h/2)
    box.rotation_euler = (0, 0, rot_z)
    bpy.ops.object.transform_apply(scale=True)
    box.data.materials.append(cardboard_mats[mat_idx % 3])
    # Add tape strip on top
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z + h - 0.005))
    tape = bpy.context.active_object
    tape.scale = (0.04, d/2, 0.005)
    tape.rotation_euler = (0, 0, rot_z)
    bpy.ops.object.transform_apply(scale=True)
    tape.data.materials.append(tape_mat)
    return box

def add_industrial_rack(x, y):
    # Vertical orange uprights
    for px, py in [(x-1.1, y-0.55), (x+1.1, y-0.55),
                   (x-1.1, y+0.55), (x+1.1, y+0.55)]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(px, py, 1.8))
        post = bpy.context.active_object
        post.scale = (0.045, 0.045, 1.8)
        bpy.ops.object.transform_apply(scale=True)
        post.data.materials.append(rack_mat)
    # Yellow cross beams
    for h in [0.5, 1.2, 2.0]:
        for fy in [y-0.55, y+0.55]:
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x, fy, h))
            beam = bpy.context.active_object
            beam.scale = (1.15, 0.04, 0.04)
            bpy.ops.object.transform_apply(scale=True)
            beam.data.materials.append(rack_beam_mat)
        # Shelf surface
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, h + 0.03))
        shelf = bpy.context.active_object
        shelf.scale = (1.1, 0.52, 0.02)
        bpy.ops.object.transform_apply(scale=True)
        shelf.data.materials.append(metal_mat)
        # Box on shelf
        if h < 1.5:
            bx = x + random.uniform(-0.3, 0.3)
            add_box(bx, y, h + 0.06, 0.38, 0.30, 0.35, 0, random.randint(0,2))

# ============================================================
# LIGHTING — HDRI + overhead fluorescents
# ============================================================
def setup_lighting():
    # HDRI world lighting
    world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()

    bg = nodes.new('ShaderNodeBackground')
    out = nodes.new('ShaderNodeOutputWorld')
    links.new(bg.outputs['Background'], out.inputs['Surface'])

    if os.path.exists(HDRI):
        tex_env = nodes.new('ShaderNodeTexEnvironment')
        tex_env.image = bpy.data.images.load(HDRI)
        links.new(tex_env.outputs['Color'], bg.inputs['Color'])
        bg.inputs['Strength'].default_value = 0.4
        print("[PRAQTOR DATδ v3] HDRI loaded.")
    else:
        bg.inputs['Color'].default_value = (0.04, 0.05, 0.09, 1.0)
        bg.inputs['Strength'].default_value = 0.2

    # Overhead fluorescent area lights
    for x, y in [(-3.5, -1), (3.5, -1), (-3.5, 5), (3.5, 5), (0, 2)]:
        bpy.ops.object.light_add(type='AREA', location=(x, y, 7.0))
        light = bpy.context.active_object
        light.data.energy = 1200
        light.data.size = 2.5
        light.data.size_y = 0.25
        light.data.color = (1.0, 0.96, 0.85)
        light.rotation_euler = (0, 0, 0)
        # Hide light geometry from camera
        light.hide_render = False
        light.data.use_shadow = True

# ============================================================
# CAMERA
# ============================================================
def setup_camera():
    bpy.ops.object.camera_add(location=(5.5, -5.5, 5.0))
    cam = bpy.context.active_object
    cam.name = "SDGCamera"
    cam.rotation_euler = (math.radians(55), 0, math.radians(38))
    cam.data.lens = 32
    cam.data.clip_start = 0.1
    cam.data.clip_end = 60
    scene.camera = cam
    return cam

# ============================================================
# BUILD SCENE
# ============================================================
print("[PRAQTOR DATδ v3] Building scene...")
add_floor()
add_warehouse_structure()
setup_lighting()
cam = setup_camera()

# Static background racks with boxes
add_industrial_rack(-7.5, 9)
add_industrial_rack(0, 10)
add_industrial_rack(7.5, 9)

print("[PRAQTOR DATδ v3] Scene built. Starting render loop...")

# ============================================================
# RENDER LOOP
# ============================================================
random.seed(77)

pallet_grid = [
    (-2.5, 0.5), (0.2, 0.5), (2.8, 1.0),
    (-2.0, 3.2), (0.8, 3.5), (3.2, 3.0),
    (-3.5, 1.8), (1.5, 2.0),
]

for frame_idx in range(NUM_FRAMES):
    print(f"\n[PRAQTOR DATδ v3] Frame {frame_idx+1}/{NUM_FRAMES}...")

    for obj in list(bpy.data.objects):
        if obj.name.startswith("DYN_"):
            bpy.data.objects.remove(obj, do_unlink=True)

    num_pallets = random.randint(4, 6)
    positions = random.sample(pallet_grid, num_pallets)

    for pos in positions:
        px = pos[0] + random.uniform(-0.2, 0.2)
        py = pos[1] + random.uniform(-0.2, 0.2)
        rot = random.uniform(-math.pi/5, math.pi/5)

        pallet_objs = add_pallet(px, py, rot)
        for i, obj in enumerate(pallet_objs):
            obj.name = f"DYN_pallet_{frame_idx}_{i}"

        num_boxes = random.randint(2, 5)
        for layer in range(num_boxes):
            bx = px + random.uniform(-0.18, 0.18)
            by = py + random.uniform(-0.10, 0.10)
            bz = 0.19 + layer * 0.41
            bw = random.uniform(0.38, 0.55)
            bd = random.uniform(0.30, 0.46)
            bh = random.uniform(0.32, 0.42)
            box = add_box(bx, by, bz, bw, bd, bh,
                         random.uniform(-0.3, 0.3),
                         random.randint(0, 2))
            box.name = f"DYN_box_{frame_idx}_{layer}"

    # Subtle camera variation
    cam.location.x = 5.5 + random.uniform(-0.4, 0.4)
    cam.location.y = -5.5 + random.uniform(-0.4, 0.4)
    cam.location.z = 5.0 + random.uniform(-0.25, 0.25)
    cam.rotation_euler[2] = math.radians(38) + random.uniform(-0.06, 0.06)

    output_path = os.path.join(OUTPUT_DIR, f"rgb_{frame_idx:04d}.png")
    scene.render.filepath = output_path
    bpy.ops.render.render(write_still=True)
    print(f"[PRAQTOR DATδ v3] Saved: {output_path}")

print(f"\n[PRAQTOR DATδ v3] Done! {NUM_FRAMES} frames in {OUTPUT_DIR}")
