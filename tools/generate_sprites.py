#!/usr/bin/env python3
"""
Generate spritesheets from Diablo 2 DCC/COF files for all character animations.
Outputs PNG spritesheets + JSON atlas for use with PixiJS.

Usage:
  python3 generate_sprites.py BA HTH LIT        # Single character+weapon
  python3 generate_sprites.py --batch            # All characters, all weapons
  python3 generate_sprites.py --batch BA AM      # Specific characters, all weapons
"""

import json
import os
import struct
import sys
from pathlib import Path
from PIL import Image
from dcc_decoder import decode_dcc

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "Diablo2_all" / "extracted" / "data" / "data" / "global"
CHARS_DIR = DATA_DIR / "CHARS"
PALETTE_DIR = DATA_DIR / "palette"
OUTPUT_DIR = BASE_DIR / "demo" / "assets" / "sprites"

# Composite type index -> directory name
COMPOSITE_NAMES = ["HD", "TR", "LG", "RA", "LA", "RH", "LH", "SH", "S1", "S2", "S3", "S4"]

# Body layers vs equipment layers
BODY_LAYERS = {"HD", "TR", "LG", "RA", "LA"}
WEAPON_LAYERS = {"RH", "LH", "SH"}

# Animation modes
ANIM_MODES = {
    "NU": "neutral",
    "WL": "walk",
    "RN": "run",
    "A1": "attack1",
    "A2": "attack2",
    "BL": "block",
    "SC": "cast",
    "GH": "gethit",
    "TN": "town_neutral",
    "TW": "town_walk",
    "KK": "kick",
    "TH": "throw",
    "S1": "skill1",
    "S2": "skill2",
    "S3": "skill3",
    "S4": "skill4",
    "DD": "dead",
    "DT": "death",
}

# Character class codes
CHAR_CLASSES = {
    "BA": "Barbarian",
    "AM": "Amazon",
    "NE": "Necromancer",
    "PA": "Paladin",
    "SO": "Sorceress",
    "DZ": "Druid",
    "AI": "Assassin",
}

# Weapon class display names
WEAPON_NAMES = {
    "HTH": "Hand to Hand",
    "1HS": "Sword & Shield",
    "1HT": "Dagger",
    "2HS": "Two-Hand Sword",
    "2HT": "Polearm",
    "BOW": "Bow",
    "XBW": "Crossbow",
    "STF": "Staff",
    "1JS": "Javelin (Swing)",
    "1JT": "Javelin (Thrust)",
    "1SS": "Spear (Swing)",
    "1ST": "Spear (Thrust)",
    "HT1": "Claw",
    "HT2": "Dual Claw",
}

# Default weapon graphics for each weapon class
# Maps weapon class -> {layer: graphic_code}
DEFAULT_WEAPON_GRAPHICS = {
    "HTH": {},
    "1HS": {"RH": "AXE", "SH": "BUC"},
    "1HT": {"RH": "DGR", "SH": "BUC"},
    "2HS": {"RH": "GSD"},
    "2HT": {"RH": "BRN"},
    "BOW": {"LH": "LBW"},
    "XBW": {"RH": "LXB", "LH": "LXB"},
    "STF": {"RH": "HAL"},
    "1JS": {"RH": "AXE", "LH": "JAV"},
    "1JT": {"RH": "DGR", "LH": "JAV"},
    "1SS": {"RH": "AXE", "LH": "AXE"},
    "1ST": {"RH": "DGR", "LH": "SPR"},
    "HT1": {},
    "HT2": {"LH": "CLW"},
}


def load_palette(act="ACT1"):
    """Load a 256-color palette from a .dat file. Format: BGR, 768 bytes."""
    pal_path = PALETTE_DIR / act / "pal.dat"
    if not pal_path.exists():
        pal_path = PALETTE_DIR / "Units" / "pal.dat"
    if not pal_path.exists():
        raise FileNotFoundError(f"No palette found at {pal_path}")

    with open(pal_path, "rb") as f:
        data = f.read(768)

    palette = []
    for i in range(256):
        b = data[i * 3]
        g = data[i * 3 + 1]
        r = data[i * 3 + 2]
        palette.append((r, g, b))
    return palette


def read_cof(cof_path):
    """Read a COF file and return layer info and animation data."""
    with open(cof_path, "rb") as f:
        data = f.read()

    num_layers = data[0]
    frames_per_dir = data[1]
    num_directions = data[2]
    speed = data[0x18] if len(data) > 0x18 else 128

    layers = []
    offset = 0x1C
    for i in range(num_layers):
        if offset + 9 > len(data):
            break
        comp_type = data[offset]
        shadow = data[offset + 1]
        selectable = data[offset + 2]
        transparent = data[offset + 3]
        draw_effect = data[offset + 4]
        weapon_class = data[offset + 5:offset + 9].decode("ascii", errors="replace").rstrip("\x00")
        layers.append({
            "type": comp_type,
            "type_name": COMPOSITE_NAMES[comp_type] if comp_type < len(COMPOSITE_NAMES) else f"UNK{comp_type}",
            "shadow": shadow,
            "selectable": selectable > 0,
            "transparent": transparent > 0,
            "draw_effect": draw_effect,
            "weapon_class": weapon_class,
        })
        offset += 9

    priority_offset = offset + frames_per_dir
    priorities = []
    for d in range(num_directions):
        dir_priorities = []
        for fr in range(frames_per_dir):
            frame_order = []
            for l in range(num_layers):
                idx = priority_offset + (d * frames_per_dir * num_layers) + (fr * num_layers) + l
                if idx < len(data):
                    frame_order.append(data[idx])
            dir_priorities.append(frame_order)
        priorities.append(dir_priorities)

    return {
        "num_layers": num_layers,
        "frames_per_dir": frames_per_dir,
        "num_directions": num_directions,
        "speed": speed,
        "layers": layers,
        "priorities": priorities,
    }


def find_dcc_file(char_code, layer_name, armor_type, anim_mode, weapon_class):
    """
    Find the DCC file for a given character/layer/armor/animation combo.
    DCC naming: {CHAR}{LAYER}{ARMOR}{MODE}{WEAPON}.dcc
    """
    char_dir = CHARS_DIR / char_code / layer_name
    if not char_dir.exists():
        return None

    prefix = f"{char_code}{layer_name}{armor_type}{anim_mode}{weapon_class}".upper()
    target = char_dir / f"{prefix}.dcc"
    if target.exists():
        return target

    # Case-insensitive search
    for f in char_dir.iterdir():
        if f.name.upper() == f"{prefix}.DCC":
            return f
    return None


def find_available_graphic(char_code, layer_name, anim_mode, weapon_class):
    """
    Find any available weapon/shield graphic for a layer+mode+weapon combo.
    Returns the graphic code (e.g., 'AXE', 'BUC') or None.
    """
    layer_dir = CHARS_DIR / char_code / layer_name
    if not layer_dir.exists():
        return None

    suffix = f"{anim_mode}{weapon_class}.DCC".upper()
    prefix = f"{char_code}{layer_name}".upper()

    for f in layer_dir.iterdir():
        name = f.name.upper()
        if name.startswith(prefix) and name.endswith(suffix):
            # Extract graphic code: between prefix and suffix
            graphic = name[len(prefix):-len(suffix)]
            if len(graphic) == 3:  # Valid 3-char graphic code
                return graphic
    return None


def get_available_weapons(char_code):
    """Get all weapon classes available for a character from COF directory."""
    cof_dir = CHARS_DIR / char_code / "COF"
    if not cof_dir.exists():
        return []

    weapons = set()
    for f in cof_dir.iterdir():
        name = f.name.upper()
        if name.endswith(".COF") and name.startswith(char_code.upper()):
            # COF naming: {CHAR}{MODE}{WEAPON}.COF
            # Char=2, Mode=2, Weapon=3, .COF=4 → total 11
            stem = name[:-4]  # Remove .COF
            if len(stem) >= 7:
                weapon = stem[-3:]
                weapons.add(weapon)
    return sorted(weapons)


def dcc_to_frames(dcc_path, palette):
    """Decode a DCC file and return list of frame data dicts."""
    with open(dcc_path, "rb") as f:
        data = f.read()

    dcc = decode_dcc(data)
    result = []

    for dir_idx, direction in enumerate(dcc.directions):
        box_w = direction.box_max_x - direction.box_min_x
        box_h = direction.box_max_y - direction.box_min_y

        for frame_idx, frame in enumerate(direction.frames):
            if frame.pixel_data is None:
                continue

            img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
            pixels = img.load()

            for y in range(box_h):
                for x in range(box_w):
                    pal_idx = frame.pixel_data[x + y * box_w]
                    if pal_idx == 0:
                        continue
                    r, g, b = palette[pal_idx]
                    pixels[x, y] = (r, g, b, 255)

            result.append({
                "dir": dir_idx,
                "frame": frame_idx,
                "image": img,
                "box_x": direction.box_min_x,
                "box_y": direction.box_min_y,
                "frame_x": frame.x_offset,
                "frame_y": frame.y_offset,
            })

    return result


def composite_layers(layer_frames_by_type, cof_data):
    """
    Composite multiple layers into final frames using COF priority order.
    layer_frames_by_type: dict mapping composite type index -> frame data list
    The COF priority table determines draw order per direction/frame.
    """
    min_bx, min_by = 100000, 100000
    max_bx, max_by = -100000, -100000

    for layer_frames in layer_frames_by_type.values():
        for fd in layer_frames:
            img = fd["image"]
            bx, by = fd["box_x"], fd["box_y"]
            min_bx = min(min_bx, bx)
            min_by = min(min_by, by)
            max_bx = max(max_bx, bx + img.width)
            max_by = max(max_by, by + img.height)

    canvas_w = max_bx - min_bx
    canvas_h = max_by - min_by

    # Build lookup: (dir, frame, comp_type) -> frame_data
    lookup = {}
    for comp_type, layer_frames in layer_frames_by_type.items():
        for fd in layer_frames:
            lookup[(fd["dir"], fd["frame"], comp_type)] = fd

    composited = {}
    num_dirs = cof_data["num_directions"]
    num_frames = cof_data["frames_per_dir"]
    priorities = cof_data["priorities"]
    fallback_order = list(layer_frames_by_type.keys())

    for d in range(num_dirs):
        for f in range(num_frames):
            canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

            # Use COF priority table for draw order (per direction/frame)
            if d < len(priorities) and f < len(priorities[d]):
                draw_order = priorities[d][f]
            else:
                draw_order = fallback_order

            for comp_type in draw_order:
                key = (d, f, comp_type)
                if key not in lookup:
                    continue
                fd = lookup[key]
                paste_x = fd["box_x"] - min_bx
                paste_y = fd["box_y"] - min_by
                canvas.alpha_composite(fd["image"], (paste_x, paste_y))

            composited[(d, f)] = canvas

    return composited, canvas_w, canvas_h, min_bx, min_by


def generate_spritesheet(composited, num_dirs, num_frames, canvas_w, canvas_h):
    """Generate a single spritesheet PNG from composited frames."""
    sheet_w = num_frames * canvas_w
    sheet_h = num_dirs * canvas_h
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))

    for d in range(num_dirs):
        for f in range(num_frames):
            key = (d, f)
            if key in composited:
                sheet.paste(composited[key], (f * canvas_w, d * canvas_h))

    return sheet


def process_animation(char_code, anim_mode, weapon_class, armor_type="LIT",
                      weapon_graphics=None, palette=None):
    """
    Process a single animation with full layer compositing including weapons/shields.
    weapon_graphics: dict mapping layer name -> graphic code (e.g., {"RH": "AXE", "SH": "BUC"})
    """
    if weapon_graphics is None:
        weapon_graphics = DEFAULT_WEAPON_GRAPHICS.get(weapon_class, {})

    # Find the COF file
    cof_name = f"{char_code}{anim_mode}{weapon_class}.COF".upper()
    cof_path = CHARS_DIR / char_code / "COF" / cof_name
    if not cof_path.exists():
        cof_dir = CHARS_DIR / char_code / "COF"
        if cof_dir.exists():
            for f in cof_dir.iterdir():
                if f.name.upper() == cof_name:
                    cof_path = f
                    break
    if not cof_path.exists():
        return None

    cof_data = read_cof(cof_path)

    # Build layer dict keyed by composite type for priority-based draw order
    layer_frames_by_type = {}
    for layer_info in cof_data["layers"]:
        layer_name = layer_info["type_name"]
        comp_type = layer_info["type"]
        # Each COF layer specifies its own weapon class for DCC lookup
        layer_wc = layer_info["weapon_class"].upper().strip()

        # Determine the "armor" code for this layer
        if layer_name in BODY_LAYERS:
            armor = armor_type
        elif layer_name in WEAPON_LAYERS:
            armor = weapon_graphics.get(layer_name)
            if not armor:
                armor = find_available_graphic(char_code, layer_name, anim_mode, layer_wc)
            if not armor:
                continue
        else:
            continue  # Skip S1, S2, etc.

        # Use the per-layer weapon class from COF, not the top-level one
        dcc_path = find_dcc_file(char_code, layer_name, armor, anim_mode, layer_wc)
        if dcc_path is None:
            continue

        try:
            frames = dcc_to_frames(dcc_path, palette)
            if frames:
                layer_frames_by_type[comp_type] = frames
        except Exception as e:
            print(f"  Warning: Failed to decode {dcc_path.name}: {e}")
            continue

    if not layer_frames_by_type:
        return None

    composited, canvas_w, canvas_h, anchor_x, anchor_y = composite_layers(layer_frames_by_type, cof_data)

    if not composited:
        return None

    num_dirs = cof_data["num_directions"]
    num_frames = cof_data["frames_per_dir"]
    sheet = generate_spritesheet(composited, num_dirs, num_frames, canvas_w, canvas_h)

    meta = {
        "frameWidth": canvas_w,
        "frameHeight": canvas_h,
        "directions": num_dirs,
        "framesPerDirection": num_frames,
        "anchorX": -anchor_x,
        "anchorY": -anchor_y,
        "speed": cof_data["speed"],
    }

    return sheet, meta


def detect_weapon_graphics(char_code, weapon_class):
    """
    Detect consistent weapon/shield graphics for a character+weapon combo.
    Scans the NU (neutral) COF to find per-layer weapon classes,
    then finds available graphics for each weapon/shield layer.
    """
    graphics = dict(DEFAULT_WEAPON_GRAPHICS.get(weapon_class, {}))

    # Read the neutral COF to check layer weapon classes
    cof_name = f"{char_code}NU{weapon_class}.COF".upper()
    cof_path = CHARS_DIR / char_code / "COF" / cof_name
    if not cof_path.exists():
        for f in (CHARS_DIR / char_code / "COF").iterdir():
            if f.name.upper() == cof_name:
                cof_path = f
                break
    if not cof_path.exists():
        return graphics

    cof_data = read_cof(cof_path)

    for layer_info in cof_data["layers"]:
        layer_name = layer_info["type_name"]
        if layer_name not in WEAPON_LAYERS:
            continue
        if layer_name in graphics:
            # Verify the default graphic actually exists with this layer's weapon class
            layer_wc = layer_info["weapon_class"].upper().strip()
            dcc = find_dcc_file(char_code, layer_name, graphics[layer_name], "NU", layer_wc)
            if dcc is None:
                # Default doesn't exist, auto-detect
                found = find_available_graphic(char_code, layer_name, "NU", layer_wc)
                if found:
                    graphics[layer_name] = found
        else:
            # No default set, auto-detect
            layer_wc = layer_info["weapon_class"].upper().strip()
            found = find_available_graphic(char_code, layer_name, "NU", layer_wc)
            if found:
                graphics[layer_name] = found

    return graphics


def generate_character(char_code, weapon_class, armor_type="LIT", palette=None):
    """Generate all animations for a character+weapon combo. Returns atlas dict or None."""
    weapon_graphics = detect_weapon_graphics(char_code, weapon_class)

    output_dir = OUTPUT_DIR / char_code.lower() / weapon_class
    output_dir.mkdir(parents=True, exist_ok=True)

    atlas = {
        "class": char_code,
        "weapon": weapon_class,
        "armor": armor_type,
        "animations": {},
    }

    count = 0
    for mode_code, mode_name in ANIM_MODES.items():
        result = process_animation(char_code, mode_code, weapon_class, armor_type,
                                   weapon_graphics, palette)
        if result is None:
            continue

        sheet, meta = result
        filename = f"{mode_code}_{weapon_class}.png"
        sheet.save(output_dir / filename)
        atlas["animations"][mode_name] = {
            "file": filename,
            **meta,
        }
        count += 1

    if count == 0:
        return None

    atlas_path = output_dir / "atlas.json"
    with open(atlas_path, "w") as f:
        json.dump(atlas, f, indent=2)

    return atlas


def batch_generate(char_codes=None):
    """Generate sprites for all characters and their available weapons."""
    palette = load_palette("ACT1")

    if char_codes is None:
        char_codes = list(CHAR_CLASSES.keys())

    manifest = {"characters": {}}

    for char_code in char_codes:
        char_name = CHAR_CLASSES.get(char_code, char_code)
        weapons = get_available_weapons(char_code)

        print(f"\n{'='*60}")
        print(f"  {char_name} ({char_code}) — {len(weapons)} weapon classes")
        print(f"  Weapons: {', '.join(weapons)}")
        print(f"{'='*60}")

        char_manifest = {"name": char_name, "weapons": {}}

        for weapon in weapons:
            weapon_name = WEAPON_NAMES.get(weapon, weapon)
            print(f"\n  [{char_code}] {weapon_name} ({weapon}):")

            atlas = generate_character(char_code, weapon, "LIT", palette)
            if atlas is None:
                print(f"    SKIP (no animations generated)")
                continue

            anim_count = len(atlas["animations"])
            print(f"    Generated {anim_count} animations")

            char_manifest["weapons"][weapon] = {
                "name": weapon_name,
                "path": f"{char_code.lower()}/{weapon}/atlas.json",
                "animations": list(atlas["animations"].keys()),
            }

        if char_manifest["weapons"]:
            manifest["characters"][char_code] = char_manifest

    # Save manifest
    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Manifest saved to {manifest_path}")
    total_combos = sum(len(c["weapons"]) for c in manifest["characters"].values())
    print(f"Total: {len(manifest['characters'])} characters, {total_combos} weapon combos")

    return manifest


def main():
    if "--batch" in sys.argv:
        # Batch mode: generate all or specified characters
        chars = [a for a in sys.argv[1:] if a != "--batch" and a in CHAR_CLASSES]
        batch_generate(chars if chars else None)
        return

    # Single character mode
    char_code = sys.argv[1] if len(sys.argv) > 1 else "BA"
    weapon = sys.argv[2] if len(sys.argv) > 2 else "HTH"
    armor = sys.argv[3] if len(sys.argv) > 3 else "LIT"

    print(f"Generating sprites for {CHAR_CLASSES.get(char_code, char_code)} ({char_code})")
    print(f"Weapon: {weapon}, Armor: {armor}")

    palette = load_palette("ACT1")
    weapon_graphics = detect_weapon_graphics(char_code, weapon)

    output_dir = OUTPUT_DIR / char_code.lower() / weapon
    output_dir.mkdir(parents=True, exist_ok=True)

    atlas = {"class": char_code, "weapon": weapon, "armor": armor, "animations": {}}

    for mode_code, mode_name in ANIM_MODES.items():
        print(f"  Processing {mode_name} ({mode_code})...", end=" ", flush=True)

        result = process_animation(char_code, mode_code, weapon, armor,
                                   weapon_graphics, palette)
        if result is None:
            print("SKIP (no DCC files)")
            continue

        sheet, meta = result
        filename = f"{mode_code}_{weapon}.png"
        sheet.save(output_dir / filename)
        atlas["animations"][mode_name] = {
            "file": filename,
            **meta,
        }
        print(f"OK ({meta['directions']}dirs × {meta['framesPerDirection']}frames, {meta['frameWidth']}×{meta['frameHeight']}px)")

    atlas_path = output_dir / "atlas.json"
    with open(atlas_path, "w") as f:
        json.dump(atlas, f, indent=2)

    print(f"\nAtlas saved to {atlas_path}")
    print(f"Sprites saved to {output_dir}")


if __name__ == "__main__":
    main()
