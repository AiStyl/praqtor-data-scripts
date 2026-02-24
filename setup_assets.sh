#!/bin/bash
# Download free CC0 assets from Polyhaven for warehouse scene
ASSETS_DIR="/workspace/polyhaven"
mkdir -p $ASSETS_DIR/textures/concrete
mkdir -p $ASSETS_DIR/textures/wood_planks
mkdir -p $ASSETS_DIR/textures/cardboard
mkdir -p $ASSETS_DIR/textures/metal_plate
mkdir -p $ASSETS_DIR/hdri

BASE="https://dl.polyhaven.org/file/ph-assets/Textures/jpg/2k"

echo "Downloading concrete floor textures..."
curl -L "$BASE/concrete_floor_02/concrete_floor_02_diff_2k.jpg" -o $ASSETS_DIR/textures/concrete/diff.jpg
curl -L "$BASE/concrete_floor_02/concrete_floor_02_rough_2k.jpg" -o $ASSETS_DIR/textures/concrete/rough.jpg
curl -L "$BASE/concrete_floor_02/concrete_floor_02_nor_gl_2k.jpg" -o $ASSETS_DIR/textures/concrete/normal.jpg

echo "Downloading wood planks textures..."
curl -L "$BASE/wood_planks_dirt/wood_planks_dirt_diff_2k.jpg" -o $ASSETS_DIR/textures/wood_planks/diff.jpg
curl -L "$BASE/wood_planks_dirt/wood_planks_dirt_rough_2k.jpg" -o $ASSETS_DIR/textures/wood_planks/rough.jpg
curl -L "$BASE/wood_planks_dirt/wood_planks_dirt_nor_gl_2k.jpg" -o $ASSETS_DIR/textures/wood_planks/normal.jpg

echo "Downloading metal plate textures..."
curl -L "$BASE/metal_plate/metal_plate_diff_2k.jpg" -o $ASSETS_DIR/textures/metal_plate/diff.jpg
curl -L "$BASE/metal_plate/metal_plate_rough_2k.jpg" -o $ASSETS_DIR/textures/metal_plate/rough.jpg
curl -L "$BASE/metal_plate/metal_plate_nor_gl_2k.jpg" -o $ASSETS_DIR/textures/metal_plate/normal.jpg
curl -L "$BASE/metal_plate/metal_plate_metal_2k.jpg" -o $ASSETS_DIR/textures/metal_plate/metal.jpg

echo "Downloading industrial HDRI..."
curl -L "https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/2k/industrial_sunset_puresky_2k.hdr" -o $ASSETS_DIR/hdri/industrial.hdr

echo "Checking downloads..."
ls -lh $ASSETS_DIR/textures/concrete/
ls -lh $ASSETS_DIR/textures/wood_planks/
ls -lh $ASSETS_DIR/textures/metal_plate/
ls -lh $ASSETS_DIR/hdri/
echo "Done!"
