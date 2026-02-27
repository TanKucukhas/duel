"""
Diablo 2 DCC file decoder.
Ported from OpenDiablo2 (Go) to Python.
Decodes .dcc sprite files into individual frames with palette indices.
"""

import struct
from dataclasses import dataclass, field
from typing import List, Optional

CRAZY_BIT_TABLE = [0, 1, 2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 26, 28, 30, 32]
CELL_SIZE = 4


class BitReader:
    """Reads individual bits from a byte buffer."""

    def __init__(self, data: bytes, bit_offset: int = 0):
        self.data = data
        self.bit_pos = bit_offset
        self.bits_read = 0

    def copy(self):
        r = BitReader(self.data, self.bit_pos)
        r.bits_read = 0
        return r

    def read_bits(self, count: int) -> int:
        if count == 0:
            return 0
        result = 0
        for i in range(count):
            byte_idx = self.bit_pos >> 3
            bit_idx = self.bit_pos & 7
            if byte_idx < len(self.data):
                result |= ((self.data[byte_idx] >> bit_idx) & 1) << i
            self.bit_pos += 1
            self.bits_read += 1
        return result

    def read_signed(self, count: int) -> int:
        val = self.read_bits(count)
        if count > 0 and (val & (1 << (count - 1))):
            val -= (1 << count)
        return val

    def read_bool(self) -> bool:
        return self.read_bits(1) == 1

    def offset_bits(self, count: int):
        self.bit_pos += count
        return self


@dataclass
class Cell:
    width: int = 0
    height: int = 0
    x_offset: int = 0
    y_offset: int = 0
    last_width: int = -1
    last_height: int = -1
    last_x_offset: int = 0
    last_y_offset: int = 0


@dataclass
class PixelBufferEntry:
    value: list = field(default_factory=lambda: [0, 0, 0, 0])
    frame: int = -1
    frame_cell_index: int = -1


@dataclass
class DCCFrame:
    width: int = 0
    height: int = 0
    x_offset: int = 0
    y_offset: int = 0
    num_optional_bytes: int = 0
    num_coded_bytes: int = 0
    bottom_up: bool = False
    box_min_x: int = 0
    box_min_y: int = 0
    box_max_x: int = 0
    box_max_y: int = 0
    h_cells: int = 0
    v_cells: int = 0
    cells: list = field(default_factory=list)
    pixel_data: Optional[bytes] = None


@dataclass
class DCCDirection:
    frames_per_dir: int = 0
    out_size_coded: int = 0
    compression_flags: int = 0
    variable0_bits: int = 0
    width_bits: int = 0
    height_bits: int = 0
    x_offset_bits: int = 0
    y_offset_bits: int = 0
    optional_data_bits: int = 0
    coded_bytes_bits: int = 0
    equal_cells_size: int = 0
    pixel_mask_size: int = 0
    encoding_type_size: int = 0
    raw_pixel_size: int = 0
    frames: list = field(default_factory=list)
    palette_entries: list = field(default_factory=lambda: [0] * 256)
    box_min_x: int = 0
    box_min_y: int = 0
    box_max_x: int = 0
    box_max_y: int = 0
    h_cells: int = 0
    v_cells: int = 0
    cells: list = field(default_factory=list)
    pixel_buffer: list = field(default_factory=list)
    pixel_data: Optional[bytearray] = None


@dataclass
class DCCFile:
    version: int = 0
    num_directions: int = 0
    frames_per_direction: int = 0
    total_size_coded: int = 0
    directions: list = field(default_factory=list)


def decode_dcc(data: bytes) -> DCCFile:
    """Decode a DCC file from raw bytes."""
    dcc = DCCFile()

    # File header
    sig = data[0]
    if sig != 0x74:
        raise ValueError(f"Invalid DCC signature: 0x{sig:02x}")

    dcc.version = data[1]
    dcc.num_directions = data[2]
    dcc.frames_per_direction = struct.unpack_from('<I', data, 3)[0]
    # skip sanity check (4 bytes) at offset 7
    dcc.total_size_coded = struct.unpack_from('<I', data, 11)[0]

    # Direction offsets
    dir_offsets = []
    for i in range(dcc.num_directions):
        offset = struct.unpack_from('<I', data, 15 + i * 4)[0]
        dir_offsets.append(offset)

    # Decode each direction
    dcc.directions = []
    for dir_idx in range(dcc.num_directions):
        direction = _decode_direction(data, dir_offsets[dir_idx], dcc.frames_per_direction)
        dcc.directions.append(direction)

    return dcc


def _decode_direction(data: bytes, offset: int, frames_per_dir: int) -> DCCDirection:
    d = DCCDirection()
    d.frames_per_dir = frames_per_dir
    stream = BitReader(data, offset * 8)

    # Direction header
    d.out_size_coded = stream.read_bits(32)
    d.compression_flags = stream.read_bits(2)
    d.variable0_bits = CRAZY_BIT_TABLE[stream.read_bits(4)]
    d.width_bits = CRAZY_BIT_TABLE[stream.read_bits(4)]
    d.height_bits = CRAZY_BIT_TABLE[stream.read_bits(4)]
    d.x_offset_bits = CRAZY_BIT_TABLE[stream.read_bits(4)]
    d.y_offset_bits = CRAZY_BIT_TABLE[stream.read_bits(4)]
    d.optional_data_bits = CRAZY_BIT_TABLE[stream.read_bits(4)]
    d.coded_bytes_bits = CRAZY_BIT_TABLE[stream.read_bits(4)]

    # Frame headers
    min_x, min_y = 100000, 100000
    max_x, max_y = -100000, -100000

    d.frames = []
    for _ in range(frames_per_dir):
        f = DCCFrame()
        stream.read_bits(d.variable0_bits)  # skip variable0
        f.width = stream.read_bits(d.width_bits)
        f.height = stream.read_bits(d.height_bits)
        f.x_offset = stream.read_signed(d.x_offset_bits)
        f.y_offset = stream.read_signed(d.y_offset_bits)
        f.num_optional_bytes = stream.read_bits(d.optional_data_bits)
        f.num_coded_bytes = stream.read_bits(d.coded_bytes_bits)
        f.bottom_up = stream.read_bool()

        # Calculate frame bounding box
        f.box_min_x = f.x_offset
        f.box_min_y = f.y_offset - f.height + 1
        f.box_max_x = f.box_min_x + f.width
        f.box_max_y = f.box_min_y + f.height

        min_x = min(min_x, f.box_min_x)
        min_y = min(min_y, f.box_min_y)
        max_x = max(max_x, f.box_max_x)
        max_y = max(max_y, f.box_max_y)
        d.frames.append(f)

    d.box_min_x = min_x
    d.box_min_y = min_y
    d.box_max_x = max_x
    d.box_max_y = max_y

    if d.optional_data_bits > 0:
        # Skip optional data
        for f in d.frames:
            stream.read_bits(f.num_optional_bytes * 8)

    # Compression flags -> bitstream sizes
    if d.compression_flags & 2:
        d.equal_cells_size = stream.read_bits(20)
    d.pixel_mask_size = stream.read_bits(20)
    if d.compression_flags & 1:
        d.encoding_type_size = stream.read_bits(20)
        d.raw_pixel_size = stream.read_bits(20)

    # Palette entries (256-bit mask)
    palette_count = 0
    d.palette_entries = [0] * 256
    for i in range(256):
        if stream.read_bool():
            d.palette_entries[palette_count] = i
            palette_count += 1

    # Sub-bitstreams
    ec = stream.copy()
    pm = stream.offset_bits(d.equal_cells_size).copy()
    et = stream.offset_bits(d.pixel_mask_size).copy()
    rpc = stream.offset_bits(d.encoding_type_size).copy()
    pcd = stream.offset_bits(d.raw_pixel_size).copy()

    # Calculate cells
    _calculate_cells(d)

    # Fill pixel buffer
    _fill_pixel_buffer(d, pcd, ec, pm, et, rpc)

    # Generate frames
    _generate_frames(d, pcd)

    return d


def _calculate_cells(d: DCCDirection):
    box_w = d.box_max_x - d.box_min_x
    box_h = d.box_max_y - d.box_min_y

    d.h_cells = 1 + (box_w - 1) // CELL_SIZE if box_w > 0 else 1
    d.v_cells = 1 + (box_h - 1) // CELL_SIZE if box_h > 0 else 1

    # Cell widths
    cell_widths = [CELL_SIZE] * d.h_cells
    if d.h_cells == 1:
        cell_widths[0] = box_w
    else:
        cell_widths[-1] = box_w - (CELL_SIZE * (d.h_cells - 1))

    # Cell heights
    cell_heights = [CELL_SIZE] * d.v_cells
    if d.v_cells == 1:
        cell_heights[0] = box_h
    else:
        cell_heights[-1] = box_h - (CELL_SIZE * (d.v_cells - 1))

    d.cells = []
    y_off = 0
    for y in range(d.v_cells):
        x_off = 0
        for x in range(d.h_cells):
            d.cells.append(Cell(
                width=cell_widths[x],
                height=cell_heights[y],
                x_offset=x_off,
                y_offset=y_off,
            ))
            x_off += CELL_SIZE
        y_off += CELL_SIZE

    # Calculate cells for each frame
    for f in d.frames:
        _calc_frame_cells(d, f)


def _calc_frame_cells(d: DCCDirection, f: DCCFrame):
    first_w = CELL_SIZE - ((f.box_min_x - d.box_min_x) % CELL_SIZE)
    first_h = CELL_SIZE - ((f.box_min_y - d.box_min_y) % CELL_SIZE)

    remainder_w = f.width - first_w - 1
    remainder_h = f.height - first_h - 1

    f.h_cells = max(1, 2 + (remainder_w // CELL_SIZE))
    if (remainder_w % CELL_SIZE) == 0:
        f.h_cells -= 1
    if f.h_cells <= 0:
        f.h_cells = 1

    f.v_cells = max(1, 2 + (remainder_h // CELL_SIZE))
    if (remainder_h % CELL_SIZE) == 0:
        f.v_cells -= 1
    if f.v_cells <= 0:
        f.v_cells = 1

    # Frame cell widths
    cell_widths = [CELL_SIZE] * f.h_cells
    cell_widths[0] = f.width if f.h_cells == 1 else first_w
    if f.h_cells > 1:
        cell_widths[-1] = f.width - first_w - (CELL_SIZE * (f.h_cells - 2))

    # Frame cell heights
    cell_heights = [CELL_SIZE] * f.v_cells
    cell_heights[0] = f.height if f.v_cells == 1 else first_h
    if f.v_cells > 1:
        cell_heights[-1] = f.height - first_h - (CELL_SIZE * (f.v_cells - 2))

    f.cells = []
    pixel_y = f.box_min_y - d.box_min_y
    for cy in range(f.v_cells):
        pixel_x = f.box_min_x - d.box_min_x
        for cx in range(f.h_cells):
            f.cells.append(Cell(
                x_offset=pixel_x,
                y_offset=pixel_y,
                width=cell_widths[cx],
                height=cell_heights[cy],
            ))
            pixel_x += cell_widths[cx]
        pixel_y += cell_heights[cy]


PIXEL_MASK_LOOKUP = [0, 1, 1, 2, 1, 2, 2, 3, 1, 2, 2, 3, 2, 3, 3, 4]


def _fill_pixel_buffer(d: DCCDirection, pcd, ec, pm, et, rpc):
    max_cells = 0
    for f in d.frames:
        max_cells += f.h_cells * f.v_cells

    d.pixel_buffer = [PixelBufferEntry() for _ in range(max_cells)]
    cell_buffer = [None] * (d.h_cells * d.v_cells)
    pb_index = -1
    last_pixel = 0

    for frame_idx, frame in enumerate(d.frames):
        origin_cx = (frame.box_min_x - d.box_min_x) // CELL_SIZE
        origin_cy = (frame.box_min_y - d.box_min_y) // CELL_SIZE

        for cy in range(frame.v_cells):
            current_cy = cy + origin_cy
            for cx in range(frame.h_cells):
                current_cell = origin_cx + cx + (current_cy * d.h_cells)
                next_cell = False

                if cell_buffer[current_cell] is not None:
                    if d.equal_cells_size > 0:
                        tmp = ec.read_bits(1)
                    else:
                        tmp = 0
                    if tmp == 0:
                        pixel_mask = pm.read_bits(4)
                    else:
                        next_cell = True
                else:
                    pixel_mask = 0x0F

                if next_cell:
                    continue

                # Decode pixels
                pixel_stack = [0, 0, 0, 0]
                last_pixel = 0
                num_pixel_bits = PIXEL_MASK_LOOKUP[pixel_mask]
                encoding_type = 0

                if num_pixel_bits != 0 and d.encoding_type_size > 0:
                    encoding_type = et.read_bits(1)

                decoded_pixel = 0
                for i in range(num_pixel_bits):
                    if encoding_type != 0:
                        pixel_stack[i] = rpc.read_bits(8)
                    else:
                        pixel_stack[i] = last_pixel
                        disp = pcd.read_bits(4)
                        pixel_stack[i] += disp
                        while disp == 15:
                            disp = pcd.read_bits(4)
                            pixel_stack[i] += disp

                    if pixel_stack[i] == last_pixel:
                        pixel_stack[i] = 0
                        break
                    else:
                        last_pixel = pixel_stack[i]
                        decoded_pixel += 1

                old_entry = cell_buffer[current_cell]
                pb_index += 1

                cur_idx = decoded_pixel - 1
                for i in range(4):
                    if (pixel_mask & (1 << i)) != 0:
                        if cur_idx >= 0:
                            d.pixel_buffer[pb_index].value[i] = pixel_stack[cur_idx]
                            cur_idx -= 1
                        else:
                            d.pixel_buffer[pb_index].value[i] = 0
                    else:
                        if old_entry is not None:
                            d.pixel_buffer[pb_index].value[i] = old_entry.value[i]

                cell_buffer[current_cell] = d.pixel_buffer[pb_index]
                d.pixel_buffer[pb_index].frame = frame_idx
                d.pixel_buffer[pb_index].frame_cell_index = cx + (cy * frame.h_cells)

    # Remap through palette entries
    for i in range(pb_index + 1):
        for x in range(4):
            idx = d.pixel_buffer[i].value[x]
            if idx < len(d.palette_entries):
                d.pixel_buffer[i].value[x] = d.palette_entries[idx]


def _generate_frames(d: DCCDirection, pcd):
    for cell in d.cells:
        cell.last_width = -1
        cell.last_height = -1

    box_w = d.box_max_x - d.box_min_x
    box_h = d.box_max_y - d.box_min_y
    d.pixel_data = bytearray(box_w * box_h)

    # pb_idx must persist across all frames — the pixel buffer is a sequential
    # stream of changed cells ordered by (frame, cell) across ALL frames.
    pb_idx = 0
    for idx in range(len(d.frames)):
        pb_idx = _generate_frame(d, idx, pcd, box_w, pb_idx)


def _generate_frame(d: DCCDirection, idx: int, pcd, box_w: int, pb_idx: int) -> int:
    frame = d.frames[idx]
    box_h = d.box_max_y - d.box_min_y
    frame.pixel_data = bytearray(box_w * box_h)

    for cell_idx, cell in enumerate(frame.cells):
        cx = cell.x_offset // CELL_SIZE
        cy = cell.y_offset // CELL_SIZE
        cell_index = cx + (cy * d.h_cells)
        buffer_cell = d.cells[cell_index]
        pbe = d.pixel_buffer[pb_idx] if pb_idx < len(d.pixel_buffer) else PixelBufferEntry()

        if pbe.frame != idx or pbe.frame_cell_index != cell_idx:
            # EqualCell — reuse content from the shared direction pixel buffer
            if cell.width != buffer_cell.last_width or cell.height != buffer_cell.last_height:
                # Different sizes - clear the cell area
                for y in range(cell.height):
                    for x in range(cell.width):
                        pos = (x + cell.x_offset) + ((y + cell.y_offset) * box_w)
                        if 0 <= pos < len(d.pixel_data):
                            d.pixel_data[pos] = 0
            else:
                # Same sizes - copy from previous position in the shared buffer
                for fy in range(cell.height):
                    for fx in range(cell.width):
                        src = (fx + buffer_cell.last_x_offset) + ((fy + buffer_cell.last_y_offset) * box_w)
                        dst = (fx + cell.x_offset) + ((fy + cell.y_offset) * box_w)
                        if 0 <= src < len(d.pixel_data) and 0 <= dst < len(d.pixel_data):
                            d.pixel_data[dst] = d.pixel_data[src]

            # Copy current state of shared buffer into this frame
            for fy in range(cell.height):
                for fx in range(cell.width):
                    pos = (fx + cell.x_offset) + ((fy + cell.y_offset) * box_w)
                    if 0 <= pos < len(d.pixel_data) and 0 <= pos < len(frame.pixel_data):
                        frame.pixel_data[pos] = d.pixel_data[pos]
        else:
            # Matching pixel buffer entry — decode new pixel data
            if pbe.value[0] == pbe.value[1]:
                # Fill with solid color
                for y in range(cell.height):
                    for x in range(cell.width):
                        pos = (x + cell.x_offset) + ((y + cell.y_offset) * box_w)
                        if 0 <= pos < len(d.pixel_data):
                            d.pixel_data[pos] = pbe.value[0]
            else:
                # Read pixel indices from the pcd bitstream
                bits_to_read = 1 if pbe.value[1] == pbe.value[2] else 2
                for y in range(cell.height):
                    for x in range(cell.width):
                        pal_idx = pcd.read_bits(bits_to_read)
                        pos = (x + cell.x_offset) + ((y + cell.y_offset) * box_w)
                        if 0 <= pos < len(d.pixel_data):
                            d.pixel_data[pos] = pbe.value[pal_idx]

            # Copy cell into frame
            for fy in range(cell.height):
                for fx in range(cell.width):
                    pos = (fx + cell.x_offset) + ((fy + cell.y_offset) * box_w)
                    if 0 <= pos < len(d.pixel_data) and 0 <= pos < len(frame.pixel_data):
                        frame.pixel_data[pos] = d.pixel_data[pos]
            pb_idx += 1

        buffer_cell.last_width = cell.width
        buffer_cell.last_height = cell.height
        buffer_cell.last_x_offset = cell.x_offset
        buffer_cell.last_y_offset = cell.y_offset

    frame.cells = []
    return pb_idx
