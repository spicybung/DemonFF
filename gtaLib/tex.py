# BLeeds - R* Leeds texture reader for CHK/XTX/TEX
# Author: spicybung
# Years: 2025 - 2026
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import struct
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Sequence

import numpy as np

#   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #
#   This script is for .CHK/XTX/TEX - dictionaries for LCS/VCS/CW/MH2 textures      #
#   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #
# - Script resources:
# • https://gtamods.com/wiki/Relocatable_chunk (pre-process)
# • https://web.archive.org/web/20180729204205/http://gtamodding.ru/wiki/CHK (.xtx, .tex)
# - Mod resources/cool stuff:
# • https://libertycity.net/files/gta-liberty-city-stories/48612-yet-another-img-editor.html (extract textures)
# • https://gtaforums.com/topic/518948-rel-gta-stories-texture-explorer-20/ (view/explore textures)
# • https://www.dixmor-hospital.com/mhs/index.php (Manhunt 2)

#######################################################

def read_u32(data: bytes, offset: int) -> int:

    return struct.unpack_from('<I', data, offset)[0]

def read_cstr(data: bytes, offset: int, length: int) -> str:

    s = data[offset:offset + length]
    end = s.find(b'\0')
    if end == -1:
        end = len(s)
    return s[:end].decode('ascii', 'replace')

def unswizzle_psp_4bit(src: bytes, w: int, h: int) -> bytes:

    min_width = 32
    bufw = w if w >= min_width else min_width
    stride = bufw // 2
    dest = bytearray(stride * h)
    nbx = stride // 16
    nby = (h + 7) // 8
    src_pos = 0
    for yb in range(nby):
        row_base = yb * 8 * stride
        for xb in range(nbx):
            block_base = row_base + xb * 16
            b_off = block_base
            for n in range(8):
                dest[b_off:b_off + 16] = src[src_pos:src_pos + 16]
                src_pos += 16
                b_off += stride
    out = bytearray((w // 2) * h)
    for row in range(h):
        src_offset = row * stride
        dst_offset = row * (w // 2)
        out[dst_offset:dst_offset + (w // 2)] = dest[src_offset:src_offset + (w // 2)]
    return bytes(out)

def unswizzle_psp_8bit(src: bytes, w: int, h: int) -> bytes:
    min_width = 16
    bufw = w if w >= min_width else min_width
    stride = bufw
    dest = bytearray(stride * h)
    nbx = stride // 16
    nby = (h + 7) // 8
    src_pos = 0
    for yb in range(nby):
        row_base = yb * 8 * stride
        for xb in range(nbx):
            block_base = row_base + xb * 16
            b_off = block_base
            for n in range(8):
                dest[b_off:b_off + 16] = src[src_pos:src_pos + 16]
                src_pos += 16
                b_off += stride
    out = bytearray(w * h)
    for row in range(h):
        src_offset = row * stride
        dst_offset = row * w
        out[dst_offset:dst_offset + w] = dest[src_offset:src_offset + w]
    return bytes(out)

def unswizzle_psp_32bit(src: bytes, w: int, h: int) -> bytes:
    min_width = 4
    bufw = w if w >= min_width else min_width
    stride = bufw * 4
    dest = bytearray(stride * h)
    nbx = stride // 16
    nby = (h + 7) // 8
    src_pos = 0
    for yb in range(nby):
        row_base = yb * 8 * stride
        for xb in range(nbx):
            block_base = row_base + xb * 16
            b_off = block_base
            for n in range(8):
                dest[b_off:b_off + 16] = src[src_pos:src_pos + 16]
                src_pos += 16
                b_off += stride
    out = bytearray(w * h * 4)
    for row in range(h):
        src_offset = row * stride
        dst_offset = row * w * 4
        out[dst_offset:dst_offset + w * 4] = dest[src_offset:src_offset + w * 4]
    return bytes(out)

def expand_nibbles_lo_first(data: bytes) -> np.ndarray:

    out = np.empty(len(data) * 2, dtype=np.uint8)
    for i, value in enumerate(data):
        out[2 * i] = value & 0x0F
        out[2 * i + 1] = (value >> 4) & 0x0F
    return out

def swizzle_ps2(x: int, y: int, logw: int) -> int:

    nx = (x & 7) ^ (((y >> 1) ^ (y >> 2)) << 2)
    nx = (nx & 7) | ((x >> 1) & ~7)
    ny = (y & 1) | ((y >> 1) & ~1)
    n = ((y >> 1) & 1) | (((x >> 3) & 1) << 1)
    return n | (nx << 2) | (ny << (logw - 1 + 2))

def unswizzle_ps2_indices(idx: np.ndarray, w: int, h: int) -> np.ndarray:

    total = w * h
    dst = np.empty(total, dtype=np.uint8)

    logw = 0
    tmp = 1
    while tmp < w:
        tmp <<= 1
        logw += 1
    for y in range(h):
        for x in range(w):
            dst[y * w + x] = idx[swizzle_ps2(x, y, logw) % len(idx)]
    return dst

def convert_clut_ps2(data: np.ndarray) -> None:

    mapping = [0x00, 0x10, 0x08, 0x18]
    for i in range(len(data)):
        v = int(data[i])
        data[i] = (v & ~0x18) | mapping[(v & 0x18) >> 3]

@dataclass
class PspTexHeader:

    unknown0: int
    raster_offset: int
    swizzle_width: int
    width_pow2: int
    height_pow2: int
    bpp: int
    mip_count: int
    tail: int

    @property
    def width(self) -> int:
        return 1 << self.width_pow2 if self.width_pow2 < 32 else 0

    @property
    def height(self) -> int:
        return 1 << self.height_pow2 if self.height_pow2 < 32 else 0

@dataclass
class Ps2TexHeader:

    reserved0: int
    reserved1: int
    raster_offset: int
    flags: int

    @property
    def swizzle_mask(self) -> int:
        return self.flags & 0xFF

    @property
    def mip_count(self) -> int:
        return (self.flags >> 8) & 0xF

    @property
    def bpp(self) -> int:
        return (self.flags >> 14) & 0x3F

    @property
    def width_pow2(self) -> int:
        return (self.flags >> 20) & 0x3F

    @property
    def height_pow2(self) -> int:
        return (self.flags >> 26) & 0x3F

    @property
    def width(self) -> int:
        return 1 << self.width_pow2 if self.width_pow2 < 32 else 0

    @property
    def height(self) -> int:
        return 1 << self.height_pow2 if self.height_pow2 < 32 else 0

def parse_psp_header(data: bytes, offset: int) -> Optional[PspTexHeader]:

    if offset <= 0 or offset + 16 > len(data):
        return None
    hdr = data[offset:offset + 16]
    if len(hdr) < 16:
        return None
    unknown0 = read_u32(hdr, 0)
    raster_offset = read_u32(hdr, 4)
    swizzle_width = struct.unpack_from('<H', hdr, 8)[0]
    width_pow2 = hdr[10]
    height_pow2 = hdr[11]
    bpp = hdr[12]
    mip_count = hdr[13]
    tail = struct.unpack_from('<H', hdr, 14)[0]
    width = 1 << width_pow2 if width_pow2 < 32 else 0
    height = 1 << height_pow2 if height_pow2 < 32 else 0
    if width == 0 or height == 0 or width > 4096 or height > 4096:
        return None
    return PspTexHeader(
        unknown0=unknown0,
        raster_offset=raster_offset,
        swizzle_width=swizzle_width,
        width_pow2=width_pow2,
        height_pow2=height_pow2,
        bpp=bpp,
        mip_count=mip_count,
        tail=tail,
    )

def parse_ps2_header(data: bytes, offset: int) -> Optional[Ps2TexHeader]:

    if offset <= 0 or offset + 16 > len(data):
        return None
    hdr = data[offset:offset + 16]
    if len(hdr) < 16:
        return None
    reserved0 = read_u32(hdr, 0)
    reserved1 = read_u32(hdr, 4)
    raster_offset = read_u32(hdr, 8)
    flags = read_u32(hdr, 12)

    w_pow2_std = (flags >> 20) & 0x3F
    h_pow2_std = (flags >> 26) & 0x3F
    bpp_std = (flags >> 14) & 0x3F
    width_std = 1 << w_pow2_std if w_pow2_std < 32 else 0
    height_std = 1 << h_pow2_std if h_pow2_std < 32 else 0

    use_alt = False

    h_pow2_alt = flags & 0x3F
    w_pow2_alt = (flags >> 6) & 0x3F
    bpp_alt = (flags >> 12) & 0x3F
    alt_unknown = (flags >> 18) & 0x3
    mip_alt = (flags >> 20) & 0xF
    swizzle_alt = (flags >> 24) & 0xFF
    width_alt = 1 << w_pow2_alt if w_pow2_alt < 32 else 0
    height_alt = 1 << h_pow2_alt if h_pow2_alt < 32 else 0

    std_invalid = (width_std == 0 or height_std == 0 or width_std > 4096 or height_std > 4096)
    alt_valid_dims = (width_alt > 0 and height_alt > 0 and width_alt <= 4096 and height_alt <= 4096)
    alt_bpp_reasonable = bpp_alt in (4, 8, 16, 32)

    if (
        std_invalid or
        (width_std <= 8 and height_std <= 8) or
        (bpp_std not in (4, 8, 16, 32))
    ) and alt_valid_dims and alt_bpp_reasonable:
        use_alt = True
    if use_alt:

        canonical_flags = (
            (swizzle_alt & 0xFF)
            | ((mip_alt & 0xF) << 8)
            | ((alt_unknown & 0x3) << 12)
            | ((bpp_alt & 0x3F) << 14)
            | ((w_pow2_alt & 0x3F) << 20)
            | ((h_pow2_alt & 0x3F) << 26)
        )
        flags = canonical_flags
        width_std = width_alt
        height_std = height_alt

    if width_std == 0 or height_std == 0 or width_std > 4096 or height_std > 4096:
        return None
    return Ps2TexHeader(
        reserved0=reserved0,
        reserved1=reserved1,
        raster_offset=raster_offset,
        flags=flags,
    )

def slot_base_from_slot_ptr(slot_ptr: int) -> int:
    if slot_ptr <= 0:
        return 0
    return max(0, slot_ptr - 8)

def parse_container(data: bytes, base: int) -> Optional[Dict[str, int]]:

    if base < 0 or base + 80 > len(data):
        return None
    tex_off = read_u32(data, base + 0x00)
    coll_off = read_u32(data, base + 0x04)
    next_slot = read_u32(data, base + 0x08)
    prev_slot = read_u32(data, base + 0x0C)
    name = read_cstr(data, base + 0x10, 64)
    return {
        'base': base,
        'tex_off': tex_off,
        'coll_off': coll_off,
        'next_slot': next_slot,
        'prev_slot': prev_slot,
        'name': name,
    }

def decode_psp_texture(
    data: bytes,
    thdr: PspTexHeader,
    block_size: int,
    palette_override: Optional[Sequence[Tuple[int, int, int, int]]] = None,
) -> Optional[np.ndarray]:
    w = thdr.width
    h = thdr.height
    bpp = thdr.bpp
    offset = thdr.raster_offset
    if w <= 0 or h <= 0 or offset <= 0:
        return None
    pixel_count = w * h
    if bpp == 4:
        base_bytes = (pixel_count + 1) // 2
    elif bpp == 8:
        base_bytes = pixel_count
    elif bpp == 32:
        base_bytes = pixel_count * 4
    else:
        return None
    if offset + base_bytes > len(data):
        return None
    raw = data[offset:offset + base_bytes]

    if thdr.swizzle_width:
        if bpp == 4:
            unswizzled = unswizzle_psp_4bit(raw, w, h)
            idx = expand_nibbles_lo_first(unswizzled)
        elif bpp == 8:
            unswizzled = unswizzle_psp_8bit(raw, w, h)
            idx = np.frombuffer(unswizzled, dtype=np.uint8)
        elif bpp == 32:
            unswizzled = unswizzle_psp_32bit(raw, w, h)
            rgba = np.frombuffer(unswizzled, dtype=np.uint8).reshape((h, w, 4))
            return rgba
    else:
        if bpp == 4:
            idx = expand_nibbles_lo_first(raw)
        elif bpp == 8:
            idx = np.frombuffer(raw, dtype=np.uint8)
        elif bpp == 32:
            rgba = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 4))
            return rgba
    pal = palette_override
    if pal is None:
        if bpp == 4:

            pal_size = 16 * 4
        elif bpp == 8:

            pal_size = 256 * 4
        else:
            pal_size = 0
        if pal_size > 0:
            pal_start = offset + block_size - pal_size
            pal_end = pal_start + pal_size
            if 0 <= pal_start < pal_end <= len(data):
                pal_bytes = data[pal_start:pal_end]
                pal = []
                for i in range(0, len(pal_bytes), 4):
                    r = pal_bytes[i]
                    g = pal_bytes[i + 1]
                    b = pal_bytes[i + 2]
                    a = pal_bytes[i + 3]
                    pal.append((r, g, b, a))
            else:
                pal = None
    rgba = np.empty((h, w, 4), dtype=np.uint8)
    if pal:

        for i, v in enumerate(idx[:pixel_count]):
            y = i // w
            x = i % w
            col = pal[int(v) % len(pal)]
            rgba[y, x] = col
    else:

        max_idx = int(idx.max()) if len(idx) > 0 else 0
        scale = 255.0 / max_idx if max_idx > 0 else 0.0
        for i, v in enumerate(idx[:pixel_count]):
            y = i // w
            x = i % w
            gval = int(v * scale + 0.5)
            rgba[y, x] = (gval, gval, gval, 255)
    return rgba

def decode_ps2_texture(
    data: bytes,
    thdr: Ps2TexHeader,
    block_size: int,
    palette_override: Optional[Sequence[Tuple[int, int, int, int]]] = None,
) -> Optional[np.ndarray]:
    w = thdr.width
    h = thdr.height
    bpp = thdr.bpp
    offset = thdr.raster_offset
    if w <= 0 or h <= 0 or offset <= 0:
        return None
    pixel_count = w * h
    if bpp == 4:
        base_bytes = (pixel_count + 1) // 2
    elif bpp == 8:
        base_bytes = pixel_count
    elif bpp == 16:
        base_bytes = pixel_count * 2
    elif bpp == 32:
        base_bytes = pixel_count * 4
    else:
        return None
    if offset + base_bytes > len(data):
        return None
    raw = data[offset:offset + base_bytes]
    pal = palette_override
    if bpp in (4, 8) and pal is None:
        pal_len = 16 if bpp == 4 else 256
        pal_bytes_len = pal_len * 4
        pal_start = offset + block_size - pal_bytes_len
        pal_end = pal_start + pal_bytes_len
        if 0 <= pal_start < pal_end <= len(data):
            pal_bytes = data[pal_start:pal_end]
            pal = []
            for i in range(0, len(pal_bytes), 4):
                r = pal_bytes[i]
                g = pal_bytes[i + 1]
                b = pal_bytes[i + 2]
                a = pal_bytes[i + 3]
                a = int(a * 255 / 128)
                if a > 255:
                    a = 255
                pal.append((r, g, b, a))
        else:
            pal = None
    if bpp == 4:
        idx = np.empty(pixel_count, dtype=np.uint8)
        for i in range(pixel_count // 2):
            byte = raw[i]
            idx[i * 2] = byte & 0x0F
            idx[i * 2 + 1] = byte >> 4
        if pixel_count % 2:
            idx[-1] = raw[pixel_count // 2] & 0x0F
        if thdr.swizzle_mask & 1:
            idx = unswizzle_ps2_indices(idx, w, h)
    elif bpp == 8:

        idx = np.frombuffer(raw, dtype=np.uint8).copy()
        if thdr.swizzle_mask & 1:
            idx = unswizzle_ps2_indices(idx, w, h)
        convert_clut_ps2(idx)
    elif bpp == 32:
        if thdr.swizzle_mask & 1:
            unswizzled = unswizzle_psp_32bit(raw, w, h)
        else:
            unswizzled = raw
        rgba = np.frombuffer(unswizzled, dtype=np.uint8).reshape((h, w, 4))
        alpha = rgba[:, :, 3].astype(np.int32) * 255 // 128
        alpha = np.clip(alpha, 0, 255).astype(np.uint8)
        rgba[:, :, 3] = alpha
        return rgba
    else:
        return None
    rgba = np.empty((h, w, 4), dtype=np.uint8)
    if pal:
        for i in range(pixel_count):
            y = i // w
            x = i % w
            col = pal[int(idx[i]) % len(pal)]
            rgba[y, x] = col
    else:
        max_idx = int(idx.max()) if len(idx) > 0 else 0
        scale = 255.0 / max_idx if max_idx > 0 else 0.0
        for i in range(pixel_count):
            y = i // w
            x = i % w
            val = int(idx[i] * scale + 0.5)
            rgba[y, x] = (val, val, val, 255)
    return rgba
