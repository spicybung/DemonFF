# DemonFF - Scripts for working with R* Leeds (GTA Stories, Chinatown Wars, Manhunt 2, etc) formats in Blender
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

import os
import struct
import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Any, Optional, Iterable

from mathutils import Matrix, Vector

#   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #
#   This script is for Stories .MDLs, the file format for actors & props            #
#   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #   #
# - Script resources:
# • https://gtamods.com/wiki/Relocatable_chunk (pre-process)
# • https://gtamods.com/wiki/Leeds_Engine (TODO: update stub)
# • https://gtamods.com/wiki/MDL (TODO: update stub with more documentation in own words)
# • https://github.com/aap/librwgta (*re'd RW/Leeds Engine source by The_Hero*)
# • https://github.com/aap/librwgta/blob/master/tools/storiesconv/rsl.h (ditto)
# • https://github.com/aap/librwgta/blob/master/tools/storiesconv/rslconv.cpp (ditto)
# • https://web.archive.org/web/20180712151513/http://gtamodding.ru/wiki/MDL (*Russian*)
# • https://web.archive.org/web/20180712151513/http://gtamodding.ru/wiki/MDL_importer (*ditto - by Alex/AK73 & good resource to start*)
# • https://web.archive.org/web/20180714005051/https://www.gtamodding.ru/wiki/GTA_Stories_RAW_Editor (ditto)
# • https://web-archive-org.translate.goog/web/20180712151513/http://gtamodding.ru/wiki/MDL?_x_tr_sl=ru&_x_tr_tl=en&_x_tr_hl=en (*English*)
# • https://web-archive-org.translate.goog/web/20180725082416/http://gtamodding.ru/wiki/MDL_importer?_x_tr_sl=ru&_x_tr_tl=en&_x_tr_hl=en (by Alex/AK73 - good resource to start w/out any other documentation)
# - Mod resources/cool stuff:
# • https://developer.valvesoftware.com/wiki/MDL_(Quake) (Rockstar Leeds MDL is loosely based on Quake MDL)
# • https://libertycity.net/files/gta-liberty-city-stories/48612-yet-another-img-editor.html (GTA3xx .img: .mdls, textures, animations)
# • https://gtaforums.com/topic/838537-lcsvcs-dir-files/
# • https://gtaforums.com/topic/285544-gtavcslcs-modding/
# • https://thegtaplace.com/forums/topic/12002-gtavcslcs-modding/
# • http://aap.papnet.eu/gta/RE/lcs_pipes.txt (a brief binary example of how bitflags work for PS2/PSP/Mobile Stories games)
# • https://libertycity.net/articles/gta-vice-city-stories/6773-how-one-of-the-best-grand-theft-auto.html
# • https://umdatabase.net/view.php?id=CB00495D (database collection of Grand Theft Auto prototypes)
# • https://www.ign.com/articles/2005/09/10/gta-liberty-city-stories-2 ( ...it's IGN, but old IGN at least)
# • https://lcsteam.net/community/forum/index.php/topic,337.msg9335.html#msg9335 (RW 3.7/4.0, .MDL's, .WRLD's, .BSP's... )
# • https://www.gamedeveloper.com/programming/opinion-why-on-earth-would-we-write-our-own-game-engine- (Renderwares fate)
# • https://vkvideo.ru/playlist/-76377865_3/video143954957_456239182?linked=1 ( *Russian* - VCS PSP MDL viewer by Daniil Sayanov)

try:
    from ..data.bone_data import (
        commonBoneOrder,
        commonBoneNamesLCS,
        kamBoneID,
        kamFrameName,
        kamBoneType,
        kamBoneIndex,
        commonBoneParentsLCS,
        commonBoneOrderVCS,
        commonBoneNamesVCS,
        kamBoneIDVCS,
        kamFrameNameVCS,
        kamBoneTypeVCS,
        kamBoneIndexVCS,
        commonBoneParentsVCS,
    )
except Exception:
    from BLeeds.data.bone_data import (
        commonBoneOrder,
        commonBoneNamesLCS,
        kamBoneID,
        kamFrameName,
        kamBoneType,
        kamBoneIndex,
        commonBoneParentsLCS,
        commonBoneOrderVCS,
        commonBoneNamesVCS,
        kamBoneIDVCS,
        kamFrameNameVCS,
        kamBoneTypeVCS,
        kamBoneIndexVCS,
        commonBoneParentsVCS,
    )
# Bone arrays and shared PED hierarchy constants live in BLeeds/data/bone_data.py.

#######################################################
# === Model Rendering Flags ===

FLAG_DRAWLAST: int = 0x4 | 0x8
FLAG_ADDITIVE: int = 0x8
FLAG_NO_ZWRITE: int = 0x40
FLAG_NO_SHADOWS: int = 0x80
FLAG_NO_BACKFACE_CULLING: int = 0x200000

@dataclass
class StripSkinData:
    indices: List[int]
    weights: List[float]

@dataclass
class StripMeta:
    base_vertex_index: int
    vertex_count: int
    skin_indices: List[List[int]] = field(default_factory=list)
    skin_weights: List[List[float]] = field(default_factory=list)
    skin_raw_dwords: List[List[int]] = field(default_factory=list)

@dataclass
class StoriesPartGeom:
    verts: List[Tuple[float, float, float]] = field(default_factory=list)
    faces: List[Tuple[int, int, int]] = field(default_factory=list)
    uvs: List[Tuple[float,float]] = field(default_factory=list)
    strips_meta: List[StripMeta] = field(default_factory=list)
    vertex_colors: List[Any] = field(default_factory=list)
    loop_colors: List[Any] = field(default_factory=list)
    material_id: int = 0
    uv_scale: Tuple[float, float] = (1.0, 1.0)
    geom_flags: int = 0
    strip_vertex_count_hint: int = 0
    bbox_i16: List[int] = field(default_factory=list)
    sphere: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    raw_part_header_offset: int = 0

@dataclass
class StoriesMaterialDesc:
    offset: int = 0
    texture: str = ""
    rgba: int = 0
    specular: float = 0.0

@dataclass
class StoriesPSPMesh:
    index: int
    verts: List[Tuple[float, float, float]] = field(default_factory=list)
    faces: List[Tuple[int, int, int]] = field(default_factory=list)
    uvs: List[Tuple[float, float]] = field(default_factory=list)
    colors: List[Tuple[int, int, int, int]] = field(default_factory=list)
    normals: List[Tuple[float, float, float]] = field(default_factory=list)
    bone_indices: List[List[int]] = field(default_factory=list)
    bone_weights: List[List[float]] = field(default_factory=list)
    mat_id: int = 0
    uv_scale: Tuple[float, float] = (1.0, 1.0)
    bonemap: List[int] = field(default_factory=list)

@dataclass
class StoriesArmatureInfo:
    frame_mats_local: Dict[int, Matrix] = field(default_factory=dict)
    frame_mats_world: Dict[int, Matrix] = field(default_factory=dict)
    frame_mats_global: Dict[int, Matrix] = field(default_factory=dict)
    frame_mats_computed_world: Dict[int, Matrix] = field(default_factory=dict)
    frame_matrix_local_offsets: Dict[int, int] = field(default_factory=dict)
    frame_matrix_global_offsets: Dict[int, int] = field(default_factory=dict)
    frame_parent_ptrs: Dict[int, int] = field(default_factory=dict)
    frame_child_ptrs: Dict[int, int] = field(default_factory=dict)
    frame_sibling_ptrs: Dict[int, int] = field(default_factory=dict)
    frame_root_ptrs: Dict[int, int] = field(default_factory=dict)
    frame_tags: Dict[int, int] = field(default_factory=dict)
    frame_field_9c: Dict[int, int] = field(default_factory=dict)
    frame_field_a0: Dict[int, int] = field(default_factory=dict)
    frame_field_a4: Dict[int, int] = field(default_factory=dict)
    frame_names: Dict[int, str] = field(default_factory=dict)
    root_frame_ptr: int = 0

@dataclass
class StoriesGeometryInfo:
    part_offsets: List[int] = field(default_factory=list)
    part_material_ids: List[int] = field(default_factory=list)

    ped_part_table_entries: List[Dict[str, Any]] = field(default_factory=list)
    x_scale: float = 1.0
    y_scale: float = 1.0
    z_scale: float = 1.0
    translation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    materials: List[StoriesMaterialDesc] = field(default_factory=list)
    parts: List[StoriesPartGeom] = field(default_factory=list)
    leeds_global_header: Optional[Dict[str, Any]] = None
    leeds_part_headers: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class StoriesPSPGeometryInfo:
    flags: int = 0
    num_strips: int = 0
    num_verts: int = 0
    scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    pos: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    uv_format: int = 0
    col_format: int = 0
    norm_format: int = 0
    pos_format: int = 0
    weight_format: int = 0
    index_format: int = 0
    num_weights_per_vertex: int = 0
    materials: List[StoriesMaterialDesc] = field(default_factory=list)
    meshes: List[StoriesPSPMesh] = field(default_factory=list)

@dataclass
class StoriesAtomicInfo:
    atomic_offset: int = 0
    atomic_list_link_offset: int = 0
    atomic_source: str = ""
    section_type: int = 0
    import_type: int = 0
    frame_ptr: int = 0
    geom_ptr: int = 0
    material_ptr: int = 0
    render_cb: int = 0
    model_info_id: int = 0
    vis_id_flag: int = 0
    hierarchy_ptr: int = 0
    armature: StoriesArmatureInfo = field(default_factory=StoriesArmatureInfo)
    ps2_geometry: StoriesGeometryInfo = field(default_factory=StoriesGeometryInfo)
    psp_geometry: StoriesPSPGeometryInfo = field(default_factory=StoriesPSPGeometryInfo)

@dataclass
class StoriesMDLContext:
    filepath: str
    platform: str
    mdl_type: str
    shrink: int = 0
    file_len: int = 0
    local_num_table: int = 0
    global_num_table: int = 0
    num_entries: int = 0
    ptr2_before_tex: int = 0
    allocated_memory: int = 0
    top_level_ptr: int = 0
    clump_ptr: int = 0
    clump_root_frame_ptr: int = 0
    clump_first_atomic_ptr: int = 0
    clump_last_atomic_ptr: int = 0
    inline_clump_header: bool = False
    section_type: int = 0
    import_type: int = 0
    actor_mdl: bool = False
    renderflags_offset: int = 0
    debug_log: List[str] = field(default_factory=list)
    atomic: StoriesAtomicInfo = field(default_factory=StoriesAtomicInfo)
    atomics: List[StoriesAtomicInfo] = field(default_factory=list)
    vehicle_extra_count: int = 0
    vehicle_extra_array_ptr: int = 0
    vehicle_primary_material_ptrs: List[int] = field(default_factory=list)
    vehicle_secondary_material_ptrs: List[int] = field(default_factory=list)
    root_names: Tuple[str, ...] = ("dummy",)

    def log(self, msg: str) -> None:
        self.debug_log.append(str(msg))
        print(msg)

def read_i8(f) -> int:
    return struct.unpack("<b", f.read(1))[0]

def read_u8(f) -> int:
    return struct.unpack("<B", f.read(1))[0]

def read_i16(f) -> int:
    return struct.unpack("<h", f.read(2))[0]

def read_u16(f) -> int:
    return struct.unpack("<H", f.read(2))[0]

def read_i32(f) -> int:
    return struct.unpack("<i", f.read(4))[0]

def read_u32(f) -> int:
    return struct.unpack("<I", f.read(4))[0]

def read_bu32(f) -> int:
    return struct.unpack(">I", f.read(4))[0]

def read_f32(f) -> float:
    return struct.unpack("<f", f.read(4))[0]

def read_string(f, ptr: int) -> str:
    if ptr == 0:
        return ""
    current = f.tell()
    f.seek(ptr)
    s = bytearray()
    while True:
        c = f.read(1)
        if c == b"\x00" or c == b"":
            break
        s += c
    f.seek(current)
    return s.decode("utf-8", errors="ignore")

def read_point3(f) -> Vector:
    return Vector(struct.unpack("<3f", f.read(12)))

def read_local_matrix(f) -> Tuple[Matrix, int, Tuple[Vector, Vector, Vector, Vector]]:
    matrix_offset = f.tell()

    row1 = read_point3(f)
    f.read(4)
    row2 = read_point3(f)
    f.read(4)
    row3 = read_point3(f)
    f.read(4)
    row4 = read_point3(f)
    f.read(4)

    scale_factor = 1.0
    x = row4.x * scale_factor
    y = row4.y * scale_factor
    z = row4.z * scale_factor
    row4_scaled = Vector((x, y, z))

    mat = Matrix(
        (
            (row1.x, row2.x, row3.x, row4_scaled.x),
            (row1.y, row2.y, row3.y, row4_scaled.y),
            (row1.z, row2.z, row3.z, row4_scaled.z),
            (0.0, 0.0, 0.0, 1.0),
        )
    )
    return mat, matrix_offset, (row1, row2, row3, row4_scaled)

def read_global_matrix(f, offset: int) -> Matrix:
    cur = f.tell()
    f.seek(offset)

    row1 = read_point3(f)
    f.read(4)
    row2 = read_point3(f)
    f.read(4)
    row3 = read_point3(f)
    f.read(4)
    row4 = read_point3(f)
    f.read(4)

    f.seek(cur)

    scale_factor = 1.0
    x = row4.x * scale_factor
    y = row4.y * scale_factor
    z = row4.z * scale_factor
    row4_scaled = Vector((x, y, z))

    M = Matrix(
        (
            (row1.x, row2.x, row3.x, row4_scaled.x),
            (row1.y, row2.y, row3.y, row4_scaled.y),
            (row1.z, row2.z, row3.z, row4_scaled.z),
            (0.0, 0.0, 0.0, 1.0),
        )
    )
    return M

def is_usable_frame_matrix(matrix_value: Any) -> bool:
    try:
        mat = Matrix(matrix_value)
        basis_total = 0.0
        for row in range(3):
            for col in range(3):
                basis_total += abs(float(mat[row][col]))
        return basis_total > 0.000001
    except Exception:
        return False

def canon_frame_name(name: str) -> str:
    if not isinstance(name, str):
        return ""

    s = name.lower().replace("~", "_").replace(" ", "_")

    return "".join(ch for ch in s if ch.isalnum())

def get_render_flag_names(render_flags: int) -> List[str]:
    names: List[str] = []
    if render_flags & FLAG_DRAWLAST:
        names.append("FLAG_DRAWLAST")
    if render_flags & FLAG_ADDITIVE:
        names.append("FLAG_ADDITIVE")
    if render_flags & FLAG_NO_ZWRITE:
        names.append("FLAG_NO_ZWRITE")
    if render_flags & FLAG_NO_SHADOWS:
        names.append("FLAG_NO_SHADOWS")
    if render_flags & FLAG_NO_BACKFACE_CULLING:
        names.append("FLAG_NO_BACKFACE_CULLING")
    if not names:
        names.append("No known render flags set")
    return names

def process_frame_tree(ctx: StoriesMDLContext, f, frame_ptr: int) -> StoriesArmatureInfo:
    arm = StoriesArmatureInfo()
    if frame_ptr == 0:
        return arm

    arm.root_frame_ptr = frame_ptr

    def _walk(ptr: int, parent_world: Matrix) -> None:
        if ptr == 0:
            return

        f.seek(ptr)
        frame_tag = read_u32(f)

        if ctx.platform == "PS2":
            name_ptr_offset = ptr + 0xA4
        else:
            name_ptr_offset = ptr + 0xA8
        if ctx.import_type == 2:
            name_ptr_offset += 4

        f.seek(name_ptr_offset)
        bone_name_ptr = read_u32(f)
        if bone_name_ptr != 0:
            cur = f.tell()
            f.seek(bone_name_ptr)
            name_bytes = bytearray()
            while True:
                b = f.read(1)
                if b == b"\x00" or not b:
                    break
                name_bytes.append(b[0])
            bone_name = name_bytes.decode("utf-8", errors="ignore")
            f.seek(cur)
        else:
            bone_name = "Bone"

        f.seek(ptr + 0x04)
        parent_ptr = read_u32(f)

        local_offset = ptr + 0x10
        f.seek(local_offset)
        local_mat, local_matrix_offset, _ = read_local_matrix(f)

        computed_world_mat = parent_world @ local_mat
        global_offset = ptr + 0x50
        global_mat = read_global_matrix(f, global_offset)
        if is_usable_frame_matrix(global_mat):
            world_mat = global_mat
            world_source = "imported_global_0x50"
        else:
            world_mat = computed_world_mat
            world_source = "computed_parent_local"

        arm.frame_mats_local[ptr] = local_mat
        arm.frame_mats_world[ptr] = world_mat
        arm.frame_mats_global[ptr] = global_mat
        arm.frame_mats_computed_world[ptr] = computed_world_mat
        arm.frame_matrix_local_offsets[ptr] = int(local_matrix_offset)
        arm.frame_matrix_global_offsets[ptr] = int(global_offset)
        arm.frame_parent_ptrs[ptr] = int(parent_ptr)
        arm.frame_names[ptr] = bone_name

        ctx.log(
            f"Frame 0x{ptr:X}: name='{bone_name}', local={local_mat}, computed_world={computed_world_mat}, imported_global={global_mat}, chosen_world={world_source}"
        )

        f.seek(ptr + 0x90)
        child_ptr = read_u32(f)
        f.seek(ptr + 0x94)
        sibling_ptr = read_u32(f)
        arm.frame_child_ptrs[ptr] = int(child_ptr)
        arm.frame_sibling_ptrs[ptr] = int(sibling_ptr)
        arm.frame_tags[ptr] = int(frame_tag) & 0xFFFFFFFF
        try:
            f.seek(ptr + 0x98)
            arm.frame_root_ptrs[ptr] = int(read_u32(f))
            arm.frame_field_9c[ptr] = int(read_u32(f))
            arm.frame_field_a0[ptr] = int(read_u32(f))
            arm.frame_field_a4[ptr] = int(read_u32(f))
        except Exception:
            arm.frame_root_ptrs[ptr] = 0
            arm.frame_field_9c[ptr] = 0
            arm.frame_field_a0[ptr] = 0
            arm.frame_field_a4[ptr] = 0

        if child_ptr != 0:
            _walk(child_ptr, world_mat)
        if sibling_ptr != 0:
            _walk(sibling_ptr, parent_world)

    _walk(frame_ptr, Matrix.Identity(4))
    return arm

def mergeArmatureInfo(dst: StoriesArmatureInfo, src: StoriesArmatureInfo) -> StoriesArmatureInfo:
    if dst is None:
        return src
    if src is None:
        return dst

    for attr_name in (
        "frame_mats_local",
        "frame_mats_world",
        "frame_mats_global",
        "frame_mats_computed_world",
        "frame_matrix_local_offsets",
        "frame_matrix_global_offsets",
        "frame_parent_ptrs",
        "frame_child_ptrs",
        "frame_sibling_ptrs",
        "frame_root_ptrs",
        "frame_tags",
        "frame_field_9c",
        "frame_field_a0",
        "frame_field_a4",
        "frame_names",
    ):
        try:
            getattr(dst, attr_name).update(getattr(src, attr_name, {}) or {})
        except Exception:
            pass

    if not int(getattr(dst, "root_frame_ptr", 0) or 0):
        dst.root_frame_ptr = int(getattr(src, "root_frame_ptr", 0) or 0)
    if not int(getattr(dst, "hierarchy_count", 0) or 0):
        dst.hierarchy_count = int(getattr(src, "hierarchy_count", 0) or 0)
        dst.hierarchy_entries_ptr = int(getattr(src, "hierarchy_entries_ptr", 0) or 0)
        dst.hierarchy_anchor_ptr = int(getattr(src, "hierarchy_anchor_ptr", 0) or 0)
        dst.hierarchy_entries = list(getattr(src, "hierarchy_entries", []) or [])
    return dst

def readAtomicHeaderAt(ctx: StoriesMDLContext, f, atomic_start: int, source: str = "") -> StoriesAtomicInfo:
    old_pos = f.tell()
    try:
        f.seek(int(atomic_start), 0)
        atomic_info = StoriesAtomicInfo()
        atomic_info.atomic_offset = int(atomic_start)
        atomic_info.atomic_list_link_offset = int(atomic_start) + 0x1C
        atomic_info.atomic_source = str(source or "")
        atomic_info.section_type = 2
        atomic_info.import_type = int(getattr(ctx, "import_type", 0) or 0)
        atomic_info.section_type_id = read_u32(f)
        atomic_info.frame_ptr = read_u32(f)
        atomic_info.frame_cycle_next = read_u32(f)
        atomic_info.frame_cycle_prev = read_u32(f)
        atomic_info.unknown_10 = read_u32(f)
        atomic_info.geom_ptr = read_u32(f)
        atomic_info.clump_ptr = read_u32(f)
        atomic_info.clump_cycle_next = read_u32(f)
        atomic_info.clump_cycle_prev = read_u32(f)
        atomic_info.render_cb = read_u32(f)
        atomic_info.model_info_id = struct.unpack("<h", f.read(2))[0]
        atomic_info.vis_id_flag = struct.unpack("<H", f.read(2))[0]
        atomic_info.hierarchy_ptr = read_u32(f)
        try:
            atomic_info.tail = read_u32(f)
        except Exception:
            atomic_info.tail = 0
        return atomic_info
    finally:
        try:
            f.seek(old_pos, 0)
        except Exception:
            pass

def discoverVehicleAtomicOffsets(ctx: StoriesMDLContext, f) -> List[Tuple[int, str, int]]:
    offsets: List[Tuple[int, str, int]] = []
    seen = set()
    file_len = int(getattr(ctx, "file_len", 0) or 0)
    clump_ptr = int(getattr(ctx, "clump_ptr", 0) or 0)
    list_head = clump_ptr + 0x08 if clump_ptr else 0
    current_link = int(getattr(ctx, "clump_first_atomic_ptr", 0) or 0)

    def add_atomic(atomic_start: int, source: str, link_offset: int) -> None:
        atomic_start = int(atomic_start or 0)
        if atomic_start <= 0 or atomic_start in seen:
            return
        if file_len and (atomic_start < 0 or atomic_start + 0x34 > file_len):
            return
        old_pos = f.tell()
        try:
            f.seek(atomic_start, 0)
            magic = read_u32(f)
        except Exception:
            return
        finally:
            try:
                f.seek(old_pos, 0)
            except Exception:
                pass
        if magic not in (0x01050001, 0x01000001, 0x0004AA01, 0x0000AA01, 0x00041601, 0x01F40400):
            return
        seen.add(atomic_start)
        offsets.append((atomic_start, source, int(link_offset or (atomic_start + 0x1C))))

    for _ in range(512):
        if not current_link or current_link == list_head or current_link in seen:
            break
        atomic_start = int(current_link) - 0x1C
        add_atomic(atomic_start, "clump", int(current_link))
        old_pos = f.tell()
        try:
            f.seek(atomic_start + 0x1C, 0)
            next_link = read_u32(f)
        except Exception:
            next_link = 0
        finally:
            try:
                f.seek(old_pos, 0)
            except Exception:
                pass
        if not next_link or next_link == current_link:
            break
        current_link = int(next_link)

    extra_count = int(getattr(ctx, "vehicle_extra_count", 0) or 0)
    extra_array = int(getattr(ctx, "vehicle_extra_array_ptr", 0) or 0)
    if extra_count > 0 and extra_array > 0 and (not file_len or extra_array + extra_count * 4 <= file_len):
        old_pos = f.tell()
        try:
            for extra_index in range(min(extra_count, 128)):
                f.seek(extra_array + extra_index * 4, 0)
                extra_atomic = read_u32(f)
                add_atomic(extra_atomic, f"extra{extra_index + 1}", extra_atomic + 0x1C)
        finally:
            try:
                f.seek(old_pos, 0)
            except Exception:
                pass

    return offsets

def readVehicleAtomics(ctx: StoriesMDLContext, f, shared_arm: StoriesArmatureInfo) -> List[StoriesAtomicInfo]:
    atomics: List[StoriesAtomicInfo] = []
    offsets = discoverVehicleAtomicOffsets(ctx, f)
    ctx.log(f"VehicleModel: discovered {len(offsets)} atomic(s) from clump/extras.")

    arm = shared_arm
    if arm is None:
        arm = StoriesArmatureInfo()

    for atomic_index, (atomic_start, source, link_offset) in enumerate(offsets):
        try:
            atomic_info = readAtomicHeaderAt(ctx, f, atomic_start, source=source)
            atomic_info.atomic_list_link_offset = int(link_offset)

            if atomic_info.frame_ptr and atomic_info.frame_ptr not in getattr(arm, "frame_names", {}):
                try:
                    extra_arm = process_frame_tree(ctx, f, int(atomic_info.frame_ptr))
                    arm = mergeArmatureInfo(arm, extra_arm)
                except Exception as frame_error:
                    ctx.log(
                        f"VehicleModel: failed to parse standalone frame 0x{atomic_info.frame_ptr:X} "
                        f"for atomic {atomic_index}: {frame_error}"
                    )

            atomic_info.armature = arm
            if int(atomic_info.geom_ptr or 0) > 0:
                atomic_info.ps2_geometry = read_ps2_geometry(ctx, f, int(atomic_info.geom_ptr))
            atomics.append(atomic_info)

            frame_name = ""
            try:
                frame_name = str(arm.frame_names.get(int(atomic_info.frame_ptr), ""))
            except Exception:
                frame_name = ""
            ctx.log(
                f"VehicleModel atomic[{atomic_index:02d}] {source}: atomic=0x{atomic_start:X} "
                f"frame=0x{int(atomic_info.frame_ptr):X} {frame_name!r} geom=0x{int(atomic_info.geom_ptr):X} "
                f"render_cb=0x{int(atomic_info.render_cb):X} parts={len(getattr(atomic_info.ps2_geometry, 'parts', []) or [])}"
            )
        except Exception as atomic_error:
            ctx.log(f"VehicleModel: failed to parse atomic at 0x{int(atomic_start):X}: {atomic_error}")

    for atomic_info in atomics:
        atomic_info.armature = arm
    return atomics

def walkFramePointersFromArmature(arm: StoriesArmatureInfo, anchor_ptr: int) -> List[int]:
    order: List[int] = []
    seen = set()

    def walk(ptr: int) -> None:
        ptr = int(ptr or 0)
        if ptr == 0 or ptr in seen:
            return
        seen.add(ptr)
        if ptr in arm.frame_names:
            order.append(ptr)
        child_ptr = int(arm.frame_child_ptrs.get(ptr, 0) or 0)
        sibling_ptr = int(arm.frame_sibling_ptrs.get(ptr, 0) or 0)
        if child_ptr:
            walk(child_ptr)
        if sibling_ptr:
            walk(sibling_ptr)

    walk(int(anchor_ptr or 0))
    return order

def parse_hierarchy_table(ctx: StoriesMDLContext, f, hierarchy_ptr: int, arm: StoriesArmatureInfo) -> None:
    hierarchy_ptr = int(hierarchy_ptr or 0)
    if hierarchy_ptr <= 0:
        return

    file_len = int(getattr(ctx, "file_len", 0) or 0)
    if file_len and hierarchy_ptr + 0x38 > file_len:
        ctx.log(f"⚠ Hierarchy pointer 0x{hierarchy_ptr:X} is outside file; skipped hierarchy table parse.")
        return

    old_pos = f.tell()
    try:
        f.seek(hierarchy_ptr)
        tag = read_u32(f)
        count = read_u32(f)
        if tag != 0x00003000 or count <= 0 or count > 512:
            ctx.log(f"⚠ Hierarchy header at 0x{hierarchy_ptr:X} is not a valid RslTAnim table: tag=0x{tag:X}, count={count}.")
            return

        f.seek(hierarchy_ptr + 0x30)
        entries_ptr = read_u32(f)
        anchor_ptr = read_u32(f)

        if not (0 < entries_ptr < file_len if file_len else entries_ptr > 0):

            f.seek(hierarchy_ptr + 0x20)
            alt_entries_ptr = read_u32(f)
            alt_anchor_ptr = read_u32(f)
            if alt_entries_ptr > 0 and (not file_len or alt_entries_ptr < file_len):
                entries_ptr = alt_entries_ptr
                if alt_anchor_ptr > 0:
                    anchor_ptr = alt_anchor_ptr

        if not (0 < entries_ptr and (not file_len or entries_ptr + count * 8 <= file_len)):
            ctx.log(f"⚠ Hierarchy entry table pointer 0x{entries_ptr:X} is invalid; skipped hierarchy table parse.")
            return

        traversal = walkFramePointersFromArmature(arm, anchor_ptr)
        entries: List[Dict[str, Any]] = []

        f.seek(entries_ptr)
        for entry_index in range(int(count)):
            packed = read_u32(f)
            zero = read_u32(f)
            bone_id = int(packed & 0xFF)
            node_index = int((packed >> 8) & 0xFF)
            bone_type = int((packed >> 16) & 0xFF)
            flag = int((packed >> 24) & 0xFF)
            frame_ptr = int(traversal[node_index]) if node_index < len(traversal) else 0
            frame_name = str(arm.frame_names.get(frame_ptr, f"bone_{node_index:02d}")) if frame_ptr else f"bone_{node_index:02d}"
            entries.append({
                "entry_index": int(entry_index),
                "packed": int(packed) & 0xFFFFFFFF,
                "zero": int(zero) & 0xFFFFFFFF,
                "bone_id": bone_id,
                "node_index": node_index,
                "bone_type": bone_type,
                "flag": flag,
                "frame_ptr": frame_ptr,
                "frame_name": frame_name,
            })

        arm.hierarchy_count = int(count)
        arm.hierarchy_entries_ptr = int(entries_ptr)
        arm.hierarchy_anchor_ptr = int(anchor_ptr)
        arm.hierarchy_entries = entries

        ctx.log(f"Hierarchy header: 0x{hierarchy_ptr:X}")
        ctx.log(f"  hierarchy_tag:   0x{tag:X}")
        ctx.log(f"  hierarchy_count: {count}")
        ctx.log(f"  entries_ptr:     0x{entries_ptr:X}")
        ctx.log(f"  anchor_frame:    0x{anchor_ptr:X}")
        for entry in entries[:80]:
            ctx.log(
                "  hierarchy[{entry_index:02d}] packed=0x{packed:08X} "
                "bone_id={bone_id:3d} node_index={node_index:3d} "
                "bone_type={bone_type:2d} flag=0x{flag:02X} -> {frame_name} @ 0x{frame_ptr:X}".format(**entry)
            )
        if len(entries) > 80:
            ctx.log(f"  ... {len(entries) - 80} more hierarchy entries omitted from console log")
    finally:
        try:
            f.seek(old_pos)
        except Exception:
            pass

def read_material_list(ctx: StoriesMDLContext, f) -> List[StoriesMaterialDesc]:
    mats: List[StoriesMaterialDesc] = []

    file_len = int(getattr(ctx, "file_len", 0) or 0)
    ptr2_before_tex = int(getattr(ctx, "ptr2_before_tex", 0) or 0)

    try:
        _ = read_u32(f)
        _ = read_u32(f)
        _ = read_u32(f)
        material_list_ptr = read_u32(f)
        material_count = read_u32(f)
    except struct.error:
        ctx.log("⚠ Material list header is truncated; skipping material decode.")
        return mats

    ctx.log(f"🧵 Material List Ptr: 0x{material_list_ptr:X}")
    ctx.log(f"🎨 Material Count: {material_count}")

    if material_count <= 0:
        return mats

    if material_count > 2048:
        ctx.log(f"⚠ Material count {material_count} looks invalid; skipping material decode.")
        return mats

    if file_len and (material_list_ptr <= 0 or material_list_ptr >= file_len):
        ctx.log(
            f"⚠ Material list ptr 0x{material_list_ptr:X} is outside file (len=0x{file_len:X}); skipping material decode."
        )
        return mats

    old_pos = f.tell()
    f.seek(material_list_ptr)

    for i in range(material_count):
        entry_pos = f.tell()
        if file_len and (entry_pos + 4 > file_len):
            ctx.log(
                f"⚠ Material pointer table truncated at entry {i + 1} (0x{entry_pos:X}); stopping material decode."
            )
            break

        ctx.log(f"  ↪ Reading Material {i + 1}/{material_count}")
        cur_mat = StoriesMaterialDesc()
        cur_mat.offset = entry_pos

        try:
            cur_mat_ptr = read_u32(f)
        except struct.error:
            ctx.log(
                f"⚠ Could not read material pointer for entry {i + 1} at 0x{entry_pos:X}; stopping material decode."
            )
            break

        ctx.log(f"    ⤷ Material Ptr: 0x{cur_mat_ptr:X}")
        old_mat_pos = f.tell()

        if ptr2_before_tex and cur_mat_ptr >= ptr2_before_tex:
            ctx.log(
                f"    ⚠ Material ptr 0x{cur_mat_ptr:X} points into/after texture-name zone (Ptr2BeforeTexNameList=0x{ptr2_before_tex:X}); stopping material decode."
            )
            break

        if file_len and (cur_mat_ptr <= 0 or cur_mat_ptr + 0x10 > file_len):
            ctx.log(
                f"    ⚠ Material ptr 0x{cur_mat_ptr:X} is out of range for a material struct; stopping material decode."
            )
            break

        try:
            f.seek(cur_mat_ptr)

            tex_ptr = read_u32(f)
            ctx.log(f"    ⤷ Texture Ptr: 0x{tex_ptr:X}")
            if tex_ptr > 0 and (not file_len or tex_ptr < file_len):
                temp_pos = f.tell()
                try:
                    f.seek(tex_ptr)
                    tex_name = read_string(f, tex_ptr)
                    cur_mat.texture = tex_name
                    ctx.log(f"    🎯 Texture Name: {tex_name}")
                except Exception as _tex_err:
                    ctx.log(f"    ⚠ Failed to read texture name at 0x{tex_ptr:X}: {_tex_err}")
                finally:
                    f.seek(temp_pos)

            rgba = read_u32(f)
            cur_mat.rgba = rgba
            ctx.log(f"    🎨 RGBA Value: 0x{rgba:08X}")

            _ = read_u32(f)

            spec_ptr = read_u32(f)
            ctx.log(f"    ⤷ Specular Ptr: 0x{spec_ptr:X}")
            if spec_ptr > 0 and (not file_len or (spec_ptr + 12) <= file_len):
                temp_pos = f.tell()
                try:
                    f.seek(spec_ptr)
                    _ = read_u32(f)
                    _ = read_u32(f)
                    spec_val = read_f32(f)
                    cur_mat.specular = spec_val
                    ctx.log(f"    ✨ Specular: {spec_val:.6f}")
                except struct.error:
                    ctx.log(f"    ⚠ Specular block at 0x{spec_ptr:X} is truncated; ignoring.")
                finally:
                    f.seek(temp_pos)

            mats.append(cur_mat)

        except struct.error as _mat_err:
            ctx.log(
                f"    ⚠ Truncated material struct for entry {i + 1} at ptr 0x{cur_mat_ptr:X}: {_mat_err}. Stopping material decode."
            )
            break
        finally:
            f.seek(old_mat_pos)

    f.seek(old_pos)
    return mats

def read_ps2_geometry(ctx: StoriesMDLContext, f, geom_ptr: int) -> StoriesGeometryInfo:
    g = StoriesGeometryInfo()
    ctx.log("Detected Section Type: 3 (Geometry, PS2)")

    def try_parse_leeds_geometry_headers() -> None:
        try:
            cur_pos = f.tell()
            f.seek(0, 2)
            file_end = f.tell()
            f.seek(cur_pos, 0)

            preamble_off = int(geom_ptr)
            global_off = preamble_off + 0x20
            if global_off + 0x40 > file_end:
                return

            f.seek(global_off, 0)
            raw_global = f.read(0x40)
            if len(raw_global) != 0x40:
                return

            sphere_x, sphere_y, sphere_z, sphere_r = struct.unpack_from("<4f", raw_global, 0x00)
            packed_size_and_material_count = struct.unpack_from("<I", raw_global, 0x10)[0]
            vertex_section_flags = struct.unpack_from("<I", raw_global, 0x14)[0]
            total_vertex_count = struct.unpack_from("<H", raw_global, 0x18)[0]
            first_tristrip_rel_off = struct.unpack_from("<H", raw_global, 0x1A)[0]
            bbox_i16 = list(struct.unpack_from("<6h", raw_global, 0x1C))
            sx, sy, sz = struct.unpack_from("<3f", raw_global, 0x28)
            tx, ty, tz = struct.unpack_from("<3f", raw_global, 0x34)

            mat_count = (packed_size_and_material_count >> 20) & 0xFFF
            geom_size_low20 = packed_size_and_material_count & 0x000FFFFF
            if mat_count == 0 or mat_count > 512 or first_tristrip_rel_off == 0:
                return

            g.leeds_global_header = {
                "sphere": [float(sphere_x), float(sphere_y), float(sphere_z), float(sphere_r)],
                "packed_size_and_material_count": int(packed_size_and_material_count),
                "geometry_size_bytes": int(geom_size_low20),
                "material_count": int(mat_count),
                "vertex_section_flags": int(vertex_section_flags),
                "total_vertex_count": int(total_vertex_count),
                "first_tristrip_offset": int(first_tristrip_rel_off),
                "bbox_i16": [int(v) for v in bbox_i16],
                "scale": [float(sx), float(sy), float(sz)],
                "translation": [float(tx), float(ty), float(tz)],
                "raw_offset": int(global_off),
            }

            g.x_scale = float(sx)
            g.y_scale = float(sy)
            g.z_scale = float(sz)
            g.translation = (float(tx), float(ty), float(tz))

            part_table_off = global_off + 0x40
            g.leeds_part_headers = []
            for part_index in range(mat_count):
                entry_off = part_table_off + (part_index * 0x30)
                if entry_off + 0x30 > file_end:
                    break
                f.seek(entry_off, 0)
                raw_part = f.read(0x30)
                if len(raw_part) != 0x30:
                    break
                psx, psy, psz, psr = struct.unpack_from("<4f", raw_part, 0x00)
                uv_u = struct.unpack_from("<f", raw_part, 0x10)[0]
                uv_v = struct.unpack_from("<f", raw_part, 0x14)[0]
                flags = struct.unpack_from("<I", raw_part, 0x18)[0]
                strip_rel = struct.unpack_from("<I", raw_part, 0x1C)[0]
                strip_vert_count = struct.unpack_from("<H", raw_part, 0x20)[0]
                tex_id = struct.unpack_from("<H", raw_part, 0x22)[0]
                part_bbox_i16 = list(struct.unpack_from("<6h", raw_part, 0x24))
                g.leeds_part_headers.append({
                    "index": int(part_index),
                    "sphere": [float(psx), float(psy), float(psz), float(psr)],
                    "uv_scale_u": float(uv_u),
                    "uv_scale_v": float(uv_v),
                    "flags": int(flags),
                    "strip_offset": int(strip_rel),
                    "strip_vertex_count": int(strip_vert_count),
                    "tex_id": int(tex_id),
                    "bbox_i16": [int(v) for v in part_bbox_i16],
                    "raw_offset": int(entry_off),
                })

            ctx.log(f"✔ Parsed Leeds geometry headers: materials={mat_count}, totalVerts={total_vertex_count}, firstTriStripOff=0x{first_tristrip_rel_off:X}")
            ctx.log(f"✔ Leeds global scale/translation from header: scale=({g.x_scale}, {g.y_scale}, {g.z_scale}) translation={g.translation}")
        except Exception as e:
            ctx.log(f"⚠ Leeds geometry header parse failed: {e}")
        finally:
            try:
                f.seek(geom_ptr, 0)
            except Exception:
                pass

    try_parse_leeds_geometry_headers()

    f.seek(geom_ptr)

    g.materials = read_material_list(ctx, f)

    for i in range(13):
        f.read(4)
    ctx.log("✔ Skipped 13 DWORDs")

    xscale_offset = f.tell()
    g.x_scale = read_f32(f)
    yscale_offset = f.tell()
    g.y_scale = read_f32(f)
    zscale_offset = f.tell()
    g.z_scale = read_f32(f)
    ctx.log(f"🟧 xScale is at file offset: 0x{xscale_offset:X}")
    ctx.log(f"🟧 yScale is at file offset: 0x{yscale_offset - 4:X}")
    ctx.log(f"🟧 zScale is at file offset: 0x{zscale_offset - 4:X}")
    ctx.log(f"✔ xScale: {g.x_scale}, yScale: {g.y_scale}, zScale: {g.z_scale}")

    scale_factor = 100.0

    global_scale = scale_factor * 0.00000030518203134641490805874367518203

    offset_x = f.tell()
    tx = read_f32(f) * scale_factor / 100.0
    ctx.log(f"✔ TranslationFactor X read at file offset: 0x{offset_x:X} ({offset_x})")

    offset_y = f.tell()
    ty = read_f32(f) * scale_factor / 100.0
    ctx.log(f"✔ TranslationFactor Y read at file offset: 0x{offset_y:X} ({offset_y})")

    offset_z = f.tell()
    tz = read_f32(f) * scale_factor / 100.0
    ctx.log(f"✔ TranslationFactor Z read at file offset: 0x{offset_z:X} ({offset_z})")

    g.translation = (tx, ty, tz)
    ctx.log(f"✔ TranslationFactor: {g.translation}")

    part_offsets: List[int] = []
    part_material_ids: List[int] = []

    part_table_seek = f.tell()

    prop_offsets_from_table = None
    prop_geo_start = None

    peek_bytes = f.read(4)
    marker_val = struct.unpack_from("<I", peek_bytes)[0] if len(peek_bytes) == 4 else 0

    mdl_type_u = (str(getattr(ctx, "mdl_type", "") or "")).upper().strip()

    if (marker_val & 0xFF000000) == 0x60000000:
        has_part_table = False

    elif mdl_type_u == "PED":
        has_part_table = True

    else:

        part_count_hint = len(g.materials) if g.materials else 0
        has_part_table = True

        if part_count_hint > 0:
            f.seek(part_table_seek)
            offs = [read_u32(f) for _ in range(part_count_hint)]

            monotonic = (offs[0] == 0) and all(offs[i] <= offs[i + 1] for i in range(len(offs) - 1))
            sane = all(o < 0x400000 for o in offs)

            found_dma = None
            scan_base = part_table_seek
            max_scan = 0x800
            for i in range(0, max_scan, 4):
                f.seek(scan_base + i)
                buf = f.read(4)
                if len(buf) < 4:
                    break
                v = struct.unpack_from("<I", buf)[0]
                if (v & 0xFF000000) == 0x60000000:
                    found_dma = scan_base + i
                    break

            if monotonic and sane and found_dma is not None:

                has_part_table = False
                prop_offsets_from_table = offs
                prop_geo_start = found_dma

    f.seek(part_table_seek)

    if has_part_table:

        ctx.log("✔ Detected explicit part table (ped/clump). Reading part offsets...")

        temp = read_u32(f)
        ped_entries: List[Dict[str, Any]] = []
        while True:
            if (temp & 0x60000000) == 0x60000000:

                break

            entry_unknown0 = int(temp) & 0xFFFFFFFF
            entry_unknowns = [read_u32(f) for _ in range(6)]
            temp_offset = read_u32(f)
            part_offsets.append(temp_offset)
            _short1 = read_u16(f)
            temp_mat = read_u16(f)
            part_material_ids.append(temp_mat)
            tail3 = [read_u32(f), read_u32(f), read_u32(f)]

            ped_entries.append({
                "entry_unknown0": entry_unknown0,
                "entry_unknowns": [int(x) & 0xFFFFFFFF for x in entry_unknowns],
                "part_offset": int(temp_offset) & 0xFFFFFFFF,
                "entry_unknown_short": int(_short1) & 0xFFFF,
                "tex_id": int(temp_mat) & 0xFFFF,
                "entry_trailing": [int(x) & 0xFFFFFFFF for x in tail3],
            })

            temp = read_u32(f)

        f.seek(-4, 1)

        geo_start = f.tell()
        g.part_offsets = part_offsets
        g.part_material_ids = part_material_ids
        g.ped_part_table_entries = ped_entries
        ctx.log(f"✔ partOffsets: {part_offsets}")
        ctx.log(f"✔ partMaterials: {part_material_ids}")
        ctx.log(f"geoStart: 0x{geo_start:X}")
    else:

        if prop_offsets_from_table is not None and prop_geo_start is not None:
            part_offsets = list(prop_offsets_from_table)
            part_material_ids = list(range(len(part_offsets)))
            geo_start = int(prop_geo_start)

            g.part_offsets = part_offsets
            g.part_material_ids = part_material_ids

            ctx.log("✔ Detected prop offset table (u32 offsets).")
            ctx.log(f"✔ partOffsets: {part_offsets}")
            ctx.log(f"✔ partMaterials: {part_material_ids}")
            ctx.log(f"geoStart: 0x{geo_start:X}")

            f.seek(geo_start, 0)
        else:

            part_count = len(g.materials) if g.materials else 0

            scan_base = f.tell()
            initial_offset = 0
            found = False

            search_limit = 0x100
            for i in range(search_limit):
                f.seek(scan_base + i)
                buf = f.read(4)
                if len(buf) < 4:
                    break
                marker_val = struct.unpack_from("<I", buf)[0]
                if (marker_val & 0xFF000000) == 0x60000000:
                    initial_offset = i
                    found = True
                    break
            if found:
                dma_tag_pos = scan_base + initial_offset
                geo_start_tmp = dma_tag_pos - 4
                offset_acc = 4
                for p in range(part_count):
                    part_offsets.append(offset_acc)
                    part_material_ids.append(p)
                    f.seek(geo_start_tmp + offset_acc)
                    tag_buf = f.read(4)
                    if len(tag_buf) < 4:
                        break
                    tag_val = struct.unpack_from("<I", tag_buf)[0]
                    qwc = tag_val & 0xFFFF
                    seg_size = (qwc * 16) + 16
                    offset_acc += seg_size
            else:
                for p in range(part_count):
                    part_offsets.append(0)
                    part_material_ids.append(p)

            dma_tag_pos = scan_base + initial_offset
            geo_start = dma_tag_pos - 4
            f.seek(geo_start, 0)
            g.part_offsets = part_offsets
            g.part_material_ids = part_material_ids
            ctx.log(f"✔ partOffsets: {part_offsets}")
            ctx.log(f"✔ partMaterials: {part_material_ids}")
            ctx.log(f"geoStart: 0x{geo_start:X}")

        if g.part_offsets:
            ctx.log("====== Geometry dmaPacket Offsets ======")
            for i, po in enumerate(g.part_offsets):
                ctx.log(f"Part {i + 1}: dmaPacket offset 0x{(geo_start + po):X}")
            ctx.log("===================================")

    if part_offsets:
        _saved_pos = f.tell()
        f.seek(0, 2)
        _file_size = f.tell()
        f.seek(_saved_pos, 0)

        _filtered_offsets: List[int] = []
        _filtered_mats: List[int] = []
        for _idx, _off in enumerate(part_offsets):
            try:
                _off_i = int(_off)
            except Exception:
                ctx.log(f"⚠ Dropping non-integer part offset at index {_idx}: {_off!r}")
                continue

            _abs = int(geo_start) + _off_i
            if _off_i < 0 or _abs < 0 or _abs >= _file_size:
                ctx.log(
                    f"⚠ Dropping invalid part offset[{_idx}] = 0x{_off_i:X} (abs 0x{_abs:X}, file_end 0x{_file_size:X})"
                )
                continue

            if _filtered_offsets and _off_i < _filtered_offsets[-1]:
                ctx.log(
                    f"⚠ Dropping non-monotonic part offset[{_idx}] = 0x{_off_i:X} (< previous 0x{_filtered_offsets[-1]:X})"
                )
                continue

            _filtered_offsets.append(_off_i)
            if _idx < len(part_material_ids):
                _filtered_mats.append(int(part_material_ids[_idx]))
            else:
                _filtered_mats.append(0)

        if len(_filtered_offsets) != len(part_offsets):
            ctx.log(
                f"⚠ Sanitized part offset table: kept {len(_filtered_offsets)} / {len(part_offsets)} entries"
            )

        part_offsets = _filtered_offsets
        part_material_ids = _filtered_mats
        g.part_offsets = list(part_offsets)
        g.part_material_ids = list(part_material_ids)

    def scan_for_vif_header(
        *,
        start: int,
        end: int,
        wanted_cmd: int,
        max_scan_bytes: int = 0x200,
        step: int = 4,
        require_b1_80: bool = True,
    ) -> Optional[Tuple[int, bytes]]:
        if end < start:
            return None
        scan_end = min(end, start + max_scan_bytes)
        pos = start
        while pos + 4 <= scan_end:
            f.seek(pos, 0)
            hdr = f.read(4)
            if len(hdr) < 4:
                return None
            b0, b1, b2, b3 = hdr[0], hdr[1], hdr[2], hdr[3]
            if require_b1_80 and b1 != 0x80:
                pos += step
                continue
            if b3 == wanted_cmd:
                return pos, hdr
            pos += step
        return None

    for part_index, part_offset in enumerate(part_offsets):
        part_addr = geo_start + part_offset

        part = StoriesPartGeom()
        part.material_id = int(part_material_ids[part_index])

        try:
            if getattr(g, "ped_part_table_entries", None) and part_index < len(g.ped_part_table_entries):
                _e = g.ped_part_table_entries[part_index]
                part.entry_unknown0 = int(_e.get("entry_unknown0", 0)) & 0xFFFFFFFF
                part.entry_unknowns = [int(x) & 0xFFFFFFFF for x in (_e.get("entry_unknowns") or [])[:6]]
                part.entry_unknown_short = int(_e.get("entry_unknown_short", 0)) & 0xFFFF
                part.entry_trailing = [int(x) & 0xFFFFFFFF for x in (_e.get("entry_trailing") or [])[:3]]
        except Exception:
            pass

        if part_index + 1 < len(part_offsets):
            next_part_addr = geo_start + part_offsets[part_index + 1]
        else:
            f.seek(0, 2)
            file_end_for_part = f.tell()
            next_part_addr = file_end_for_part
            try:
                leeds_header = getattr(g, "leeds_global_header", {}) or {}
                global_header_off = int(leeds_header.get("raw_offset", 0))
                geometry_size_bytes = int(leeds_header.get("geometry_size_bytes", 0))
                geometry_end = global_header_off + geometry_size_bytes
                if geometry_end > part_addr and geometry_end <= file_end_for_part:
                    next_part_addr = geometry_end
            except Exception:
                pass

        f.seek(part_addr)
        ctx.log(
            f"\n🔄 Reading geometry dmaOffset {part_index + 1}/{len(part_offsets)} (Offset: 0x{part_addr:X})"
        )

        while f.tell() < next_part_addr:
            marker_seek = f.tell()
            ctx.log(f"🔎 Looking for triangle strip marker at offset: 0x{marker_seek:X}")

            if f.tell() + 4 > next_part_addr:
                ctx.log(f"⚠ Reached end of part before marker read at 0x{f.tell():X}; stopping part decode.")
                break
            try:
                marker = read_u32(f)
            except struct.error as _marker_err:
                ctx.log(f"⚠ Short read while reading strip marker at 0x{marker_seek:X}: {_marker_err}")
                break
            ctx.log(f"   Read marker 0x{marker:08X} at 0x{marker_seek:X}")

            if marker == 0x6C018000:
                split_flag_offset = marker_seek
                ctx.log(
                    f"✔ 0x6C018000 split flag found at 0x{split_flag_offset:X} -- reading split section header..."
                )

                zeros1_offset = f.tell()
                zeros1 = f.read(4)
                ctx.log(
                    f"  [0x{zeros1_offset:X}] zeros1: {zeros1.hex()} (should be 00 00 00 00)"
                )
                zeros2_offset = f.tell()
                zeros2 = f.read(4)
                ctx.log(
                    f"  [0x{zeros2_offset:X}] zeros2: {zeros2.hex()} (should be 00 00 00 00)"
                )

                vert_count1_offset = f.tell()
                vert_count1 = read_u8(f)
                ctx.log(f"  [0x{vert_count1_offset:X}] vert_count1: {vert_count1}")
                pad3_offset = f.tell()
                pad3 = f.read(3)
                ctx.log(
                    f"  [0x{pad3_offset:X}] pad3: {pad3.hex()} (should be 00 00 00)"
                )

                vert_count2_offset = f.tell()
                vert_count2 = read_u8(f)
                ctx.log(f"  [0x{vert_count2_offset:X}] vert_count2: {vert_count2}")

                flags_offset = f.tell()
                flags = read_u16(f)
                vert_count_dma = flags & 0x7FFF
                culling_disabled = bool(flags & 0x8000)
                ctx.log(f"  [0x{flags_offset:X}] flags: 0x{flags:04X}")
                ctx.log(f"     - vert_count_dma (flags & 0x7FFF): {vert_count_dma}")
                ctx.log(f"     - culling_disabled (flags & 0x8000): {culling_disabled}")

                pad4_offset = f.tell()
                pad4 = f.read(4)
                ctx.log(f"  [0x{pad4_offset:X}] pad4: {pad4.hex()}")

                tech1_offset = f.tell()
                tech1 = f.read(4)
                ctx.log(
                    f"  [0x{tech1_offset:X}] tech1: {tech1.hex()} (typically 40404020)"
                )

                tech2_offset = f.tell()
                tech2 = f.read(4)
                ctx.log(f"  [0x{tech2_offset:X}] tech2: {tech2.hex()}")

                f.seek(marker_seek)

                if vert_count1 != vert_count2:
                    ctx.log(
                        f"  WARNING: vert_count1 ({vert_count1}) != vert_count2 ({vert_count2}) at 0x{f.tell():X}"
                    )
                else:
                    ctx.log(f"✔ Vertex counts match: {vert_count1}")
                ctx.log("=== END OF 0x6C018000 SPLIT BLOCK ===")

            f.seek(16, 1)

            while (marker & 0x60000000) != 0x60000000 and f.tell() < next_part_addr:
                ctx.log(
                    f"      Not a tri-strip flag (got 0x{marker:08X}). Skipping 44 bytes (11 DWORDs) at 0x{f.tell():X}"
                )
                for _ in range(11):
                    f.read(4)
                skip_offset = f.tell()
                if f.tell() + 4 > next_part_addr:
                    ctx.log(f"      ⚠ Reached end of part while scanning for strip marker at 0x{f.tell():X}")
                    break
                try:
                    marker = read_u32(f)
                except struct.error as _scan_err:
                    ctx.log(f"      ⚠ Short read while scanning strip marker at 0x{skip_offset:X}: {_scan_err}")
                    break
                ctx.log(
                    f"      Checked tri-strip marker 0x{marker:08X} at 0x{skip_offset:X}"
                )

            if (marker & 0x60000000) != 0x60000000:
                ctx.log(f"✗ No valid strip marker found, breaking out at offset 0x{f.tell():X}")
                break

            if marker == 0x60000000:
                ctx.log(
                    f"✔ 0x60000000 tri-strip flag found at 0x{marker_seek:X}, skipping 16 bytes to 0x{marker_seek + 16:X}"
                )
                f.seek(marker_seek, 0)
            elif marker == 0x6C018000:
                ctx.log(
                    f"✔ 0x6C018000 split section marker found at 0x{marker_seek:X}, rewinding to flag for detailed breakdown"
                )
                f.seek(marker_seek, 0)
            else:
                ctx.log(
                    f"✔ Valid tri-strip flag (0x{marker:08X}) found at 0x{marker_seek:X}, rewinding to flag"
                )
                f.seek(-4, 1)

            split_segment_start = marker_seek
            is_ped_split_segment = (marker == 0x6C018000)
            if not is_ped_split_segment and (marker & 0x60000000) == 0x60000000:
                try:
                    _saved_probe = f.tell()
                    f.seek(marker_seek + 16, 0)
                    is_ped_split_segment = (read_u32(f) == 0x6C018000)
                    if is_ped_split_segment:
                        split_segment_start = marker_seek + 16
                    f.seek(_saved_probe, 0)
                except Exception:
                    try:
                        f.seek(_saved_probe, 0)
                    except Exception:
                        pass

            for _ in range(4):
                f.read(4)

            tri_strip_start = f.tell()
            ctx.log(f"  Tri-Strip Start: 0x{tri_strip_start:X}")

            for _ in range(8):
                f.read(4)
            _ = read_u16(f)
            cur_strip_vert_count = read_u8(f)
            pad_byte = read_u8(f)
            ctx.log(
                f"    - curStripVertCount: {cur_strip_vert_count} (padByte={pad_byte}) at 0x{f.tell():X}"
            )

            vertex_data_offset = f.tell()
            ctx.log(
                f"    🧊 Vertex data begins at file offset: 0x{vertex_data_offset:X} ({vertex_data_offset})"
            )

            verts: List[Tuple[float, float, float]] = []
            skin_indices: List[List[int]] = []
            skin_weights: List[List[float]] = []
            skin_raw_dwords: List[List[int]] = []

            base_idx = len(part.verts)

            for vi in range(cur_strip_vert_count):
                offset_x = f.tell()
                x_raw = read_i16(f)
                offset_y = f.tell()
                y_raw = read_i16(f)
                offset_z = f.tell()
                z_raw = read_i16(f)

                x = x_raw * g.x_scale * global_scale + tx
                y = y_raw * g.y_scale * global_scale + ty
                z = z_raw * g.z_scale * global_scale + tz

                verts.append((x, y, z))

                ctx.log(f"        🧊 Vertex {vi}:")
                ctx.log(
                    f"           • X Offset: 0x{offset_x:X}, Raw: {x_raw}, Final: {x:.6f}"
                )
                ctx.log(
                    f"           • Y Offset: 0x{offset_y:X}, Raw: {y_raw}, Final: {y:.6f}"
                )
                ctx.log(
                    f"           • Z Offset: 0x{offset_z:X}, Raw: {z_raw}, Final: {z:.6f}"
                )

            part.verts.extend(verts)

            for i in range(2, cur_strip_vert_count):
                if (i % 2) == 0:
                    v0 = base_idx + i - 2
                    v1 = base_idx + i - 1
                    v2 = base_idx + i
                else:
                    v0 = base_idx + i - 1
                    v1 = base_idx + i - 2
                    v2 = base_idx + i
                if v0 != v1 and v1 != v2 and v2 != v0:
                    part.faces.append((v0, v1, v2))

            ped_segment_parsed = False
            if is_ped_split_segment:

                try:
                    align4 = f.tell() % 4
                    if align4:
                        pad_bytes = 4 - align4
                        f.read(pad_bytes)
                        ctx.log(f"    🟦 PED align to dword after verts: {pad_bytes} bytes")

                    stmask_pos = f.tell()
                    stmask_word = read_u32(f)
                    stmask_value = read_u32(f)
                    strow_word = read_u32(f)
                    strow_values = [read_u32(f), read_u32(f), read_u32(f), read_u32(f)]
                    ctx.log(
                        f"    🧷 PED UV STMASK/STROW at 0x{stmask_pos:X}: "
                        f"0x{stmask_word:08X}, 0x{stmask_value:08X}, "
                        f"0x{strow_word:08X}, rows={strow_values}"
                    )

                    if stmask_word != 0x20000000 or strow_word != 0x30000000:
                        raise ValueError(
                            f"unexpected PED UV STMASK/STROW block at 0x{stmask_pos:X}: "
                            f"0x{stmask_word:08X}/0x{strow_word:08X}"
                        )

                    uv_header_pos = f.tell()
                    uv_header = f.read(4)
                    if len(uv_header) < 4:
                        raise EOFError("short read while reading PED UV header")
                    b0, b1, b2, b3 = uv_header[0], uv_header[1], uv_header[2], uv_header[3]
                    if b3 != 0x76:
                        found = scan_for_vif_header(
                            start=uv_header_pos,
                            end=next_part_addr,
                            wanted_cmd=0x76,
                            max_scan_bytes=0x80,
                            step=4,
                            require_b1_80=False,
                        )
                        if not found:
                            raise ValueError(
                                f"PED UV header not found near 0x{uv_header_pos:X}; got {uv_header.hex()}"
                            )
                        uv_header_pos, uv_header = found
                        f.seek(uv_header_pos + 4, 0)
                        b0, b1, b2, b3 = uv_header[0], uv_header[1], uv_header[2], uv_header[3]

                    cur_strip_tvert_count = int(b2)
                    if cur_strip_tvert_count <= 0 or cur_strip_tvert_count > 0x80:
                        ctx.log(
                            f"    ⚠ PED UV count b2={cur_strip_tvert_count} invalid; "
                            f"using curStripVertCount={cur_strip_vert_count}"
                        )
                        cur_strip_tvert_count = int(cur_strip_vert_count)
                    ctx.log(
                        f"    ⬛ PED UV header at 0x{uv_header_pos:X}: "
                        f"b0=0x{b0:02X}, b1=0x{b1:02X}, "
                        f"b2(count)={cur_strip_tvert_count}, b3=0x{b3:02X}"
                    )

                    uvs: List[Tuple[float, float]] = []
                    uv_bytes = f.read(cur_strip_tvert_count * 2)
                    for i in range(cur_strip_tvert_count):
                        if (i * 2 + 1) < len(uv_bytes):
                            u_raw = uv_bytes[i * 2]
                            v_raw = uv_bytes[i * 2 + 1]
                            uvs.append((u_raw / 127.5, v_raw / 127.5))
                    part.uvs.extend(uvs)
                    pad = (4 - ((cur_strip_tvert_count * 2) % 4)) % 4
                    if pad:
                        f.read(pad)
                        ctx.log(f"    🟦 PED padding after UVs: {pad} bytes")

                    normal_header_pos = f.tell()
                    normal_header = f.read(4)
                    if len(normal_header) < 4:
                        raise EOFError("short read while reading PED normal header")
                    nb0, nb1, nb2, nb3 = normal_header[0], normal_header[1], normal_header[2], normal_header[3]
                    if nb3 != 0x6A:
                        raise ValueError(
                            f"expected PED normal header 0x6A at 0x{normal_header_pos:X}, got {normal_header.hex()}"
                        )
                    normal_count = int(nb2)
                    if normal_count <= 0 or normal_count > 0x80:
                        normal_count = int(cur_strip_vert_count)
                    ctx.log(
                        f"   >> PED normal header: b1={nb1:02X}, count={normal_count}, "
                        f"b3={nb3:02X} at 0x{normal_header_pos:X}"
                    )
                    norms: List[Tuple[float, float, float]] = []
                    for i in range(normal_count):
                        nx = read_i8(f) / 128.0
                        ny = read_i8(f) / 128.0
                        nz = read_i8(f) / 128.0
                        norms.append((nx, ny, nz))
                    pad = (4 - ((normal_count * 3) % 4)) % 4
                    if pad:
                        f.read(pad)
                    if normal_count:
                        if not hasattr(part, 'normals'):
                            part.normals = []
                        part.normals.extend(norms)

                    skin_header_pos = f.tell()
                    skin_header = f.read(4)
                    if len(skin_header) < 4:
                        raise EOFError("short read while reading PED skin header")
                    sb0, sb1, sb2, sb3 = skin_header[0], skin_header[1], skin_header[2], skin_header[3]
                    if sb3 != 0x6C:
                        raise ValueError(
                            f"expected PED skin header 0x6C at 0x{skin_header_pos:X}, got {skin_header.hex()}"
                        )
                    skin_count = int(sb2)
                    if skin_count <= 0 or skin_count > 0x80:
                        skin_count = int(cur_strip_vert_count)
                    ctx.log(
                        f"   >> PED skin header: b1={sb1:02X}, count={skin_count}, "
                        f"b3={sb3:02X} at 0x{skin_header_pos:X}"
                    )
                    for i in range(skin_count):
                        raw1 = read_u32(f)
                        raw2 = read_u32(f)
                        raw3 = read_u32(f)
                        raw4 = read_u32(f)

                        bone1, w1 = _decode_ps2_ped_skin_word(raw1)
                        bone2, w2 = _decode_ps2_ped_skin_word(raw2)
                        bone3, w3 = _decode_ps2_ped_skin_word(raw3)
                        bone4, w4 = _decode_ps2_ped_skin_word(raw4)

                        skin_indices.append([bone1, bone2, bone3, bone4])
                        skin_weights.append([w1, w2, w3, w4])
                        skin_raw_dwords.append([raw1 & 0xFFFFFFFF, raw2 & 0xFFFFFFFF, raw3 & 0xFFFFFFFF, raw4 & 0xFFFFFFFF])

                    mscal_pos = f.tell()
                    if mscal_pos + 4 <= next_part_addr:
                        mscal_word = read_u32(f)
                        if mscal_word != 0x14000006:
                            ctx.log(
                                f"    ⚠ Expected PED MSCAL at 0x{mscal_pos:X}, got 0x{mscal_word:08X}; rewinding"
                            )
                            f.seek(mscal_pos, 0)
                        else:
                            ctx.log(f"    ✔ PED MSCAL at 0x{mscal_pos:X}")

                    rel_after_segment = (f.tell() - split_segment_start) % 16
                    if rel_after_segment:
                        pad_bytes = 16 - rel_after_segment
                        if f.tell() + pad_bytes <= next_part_addr:
                            f.read(pad_bytes)
                            ctx.log(f"    🟦 PED segment qword padding: {pad_bytes} bytes")

                    ped_segment_parsed = True
                except Exception as ped_parse_error:
                    ctx.log(
                        f"    ⚠ PED exact VIF parse failed at strip 0x{marker_seek:X}: {ped_parse_error}; "
                        f"falling back to generic scanner"
                    )

                    f.seek(vertex_data_offset + (cur_strip_vert_count * 6), 0)
                    align4 = f.tell() % 4
                    if align4:
                        f.read(4 - align4)

            if not ped_segment_parsed:

                if (cur_strip_vert_count % 2) == 1:
                    pad_short_pos = f.tell()
                    pad_short = read_i16(f)
                    ctx.log(
                        f"    ⬛ Padding short after verts (odd count): {pad_short} at 0x{pad_short_pos:X}"
                    )

                align4 = f.tell() % 4
                if align4:
                    pad_bytes = 4 - align4
                    f.read(pad_bytes)
                    ctx.log(f"    🟦 Align to dword after verts: {pad_bytes} bytes")

                uv_header_pos = f.tell()
                uv_header = None
                found = scan_for_vif_header(
                    start=uv_header_pos,
                    end=next_part_addr,
                    wanted_cmd=0x76,
                    max_scan_bytes=0x200,
                    step=4,
                    require_b1_80=True,
                )
                if found:
                    uv_header_pos, uv_header = found
                    ctx.log(f"    ✔ Found UV header by scan at 0x{uv_header_pos:X}")
                else:

                    f.seek(uv_header_pos, 0)
                    uv_header = f.read(4)
                    if len(uv_header) < 4:
                        break
                    ctx.log(
                        f"    ⚠ UV header scan failed; using current position 0x{uv_header_pos:X}"
                    )

                f.seek(uv_header_pos + 4, 0)
                b0, b1, b2, b3 = uv_header[0], uv_header[1], uv_header[2], uv_header[3]

                cur_strip_tvert_count = int(b2)
                if cur_strip_tvert_count <= 0 or cur_strip_tvert_count > 0x80:
                    ctx.log(
                        f"    ⚠ UV count b2={cur_strip_tvert_count} looks invalid; using curStripVertCount={cur_strip_vert_count}"
                    )
                    cur_strip_tvert_count = int(cur_strip_vert_count)
                ctx.log(
                    f"    ⬛ UV header at 0x{uv_header_pos:X}: b0=0x{b0:02X}, b1=0x{b1:02X}, b2 (count)={cur_strip_tvert_count}, b3=0x{b3:02X}"
                )

                if b3 != 0x76:
                    ctx.log(f"    ⚠ Unexpected UV section header b3=0x{b3:02X} at 0x{uv_header_pos:X}")

                uvs: List[Tuple[float, float]] = []

                uv_bytes = f.read(cur_strip_tvert_count * 2)
                for i in range(cur_strip_tvert_count):
                    if (i * 2 + 1) < len(uv_bytes):
                        u_raw = uv_bytes[i * 2]
                        v_raw = uv_bytes[i * 2 + 1]
                        u_f = u_raw / 127.5
                        v_f = v_raw / 127.5
                        uvs.append((u_f, v_f))
                        ctx.log(
                            f"      🟪 UV {i}: U={u_f:.6f}, V={v_f:.6f} (raw: {u_raw}, {v_raw})"
                        )

                pad = (4 - ((cur_strip_tvert_count * 2) % 4)) % 4
                if pad:
                    f.read(pad)
                    ctx.log(f"    🟦 Padding after UVs: {pad} bytes")

                part.uvs.extend(uvs)

                while True:
                    subsection_pos = f.tell()
                    header = f.read(4)
                    if len(header) < 4:
                        break

                    marker_val = struct.unpack("<I", header)[0]
                    b0, b1, b2, b3 = header[0], header[1], header[2], header[3]

                    if marker_val == 0x60000000:
                        ctx.log(
                            f"✔ Found 0x60000000 strip marker at 0x{subsection_pos:X} -- skipping 16 bytes"
                        )
                        f.seek(16, 1)
                        break
                    elif marker_val == 0x6C018000:
                        ctx.log(
                            f"✔ Found 0x6C018000 split flag at 0x{subsection_pos:X} -- rewinding to marker"
                        )
                        f.seek(subsection_pos, 0)
                        break

                    if b1 == 0x80 and b3 in (0x6F, 0x6A, 0x6C):
                        section_count = b2
                        ctx.log(
                            f"   >> Subsection header: b1={b1:02X}, count={section_count}, b3={b3:02X} at 0x{subsection_pos:X}"
                        )

                        if b3 == 0x6F:
                            ctx.log(f"      🎨 Reading {section_count} vertex colors")
                            for i in range(section_count):
                                vcolor = read_u16(f)

                                r = (vcolor & 0x1F) * (1.0 / 32.0)

                                gcol = ((vcolor >> 5) & 0x1F) * (1.0 / 32.0)
                                b = ((vcolor >> 10) & 0x1F) * (1.0 / 32.0)
                                a = ((vcolor >> 15) & 0x01) * 1.0
                                ctx.log(
                                    f"         R={r:.3f} G={gcol:.3f} B={b:.3f} A={a:.1f} (raw=0x{vcolor:04X})"
                                )
                            pad = 2 - ((2 * section_count) % 4)
                            if pad != 4:
                                f.read(pad)

                        elif b3 == 0x6A:
                            ctx.log(f"      🧲 Reading {section_count} normals")
                            norms: List[Tuple[float, float, float]] = []
                            for i in range(section_count):
                                nx = read_i8(f) / 128.0
                                ny = read_i8(f) / 128.0
                                nz = read_i8(f) / 128.0
                                norms.append((nx, ny, nz))
                                ctx.log(f"         N={nx:.4f} {ny:.4f} {nz:.4f}")
                            pad = 4 - ((3 * section_count) % 4)
                            if pad != 4:
                                f.read(pad)

                            if section_count:
                                if not hasattr(part, 'normals'):
                                    part.normals = []
                                part.normals.extend(norms)

                        elif b3 == 0x6C:
                            ctx.log(f"      🦴 Reading {section_count} skin weights")
                            for i in range(section_count):
                                raw1 = read_u32(f)
                                raw2 = read_u32(f)
                                raw3 = read_u32(f)
                                raw4 = read_u32(f)

                                bone1, w1 = _decode_ps2_ped_skin_word(raw1)
                                bone2, w2 = _decode_ps2_ped_skin_word(raw2)
                                bone3, w3 = _decode_ps2_ped_skin_word(raw3)
                                bone4, w4 = _decode_ps2_ped_skin_word(raw4)

                                ctx.log(
                                    f"         B1={bone1} W1={w1:.4f} ... B4={bone4} W4={w4:.4f}"
                                )

                                indices = [bone1, bone2, bone3, bone4]
                                weights = [w1, w2, w3, w4]

                                skin_indices.append(indices)
                                skin_weights.append(weights)
                                skin_raw_dwords.append([raw1 & 0xFFFFFFFF, raw2 & 0xFFFFFFFF, raw3 & 0xFFFFFFFF, raw4 & 0xFFFFFFFF])
                        continue

            if len(skin_indices) != cur_strip_vert_count or len(skin_weights) != cur_strip_vert_count:
                ctx.log(
                    f"[WARN] strip verts={cur_strip_vert_count}, skin_idx={len(skin_indices)}, skin_wts={len(skin_weights)} — padding zeros to match"
                )
                while len(skin_indices) < cur_strip_vert_count:
                    skin_indices.append([0, 0, 0, 0])
                    skin_weights.append([0.0, 0.0, 0.0, 0.0])
                skin_indices = skin_indices[:cur_strip_vert_count]
                skin_weights = skin_weights[:cur_strip_vert_count]

            while len(skin_raw_dwords) < cur_strip_vert_count:
                skin_raw_dwords.append([0, 0, 0, 0])
            skin_raw_dwords = skin_raw_dwords[:cur_strip_vert_count]

            strip_meta = StripMeta(
                base_vertex_index=base_idx,
                vertex_count=cur_strip_vert_count,
                skin_indices=[list(lst) for lst in skin_indices],
                skin_weights=[list(lst) for lst in skin_weights],
                skin_raw_dwords=[list(lst) for lst in skin_raw_dwords],
            )
            part.strips_meta.append(strip_meta)
            if not hasattr(part, 'skin_raw_dwords'):
                part.skin_raw_dwords = []
            part.skin_raw_dwords.extend([list(lst) for lst in skin_raw_dwords])
            skin_indices.clear()
            skin_weights.clear()
            skin_raw_dwords.clear()

        if part_index < len(g.leeds_part_headers):
            _ph = g.leeds_part_headers[part_index]
            try:
                part.uv_scale = (float(_ph.get("uv_scale_u", 1.0)), float(_ph.get("uv_scale_v", 1.0)))
                part.geom_flags = int(_ph.get("flags", 0))
                part.strip_vertex_count_hint = int(_ph.get("strip_vertex_count", 0))
                part.bbox_i16 = [int(v) for v in (_ph.get("bbox_i16", []) or [])[:6]]
                _sph = _ph.get("sphere", [0.0, 0.0, 0.0, 0.0])
                if isinstance(_sph, (list, tuple)) and len(_sph) >= 4:
                    part.sphere = (float(_sph[0]), float(_sph[1]), float(_sph[2]), float(_sph[3]))
                part.raw_part_header_offset = int(_ph.get("raw_offset", 0))
            except Exception:
                pass

        g.parts.append(part)

    return g

def read_psp_geometry(ctx: StoriesMDLContext, f, geom_ptr: int) -> StoriesPSPGeometryInfo:
    g = StoriesPSPGeometryInfo()
    ctx.log("Attempting PSP Stories MDL read...")

    f.seek(geom_ptr)
    header_offset = f.tell()

    g.materials = read_material_list(ctx, f)

    f.seek(12, 1)

    psp_header = f.read(0x48)
    if len(psp_header) != 0x48:
        raise Exception("Not enough bytes for PSP geometry header!")

    (
        size,
        flags,
        num_strips,
        unk1,
        bound0,
        bound1,
        bound2,
        bound3,
        scale_x,
        scale_y,
        scale_z,
        num_verts,
        pos_x,
        pos_y,
        pos_z,
        unk2,
        offset,
        unk3,
    ) = struct.unpack("<4I4f3fi3fiIf", psp_header)

    g.flags = flags
    g.num_strips = num_strips
    g.num_verts = num_verts
    g.scale = (scale_x, scale_y, scale_z)
    g.pos = (pos_x, pos_y, pos_z)

    uvfmt = flags & 0x3
    colfmt = (flags >> 2) & 0x7
    normfmt = (flags >> 5) & 0x3
    posfmt = (flags >> 7) & 0x3
    wghtfmt = (flags >> 9) & 0x3
    idxfmt = (flags >> 11) & 0x3
    nwght = ((flags >> 14) & 0x7) + 1

    g.uv_format = uvfmt
    g.col_format = colfmt
    g.norm_format = normfmt
    g.pos_format = posfmt
    g.weight_format = wghtfmt
    g.index_format = idxfmt
    g.num_weights_per_vertex = nwght

    known_flag_formats = {0x120, 0x121, 0x115, 0x114, 0xA1, 0x1C321}
    if flags not in known_flag_formats:
        ctx.log(f"⚠️ Unknown PSP geometry flags format: 0x{flags:X}")
        raise Exception(f"Unknown PSP geometry flags format: 0x{flags:X}")
    else:
        ctx.log(f"✔ Known PSP geometry flags format: 0x{flags:X}")

    ctx.log("----- Flags Format Case Breakdown -----")

    if uvfmt == 0:
        ctx.log("  uvfmt   = 0: No UV coordinates (case 0) [OK]")
    elif uvfmt == 1:
        ctx.log("  uvfmt   = 1: U8 UVs (case 1) [OK]")
    else:
        ctx.log(f"  uvfmt   = {uvfmt}: Unsupported UV format! [ERROR]")
        raise Exception(f"Unsupported tex coord format (uvfmt={uvfmt})")

    if colfmt == 0:
        ctx.log("  colfmt  = 0: No vertex color (case 0) [OK]")
    elif colfmt == 5:
        ctx.log("  colfmt  = 5: 16-bit RGBA5551 color (case 5) [OK]")
    else:
        ctx.log(f"  colfmt  = {colfmt}: Unsupported vertex color format! [ERROR]")
        raise Exception(f"Unsupported color format (colfmt={colfmt})")

    if normfmt == 0:
        ctx.log("  normfmt = 0: No normals (case 0) [OK]")
    elif normfmt == 1:
        ctx.log("  normfmt = 1: S8 normals (case 1) [OK]")
    else:
        ctx.log(f"  normfmt = {normfmt}: Unsupported normal format! [ERROR]")
        raise Exception(f"Unsupported normal format (normfmt={normfmt})")

    if posfmt == 1:
        ctx.log("  posfmt  = 1: S8 positions (case 1) [OK]")
    elif posfmt == 2:
        ctx.log("  posfmt  = 2: S16 positions (case 2) [OK]")
    else:
        ctx.log(f"  posfmt  = {posfmt}: Unsupported vertex position format! [ERROR]")
        raise Exception(f"Unsupported vertex format (posfmt={posfmt})")

    if wghtfmt == 0:
        ctx.log("  wghtfmt = 0: No weights/skin [OK]")
    elif wghtfmt == 1:
        ctx.log("  wghtfmt = 1: U8 weights/skin [OK]")
    else:
        ctx.log(f"  wghtfmt = {wghtfmt}: Unsupported weights format! [ERROR]")
        raise Exception(f"Unsupported weight format (wghtfmt={wghtfmt})")

    if idxfmt == 0:
        ctx.log("  idxfmt  = 0: Index format [OK]")
    else:
        ctx.log(f"  idxfmt  = {idxfmt}: Unsupported/invalid index format! [ERROR]")
        raise Exception(f"idxfmt must be 0 (got {idxfmt})")

    ctx.log(f"  nwght   = {nwght}: Number of weights per vertex (parsed as ((flags>>14) & 7) + 1)")
    ctx.log("--------------------------------------")

    ctx.log("----- PSP Geometry Struct -----")
    ctx.log(f"  size      (header+data): {size} (0x{size:08X})")
    ctx.log(f"  flags     (VTYPE)      : {flags} (0x{flags:08X})")
    ctx.log(f"  numStrips              : {num_strips}")
    ctx.log(f"  unk1                   : {unk1} (0x{unk1:08X})")
    ctx.log(f"  bound   [0]            : {bound0}")
    ctx.log(f"  bound   [1]            : {bound1}")
    ctx.log(f"  bound   [2]            : {bound2}")
    ctx.log(f"  bound   [3]            : {bound3}")
    ctx.log(f"  scale_x                : {scale_x}")
    ctx.log(f"  scale_y                : {scale_y}")
    ctx.log(f"  scale_z                : {scale_z}")
    ctx.log(f"  numVerts               : {num_verts}")
    ctx.log(f"  pos_x                  : {pos_x}")
    ctx.log(f"  pos_y                  : {pos_y}")
    ctx.log(f"  pos_z                  : {pos_z}")
    ctx.log(f"  unk2                   : {unk2} (0x{unk2:08X})")
    ctx.log(f"  offset (to vertices)   : {offset} (0x{offset:08X})")
    ctx.log(f"  unk3                   : {unk3}")
    ctx.log("--------------------------------")

    mesh_list: List[Dict[str, Any]] = []
    for i in range(num_strips):
        mesh_offset = f.tell()
        mesh_bytes = f.read(0x30)
        if len(mesh_bytes) != 0x30:
            ctx.log(
                f"✗ ERROR: Could not read 0x30 bytes for sPspGeometryMesh[{i}] at 0x{mesh_offset:X}"
            )
            break

        (
            m_offset,
            m_num_triangles,
            m_mat_id,
            m_unk1,
            m_uv_scale0,
            m_uv_scale1,
            m_unk2_0,
            m_unk2_1,
            m_unk2_2,
            m_unk2_3,
            m_unk3,
            *m_bonemap,
        ) = struct.unpack("<I H H f 2f 4f f 8B", mesh_bytes)

        ctx.log(f"\n---- [sPspGeometryMesh {i + 1}/{num_strips}] ----")
        ctx.log(f"  File Offset        : 0x{mesh_offset:X}")
        ctx.log(f"  offset (to tris)   : 0x{m_offset:08X}")
        ctx.log(f"  numTriangles       : {m_num_triangles}")
        ctx.log(f"  matID              : {m_mat_id}")
        ctx.log(f"  unk1               : {m_unk1}")
        ctx.log(f"  uvScale            : ({m_uv_scale0}, {m_uv_scale1})")
        ctx.log(
            f"  unk2[0..3]         : ({m_unk2_0}, {m_unk2_1}, {m_unk2_2}, {m_unk2_3})"
        )
        ctx.log(f"  unk3               : {m_unk3}")
        ctx.log(f"  bonemap            : {list(m_bonemap)}")

        mesh_dict = {
            "offset": m_offset,
            "numTriangles": m_num_triangles,
            "matID": m_mat_id,
            "unk1": m_unk1,
            "uvScale": (m_uv_scale0, m_uv_scale1),
            "unk2": (m_unk2_0, m_unk2_1, m_unk2_2, m_unk2_3),
            "unk3": m_unk3,
            "bonemap": list(m_bonemap),
            "raw_bytes": mesh_bytes,
            "file_offset": mesh_offset,
        }
        mesh_list.append(mesh_dict)

    ctx.log(
        f"✔ Finished reading {len(mesh_list)} sPspGeometryMesh structs (expected: {num_strips})\n"
    )

    vertex_buffer_file_offset = header_offset + offset - 168
    ctx.log(f"Vertex buffer begins at file offset: 0x{vertex_buffer_file_offset:X}")

    f.seek(vertex_buffer_file_offset)
    vertex_buffer = f.read(num_verts * 24)
    if len(vertex_buffer) < num_verts:
        raise Exception("Not enough data for vertex buffer!")

    for mesh_index, mesh in enumerate(mesh_list):
        ctx.log(f"--- Building mesh for sPspGeometryMesh {mesh_index + 1}/{len(mesh_list)} ---")
        m = StoriesPSPMesh(index=mesh_index)
        m.mat_id = mesh["matID"]
        m.uv_scale = mesh["uvScale"]
        m.bonemap = list(mesh["bonemap"])

        tri_strip_offset = vertex_buffer_file_offset + mesh["offset"]
        f.seek(tri_strip_offset)

        bytes_per_vert = 20
        verts_to_skip = 10
        skip_bytes = bytes_per_vert * verts_to_skip
        f.seek(skip_bytes, 1)
        ctx.log(
            f"⏩ Skipped first {verts_to_skip} verts ({skip_bytes} bytes) for mesh {mesh_index}"
        )

        num_strip_verts = mesh["numTriangles"] + 2
        ctx.log(
            f"🟩 [PSP] Reading Mesh/Strip {mesh_index}: Vertex data starts at file offset 0x{tri_strip_offset:X} ({tri_strip_offset})"
        )
        ctx.log(
            f"  Tri-strip data for mesh {mesh_index}: offset=0x{tri_strip_offset:X}, numTriangles={mesh['numTriangles']}, thus numVertices={num_strip_verts}"
        )

        for vi in range(num_strip_verts):
            vertex_data = f.read(20)
            if len(vertex_data) < 8:
                ctx.log(f"    ! Not enough data for vertex {vi} of strip {mesh_index}")
                break

            local_o = 0

            if wghtfmt:
                weights_raw = [vertex_data[local_o + j] for j in range(nwght)]
                local_o += nwght

                K = min(4, nwght)
                w4 = [weights_raw[j] / 128.0 for j in range(K)]
                if K < 4:
                    w4.extend([0.0] * (4 - K))

                palette = mesh.get("bonemap") or []
                idx4: List[int] = []
                for j in range(K):
                    idx4.append(palette[j] if j < len(palette) else 0)
                if K < 4:
                    idx4.extend([0] * (4 - K))

                s = sum(w4)
                if s > 0.0:
                    w4 = [w / s for w in w4]

                if nwght > 4 and any(x != 0 for x in weights_raw[4:]):
                    ctx.log(
                        f"PSP: vertex had {nwght} weights; extra bytes beyond 4 were non-zero and ignored: {weights_raw[4:]}"
                    )

                m.bone_weights.append(w4)
                m.bone_indices.append(idx4)

            u_val = 0.0
            v_val = 0.0
            if uvfmt == 1:
                u_val = vertex_data[local_o] / 128.0 * mesh["uvScale"][0]
                v_val = vertex_data[local_o + 1] / 128.0 * mesh["uvScale"][1]
                m.uvs.append((u_val, v_val))
                local_o += 2

            col_val = None
            if colfmt == 5:
                local_o = ((local_o + 1) // 2) * 2
                col = struct.unpack_from("<H", vertex_data, local_o)[0]
                r = (col & 0x1F) * 255 // 0x1F
                g_c = ((col >> 5) & 0x1F) * 255 // 0x1F
                b_c = ((col >> 10) & 0x1F) * 255 // 0x1F
                a_c = 0xFF if (col & 0x8000) else 0
                col_val = (r, g_c, b_c, a_c)
                m.colors.append(col_val)
                local_o += 2

            norm_val = None
            if normfmt == 1:
                nx = struct.unpack_from("<b", vertex_data, local_o)[0] / 128.0
                ny = struct.unpack_from("<b", vertex_data, local_o + 1)[0] / 128.0
                nz = struct.unpack_from("<b", vertex_data, local_o + 2)[0] / 128.0
                norm_val = (nx, ny, nz)
                m.normals.append(norm_val)
                local_o += 3

            px = 0.0
            py = 0.0
            pz = 0.0
            if posfmt == 1:
                px = struct.unpack_from("<b", vertex_data, local_o)[0] / 128.0 * scale_x + pos_x
                py = struct.unpack_from("<b", vertex_data, local_o + 1)[0] / 128.0 * scale_y + pos_y
                pz = struct.unpack_from("<b", vertex_data, local_o + 2)[0] / 128.0 * scale_z + pos_z
                local_o += 3
            elif posfmt == 2:
                local_o = ((local_o + 1) // 2) * 2
                px = (
                    struct.unpack_from("<h", vertex_data, local_o)[0] / 32768.0 * scale_x
                    + pos_x
                )
                py = (
                    struct.unpack_from("<h", vertex_data, local_o + 2)[0] / 32768.0 * scale_y
                    + pos_y
                )
                pz = (
                    struct.unpack_from("<h", vertex_data, local_o + 4)[0] / 32768.0 * scale_z
                    + pos_z
                )
                local_o += 6

            m.verts.append((px, py, pz))

            ctx.log(
                f"    Vertex {vi}: pos=({px}, {py}, {pz})  uv=({u_val}, {v_val})  color={col_val}  normal={norm_val}"
            )

        for i in range(2, num_strip_verts):
            if (i % 2) == 0:
                v0 = i - 2
                v1 = i - 1
                v2 = i
            else:
                v0 = i - 1
                v1 = i - 2
                v2 = i
            if v0 != v1 and v1 != v2 and v2 != v0:
                m.faces.append((v0, v1, v2))

        ctx.log(
            f"✔ Built PSP mesh {mesh_index}: verts={len(m.verts)}, faces={len(m.faces)}"
        )
        g.meshes.append(m)

    ctx.log("✔ All PSP geometry meshes have been parsed (no Blender objects created here).")
    return g

class read_stories:

    def __init__(self, filepath: str, platform: str, mdl_type: str):
        self.filepath = filepath
        self.platform = platform
        self.mdl_type = mdl_type
        self.ctx: StoriesMDLContext | None = None

    def read(self) -> StoriesMDLContext:
        ctx = StoriesMDLContext(
            filepath=self.filepath,
            platform=self.platform,
            mdl_type=self.mdl_type,
        )

        filepath = self.filepath
        platform = self.platform
        mdl_type = self.mdl_type

        with open(filepath, "rb") as f:
            ctx.log(f"✔ Opened: {filepath}")
            if f.read(4) != b"ldm\x00":
                ctx.log("Invalid Stories MDL header.")
                raise ValueError("Invalid Stories MDL header")

            ctx.shrink = read_u32(f)
            ctx.file_len = read_u32(f)
            ctx.local_num_table = read_u32(f)
            ctx.global_num_table = read_u32(f)

            is_psp = platform == "PSP"
            if is_psp:
                ctx.log("Detected PSP MDL: Skipping 4 bytes after global_numTable.")
                f.seek(-4, 1)

            if ctx.global_num_table == (ctx.local_num_table + 4):
                ctx.actor_mdl = True
                ctx.log("✔ Ped/actor or prop MDL detected.")
            else:
                f.seek(-4, 1)
                ctx.num_entries = read_u32(f)
                ctx.log("✔ Non-actor MDL detected: possibly a prop.")
                if is_psp:
                    f.seek(4, 1)

            ctx.num_entries = read_u32(f)
            ctx.ptr2_before_tex = read_u32(f)
            ctx.allocated_memory = read_u32(f)

            next_ptr_offset = f.tell()
            possible_ptr = read_u32(f)
            if str(mdl_type or "").upper().strip() == "VEH" and next_ptr_offset == 0x20:
                vehicle_header_pos = f.tell()
                try:
                    ctx.vehicle_extra_count = read_u32(f)
                    ctx.vehicle_extra_array_ptr = read_u32(f)
                    primary_count = 30 if platform == "PS2" and possible_ptr else 25
                    ctx.vehicle_primary_material_ptrs = [read_u32(f) for _ in range(primary_count)]

                    ctx.vehicle_secondary_material_ptrs = [read_u32(f) for _ in range(25)]
                except Exception:
                    ctx.vehicle_extra_count = 0
                    ctx.vehicle_extra_array_ptr = 0
                    ctx.vehicle_primary_material_ptrs = []
                    ctx.vehicle_secondary_material_ptrs = []
                finally:
                    try:
                        f.seek(vehicle_header_pos, 0)
                    except Exception:
                        pass
                ctx.log(
                    f"VehicleModel header: clump_ptr=0x{possible_ptr:X}, "
                    f"extra_count={ctx.vehicle_extra_count}, extra_array=0x{ctx.vehicle_extra_array_ptr:X}"
                )
            ctx.log(f"Pointer after allocMem (offset 0x{next_ptr_offset:X}): 0x{possible_ptr:X}")

            def is_known_vtable(val: int) -> bool:
                KNOWN_VTABLES = {

                    0x00000002,
                    0x0000AA02,
                    0x0004AA01,
                    0x0000AA01,
                    0x0300AA00,
                    0x01050001,
                    0x01000001,
                }

                return val in KNOWN_VTABLES or (val & 0xFFFF) in {v & 0xFFFF for v in KNOWN_VTABLES}

            inline_top_level_magic = possible_ptr in {
                LCSCLUMPPS2 if 'LCSCLUMPPS2' in locals() else 0x00000002,
                VCSCLUMPPS2 if 'VCSCLUMPPS2' in locals() else 0x0000AA02,
                0x00000002,
                0x0000AA02,
                0x01050001,
                0x01000001,
                0x0004AA01,
                0x0000AA01,
            }

            if (next_ptr_offset == 0x20 and int(ctx.allocated_memory or 0) == 0 and inline_top_level_magic):
                ctx.inline_clump_header = possible_ptr in {0x00000002, 0x0000AA02}
                ctx.top_level_ptr = next_ptr_offset
                ctx.renderflags_offset = 0
                ctx.log(
                    f"Detected inline cutscene/actor top-level section at 0x{next_ptr_offset:X}: magic=0x{possible_ptr:X}"
                )
                peek_type = "inline_top_level"
                string_val = ""
                file_current = f.tell()
            else:
                peek_type = "unknown"
                string_val = ""
                file_current = f.tell()

            if peek_type != "inline_top_level":
                if 0 < possible_ptr < ctx.file_len:
                    f.seek(possible_ptr)
                    peek_bytes = f.read(8)
                    s = peek_bytes.split(b"\x00")[0]
                    if s and all(32 <= b <= 126 for b in s):
                        string_val = s.decode("ascii", errors="ignore")
                        peek_type = "string"
                    else:
                        val = struct.unpack("<I", peek_bytes[:4])[0]
                        if is_known_vtable(val):
                            peek_type = "vtable"
                        else:
                            peek_type = "struct_or_flags"
                    f.seek(file_current)
                else:
                    if is_known_vtable(possible_ptr):
                        peek_type = "vtable"
                    elif 32 <= (possible_ptr & 0xFF) <= 126:
                        peek_type = "string_candidate"
                    else:
                        peek_type = "unknown"
            ctx.log(
                f"Analysis: pointer after allocMem is {peek_type}"
                + (f" ('{string_val}')" if string_val else "")
            )

            renderflags_offset = 0

            if peek_type == "inline_top_level":
                ctx.log("This MDL uses the cutscene actor header variant: the 16-byte Clump starts directly at MDL +0x20.")
            elif peek_type == "vtable":
                ctx.log("This pointer is a vtable/top-level struct (Clump/Atomic etc).")
                ctx.top_level_ptr = possible_ptr
            elif peek_type in ("string", "string_candidate"):
                ctx.log(
                    f"This pointer is a string (probably a material/texture name): '{string_val}'"
                )
            elif peek_type == "struct_or_flags":
                ctx.log(
                    "This pointer appears to point to a struct or flags; treat as renderflags offset or substruct."
                )
                renderflags_offset = possible_ptr
                if mdl_type == "SIM":
                    f.seek(-4, 1)
                ctx.top_level_ptr = read_u32(f)
            else:
                ctx.log("Pointer after allocMem type could not be determined; treating as unknown/flags.")
                renderflags_offset = possible_ptr
                ctx.top_level_ptr = read_u32(f)

            ctx.renderflags_offset = renderflags_offset

            ctx.log(f"File Size: 0x{ctx.file_len:X}")
            ctx.log(f"Local Realloc Table: 0x{ctx.local_num_table:X}, Global Realloc Table: 0x{ctx.global_num_table:X}")
            ctx.log(f"Number of entries: 0x{ctx.num_entries:X}")
            ctx.log(f"Ptr2BeforeTexNameList: 0x{ctx.ptr2_before_tex:X}")
            ctx.log(f"Allocated memory: 0x{ctx.allocated_memory:X}")
            ctx.log(f"Top-level ptr or magic value: 0x{ctx.top_level_ptr:X}")

            f.seek(ctx.top_level_ptr)
            top_magic = read_u32(f)

            LCSCLUMPPS2 = 0x00000002
            VCSCLUMPPS2 = 0x0000AA02
            CLUMPPSP = 0x00000002
            LCSATOMIC1 = 0x01050001
            LCSATOMIC2 = 0x01000001
            VCSATOMIC1 = 0x0004AA01
            VCSATOMIC2 = 0x0000AA01
            VCSATOMICPSP1 = 0x00041601
            VCSATOMICPSP2 = 0x01F40400

            ctx.section_type = 0
            ctx.import_type = 0

            if top_magic in (LCSCLUMPPS2, VCSCLUMPPS2):
                ctx.section_type = 7
                if is_psp:
                    if top_magic == CLUMPPSP:
                        ctx.log(" Top magic matches PSP values, setting import type 3.")
                        ctx.import_type = 3
                else:
                    ctx.import_type = 1 if top_magic == LCSCLUMPPS2 else 2
            elif top_magic in (LCSATOMIC1, LCSATOMIC2, VCSATOMIC1, VCSATOMIC2):
                ctx.section_type = 2
                ctx.import_type = 1 if top_magic in (LCSATOMIC1, LCSATOMIC2) else 2
            elif top_magic in (VCSATOMICPSP1, VCSATOMICPSP2):
                ctx.section_type = 2
                ctx.import_type = 3 if top_magic in (VCSATOMICPSP1, VCSATOMICPSP2) else 2

            ctx.log(f"Section Type: {ctx.section_type}, Import Type: {ctx.import_type}")

            atomic_info = StoriesAtomicInfo()
            ctx.atomic = atomic_info

            atomic_from_clump = False
            if ctx.section_type == 7:
                ctx.log("✔ Detected Section Type: 7 (Clump)")

                f.seek(ctx.top_level_ptr, 0)
                clump_id = read_u32(f)
                first_frame = read_u32(f)
                first_atomic = read_u32(f)
                last_atomic = read_u32(f)
                ctx.clump_ptr = int(ctx.top_level_ptr)
                ctx.clump_root_frame_ptr = int(first_frame)
                ctx.clump_first_atomic_ptr = int(first_atomic)
                ctx.clump_last_atomic_ptr = int(last_atomic)
                ctx.log(f"Clump section begins at: 0x{ctx.top_level_ptr:X}")
                ctx.log(f"clump.root_frame: 0x{first_frame:X}")
                ctx.log(f"clump.first_atomic: 0x{first_atomic:X}")
                ctx.log(f"clump.last_atomic: 0x{last_atomic:X}")
                atomic_seek = first_atomic - 0x1C
                f.seek(atomic_seek, 0)
                atomic_from_clump = True
                ctx.section_type = 2

            if ctx.section_type == 2:
                ctx.log("✔ Detected Section Type: 2 (Atomic)")

                atomic_start = f.tell()
                ctx.log(f"Atomic section begins at: 0x{atomic_start:X}")

                if mdl_type == "SIM":
                    if atomic_from_clump:
                        ctx.log("MDL type is Prop: clump-derived atomic start detected, skipped f.seek(-4, 1).")
                    else:
                        f.seek(-4, 1)
                        ctx.log("MDL type is Prop: performed f.seek(-4, 1) before reading atomic_id.")
                else:
                    ctx.log("MDL type is Ped: did NOT perform f.seek(-4, 1) before reading atomic_id.")

                atomic_id = read_u32(f)
                frame_ptr = read_u32(f)
                prev_link = read_u32(f)
                prev_link2 = read_u32(f)
                padAAAA = read_u32(f)
                geom_ptr = read_u32(f)
                clump_ptr = read_u32(f)
                link_ptr = read_u32(f)
                link_ptr2 = read_u32(f)
                render_cb = read_u32(f)
                model_info_id = struct.unpack("<h", f.read(2))[0]
                vis_id_flag = struct.unpack("<H", f.read(2))[0]
                hierarchy_ptr = read_u32(f)
                material_ptr = 0
                if mdl_type == "PED":
                    pos_after_hier = f.tell()
                    try:
                        material_ptr = read_u32(f)
                    except Exception:
                        material_ptr = 0
                    f.seek(pos_after_hier, 0)

                ctx.log(f"frame_ptr: 0x{frame_ptr:X}")
                ctx.log(f"previous link: {prev_link:X}")
                ctx.log(f"previous link 2: {prev_link2:X}")
                ctx.log(f"pad AAAA: {padAAAA:X}")
                ctx.log(f"geom_ptr:      0x{geom_ptr:X}")
                ctx.log(f"clump_ptr:     0x{clump_ptr:X}")
                ctx.log(f"link_ptr:      0x{link_ptr:X}")
                ctx.log(f"link_ptr2:     0x{link_ptr2:X}")
                ctx.log(f"render_cb:     0x{render_cb:X}")
                ctx.log(f"model_info_id: {model_info_id}")
                ctx.log(f"vis_id_flag:   0x{vis_id_flag:X}")
                ctx.log(f"hierarchy_ptr: 0x{hierarchy_ptr:X}")
                if material_ptr:
                    ctx.log(f"material_ptr (peek): 0x{material_ptr:X}")

                atomic_info.section_type = ctx.section_type
                atomic_info.import_type = ctx.import_type
                atomic_info.frame_ptr = frame_ptr
                atomic_info.geom_ptr = geom_ptr
                atomic_info.material_ptr = material_ptr
                atomic_info.render_cb = render_cb
                atomic_info.model_info_id = model_info_id
                atomic_info.vis_id_flag = vis_id_flag
                atomic_info.hierarchy_ptr = hierarchy_ptr

                frame_tree_ptr = int(frame_ptr or 0)
                if str(mdl_type or "").upper().strip() in {"CUT", "VEH"} and int(getattr(ctx, "clump_root_frame_ptr", 0) or 0):
                    frame_tree_ptr = int(getattr(ctx, "clump_root_frame_ptr", 0) or 0)
                    if str(mdl_type or "").upper().strip() == "CUT":
                        ctx.log(f"Cutscene actor: walking frame tree from Clump.root_frame 0x{frame_tree_ptr:X} instead of Atomic.frame_ptr 0x{frame_ptr:X}.")
                    else:
                        ctx.log(f"VehicleModel: walking full frame tree from Clump.root_frame 0x{frame_tree_ptr:X} instead of first Atomic.frame_ptr 0x{frame_ptr:X}.")

                if frame_tree_ptr != 0:
                    try:
                        arm = process_frame_tree(ctx, f, frame_tree_ptr)
                        if hierarchy_ptr != 0:
                            try:
                                parse_hierarchy_table(ctx, f, hierarchy_ptr, arm)
                            except Exception as hierarchy_error:
                                ctx.log(f"⚠️ Failed to parse hierarchy table: {hierarchy_error}")
                        atomic_info.armature = arm
                    except Exception as e:
                        ctx.log(f"⚠️ Failed to build armature: {e}")
                        atomic_info.armature = None

                if platform == "PS2":
                    atomic_info.ps2_geometry = read_ps2_geometry(ctx, f, geom_ptr)
                else:
                    atomic_info.psp_geometry = read_psp_geometry(ctx, f, geom_ptr)

                if platform == "PS2" and str(mdl_type or "").upper().strip() == "VEH" and int(getattr(ctx, "clump_ptr", 0) or 0):
                    try:
                        vehicle_atomics = readVehicleAtomics(ctx, f, atomic_info.armature)
                        if vehicle_atomics:
                            ctx.atomics = vehicle_atomics
                            ctx.atomic = vehicle_atomics[0]
                            atomic_info = ctx.atomic
                    except Exception as vehicle_error:
                        ctx.log(f"⚠ VehicleModel multi-atomic parse failed: {vehicle_error}")

                try:
                    arm = atomic_info.armature
                    missing_frames = (
                        arm is None or
                        not getattr(arm, 'frame_names', None) or
                        len(getattr(arm, 'frame_names', {})) == 0
                    )
                except Exception:
                    missing_frames = True
                if missing_frames:

                    import_type = int(getattr(ctx, 'import_type', 0) or 0)
                    if import_type in (0, 1):
                        bone_names = list(commonBoneNamesLCS)
                    elif import_type in (2, 3):
                        bone_names = list(commonBoneNamesVCS)
                    else:
                        bone_names = [f"bone_{i:02d}" for i in range(32)]

                    fallback_arm = StoriesArmatureInfo()
                    for idx, bname in enumerate(bone_names):
                        mat = Matrix.Identity(4)
                        ptr_id = idx
                        fallback_arm.frame_mats_local[ptr_id] = mat
                        fallback_arm.frame_mats_world[ptr_id] = mat
                        fallback_arm.frame_mats_global[ptr_id] = mat
                        fallback_arm.frame_mats_computed_world[ptr_id] = mat
                        fallback_arm.frame_matrix_local_offsets[ptr_id] = 0
                        fallback_arm.frame_matrix_global_offsets[ptr_id] = 0
                        fallback_arm.frame_parent_ptrs[ptr_id] = 0
                        fallback_arm.frame_child_ptrs[ptr_id] = 0
                        fallback_arm.frame_sibling_ptrs[ptr_id] = 0
                        fallback_arm.frame_names[ptr_id] = bname
                    atomic_info.armature = fallback_arm

        txt_path = os.path.splitext(filepath)[0] + "_import_log.txt"
        try:
            with open(txt_path, "w", encoding="utf-8") as outf:
                outf.write("\n".join(ctx.debug_log))
            ctx.log(f"✔ Debug log written to: {txt_path}")
        except Exception as e:
            ctx.log(f"✗ Failed to write debug log: {e}")

        self.ctx = ctx
        return ctx

def read_stories_mdl(filepath: str, platform: str, mdl_type: str) -> StoriesMDLContext:
    reader = read_stories(filepath, platform, mdl_type)
    return reader.read()

import math
import struct

from dataclasses import dataclass
from typing import List, Tuple, Optional

LCSCLUMPPS2 = 0x00000002
VCSCLUMPPS2 = 0x0000AA02

LCSATOMIC1 = 0x01050001
LCSATOMIC2 = 0x01000001
VCSATOMIC1 = 0x0004AA01
VCSATOMIC2 = 0x0300AA00

FIRST_SECTION_OFFSET = 0x24

TRI_STRIP_FLAG = 0x60000041

VIF_UNPACK = 0x6C018000

VIF_STMASK = 0x20000000
VIF_STROW = 0x30000000

VIF_POS_HEADER = 0x79000000
VIF_TEX_HEADER = 0x76004000

VIF_MSCAL = 0x14000006

@dataclass
class Ps2Vertex:
    x: float
    y: float
    z: float
    u: float
    v: float
    nx: float = 0.0
    ny: float = 0.0
    nz: float = 1.0
    r: int = 255
    g: int = 255
    b: int = 255
    a: int = 255
    bone_indices: Tuple[int, int, int, int] = (0, 0, 0, 0)
    bone_weights: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    skin_raw_dwords: Any = None

@dataclass
class ScalePos:
    scale: Tuple[float, float, float]
    pos: Tuple[float, float, float]

def write_u8(buf: bytearray, value: int) -> None:
    buf += struct.pack("<B", value & 0xFF)

def write_u16(buf: bytearray, value: int) -> None:
    buf += struct.pack("<H", value & 0xFFFF)

def write_i16(buf: bytearray, value: int) -> None:
    buf += struct.pack("<h", int(value))

def write_u32(buf_or_value, value: int | None = None):

    if value is None:
        return struct.pack("<I", int(buf_or_value) & 0xFFFFFFFF)

    buf = buf_or_value
    buf += struct.pack("<I", int(value) & 0xFFFFFFFF)
    return None

def reserve_u32(buf: bytearray, initial_value: int = 0) -> int:
    off = len(buf)
    write_u32(buf, initial_value)
    return off

def write_i32(buf: bytearray, value: int) -> None:
    buf += struct.pack("<i", int(value))

def write_f32(buf: bytearray, value: float) -> None:
    buf += struct.pack("<f", float(value))

def write_cstring(
    buf: bytearray,
    text: str,
    *,
    encoding: str = "ascii",
    errors: str = "ignore",
) -> int:

    start_off = len(buf)
    if text is None:
        buf.append(0)
        return start_off

    try:
        raw = str(text).encode(encoding, errors=errors)
    except Exception:
        raw = b""

    buf.extend(raw)
    buf.append(0)
    return start_off

def align_buffer(buf: bytearray, alignment: int) -> None:
    remainder = len(buf) % alignment
    if remainder != 0:
        buf += b"\x00" * (alignment - remainder)

def pad_bytes_to(data: bytearray, alignment: int) -> None:
    r = len(data) % alignment
    if r:
        data.extend(b"\x00" * (alignment - r))

def pad_to_sector(buf: bytearray, sector: int = 0x800) -> None:
    pad = (-len(buf)) % sector
    if pad:
        buf += b"\x00" * pad

def read_root_base_scale_pos(root_obj) -> Optional[ScalePos]:
    def vec3_from_any(v) -> Optional[Tuple[float, float, float]]:
        if v is None:
            return None
        if isinstance(v, (list, tuple)) and len(v) >= 3:
            return (float(v[0]), float(v[1]), float(v[2]))
        try:

            return (float(v[0]), float(v[1]), float(v[2]))
        except Exception:
            return None

    if hasattr(root_obj, "bleeds_leeds_scale_base") and hasattr(root_obj, "bleeds_leeds_pos_base"):
        s = vec3_from_any(getattr(root_obj, "bleeds_leeds_scale_base"))
        p = vec3_from_any(getattr(root_obj, "bleeds_leeds_pos_base"))
        if s is not None and p is not None:
            return ScalePos(scale=s, pos=p)

    for sk, pk in (
        ("bleeds_leeds_scale_base", "bleeds_leeds_pos_base"),
        ("mdl_scale", "mdl_pos"),
        ("leeds_scale", "leeds_pos"),
    ):
        if isinstance(root_obj, dict):
            s = vec3_from_any(root_obj.get(sk))
            p = vec3_from_any(root_obj.get(pk))
        else:
            s = vec3_from_any(root_obj.get(sk) if hasattr(root_obj, "get") else (root_obj[sk] if sk in root_obj else None))
            p = vec3_from_any(root_obj.get(pk) if hasattr(root_obj, "get") else (root_obj[pk] if pk in root_obj else None))
        if s is not None and p is not None:
            return ScalePos(scale=s, pos=p)

    return None

def compute_effective_scale_pos(root_obj) -> Optional[ScalePos]:
    base = read_root_base_scale_pos(root_obj)
    if base is None:
        return None

    sx, sy, sz = base.scale
    px, py, pz = base.pos

    rs = getattr(root_obj, "scale", None)
    rl = getattr(root_obj, "location", None)

    if rs is None or rl is None:

        return base

    eff_scale = (float(sx) * float(rs[0]), float(sy) * float(rs[1]), float(sz) * float(rs[2]))
    eff_pos = (
        (float(px) * float(rs[0])) + float(rl[0]),
        (float(py) * float(rs[1])) + float(rl[1]),
        (float(pz) * float(rs[2])) + float(rl[2]),
    )

    eps = 1e-10
    if abs(eff_scale[0]) < eps or abs(eff_scale[1]) < eps or abs(eff_scale[2]) < eps:
        return None

    return ScalePos(scale=eff_scale, pos=eff_pos)

PS2_MAX_TRISTRIP_VERTS: int = 70
PS2_MAX_TRISTRIP_VERTS_PED: int = 42

def split_ps2_tristrip_vertices(
    strip: List["Ps2Vertex"],
    *,
    max_verts: int = PS2_MAX_TRISTRIP_VERTS,
    overlap: int = 2,
) -> List[List["Ps2Vertex"]]:
    if max_verts < 3:
        max_verts = 3
    if overlap < 0:
        overlap = 0
    if overlap >= max_verts:
        overlap = max_verts - 1

    n = len(strip)
    if n <= max_verts:
        return [strip] if strip else []

    chunks: List[List["Ps2Vertex"]] = []

    start = 0
    while start < n:
        if start == 0:
            end = min(n, max_verts)
            chunks.append(strip[start:end])
            start = end
            continue

        chunk_start = max(0, start - overlap)
        end = min(n, chunk_start + max_verts)
        chunks.append(strip[chunk_start:end])

        start = end

    chunks = [c for c in chunks if len(c) >= 3]
    return chunks

def split_ps2_ped_vif_segments(
    strip: List["Ps2Vertex"],
    *,
    max_verts: int = PS2_MAX_TRISTRIP_VERTS_PED,
) -> List[List["Ps2Vertex"]]:
    if max_verts < 3:
        max_verts = 3

    n = len(strip)
    if n <= max_verts:
        return [strip] if len(strip) >= 3 else []

    def same_vertex(a: "Ps2Vertex", b: "Ps2Vertex") -> bool:
        try:
            return a is b or (
                float(a.x) == float(b.x) and float(a.y) == float(b.y) and float(a.z) == float(b.z)
                and float(a.u) == float(b.u) and float(a.v) == float(b.v)
                and tuple(getattr(a, 'bone_indices', ())) == tuple(getattr(b, 'bone_indices', ()))
            )
        except Exception:
            return a is b

    def find_safe_split(start_index: int, hard_end: int) -> int:
        for split_index in range(hard_end, start_index + 3, -1):
            if split_index - 2 < start_index or split_index + 1 >= n:
                continue
            if same_vertex(strip[split_index - 2], strip[split_index - 1]) and same_vertex(strip[split_index], strip[split_index + 1]):
                return split_index
        for split_index in range(hard_end, start_index + 3, -1):
            if split_index - 2 >= start_index and same_vertex(strip[split_index - 2], strip[split_index - 1]):
                return split_index
        return hard_end

    chunks: List[List["Ps2Vertex"]] = []
    start = 0
    while start < n:
        hard_end = min(n, start + max_verts)
        end = find_safe_split(start, hard_end) if hard_end < n else hard_end
        if end <= start + 2:
            end = hard_end
        chunk = strip[start:end]
        if len(chunk) >= 3:
            chunks.append(chunk)
        start = end
    return chunks

def trim_ps2_ped_dma_packet_to_vertex_count(packet: bytes, target_vertex_count: int) -> bytearray:
    try:
        target_vertex_count = int(target_vertex_count)
    except Exception:
        return bytearray(packet or b"")

    raw = bytes(packet or b"")
    if target_vertex_count <= 0 or len(raw) < 16:
        return bytearray(raw)

    first_word = struct.unpack_from("<I", raw, 0)[0]
    has_dma_tag = ((first_word >> 28) & 0xF) == 0x6
    payload = raw[16:] if has_dma_tag else raw

    def align4(value: int) -> int:
        return (int(value) + 3) & ~3

    def parse_segment(data: bytes, start: int) -> Optional[Tuple[int, int, Dict[str, Any]]]:
        try:
            if start + 48 > len(data):
                return None
            if struct.unpack_from("<I", data, start)[0] != 0x6C018000:
                return None
            count = struct.unpack_from("<I", data, start + 12)[0] & 0xFF
            if count <= 0:
                return None

            cursor = start + 48

            pos_header = struct.unpack_from("<I", data, cursor)[0]
            cursor += 4
            pos_data_off = cursor
            pos_data_len = count * 6
            cursor += align4(pos_data_len)

            uv_prolog_off = cursor
            cursor += 28
            uv_header = struct.unpack_from("<I", data, cursor)[0]
            cursor += 4
            uv_data_off = cursor
            uv_data_len = count * 2
            cursor += align4(uv_data_len)

            norm_header = struct.unpack_from("<I", data, cursor)[0]
            cursor += 4
            norm_data_off = cursor
            norm_data_len = count * 3
            cursor += align4(norm_data_len)

            skin_header = struct.unpack_from("<I", data, cursor)[0]
            cursor += 4
            skin_data_off = cursor
            skin_data_len = count * 16
            cursor += skin_data_len

            if cursor + 4 > len(data):
                return None
            mscal = struct.unpack_from("<I", data, cursor)[0]
            if mscal != VIF_MSCAL:
                return None
            cursor += 4

            segment_end = (cursor + 15) & ~15
            if segment_end > len(data):
                segment_end = len(data)

            info = {
                "count": count,
                "split_header": data[start:start + 48],
                "pos_header": pos_header,
                "pos_data": data[pos_data_off:pos_data_off + pos_data_len],
                "uv_prolog": data[uv_prolog_off:uv_prolog_off + 28],
                "uv_header": uv_header,
                "uv_data": data[uv_data_off:uv_data_off + uv_data_len],
                "norm_header": norm_header,
                "norm_data": data[norm_data_off:norm_data_off + norm_data_len],
                "skin_header": skin_header,
                "skin_data": data[skin_data_off:skin_data_off + skin_data_len],
            }
            return segment_end, count, info
        except Exception:
            return None

    def update_count_header(header: int, count: int) -> int:
        return (int(header) & 0xFF00FFFF) | ((int(count) & 0xFF) << 16)

    def rebuild_segment(info: Dict[str, Any], keep_count: int) -> bytes:
        keep_count = max(0, min(int(keep_count), int(info.get("count", 0))))
        if keep_count < 3:
            return b""

        out = bytearray(info["split_header"])
        struct.pack_into("<I", out, 12, keep_count & 0xFF)
        old_count_word = struct.unpack_from("<I", out, 16)[0]
        struct.pack_into("<I", out, 16, (old_count_word & 0xFFFFFF00) | (keep_count & 0xFF))

        out.extend(struct.pack("<I", update_count_header(info["pos_header"], keep_count)))
        out.extend(info["pos_data"][:keep_count * 6])
        pad_bytes_to(out, 4)

        out.extend(info["uv_prolog"])
        out.extend(struct.pack("<I", update_count_header(info["uv_header"], keep_count)))
        out.extend(info["uv_data"][:keep_count * 2])
        pad_bytes_to(out, 4)

        out.extend(struct.pack("<I", update_count_header(info["norm_header"], keep_count)))
        out.extend(info["norm_data"][:keep_count * 3])
        pad_bytes_to(out, 4)

        out.extend(struct.pack("<I", update_count_header(info["skin_header"], keep_count)))
        out.extend(info["skin_data"][:keep_count * 16])

        out.extend(write_u32(VIF_MSCAL))
        pad_bytes_to(out, 16)
        return bytes(out)

    pos = 0
    remaining = int(target_vertex_count)
    new_payload = bytearray()
    parsed_any = False

    while pos < len(payload) and remaining > 0:
        parsed = parse_segment(payload, pos)
        if parsed is None:
            break
        segment_end, count, info = parsed
        parsed_any = True
        keep = min(int(count), remaining)
        rebuilt = rebuild_segment(info, keep)
        if rebuilt:
            new_payload.extend(rebuilt)
            remaining -= keep
        pos = int(segment_end)

    if not parsed_any or remaining > 0:
        return bytearray(raw)

    if has_dma_tag:
        out = bytearray(raw[:16])
        qwc_total = len(new_payload) // 16
        struct.pack_into("<I", out, 0, 0x60000000 | (qwc_total & 0xFFFF))
        out.extend(new_payload)
    else:
        out = bytearray(new_payload)

    try:
        validate_ps2_dma_vif_payload(bytes(out[16:] if has_dma_tag else out), vif_profile="PED")
    except Exception:
        return bytearray(raw)

    return out

def trim_ps2_ped_dma_packet_to_byte_length(packet: bytes, target_byte_length: int) -> bytearray:
    raw = bytes(packet or b"")
    try:
        target_byte_length = int(target_byte_length)
    except Exception:
        return bytearray(raw)
    if target_byte_length <= 0 or len(raw) <= target_byte_length:
        return bytearray(raw)

    first_word = struct.unpack_from("<I", raw, 0)[0] if len(raw) >= 4 else 0
    has_dma_tag = ((first_word >> 28) & 0xF) == 0x6
    payload = raw[16:] if has_dma_tag and len(raw) >= 16 else raw

    current_total = 0
    pos = 0
    while pos < len(payload):
        try:
            if pos + 48 > len(payload) or struct.unpack_from("<I", payload, pos)[0] != 0x6C018000:
                break
            count = struct.unpack_from("<I", payload, pos + 12)[0] & 0xFF
            if count <= 0:
                break
            current_total += count

            def align4(value: int) -> int:
                return (int(value) + 3) & ~3

            cursor = pos + 48
            cursor += 4 + align4(count * 6)
            cursor += 28
            cursor += 4 + align4(count * 2)
            cursor += 4 + align4(count * 3)
            cursor += 4 + (count * 16)
            if cursor + 4 > len(payload) or struct.unpack_from("<I", payload, cursor)[0] != VIF_MSCAL:
                break
            cursor += 4
            pos = (cursor + 15) & ~15
        except Exception:
            break

    if current_total <= 0:
        return bytearray(raw)

    best = bytearray(raw)
    for target_vertices in range(current_total - 1, 2, -1):
        candidate = trim_ps2_ped_dma_packet_to_vertex_count(raw, target_vertices)
        if len(candidate) <= target_byte_length:
            best = candidate
            break

    return best

def validate_ps2_dma_vif_payload(payload: bytes, *, vif_profile: str = "SIM") -> None:
    profile = str(vif_profile).upper().strip()
    if profile != "PED":
        if (len(payload) % 16) != 0:
            raise ValueError(f"PS2 DMA/VIF payload is not 16-byte aligned (len={len(payload)}).")
        if len(payload) < 4 or struct.unpack_from("<I", payload, len(payload) - 16)[0] != VIF_MSCAL:
            raise ValueError("PS2 DMA/VIF payload does not end with MSCAL on a qword boundary.")
        return

    pos = 0
    payload_len = len(payload)
    strip_index = 0

    while pos < payload_len:
        strip_start = pos
        if (payload_len - pos) < 48:
            raise ValueError(
                f"PED DMA/VIF strip {strip_index} is truncated before the split header "
                f"(offset 0x{strip_start:X}, remaining {payload_len - pos} bytes)."
            )

        split_marker = struct.unpack_from("<I", payload, pos)[0]
        if split_marker != 0x6C018000:
            raise ValueError(
                f"PED DMA/VIF strip {strip_index} does not begin with 0x6C018000 "
                f"(offset 0x{strip_start:X}, got 0x{split_marker:08X})."
            )

        zero0 = struct.unpack_from("<I", payload, pos + 4)[0]
        zero1 = struct.unpack_from("<I", payload, pos + 8)[0]
        split_count0 = struct.unpack_from("<I", payload, pos + 12)[0] & 0xFF
        split_count1_word = struct.unpack_from("<I", payload, pos + 16)[0]
        split_count1 = split_count1_word & 0xFF
        stmask = struct.unpack_from("<I", payload, pos + 20)[0]
        stmask_value = struct.unpack_from("<I", payload, pos + 24)[0]
        strow = struct.unpack_from("<I", payload, pos + 28)[0]
        strow_values = struct.unpack_from("<4I", payload, pos + 32)

        if zero0 != 0 or zero1 != 0:
            raise ValueError(
                f"PED DMA/VIF strip {strip_index} split header contains non-zero reserved dwords "
                f"(offset 0x{strip_start:X})."
            )
        if split_count0 <= 0 or split_count0 > 0xFF:
            raise ValueError(
                f"PED DMA/VIF strip {strip_index} has invalid split vertex count {split_count0} "
                f"at offset 0x{strip_start:X}."
            )
        if split_count1 != split_count0 or (split_count1_word & 0x8000) == 0:
            raise ValueError(
                f"PED DMA/VIF strip {strip_index} has mismatched split counts/flags "
                f"(count0={split_count0}, word=0x{split_count1_word:08X}) at offset 0x{strip_start:X}."
            )
        if stmask != VIF_STMASK or stmask_value != 0x40404040:
            raise ValueError(
                f"PED DMA/VIF strip {strip_index} has invalid split STMASK block at offset 0x{strip_start:X}."
            )
        if strow != VIF_STROW or any(v != 0 for v in strow_values):
            raise ValueError(
                f"PED DMA/VIF strip {strip_index} has invalid split STROW block at offset 0x{strip_start:X}."
            )

        pos += 48

        pos_header = struct.unpack_from("<I", payload, pos)[0]
        pos_cmd = (pos_header >> 24) & 0x7F
        pos_count = (pos_header >> 16) & 0xFF
        if pos_cmd != 0x79 or pos_count != split_count0 or (pos_header & 0xFFFF) != 0x8001:
            raise ValueError(
                f"PED DMA/VIF strip {strip_index} has invalid position UNPACK header "
                f"0x{pos_header:08X} at offset 0x{pos:X}."
            )
        pos += 4 + (pos_count * 6)
        pos += ((4 - ((pos_count * 6) % 4)) % 4)

        if (payload_len - pos) < 28:
            raise ValueError(
                f"PED DMA/VIF strip {strip_index} is truncated before the UV STMASK/STROW block "
                f"at offset 0x{pos:X}."
            )
        if struct.unpack_from("<I", payload, pos)[0] != VIF_STMASK:
            raise ValueError(
                f"PED DMA/VIF strip {strip_index} has invalid UV STMASK opcode at offset 0x{pos:X}."
            )
        if struct.unpack_from("<I", payload, pos + 4)[0] != 0x50505050:
            raise ValueError(
                f"PED DMA/VIF strip {strip_index} has invalid UV STMASK value at offset 0x{pos + 4:X}."
            )
        if struct.unpack_from("<I", payload, pos + 8)[0] != VIF_STROW:
            raise ValueError(
                f"PED DMA/VIF strip {strip_index} has invalid UV STROW opcode at offset 0x{pos + 8:X}."
            )
        uv_row_values = struct.unpack_from("<4I", payload, pos + 12)
        if uv_row_values != (0, 0, 0x000000FF, 0):
            raise ValueError(
                f"PED DMA/VIF strip {strip_index} has invalid UV STROW values at offset 0x{pos + 12:X}."
            )
        pos += 28

        uv_header = struct.unpack_from("<I", payload, pos)[0]
        uv_cmd = (uv_header >> 24) & 0x7F
        uv_count = (uv_header >> 16) & 0xFF
        if uv_cmd != 0x76 or uv_count != split_count0 or (uv_header & 0xFFFF) != 0xC055:
            raise ValueError(
                f"PED DMA/VIF strip {strip_index} has invalid UV UNPACK header 0x{uv_header:08X} "
                f"at offset 0x{pos:X}."
            )
        pos += 4 + (uv_count * 2)
        pos += ((4 - ((uv_count * 2) % 4)) % 4)

        norm_header = struct.unpack_from("<I", payload, pos)[0]
        norm_cmd = (norm_header >> 24) & 0x7F
        norm_count = (norm_header >> 16) & 0xFF
        if norm_cmd != 0x6A or norm_count != split_count0 or (norm_header & 0xFFFF) != 0x802B:
            raise ValueError(
                f"PED DMA/VIF strip {strip_index} has invalid normal UNPACK header 0x{norm_header:08X} "
                f"at offset 0x{pos:X}."
            )
        pos += 4 + (norm_count * 3)
        pos += ((4 - ((norm_count * 3) % 4)) % 4)

        skin_header = struct.unpack_from("<I", payload, pos)[0]
        skin_cmd = (skin_header >> 24) & 0x7F
        skin_count = (skin_header >> 16) & 0xFF
        if skin_cmd != 0x6C or skin_count != split_count0 or (skin_header & 0xFFFF) != 0x807F:
            raise ValueError(
                f"PED DMA/VIF strip {strip_index} has invalid skin UNPACK header 0x{skin_header:08X} "
                f"at offset 0x{pos:X}."
            )
        pos += 4 + (skin_count * 16)

        mscal = struct.unpack_from("<I", payload, pos)[0]
        if mscal != VIF_MSCAL:
            raise ValueError(
                f"PED DMA/VIF strip {strip_index} does not terminate with MSCAL at offset 0x{pos:X} "
                f"(got 0x{mscal:08X})."
            )
        pos += 4
        pos += ((16 - (pos % 16)) % 16)
        strip_index += 1

    if pos != payload_len:
        raise ValueError(
            f"PED DMA/VIF payload length mismatch: parser consumed {pos} bytes, buffer has {payload_len} bytes."
        )

def validate_dma_ref_packet(packet: bytes, *, vif_profile: str = "SIM") -> None:
    if len(packet) < 16:
        raise ValueError(f"DMA REF packet too short ({len(packet)} bytes).")

    tag = struct.unpack_from("<I", packet, 0)[0]
    if (tag & 0xF0000000) != 0x60000000:
        raise ValueError(f"Expected DMA REF tag, got 0x{tag:08X}.")

    qwc = tag & 0xFFFF
    payload = packet[16:]
    if (len(payload) % 16) != 0:
        raise ValueError(f"DMA REF payload is not 16-byte aligned (len={len(payload)}).")

    expected_qwc = len(payload) // 16
    if qwc != expected_qwc:
        raise ValueError(
            f"DMA REF QWC mismatch: tag says {qwc}, payload needs {expected_qwc} qwords."
        )

    validate_ps2_dma_vif_payload(payload, vif_profile=vif_profile)

def build_ps2_dma_for_strip(
    verts: List[Ps2Vertex],
    *,
    emit_dma_tag: bool = True,
    use_normals: bool = True,
    max_batch_verts: int = 70,
    scale_pos_override: Optional[ScalePos] = None,
    rounding_mode: str = "ROUND",

    vif_profile: str = "SIM",

    include_split_header: bool = False,
) -> Tuple[bytearray, ScalePos]:

    if max_batch_verts <= 0:
        max_batch_verts = 70

    num_verts = len(verts)
    if num_verts == 0:
        return bytearray(), ScalePos((1.0, 1.0, 1.0), (0.0, 0.0, 0.0))

    if num_verts > max_batch_verts:
        raise ValueError(
            f"Triangle strip has {num_verts} verts, but max is {max_batch_verts}. "
            f"Split the mesh/strip before export (do NOT auto-segment inside DMA)."
        )

    GLOBAL_SCALE = 100.0 * 0.00000030518203134641490805874367518203
    if scale_pos_override is not None:
        scale_pos = scale_pos_override
    else:
        xs = [float(v.x) for v in verts]
        ys = [float(v.y) for v in verts]
        zs = [float(v.z) for v in verts]

        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        zmin, zmax = min(zs), max(zs)

        cx = (xmin + xmax) * 0.5
        cy = (ymin + ymax) * 0.5
        cz = (zmin + zmax) * 0.5

        hx = max(1.0e-9, (xmax - xmin) * 0.5)
        hy = max(1.0e-9, (ymax - ymin) * 0.5)
        hz = max(1.0e-9, (zmax - zmin) * 0.5)

        safe_raw_limit = 28672.0
        denom = safe_raw_limit * GLOBAL_SCALE
        sx = float(hx) / denom
        sy = float(hy) / denom
        sz = float(hz) / denom

        scale_pos = ScalePos((sx, sy, sz), (cx, cy, cz))

    sx, sy, sz = scale_pos.scale
    tx, ty, tz = scale_pos.pos

    def apply_round(x: float) -> int:
        if rounding_mode == "FLOOR":
            return int(math.floor(x))
        if rounding_mode == "CEIL":
            return int(math.ceil(x))

        if x >= 0.0:
            return int(math.floor(x + 0.5))
        return int(math.ceil(x - 0.5))

    def encode_pos_i16(px: float, py: float, pz: float) -> bytes:

        ix = apply_round((px - tx) / (sx * GLOBAL_SCALE)) if abs(sx) > 1.0e-12 else 0
        iy = apply_round((py - ty) / (sy * GLOBAL_SCALE)) if abs(sy) > 1.0e-12 else 0
        iz = apply_round((pz - tz) / (sz * GLOBAL_SCALE)) if abs(sz) > 1.0e-12 else 0

        ix = max(-32768, min(32767, ix))
        iy = max(-32768, min(32767, iy))
        iz = max(-32768, min(32767, iz))

        return struct.pack("<hhh", ix, iy, iz)

    def encode_uv_bytes(u: float, v: float) -> bytes:
        uu = int(apply_round(u * 127.5))
        vv = int(apply_round(v * 127.5))
        uu = max(0, min(255, uu))
        vv = max(0, min(255, vv))
        return struct.pack("<BB", uu, vv)

    def encode_norm_bytes(nx: float, ny: float, nz: float) -> bytes:

        def clamp_s8(x: int) -> int:
            return max(-128, min(127, x))

        ix = clamp_s8(apply_round(nx * 127.0))
        iy = clamp_s8(apply_round(ny * 127.0))
        iz = clamp_s8(apply_round(nz * 127.0))
        return struct.pack("<bbb", ix, iy, iz)

    seg_count = num_verts
    payload = bytearray()
    is_ped = (str(vif_profile).upper().strip() == "PED")
    emit_normals = bool(use_normals) or is_ped

    if include_split_header:
        payload.extend(write_u32(0x6C018000))
        payload.extend(write_u32(0))
        payload.extend(write_u32(0))
        payload.extend(write_u32(seg_count & 0xFF))
        payload.extend(write_u32((seg_count & 0xFF) | 0x00008000))

        if is_ped:

            payload.extend(write_u32(VIF_STMASK))
            payload.extend(write_u32(0x40404040))
            payload.extend(write_u32(VIF_STROW))
            payload.extend(write_u32(0))
            payload.extend(write_u32(0))
            payload.extend(write_u32(0))
            payload.extend(write_u32(0))
        else:

            payload.extend(write_u32(0))
            payload.extend(write_u32(0x40404020))
            payload.extend(write_u32(0x40404040))

    if not is_ped:

        payload.extend(write_u32(VIF_UNPACK))
        payload.extend(write_u32(0))
        payload.extend(write_u32(0))
        payload.extend(write_u32(seg_count))
        payload.extend(write_u32(0x8000 | (seg_count & 0xFFFF)))

        payload.extend(write_u32(VIF_STMASK))
        payload.extend(write_u32(0x40404040))
        payload.extend(write_u32(VIF_STROW))
        payload.extend(write_u32(0))
        payload.extend(write_u32(0))
        payload.extend(write_u32(0))
        payload.extend(write_u32(0))

    pos_header = (0x79 << 24) | ((seg_count & 0xFF) << 16) | 0x8001
    payload.extend(write_u32(pos_header))
    for v in verts:
        payload.extend(encode_pos_i16(v.x, v.y, v.z))
    pad_bytes_to(payload, 4)

    payload.extend(write_u32(VIF_STMASK))
    payload.extend(write_u32(0x50505050))
    payload.extend(write_u32(VIF_STROW))
    payload.extend(write_u32(0))
    payload.extend(write_u32(0))
    payload.extend(write_u32(0x000000FF))
    payload.extend(write_u32(0))

    if str(vif_profile).upper().strip() == "PED":
        tex_header = (0x76 << 24) | ((seg_count & 0xFF) << 16) | 0xC055
    else:
        tex_header = (0x76 << 24) | ((seg_count & 0xFF) << 16) | 0x808D
    payload.extend(write_u32(tex_header))
    for v in verts:
        payload.extend(encode_uv_bytes(v.u, v.v))
    pad_bytes_to(payload, 4)

    if emit_normals:

        if str(vif_profile).upper().strip() == "PED":
            norm_header = (0x6A << 24) | ((seg_count & 0xFF) << 16) | 0x802B
        else:
            norm_header = (0x6A << 24) | ((seg_count & 0xFF) << 16) | 0x8047
        payload.extend(write_u32(norm_header))
        for v in verts:
            payload.extend(encode_norm_bytes(v.nx, v.ny, v.nz))
        pad_bytes_to(payload, 4)

    def _encode_skin_payload(v: Ps2Vertex) -> bytes:
        raw_dwords = getattr(v, 'skin_raw_dwords', None)

        def raw_skin_bytes_or_none() -> Optional[bytes]:
            if raw_dwords is None:
                return None
            try:
                raw_values = list(raw_dwords)[:4]
            except Exception:
                return None
            if len(raw_values) < 4:
                return None
            try:
                if not any((int(raw_value) & 0xFFFFFFFF) != 0 for raw_value in raw_values[:4]):
                    return None
            except Exception:
                pass
            out_raw = bytearray()
            try:
                for raw_value in raw_values[:4]:
                    out_raw.extend(struct.pack('<I', int(raw_value) & 0xFFFFFFFF))
            except Exception:
                return None
            return bytes(out_raw)

        idxs = list(getattr(v, 'bone_indices', (0, 0, 0, 0)) or (0, 0, 0, 0))[:4]
        wts = list(getattr(v, 'bone_weights', (0.0, 0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0, 0.0))[:4]
        while len(idxs) < 4:
            idxs.append(0)
        while len(wts) < 4:
            wts.append(0.0)

        pairs = []
        for bi, wt in zip(idxs, wts):
            try:
                bi_i = int(bi)
            except Exception:
                bi_i = 0
            if bi_i < 0:
                bi_i = 0
            if bi_i > 0x3FFF:
                bi_i = 0x3FFF
            try:
                wt_f = float(wt)
            except Exception:
                wt_f = 0.0
            if not math.isfinite(wt_f):
                wt_f = 0.0
            if wt_f < 0.0:
                wt_f = 0.0
            pairs.append([bi_i, wt_f])

        raw_fallback = raw_skin_bytes_or_none()
        meaningful_generated_weights = any(p[1] > 1.0e-8 for p in pairs)

        generated_is_root_placeholder = False
        if meaningful_generated_weights:
            nonzero_pairs = [(bi, wt) for bi, wt in pairs if wt > 1.0e-8]
            if len(nonzero_pairs) == 1 and int(nonzero_pairs[0][0]) == 0 and raw_fallback is not None:
                generated_is_root_placeholder = True

        if (not meaningful_generated_weights or generated_is_root_placeholder) and raw_fallback is not None:
            return raw_fallback

        pairs.sort(key=lambda p: p[1], reverse=True)
        total_w = sum(p[1] for p in pairs)
        if total_w > 1.0e-8:
            inv = 1.0 / total_w
            for p in pairs:
                p[1] *= inv
        elif raw_fallback is not None:
            return raw_fallback
        else:
            pairs = [[0, 1.0], [0, 0.0], [0, 0.0], [0, 0.0]]

        while len(pairs) < 4:
            pairs.append([0, 0.0])

        out_skin = bytearray()
        for bi_i, wt_f in pairs[:4]:
            raw_word = _encode_ps2_ped_skin_word(bi_i, wt_f) & 0xFFFFFFFF
            out_skin.extend(struct.pack('<I', raw_word))
        return bytes(out_skin)

    has_skin_stream = is_ped or any(
        any(int(b) != 0 for b in (getattr(v, 'bone_indices', (0, 0, 0, 0)) or (0, 0, 0, 0))) or
        any(abs(float(w)) > 1.0e-8 for w in (getattr(v, 'bone_weights', (0.0, 0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0, 0.0)))
        for v in verts
    )
    if has_skin_stream:

        if str(vif_profile).upper().strip() == "PED":
            skin_header = (0x6C << 24) | ((seg_count & 0xFF) << 16) | 0x807F
        else:
            skin_header = (0x6C << 24) | ((seg_count & 0xFF) << 16) | 0x8047
        payload.extend(write_u32(skin_header))
        for v in verts:
            payload.extend(_encode_skin_payload(v))

    payload.extend(write_u32(VIF_MSCAL))

    pad_bytes_to(payload, 16)
    validate_ps2_dma_vif_payload(payload, vif_profile=vif_profile)
    qwc_total = len(payload) // 16
    if qwc_total > 0xFFFF:
        raise ValueError(f"DMA payload too large (QWC={qwc_total}).")

    if not emit_dma_tag:
        return payload, scale_pos

    if not emit_dma_tag:
        return payload, scale_pos

    dma = bytearray()
    dma_tag = 0x60000000 | (qwc_total & 0xFFFF)
    dma.extend(write_u32(dma_tag))
    dma.extend(write_u32(0))
    dma.extend(write_u32(0))
    dma.extend(write_u32(0))
    dma.extend(payload)

    return dma, scale_pos

@dataclass
class HeaderPatchInfo:
    file_len_off: int
    local_num_off: int
    global_num_off: int
    num_entries_off: int
    ptr2_before_tex_off: int
    alloc_mem_off: int
    ptr_after_alloc_off: int

@dataclass
class HeaderPatchInfoPedPS2:

    file_len_off: int
    local_num_off: int
    global_num_off: int
    num_entries_off: int
    ptr2_before_tex_off: int
    alloc_mem_off: int
    struct_or_flags_off: int
    top_level_ptr_off: int
    extra_ptr0_off: int
    extra_ptr1_off: int
    extra_ptr2_off: int

def get_cached_atomic_hash_key(root_obj) -> int:
    if root_obj is None:
        return 0
    for key in ("bleeds_atomic_hash_key", "leeds_atomic_hash_key", "mdl_atomic_hash_key"):
        if key in root_obj:
            try:
                return int(root_obj[key]) & 0xFFFFFFFF
            except Exception:
                return 0
    return 0

def set_cached_atomic_hash_key(root_obj, value: int) -> None:
    if root_obj is None:
        return
    root_obj["bleeds_atomic_hash_key"] = int(value) & 0xFFFFFFFF

def begin_mdl_header(buf: bytearray) -> HeaderPatchInfo:
    buf += b"ldm\x00"
    write_u32(buf, 0)

    file_len_off          = reserve_u32(buf, 0)
    local_num_off         = reserve_u32(buf, 0)
    global_num_off        = reserve_u32(buf, 0)
    num_entries_off       = reserve_u32(buf, 0)
    ptr2_before_tex_off   = reserve_u32(buf, 0)
    alloc_mem_off         = reserve_u32(buf, 0)
    ptr_after_alloc_off   = reserve_u32(buf, 0)

    return HeaderPatchInfo(
        file_len_off=file_len_off,
        local_num_off=local_num_off,
        global_num_off=global_num_off,
        num_entries_off=num_entries_off,
        ptr2_before_tex_off=ptr2_before_tex_off,
        alloc_mem_off=alloc_mem_off,
        ptr_after_alloc_off=ptr_after_alloc_off,
    )

def begin_mdl_header_ped_ps2(buf: bytearray) -> HeaderPatchInfoPedPS2:
    buf += b"ldm\x00"
    write_u32(buf, 0)

    file_len_off = reserve_u32(buf, 0)
    local_num_off = reserve_u32(buf, 0)
    global_num_off = reserve_u32(buf, 0)
    num_entries_off = reserve_u32(buf, 0)
    ptr2_before_tex_off = reserve_u32(buf, 0)
    alloc_mem_off = reserve_u32(buf, 0)
    struct_or_flags_off = reserve_u32(buf, 0)
    top_level_ptr_off = reserve_u32(buf, 0)

    extra_ptr0_off = reserve_u32(buf, 0)
    extra_ptr1_off = reserve_u32(buf, 0)
    extra_ptr2_off = reserve_u32(buf, 0)

    return HeaderPatchInfoPedPS2(
        file_len_off=file_len_off,
        local_num_off=local_num_off,
        global_num_off=global_num_off,
        num_entries_off=num_entries_off,
        ptr2_before_tex_off=ptr2_before_tex_off,
        alloc_mem_off=alloc_mem_off,
        struct_or_flags_off=struct_or_flags_off,
        top_level_ptr_off=top_level_ptr_off,
        extra_ptr0_off=extra_ptr0_off,
        extra_ptr1_off=extra_ptr1_off,
        extra_ptr2_off=extra_ptr2_off,
    )

def finalize_mdl_header_ped_ps2(
    *,
    buf: bytearray,
    header: HeaderPatchInfoPedPS2,
    file_size: int,
    local_num_offset: int,
    global_num_offset: int,
    pointer_count: int,
    struct_or_flags_ptr: int,
    top_level_ptr: int,
    extra_ptr0: int,
    extra_ptr1: int,
    extra_ptr2: int,
) -> None:
    struct.pack_into("<I", buf, header.file_len_off, int(file_size) & 0xFFFFFFFF)
    struct.pack_into("<I", buf, header.local_num_off, int(local_num_offset) & 0xFFFFFFFF)
    struct.pack_into("<I", buf, header.global_num_off, int(global_num_offset) & 0xFFFFFFFF)
    struct.pack_into("<I", buf, header.num_entries_off, int(pointer_count) & 0xFFFFFFFF)

    struct.pack_into("<I", buf, header.ptr2_before_tex_off, int(local_num_offset) & 0xFFFFFFFF)

    alloc_mem = 0x00010000
    struct.pack_into("<I", buf, header.alloc_mem_off, alloc_mem)
    struct.pack_into("<I", buf, header.struct_or_flags_off, int(struct_or_flags_ptr) & 0xFFFFFFFF)
    struct.pack_into("<I", buf, header.top_level_ptr_off, int(top_level_ptr) & 0xFFFFFFFF)

    struct.pack_into("<I", buf, header.extra_ptr0_off, int(extra_ptr0) & 0xFFFFFFFF)
    struct.pack_into("<I", buf, header.extra_ptr1_off, int(extra_ptr1) & 0xFFFFFFFF)
    struct.pack_into("<I", buf, header.extra_ptr2_off, int(extra_ptr2) & 0xFFFFFFFF)

def write_pointer_tables(buf: bytearray, pointer_fields: List[int]) -> Tuple[int, int]:
    align_buffer(buf, 4)
    local_num_offset = len(buf)
    pointer_count = len(pointer_fields)
    write_u32(buf, pointer_count)

    global_num_offset = len(buf)
    for off in pointer_fields:
        write_u32(buf, off)

    return local_num_offset, global_num_offset

def write_pointer_tables_ped_ps2(
    buf: bytearray,
    pointer_fields: List[int],
    *,
    root_offset: int,
) -> Tuple[int, int]:
    local_num_offset = len(buf)

    write_u32(buf, int(root_offset) & 0xFFFFFFFF)

    global_num_offset = len(buf)
    write_u32(buf, int(local_num_offset) & 0xFFFFFFFF)

    for off in pointer_fields:
        write_u32(buf, int(off) & 0xFFFFFFFF)

    return local_num_offset, global_num_offset

def ped_ps2_pointer_field_is_allowed(field_off: int, value: int, *, hdr0_off: Optional[int] = None, hdr1_off: Optional[int] = None, clump_offset: Optional[int] = None, atomic_offset: Optional[int] = None, frame_offsets: Optional[Iterable[int]] = None, header: Optional[HeaderPatchInfoPedPS2] = None) -> bool:
    try:
        off = int(field_off)
        val = int(value) & 0xFFFFFFFF
    except Exception:
        return False
    if off < 0 or val in (0, 0xAAAAAAAA):
        return False

    allowed = set()
    if header is not None:
        for header_off in (header.struct_or_flags_off, header.top_level_ptr_off, header.extra_ptr0_off, header.extra_ptr1_off, header.extra_ptr2_off):
            if header_off is not None:
                allowed.add(int(header_off))
    for base_off in (hdr0_off, hdr1_off):
        if base_off is None:
            continue
        base = int(base_off)
        for rel in (0x04, 0x08, 0x0C, 0x90, 0x94, 0x98, 0xA4, 0xA8):
            allowed.add(base + rel)
    if clump_offset is not None:
        base = int(clump_offset)
        for rel in (0x04, 0x08, 0x0C):
            allowed.add(base + rel)
    if atomic_offset is not None:
        base = int(atomic_offset)
        for rel in (0x04, 0x08, 0x0C, 0x14, 0x18, 0x1C, 0x20, 0x2C):
            allowed.add(base + rel)
    for base in list(frame_offsets or []):
        try:
            node_base = int(base)
        except Exception:
            continue
        for rel in (0x04, 0x08, 0x0C, 0x90, 0x94, 0x98, 0xA8):
            allowed.add(node_base + rel)

    return off in allowed

def ensure_ped_ps2_pointer_fields_registered(
    buf: bytearray,
    pointer_fields: List[int],
    *,
    header: Optional[HeaderPatchInfoPedPS2] = None,
    hdr0_off: Optional[int] = None,
    hdr1_off: Optional[int] = None,
    clump_offset: Optional[int] = None,
    atomic_offset: Optional[int] = None,
    ped_frame_meta: Optional[Dict[str, Any]] = None,
    forced_fields: Optional[Iterable[int]] = None,
) -> List[int]:

    seen = {int(off) for off in pointer_fields if isinstance(off, int) or str(off).lstrip('-').isdigit()}

    frame_offsets = []
    if isinstance(ped_frame_meta, dict):
        raw_offsets = ped_frame_meta.get('node_offsets') or []
        if isinstance(raw_offsets, (list, tuple)):
            for raw_off in raw_offsets:
                try:
                    off = int(raw_off)
                except Exception:
                    continue
                if off >= 0:
                    frame_offsets.append(off)

    def read_u32_if_valid(field_off: int) -> Optional[int]:
        try:
            off = int(field_off)
        except Exception:
            return None
        if off < 0 or off + 4 > len(buf):
            return None
        try:
            return struct.unpack_from('<I', buf, off)[0]
        except Exception:
            return None

    def register_if_pointer(field_off: Optional[int]) -> None:
        if field_off is None:
            return
        try:
            off = int(field_off)
        except Exception:
            return
        if off < 0 or off in seen:
            return
        value = read_u32_if_valid(off)
        if value is None:
            return
        if not ped_ps2_pointer_field_is_allowed(
            off,
            value,
            hdr0_off=hdr0_off,
            hdr1_off=hdr1_off,
            clump_offset=clump_offset,
            atomic_offset=atomic_offset,
            frame_offsets=frame_offsets,
            header=header,
        ):
            return
        seen.add(off)
        pointer_fields.append(off)

    if forced_fields:
        for raw_off in forced_fields:
            try:
                off = int(raw_off)
            except Exception:
                continue
            if off < 0 or off in seen:
                continue
            seen.add(off)
            pointer_fields.append(off)

    if header is not None:
        register_if_pointer(header.struct_or_flags_off)
        register_if_pointer(header.top_level_ptr_off)
        register_if_pointer(header.extra_ptr0_off)
        register_if_pointer(header.extra_ptr1_off)
        register_if_pointer(header.extra_ptr2_off)

    for base_off in (hdr0_off, hdr1_off):
        if base_off is None:
            continue
        base = int(base_off)
        for rel in (0x04, 0x08, 0x0C, 0x90, 0x94, 0x98, 0xA8):
            register_if_pointer(base + rel)

    if clump_offset is not None:
        base = int(clump_offset)
        for rel in (0x04, 0x08, 0x0C):
            register_if_pointer(base + rel)

    if atomic_offset is not None:
        base = int(atomic_offset)
        for rel in (0x04, 0x08, 0x0C, 0x14, 0x18, 0x1C, 0x20, 0x2C):
            register_if_pointer(base + rel)

    for base in frame_offsets:
        for rel in (0x04, 0x08, 0x0C, 0x90, 0x94, 0x98, 0xA8):
            register_if_pointer(int(base) + rel)

    return pointer_fields

def sanitize_ped_ps2_pointer_fields(
    pointer_fields: List[int],
    *,
    disallowed_fields: Optional[Iterable[int]] = None,
) -> List[int]:

    blocked = set()
    if disallowed_fields:
        for raw_off in disallowed_fields:
            try:
                off = int(raw_off)
            except Exception:
                continue
            if off >= 0:
                blocked.add(off)

    cleaned: List[int] = []
    seen = set()

    for raw_off in pointer_fields:
        try:
            off = int(raw_off)
        except Exception:
            continue

        if off < 0 or off in blocked or off in seen:
            continue

        seen.add(off)
        cleaned.append(off)

    return cleaned

def order_ped_ps2_pointer_fields_retail_like(
    pointer_fields: List[int],
    *,
    header: Optional[HeaderPatchInfoPedPS2] = None,
    frames_offset: int = 0,
    clump_offset: int = 0,
) -> List[int]:

    unique: List[int] = []
    seen = set()
    for raw_off in pointer_fields:
        try:
            off = int(raw_off)
        except Exception:
            continue
        if off < 0 or off in seen:
            continue
        seen.add(off)
        unique.append(off)

    header_fields: List[int] = []
    if header is not None:
        for raw_off in (
            header.struct_or_flags_off,
            header.top_level_ptr_off,
            header.extra_ptr0_off,
            header.extra_ptr1_off,
            header.extra_ptr2_off,
        ):
            try:
                off = int(raw_off)
            except Exception:
                continue
            if off >= 0 and off in seen and off not in header_fields:
                header_fields.append(off)

    if not header_fields:
        return unique

    header_set = set(header_fields)
    without_header = [off for off in unique if off not in header_set]

    splice_after = -1

    try:
        fixed_helper_base = int(frames_offset) + 0x140
    except Exception:
        fixed_helper_base = 0

    preferred_tail = fixed_helper_base + 0x58
    if preferred_tail in without_header:
        splice_after = without_header.index(preferred_tail)

    if splice_after < 0:
        preferred_tail = int(frames_offset) + 0x198
        if preferred_tail in without_header:
            splice_after = without_header.index(preferred_tail)

    if splice_after < 0:
        root_name_field = int(frames_offset) + 0xA8
        if root_name_field in without_header:
            splice_after = without_header.index(root_name_field)

    if splice_after < 0:
        return header_fields + without_header

    return without_header[:splice_after + 1] + header_fields + without_header[splice_after + 1:]

def _snap_ps2_ped_collision_radius(raw_radius: float) -> float:
    value = float(raw_radius or 0.0) * 0.75
    if value < 0.15:
        value = 0.15
    if value > 0.25:
        value = 0.25

    for target in (0.15, 0.16, 0.20, 0.25):
        if abs(value - target) <= 0.015:
            return float(target)

    return float(round(value, 3))

def _build_ps2_ped_collision_candidates(
    part_headers: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for idx, raw_header in enumerate(list(part_headers or [])):
        ph = dict(raw_header or {})
        sphere = ph.get('sphere')
        if isinstance(sphere, (list, tuple)) and len(sphere) >= 4:
            cx = float(sphere[0])
            cy = float(sphere[1])
            cz = float(sphere[2])
            raw_radius = float(sphere[3])
        else:
            cx = cy = cz = 0.0
            raw_radius = 0.0

        candidates.append({
            'part_index': int(ph.get('part_index', idx)) & 0xFFFFFFFF,
            'source_index': int(idx),
            'center': (float(cx), float(cy), float(cz)),
            'radius': _snap_ps2_ped_collision_radius(raw_radius),
            'raw_radius': float(raw_radius),
            'id': int(ph.get('dominant_bone_id', ph.get('collision_id', ph.get('tex_id', idx)))) & 0xFF,
        })

    candidates.sort(key=lambda item: (int(item.get('part_index', 0)), int(item.get('source_index', 0))))
    return candidates

def _merge_ps2_ped_collision_candidates(
    candidates: List[Dict[str, Any]],
    *,
    target_count: int,
) -> List[Dict[str, Any]]:
    merged = [dict(item) for item in list(candidates or [])]
    target_count = int(target_count or 0)
    if target_count <= 0:
        return merged

    def _distance(a: Dict[str, Any], b: Dict[str, Any]) -> float:
        ac = a.get('center', (0.0, 0.0, 0.0))
        bc = b.get('center', (0.0, 0.0, 0.0))
        dx = float(ac[0]) - float(bc[0])
        dy = float(ac[1]) - float(bc[1])
        dz = float(ac[2]) - float(bc[2])
        return math.sqrt((dx * dx) + (dy * dy) + (dz * dz))

    def _merge_two(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
        ar = float(a.get('radius', 0.15))
        br = float(b.get('radius', 0.15))
        aw = max(0.001, float(a.get('raw_radius', ar)))
        bw = max(0.001, float(b.get('raw_radius', br)))
        total = aw + bw
        ac = a.get('center', (0.0, 0.0, 0.0))
        bc = b.get('center', (0.0, 0.0, 0.0))
        cx = ((float(ac[0]) * aw) + (float(bc[0]) * bw)) / total
        cy = ((float(ac[1]) * aw) + (float(bc[1]) * bw)) / total
        cz = ((float(ac[2]) * aw) + (float(bc[2]) * bw)) / total
        keep_id = int(a.get('id', 0)) & 0xFF
        if aw < bw:
            keep_id = int(b.get('id', keep_id)) & 0xFF
        return {
            'part_index': min(int(a.get('part_index', 0)), int(b.get('part_index', 0))),
            'source_index': min(int(a.get('source_index', 0)), int(b.get('source_index', 0))),
            'center': (float(cx), float(cy), float(cz)),
            'radius': max(ar, br),
            'raw_radius': max(float(a.get('raw_radius', ar)), float(b.get('raw_radius', br))),
            'id': keep_id,
        }

    while len(merged) > target_count and len(merged) >= 2:
        best_pair: Optional[Tuple[float, int, int]] = None

        for i in range(len(merged) - 1):
            for j in range(i + 1, len(merged)):
                a = merged[i]
                b = merged[j]
                dist = _distance(a, b)
                ar = float(a.get('radius', 0.15))
                br = float(b.get('radius', 0.15))
                same_id = int(a.get('id', 0)) == int(b.get('id', 1))
                near = dist <= max(0.05, (max(ar, br) * 0.60))
                overlap = dist <= max(0.04, (ar + br) * 0.35)
                accessory_bias = min(ar, br)

                score = dist + accessory_bias
                if same_id:
                    score -= 1.5
                if overlap:
                    score -= 0.75
                if near:
                    score -= 0.25

                if best_pair is None or score < best_pair[0]:
                    best_pair = (float(score), int(i), int(j))

        if best_pair is None:
            break

        _, i, j = best_pair
        a = merged[i]
        b = merged[j]
        merged_item = _merge_two(a, b)
        merged = [item for k, item in enumerate(merged) if k not in (i, j)]
        merged.append(merged_item)
        merged.sort(key=lambda item: (int(item.get('part_index', 0)), int(item.get('source_index', 0))))

    return merged

def _looks_like_ps2_ped_collision_header(buf: Any, off: int) -> bool:
    try:
        off = int(off or 0)
        if off <= 0 or off + 0x60 > len(buf):
            return False
        if bytes(buf[off:off + 12]) != b'\x00' * 12:
            return False
        if struct.unpack_from('<I', buf, off + 0x0C)[0] != 0x40000000:
            return False
        count = struct.unpack_from('<I', buf, off + 0x34)[0]
        entries_ptr = struct.unpack_from('<I', buf, off + 0x38)[0]
        if count <= 0 or count > 256:
            return False
        if entries_ptr < off + 0x40 or entries_ptr + (count * 0x20) > len(buf):
            return False
        if bytes(buf[off + 0x54:off + 0x60]) != b'\xAA' * 12:
            return False
        return True
    except Exception:
        return False

def _find_recent_ps2_ped_collision_header(buf: Any, search_start: int = 0) -> int:
    try:
        start = max(0, int(search_start or 0))
        end = max(0, len(buf) - 0x60)
        best = 0
        for off in range(start, end + 1, 0x10):
            if _looks_like_ps2_ped_collision_header(buf, off):
                best = int(off)
        return int(best)
    except Exception:
        return 0

def _append_ps2_ped_collision_block(
    buf: bytearray,
    pointer_fields: List[int],
    *,
    scale_pos: ScalePos,
    part_headers: Optional[List[Dict[str, Any]]] = None,
    atomic_meta: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    template = _load_ped_source_template_blocks(dict(atomic_meta or {}))
    template_ids = [int(v) & 0xFF for v in list(template.get('ped_collision_ids', []) or [])]
    target_count = int(template.get('ped_collision_count', 0) or 0)

    candidates = _build_ps2_ped_collision_candidates(part_headers)
    if not candidates:
        return None

    if target_count <= 0:

        target_count = min(len(candidates), 10) if len(candidates) > 10 else len(candidates)

    if len(candidates) > target_count:
        candidates = _merge_ps2_ped_collision_candidates(
            candidates,
            target_count=target_count,
        )

    entries = list(candidates[:target_count])
    if template_ids and len(template_ids) == len(entries):
        for entry, entry_id in zip(entries, template_ids):
            entry['id'] = int(entry_id) & 0xFF

    minx = -0.5
    miny = -0.5
    minz = -1.2
    maxx = 0.5
    maxy = 0.5
    maxz = 1.2

    block_off = len(buf)

    buf += struct.pack('<3I', 0, 0, 0)
    buf += struct.pack('<f', 2.0)
    buf += struct.pack('<4f', minx, miny, minz, 0.0)
    buf += struct.pack('<4f', maxx, maxy, maxz, 0.0)

    write_u32(buf, 0)
    write_u32(buf, int(len(entries)) & 0xFFFFFFFF)

    entries_ptr_field = len(buf)
    write_u32(buf, 0)
    pointer_fields.append(int(entries_ptr_field))

    for _ in range(6):
        write_u32(buf, 0)

    write_u32(buf, 0xAAAAAAAA)
    write_u32(buf, 0xAAAAAAAA)
    write_u32(buf, 0xAAAAAAAA)

    entries_off = len(buf)
    struct.pack_into('<I', buf, int(entries_ptr_field), int(entries_off) & 0xFFFFFFFF)

    for entry in entries:
        write_u32(buf, 0)
        write_u32(buf, 0)
        write_u32(buf, 0)
        buf.extend(struct.pack('<f', float(entry.get('radius', 0.15))))
        buf.extend(bytes((0x11, int(entry.get('id', 0)) & 0xFF)))
        buf.extend(b'\xAA' * 14)

    return int(block_off)

def finalize_mdl_header(
    buf: bytearray,
    header: HeaderPatchInfo,
    file_size: int,
    local_num_offset: int,
    global_num_offset: int,
    pointer_count: int,
) -> None:
    struct.pack_into("<I", buf, header.file_len_off, file_size)
    struct.pack_into("<I", buf, header.local_num_off, local_num_offset)
    struct.pack_into("<I", buf, header.global_num_off, global_num_offset)
    struct.pack_into("<I", buf, header.num_entries_off, pointer_count)
    struct.pack_into("<I", buf, header.ptr2_before_tex_off, local_num_offset)

    alloc_mem = 0x00010000
    struct.pack_into("<I", buf, header.alloc_mem_off, alloc_mem)

    struct.pack_into("<I", buf, header.ptr_after_alloc_off, FIRST_SECTION_OFFSET)

PendingTexture = Tuple[int, str]
PendingFrameName = Tuple[int, str]

def write_material(
    buf: bytearray,
    tex_name: str,
    pointer_fields: List[int],
    pending_textures: List[PendingTexture],
    rgba: int = 0xFFFFFFFF,
) -> int:
    material_offset = len(buf)

    tex_ptr_field = len(buf)
    write_u32(buf, 0)
    pointer_fields.append(tex_ptr_field)

    write_u32(buf, int(rgba) & 0xFFFFFFFF)
    write_u32(buf, 0x00000002)
    write_u32(buf, 0)

    pending_textures.append((tex_ptr_field, tex_name))
    return material_offset

def write_frame_name_strings_before_tables(
    buf: bytearray,
    pending_frame_names: List[PendingFrameName],
) -> None:
    if not pending_frame_names:
        return

    table_start = len(buf)

    for name_ptr_field, frame_name in pending_frame_names:
        name_offset = len(buf)
        write_cstring(buf, str(frame_name))
        struct.pack_into("<I", buf, int(name_ptr_field), int(name_offset) & 0xFFFFFFFF)

    while ((len(buf) - table_start) & 3) != 0:
        buf.append(0)

def write_texture_strings_after_tables(
    buf: bytearray,
    pending_textures: List[PendingTexture],
) -> None:
    if not pending_textures:
        return

    string_offsets: Dict[str, int] = {}

    for tex_ptr_field, tex_name in pending_textures:
        key = str(tex_name)
        if key not in string_offsets:
            string_offsets[key] = len(buf)
            name_bytes = key.encode("ascii", errors="ignore") + b"\x00"
            buf.extend(name_bytes)
        struct.pack_into("<I", buf, tex_ptr_field, string_offsets[key])

def _build_ps2_ped_material_footer_bytes(
    *,
    ped_frame_meta: Optional[Dict[str, Any]] = None,
    template_blocks: Optional[Dict[str, Any]] = None,
    next_block_ptr: int = 0,
) -> bytes:
    footer = bytearray(b"\x00" * 0x40)

    bone_count = 0
    if isinstance(template_blocks, dict):
        try:
            bone_count = int(template_blocks.get("material_footer_bone_count", 0) or 0)
        except Exception:
            bone_count = 0
    if bone_count <= 0:
        try:
            bone_count = int((ped_frame_meta or {}).get("node_count", 0) or 0)
        except Exception:
            bone_count = 0
    if bone_count > 0:
        struct.pack_into("<I", footer, 0x00, int(bone_count) & 0xFFFFFFFF)

    if next_block_ptr > 0:
        struct.pack_into("<I", footer, 0x0C, int(next_block_ptr) & 0xFFFFFFFF)

    return bytes(footer)

def _extract_ps2_ped_material_footer_template(
    data: bytes,
    *,
    material_ptr: int = 0,
    material_entry_ptrs: Optional[List[int]] = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    if not isinstance(data, (bytes, bytearray)) or material_ptr <= 0 or material_ptr >= len(data):
        return result

    ptrs = [int(v) & 0xFFFFFFFF for v in list(material_entry_ptrs or []) if int(v) > 0]
    if not ptrs:
        return result

    in_material = sorted(v for v in ptrs if material_ptr <= v and (v + 0x10) <= len(data))
    if not in_material:
        return result

    cluster: List[int] = []
    for ptr in in_material:
        entry = data[ptr: ptr + 0x10]
        if len(entry) != 0x10:
            continue
        third = struct.unpack_from("<I", entry, 0x08)[0]
        fourth = struct.unpack_from("<I", entry, 0x0C)[0]
        if third not in (0, 2):
            continue
        if fourth != 0:
            continue
        if not cluster:
            cluster.append(int(ptr))
            continue
        if int(ptr) == (cluster[-1] + 0x10):
            cluster.append(int(ptr))

    if not cluster:
        return result

    footer_off = int(cluster[-1]) + 0x10
    if footer_off + 0x40 > len(data):
        return result

    footer_bytes = bytes(data[footer_off: footer_off + 0x40])
    if footer_bytes.count(0) == len(footer_bytes):
        return result

    result["material_footer_bytes"] = footer_bytes
    try:
        result["material_footer_bone_count"] = int(_ped_template_decode_u32(struct.unpack_from("<I", footer_bytes, 0x00)[0])) & 0xFFFFFFFF
    except Exception:
        pass
    return result

def resolve_texture_name_identity(out: bytearray, atomic2_offset: int = 0) -> int:
    frames_offset = len(out)

    for _ in range(2):
        out.extend(struct.pack(
            "<15fI",
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0,
            1
        ))

    out.extend(struct.pack("<2I", 0, 0))
    out.extend(struct.pack("<I", int(atomic2_offset) & 0xFFFFFFFF))
    out.extend(struct.pack("<I", 0xAAAAAAAA))
    out.extend(struct.pack("<I", 0xFFFFFFFF))
    out.extend(struct.pack("<3I", 0, 0, 0))

    return frames_offset

def write_geometry_and_material(
    buf: bytearray,
    pointer_fields: List[int],
    part_materials: List[int],
    scale_pos: ScalePos,
    dma_packets: List[bytearray],
    material_offsets: List[int],
    part_headers: Optional[List[Dict[str, Any]]] = None,
    global_header: Optional[Dict[str, Any]] = None,
    bounds_header_ptr: int = 0,
    inverse_matrix_table_bytes: Optional[bytes] = None,
    material_names: Optional[List[str]] = None,
    material_rgba_values: Optional[List[int]] = None,
    pending_textures: Optional[List[PendingTexture]] = None,
    out_info: Optional[Dict[str, Any]] = None,
) -> int:

    if len(part_materials) != len(dma_packets):
        raise ValueError("part_materials and dma_packets length mismatch")

    geom_offset = len(buf)
    if geom_offset & 0x0F:
        raise RuntimeError(
            "PS2 PED geometry block is not 16-byte aligned: "
            f"geom_offset=0x{geom_offset:X}."
        )

    buf.extend(struct.pack("<III", 8, 0, 1))

    material_list_ptr_field = len(buf)
    buf.extend(struct.pack("<I", 0))
    pointer_fields.append(material_list_ptr_field)

    material_count = len(material_offsets)
    buf.extend(struct.pack("<I", material_count))
    buf.extend(struct.pack("<I", 0x10))

    aux_bounds_field_off = len(buf)
    buf.extend(struct.pack("<I", 0))

    buf.extend(struct.pack("<I", 0))

    material_names = list(material_names or [])
    material_rgba_values = list(material_rgba_values or [])
    pending_textures_ref = pending_textures
    write_inline_material_descriptors = bool(material_names) and pending_textures_ref is not None and all(int(v or 0) == 0 for v in material_offsets)

    delayed_material_ptr_table: bool = True
    delayed_material_offsets: List[int] = list(material_offsets)
    material_list_entry_field_offsets: List[int] = []
    material_list_offset = 0
    written_material_offsets: List[int] = []

    part_offset_field_offsets: List[int] = []
    part_headers = list(part_headers or [])
    global_header = dict(global_header or {})

    part_count = len(part_materials)

    dma_packets = [bytearray(packet) for packet in dma_packets]

    dma_payload_size = 0
    for packet in dma_packets:
        try:
            dma_payload_size += len(packet)
        except Exception:
            pass

    def getFloatList(value, count, fallback):
        try:
            values = list(value)
            out = []
            for index in range(count):
                out.append(float(values[index]))
            return out
        except Exception:
            return list(fallback)

    def getIntList(value, count, fallback):
        try:
            values = list(value)
            out = []
            for index in range(count):
                out.append(int(values[index]))
            return out
        except Exception:
            return list(fallback)

    def unsigned32(value: int) -> int:
        return int(value) & 0xFFFFFFFF

    def getU32List(value, count, fallback):
        try:
            values = list(value)
            out = []
            for index in range(count):
                out.append(unsigned32(values[index]))
            return out
        except Exception:
            return [unsigned32(v) for v in list(fallback)]

    def clampI16(value: int) -> int:
        value = int(value)
        if value < -32768:
            return -32768
        if value > 32767:
            return 32767
        return value

    sphere = getFloatList(global_header.get("sphere"), 4, [0.0, 0.0, 0.0, 0.0])
    bbox_i16 = [clampI16(v) for v in getIntList(global_header.get("bbox_i16"), 6, [0, 0, 0, 0, 0, 0])]

    def readScalePosAxisValues(scale_pos_value, field_name: str, legacy_names, fallback_values):
        if scale_pos_value is None:
            return list(fallback_values)

        try:
            field_value = getattr(scale_pos_value, field_name)
            values = list(field_value)
            if len(values) >= 3:
                return [float(values[0]), float(values[1]), float(values[2])]
        except Exception:
            pass

        out = []
        for legacy_name, fallback_value in zip(legacy_names, fallback_values):
            try:
                out.append(float(getattr(scale_pos_value, legacy_name)))
            except Exception:
                out.append(float(fallback_value))
        return out

    scale_default = readScalePosAxisValues(
        scale_pos,
        "scale",
        ("x_scale", "y_scale", "z_scale"),
        (1.0, 1.0, 1.0),
    )
    translation_default = readScalePosAxisValues(
        scale_pos,
        "pos",
        ("x_pos", "y_pos", "z_pos"),
        (0.0, 0.0, 0.0),
    )
    force_scale_pos = False
    try:
        force_scale_pos = bool(global_header.get("force_scale_pos", False))
    except Exception:
        force_scale_pos = False

    if force_scale_pos:

        scale_values = list(scale_default)
        translation_values = list(translation_default)
    else:
        scale_values = getFloatList(global_header.get("scale"), 3, scale_default)
        translation_values = getFloatList(global_header.get("translation"), 3, translation_default)

    vertex_section_flags = int(global_header.get("vertex_section_flags", 0)) & 0xFFFFFFFF

    def calculatePedRuntimeVertexCount(headers: List[Dict[str, Any]], fallback_part_count: int) -> int:
        runtime_total = 0
        saw_runtime_count = False
        saw_strip_count = False

        for header in list(headers or []):
            if not isinstance(header, dict):
                continue

            runtime_value = header.get("runtime_vertex_count")
            if runtime_value is None:
                runtime_value = header.get("emitted_runtime_vertex_count")
            if runtime_value is not None:
                try:
                    runtime_count = int(runtime_value)
                    if runtime_count > 0:
                        runtime_total += runtime_count
                        saw_runtime_count = True
                        continue
                except Exception:
                    pass

            try:
                strip_count = int(header.get("strip_vertex_count", 0))
            except Exception:
                strip_count = 0

            if strip_count > 0:
                saw_strip_count = True
                extra_count = None
                for key in ("emitted_setup_vertex_count", "ped_setup_vertex_count"):
                    if key in header:
                        try:
                            extra_count = int(header.get(key, 0))
                        except Exception:
                            extra_count = None
                        break

                if extra_count is None:
                    sub_strip_count = None
                    for key in ("emitted_sub_strip_count", "sub_strip_count", "strip_count"):
                        if key in header:
                            try:
                                sub_strip_count = int(header.get(key, 0))
                            except Exception:
                                sub_strip_count = None
                            break
                    if sub_strip_count is None or sub_strip_count <= 0:
                        sub_strip_count = 1
                    extra_count = int(sub_strip_count) * 2

                runtime_total += max(0, int(strip_count) + int(extra_count))

        if saw_runtime_count or saw_strip_count:
            return max(0, int(runtime_total))

        return 0

    imported_total_vertex_count = int(global_header.get("total_vertex_count", 0)) & 0xFFFF
    rebuilt_total_vertex_count = calculatePedRuntimeVertexCount(part_headers, part_count)
    if rebuilt_total_vertex_count > 0:
        total_vertex_count = rebuilt_total_vertex_count & 0xFFFF
        global_header["total_vertex_count"] = int(total_vertex_count)
        if out_info is not None:
            out_info["imported_total_vertex_count"] = int(imported_total_vertex_count)
            out_info["rebuilt_total_vertex_count"] = int(rebuilt_total_vertex_count)
            out_info["written_total_vertex_count"] = int(total_vertex_count)
    else:
        total_vertex_count = imported_total_vertex_count

    first_tristrip_offset = (0x40 + (int(part_count) * 0x30)) & 0xFFFF
    global_header["first_tristrip_offset"] = int(first_tristrip_offset)

    packed_size_and_material_count = global_header.get("packed_size_and_material_count")
    if packed_size_and_material_count is None:
        geometry_size_bytes = 0x40 + (part_count * 0x30) + int(dma_payload_size)
        packed_size_and_material_count = (int(geometry_size_bytes) & 0x000FFFFF) | ((int(part_count) & 0xFFF) << 20)
    else:
        packed_size_and_material_count = int(packed_size_and_material_count) & 0xFFFFFFFF
        packed_size_and_material_count &= 0x000FFFFF
        packed_size_and_material_count |= ((int(part_count) & 0xFFF) << 20)

    global_packed_field_offset = len(buf) + 0x10

    buf.extend(struct.pack(
        "<4fIIHH6h6f",
        float(sphere[0]), float(sphere[1]), float(sphere[2]), float(sphere[3]),
        int(packed_size_and_material_count) & 0xFFFFFFFF,
        int(vertex_section_flags) & 0xFFFFFFFF,
        int(total_vertex_count) & 0xFFFF,
        int(first_tristrip_offset) & 0xFFFF,
        int(bbox_i16[0]), int(bbox_i16[1]), int(bbox_i16[2]),
        int(bbox_i16[3]), int(bbox_i16[4]), int(bbox_i16[5]),
        float(scale_values[0]), float(scale_values[1]), float(scale_values[2]),
        float(translation_values[0]), float(translation_values[1]), float(translation_values[2]),
    ))

    for part_index, mat_index in enumerate(part_materials):
        ph = part_headers[part_index] if part_index < len(part_headers) else {}

        sphere_values = getFloatList(ph.get("sphere"), 4, [0.0, 0.0, 0.0, 0.0])
        uv_scale_u = float(ph.get("uv_scale_u", 1.0))
        uv_scale_v = float(ph.get("uv_scale_v", 1.0))
        flags = int(ph.get("flags", vertex_section_flags if vertex_section_flags else 0)) & 0xFFFFFFFF

        part_offset_field_offsets.append(len(buf) + 0x1C)

        strip_vertex_count = int(ph.get("strip_vertex_count", 0)) & 0xFFFF

        material_descriptor_count = max(1, int(len(material_offsets)))
        tex_id = int(ph.get("tex_id", mat_index)) % material_descriptor_count
        part_bbox = [clampI16(v) for v in getIntList(ph.get("bbox_i16"), 6, [0, 0, 0, 0, 0, 0])]

        raw_unknowns = None
        try:
            if "entry_unknown0" in ph and "entry_unknowns" in ph and "entry_trailing" in ph:
                raw_unknowns = [unsigned32(ph.get("entry_unknown0", 0))]
                raw_unknowns.extend(getU32List(ph.get("entry_unknowns"), 6, [0, 0, 0, 0, 0, int(flags) & 0xFFFFFFFF]))
                raw_trailing = getU32List(ph.get("entry_trailing"), 3, [0, 0, 0])
            else:
                raw_trailing = None
        except Exception:
            raw_unknowns = None
            raw_trailing = None

        if raw_unknowns is not None and len(raw_unknowns) == 7 and raw_trailing is not None and len(raw_trailing) == 3:

            buf.extend(struct.pack(
                "<7IIHH3I",
                int(raw_unknowns[0]) & 0xFFFFFFFF,
                int(raw_unknowns[1]) & 0xFFFFFFFF,
                int(raw_unknowns[2]) & 0xFFFFFFFF,
                int(raw_unknowns[3]) & 0xFFFFFFFF,
                int(raw_unknowns[4]) & 0xFFFFFFFF,
                int(raw_unknowns[5]) & 0xFFFFFFFF,
                int(raw_unknowns[6]) & 0xFFFFFFFF,
                0,
                int(strip_vertex_count) & 0xFFFF,
                int(tex_id) & 0xFFFF,
                int(raw_trailing[0]) & 0xFFFFFFFF,
                int(raw_trailing[1]) & 0xFFFFFFFF,
                int(raw_trailing[2]) & 0xFFFFFFFF,
            ))
        else:
            buf.extend(struct.pack(
                "<4f2fIIHH6h",
                float(sphere_values[0]), float(sphere_values[1]), float(sphere_values[2]), float(sphere_values[3]),
                float(uv_scale_u),
                float(uv_scale_v),
                int(flags) & 0xFFFFFFFF,
                0,
                int(strip_vertex_count) & 0xFFFF,
                int(tex_id) & 0xFFFF,
                int(part_bbox[0]), int(part_bbox[1]), int(part_bbox[2]),
                int(part_bbox[3]), int(part_bbox[4]), int(part_bbox[5]),
            ))

    dma_start = len(buf)
    if dma_start & 0x0F:
        raise RuntimeError(
            "PS2 PED geometry writer produced an unaligned DMA stream: "
            f"dma_start=0x{dma_start:X}. Align the geometry block before writing it."
        )

    for i, packet in enumerate(dma_packets):
        rel = len(buf) - dma_start
        struct.pack_into("<I", buf, part_offset_field_offsets[i], rel)
        buf.extend(packet)

    actual_geometry_size = len(buf) - (int(geom_offset) + 0x20)
    actual_packed_size_and_material_count = (
        (int(actual_geometry_size) & 0x000FFFFF)
        | ((int(part_count) & 0xFFF) << 20)
    )
    struct.pack_into(
        "<I",
        buf,
        int(global_packed_field_offset),
        int(actual_packed_size_and_material_count) & 0xFFFFFFFF,
    )
    packed_size_and_material_count = int(actual_packed_size_and_material_count) & 0xFFFFFFFF

    align_buffer(buf, 16)

    if delayed_material_ptr_table:
        align_buffer(buf, 16)
        material_list_offset = len(buf)
        struct.pack_into("<I", buf, material_list_ptr_field, material_list_offset)

        if write_inline_material_descriptors:
            descriptor_pointer_fields: List[int] = []
            for _ in material_names:
                field_off = len(buf)
                buf.extend(struct.pack("<I", 0))
                pointer_fields.append(field_off)
                material_list_entry_field_offsets.append(int(field_off))
                descriptor_pointer_fields.append(int(field_off))

            for material_index, material_name in enumerate(material_names):
                rgba = 0xFFFFFFFF
                if material_index < len(material_rgba_values):
                    try:
                        rgba = int(material_rgba_values[material_index]) & 0xFFFFFFFF
                    except Exception:
                        rgba = 0xFFFFFFFF

                material_offset = write_material(
                    buf,
                    str(material_name),
                    pointer_fields,
                    pending_textures_ref,
                    rgba=rgba,
                )
                written_material_offsets.append(int(material_offset))
                if material_index < len(descriptor_pointer_fields):
                    struct.pack_into("<I", buf, int(descriptor_pointer_fields[material_index]), int(material_offset) & 0xFFFFFFFF)
        else:
            for mat_off in delayed_material_offsets:
                field_off = len(buf)
                buf.extend(struct.pack("<I", int(mat_off) & 0xFFFFFFFF))
                pointer_fields.append(field_off)
                material_list_entry_field_offsets.append(int(field_off))

    align_buffer(buf, 16)
    aux_header_offset = len(buf)
    struct.pack_into("<I", buf, aux_bounds_field_off, int(aux_header_offset) & 0xFFFFFFFF)
    pointer_fields.append(int(aux_bounds_field_off))

    write_u32(buf, 0x19)
    write_u32(buf, 0)
    write_u32(buf, 0)

    matrix_table_ptr_field = len(buf)
    write_u32(buf, 0)
    pointer_fields.append(int(matrix_table_ptr_field))

    while len(buf) < aux_header_offset + 0x40:
        write_u32(buf, 0)

    matrix_table_offset = len(buf)
    struct.pack_into("<I", buf, matrix_table_ptr_field, int(matrix_table_offset) & 0xFFFFFFFF)

    matrix_table_bytes = bytes(inverse_matrix_table_bytes or b"")
    if not matrix_table_bytes:
        identity_matrix = Matrix.Identity(4)
        tmp_identity = bytearray()
        _write_ps2_bind_palette_matrix_block(tmp_identity, identity_matrix)
        matrix_table_bytes = bytes(tmp_identity)
    buf.extend(matrix_table_bytes)
    align_buffer(buf, 16)

    if out_info is not None:
        out_info.clear()
        out_info["geom_offset"] = int(geom_offset)
        out_info["material_list_ptr_field"] = int(material_list_ptr_field)
        out_info["material_list_offset"] = int(material_list_offset)
        out_info["material_list_entry_field_offsets"] = [int(v) for v in material_list_entry_field_offsets]
        out_info["delayed_material_ptr_table"] = bool(delayed_material_ptr_table)
        out_info["dma_start"] = int(dma_start)
        out_info["first_tristrip_offset"] = int(first_tristrip_offset)
        out_info["expected_dma_start_from_first_tristrip"] = int(geom_offset) + 0x20 + int(first_tristrip_offset)
        out_info["aux_header_offset"] = int(aux_header_offset)
        out_info["matrix_table_offset"] = int(matrix_table_offset)
        if written_material_offsets:
            out_info["material_offsets"] = [int(v) for v in written_material_offsets]

    return geom_offset

def _should_place_ps2_ped_materials_after_geometry(
    *,
    current_size: int,
    dma_packets: List[bytes],
    material_count: int,
    part_count: int,
) -> bool:
    sector_size = 0x1000
    target_small_file_sectors = 15

    dma_size = 0
    for packet in list(dma_packets or []):
        try:
            dma_size += len(packet)
        except Exception:
            continue

    estimated_tail = 0
    estimated_tail += 0x80
    estimated_tail += max(1, int(part_count)) * 0x30
    estimated_tail += dma_size
    estimated_tail += max(1, int(material_count)) * 0x10
    estimated_tail += 0x800

    predicted_total = max(0, int(current_size)) + estimated_tail
    predicted_sectors = (predicted_total + (sector_size - 1)) // sector_size
    return predicted_sectors <= target_small_file_sectors

def write_simplemodel_ps2_prop_mdl(
    filepath: str,
    scale_pos,
    dma_packets: List[bytes],
    material_names: List[str],
    atomic_hash_key: int = 0,
    material_vcols: Optional[List[int]] = None,
    bounds: Optional[Tuple[float, float, float, float]] = None,
    unknown_geom_ints: Optional[List[int]] = None,
    geom_block_override: Optional[bytes] = None,
    part_headers: Optional[List[Dict[str, Any]]] = None,
    vertex_section_flags: Optional[int] = None,
) -> None:

    if not material_names:
        material_names = ["default"]

    if material_vcols is None or len(material_vcols) < len(material_names):
        default_v = 0xFF959595
        material_vcols = (material_vcols or []) + [default_v] * (len(material_names) - (len(material_vcols) if material_vcols else 0))

    HEADER_SIZE = 0x24
    ATOMIC2_OFF = 0x30
    MATRICES_OFF = 0x40
    ATOMIC1_OFF = 0xE0
    TEXLIST_OFF = 0x120
    GEOM_HDR_OFF = 0x150

    GEOM_PREAMBLE_SIZE = 0x20
    LEEDS_GLOBAL_HDR_SIZE = 0x40
    LEEDS_PART_HDR_SIZE = 0x30

    num_parts = len(dma_packets)
    PART_TABLE_OFF = GEOM_HDR_OFF + GEOM_PREAMBLE_SIZE + LEEDS_GLOBAL_HDR_SIZE
    DMA_START_OFF = PART_TABLE_OFF + (num_parts * LEEDS_PART_HDR_SIZE)
    DMA_START_OFF = (DMA_START_OFF + 0x0F) & ~0x0F

    out = bytearray(b"\x00" * DMA_START_OFF)

    out[0:4] = b"ldm\x00"
    struct.pack_into("<I", out, 0x04, 0)
    struct.pack_into("<I", out, 0x08, 0)
    struct.pack_into("<I", out, 0x0C, 0)
    struct.pack_into("<I", out, 0x10, 0)
    struct.pack_into("<I", out, 0x14, 16)
    struct.pack_into("<I", out, 0x18, 0)
    struct.pack_into("<I", out, 0x1C, 0x00010000)
    struct.pack_into("<I", out, 0x20, ATOMIC1_OFF)

    struct.pack_into("<I", out, ATOMIC2_OFF + 0x00, 0x0300AA00)
    struct.pack_into("<I", out, ATOMIC2_OFF + 0x04, 0)

    atomic1_prev_entry = ATOMIC1_OFF + 0x08
    struct.pack_into("<I", out, ATOMIC2_OFF + 0x08, atomic1_prev_entry)
    struct.pack_into("<I", out, ATOMIC2_OFF + 0x0C, atomic1_prev_entry)

    tmp = bytearray()
    resolve_texture_name_identity(tmp, ATOMIC2_OFF)
    out[MATRICES_OFF:MATRICES_OFF + len(tmp)] = tmp

    struct.pack_into("<I", out, ATOMIC1_OFF + 0x00, 0x0004AA01)
    struct.pack_into("<I", out, ATOMIC1_OFF + 0x04, ATOMIC2_OFF)
    struct.pack_into("<I", out, ATOMIC1_OFF + 0x08, ATOMIC2_OFF + 0x08)
    struct.pack_into("<I", out, ATOMIC1_OFF + 0x0C, ATOMIC2_OFF + 0x08)
    struct.pack_into("<I", out, ATOMIC1_OFF + 0x10, 0)

    struct.pack_into("<I", out, ATOMIC1_OFF + 0x14, GEOM_HDR_OFF)
    struct.pack_into("<I", out, ATOMIC1_OFF + 0x18, 0)

    hk = int(atomic_hash_key) & 0xFFFFFFFF
    struct.pack_into("<I", out, ATOMIC1_OFF + 0x1C, hk)
    struct.pack_into("<I", out, ATOMIC1_OFF + 0x20, hk)

    struct.pack_into("<I", out, ATOMIC1_OFF + 0x24, 0)
    struct.pack_into("<I", out, ATOMIC1_OFF + 0x28, GEOM_HDR_OFF)

    struct.pack_into("<I", out, ATOMIC1_OFF + 0x2C, 0)
    struct.pack_into("<I", out, ATOMIC1_OFF + 0x30, 0)

    struct.pack_into("<I", out, ATOMIC1_OFF + 0x34, 0)
    struct.pack_into("<I", out, ATOMIC1_OFF + 0x38, int(material_vcols[0]) & 0xFFFFFFFF)

    num_parts = len(dma_packets)
    struct.pack_into("<I", out, TEXLIST_OFF - 0x04, num_parts)

    num_tex = len(material_names)

    struct.pack_into("<I", out, TEXLIST_OFF + 0x00, TEXLIST_OFF + 0x04)

    struct.pack_into("<I", out, TEXLIST_OFF + 0x04, 0)

    struct.pack_into("<I", out, TEXLIST_OFF + 0x08, 0)

    struct.pack_into("<f", out, TEXLIST_OFF + 0x0C, 1.0)

    struct.pack_into("<I", out, TEXLIST_OFF + 0x10, num_tex)

    struct.pack_into("<I", out, TEXLIST_OFF + 0x14, ATOMIC1_OFF + 0x34)

    struct.pack_into("<I", out, TEXLIST_OFF + 0x18, TEXLIST_OFF + 0x1C)

    struct.pack_into("<I", out, TEXLIST_OFF + 0x1C, 0)

    second_vcol = material_vcols[1] if num_tex > 1 else material_vcols[0]
    struct.pack_into("<I", out, TEXLIST_OFF + 0x20, int(second_vcol) & 0xFFFFFFFF)

    struct.pack_into("<I", out, TEXLIST_OFF + 0x24, num_tex)

    struct.pack_into("<I", out, TEXLIST_OFF + 0x28, 0)
    struct.pack_into("<I", out, TEXLIST_OFF + 0x2C, 0)

    GLOBAL_GEOM_HDR_OFF = GEOM_HDR_OFF + GEOM_PREAMBLE_SIZE

    def write_leeds_global_header(
        outbuf: bytearray,
        global_off: int,
        *,
        sphere_vals: Tuple[float, float, float, float],
        bbox_i16_vals: List[int],
        sx: float,
        sy: float,
        sz: float,
        tx: float,
        ty: float,
        tz: float,
        packed_size_and_material_count: int,
        vtx_flags: int,
        total_vtx_count: int,
        first_tristrip_rel_off: int,
    ) -> None:
        bx, by, bz, br = sphere_vals
        struct.pack_into("<4f", outbuf, global_off + 0x00, float(bx), float(by), float(bz), float(br))
        struct.pack_into("<I", outbuf, global_off + 0x10, int(packed_size_and_material_count) & 0xFFFFFFFF)
        struct.pack_into("<I", outbuf, global_off + 0x14, int(vtx_flags) & 0xFFFFFFFF)
        struct.pack_into("<H", outbuf, global_off + 0x18, int(total_vtx_count) & 0xFFFF)
        struct.pack_into("<H", outbuf, global_off + 0x1A, int(first_tristrip_rel_off) & 0xFFFF)

        bb = [0, 0, 0, 0, 0, 0]
        for idx, v in enumerate((bbox_i16_vals or [])[:6]):
            iv = int(v)
            if iv < -32768:
                iv = -32768
            elif iv > 32767:
                iv = 32767
            bb[idx] = iv
        struct.pack_into("<6h", outbuf, global_off + 0x1C, *bb)

        struct.pack_into("<3f", outbuf, global_off + 0x28, float(sx), float(sy), float(sz))
        struct.pack_into("<3f", outbuf, global_off + 0x34, float(tx), float(ty), float(tz))

    def write_leeds_part_header(
        outbuf: bytearray,
        hdr_off: int,
        *,
        sphere_vals: Tuple[float, float, float, float],
        uv_scale_u: float,
        uv_scale_v: float,
        flags_val: int,
        tristrip_rel_off: int,
        strip_vertex_count: int,
        tex_id: int,
        bbox_i16_vals: List[int],
    ) -> None:
        sx0, sy0, sz0, sr0 = sphere_vals
        struct.pack_into("<4f", outbuf, hdr_off + 0x00, float(sx0), float(sy0), float(sz0), float(sr0))
        struct.pack_into("<f", outbuf, hdr_off + 0x10, float(uv_scale_u))
        struct.pack_into("<f", outbuf, hdr_off + 0x14, float(uv_scale_v))
        struct.pack_into("<I", outbuf, hdr_off + 0x18, int(flags_val) & 0xFFFFFFFF)
        struct.pack_into("<I", outbuf, hdr_off + 0x1C, int(tristrip_rel_off) & 0xFFFFFFFF)
        struct.pack_into("<H", outbuf, hdr_off + 0x20, int(strip_vertex_count) & 0xFFFF)
        struct.pack_into("<H", outbuf, hdr_off + 0x22, int(tex_id) & 0xFFFF)

        bb = [0, 0, 0, 0, 0, 0]
        for idx, v in enumerate((bbox_i16_vals or [])[:6]):
            iv = int(v)
            if iv < -32768:
                iv = -32768
            elif iv > 32767:
                iv = 32767
            bb[idx] = iv
        struct.pack_into("<6h", outbuf, hdr_off + 0x24, *bb)

    def union_bbox_from_part_headers(headers: Optional[List[Dict[str, Any]]]) -> List[int]:
        if not headers:
            return [0, 0, 0, 0, 0, 0]
        mins = [32767, 32767, 32767]
        maxs = [-32768, -32768, -32768]
        found = False
        for h in headers:
            bb = h.get("bbox_i16")
            if not bb or len(bb) < 6:
                continue
            found = True
            mins[0] = min(mins[0], int(bb[0])); mins[1] = min(mins[1], int(bb[1])); mins[2] = min(mins[2], int(bb[2]))
            maxs[0] = max(maxs[0], int(bb[3])); maxs[1] = max(maxs[1], int(bb[4])); maxs[2] = max(maxs[2], int(bb[5]))
        if not found:
            return [0, 0, 0, 0, 0, 0]
        return [mins[0], mins[1], mins[2], maxs[0], maxs[1], maxs[2]]

    dma_rel_offsets: List[int] = []
    rel_accum = 0
    for pkt in dma_packets:
        dma_rel_offsets.append(rel_accum)
        rel_accum += len(pkt)

    if geom_block_override is None or part_headers is not None:

        struct.pack_into("<I", out, GEOM_HDR_OFF + 0x00, 8)
        struct.pack_into("<I", out, GEOM_HDR_OFF + 0x04, 0)
        struct.pack_into("<I", out, GEOM_HDR_OFF + 0x08, 1)
        struct.pack_into("<I", out, GEOM_HDR_OFF + 0x0C, TEXLIST_OFF + 0x14)
        struct.pack_into("<I", out, GEOM_HDR_OFF + 0x10, num_tex)
        struct.pack_into("<I", out, GEOM_HDR_OFF + 0x14, 0x10)
        struct.pack_into("<I", out, GEOM_HDR_OFF + 0x18, 0)
        struct.pack_into("<I", out, GEOM_HDR_OFF + 0x1C, 0)

        sx, sy, sz = scale_pos.scale
        tx, ty, tz = scale_pos.pos

        global_sphere = (0.0, 0.0, 0.0, 0.0)
        if bounds is not None and len(bounds) >= 4:
            global_sphere = (float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3]))
        elif part_headers and len(part_headers) > 0:
            h0s = part_headers[0].get("sphere")
            if h0s and len(h0s) >= 4:
                global_sphere = (float(h0s[0]), float(h0s[1]), float(h0s[2]), float(h0s[3]))

        packed_size_and_material_count = 0
        flags_u32 = int(vertex_section_flags if vertex_section_flags is not None else 7) & 0xFFFFFFFF
        total_vertex_count = 0
        first_tristrip_rel_off = DMA_START_OFF - GLOBAL_GEOM_HDR_OFF
        global_bbox_i16 = union_bbox_from_part_headers(part_headers)

        if part_headers:
            runtime_sum = 0
            saw_count = False
            for h in part_headers:
                try:
                    runtime_value = h.get("runtime_vertex_count")
                    if runtime_value is None:
                        runtime_value = h.get("emitted_runtime_vertex_count")
                    if runtime_value is not None and int(runtime_value) > 0:
                        runtime_sum += int(runtime_value)
                        saw_count = True
                        continue
                except Exception:
                    pass
                try:
                    strip_count = int(h.get("strip_vertex_count", 0))
                except Exception:
                    strip_count = 0
                if strip_count > 0:
                    saw_count = True
                    try:
                        setup_count = int(h.get("emitted_setup_vertex_count", 0))
                    except Exception:
                        setup_count = 0
                    if setup_count <= 0:
                        try:
                            setup_count = int(h.get("emitted_sub_strip_count", 1)) * 2
                        except Exception:
                            setup_count = 2
                    runtime_sum += int(strip_count) + int(setup_count)
            if saw_count:
                total_vertex_count = runtime_sum & 0xFFFF

        if unknown_geom_ints:
            ints = [int(v) & 0xFFFFFFFF for v in unknown_geom_ints[:6]]
            if len(ints) >= 1:
                packed_size_and_material_count = ints[0]
            if len(ints) >= 2 and vertex_section_flags is None:
                flags_u32 = ints[1]
            if len(ints) >= 3 and not part_headers:
                total_vertex_count = ints[2] & 0xFFFF
                first_tristrip_rel_off = (ints[2] >> 16) & 0xFFFF
            elif len(ints) >= 3:
                first_tristrip_rel_off = (ints[2] >> 16) & 0xFFFF

            if (not part_headers) and len(ints) >= 6:
                raw_bbox_bytes = struct.pack("<III", ints[3], ints[4], ints[5])
                global_bbox_i16 = list(struct.unpack("<6h", raw_bbox_bytes))

        write_leeds_global_header(
            out,
            GLOBAL_GEOM_HDR_OFF,
            sphere_vals=global_sphere,
            bbox_i16_vals=global_bbox_i16,
            sx=sx, sy=sy, sz=sz,
            tx=tx, ty=ty, tz=tz,
            packed_size_and_material_count=packed_size_and_material_count,
            vtx_flags=flags_u32,
            total_vtx_count=total_vertex_count,
            first_tristrip_rel_off=first_tristrip_rel_off,
        )

        for i in range(num_parts):
            hdr = part_headers[i] if (part_headers is not None and i < len(part_headers)) else {}
            sphere_vals = hdr.get("sphere", global_sphere)
            if sphere_vals is None or len(sphere_vals) < 4:
                sphere_vals = global_sphere
            uv_u = float(hdr.get("uv_scale_u", 1.0))
            uv_v = float(hdr.get("uv_scale_v", 1.0))
            flags_val = int(hdr.get("flags", 0x10)) & 0xFFFFFFFF
            strip_vtx_count = int(hdr.get("strip_vertex_count", 0)) & 0xFFFF
            tex_id = int(hdr.get("tex_id", i)) & 0xFFFF
            bbox_i16 = hdr.get("bbox_i16", [0, 0, 0, 0, 0, 0])

            write_leeds_part_header(
                out,
                PART_TABLE_OFF + (i * LEEDS_PART_HDR_SIZE),
                sphere_vals=(float(sphere_vals[0]), float(sphere_vals[1]), float(sphere_vals[2]), float(sphere_vals[3])),
                uv_scale_u=uv_u,
                uv_scale_v=uv_v,
                flags_val=flags_val,
                tristrip_rel_off=dma_rel_offsets[i],
                strip_vertex_count=strip_vtx_count,
                tex_id=tex_id,
                bbox_i16_vals=bbox_i16,
            )
    else:

        block = geom_block_override
        if not isinstance(block, (bytes, bytearray)):
            raise TypeError("geom_block_override must be bytes or bytearray")
        max_len = DMA_START_OFF - GEOM_HDR_OFF
        blen = min(len(block), max_len)
        out[GEOM_HDR_OFF:GEOM_HDR_OFF + blen] = block[:blen]

    for pkt in dma_packets:
        out.extend(pkt)

    def align(n: int, a: int) -> int:
        return (n + (a - 1)) & ~(a - 1)

    out_off = len(out)
    out_off = align(out_off, 0x10)
    if len(out) < out_off:
        out.extend(b"\x00" * (out_off - len(out)))

    local_num_table_off = out_off
    s0 = material_names[0].encode("ascii", errors="replace") + b"\x00"
    out.extend(s0)

    global_num_table_off = align(len(out), 4)
    if len(out) < global_num_table_off:
        out.extend(b"\x00" * (global_num_table_off - len(out)))

    pointer_offsets = [
        0x38,
        0x3C,
        0xC8,
        0xE4,
        0xE8,
        0xEC,
        0xF4,
        0x114,
        0x120,
        0x128,
        0x134,
        0x138,
        0x13C,
        0x15C,
        0x20,
        0x104,
    ]

    ptr2_before_tex_off = global_num_table_off + 4 + (len(pointer_offsets) - 1) * 4

    out.extend(struct.pack("<I", ptr2_before_tex_off))
    for o in pointer_offsets:
        out.extend(struct.pack("<I", o))

    out_off2 = align(len(out), 0x10)
    if len(out) < out_off2:
        out.extend(b"\x00" * (out_off2 - len(out)))

    string1_off = local_num_table_off
    if len(material_names) > 1:
        string1_off = len(out)
        s1 = material_names[1].encode("ascii", errors="replace") + b"\x00"
        out.extend(s1)

    struct.pack_into("<I", out, TEXLIST_OFF + 0x08, local_num_table_off)

    struct.pack_into("<I", out, TEXLIST_OFF + 0x1C, string1_off)

    struct.pack_into("<I", out, ATOMIC1_OFF + 0x34, string1_off)

    GLOBAL_GEOM_HDR_OFF = GEOM_HDR_OFF + GEOM_PREAMBLE_SIZE
    geom_section_size = local_num_table_off - GLOBAL_GEOM_HDR_OFF
    packed_size_and_material_count = (((len(dma_packets) & 0xFFF) << 20) |
                                      (geom_section_size & 0xFFFFF))
    struct.pack_into("<I", out, GLOBAL_GEOM_HDR_OFF + 0x10, packed_size_and_material_count)

    struct.pack_into("<I", out, 0x0C, local_num_table_off)
    struct.pack_into("<I", out, 0x10, global_num_table_off)
    struct.pack_into("<I", out, 0x18, ptr2_before_tex_off)

    logical_len = len(out)
    struct.pack_into("<I", out, 0x08, logical_len)

    pad = (0x800 - (len(out) % 0x800)) % 0x800
    if pad:
        out.extend(b"\x00" * pad)

    with open(filepath, "wb") as f:
        f.write(out)

    _write_mdl_export_log(
        filepath,
        mdl_kind="PROP_PS2",
        export_context={
            "material_names": list(material_names),
            "part_headers": list(part_headers or []),
            "pointer_offsets_hint": list(pointer_offsets),
            "local_num_offset": int(local_num_table_off),
            "global_num_offset": int(global_num_table_off),
            "ptr2_before_tex_offset": int(ptr2_before_tex_off),
        },
    )

def _ped_template_decode_u32(raw_value: int) -> int:
    raw_value = int(raw_value) & 0xFFFFFFFF
    packed = bytearray(struct.pack("<I", raw_value))
    changed = False
    for i, b in enumerate(packed):
        if b == 0x20:
            packed[i] = 0
            changed = True
    if not changed:
        return raw_value
    return struct.unpack("<I", bytes(packed))[0]

def _ped_template_meta_u32(meta: Dict[str, Any], *keys: str) -> int:
    for key in keys:
        if key in meta and meta[key] is not None:
            try:
                return int(meta[key]) & 0xFFFFFFFF
            except Exception:
                continue
    return 0

def _resolve_ped_template_source_path(atomic_meta: Dict[str, Any], export_path: str = "") -> str:
    try:
        import os
        for key in (
            "source_filepath",
            "roundtrip_source_path",
            "bleeds_mdl_filepath",
            "filepath",
            "source_path",
        ):
            raw = atomic_meta.get(key) if isinstance(atomic_meta, dict) else None
            if raw is None:
                continue
            path = str(raw).strip()
            if path and os.path.isfile(path):
                return path
    except Exception:
        pass
    return ""

def _find_source_atomic1_offset_for_ped(
    data: bytes,
    *,
    frame_ptr: int,
    geom_ptr: int,
    hierarchy_ptr: int,
) -> Optional[int]:
    targets = {
        "frame": int(frame_ptr) & 0xFFFFFFFF,
        "geom": int(geom_ptr) & 0xFFFFFFFF,
        "hier": int(hierarchy_ptr) & 0xFFFFFFFF,
    }
    magic_low24 = int(VCSATOMIC1) & 0x00FFFFFF

    best_match = None
    best_score = -1
    data_len = len(data)
    for off in range(0, max(0, data_len - 0x34), 4):
        raw_magic = struct.unpack_from("<I", data, off)[0]
        dec_magic = _ped_template_decode_u32(raw_magic)
        if (dec_magic & 0x00FFFFFF) != magic_low24 and (raw_magic & 0x00FFFFFF) != magic_low24:
            continue

        score = 0
        raw_frame = struct.unpack_from("<I", data, off + 0x04)[0]
        raw_geom = struct.unpack_from("<I", data, off + 0x14)[0]
        raw_hier = struct.unpack_from("<I", data, off + 0x2C)[0]
        vals = {
            "frame": _ped_template_decode_u32(raw_frame),
            "geom": _ped_template_decode_u32(raw_geom),
            "hier": _ped_template_decode_u32(raw_hier),
        }
        for name, want in targets.items():
            if want and vals[name] == want:
                score += 1
        if score > best_score:
            best_score = score
            best_match = off
            if score >= 3:
                break

    if best_score < 2:
        return None
    return int(best_match) if best_match is not None else None

def _extract_ps2_ped_collision_template(
    data: bytes,
    *,
    frame_ptr: int = 0,
    atomic_off: int = 0,
) -> Dict[str, Any]:
    if not isinstance(data, (bytes, bytearray)) or len(data) < 0x60:
        return {}

    def read_u32_at(offset: int) -> int:
        try:
            offset = int(offset)
            if offset < 0 or offset + 4 > len(data):
                return 0
            return _ped_template_decode_u32(struct.unpack_from('<I', data, offset)[0]) & 0xFFFFFFFF
        except Exception:
            return 0

    def parse_full_header(off: int) -> Dict[str, Any]:
        off = int(off or 0)
        if off <= 0 or off + 0x60 > len(data):
            return {}
        try:
            if data[off:off + 12] != b'\x00' * 12:
                return {}
            marker = struct.unpack_from('<I', data, off + 0x0C)[0]
            if marker != 0x40000000:
                return {}
            count = read_u32_at(off + 0x34)
            entries_ptr = read_u32_at(off + 0x38)
            if count <= 0 or count > 256:
                return {}
            if entries_ptr < off + 0x40 or entries_ptr + (count * 0x20) > len(data):
                return {}
            if data[off + 0x54:off + 0x60] != (b'\xAA' * 12):
                return {}

            ids: List[int] = []
            radii: List[float] = []
            for entry_index in range(count):
                entry_off = entries_ptr + (entry_index * 0x20)
                entry = data[entry_off:entry_off + 0x20]
                if len(entry) != 0x20:
                    return {}
                if entry[0:12] != b'\x00' * 12:
                    return {}
                if entry[0x10] != 0x11:
                    return {}
                if entry[0x12:0x20] != b'\xAA' * 14:
                    return {}
                ids.append(int(entry[0x11]) & 0xFF)
                radii.append(float(struct.unpack_from('<f', entry, 0x0C)[0]))

            return {
                'ped_collision_header_offset': int(off),
                'ped_collision_entries_offset': int(entries_ptr),
                'ped_collision_count': int(count),
                'ped_collision_ids': [int(v) & 0xFF for v in ids],
                'ped_collision_radii': [float(v) for v in radii],
                'ped_collision_header_bytes': bytes(data[off:off + 0x60]),
            }
        except Exception:
            return {}

    header_ptr = read_u32_at(0x20)
    parsed = parse_full_header(header_ptr)
    if parsed:
        return parsed

    frame_ptr = int(frame_ptr or 0)
    atomic_off = int(atomic_off or 0)
    search_end = len(data)
    positive_anchors = [v for v in (frame_ptr, atomic_off) if v > 0]
    if positive_anchors:
        search_end = min(search_end, max(positive_anchors))
    search_start = max(0, search_end - 0x2000)

    best: Dict[str, Any] = {}
    best_score = -1
    for off in range(search_start, max(search_start, search_end - 0x60), 4):
        parsed = parse_full_header(off)
        if not parsed:
            continue
        count = int(parsed.get('ped_collision_count', 0) or 0)
        score = count * 1000
        if frame_ptr > 0:
            score -= abs(int(off) - int(frame_ptr))
        if score > best_score:
            best_score = int(score)
            best = parsed

    if best:
        return best

    best_score = -1
    for off in range(search_start, max(search_start, search_end - 0x30), 4):
        if off + 0x30 > len(data):
            break
        count = read_u32_at(off + 0x04)
        entries_ptr = read_u32_at(off + 0x08)
        if count <= 0 or count > 256:
            continue
        if entries_ptr != off + 0x30:
            continue
        if entries_ptr + (count * 0x20) > len(data):
            continue
        try:
            if not (read_u32_at(off + 0x20) == 0 and read_u32_at(off + 0x24) == 0xAAAAAAAA and read_u32_at(off + 0x28) == 0xAAAAAAAA and read_u32_at(off + 0x2C) == 0xAAAAAAAA):
                continue
            ids: List[int] = []
            radii: List[float] = []
            valid = True
            for entry_index in range(count):
                entry_off = entries_ptr + (entry_index * 0x20)
                entry = data[entry_off:entry_off + 0x20]
                if len(entry) != 0x20 or entry[0:12] != b'\x00' * 12 or entry[0x10] != 0x11 or entry[0x12:0x20] != b'\xAA' * 14:
                    valid = False
                    break
                ids.append(int(entry[0x11]) & 0xFF)
                radii.append(float(struct.unpack_from('<f', entry, 0x0C)[0]))
            if not valid:
                continue
            score = int(count) * 1000
            if frame_ptr > 0:
                score -= abs(int(off) - int(frame_ptr))
            if score > best_score:
                best_score = int(score)
                best = {
                    'ped_collision_header_offset': int(off),
                    'ped_collision_entries_offset': int(entries_ptr),
                    'ped_collision_count': int(count),
                    'ped_collision_ids': [int(v) & 0xFF for v in ids],
                    'ped_collision_radii': [float(v) for v in radii],
                }
        except Exception:
            continue

    return best

def _build_ps2_ped_header_material_entry_ptrs(
    template_blocks: Optional[Dict[str, Any]],
    material_offsets: List[int],
) -> List[int]:
    offsets = [int(v) & 0xFFFFFFFF for v in list(material_offsets or []) if int(v) > 0]
    if not offsets:
        return [0, 0, 0]

    rebuilt: List[int] = []
    blocks = dict(template_blocks or {})

    header_extra_indices = blocks.get("header_extra_material_indices")
    if isinstance(header_extra_indices, list):
        for idx in list(header_extra_indices)[:3]:
            try:
                idx_int = int(idx)
            except Exception:
                idx_int = -1
            if 0 <= idx_int < len(offsets):
                rebuilt.append(int(offsets[idx_int]) & 0xFFFFFFFF)
            else:
                rebuilt.append(0)

    if not rebuilt:
        source_ptrs = blocks.get("header_extra_ptrs")
        entry_ptrs = blocks.get("material_entry_ptrs")
        if isinstance(source_ptrs, list) and isinstance(entry_ptrs, list) and entry_ptrs:
            resolved_indices: List[int] = []
            for raw_ptr in list(source_ptrs)[:3]:
                try:
                    decoded = int(raw_ptr) & 0xFFFFFFFF
                except Exception:
                    decoded = 0
                try:
                    resolved_indices.append(list(entry_ptrs).index(decoded))
                except Exception:
                    resolved_indices.append(-1)
            for idx_int in resolved_indices[:3]:
                if 0 <= idx_int < len(offsets):
                    rebuilt.append(int(offsets[idx_int]) & 0xFFFFFFFF)
                else:
                    rebuilt.append(0)

    if not rebuilt:
        rebuilt = list(offsets[:3])

    while len(rebuilt) < 3:
        rebuilt.append(0)

    return [int(v) & 0xFFFFFFFF for v in rebuilt[:3]]
def _load_ped_source_template_blocks(atomic_meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = dict(atomic_meta or {})
    source_path = _resolve_ped_template_source_path(meta, export_path=str(meta.get("export_filepath") or ""))
    if not source_path:
        return {}

    try:
        with open(source_path, "rb") as source_file:
            data = source_file.read()
    except Exception:
        return {}

    if not isinstance(data, (bytes, bytearray)) or len(data) < 0x40:
        return {}

    def read_u32_at(offset: int) -> int:
        try:
            offset = int(offset)
            if offset < 0 or offset + 4 > len(data):
                return 0
            return _ped_template_decode_u32(struct.unpack_from("<I", data, offset)[0]) & 0xFFFFFFFF
        except Exception:
            return 0

    result: Dict[str, Any] = {"source_path": str(source_path)}

    header_struct_ptr = read_u32_at(0x20)
    clump_offset = read_u32_at(0x24)
    result["struct_or_flags_ptr"] = int(header_struct_ptr)
    result["clump_offset"] = int(clump_offset)

    frame_ptr = int(_ped_template_meta_u32(meta, "frame_ptr", "bleeds_mdl_frame_ptr") or 0)
    geom_ptr = int(_ped_template_meta_u32(meta, "geom_ptr", "geometry_ptr", "bleeds_mdl_geom_ptr") or 0)
    hierarchy_ptr = int(_ped_template_meta_u32(meta, "hierarchy_ptr", "bleeds_mdl_hierarchy_ptr") or 0)

    atomic_offset = 0
    if frame_ptr and geom_ptr and hierarchy_ptr:
        found_atomic = _find_source_atomic1_offset_for_ped(
            data,
            frame_ptr=int(frame_ptr),
            geom_ptr=int(geom_ptr),
            hierarchy_ptr=int(hierarchy_ptr),
        )
        if found_atomic is not None:
            atomic_offset = int(found_atomic)

    if atomic_offset <= 0:
        magic_low24 = int(VCSATOMIC1) & 0x00FFFFFF
        best_score = -1
        best_off = 0
        for off in range(0, max(0, len(data) - 0x34), 4):
            raw_magic = read_u32_at(off)
            if (raw_magic & 0x00FFFFFF) != magic_low24:
                continue
            score = 0
            cand_frame = read_u32_at(off + 0x04)
            cand_geom = read_u32_at(off + 0x14)
            cand_hier = read_u32_at(off + 0x2C)
            if frame_ptr and cand_frame == frame_ptr:
                score += 2
            if geom_ptr and cand_geom == geom_ptr:
                score += 2
            if hierarchy_ptr and cand_hier == hierarchy_ptr:
                score += 2
            if clump_offset and read_u32_at(off + 0x18) == clump_offset:
                score += 1
            if score > best_score:
                best_score = score
                best_off = int(off)
        if best_score >= 2:
            atomic_offset = int(best_off)

    if atomic_offset > 0:
        result["atomic_offset"] = int(atomic_offset)
        if not frame_ptr:
            frame_ptr = read_u32_at(atomic_offset + 0x04)
        if not geom_ptr:
            geom_ptr = read_u32_at(atomic_offset + 0x14)
        if not hierarchy_ptr:
            hierarchy_ptr = read_u32_at(atomic_offset + 0x2C)

    if frame_ptr:
        result["frame_offset"] = int(frame_ptr)
    if geom_ptr:
        result["geometry_offset"] = int(geom_ptr)
    if hierarchy_ptr:
        result["hierarchy_offset"] = int(hierarchy_ptr)

    hierarchy_count = 0
    if hierarchy_ptr > 0 and hierarchy_ptr + 8 <= len(data):
        try:
            if read_u32_at(hierarchy_ptr) == 0x00003000:
                hierarchy_count = read_u32_at(hierarchy_ptr + 0x04)
        except Exception:
            hierarchy_count = 0
    if hierarchy_count > 0:
        result["hierarchy_count"] = int(hierarchy_count)

    if geom_ptr > 0 and geom_ptr + 0x20 <= len(data):
        aux_header = read_u32_at(geom_ptr + 0x18)
        if aux_header > 0 and aux_header + 0x10 <= len(data) and read_u32_at(aux_header) == 0x19:
            matrix_table = read_u32_at(aux_header + 0x0C)
            matrix_count = int(hierarchy_count or 0)
            if matrix_count <= 0 or matrix_count > 256:
                matrix_count = 25
            matrix_size = int(matrix_count) * 0x40
            if matrix_table > 0 and matrix_table + matrix_size <= len(data):
                result["aux_header_offset"] = int(aux_header)
                result["bind_matrix_table_offset"] = int(matrix_table)
                result["bind_matrix_count"] = int(matrix_count)
                result["bind_matrix_table_bytes"] = bytes(data[matrix_table:matrix_table + matrix_size])
                result["inverse_matrix_table_bytes"] = bytes(data[matrix_table:matrix_table + matrix_size])

    collision = _extract_ps2_ped_collision_template(
        data,
        frame_ptr=int(frame_ptr or 0),
        atomic_off=int(atomic_offset or 0),
    )
    if isinstance(collision, dict):
        result.update(collision)

    return result

def _load_ps2_ped_source_relocation_info(atomic_meta: Dict[str, Any]) -> Dict[str, Any]:
    return {}

def _collect_ps2_ped_source_frame_layout(atomic_meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = dict(atomic_meta or {})
    template = _load_ped_source_template_blocks(meta)
    source_path = str(template.get("source_path") or _resolve_ped_template_source_path(meta) or "")
    frame_ptr = int(template.get("frame_offset", 0) or _ped_template_meta_u32(meta, "frame_ptr", "bleeds_mdl_frame_ptr") or 0)
    if not source_path or frame_ptr <= 0:
        return {}

    try:
        with open(source_path, "rb") as source_file:
            data = source_file.read()
    except Exception:
        return {}

    names: List[str] = []
    seen: set[int] = set()

    def read_name(node_off: int) -> str:
        for rel in (0xA8, 0xA4):
            ptr_off = int(node_off) + rel
            if ptr_off + 4 > len(data):
                continue
            ptr = _ped_template_decode_u32(struct.unpack_from("<I", data, ptr_off)[0])
            if 0 < ptr < len(data):
                name = _read_cstring_from_blob(data, ptr)
                if name:
                    return str(name)
        return ""

    def walk(node_off: int) -> None:
        node_off = int(node_off or 0)
        if node_off <= 0 or node_off + 0xB0 > len(data) or node_off in seen:
            return
        tag = _ped_template_decode_u32(struct.unpack_from("<I", data, node_off)[0])
        if tag not in (0x0180AA00, 0x0380AA00):
            return
        seen.add(node_off)
        name = read_name(node_off)
        if name:
            names.append(name)
        child = _ped_template_decode_u32(struct.unpack_from("<I", data, node_off + 0x90)[0])
        sib = _ped_template_decode_u32(struct.unpack_from("<I", data, node_off + 0x94)[0])
        if child:
            walk(child)
        if sib:
            walk(sib)

    walk(frame_ptr)

    base_helper_name = ""
    for name in names:
        canon = canon_frame_name(name)
        if canon.startswith(canon_frame_name("male_base")) or canon.startswith(canon_frame_name("female_base")):
            base_helper_name = str(name)
            break

    return {
        "source_path": str(source_path),
        "frame_ptr": int(frame_ptr),
        "base_helper_name": str(base_helper_name),
        "string_pool_order": list(names),
        "string_pool_size_raw": 0,
        "string_pool_size_rounded": 0,
    }

def _reorder_pending_frame_names_from_source(
    pending_frame_names: List[PendingFrameName],
    *,
    atomic_meta: Optional[Dict[str, Any]] = None,
) -> List[PendingFrameName]:
    ordered_pending = list(pending_frame_names or [])
    if not ordered_pending:
        return ordered_pending

    source_layout = _collect_ps2_ped_source_frame_layout(dict(atomic_meta or {}))
    source_order = list(source_layout.get("string_pool_order", []) or [])
    if not source_order:
        return ordered_pending

    rank_map: Dict[str, int] = {}
    for idx, raw_name in enumerate(source_order):
        canon_name = canon_frame_name(str(raw_name))
        if canon_name and canon_name not in rank_map:
            rank_map[canon_name] = int(idx)

    with_index = list(enumerate(ordered_pending))
    with_index.sort(
        key=lambda item: (
            0 if canon_frame_name(str(item[1][1])) in rank_map else 1,
            rank_map.get(canon_frame_name(str(item[1][1])), 10 ** 9),
            int(item[0]),
        )
    )
    return [entry for _, entry in with_index]

def _measure_ps2_ped_source_name_table(atomic_meta: Dict[str, Any]) -> Tuple[int, int]:
    layout = _collect_ps2_ped_source_frame_layout(dict(atomic_meta or {}))
    return (
        int(layout.get("string_pool_size_raw", 0) or 0),
        int(layout.get("string_pool_size_rounded", 0) or 0),
    )

def _pad_or_seek_to_absolute_offset(buf: bytearray, target_offset: int) -> bool:
    target_offset = int(target_offset)
    if target_offset < 0:
        return False
    if len(buf) > target_offset:
        return False
    if len(buf) < target_offset:
        buf.extend(b"\x00" * (target_offset - len(buf)))
    return True

def _ped_template_atomic_placement(atomic_meta: Dict[str, Any]) -> str:
    template = _load_ped_source_template_blocks(atomic_meta or {})
    atomic_off = int(template.get("atomic_offset", 0) or 0)
    frame_ptr = int((atomic_meta or {}).get("frame_ptr", 0) or 0)
    if atomic_off <= 0 or frame_ptr <= 0:
        return "after_header"

    diff = int(atomic_off) - int(frame_ptr)
    if diff >= 0x160:
        return "after_node2"
    if diff >= 0xB0:
        return "after_node1"
    return "after_header"

def _ped_template_preferred_offsets(atomic_meta: Dict[str, Any]) -> Dict[str, int]:
    return {}

def _ped_template_geometry_wrapper_info(atomic_meta: Dict[str, Any]) -> Dict[str, int]:
    template = _load_ped_source_template_blocks(atomic_meta or {})
    result: Dict[str, int] = {
        'wrapper_rel': 0,
        'wrapper_aux': 0,
        'wrapper_size': 0x20,
    }
    wrapper_bytes = template.get('hierarchy_wrapper_bytes') or template.get('hierarchy_bytes')
    source_geom_ptr = int((atomic_meta or {}).get('geometry_ptr', 0) or (atomic_meta or {}).get('geom_ptr', 0) or 0)
    if not isinstance(wrapper_bytes, (bytes, bytearray)) or len(wrapper_bytes) < 4:
        return result
    try:
        inner_ptr = _ped_template_decode_u32(struct.unpack_from('<I', wrapper_bytes, 0)[0])
    except Exception:
        inner_ptr = 0
    try:
        aux_val = _ped_template_decode_u32(struct.unpack_from('<I', wrapper_bytes, 4)[0]) if len(wrapper_bytes) >= 8 else 0
    except Exception:
        aux_val = 0
    if source_geom_ptr > 0 and inner_ptr >= source_geom_ptr:
        result['wrapper_rel'] = int(inner_ptr - source_geom_ptr) & 0xFFFFFFFF
    result['wrapper_aux'] = int(aux_val) & 0xFFFFFFFF
    if isinstance(wrapper_bytes, (bytes, bytearray)) and len(wrapper_bytes) >= 0x20:
        result['wrapper_size'] = 0x20
    return result

def _find_nearest_ps2_geometry_packet_header(
    buf: bytearray,
    *,
    geom_offset: int,
    desired_offset: int,
) -> int:
    geom_offset = int(geom_offset)
    desired_offset = int(desired_offset)
    if geom_offset < 0:
        geom_offset = 0
    if desired_offset < geom_offset:
        desired_offset = geom_offset

    candidates: List[int] = []
    end = max(geom_offset, len(buf) - 4)
    for off in range(geom_offset, end + 1, 4):
        try:
            val = struct.unpack_from('<I', buf, off)[0]
        except Exception:
            break
        if (val & 0xFF00FF00) == 0x79008000:
            candidates.append(int(off))

    if not candidates:
        return desired_offset

    prev_candidates = [off for off in candidates if off <= desired_offset]
    if prev_candidates:
        return prev_candidates[-1]

    return candidates[0]

def _append_ps2_geometry_wrapper(
    buf: bytearray,
    pointer_fields: List[int],
    *,
    geom_offset: int,
    atomic_meta: Optional[Dict[str, Any]] = None,
) -> int:
    align_buffer(buf, 16)
    wrapper_off = len(buf)
    info = _ped_template_geometry_wrapper_info(dict(atomic_meta or {}))
    inner_target = int(geom_offset) + int(info.get('wrapper_rel', 0) or 0)
    if inner_target < int(geom_offset):
        inner_target = int(geom_offset)
    inner_target = _find_nearest_ps2_geometry_packet_header(
        buf,
        geom_offset=int(geom_offset),
        desired_offset=int(inner_target),
    )
    first_field = len(buf)
    write_u32(buf, inner_target)
    pointer_fields.append(int(first_field))
    write_u32(buf, int(info.get('wrapper_aux', 0) or 0))
    while len(buf) < wrapper_off + int(info.get('wrapper_size', 0x20) or 0x20):
        buf.append(0)
    return wrapper_off

def _ped_export_name_sets(import_type_hint: Optional[int]) -> Tuple[List[str], List[str], Dict[str, str]]:
    try:
        imp = int(import_type_hint) if import_type_hint is not None else None
    except Exception:
        imp = None

    if imp in (2, 3):
        return (list(kamFrameNameVCS), list(commonBoneOrderVCS), dict(commonBoneParentsVCS))
    return (list(kamFrameName), list(commonBoneOrder), dict(commonBoneParentsLCS))

def _official_vcs_frame_disk_name(raw_name: str) -> str:
    name = str(raw_name or "")
    canon = canon_frame_name(name)
    vcs_lookup: Dict[str, str] = {
        canon_frame_name("scene_root"): "scene_root",
        canon_frame_name("male_base"): "male_base",
        canon_frame_name("female_base"): "female_base",
    }
    for disk_name in kamFrameNameVCS:
        vcs_lookup[canon_frame_name(disk_name)] = disk_name
    return vcs_lookup.get(canon, name)

def _write_ps2_frame_matrix_block(buf: bytearray, m: Any) -> None:
    try:
        mat = Matrix(m)
    except Exception:
        mat = Matrix.Identity(4)

    try:
        mat = mat.copy()
        if getattr(mat, 'size', 4) != 4:
            mat = mat.to_4x4()
    except Exception:
        mat = Matrix.Identity(4)

    right = (float(mat[0][0]), float(mat[1][0]), float(mat[2][0]))
    up    = (float(mat[0][1]), float(mat[1][1]), float(mat[2][1]))
    at    = (float(mat[0][2]), float(mat[1][2]), float(mat[2][2]))
    pos   = (float(mat[0][3]), float(mat[1][3]), float(mat[2][3]))

    for row_index, row in enumerate((right, up, at, pos)):
        write_f32(buf, row[0])
        write_f32(buf, row[1])
        write_f32(buf, row[2])
        write_u32(buf, 1 if row_index == 3 else 0)

VCS_PED_RUNTIME_FRAME_GLOBAL_ROWS = {
    'male_base01': ((1.0, -2.137341438222958e-18, 0.0, 4.467536118824e-09), (2.137341438222958e-18, 1.0, 0.0, 0.034034959971904755), (0.0, 0.0, 1.0, 1.3512089252471924), (0.0, 0.0, 0.0, 1.0)),
    'root': ((-1.430511474609375e-06, -1.0, 0.0, 0.0), (1.0, -1.430511474609375e-06, 0.0, 0.0), (0.0, -0.0, 1.0, 0.996275007724762), (0.0, 0.0, 0.0, 1.0)),
    'pelvis': ((1.4007091522216797e-06, -2.8014183044433594e-06, -1.0, 0.0), (2.0037305148434825e-12, 1.0, -2.8312206268310547e-06, 0.0), (1.0, 0.0, 1.3709068298339844e-06, 0.996275007724762), (0.0, 0.0, 0.0, 1.0)),
    'spine': ((5.161336602554911e-08, 1.3589575473815785e-06, -1.0, 3.177025531542199e-09), (0.0007962306262925267, 0.9999997019767761, 1.3291955838212743e-06, -0.00014456371718551964), (0.9999997019767761, -0.0007962306262925267, 2.0728975869133137e-08, 1.0960111618041992), (0.0, 0.0, 0.0, 1.0)),
    'spine1': ((5.161336602554911e-08, 1.3589575473815785e-06, -1.0, 8.823777264410637e-09), (0.0007962306262925267, 0.9999997019767761, 1.3291955838212743e-06, -0.00019139170763082802), (0.9999997019767761, -0.0007962306262925267, 2.0728975869133137e-08, 1.2775012254714966), (0.0, 0.0, 0.0, 1.0)),
    'neck': ((-6.706928701305515e-08, 1.3581900475401198e-06, -1.0, 1.6097574828677352e-08), (0.08230458945035934, 0.99660724401474, 1.318259251092968e-06, -0.0001101364177884534), (0.99660724401474, -0.08230458945035934, -2.0842934134179814e-07, 1.5177991390228271), (0.0, 0.0, 0.0, 1.0)),
    'head': ((4.09056042371958e-08, 1.3594043366538244e-06, -1.0, 5.054726415210098e-09), (-1.4280445839176537e-06, 1.0, 1.3296015595187782e-06, 0.011305262334644794), (1.0, 1.4280442428571405e-06, 1.1105230512953312e-08, 1.6560256481170654), (0.0, 0.0, 0.0, 1.0)),
    'jaw': ((0.9999999403953552, 1.3594060419563903e-06, -1.3299987813297776e-06, 3.102416457068102e-08), (-1.3296033785081818e-06, 1.0, 2.468798498966862e-09, 0.030347924679517746), (1.3598011037174729e-06, -2.467231752234511e-09, 0.9999999403953552, 1.6580487489700317), (0.0, 0.0, 0.0, 1.0)),
    'bip01_l_clavicle': ((-0.9998235106468201, 1.4161036006044014e-06, 0.018785972148180008, -0.030353982001543045), (-1.4445416809394374e-06, -1.0, -6.428360421750767e-08, -1.210070621482373e-07), (0.018785974010825157, -8.658349059942338e-08, 0.9998235106468201, 1.5177900791168213), (0.0, 0.0, 0.0, 1.0)),
    'l_upperarm': ((-0.33415302634239197, -0.26167112588882446, -0.905466616153717, -0.20133663713932037), (0.5750886797904968, -0.8177363872528076, 0.02408745512366295, -3.680422366869607e-07), (-0.7467360496520996, -0.5126747488975525, 0.4237332046031952, 1.5210028886795044), (0.0, 0.0, 0.0, 1.0)),
    'l_forearm': ((-0.30512621998786926, -0.29500502347946167, -0.905466616153717, -0.2941475212574005), (0.657017171382904, -0.7534906268119812, 0.024087443947792053, 0.15973031520843506), (-0.6893666386604309, -0.5875574946403503, 0.4237331449985504, 1.3135972023010254), (0.0, 0.0, 0.0, 1.0)),
    'l_hand': ((-0.26784390211105347, 0.905204176902771, -0.32994672656059265, -0.3750544786453247), (0.742031455039978, -0.02462085150182247, -0.6699127554893494, 0.33394432067871094), (-0.614531397819519, -0.4242629110813141, -0.6650955677032471, 1.1308053731918335), (0.0, 0.0, 0.0, 1.0)),
    'l_finger': ((-0.26784390211105347, 0.905466616153717, -0.3292258381843567, -0.40409088134765625), (0.742031455039978, -0.02408743090927601, -0.6699321866035461, 0.41438645124435425), (-0.614531397819519, -0.4237331748008728, -0.6654331684112549, 1.0641852617263794), (0.0, 0.0, 0.0, 1.0)),
    'bip01_r_clavicle': ((0.9998235106468201, 1.4161034869175637e-06, 0.018785983324050903, 0.03035401552915573), (1.4441035318668582e-06, -1.0, 1.1870826455151473e-07, -3.333495612878323e-08), (0.018785983324050903, -8.910305382414663e-08, -0.9998235106468201, 1.5177900791168213), (0.0, 0.0, 0.0, 1.0)),
    'r_upperarm': ((0.3316374123096466, 0.2652413249015808, -0.9053527116775513, 0.20133666694164276), (0.5765477418899536, -0.8165821433067322, -0.02804054692387581, 2.1362528457302687e-07), (-0.7467323541641235, -0.5126798152923584, -0.42373350262641907, 1.5210028886795044), (0.0, 0.0, 0.0, 1.0)),
    'r_forearm': ((0.3048934042453766, 0.29559487104415894, -0.9053527116775513, 0.29344886541366577), (0.6516339182853699, -0.7580150961875916, -0.028040511533617973, 0.1601361632347107), (-0.694559633731842, -0.5814092755317688, -0.4237334728240967, 1.3135981559753418), (0.0, 0.0, 0.0, 1.0)),
    'r_hand': ((0.26755040884017944, -0.9050891399383545, -0.33049988746643066, 0.37429410219192505), (0.7372397184371948, -0.028558198362588882, 0.6750273108482361, 0.3329227566719055), (-0.6203984022140503, -0.4242614805698395, 0.6596270799636841, 1.1294294595718384), (0.0, 0.0, 0.0, 1.0)),
    'r_finger': ((0.2675504982471466, -0.905351996421814, -0.32977911829948425, 0.4032987356185913), (0.7372397184371948, -0.028020642697811127, 0.6750498414039612, 0.4128454029560089), (-0.6203984022140503, -0.42373618483543396, 0.6599646806716919, 1.0621732473373413), (0.0, 0.0, 0.0, 1.0)),
    'l_thigh': ((9.81965442292676e-08, -1.3347868161872611e-06, 1.0, -0.10089899599552155), (0.04557426646351814, 0.9989609718322754, 1.3587272178483545e-06, -1.892473591169619e-07), (-0.9989609718322754, 0.04557426646351814, 1.8872876239584002e-07, 0.9962750673294067), (0.0, 0.0, 0.0, 1.0)),
    'l_calf': ((2.7663955393109063e-07, -1.3115635510985157e-06, 1.0, -0.10089896619319916), (-0.0765017494559288, 0.9970694184303284, 1.3586858358394238e-06, 0.020030789077281952), (-0.9970694184303284, -0.0765017494559288, 2.0529428468307742e-07, 0.5572077631950378), (0.0, 0.0, 0.0, 1.0)),
    'l_foot': ((-4.0884270191554606e-08, -1.4152042240311857e-06, 1.0, -0.1008988618850708), (8.171591048267146e-08, 0.9999999403953552, 1.4450067737925565e-06, -0.01673281379044056), (-0.9999999403953552, 8.171618759433841e-08, -1.1081792372635846e-08, 0.07805705815553665), (0.0, 0.0, 0.0, 1.0)),
    'l_toe0': ((-1.4301052715381957e-06, 8.558771469324711e-08, 1.0, -0.10089904069900513), (0.9999998807907104, -2.2111199982077778e-08, 1.4599078212995664e-06, 0.10902117192745209), (2.2111541042590943e-08, 0.9999998807907104, -5.578531769856454e-08, 0.00200808048248291), (0.0, 0.0, 0.0, 1.0)),
    'r_thigh': ((-7.931470236144378e-08, -1.4989196870374144e-06, 1.0, 0.10089899599552155), (0.04557426646351814, 0.9989609718322754, 1.5307798548747087e-06, 1.0223379831586499e-07), (-0.9989609718322754, 0.04557426646351814, 1.8882200691905382e-08, 0.996275007724762), (0.0, 0.0, 0.0, 1.0)),
    'r_calf': ((1.0987241694238037e-07, -1.4986715086706681e-06, 1.0, 0.10089895129203796), (-0.0765017494559288, 0.9970694184303284, 1.5324878859246382e-06, 0.02003108523786068), (-0.9970694184303284, -0.0765017494559288, 2.4701771295099206e-08, 0.5572077035903931), (0.0, 0.0, 0.0, 1.0)),
    'r_foot': ((-4.0913210597182115e-08, -1.4148914715406136e-06, 1.0, 0.10089898109436035), (8.171615206720162e-08, 0.9999999403953552, 1.4446943623624975e-06, -0.016732515767216682), (-0.9999999403953552, 8.171620891062048e-08, -1.1110759423615946e-08, 0.07805702835321426), (0.0, 0.0, 0.0, 1.0)),
    'r_toe0': ((-1.4297925190476235e-06, 8.561665509887462e-08, 1.0, 0.10089880228042603), (0.9999998807907104, -2.2111441566607937e-08, 1.4595954098695074e-06, 0.10902146995067596), (2.2111562358873016e-08, 0.9999998807907104, -5.581428652590148e-08, 0.0020080506801605225), (0.0, 0.0, 0.0, 1.0)),
}

def _vcs_default_ped_frame_global_matrix(canon_name: str) -> Optional[Matrix]:
    try:
        canon = canon_frame_name(str(canon_name))
    except Exception:
        canon = str(canon_name or '').strip().lower()
    if not canon:
        return None
    for raw_name, rows in VCS_PED_RUNTIME_FRAME_GLOBAL_ROWS.items():
        try:
            if canon_frame_name(raw_name) == canon:
                return Matrix(rows)
        except Exception:
            continue
    return None

def _vcs_runtime_frame_map_looks_valid(world_by_name: Dict[str, Matrix]) -> bool:
    if not world_by_name:
        return False
    pelvis = world_by_name.get(canon_frame_name('pelvis'))
    spine = world_by_name.get(canon_frame_name('spine'))
    if pelvis is None or spine is None:
        return False
    try:

        pelvis_score = max(abs(float(pelvis[0][2])), abs(float(pelvis[2][0])))
        spine_score = max(abs(float(spine[0][2])), abs(float(spine[2][0])))
        return pelvis_score > 0.75 and spine_score > 0.75
    except Exception:
        return False

def _seed_vcs_runtime_frame_maps_if_needed(
    import_type_hint: Optional[int],
    world_by_name: Dict[str, Matrix],
    local_by_name: Dict[str, Matrix],
) -> str:
    try:
        imp = int(import_type_hint) if import_type_hint is not None else None
    except Exception:
        imp = None
    if imp not in (2, 3):
        return 'not_vcs'

    if _vcs_runtime_frame_map_looks_valid(world_by_name):
        return 'kept_imported_vcs_runtime_frame_arrays'

    for raw_name, rows in VCS_PED_RUNTIME_FRAME_GLOBAL_ROWS.items():
        try:
            world_by_name[canon_frame_name(raw_name)] = Matrix(rows)
        except Exception:
            pass
    local_by_name.clear()
    return 'seeded_default_vcs_runtime_frame_arrays'

def _decode_ps2_ped_skin_word(raw_value: int) -> Tuple[int, float]:
    try:
        raw = int(raw_value) & 0xFFFFFFFF
    except Exception:
        raw = 0

    bone_token = raw & 0xFF
    bone_index = int(bone_token // 4)

    weight_word = raw & 0xFFFFFF00
    try:
        weight = float(struct.unpack('<f', struct.pack('<I', weight_word))[0])
    except Exception:
        weight = 0.0

    if not math.isfinite(weight):
        weight = 0.0
    if weight < 0.0:
        weight = 0.0
    if weight > 4.0:
        weight = 4.0

    return bone_index, weight

def _encode_ps2_ped_skin_word(bone_index: int, weight: float) -> int:
    try:
        bone_i = int(bone_index)
    except Exception:
        bone_i = 0
    if bone_i < 0:
        bone_i = 0
    if bone_i > 63:
        bone_i = 63

    try:
        weight_f = float(weight)
    except Exception:
        weight_f = 0.0
    if not math.isfinite(weight_f):
        weight_f = 0.0
    if weight_f < 0.0:
        weight_f = 0.0
    if weight_f > 4.0:
        weight_f = 4.0

    weight_word = struct.unpack('<I', struct.pack('<f', weight_f))[0] & 0xFFFFFF00
    bone_token = (bone_i * 4) & 0xFF
    return weight_word | bone_token

def _coerce_inline_bind_matrix_bytes(value: Any) -> bytes:
    if value is None:
        return b""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    try:
        return bytes((int(v) & 0xFF) for v in list(value))
    except Exception:
        return b""

def _write_ps2_bind_palette_matrix_block(buf: bytearray, m: Any) -> None:
    try:
        mat = Matrix(m)
    except Exception:
        mat = Matrix.Identity(4)

    try:
        mat = mat.copy()
        if getattr(mat, 'size', 4) != 4:
            mat = mat.to_4x4()
    except Exception:
        mat = Matrix.Identity(4)

    right = (float(mat[0][0]), float(mat[1][0]), float(mat[2][0]))
    up    = (float(mat[0][1]), float(mat[1][1]), float(mat[2][1]))
    at    = (float(mat[0][2]), float(mat[1][2]), float(mat[2][2]))
    pos   = (float(mat[0][3]), float(mat[1][3]), float(mat[2][3]))

    for row_index, row in enumerate((right, up, at, pos)):
        write_f32(buf, row[0])
        write_f32(buf, row[1])
        write_f32(buf, row[2])
        write_f32(buf, 1.0 if row_index == 3 else 0.0)

def _append_ps2_ped_frames_from_armature(
    buf: bytearray,
    pointer_fields: List[int],
    *,
    armature_obj: Any,
    import_type_hint: Optional[int] = None,
    reserved_root_off: Optional[int] = None,
    pending_frame_names: Optional[List[PendingFrameName]] = None,
    out_meta: Optional[Dict[str, Any]] = None,
    atomic_meta: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    if armature_obj is None:
        return None

    arm_data = getattr(armature_obj, 'data', None)
    bones = list(getattr(arm_data, 'bones', []) or [])
    if not bones:
        return None

    disk_names, display_names, parent_map = _ped_export_name_sets(import_type_hint)
    try:
        _ped_imp = int(import_type_hint) if import_type_hint is not None else None
    except Exception:
        _ped_imp = None

    canon_to_bone: Dict[str, Any] = {}
    for b in bones:
        candidates: List[str] = []
        try:
            candidates.append(canon_frame_name(str(getattr(b, 'name', ''))))
        except Exception:
            pass
        try:
            if hasattr(b, '__getitem__') and 'bleeds_frame_name' in b:
                candidates.append(canon_frame_name(str(b['bleeds_frame_name'])))
        except Exception:
            pass
        for c in candidates:
            if c and c not in canon_to_bone:
                canon_to_bone[c] = b

    bone_nodes: List[Dict[str, Any]] = []
    for idx, (disk_name, disp_name) in enumerate(zip(disk_names, display_names)):
        candidates: List[str] = []
        try:
            candidates.append(canon_frame_name(disk_name))
        except Exception:
            pass
        try:
            candidates.append(canon_frame_name(disp_name))
        except Exception:
            pass
        try:
            if _ped_imp in (2, 3) and idx < len(commonBoneOrderVCS):
                candidates.append(canon_frame_name(commonBoneOrderVCS[idx]))
        except Exception:
            pass

        bone = None
        for c in candidates:
            if c in canon_to_bone:
                bone = canon_to_bone[c]
                break
        if bone is None:
            continue

        out_disk_name = str(disk_name)
        if _ped_imp in (2, 3):
            out_disk_name = _official_vcs_frame_disk_name(out_disk_name)

        out_display_name = str(disp_name)
        if _ped_imp in (2, 3):
            out_display_name = _official_vcs_frame_disk_name(out_display_name)

        bone_nodes.append({
            'disk_name': out_disk_name,
            'display_name': out_display_name,
            'canon': canon_frame_name(str(disp_name)),
            'bone': bone,
            'parent_index': -1,
            'children': [],
        })

    if not bone_nodes:
        def _bone_sort_key(b):
            bid = 10 ** 9
            try:
                if 'BoneID' in b:
                    bid = int(b['BoneID'])
            except Exception:
                pass
            return (bid, str(getattr(b, 'name', '')))

        for b in sorted(bones, key=_bone_sort_key):
            out_name = str(getattr(b, 'name', 'Bone'))
            try:
                if hasattr(b, '__getitem__') and 'bleeds_frame_name' in b:
                    out_name = str(b['bleeds_frame_name'])
            except Exception:
                pass
            if _ped_imp in (2, 3):
                out_name = _official_vcs_frame_disk_name(out_name)
            bone_nodes.append({
                'disk_name': out_name,
                'display_name': out_name,
                'canon': canon_frame_name(out_name),
                'bone': b,
                'parent_index': -1,
                'children': [],
            })

    bone_to_index = {n['bone']: i for i, n in enumerate(bone_nodes)}
    canon_to_index = {n['canon']: i for i, n in enumerate(bone_nodes)}

    def _matrix_from_flat(flat_values: Any) -> Matrix:
        return Matrix((
            (float(flat_values[0]),  float(flat_values[1]),  float(flat_values[2]),  float(flat_values[3])),
            (float(flat_values[4]),  float(flat_values[5]),  float(flat_values[6]),  float(flat_values[7])),
            (float(flat_values[8]),  float(flat_values[9]),  float(flat_values[10]), float(flat_values[11])),
            (float(flat_values[12]), float(flat_values[13]), float(flat_values[14]), float(flat_values[15])),
        ))

    def _prop_value(owner: Any, key: str, default: Any = None) -> Any:
        try:
            if owner is not None and hasattr(owner, '__contains__') and key in owner:
                return owner[key]
        except Exception:
            pass
        try:
            value = getattr(owner, key)
            if value is not None:
                return value
        except Exception:
            pass
        return default

    def _matrix_from_owner_property(owner: Any, keys: Tuple[str, ...]) -> Optional[Matrix]:
        for key in keys:
            raw = _prop_value(owner, key, None)
            if raw is None:
                continue
            try:
                flat = list(raw)
                if len(flat) == 16:
                    return _matrix_from_flat(flat)
            except Exception:
                pass
        return None

    def _matrix_list_from_owner_property(owner: Any, keys: Tuple[str, ...]) -> List[Matrix]:
        for key in keys:
            raw = _prop_value(owner, key, None)
            if raw is None:
                continue
            try:
                flat = list(raw)
            except Exception:
                continue
            if len(flat) < 16 or (len(flat) % 16) != 0:
                continue
            matrices: List[Matrix] = []
            for base in range(0, len(flat), 16):
                try:
                    matrices.append(_matrix_from_flat(flat[base:base + 16]))
                except Exception:
                    matrices.append(Matrix.Identity(4))
            if matrices:
                return matrices
        return []

    def _build_imported_frame_matrix_maps() -> Tuple[Dict[str, Matrix], Dict[str, Matrix]]:
        world_by_name: Dict[str, Matrix] = {}
        local_by_name: Dict[str, Matrix] = {}
        owners = (armature_obj, getattr(armature_obj, 'data', None), getattr(armature_obj, 'parent', None))
        for owner in owners:
            names_raw = _prop_value(owner, 'bleeds_mdl_frame_names', None)
            if names_raw is None:
                continue
            try:
                names = [str(n) for n in list(names_raw)]
            except Exception:
                continue
            if not names:
                continue
            world_mats = _matrix_list_from_owner_property(owner, (
                'bleeds_mdl_frame_import_global_matrices',
                'bleeds_mdl_frame_global_matrices',
                'bleeds_mdl_frame_world_matrices',
            ))
            local_mats = _matrix_list_from_owner_property(owner, (
                'bleeds_mdl_frame_import_local_matrices',
                'bleeds_mdl_frame_local_matrices',
            ))
            for idx, raw_name in enumerate(names):
                canon = canon_frame_name(raw_name)
                if not canon:
                    continue
                if idx < len(world_mats) and canon not in world_by_name:
                    world_by_name[canon] = world_mats[idx]
                if idx < len(local_mats) and canon not in local_by_name:
                    local_by_name[canon] = local_mats[idx]
        policy = _seed_vcs_runtime_frame_maps_if_needed(import_type_hint, world_by_name, local_by_name)
        try:
            if policy == 'seeded_default_vcs_runtime_frame_arrays' and atomic_meta is not None:
                atomic_meta['frame_matrix_authority'] = 'DEFAULT_VCS_PS2_RUNTIME_FRAME_BASIS'
        except Exception:
            pass
        return world_by_name, local_by_name

    imported_world_by_name, imported_local_by_name = _build_imported_frame_matrix_maps()
    try:
        for owner in (armature_obj, getattr(armature_obj, 'data', None), getattr(armature_obj, 'parent', None)):
            if owner is not None and hasattr(owner, '__setitem__') and imported_world_by_name:
                if _vcs_runtime_frame_map_looks_valid(imported_world_by_name):
                    owner['bleeds_mdl_export_frame_matrix_authority'] = str((atomic_meta or {}).get('frame_matrix_authority', 'VCS_PS2_RUNTIME_FRAME_BASIS'))
    except Exception:
        pass

    try:
        prefer_live_armature_bind_matrices = bool((atomic_meta or {}).get('prefer_live_armature_bind_matrices', False))
    except Exception:
        prefer_live_armature_bind_matrices = False

    try:
        preserve_imported_frame_matrices = bool((atomic_meta or {}).get('preserve_imported_frame_matrices', False))
    except Exception:
        preserve_imported_frame_matrices = False

    if preserve_imported_frame_matrices:

        prefer_live_armature_bind_matrices = False

    def _live_armature_global_matrix(bone: Any) -> Optional[Matrix]:
        try:
            live_m = bone.matrix_local.copy()
            if getattr(live_m, 'size', 4) != 4:
                live_m = live_m.to_4x4()
            try:
                return armature_obj.matrix_world @ live_m
            except Exception:
                return live_m
        except Exception:
            return None

    def _live_armature_local_matrix(bone: Any) -> Optional[Matrix]:
        try:
            live_m = bone.matrix_local.copy()
            if getattr(live_m, 'size', 4) != 4:
                live_m = live_m.to_4x4()
        except Exception:
            return None

        try:
            parent = getattr(bone, 'parent', None)
        except Exception:
            parent = None
        if parent is None:
            return live_m

        try:
            parent_m = parent.matrix_local.copy()
            if getattr(parent_m, 'size', 4) != 4:
                parent_m = parent_m.to_4x4()
            return parent_m.inverted() @ live_m
        except Exception:
            return live_m

    def _int_list_from_owner_property(owner: Any, keys: Tuple[str, ...]) -> List[int]:
        for key in keys:
            raw = _prop_value(owner, key, None)
            if raw is None:
                continue
            try:
                return [int(v) & 0xFFFFFFFF for v in list(raw)]
            except Exception:
                continue
        return []

    def _build_imported_frame_u32_map(keys: Tuple[str, ...]) -> Dict[str, int]:
        out: Dict[str, int] = {}
        owners = (armature_obj, getattr(armature_obj, 'data', None), getattr(armature_obj, 'parent', None))
        for owner in owners:
            names_raw = _prop_value(owner, 'bleeds_mdl_frame_names', None)
            if names_raw is None:
                continue
            try:
                names = [str(n) for n in list(names_raw)]
            except Exception:
                continue
            values = _int_list_from_owner_property(owner, keys)
            if not names or not values:
                continue
            for idx, raw_name in enumerate(names):
                if idx >= len(values):
                    break
                canon = canon_frame_name(raw_name)
                if canon and canon not in out:
                    out[canon] = int(values[idx]) & 0xFFFFFFFF
        return out

    imported_tag_by_name = _build_imported_frame_u32_map(('bleeds_mdl_frame_tags',))
    imported_9c_by_name = _build_imported_frame_u32_map(('bleeds_mdl_frame_field_9c',))
    imported_a0_by_name = _build_imported_frame_u32_map(('bleeds_mdl_frame_field_a0',))
    imported_a4_by_name = _build_imported_frame_u32_map(('bleeds_mdl_frame_field_a4',))

    source_frame_nodes = _collect_ps2_ped_source_frame_node_map(dict(atomic_meta or {}))
    source_nodes_by_canon: Dict[str, Dict[str, Any]] = {}
    try:
        for source_node in list(source_frame_nodes.get('nodes', []) or []):
            if not isinstance(source_node, dict):
                continue
            canon = canon_frame_name(str(source_node.get('canon', '') or source_node.get('name', '') or ''))
            if canon and canon not in source_nodes_by_canon:
                source_nodes_by_canon[canon] = source_node
    except Exception:
        source_nodes_by_canon = {}

    def _source_node_for_canon(canon: str) -> Optional[Dict[str, Any]]:
        canon = canon_frame_name(canon)
        if not canon:
            return None
        node = source_nodes_by_canon.get(canon)
        if node is not None:
            return node

        alias_canons: List[str] = []
        if canon.startswith(canon_frame_name('male_base')):
            alias_canons.extend([canon_frame_name('male_base01'), canon_frame_name('male_base')])
        if canon.startswith(canon_frame_name('female_base')):
            alias_canons.extend([canon_frame_name('female_base01'), canon_frame_name('female_base')])
        for alias in alias_canons:
            node = source_nodes_by_canon.get(alias)
            if node is not None:
                return node
        return None

    def _is_ped_helper_canon(canon: str) -> bool:
        canon = canon_frame_name(canon)
        if not canon:
            return False
        if canon in {
            canon_frame_name('scene_root'),
            canon_frame_name('male_base'),
            canon_frame_name('male_base01'),
            canon_frame_name('female_base'),
            canon_frame_name('female_base01'),
            canon_frame_name('pivots'),
            canon_frame_name(str(base_helper_name)),
        }:
            return True
        if canon.startswith(canon_frame_name('male_base')) or canon.startswith(canon_frame_name('female_base')):
            return True
        return False

    def _source_u32_for_canon(canon: str, imported_map: Dict[str, int], source_key: str, default: Optional[int] = None) -> Optional[int]:
        canon = canon_frame_name(canon)
        if canon in imported_map:
            return int(imported_map[canon]) & 0xFFFFFFFF
        node = _source_node_for_canon(canon)
        if isinstance(node, dict) and source_key in node:
            try:
                return int(node.get(source_key, 0)) & 0xFFFFFFFF
            except Exception:
                pass
        return default

    def _bone_lookup_names(bone: Any) -> List[str]:
        names: List[str] = []
        for key in ('bleeds_frame_name', 'bleeds_mdl_import_frame_name'):
            raw = _prop_value(bone, key, None)
            if raw is not None:
                names.append(str(raw))
        try:
            names.append(str(getattr(bone, 'name', '') or ''))
        except Exception:
            pass
        return [n for n in names if n]

    def _matrix_from_imported_map(bone: Any, matrix_map: Dict[str, Matrix]) -> Optional[Matrix]:
        for name in _bone_lookup_names(bone):
            canon = canon_frame_name(name)
            if canon in matrix_map:
                return matrix_map[canon].copy()
        return None

    def _bone_global_matrix(bone: Any) -> Matrix:

        if preserve_imported_frame_matrices:
            mapped_m = _matrix_from_imported_map(bone, imported_world_by_name)
            if mapped_m is not None:
                return mapped_m

        imported_m = _matrix_from_owner_property(bone, (
            'bleeds_mdl_import_global_matrix',
            'bleeds_mdl_frame_import_global_matrix',
            'bleeds_mdl_export_world_matrix',
            'bleeds_frame_matrix',
        ))
        if imported_m is not None:
            return imported_m

        mapped_m = _matrix_from_imported_map(bone, imported_world_by_name)
        if mapped_m is not None:
            return mapped_m

        live_m = _live_armature_global_matrix(bone)
        if live_m is not None:
            return live_m
        return Matrix.Identity(4)

    def _bone_local_matrix(bone: Any) -> Optional[Matrix]:

        if preserve_imported_frame_matrices:
            mapped_m = _matrix_from_imported_map(bone, imported_local_by_name)
            if mapped_m is not None:
                return mapped_m
            return None

        imported_m = _matrix_from_owner_property(bone, (
            'bleeds_mdl_import_local_matrix',
            'bleeds_mdl_frame_import_local_matrix',
            'bleeds_mdl_export_local_matrix',
            'bleeds_frame_local_matrix',
        ))
        if imported_m is not None:
            return imported_m

        mapped_m = _matrix_from_imported_map(bone, imported_local_by_name)
        if mapped_m is not None:
            return mapped_m

        return _live_armature_local_matrix(bone)

    def _find_source_frame_bone(*names: str) -> Any:
        for raw_name in names:
            try:
                canon = canon_frame_name(str(raw_name))
            except Exception:
                canon = str(raw_name or '').strip().lower()
            if not canon:
                continue
            bone = canon_to_bone.get(canon)
            if bone is not None:
                return bone
        return None

    def _source_matrix_pair_for_bone(bone: Any) -> Tuple[Matrix, Optional[Matrix]]:
        if bone is None:
            return Matrix.Identity(4), None
        return _bone_global_matrix(bone), _bone_local_matrix(bone)

    def _source_frame_name_from_bone(bone: Any, fallback: str) -> str:
        if bone is None:
            return str(fallback)
        try:
            if hasattr(bone, '__getitem__') and 'bleeds_frame_name' in bone:
                name = str(bone['bleeds_frame_name']).strip()
                if name:
                    return name
        except Exception:
            pass
        try:
            name = str(getattr(bone, 'name', '') or '').strip()
            if name:
                return name
        except Exception:
            pass
        return str(fallback)

    scene_root_bone = _find_source_frame_bone('scene_root')
    root_helper_matrix, root_helper_local_matrix = _source_matrix_pair_for_bone(scene_root_bone)
    if scene_root_bone is None:
        root_helper_matrix = Matrix.Identity(4)
        root_helper_local_matrix = Matrix.Identity(4)

    for n in bone_nodes:
        n['global_m'] = _bone_global_matrix(n['bone'])
        n['source_local_m'] = _bone_local_matrix(n['bone'])

    for n in bone_nodes:
        canon_name = str(n.get('canon', '') or '')

        p_name = parent_map.get(str(n.get('display_name', ''))) or parent_map.get(str(n.get('disk_name', '')).replace('~', ' '))
        if p_name:
            try:
                cpn = canon_frame_name(str(p_name))
            except Exception:
                cpn = str(p_name).strip().lower()
            n['parent_index'] = canon_to_index.get(cpn, -1)
            continue

        bone = n['bone']
        p = getattr(bone, 'parent', None)
        if p in bone_to_index:
            n['parent_index'] = bone_to_index[p]

    base_helper_name = 'female_base'
    try:
        source_layout = _collect_ps2_ped_source_frame_layout(dict(atomic_meta or {}))
        source_base_helper_name = str(source_layout.get('base_helper_name', '') or '').strip()
        if source_base_helper_name:
            base_helper_name = source_base_helper_name
        else:
            for owner in (getattr(armature_obj, 'parent', None), armature_obj):
                if owner is None or not hasattr(owner, '__getitem__'):
                    continue
                for key in ('bleeds_base_frame_name', 'bleeds_ped_base_name', 'bleeds_root_helper_name'):
                    if key in owner:
                        raw = str(owner[key]).strip()
                        if not raw:
                            continue
                        base_helper_name = raw
                        raise StopIteration
    except StopIteration:
        pass
    except Exception:
        pass

    atomic_frame_name = ''
    try:
        for owner in (armature_obj, getattr(armature_obj, 'data', None), getattr(armature_obj, 'parent', None)):
            if owner is None or not hasattr(owner, '__getitem__'):
                continue
            for key in ('bleeds_mdl_atomic_frame_name', 'bleeds_base_frame_name'):
                try:
                    if key in owner:
                        raw = str(owner[key]).strip()
                        if raw:
                            atomic_frame_name = raw
                            raise StopIteration
                except StopIteration:
                    raise
                except Exception:
                    pass
    except StopIteration:
        pass

    if atomic_frame_name:
        base_helper_name = atomic_frame_name

    base_helper_bone = _find_source_frame_bone(
        base_helper_name,
        atomic_frame_name,
        'male_base01',
        'male_base',
        'female_base',
    )
    if base_helper_bone is not None:
        base_helper_name = _source_frame_name_from_bone(base_helper_bone, base_helper_name)
    base_helper_matrix, base_helper_local_matrix = _source_matrix_pair_for_bone(base_helper_bone)
    if base_helper_bone is None:
        default_base_matrix = _vcs_default_ped_frame_global_matrix(base_helper_name)
        if default_base_matrix is None:
            default_base_matrix = _vcs_default_ped_frame_global_matrix('male_base01')
        if default_base_matrix is not None:
            base_helper_matrix = default_base_matrix.copy()
            base_helper_local_matrix = default_base_matrix.copy()
        else:
            base_helper_matrix = root_helper_matrix.copy()
            base_helper_local_matrix = root_helper_matrix.copy()

    root_bone_index = canon_to_index.get(canon_frame_name('root'), -1)
    if root_bone_index < 0 and bone_nodes:
        root_bone_index = 0

    root_bone_node = None
    remaining_bone_nodes: List[Dict[str, Any]] = []
    for idx, node in enumerate(bone_nodes):
        if idx == root_bone_index and root_bone_node is None:
            root_bone_node = node
        else:
            remaining_bone_nodes.append(node)

    if root_bone_node is None:
        root_bone_node = {
            'disk_name': 'root',
            'display_name': 'root',
            'canon': canon_frame_name('root'),
            'bone': None,
            'parent_index': -1,
            'children': [],
            'global_m': Matrix.Identity(4),
            'local_m': Matrix.Identity(4),
        }

    scene_root_node = {
        'disk_name': 'scene_root',
        'display_name': 'scene_root',
        'canon': canon_frame_name('scene_root'),
        'bone': scene_root_bone,
        'parent_index': -1,
        'children': [],
        'global_m': root_helper_matrix.copy(),
        'source_local_m': root_helper_local_matrix.copy() if root_helper_local_matrix is not None else None,
    }
    female_base_node = {
        'disk_name': str(base_helper_name),
        'display_name': str(base_helper_name),
        'canon': canon_frame_name(str(base_helper_name)),
        'bone': base_helper_bone,
        'parent_index': 1,
        'children': [],
        'global_m': base_helper_matrix.copy(),
        'source_local_m': base_helper_local_matrix.copy() if base_helper_local_matrix is not None else None,
    }

    nodes: List[Dict[str, Any]] = [root_bone_node, scene_root_node, female_base_node] + remaining_bone_nodes
    helper_count = 3

    for n in nodes[helper_count:]:
        pi = int(n.get('parent_index', -1))
        if pi == root_bone_index:
            n['parent_index'] = 0
        elif pi >= 0:
            shift = helper_count - 1 if pi > root_bone_index else helper_count
            n['parent_index'] = pi + shift
        else:
            n['parent_index'] = 0

    nodes[0]['parent_index'] = 1
    nodes[1]['parent_index'] = -1
    nodes[2]['parent_index'] = 1

    for n in nodes:
        n['children'] = []
    for i, n in enumerate(nodes):
        pi = int(n.get('parent_index', -1))
        if 0 <= pi < len(nodes):
            nodes[pi]['children'].append(i)

    try:
        scene_children = list(nodes[1].get('children', []) or [])
        ordered_scene_children = []
        if 2 in scene_children:
            ordered_scene_children.append(2)
        if 0 in scene_children:
            ordered_scene_children.append(0)
        for child_index in scene_children:
            if child_index not in ordered_scene_children:
                ordered_scene_children.append(child_index)
        nodes[1]['children'] = ordered_scene_children
    except Exception:
        pass

    for i, n in enumerate(nodes):
        gm = n.get('global_m', Matrix.Identity(4))
        pi = int(n.get('parent_index', -1))
        source_local = n.get('source_local_m')

        if source_local is not None and not preserve_imported_frame_matrices:
            try:
                n['local_m'] = Matrix(source_local)
                continue
            except Exception:
                pass
        if 0 <= pi < len(nodes):
            try:
                pm = nodes[pi].get('global_m', Matrix.Identity(4))
                n['local_m'] = pm.inverted() @ gm
            except Exception:
                n['local_m'] = gm.copy()
        else:
            n['local_m'] = gm.copy()

    ordered_indices: List[int] = list(range(len(nodes)))
    ordered_nodes = [dict(n) for n in nodes]

    node_size = 0xB0
    root_frame_off = int(reserved_root_off) if reserved_root_off is not None else len(buf)
    scene_root_off = root_frame_off + node_size

    clump_reserved_off = root_frame_off + (2 * node_size)
    female_base_off = clump_reserved_off + 0x20
    first_regular_off = female_base_off + node_size
    regular_start_off = first_regular_off + node_size

    if ordered_nodes:
        last_index = len(ordered_nodes) - 1
        if last_index <= 0:
            required_end = root_frame_off + node_size
        elif last_index == 1:
            required_end = scene_root_off + node_size
        elif last_index == 2:
            required_end = female_base_off + node_size
        else:
            required_end = first_regular_off + ((last_index - 2) * node_size)
    else:
        required_end = root_frame_off

    align_buffer(buf, 16)
    if len(buf) < required_end:
        buf.extend(b'\x00' * (required_end - len(buf)))

    frames_offset = root_frame_off

    node_offsets: List[int] = []
    for i in range(len(ordered_nodes)):
        if i == 0:
            node_offsets.append(root_frame_off)
        elif i == 1:
            node_offsets.append(scene_root_off)
        elif i == 2:
            node_offsets.append(female_base_off)
        else:
            node_offsets.append(first_regular_off + ((i - 3) * node_size))

    if pending_frame_names is None:
        pending_frame_names = []

    try:
        prev_frame_off = int(reserved_root_off) if reserved_root_off is not None else int(frames_offset)
    except Exception:
        prev_frame_off = 0

    for i, n in enumerate(ordered_nodes):
        node_off = node_offsets[i]
        child_list = list(n.get('children', []) or [])
        child_ptr = node_offsets[child_list[0]] if child_list else 0

        sib_ptr = 0
        pi = int(n.get('parent_index', -1))
        if 0 <= pi < len(ordered_nodes):
            siblings = list(ordered_nodes[pi].get('children', []) or [])
            try:
                pos = siblings.index(i)
                if pos + 1 < len(siblings):
                    sib_ptr = node_offsets[siblings[pos + 1]]
            except Exception:
                sib_ptr = 0
        else:
            try:
                root_nodes = [idx for idx, on in enumerate(ordered_nodes) if int(on.get('parent_index', -1)) < 0]
                pos = root_nodes.index(i)
                if pos + 1 < len(root_nodes):
                    sib_ptr = node_offsets[root_nodes[pos + 1]]
            except Exception:
                sib_ptr = 0

        canon_name = canon_frame_name(str(n.get('disk_name', '')))
        parent_ptr = 0
        if 0 <= pi < len(ordered_nodes):
            parent_ptr = node_offsets[pi]

        root_ptr = scene_root_off if 'scene_root_off' in locals() else (frames_offset if frames_offset is not None else 0)

        source_tag = _source_u32_for_canon(canon_name, imported_tag_by_name, 'tag', None)
        if source_tag in (0x0180AA00, 0x0380AA00):
            magic = int(source_tag) & 0xFFFFFFFF
        else:
            magic = 0x0380AA00 if _is_ped_helper_canon(canon_name) else 0x0180AA00

        struct.pack_into('<I', buf, node_off + 0x00, magic)

        prev_ptr = int(parent_ptr) & 0xFFFFFFFF
        struct.pack_into('<I', buf, node_off + 0x04, prev_ptr)
        if prev_ptr:
            pointer_fields.append(node_off + 0x04)

        self_ptr_val = (node_off + 0x08) & 0xFFFFFFFF
        struct.pack_into('<I', buf, node_off + 0x08, self_ptr_val)
        struct.pack_into('<I', buf, node_off + 0x0C, self_ptr_val)
        pointer_fields.append(node_off + 0x08)
        pointer_fields.append(node_off + 0x0C)

        tmp_local = bytearray()
        _write_ps2_frame_matrix_block(tmp_local, n.get('local_m', Matrix.Identity(4)))
        tmp_global = bytearray()
        _write_ps2_frame_matrix_block(tmp_global, n.get('global_m', Matrix.Identity(4)))
        buf[node_off + 0x10: node_off + 0x50] = tmp_local
        buf[node_off + 0x50: node_off + 0x90] = tmp_global

        struct.pack_into('<I', buf, node_off + 0x90, int(child_ptr) & 0xFFFFFFFF)
        struct.pack_into('<I', buf, node_off + 0x94, int(sib_ptr) & 0xFFFFFFFF)
        try:
            root_stub = int(scene_root_off) if 'scene_root_off' in locals() else (int(reserved_root_off) if reserved_root_off is not None else int(frames_offset))
        except Exception:
            root_stub = 0
        struct.pack_into('<I', buf, node_off + 0x98, root_stub & 0xFFFFFFFF)

        source_field_9c = _source_u32_for_canon(canon_name, imported_9c_by_name, 'field_9c', None)
        source_field_a0 = _source_u32_for_canon(canon_name, imported_a0_by_name, 'field_a0', None)
        source_field_a4 = _source_u32_for_canon(canon_name, imported_a4_by_name, 'field_a4', None)

        if source_field_9c is None or int(source_field_9c) == 0:
            try:
                known_id_map, _known_type_map = _ped_ps2_runtime_hierarchy_maps(import_type_hint)
                mapped_bid = known_id_map.get(canon_name)
                source_field_9c = int(mapped_bid) & 0xFF if mapped_bid is not None else 0
            except Exception:
                source_field_9c = 0
        if source_field_a0 is None:
            source_field_a0 = 0
        if source_field_a4 is None or canon_name == canon_frame_name('root'):
            source_field_a4 = 0

        struct.pack_into('<I', buf, node_off + 0x9C, int(source_field_9c) & 0xFFFFFFFF)
        struct.pack_into('<I', buf, node_off + 0xA0, int(source_field_a0) & 0xFFFFFFFF)
        bone_params_ptr = int(source_field_a4) & 0xFFFFFFFF
        struct.pack_into('<I', buf, node_off + 0xA4, bone_params_ptr)
        name_ptr_field = node_off + 0xA8
        struct.pack_into('<I', buf, name_ptr_field, 0)
        struct.pack_into('<I', buf, node_off + 0xAC, 0)

        if child_ptr:
            pointer_fields.append(node_off + 0x90)
        if sib_ptr:
            pointer_fields.append(node_off + 0x94)

        if root_stub:
            pointer_fields.append(node_off + 0x98)

        if canon_name == canon_frame_name('root'):
            pointer_fields.append(node_off + 0xA4)

        pointer_fields.append(node_off + 0xA8)
        pending_frame_names.append((int(name_ptr_field), str(n.get('disk_name', 'scene_root'))))

        prev_frame_off = node_off

    if out_meta is not None:
        try:
            node_name_to_off: Dict[str, int] = {}
            inverse_matrix_table = bytearray()

            try:
                atomic_frame_global_m = Matrix(base_helper_matrix).copy()
                if getattr(atomic_frame_global_m, 'size', 4) != 4:
                    atomic_frame_global_m = atomic_frame_global_m.to_4x4()
            except Exception:
                atomic_frame_global_m = Matrix.Identity(4)

            non_helper_matrix_count = 0
            for idx, n in enumerate(ordered_nodes):
                canon_name = canon_frame_name(str(n.get('disk_name', '')))
                if canon_name:
                    node_name_to_off[canon_name] = int(node_offsets[idx])
                if _is_ped_helper_canon(canon_name):
                    continue
                non_helper_matrix_count += 1
                try:
                    inv_m = n.get('global_m', Matrix.Identity(4)).inverted()
                except Exception:
                    inv_m = Matrix.Identity(4)
                try:
                    bind_m = inv_m @ atomic_frame_global_m
                except Exception:
                    bind_m = inv_m
                _write_ps2_bind_palette_matrix_block(inverse_matrix_table, bind_m)

            matrix_table_source = 'COMPUTED_INVERSE_FRAME_TIMES_ATOMIC_FRAME'
            matrix_table_to_write = bytes(inverse_matrix_table)

            if preserve_imported_frame_matrices:
                source_bind_bytes = b''
                try:
                    source_bind_bytes = _coerce_inline_bind_matrix_bytes((atomic_meta or {}).get('source_bind_matrix_table_u8'))
                except Exception:
                    source_bind_bytes = b''
                if not source_bind_bytes:
                    try:
                        source_bind_bytes = _coerce_inline_bind_matrix_bytes((atomic_meta or {}).get('bleeds_mdl_inverse_matrix_table_u8'))
                    except Exception:
                        source_bind_bytes = b''
                if not source_bind_bytes:
                    try:
                        source_bind_bytes = bytes((atomic_meta or {}).get('inverse_matrix_table_bytes') or b'')
                    except Exception:
                        source_bind_bytes = b''
                expected_size = int(non_helper_matrix_count) * 0x40
                if expected_size > 0 and len(source_bind_bytes) >= expected_size:
                    matrix_table_source = 'PRESERVED_IMPORTED_STORIES_BIND_PALETTE_TABLE'
                    matrix_table_to_write = bytes(source_bind_bytes[:expected_size])

            out_meta.clear()
            out_meta['frames_offset'] = int(frames_offset)
            out_meta['node_offsets'] = [int(off) for off in node_offsets]
            out_meta['node_count'] = int(len(node_offsets))
            out_meta['scene_root_off'] = int(node_name_to_off.get(canon_frame_name('scene_root'), 0) or 0)
            out_meta['node_name_to_off'] = dict(node_name_to_off)
            out_meta['base_helper_off'] = int(node_name_to_off.get(canon_frame_name(str(base_helper_name)), 0) or 0)
            out_meta['pivots_off'] = int(node_name_to_off.get(canon_frame_name('pivots'), 0) or 0)
            out_meta['root_bone_off'] = int(node_name_to_off.get(canon_frame_name('root'), 0) or 0)
            out_meta['root_bone_a4_off'] = int((node_name_to_off.get(canon_frame_name('root'), 0) or 0) + 0xA4)
            out_meta['pelvis_off'] = int(node_name_to_off.get(canon_frame_name('pelvis'), 0) or 0)
            out_meta['root_bone_name'] = 'root'
            out_meta['inverse_matrix_table_bytes'] = bytes(matrix_table_to_write)
            out_meta['inverse_matrix_count'] = int(len(matrix_table_to_write) // 0x40)
            out_meta['inverse_matrix_table_source'] = str(matrix_table_source)
        except Exception:
            pass

    return frames_offset

def _append_ps2_ped_frames_all_bones(
    buf: bytearray,
    pointer_fields: List[int],
    *,
    armature_obj: Any,
    import_type_hint: Optional[int] = None,
    pending_frame_names: Optional[List[PendingFrameName]] = None,
) -> Optional[int]:
    if armature_obj is None:
        return None

    arm_data = getattr(armature_obj, "data", None)
    bones = list(getattr(arm_data, "bones", []) or [])
    if not bones:
        return None

    try:
        import_type = int(import_type_hint) if import_type_hint is not None else 2
    except Exception:
        import_type = 2

    name_ptr_rel = 0xA8 if import_type == 2 else 0xA4

    base_raw = str(getattr(armature_obj, "name", "model")).strip()
    try:
        par = getattr(armature_obj, "parent", None)
        if par is not None and getattr(par, "type", None) == "EMPTY":
            par_name = str(getattr(par, "name", "") or "").strip()
            if par_name.upper().endswith("_ROOT"):
                base_raw = par_name[:-5].strip() or base_raw
    except Exception:
        pass

    for suf in ("_Arm", "_ARM", "Arm", "arm", "Armature", "_armature", "_ARMATURE"):
        if base_raw.endswith(suf) and len(base_raw) > len(suf):
            base_raw = base_raw[: -len(suf)].strip()
            break

    if not base_raw:
        base_raw = "model"

    base_name = base_raw
    if not canon_frame_name(base_name).endswith("base"):
        base_name = f"{base_name}_base"

    bone_by_name: Dict[str, Any] = {str(b.name): b for b in bones}
    children_by_parent: Dict[str, List[str]] = {str(b.name): [] for b in bones}
    root_bone_names: List[str] = []

    for b in bones:
        bname = str(getattr(b, "name", "Bone"))
        p = getattr(b, "parent", None)
        if p is None:
            root_bone_names.append(bname)
            continue
        pname = str(getattr(p, "name", ""))
        if pname in children_by_parent:
            children_by_parent[pname].append(bname)
        else:

            root_bone_names.append(bname)

    if not root_bone_names:
        root_bone_names = [str(getattr(bones[0], "name", "Bone"))]

    def flat_to_matrix(flat: Any) -> Matrix:
        return Matrix((
            (float(flat[0]),  float(flat[1]),  float(flat[2]),  float(flat[3])),
            (float(flat[4]),  float(flat[5]),  float(flat[6]),  float(flat[7])),
            (float(flat[8]),  float(flat[9]),  float(flat[10]), float(flat[11])),
            (float(flat[12]), float(flat[13]), float(flat[14]), float(flat[15])),
        ))

    def get_bone_global_matrix(b: Any) -> Matrix:

        for key in (
            "bleeds_mdl_import_global_matrix",
            "bleeds_mdl_frame_import_global_matrix",
            "bleeds_mdl_export_world_matrix",
            "bleeds_frame_matrix",
        ):
            try:
                if hasattr(b, "__getitem__") and key in b:
                    flat = b[key]
                    if isinstance(flat, (list, tuple)) and len(flat) == 16:
                        return flat_to_matrix(flat)
            except Exception:
                pass

        try:
            m = b.matrix_local.copy()
        except Exception:
            m = Matrix.Identity(4)

        try:
            return armature_obj.matrix_world @ m
        except Exception:
            return m

    nodes: List[Dict[str, Any]] = []

    def add_node(name: str, parent_index: int, global_m: Matrix) -> int:
        if 0 <= parent_index < len(nodes):
            try:
                parent_global = nodes[parent_index]["global_m"]
                local_m = parent_global.inverted() @ global_m
            except Exception:
                local_m = global_m.copy()
        else:
            local_m = global_m.copy()

        idx = len(nodes)
        nodes.append({
            "name": str(name),
            "parent_index": int(parent_index),
            "global_m": global_m,
            "local_m": local_m,
            "children": [],
        })
        if 0 <= parent_index < len(nodes):
            nodes[parent_index]["children"].append(idx)
        return idx

    base_index = add_node(base_name, -1, Matrix.Identity(4))

    def build_tree(bone_name: str, parent_index: int) -> None:
        b = bone_by_name.get(bone_name)
        if b is None:
            return

        try:
            if hasattr(b, "__getitem__") and "bleeds_frame_name" in b:
                out_name = str(b["bleeds_frame_name"])
            else:
                out_name = str(getattr(b, "name", bone_name))
        except Exception:
            out_name = str(getattr(b, "name", bone_name))

        gmat = get_bone_global_matrix(b)
        idx = add_node(out_name, parent_index, gmat)

        for child_name in children_by_parent.get(bone_name, []) or []:
            build_tree(child_name, idx)

    for rname in root_bone_names:
        build_tree(rname, base_index)

    if len(nodes) <= 1:
        return None

    align_buffer(buf, 16)
    frames_offset = len(buf)
    node_size = 0xB0

    node_offsets = [frames_offset + i * node_size for i in range(len(nodes))]
    for _ in nodes:
        buf.extend(b"\x00" * node_size)

    if pending_frame_names is None:
        pending_frame_names = []

    for i, n in enumerate(nodes):
        off = node_offsets[i]

        children = n.get("children", []) or []
        child_ptr = node_offsets[int(children[0])] if children else 0

        sib_ptr = 0
        pi = int(n.get("parent_index", -1))
        if 0 <= pi < len(nodes):
            sibs = nodes[pi].get("children", []) or []
            try:
                pos = sibs.index(i)
                if pos + 1 < len(sibs):
                    sib_ptr = node_offsets[int(sibs[pos + 1])]
            except Exception:
                sib_ptr = 0

        parent_ptr = 0
        if 0 <= pi < len(nodes):
            parent_ptr = node_offsets[int(pi)]
        root_ptr = node_offsets[0] if node_offsets else 0
        self_ptr = (off + 0x08) & 0xFFFFFFFF
        struct.pack_into("<I", buf, off + 0x00, 0x0180AA00)
        struct.pack_into("<I", buf, off + 0x04, int(parent_ptr) & 0xFFFFFFFF)
        struct.pack_into("<I", buf, off + 0x08, self_ptr)
        struct.pack_into("<I", buf, off + 0x0C, self_ptr)

        tmp_local = bytearray()
        _write_ps2_frame_matrix_block(tmp_local, n.get("local_m", Matrix.Identity(4)))
        tmp_global = bytearray()
        _write_ps2_frame_matrix_block(tmp_global, n.get("global_m", Matrix.Identity(4)))

        buf[off + 0x10: off + 0x50] = tmp_local
        buf[off + 0x50: off + 0x90] = tmp_global

        struct.pack_into("<I", buf, off + 0x90, int(child_ptr) & 0xFFFFFFFF)
        struct.pack_into("<I", buf, off + 0x94, int(sib_ptr) & 0xFFFFFFFF)
        struct.pack_into("<I", buf, off + 0x98, int(root_ptr) & 0xFFFFFFFF)
        name_ptr_field = off + name_ptr_rel
        struct.pack_into("<I", buf, name_ptr_field, 0)

        if parent_ptr:
            pointer_fields.append(off + 0x04)
        if self_ptr:
            pointer_fields.append(off + 0x08)
            pointer_fields.append(off + 0x0C)
        if child_ptr:
            pointer_fields.append(off + 0x90)
        if sib_ptr:
            pointer_fields.append(off + 0x94)
        if root_ptr:
            pointer_fields.append(off + 0x98)
        pointer_fields.append(off + name_ptr_rel)
        pending_frame_names.append((int(name_ptr_field), str(n.get("name", "Bone"))))

    if out_meta is not None:
        try:
            node_name_to_off: Dict[str, int] = {}
            for idx, n in enumerate(nodes):
                canon_name = canon_frame_name(str(n.get("disk_name", "")))
                if canon_name:
                    node_name_to_off[canon_name] = int(node_offsets[idx])
            out_meta.clear()
            out_meta["frames_offset"] = int(frames_offset)
            out_meta["node_offsets"] = [int(off) for off in node_offsets]
            out_meta["node_count"] = int(len(node_offsets))
            out_meta["scene_root_off"] = int(node_name_to_off.get(canon_frame_name("scene_root"), 0) or 0)
            out_meta["node_name_to_off"] = dict(node_name_to_off)
            out_meta["base_helper_off"] = int(node_name_to_off.get(canon_frame_name(str(base_helper_name)), 0) or 0)
            out_meta["pivots_off"] = int(node_name_to_off.get(canon_frame_name("pivots"), 0) or 0)
            out_meta["root_bone_off"] = int(node_name_to_off.get(canon_frame_name("root"), 0) or 0)
            out_meta["root_bone_a4_off"] = int((node_name_to_off.get(canon_frame_name("root"), 0) or 0) + 0xA4)
            out_meta["pelvis_off"] = int(node_name_to_off.get(canon_frame_name("pelvis"), 0) or 0)
            out_meta["root_bone_name"] = "root"
        except Exception:
            pass

    try:
        print(
            f"[BLeeds] PED frames: wrote {len(nodes)} nodes from armature '{getattr(armature_obj, 'name', '?')}' at 0x{frames_offset:X}"
        )
    except Exception:
        pass

    return frames_offset

def _ped_known_hanim_order(import_type_hint: Optional[int]) -> List[str]:
    try:
        imp = int(import_type_hint) if import_type_hint is not None else None
    except Exception:
        imp = None

    if imp in (2, 3):
        return [
            "root", "pelvis", "spine", "spine1", "neck", "head",
            "jaw", "bip01_l_clavicle", "l_upperarm", "l_forearm", "l_hand", "l_finger",
            "bip01_r_clavicle", "r_upperarm", "r_forearm", "r_hand", "r_finger", "l_thigh",
            "l_calf", "l_foot", "l_toe0", "r_thigh", "r_calf", "r_foot", "r_toe0",
        ]
    return [canon_frame_name(n) for n in commonBoneOrder]

def _ped_known_hanim_maps(import_type_hint: Optional[int]) -> Tuple[Dict[str, int], Dict[str, int]]:
    try:
        imp = int(import_type_hint) if import_type_hint is not None else None
    except Exception:
        imp = None

    if imp in (2, 3):

        name_sequence = (
            "root", "pelvis", "spine", "spine1", "neck", "head",
            "jaw", "bip01_l_clavicle", "l_upperarm", "l_forearm", "l_hand", "l_finger",
            "bip01_r_clavicle", "r_upperarm", "r_forearm", "r_hand", "r_finger", "l_thigh",
            "l_calf", "l_foot", "l_toe0", "r_thigh", "r_calf", "r_foot", "r_toe0",
        )
        bone_ids = (
            0x00, 0x01, 0x02, 0x03, 0x04, 0x05,
            0xFF, 0x1F, 0x20, 0x21, 0x22, 0x23,
            0x15, 0x16, 0x17, 0x18, 0x19, 0x29,
            0x2A, 0x2B, 0xFF, 0x33, 0x34, 0x35,
            0xFF,
        )
        bone_types = (
            0, 0, 0, 0, 0, 0,
            1, 0, 0, 0, 0, 1,
            0, 0, 0, 0, 1, 0,
            0, 1, 1, 0, 0, 1,
            1,
        )
    else:
        name_sequence = tuple(canon_frame_name(n) for n in commonBoneOrder)
        bone_ids = tuple(int(v) if int(v) < 256 else 0xFF for v in kamBoneID)
        bone_types = tuple(int(v) for v in kamBoneType)

    id_map: Dict[str, int] = {}
    type_map: Dict[str, int] = {}
    for raw_name, bid, btype in zip(name_sequence, bone_ids, bone_types):
        canon = canon_frame_name(raw_name)
        id_map[canon] = int(bid) & 0xFF
        type_map[canon] = int(btype) & 0xFF
    return id_map, type_map

def _ped_ps2_runtime_hierarchy_maps(import_type_hint: Optional[int]) -> Tuple[Dict[str, int], Dict[str, int]]:
    try:
        imp = int(import_type_hint) if import_type_hint is not None else None
    except Exception:
        imp = None

    if imp in (2, 3):
        name_sequence = (
            "root", "pelvis", "spine", "spine1", "neck", "head",
            "jaw", "bip01_l_clavicle", "l_upperarm", "l_forearm", "l_hand", "l_finger",
            "bip01_r_clavicle", "r_upperarm", "r_forearm", "r_hand", "r_finger",
            "l_thigh", "l_calf", "l_foot", "l_toe0", "r_thigh", "r_calf", "r_foot", "r_toe0",
        )
        bone_ids = (
            0x00, 0x01, 0x02, 0x23, 0x15, 0x35,
            0xFF, 0x2A, 0x2B, 0xFF, 0x33, 0x34,
            0x16, 0x17, 0x18, 0x19, 0x29,
            0x1F, 0x20, 0x21, 0x22, 0x03, 0x04, 0x05, 0x06,
        )
        bone_types = (
            0, 0, 0, 2, 0, 2,
            1, 2, 0, 0, 0, 1,
            0, 0, 0, 0, 1,
            2, 0, 0, 1, 0, 0, 0, 1,
        )
    else:
        name_sequence = tuple(canon_frame_name(n) for n in commonBoneOrder)
        bone_ids = tuple(int(v) if int(v) < 256 else 0xFF for v in kamBoneID)
        bone_types = tuple(int(v) for v in kamBoneType)

    id_map: Dict[str, int] = {}
    type_map: Dict[str, int] = {}
    for raw_name, bid, btype in zip(name_sequence, bone_ids, bone_types):
        canon = canon_frame_name(raw_name)
        id_map[canon] = int(bid) & 0xFF
        type_map[canon] = int(btype) & 0xFF
    return id_map, type_map

def _collect_ps2_ped_hanim_entries(
    *,
    armature_obj: Any,
    import_type_hint: Optional[int] = None,
) -> List[Tuple[int, int, int]]:
    if armature_obj is None:
        return []

    arm_data = getattr(armature_obj, 'data', None)
    bones = list(getattr(arm_data, 'bones', []) or [])
    if not bones:
        return []

    def _read_int_prop(owner: Any, keys: Tuple[str, ...]) -> Optional[int]:
        for key in keys:
            try:
                if hasattr(owner, '__getitem__') and key in owner:
                    return int(owner[key])
            except Exception:
                continue
            try:
                value = getattr(owner, key, None)
                if value is not None:
                    return int(value)
            except Exception:
                continue
        return None

    def _bone_name_for_export(bone: Any) -> str:
        try:
            if hasattr(bone, '__getitem__') and 'bleeds_frame_name' in bone:
                return str(bone['bleeds_frame_name'])
        except Exception:
            pass
        return str(getattr(bone, 'name', 'Bone'))

    def _depth_first_bone_order(root_bones: List[Any], child_map: Dict[str, List[Any]]) -> List[Any]:
        ordered: List[Any] = []

        def _sort_key(b: Any) -> Tuple[int, str]:
            bid = _read_int_prop(b, ('BoneID', 'bone_id', 'bleeds_bone_id', 'bleeds_boneid'))
            if bid is None:
                bid = 10 ** 9
            return (int(bid), str(_bone_name_for_export(b)))

        def _visit(b: Any) -> None:
            ordered.append(b)
            for child in sorted(child_map.get(str(getattr(b, 'name', '')), []) or [], key=_sort_key):
                _visit(child)

        for root_bone in sorted(root_bones, key=_sort_key):
            _visit(root_bone)
        return ordered

    id_map, type_map = _ped_ps2_runtime_hierarchy_maps(import_type_hint)
    known_order = _ped_known_hanim_order(import_type_hint)
    child_map: Dict[str, List[Any]] = {}
    root_bones: List[Any] = []
    canon_to_bone: Dict[str, Any] = {}
    for bone in bones:
        bname = str(getattr(bone, 'name', ''))
        canon_to_bone.setdefault(canon_frame_name(_bone_name_for_export(bone)), bone)
        parent = getattr(bone, 'parent', None)
        if parent is None:
            root_bones.append(bone)
            continue
        pname = str(getattr(parent, 'name', ''))
        child_map.setdefault(pname, []).append(bone)

    ordered_bones: List[Any] = []
    seen_bones: set[int] = set()
    for canon_name in known_order:
        bone = canon_to_bone.get(canon_frame_name(canon_name))
        if bone is None:
            continue
        marker = id(bone)
        if marker in seen_bones:
            continue
        ordered_bones.append(bone)
        seen_bones.add(marker)

    for bone in _depth_first_bone_order(root_bones or bones[:1], child_map):
        marker = id(bone)
        if marker in seen_bones:
            continue
        ordered_bones.append(bone)
        seen_bones.add(marker)

    if len(ordered_bones) != len(bones):
        for bone in bones:
            marker = id(bone)
            if marker in seen_bones:
                continue
            ordered_bones.append(bone)
            seen_bones.add(marker)

    used_ids: set[int] = set()
    next_synth_id = 0
    entries: List[Tuple[int, int, int]] = []

    for node_index, bone in enumerate(ordered_bones):
        export_name = _bone_name_for_export(bone)
        canon = canon_frame_name(export_name)
        children = child_map.get(str(getattr(bone, 'name', '')), []) or []

        mapped_bone_id = id_map.get(canon)
        bone_id = mapped_bone_id
        if bone_id is None:
            bone_id = _read_int_prop(bone, ('bleeds_hanim_bone_id', 'BoneID', 'bone_id', 'bleeds_bone_id', 'bleeds_boneid'))
        if bone_id is None:
            while next_synth_id in used_ids or next_synth_id == 0xFF:
                next_synth_id += 1
            bone_id = next_synth_id
            next_synth_id += 1
        bone_id = int(bone_id)
        if bone_id < 0:
            bone_id = 0
        if bone_id > 0xFF:
            bone_id = 0xFF
        used_ids.add(bone_id)

        bone_type = _read_int_prop(bone, ('BoneType', 'bone_type', 'bleeds_bone_type', 'bleeds_bonetype'))
        if bone_type is None:
            bone_type = type_map.get(canon)
        if bone_type is None:
            if len(children) == 0:
                bone_type = 1
            elif int(node_index) == 0 or len(children) > 1:
                bone_type = 2
            else:
                bone_type = 0
        bone_type = int(bone_type) & 0xFF

        entries.append((int(bone_id) & 0xFF, int(node_index) & 0xFF, bone_type))

    return entries

def _collect_ps2_ped_source_frame_node_map(
    atomic_meta: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    meta = dict(atomic_meta or {})
    template = _load_ped_source_template_blocks(meta)
    source_path = _resolve_ped_template_source_path(
        meta,
        export_path=str(meta.get("export_filepath") or ""),
    )
    if not source_path:
        source_path = str(template.get("source_path") or "").strip()

    frame_ptr = int(
        template.get("frame_offset", 0)
        or _ped_template_meta_u32(meta, "frame_ptr", "bleeds_mdl_frame_ptr")
        or 0
    )
    if not source_path or frame_ptr <= 0:
        return {}

    try:
        with open(source_path, "rb") as src_f:
            data = src_f.read()
    except Exception:
        return {}

    if frame_ptr <= 0 or frame_ptr >= len(data):
        return {}

    def _read_name_ptr(node_off: int) -> int:
        for rel in (0xA8, 0xA4):
            ptr_off = int(node_off) + rel
            if ptr_off + 4 > len(data):
                continue
            raw_val = struct.unpack_from("<I", data, ptr_off)[0]
            dec_val = _ped_template_decode_u32(raw_val)
            if 0 < dec_val < len(data):
                return int(dec_val)
        return 0

    helper_names = {
        canon_frame_name("scene_root"),
        canon_frame_name("male_base"),
        canon_frame_name("male_base01"),
        canon_frame_name("female_base"),
        canon_frame_name("female_base01"),
        canon_frame_name("pivots"),
    }

    nodes: List[Dict[str, Any]] = []
    by_offset: Dict[int, Dict[str, Any]] = {}
    by_canon: Dict[str, int] = {}
    seen: set[int] = set()

    def _walk(node_ptr: int, parent_ptr: int = 0) -> None:
        node_ptr = int(node_ptr or 0)
        if node_ptr <= 0 or node_ptr + 0xB0 > len(data) or node_ptr in seen:
            return
        seen.add(node_ptr)

        raw_tag = struct.unpack_from("<I", data, node_ptr)[0]
        tag = _ped_template_decode_u32(raw_tag)
        if tag not in (0x0180AA00, 0x0380AA00):
            return

        name_ptr = _read_name_ptr(node_ptr)
        raw_name = _read_cstring_from_blob(data, name_ptr) if name_ptr else ""
        canon = canon_frame_name(raw_name)

        actual_parent_ptr = 0
        child_ptr = 0
        sib_ptr = 0
        root_ptr = 0
        field_9c = 0
        field_a0 = 0
        field_a4 = 0
        if node_ptr + 0xA8 <= len(data):
            actual_parent_ptr = _ped_template_decode_u32(struct.unpack_from("<I", data, node_ptr + 0x04)[0])
            child_ptr = _ped_template_decode_u32(struct.unpack_from("<I", data, node_ptr + 0x90)[0])
            sib_ptr = _ped_template_decode_u32(struct.unpack_from("<I", data, node_ptr + 0x94)[0])
            root_ptr = _ped_template_decode_u32(struct.unpack_from("<I", data, node_ptr + 0x98)[0])
            field_9c = _ped_template_decode_u32(struct.unpack_from("<I", data, node_ptr + 0x9C)[0])
            field_a0 = _ped_template_decode_u32(struct.unpack_from("<I", data, node_ptr + 0xA0)[0])
            field_a4 = _ped_template_decode_u32(struct.unpack_from("<I", data, node_ptr + 0xA4)[0])

        info = {
            "offset": int(node_ptr),
            "tag": int(tag),
            "name": str(raw_name),
            "canon": str(canon),
            "parent_ptr": int(actual_parent_ptr or parent_ptr),
            "child_ptr": int(child_ptr),
            "sib_ptr": int(sib_ptr),
            "root_ptr": int(root_ptr),
            "field_9c": int(field_9c) & 0xFFFFFFFF,
            "field_a0": int(field_a0) & 0xFFFFFFFF,
            "field_a4": int(field_a4) & 0xFFFFFFFF,
        }
        nodes.append(info)
        by_offset[int(node_ptr)] = info
        if canon and canon not in by_canon:
            by_canon[canon] = int(node_ptr)

        if child_ptr:
            _walk(int(child_ptr), int(node_ptr))
        if sib_ptr:
            _walk(int(sib_ptr), int(parent_ptr))

    _walk(int(frame_ptr), 0)

    try:
        parent_chain_ptr = _ped_template_decode_u32(struct.unpack_from("<I", data, int(frame_ptr) + 0x04)[0])
        hop_guard = 0
        while parent_chain_ptr and parent_chain_ptr not in seen and hop_guard < 32:
            _walk(int(parent_chain_ptr), 0)
            parent_chain_ptr = _ped_template_decode_u32(struct.unpack_from("<I", data, int(parent_chain_ptr) + 0x04)[0])
            hop_guard += 1
    except Exception:
        pass

    first_regular_off = 0
    for node in nodes:
        canon = str(node.get("canon", ""))
        if canon in helper_names:
            continue
        if int(node.get("tag", 0)) == 0x0180AA00:
            first_regular_off = int(node.get("offset", 0))
            break

    return {
        "source_path": str(source_path),
        "frame_ptr": int(frame_ptr),
        "nodes": nodes,
        "by_offset": by_offset,
        "by_canon": by_canon,
        "first_regular_off": int(first_regular_off),
    }

def _choose_ps2_ped_hierarchy_anchor_offset(
    ped_frame_meta: Optional[Dict[str, Any]],
    *,
    preferred_canon_name: str = "",
) -> int:
    meta = dict(ped_frame_meta or {})
    node_name_to_off = meta.get("node_name_to_off") if isinstance(meta, dict) else {}
    if isinstance(node_name_to_off, dict):
        canon = canon_frame_name(preferred_canon_name)
        if canon:
            try:
                preferred = int(node_name_to_off.get(canon, 0) or 0)
            except Exception:
                preferred = 0
            if preferred > 0:
                return preferred

    for key in ("root_bone_off", "pelvis_off", "base_helper_off", "scene_root_off"):
        try:
            off = int(meta.get(key, 0) or 0)
        except Exception:
            off = 0
        if off > 0:
            return off

    node_offsets = meta.get("node_offsets") if isinstance(meta, dict) else None
    if isinstance(node_offsets, (list, tuple)):
        for raw_off in node_offsets:
            try:
                off = int(raw_off)
            except Exception:
                continue
            if off > 0:
                return off

    return 0

def _build_ps2_ped_hierarchy_header_info(
    *,
    atomic_meta: Optional[Dict[str, Any]],
    ped_frame_meta: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    default_anchor_off = _choose_ps2_ped_hierarchy_anchor_offset(ped_frame_meta)
    if default_anchor_off <= 0:

        default_anchor_off = 0x40

    meta = dict(atomic_meta or {})

    result: Dict[str, Any] = {
        "header_size": int(meta.get("hierarchy_header_size", 0x38) or 0x38),
        "header_bytes": b"",
        "hash_value": int(meta.get("hierarchy_hash_value", 0) or 0) & 0xFFFFFFFF,
        "tail_value": int(meta.get("hierarchy_tail_value", 0) or 0) & 0xFFFFFFFF,
        "entries_ptr_field_rel": 0x30,
        "node_ptr_field_rel": 0x34,
        "anchor_off": int(default_anchor_off),
    }

    try:
        raw_header_hex = str(meta.get("hierarchy_header_hex", "") or "").strip()
        if raw_header_hex:
            raw_header = bytes.fromhex(raw_header_hex)
            if len(raw_header) >= 0x38:
                requested_size = int(meta.get("hierarchy_header_size", 0x38) or 0x38)
                if requested_size < 0x38:
                    requested_size = 0x38
                requested_size = min(requested_size, len(raw_header), 0x80)
                result["header_size"] = int(requested_size)
                result["header_bytes"] = raw_header[:int(requested_size)]
                if len(raw_header) >= 0x2C:
                    result["hash_value"] = int(struct.unpack_from("<I", raw_header, 0x28)[0]) & 0xFFFFFFFF
                if len(raw_header) >= 0x30:
                    result["tail_value"] = int(struct.unpack_from("<I", raw_header, 0x2C)[0]) & 0xFFFFFFFF
    except Exception:
        pass
    template = _load_ped_source_template_blocks(meta)
    source_path = _resolve_ped_template_source_path(
        meta,
        export_path=str(meta.get("export_filepath") or ""),
    )
    if not source_path:
        source_path = str(template.get("source_path") or "").strip()

    hierarchy_off = int(template.get("hierarchy_offset", 0) or _ped_template_meta_u32(meta, "hierarchy_ptr", "bleeds_mdl_hierarchy_ptr") or 0)
    frame_ptr = int(template.get("frame_offset", 0) or _ped_template_meta_u32(meta, "frame_ptr", "bleeds_mdl_frame_ptr") or 0)
    if not source_path or hierarchy_off <= 0 or frame_ptr <= hierarchy_off:
        return result

    try:
        with open(source_path, "rb") as src_f:
            data = src_f.read()
    except Exception:
        return result

    if hierarchy_off + 0x30 > len(data) or frame_ptr > len(data):
        return result

    raw_entries_ptr = struct.unpack_from("<I", data, hierarchy_off + 0x30)[0]
    entries_ptr = _ped_template_decode_u32(raw_entries_ptr)

    header_size = 0x38
    max_size = max(0x38, min(int(frame_ptr - hierarchy_off), 0x80))
    if hierarchy_off < entries_ptr < frame_ptr:
        candidate_size = int(entries_ptr - hierarchy_off)
        if 0x38 <= candidate_size <= max_size:
            header_size = candidate_size

    header_size = max(0x38, min(header_size, int(frame_ptr - hierarchy_off)))
    if hierarchy_off + header_size > len(data):
        return result

    header_bytes = bytes(data[hierarchy_off:hierarchy_off + header_size])
    result["header_size"] = int(header_size)
    result["header_bytes"] = header_bytes

    if header_size >= 0x2C:
        result["hash_value"] = int(_ped_template_decode_u32(struct.unpack_from("<I", header_bytes, 0x28)[0])) & 0xFFFFFFFF
    if header_size >= 0x30:
        result["tail_value"] = int(_ped_template_decode_u32(struct.unpack_from("<I", header_bytes, 0x2C)[0])) & 0xFFFFFFFF

    source_nodes = _collect_ps2_ped_source_frame_node_map(meta)
    source_by_offset = source_nodes.get("by_offset") if isinstance(source_nodes, dict) else {}
    preferred_canon_name = ""

    if isinstance(source_by_offset, dict):
        for rel in range(0x30, header_size, 4):
            raw_val = struct.unpack_from("<I", header_bytes, rel)[0]
            val = int(_ped_template_decode_u32(raw_val)) & 0xFFFFFFFF

            if hierarchy_off < val < frame_ptr:
                result["entries_ptr_field_rel"] = int(rel)
                continue

            node_info = source_by_offset.get(val)
            if isinstance(node_info, dict):
                result["node_ptr_field_rel"] = int(rel)
                preferred_canon_name = str(node_info.get("canon", "") or "")
                break

    anchor_off = _choose_ps2_ped_hierarchy_anchor_offset(
        ped_frame_meta,
        preferred_canon_name=preferred_canon_name,
    )
    if anchor_off <= 0:
        anchor_off = _choose_ps2_ped_hierarchy_anchor_offset(ped_frame_meta)
    if anchor_off > 0:
        result["anchor_off"] = int(anchor_off)

    return result

def _append_ps2_ped_hierarchy_block_common(
    buf: bytearray,
    entries: List[Tuple[int, int, int]],
    pointer_fields: Optional[List[int]] = None,
    *,
    atomic_meta: Optional[Dict[str, Any]] = None,
    ped_frame_meta: Optional[Dict[str, Any]] = None,
) -> int:
    header_info = _build_ps2_ped_hierarchy_header_info(
        atomic_meta=atomic_meta,
        ped_frame_meta=ped_frame_meta,
    )

    canonical_max_entries = len(_ped_known_hanim_order(2))
    if len(entries) > canonical_max_entries:
        entries = list(entries[:canonical_max_entries])

    hier_off = len(buf)
    header_size = int(header_info.get("header_size", 0x38) or 0x38)
    if header_size < 0x38:
        header_size = 0x38

    raw_header = header_info.get("header_bytes")
    header = bytearray(b"\x00" * header_size)
    if isinstance(raw_header, (bytes, bytearray)) and len(raw_header) >= header_size:

        header[:header_size] = raw_header[:header_size]

    struct.pack_into("<I", header, 0x00, 0x3000)
    struct.pack_into("<I", header, 0x04, len(entries))
    reserved_end = min(0x28, header_size)
    if reserved_end > 0x08:
        header[0x08:reserved_end] = b"\x00" * (reserved_end - 0x08)

    if header_size >= 0x2C:
        struct.pack_into(
            "<I",
            header,
            0x28,
            int(header_info.get("hash_value", 0) or 0) & 0xFFFFFFFF,
        )
    if header_size >= 0x30:
        struct.pack_into(
            "<I",
            header,
            0x2C,
            int(header_info.get("tail_value", 0) or 0) & 0xFFFFFFFF,
        )
    if header_size >= 0x38:
        struct.pack_into("<I", header, 0x34, 0)

    entries_ptr_field_rel = int(header_info.get("entries_ptr_field_rel", 0x30) or 0x30)
    if entries_ptr_field_rel < 0 or entries_ptr_field_rel + 4 > header_size:
        entries_ptr_field_rel = 0x30 if header_size >= 0x34 else max(0, header_size - 8)

    entries_ptr = int(hier_off) + int(header_size)
    struct.pack_into("<I", header, int(entries_ptr_field_rel), entries_ptr & 0xFFFFFFFF)
    if pointer_fields is not None:
        pointer_fields.append(int(hier_off) + int(entries_ptr_field_rel))

    anchor_off = int(header_info.get("anchor_off", 0) or 0)
    node_ptr_field_rel = header_info.get("node_ptr_field_rel", 0x34)
    try:
        node_ptr_field_rel = int(node_ptr_field_rel)
    except Exception:
        node_ptr_field_rel = 0x34

    if anchor_off > 0:
        if node_ptr_field_rel < 0 or node_ptr_field_rel + 4 > header_size or node_ptr_field_rel == entries_ptr_field_rel:
            node_ptr_field_rel = max(0x34, header_size - 4) if header_size >= 0x38 else header_size - 4
        if node_ptr_field_rel + 4 <= header_size and node_ptr_field_rel >= 0:
            struct.pack_into("<I", header, int(node_ptr_field_rel), anchor_off & 0xFFFFFFFF)
            if pointer_fields is not None:
                pointer_fields.append(int(hier_off) + int(node_ptr_field_rel))

    buf.extend(header)

    for bone_id, node_index, bone_type in entries:
        packed = (
            (int(bone_id) & 0xFF)
            | ((int(node_index) & 0xFF) << 8)
            | ((int(bone_type) & 0xFF) << 16)
            | (0xAA << 24)
        )
        write_u32(buf, packed)
        write_u32(buf, 0)

    return hier_off

def _append_ps2_ped_hierarchy_block(
    buf: bytearray,
    pointer_fields: Optional[List[int]] = None,
    *,
    import_type_hint: Optional[int],
    armature_obj: Any = None,
    atomic_meta: Optional[Dict[str, Any]] = None,
    ped_frame_meta: Optional[Dict[str, Any]] = None,
) -> int:
    ped_import_type_hint = 2 if import_type_hint is None else import_type_hint
    entries = _collect_ps2_ped_hanim_entries(
        armature_obj=armature_obj,
        import_type_hint=ped_import_type_hint,
    )

    if not entries:
        imp = int(ped_import_type_hint) if ped_import_type_hint is not None else 2
        if imp in (0, 1):
            bone_ids = tuple(int(v) if int(v) < 256 else 0xFF for v in kamBoneID)
            bone_types = tuple(int(v) for v in kamBoneType)
            entries = [(int(bid) & 0xFF, int(i) & 0xFF, int(bone_types[i]) & 0xFF) for i, bid in enumerate(bone_ids)]
        else:
            id_map, type_map = _ped_ps2_runtime_hierarchy_maps(ped_import_type_hint)
            ordered_names = _ped_known_hanim_order(ped_import_type_hint)
            entries = []
            for i, raw_name in enumerate(ordered_names):
                canon = canon_frame_name(raw_name)
                entries.append((
                    int(id_map.get(canon, 0xFF)) & 0xFF,
                    int(i) & 0xFF,
                    int(type_map.get(canon, 0)) & 0xFF,
                ))

    return _append_ps2_ped_hierarchy_block_common(
        buf,
        entries,
        pointer_fields,
        atomic_meta=atomic_meta,
        ped_frame_meta=ped_frame_meta,
    )

def _read_cstring_from_blob(data: Any, offset: int) -> str:
    try:
        off = int(offset)
    except Exception:
        return ""
    if off <= 0 or off >= len(data):
        return ""
    end = data.find(b"\0", off)
    if end == -1:
        end = len(data)
    try:
        return data[off:end].decode("latin1", "ignore")
    except Exception:
        return ""

def _collect_ps2_ped_hanim_entries_from_frames_blob(
    data: Any,
    *,
    frames_offset: int,
    import_type_hint: Optional[int] = None,
) -> List[Tuple[int, int, int]]:
    try:
        start = int(frames_offset)
    except Exception:
        return []

    helper_names = {
        canon_frame_name("scene_root"),
        canon_frame_name("male_base"),
        canon_frame_name("male_base01"),
        canon_frame_name("female_base"),
        canon_frame_name("female_base01"),
        canon_frame_name("pivots"),
    }

    def read_node(node_off: int) -> Optional[Dict[str, Any]]:
        try:
            off = int(node_off)
        except Exception:
            return None
        if off < 0 or off + 0xB0 > len(data):
            return None

        tag = struct.unpack_from("<I", data, off)[0]
        if tag not in (0x0180AA00, 0x0380AA00):
            return None

        name_ptr = struct.unpack_from("<I", data, off + 0xA8)[0]
        if name_ptr == 0:
            name_ptr = struct.unpack_from("<I", data, off + 0xA4)[0]
        raw_name = _read_cstring_from_blob(data, name_ptr)
        canon = canon_frame_name(raw_name)

        return {
            "offset": int(off),
            "tag": int(tag),
            "name": str(raw_name),
            "canon": canon,
            "child_ptr": struct.unpack_from("<I", data, off + 0x90)[0],
            "sib_ptr": struct.unpack_from("<I", data, off + 0x94)[0],
            "root_ptr": struct.unpack_from("<I", data, off + 0x98)[0],
        }

    raw_nodes: List[Dict[str, Any]] = []
    seen_offsets: set[int] = set()

    def append_graph_chain(first_off: int) -> None:
        queue: List[int] = [int(first_off)]
        while queue:
            current = int(queue.pop(0))
            if current in seen_offsets:
                continue

            node = read_node(current)
            if node is None:
                continue

            seen_offsets.add(current)
            raw_nodes.append(node)

            child_ptr = int(node.get("child_ptr", 0)) & 0xFFFFFFFF
            if child_ptr and child_ptr not in seen_offsets:
                queue.append(child_ptr)

            sib_ptr = int(node.get("sib_ptr", 0)) & 0xFFFFFFFF
            if sib_ptr and sib_ptr not in seen_offsets:
                queue.append(sib_ptr)

    start_node = read_node(start)
    if start_node is not None:
        append_graph_chain(start)

        first_child = int(start_node.get("child_ptr", 0)) & 0xFFFFFFFF
        if first_child and first_child not in seen_offsets:
            append_graph_chain(first_child)

    if not raw_nodes:
        off = start
        while off + 0xB0 <= len(data):
            node = read_node(off)
            if node is None:
                break
            if int(node["offset"]) in seen_offsets:
                break
            seen_offsets.add(int(node["offset"]))
            raw_nodes.append(node)
            off += 0xB0

    if not raw_nodes:
        return []

    raw_nodes.sort(key=lambda node: int(node.get("offset", 0)))

    filtered_nodes: List[Dict[str, Any]] = []
    for node in raw_nodes:
        canon = str(node.get("canon", ""))
        if not canon or canon in helper_names:
            continue
        filtered_nodes.append(node)

    if not filtered_nodes:
        return []

    filtered_offset_set = {int(n["offset"]) for n in filtered_nodes}
    id_map, type_map = _ped_ps2_runtime_hierarchy_maps(import_type_hint)
    known_order = [canon_frame_name(name) for name in _ped_known_hanim_order(import_type_hint)]

    by_canon: Dict[str, Dict[str, Any]] = {}
    for node in filtered_nodes:
        canon = str(node.get("canon", ""))
        if canon and canon not in by_canon and canon in id_map:
            by_canon[canon] = node

    ordered_nodes: List[Dict[str, Any]] = []
    for canon in known_order:
        node = by_canon.get(canon)
        if node is not None:
            ordered_nodes.append(node)

    if not ordered_nodes:
        return []

    ordered_offset_set = {int(n["offset"]) for n in ordered_nodes}
    entries: List[Tuple[int, int, int]] = []
    for node_index, node in enumerate(ordered_nodes):
        canon = str(node.get("canon", ""))
        bone_id = int(id_map.get(canon, 0xFF)) & 0xFF

        bone_type = type_map.get(canon)
        if bone_type is None:
            children: List[int] = []
            child_ptr = int(node.get("child_ptr", 0)) & 0xFFFFFFFF
            hop_guard = 0
            while child_ptr and child_ptr in ordered_offset_set and hop_guard < 512:
                children.append(child_ptr)
                child_record_sib = struct.unpack_from("<I", data, int(child_ptr) + 0x94)[0]
                child_ptr = int(child_record_sib) & 0xFFFFFFFF
                hop_guard += 1

            if len(children) == 0:
                bone_type = 1
            elif int(node_index) == 0 or len(children) > 1:
                bone_type = 2
            else:
                bone_type = 0

        entries.append((int(bone_id) & 0xFF, int(node_index) & 0xFF, int(bone_type) & 0xFF))

    return entries

def _append_ps2_ped_hierarchy_block_from_frames(
    buf: bytearray,
    pointer_fields: List[int],
    *,
    frames_offset: int,
    import_type_hint: Optional[int] = None,
    armature_obj: Any = None,
    atomic_meta: Optional[Dict[str, Any]] = None,
    ped_frame_meta: Optional[Dict[str, Any]] = None,
) -> int:
    ped_import_type_hint = 2 if import_type_hint is None else import_type_hint
    entries = _collect_ps2_ped_hanim_entries_from_frames_blob(
        buf,
        frames_offset=frames_offset,
        import_type_hint=ped_import_type_hint,
    )
    if not entries:
        return _append_ps2_ped_hierarchy_block(
            buf,
            import_type_hint=ped_import_type_hint,
            armature_obj=armature_obj,
            atomic_meta=atomic_meta,
            ped_frame_meta=ped_frame_meta,
        )

    return _append_ps2_ped_hierarchy_block_common(
        buf,
        entries,
        pointer_fields,
        atomic_meta=atomic_meta,
        ped_frame_meta=ped_frame_meta,
    )

def _append_ps2_ped_geometry_bounds_header(
    buf: bytearray,
    pointer_fields: List[int],
    *,
    bounds_float_ptr: int,
) -> int:
    align_buffer(buf, 4)
    header_off = len(buf)

    write_u32(buf, 0x19)
    write_u32(buf, 0)
    write_u32(buf, 0)

    bounds_ptr_field = len(buf)
    write_u32(buf, int(bounds_float_ptr) & 0xFFFFFFFF)
    pointer_fields.append(int(bounds_ptr_field))

    while len(buf) < header_off + 0x3C:
        write_u32(buf, 0)

    return header_off
def _append_ps2_ped_struct_or_flags_bounds(
    buf: bytearray,
    pointer_fields: List[int],
    *,
    scale_pos: ScalePos,
) -> Tuple[int, int]:
    bounds_off = len(buf)

    sx, sy, sz = (float(scale_pos.scale[0]), float(scale_pos.scale[1]), float(scale_pos.scale[2]))
    px, py, pz = (float(scale_pos.pos[0]), float(scale_pos.pos[1]), float(scale_pos.pos[2]))

    minx, miny, minz = (px - sx, py - sy, pz - sz)
    maxx, maxy, maxz = (px + sx, py + sy, pz + sz)

    cx, cy, cz = (px, py, pz)
    radius = math.sqrt((maxx - cx) ** 2 + (maxy - cy) ** 2 + (maxz - cz) ** 2)

    buf += struct.pack("<3I", 0, 0, 0)
    buf += struct.pack("<f", 2.0)

    buf += struct.pack("<4f", minx, miny, minz, 0.0)
    buf += struct.pack("<4f", maxx, maxy, maxz, 0.0)

    buf += struct.pack("<I", 0)
    buf += struct.pack("<I", 0x0A)

    radius_ptr_field = len(buf)
    write_u32(buf, 0)
    pointer_fields.append(int(radius_ptr_field))

    write_u32(buf, 0)

    while (len(buf) & 0xF) != 0:
        buf.append(0)

    radius_off = len(buf)
    buf += struct.pack("<3I", 0, 0, 0)
    buf += struct.pack("<f", float(radius))

    while (len(buf) & 0xF) != 0:
        buf.append(0)

    struct.pack_into("<I", buf, radius_ptr_field, int(radius_off) & 0xFFFFFFFF)

    return bounds_off, radius_off

def _unused_imported_ps2_ped_source_topology():
    return [
        ("root", 0x40, 0xF0, 0xDC30, 0x00000000, 0xF0),
        ("head", 0x1C0, 0xE520, 0x0270, 0x00000000, 0xF0),
        ("jaw", 0x270, 0x01C0, 0x00000000, 0x00000000, 0xF0),
        ("bip01_l_clavicle", 0x320, 0xE520, 0x03D0, 0x01C0, 0xF0),
        ("l_upperarm", 0x3D0, 0x0320, 0x0480, 0x00000000, 0xF0),
        ("l_forearm", 0x480, 0x03D0, 0x0530, 0x00000000, 0xF0),
        ("l_hand", 0x530, 0x0480, 0x05E0, 0x00000000, 0xF0),
        ("l_finger", 0x5E0, 0x0530, 0x00000000, 0x00000000, 0xF0),
        ("bip01_r_clavicle", 0x690, 0xE520, 0x0740, 0x0320, 0xF0),
        ("r_upperarm", 0x740, 0x0690, 0x07F0, 0x00000000, 0xF0),
        ("r_forearm", 0x7F0, 0x0740, 0x08A0, 0x00000000, 0xF0),
        ("r_hand", 0x8A0, 0x07F0, 0x0950, 0x00000000, 0xF0),
        ("r_finger", 0x950, 0x08A0, 0x00000000, 0x00000000, 0xF0),
        ("l_thigh", 0xA00, 0xE3C0, 0x0AB0, 0xE470, 0xF0),
        ("l_calf", 0xAB0, 0x0A00, 0xDCE0, 0x00000000, 0xF0),
        ("pelvis", 0xDC30, 0x0040, 0xE3C0, 0x00000000, 0xF0),
        ("l_foot", 0xDCE0, 0x0AB0, 0xDD90, 0x00000000, 0xF0),
        ("l_toe0", 0xDD90, 0xDCE0, 0x00000000, 0x00000000, 0xF0),
        ("r_thigh", 0xDE40, 0xE3C0, 0xDEF0, 0x0A00, 0xF0),
        ("r_calf", 0xDEF0, 0xDE40, 0xDFA0, 0x00000000, 0xF0),
        ("r_foot", 0xDFA0, 0xDEF0, 0xE050, 0x00000000, 0xF0),
        ("r_toe0", 0xE050, 0xDFA0, 0x00000000, 0x00000000, 0xF0),
        ("pivots", 0xE200, 0x00F0, 0x00000000, 0x0040, 0xF0),
        ("spine", 0xE3C0, 0xDC30, 0xDE40, 0x00000000, 0xF0),
        ("spine1", 0xE470, 0xE3C0, 0xE520, 0x00000000, 0xF0),
        ("neck", 0xE520, 0xE470, 0x0690, 0x00000000, 0xF0),
    ]

def _apply_imported_ps2_ped_source_layout(
    filepath: str,
    atomic_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {}

def _log_hex_words(data: bytes, start_offset: int = 0, word_size: int = 4, words_per_line: int = 4) -> str:
    if not isinstance(data, (bytes, bytearray)) or not data:
        return ""

    lines: List[str] = []
    index = 0
    total = len(data)
    while index < total:
        line_bytes = data[index:index + (word_size * words_per_line)]
        words: List[str] = []
        for pos in range(0, len(line_bytes), word_size):
            chunk = line_bytes[pos:pos + word_size]
            words.append(chunk.hex(" ").upper())
        lines.append(f"  0x{start_offset + index:08X}: " + " | ".join(words))
        index += word_size * words_per_line
    return "\n".join(lines)

def _log_read_u32(data: bytes, offset: int) -> int:
    try:
        off = int(offset)
    except Exception:
        return 0
    if off < 0 or off + 4 > len(data):
        return 0
    return struct.unpack_from('<I', data, off)[0]

def _log_read_i16(data: bytes, offset: int) -> int:
    try:
        off = int(offset)
    except Exception:
        return 0
    if off < 0 or off + 2 > len(data):
        return 0
    return struct.unpack_from('<h', data, off)[0]

def _log_read_u16(data: bytes, offset: int) -> int:
    try:
        off = int(offset)
    except Exception:
        return 0
    if off < 0 or off + 2 > len(data):
        return 0
    return struct.unpack_from('<H', data, off)[0]

def _log_read_f32(data: bytes, offset: int) -> float:
    try:
        off = int(offset)
    except Exception:
        return 0.0
    if off < 0 or off + 4 > len(data):
        return 0.0
    return struct.unpack_from('<f', data, off)[0]

def _log_read_cstring(data: bytes, offset: int) -> str:
    try:
        off = int(offset)
    except Exception:
        return ""
    if off <= 0 or off >= len(data):
        return ""
    end = data.find(b'\x00', off)
    if end < 0:
        end = len(data)
    try:
        return data[off:end].decode('latin1', 'ignore')
    except Exception:
        return ""

def _ped_frame_name_ptr_for_log(data: bytes, node_off: int) -> int:
    for rel in (0xA8, 0xA4):
        ptr = _log_read_u32(data, int(node_off) + rel)
        if 0 < ptr < len(data):
            return int(ptr)
    return 0

def _parse_ped_frame_tree_for_log(data: bytes, frame_root_off: int) -> Dict[str, Any]:
    nodes_tree: List[Dict[str, Any]] = []
    nodes_by_offset: Dict[int, Dict[str, Any]] = {}
    seen: set[int] = set()

    def walk(node_off: int, parent_hint: int = 0) -> None:
        off = int(node_off or 0)
        if off <= 0 or off + 0xB0 > len(data) or off in seen:
            return
        tag = _log_read_u32(data, off)
        if tag not in (0x0180AA00, 0x0380AA00):
            return
        seen.add(off)

        name_ptr = _ped_frame_name_ptr_for_log(data, off)
        name = _log_read_cstring(data, name_ptr)
        info = {
            "offset": int(off),
            "tag": int(tag),
            "parent_ptr": int(_log_read_u32(data, off + 0x04) or parent_hint),
            "first_atomic_ptr": int(_log_read_u32(data, off + 0x08)),
            "last_atomic_ptr": int(_log_read_u32(data, off + 0x0C)),
            "child_ptr": int(_log_read_u32(data, off + 0x90)),
            "sib_ptr": int(_log_read_u32(data, off + 0x94)),
            "root_ptr": int(_log_read_u32(data, off + 0x98)),
            "bone_id": int(_log_read_u32(data, off + 0x9C)),
            "bone_params_ptr": int(_log_read_u32(data, off + 0xA0)),
            "name_ptr": int(name_ptr),
            "name": str(name),
            "node_info_id": int(_log_read_u32(data, off + 0xA8)),
        }
        nodes_tree.append(info)
        nodes_by_offset[int(off)] = info

        child = int(info["child_ptr"])
        if child:
            walk(child, off)
        sib = int(info["sib_ptr"])
        if sib:
            walk(sib, parent_hint)

    walk(int(frame_root_off or 0), 0)

    nodes_offset_order = sorted(nodes_tree, key=lambda item: int(item.get("offset", 0)))

    helper_names = {
        canon_frame_name("scene_root"),
        canon_frame_name("male_base"),
        canon_frame_name("female_base"),
        canon_frame_name("pivots"),
    }
    filtered_offset_order: List[Dict[str, Any]] = []
    for node in nodes_offset_order:
        canon = canon_frame_name(str(node.get("name", "")))
        if canon in helper_names:
            continue
        filtered_offset_order.append(node)

    return {
        "tree_order": nodes_tree,
        "offset_order": nodes_offset_order,
        "filtered_offset_order": filtered_offset_order,
        "by_offset": nodes_by_offset,
    }

def _parse_ped_hierarchy_table_for_log(data: bytes, hierarchy_off: int, frame_log: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "offset": int(hierarchy_off or 0),
        "entry_count": 0,
        "entries_ptr": 0,
        "anchor_ptr": 0,
        "header_size": 0,
        "entries": [],
    }
    off = int(hierarchy_off or 0)
    if off <= 0 or off + 0x38 > len(data):
        return result

    entry_count = _log_read_u32(data, off + 0x04)
    entries_ptr = _log_read_u32(data, off + 0x30)
    anchor_ptr = _log_read_u32(data, off + 0x34)
    header_size = 0x38
    if entries_ptr > off and entries_ptr <= len(data):
        candidate_size = int(entries_ptr - off)
        if 0x38 <= candidate_size <= 0x100:
            header_size = candidate_size

    frame_nodes = []
    if isinstance(frame_log, dict):
        frame_nodes = list(frame_log.get("filtered_offset_order") or [])

    entries: List[Dict[str, Any]] = []
    safe_count = int(entry_count)
    if safe_count < 0:
        safe_count = 0
    if safe_count > 2048:
        safe_count = 2048

    if entries_ptr > 0:
        for index in range(safe_count):
            entry_off = int(entries_ptr) + (index * 8)
            if entry_off + 8 > len(data):
                break
            packed = _log_read_u32(data, entry_off)
            zero_dword = _log_read_u32(data, entry_off + 4)
            bone_id = packed & 0xFF
            node_index = (packed >> 8) & 0xFF
            bone_type = (packed >> 16) & 0xFF
            flag_byte = (packed >> 24) & 0xFF
            frame_name = ""
            frame_off = 0
            if 0 <= node_index < len(frame_nodes):
                frame_name = str(frame_nodes[node_index].get("name", ""))
                frame_off = int(frame_nodes[node_index].get("offset", 0))
            entries.append({
                "offset": int(entry_off),
                "packed": int(packed),
                "zero": int(zero_dword),
                "bone_id": int(bone_id),
                "node_index": int(node_index),
                "bone_type": int(bone_type),
                "flag_byte": int(flag_byte),
                "frame_name": str(frame_name),
                "frame_offset": int(frame_off),
            })

    result.update({
        "entry_count": int(entry_count),
        "entries_ptr": int(entries_ptr),
        "anchor_ptr": int(anchor_ptr),
        "header_size": int(header_size),
        "entries": entries,
    })
    return result

def _ped_pointer_field_meaning(
    field_off: int,
    *,
    data: Optional[bytes] = None,
    clump_off: int,
    atomic_off: int,
    hierarchy_off: int,
    frame_log: Optional[Dict[str, Any]] = None,
) -> str:
    field_off = int(field_off)
    known = {
        0x0C: "MDL header.local_numTable",
        0x10: "MDL header.global_numTable",
        0x18: "MDL header.ptr2_before_tex / mirrors local table",
        0x20: "MDL header.struct_or_flags pointer",
        0x24: "MDL header.top_level_ptr / top-level clump/node pointer",
        0x28: "MDL header.extra_ptr0 / material descriptor pointer 0",
        0x2C: "MDL header.extra_ptr1 / material descriptor pointer 1",
        0x30: "MDL header.extra_ptr2 / material descriptor pointer 2",
        0x44: "Header RslNode1.next pointer",
        0x48: "Header RslNode1.self pointer A",
        0x4C: "Header RslNode1.self pointer B",
        0xF8: "Fixed RslNode2.self pointer A",
        0xFC: "Fixed RslNode2.self pointer B",
    }
    if field_off in known:
        return known[field_off]

    if isinstance(frame_log, dict):
        for node in list(frame_log.get("offset_order") or []):
            node_off = int(node.get("offset", 0))
            rel = field_off - node_off
            frame_name = str(node.get("name", "")).strip() or f"frame_0x{node_off:X}"
            frame_known = {
                0x04: "parent pointer",
                0x08: "frame-cycle/self pointer A",
                0x0C: "frame-cycle/self pointer B",
                0x90: "child pointer",
                0x94: "sibling pointer",
                0x98: "root/helper pointer",
                0xA4: "bone-params pointer / alt-name pointer",
                0xA8: "name string pointer",
            }
            if rel in frame_known:
                return f"Frame '{frame_name}' +0x{rel:02X} {frame_known[rel]}"

    if clump_off > 0:
        rel = field_off - int(clump_off)
        clump_known = {
            0x04: "Top-level clump/node +0x04 helper/root pointer",
            0x08: "Top-level clump/node +0x08 first atomic-cycle pointer",
            0x0C: "Top-level clump/node +0x0C last atomic-cycle pointer",
        }
        if rel in clump_known:
            return clump_known[rel]

    if atomic_off > 0:
        rel = field_off - int(atomic_off)
        atomic_known = {
            0x04: "Atomic +0x04 parent/helper pointer",
            0x08: "Atomic +0x08 frame-cycle next pointer",
            0x0C: "Atomic +0x0C frame-cycle prev pointer",
            0x14: "Atomic +0x14 geometry header pointer",
            0x18: "Atomic +0x18 owning clump pointer",
            0x1C: "Atomic +0x1C clump-cycle next pointer",
            0x20: "Atomic +0x20 clump-cycle prev pointer",
            0x2C: "Atomic +0x2C hierarchy header pointer",
        }
        if rel in atomic_known:
            return atomic_known[rel]

    if hierarchy_off > 0:
        rel = field_off - int(hierarchy_off)
        if rel == 0x30:
            return "Hierarchy header +0x30 packed-entry-table pointer"
        if rel == 0x34:
            return "Hierarchy header +0x34 anchor/root frame pointer"

    if isinstance(data, (bytes, bytearray)):
        geom_off = int(_log_read_u32(data, atomic_off + 0x14) if atomic_off > 0 else 0)
        if geom_off > 0:
            rel = field_off - geom_off
            if rel == 0x0C:
                return "Geometry header +0x0C material-descriptor-table pointer"
            if rel == 0x18:
                return "Geometry header +0x18 bounds-header pointer"

            mat_table_off = int(_log_read_u32(data, geom_off + 0x0C)) if geom_off + 0x10 <= len(data) else 0
            if mat_table_off > 0 and field_off >= mat_table_off and field_off < mat_table_off + 0x40 and (field_off - mat_table_off) % 4 == 0:
                index = (field_off - mat_table_off) // 4
                return f"material-descriptor pointer table entry[{index}]"

        collision_off = int(_log_read_u32(data, 0x20)) if len(data) >= 0x24 else 0
        if collision_off > 0 and field_off == collision_off + 0x38:
            return "embedded collision/bounds block +0x38 spheres-array pointer"

        if field_off >= 0:
            target = _log_read_u32(data, field_off)
            if target > 0 and target < len(data):
                name = _log_read_cstring(data, target)
                if name and name.lower().startswith('hfost_'):
                    return f'material descriptor "{name}" +0x00 name string pointer'

        bounds_target = int(_log_read_u32(data, field_off))
        if bounds_target > 0 and bounds_target < len(data):
            maybe_geom_off = int(_log_read_u32(data, atomic_off + 0x14) if atomic_off > 0 else 0)
            if maybe_geom_off > 0 and field_off != maybe_geom_off + 0x18:
                geom_bounds = int(_log_read_u32(data, maybe_geom_off + 0x18)) if maybe_geom_off + 0x1C <= len(data) else 0
                if geom_bounds > 0 and field_off == geom_bounds + 0x0C:
                    return "bounds header +0x0C first-bounds-data pointer"

    return "unknown pointer field"

def _prop_pointer_field_meaning(field_off: int) -> str:
    known = {
        0x20: "MDL header.ptr_after_alloc / Atomic1 pointer",
        0x38: "Atomic2.prev_entry",
        0x3C: "Atomic2.next_entry",
        0xC8: "Identity block trailer pointer",
        0xE4: "Atomic1.prev_vtable / Atomic2 pointer",
        0xE8: "Atomic1.prev_entry",
        0xEC: "Atomic1.next_entry",
        0xF4: "Atomic1.geometry_ptr",
        0x114: "Atomic1.texture_ptr",
        0x120: "Texture list.self_plus_4",
        0x128: "Texture list.string0_ptr",
        0x134: "Texture list.ptr_field_atomic1_texture_ptr",
        0x138: "Texture list.ptr_field_string1_ptr",
        0x13C: "Texture list.string1_ptr",
        0x15C: "Geometry preamble.texture_list_pointer_field_ptr",
        0x104: "Retail extra pointer slot",
    }
    return known.get(int(field_off), "unknown pointer field")

def _append_ped_import_style_export_fields(
    lines: List[str],
    data: bytes,
    *,
    filepath: str,
    clump_off: int,
    atomic_off: int,
    geom_off: int,
    hierarchy_off: int,
) -> None:
    lines.append("Import-style exported field view")
    lines.append(f"✔ Exported: {filepath}")
    lines.append("✔ Ped/actor or prop MDL detected.")

    ptr_after_alloc = _log_read_u32(data, 0x20)
    local_reloc = _log_read_u32(data, 0x0C)
    global_reloc = _log_read_u32(data, 0x10)
    entry_count = _log_read_u32(data, 0x14)
    ptr2_before_tex = _log_read_u32(data, 0x18)
    alloc_mem = _log_read_u32(data, 0x1C)
    top_level = _log_read_u32(data, 0x24)

    lines.append(f"Pointer after allocMem (offset 0x20): 0x{ptr_after_alloc:X}")
    lines.append(f"File Size: 0x{_log_read_u32(data, 0x08):X}")
    lines.append(f"Local Realloc Table: 0x{local_reloc:X}, Global Realloc Table: 0x{global_reloc:X}")
    lines.append(f"Number of entries: 0x{entry_count:X}")
    lines.append(f"Ptr2BeforeTexNameList: 0x{ptr2_before_tex:X}")
    lines.append(f"Allocated memory: 0x{alloc_mem:X}")
    lines.append(f"Top-level ptr or magic value: 0x{top_level:X}")

    if clump_off > 0:
        lines.append("Section Type: 7, Import Type: 2")
        lines.append("✔ Detected Section Type: 7 (Clump)")
        lines.append(f"Clump section begins at: 0x{clump_off:X}")
        lines.append(f"clump.root_frame: 0x{_log_read_u32(data, clump_off + 0x04):X}")
        lines.append(f"clump.first_atomic: 0x{_log_read_u32(data, clump_off + 0x08):X}")
        lines.append(f"clump.last_atomic: 0x{_log_read_u32(data, clump_off + 0x0C):X}")

    if atomic_off > 0:
        lines.append("✔ Detected Section Type: 2 (Atomic)")
        lines.append(f"Atomic section begins at: 0x{atomic_off:X}")
        lines.append("Atomic fields by fixed RslNode3 offsets:")
        lines.append(f"  section_id:     0x{_log_read_u32(data, atomic_off + 0x00):X}")
        lines.append(f"  frame_ptr:      0x{_log_read_u32(data, atomic_off + 0x04):X}")
        lines.append(f"  previous link:  0x{_log_read_u32(data, atomic_off + 0x08):X}")
        lines.append(f"  previous link2: 0x{_log_read_u32(data, atomic_off + 0x0C):X}")
        lines.append(f"  pad AAAA:       0x{_log_read_u32(data, atomic_off + 0x10):X}")
        lines.append(f"  geom_ptr:       0x{_log_read_u32(data, atomic_off + 0x14):X}")
        lines.append(f"  clump_ptr:      0x{_log_read_u32(data, atomic_off + 0x18):X}")
        lines.append(f"  link_ptr:       0x{_log_read_u32(data, atomic_off + 0x1C):X}")
        lines.append(f"  link_ptr2:      0x{_log_read_u32(data, atomic_off + 0x20):X}")
        lines.append(f"  render_cb:      0x{_log_read_u32(data, atomic_off + 0x24):X}")
        packed_model_vis = _log_read_u32(data, atomic_off + 0x28)
        model_info_id = packed_model_vis & 0xFFFF
        if model_info_id >= 0x8000:
            model_info_id -= 0x10000
        vis_id_flag = (packed_model_vis >> 16) & 0xFFFF
        lines.append(f"  model_info_id:  {model_info_id}")
        lines.append(f"  vis_id_flag:    0x{vis_id_flag:X}")
        lines.append(f"  hierarchy_ptr:  0x{_log_read_u32(data, atomic_off + 0x2C):X}")
        lines.append(f"  atomic_tail:    0x{_log_read_u32(data, atomic_off + 0x30):X}")

    if hierarchy_off > 0:
        hier_tag = _log_read_u32(data, hierarchy_off + 0x00)
        hier_count = _log_read_u32(data, hierarchy_off + 0x04)
        lines.append(f"Hierarchy header: 0x{hierarchy_off:X}")
        lines.append(f"  hierarchy_tag:   0x{hier_tag:X}")
        lines.append(f"  hierarchy_count: {hier_count}")
        lines.append(f"  entries_ptr:     0x{_log_read_u32(data, hierarchy_off + 0x30):X}")
        lines.append(f"  anchor_frame:    0x{_log_read_u32(data, hierarchy_off + 0x34):X}")
        if hier_tag != 0x3000:
            lines.append("  ⚠ hierarchy_tag is not 0x3000; the game will not read this as a valid compact hierarchy header.")

    if geom_off > 0:
        material_list_ptr = _log_read_u32(data, geom_off + 0x0C)
        material_count = _log_read_u32(data, geom_off + 0x10)
        aux_ptr = _log_read_u32(data, geom_off + 0x18)
        global_off = int(geom_off) + 0x20
        packed = _log_read_u32(data, global_off + 0x10)
        part_count = (packed >> 20) & 0xFFF
        geom_size = packed & 0xFFFFF
        flags = _log_read_u32(data, global_off + 0x14)
        total_verts = _log_read_u16(data, global_off + 0x18)
        first_tri_rel = _log_read_u16(data, global_off + 0x1A)
        dma_start = global_off + first_tri_rel if first_tri_rel else 0

        lines.append("Detected Section Type: 3 (Geometry, PS2)")
        lines.append(f"🧵 Material List Ptr: 0x{material_list_ptr:X}")
        lines.append(f"🎨 Material Count: {material_count}")
        lines.append(f"aux/header ptr: 0x{aux_ptr:X}")
        lines.append(f"global geometry header: 0x{global_off:X}")
        lines.append(f"packed_size_and_part_count: 0x{packed:08X} (parts={part_count}, geom_size=0x{geom_size:X})")
        lines.append(f"vertex_section_flags: 0x{flags:X}")
        lines.append(f"total_vertex_count: {total_verts}")
        lines.append(f"firstTriStripOff: 0x{first_tri_rel:X}")
        lines.append(f"geoStart: 0x{dma_start:X}")
        lines.append(f"✔ xScale: {_log_read_f32(data, global_off + 0x28)}, yScale: {_log_read_f32(data, global_off + 0x2C)}, zScale: {_log_read_f32(data, global_off + 0x30)}")
        lines.append(f"✔ TranslationFactor: ({_log_read_f32(data, global_off + 0x34)}, {_log_read_f32(data, global_off + 0x38)}, {_log_read_f32(data, global_off + 0x3C)})")

        part_offsets: List[int] = []
        part_materials: List[int] = []
        part_table = global_off + 0x40
        safe_part_count = min(int(part_count), 256)
        for part_index in range(safe_part_count):
            part_off = part_table + (part_index * 0x30)
            if part_off + 0x30 > len(data):
                break
            strip_rel = _log_read_u32(data, part_off + 0x1C)
            strip_count = _log_read_u16(data, part_off + 0x20)
            tex_id = _log_read_u16(data, part_off + 0x22)
            target = dma_start + strip_rel if dma_start else 0
            tag = _log_read_u32(data, target) if 0 <= target + 4 <= len(data) else 0
            qwc = tag & 0xFFFF
            part_offsets.append(int(strip_rel))
            part_materials.append(int(tex_id))
            lines.append(
                f"  part[{part_index:02d}] entry=0x{part_off:X} rel_off=0x{strip_rel:X} abs=0x{target:X} "
                f"stripVerts={strip_count} tex_id={tex_id} dmaTag=0x{tag:08X} qwc={qwc}"
            )
        lines.append(f"✔ partOffsets: {part_offsets}")
        lines.append(f"✔ partMaterials: {part_materials}")

    lines.append("")

def _write_ped_export_log(filepath: str, data: bytes, export_context: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    header_bytes = data[:0x34]
    source_path = str((export_context or {}).get("roundtrip_source_path", "") or "")
    if not source_path:
        source_path = str((export_context or {}).get("source_path", "") or "")
    if not source_path:
        source_path = str((export_context or {}).get("atomic_meta", {}).get("source_filepath", "") or "")
    source_roundtrip_mode = bool((export_context or {}).get("source_roundtrip_mode"))
    imported_export_mode = str((export_context or {}).get("imported_export_mode", "") or "").strip()
    source_relocation_applied = bool((export_context or {}).get("source_relocation_applied"))
    source_relocation_pointer_count = int((export_context or {}).get("source_relocation_pointer_count", 0) or 0)
    source_relocation_root_offset = int((export_context or {}).get("source_relocation_root_offset", 0) or 0)

    lines.append(f"Exported file: {filepath}")
    if source_path:
        lines.append(f"Imported source MDL: {source_path}")
    if imported_export_mode:
        lines.append(f"Imported export mode: {imported_export_mode}")
    if source_roundtrip_mode:
        lines.append("Round-trip mode: final export bytes were copied from the imported source MDL after relocation-table validation")
    elif source_relocation_applied:
        lines.append(f"Source relocation roster applied: {source_relocation_pointer_count} entries, root_offset=0x{source_relocation_root_offset:08X}")
    lines.append("MDL kind: PS2 PED / clump-based Stories export")
    lines.append("")

    lines.append("MDL header bytes (0x00-0x33)")
    lines.append(_log_hex_words(header_bytes, 0x00))
    lines.append("")

    header_fields = [
        (0x00, 4, "signature", "container signature, expected 'ldm\\0'"),
        (0x04, 4, "shrink/reserved", "container reserved field"),
        (0x08, 4, "file_len", "logical MDL size before sector padding"),
        (0x0C, 4, "local_numTable", "local relocation table header / root pointer area"),
        (0x10, 4, "global_numTable", "global relocation pointer list"),
        (0x14, 4, "numEntries", "number of relocation pointer fields"),
        (0x18, 4, "ptr2_before_tex", "mirrors local table in PED exports"),
        (0x1C, 4, "allocMem", "engine allocation field"),
        (0x20, 4, "struct_or_flags", "PS2 PED header pointer slot"),
        (0x24, 4, "top_level_ptr", "top-level Clump pointer"),
        (0x28, 4, "extra_ptr0", "extra header pointer 0 / source-driven material helper"),
        (0x2C, 4, "extra_ptr1", "extra header pointer 1 / source-driven material helper"),
        (0x30, 4, "extra_ptr2", "extra header pointer 2 / source-driven material helper"),
    ]
    lines.append("MDL header fields")
    for off, size, name, meaning in header_fields:
        value = _log_read_u32(data, off)
        lines.append(f"  0x{off:02X} {name:<18} = 0x{value:08X} ({value}) | {meaning}")
    lines.append("")

    atomic_meta_for_log = dict((export_context or {}).get("atomic_meta") or {})
    template_for_log = _load_ped_source_template_blocks(atomic_meta_for_log)

    clump_off = int((export_context or {}).get("clump_offset") or _log_read_u32(data, 0x24) or template_for_log.get("clump_offset", 0) or 0)
    atomic_off = int((export_context or {}).get("atomic_offset") or template_for_log.get("atomic_offset", 0) or 0)
    if atomic_off <= 0 and clump_off > 0:
        first_atomic_entry = _log_read_u32(data, clump_off + 0x08)
        if first_atomic_entry >= 0x1C:
            atomic_off = int(first_atomic_entry - 0x1C)
    if atomic_off <= 0:
        for scan_off in range(0x40, max(0x40, len(data) - 4), 4):
            if _log_read_u32(data, scan_off) == 0x0004AA01:
                atomic_off = int(scan_off)
                break

    frame_root_off = int(template_for_log.get("frame_offset", 0) or (export_context or {}).get("frames_offset") or 0)
    if frame_root_off <= 0 and clump_off > 0:
        frame_root_off = int(_log_read_u32(data, clump_off + 0x04) or 0)
    hierarchy_off = int((export_context or {}).get("hierarchy_offset") or template_for_log.get("hierarchy_offset", 0) or (_log_read_u32(data, atomic_off + 0x2C) if atomic_off > 0 else 0) or 0)
    geom_off = int((export_context or {}).get("geometry_offset") or (_log_read_u32(data, atomic_off + 0x14) if atomic_off > 0 else 0) or 0)

    collision_template = _extract_ps2_ped_collision_template(
        data,
        frame_ptr=int(frame_root_off or 0),
        atomic_off=int(atomic_off or 0),
    )
    collision_off = int(collision_template.get("ped_collision_header_offset", 0) or 0) if isinstance(collision_template, dict) else 0

    frame_log = _parse_ped_frame_tree_for_log(data, frame_root_off)
    hierarchy_log = _parse_ped_hierarchy_table_for_log(data, hierarchy_off, frame_log)

    _append_ped_import_style_export_fields(
        lines,
        data,
        filepath=filepath,
        clump_off=int(clump_off or 0),
        atomic_off=int(atomic_off or 0),
        geom_off=int(geom_off or 0),
        hierarchy_off=int(hierarchy_off or 0),
    )

    structures: List[Tuple[int, str]] = [
        (0x00, "MDL container header"),
        (0x40, "Primary header RslNode1 / fixed header frame"),
        (0xF0, "Secondary header RslNode2 / fixed helper"),
    ]
    if collision_off > 0:
        structures.append((collision_off, "PED collision sphere header"))
    if clump_off > 0:
        structures.append((clump_off, "Clump"))
    if atomic_off > 0:
        structures.append((atomic_off, "Atomic / RslNode3"))
    if hierarchy_off > 0:
        structures.append((hierarchy_off, "Hierarchy header"))
    if hierarchy_log.get("entries_ptr"):
        structures.append((int(hierarchy_log.get("entries_ptr", 0)), "Hierarchy pointer table entries"))
    if geom_off > 0:
        structures.append((geom_off, "Geometry header + material/parts block"))
    for node in list(frame_log.get("offset_order") or []):
        node_name = str(node.get("name", "")).strip() or f"frame_0x{int(node.get('offset', 0)):X}"
        structures.append((int(node.get("offset", 0)), f"Frame node '{node_name}'"))
    structures = sorted({(int(off), str(name)) for off, name in structures if int(off) >= 0}, key=lambda item: item[0])

    lines.append("Exported structure order (sorted by file offset)")
    for off, name in structures:
        lines.append(f"  0x{off:08X}  {name}")
    lines.append("")

    lines.append("Frame hierarchy traversal order (child/sibling walk)")
    for index, node in enumerate(list(frame_log.get("tree_order") or [])):
        node_name = str(node.get("name", "")).strip() or f"frame_0x{int(node.get('offset', 0)):X}"
        lines.append(
            f"  [{index:02d}] 0x{int(node.get('offset', 0)):08X} {node_name} | "
            f"parent=0x{int(node.get('parent_ptr', 0)):08X} child=0x{int(node.get('child_ptr', 0)):08X} "
            f"sibling=0x{int(node.get('sib_ptr', 0)):08X} root=0x{int(node.get('root_ptr', 0)):08X}"
        )
    if not list(frame_log.get("tree_order") or []):
        lines.append("  <no frame nodes parsed>")
    lines.append("")

    lines.append("Primary fixed header fields")
    for rel, name, meaning in [
        (0x00, "section_id", "header frame section ID / fixed RslNode1 tag"),
        (0x04, "next_ptr", "pointer to the secondary fixed helper node"),
        (0x08, "self_ptr_a", "self/cycle pointer A for the fixed header node"),
        (0x0C, "self_ptr_b", "self/cycle pointer B for the fixed header node"),
    ]:
        value = _log_read_u32(data, 0x40 + rel)
        lines.append(f"  0x{0x40 + rel:08X} {name:<14} = 0x{value:08X} | {meaning}")
    lines.append("")

    lines.append("Secondary fixed helper fields")
    for rel, name, meaning in [
        (0x00, "section_id", "fixed 00 AA 80 03 helper node tag"),
        (0x04, "parent_ptr", "fixed helper parent pointer / usually zero"),
        (0x08, "self_or_next_a", "helper cycle pointer A"),
        (0x0C, "self_or_next_b", "helper cycle pointer B"),
    ]:
        value = _log_read_u32(data, 0xF0 + rel)
        lines.append(f"  0x{0xF0 + rel:08X} {name:<14} = 0x{value:08X} | {meaning}")
    lines.append("")

    if clump_off > 0:
        lines.append(f"Clump fields @ 0x{clump_off:08X}")
        for rel, name, meaning in [
            (0x00, "section_id", "Clump section ID"),
            (0x04, "root_frame", "pointer to the root frame used by the clump"),
            (0x08, "first_atomic", "pointer to the first Atomic clump-cycle entry"),
            (0x0C, "last_atomic", "pointer to the last Atomic clump-cycle entry"),
        ]:
            value = _log_read_u32(data, clump_off + rel)
            lines.append(f"  0x{clump_off + rel:08X} {name:<14} = 0x{value:08X} | {meaning}")
        lines.append("")

    if atomic_off > 0:
        lines.append(f"Atomic / RslNode3 fields @ 0x{atomic_off:08X}")
        atomic_fields = [
            (0x00, "section_id", "Atomic section ID"),
            (0x04, "parent_frame", "pointer to parent frame / helper node"),
            (0x08, "frame_cycle_next", "next pointer in the frame-atomic cycle"),
            (0x0C, "frame_cycle_prev", "previous pointer in the frame-atomic cycle"),
            (0x10, "unknown", "retail/export filler field"),
            (0x14, "geometry_ptr", "pointer to geometry header block"),
            (0x18, "clump_ptr", "pointer to owning clump"),
            (0x1C, "clump_cycle_next", "next pointer in clump-atomic cycle"),
            (0x20, "clump_cycle_prev", "previous pointer in clump-atomic cycle"),
            (0x24, "render_cb", "render callback / method ID"),
            (0x28, "model_info_id", "IDE model info ID"),
            (0x2A, "vis_id_flag", "visibility / detach flag field"),
            (0x2C, "hierarchy_ptr", "pointer to packed hierarchy header"),
            (0x30, "tail", "tail field, usually 0"),
        ]
        for rel, name, meaning in atomic_fields:
            field_off = atomic_off + rel
            if rel == 0x28:
                value = _log_read_i16(data, field_off)
                lines.append(f"  0x{field_off:08X} {name:<16} = {value} | {meaning}")
            elif rel == 0x2A:
                value = _log_read_u16(data, field_off)
                lines.append(f"  0x{field_off:08X} {name:<16} = 0x{value:04X} ({value}) | {meaning}")
            else:
                value = _log_read_u32(data, field_off)
                lines.append(f"  0x{field_off:08X} {name:<16} = 0x{value:08X} ({value}) | {meaning}")
        lines.append("")

    if hierarchy_off > 0:
        header_size = int(hierarchy_log.get("header_size", 0) or 0x38)
        lines.append(f"Hierarchy header @ 0x{hierarchy_off:08X}")
        lines.append(_log_hex_words(data[hierarchy_off:hierarchy_off + header_size], hierarchy_off))
        for rel, name, meaning in [
            (0x00, "section_id", "hierarchy header tag, expected 0x00003000"),
            (0x04, "entry_count", "number of packed hierarchy entries"),
            (0x28, "hash_value", "source-driven hash / unknown retail field"),
            (0x2C, "tail_value", "source-driven tail / unknown retail field"),
            (0x30, "entries_ptr", "pointer to the packed hierarchy entry table"),
            (0x34, "anchor_frame_ptr", "pointer to the frame node used as hierarchy anchor"),
        ]:
            if rel + 4 > header_size:
                continue
            value = _log_read_u32(data, hierarchy_off + rel)
            lines.append(f"  0x{hierarchy_off + rel:08X} {name:<16} = 0x{value:08X} ({value}) | {meaning}")
        lines.append("")

        lines.append("Hierarchy pointer table entries")
        for entry in list(hierarchy_log.get("entries") or []):
            frame_desc = ""
            if entry.get("frame_name"):
                frame_desc = f" -> frame '{entry.get('frame_name')}' @ 0x{int(entry.get('frame_offset', 0)):08X}"
            lines.append(
                f"  0x{int(entry.get('offset', 0)):08X} packed=0x{int(entry.get('packed', 0)):08X} | "
                f"bone_id={int(entry.get('bone_id', 0)):3d} node_index={int(entry.get('node_index', 0)):3d} "
                f"bone_type={int(entry.get('bone_type', 0)):3d} flag=0x{int(entry.get('flag_byte', 0)):02X} zero=0x{int(entry.get('zero', 0)):08X}{frame_desc}"
            )
        if not list(hierarchy_log.get("entries") or []):
            lines.append("  <no hierarchy entries parsed>")
        lines.append("")

    if geom_off > 0:
        lines.append(f"Geometry header block @ 0x{geom_off:08X}")
        geom_fields = [
            (0x00, "section_id", "geometry section ID / preamble field 0"),
            (0x04, "unknown0", "geometry preamble field 1"),
            (0x08, "unknown1", "geometry preamble field 2"),
            (0x0C, "material_list_ptr", "pointer to material pointer list"),
            (0x10, "material_count", "number of material entries"),
            (0x14, "bounds_header_ptr", "pointer to the auxiliary bounds header when present"),
            (0x18, "unknown2", "geometry preamble field 6"),
            (0x1C, "unknown3", "geometry preamble field 7"),
            (0x50, "scale_x", "global scale X used to decode short positions"),
            (0x54, "scale_y", "global scale Y used to decode short positions"),
            (0x58, "scale_z", "global scale Z used to decode short positions"),
            (0x5C, "pos_x", "global translation X"),
            (0x60, "pos_y", "global translation Y"),
            (0x64, "pos_z", "global translation Z"),
        ]
        for rel, name, meaning in geom_fields:
            field_off = geom_off + rel
            if rel >= 0x50:
                value = _log_read_f32(data, field_off)
                lines.append(f"  0x{field_off:08X} {name:<18} = {value:.9g} | {meaning}")
            else:
                value = _log_read_u32(data, field_off)
                lines.append(f"  0x{field_off:08X} {name:<18} = 0x{value:08X} ({value}) | {meaning}")
        lines.append("")

    lines.append("Frame node fields (offset order)")
    for node in list(frame_log.get("offset_order") or []):
        node_off = int(node.get("offset", 0))
        node_name = str(node.get("name", "")).strip() or f"frame_0x{node_off:X}"
        lines.append(f"  Frame '{node_name}' @ 0x{node_off:08X}")
        lines.append(f"    0x{node_off + 0x00:08X} section_id          = 0x{int(node.get('tag', 0)):08X} | frame node section tag")
        lines.append(f"    0x{node_off + 0x04:08X} parent_ptr          = 0x{int(node.get('parent_ptr', 0)):08X} | parent frame pointer")
        lines.append(f"    0x{node_off + 0x08:08X} first_atomic_ptr    = 0x{int(node.get('first_atomic_ptr', 0)):08X} | frame-atomic cycle first pointer")
        lines.append(f"    0x{node_off + 0x0C:08X} last_atomic_ptr     = 0x{int(node.get('last_atomic_ptr', 0)):08X} | frame-atomic cycle last pointer")
        lines.append(f"    0x{node_off + 0x90:08X} child_ptr           = 0x{int(node.get('child_ptr', 0)):08X} | child frame pointer")
        lines.append(f"    0x{node_off + 0x94:08X} sibling_ptr         = 0x{int(node.get('sib_ptr', 0)):08X} | sibling frame pointer")
        lines.append(f"    0x{node_off + 0x98:08X} root_ptr            = 0x{int(node.get('root_ptr', 0)):08X} | root frame pointer")
        lines.append(f"    0x{node_off + 0x9C:08X} bone_id             = 0x{int(node.get('bone_id', 0)) & 0xFFFFFFFF:08X} | bone ID / ped-only metadata")
        lines.append(f"    0x{node_off + 0xA0:08X} bone_params_ptr     = 0x{int(node.get('bone_params_ptr', 0)):08X} | pointer to bone params when present")
        lines.append(f"    0x{node_off + 0xA8:08X} name_ptr_or_info    = 0x{int(node.get('name_ptr', 0)):08X} | frame name pointer / model info slot")
    if not list(frame_log.get("offset_order") or []):
        lines.append("  <no frame nodes parsed>")
    lines.append("")

    local_num_off = _log_read_u32(data, 0x0C)
    global_num_off = _log_read_u32(data, 0x10)
    pointer_count = _log_read_u32(data, 0x14)
    root_local = _log_read_u32(data, local_num_off) if local_num_off > 0 else 0
    local_self = _log_read_u32(data, global_num_off) if global_num_off > 0 else 0

    lines.append("Relocation / pointer table")
    if local_num_off > 0:
        lines.append(f"  local_numTable @ 0x{local_num_off:08X}: root_offset=0x{root_local:08X}")
    if global_num_off > 0:
        lines.append(f"  global_numTable @ 0x{global_num_off:08X}: local_table_self=0x{local_self:08X}")
    lines.append(f"  pointer_count = {pointer_count}")
    for index in range(int(pointer_count)):
        entry_off = int(global_num_off) + 4 + (index * 4)
        if entry_off + 4 > len(data):
            break
        field_off = _log_read_u32(data, entry_off)
        target_value = _log_read_u32(data, field_off) if 0 <= field_off + 4 <= len(data) else 0
        meaning = _ped_pointer_field_meaning(
            field_off,
            data=data,
            clump_off=int(clump_off or 0),
            atomic_off=int(atomic_off or 0),
            hierarchy_off=int(hierarchy_off or 0),
            frame_log=frame_log,
        )
        lines.append(
            f"  [{index:03d}] table@0x{entry_off:08X} -> field@0x{field_off:08X} = 0x{target_value:08X} | {meaning}"
        )
    lines.append("")

    part_headers = list((export_context or {}).get("part_headers") or [])
    material_names = list((export_context or {}).get("material_names") or [])
    if part_headers or material_names:
        lines.append("Exporter-side part/material ordering used to build the file")
        for index, header in enumerate(part_headers):
            tex_id = int(header.get("tex_id", index)) if isinstance(header, dict) else int(index)
            mat_name = material_names[index] if index < len(material_names) else ""
            lines.append(
                f"  part[{index:02d}] tex_id={tex_id:3d} material='{mat_name}' strip_vertex_count={int(header.get('strip_vertex_count', 0)) if isinstance(header, dict) else 0}"
            )
        if not part_headers and material_names:
            for index, name in enumerate(material_names):
                lines.append(f"  material[{index:02d}] '{name}'")
        lines.append("")

    skin_stats_found = False
    for header in part_headers:
        if isinstance(header, dict) and isinstance(header.get("skin_export_stats"), dict):
            skin_stats_found = True
            break
    if skin_stats_found:
        lines.append("PED skin export stats by part")
        lines.append("  These are exporter-side stats for the final rebuilt 0x6C skin stream. They are not imported raw dword roundtrip stats.")
        for index, header in enumerate(part_headers):
            if not isinstance(header, dict):
                continue
            stats = header.get("skin_export_stats")
            if not isinstance(stats, dict):
                continue
            tex_id = int(header.get("tex_id", index))
            mat_name = material_names[index] if index < len(material_names) else ""
            lines.append(f"  part[{index:02d}] tex_id={tex_id:3d} material='{mat_name}' object='{stats.get('object_name', '')}'")
            lines.append(
                "    vertices: "
                f"mesh={int(stats.get('mesh_vertex_count', 0) or 0)} "
                f"emitted={int(stats.get('emitted_vertex_count', 0) or 0)} "
                f"subStrips={int(stats.get('emitted_sub_strip_count', 0) or 0)} "
                f"usedNodes={int(stats.get('used_node_count', 0) or 0)}"
            )
            lines.append(
                "    repairs/regeneration: "
                f"validAttrs={int(stats.get('attribute_valid_count', 0) or 0)} "
                f"fromGroups={int(stats.get('regenerated_from_groups', 0) or 0)} "
                f"fromNearest={int(stats.get('regenerated_from_nearest', 0) or 0)} "
                f"fromDefault={int(stats.get('regenerated_from_default', 0) or 0)} "
                f"regionRepairedVerts={int(stats.get('region_repaired_vertices', 0) or 0)} "
                f"rejectedNodes={int(stats.get('rejected_node_count', 0) or 0)}"
            )
            lines.append(
                "    final weight ranges: "
                f"nonzero=[{float(stats.get('nonzero_weight_min', 0.0) or 0.0):.6f}, {float(stats.get('nonzero_weight_max', 0.0) or 0.0):.6f}] "
                f"sum=[{float(stats.get('weight_sum_min', 0.0) or 0.0):.6f}, {float(stats.get('weight_sum_max', 0.0) or 0.0):.6f}] "
                f"zeroWeightVerts={int(stats.get('zero_weight_vertices', 0) or 0)} "
                f"badSumVerts={int(stats.get('not_normalized_vertices', 0) or 0)} "
                f"invalidNodeVerts={int(stats.get('invalid_node_vertices', 0) or 0)}"
            )
            allowed_nodes = list(stats.get("allowed_nodes") or [])
            allowed_names = list(stats.get("allowed_node_names") or [])
            if allowed_nodes:
                pairs = []
                for allowed_index, node in enumerate(allowed_nodes):
                    name = allowed_names[allowed_index] if allowed_index < len(allowed_names) else f"node_{node}"
                    pairs.append(f"{int(node)}:{name}")
                lines.append("    allowed nodes: " + ", ".join(pairs))
            else:
                lines.append("    allowed nodes: <unrestricted/imported body part>")
            usage_rows = list(stats.get("node_usage") or [])
            if usage_rows:
                lines.append("    node usage:")
                for row in sorted(usage_rows, key=lambda item: int(item.get("node", 0)) if isinstance(item, dict) else 0):
                    if not isinstance(row, dict):
                        continue
                    lines.append(
                        f"      node {int(row.get('node', 0)):02d} {str(row.get('name', '')):<24} "
                        f"count={int(row.get('count', 0) or 0):5d} weightSum={float(row.get('weight_sum', 0.0) or 0.0):.6f}"
                    )
            else:
                lines.append("    node usage: <none>")
        lines.append("")

    return lines

def _write_prop_export_log(filepath: str, data: bytes, export_context: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    lines.append(f"Exported file: {filepath}")
    lines.append("MDL kind: PS2 PROP / simple-model Stories export")
    lines.append("")

    lines.append("MDL header bytes (0x00-0x23)")
    lines.append(_log_hex_words(data[:0x24], 0x00))
    lines.append("")

    lines.append("MDL header fields")
    for off, name, meaning in [
        (0x00, "signature", "container signature, expected 'ldm\\0'"),
        (0x04, "reserved", "container reserved field"),
        (0x08, "file_len", "logical MDL size before sector padding"),
        (0x0C, "local_numTable", "string table / relocation table start"),
        (0x10, "global_numTable", "relocation pointer list"),
        (0x14, "numEntries", "number of relocation entries"),
        (0x18, "ptr2_before_tex", "pointer just before last texture relocation entry"),
        (0x1C, "allocMem", "engine allocation/version field"),
        (0x20, "ptr_after_alloc", "top-level Atomic1 pointer"),
    ]:
        value = _log_read_u32(data, off)
        lines.append(f"  0x{off:02X} {name:<18} = 0x{value:08X} ({value}) | {meaning}")
    lines.append("")

    atomic2_off = 0x30
    matrices_off = 0x40
    atomic1_off = 0xE0
    texlist_off = 0x120
    geom_hdr_off = 0x150
    global_geom_off = 0x170
    part_count = _log_read_u32(data, texlist_off - 0x04)
    packed = _log_read_u32(data, global_geom_off + 0x10)
    material_count = (packed >> 20) & 0xFFF
    geom_size = packed & 0xFFFFF
    first_tristrip_rel_off = _log_read_u16(data, global_geom_off + 0x16)
    dma_start_off = global_geom_off + first_tristrip_rel_off if first_tristrip_rel_off > 0 else 0

    lines.append("Exported structure order (sorted by file offset)")
    for off, name in [
        (0x00, "MDL container header"),
        (atomic2_off, "Atomic2 / helper"),
        (matrices_off, "identity matrices block"),
        (atomic1_off, "Atomic1 / live simple-model node"),
        (texlist_off, "texture-name pointer block"),
        (geom_hdr_off, "geometry preamble"),
        (global_geom_off, "Leeds global geometry header"),
        (dma_start_off, "DMA / VIF stream start"),
    ]:
        if off > 0:
            lines.append(f"  0x{off:08X}  {name}")
    lines.append("")

    lines.append(f"Atomic2 fields @ 0x{atomic2_off:08X}")
    for rel, name, meaning in [
        (0x00, "section_id", "Atomic2 section ID"),
        (0x04, "zero", "reserved / zero in retail props"),
        (0x08, "prev_entry", "pointer to Atomic1+0x08"),
        (0x0C, "next_entry", "pointer to Atomic1+0x08"),
    ]:
        value = _log_read_u32(data, atomic2_off + rel)
        lines.append(f"  0x{atomic2_off + rel:08X} {name:<14} = 0x{value:08X} | {meaning}")
    lines.append("")

    lines.append(f"Atomic1 fields @ 0x{atomic1_off:08X}")
    for rel, name, meaning in [
        (0x00, "section_id", "Atomic1 section ID"),
        (0x04, "prev_vtable", "pointer back to Atomic2"),
        (0x08, "prev_entry", "Atomic cycle prev entry"),
        (0x0C, "next_entry", "Atomic cycle next entry"),
        (0x14, "geom_ptr", "pointer to geometry preamble"),
        (0x1C, "hash_key_a", "hash / key field copy A"),
        (0x20, "hash_key_b", "hash / key field copy B"),
        (0x28, "geom_ptr_b", "duplicate geometry pointer"),
        (0x34, "tex_ptr", "pointer to selected material string"),
        (0x38, "vcol", "material colour / RGBA field"),
    ]:
        value = _log_read_u32(data, atomic1_off + rel)
        lines.append(f"  0x{atomic1_off + rel:08X} {name:<14} = 0x{value:08X} ({value}) | {meaning}")
    lines.append("")

    lines.append(f"Texture pointer block @ 0x{texlist_off:08X}")
    for rel, name, meaning in [
        (0x00, "self_plus_4", "pointer to TEXLIST_OFF+4"),
        (0x08, "string0_ptr", "pointer to first texture string"),
        (0x10, "texture_count", "number of texture names"),
        (0x14, "ptr_field_tex_ptr", "points at Atomic1.tex_ptr field"),
        (0x18, "ptr_field_string1", "points at this block's string1 pointer field"),
        (0x1C, "string1_ptr", "pointer to second texture string"),
        (0x20, "vcol_string1", "RGBA/vcol for second texture slot"),
        (0x24, "texture_count_b", "duplicated texture count"),
    ]:
        field_off = texlist_off + rel
        if rel == 0x10 or rel == 0x24:
            value = _log_read_u32(data, field_off)
        else:
            value = _log_read_u32(data, field_off)
        lines.append(f"  0x{field_off:08X} {name:<16} = 0x{value:08X} ({value}) | {meaning}")
    lines.append("")

    lines.append(f"Geometry global header @ 0x{global_geom_off:08X}")
    lines.append(f"  packed_size_and_material_count = 0x{packed:08X} | material_count={material_count} geom_size=0x{geom_size:X}")
    lines.append(f"  sphere_x = {_log_read_f32(data, global_geom_off + 0x00):.9g}")
    lines.append(f"  sphere_y = {_log_read_f32(data, global_geom_off + 0x04):.9g}")
    lines.append(f"  sphere_z = {_log_read_f32(data, global_geom_off + 0x08):.9g}")
    lines.append(f"  sphere_r = {_log_read_f32(data, global_geom_off + 0x0C):.9g}")
    lines.append(f"  vertex_section_flags = 0x{_log_read_u32(data, global_geom_off + 0x14):08X}")
    lines.append(f"  total_vertex_count   = {_log_read_u16(data, global_geom_off + 0x18)}")
    lines.append(f"  first_tristrip_rel   = 0x{_log_read_u16(data, global_geom_off + 0x1A):04X}")
    lines.append(f"  scale = ({_log_read_f32(data, global_geom_off + 0x20):.9g}, {_log_read_f32(data, global_geom_off + 0x24):.9g}, {_log_read_f32(data, global_geom_off + 0x28):.9g})")
    lines.append(f"  pos   = ({_log_read_f32(data, global_geom_off + 0x2C):.9g}, {_log_read_f32(data, global_geom_off + 0x30):.9g}, {_log_read_f32(data, global_geom_off + 0x34):.9g})")
    lines.append("")

    lines.append("Per-part Leeds headers")
    part_table_off = global_geom_off + 0x40
    safe_part_count = int(part_count)
    if safe_part_count < 0:
        safe_part_count = 0
    if safe_part_count > 1024:
        safe_part_count = 1024
    for part_index in range(safe_part_count):
        part_off = part_table_off + (part_index * 0x30)
        if part_off + 0x30 > len(data):
            break
        rel_off = _log_read_u16(data, part_off + 0x1A)
        lines.append(
            f"  part[{part_index:02d}] @ 0x{part_off:08X} | tex_id={_log_read_u16(data, part_off + 0x1E)} "
            f"strip_vertex_count={_log_read_u16(data, part_off + 0x1C)} rel_off=0x{rel_off:04X} "
            f"bbox_i16=({_log_read_i16(data, part_off + 0x20)}, {_log_read_i16(data, part_off + 0x22)}, {_log_read_i16(data, part_off + 0x24)}, {_log_read_i16(data, part_off + 0x26)}, {_log_read_i16(data, part_off + 0x28)}, {_log_read_i16(data, part_off + 0x2A)})"
        )
    if safe_part_count == 0:
        lines.append("  <no part headers parsed>")
    lines.append("")

    local_num_off = _log_read_u32(data, 0x0C)
    global_num_off = _log_read_u32(data, 0x10)
    ptr2_before_tex = _log_read_u32(data, 0x18)
    pointer_count = _log_read_u32(data, 0x14)
    lines.append("Relocation / pointer table")
    lines.append(f"  local_numTable  @ 0x{local_num_off:08X}")
    lines.append(f"  global_numTable @ 0x{global_num_off:08X}")
    lines.append(f"  ptr2_before_tex = 0x{ptr2_before_tex:08X}")
    lines.append(f"  pointer_count   = {pointer_count}")

    table_start = int(global_num_off) + 4
    for index in range(int(pointer_count)):
        entry_off = table_start + (index * 4)
        if entry_off + 4 > len(data):
            break
        field_off = _log_read_u32(data, entry_off)
        target_value = _log_read_u32(data, field_off) if 0 <= field_off + 4 <= len(data) else 0
        meaning = _prop_pointer_field_meaning(field_off)
        lines.append(f"  [{index:03d}] table@0x{entry_off:08X} -> field@0x{field_off:08X} = 0x{target_value:08X} | {meaning}")
    lines.append("")

    material_names = list((export_context or {}).get("material_names") or [])
    part_headers = list((export_context or {}).get("part_headers") or [])
    if material_names or part_headers:
        lines.append("Exporter-side part/material ordering used to build the file")
        for index, name in enumerate(material_names):
            tex_id = index
            strip_count = 0
            if index < len(part_headers) and isinstance(part_headers[index], dict):
                tex_id = int(part_headers[index].get("tex_id", index))
                strip_count = int(part_headers[index].get("strip_vertex_count", 0))
            lines.append(f"  slot[{index:02d}] tex_id={tex_id:3d} material='{name}' strip_vertex_count={strip_count}")
        lines.append("")

    return lines

def _write_mdl_export_log(filepath: str, *, mdl_kind: str, export_context: Optional[Dict[str, Any]] = None) -> None:
    export_context = dict(export_context or {})
    log_path = os.path.splitext(filepath)[0] + "_export_log.txt"

    try:
        with open(filepath, 'rb') as f:
            data = f.read()
    except Exception:
        return

    lines: List[str] = []
    try:
        kind = str(mdl_kind or "").upper().strip()
        if kind == "PED_PS2":
            lines = _write_ped_export_log(filepath, data, export_context)
        else:
            lines = _write_prop_export_log(filepath, data, export_context)
    except Exception as exc:
        lines = [
            f"Exported file: {filepath}",
            f"Failed to build structured export log: {exc}",
        ]

    try:
        with open(log_path, 'w', encoding='utf-8', newline='\n') as outf:
            outf.write("\n".join(lines).rstrip() + "\n")
    except Exception:
        return

def write_simplemodel_ps2_ped_mdl(
    filepath: str,
    scale_pos,
    dma_packets: List[bytes],
    material_names: List[str],
    part_headers: Optional[List[Dict[str, Any]]] = None,
    global_header: Optional[Dict[str, Any]] = None,
    atomic_meta: Optional[Dict[str, Any]] = None,
    armature_obj: Any = None,
    import_type_hint: Optional[int] = None,
    material_vcols: Optional[List[int]] = None,
    imported_export_mode: Optional[str] = None,
) -> None:
    if not dma_packets:
        raise RuntimeError("PED export requires at least one DMA packet.")
    if armature_obj is None:
        raise RuntimeError("PED export requires a valid armature object.")

    if not material_names:
        material_names = ["default"]

    buf = bytearray()
    pointer_fields: List[int] = []
    pending_textures: List[PendingTexture] = []
    pending_frame_names: List[PendingFrameName] = []

    header = begin_mdl_header_ped_ps2(buf)

    if len(buf) < 0x40:
        buf.extend(b"\x00" * (0x40 - len(buf)))
    else:
        align_buffer(buf, 0x10)

    ped_frame_meta: Dict[str, Any] = {}
    frames_offset = _append_ps2_ped_frames_from_armature(
        buf,
        pointer_fields,
        armature_obj=armature_obj,
        import_type_hint=import_type_hint,
        reserved_root_off=0x40,
        pending_frame_names=pending_frame_names,
        out_meta=ped_frame_meta,
        atomic_meta=atomic_meta,
    )
    if not frames_offset:
        frames_offset = _append_ps2_ped_frames_all_bones(
            buf,
            pointer_fields,
            armature_obj=armature_obj,
            import_type_hint=import_type_hint,
            pending_frame_names=pending_frame_names,
        )
    if not frames_offset:
        raise RuntimeError("PED export requires a valid frame tree. Failed to generate frames from the Blender armature.")

    hierarchy_offset = _append_ps2_ped_hierarchy_block_from_frames(
        buf,
        pointer_fields,
        frames_offset=int(frames_offset),
        import_type_hint=import_type_hint,
        armature_obj=armature_obj,
        atomic_meta=atomic_meta,
        ped_frame_meta=ped_frame_meta,
    )
    if hierarchy_offset > 0 and hierarchy_offset + 8 <= len(buf):

        struct.pack_into("<I", buf, int(hierarchy_offset), 0x00003000)

    material_offsets: List[int] = []
    if material_vcols is None:
        material_vcols = []
    if len(material_vcols) < len(material_names):
        material_vcols = list(material_vcols) + [0xFFFFFFFF] * (len(material_names) - len(material_vcols))

    material_rgba_values = [int(material_vcols[index]) & 0xFFFFFFFF for index in range(len(material_names))]
    post_geometry_materials = _should_place_ps2_ped_materials_after_geometry(
        current_size=len(buf),
        dma_packets=dma_packets,
        material_count=len(material_names),
        part_count=len(dma_packets),
    )
    geometry_write_info: Dict[str, Any] = {}

    if not post_geometry_materials:
        align_buffer(buf, 0x10)
        for index, material_name in enumerate(material_names):
            material_offsets.append(
                write_material(
                    buf,
                    str(material_name),
                    pointer_fields,
                    pending_textures,
                    rgba=material_rgba_values[index],
                )
            )
    else:
        material_offsets = [0] * len(material_names)

    collision_offset = None
    struct_bounds_offset = 0
    geom_bounds_header_offset = 0

    part_materials: List[int] = []
    material_count = max(1, len(material_offsets))
    for part_index in range(len(dma_packets)):
        material_id = part_index % material_count
        if part_headers and part_index < len(part_headers):
            try:
                material_id = int((part_headers[part_index] or {}).get('tex_id', material_id))
            except Exception:
                material_id = part_index % material_count
        part_materials.append(int(material_id) % material_count)

    clump_offset = int(frames_offset) + (2 * 0xB0)
    clump_end = clump_offset + 0x20
    if len(buf) < clump_end:
        buf.extend(b'\x00' * (clump_end - len(buf)))

    scene_root_for_clump = int(ped_frame_meta.get('scene_root_off', 0) or 0)
    clump_root_ptr = scene_root_for_clump if scene_root_for_clump > 0 else int(frames_offset)
    struct.pack_into('<I', buf, clump_offset + 0x00, 0x0000AA02)
    clump_root_field = clump_offset + 0x04
    struct.pack_into('<I', buf, clump_root_field, clump_root_ptr & 0xFFFFFFFF)
    clump_first_atomic_field = clump_offset + 0x08
    struct.pack_into('<I', buf, clump_first_atomic_field, 0)
    clump_last_atomic_field = clump_offset + 0x0C
    struct.pack_into('<I', buf, clump_last_atomic_field, 0)
    struct.pack_into('<I', buf, clump_offset + 0x10, 0)
    struct.pack_into('<I', buf, clump_offset + 0x14, 0x000000FF)
    struct.pack_into('<I', buf, clump_offset + 0x18, 0)
    struct.pack_into('<I', buf, clump_offset + 0x1C, 0)

    align_buffer(buf, 0x10)

    scene_root_off = int(ped_frame_meta.get('scene_root_off', 0) or 0)
    base_helper_off = int(ped_frame_meta.get('base_helper_off', 0) or 0)

    atomic_parent_ptr = int(base_helper_off or scene_root_off or frames_offset)
    atomic_offset = len(buf)

    write_u32(buf, 0x0004AA01)

    atomic_parent_field = len(buf)
    write_u32(buf, int(atomic_parent_ptr) & 0xFFFFFFFF)

    atomic_next_field = len(buf)
    write_u32(buf, (int(atomic_parent_ptr) + 0x08) & 0xFFFFFFFF)

    atomic_prev_field = len(buf)
    write_u32(buf, (int(atomic_parent_ptr) + 0x08) & 0xFFFFFFFF)

    write_u32(buf, 0x00000000)

    atomic_geom_field = len(buf)
    write_u32(buf, 0)

    atomic_clump_field = len(buf)
    write_u32(buf, int(clump_offset) & 0xFFFFFFFF)

    atomic_clump_next_field = len(buf)
    write_u32(buf, (int(clump_offset) + 0x08) & 0xFFFFFFFF)

    atomic_clump_prev_field = len(buf)
    write_u32(buf, (int(clump_offset) + 0x08) & 0xFFFFFFFF)

    render_cb = 0x12
    model_info_id = -1
    vis_id_flag = -1
    if isinstance(atomic_meta, dict):
        try:
            render_cb = int(atomic_meta.get("render_cb", render_cb))
        except Exception:
            pass
        try:
            model_info_id = int(atomic_meta.get("model_info_id", model_info_id))
        except Exception:
            pass
        try:
            vis_id_flag = int(atomic_meta.get("vis_id_flag", vis_id_flag))
        except Exception:
            pass

    write_u32(buf, render_cb & 0xFFFFFFFF)

    packed_model_vis = ((int(vis_id_flag) & 0xFFFF) << 16) | (int(model_info_id) & 0xFFFF)
    write_u32(buf, packed_model_vis & 0xFFFFFFFF)

    atomic_hierarchy_field = len(buf)
    write_u32(buf, int(hierarchy_offset) & 0xFFFFFFFF)

    write_u32(buf, 0)

    root_bone_a4_off = int(ped_frame_meta.get('root_bone_a4_off', 0) or 0)
    if root_bone_a4_off <= 0:
        try:
            root_bone_a4_off = int(ped_frame_meta.get('root_bone_off', 0) or 0) + 0xA4
        except Exception:
            root_bone_a4_off = 0
    if root_bone_a4_off <= 0:
        try:
            root_bone_a4_off = int(frames_offset) + 0xA4
        except Exception:
            root_bone_a4_off = 0
    if root_bone_a4_off > 0 and root_bone_a4_off + 4 <= len(buf):
        struct.pack_into('<I', buf, root_bone_a4_off, int(hierarchy_offset) & 0xFFFFFFFF)

    struct.pack_into('<I', buf, clump_first_atomic_field, int(atomic_clump_next_field) & 0xFFFFFFFF)
    struct.pack_into('<I', buf, clump_last_atomic_field, int(atomic_clump_next_field) & 0xFFFFFFFF)
    struct.pack_into('<I', buf, atomic_clump_next_field, int(clump_first_atomic_field) & 0xFFFFFFFF)
    struct.pack_into('<I', buf, atomic_clump_prev_field, int(clump_first_atomic_field) & 0xFFFFFFFF)

    try:
        if base_helper_off > 0 and base_helper_off + 0x0C < len(buf):
            struct.pack_into('<I', buf, base_helper_off + 0x08, int(atomic_next_field) & 0xFFFFFFFF)
            struct.pack_into('<I', buf, base_helper_off + 0x0C, int(atomic_next_field) & 0xFFFFFFFF)
    except Exception:
        pass

    align_buffer(buf, 0x10)

    geometry_offset = write_geometry_and_material(
        buf=buf,
        pointer_fields=pointer_fields,
        part_materials=part_materials,
        scale_pos=scale_pos,
        dma_packets=[bytearray(p) for p in dma_packets],
        material_offsets=material_offsets,
        part_headers=part_headers,
        global_header=global_header,
        bounds_header_ptr=geom_bounds_header_offset,
        inverse_matrix_table_bytes=bytes(ped_frame_meta.get('inverse_matrix_table_bytes', b'') or b''),
        material_names=material_names if post_geometry_materials else None,
        material_rgba_values=material_rgba_values if post_geometry_materials else None,
        pending_textures=pending_textures if post_geometry_materials else None,
        out_info=geometry_write_info,
    )
    struct.pack_into('<I', buf, atomic_geom_field, int(geometry_offset) & 0xFFFFFFFF)
    if hierarchy_offset > 0 and hierarchy_offset + 8 <= len(buf):
        struct.pack_into("<I", buf, int(hierarchy_offset), 0x00003000)

    if post_geometry_materials:
        material_offsets = [int(v) for v in geometry_write_info.get("material_offsets", [])]
        if not material_offsets:
            raise RuntimeError("PS2 PED post-geometry material table was not written inline before the aux matrix header.")

    align_buffer(buf, 0x10)
    collision_search_start = len(buf)
    collision_offset = _append_ps2_ped_collision_block(
        buf,
        pointer_fields,
        scale_pos=scale_pos,
        part_headers=part_headers,
        atomic_meta=atomic_meta,
    )
    if collision_offset is not None and not _looks_like_ps2_ped_collision_header(buf, int(collision_offset)):
        recovered_collision_offset = _find_recent_ps2_ped_collision_header(buf, collision_search_start)
        if recovered_collision_offset > 0:
            collision_offset = int(recovered_collision_offset)

    forced_fields = [
        header.struct_or_flags_off,
        header.top_level_ptr_off,
        header.extra_ptr0_off,
        header.extra_ptr1_off,
        header.extra_ptr2_off,
        clump_root_field,
        clump_first_atomic_field,
        clump_last_atomic_field,
        atomic_parent_field,
        atomic_next_field,
        atomic_prev_field,
        atomic_geom_field,
        atomic_clump_field,
        atomic_clump_next_field,
        atomic_clump_prev_field,
        atomic_hierarchy_field,
    ]
    if hierarchy_offset > 0:
        forced_fields.extend([
            int(hierarchy_offset) + 0x30,
            int(hierarchy_offset) + 0x34,
        ])
    ensure_ped_ps2_pointer_fields_registered(
        buf,
        pointer_fields,
        header=header,
        hdr0_off=int(frames_offset),
        hdr1_off=None,
        clump_offset=int(clump_offset),
        atomic_offset=int(atomic_offset),
        ped_frame_meta=ped_frame_meta,
        forced_fields=forced_fields,
    )
    pointer_fields = sanitize_ped_ps2_pointer_fields(pointer_fields)
    pointer_fields = order_ped_ps2_pointer_fields_retail_like(
        pointer_fields,
        header=header,
        frames_offset=int(frames_offset),
        clump_offset=int(clump_offset),
    )

    write_frame_name_strings_before_tables(buf, pending_frame_names)

    ped_local_root_offset = int(atomic_offset) + 0x24
    local_num_offset, global_num_offset = write_pointer_tables_ped_ps2(
        buf,
        pointer_fields,
        root_offset=int(ped_local_root_offset),
    )
    write_texture_strings_after_tables(buf, pending_textures)

    file_size = len(buf)
    header_material_ptrs = _build_ps2_ped_header_material_entry_ptrs(None, material_offsets)
    extra0 = header_material_ptrs[0] if len(header_material_ptrs) > 0 else 0
    extra1 = header_material_ptrs[1] if len(header_material_ptrs) > 1 else extra0
    extra2 = header_material_ptrs[2] if len(header_material_ptrs) > 2 else extra1

    finalize_mdl_header_ped_ps2(
        buf=buf,
        header=header,
        file_size=file_size,
        local_num_offset=local_num_offset,
        global_num_offset=global_num_offset,
        pointer_count=len(pointer_fields),
        struct_or_flags_ptr=int(collision_offset if collision_offset is not None else struct_bounds_offset),
        top_level_ptr=int(clump_offset),
        extra_ptr0=int(extra0),
        extra_ptr1=int(extra1),
        extra_ptr2=int(extra2),
    )

    if hierarchy_offset > 0 and hierarchy_offset + 8 <= len(buf):
        struct.pack_into("<I", buf, int(hierarchy_offset), 0x00003000)

    export_context = {
        "material_names": list(material_names),
        "part_headers": list(part_headers or []),
        "pointer_count": len(pointer_fields),
        "frames_offset": int(frames_offset),
        "hierarchy_offset": int(hierarchy_offset),
        "geometry_offset": int(geometry_offset),
        "clump_offset": int(clump_offset),
        "atomic_offset": int(atomic_offset),
        "collision_offset": int(collision_offset) if collision_offset is not None else 0,
        "struct_bounds_offset": int(struct_bounds_offset),
    }

    pad_to_sector(buf)

    if hierarchy_offset > 0 and hierarchy_offset + 8 <= len(buf):
        struct.pack_into("<I", buf, int(hierarchy_offset), 0x00003000)

    with open(filepath, 'wb') as outf:
        outf.write(buf)

    _write_mdl_export_log(filepath, mdl_kind="PED_PS2", export_context=export_context)

class Mh2MdlReader:
    MH2_PC_MATERIAL_ID_SIZE = 44
    def __init__(self, path, context, collection_name=None):
        self.path = path
        self.context = context
        self.collection_name = collection_name

        self.file = None
        self.file_size = 0
        self.stem = os.path.splitext(os.path.basename(path))[0]
        self.collection = None
        self.armature_obj = None
        self.bone_map = {}
        self.object_infos = []
        self.imported_mesh_objects = []
        self.debug_log = []
        self.source_to_blender = None
        self.blender_to_source = None

    def run(self):
        with open(self.path, "rb") as f:
            self.file = f
            f.seek(0, os.SEEK_END)
            self.file_size = f.tell()
            f.seek(0)
            self.source_to_blender = Matrix.Rotation(math.pi / 2.0, 4, "X")
            self.blender_to_source = self.source_to_blender.inverted()
            self.read_header()
            self.read_entry()
            self.read_bones()
            self.build_armature()
            self.read_object_infos()
            self.prepare_meshes()
            self.write_import_log()
        return True

    def is_valid_offset(self, value, minimum=0):
        try:
            value = int(value)
        except Exception:
            return False
        return minimum <= value < self.file_size

    def is_valid_bone_offset(self, value):
        return self.is_valid_offset(value, 0x40) and value + 192 <= self.file_size

    def source_matrix_to_blender(self, matrix):
        return self.source_to_blender @ matrix @ self.blender_to_source

    def source_vector_to_blender(self, value):
        return self.source_to_blender @ Vector(value)

    def run_silent_mode_set(self, mode):
        import bpy
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode=mode)

    def log(self, message):
        text = str(message)
        self.debug_log.append(text)
        try:
            print(text)
        except Exception:
            pass

    def ensure_text_block(self, name, text):
        try:
            import bpy
            block = bpy.data.texts.get(name) or bpy.data.texts.new(name)
            block.clear()
            block.write(text)
            return block
        except Exception:
            return None

    def write_import_log(self):
        lines = list(self.debug_log)
        if not lines:
            return
        text = "\n".join(lines) + "\n"
        log_path = os.path.splitext(self.path)[0] + "_mh2_import_log.txt"
        try:
            with open(log_path, "w", encoding="utf-8") as outf:
                outf.write(text)
            self.log(f"✔ MH2 PC import log written to: {log_path}")
            text = "\n".join(self.debug_log) + "\n"
        except Exception as exc:
            self.log(f"✗ Failed to write MH2 PC import log: {exc}")
            text = "\n".join(self.debug_log) + "\n"
        safe_name = "BLeeds_MH2_" + self.stem[:40]
        self.ensure_text_block(safe_name, text)

    def read_header(self):
        import bpy

        f = self.file
        data = f.read(0x28)
        if len(data) < 0x28:
            raise ValueError("File too small to be a valid Manhunt 2 PC MDL")

        header = struct.unpack("<4sIIIIIIIii", data)
        signature = header[0].decode("ascii", errors="replace")
        if signature != "PMLC":
            raise ValueError(f"Unsupported MH2 MDL signature {signature!r}; expected PC PMLC")

        first_entry_offset = header[8]

        self.log("==== MH2 PC MDL Import Log ====")
        self.log(f"Source: {self.path}")
        self.log(f"Signature:           {signature}")
        self.log(f"Version:             0x{header[1]:08X}")
        self.log(f"File Size:           {header[2]} bytes")
        self.log(f"Data Size:           {header[3]} bytes")
        self.log(f"Offset Table Start:  0x{header[4]:08X}")
        self.log(f"Num Table Entries:   {header[5]}")
        self.log(f"First Entry Offset:  0x{first_entry_offset:08X}")
        self.log(f"Last Entry Offset:   0x{header[9]:08X}")

        if not self.is_valid_offset(first_entry_offset, 0x20):
            raise ValueError("MH2 PC first entry index is out of range")

        f.seek(first_entry_offset)
        entry_index_data = f.read(16)
        if len(entry_index_data) < 16:
            raise ValueError("MH2 PC first entry index is truncated")

        entry_index = struct.unpack("<iiii", entry_index_data)
        entry_data_offset = entry_index[2]

        self.log("---- First EntryIndex ----")
        self.log(f"Next Entry Offset:   0x{entry_index[0]:08X}")
        self.log(f"Prev Entry Offset:   0x{entry_index[1]:08X}")
        self.log(f"Entry Data Offset:   0x{entry_data_offset:08X}")
        self.log(f"Zero Field:          {entry_index[3]}")

        if not self.is_valid_offset(entry_data_offset, 0x20):
            raise ValueError("MH2 PC first entry data offset is out of range")
        f.seek(entry_data_offset)

        coll_name = self.collection_name or f"MH2_PC_{self.stem}"
        coll = bpy.data.collections.get(coll_name) or bpy.data.collections.new(coll_name)
        if coll.name not in {c.name for c in self.context.scene.collection.children}:
            self.context.scene.collection.children.link(coll)
        self.collection = coll

    def read_entry(self):
        f = self.file
        raw = f.read(0x1C)
        if len(raw) < 0x1C:
            raise ValueError("MH2 PC entry header is out of range")

        entry = struct.unpack("<7i", raw)
        self.root_bone_offset = entry[0]
        self.bone_trans_idx_offs = entry[2]
        self.first_objinfo_offs = entry[5]
        self.last_objinfo_offs = entry[6]

        self.log("---- Entry ----")
        self.log(f"Root Bone Offset:    0x{self.root_bone_offset:08X}")
        self.log(f"Bone Trans Idx Off:  0x{self.bone_trans_idx_offs:08X}")
        self.log(f"First ObjInfo Off:   0x{self.first_objinfo_offs:08X}")
        self.log(f"Last ObjInfo Off:    0x{self.last_objinfo_offs:08X}")

    def read_bones(self):
        if self.is_valid_bone_offset(self.root_bone_offset):
            self.read_bone_block(self.root_bone_offset)

    def build_armature(self):
        import bpy

        arm = bpy.data.armatures.new(f"{self.stem}_Armature")
        arm_obj = bpy.data.objects.new(arm.name, arm)
        self.collection.objects.link(arm_obj)

        bpy.context.view_layer.objects.active = arm_obj
        try:
            arm_obj.select_set(True)
        except Exception:
            pass
        self.run_silent_mode_set("EDIT")

        edits = {}
        for off, bone_info in self.bone_map.items():
            bone_name = bone_info["name"] or f"Bone_{off:08X}"
            if bone_name in edits:
                bone_name = f"{bone_name}_{off:08X}"
                bone_info["name"] = bone_name
            eb = arm.edit_bones.new(bone_name)
            head = bone_info["matrix"].to_translation()
            y_axis = bone_info["matrix"].to_3x3() @ Vector((0.0, 1.0, 0.0))
            if y_axis.length < 0.000001:
                y_axis = Vector((0.0, 0.0, 1.0))
            tail = head + y_axis.normalized() * 0.05
            if (tail - head).length < 0.000001:
                tail = head + Vector((0.0, 0.0, 0.05))
            eb.head = head
            eb.tail = tail
            try:
                z_axis = bone_info["matrix"].to_3x3() @ Vector((0.0, 0.0, 1.0))
                eb.align_roll(z_axis)
            except Exception:
                pass
            edits[off] = eb

        for off, bone_info in self.bone_map.items():
            parent_offset = bone_info["parent_offset"]
            if parent_offset in edits:
                edits[off].parent = edits[parent_offset]

        self.run_silent_mode_set("OBJECT")

        for off, bone_info in self.bone_map.items():
            pose_bone = arm_obj.pose.bones.get(bone_info["name"])
            edit_bone = arm_obj.data.bones.get(bone_info["name"])
            for target in (pose_bone, edit_bone):
                if target is None:
                    continue
                target["bleeds_mh2_pc_bone_offset"] = int(off)
                target["bleeds_mh2_pc_parent_offset"] = int(bone_info.get("parent_offset", 0))
                target["bleeds_mh2_pc_sibling_offset"] = int(bone_info.get("sibling_offset", 0))
                target["bleeds_mh2_pc_child_offset"] = int(bone_info.get("subbone_offset", 0))
                target["bleeds_mh2_pc_anim_data_idx_offset"] = int(bone_info.get("anim_data_idx_offset", 0))

        arm_obj["bleeds_model_game"] = "MH2"
        arm_obj["bleeds_mh2_platform"] = "PC"
        arm_obj["bleeds_mdl_filepath"] = self.path
        self.armature_obj = arm_obj

    def read_object_infos(self):
        f = self.file
        cur = self.first_objinfo_offs
        last = self.last_objinfo_offs
        seen = set()
        infos = []

        while cur and cur not in seen:
            if not self.is_valid_offset(cur, 0x40) or cur + 28 > self.file_size:
                self.log(f"MH2 PC ObjInfo stop: 0x{cur:08X} is not a real ObjInfo offset")
                break
            seen.add(cur)
            f.seek(cur)
            raw = f.read(28)
            if len(raw) < 28:
                break
            next_off, prev_off, parent_bone_off, object_data_off, flags, zero_field, object_type = struct.unpack("<7I", raw)
            if not self.is_valid_offset(object_data_off, 0x40):
                self.log(f"MH2 PC ObjInfo stop: object data 0x{object_data_off:08X} is invalid")
                break
            infos.append({
                "objinfo_offset": cur,
                "object_data_offset": object_data_off,
                "parent_bone_offset": parent_bone_off,
                "prev_offset": prev_off,
                "next_offset": next_off,
                "flags": flags,
                "object_type": object_type,
            })
            self.log(
                f"MH2 PC ObjInfo[{len(infos) - 1:02d}] info=0x{cur:08X} "
                f"object=0x{object_data_off:08X} parent_bone=0x{parent_bone_off:08X} "
                f"next=0x{next_off:08X}"
            )
            if cur == last:
                break
            if next_off == 0 or next_off == cur:
                break
            cur = next_off

        self.object_infos = infos

    def prepare_meshes(self):
        for idx, item in enumerate(self.object_infos):
            self.read_object(idx, item)

    def read_bone_block(self, offset):
        f = self.file
        if not self.is_valid_bone_offset(offset) or offset in self.bone_map:
            return
        f.seek(offset)
        block = f.read(192)
        if len(block) < 192:
            return

        dispatch_or_hash, sibling_offset, parent_offset, root_offset, subbone_offset, anim_data_idx_offset = struct.unpack_from("<6I", block, 0)
        name = block[24:64].split(b"\x00")[0].decode("ascii", errors="replace")

        raw = struct.unpack_from("<16f", block, 128)
        source_matrix = Matrix((
            (raw[0], raw[4], raw[8], raw[12]),
            (raw[1], raw[5], raw[9], raw[13]),
            (raw[2], raw[6], raw[10], raw[14]),
            (raw[3], raw[7], raw[11], raw[15]),
        ))
        blender_matrix = self.source_matrix_to_blender(source_matrix)

        self.bone_map[offset] = {
            "name": name,
            "dispatch_or_hash": dispatch_or_hash,
            "parent_offset": parent_offset,
            "root_offset": root_offset,
            "subbone_offset": subbone_offset,
            "sibling_offset": sibling_offset,
            "anim_data_idx_offset": anim_data_idx_offset,
            "source_matrix": source_matrix,
            "matrix": blender_matrix,
        }

        self.log(
            f"MH2 PC Bone 0x{offset:08X}: name='{name}' "
            f"sibling=0x{sibling_offset:08X} parent=0x{parent_offset:08X} "
            f"child=0x{subbone_offset:08X}"
        )

        if self.is_valid_bone_offset(subbone_offset):
            self.read_bone_block(subbone_offset)
        if self.is_valid_bone_offset(sibling_offset):
            self.read_bone_block(sibling_offset)

    def read_mh2_pc_material_ids(self, obj_off, count):
        f = self.file
        records = []
        start = obj_off + 180
        if count <= 0:
            return records
        cur = f.tell()
        try:
            f.seek(start)
            for material_index in range(int(count)):
                row = f.read(self.MH2_PC_MATERIAL_ID_SIZE)
                if len(row) < self.MH2_PC_MATERIAL_ID_SIZE:
                    break
                try:
                    (
                        bb_min_x, bb_min_y, bb_min_z,
                        bb_max_x, bb_max_y, bb_max_z,
                        num_face_indices, material_id, start_face_index, unknown
                    ) = struct.unpack_from("<6f4H", row, 0)
                except Exception:
                    continue
                records.append({
                    "index": material_index,
                    "bounds_min": (bb_min_x, bb_min_y, bb_min_z),
                    "bounds_max": (bb_max_x, bb_max_y, bb_max_z),
                    "num_face_indices": int(num_face_indices),
                    "num_faces": int(num_face_indices) // 3,
                    "material_id": int(material_id),
                    "start_face_index": int(start_face_index),
                    "start_face": int(start_face_index) // 3,
                    "unknown": int(unknown),
                })
        finally:
            f.seek(cur)
        return records

    def parent_mesh_to_armature(self, obj):
        if obj is None or self.armature_obj is None:
            return False
        try:
            obj.parent = self.armature_obj
            obj.matrix_parent_inverse = self.armature_obj.matrix_world.inverted()
        except Exception as exc:
            self.log(f"MH2 PC parent warning: failed to parent '{getattr(obj, 'name', '<mesh>')}' to armature: {exc}")
            return False

        try:
            modifier = None
            for existing in obj.modifiers:
                if existing.type == "ARMATURE" and getattr(existing, "object", None) == self.armature_obj:
                    modifier = existing
                    break
            if modifier is None:
                modifier = obj.modifiers.new(name="BLeeds_MH2_Armature", type="ARMATURE")
                modifier.object = self.armature_obj
            try:
                modifier.show_in_editmode = True
                modifier.show_on_cage = True
            except Exception:
                pass
        except Exception as exc:
            self.log(f"MH2 PC parent warning: failed to add armature modifier to '{getattr(obj, 'name', '<mesh>')}': {exc}")

        obj["bleeds_mh2_pc_child_of_armature"] = True
        obj["bleeds_mh2_pc_armature_name"] = self.armature_obj.name
        if obj not in self.imported_mesh_objects:
            self.imported_mesh_objects.append(obj)
        return True

    def read_object(self, idx, info):
        f = self.file
        obj_off = info["object_data_offset"]
        f.seek(obj_off)
        header = f.read(180)
        if len(header) < 180:
            return None

        unpacked = struct.unpack("<3I f I 3f 2I 3I 3f f 3f I 3I I 11I I 8I", header)
        material_offset = unpacked[0]
        num_materials = unpacked[1]
        num_material_ids = unpacked[11]
        num_face_index = unpacked[12]
        num_vertices = unpacked[20]
        vertex_stride = unpacked[24]
        rest = unpacked[25:]
        vertex_element_type = rest[11]

        index_count = max(0, int(num_face_index))
        tri_count = index_count // 3
        material_id_records = self.read_mh2_pc_material_ids(obj_off, num_material_ids)
        face_start = obj_off + 180 + (num_material_ids * self.MH2_PC_MATERIAL_ID_SIZE)
        f.seek(face_start)
        faces = []
        for face_index in range(tri_count):
            tri = f.read(6)
            if len(tri) < 6:
                break
            a, b, c = struct.unpack("<3H", tri)
            if a < num_vertices and b < num_vertices and c < num_vertices:
                faces.append((a, b, c))

        vertex_start = face_start + (tri_count * 6)
        f.seek(vertex_start)
        parent_bone_offset = info.get("parent_bone_offset", 0)
        parent_bone_info = self.bone_map.get(parent_bone_offset)
        verts, uvs, vertex_stats = self.read_vertex_stride(vertex_element_type, vertex_stride, num_vertices, parent_bone_info)

        materials = []
        if material_offset and num_materials > 0 and self.is_valid_offset(material_offset, 0x40):
            f.seek(material_offset)
            for material_index in range(num_materials):
                row = f.read(16)
                if len(row) < 16:
                    break
                tex_off, loaded = struct.unpack("<IB", row[:5])
                color = struct.unpack("4B", row[5:9])
                tex_name = self.read_c_string(tex_off) if self.is_valid_offset(tex_off, 0x40) else ""
                materials.append({"tex_name": tex_name, "color": color, "loaded": loaded})

        parent_name = self.bone_map.get(parent_bone_offset, {}).get("name", "")
        mesh_name = f"{self.stem}_{idx}"
        if parent_name:
            mesh_name = f"{self.stem}_{idx}_{parent_name}"

        obj = self.make_mesh(mesh_name, [tuple(v) for v in verts], faces, uvs, materials, material_id_records)
        if obj is not None:
            obj["bleeds_mh2_pc_objinfo_offset"] = int(info.get("objinfo_offset", 0))
            obj["bleeds_mh2_pc_object_data_offset"] = int(obj_off)
            obj["bleeds_mh2_pc_parent_bone_offset"] = int(parent_bone_offset)
            obj["bleeds_mh2_pc_parent_bone_name"] = parent_name
            obj["bleeds_mh2_pc_vertex_element_type"] = int(vertex_element_type)
            obj["bleeds_mh2_pc_vertex_stride"] = int(vertex_stride)
            obj["bleeds_mh2_pc_num_vertices"] = int(num_vertices)
            obj["bleeds_mh2_pc_num_face_indices"] = int(num_face_index)
            obj["bleeds_mh2_pc_vertex_start"] = int(vertex_start)
            obj["bleeds_mh2_pc_mesh_space"] = "parent_bone_world" if parent_bone_info else "source_blender"
            self.parent_mesh_to_armature(obj)
        parent_status = "armature-child" if (obj is not None and getattr(obj, "parent", None) == self.armature_obj) else "unparented"
        self.log(
            f"MH2 PC Mesh[{idx:02d}] '{mesh_name}' object=0x{obj_off:08X} "
            f"parent=0x{parent_bone_offset:08X} '{parent_name}' verts={len(verts)}/{num_vertices} "
            f"faces={len(faces)}/{tri_count} stride={vertex_stride} vet=0x{vertex_element_type:X} "
            f"matid_count={num_material_ids} matid_size={self.MH2_PC_MATERIAL_ID_SIZE} "
            f"face_start=0x{face_start:08X} vertex_start=0x{vertex_start:08X} "
            f"space={'parent-bone-world' if parent_bone_info else 'source-blender'} "
            f"object_parent={parent_status} "
            f"bounds={vertex_stats.get('bounds_text', 'n/a')}"
        )
        for record in material_id_records:
            self.log(
                f"    MatID[{record.get('index', 0):02d}] faces={record.get('num_faces', 0)} "
                f"material={record.get('material_id', 0)} start_face={record.get('start_face', 0)} "
                f"raw_indices={record.get('num_face_indices', 0)} raw_start={record.get('start_face_index', 0)} "
                f"unknown=0x{record.get('unknown', 0):04X}"
            )
        return obj

    def read_c_string(self, offset):
        f = self.file
        cur = f.tell()
        if not self.is_valid_offset(offset, 0):
            return ""
        f.seek(offset)
        text = bytearray()
        while True:
            b = f.read(1)
            if not b or b == b"\x00":
                break
            text += b
        f.seek(cur)
        return text.decode("ascii", errors="replace")

    def vertex_position_offset(self, data, stride):
        if len(data) < 16:
            return 0
        first_word = struct.unpack_from("<I", data, 0)[0]
        color_like = first_word in (0xFF000000, 0x000000FF)
        if not color_like:
            return 0
        try:
            x0, y0, z0 = struct.unpack_from("<3f", data, 0)
            x1, y1, z1 = struct.unpack_from("<3f", data, 4)
        except Exception:
            return 0
        first_valid = all(math.isfinite(v) and abs(v) < 10000.0 for v in (x0, y0, z0))
        second_valid = all(math.isfinite(v) and abs(v) < 10000.0 for v in (x1, y1, z1))
        if second_valid and not first_valid:
            return 4
        if second_valid and (abs(x0) > 100.0 or abs(y0) > 100.0 or abs(z0) > 100.0):
            return 4
        return 0

    def vertex_uv_offset(self, stride, position_offset):
        if stride >= 52:
            return 32 + position_offset
        if stride == 40:
            return 28 + position_offset
        if stride == 32:
            return 20 + position_offset
        return None

    def read_vertex_stride(self, vertex_element_type, vertex_stride, count, parent_bone_info=None):
        f = self.file
        verts = []
        uvs = None

        if vertex_stride <= 0:
            if vertex_element_type == 0x52:
                vertex_stride = 24
            elif vertex_element_type == 0x152:
                vertex_stride = 32
            elif vertex_element_type == 0x252:
                vertex_stride = 40
            elif vertex_element_type == 0x115E:
                vertex_stride = 52
            elif vertex_element_type == 0x125E:
                vertex_stride = 60
            else:
                raise ValueError(f"Unknown MH2 PC VertexElementType: 0x{vertex_element_type:X}")

        parent_matrix = None
        if parent_bone_info is not None:
            parent_matrix = parent_bone_info.get("matrix")

        min_v = Vector((999999.0, 999999.0, 999999.0))
        max_v = Vector((-999999.0, -999999.0, -999999.0))
        skipped = 0

        for vertex_index in range(count):
            data = f.read(vertex_stride)
            if len(data) < vertex_stride:
                break

            position_offset = 0
            if position_offset + 12 > len(data):
                skipped += 1
                continue

            pos = struct.unpack_from("<3f", data, position_offset)
            if not all(math.isfinite(v) and abs(v) < 100000.0 for v in pos):
                skipped += 1
                continue

            local_blender = self.source_vector_to_blender(pos)
            if parent_matrix is not None:
                out_pos = parent_matrix @ local_blender
            else:
                out_pos = local_blender
            verts.append(out_pos)

            min_v.x = min(min_v.x, out_pos.x)
            min_v.y = min(min_v.y, out_pos.y)
            min_v.z = min(min_v.z, out_pos.z)
            max_v.x = max(max_v.x, out_pos.x)
            max_v.y = max(max_v.y, out_pos.y)
            max_v.z = max(max_v.z, out_pos.z)

            uv_offset = self.vertex_uv_offset(vertex_stride, position_offset)
            if uv_offset is not None and uv_offset + 8 <= len(data):
                uv = struct.unpack_from("<2f", data, uv_offset)
                if all(math.isfinite(v) and abs(v) < 10000.0 for v in uv):
                    if uvs is None:
                        uvs = []
                    uvs.append((uv[0], 1.0 - uv[1]))
                elif uvs is not None:
                    uvs.append((0.0, 0.0))
            elif uvs is not None:
                uvs.append((0.0, 0.0))

        if verts:
            bounds_text = (
                f"min=({min_v.x:.6f},{min_v.y:.6f},{min_v.z:.6f}) "
                f"max=({max_v.x:.6f},{max_v.y:.6f},{max_v.z:.6f})"
            )
        else:
            bounds_text = "empty"

        return verts, uvs, {
            "skipped_vertices": skipped,
            "bounds_text": bounds_text,
        }

    def make_mesh(self, name, verts, faces, uvs, materials, material_id_records=None):
        import bpy

        if not verts:
            return None

        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(verts, [], faces)
        mesh.update()

        if uvs and len(uvs) >= len(verts):
            uv_layer = mesh.uv_layers.new(name="UVMap")
            for poly in mesh.polygons:
                for loop_index in poly.loop_indices:
                    vertex_index = mesh.loops[loop_index].vertex_index
                    if vertex_index < len(uvs):
                        uv_layer.data[loop_index].uv = uvs[vertex_index]

        for material_info in materials:
            material_name = material_info.get("tex_name") or "Material"
            material = bpy.data.materials.get(material_name) or bpy.data.materials.new(material_name)
            material.use_nodes = True
            mesh.materials.append(material)

        if material_id_records:
            for record in material_id_records:
                material_index = int(record.get("material_id", 0))
                start_face = int(record.get("start_face", 0))
                num_faces = int(record.get("num_faces", 0))
                end_face = start_face + num_faces
                for polygon_index in range(start_face, end_face):
                    if polygon_index < len(mesh.polygons):
                        if material_index < len(mesh.materials):
                            mesh.polygons[polygon_index].material_index = material_index

        obj = bpy.data.objects.new(name, mesh)
        self.collection.objects.link(obj)
        obj["bleeds_model_game"] = "MH2"
        obj["bleeds_mh2_platform"] = "PC"
        obj["bleeds_mdl_filepath"] = self.path

        return obj

def import_mh2(path, context, collection_name=None):
    return Mh2MdlReader(path, context, collection_name).run()
