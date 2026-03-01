"""
Diablo 2 DT1 tile graphics decoder.
Parses .dt1 files and decodes tile pixel data (isometric diamond + RLE).
Returns palette indices ready for palette lookup.
"""

import struct
from dataclasses import dataclass, field
from typing import List, Optional


# Isometric diamond decode tables (32x16 sub-tile = 256 pixels)
XJUMP = [14, 12, 10, 8, 6, 4, 2, 0, 2, 4, 6, 8, 10, 12, 14]
NBPIX = [4, 8, 12, 16, 20, 24, 28, 32, 28, 24, 20, 16, 12, 8, 4]

# Orientation types
ORIENT_FLOOR = 0
ORIENT_WALL_LEFT = 1
ORIENT_WALL_RIGHT = 2
ORIENT_WALL_NW = 3
ORIENT_WALL_NE = 4
ORIENT_WALL_LEFT_END = 5
ORIENT_WALL_RIGHT_END = 6
ORIENT_WALL_S = 7
ORIENT_WALL_DOOR_LEFT = 8
ORIENT_WALL_DOOR_RIGHT = 9
ORIENT_SPECIAL_10 = 10
ORIENT_SPECIAL_11 = 11
ORIENT_PILLAR = 12
ORIENT_SHADOW = 13
ORIENT_TREE = 14
ORIENT_ROOF = 15
ORIENT_LOWER_WALL_LEFT = 16
ORIENT_LOWER_WALL_RIGHT = 17
ORIENT_LOWER_WALL_18 = 18
ORIENT_LOWER_WALL_19 = 19


@dataclass
class DT1Block:
    x: int = 0
    y: int = 0
    grid_x: int = 0
    grid_y: int = 0
    format: int = 0  # 1 = isometric (3D), 0 = RLE
    length: int = 0
    data_offset: int = 0  # offset from tile's block_headers_ptr
    pixel_data: Optional[bytes] = None


@dataclass
class DT1Tile:
    direction: int = 0
    roof_height: int = 0
    sound_index: int = 0
    animated: int = 0
    height: int = 0
    width: int = 0
    orientation: int = 0
    main_index: int = 0
    sub_index: int = 0
    rarity: int = 0
    sub_tile_flags: bytes = b'\x00' * 25
    block_headers_ptr: int = 0
    block_data_length: int = 0
    num_blocks: int = 0
    blocks: List[DT1Block] = field(default_factory=list)
    # Decoded pixel data (palette indices), size = width * abs(height)
    pixels: Optional[bytearray] = None
    y_offset: int = 0  # min block Y, for positioning during rendering


@dataclass
class DT1File:
    major_version: int = 0
    minor_version: int = 0
    num_tiles: int = 0
    tiles: List[DT1Tile] = field(default_factory=list)


def decode_dt1(data: bytes) -> DT1File:
    """Decode a DT1 file from raw bytes."""
    dt1 = DT1File()

    # File header (276 bytes)
    dt1.major_version = struct.unpack_from('<i', data, 0x00)[0]
    dt1.minor_version = struct.unpack_from('<i', data, 0x04)[0]
    # 260 bytes of zeros at 0x08
    dt1.num_tiles = struct.unpack_from('<i', data, 0x10C)[0]
    tile_headers_ptr = struct.unpack_from('<i', data, 0x110)[0]

    # Parse tile headers (96 bytes each)
    dt1.tiles = []
    for i in range(dt1.num_tiles):
        offset = tile_headers_ptr + i * 96
        tile = _parse_tile_header(data, offset)
        dt1.tiles.append(tile)

    # Parse blocks and decode pixels for each tile
    for tile in dt1.tiles:
        _parse_tile_blocks(data, tile)
        _decode_tile_pixels(tile)

    return dt1


def _parse_tile_header(data: bytes, offset: int) -> DT1Tile:
    tile = DT1Tile()
    tile.direction = struct.unpack_from('<i', data, offset + 0x00)[0]
    tile.roof_height = struct.unpack_from('<h', data, offset + 0x04)[0]
    tile.sound_index = data[offset + 0x06]
    tile.animated = data[offset + 0x07]
    tile.height = struct.unpack_from('<i', data, offset + 0x08)[0]
    tile.width = struct.unpack_from('<i', data, offset + 0x0C)[0]
    # 4 bytes zeros at +0x10
    tile.orientation = struct.unpack_from('<i', data, offset + 0x14)[0]
    tile.main_index = struct.unpack_from('<i', data, offset + 0x18)[0]
    tile.sub_index = struct.unpack_from('<i', data, offset + 0x1C)[0]
    tile.rarity = struct.unpack_from('<i', data, offset + 0x20)[0]
    # 4 bytes unknown at +0x24
    tile.sub_tile_flags = data[offset + 0x28: offset + 0x28 + 25]
    # 7 bytes padding at +0x41
    tile.block_headers_ptr = struct.unpack_from('<i', data, offset + 0x48)[0]
    tile.block_data_length = struct.unpack_from('<i', data, offset + 0x4C)[0]
    tile.num_blocks = struct.unpack_from('<i', data, offset + 0x50)[0]
    # 12 bytes padding at +0x54
    return tile


def _parse_tile_blocks(data: bytes, tile: DT1Tile):
    """Parse sub-block headers and extract pixel data for a tile."""
    tile.blocks = []
    for i in range(tile.num_blocks):
        offset = tile.block_headers_ptr + i * 20
        block = DT1Block()
        block.x = struct.unpack_from('<h', data, offset + 0x00)[0]
        block.y = struct.unpack_from('<h', data, offset + 0x02)[0]
        # 2 bytes zeros at +0x04
        block.grid_x = data[offset + 0x06]
        block.grid_y = data[offset + 0x07]
        block.format = struct.unpack_from('<h', data, offset + 0x08)[0]
        block.length = struct.unpack_from('<i', data, offset + 0x0A)[0]
        # 2 bytes zeros at +0x0E
        block.data_offset = struct.unpack_from('<i', data, offset + 0x10)[0]

        # Extract raw pixel data
        abs_offset = tile.block_headers_ptr + block.data_offset
        block.pixel_data = data[abs_offset: abs_offset + block.length]
        tile.blocks.append(block)


def _decode_tile_pixels(tile: DT1Tile):
    """Decode all blocks into a single pixel buffer for the tile."""
    if tile.width <= 0 or tile.height == 0 or not tile.blocks:
        return

    abs_height = abs(tile.height)

    # Compute Y offset: blocks may have negative Y (walls extend upward).
    # Find minimum block Y to use as the origin.
    min_block_y = min(b.y for b in tile.blocks)
    tile.y_offset = min_block_y  # store for rendering

    tile.pixels = bytearray(tile.width * abs_height)

    for block in tile.blocks:
        if block.format == 1:
            # 3D isometric diamond (32x16, always 256 bytes)
            _decode_isometric(block, tile, min_block_y)
        else:
            # RLE compressed (rectangular 32x32 sub-blocks)
            _decode_rle(block, tile, min_block_y)


def _decode_isometric(block: DT1Block, tile: DT1Tile, min_y: int):
    """Decode isometric diamond sub-tile (format=1, 256 bytes raw)."""
    if block.pixel_data is None or len(block.pixel_data) < 256:
        return

    abs_height = abs(tile.height)
    y_base = block.y - min_y
    data_idx = 0
    for row in range(15):
        x0 = block.x + XJUMP[row]
        y0 = y_base + row
        if y0 < 0 or y0 >= abs_height:
            data_idx += NBPIX[row]
            continue
        for col in range(NBPIX[row]):
            px = x0 + col
            if 0 <= px < tile.width:
                pos = y0 * tile.width + px
                if 0 <= pos < len(tile.pixels) and data_idx < len(block.pixel_data):
                    tile.pixels[pos] = block.pixel_data[data_idx]
            data_idx += 1


def _decode_rle(block: DT1Block, tile: DT1Tile, min_y: int):
    """Decode RLE compressed sub-block (format=0)."""
    if block.pixel_data is None or len(block.pixel_data) == 0:
        return

    abs_height = abs(tile.height)
    x = 0
    y = 0
    src_idx = 0

    while src_idx < len(block.pixel_data) - 1:
        skip = block.pixel_data[src_idx]
        count = block.pixel_data[src_idx + 1]
        src_idx += 2

        if skip == 0 and count == 0:
            x = 0
            y += 1
            continue

        x += skip
        for i in range(count):
            if src_idx >= len(block.pixel_data):
                break
            px = block.x + x
            py = (block.y - min_y) + y
            if 0 <= px < tile.width and 0 <= py < abs_height:
                pos = py * tile.width + px
                if 0 <= pos < len(tile.pixels):
                    tile.pixels[pos] = block.pixel_data[src_idx]
            src_idx += 1
            x += 1


def build_tile_index(dt1_files: List[DT1File]) -> dict:
    """Build a lookup index: (orientation, mainIndex, subIndex) -> list of DT1Tile.
    Multiple tiles can share the same key (random selection by rarity).
    """
    index = {}
    for dt1 in dt1_files:
        for tile in dt1.tiles:
            key = (tile.orientation, tile.main_index, tile.sub_index)
            if key not in index:
                index[key] = []
            index[key].append(tile)
    return index


def select_tile(tiles: List[DT1Tile], seed: int = 0) -> Optional[DT1Tile]:
    """Select a tile from a list using rarity weights."""
    if not tiles:
        return None
    if len(tiles) == 1:
        return tiles[0]

    total_rarity = sum(max(t.rarity, 0) for t in tiles)
    if total_rarity == 0:
        return tiles[-1]

    pick = seed % total_rarity
    cumulative = 0
    for t in tiles:
        cumulative += max(t.rarity, 0)
        if pick < cumulative:
            return t
    return tiles[-1]


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python dt1_decoder.py <file.dt1>")
        sys.exit(1)

    with open(sys.argv[1], 'rb') as f:
        data = f.read()

    dt1 = decode_dt1(data)
    print(f"DT1 v{dt1.major_version}.{dt1.minor_version}, {dt1.num_tiles} tiles")
    for i, t in enumerate(dt1.tiles):
        orient_name = {0: 'floor', 1: 'wall-L', 2: 'wall-R', 3: 'wall-NW',
                       4: 'wall-NE', 5: 'wall-LE', 6: 'wall-RE', 7: 'wall-S',
                       8: 'door-L', 9: 'door-R', 10: 'special', 11: 'special',
                       12: 'pillar', 13: 'shadow', 14: 'tree', 15: 'roof',
                       16: 'lwall-L', 17: 'lwall-R', 18: 'lwall', 19: 'lwall'
                       }.get(t.orientation, f'orient-{t.orientation}')
        print(f"  [{i:3d}] {orient_name:8s} main={t.main_index:2d} sub={t.sub_index:2d} "
              f"{t.width}x{abs(t.height)} blocks={t.num_blocks} "
              f"rarity={t.rarity} anim={t.animated}")
