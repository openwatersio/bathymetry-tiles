#!/usr/bin/env bash
# Run the full GEBCO → tile pipeline.
#
# Usage:
#   ./scripts/pipeline.sh                            # full global build
#   BBOX="-80.5,20.9,-72.7,27.3" ./scripts/pipeline.sh  # Bahamas only
#
# Set environment variables to customize:
#   BBOX        Bounding box "west,south,east,north" (empty = global)
#   MAX_ZOOM    Maximum tile zoom level (default: 14)
#   THREADS     Parallel processing threads (default: nproc)
#   FORCE       Set to 1 to rebuild all cached files

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  GEBCO → Tiles Pipeline                                 ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Download & clip
echo "── Step 1/3: Download GEBCO data ─────────────────────────"
INPUT_TIF=$("${SCRIPT_DIR}/download.sh")
echo ""

# Step 2: Build Terrain-RGB tiles (for depth shading + hillshade)
echo "── Step 2/3: Build Terrain-RGB tiles ─────────────────────"
"${SCRIPT_DIR}/build-terrain-rgb.sh" "${INPUT_TIF}"
echo ""

# Step 3: Generate contour vector tiles
echo "── Step 3/3: Generate contour tiles ──────────────────────"
"${SCRIPT_DIR}/generate-contours-fgb.sh" "${INPUT_TIF}"
