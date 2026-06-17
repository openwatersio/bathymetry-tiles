"""Register a streaming source from a flat *urllist* — a text manifest of one tile URL per
line (e.g. NOAA CUDEM's ``urllist8483.txt``: 942 tile URLs across all US coastal regions).

``file_list.txt`` holds the urllist URL(s). ``BBOX`` (W,S,E,N lon/lat) prefilters by each
tile's name-encoded location (``ncei19_n29x00_w089x25_…``) so a regional build only probes
nearby tiles. See ``source_remote`` for the streaming model; ``source_register_remote_geopkg``
is the GeoPackage variant.

Run from pipelines/:  uv run python source_register_remote_urllist.py <source-id>
"""

import os
import re
import sys

import requests

import config
from source_download_filelist import filelist_urls
from source_remote import register_tiles


def tile_lonlat(name):
    """(lon, lat) of a tile from a name like ``ncei19_n29x00_w089x25_...``, else None.
    A cheap BBOX prefilter; the covering re-filters precisely from real header bounds, so
    over-inclusion is harmless and under-inclusion is what we must avoid — hence near()'s margin."""
    mlat = re.search(r"[_/]n(\d+)[xX](\d+)", name)  # names mix n39x00 and n25X75
    mlon = re.search(r"_w(\d+)[xX](\d+)", name)
    if not (mlat and mlon):
        return None
    lat = int(mlat.group(1)) + int(mlat.group(2)) / 100.0
    lon = -(int(mlon.group(1)) + int(mlon.group(2)) / 100.0)
    return lon, lat


def near(lonlat, bbox, margin=0.5):
    lon, lat = lonlat
    w, s, e, n = bbox
    return (w - margin) <= lon <= (e + margin) and (s - margin) <= lat <= (n + margin)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: source_register_remote_urllist.py <source-id>")
    source = sys.argv[1]
    bbox = os.environ.get("BBOX", "").strip()
    bbox = [float(x) for x in bbox.split(",")] if bbox else None

    urls = []
    for manifest in config.file_list(source):
        print(f"reading urllist {manifest}")
        r = requests.get(manifest, timeout=60)
        r.raise_for_status()
        urls += filelist_urls(r.text)
    # A urllist also names sidecars (tile-index .shp/.shx/.dbf, .vrt, .xml, .pdf, itself);
    # keep only raster tiles.
    urls = [u for u in urls if u.lower().endswith((".tif", ".tiff"))]
    if bbox is not None:
        kept = [u for u in urls
                if (ll := tile_lonlat(u.rsplit("/", 1)[-1])) is None or near(ll, bbox)]
        print(f"{source}: {len(kept)}/{len(urls)} tiles within BBOX")
        urls = kept
    register_tiles(source, urls)


def _check():
    assert tile_lonlat("ncei19_n39x00_w075x25_2014v1.tif") == (-75.25, 39.0)
    assert tile_lonlat("ncei19_n25X75_w080X25_2018v1.tif") == (-80.25, 25.75)  # uppercase X
    assert tile_lonlat("southeast_topobathy_19.shx") is None  # sidecar, unparseable
    assert near((-75.0, 39.0), [-76, 38, -74, 40])
    assert not near((-70.0, 39.0), [-76, 38, -74, 40])
    print("source_register_remote_urllist.py self-check ok")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--check"]:
        _check()
    else:
        main()
