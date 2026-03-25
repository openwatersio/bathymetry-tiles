#!/usr/bin/env bash
# Generate bathymetric contour lines with non-uniform intervals.
#
# Upsamples the DEM 2x with cubicspline to eliminate grid stairstepping,
# generates contours at specific depth levels defined in config.sh, then
# applies Chaikin corner-cutting for naturally curved lines.
#
# Outputs a PMTiles vector tileset with zoom-dependent filtering.
#
# Usage:
#   ./scripts/generate-contours-fgb.sh [input.tif]

source "$(dirname "$0")/config.sh"
check_deps gdal_contour gdalwarp ogr2ogr tippecanoe

resolve_input_dem "${1:-}"

# ─── Step 1: Upsample DEM ────────────────────────────────────────────────────
UPSAMPLED="${WORK_DIR}/gebco_upsampled${SUFFIX}.tif"
upsample_dem "${INPUT_TIF}" "${UPSAMPLED}"

# ─── Step 2: Generate contours at fixed levels ──────────────────────────────
# Use a simple filename to avoid ogr2ogr SQL table name issues with commas.
CONTOURS_RAW="${WORK_DIR}/contours_raw.fgb"

if cached "${CONTOURS_RAW}"; then
  log "Raw contours already exist"
else
  rm -f "${CONTOURS_RAW}"
  log "Generating contours (${CONTOUR_LEVELS})..."
  gdal_contour \
    -fl ${CONTOUR_LEVELS} \
    -a depth_m \
    -f FlatGeobuf \
    "${UPSAMPLED}" \
    "${CONTOURS_RAW}"
  COUNT=$(ogrinfo -al -so "${CONTOURS_RAW}" 2>/dev/null | grep "Feature Count" | awk '{print $NF}')
  log "  → ${COUNT} features"
fi

# ─── Step 3: Smooth contour geometries (Chaikin) ────────────────────────────
# Chaikin's corner-cutting algorithm rounds off angular vertices left over
# from the marching-squares contour extraction, especially visible in shallow
# water where contours follow individual grid cells.
CONTOURS_SMOOTH="${WORK_DIR}/contours_smooth.fgb"

if cached "${CONTOURS_SMOOTH}"; then
  log "Smoothed contours already exist"
else
  rm -f "${CONTOURS_SMOOTH}"
  log "Smoothing contour geometries (simplify + Chaikin)..."
  python3 "$(dirname "$0")/smooth-contours.py" \
    "${CONTOURS_RAW}" \
    "${CONTOURS_SMOOTH}" \
    0.0002 5
fi

# ─── Step 4: Enrich attributes ──────────────────────────────────────────────
CONTOURS_ENRICHED="${WORK_DIR}/contours_enriched.fgb"

if cached "${CONTOURS_ENRICHED}"; then
  log "Enriched contours already exist"
else
  rm -f "${CONTOURS_ENRICHED}"
  log "Enriching contours..."
  ogr2ogr \
    -f FlatGeobuf \
    "${CONTOURS_ENRICHED}" \
    "${CONTOURS_SMOOTH}" \
    -dialect sqlite \
    -sql "
      SELECT geometry, depth_m,
        CAST(-depth_m AS INTEGER) AS depth_abs_m
      FROM contour
      WHERE depth_m < 0
    "
  COUNT=$(ogrinfo -al -so "${CONTOURS_ENRICHED}" 2>/dev/null | grep "Feature Count" | awk '{print $NF}')
  log "  → ${COUNT} ocean features"
fi

# ─── Step 5: Build vector tiles ──────────────────────────────────────────────
CONTOUR_PMTILES="${OUTPUT_DIR}/gebco-contours${SUFFIX}.pmtiles"

if cached "${CONTOUR_PMTILES}"; then
  log "Contour tiles already exist: ${CONTOUR_PMTILES}"
else
  rm -f "${CONTOUR_PMTILES}"
  log "Building contour vector tiles (z0–${MAX_ZOOM})..."
  tippecanoe \
    -o "${CONTOUR_PMTILES}" \
    -f \
    -l contours \
    -n "GEBCO Bathymetric Contours" \
    -A '<a href="https://www.gebco.net">GEBCO</a>' \
    -N "Bathymetric contour lines derived from the GEBCO grid." \
    -Z 0 \
    -z "${MAX_ZOOM}" \
    -P \
    -y depth_m \
    -y depth_abs_m \
    -j '{
      "*": [
        "any",
        ["all", ["<=", "$zoom", 4],  ["<=", "depth_m", -1000]],
        ["all", ["<=", "$zoom", 6],  ["<=", "depth_m", -200]],
        ["all", ["<=", "$zoom", 8],  ["<=", "depth_m", -50]],
        [">=", "$zoom", 9]
      ]
    }' \
    "${CONTOURS_ENRICHED}"

  log "Contour tiles: ${CONTOUR_PMTILES} ($(du -h "${CONTOUR_PMTILES}" | cut -f1))"
fi

log ""
log "═══ Contour generation complete ═══"
log "  PMTiles: ${CONTOUR_PMTILES}"
