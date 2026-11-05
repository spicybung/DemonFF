# BLeeds - Scripts for working with R* Leeds (GTA Stories, Manhunt 2, etc) formats in Blender
# Author: spicybung
# Years: 2025 - 2026

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# LVZ/IMG reader adapted from BLeeds; shared by the hidden IMG import route.
from __future__ import annotations
import struct
import os
import zlib
import time
import math
import csv
import re
import zipfile
from bisect import bisect_right
from pathlib import Path
from dataclasses import dataclass
from typing import Tuple, List, Dict, Optional, Iterable
import numpy as np
try:
    import bpy
    from mathutils import Matrix
except ModuleNotFoundError:
    bpy = None
    Matrix = None


def set_mesh_auto_smooth(mesh, enabled=True):
    if hasattr(mesh, 'use_auto_smooth'):
        mesh.use_auto_smooth = enabled

CONCISE_IMPORT_LOG = True

def conciseImportLogMessage(message):
    text = str(message)
    stripped = text.strip()
    if not CONCISE_IMPORT_LOG:
        return text
    if not stripped:
        return ""
    if text.startswith(("  ", "\t")):
        return None

    hidden_prefixes = (
        "Patch:", "[policy]", "[mode]", "[ide]", "[wrldtool-offset]",
        "[res ", "[overlay-bounds]", "[2dfx]", "[img-mdl]", "[matrix]",
        "[matrix-log]", "[resolver]", "[submodel]", "[geometry-recovery]",
        "[compare]", "[ids]", "[mdl]", "[unpack]", "[overlay]",
        "[row-overlay]", "[nested]", "[area-mdl]", "[ipl-mdl]",
        "[aggregate]", "[cleanup]", "[reference-dff-compare]",
        "[apply] RES=", "[apply] matrix_world", "[apply] global IPL",
        "[apply] reused ", "[apply] IPL/model", "[apply] exact missing",
        "[apply] final missing", "[apply] recovered WRLD",
        "[apply] imported missing", "[apply] first ",
    )
    if stripped.startswith(hidden_prefixes):
        return None

    if stripped.startswith(("— Master Resource Table", "— FILTERED VISIBLE RESOURCE IDs", "— Slave Group Table")):
        return None
    if stripped.startswith((
        "LIGHTS-SKIP ", "SKIP_DUP ", "SUBMODEL ", "REJECT ",
        "EXACT MISSING ", "FINAL MISSING ", "MISSING MDL ", "ROW_MATRIX ",
    )):
        return None

    if stripped in ("===== LVZ Walk + IMG Match/Apply =====", "===== LVZ + IMG Import ====="):
        return "===== LVZ + IMG Import ====="
    if stripped.startswith("[log] live import log:"):
        return "Log: " + stripped.split(":", 1)[1].strip()
    if stripped.startswith("[io] LVZ bytes in:"):
        match = re.search(r"LVZ bytes in:\s*(\d+)\s+decomp:\s*(\d+)(.*)$", stripped)
        if match:
            suffix = match.group(3).strip()
            return "LVZ size: {} bytes -> {} bytes{}".format(
                match.group(1), match.group(2), (" " + suffix) if suffix else ""
            )
    if stripped.startswith("[lvz] master Resource[]:"):
        match = re.search(r"count=(\d+).*?game_hint=([^ ]+)", stripped)
        if match:
            return "Resource entries: {} ({})".format(match.group(1), match.group(2).upper())
    if stripped.startswith("— IMG Read —"):
        match = re.search(r"source:\s*(.*?)\s+bytes=(\d+)", stripped)
        if match:
            return "IMG: {} ({} bytes)".format(match.group(1), match.group(2))
    if stripped.startswith("[platform] auto-detected"):
        match = re.search(r"auto-detected\s+([^;]+)", stripped)
        return "Platform: " + (match.group(1).strip() if match else stripped)
    if stripped.startswith("[platform] resource dialects:"):
        match = re.search(r"final platform=([^;]+)", stripped)
        return "Platform confirmed: " + (match.group(1).strip() if match else stripped)
    if stripped.startswith("[continues-img] proof scan:"):
        match = re.search(r"empty_resource_ids=(\d+).*?proven=(\d+).*?new=(\d+)", stripped)
        if match:
            return "Empty LVZ model entries checked: {}; IMG matches found: {} ({} new)".format(
                match.group(1), match.group(2), match.group(3)
            )
        return None
    if stripped.startswith("IMG-backed models found:"):
        return "IMG-backed model entries: " + stripped.split(":", 1)[1].strip()
    if stripped.startswith("[img] sector row directories:"):
        return "World sector rows: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[img] concrete sector headers:"):
        return "Static map blocks: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[img] extra AREA/triggered candidate containers:"):
        return "Additional IMG model-data blocks: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[speed] exact duplicate visible placement rows removed:"):
        match = re.search(r"removed:\s*(\d+).*?retained=(\d+)", stripped)
        if match:
            return "Repeated sector copies removed: {}\nStatic placements kept: {}".format(
                match.group(1), match.group(2)
            )
    if stripped.startswith("[img] sector rows candidate="):
        match = re.search(
            r"candidate=(\d+)\s+valid=(\d+)\s+kept=(\d+)\s+skipped_lod=(\d+)\s+skipped_dupes=(\d+)",
            stripped,
        )
        if match:
            return (
                "Placement rows scanned: {}\n"
                "Valid rows: {}\n"
                "LOD rows ignored: {}\n"
                "Repeated rows ignored: {}"
            ).format(match.group(1), match.group(2), match.group(4), match.group(5))
        return None
    if stripped.startswith("[img] extra rows candidate="):
        return None
    if stripped.startswith("[img] IMG placement rows kept after pass filtering:"):
        return "Placements ready: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[img] resource-id dump skipped"):
        return None
    if stripped.startswith("[img] LIGHTS mesh placements kept:"):
        return "LIGHTS mesh placements kept: " + stripped.rsplit(":", 1)[1].strip() + " (2DFX effects are separate)"
    if stripped.startswith("[model-lookup] after LVZ and same-sector IMG:"):
        match = re.search(r"details=(\d+).*?row/res=(\d+).*?res=(\d+)", stripped)
        if match:
            return (
                "Model lookup after LVZ and matching sector tables: {} placements still need models; "
                "{} row-specific keys and {} resource IDs will be checked in the remaining exact tables."
            ).format(match.group(1), match.group(2), match.group(3))
        return None
    if stripped.startswith("[exact-models] other map blocks added:"):
        return "Exact models added from other static map blocks: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[exact-models] conflicting resource IDs skipped:"):
        return "Conflicting model entries ignored during the cross-sector search: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[exact-models] conflicting static resource IDs not used outside their own sector:"):
        return "Resource IDs with different sector-specific models kept local to their own sectors: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[exact-models] conflicting linked resource IDs skipped:"):
        return "Linked model IDs with conflicting geometry left unresolved: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[exact-models] ambiguous unresolved resource IDs left unplaced:"):
        return "Placements left missing instead of using conflicting model data: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[exact-resolution] unresolved placements="):
        match = re.search(r"unresolved placements=(\d+)\s+resource_ids=(\d+)", stripped)
        if match:
            return "After all exact WRLD resource tables: {} placements still lack models ({} resource IDs).".format(
                match.group(1), match.group(2)
            )
        return None
    if stripped.startswith("[raw-img-models] recovered="):
        match = re.search(r"recovered=(\d+)\s+requested=(\d+)", stripped)
        if match:
            return "Models found in the remaining raw IMG data: {} of {} requested resource IDs.".format(
                match.group(1), match.group(2)
            )
        return None
    if stripped.startswith("[raw-img-models] final-choice model pool:"):
        return "Raw IMG models available only for unresolved IDs: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[progress]"):
        lower = stripped.lower()
        if "applying img placement" in lower:
            return "Placing objects..."
        if "building lvz resource" in lower:
            return "Building LVZ models..."
        if "same-sector img resource" in lower:
            return "Building IMG models used by static map blocks..."
        if "raw img model data" in lower:
            return "Checking remaining raw IMG model data for unresolved resource IDs..."
        if "exact img resource models from other map blocks" in lower:
            return "Checking exact resource tables in other static map blocks..."
        if "child resource records" in lower:
            return "Checking exact child resource records..."
        if "shared resource records" in lower:
            return "Checking exact shared resource records..."
        if "linked area records" in lower:
            return "Checking exact linked AREA resource records..."
        return None
    if stripped.startswith("[speed] disabled Blender global undo"):
        return "Speed mode: Blender global undo temporarily disabled."
    if stripped.startswith("[speed] linked duplicate placements"):
        return "Speed mode: linked placement copies are batched until placement finishes."
    if stripped.startswith("[speed] hidden placement collection setup failed"):
        return "Warning: placement batching could not be enabled."
    if stripped.startswith("[apply-progress] placed="):
        match = re.search(r"placed=(\d+)/(\d+).*?missing=(\d+)", stripped)
        if match:
            return "Placed {} of {} objects; {} still missing".format(
                match.group(1), match.group(2), match.group(3)
            )
    if stripped.startswith("[apply-progress] finished placement loop"):
        return None
    if stripped.startswith("[apply] skipped missing mesh/resource rows:"):
        return "Missing placements: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[apply] skipped LIGHTS-pass IPL mesh rows:"):
        return "LIGHTS mesh rows skipped: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[apply] raw parser base cleanup:"):
        return None
    if stripped.startswith("[apply] IMG placement rows applied:"):
        return "Objects placed: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[apply] linked duplicate placement objects created:"):
        return "Linked placement copies created: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("Warning: parse failed at"):
        match = re.search(
            r"Warning: parse failed at (0x[0-9A-Fa-f]+): unsupported or implausible WRLD material list at (0x[0-9A-Fa-f]+): count16=(\d+) size16=(\d+)",
            stripped,
        )
        if match:
            return "Warning: model data at {} has an invalid material table (count={}, size={}).".format(
                match.group(1), match.group(3), match.group(4)
            )
        return stripped.replace("unsupported or implausible WRLD", "invalid WRLD")
    if stripped.startswith("[summary] LVZ-table MDL resource objects parsed:"):
        return "LVZ models built: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[summary] IMG sector overlay MDL objects parsed:"):
        return "IMG models built for static map blocks: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[summary] IMG child-record exact models parsed:"):
        return "Exact IMG models from child resource records: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[summary] IMG shared-record exact models parsed:"):
        return "Exact IMG models from shared resource records: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[summary] IMG linked AREA exact models parsed:"):
        return "Exact IMG models from linked AREA records: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[summary] deleted unplaced resource objects:"):
        return "Unused model bases cleaned up: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[summary] linked IMG placement duplicates:"):
        return "Linked placement copies: " + stripped.rsplit(":", 1)[1].strip()
    if stripped.startswith("[summary]"):
        return None
    if stripped.startswith("[done]"):
        return None
    if stripped.startswith("[total] finished in"):
        parts = stripped.rsplit(" in ", 1)
        return "Total time: " + (parts[1] if len(parts) > 1 else stripped)
    if stripped.startswith("[speed] restored Blender global undo"):
        return "Speed mode: Blender global undo restored."
    if stripped.startswith("[") or stripped.startswith("—"):
        return None
    if stripped.startswith("Warning: exact missing IMG MDL"):
        return None
    return text

class DebugOut:
    def __init__(self, enable_console: bool, write_file: bool, file_path: Optional[str]):
        self.enable_console = enable_console
        self.write_file = write_file
        self.file_path = file_path
        self._buf: List[str] = []
        self._line_count = 0
        self._fh = None
        self._concise_seen = set()
        self._pending_log_bytes = 0
        self._last_log_flush = time.monotonic()
        if self.write_file and self.file_path:
            self.openLiveLog()

    def openLiveLog(self):
        paths = []
        if self.file_path:
            paths.append(Path(self.file_path))
            try:
                paths.append(Path.cwd() / Path(self.file_path).name)
            except Exception:
                pass
            try:
                paths.append(Path.home() / "Desktop" / Path(self.file_path).name)
            except Exception:
                pass
        tried = set()
        for path in paths:
            try:
                path = Path(path)
                key = str(path).lower()
                if key in tried:
                    continue
                tried.add(key)
                path.parent.mkdir(parents=True, exist_ok=True)
                self._fh = path.open("w", encoding="utf-8", buffering=65536)
                self.file_path = str(path)
                return
            except Exception as e:
                print(f"[log] failed to open '{path}': {e}")
        self.write_file = False
        self._fh = None

    def log(self, msg: str):
        raw_msg = str(msg)


        if self.enable_console:
            print(raw_msg)

        msg = conciseImportLogMessage(raw_msg)
        if msg is None:
            return
        once_prefixes = (
            "Resource entries:", "IMG-backed model entries:",
            "Building LVZ models...", "Building IMG models used by static map blocks...",
            "Checking remaining raw IMG model data for unresolved resource IDs...",
            "Checking exact resource tables in other static map blocks...",
            "Checking exact child resource records...",
            "Checking exact shared resource records...",
            "Checking exact linked AREA resource records...",
            "Placing objects...", "LVZ models built:",
            "IMG models built for static map blocks:",
            "Additional exact IMG models built:",
        )
        if str(msg).startswith(once_prefixes):
            if msg in self._concise_seen:
                return
            self._concise_seen.add(msg)
        if self.write_file:
            self._line_count += 1
            if self._fh is not None:
                try:
                    line = str(msg) + "\n"
                    self._fh.write(line)
                    self._pending_log_bytes += len(line)
                    now = time.monotonic()
                    if self._pending_log_bytes >= 65536 or now - self._last_log_flush >= 0.5:
                        self._fh.flush()
                        self._pending_log_bytes = 0
                        self._last_log_flush = now
                except Exception as e:
                    print(f"[log] live write failed '{self.file_path}': {e}")
                    try:
                        self._fh.close()
                    except Exception:
                        pass
                    self._fh = None
                    self._buf.append(msg)
            else:
                self._buf.append(msg)

    def flush(self):
        if not self.write_file or not self.file_path:
            return
        try:
            if self._fh is not None:
                self._fh.flush()
                self._pending_log_bytes = 0
                self._last_log_flush = time.monotonic()
                return
            Path(self.file_path).write_text("\n".join(self._buf), encoding="utf-8")
        except Exception as e:
            print(f"[log] failed to write '{self.file_path}': {e}")

    def close(self):
        self.flush()
        if self._fh is not None:
            try:
                self._fh.close()
            except Exception:
                pass
            self._fh = None

DEBUG: Optional[DebugOut] = None

def dbg(msg: str):
    if DEBUG is not None:
        DEBUG.log(msg)

LVZ_MAX_DECOMPRESSED_BYTES = 256 * 1024 * 1024

LVZ_MAX_RESOURCE_ROWS = 200000

LVZ_MAX_TEXTURE_BLOB_BYTES = (2 * 1024 * 1024) + 64

LVZ_DIRECT_TEXTURE_HEADER_BYTES = 16

LVZ_DIRECT_TEXTURE_PALETTE_BYTES = 64

LVZ_DIRECT_TEXTURE_PALETTE_BYTES_8BPP = 1024

LVZ_MAX_TEXTURE_DIMENSION = 2048

LVZ_MAX_TEXTURE_PIXELS = LVZ_MAX_TEXTURE_DIMENSION * LVZ_MAX_TEXTURE_DIMENSION

LVZ_MAX_IMG_ROWS_PER_CONTAINER = 200000

LVZ_MAX_MDL_BATCHES_PER_RESOURCE = 512

LVZ_MAX_MDL_VERTICES_PER_BATCH = 8192

LVZ_MAX_MDL_VERTICES_PER_OBJECT = 250000

LVZ_MAX_VERBOSE_VERTEX_LOGS_PER_MDL = 512

LVZ_UNPACK_SEARCH_WINDOW = 0x90

LVZ_UNPACK_ALIGN_LOG_LIMIT = 120

LVZ_UNPACK_NEXT_SELF_LOOP_LOG_LIMIT = 80

LVZ_MIN_RESOURCE_CANDIDATE_ADDR = 0x40

IMG_PASS_NAMES_VCS = (
    "SUPERLOD",
    "UNDERWATER",
    "LOD",
    "ROADS",
    "NORMAL",
    "NOZWRITE",
    "LIGHTS",
    "TRANSPARENT",
)

IMG_PASS_NAMES_LCS = (
    "SUPERLOD",
    "LOD",
    "ROADS",
    "NORMAL",
    "NOZWRITE",
    "LIGHTS",
    "TRANSPARENT",
)

IMG_VISIBLE_PASS_NAMES_DEFAULT = {
    "UNDERWATER",
    "ROADS",
    "NORMAL",
    "NOZWRITE",
    "LIGHTS",
    "TRANSPARENT",
}

IMG_MODEL_PASS_NAMES_DEFAULT = set(IMG_VISIBLE_PASS_NAMES_DEFAULT)

IMG_NON_MODEL_PASS_NAMES = set()

IMG_LOD_PASS_NAMES = {"SUPERLOD", "LOD"}

def read_u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]

def read_u16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]

def read_i16(b: bytes, o: int) -> int:
    return struct.unpack_from("<h", b, o)[0]

def align_up4(o: int) -> int:
    return (o + 3) & ~3

def align_down4(o: int) -> int:
    return (o) & ~3

def is_zlib(data: bytes) -> bool:
    return len(data) >= 2 and data[0] == 0x78 and data[1] in (0x01, 0x9C, 0xDA)

def decompress_with_limit(data: bytes, wbits: int, max_output: int = LVZ_MAX_DECOMPRESSED_BYTES) -> bytes:
    decoder = zlib.decompressobj(wbits)
    out = decoder.decompress(data, max_output + 1)
    if len(out) > max_output or decoder.unconsumed_tail:
        raise ValueError(
            f"Refusing to decompress LVZ past {max_output} bytes. "
            "The input may be corrupt, the wrong platform variant, or not a Leeds LVZ."
        )
    tail = decoder.flush(max_output + 1 - len(out))
    out += tail
    if len(out) > max_output:
        raise ValueError(
            f"Refusing to decompress LVZ past {max_output} bytes. "
            "The input may be corrupt, the wrong platform variant, or not a Leeds LVZ."
        )
    if not decoder.eof:
        raise ValueError('Truncated compressed LVZ stream')
    return out

def safe_decompress(data: bytes) -> Tuple[bytes, bool]:
    if not data:
        return data, False
    if is_zlib(data):
        try:
            return decompress_with_limit(data, zlib.MAX_WBITS), True
        except ValueError:
            raise
        except Exception:
            pass
    for wbits in (16 + zlib.MAX_WBITS, -zlib.MAX_WBITS):
        try:
            return decompress_with_limit(data, wbits), True
        except ValueError:
            raise
        except Exception:
            continue
    return data, False

def hexdump_bytes(b: bytes, max_len: int = 32) -> str:
    n = min(len(b), max_len)
    return " ".join(f"{x:02X}" for x in b[:n])

def half_to_float(h: int) -> float:
    return float(np.frombuffer(struct.pack('<H', h), dtype=np.float16)[0])

def matrix_from_16_floats_row_major_values(values) -> Matrix:

    return Matrix((
        (values[0], values[4], values[8],  values[12]),
        (values[1], values[5], values[9],  values[13]),
        (values[2], values[6], values[10], values[14]),
        (values[3], values[7], values[11], values[15]),
    ))

def detect_world_game_from_sector_row_count(row_count: int, fallback: str = "vcs") -> str:

    if int(row_count) == 47:
        return "lcs"
    if int(row_count) == 37:
        return "vcs"
    return str(fallback or "vcs").lower()

def sector_origin_for_xy(game_hint: str, sector_x: int, sector_y: int) -> Tuple[float, float, float]:
    game = str(game_hint or "vcs").lower()
    if game == "lcs":
        xinc = 100.0
        yinc = 86.6
        xstart = -2000.0
        ystart = -2000.0
    else:
        xinc = 125.0
        yinc = 108.25
        xstart = -2400.0
        ystart = -2000.0
    x = xstart + (xinc * 0.5) + (xinc * int(sector_x)) - ((int(sector_y) & 1) * xinc * 0.5)
    y = ystart + (yinc * 0.5) + (yinc * int(sector_y))
    return (float(x), float(y), 0.0)

def matrix_from_16_floats_row_major_values_with_origin(values, origin) -> Matrix:
    matrix = matrix_from_16_floats_row_major_values(values)
    if origin is not None:
        ox, oy, oz = origin
        matrix[0][3] += float(ox)
        matrix[1][3] += float(oy)
        matrix[2][3] += float(oz)
    return matrix

def is_ver2_img_archive(img_bytes: bytes) -> bool:
    return len(img_bytes) >= 8 and img_bytes[:4] == b"VER2"

def parse_ver2_img_directory(img_bytes: bytes) -> List[Dict[str, object]]:
    if not is_ver2_img_archive(img_bytes):
        return []
    count = read_u32(img_bytes, 4)
    dir_end = 8 + count * 32
    if count <= 0 or dir_end > len(img_bytes):
        return []
    entries = []
    for index in range(count):
        off = 8 + index * 32
        sector = read_u32(img_bytes, off)
        sectors = read_u32(img_bytes, off + 4)
        raw_name = img_bytes[off + 8:off + 32].split(b"\0", 1)[0]
        try:
            name = raw_name.decode("ascii", "replace")
        except Exception:
            name = ""
        start = sector * 2048
        end = start + sectors * 2048
        if start < len(img_bytes):
            end = min(end, len(img_bytes))
            entries.append({
                "index": index,
                "sector": sector,
                "sectors": sectors,
                "start": start,
                "end": end,
                "name": name,
            })
    entries.sort(key=lambda item: (int(item["start"]), int(item["end"])))
    return entries

def find_ver2_entry_for_abs_offset(entries: List[Dict[str, object]], abs_off: int) -> Optional[Dict[str, object]]:
    for entry in entries:
        if int(entry["start"]) <= abs_off < int(entry["end"]):
            return entry
    return None

def looks_like_img_instance_row(img_bytes: bytes, off: int, max_resource_id: Optional[int] = None) -> bool:
    if off < 0 or off + 0x50 > len(img_bytes):
        return False
    res_id = read_u16(img_bytes, off + 0x02)
    if res_id == 0 or res_id == 0xFFFF:
        return False
    if max_resource_id is not None and res_id >= int(max_resource_id):
        return False
    try:
        bounds = [half_to_float(read_u16(img_bytes, off + 0x04 + i * 2)) for i in range(4)]
        matrix = struct.unpack_from("<16f", img_bytes, off + 0x10)
    except Exception:
        return False
    if not all(math.isfinite(float(v)) for v in bounds):
        return False
    if not all(math.isfinite(float(v)) for v in matrix):
        return False
    if any(abs(float(v)) > 100000.0 for v in matrix):
        return False
    row_scale0 = math.sqrt(matrix[0] * matrix[0] + matrix[1] * matrix[1] + matrix[2] * matrix[2])
    row_scale1 = math.sqrt(matrix[4] * matrix[4] + matrix[5] * matrix[5] + matrix[6] * matrix[6])
    row_scale2 = math.sqrt(matrix[8] * matrix[8] + matrix[9] * matrix[9] + matrix[10] * matrix[10])
    scales = (row_scale0, row_scale1, row_scale2)
    if not all(math.isfinite(float(v)) for v in scales):
        return False
    if any(v > 4096.0 for v in scales):
        return False
    if any(v <= 0.000001 for v in scales):
        return False
    if abs(float(matrix[15]) - 1.0) > 0.001:
        return False
    return True

def ps2SwizzleAddressGrid(width: int, height: int) -> np.ndarray:
    logw = read_lvz.log2Pow2(width)
    x = np.arange(width, dtype=np.int32)[None, :]
    y = np.arange(height, dtype=np.int32)[:, None]
    distorted_x = x ^ ((((y >> 1) & 1) ^ ((y >> 2) & 1)) << 2)
    nx = (distorted_x & 7) | ((distorted_x >> 1) & ~7)
    ny = (y & 1) | ((y >> 1) & ~1)
    n = ((y >> 1) & 1) | (((x >> 3) & 1) << 1)
    return (n | (nx << 2) | (ny << (logw + 1))).reshape(-1)

@dataclass
class LVZMaster:
    magic: bytes
    type: int
    g0: int
    g1: int
    g1_dup: int
    count_like: int
    res_table_addr: int

@dataclass
class SlaveGroup:
    index: int
    addr: int
    tag: str
    total: int
    gcnt: int
    cont: int
    note: str

@dataclass
class MDLMaterial:
    texture_id: int
    tri_strip_size: int
    backface_cull: bool
    u_scale: float
    v_scale: float
    flags2: int
    bbox6_i16: Tuple[int, int, int, int, int, int]
    row_format: str = ""
    packet_raw: int = 0

@dataclass
class MDLMaterialList:
    count: int
    size_bytes: int
    materials: List[MDLMaterial]
    bytes_read: int
    aa_tail: bytes
    next_off: int
    format_tag: str = "ps2_unknown"
    row_len: int = 0

@dataclass
class TriStrip:
    count: int
    verts: List[Tuple[float, float, float]]
    uvs: List[Tuple[float, float]]
    cols_raw_u16: List[int]
    cols_rgba4444: List[Tuple[int, int, int, int]]
    material_res_index: int = -1
    u_scale: float = 1.0
    v_scale: float = 1.0

@dataclass
class MDLStripGroup:
    strips: List[TriStrip]
    bytes_read: int
    start_off: int
    end_off: int

def nativeWorldUvModes(format_flags: int) -> Tuple[int, int]:

    flags = int(format_flags)
    return (flags >> 8) & 3, (flags >> 10) & 3

def configureNativeWorldUvAnimation(material, format_flags: int, game_hint: str,
                                    frame_start: int = 1, v_flipped: bool = False) -> bool:

    if str(game_hint).lower() != "vcs" or int(format_flags) & 0xF000 != 0xC000:
        return False
    u_mode, v_mode = nativeWorldUvModes(format_flags)
    material["bleeds_uv_source"] = "VCS_PS2_WORLD"
    material["bleeds_uv_mode_u"] = u_mode
    material["bleeds_uv_mode_v"] = v_mode
    material["bleeds_uv_brightness_effect"] = 3 in (u_mode, v_mode)
    if 3 in (u_mode, v_mode) or (u_mode, v_mode) == (0, 0):
        return False
    tree = getattr(material, "node_tree", None)
    if tree is None:
        return False
    texture_nodes = [node for node in tree.nodes if node.type == 'TEX_IMAGE']
    if not texture_nodes:
        return False


    material["bleeds_uv_phase_step"] = 0.05
    material["bleeds_uv_frame_start"] = int(frame_start)

    for name in ("Leeds World UV", "Leeds UV Offset", "Leeds Animated UV"):
        previous = tree.nodes.get(name)
        if previous is not None:
            if previous.type == 'COMBXYZ':
                for socket in previous.inputs:
                    socket.driver_remove("default_value")
            tree.nodes.remove(previous)
    coordinates = tree.nodes.new("ShaderNodeTexCoord")
    coordinates.name = "Leeds World UV"
    coordinates.location = (-900, 0)
    offset = tree.nodes.new("ShaderNodeCombineXYZ")
    offset.name = "Leeds UV Offset"
    offset.label = "Native scrolling"
    offset.location = (-900, -200)
    addition = tree.nodes.new("ShaderNodeVectorMath")
    addition.operation = 'ADD'
    addition.name = "Leeds Animated UV"
    addition.location = (-600, 0)
    tree.links.new(coordinates.outputs['UV'], addition.inputs[0])
    tree.links.new(offset.outputs['Vector'], addition.inputs[1])
    advance = f"((frame-({int(frame_start)}))*0.05)"
    phase = f"({advance}-floor({advance}))"
    for axis, mode in enumerate((u_mode, v_mode)):
        if mode == 0:
            continue
        expression = phase
        if mode == 2:


            expression = f"(0.0 if {phase}==0.25 else floor(2.0*{phase}+0.5)*0.25)"
        if axis == 1 and v_flipped:
            expression = f"-({expression})"
        curve = offset.inputs[axis].driver_add("default_value")
        curve.driver.type = 'SCRIPTED'
        curve.driver.expression = expression
    for texture_node in texture_nodes:
        texture_node.extension = 'REPEAT'
        tree.links.new(addition.outputs['Vector'], texture_node.inputs['Vector'])
    return True

class read_lvz:
    UNPACK = 0x6C018000
    STMASK = 0x20000000
    STROW  = 0x30000000
    MSCAL  = 0x14000006

    def __init__(self, decomp_bytes: bytes, stem: str, use_swizzle: bool, debug_print: bool):
        self.decomp = decomp_bytes
        self.stem = stem
        self.use_swizzle = use_swizzle
        self.debug_print = debug_print
        self.material_by_res_index: Dict[int, bpy.types.Material] = {}
        self.master_resource_count: int = 0
        self.master_resource_stride: int = 0
        self.master_group_table_end: int = 0
        self.master_first_group_addr: int = 0
        self.master_game_hint: str = "unknown"

    def parse_master_header(self) -> LVZMaster:
        lvz = self.decomp
        if len(lvz) < 0x24:
            raise ValueError("LVZ smaller than 0x24")
        magic = lvz[0:4]
        _type = read_u32(lvz, 0x04)
        g0 = read_u32(lvz, 0x08)
        g1 = read_u32(lvz, 0x0C)
        g1d = read_u32(lvz, 0x10)
        cnt = read_u32(lvz, 0x14)
        rtab = read_u32(lvz, 0x20)
        return LVZMaster(magic, _type, g0, g1, g1d, cnt, rtab)

    def peekGlobal32(self, addr: int):
        lvz = self.decomp
        n = len(lvz)
        if addr < 0 or addr + 32 > n:
            return ("(oob)", {}, "out-of-bounds")
        blk = lvz[addr:addr+32]
        tag = blk[0:4]
        info = {}
        note = ""
        try:
            tag_str = tag.decode("ascii", errors="replace")
        except Exception:
            tag_str = tag.hex()
        if tag == b"DLRW":
            wrld_type = read_u32(blk, 0x04)
            total = read_u32(blk, 0x08)
            g0 = read_u32(blk, 0x0C)
            g1 = read_u32(blk, 0x10)
            gcnt = read_u32(blk, 0x14)
            cont = read_u32(blk, 0x18)
            info = {"wrld_type": wrld_type, "total": total, "g0": g0, "g1": g1, "gcnt": gcnt, "cont": cont}
            note = "WRLD 32B preface"
        elif tag == b"xet\x00":
            _hdrsz = read_u32(blk, 0x04)
            total = read_u32(blk, 0x08)
            g0 = read_u32(blk, 0x0C)
            g1 = read_u32(blk, 0x10)
            gcnt = read_u32(blk, 0x14)
            cont = read_u32(blk, 0x18)
            info = {"total": total, "g0": g0, "g1": g1, "gcnt": gcnt, "cont": cont, "hdrsz": _hdrsz}
            note = "TEX 32B preface"
        else:
            note = "Unknown 32B header"
            info = {"first16_hex": hexdump_bytes(blk[:16], 16)}
        return (tag_str, info, note)

    def score_resource_entry_stride(self, base: int, res_count: int, stride: int, table_limit: int) -> int:
        lvz = self.decomp
        n = len(lvz)
        if stride not in (8, 12):
            return -1000000
        if base <= 0 or base >= n or res_count <= 0:
            return -1000000
        if base + res_count * stride > min(n, table_limit):
            return -1000000

        sample_count = min(res_count, 1024)
        score = 0
        nonempty = 0
        supported = 0
        invalid = 0
        id_like = 0
        dma_zero = 0

        for i in range(sample_count):
            off = base + i * stride
            raw_ptr = read_u32(lvz, off + 0)
            dma_ptr = read_u32(lvz, off + 4)
            res_id_field = read_u32(lvz, off + 8) if stride == 12 else None

            if stride == 12:
                if res_id_field == 0xFFFFFFFF:
                    id_like += 2
                elif 0 <= int(res_id_field) <= max(res_count + 4096, 0xFFFF):
                    id_like += 1
                else:
                    id_like -= 4

            if dma_ptr == 0 or (LVZ_MIN_RESOURCE_CANDIDATE_ADDR <= dma_ptr < n and (dma_ptr & 3) == 0):
                dma_zero += 1
            else:
                score -= 1

            if raw_ptr in (0, 0xFFFFFFFF):
                score += 1
                continue
            nonempty += 1

            if not (LVZ_MIN_RESOURCE_CANDIDATE_ADDR <= raw_ptr < n and (raw_ptr & 3) == 0):
                invalid += 1
                score -= 8
                continue

            score += 2
            kind_score, kind, _info = self.classify_resource_candidate(raw_ptr)
            if kind_score >= 0 and kind not in ("EMPTY", "INVALID"):
                supported += 1
                score += 4
            elif kind == "INVALID":
                score -= 1

        if stride == 12:
            score += id_like
            if id_like > sample_count:
                score += sample_count * 3
        else:
            score += dma_zero // 4

        if nonempty > 0:
            score += min(supported, 512)
            score -= invalid * 2
        return score

    def detect_master_resource_stride(self, base: int, res_count: int, first_group_addr: int) -> int:
        lvz = self.decomp
        n = len(lvz)
        if base <= 0 or base >= n or res_count <= 0:
            return 8
        table_limit = n
        if first_group_addr > base:
            table_limit = min(table_limit, int(first_group_addr))
        space = max(0, table_limit - base)

        candidates: List[Tuple[int, int]] = []
        for stride in (12, 8):
            if space >= res_count * stride:
                candidates.append((self.score_resource_entry_stride(base, res_count, stride, table_limit), stride))
        if not candidates:
            if space >= res_count * 8:
                return 8
            if space >= res_count * 12:
                return 12
            return 8
        candidates.sort(reverse=True)
        return int(candidates[0][1])

    def parse_slave_groups_and_rescount(self):
        lvz = self.decomp
        n = len(lvz)
        master = self.parse_master_header()

        groups: List[SlaveGroup] = []
        cursor = 0x24
        idx = 0

        if master.magic == b"DLRW":
            while cursor + 8 <= n:
                addr = read_u32(lvz, cursor + 0)
                group_type = read_u32(lvz, cursor + 4)
                if not (0 < addr < n and (addr & 0x3) == 0 and addr + 0x20 <= n):
                    break
                tag = lvz[addr:addr + 4]
                if tag not in (b"DLRW", b"xet\0"):
                    break
                tag_str, info, note = self.peekGlobal32(addr)
                total = int(info.get("total", 0))
                gcnt = int(info.get("gcnt", 0))
                cont = int(info.get("cont", 0))
                groups.append(SlaveGroup(
                    idx,
                    addr,
                    str(tag_str),
                    total,
                    gcnt,
                    cont,
                    f"{note}; group_type=0x{group_type:08X}"
                ))
                idx += 1
                cursor += 8

            res_count = 0
            if groups and cursor + 4 <= n:
                res_count = read_u32(lvz, cursor)
                cursor += 4
            if res_count <= 0 or res_count > LVZ_MAX_RESOURCE_ROWS:
                res_count = int(master.count_like)

            first_group_addr = min((int(g.addr) for g in groups), default=0)
            stride = self.detect_master_resource_stride(int(master.res_table_addr), int(res_count), int(first_group_addr))
            self.master_resource_count = int(res_count)
            self.master_resource_stride = int(stride)
            self.master_group_table_end = int(cursor)
            self.master_first_group_addr = int(first_group_addr)
            self.master_game_hint = "vcs" if stride == 12 else "lcs"

            if res_count > LVZ_MAX_RESOURCE_ROWS:
                dbg(f"[lvz] WARNING: master resource count {res_count} exceeds parser limit; clamping to {LVZ_MAX_RESOURCE_ROWS}")
                res_count = LVZ_MAX_RESOURCE_ROWS
                self.master_resource_count = int(res_count)

            dbg(
                f"[lvz] master Resource[]: count={res_count} stride={stride} "
                f"game_hint={self.master_game_hint} table=0x{int(master.res_table_addr):08X} "
                f"groups_end=0x{self.master_group_table_end:08X} first_group=0x{first_group_addr:08X}"
            )
            return (groups, res_count, cursor)

        while cursor + 8 <= n:
            addr = read_u32(lvz, cursor + 0)
            resv = read_u32(lvz, cursor + 4)
            plaus = (0 < addr < n and (addr & 0x3) == 0)
            plaus = plaus and (resv == 0 or (resv & 0xFFFF) == 0)
            if not plaus:
                break
            tag, info, note = self.peekGlobal32(addr)
            total = int(info.get("total", 0))
            gcnt  = int(info.get("gcnt", 0))
            cont  = int(info.get("cont", 0))
            groups.append(SlaveGroup(idx, addr, str(tag), total, gcnt, cont, note))
            idx += 1
            cursor += 8

        res_count = int(master.count_like)
        if res_count <= 0 and cursor + 4 <= n:
            res_count_u32 = read_u32(lvz, cursor)
            res_count = res_count_u32 & 0xFFFF
            cursor += 4
        if res_count > LVZ_MAX_RESOURCE_ROWS:
            dbg(f"[lvz] WARNING: resource count {res_count} exceeds parser limit; clamping to {LVZ_MAX_RESOURCE_ROWS}")
            res_count = LVZ_MAX_RESOURCE_ROWS
        self.master_resource_count = int(res_count)
        self.master_resource_stride = 8
        self.master_group_table_end = int(cursor)
        self.master_first_group_addr = min((int(g.addr) for g in groups), default=0)
        self.master_game_hint = "unknown"
        return (groups, res_count, cursor)

    def material_list_stream_has_unpack(self, addr: int, list_end: int, max_end: Optional[int] = None) -> bool:
        lvz = self.decomp
        n = len(lvz) if max_end is None else min(len(lvz), max(0, int(max_end)))
        if list_end < addr or list_end > n:
            return False
        stream_start = list_end
        while stream_start < n and lvz[stream_start] == 0xAA and stream_start - addr < 0x1000:
            stream_start += 1
        stream_start = align_up4(stream_start)
        unpack_bytes = struct.pack("<I", self.UNPACK)
        return lvz.find(unpack_bytes, max(addr, stream_start - 0x10), min(n, stream_start + 0x100)) >= 0

    def expected_ps2_material_size16(self, count: int, row_len: int) -> int:
        try:
            total = (4 + (int(count) * int(row_len)) + 15) & ~15
            return int(total - 4)
        except Exception:
            return -1

    def logMdlDescriptorAlignment(self, requested_off: int, found_off: int):
        if int(requested_off) == int(found_off):
            return
        try:
            count = int(getattr(self, "_mdl_descriptor_align_log_count", 0))
        except Exception:
            count = 0
        if count < 96:
            try:
                dbg(
                    f"[descriptor-align] MDL descriptor pointer adjusted "
                    f"0x{int(requested_off):08X}->0x{int(found_off):08X} "
                    f"delta={int(found_off) - int(requested_off):+d}"
                )
            except Exception:
                pass
        elif count == 96:
            try:
                dbg("[descriptor-align] further MDL descriptor pointer adjustment logs suppressed")
            except Exception:
                pass
        try:
            setattr(self, "_mdl_descriptor_align_log_count", count + 1)
        except Exception:
            pass

    def find_mdl_material_list_start_near(self, addr: int, max_end: Optional[int] = None) -> Optional[int]:
        lvz = self.decomp
        n = len(lvz) if max_end is None else min(len(lvz), max(0, int(max_end)))
        try:
            addr = int(addr)
        except Exception:
            return None
        if addr < LVZ_MIN_RESOURCE_CANDIDATE_ADDR or addr + 8 > n:
            return None


        preferred_deltas = (
            0,
            4, 8, 12, 16, 20, 24, 28, 32,
            36, 40, 44, 48, 52, 56, 60, 64,
            0x4C, 0x50, 0x54, 0x58, 0x5C, 0x60,
            0x70, 0x80, 0x90, 0xA0, 0xB0, 0xC0,
        )
        seen = set()
        for delta in preferred_deltas:
            candidate = addr + int(delta)
            if candidate in seen:
                continue
            seen.add(candidate)
            if candidate < LVZ_MIN_RESOURCE_CANDIDATE_ADDR or candidate + 8 > n or (candidate & 3) != 0:
                continue
            if self.detect_mdl_material_list_format(candidate, max_end=n) is not None:
                return int(candidate)
        return None

    def score_ps2_material_row_format(self, addr: int, count: int, size_bytes: int, row_len: int) -> int:
        lvz = self.decomp
        score = 0
        material_count_to_test = min(max(0, count), 8)
        off = addr + 4
        for _ in range(material_count_to_test):
            if off + row_len > len(lvz):
                return -100000
            try:
                if row_len == 24:
                    packet_raw = read_u32(lvz, off + 0)
                    packet_size = packet_raw >> 1
                    tex_id = read_u16(lvz, off + 4)
                    u_scale = half_to_float(read_u16(lvz, off + 6))
                    v_scale = half_to_float(read_u16(lvz, off + 8))
                    flags2 = read_u16(lvz, off + 10)
                    if packet_raw == 0 or packet_size > 0x40000:
                        score -= 10
                    else:
                        score += 12
                    if tex_id != 0xFFFF:
                        score += 2
                    if math.isfinite(u_scale) and math.isfinite(v_scale) and abs(u_scale) <= 256.0 and abs(v_scale) <= 256.0:
                        score += 10
                        if abs(u_scale) >= 0.00001 or abs(v_scale) >= 0.00001:
                            score += 4
                    else:
                        score -= 40
                    if flags2 in (0x0000, 0x0040, 0x3C00, 0x4000) or (flags2 & 0xC000) in (0, 0x4000):
                        score += 1
                else:
                    tex_id = read_u16(lvz, off + 0)
                    packet_raw = read_u16(lvz, off + 2)
                    packet_size = packet_raw & 0x7FFF
                    u_scale = half_to_float(read_u16(lvz, off + 4))
                    v_scale = half_to_float(read_u16(lvz, off + 6))
                    flags2 = read_u16(lvz, off + 8)
                    if packet_size > 0 and packet_size <= 0x8000:
                        score += 8
                    else:
                        score -= 6
                    if tex_id != 0xFFFF:
                        score += 2
                    if math.isfinite(u_scale) and math.isfinite(v_scale) and abs(u_scale) <= 256.0 and abs(v_scale) <= 256.0:
                        score += 6
                        if abs(u_scale) >= 0.00001 or abs(v_scale) >= 0.00001:
                            score += 2
                    else:
                        score -= 30
                    if flags2 in (0x0000, 0x0040, 0x3C00, 0x4000) or (flags2 & 0xC000) in (0, 0x4000):
                        score += 1
            except Exception:
                return -100000
            off += row_len
        return score

    def detect_mdl_material_list_format(self, addr: int, max_end: Optional[int] = None) -> Optional[Dict[str, object]]:
        lvz = self.decomp
        n = len(lvz) if max_end is None else min(len(lvz), max(0, int(max_end)))
        if addr < LVZ_MIN_RESOURCE_CANDIDATE_ADDR or addr + 8 > n or (addr & 0x3) != 0:
            return None
        if lvz[addr:addr + 4] in (b"DLRW", b"xet\0"):
            return None

        candidates: List[Dict[str, object]] = []

        count16 = read_u16(lvz, addr + 0)
        size16 = read_u16(lvz, addr + 2)
        if 0 < count16 <= 512 and 0 <= size16 <= 0x8000 and addr + 4 + size16 <= n:
            for tag, row_len, base_score in (("ps2_vcs", 24, 30), ("ps2_lcs", 22, 10)):
                expected_size = self.expected_ps2_material_size16(count16, row_len)
                if size16 != expected_size:
                    continue
                list_end = addr + 4 + size16
                if not self.material_list_stream_has_unpack(addr, list_end, max_end=n):
                    continue
                score = base_score + self.score_ps2_material_row_format(addr, count16, size16, row_len)
                if score < 20:
                    continue
                candidates.append({
                    "format_tag": tag,
                    "count": int(count16),
                    "size_bytes": int(size16),
                    "row_len": int(row_len),
                    "header_len": 4,
                    "list_end": int(list_end),
                    "score": int(score),
                })

        count32 = read_u32(lvz, addr + 0)
        unk_float = 0.0
        try:
            unk_float = struct.unpack_from("<f", lvz, addr + 4)[0]
        except Exception:
            unk_float = 0.0
        if 0 < count32 <= 1024 and math.isfinite(float(unk_float)):
            for tag, row_len, base_score in (("psp_wrld_24", 24, 20), ("psp_wrld_10", 10, 12)):
                list_end = addr + 8 + (int(count32) * row_len)
                if list_end > n:
                    continue
                material_score = 0
                total_vertices = 0
                ok = True
                test_count = min(int(count32), 16)
                for mi in range(test_count):
                    roff = addr + 8 + mi * row_len
                    tex_id = read_u16(lvz, roff + 0)
                    count_raw = read_u16(lvz, roff + 2)
                    vertex_count = count_raw & 0x7FFF
                    u_scale = half_to_float(read_u16(lvz, roff + 4)) if row_len >= 8 else 1.0
                    v_scale = half_to_float(read_u16(lvz, roff + 6)) if row_len >= 8 else 1.0
                    if vertex_count <= 0 or vertex_count > 8192:
                        ok = False
                        break
                    if not (math.isfinite(u_scale) and math.isfinite(v_scale) and abs(u_scale) <= 256.0 and abs(v_scale) <= 256.0):
                        ok = False
                        break
                    if tex_id != 0xFFFF:
                        material_score += 2
                    total_vertices += vertex_count
                if not ok:
                    continue
                full_vertex_total = 0
                for mi in range(min(int(count32), 1024)):
                    roff = addr + 8 + mi * row_len
                    full_vertex_total += read_u16(lvz, roff + 2) & 0x7FFF
                    if full_vertex_total > LVZ_MAX_MDL_VERTICES_PER_OBJECT:
                        break
                geo_start = align_up4(list_end)
                while geo_start < n and lvz[geo_start] == 0xAA and geo_start - addr < 0x1000:
                    geo_start += 1
                geo_start = align_up4(geo_start)
                if full_vertex_total <= 0 or geo_start + (full_vertex_total * 10) > n:
                    continue
                candidates.append({
                    "format_tag": tag,
                    "count": int(count32),
                    "size_bytes": int(count32) * row_len,
                    "row_len": int(row_len),
                    "header_len": 8,
                    "list_end": int(list_end),
                    "score": int(base_score + material_score + (8 if row_len == 24 and abs(float(unk_float)) > 0.0 else 0)),
                })

        if not candidates:
            return None
        candidates.sort(key=lambda item: int(item.get("score", 0)), reverse=True)
        return candidates[0]

    def looks_like_mdl_material_list_candidate(self, addr: int) -> bool:
        return self.find_mdl_material_list_start_near(addr) is not None

    def looks_like_direct_texture_candidate(self, addr: int) -> bool:
        lvz = self.decomp
        n = len(lvz)
        if addr < LVZ_MIN_RESOURCE_CANDIDATE_ADDR or addr + (LVZ_DIRECT_TEXTURE_HEADER_BYTES + LVZ_DIRECT_TEXTURE_PALETTE_BYTES) > n or (addr & 0x3) != 0:
            return False
        if read_u32(lvz, addr + 0) != 0xCCCCCCCC:
            return False

        width_half = read_u16(lvz, addr + 4)
        format_flags = read_u16(lvz, addr + 6)
        data_pointer = read_u32(lvz, addr + 8)
        raster_flags = read_u32(lvz, addr + 12)

        if width_half not in (4, 8, 16, 32, 64, 128, 256, 512):
            return False

        low_flag = format_flags & 0x00FF


        high_flag = format_flags & 0xF000
        if low_flag not in (0x25, 0x45) or high_flag != 0xC000:
            return False
        if data_pointer not in (addr + LVZ_DIRECT_TEXTURE_HEADER_BYTES, 0):
            if not (addr < data_pointer < n and (data_pointer & 0x3) == 0):
                return False
        logw = raster_flags & 0x3F
        logh = (raster_flags >> 6) & 0x3F
        depth = (raster_flags >> 12) & 0x3F
        mipmaps = (raster_flags >> 20) & 0x0F
        if logw > 12 or logh > 12 or depth not in (4, 8, 32) or mipmaps > 8:
            return False
        if depth == 4 and width_half and (1 << logw) not in (int(width_half), int(width_half) * 2):
            return False
        return True

    def looks_like_texture_ref_candidate(self, addr: int) -> bool:
        lvz = self.decomp
        n = len(lvz)
        if addr < LVZ_MIN_RESOURCE_CANDIDATE_ADDR or addr + 8 > n or (addr & 0x3) != 0:
            return False
        ref_addr = read_u32(lvz, addr + 0)
        if ref_addr < LVZ_MIN_RESOURCE_CANDIDATE_ADDR or ref_addr >= n or (ref_addr & 0x3) != 0:
            return False

        if lvz[ref_addr:ref_addr + 4] in (b"DLRW", b"xet\0"):
            return False
        return True

    def classify_resource_candidate(self, addr: int) -> Tuple[int, str, Dict]:
        lvz = self.decomp
        n = len(lvz)
        if addr in (0, 0xFFFFFFFF):
            return (0, "EMPTY", {"reason": "continues_in_img"})
        if addr < LVZ_MIN_RESOURCE_CANDIDATE_ADDR or addr + 8 > n or (addr & 0x3) != 0:
            return (-100, "INVALID", {"why": "candidate_out_of_range_or_unaligned"})
        if lvz[addr:addr + 4] in (b"DLRW", b"xet\0"):
            return (-50, "INVALID", {"why": "candidate_points_to_preface"})

        a16 = read_u16(lvz, addr + 0)
        b16 = read_u16(lvz, addr + 2)
        a32 = read_u32(lvz, addr + 0)
        b32 = read_u32(lvz, addr + 4)
        info = {"u16_pair": (a16, b16), "u32_pair": (a32, b32)}

        if self.looks_like_direct_texture_candidate(addr):
            info["direct_texture"] = True
            info["width_half"] = read_u16(lvz, addr + 4)
            info["texture_flags"] = read_u16(lvz, addr + 6)
            info["data_addr"] = read_u32(lvz, addr + 8)
            info["texture_meta"] = read_u32(lvz, addr + 12)
            info["raster_flags"] = read_u32(lvz, addr + 12)
            return (90, "TEX", info)


        if self.looks_like_mdl_material_list_candidate(addr):
            return (100, "MDL", info)
        if self.looks_like_texture_ref_candidate(addr):
            info["ref_addr"] = a32
            info["embedded_res_id"] = b32
            return (80, "TEX_REF", info)
        if a16 == 0:
            info["unk_fac0"] = b16
            return (10, "UNK_FAC0", info)
        return (-10, "INVALID", {**info, "why": "not_a_supported_lvz_resource"})

    def choose_resource_table_pointer(self, dword0: int, dword1: int) -> Tuple[int, str, Dict, int]:
        candidates = []
        for slot, addr in ((0, dword0), (1, dword1)):
            score, kind, info = self.classify_resource_candidate(addr)
            candidates.append((score, slot, addr, kind, info))
        candidates.sort(key=lambda item: (item[0], -item[1]), reverse=True)
        score, slot, addr, kind, info = candidates[0]
        if score >= 0:
            return addr, kind, info, slot
        if dword0 in (0, 0xFFFFFFFF) and dword1 in (0, 0xFFFFFFFF):
            return 0, "EMPTY", {"reason": "continues_in_img", "u16_pair": (None, None), "u32_pair": (None, None)}, -1
        return addr, kind, info, slot

    def walk_master_resource_table(self, res_table_addr: int, res_count: int) -> List[Dict]:
        lvz = self.decomp
        rows: List[Dict] = []
        n = len(lvz)
        base = int(res_table_addr)
        if base <= 0 or base >= n:
            dbg(f"[lvz] WARNING: resource table address 0x{base:08X} is outside LVZ bounds.")
            return rows

        stride = int(self.master_resource_stride or 0)
        if stride not in (8, 12):
            stride = self.detect_master_resource_stride(base, int(res_count), int(self.master_first_group_addr or 0))
            self.master_resource_stride = stride
            self.master_game_hint = "vcs" if stride == 12 else "lcs"

        table_limit = n
        if self.master_first_group_addr and self.master_first_group_addr > base:
            table_limit = min(table_limit, int(self.master_first_group_addr))

        if base + (int(res_count) * stride) > table_limit:
            max_rows = max(0, (table_limit - base) // stride)
            if res_count > max_rows:
                dbg(f"[lvz] WARNING: res_count={res_count} exceeds Resource[] table bounds for stride={stride}; clamping to {max_rows}")
                res_count = max_rows
        if res_count > LVZ_MAX_RESOURCE_ROWS:
            dbg(f"[lvz] WARNING: res_count={res_count} exceeds parser limit; clamping to {LVZ_MAX_RESOURCE_ROWS}")
            res_count = LVZ_MAX_RESOURCE_ROWS

        dbg(f"[lvz] walking Resource[] rows: table=0x{base:08X} count={res_count} stride={stride} game_hint={self.master_game_hint}")

        off = base
        for i in range(int(res_count)):
            raw_ptr = read_u32(lvz, off + 0)
            dma_ptr = read_u32(lvz, off + 4) if off + 8 <= n else 0
            resource_id_field = read_u32(lvz, off + 8) if stride == 12 and off + 12 <= n else None

            score, kind, info = self.classify_resource_candidate(raw_ptr)
            if raw_ptr in (0, 0xFFFFFFFF):
                kind = "EMPTY"
                info = {"reason": "continues_in_img", "u16_pair": (None, None), "u32_pair": (0, 0)}
            elif score < 0 and not (LVZ_MIN_RESOURCE_CANDIDATE_ADDR <= raw_ptr < n and (raw_ptr & 3) == 0):
                kind = "INVALID"

            a16, b16 = info.get("u16_pair", (None, None))
            a32, b32 = info.get("u32_pair", (None, None))
            row: Dict = {
                "index": i,
                "table_off": off,
                "resource_stride": stride,
                "raw_dword0": raw_ptr,
                "raw_dword1": dma_ptr,
                "raw_dword2": resource_id_field,
                "pointer_slot": 0,
                "res_addr": raw_ptr,
                "reserved": dma_ptr,
                "dma_ptr": dma_ptr,
                "resource_id_field": resource_id_field,
                "kind": kind,
                "peek_u16": (a16, b16),
                "peek_u32": (a32, b32),
            }
            if kind == "UNK_FAC0":
                row["unk_fac0"] = info.get("unk_fac0")
            if kind == "EMPTY":
                row["empty_reason"] = info.get("reason", "unknown")
            if kind == "INVALID":
                row["invalid_reason"] = info.get("why", "unknown")
            if kind == "TEX":
                row["res_id"] = i
                row["direct_texture"] = True
                row["width_half"] = info.get("width_half")
                row["texture_flags"] = info.get("texture_flags")
                row["data_addr"] = info.get("data_addr")
                row["texture_meta"] = info.get("texture_meta")
                row["raster_flags"] = info.get("raster_flags")
            if kind == "TEX_REF":
                row["ref_addr"] = info.get("ref_addr")
                row["res_id"] = i
                row["embedded_res_id"] = info.get("embedded_res_id")
            rows.append(row)
            off += stride

        valid_resource_addrs = sorted(set(
            int(row["res_addr"]) for row in rows
            if isinstance(row.get("res_addr"), int)
            and LVZ_MIN_RESOURCE_CANDIDATE_ADDR <= int(row["res_addr"]) < n
            and (int(row["res_addr"]) & 3) == 0
            and self.decomp[int(row["res_addr"]):int(row["res_addr"]) + 4] not in (b"DLRW", b"xet\0")
        ))
        for row in rows:
            addr = int(row.get("res_addr", 0) or 0)
            end = n
            next_index = bisect_right(valid_resource_addrs, addr)
            if next_index < len(valid_resource_addrs):
                end = valid_resource_addrs[next_index]
            if base > addr:
                end = min(end, base)
            row["res_end"] = end
            if addr > 0 and end > addr:
                row["res_size_estimate"] = end - addr
            else:
                row["res_size_estimate"] = 0
        return rows

    @staticmethod
    def expand_nibbles_lo_first(b: bytes) -> np.ndarray:
        arr = np.frombuffer(b, dtype=np.uint8)
        lo = arr & 0x0F
        hi = arr >> 4
        return np.vstack([lo, hi]).T.reshape(-1)

    @staticmethod
    def log2Pow2(n: int) -> int:
        l = 0
        v = max(1, n)
        while (1 << l) < v:
            l += 1
        return l

    @staticmethod
    def swizzle_ps2_addr(x: int, y: int, logw: int) -> int:
        X3 = (x >> 3) & 1
        Y1 = (y >> 1) & 1
        Y2 = (y >> 2) & 1
        x ^= ((Y1 ^ Y2) << 2)
        nx = (x & 7) | ((x >> 1) & ~7)
        ny = (y & 1) | ((y >> 1) & ~1)
        n = (Y1) | (X3 << 1)
        return (n | (nx << 2) | (ny << (logw - 1 + 2)))

    @classmethod
    def unswizzle8_ps2_linearized(cls, src: np.ndarray, w: int, h: int) -> np.ndarray:
        source = np.asarray(src, dtype=np.uint8).reshape(-1)
        if not source.size:
            raise ValueError('PS2 swizzled texture has no index data')
        addresses = ps2SwizzleAddressGrid(w, h)
        return source[addresses % source.size]

    @staticmethod
    def apply_ps2_alpha_scale(palette_rgba: np.ndarray, do_scale: bool) -> np.ndarray:
        if not do_scale:
            return palette_rgba
        pal = palette_rgba.copy()
        a = pal[:, 3].astype(np.uint16)
        a = (a * 255 + 64) // 128
        pal[:, 3] = np.clip(a, 0, 255).astype(np.uint8)
        return pal

    @staticmethod
    def image_from_rgba_uint8(rgba: np.ndarray, name: str, w: int, h: int) -> bpy.types.Image:
        img = bpy.data.images.new(name=name, width=w, height=h, alpha=True, float_buffer=False)
        flat = (rgba.astype(np.float32) / 255.0).reshape(-1, 4)
        img.pixels = flat.flatten().tolist()
        img.alpha_mode = 'STRAIGHT'
        img.pack()
        return img

    @staticmethod
    def create_material_from_image(img: bpy.types.Image, mat_name: str) -> bpy.types.Material:
        mat = bpy.data.materials.new(mat_name)
        mat.use_nodes = True
        nt = mat.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (300, 0)
        princ = nt.nodes.new("ShaderNodeBsdfPrincipled"); princ.location = (0, 0)
        tex = nt.nodes.new("ShaderNodeTexImage"); tex.location = (-300, 0); tex.image = img
        nt.links.new(tex.outputs["Color"], princ.inputs["Base Color"])
        if img.has_data and "Alpha" in tex.outputs and "Alpha" in princ.inputs:
            nt.links.new(tex.outputs["Alpha"], princ.inputs["Alpha"])
            mat.blend_method = 'BLEND'
        nt.links.new(princ.outputs["BSDF"], out.inputs["Surface"])
        return mat

    @staticmethod
    def split_index_and_palette_tail64(data: bytes) -> Tuple[bytes, List[Tuple[int,int,int,int]], int, int]:
        if len(data) < 64:
            raise ValueError("Input shorter than 64 bytes; cannot take tail-64 palette.")
        index = data[:-64]
        pal = data[-64:]
        palette = [tuple(pal[i:i+4]) for i in range(0, 64, 4)]
        return index, palette, len(data) - 64, 64

    @staticmethod
    def split_index_and_palette_explicit(data: bytes, pal_offset: int, pal_size: int) -> Tuple[bytes, List[Tuple[int,int,int,int]], int, int]:
        if pal_offset < 0 or pal_offset + pal_size > len(data):
            raise ValueError("Palette window out of range.")
        pal = data[pal_offset: pal_offset + pal_size]
        if pal_size % 4 != 0:
            raise ValueError("Palette size must be divisible by 4 (RGBA entries).")
        index = data[:pal_offset]
        palette = [tuple(pal[i:i+4]) for i in range(0, pal_size, 4)]
        return index, palette, pal_offset, pal_size

    @classmethod
    def palette_candidate_single(cls, data: bytes, mode: str, explicit_off: Optional[int], explicit_sz: Optional[int]):
        if mode == "explicit" and explicit_off is not None and explicit_sz is not None:
            i, p, off, sz = cls.split_index_and_palette_explicit(data, explicit_off, explicit_sz)
            return (i, p, off, sz, f"pal_explicit_{sz}")
        i, p, off, sz = cls.split_index_and_palette_tail64(data)
        return (i, p, off, sz, "pal_tail64")

    @staticmethod
    def nearest_pow2(n: int) -> int:
        if n <= 1:
            return 1
        if (n & (n - 1)) == 0:
            return n
        lower = 1 << (n.bit_length() - 1)
        upper = lower << 1
        return upper if (n - lower) > (upper - n) else lower

    @staticmethod
    def resize_indices_to_dims(idx2d: np.ndarray, new_w: int, new_h: int) -> np.ndarray:
        h, w = idx2d.shape
        if new_h < h:
            idx2d = idx2d[:new_h, :]
            h = new_h
        if new_w < w:
            idx2d = idx2d[:, :new_w]
            w = new_w
        if new_h > h:
            pad_h = new_h - h
            idx2d = np.pad(idx2d, ((0, pad_h), (0, 0)), mode='edge')
            h = new_h
        if new_w > w:
            pad_w = new_w - w
            idx2d = np.pad(idx2d, ((0, 0), (0, pad_w)), mode='edge')
        return idx2d

    @staticmethod
    def choose_single_size_for_4bpp(index_len_bytes: int, sizes_hint: Optional[str], prefer_square: bool = True) -> Tuple[int, int]:
        total_pixels = index_len_bytes * 2
        if total_pixels <= 0:
            raise ValueError("Index length is zero; cannot choose size.")
        if sizes_hint:
            hints = []
            for chunk in sizes_hint.split(","):
                chunk = chunk.strip().lower()
                if not chunk or "x" not in chunk:
                    continue
                w_str, h_str = chunk.split("x", 1)
                try:
                    w = int(w_str); h = int(h_str)
                    hints.append((w, h))
                except ValueError:
                    continue
            for (w, h) in hints:
                if w > 0 and h > 0 and (w * h) == total_pixels:
                    return (w, h)

        dim_pool = [16, 32, 64, 128, 256, 512, 1024]
        cands: List[Tuple[int, int]] = []
        for w in dim_pool:
            if total_pixels % w != 0:
                continue
            h = total_pixels // w
            if h in dim_pool:
                cands.append((w, h))
        if not cands:
            for w in dim_pool:
                if total_pixels % w == 0:
                    h = total_pixels // w
                    if h > 0:
                        cands.append((w, h))
        if not cands:
            raise ValueError(f"No dimension pair matches pixel count {total_pixels}. Provide an explicit size.")
        squares = [(w, h) for (w, h) in cands if w == h]
        if prefer_square and squares:
            squares.sort(key=lambda wh: abs(wh[0] - int(math.sqrt(total_pixels))))
            return squares[0]
        cands.sort(key=lambda wh: (abs(wh[0] - wh[1]), -wh[0]))
        return cands[0]

    def decode_blob_4bpp_lo_single(self,
                                   blob: bytes,
                                   out_stem: str,
                                   palette_mode: str,
                                   palette_offset: Optional[int],
                                   palette_size: Optional[int],
                                   use_swizzle: bool,
                                   sizes_hint: Optional[str],
                                   alpha_scale: str,
                                   name_override: Optional[str] = None,
                                   fixed_size: Optional[Tuple[int, int]] = None,
                                   round_to_power_of_two: bool = True) -> Dict:
        index, palette, pal_off, pal_sz, tag = self.palette_candidate_single(blob, palette_mode, palette_offset, palette_size)
        if self.debug_print:
            dbg(f"[palette] using {tag}  index_len={len(index)}  pal_sz={pal_sz}")
        if fixed_size is not None:
            w, h = int(fixed_size[0]), int(fixed_size[1])
            if w <= 0 or h <= 0 or (w * h) > len(index) * 2:
                raise ValueError(f"fixed texture size {w}x{h} does not fit index bytes {len(index)}")
        else:
            w, h = self.choose_single_size_for_4bpp(len(index), sizes_hint, prefer_square=True)
        if w > LVZ_MAX_TEXTURE_DIMENSION or h > LVZ_MAX_TEXTURE_DIMENSION or (w * h) > LVZ_MAX_TEXTURE_PIXELS:
            raise ValueError(
                f"refusing inferred texture size {w}x{h} from index_len={len(index)}; "
                "the TEX_REF span is probably not one texture blob"
            )
        if self.debug_print:
            dbg(f"[size] chosen (pre-round): {w}x{h} (pixels={w*h}, index_bytes={len(index)})")
        expanded = self.expand_nibbles_lo_first(index)
        need = w * h
        if len(expanded) < need:
            raise ValueError(f"Expanded indices smaller than required pixels ({len(expanded)} < {need}).")
        slab = expanded[:need]
        if use_swizzle:
            slab = self.unswizzle8_ps2_linearized(slab, w, h)
        idx2d = slab.reshape(h, w)
        if round_to_power_of_two:
            w2 = self.nearest_pow2(w)
            h2 = self.nearest_pow2(h)
            if (w2, h2) != (w, h):
                if w2 > LVZ_MAX_TEXTURE_DIMENSION or h2 > LVZ_MAX_TEXTURE_DIMENSION or (w2 * h2) > LVZ_MAX_TEXTURE_PIXELS:
                    raise ValueError(
                        f"refusing rounded texture size {w2}x{h2}; "
                        "the TEX_REF span is probably not one texture blob"
                    )
                if self.debug_print:
                    dbg(f"[pow2] rounding to nearest per-dimension: ({w}x{h}) → ({w2}x{h2})")
                idx2d = self.resize_indices_to_dims(idx2d, w2, h2)
                w, h = w2, h2
        idx2d = np.flipud(idx2d)
        pal_arr = np.asarray(palette, dtype=np.uint8)
        pal_arr = self.apply_ps2_alpha_scale(pal_arr, do_scale=(alpha_scale == "ps2"))
        rgba = pal_arr[np.clip(idx2d, 0, pal_arr.shape[0] - 1)]
        asset_name = name_override if name_override else out_stem
        img = self.image_from_rgba_uint8(rgba, asset_name, w, h)
        mat = self.create_material_from_image(img, asset_name)
        return {"material": mat, "size": (w, h), "palette_tag": tag}

    def decode_blob_8bpp_single(self,
                                blob: bytes,
                                out_stem: str,
                                use_swizzle: bool,
                                alpha_scale: str,
                                name_override: Optional[str] = None,
                                fixed_size: Optional[Tuple[int, int]] = None) -> Dict:
        if len(blob) < LVZ_DIRECT_TEXTURE_PALETTE_BYTES_8BPP:
            raise ValueError("8bpp direct texture blob is shorter than its 256-color palette")
        index = blob[:-LVZ_DIRECT_TEXTURE_PALETTE_BYTES_8BPP]
        pal = blob[-LVZ_DIRECT_TEXTURE_PALETTE_BYTES_8BPP:]
        palette = [tuple(pal[i:i+4]) for i in range(0, LVZ_DIRECT_TEXTURE_PALETTE_BYTES_8BPP, 4)]
        tag = "pal_tail1024"
        if self.debug_print:
            dbg(f"[palette] using {tag}  index_len={len(index)}  pal_sz={LVZ_DIRECT_TEXTURE_PALETTE_BYTES_8BPP}")

        if fixed_size is not None:
            w, h = int(fixed_size[0]), int(fixed_size[1])
            if w <= 0 or h <= 0 or (w * h) > len(index):
                raise ValueError(f"fixed 8bpp texture size {w}x{h} does not fit index bytes {len(index)}")
        else:
            # A byte is one pixel in an 8-bit indexed texture. The dimension
            # inference helper works in units of 4-bit index bytes.
            if len(index) % 2:
                raise ValueError("8bpp texture contains an odd number of index bytes; dimensions are ambiguous")
            w, h = self.choose_single_size_for_4bpp(len(index) // 2, None, prefer_square=True)

        if w > LVZ_MAX_TEXTURE_DIMENSION or h > LVZ_MAX_TEXTURE_DIMENSION or (w * h) > LVZ_MAX_TEXTURE_PIXELS:
            raise ValueError(f"refusing 8bpp texture size {w}x{h}")
        if self.debug_print:
            dbg(f"[size] chosen (8bpp): {w}x{h} (pixels={w*h}, index_bytes={len(index)})")

        need = w * h
        slab = np.frombuffer(index[:need], dtype=np.uint8).copy()
        if slab.size < need:
            raise ValueError(f"8bpp indices smaller than required pixels ({slab.size} < {need}).")
        if use_swizzle:
            slab = self.unswizzle8_ps2_linearized(slab, w, h)
        idx2d = slab.reshape(h, w)
        idx2d = np.flipud(idx2d)
        pal_arr = np.asarray(palette, dtype=np.uint8)
        pal_arr = self.apply_ps2_alpha_scale(pal_arr, do_scale=(alpha_scale == "ps2"))
        rgba = pal_arr[np.clip(idx2d, 0, pal_arr.shape[0] - 1)]
        asset_name = name_override if name_override else out_stem
        img = self.image_from_rgba_uint8(rgba, asset_name, w, h)
        mat = self.create_material_from_image(img, asset_name)
        return {"material": mat, "size": (w, h), "palette_tag": tag}

    def decode_blob_32bpp_single(self, blob: bytes, name: str, width: int, height: int,
                                  alpha_scale: str = "ps2") -> Dict:
        if width <= 0 or height <= 0 or width > LVZ_MAX_TEXTURE_DIMENSION or height > LVZ_MAX_TEXTURE_DIMENSION:
            raise ValueError(f"invalid 32bpp texture dimensions {width}x{height}")
        pixel_count = width * height
        if pixel_count > LVZ_MAX_TEXTURE_PIXELS or len(blob) < pixel_count * 4:
            raise ValueError(f"truncated or oversized 32bpp texture {width}x{height}")
        rgba = np.frombuffer(blob, dtype=np.uint8, count=pixel_count * 4).copy().reshape(height, width, 4)
        if alpha_scale == "ps2":
            rgba[:, :, 3] = np.minimum(rgba[:, :, 3].astype(np.uint16) * 2, 255).astype(np.uint8)
        rgba = np.flipud(rgba)
        image = self.image_from_rgba_uint8(rgba, name, width, height)
        material = self.create_material_from_image(image, name)
        return {"material": material, "size": (width, height), "palette_tag": "rgba32"}

    def direct_texture_raster_info_from_blob(self, blob: bytes) -> Dict[str, int]:
        if len(blob) < LVZ_DIRECT_TEXTURE_HEADER_BYTES:
            raise ValueError("direct texture blob is shorter than its 16-byte header")
        raster_flags = read_u32(blob, 12)
        logw = raster_flags & 0x3F
        logh = (raster_flags >> 6) & 0x3F
        depth = (raster_flags >> 12) & 0x3F
        mipmaps = (raster_flags >> 20) & 0x0F
        swizzle_mask = (raster_flags >> 24) & 0xFF
        if logw > 12 or logh > 12 or depth not in (4, 8, 32):
            raise ValueError(f"unsupported direct texture raster flags 0x{raster_flags:08X}")
        return {
            "flags": int(raster_flags),
            "format_flags": int(read_u16(blob, 6)),
            "width": int(1 << logw),
            "height": int(1 << logh),
            "depth": int(depth),
            "mipmaps": int(mipmaps),
            "swizzle_mask": int(swizzle_mask),
        }

    def direct_texture_dimensions_from_blob(self, blob: bytes) -> Tuple[int, int]:
        info = self.direct_texture_raster_info_from_blob(blob)
        width = int(info["width"])
        height = int(info["height"])
        if width <= 0 or height <= 0 or width > LVZ_MAX_TEXTURE_DIMENSION or height > LVZ_MAX_TEXTURE_DIMENSION:
            raise ValueError(f"unsupported direct texture dimensions {width}x{height}")
        return width, height

    def direct_texture_payload_from_blob(self, blob: bytes, width: int, height: int) -> bytes:
        info = self.direct_texture_raster_info_from_blob(blob)
        depth = int(info["depth"])
        mipmaps = max(1, int(info["mipmaps"]))
        if depth not in (4, 8, 32):
            raise ValueError(f"unsupported direct LVZ texture depth={depth}")

        palette_bytes = LVZ_DIRECT_TEXTURE_PALETTE_BYTES_8BPP if depth == 8 else LVZ_DIRECT_TEXTURE_PALETTE_BYTES
        level_w = int(width)
        level_h = int(height)
        image_bytes_total = 0
        level0_bytes = (level_w * level_h * depth + 7) // 8
        for _ in range(mipmaps):
            image_bytes_total += (max(1, level_w) * max(1, level_h) * depth + 7) // 8
            level_w = max(1, level_w // 2)
            level_h = max(1, level_h // 2)

        src_index_start = LVZ_DIRECT_TEXTURE_HEADER_BYTES
        src_index_end = src_index_start + level0_bytes
        palette_start = LVZ_DIRECT_TEXTURE_HEADER_BYTES + image_bytes_total

        if src_index_end > len(blob):
            raise ValueError("direct texture base mip is truncated")

        if depth == 32:
            return blob[src_index_start:src_index_end]

        if palette_start + palette_bytes <= len(blob):
            palette = blob[palette_start:palette_start + palette_bytes]
        elif src_index_end + palette_bytes <= len(blob):
            palette = blob[src_index_end:src_index_end + palette_bytes]
        else:
            raise ValueError("direct texture palette is truncated")

        return blob[src_index_start:src_index_end] + palette

    def decode_textures(self, rows: List[Dict], progress_callback=None, decode_pixels=True) -> int:
        if not decode_pixels:
            for row in rows:
                if row.get("kind") not in {"TEX", "TEX_REF"}:
                    continue
                resource_id = int(row.get("res_id", row.get("index", -1)))
                material = bpy.data.materials.new("texture%d" % resource_id)
                material.diffuse_color = (0.8, 0.8, 0.8, 1.0)
                material["blds_kind"] = "TEX_PLACEHOLDER"
                material["blds_res_index"] = resource_id
                material["blds_texture_res_index"] = resource_id
                self.material_by_res_index[resource_id] = material
            return 0
        direct_rows = [r for r in rows if r.get("kind") == "TEX"]
        tex_ref_rows = [r for r in rows if r.get("kind") == "TEX_REF"]
        if not direct_rows and not tex_ref_rows:
            dbg("[tex] no TEX/TEX_REF rows")
            return 0

        dbg(f"[tex] direct TEX rows: {len(direct_rows)}  TEX_REF rows: {len(tex_ref_rows)}")
        decoded = 0
        direct_sorted = sorted(direct_rows, key=lambda r: int(r.get("res_id", r.get("index", -1))))
        unique_reference_rows = []
        if tex_ref_rows:
            reference_sorted = sorted(
                [{"i": r["index"], "ref_addr": r.get("ref_addr", -1), "res_id": r.get("res_id", -1),
                  "embedded": r.get("embedded_res_id", None)} for r in tex_ref_rows],
                key=lambda d: d["ref_addr"]
            )
            seen_reference_addresses = set()
            reference_by_address = {}
            for reference_row in reference_sorted:
                reference_address = reference_row["ref_addr"]
                if not isinstance(reference_address, int) or not (0 <= reference_address < len(self.decomp)):
                    continue
                if reference_address in seen_reference_addresses:
                    reference_by_address[reference_address]["aliases"].append(reference_row["res_id"])
                    continue
                seen_reference_addresses.add(reference_address)
                reference_row["aliases"] = [reference_row["res_id"]]
                reference_by_address[reference_address] = reference_row
                unique_reference_rows.append(reference_row)

        texture_row_total = len(direct_sorted) + len(unique_reference_rows)
        for direct_index, row in enumerate(direct_sorted):
            if progress_callback is not None:
                try:
                    progress_callback(direct_index, texture_row_total)
                except Exception:
                    pass
            res_index = int(row.get("res_id", row.get("index", -1)))
            start = int(row.get("res_addr", 0) or 0)
            end = int(row.get("res_end", len(self.decomp)) or len(self.decomp))
            if end <= start:
                continue
            blob_len = end - start
            if blob_len < LVZ_DIRECT_TEXTURE_HEADER_BYTES:
                continue
            if blob_len > LVZ_MAX_TEXTURE_BLOB_BYTES:
                dbg(
                    f"[tex] skip direct TEX RES={res_index} LVZ+0x{start:08X}: "
                    f"span 0x{blob_len:X} is too large for one protected texture decode"
                )
                continue

            material_name = f"{self.stem}{res_index:0d}"
            try:
                full_blob = self.decomp[start:end]
                raster_info = self.direct_texture_raster_info_from_blob(full_blob)
                width, height = int(raster_info["width"]), int(raster_info["height"])
                payload = self.direct_texture_payload_from_blob(full_blob, width, height)
                depth = int(raster_info.get("depth", 4))
                texture_uses_swizzle = bool(self.use_swizzle and (int(raster_info.get("swizzle_mask", 0)) & 1))
                if depth == 32:
                    result = self.decode_blob_32bpp_single(
                        blob=payload,
                        name=material_name,
                        width=width,
                        height=height,
                        alpha_scale="ps2" if self.use_swizzle else "none",
                    )
                elif depth == 8:
                    result = self.decode_blob_8bpp_single(
                        blob=payload,
                        out_stem=material_name,
                        use_swizzle=texture_uses_swizzle,
                        alpha_scale="ps2",
                        name_override=material_name,
                        fixed_size=(width, height),
                    )
                else:
                    result = self.decode_blob_4bpp_lo_single(
                        blob=payload,
                        out_stem=material_name,
                        palette_mode="tail64",
                        palette_offset=None,
                        palette_size=None,
                        use_swizzle=texture_uses_swizzle,
                        sizes_hint=None,
                        alpha_scale="ps2",
                        name_override=material_name,
                        fixed_size=(width, height),
                        round_to_power_of_two=False,
                    )
                mat = result["material"]
                try:
                    mat["blds_kind"] = "TEX"
                    mat["blds_res_index"] = int(res_index)
                    mat["blds_texture_res_index"] = int(res_index)
                    mat["blds_lvz_ref_addr"] = int(start)
                    mat["blds_lvz_texture_blob_len"] = int(blob_len)
                    mat["blds_lvz_texture_direct"] = True
                    mat["blds_lvz_texture_header_len"] = int(LVZ_DIRECT_TEXTURE_HEADER_BYTES)
                    mat["blds_lvz_texture_width_half"] = int(row.get("width_half", 0) or 0)
                    mat["blds_lvz_texture_flags"] = int(raster_info["format_flags"])
                    mat["blds_lvz_raster_flags"] = int(raster_info.get("flags", 0))
                    mat["blds_lvz_texture_depth"] = int(raster_info.get("depth", 0))
                    mat["blds_lvz_texture_swizzled"] = bool(texture_uses_swizzle)
                    if getattr(result.get("material"), "node_tree", None) is not None:
                        for node in result["material"].node_tree.nodes:
                            if getattr(node, "type", None) == 'TEX_IMAGE' and getattr(node, "image", None) is not None:
                                node.image["blds_kind"] = "TEX"
                                node.image["blds_res_index"] = int(res_index)
                                node.image["blds_texture_res_index"] = int(res_index)
                                node.image["blds_lvz_ref_addr"] = int(start)
                                node.image["blds_lvz_texture_blob_len"] = int(blob_len)
                                node.image["blds_lvz_texture_direct"] = True
                                node.image["blds_lvz_texture_header_len"] = int(LVZ_DIRECT_TEXTURE_HEADER_BYTES)
                                node.image["blds_lvz_texture_flags"] = int(raster_info["format_flags"])
                                node.image["bleeds_uv_game_hint"] = self.master_game_hint
                                node.image["blds_lvz_raster_flags"] = int(raster_info.get("flags", 0))
                                node.image["blds_lvz_texture_depth"] = int(raster_info.get("depth", 0))
                                node.image["blds_lvz_texture_swizzled"] = bool(texture_uses_swizzle)
                                mat["blds_texture_image_name"] = node.image.name
                                break
                except Exception:
                    pass
                configureNativeWorldUvAnimation(
                    mat, raster_info["format_flags"], self.master_game_hint,
                    frame_start=int(bpy.context.scene.frame_start),
                )
                self.material_by_res_index[res_index] = mat
                decoded += 1
                if self.debug_print:
                    dbg(
                        f"[tex] {material_name}: direct material='{mat.name}' "
                        f"size={result['size']} RES={res_index} "
                        f"hdr_width_half={row.get('width_half')} flags=0x{int(row.get('texture_flags', 0) or 0):04X} "
                        f"raster=0x{int(raster_info.get('flags', 0)):08X} swiz={int(texture_uses_swizzle)}"
                    )
            except Exception as e:
                dbg(f"[tex] {material_name}: direct decode error: {e}")
                if res_index not in self.material_by_res_index:
                    mat = bpy.data.materials.new(material_name)
                    mat.diffuse_color = (0.8, 0.8, 0.8, 1.0)
                    mat["blds_kind"] = "TEX_PLACEHOLDER"
                    mat["blds_res_index"] = int(res_index)
                    mat["blds_texture_res_index"] = int(res_index)
                    mat["blds_lvz_ref_addr"] = int(start)
                    mat["blds_lvz_texture_blob_len"] = int(blob_len)
                    mat["blds_lvz_texture_direct"] = True
                    self.material_by_res_index[res_index] = mat

        if unique_reference_rows:
            direct_count = len(direct_sorted)
            for idx, r in enumerate(unique_reference_rows):
                if progress_callback is not None:
                    try:
                        progress_callback(direct_count + idx, texture_row_total)
                    except Exception:
                        pass
                start = r["ref_addr"]
                end = unique_reference_rows[idx+1]["ref_addr"] if idx+1 < len(unique_reference_rows) else len(self.decomp)
                blob_len = end - start
                if end <= start or blob_len < 64:
                    continue
                if blob_len > LVZ_MAX_TEXTURE_BLOB_BYTES:
                    dbg(
                        f"[tex] skip RES(index)={r.get('res_id')} LVZ+0x{start:08X}: "
                        f"span 0x{blob_len:X} is too large for one protected texture decode"
                    )
                    continue
                blob = self.decomp[start:end]

                res_index = r["res_id"]
                material_name = f"{self.stem}{res_index:0d}"
                try:
                    result = self.decode_blob_4bpp_lo_single(
                        blob=blob,
                        out_stem=material_name,
                        palette_mode="tail64",
                        palette_offset=None,
                        palette_size=None,
                        use_swizzle=self.use_swizzle,
                        sizes_hint=None,
                        alpha_scale="ps2",
                        name_override=material_name,
                    )
                    mat = result["material"]
                    try:
                        mat["blds_kind"] = "TEX"
                        mat["blds_res_index"] = int(res_index)
                        mat["blds_texture_res_index"] = int(res_index)
                        mat["blds_lvz_ref_addr"] = int(start)
                        mat["blds_lvz_texture_blob_len"] = int(end - start)
                        if getattr(result.get("material"), "node_tree", None) is not None:
                            for node in result["material"].node_tree.nodes:
                                if getattr(node, "type", None) == 'TEX_IMAGE' and getattr(node, "image", None) is not None:
                                    node.image["blds_kind"] = "TEX"
                                    node.image["blds_res_index"] = int(res_index)
                                    node.image["blds_texture_res_index"] = int(res_index)
                                    node.image["blds_lvz_ref_addr"] = int(start)
                                    node.image["blds_lvz_texture_blob_len"] = int(end - start)
                                    mat["blds_texture_image_name"] = node.image.name
                                    break
                    except Exception:
                        pass
                    self.material_by_res_index[res_index] = mat
                    for alias_res_id in r["aliases"]:
                        self.material_by_res_index[int(alias_res_id)] = mat
                    decoded += 1
                    if self.debug_print:
                        if r["embedded"] is not None:
                            dbg(f"[tex] {material_name}: material='{mat.name}' size={result['size']} RES(index)={res_index} embedded=0x{r['embedded']:08X}")
                        else:
                            dbg(f"[tex] {material_name}: material='{mat.name}' size={result['size']} RES(index)={res_index}")
                except Exception as e:
                    dbg(f"[tex] {material_name}: decode error: {e}")
                    if res_index not in self.material_by_res_index:
                        mat = bpy.data.materials.new(material_name)
                        mat.diffuse_color = (0.8, 0.8, 0.8, 1.0)
                        mat["blds_kind"] = "TEX_PLACEHOLDER"
                        mat["blds_res_index"] = int(res_index)
                        mat["blds_texture_res_index"] = int(res_index)
                        mat["blds_lvz_ref_addr"] = int(start)
                        mat["blds_lvz_texture_blob_len"] = int(end - start)
                        self.material_by_res_index[res_index] = mat
                        for alias_res_id in r["aliases"]:
                            self.material_by_res_index[int(alias_res_id)] = mat
        if progress_callback is not None:
            try:
                progress_callback(texture_row_total, texture_row_total)
            except Exception:
                pass
        dbg(f"[tex] total decoded: {decoded}")
        return decoded

    def readVec3I16Norm(self, buf: bytes, off: int) -> Tuple[float,float,float]:
        x = read_i16(buf, off + 0); y = read_i16(buf, off + 2); z = read_i16(buf, off + 4)
        return (x / 32767.5, y / 32767.5, z / 32767.5)

    def readPackedWorldUv(self, buf: bytes, off: int) -> Tuple[float,float]:
        u = buf[off + 0]
        v = buf[off + 1]
        return (u / 128.0, v / 128.0)

    def decodeRgba5551(self, v16: int) -> Tuple[int,int,int,int]:
        r = (v16 & 0x1F) * 255 // 0x1F
        g = ((v16 >> 5) & 0x1F) * 255 // 0x1F
        b = ((v16 >> 10) & 0x1F) * 255 // 0x1F
        a = 255 if (v16 & 0x8000) else 0
        return (r, g, b, a)

    def decodeRgba4444(self, v16: int) -> Tuple[int,int,int,int]:
        return self.decodeRgba5551(v16)

    def logUnpackAlignment(self, requested_off: int, found_off: int):
        if requested_off == found_off:
            return
        try:
            count = int(getattr(self, "_unpack_align_log_count", 0))
        except Exception:
            count = 0
        if count < LVZ_UNPACK_ALIGN_LOG_LIMIT:
            try:
                dbg(
                    f"[unpack-align] UNPACK pointer adjusted "
                    f"0x{requested_off:08X}->0x{found_off:08X} "
                    f"delta={found_off - requested_off:+d}"
                )
            except Exception:
                pass
        elif count == LVZ_UNPACK_ALIGN_LOG_LIMIT:
            try:
                dbg(f"[unpack-align] further UNPACK pointer adjustment logs suppressed after {LVZ_UNPACK_ALIGN_LOG_LIMIT}")
            except Exception:
                pass
        try:
            setattr(self, "_unpack_align_log_count", count + 1)
        except Exception:
            pass

    def findUnpackNear(self, buf: bytes, off: int, window: int = LVZ_UNPACK_SEARCH_WINDOW, max_end: Optional[int] = None, allow_backward: bool = True) -> int:
        n = len(buf)
        if max_end is not None:
            n = min(n, max(0, int(max_end)))
        requested = int(off)
        if n <= 0:
            raise ValueError(f"UNPACK header not found near 0x{requested:08X}")

        def valid_unpack(p: int) -> bool:
            if not allow_backward and p < requested:
                return False
            return (p & 3) == 0 and 0 <= p and p + 4 <= n and read_u32(buf, p) == self.UNPACK


        preferred_deltas = (
            0,
            0x50, -0x50,
            0x4C, 0x54, 0x48, 0x58, 0x44, 0x5C, 0x40, 0x60,
            -12, 12, -16, 16, -8, 8, -4, 4,
            -20, 20, -24, 24, -28, 28, -32, 32, -36, 36, -40, 40,
        )
        seen = set()
        for delta in preferred_deltas:
            if not allow_backward and delta < 0:
                continue
            p = requested + delta
            if p in seen:
                continue
            seen.add(p)
            if valid_unpack(p):
                self.logUnpackAlignment(requested, p)
                return p

        win = max(int(window), 0x90)
        start = max(0, requested - win) if allow_backward else max(0, requested)
        end = min(n - 4, requested + win)
        aligned = []
        for p in range(start, end + 1):
            if (p & 3) == 0 and p not in seen and valid_unpack(p):
                aligned.append(p)
        if aligned:


            p = sorted(aligned, key=lambda q: (abs(q - requested), q))[0]
            self.logUnpackAlignment(requested, p)
            return p
        raise ValueError(f"UNPACK header not found near 0x{requested:08X}")

    def findNextUnpackAfterMscal(self, buf: bytes, off: int, window: int = LVZ_UNPACK_SEARCH_WINDOW, max_end: Optional[int] = None) -> int:
        return self.findUnpackNear(buf, off, window=window, max_end=max_end, allow_backward=False)

    def logUnpackNextSelfLoopGuard(self, requested_off: int, found_off: int):
        try:
            count = int(getattr(self, "_unpack_next_self_loop_log_count", 0))
        except Exception:
            count = 0
        if count < LVZ_UNPACK_NEXT_SELF_LOOP_LOG_LIMIT:
            try:
                dbg(
                    f"[unpack-align] rejected backward/duplicate next UNPACK "
                    f"after MSCAL: requested=0x{requested_off:08X} found=0x{found_off:08X}"
                )
            except Exception:
                pass
        elif count == LVZ_UNPACK_NEXT_SELF_LOOP_LOG_LIMIT:
            try:
                dbg(f"[unpack-align] further next-UNPACK self-loop guard logs suppressed after {LVZ_UNPACK_NEXT_SELF_LOOP_LOG_LIMIT}")
            except Exception:
                pass
        try:
            setattr(self, "_unpack_next_self_loop_log_count", count + 1)
        except Exception:
            pass

    def parse_mdl_material_list(self, base: int, max_end: Optional[int] = None) -> MDLMaterialList:
        lvz = self.decomp
        n = len(lvz)
        if max_end is not None:
            n = min(n, max(0, int(max_end)))
        requested_base = int(base)
        detected = self.detect_mdl_material_list_format(base, max_end=n)
        if detected is None:
            adjusted_base = self.find_mdl_material_list_start_near(base, max_end=n)
            if adjusted_base is not None and adjusted_base != base:
                self.logMdlDescriptorAlignment(requested_base, int(adjusted_base))
                base = int(adjusted_base)
                detected = self.detect_mdl_material_list_format(base, max_end=n)
        if detected is None:
            if base + 4 > n:
                raise ValueError("MDL material list header out of range.")
            count = read_u16(lvz, base + 0)
            size_bytes = read_u16(lvz, base + 2)
            raise ValueError(f"unsupported or implausible WRLD material list at 0x{base:08X}: count16={count} size16={size_bytes}")

        format_tag = str(detected["format_tag"])
        count = int(detected["count"])
        size_bytes = int(detected["size_bytes"])
        row_len = int(detected["row_len"])
        header_len = int(detected["header_len"])
        list_end = int(detected["list_end"])
        off = base + header_len
        materials: List[MDLMaterial] = []

        for mi in range(count):
            if off + row_len > n or off + row_len > list_end:
                dbg(f"[mdl] material {mi}: truncated before declared list end (need up to 0x{off + row_len:08X})")
                break

            if format_tag == "ps2_vcs":
                packet_raw = read_u32(lvz, off + 0)
                tri_strip_size = packet_raw >> 1
                backface_cull = (packet_raw & 1) != 0
                texture_id = read_u16(lvz, off + 4)
                u_scale = half_to_float(read_u16(lvz, off + 6))
                v_scale = half_to_float(read_u16(lvz, off + 8))
                flags2 = read_u16(lvz, off + 10)
                b0 = read_i16(lvz, off + 12)
                b1 = read_i16(lvz, off + 14)
                b2 = read_i16(lvz, off + 16)
                b3 = read_i16(lvz, off + 18)
                b4 = read_i16(lvz, off + 20)
                b5 = read_i16(lvz, off + 22)
            elif format_tag == "ps2_lcs":
                texture_id = read_u16(lvz, off + 0)
                packet_raw = read_u16(lvz, off + 2)
                tri_strip_size = packet_raw & 0x7FFF
                backface_cull = (packet_raw & 0x8000) != 0
                u_scale = half_to_float(read_u16(lvz, off + 4))
                v_scale = half_to_float(read_u16(lvz, off + 6))
                flags2 = read_u16(lvz, off + 8)
                b0 = read_i16(lvz, off + 10)
                b1 = read_i16(lvz, off + 12)
                b2 = read_i16(lvz, off + 14)
                b3 = read_i16(lvz, off + 16)
                b4 = read_i16(lvz, off + 18)
                b5 = read_i16(lvz, off + 20)
            elif format_tag in ("psp_wrld_10", "psp_wrld_24"):
                texture_id = read_u16(lvz, off + 0)
                packet_raw = read_u16(lvz, off + 2)
                tri_strip_size = packet_raw & 0x7FFF
                backface_cull = (packet_raw & 0x8000) != 0
                u_scale = half_to_float(read_u16(lvz, off + 4)) if row_len >= 8 else 1.0
                v_scale = half_to_float(read_u16(lvz, off + 6)) if row_len >= 8 else 1.0
                flags2 = read_u16(lvz, off + 8) if row_len >= 10 else 0
                if row_len >= 24:
                    b0 = read_i16(lvz, off + 12)
                    b1 = read_i16(lvz, off + 14)
                    b2 = read_i16(lvz, off + 16)
                    b3 = read_i16(lvz, off + 18)
                    b4 = read_i16(lvz, off + 20)
                    b5 = read_i16(lvz, off + 22)
                else:
                    b0 = b1 = b2 = b3 = b4 = b5 = 0
            else:
                raise ValueError(f"unknown material list format {format_tag}")

            if not math.isfinite(u_scale) or abs(u_scale) > 4096.0:
                u_scale = 1.0
            if not math.isfinite(v_scale) or abs(v_scale) > 4096.0:
                v_scale = 1.0

            materials.append(MDLMaterial(
                texture_id=texture_id,
                tri_strip_size=tri_strip_size,
                backface_cull=backface_cull,
                u_scale=u_scale,
                v_scale=v_scale,
                flags2=flags2,
                bbox6_i16=(b0, b1, b2, b3, b4, b5),
                row_format=format_tag,
                packet_raw=int(packet_raw),
            ))
            off += row_len

        aa_tail, new_off = self.scanAaTail(list_end)
        next_offset = align_up4(new_off)
        return MDLMaterialList(
            count=count,
            size_bytes=size_bytes,
            materials=materials,
            bytes_read=list_end - base,
            aa_tail=aa_tail,
            next_off=next_offset,
            format_tag=format_tag,
            row_len=row_len,
        )

    def scanAaTail(self, off: int) -> Tuple[bytes, int]:
        lvz = self.decomp
        n = len(lvz); i = off
        while i < n and lvz[i] == 0xAA:
            i += 1
        return (lvz[off:i], i)

    def parse_one_batch_noskip(self, buf: bytes, pos: int, max_end: Optional[int] = None) -> Tuple[TriStrip, int]:
        n = len(buf)
        if max_end is not None:
            n = min(n, max(0, int(max_end)))
        pos = self.findUnpackNear(buf, align_down4(pos), max_end=n)
        if pos + 20 > n:
            raise ValueError("Batch header truncated.")
        nvert_all = read_u32(buf, pos + 16) & 0x7FFF
        if nvert_all <= 0 or nvert_all > LVZ_MAX_MDL_VERTICES_PER_BATCH:
            raise ValueError(f"Refusing implausible batch vertex count {nvert_all} at 0x{pos:08X}")
        nvert_eff = nvert_all
        w = pos + 20

        if read_u32(buf, w) != self.STMASK: raise ValueError(f"Expected STMASK before positions at 0x{w:08X}")
        w += 8
        if read_u32(buf, w) != self.STROW:  raise ValueError(f"Expected STROW before positions at 0x{w:08X}")
        w += 20
        h_pos = read_u32(buf, w)
        if (h_pos & 0xFF000000) != 0x79000000: raise ValueError(f"Unexpected positions header 0x{h_pos:08X} at 0x{w:08X}")
        w += 4
        need_bytes_pos = nvert_all * 6
        if w + need_bytes_pos > n: raise ValueError("Position payload truncated.")
        verts: List[Tuple[float,float,float]] = []
        for i in range(nvert_eff):
            off = w + i * 6
            verts.append(self.readVec3I16Norm(buf, off))
        w += need_bytes_pos
        w = align_up4(w)

        if read_u32(buf, w) != self.STMASK: raise ValueError(f"Expected STMASK before texcoords at 0x{w:08X}")
        w += 8
        if read_u32(buf, w) != self.STROW:  raise ValueError(f"Expected STROW before texcoords at 0x{w:08X}")
        w += 20
        h_uv = read_u32(buf, w)
        if (h_uv & 0xFF000000) != 0x76000000: raise ValueError(f"Unexpected UV header 0x{h_uv:08X} at 0x{w:08X}")
        w += 4
        need_bytes_uv = nvert_all * 2
        if w + need_bytes_uv > n: raise ValueError("UV payload truncated.")
        uvs: List[Tuple[float,float]] = []
        for i in range(nvert_eff):
            off = w + i * 2
            uvs.append(self.readPackedWorldUv(buf, off))
        w += need_bytes_uv
        w = align_up4(w)

        h_col = read_u32(buf, w)
        if (h_col & 0xFF000000) != 0x6F000000: raise ValueError(f"Unexpected prelight header 0x{h_col:08X} at 0x{w:08X}")
        w += 4
        need_bytes_col = nvert_all * 2
        if w + need_bytes_col > n: raise ValueError("Prelight payload truncated.")
        cols_raw_u16: List[int] = []
        cols_rgba4444: List[Tuple[int,int,int,int]] = []
        for i in range(nvert_eff):
            c16 = read_u16(buf, w + i * 2)
            cols_raw_u16.append(c16)
            cols_rgba4444.append(self.decodeRgba5551(c16))
        w += need_bytes_col
        w = align_up4(w)

        if read_u32(buf, w) != self.MSCAL:
            if w + 4 <= n and read_u32(buf, w + 4) == self.MSCAL:
                w += 4
            else:
                raise ValueError(f"MSCAL 0x14000006 missing around 0x{w:08X}")
        w += 4
        while w + 4 <= n and read_u32(buf, w) == 0:
            w += 4

        strip = TriStrip(
            count=nvert_eff,
            verts=verts,
            uvs=uvs,
            cols_raw_u16=cols_raw_u16,
            cols_rgba4444=cols_rgba4444
        )
        return strip, w

    def ps2_mdl_stream_byte_budget_from_material_list(self, mlist: MDLMaterialList) -> int:
        if not str(getattr(mlist, "format_tag", "")).startswith("ps2_"):
            return 0
        total = 0
        for material in getattr(mlist, "materials", []) or []:
            try:
                packet_size = int(getattr(material, "tri_strip_size", 0))
            except Exception:
                packet_size = 0
            if packet_size <= 0:
                continue
            if packet_size > 0x400000:
                return 0
            total += packet_size
            if total > 0x2000000:
                return 0
        return int(total)

    def parse_mdl_stream_after_list(self, start_off: int, max_groups: int = LVZ_MAX_MDL_BATCHES_PER_RESOURCE, max_end: Optional[int] = None, byte_budget: Optional[int] = None) -> Tuple[List[MDLStripGroup], int]:
        buf = self.decomp
        groups: List[MDLStripGroup] = []
        hard_end = len(buf) if max_end is None else min(len(buf), max(0, int(max_end)))
        if start_off >= hard_end:
            return groups, start_off
        try:
            off = self.findUnpackNear(buf, start_off, max_end=hard_end)
        except Exception:
            return groups, start_off

        parse_end = hard_end
        budget_end = None
        if byte_budget is not None:
            try:
                budget = int(byte_budget)
            except Exception:
                budget = 0
            if budget > 0:
                budget_end = min(hard_end, off + budget)
                if budget_end > off:
                    parse_end = budget_end

        total_vertices = 0
        for _ in range(max_groups):
            if off >= parse_end:
                break
            try:
                strip, next_off = self.parse_one_batch_noskip(buf, off, max_end=parse_end)
            except Exception:
                break
            total_vertices += int(strip.count)
            if total_vertices > LVZ_MAX_MDL_VERTICES_PER_OBJECT:
                dbg(
                    f"[splits] stop at 0x{off:08X}: object vertex limit "
                    f"{LVZ_MAX_MDL_VERTICES_PER_OBJECT} exceeded"
                )
                break
            groups.append(MDLStripGroup(strips=[strip], bytes_read=(next_off - off), start_off=off, end_off=next_off))
            if next_off <= off:
                self.logUnpackNextSelfLoopGuard(next_off, off)
                off = next_off
                break
            if budget_end is not None and next_off >= budget_end:
                off = next_off
                break
            try:
                next_unpack = self.findNextUnpackAfterMscal(buf, next_off, max_end=parse_end)
            except Exception:
                off = next_off
                break
            if next_unpack <= off:
                self.logUnpackNextSelfLoopGuard(next_off, next_unpack)
                off = next_off
                break
            off = next_unpack
        if len(groups) >= max_groups:
            dbg(f"[splits] stopped after max_groups={max_groups}")
        return groups, off

    def parse_psp_wrld_stream_after_list(self, mlist: MDLMaterialList, max_end: Optional[int] = None) -> Tuple[List[MDLStripGroup], int]:
        buf = self.decomp
        parse_end = len(buf) if max_end is None else min(len(buf), max(0, int(max_end)))
        off = align_up4(int(mlist.next_off))
        groups: List[MDLStripGroup] = []
        total_vertices = 0

        for material in mlist.materials:
            vertex_count = int(material.tri_strip_size)
            if vertex_count <= 0:
                continue
            if vertex_count > LVZ_MAX_MDL_VERTICES_PER_BATCH:
                dbg(f"[psp-wrld] stop at 0x{off:08X}: implausible vertex count {vertex_count}")
                break
            need = vertex_count * 10
            if off + need > parse_end:
                dbg(f"[psp-wrld] stop at 0x{off:08X}: vertex payload truncated ({need} bytes)")
                break

            verts: List[Tuple[float, float, float]] = []
            uvs: List[Tuple[float, float]] = []
            cols_raw_u16: List[int] = []
            cols_rgba: List[Tuple[int, int, int, int]] = []
            for vi in range(vertex_count):
                voff = off + vi * 10
                u, v = self.readPackedWorldUv(buf, voff)
                color = read_u16(buf, voff + 2)
                x = read_i16(buf, voff + 4) / 32768.0
                y = read_i16(buf, voff + 6) / 32768.0
                z = read_i16(buf, voff + 8) / 32768.0
                verts.append((x, y, z))
                uvs.append((u * material.u_scale, v * material.v_scale))
                cols_raw_u16.append(color)
                cols_rgba.append(self.decodeRgba5551(color))

            strip = TriStrip(
                count=vertex_count,
                verts=verts,
                uvs=uvs,
                cols_raw_u16=cols_raw_u16,
                cols_rgba4444=cols_rgba,
                material_res_index=int(material.texture_id),
                u_scale=material.u_scale,
                v_scale=material.v_scale,
            )
            groups.append(MDLStripGroup(strips=[strip], bytes_read=need, start_off=off, end_off=off + need))
            total_vertices += vertex_count
            if total_vertices > LVZ_MAX_MDL_VERTICES_PER_OBJECT:
                dbg(f"[psp-wrld] object vertex limit {LVZ_MAX_MDL_VERTICES_PER_OBJECT} exceeded")
                break
            off += need
        return groups, off

    def parse_mdl_geometry_after_list(self, mlist: MDLMaterialList, max_end: Optional[int] = None) -> Tuple[List[MDLStripGroup], int]:
        if str(getattr(mlist, "format_tag", "")).startswith("psp_wrld"):
            return self.parse_psp_wrld_stream_after_list(mlist, max_end=max_end)
        byte_budget = self.ps2_mdl_stream_byte_budget_from_material_list(mlist)
        return self.parse_mdl_stream_after_list(mlist.next_off, max_end=max_end, byte_budget=byte_budget)

    def assign_materials_by_strip_bytes(self, mlist: MDLMaterialList, groups: List[MDLStripGroup]):

        if not mlist.materials or not groups:
            return


        if str(getattr(mlist, "format_tag", "")).startswith("psp_wrld"):
            return

        flat: List[Tuple[TriStrip, int, int]] = []
        gstart = min(g.start_off for g in groups)
        for g in groups:
            for s in g.strips:
                s_start = g.start_off
                s_end = g.end_off
                flat.append((s, s_start - gstart, s_end - gstart))

        flat.sort(key=lambda item: item[1])

        m_idx = 0
        m = mlist.materials[m_idx]
        m_window = m.tri_strip_size
        acc_len = 0

        for s, rel_start, rel_end in flat:
            batch_len = rel_end - rel_start
            if batch_len <= 0:
                continue

            while m_idx < len(mlist.materials) and acc_len >= m_window and m_window > 0:
                m_idx += 1
                if m_idx < len(mlist.materials):
                    m = mlist.materials[m_idx]
                    m_window = m.tri_strip_size
                    acc_len = 0

            if m_idx >= len(mlist.materials):
                break

            s.material_res_index = m.texture_id
            s.u_scale = m.u_scale
            s.v_scale = m.v_scale
            if s.uvs:
                s.uvs = [(u * s.u_scale, v * s.v_scale) for (u, v) in s.uvs]
            acc_len += batch_len

    def triangulateStripIndices(self, local_count: int) -> List[Tuple[int,int,int]]:
        tris: List[Tuple[int,int,int]] = []
        for i in range(local_count - 2):
            if i & 1:
                tris.append((i + 1, i, i + 2))
            else:
                tris.append((i, i + 1, i + 2))
        return tris

    def buildMeshFromMdlGroups(self, res_index: int, groups: List[MDLStripGroup]):
        if not groups:
            return None, []
        vertices: List[Tuple[float,float,float]] = []
        uvs: List[Tuple[float,float]] = []
        faces: List[Tuple[int,int,int]] = []
        colors = []
        face_ranges: List[Tuple[int,int,int]] = []

        for g in groups:
            for s in g.strips:
                k = min(len(s.verts), len(s.uvs), s.count)
                if k < 3:
                    continue
                base = len(vertices)
                vertices.extend(s.verts[:k])
                colors.extend(list(s.cols_rgba4444[:k]) + [(255, 255, 255, 255)] * max(0, k - len(s.cols_rgba4444)))
                uvs.extend(s.uvs[:k])
                tri_list = self.triangulateStripIndices(k)
                poly_start = len(faces)
                for a,b,c in tri_list:
                    faces.append((base + a, base + b, base + c))
                poly_count = len(tri_list)
                face_ranges.append((poly_start, poly_count, s.material_res_index))

        if not faces or not vertices:
            return None, []

        mesh_name = f"{self.stem}{res_index:0d}"
        me = bpy.data.meshes.new(mesh_name)
        me.from_pydata(vertices, [], faces)
        set_mesh_auto_smooth(me, True)
        me.validate(clean_customdata=False)
        me.update()

        if uvs:
            uv_layer = me.uv_layers.new(name="UVMap")
            uv_data = uv_layer.data
            for poly in me.polygons:
                li = poly.loop_start
                for j, vi in enumerate(poly.vertices):
                    if vi < len(uvs):
                        u, v = uvs[vi]
                        uv_data[li + j].uv = (u, v)

        color_layer = (me.color_attributes.new(name='Col', type='BYTE_COLOR', domain='CORNER')
                       if hasattr(me, 'color_attributes') else me.vertex_colors.new(name='Col'))
        for loop in me.loops:
            color_layer.data[loop.index].color = tuple(value / 255.0 for value in colors[loop.vertex_index])
        obj = bpy.data.objects.new(mesh_name, me)
        bpy.context.scene.collection.objects.link(obj)
        obj["blds_kind"] = "MDL"
        obj["blds_res_index"] = res_index
        obj["blds_groups"] = len(groups)
        obj["blds_faces"] = len(faces)
        obj["blds_verts"] = len(vertices)
        return obj, face_ranges

    def build_mdl_objects(self, rows: List[Dict]) -> Dict[int, bpy.types.Object]:
        mdl_rows = [r for r in rows if r["kind"] == "MDL"]
        built_by_res: Dict[int, bpy.types.Object] = {}
        if not mdl_rows:
            dbg("— MDL — none found")
            return built_by_res

        dbg("— MDL Material Lists + Batches + Mesh Build (NO-SKIP) —")
        built_cnt = 0
        for row in mdl_rows:
            res_index = row["index"]
            res_addr  = row["res_addr"]
            res_end = int(row.get("res_end", len(self.decomp)) or len(self.decomp))
            try:
                mlist = self.parse_mdl_material_list(res_addr, max_end=res_end)
            except Exception as e:
                dbg(f"[mdl {res_index}] material list error at 0x{res_addr:08X}: {e}")
                continue

            dbg(f"[mdl {res_index}] list: format={mlist.format_tag} row_len={mlist.row_len} count={mlist.count} size_bytes={mlist.size_bytes} bytes_read={mlist.bytes_read} aa_tail={len(mlist.aa_tail)} next=0x{mlist.next_off:08X} end=0x{res_end:08X}")
            for i, m in enumerate(mlist.materials):
                dbg(f"  mat[{i:02d}] texRES={m.texture_id} strip_size={m.tri_strip_size} cull={int(m.backface_cull)} us={m.u_scale:.4f} vs={m.v_scale:.4f} flags2=0x{m.flags2:04X} bbox={m.bbox6_i16}")

            groups, after = self.parse_mdl_geometry_after_list(mlist, max_end=res_end)
            dbg(f"[mdl {res_index}] batches={len(groups)} stream_end=0x{after:08X} bounded_end=0x{res_end:08X}")

            self.assign_materials_by_strip_bytes(mlist, groups)

            verbose_vertices_left = LVZ_MAX_VERBOSE_VERTEX_LOGS_PER_MDL
            for gi, g in enumerate(groups):
                for si, s in enumerate(g.strips):
                    k = s.count
                    dbg(f"[mdl {res_index}] dump: group={gi} strip={si} count={k} matRES={s.material_res_index} us={s.u_scale:.4f} vs={s.v_scale:.4f}")
                    if verbose_vertices_left <= 0:
                        continue
                    for vi in range(k):
                        if verbose_vertices_left <= 0:
                            dbg(f"    ... vertex dump capped at {LVZ_MAX_VERBOSE_VERTEX_LOGS_PER_MDL} vertices for this MDL")
                            break
                        px, py, pz = s.verts[vi]
                        tu, tv     = s.uvs[vi]
                        c16        = s.cols_raw_u16[vi] if vi < len(s.cols_raw_u16) else 0
                        r,gc,b,a   = s.cols_rgba4444[vi] if vi < len(s.cols_rgba4444) else (0,0,0,0)
                        dbg(f"    v[{vi:04d}] pos=({px:.6f},{py:.6f},{pz:.6f}) uv=({tu:.6f},{tv:.6f}) col16=0x{c16:04X} rgba4444=({r},{gc},{b},{a})")
                        verbose_vertices_left -= 1

            obj, face_ranges = self.buildMeshFromMdlGroups(res_index, groups)
            if obj is not None:
                mat_slots_added = 0
                resid_to_slot: Dict[int, int] = {}
                if mlist.materials:
                    for m in mlist.materials:
                        mat = self.material_by_res_index.get(m.texture_id)
                        if mat is None:
                            mat_name = f"{self.stem}{int(m.texture_id):0d}"
                            mat = bpy.data.materials.new(mat_name)
                            mat.diffuse_color = (0.8, 0.8, 0.8, 1.0)
                            mat["blds_kind"] = "TEX_PLACEHOLDER"
                            mat["blds_res_index"] = int(m.texture_id)
                            mat["blds_texture_res_index"] = int(m.texture_id)
                            mat["blds_reason"] = "placeholder created from WRLD material texture id"
                            self.material_by_res_index[int(m.texture_id)] = mat
                        if mat is not None:
                            if mat.name not in [mm.name for mm in obj.data.materials]:
                                obj.data.materials.append(mat)
                                resid_to_slot[m.texture_id] = len(obj.data.materials) - 1
                                mat_slots_added += 1
                            else:
                                for si, mm in enumerate(obj.data.materials):
                                    if mm and mm.name == mat.name:
                                        resid_to_slot[m.texture_id] = si
                                        break
                if face_ranges:
                    polys = obj.data.polygons
                    for (pstart, pcount, mat_resid) in face_ranges:
                        if mat_resid is None or mat_resid < 0:
                            continue
                        slot = resid_to_slot.get(mat_resid)
                        if slot is None:
                            continue
                        for pi in range(pstart, pstart + pcount):
                            if 0 <= pi < len(polys):
                                polys[pi].material_index = slot
                built_cnt += 1
                built_by_res[res_index] = obj
                dbg(f"[mdl {res_index}] → created object '{obj.name}' (added {mat_slots_added} material slots)")
            else:
                dbg(f"[mdl {res_index}] no faces/verts, skipped object creation")
        dbg(f"[done] total MDL objects created: {built_cnt}")
        return built_by_res

class read_img:
    def __init__(self, img_bytes: bytes, lvz_bytes: bytes):
        self.img_bytes = img_bytes
        self.lvz_bytes = lvz_bytes
        self.is_ver2_archive = is_ver2_img_archive(img_bytes)
        self.ver2_entries = parse_ver2_img_directory(img_bytes) if self.is_ver2_archive else []
        self._wrldtool_img_offset_by_lvz_addr = None
        self._wrldtool_img_offset_log_done = False
        self._img_mdl_parser = read_lvz(
            decomp_bytes=img_bytes,
            stem="img",
            use_swizzle=False,
            debug_print=False,
        )

    def find_mdl_material_list_start_near(self, addr: int, max_end: Optional[int] = None) -> Optional[int]:
        return self._img_mdl_parser.find_mdl_material_list_start_near(addr, max_end=max_end)

    def detect_mdl_material_list_format(self, addr: int, max_end: Optional[int] = None) -> Optional[Dict[str, object]]:
        return self._img_mdl_parser.detect_mdl_material_list_format(addr, max_end=max_end)

    def parse_mdl_material_list(self, base: int, max_end: Optional[int] = None) -> MDLMaterialList:
        return self._img_mdl_parser.parse_mdl_material_list(base, max_end=max_end)

    def parse_mdl_geometry_after_list(self, material_list: MDLMaterialList, max_end: Optional[int] = None) -> Tuple[List[MDLStripGroup], int]:
        return self._img_mdl_parser.parse_mdl_geometry_after_list(material_list, max_end=max_end)

    def wrldtool_img_offset_by_lvz_addr(self) -> Dict[int, int]:

        if self._wrldtool_img_offset_by_lvz_addr is not None:
            return self._wrldtool_img_offset_by_lvz_addr

        mapping: Dict[int, int] = {}
        for addr in self.iterLvzDlrwHeadersForDirectContimg():
            try:
                total = read_u32(self.lvz_bytes, addr + 0x08)
                cont_img = read_u32(self.lvz_bytes, addr + 0x18)
                if total >= 0x20 and 0 <= int(cont_img) < len(self.img_bytes):
                    mapping[int(addr)] = int(cont_img)
            except Exception:
                pass

        self._wrldtool_img_offset_by_lvz_addr = mapping
        try:
            if not self._wrldtool_img_offset_log_done:
                dbg(f"[wrldtool-offset] direct LVZ +0x18 contIMG offsets: {len(mapping)}")
                for i, addr in enumerate(sorted(mapping)[:64]):
                    cont_img = mapping[addr]
                    total = read_u32(self.lvz_bytes, addr + 0x08)
                    dbg(
                        f"[wrldtool-offset] sample {i:03d}: offsetLVZ=0x{addr:08X} "
                        f"size={int(total)} contIMG=0x{int(cont_img):08X} "
                        f"dataBase=0x{int(cont_img):08X} dataEnd=0x{int(cont_img + max(0, int(total) - 0x20)):08X}"
                    )
                self._wrldtool_img_offset_log_done = True
        except Exception:
            pass
        return mapping

    def iterLvzDlrwHeadersForDirectContimg(self) -> List[int]:
        lvz = self.lvz_bytes
        n = len(lvz)
        out = []
        seen = set()

        def add(addr):
            try:
                addr = int(addr)
                if addr in seen:
                    return
                if not (0 <= addr and addr + 0x20 <= n and (addr & 3) == 0):
                    return
                if lvz[addr:addr + 4] not in (b"DLRW", b"xet\0"):
                    return
                total = read_u32(lvz, addr + 0x08)
                cont_img = read_u32(lvz, addr + 0x18)
                if total < 0x20 or total > 0x4000000:
                    return
                if not (0 <= cont_img < len(self.img_bytes)):
                    return
                seen.add(addr)
                out.append(addr)
            except Exception:
                pass


        cursor = 0x24
        while cursor + 8 <= n:
            addr = read_u32(lvz, cursor + 0)
            if not (0 < addr < n and (addr & 3) == 0 and addr + 0x20 <= n):
                break
            if lvz[addr:addr + 4] not in (b"DLRW", b"xet\0"):
                break
            add(addr)
            group_count = read_u32(lvz, addr + 0x14)
            if group_count <= 0 or group_count > 4096:
                group_count = 1
            for child in range(1, int(group_count)):
                add(addr + child * 0x20)
            cursor += 8


        pos = 0
        while True:
            pos = lvz.find(b"DLRW", pos)
            if pos < 0:
                break
            add(pos)
            pos += 4

        out.sort()
        return out

    def img_data_base_for_lvz_dlrw_header(self, header_addr: int, fallback_global_rel: int, file_size: int):
        mapping = self.wrldtool_img_offset_by_lvz_addr()
        header_addr = int(header_addr)
        cont_img = mapping.get(header_addr)
        if cont_img is None:
            cont_img = int(fallback_global_rel)


        data_base = int(cont_img)
        data_end = min(len(self.img_bytes), data_base + max(0, int(file_size) - 0x20))
        used_direct_contimg = 0 <= data_base < len(self.img_bytes)
        return int(data_base), int(data_end), int(data_base), bool(used_direct_contimg)


    def find_sector_row_directories_from_lvz(self) -> List[Dict[str, int]]:
        lvz = self.lvz_bytes
        n = len(lvz)
        rows: List[Dict[str, int]] = []
        if n < 0x24 or lvz[:4] != b"DLRW":
            return rows

        cursor = 0x24
        row_index = 0
        while cursor + 8 <= n:
            header_addr = read_u32(lvz, cursor + 0)
            start_off = read_u32(lvz, cursor + 4)
            if not (0 < header_addr < n and (header_addr & 0x3) == 0 and header_addr + 0x20 <= n):
                break
            if lvz[header_addr:header_addr + 4] != b"DLRW":
                break
            rows.append({
                "row_index": int(row_index),
                "header_addr": int(header_addr),
                "start_off": int(start_off),
            })
            row_index += 1
            cursor += 8
        return rows

    def detect_sector_game_hint(self) -> str:
        return detect_world_game_from_sector_row_count(len(self.find_sector_row_directories_from_lvz()), "vcs")

    def sector_pass_names(self) -> Tuple[str, ...]:
        return IMG_PASS_NAMES_LCS if self.detect_sector_game_hint() == "lcs" else IMG_PASS_NAMES_VCS

    def find_sector_container_records_from_lvz(self) -> List[Dict[str, int]]:
        lvz = self.lvz_bytes
        rows = self.find_sector_row_directories_from_lvz()
        if len(rows) < 2:
            return []

        game_hint = detect_world_game_from_sector_row_count(len(rows), "vcs")
        records: List[Dict[str, int]] = []
        sector_index = 0
        for row_index in range(len(rows) - 1):
            row = rows[row_index]
            next_row = rows[row_index + 1]
            first_header = int(row["header_addr"])
            next_header = int(next_row["header_addr"])
            if next_header <= first_header:
                continue
            header_count = (next_header - first_header) // 0x20
            if header_count <= 0:
                continue
            sector_y = int(row_index)
            start_x = int(row.get("start_off", 0))
            for header_index in range(header_count):
                header_addr = first_header + header_index * 0x20
                if header_addr + 0x20 > len(lvz):
                    break
                if lvz[header_addr:header_addr + 4] != b"DLRW":
                    break
                file_size = read_u32(lvz, header_addr + 0x08)
                data_size = read_u32(lvz, header_addr + 0x0C)
                reloc_tab = read_u32(lvz, header_addr + 0x10)
                num_relocs = read_u32(lvz, header_addr + 0x14)
                global_tab = read_u32(lvz, header_addr + 0x18)
                if file_size < 0x20:
                    continue
                data_base, data_end, img_header_off, used_direct_contimg = self.img_data_base_for_lvz_dlrw_header(header_addr, global_tab, file_size)
                sector_x = start_x + header_index
                origin = sector_origin_for_xy(game_hint, sector_x, sector_y)
                records.append({
                    "sector_index": int(sector_index),
                    "row_index": int(row_index),
                    "sector_x": int(sector_x),
                    "sector_y": int(sector_y),
                    "header_addr": int(header_addr),
                    "cont": int(data_base),
                    "file_size": int(file_size),
                    "data_size": int(data_size),
                    "reloc_tab": int(reloc_tab),
                    "num_relocs": int(num_relocs),
                    "end": int(data_end),
                    "origin": origin,
                    "game_hint": game_hint,
                    "img_header_off": int(img_header_off),
                    "global_rel": int(global_tab),
                    "wrldtool_direct_contimg": bool(used_direct_contimg),
                })
                sector_index += 1
        return records

    def get_pass_pointer_count_for_sector(self, sector_record: Dict[str, int]) -> int:
        img = self.img_bytes
        cont = int(sector_record.get("cont", -1))
        entry_end = int(sector_record.get("end", len(img)))
        game_hint = str(sector_record.get("game_hint", self.detect_sector_game_hint()))
        count = 8 if game_hint == "lcs" else 9
        if cont < 0 or cont + 0x08 + count * 4 > len(img):
            return 0
        ptrs = [read_u32(img, cont + 0x08 + i * 4) for i in range(count)]
        if any(p < 0x20 for p in ptrs):
            return 0
        if any((p & 3) != 0 for p in ptrs):
            return 0
        if any(ptrs[i] > ptrs[i + 1] for i in range(len(ptrs) - 1)):
            return 0
        if any(cont + p - 0x20 > entry_end for p in ptrs):
            return 0
        return count

    def sector_instance_spans(self, sector_record: Dict[str, int]):
        img = self.img_bytes
        cont = int(sector_record.get("cont", -1))
        entry_end = min(len(img), int(sector_record.get("end", len(img))))
        if cont < 0 or cont + 0x30 > len(img) or entry_end <= cont:
            return []
        pass_count = self.get_pass_pointer_count_for_sector(sector_record)
        if pass_count <= 1:
            return []
        pass_ptrs = [read_u32(img, cont + 0x08 + i * 4) for i in range(pass_count)]
        pass_names = IMG_PASS_NAMES_LCS if str(sector_record.get("game_hint", "vcs")) == "lcs" else IMG_PASS_NAMES_VCS
        spans = []
        total_rows = 0
        for pass_index in range(pass_count - 1):
            start_ptr = int(pass_ptrs[pass_index])
            stop_ptr = int(pass_ptrs[pass_index + 1])
            if stop_ptr <= start_ptr:
                continue
            start = max(cont, cont + start_ptr - 0x20)
            stop = min(entry_end, cont + stop_ptr - 0x20)
            if stop <= start:
                continue
            row_count = (stop - start) // 0x50
            if row_count <= 0:
                continue
            total_rows += row_count
            if total_rows > LVZ_MAX_IMG_ROWS_PER_CONTAINER:
                allowed = max(0, LVZ_MAX_IMG_ROWS_PER_CONTAINER - (total_rows - row_count))
                stop = start + allowed * 0x50
            pass_name = pass_names[pass_index] if pass_index < len(pass_names) else f"PASS_{pass_index}"
            spans.append((pass_index, pass_name, start, stop, pass_ptrs))
            if total_rows >= LVZ_MAX_IMG_ROWS_PER_CONTAINER:
                break
        return spans

    def collect_sector_overlay_resources(self, sector_records: Optional[List[Dict[str, int]]] = None, max_resource_id: Optional[int] = None, include_alt_12_layouts: bool = False, wanted_res_ids: Optional[set] = None, progress_callback=None) -> List[Dict[str, int]]:
        img = self.img_bytes
        if sector_records is None:
            sector_records = self.find_sector_container_records_from_lvz()

        wanted = None
        if wanted_res_ids is not None:
            try:
                wanted = {int(x) for x in wanted_res_ids}
            except Exception:
                wanted = None

        overlays: List[Dict[str, int]] = []
        seen = set()
        container_bounds = sorted(set(
            int(record.get("cont", -1))
            for record in (sector_records or [])
            if 0 <= int(record.get("cont", -1)) < len(img)
        ))
        next_container_by_cont: Dict[int, int] = {}
        for bound_index, bound_cont in enumerate(container_bounds):
            next_container_by_cont[int(bound_cont)] = int(container_bounds[bound_index + 1]) if bound_index + 1 < len(container_bounds) else len(img)

        def expanded_container_end(cont: int, declared_end: int) -> int:
            hard_end = int(next_container_by_cont.get(int(cont), len(img)))
            if hard_end <= cont:
                hard_end = len(img)
            declared_end = max(int(declared_end), int(cont))
            return max(int(declared_end), min(len(img), hard_end))

        self.last_overlay_resource_stats = {
            "containers": 0,
            "rows_8_id_ptr": 0,
            "rows_12_ptr_id": 0,
            "rows_12_ptr_mid_id": 0,
            "rows_12_id_unused_ptr": 0,
            "rows_12_id_ptr_unused": 0,
            "accepted": 0,
            "pointer_variants": 0,
            "expanded_bounds": 0,
            "tight_resource_bounds": 0,
        }

        def add_overlay(sector, resource_index: int, res_id: int, raw_ptr: int, raw_off: int, row_off: int, stride: int, layout: str, cont: int, end: int):
            if res_id < 0:
                return
            if wanted is not None and int(res_id) not in wanted:
                return
            if max_resource_id is not None and res_id >= int(max_resource_id):
                return
            if raw_ptr < 0:
                return


            candidates = []
            def push(label, off):
                try:
                    off = int(off)
                except Exception:
                    return
                if off not in [v for _, v in candidates]:
                    candidates.append((label, off))

            push("", int(raw_off))


            if not sector.get("strict_overlay") and wanted is not None and int(res_id) in wanted:
                push(":ptr_cont_minus20", int(cont) + int(raw_ptr) - 0x20)
                push(":ptr_cont", int(cont) + int(raw_ptr))
                push(":ptr_abs", int(raw_ptr))
                push(":ptr_abs_minus20", int(raw_ptr) - 0x20)

            for suffix, cand_off in candidates:
                if raw_ptr < 0x20 and suffix in ("", ":ptr_cont_minus20"):
                    continue
                if cand_off < cont or cand_off + 4 > end:


                    if sector.get("strict_overlay") or not (wanted is not None and int(res_id) in wanted and 0 <= cand_off + 4 <= len(img)):
                        continue
                if cand_off < 0 or cand_off + 4 > len(img):
                    continue
                if (cand_off & 3) != 0:
                    continue

                descriptor_max_end = end
                if not (cont <= cand_off < end):
                    descriptor_max_end = len(img)
                descriptor_off = self.find_mdl_material_list_start_near(cand_off, max_end=descriptor_max_end)
                if descriptor_off is None:
                    continue
                cand_off = int(descriptor_off)

                key = (
                    int(sector.get("sector_index", -1)),
                    int(sector.get("row_index", -1)),
                    int(res_id),
                    int(cand_off),
                    int(stride),
                    str(layout) + str(suffix),
                )
                if key in seen:
                    continue
                seen.add(key)
                overlays.append({
                    "sector_index": int(sector.get("sector_index", -1)),
                    "row_index": int(sector.get("row_index", -1)),
                    "sector_x": int(sector.get("sector_x", 0)),
                    "sector_y": int(sector.get("sector_y", 0)),
                    "cont": cont,
                    "sector_end": max(int(end), int(cand_off) + 4) if int(cand_off) >= int(end) else end,
                    "resource_index": int(resource_index),
                    "res_id": int(res_id),
                    "raw_ptr": int(raw_ptr),
                    "raw_off": int(cand_off),
                    "resource_row_off": int(row_off),
                    "resource_stride": int(stride),
                    "resource_layout": str(layout) + str(suffix),
                })
                self.last_overlay_resource_stats["accepted"] += 1
                if suffix:
                    self.last_overlay_resource_stats["pointer_variants"] += 1

        sector_total = len(sector_records)
        for sector_number, sector in enumerate(sector_records):
            if progress_callback is not None:
                try:
                    progress_callback(sector_number, sector_total)
                except Exception:
                    pass
            cont = int(sector.get("cont", -1))
            declared_end = min(len(img), int(sector.get("end", len(img))))
            end = declared_end if sector.get("strict_overlay") else expanded_container_end(cont, declared_end)
            if end > declared_end:
                self.last_overlay_resource_stats["expanded_bounds"] += 1
            if cont < 0 or cont + 8 > len(img) or end <= cont:
                continue

            resources_ptr = read_u32(img, cont + 0x00)
            num_resources = read_u16(img, cont + 0x04)
            if num_resources <= 0 or num_resources > 4096:
                continue

            list_start = cont + int(resources_ptr) - 0x20
            if list_start < cont or list_start + 8 > end:
                continue

            self.last_overlay_resource_stats["containers"] += 1

            if sector.get('strict_overlay'):
                if resources_ptr < 0x20 or list_start + num_resources * 8 > end:
                    continue
                rows = []
                for resource_index in range(num_resources):
                    row_off = list_start + resource_index * 8
                    res_id, raw_ptr = struct.unpack_from('<II', img, row_off)
                    raw_off = cont + raw_ptr - 0x20
                    if raw_ptr >= 0x20 and cont <= raw_off and raw_off + 4 <= end and raw_off % 4 == 0:
                        rows.append((resource_index, row_off, res_id, raw_ptr, raw_off))
                starts = sorted({row[4] for row in rows})
                for resource_index, row_off, res_id, raw_ptr, raw_off in rows:
                    next_index = bisect_right(starts, raw_off)
                    allocation_end = starts[next_index] if next_index < len(starts) else end
                    add_overlay(sector, resource_index, res_id, raw_ptr, raw_off, row_off,
                                8, 'linked_id_ptr', cont, allocation_end)
                continue


            if list_start + num_resources * 8 <= end:
                for resource_index in range(num_resources):
                    row_off = list_start + resource_index * 8
                    res_id = struct.unpack_from("<i", img, row_off + 0x00)[0]
                    raw_ptr = read_u32(img, row_off + 0x04)
                    before = len(overlays)
                    add_overlay(sector, resource_index, int(res_id), int(raw_ptr), cont + int(raw_ptr) - 0x20, row_off, 8, "id_ptr", cont, end)
                    if len(overlays) != before:
                        self.last_overlay_resource_stats["rows_8_id_ptr"] += 1


            if list_start + num_resources * 12 <= end:
                for resource_index in range(num_resources):
                    row_off = list_start + resource_index * 12
                    a = read_u32(img, row_off + 0x00)
                    b = read_u32(img, row_off + 0x04)
                    c = read_u32(img, row_off + 0x08)

                    before = len(overlays)
                    add_overlay(sector, resource_index, int(c), int(a), cont + int(a) - 0x20, row_off, 12, "ptr_unused_id", cont, end)
                    if len(overlays) != before:
                        self.last_overlay_resource_stats["rows_12_ptr_id"] += 1


                    if include_alt_12_layouts:
                        before = len(overlays)
                        add_overlay(sector, resource_index, int(b), int(a), cont + int(a) - 0x20, row_off, 12, "ptr_id_unused", cont, end)
                        if len(overlays) != before:
                            self.last_overlay_resource_stats["rows_12_ptr_mid_id"] += 1

                        before = len(overlays)
                        add_overlay(sector, resource_index, int(a), int(c), cont + int(c) - 0x20, row_off, 12, "id_unused_ptr", cont, end)
                        if len(overlays) != before:
                            self.last_overlay_resource_stats["rows_12_id_unused_ptr"] += 1

                        before = len(overlays)
                        add_overlay(sector, resource_index, int(a), int(b), cont + int(b) - 0x20, row_off, 12, "id_ptr_unused", cont, end)
                        if len(overlays) != before:
                            self.last_overlay_resource_stats["rows_12_id_ptr_unused"] += 1


        def looks_like_mdl_resource_start_for_bounds(raw_off: int, sector_end: int) -> bool:
            try:
                raw_off = int(raw_off)
                sector_end = min(len(img), int(sector_end))
            except Exception:
                return False
            if raw_off < 0 or raw_off + 8 > sector_end or raw_off + 8 > len(img):
                return False
            if (raw_off & 3) != 0:
                return False
            if img[raw_off:raw_off + 4] in (b"DLRW", b"xet\x00"):
                return False


            if read_u32(img, raw_off) == 0x6C018000:
                return False

            descriptor_off = self.find_mdl_material_list_start_near(raw_off, max_end=sector_end)
            return descriptor_off is not None

        bound_groups: Dict[int, List[Dict[str, int]]] = {}
        for overlay in overlays:
            try:
                cont_key = int(overlay.get("cont", -1))
                raw_off = int(overlay.get("raw_off", -1))
                sector_end = int(overlay.get("sector_end", len(img)))
                if cont_key < 0 or raw_off < 0 or raw_off + 4 > len(img):
                    continue
                if raw_off >= sector_end:
                    continue
                bound_groups.setdefault(cont_key, []).append(overlay)
            except Exception:
                continue

        tight_count = 0
        ignored_bound_starts = 0
        for cont_key, group_overlays in bound_groups.items():
            starts = []
            for overlay in group_overlays:
                try:
                    raw_off = int(overlay.get("raw_off", -1))
                    row_off = int(overlay.get("resource_row_off", -1))
                    layout = str(overlay.get("resource_layout", ""))
                    sector_end = int(overlay.get("sector_end", len(img)))
                    if raw_off >= 0 and raw_off + 4 <= len(img) and raw_off < sector_end:
                        if looks_like_mdl_resource_start_for_bounds(raw_off, sector_end):
                            starts.append((raw_off, row_off, layout))
                        else:
                            ignored_bound_starts += 1
                except Exception:
                    continue
            starts.sort(key=lambda item: (item[0], item[1], item[2]))
            for overlay in group_overlays:
                try:
                    raw_off = int(overlay.get("raw_off", -1))
                    row_off = int(overlay.get("resource_row_off", -1))
                    sector_end = int(overlay.get("sector_end", len(img)))
                    resource_end = sector_end
                    for next_raw, next_row_off, _layout in starts:
                        if next_raw <= raw_off:
                            continue
                        if next_row_off == row_off:
                            continue
                        if next_raw > raw_off + 4:
                            resource_end = min(resource_end, next_raw)
                            break
                    resource_end = max(raw_off + 4, min(resource_end, sector_end, len(img)))
                    overlay["resource_end"] = int(resource_end)
                    if resource_end < sector_end:
                        tight_count += 1
                except Exception:
                    continue

        if tight_count:
            try:
                self.last_overlay_resource_stats["tight_resource_bounds"] = int(tight_count)
            except Exception:
                pass
            try:
                dbg(f"[overlay-bounds] tightened IMG resource parse bounds for {tight_count} overlay rows")
            except Exception:
                pass
        if ignored_bound_starts:
            try:
                self.last_overlay_resource_stats["ignored_non_mdl_bound_starts"] = int(ignored_bound_starts)
            except Exception:
                pass
            try:
                dbg(f"[overlay-bounds] ignored non-MDL/alias resource starts while tightening bounds: {ignored_bound_starts}")
            except Exception:
                pass

        return overlays


    def find_area_info_records_from_lvz(self) -> List[Dict[str, int]]:

        lvz = self.lvz_bytes
        img = self.img_bytes
        if len(lvz) < 0x40 or len(img) < 0x40:
            return []


        pair_offsets = [0x2F0]
        scan_end = min(len(lvz) - 8, 0x500)
        for off in range(0x150, max(0x150, scan_end + 1), 4):
            if off not in pair_offsets:
                pair_offsets.append(off)

        best = []
        best_score = -1
        for pair_off in pair_offsets:
            if pair_off < 0 or pair_off + 8 > len(lvz):
                continue
            count = read_u32(lvz, pair_off)
            table_ptr = read_u32(lvz, pair_off + 4)
            if count <= 0 or count > 1024:
                continue
            if table_ptr < 0x20 or table_ptr + count * 16 > len(lvz):
                continue

            records = []
            valid = 0
            for area_index in range(int(count)):
                row_off = int(table_ptr) + area_index * 16
                try:
                    cell_x, cell_y = struct.unpack_from("<hh", lvz, row_off)
                    file_offset, file_size, declared_resources = struct.unpack_from("<IIi", lvz, row_off + 4)
                except Exception:
                    continue
                if file_offset < 0 or file_size < 0x28 or file_offset + file_size > len(img):
                    continue
                if img[file_offset:file_offset + 4] != b"AERA":
                    continue
                header_file_size = read_u32(img, file_offset + 0x08)
                data_size = read_u32(img, file_offset + 0x0C)
                reloc_tab = read_u32(img, file_offset + 0x10)
                num_relocs = read_u32(img, file_offset + 0x14)
                area_resources = struct.unpack_from("<i", img, file_offset + 0x20)[0]
                resources_ptr = read_u32(img, file_offset + 0x24)
                if area_resources < 0 or area_resources > 4096:
                    continue
                if declared_resources >= 0 and area_resources != declared_resources:


                    if declared_resources > 4096:
                        continue
                resource_table_off = int(file_offset) + int(resources_ptr)
                if resource_table_off < file_offset + 0x20 or resource_table_off + area_resources * 8 > file_offset + file_size:
                    continue
                data_end_rel = int(reloc_tab) if 0x20 <= int(reloc_tab) <= int(file_size) else int(file_size)
                data_end = min(len(img), int(file_offset) + data_end_rel)
                records.append({
                    "area_index": int(area_index),
                    "cell_x": int(cell_x),
                    "cell_y": int(cell_y),
                    "lvz_area_table_off": int(pair_off),
                    "lvz_area_info_off": int(row_off),
                    "file_offset": int(file_offset),
                    "file_size": int(file_size),
                    "header_file_size": int(header_file_size),
                    "data_size": int(data_size),
                    "reloc_tab": int(reloc_tab),
                    "num_relocs": int(num_relocs),
                    "declared_resources": int(declared_resources),
                    "num_resources": int(area_resources),
                    "resources_ptr": int(resources_ptr),
                    "resource_table_off": int(resource_table_off),
                    "data_end": int(data_end),
                })
                valid += 1


            required = min(int(count), 3)
            if valid < required:
                continue
            score = valid * 1000 - abs(int(count) - valid)
            if pair_off == 0x2F0:
                score += 100
            if score > best_score:
                best_score = score
                best = records

        best.sort(key=lambda record: int(record.get("area_index", -1)))
        self.last_area_info_stats = {
            "areas": len(best),
            "table_off": int(best[0].get("lvz_area_table_off", -1)) if best else -1,
            "resource_rows": sum(int(record.get("num_resources", 0)) for record in best),
        }
        return best

    def collect_area_resources(self, area_records: Optional[List[Dict[str, int]]] = None,
                               wanted_res_ids: Optional[set] = None,
                               max_resource_id: Optional[int] = None,
                               progress_callback=None) -> List[Dict[str, int]]:

        img = self.img_bytes
        if area_records is None:
            area_records = self.find_area_info_records_from_lvz()
        wanted = None
        if wanted_res_ids is not None:
            try:
                wanted = {int(value) for value in wanted_res_ids}
            except Exception:
                wanted = None

        results: List[Dict[str, int]] = []
        seen = set()
        stats = {
            "areas": len(area_records or []),
            "rows": 0,
            "wanted_rows": 0,
            "accepted": 0,
            "invalid_pointer": 0,
            "non_geometry": 0,
        }

        total_areas = len(area_records or [])
        for area_number, area in enumerate(area_records or []):
            if progress_callback is not None:
                try:
                    progress_callback(area_number, total_areas)
                except Exception:
                    pass
            area_index = int(area.get("area_index", -1))
            base = int(area.get("file_offset", -1))
            file_size = int(area.get("file_size", 0))
            table_off = int(area.get("resource_table_off", -1))
            count = int(area.get("num_resources", 0))
            data_end = min(len(img), int(area.get("data_end", base + file_size)))
            if base < 0 or table_off < 0 or count <= 0 or data_end <= base + 0x20:
                continue

            rows = []
            payload_offsets = []
            for resource_index in range(count):
                row_off = table_off + resource_index * 8
                if row_off < 0 or row_off + 8 > min(len(img), base + file_size):
                    break
                stats["rows"] += 1
                res_id, secondary_id, raw_ptr = struct.unpack_from("<hhI", img, row_off)
                if res_id < 0:
                    continue
                if max_resource_id is not None and int(res_id) >= int(max_resource_id):
                    continue
                if wanted is not None and int(res_id) not in wanted:
                    continue
                stats["wanted_rows"] += 1
                raw_off = base + int(raw_ptr)
                if raw_ptr < 0x20 or raw_off < base + 0x20 or raw_off + 8 > data_end:
                    stats["invalid_pointer"] += 1
                    continue
                rows.append((resource_index, row_off, int(res_id), int(secondary_id), int(raw_ptr), int(raw_off)))
                payload_offsets.append(int(raw_off))

            unique_payloads = sorted(set(payload_offsets))
            next_payload = {}
            for payload_index, payload_off in enumerate(unique_payloads):
                next_payload[payload_off] = unique_payloads[payload_index + 1] if payload_index + 1 < len(unique_payloads) else data_end

            for resource_index, row_off, res_id, secondary_id, raw_ptr, raw_off in rows:
                resource_end = min(data_end, int(next_payload.get(raw_off, data_end)))
                if resource_end <= raw_off + 8:
                    resource_end = data_end
                descriptor_off = self.find_mdl_material_list_start_near(raw_off, max_end=resource_end)
                if descriptor_off is None and resource_end < data_end:


                    descriptor_off = self.find_mdl_material_list_start_near(raw_off, max_end=data_end)
                    if descriptor_off is not None:
                        resource_end = data_end
                if descriptor_off is None:
                    stats["non_geometry"] += 1
                    continue
                key = (area_index, res_id, int(descriptor_off))
                if key in seen:
                    continue
                seen.add(key)
                results.append({
                    "sector_index": int(-200000 - area_index),
                    "row_index": int(area.get("cell_y", -1)),
                    "sector_x": int(area.get("cell_x", 0)),
                    "sector_y": int(area.get("cell_y", 0)),
                    "area_index": int(area_index),
                    "area_cell_x": int(area.get("cell_x", 0)),
                    "area_cell_y": int(area.get("cell_y", 0)),
                    "cont": int(base),
                    "sector_end": int(data_end),
                    "resource_end": int(resource_end),
                    "resource_index": int(resource_index),
                    "res_id": int(res_id),
                    "secondary_id": int(secondary_id),
                    "raw_ptr": int(raw_ptr),
                    "raw_off": int(descriptor_off),
                    "resource_row_off": int(row_off),
                    "resource_stride": 8,
                    "resource_layout": "area_s16id_s16secondary_ptr",
                    "area_file_size": int(file_size),
                    "area_reloc_tab": int(area.get("reloc_tab", 0)),
                })
                stats["accepted"] += 1

        if progress_callback is not None:
            try:
                progress_callback(total_areas, total_areas)
            except Exception:
                pass
        results.sort(key=lambda row: (int(row.get("area_index", -1)), int(row.get("resource_index", -1))))
        self.last_area_resource_stats = stats
        return results

    def build_area_model_info_map(self, area_records: Optional[List[Dict[str, int]]] = None,
                                  wanted_res_ids: Optional[set] = None,
                                  max_resource_id: Optional[int] = None):

        img = self.img_bytes
        if area_records is None:
            area_records = self.find_area_info_records_from_lvz()
        wanted = None
        if wanted_res_ids is not None:
            try:
                wanted = {int(value) for value in wanted_res_ids}
            except Exception:
                wanted = None

        by_res: Dict[int, int] = {}
        provenance: Dict[int, Dict[str, int]] = {}
        conflicts: Dict[int, set] = {}
        stats = {
            "areas": len(area_records or []),
            "rows": 0,
            "wanted_rows": 0,
            "valid_pointer_rows": 0,
            "mapped_res_ids": 0,
            "conflicting_res_ids": 0,
        }

        for area in area_records or []:
            area_index = int(area.get("area_index", -1))
            base = int(area.get("file_offset", -1))
            file_size = int(area.get("file_size", 0))
            table_off = int(area.get("resource_table_off", -1))
            count = int(area.get("num_resources", 0))
            data_end = min(len(img), int(area.get("data_end", base + file_size)))
            if base < 0 or table_off < 0 or count <= 0 or data_end <= base + 0x20:
                continue
            chunk_end = min(len(img), base + file_size)
            for resource_index in range(count):
                row_off = table_off + resource_index * 8
                if row_off < 0 or row_off + 8 > chunk_end:
                    break
                stats["rows"] += 1
                try:
                    res_id, model_info_id, raw_ptr = struct.unpack_from("<hhI", img, row_off)
                except Exception:
                    continue
                res_id = int(res_id)
                model_info_id = int(model_info_id)
                raw_ptr = int(raw_ptr)
                if res_id < 0 or model_info_id < 0:
                    continue
                if max_resource_id is not None and res_id >= int(max_resource_id):
                    continue
                if wanted is not None and res_id not in wanted:
                    continue
                stats["wanted_rows"] += 1
                raw_off = base + raw_ptr
                if raw_ptr >= 0x20 and raw_off >= base + 0x20 and raw_off < data_end:
                    stats["valid_pointer_rows"] += 1


                previous = by_res.get(res_id)
                if previous is None:
                    by_res[res_id] = model_info_id
                    provenance[res_id] = {
                        "area_index": area_index,
                        "resource_index": int(resource_index),
                        "resource_row_off": int(row_off),
                        "raw_ptr": raw_ptr,
                        "raw_off": int(raw_off),
                        "model_info_id": model_info_id,
                    }
                elif int(previous) != model_info_id:
                    values = conflicts.setdefault(res_id, {int(previous)})
                    values.add(model_info_id)

        for res_id in conflicts:
            by_res.pop(int(res_id), None)
            provenance.pop(int(res_id), None)

        stats["mapped_res_ids"] = len(by_res)
        stats["conflicting_res_ids"] = len(conflicts)
        stats["conflicts"] = {
            int(key): sorted(int(value) for value in values)
            for key, values in conflicts.items()
        }
        self.last_area_model_info_stats = stats
        return by_res, provenance, conflicts


    def enumerate_sector_details(self, max_resource_id: Optional[int] = None, include_lod: bool = False, dedupe_visible: bool = True, progress_callback=None):
        img = self.img_bytes
        details = []
        stats = {
            "sector_records": 0,
            "candidate_rows": 0,
            "valid_rows": 0,
            "kept_rows": 0,
            "skipped_lod_rows": 0,
            "skipped_light_rows": 0,
            "skipped_duplicate_rows": 0,
        }
        seen_keys = set()
        sector_records = self.find_sector_container_records_from_lvz()
        sector_total = len(sector_records)
        stats["sector_records"] = sector_total
        for sector_number, sector in enumerate(sector_records):
            if progress_callback is not None:
                try:
                    progress_callback(sector_number, sector_total)
                except Exception:
                    pass
            cont = int(sector.get("cont", -1))
            origin = tuple(sector.get("origin", (0.0, 0.0, 0.0)))
            sector_index = int(sector.get("sector_index", -1))
            for pass_index, pass_name, start, stop, pass_ptrs in self.sector_instance_spans(sector):
                off = start
                while off + 0x50 <= stop:
                    stats["candidate_rows"] += 1
                    if not looks_like_img_instance_row(img, off, max_resource_id=max_resource_id):
                        off += 0x50
                        continue
                    stats["valid_rows"] += 1
                    ipl_raw = read_u16(img, off + 0x00)
                    ipl_id = int(ipl_raw & 0x7FFF)
                    res_id = read_u16(img, off + 0x02)
                    if (not include_lod) and str(pass_name) in IMG_LOD_PASS_NAMES:
                        stats["skipped_lod_rows"] += 1
                        off += 0x50
                        continue
                    if str(pass_name) in IMG_NON_MODEL_PASS_NAMES:
                        if str(pass_name).upper() == "LIGHTS":
                            stats["skipped_light_rows"] += 1
                        else:
                            stats["skipped_lod_rows"] += 1
                        off += 0x50
                        continue
                    if (not include_lod) and str(pass_name) not in IMG_MODEL_PASS_NAMES_DEFAULT:
                        stats["skipped_lod_rows"] += 1
                        off += 0x50
                        continue
                    sx = half_to_float(read_u16(img, off + 0x04))
                    sy = half_to_float(read_u16(img, off + 0x06))
                    sz = half_to_float(read_u16(img, off + 0x08))
                    sr = half_to_float(read_u16(img, off + 0x0A))
                    m = struct.unpack_from("<16f", img, off + 0x10)


                    dedupe_key = (
                        int(ipl_id), int(res_id), str(pass_name),
                        round(float(sx), 4), round(float(sy), 4),
                        round(float(sz), 4), round(float(sr), 4),
                        round(float(m[0]), 4), round(float(m[1]), 4), round(float(m[2]), 4),
                        round(float(m[4]), 4), round(float(m[5]), 4), round(float(m[6]), 4),
                        round(float(m[8]), 4), round(float(m[9]), 4), round(float(m[10]), 4),
                        round(float(m[12] + origin[0]), 4), round(float(m[13] + origin[1]), 4),
                        round(float(m[14] + origin[2]), 4),
                    )
                    if dedupe_visible and dedupe_key in seen_keys:
                        stats["skipped_duplicate_rows"] += 1
                        off += 0x50
                        continue
                    seen_keys.add(dedupe_key)
                    s0 = math.sqrt(m[0]*m[0] + m[1]*m[1] + m[2]*m[2])
                    s1 = math.sqrt(m[4]*m[4] + m[5]*m[5] + m[6]*m[6])
                    s2 = math.sqrt(m[8]*m[8] + m[9]*m[9] + m[10]*m[10])
                    details.append((
                        int(res_id), cont, off - cont, int(ipl_raw), ipl_id,
                        sx, sy, sz, sr, s0, s1, s2, m,
                        int(pass_index), str(pass_name), sector_index,
                        int(sector.get("sector_x", 0)), int(sector.get("sector_y", 0)), origin,
                        int(sector.get("row_index", -1)),
                    ))
                    stats["kept_rows"] += 1
                    off += 0x50
        if progress_callback is not None:
            try:
                progress_callback(sector_total, sector_total)
            except Exception:
                pass
        details.sort(key=lambda t: (int(t[15]), int(t[13]), int(t[2])))
        self.last_sector_walk_stats = stats
        return details


    def findLinkedWorldContainers(self):
        lvz = self.lvz_bytes
        img = self.img_bytes
        records = []
        seen = set()
        for header in range(0x20, len(lvz) - 0x20 + 1, 4):
            if lvz[header:header + 4] != b'DLRW':
                continue
            size, data_end, reloc, reloc_count, base = struct.unpack_from('<5I', lvz, header + 8)
            if (size < 0x28 or size > 0x04000000 or data_end < 0x20
                    or data_end > size or reloc < data_end
                    or reloc + reloc_count * 4 > size
                    or base + size - 0x20 > len(img)):
                continue
            end = base + data_end - 0x20
            if base in seen or base + 8 > end:
                continue
            pointer = read_u32(img, base)
            count = read_u16(img, base + 4)
            table = base + pointer - 0x20
            if pointer < 0x20 or not 0 < count <= 4096:
                continue
            if table < base or table + count * 8 > end:
                continue
            seen.add(base)
            records.append({
                'lvz_addr': header, 'cont': base, 'total': size,
                'g0': data_end, 'g1': reloc, 'gcnt': reloc_count,
                'end': end, 'tag_u32': read_u32(lvz, header),
                'strict_overlay': True,
            })
        return records

    def find_extra_container_records_from_lvz(self, sector_records: Optional[List[Dict[str, int]]] = None) -> List[Dict[str, int]]:
        img = self.img_bytes
        if sector_records is None:
            sector_records = self.find_sector_container_records_from_lvz()

        sector_header_addrs = set(int(record.get("header_addr", -1)) for record in sector_records)
        sector_conts = set(int(record.get("cont", -1)) for record in sector_records)
        records_by_key: Dict[Tuple[int, int], Dict[str, int]] = {}
        candidates = list(self.findLinkedWorldContainers())
        candidates.extend(self.find_parent_container_records_from_lvz())
        candidates.extend(self.find_nested_container_records_from_lvz())
        game_hint = self.detect_sector_game_hint()

        extra_index = 0
        for candidate in candidates:
            header_addr = int(candidate.get("lvz_addr", -1))
            cont = int(candidate.get("cont", -1))
            total = int(candidate.get("total", 0))
            tag_u32 = int(candidate.get("tag_u32", 0))
            if header_addr in sector_header_addrs:
                continue
            if cont in sector_conts:
                continue
            if cont < 0 or cont >= len(img):
                continue
            if total < 0x20:
                continue
            end = int(candidate.get("end", min(len(img), cont + total - 0x20)))
            if end <= cont + 0x30:
                continue
            key = (header_addr, cont)
            if key in records_by_key or any(record["cont"] == cont for record in records_by_key.values()):
                continue

            group_index = int(candidate.get("group_index", -1))
            child_index = int(candidate.get("child_index", 0))
            group_start_x = int(candidate.get("group_type", 0))
            sector_x = 0
            sector_y = 0
            origin = (0.0, 0.0, 0.0)


            if group_index >= 0 and 0 <= group_start_x < 256 and 0 <= child_index < 4096:
                sector_x = group_start_x + child_index
                sector_y = group_index
                origin = sector_origin_for_xy(game_hint, sector_x, sector_y)

            records_by_key[key] = {
                "sector_index": int(-100000 - extra_index),
                "row_index": int(group_index),
                "sector_x": int(sector_x),
                "sector_y": int(sector_y),
                "header_addr": header_addr,
                "cont": cont,
                "file_size": total,
                "data_size": int(candidate.get("g0", 0)),
                "reloc_tab": int(candidate.get("g1", 0)),
                "num_relocs": int(candidate.get("gcnt", 0)),
                "end": int(end),
                "origin": origin,
                "game_hint": game_hint,
                "extra_container": True,
                "strict_overlay": bool(candidate.get("strict_overlay", False)),
                "extra_tag_u32": tag_u32,
                "extra_group_index": int(group_index),
                "extra_child_index": int(child_index),
            }
            extra_index += 1

        return [records_by_key[key] for key in sorted(records_by_key)]

    def extra_container_instance_spans(self, container_record: Dict[str, int]):
        img = self.img_bytes
        cont = int(container_record.get("cont", -1))
        entry_end = min(len(img), int(container_record.get("end", len(img))))
        if cont < 0 or cont + 0x30 > len(img) or entry_end <= cont:
            return []
        pass_count = self.detect_pass_pointer_count(cont, entry_end)
        if pass_count <= 1:
            return []
        pass_ptrs = [read_u32(img, cont + 0x08 + i * 4) for i in range(pass_count)]


        pass_names = IMG_PASS_NAMES_LCS if str(container_record.get("game_hint", self.detect_sector_game_hint())) == "lcs" else IMG_PASS_NAMES_VCS
        spans = []
        total_rows = 0
        for pass_index in range(pass_count - 1):
            start_ptr = int(pass_ptrs[pass_index])
            stop_ptr = int(pass_ptrs[pass_index + 1])
            if stop_ptr <= start_ptr:
                continue
            start = max(cont, cont + start_ptr - 0x20)
            stop = min(entry_end, cont + stop_ptr - 0x20)
            if stop <= start:
                continue
            row_count = (stop - start) // 0x50
            if row_count <= 0:
                continue
            total_rows += row_count
            if total_rows > LVZ_MAX_IMG_ROWS_PER_CONTAINER:
                allowed = max(0, LVZ_MAX_IMG_ROWS_PER_CONTAINER - (total_rows - row_count))
                stop = start + allowed * 0x50
            pass_name = pass_names[pass_index] if pass_index < len(pass_names) else f"PASS_{pass_index}"
            spans.append((pass_index, pass_name, start, stop, pass_ptrs))
            if total_rows >= LVZ_MAX_IMG_ROWS_PER_CONTAINER:
                break
        return spans

    def enumerate_extra_container_details(self, container_records: Optional[List[Dict[str, int]]] = None, max_resource_id: Optional[int] = None, include_lod: bool = False, progress_callback=None):
        img = self.img_bytes
        details = []
        stats = {
            "container_records": 0,
            "candidate_rows": 0,
            "valid_rows": 0,
            "kept_rows": 0,
            "skipped_lod_rows": 0,
            "skipped_light_rows": 0,
            "nonzero_origin_containers": 0,
        }
        if container_records is None:
            container_records = self.find_extra_container_records_from_lvz()
        stats["container_records"] = len(container_records)
        container_total = len(container_records)
        for container_number, container in enumerate(container_records):
            if progress_callback is not None:
                try:
                    progress_callback(container_number, container_total)
                except Exception:
                    pass
            cont = int(container.get("cont", -1))
            origin = tuple(container.get("origin", (0.0, 0.0, 0.0)))
            if any(abs(float(v)) > 0.0001 for v in origin[:3]):
                stats["nonzero_origin_containers"] += 1
            sector_index = int(container.get("sector_index", -1))
            for pass_index, pass_name, start, stop, pass_ptrs in self.extra_container_instance_spans(container):
                off = start
                while off + 0x50 <= stop:
                    stats["candidate_rows"] += 1
                    if not looks_like_img_instance_row(img, off, max_resource_id=max_resource_id):
                        off += 0x50
                        continue
                    stats["valid_rows"] += 1
                    ipl_raw = read_u16(img, off + 0x00)
                    ipl_id = int(ipl_raw & 0x7FFF)
                    res_id = read_u16(img, off + 0x02)
                    if (not include_lod) and str(pass_name) in IMG_LOD_PASS_NAMES:
                        stats["skipped_lod_rows"] += 1
                        off += 0x50
                        continue
                    if str(pass_name) in IMG_NON_MODEL_PASS_NAMES:
                        if str(pass_name).upper() == "LIGHTS":
                            stats["skipped_light_rows"] += 1
                        else:
                            stats["skipped_lod_rows"] += 1
                        off += 0x50
                        continue
                    if (not include_lod) and str(pass_name) not in IMG_MODEL_PASS_NAMES_DEFAULT:
                        stats["skipped_lod_rows"] += 1
                        off += 0x50
                        continue
                    sx = half_to_float(read_u16(img, off + 0x04))
                    sy = half_to_float(read_u16(img, off + 0x06))
                    sz = half_to_float(read_u16(img, off + 0x08))
                    sr = half_to_float(read_u16(img, off + 0x0A))
                    m = struct.unpack_from("<16f", img, off + 0x10)
                    s0 = math.sqrt(m[0]*m[0] + m[1]*m[1] + m[2]*m[2])
                    s1 = math.sqrt(m[4]*m[4] + m[5]*m[5] + m[6]*m[6])
                    s2 = math.sqrt(m[8]*m[8] + m[9]*m[9] + m[10]*m[10])
                    details.append((
                        int(res_id), cont, off - cont, int(ipl_raw), ipl_id,
                        sx, sy, sz, sr, s0, s1, s2, m,
                        int(pass_index), str(pass_name), sector_index,
                        int(container.get("sector_x", 0)), int(container.get("sector_y", 0)), origin,
                    ))
                    stats["kept_rows"] += 1
                    off += 0x50
        if progress_callback is not None:
            try:
                progress_callback(container_total, container_total)
            except Exception:
                pass
        details.sort(key=lambda t: (int(t[15]), int(t[13]), int(t[2])))
        self.last_extra_container_walk_stats = stats
        return details

    def merge_instance_details(self, *detail_lists):
        merged = []
        seen_source_rows = set()
        seen_visible_rows = set()
        duplicate_source_rows = 0
        duplicate_visible_rows = 0

        for detail_list in detail_lists:
            for detail in detail_list:
                source_key = (int(detail[1]), int(detail[2]), int(detail[3]), int(detail[0]))
                if source_key in seen_source_rows:
                    duplicate_source_rows += 1
                    continue
                seen_source_rows.add(source_key)

                values = detail[12]
                sphere_key = tuple(round(float(value), 4) for value in detail[5:9])
                basis_key = (
                    round(float(values[0]), 4), round(float(values[1]), 4), round(float(values[2]), 4),
                    round(float(values[4]), 4), round(float(values[5]), 4), round(float(values[6]), 4),
                    round(float(values[8]), 4), round(float(values[9]), 4), round(float(values[10]), 4),
                )
                visible_key = (
                    int(detail[4]),
                    int(detail[0]),
                    str(detail[14]),
                    sphere_key,
                    basis_key,
                )
                if visible_key in seen_visible_rows:
                    duplicate_visible_rows += 1
                    continue
                seen_visible_rows.add(visible_key)
                merged.append(detail)

        merged.sort(key=lambda t: (int(t[15]), int(t[13]), int(t[1]), int(t[2])))
        self.last_merge_instance_stats = {
            "source_rows": sum(len(detail_list) for detail_list in detail_lists),
            "duplicate_source_rows": int(duplicate_source_rows),
            "duplicate_visible_rows": int(duplicate_visible_rows),
            "kept_rows": len(merged),
        }
        return merged

    def write_sector_csvs(self, lvz_path: str, details, enable_unique: bool):
        all_rows = [(int(d[1]), int(d[2]), int(d[3]), int(d[4]), int(d[0])) for d in details]
        out_csv = str(Path(lvz_path).with_suffix("")) + "_all_res_ids.csv"
        try:
            with open(out_csv, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["index", "sector", "sector_x", "sector_y", "pass", "cont_hex", "off_hex", "ipl_raw", "ipl_id", "res_id"])
                for i, d in enumerate(details):
                    w.writerow([i, int(d[15]), int(d[16]), int(d[17]), str(d[14]), f"0x{int(d[1]):08X}", f"0x{int(d[2]):08X}", f"0x{int(d[3]):04X}", int(d[4]), int(d[0])])
            dbg(f"[ids] wrote {len(details)} filtered visible rows → {out_csv}")
        except Exception as e:
            dbg(f"[ids] failed to write CSV: {e}")
        if enable_unique:
            try:
                out_csv_unique = str(Path(lvz_path).with_suffix("")) + "_all_res_ids_unique.csv"
                seen = set()
                unique_details = []
                for d in details:
                    key = (int(d[15]), int(d[13]), int(d[4]), int(d[0]))
                    if key in seen:
                        continue
                    seen.add(key)
                    unique_details.append(d)
                with open(out_csv_unique, "w", newline="", encoding="utf-8") as f2:
                    w2 = csv.writer(f2)
                    w2.writerow(["index", "sector", "sector_x", "sector_y", "pass", "cont_hex", "off_hex", "ipl_raw", "ipl_id", "res_id"])
                    for i, d in enumerate(unique_details):
                        w2.writerow([i, int(d[15]), int(d[16]), int(d[17]), str(d[14]), f"0x{int(d[1]):08X}", f"0x{int(d[2]):08X}", f"0x{int(d[3]):04X}", int(d[4]), int(d[0])])
                dbg(f"[ids] wrote {len(unique_details)} unique filtered rows → {out_csv_unique}")
            except Exception as e:
                dbg(f"[ids] failed to write UNIQUE CSV: {e}")
        return all_rows

    def build_sector_transforms_map_and_log(self, details, enable_unique_log: bool) -> Dict[int, Matrix]:
        transforms_by_res: Dict[int, Matrix] = {}
        if not enable_unique_log:
            for d in details:
                res_id = int(d[0])
                if res_id not in transforms_by_res:
                    transforms_by_res[res_id] = matrix_from_16_floats_row_major_values_with_origin(d[12], d[18])
            return transforms_by_res
        seen = set()
        kept = 0
        dbg("— UNIQUE VISIBLE RES IDs: pass + sector + xyzr + scales + matrix + world pos —")
        for d in details:
            res_id, cont, rel_off, ipl_raw, ipl_id, sx, sy, sz, sr, s0, s1, s2, m = d[:13]
            if res_id in seen:
                continue
            seen.add(res_id)
            kept += 1
            origin = d[18]
            posx, posy, posz = (m[12] + origin[0], m[13] + origin[1], m[14] + origin[2])
            dbg(f"  RES={res_id} sector={int(d[15])} xy=({int(d[16])},{int(d[17])}) pass={d[14]} @ IMG+0x{cont:08X}+0x{rel_off:08X}  IPLraw=0x{ipl_raw:04X}  IPLid={ipl_id}")
            dbg(f"     sphere=({sx:.6f},{sy:.6f},{sz:.6f}, r={sr:.6f}) scale=({s0:.6f},{s1:.6f},{s2:.6f}) sector_origin=({origin[0]:.6f},{origin[1]:.6f},{origin[2]:.6f})")
            dbg(f"     pos=({posx:.6f},{posy:.6f},{posz:.6f})")
            transforms_by_res[res_id] = matrix_from_16_floats_row_major_values_with_origin(m, origin)
        dbg(f"[ids] unique visible printed: {kept}")
        return transforms_by_res

    def find_parent_container_records_from_lvz(self) -> List[Dict[str, int]]:
        lvz = self.lvz_bytes
        n = len(lvz)
        records: List[Dict[str, int]] = []
        if n < 0x24 or lvz[:4] != b"DLRW":
            return records

        cursor = 0x24
        group_index = 0
        while cursor + 8 <= n:
            group_addr = read_u32(lvz, cursor + 0)
            group_type = read_u32(lvz, cursor + 4)
            if not (0 < group_addr < n and (group_addr & 0x3) == 0 and group_addr + 0x20 <= n):
                break
            tag = lvz[group_addr:group_addr + 4]
            if tag not in (b"DLRW", b"xet\0"):
                break

            total = read_u32(lvz, group_addr + 0x08)
            global_rel = read_u32(lvz, group_addr + 0x18)
            data_base, data_end, img_header_off, used_direct_contimg = self.img_data_base_for_lvz_dlrw_header(group_addr, global_rel, total)
            records.append({
                "group_index": group_index,
                "group_type": int(group_type),
                "child_index": 0,
                "lvz_addr": int(group_addr),
                "tag_u32": read_u32(lvz, group_addr + 0x00),
                "wrld_type": read_u32(lvz, group_addr + 0x04),
                "total": int(total),
                "g0": read_u32(lvz, group_addr + 0x0C),
                "g1": read_u32(lvz, group_addr + 0x10),
                "gcnt": read_u32(lvz, group_addr + 0x14),
                "cont": int(data_base),
                "end": int(data_end),
                "img_header_off": int(img_header_off),
                "global_rel": int(global_rel),
                "wrldtool_direct_contimg": bool(used_direct_contimg),
            })
            group_index += 1
            cursor += 8
        return records

    def find_nested_container_records_from_lvz(self) -> List[Dict[str, int]]:

        lvz = self.lvz_bytes
        n = len(lvz)
        records: List[Dict[str, int]] = []
        for parent in self.find_parent_container_records_from_lvz():
            group_addr = int(parent["lvz_addr"])
            group_type = int(parent["group_type"])
            group_count = int(parent.get("gcnt", 0))
            if group_count <= 0 or group_count > LVZ_MAX_RESOURCE_ROWS:
                group_count = 1
            for child_index in range(group_count):
                child_addr = group_addr + (child_index * 0x20)
                if child_addr + 0x20 > n:
                    break
                child_tag = lvz[child_addr:child_addr + 4]
                if child_tag not in (b"DLRW", b"xet\0"):
                    break
                total = read_u32(lvz, child_addr + 0x08)
                global_rel = read_u32(lvz, child_addr + 0x18)
                data_base, data_end, img_header_off, used_direct_contimg = self.img_data_base_for_lvz_dlrw_header(child_addr, global_rel, total)
                records.append({
                    "group_index": int(parent["group_index"]),
                    "group_type": group_type,
                    "child_index": child_index,
                    "lvz_addr": int(child_addr),
                    "tag_u32": read_u32(lvz, child_addr + 0x00),
                    "wrld_type": read_u32(lvz, child_addr + 0x04),
                    "total": int(total),
                    "g0": read_u32(lvz, child_addr + 0x0C),
                    "g1": read_u32(lvz, child_addr + 0x10),
                    "gcnt": read_u32(lvz, child_addr + 0x14),
                    "cont": int(data_base),
                    "end": int(data_end),
                    "img_header_off": int(img_header_off),
                    "global_rel": int(global_rel),
                    "wrldtool_direct_contimg": bool(used_direct_contimg),
                })
        return records

    def find_top_level_container_records_from_lvz(self) -> List[Dict[str, int]]:
        return self.find_parent_container_records_from_lvz()

    def find_top_level_conts_from_lvz(self) -> List[int]:
        records = self.find_parent_container_records_from_lvz()
        return sorted(set(int(record["cont"]) for record in records))

    def detect_platform_from_lvz_groups(self) -> str:
        records = self.find_parent_container_records_from_lvz()
        group_types = sorted(set(int(record.get("group_type", 0)) for record in records))
        nonzero = [value for value in group_types if value != 0]
        if any(value >= 0x0D for value in nonzero):
            return "PS2"
        if any(value in (0x02, 0x03) for value in nonzero):
            return "PSP"
        return "PS2"

    def find_conts(self) -> List[int]:

        conts = self.find_top_level_conts_from_lvz()
        if conts:
            if self.is_ver2_archive:
                conts = [c for c in conts if find_ver2_entry_for_abs_offset(self.ver2_entries, c) is not None]
            else:
                conts = [c for c in conts if 0 <= c < len(self.img_bytes)]
            if 0 not in conts and not self.is_ver2_archive:
                conts = [0] + conts
            return sorted(set(conts))

        if self.is_ver2_archive:
            return []
        return [0] if self.img_bytes else []

    def build_cont_next_map(self, conts: List[int]) -> Dict[int, Optional[int]]:
        ordered = sorted(set(int(c) for c in conts if c is not None))
        out: Dict[int, Optional[int]] = {}
        for i, cont in enumerate(ordered):
            out[cont] = ordered[i + 1] if i + 1 < len(ordered) else None
        return out

    def detect_pass_pointer_count(self, cont: int, entry_end: int) -> int:
        img = self.img_bytes

        candidates = []
        for count in (9, 8):
            if cont + 0x08 + count * 4 > len(img):
                continue
            ptrs = [read_u32(img, cont + 0x08 + i * 4) for i in range(count)]
            if any(p < 0x20 for p in ptrs):
                continue
            if any((p & 3) != 0 for p in ptrs):
                continue
            if any(ptrs[i] > ptrs[i + 1] for i in range(len(ptrs) - 1)):
                continue
            if any(cont + p - 0x20 > entry_end for p in ptrs):
                continue
            span_bytes = max(0, ptrs[-1] - ptrs[0])
            if span_bytes > 0 and span_bytes % 0x10 == 0:
                candidates.append((count, ptrs))
        if not candidates:
            return 0
        return candidates[0][0]

    def imgInstanceSpans(self, cont: int, next_cont: Optional[int] = None):
        img = self.img_bytes
        if cont < 0 or cont + 0x30 > len(img):
            return []
        entry_end = len(img)
        if next_cont is not None and next_cont > cont:
            entry_end = min(entry_end, int(next_cont))
        if self.is_ver2_archive:
            entry = find_ver2_entry_for_abs_offset(self.ver2_entries, cont)
            if entry is None:
                return []
            entry_end = min(entry_end, int(entry["end"]))

        pass_count = self.detect_pass_pointer_count(cont, entry_end)
        if pass_count <= 1:
            return []
        pass_ptrs = [read_u32(img, cont + 0x08 + i * 4) for i in range(pass_count)]
        spans = []
        total_rows = 0
        for pass_index in range(pass_count - 1):
            start_ptr = int(pass_ptrs[pass_index])
            stop_ptr = int(pass_ptrs[pass_index + 1])
            if stop_ptr <= start_ptr:
                continue
            start = cont + start_ptr - 0x20
            stop = cont + stop_ptr - 0x20
            start = max(cont, start)
            stop = min(stop, entry_end)
            if stop <= start:
                continue
            row_count = (stop - start) // 0x50
            if row_count <= 0:
                continue
            total_rows += row_count
            if total_rows > LVZ_MAX_IMG_ROWS_PER_CONTAINER:
                dbg(
                    f"[img] WARNING: container 0x{cont:08X} declares too many instance rows; "
                    f"clamping to {LVZ_MAX_IMG_ROWS_PER_CONTAINER}"
                )
                allowed = max(0, LVZ_MAX_IMG_ROWS_PER_CONTAINER - (total_rows - row_count))
                stop = start + allowed * 0x50
            spans.append((pass_index, start, stop, pass_ptrs))
            if total_rows >= LVZ_MAX_IMG_ROWS_PER_CONTAINER:
                break
        return spans

    def imgSkySpan(self, cont: int, next_cont: Optional[int] = None):
        spans = self.imgInstanceSpans(cont, next_cont)
        if not spans:
            return None
        start = min(span[1] for span in spans)
        stop = max(span[2] for span in spans)
        return (start, stop, spans[0][3])

    def enumerate_all_rows(self, conts: List[int], max_resource_id: Optional[int] = None):
        rows: List[Tuple[int,int,int,int,int]] = []
        ENTRY = 0x50
        img = self.img_bytes
        next_by_cont = self.build_cont_next_map(conts)
        for cont in conts:
            spans = self.imgInstanceSpans(cont, next_by_cont.get(cont))
            for pass_index, start, stop, pass_ptrs in spans:
                off = start
                while off + ENTRY <= stop:
                    if looks_like_img_instance_row(img, off, max_resource_id=max_resource_id):
                        ipl_raw = read_u16(img, off + 0x00)
                        res_id  = read_u16(img, off + 0x02)
                        rows.append((cont, off - cont, ipl_raw, (ipl_raw & 0x7FFF), res_id))
                    off += ENTRY
        rows.sort(key=lambda t: (t[0], t[1]))
        return rows

    def enumerate_details(self, conts: List[int], max_resource_id: Optional[int] = None):
        rows = []
        ENTRY = 0x50
        img = self.img_bytes
        next_by_cont = self.build_cont_next_map(conts)
        for cont in conts:
            spans = self.imgInstanceSpans(cont, next_by_cont.get(cont))
            for pass_index, start, stop, pass_ptrs in spans:
                off = start
                while off + ENTRY <= stop:
                    if not looks_like_img_instance_row(img, off, max_resource_id=max_resource_id):
                        off += ENTRY
                        continue
                    ipl_raw = read_u16(img, off + 0x00)
                    ipl_id  = (ipl_raw & 0x7FFF)
                    res_id  = read_u16(img, off + 0x02)
                    sx = half_to_float(read_u16(img, off + 0x04))
                    sy = half_to_float(read_u16(img, off + 0x06))
                    sz = half_to_float(read_u16(img, off + 0x08))
                    sr = half_to_float(read_u16(img, off + 0x0A))
                    m  = struct.unpack_from("<16f", img, off + 0x10)
                    s0 = math.sqrt(m[0]*m[0] + m[1]*m[1] + m[2]*m[2])
                    s1 = math.sqrt(m[4]*m[4] + m[5]*m[5] + m[6]*m[6])
                    s2 = math.sqrt(m[8]*m[8] + m[9]*m[9] + m[10]*m[10])
                    rows.append((res_id, cont, off - cont, ipl_raw, ipl_id, sx, sy, sz, sr, s0, s1, s2, m))
                    off += ENTRY
        rows.sort(key=lambda t: (t[1], t[2]))
        return rows

    def write_csvs(self, lvz_path: str, all_rows, unique_rows, enable_unique: bool):
        out_csv = str(Path(lvz_path).with_suffix("")) + "_all_res_ids.csv"
        try:
            with open(out_csv, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["index","cont_hex","off_hex","ipl_raw","ipl_id","res_id"])
                for i,(cont, rel_off, ipl_raw, ipl_id, res_id) in enumerate(all_rows):
                    w.writerow([i, f"0x{cont:08X}", f"0x{rel_off:08X}", f"0x{ipl_raw:04X}", ipl_id, res_id])
            dbg(f"[ids] wrote {len(all_rows)} rows → {out_csv}")
        except Exception as e:
            dbg(f"[ids] failed to write CSV: {e}")

        if enable_unique:
            try:
                out_csv_unique = str(Path(lvz_path).with_suffix("")) + "_all_res_ids_unique.csv"
                with open(out_csv_unique, "w", newline="", encoding="utf-8") as f2:
                    w2 = csv.writer(f2)
                    w2.writerow(["index","cont_hex","off_hex","ipl_raw","ipl_id","res_id"])
                    for i,(cont, rel_off, ipl_raw, ipl_id, res_id) in enumerate(unique_rows):
                        w2.writerow([i, f"0x{cont:08X}", f"0x{rel_off:08X}", f"0x{ipl_raw:04X}", ipl_id, res_id])
                dbg(f"[ids] wrote {len(unique_rows)} unique rows → {out_csv_unique}")
            except Exception as e:
                dbg(f"[ids] failed to write UNIQUE CSV: {e}")

    def build_transforms_map_and_log(self, details, enable_unique_log: bool) -> Dict[int, Matrix]:
        transforms_by_res: Dict[int, Matrix] = {}
        if not enable_unique_log:
            seen = set()
            for (res_id, cont, rel_off, ipl_raw, ipl_id, sx, sy, sz, sr, s0, s1, s2, m) in details:
                if res_id in seen:
                    continue
                seen.add(res_id)
                transforms_by_res[res_id] = matrix_from_16_floats_row_major_values(m)
            return transforms_by_res

        seen_res = set()
        kept = 0
        dbg("— UNIQUE RES IDs: xyzr + scales + matrix + pos —")
        for (res_id, cont, rel_off, ipl_raw, ipl_id, sx, sy, sz, sr, s0, s1, s2, m) in details:
            if res_id in seen_res:
                continue
            seen_res.add(res_id)
            kept += 1
            posx, posy, posz = (m[12], m[13], m[14])
            dbg(f"  RES={res_id} @ IMG+0x{cont:08X}+0x{rel_off:08X}  IPLraw=0x{ipl_raw:04X}  IPLid={ipl_id}")
            dbg(f"     sphere=({sx:.6f},{sy:.6f},{sz:.6f}, r={sr:.6f}) scale=({s0:.6f},{s1:.6f},{s2:.6f})")
            dbg(f"     mat=[[{m[0]:.6f},{m[1]:.6f},{m[2]:.6f},{m[3]:.6f}],")
            dbg(f"          [{m[4]:.6f},{m[5]:.6f},{m[6]:.6f},{m[7]:.6f}],")
            dbg(f"          [{m[8]:.6f},{m[9]:.6f},{m[10]:.6f},{m[11]:.6f}],")
            dbg(f"          [{m[12]:.6f},{m[13]:.6f},{m[14]:.6f},{m[15]:.6f}]]")
            dbg(f"     pos=({posx:.6f},{posy:.6f},{posz:.6f})")

            transforms_by_res[res_id] = matrix_from_16_floats_row_major_values(m)
        dbg(f"[ids] unique printed: {kept}")
        return transforms_by_res
