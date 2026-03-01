"""
Diablo 2 DS1 map layout decoder.
Parses .ds1 files and extracts tile layer grids.
Each cell references a DT1 tile by (orientation, mainIndex, subIndex).
"""

import struct
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DS1Cell:
    prop1: int = 0       # bits 0-7: draw priority / height
    sequence: int = 0    # bits 8-13: subIndex (maps to DT1 subIndex)
    style: int = 0       # bits 20-25: mainIndex (maps to DT1 mainIndex)
    hidden: bool = False  # bit 31: don't draw


@dataclass
class DS1OrientCell:
    orientation: int = 0  # bits 0-7: tile orientation type (0-19)


@dataclass
class DS1Object:
    type: int = 0    # 1=NPC, 2=substitution, 4=item
    id: int = 0
    x: int = 0       # sub-tile X
    y: int = 0       # sub-tile Y
    flags: int = 0


@dataclass
class DS1File:
    version: int = 0
    width: int = 0          # actual width (stored value + 1)
    height: int = 0         # actual height (stored value + 1)
    act: int = 0
    substitution_type: int = 0
    dt1_paths: List[str] = field(default_factory=list)
    wall_layer_count: int = 1
    floor_layer_count: int = 1

    # Layer data: list of 2D grids [layer][row * width + col]
    wall_layers: List[List[DS1Cell]] = field(default_factory=list)
    orient_layers: List[List[DS1OrientCell]] = field(default_factory=list)
    floor_layers: List[List[DS1Cell]] = field(default_factory=list)
    shadow_layer: List[DS1Cell] = field(default_factory=list)
    substitution_layer: List[DS1Cell] = field(default_factory=list)

    objects: List[DS1Object] = field(default_factory=list)


# Orientation lookup for versions < 7
DIR_LOOKUP = [
    0, 1, 2, 1, 2, 3, 3, 5, 5, 6, 6, 7, 7, 8, 9, 10,
    11, 12, 13, 14, 15, 16, 17, 18, 20
]


def decode_ds1(data: bytes) -> DS1File:
    """Decode a DS1 file from raw bytes."""
    ds1 = DS1File()
    offset = 0

    # Header
    ds1.version = struct.unpack_from('<i', data, offset)[0]
    offset += 4
    raw_w = struct.unpack_from('<i', data, offset)[0]
    offset += 4
    raw_h = struct.unpack_from('<i', data, offset)[0]
    offset += 4
    ds1.width = raw_w + 1
    ds1.height = raw_h + 1

    if ds1.version >= 8:
        ds1.act = min(struct.unpack_from('<i', data, offset)[0], 4)
        offset += 4

    if ds1.version >= 10:
        ds1.substitution_type = struct.unpack_from('<i', data, offset)[0]
        offset += 4

    # DT1 file paths
    if ds1.version >= 3:
        num_files = struct.unpack_from('<i', data, offset)[0]
        offset += 4
        for _ in range(num_files):
            path_bytes = b''
            while offset < len(data) and data[offset] != 0:
                path_bytes += bytes([data[offset]])
                offset += 1
            offset += 1  # skip null terminator
            path = path_bytes.decode('ascii', errors='replace')
            # Normalize path: replace backslashes, convert .tg1/.tg1 to .dt1
            path = path.replace('\\', '/')
            if path.lower().endswith('.tg1'):
                path = path[:-4] + '.dt1'
            ds1.dt1_paths.append(path)

    # Unknown bytes for certain versions
    if 9 <= ds1.version <= 13:
        offset += 8

    # Wall layer count
    if ds1.version >= 4:
        ds1.wall_layer_count = struct.unpack_from('<i', data, offset)[0]
        offset += 4

    # Floor layer count
    if ds1.version >= 16:
        ds1.floor_layer_count = struct.unpack_from('<i', data, offset)[0]
        offset += 4

    # Read layer stream
    cells_per_layer = ds1.width * ds1.height
    offset = _read_layers(data, offset, ds1, cells_per_layer)

    # Objects
    if ds1.version >= 2 and offset + 4 <= len(data):
        offset = _read_objects(data, offset, ds1)

    return ds1


def _read_cell(data: bytes, offset: int) -> DS1Cell:
    """Read a single tile cell DWORD."""
    val = struct.unpack_from('<I', data, offset)[0]
    cell = DS1Cell()
    cell.prop1 = val & 0xFF
    cell.sequence = (val >> 8) & 0x3F      # subIndex
    cell.style = (val >> 20) & 0x3F        # mainIndex
    cell.hidden = bool((val >> 31) & 1)
    return cell


def _read_orient_cell(data: bytes, offset: int, version: int) -> DS1OrientCell:
    """Read an orientation cell DWORD."""
    val = struct.unpack_from('<I', data, offset)[0]
    cell = DS1OrientCell()
    orient = val & 0xFF
    if version < 7 and orient < len(DIR_LOOKUP):
        orient = DIR_LOOKUP[orient]
    cell.orientation = orient
    return cell


def _read_layers(data: bytes, offset: int, ds1: DS1File, cells: int) -> int:
    """Read all tile layers from the layer stream."""
    if ds1.version >= 4:
        # Interleaved: wall, orient, wall, orient, ..., floors, shadow, [subst]
        for layer_idx in range(ds1.wall_layer_count):
            # Wall layer
            wall_cells = []
            for i in range(cells):
                wall_cells.append(_read_cell(data, offset))
                offset += 4
            ds1.wall_layers.append(wall_cells)

            # Orientation layer
            orient_cells = []
            for i in range(cells):
                orient_cells.append(_read_orient_cell(data, offset, ds1.version))
                offset += 4
            ds1.orient_layers.append(orient_cells)

        # Floor layers
        for layer_idx in range(ds1.floor_layer_count):
            floor_cells = []
            for i in range(cells):
                floor_cells.append(_read_cell(data, offset))
                offset += 4
            ds1.floor_layers.append(floor_cells)

        # Shadow layer
        shadow_cells = []
        for i in range(cells):
            shadow_cells.append(_read_cell(data, offset))
            offset += 4
        ds1.shadow_layer = shadow_cells

        # Substitution layer
        if ds1.substitution_type in (1, 2) and ds1.version >= 12:
            subst_cells = []
            for i in range(cells):
                subst_cells.append(_read_cell(data, offset))
                offset += 4
            ds1.substitution_layer = subst_cells

    else:
        # Old format (version < 4): Wall1, Floor1, Orient1, Unknown, Shadow
        wall_cells = []
        for i in range(cells):
            wall_cells.append(_read_cell(data, offset))
            offset += 4
        ds1.wall_layers.append(wall_cells)

        floor_cells = []
        for i in range(cells):
            floor_cells.append(_read_cell(data, offset))
            offset += 4
        ds1.floor_layers.append(floor_cells)

        orient_cells = []
        for i in range(cells):
            orient_cells.append(_read_orient_cell(data, offset, ds1.version))
            offset += 4
        ds1.orient_layers.append(orient_cells)

        # Unknown layer
        for i in range(cells):
            offset += 4

        # Shadow layer
        shadow_cells = []
        for i in range(cells):
            shadow_cells.append(_read_cell(data, offset))
            offset += 4
        ds1.shadow_layer = shadow_cells

    return offset


def _read_objects(data: bytes, offset: int, ds1: DS1File) -> int:
    """Read object records."""
    if offset + 4 > len(data):
        return offset
    num_objects = struct.unpack_from('<i', data, offset)[0]
    offset += 4

    for _ in range(num_objects):
        if offset + 16 > len(data):
            break
        obj = DS1Object()
        obj.type = struct.unpack_from('<i', data, offset)[0]
        obj.id = struct.unpack_from('<i', data, offset + 4)[0]
        obj.x = struct.unpack_from('<i', data, offset + 8)[0]
        obj.y = struct.unpack_from('<i', data, offset + 12)[0]
        offset += 16
        if ds1.version > 5:
            if offset + 4 <= len(data):
                obj.flags = struct.unpack_from('<i', data, offset)[0]
                offset += 4
        ds1.objects.append(obj)

    return offset


def get_dt1_key_for_floor(cell: DS1Cell):
    """Get the DT1 lookup key for a floor cell."""
    return (0, cell.style, cell.sequence)  # orientation 0 = floor


def get_dt1_key_for_shadow(cell: DS1Cell):
    """Get the DT1 lookup key for a shadow cell."""
    return (13, cell.style, cell.sequence)  # orientation 13 = shadow


def get_dt1_key_for_wall(cell: DS1Cell, orient_cell: DS1OrientCell):
    """Get the DT1 lookup key for a wall cell."""
    return (orient_cell.orientation, cell.style, cell.sequence)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ds1_decoder.py <file.ds1>")
        sys.exit(1)

    with open(sys.argv[1], 'rb') as f:
        data = f.read()

    ds1 = decode_ds1(data)
    print(f"DS1 v{ds1.version}, {ds1.width}x{ds1.height}, act={ds1.act}")
    print(f"Wall layers: {ds1.wall_layer_count}, Floor layers: {ds1.floor_layer_count}")
    print(f"DT1 files ({len(ds1.dt1_paths)}):")
    for p in ds1.dt1_paths:
        print(f"  {p}")
    print(f"Objects: {len(ds1.objects)}")

    # Stats on non-empty cells
    for li, layer in enumerate(ds1.floor_layers):
        non_empty = sum(1 for c in layer if c.style > 0 or c.sequence > 0)
        print(f"Floor layer {li}: {non_empty}/{len(layer)} cells have tile data")
    for li, layer in enumerate(ds1.wall_layers):
        non_empty = sum(1 for c in layer if c.style > 0 or c.sequence > 0)
        print(f"Wall layer {li}: {non_empty}/{len(layer)} cells have tile data")
    shadow_non_empty = sum(1 for c in ds1.shadow_layer if c.style > 0 or c.sequence > 0)
    print(f"Shadow layer: {shadow_non_empty}/{len(ds1.shadow_layer)} cells have tile data")
