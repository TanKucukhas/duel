"""
Diablo 2 map renderer.
Loads a DS1 map + referenced DT1 tile graphics + act palette,
then composites the full isometric map to a PNG image.
"""

import os
import sys
import json
import struct
from pathlib import Path
from PIL import Image

# Add tools dir to path
sys.path.insert(0, os.path.dirname(__file__))
from dt1_decoder import decode_dt1, DT1File, DT1Tile, build_tile_index, select_tile
from ds1_decoder import (
    decode_ds1, DS1File, DS1Cell, DS1OrientCell,
    get_dt1_key_for_floor, get_dt1_key_for_shadow, get_dt1_key_for_wall,
)

# Tile dimensions
TILE_WIDTH = 160
TILE_HEIGHT = 80
SUBTILE_WIDTH = 32
SUBTILE_HEIGHT = 16

# Base path for extracted tiles
TILES_BASE = os.path.join(os.path.dirname(__file__), '..', 'Diablo2_all', 'extracted', 'tiles', 'data', 'global', 'tiles')
PALETTE_BASE = os.path.join(os.path.dirname(__file__), '..', 'Diablo2_all', 'extracted', 'data', 'data', 'global', 'palette')


def load_palette(act: int) -> list:
    """Load a 256-color palette for the given act (0-indexed)."""
    act_name = f'ACT{act + 1}'
    pal_path = os.path.join(PALETTE_BASE, act_name, 'pal.dat')
    if not os.path.exists(pal_path):
        # Fallback to ACT1
        pal_path = os.path.join(PALETTE_BASE, 'ACT1', 'pal.dat')

    with open(pal_path, 'rb') as f:
        pal_data = f.read()

    palette = []
    for i in range(256):
        b, g, r = pal_data[i * 3], pal_data[i * 3 + 1], pal_data[i * 3 + 2]
        palette.append((r, g, b))
    return palette


def resolve_dt1_path(ds1_path: str) -> str:
    """Resolve a DS1's DT1 reference path to an actual file on disk."""
    # DS1 stores paths like: /d2/data/global/tiles/act1/town/floor.dt1
    # We need to find this in: TILES_BASE/ACT1/TOWN/floor.dt1
    # Strip the prefix up to 'tiles/'
    path = ds1_path.lower()
    idx = path.find('tiles/')
    if idx >= 0:
        rel = ds1_path[idx + 6:]  # after 'tiles/'
    else:
        rel = os.path.basename(ds1_path)

    # Try exact path first
    candidate = os.path.join(TILES_BASE, rel)
    if os.path.exists(candidate):
        return candidate

    # Try case-insensitive search
    parts = rel.replace('\\', '/').split('/')
    current = TILES_BASE
    for part in parts:
        if not os.path.isdir(current):
            break
        entries = os.listdir(current)
        match = None
        for entry in entries:
            if entry.lower() == part.lower():
                match = entry
                break
        if match:
            current = os.path.join(current, match)
        else:
            return ''

    if os.path.isfile(current):
        return current
    return ''


def load_dt1_files(ds1: DS1File) -> list:
    """Load all DT1 files referenced by a DS1."""
    dt1_files = []
    for path in ds1.dt1_paths:
        resolved = resolve_dt1_path(path)
        if resolved and os.path.exists(resolved):
            with open(resolved, 'rb') as f:
                data = f.read()
            dt1 = decode_dt1(data)
            dt1_files.append(dt1)
        else:
            print(f"  Warning: DT1 not found: {path}")
    return dt1_files


def tile_to_screen(tile_x: int, tile_y: int):
    """Convert tile grid coordinates to screen pixel coordinates."""
    sx = (tile_x - tile_y) * (TILE_WIDTH // 2)
    sy = (tile_x + tile_y) * (TILE_HEIGHT // 2)
    return sx, sy


def render_tile_to_image(img_data: bytearray, img_width: int, img_height: int,
                         tile: DT1Tile, palette: list,
                         screen_x: int, screen_y: int,
                         alpha: int = 255):
    """Render a decoded DT1 tile's pixels onto the output image buffer."""
    if tile.pixels is None:
        return

    tw = tile.width
    th = abs(tile.height)

    for py in range(th):
        for px in range(tw):
            pi = tile.pixels[py * tw + px]
            if pi == 0:
                continue  # transparent

            # Destination pixel
            dx = screen_x + px
            dy = screen_y + py
            if 0 <= dx < img_width and 0 <= dy < img_height:
                r, g, b = palette[pi]
                base = (dy * img_width + dx) * 4
                if alpha == 255:
                    img_data[base] = r
                    img_data[base + 1] = g
                    img_data[base + 2] = b
                    img_data[base + 3] = 255
                else:
                    # Alpha blend for shadows
                    old_r = img_data[base]
                    old_g = img_data[base + 1]
                    old_b = img_data[base + 2]
                    old_a = img_data[base + 3]
                    if old_a > 0:
                        img_data[base] = (old_r * (255 - alpha) + r * alpha) // 255
                        img_data[base + 1] = (old_g * (255 - alpha) + g * alpha) // 255
                        img_data[base + 2] = (old_b * (255 - alpha) + b * alpha) // 255


def render_map(ds1_path: str, output_path: str, render_walls: bool = True,
               render_shadows: bool = True):
    """Render a DS1 map to a PNG image."""
    print(f"Loading DS1: {ds1_path}")
    with open(ds1_path, 'rb') as f:
        data = f.read()
    ds1 = decode_ds1(data)

    print(f"  Version: {ds1.version}, Size: {ds1.width}x{ds1.height}, Act: {ds1.act}")
    print(f"  Walls: {ds1.wall_layer_count} layers, Floors: {ds1.floor_layer_count} layers")

    # Load palette
    palette = load_palette(ds1.act)

    # Load DT1 files
    print(f"Loading {len(ds1.dt1_paths)} DT1 files...")
    dt1_files = load_dt1_files(ds1)
    tile_index = build_tile_index(dt1_files)
    print(f"  Tile index: {len(tile_index)} unique (orient, main, sub) keys")

    # Calculate output image size
    # The isometric grid creates a diamond shape.
    # For a WxH grid, the bounding box in screen space is:
    #   width_px = (W + H) * TILE_WIDTH/2
    #   height_px = (W + H) * TILE_HEIGHT/2
    # Plus extra height for walls above floor level.
    w = ds1.width
    h = ds1.height
    out_w = (w + h) * (TILE_WIDTH // 2)
    out_h = (w + h) * (TILE_HEIGHT // 2)

    # Add padding for walls that extend above the floor
    wall_padding_top = 400  # generous padding for tall walls/trees
    out_h += wall_padding_top

    # Offset so tile(0,0) is at the top center
    origin_x = (h - 1) * (TILE_WIDTH // 2)
    origin_y = wall_padding_top

    print(f"  Output image: {out_w}x{out_h}")

    # Create raw pixel buffer (RGBA)
    img_data = bytearray(out_w * out_h * 4)

    # --- Render floors ---
    print("  Rendering floors...")
    for layer_idx, floor_layer in enumerate(ds1.floor_layers):
        for ty in range(h):
            for tx in range(w):
                cell = floor_layer[ty * w + tx]
                if cell.style == 0 and cell.sequence == 0 and cell.prop1 == 0:
                    continue
                if cell.hidden:
                    continue

                key = get_dt1_key_for_floor(cell)
                candidates = tile_index.get(key, [])
                if not candidates:
                    continue

                dt1_tile = select_tile(candidates, tx * 7 + ty * 11)
                if dt1_tile is None or dt1_tile.pixels is None:
                    continue

                sx, sy = tile_to_screen(tx, ty)
                # Floor tiles are diamond-shaped within a 160x80 area,
                # but the actual bitmap may be taller (e.g., 160x128)
                # The diamond starts at y_offset within the bitmap
                render_tile_to_image(
                    img_data, out_w, out_h,
                    dt1_tile, palette,
                    origin_x + sx, origin_y + sy
                )

    # --- Render shadows ---
    if render_shadows and ds1.shadow_layer:
        print("  Rendering shadows...")
        for ty in range(h):
            for tx in range(w):
                cell = ds1.shadow_layer[ty * w + tx]
                if cell.style == 0 and cell.sequence == 0:
                    continue
                if cell.hidden:
                    continue

                key = get_dt1_key_for_shadow(cell)
                candidates = tile_index.get(key, [])
                if not candidates:
                    continue

                dt1_tile = select_tile(candidates, tx * 7 + ty * 11)
                if dt1_tile is None or dt1_tile.pixels is None:
                    continue

                sx, sy = tile_to_screen(tx, ty)
                render_tile_to_image(
                    img_data, out_w, out_h,
                    dt1_tile, palette,
                    origin_x + sx, origin_y + sy,
                    alpha=128
                )

    # --- Render walls (three-pass: lower walls, regular walls, roofs) ---
    if render_walls:
        print("  Rendering walls...")
        # Collect all resolved wall tiles across all layers
        # Each entry: (orient, layer_idx, ty, tx, dt1_tile)
        resolved_walls = []
        for layer_idx in range(ds1.wall_layer_count):
            wall_layer = ds1.wall_layers[layer_idx]
            orient_layer = ds1.orient_layers[layer_idx]

            for ty in range(h):
                for tx in range(w):
                    cell = wall_layer[ty * w + tx]
                    orient_cell = orient_layer[ty * w + tx]

                    if cell.style == 0 and cell.sequence == 0:
                        continue
                    if cell.hidden:
                        continue
                    if orient_cell.orientation in (10, 11):
                        continue  # special/invisible tiles

                    key = get_dt1_key_for_wall(cell, orient_cell)
                    candidates = tile_index.get(key, [])
                    if not candidates:
                        continue

                    dt1_tile = select_tile(candidates, tx * 7 + ty * 11)
                    if dt1_tile is None or dt1_tile.pixels is None:
                        continue

                    resolved_walls.append((orient_cell.orientation, layer_idx, ty, tx, dt1_tile))

        # Three ordered passes, each sorted by (ty, tx, layer) for back-to-front
        LOWER_WALLS = {16, 17, 18, 19}
        REGULAR_WALLS = {1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 14}
        ROOFS = {15}

        for pass_orients in (LOWER_WALLS, REGULAR_WALLS, ROOFS):
            for orient, layer_idx, ty, tx, dt1_tile in resolved_walls:
                if orient not in pass_orients:
                    continue

                sx, sy = tile_to_screen(tx, ty)
                wall_y_adjust = dt1_tile.y_offset if dt1_tile.y_offset < 0 else 0

                if orient == 15:
                    # Roof tiles: shift upward by roof_height
                    roof_offset = dt1_tile.roof_height if dt1_tile.roof_height > 0 else 0
                    render_tile_to_image(
                        img_data, out_w, out_h,
                        dt1_tile, palette,
                        origin_x + sx, origin_y + sy - roof_offset + wall_y_adjust
                    )
                else:
                    render_tile_to_image(
                        img_data, out_w, out_h,
                        dt1_tile, palette,
                        origin_x + sx, origin_y + sy + wall_y_adjust
                    )

    # Convert to PIL Image
    print("  Compositing final image...")
    img = Image.frombytes('RGBA', (out_w, out_h), bytes(img_data))

    # Crop to content (remove excess transparent borders)
    bbox = img.getbbox()
    if bbox:
        # Add small margin
        margin = 20
        bbox = (
            max(0, bbox[0] - margin),
            max(0, bbox[1] - margin),
            min(out_w, bbox[2] + margin),
            min(out_h, bbox[3] + margin),
        )
        img = img.crop(bbox)

    img.save(output_path)
    print(f"  Saved: {output_path} ({img.size[0]}x{img.size[1]})")
    return img.size


def render_act1_town(output_dir: str):
    """Render all Act 1 Town DS1 stamps."""
    town_dir = os.path.join(TILES_BASE, 'ACT1', 'TOWN')
    ds1_files = [
        'townN1.ds1',
        'townE1.ds1',
        'townS1.ds1',
        'townW1.ds1',
    ]

    os.makedirs(output_dir, exist_ok=True)
    results = {}

    for ds1_name in ds1_files:
        ds1_path = os.path.join(town_dir, ds1_name)
        if not os.path.exists(ds1_path):
            print(f"  Skipping {ds1_name}: not found")
            continue

        out_name = ds1_name.replace('.ds1', '.png')
        out_path = os.path.join(output_dir, out_name)
        size = render_map(ds1_path, out_path)
        results[ds1_name] = {
            'file': out_name,
            'width': size[0],
            'height': size[1],
        }

    # Write manifest
    manifest_path = os.path.join(output_dir, 'manifest.json')
    with open(manifest_path, 'w') as f:
        json.dump({
            'act': 1,
            'area': 'town',
            'tileWidth': TILE_WIDTH,
            'tileHeight': TILE_HEIGHT,
            'stamps': results,
        }, f, indent=2)
    print(f"\nManifest written: {manifest_path}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python render_map.py <file.ds1> [output.png]")
        print("  python render_map.py --act1-town")
        sys.exit(1)

    if sys.argv[1] == '--act1-town':
        output_dir = os.path.join(os.path.dirname(__file__), '..', 'demo', 'assets', 'maps', 'act1_town')
        render_act1_town(output_dir)
    else:
        ds1_path = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) > 2 else '/tmp/map_output.png'
        render_map(ds1_path, output_path)
