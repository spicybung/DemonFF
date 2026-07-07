# DemonFF - Blender scripts for working with Renderware & R*/SA-MP/open.mp formats in Blender
# 2023 - 2026 spicybung

# This is a fork of DragonFF by Parik27 - maintained by Psycrow, and various others!
# Check it out at: https://github.com/Parik27/DragonFF

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
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Any

import bpy
from mathutils import Matrix, Vector

from ..gtaLib import mdl as stories_mdl
from .mdl_blender_api import ensureMeshAttribute, getMeshAttribute, removeMeshAttribute, getOrCreateCornerColorLayer, setActiveObject, safeSelectObject

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
# • https://libertycity.net/files/gta-liberty-city-stories/48612-yet-another-img-editor.html (GTA3xx .img: .mdls, textures, animations)
# • https://gtaforums.com/topic/838537-lcsvcs-dir-files/
# • https://gtaforums.com/topic/285544-gtavcslcs-modding/
# • https://thegtaplace.com/forums/topic/12002-gtavcslcs-modding/
# • http://aap.papnet.eu/gta/RE/lcs_pipes.txt (a brief binary rundown of how bitflags work for PS2/PSP/Mobile Stories games)
# • https://libertycity.net/articles/gta-vice-city-stories/6773-how-one-of-the-best-grand-theft-auto.html
# • https://umdatabase.net/view.php?id=CB00495D (database collection of Grand Theft Auto prototypes)
# • https://www.ign.com/articles/2005/09/10/gta-liberty-city-stories-2 ( ...it's IGN, but old IGN at least)
# • https://lcsteam.net/community/forum/index.php/topic,337.msg9335.html#msg9335 (RW 3.7/4.0, .MDL's, .WRLD's, .BSP's... )
# • https://www.gamedeveloper.com/programming/opinion-why-on-earth-would-we-write-our-own-game-engine- (Renderwares fate)

@dataclass
class StoriesImportContext:
    filepath: str
    platform: str
    mdl_type: str
    shrink: int
    import_type: int
    atomic: Any
    debug_log: List[str] = field(default_factory=list)

    def log(self, msg: str) -> None:
        self.debug_log.append(str(msg))
        print(msg)

MATERIAL_CACHE: Dict[str, bpy.types.Material] = {}

def getArmatureFrameMatrix(arm_info: Any, dict_name: str, ptr: int, fallback: Matrix = None) -> Matrix:
    if fallback is None:
        fallback = Matrix.Identity(4)
    try:
        matrix_dict = getattr(arm_info, dict_name, None)
        if matrix_dict is not None and ptr in matrix_dict and matrix_dict[ptr] is not None:
            return matrix_dict[ptr].copy()
    except Exception:
        pass
    return fallback.copy()

def getFrameMatrixOffsets(arm_info: Any, ptr: int) -> Tuple[int, int]:
    local_offset = 0
    global_offset = 0
    try:
        local_offset = int(getattr(arm_info, "frame_matrix_local_offsets", {}).get(ptr, 0) or 0)
    except Exception:
        local_offset = 0
    try:
        global_offset = int(getattr(arm_info, "frame_matrix_global_offsets", {}).get(ptr, 0) or 0)
    except Exception:
        global_offset = 0
    return local_offset, global_offset

def getFrameLinkPointers(arm_info: Any, ptr: int) -> Tuple[int, int, int]:
    parent_ptr = 0
    child_ptr = 0
    sibling_ptr = 0
    try:
        parent_ptr = int(getattr(arm_info, "frame_parent_ptrs", {}).get(ptr, 0) or 0)
    except Exception:
        parent_ptr = 0
    try:
        child_ptr = int(getattr(arm_info, "frame_child_ptrs", {}).get(ptr, 0) or 0)
    except Exception:
        child_ptr = 0
    try:
        sibling_ptr = int(getattr(arm_info, "frame_sibling_ptrs", {}).get(ptr, 0) or 0)
    except Exception:
        sibling_ptr = 0
    return parent_ptr, child_ptr, sibling_ptr

def writeMdlImportedFrameMatrixAttributes(owner: Any, ptr: int, name: str, arm_info: Any) -> None:
    if owner is None or arm_info is None:
        return

    local_matrix = getArmatureFrameMatrix(arm_info, "frame_mats_local", ptr)
    global_matrix = getArmatureFrameMatrix(arm_info, "frame_mats_global", ptr, getArmatureFrameMatrix(arm_info, "frame_mats_world", ptr))
    world_matrix = getArmatureFrameMatrix(arm_info, "frame_mats_world", ptr, global_matrix)
    computed_world_matrix = getArmatureFrameMatrix(arm_info, "frame_mats_computed_world", ptr, world_matrix)
    local_offset, global_offset = getFrameMatrixOffsets(arm_info, ptr)
    parent_ptr, child_ptr, sibling_ptr = getFrameLinkPointers(arm_info, ptr)

    owner["bleeds_frame_ptr"] = int(ptr)
    owner["bleeds_frame_name"] = str(name)

    owner["bleeds_frame_matrix"] = flattenMatrixForMdlProperty(global_matrix)
    owner["bleeds_frame_local_matrix"] = flattenMatrixForMdlProperty(local_matrix)

    owner["bleeds_mdl_import_frame_ptr"] = int(ptr)
    owner["bleeds_mdl_import_frame_name"] = str(name)
    owner["bleeds_mdl_import_local_matrix"] = flattenMatrixForMdlProperty(local_matrix)
    owner["bleeds_mdl_import_global_matrix"] = flattenMatrixForMdlProperty(global_matrix)
    owner["bleeds_mdl_computed_world_matrix"] = flattenMatrixForMdlProperty(computed_world_matrix)
    owner["bleeds_mdl_export_local_matrix"] = flattenMatrixForMdlProperty(local_matrix)
    owner["bleeds_mdl_export_world_matrix"] = flattenMatrixForMdlProperty(global_matrix)
    owner["bleeds_mdl_import_local_matrix_offset"] = int(local_offset)
    owner["bleeds_mdl_import_global_matrix_offset"] = int(global_offset)
    owner["bleeds_mdl_import_parent_frame_ptr"] = int(parent_ptr)
    owner["bleeds_mdl_import_child_frame_ptr"] = int(child_ptr)
    owner["bleeds_mdl_import_sibling_frame_ptr"] = int(sibling_ptr)
    try:
        owner["bleeds_mdl_import_frame_tag"] = int(getattr(arm_info, "frame_tags", {}).get(ptr, 0)) & 0xFFFFFFFF
        owner["bleeds_mdl_import_root_frame_ptr"] = int(getattr(arm_info, "frame_root_ptrs", {}).get(ptr, 0)) & 0xFFFFFFFF
        owner["bleeds_mdl_import_frame_field_9c"] = int(getattr(arm_info, "frame_field_9c", {}).get(ptr, 0)) & 0xFFFFFFFF
        owner["bleeds_mdl_import_frame_field_a0"] = int(getattr(arm_info, "frame_field_a0", {}).get(ptr, 0)) & 0xFFFFFFFF
        owner["bleeds_mdl_import_frame_field_a4"] = int(getattr(arm_info, "frame_field_a4", {}).get(ptr, 0)) & 0xFFFFFFFF
    except Exception:
        pass

def writeBlenderRestMatrixAttributes(owner: Any, arm_data: Any, bone_name: str) -> None:
    if owner is None or arm_data is None or not bone_name:
        return
    try:
        bone = arm_data.bones.get(str(bone_name))
    except Exception:
        bone = None
    if bone is None:
        return

    try:
        global_matrix = bone.matrix_local.copy()
    except Exception:
        global_matrix = Matrix.Identity(4)

    try:
        if bone.parent is not None:
            local_matrix = bone.parent.matrix_local.inverted_safe() @ bone.matrix_local
        else:
            local_matrix = bone.matrix_local.copy()
    except Exception:
        local_matrix = Matrix.Identity(4)

    try:
        owner["bleeds_blender_import_global_matrix"] = flattenMatrixForMdlProperty(global_matrix)
        owner["bleeds_blender_import_local_matrix"] = flattenMatrixForMdlProperty(local_matrix)
        owner["bleeds_blender_rest_global_matrix"] = flattenMatrixForMdlProperty(global_matrix)
        owner["bleeds_blender_rest_local_matrix"] = flattenMatrixForMdlProperty(local_matrix)
    except Exception:
        pass

def alignEditBoneToFrameMatrix(edit_bone: Any, world_mat: Matrix, *, default_length: float = 0.1) -> None:
    if edit_bone is None or world_mat is None:
        return

    try:
        head = world_mat.to_translation()
    except Exception:
        head = Vector((0.0, 0.0, 0.0))

    try:
        basis = world_mat.to_3x3()
        y_axis = Vector((basis[0][1], basis[1][1], basis[2][1]))
        z_axis = Vector((basis[0][2], basis[1][2], basis[2][2]))
        x_axis = Vector((basis[0][0], basis[1][0], basis[2][0]))
    except Exception:
        y_axis = Vector((0.0, 1.0, 0.0))
        z_axis = Vector((0.0, 0.0, 1.0))
        x_axis = Vector((1.0, 0.0, 0.0))

    if y_axis.length <= 0.000001:
        y_axis = Vector((0.0, 1.0, 0.0))
    else:
        y_axis.normalize()

    if z_axis.length <= 0.000001:
        z_axis = Vector((0.0, 0.0, 1.0))
    else:
        z_axis.normalize()

    try:
        edit_bone.head = head
        edit_bone.tail = head + (y_axis * float(default_length))
        if abs(float(y_axis.dot(z_axis))) > 0.999:
            if x_axis.length <= 0.000001:
                x_axis = Vector((1.0, 0.0, 0.0))
            else:
                x_axis.normalize()
            z_axis = y_axis.cross(x_axis)
            if z_axis.length <= 0.000001:
                z_axis = Vector((0.0, 0.0, 1.0))
            else:
                z_axis.normalize()
        edit_bone.align_roll(z_axis)
    except Exception:
        try:
            edit_bone.head = head
            edit_bone.tail = head + Vector((0.0, float(default_length), 0.0))
        except Exception:
            pass

def writeMdlArmatureFrameMatrixArrays(owner: Any, arm_info: Any) -> None:
    if owner is None or arm_info is None:
        return

    frame_names_by_ptr = dict(getattr(arm_info, "frame_names", {}) or {})
    ptrs = [int(ptr) for ptr in frame_names_by_ptr.keys()]
    names = [str(frame_names_by_ptr[ptr]) for ptr in frame_names_by_ptr.keys()]

    local_values = []
    global_values = []
    world_values = []
    computed_values = []
    local_offsets = []
    global_offsets = []
    parent_ptrs = []
    child_ptrs = []
    sibling_ptrs = []
    root_ptrs = []
    frame_tags = []
    frame_field_9c = []
    frame_field_a0 = []
    frame_field_a4 = []

    for ptr in frame_names_by_ptr.keys():
        local_matrix = getArmatureFrameMatrix(arm_info, "frame_mats_local", ptr)
        global_matrix = getArmatureFrameMatrix(arm_info, "frame_mats_global", ptr, getArmatureFrameMatrix(arm_info, "frame_mats_world", ptr))
        world_matrix = getArmatureFrameMatrix(arm_info, "frame_mats_world", ptr, global_matrix)
        computed_world_matrix = getArmatureFrameMatrix(arm_info, "frame_mats_computed_world", ptr, world_matrix)
        local_offset, global_offset = getFrameMatrixOffsets(arm_info, ptr)
        parent_ptr, child_ptr, sibling_ptr = getFrameLinkPointers(arm_info, ptr)

        local_values.extend(flattenMatrixForMdlProperty(local_matrix))
        global_values.extend(flattenMatrixForMdlProperty(global_matrix))
        world_values.extend(flattenMatrixForMdlProperty(world_matrix))
        computed_values.extend(flattenMatrixForMdlProperty(computed_world_matrix))
        local_offsets.append(int(local_offset))
        global_offsets.append(int(global_offset))
        parent_ptrs.append(int(parent_ptr))
        child_ptrs.append(int(child_ptr))
        sibling_ptrs.append(int(sibling_ptr))
        root_ptrs.append(int(getattr(arm_info, "frame_root_ptrs", {}).get(ptr, 0)) & 0xFFFFFFFF)
        frame_tags.append(int(getattr(arm_info, "frame_tags", {}).get(ptr, 0)) & 0xFFFFFFFF)
        frame_field_9c.append(int(getattr(arm_info, "frame_field_9c", {}).get(ptr, 0)) & 0xFFFFFFFF)
        frame_field_a0.append(int(getattr(arm_info, "frame_field_a0", {}).get(ptr, 0)) & 0xFFFFFFFF)
        frame_field_a4.append(int(getattr(arm_info, "frame_field_a4", {}).get(ptr, 0)) & 0xFFFFFFFF)

    owner["bleeds_mdl_armature_matrix_schema"] = "FRAME_IMPORTED_LOCAL_GLOBAL_FLAT_4X4"
    owner["bleeds_mdl_frame_ptrs"] = ptrs
    owner["bleeds_mdl_frame_names"] = names
    owner["bleeds_mdl_frame_local_matrices"] = local_values
    owner["bleeds_mdl_frame_world_matrices"] = world_values
    owner["bleeds_mdl_frame_global_matrices"] = global_values
    owner["bleeds_mdl_frame_import_local_matrices"] = local_values
    owner["bleeds_mdl_frame_import_global_matrices"] = global_values
    owner["bleeds_mdl_frame_computed_world_matrices"] = computed_values
    owner["bleeds_mdl_frame_local_matrix_offsets"] = local_offsets
    owner["bleeds_mdl_frame_global_matrix_offsets"] = global_offsets
    owner["bleeds_mdl_frame_parent_ptrs"] = parent_ptrs
    owner["bleeds_mdl_frame_child_ptrs"] = child_ptrs
    owner["bleeds_mdl_frame_sibling_ptrs"] = sibling_ptrs
    owner["bleeds_mdl_frame_root_ptrs"] = root_ptrs
    owner["bleeds_mdl_frame_tags"] = frame_tags
    owner["bleeds_mdl_frame_field_9c"] = frame_field_9c
    owner["bleeds_mdl_frame_field_a0"] = frame_field_a0
    owner["bleeds_mdl_frame_field_a4"] = frame_field_a4

def _material_cache_get_valid(key: str):
    mat = MATERIAL_CACHE.get(key)
    if mat is None:
        return None
    try:
        _ = mat.name
        return mat
    except Exception:
        try:
            MATERIAL_CACHE.pop(key, None)
        except Exception:
            pass
        return None

def get_bone_name_list(import_type: int) -> List[str]:
    names: List[str] = []

    if import_type in (0, 1):

        for name in stories_mdl.commonBoneNamesLCS:
            names.append(name)
    elif import_type in (2, 3):

        for name in stories_mdl.commonBoneNamesVCS:
            names.append(name)
    else:

        for i in range(32):
            names.append(f"bone_{i:02d}")

    return names

def get_bone_parent_map(import_type: int) -> Dict[str, str]:
    if import_type in (0, 1):
        return dict(stories_mdl.commonBoneParentsLCS)
    if import_type in (2, 3):
        return dict(stories_mdl.commonBoneParentsVCS)
    return {}

def create_armature_from_context(
    context: bpy.types.Context,
    stories_ctx: Any,
    collection: bpy.types.Collection,
    name_suffix: str,
) -> bpy.types.Object:
    atomic = stories_ctx.atomic
    arm_info = atomic.armature

    if arm_info is None or not getattr(arm_info, 'frame_names', None):
        return None

    view_layer = context.view_layer
    old_active = view_layer.objects.active
    old_mode = context.mode

    base_name = os.path.splitext(os.path.basename(stories_ctx.filepath))[0]
    arm_data = bpy.data.armatures.new(f"{base_name}_{name_suffix}")
    arm_obj = bpy.data.objects.new(arm_data.name, arm_data)
    collection.objects.link(arm_obj)

    view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")

    bone_parent_map = get_bone_parent_map(stories_ctx.import_type)
    name_to_edit_bone: Dict[str, bpy.types.EditBone] = {}
    ptr_to_edit_bone: Dict[int, bpy.types.EditBone] = {}
    mdl_type_u = str(getattr(stories_ctx, "mdl_type", "") or "").upper().strip()

    for ptr, name in arm_info.frame_names.items():
        if ptr not in arm_info.frame_mats_world:
            continue
        if mdl_type_u == "CUT" and not isCutsceneActorBodyBoneName(str(name)):
            continue

        world_mat = arm_info.frame_mats_world[ptr]

        edit_bone = arm_data.edit_bones.new(name)
        alignEditBoneToFrameMatrix(edit_bone, world_mat, default_length=0.1)

        name_to_edit_bone[name] = edit_bone
        ptr_to_edit_bone[int(ptr)] = edit_bone

    for ptr, edit_bone in ptr_to_edit_bone.items():
        try:
            parent_ptr = int(getattr(arm_info, "frame_parent_ptrs", {}).get(ptr, 0) or 0)
        except Exception:
            parent_ptr = 0
        if parent_ptr and parent_ptr in ptr_to_edit_bone and parent_ptr != ptr:
            edit_bone.parent = ptr_to_edit_bone[parent_ptr]

    for name, edit_bone in name_to_edit_bone.items():
        if edit_bone.parent is not None:
            continue
        parent_name = bone_parent_map.get(name)
        if parent_name and parent_name in name_to_edit_bone:
            edit_bone.parent = name_to_edit_bone[parent_name]

    bpy.ops.object.mode_set(mode="OBJECT")

    try:
        for ptr, name in arm_info.frame_names.items():
            bone = arm_data.bones.get(name)
            if bone is None:
                continue
            writeMdlImportedFrameMatrixAttributes(bone, int(ptr), str(name), arm_info)
            writeBlenderRestMatrixAttributes(bone, arm_data, str(name))
            try:
                canon_name = stories_mdl.canon_frame_name(str(name))
                id_map, type_map = stories_mdl._ped_known_hanim_maps(stories_ctx.import_type)
                if canon_name in id_map:
                    anim_bone_id = int(id_map[canon_name])
                    bone["BoneID"] = anim_bone_id
                    bone["bleeds_hanim_bone_id"] = anim_bone_id
                    bone["bleeds_anim_bone_id"] = anim_bone_id
                    bone["bleeds_mdl_anim_bone_id"] = anim_bone_id
                else:
                    bone_names = get_bone_name_list(stories_ctx.import_type)
                    if str(name) in bone_names:
                        anim_bone_id = int(bone_names.index(str(name)))
                        bone["BoneID"] = anim_bone_id
                        bone["bleeds_anim_bone_id"] = anim_bone_id
                        bone["bleeds_mdl_anim_bone_id"] = anim_bone_id
                if canon_name in type_map:
                    bone["BoneType"] = int(type_map[canon_name])
                    bone["bleeds_hanim_bone_type"] = int(type_map[canon_name])
            except Exception:
                pass
    except Exception:
        pass

    try:
        frame_names_by_ptr = dict(getattr(arm_info, "frame_names", {}) or {})
        writeMdlArmatureFrameMatrixArrays(arm_obj, arm_info)
        writeMdlArmatureFrameMatrixArrays(arm_data, arm_info)
        stampPs2PedSkinPaletteAttributes(arm_obj, stories_ctx.import_type, arm_obj)
        stampPs2PedSkinPaletteAttributes(arm_data, stories_ctx.import_type, arm_obj)
        try:
            hierarchy_order = buildPedHierarchyNodeOrder(
                arm_info,
                filepath=str(getattr(stories_ctx, "filepath", "") or ""),
                hierarchy_ptr=int(getattr(atomic, "hierarchy_ptr", 0) or 0),
            )
            writePedHierarchyNodeAttributes(arm_obj, hierarchy_order)
            writePedHierarchyNodeAttributes(arm_data, hierarchy_order)
            hierarchy_by_name, hierarchy_by_node = buildPedHierarchyEntryMaps(arm_info)
            for node_index, (_node_ptr, node_name) in enumerate(hierarchy_order):
                bone = arm_data.bones.get(str(node_name))
                if bone is not None:
                    bone["bleeds_mdl_hierarchy_node_index"] = int(node_index)
                    bone["node_index"] = int(node_index)
                    bone["bleeds_anim_table_index"] = int(node_index)
                    entry = hierarchy_by_name.get(stories_mdl.canon_frame_name(str(node_name)))
                    if entry is None:
                        entry = hierarchy_by_node.get(int(node_index))
                    if entry is not None:
                        writeRawPedHierarchyBoneIdAttributes(bone, entry)
        except Exception:
            pass
        try:
            atomic_frame_ptr = int(getattr(atomic, "frame_ptr", 0) or 0)
            arm_obj["bleeds_mdl_atomic_frame_ptr"] = atomic_frame_ptr
            if atomic_frame_ptr in frame_names_by_ptr:
                arm_obj["bleeds_mdl_atomic_frame_name"] = str(frame_names_by_ptr[atomic_frame_ptr])
                arm_obj["bleeds_base_frame_name"] = str(frame_names_by_ptr[atomic_frame_ptr])
        except Exception:
            pass
    except Exception:
        pass

    if old_active is not None:
        try:
            view_layer.objects.active = old_active
            bpy.ops.object.mode_set(mode=old_mode)
        except Exception:

            pass

    return arm_obj

def match_mesh_to_armature_space(
    obj: bpy.types.Object,
    stories_ctx: Any,
    arm_obj: bpy.types.Object,
) -> None:
    if arm_obj is None:
        return

    atomic = stories_ctx.atomic
    arm_info = atomic.armature
    frame_ptr = atomic.frame_ptr

    world_mat = arm_info.frame_mats_world.get(frame_ptr)
    if world_mat is not None:

        obj.matrix_world = world_mat

    for mod in list(obj.modifiers):
        if mod.type == "ARMATURE":
            obj.modifiers.remove(mod)

    arm_mod = obj.modifiers.new(name="Armature", type="ARMATURE")
    arm_mod.object = arm_obj

    obj.parent = arm_obj
    obj.matrix_parent_inverse = arm_obj.matrix_world.inverted()

def parent_object_keep_world(child_obj: bpy.types.Object, parent_obj: bpy.types.Object) -> None:
    if child_obj is None or parent_obj is None:
        return

    saved_world = child_obj.matrix_world.copy()
    child_obj.parent = parent_obj
    child_obj.matrix_parent_inverse = parent_obj.matrix_world.inverted()
    child_obj.matrix_world = saved_world

def flattenMatrixForMdlProperty(matrix_value: Matrix) -> List[float]:
    matrix = matrix_value.copy()
    if getattr(matrix, "size", 4) != 4:
        matrix = matrix.to_4x4()
    return [float(matrix[row][col]) for row in range(4) for col in range(4)]

def signedInt32ForIdProp(value):
    value = int(value) & 0xFFFFFFFF
    if value >= 0x80000000:
        value -= 0x100000000
    return value

def signedInt32ListForIdProp(values, count=None):
    result = []
    for value in list(values or []):
        result.append(signedInt32ForIdProp(value))
        if count is not None and len(result) >= int(count):
            break
    return result

def writeMdlPartMatrixProperties(mesh_obj: bpy.types.Object, part_index: int) -> None:
    if mesh_obj is None:
        return

    try:
        world_matrix = mesh_obj.matrix_world.copy()
    except Exception:
        world_matrix = Matrix.Identity(4)

    try:
        local_matrix = mesh_obj.matrix_local.copy()
    except Exception:
        local_matrix = Matrix.Identity(4)

    try:
        parent_inverse = mesh_obj.matrix_parent_inverse.copy()
    except Exception:
        parent_inverse = Matrix.Identity(4)

    try:
        parent_world = mesh_obj.parent.matrix_world.copy() if mesh_obj.parent is not None else Matrix.Identity(4)
    except Exception:
        parent_world = Matrix.Identity(4)

    props = {
        "bleeds_mdl_part_matrix_world": flattenMatrixForMdlProperty(world_matrix),
        "bleeds_mdl_part_matrix_local": flattenMatrixForMdlProperty(local_matrix),
        "bleeds_mdl_part_matrix_parent_inverse": flattenMatrixForMdlProperty(parent_inverse),
        "bleeds_mdl_part_matrix_parent_world": flattenMatrixForMdlProperty(parent_world),
        "bleeds_mdl_part_matrix_basis": flattenMatrixForMdlProperty(mesh_obj.matrix_basis.copy()),
        "bleeds_mdl_part_matrix_export_basis": flattenMatrixForMdlProperty(world_matrix),
        "bleeds_mdl_part_matrix_index": int(part_index),
    }

    for key, value in props.items():
        try:
            mesh_obj[key] = value
        except Exception:
            pass
        try:
            if getattr(mesh_obj, "data", None) is not None:
                mesh_obj.data[key] = value
        except Exception:
            pass
def get_or_create_material_for_stories(
    mat_desc: Any,
    index: int,
) -> bpy.types.Material:
    key = getattr(mat_desc, "texture", "") or f"StoriesMat_{index:03d}"
    cached = _material_cache_get_valid(key)
    if cached is not None:
        return cached

    mat = bpy.data.materials.new(name=key)
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    for n in list(nodes):
        nodes.remove(n)

    out = nodes.new(type="ShaderNodeOutputMaterial")
    out.location = (300, 0)

    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)

    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    rgba = getattr(mat_desc, "rgba", 0)
    r = (rgba & 0xFF) / 255.0
    g = ((rgba >> 8) & 0xFF) / 255.0
    b = ((rgba >> 16) & 0xFF) / 255.0
    a = ((rgba >> 24) & 0xFF) / 255.0 if rgba != 0 else 1.0

    bsdf.inputs["Base Color"].default_value = (r, g, b, a)

    MATERIAL_CACHE[key] = mat
    return mat

CUTSCENE_BODY_BONE_NAMES = {
    "root",
    "pelvis",
    "spine",
    "spine1",
    "neck",
    "head",
    "l_thigh",
    "l_calf",
    "l_foot",
    "l_toe0",
    "r_thigh",
    "r_calf",
    "r_foot",
    "r_toe0",
    "l_clavicle",
    "l_upperarm",
    "l_forearm",
    "l_hand",
    "l_finger",
    "l_finger0",
    "l_finger01",
    "r_clavicle",
    "r_upperarm",
    "r_forearm",
    "r_hand",
    "r_finger",
    "r_finger0",
    "r_finger01",
    "bip01_l_clavicle",
    "bip01_r_clavicle",
}

def normalizeCutsceneBoneName(name: str) -> str:
    cleaned = str(name or "").strip()
    if cleaned.startswith("Bip01 "):
        cleaned = cleaned[6:]
    return cleaned.lower()

def isCutsceneActorBodyBoneName(name: str) -> bool:
    normalized = normalizeCutsceneBoneName(name)
    if not normalized:
        return False
    if normalized in CUTSCENE_BODY_BONE_NAMES:
        return True

    if normalized.endswith("jnt") or normalized == "_footsteps":
        return False
    if normalized.endswith("geo") or normalized == "scene_root":
        return False
    return False

def getArmatureBoneNameSet(arm_obj: bpy.types.Object) -> set:
    try:
        if arm_obj is not None and getattr(arm_obj, "data", None) is not None:
            return {str(bone.name) for bone in arm_obj.data.bones}
    except Exception:
        pass
    return set()

def getImportedHierarchyBoneNames(arm_obj: bpy.types.Object) -> List[str]:
    names: List[str] = []
    if arm_obj is None:
        return names

    for owner in (arm_obj, getattr(arm_obj, "data", None)):
        if owner is None:
            continue
        try:
            if "bleeds_mdl_hierarchy_node_names" in owner:
                values = list(owner["bleeds_mdl_hierarchy_node_names"] or [])
                names = [str(value) for value in values if str(value)]
                if names:
                    return names
        except Exception:
            pass

    return names

def getCanonicalPedSkinPaletteBoneNames(import_type: int, arm_obj: bpy.types.Object = None) -> List[str]:
    names = [str(name) for name in get_bone_name_list(import_type)]
    if not names:
        return []

    if arm_obj is None:
        return names

    try:
        arm_bone_names = getArmatureBoneNameSet(arm_obj)
    except Exception:
        arm_bone_names = set()

    if not arm_bone_names:
        return names

    usable = 0
    for name in names:
        if str(name) in arm_bone_names:
            usable += 1

    if usable >= max(6, int(len(names) * 0.50)):
        return names

    return names

def getPs2PedSkinPaletteBoneNames(import_type: int, arm_obj: bpy.types.Object = None) -> List[str]:
    names = getCanonicalPedSkinPaletteBoneNames(import_type, arm_obj)
    if names:
        return names

    names = getImportedHierarchyBoneNames(arm_obj)
    if names:
        return names

    return get_bone_name_list(import_type)

def stampPs2PedSkinPaletteAttributes(owner: Any, import_type: int, arm_obj: bpy.types.Object = None) -> None:
    if owner is None:
        return
    try:
        names = getPs2PedSkinPaletteBoneNames(import_type, arm_obj)
        owner["bleeds_mdl_skin_palette_node_names"] = [str(name) for name in names]
        owner["bleeds_mdl_skin_palette_node_count"] = int(len(names))
        owner["bleeds_mdl_skin_palette_source"] = "CANONICAL_PED_HANIM_SKIN_TOKENS"
        owner["bleeds_mdl_skin_palette_note"] = (
            "PS2 PED 0x6C skin token index uses the canonical HAnim/ANIM palette; "
            "it is not the imported hierarchy traversal order."
        )
    except Exception:
        pass

def accumulateMdlVertexSkinWeight(
    assignments: Dict[int, Dict[str, float]],
    vertex_index: int,
    bone_index: int,
    weight: float,
    bone_names: List[str],
) -> None:
    try:
        vi = int(vertex_index)
        bi = int(bone_index)
        wf = float(weight)
    except Exception:
        return

    if vi < 0 or wf <= 0.0:
        return

    if 0 <= bi < len(bone_names):
        name = str(bone_names[bi])
    else:
        name = f"bone_{bi:02d}"

    if not name:
        return

    per_vertex = assignments.setdefault(vi, {})
    per_vertex[name] = float(per_vertex.get(name, 0.0)) + wf

def writeMdlVertexSkinAssignments(obj: bpy.types.Object, assignments: Dict[int, Dict[str, float]]) -> None:
    if obj is None or not assignments:
        return

    vertex_count = 0
    try:
        vertex_count = len(obj.data.vertices)
    except Exception:
        vertex_count = 0

    vg_by_name: Dict[str, bpy.types.VertexGroup] = {}

    def getVertexGroup(name: str) -> bpy.types.VertexGroup:
        if name not in vg_by_name:
            existing = obj.vertex_groups.get(name)
            if existing is not None:
                vg_by_name[name] = existing
            else:
                vg_by_name[name] = obj.vertex_groups.new(name=name)
        return vg_by_name[name]

    for vertex_index, name_weights in assignments.items():
        try:
            vi = int(vertex_index)
        except Exception:
            continue
        if vi < 0 or vi >= vertex_count:
            continue

        clean_pairs: List[Tuple[str, float]] = []
        for name, weight in name_weights.items():
            try:
                wf = float(weight)
            except Exception:
                continue
            if wf <= 0.0:
                continue
            clean_pairs.append((str(name), wf))

        if not clean_pairs:
            continue

        total = sum(weight for _name, weight in clean_pairs)
        if total <= 0.000001:
            continue

        for name, weight in clean_pairs:
            vg = getVertexGroup(name)
            vg.add([vi], float(weight) / float(total), "REPLACE")

def assign_ps2_skin_merged(
    obj: bpy.types.Object,
    parts: List[Any],
    part_vertex_offsets: List[int],
    import_type: int,
    arm_obj: bpy.types.Object,
) -> None:
    if arm_obj is None:
        return

    me = obj.data
    vertex_count = len(me.vertices)
    if vertex_count == 0:
        return

    obj.vertex_groups.clear()

    bone_names = getPs2PedSkinPaletteBoneNames(import_type, arm_obj)
    stampPs2PedSkinPaletteAttributes(obj, import_type, arm_obj)
    try:
        stampPs2PedSkinPaletteAttributes(obj.data, import_type, arm_obj)
    except Exception:
        pass

    assignments: Dict[int, Dict[str, float]] = {}

    for part_index, part in enumerate(parts):
        if part_index >= len(part_vertex_offsets):
            continue

        merged_part_base = int(part_vertex_offsets[part_index])
        strips_meta = list(getattr(part, "strips_meta", []) or [])
        for strip in strips_meta:
            base = int(getattr(strip, "base_vertex_index", 0) or 0)
            count = int(getattr(strip, "vertex_count", 0) or 0)

            if not getattr(strip, "skin_indices", None) or not getattr(strip, "skin_weights", None):
                continue

            for local_i in range(max(0, count)):
                vert_index = merged_part_base + base + local_i
                if vert_index < 0 or vert_index >= vertex_count:
                    continue
                if local_i >= len(strip.skin_indices) or local_i >= len(strip.skin_weights):
                    continue

                for bone_index, weight in zip(strip.skin_indices[local_i], strip.skin_weights[local_i]):
                    accumulateMdlVertexSkinWeight(assignments, vert_index, bone_index, weight, bone_names)

    writeMdlVertexSkinAssignments(obj, assignments)

def writeMergedPs2MdlSemanticAttributes(
    mesh: bpy.types.Mesh,
    parts: List[Any],
    part_vertex_offsets: List[int],
    part_face_offsets: List[int],
) -> None:
    if mesh is None:
        return

    try:
        mesh.update(calc_edges=True)
    except Exception:
        try:
            mesh.update()
        except Exception:
            pass

    face_part = ensureMdlIntAttribute(mesh, "bleeds_mdl_part_index", 'FACE')
    face_material = ensureMdlIntAttribute(mesh, "bleeds_mdl_material_index", 'FACE')
    face_strip = ensureMdlIntAttribute(mesh, "bleeds_mdl_source_strip_index", 'FACE')
    face_strip_tri = ensureMdlIntAttribute(mesh, "bleeds_mdl_source_strip_triangle_index", 'FACE')

    corner_emit = ensureMdlIntAttribute(mesh, "bleeds_mdl_corner_source_emit_index", 'CORNER')
    corner_export = ensureMdlIntAttribute(mesh, "bleeds_mdl_corner_source_export_vertex_index", 'CORNER')
    corner_strip = ensureMdlIntAttribute(mesh, "bleeds_mdl_corner_source_strip_index", 'CORNER')
    corner_strip_vertex = ensureMdlIntAttribute(mesh, "bleeds_mdl_corner_source_strip_vertex_index", 'CORNER')

    point_emit = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_source_emit_index", 'POINT')
    point_export = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_source_export_vertex_index", 'POINT')
    point_strip = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_source_strip_index", 'POINT')
    point_strip_vertex = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_source_strip_vertex_index", 'POINT')
    point_skin_raw0 = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_skin_raw0", 'POINT')
    point_skin_raw1 = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_skin_raw1", 'POINT')
    point_skin_raw2 = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_skin_raw2", 'POINT')
    point_skin_raw3 = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_skin_raw3", 'POINT')

    source_emit = 0
    part_vertex_counts = []
    part_face_counts = []
    part_material_ids = []
    part_strip_counts = []

    for part_index, part in enumerate(parts):
        merged_vertex_base = int(part_vertex_offsets[part_index]) if part_index < len(part_vertex_offsets) else 0
        merged_face_base = int(part_face_offsets[part_index]) if part_index < len(part_face_offsets) else 0
        material_id = int(getattr(part, "material_id", 0) or 0)
        strips_meta = list(getattr(part, "strips_meta", []) or [])
        skin_raw_dwords = list(getattr(part, "skin_raw_dwords", []) or [])
        part_faces = list(getattr(part, "faces", []) or [])

        part_vertex_counts.append(int(len(getattr(part, "verts", []) or [])))
        part_face_counts.append(int(len(part_faces)))
        part_material_ids.append(int(material_id))
        part_strip_counts.append(int(len(strips_meta)))

        vertex_to_strip: Dict[int, Tuple[int, int, int]] = {}
        for strip_index, strip in enumerate(strips_meta):
            base_vertex_index = int(getattr(strip, "base_vertex_index", 0) or 0)
            vertex_count = int(getattr(strip, "vertex_count", 0) or 0)
            for local_index in range(max(0, vertex_count)):
                local_vertex_index = base_vertex_index + local_index
                vertex_to_strip[int(local_vertex_index)] = (
                    int(strip_index),
                    int(local_index),
                    int(source_emit),
                )
                source_emit += 1

        for local_vertex_index in range(int(part_vertex_counts[-1])):
            global_vertex_index = merged_vertex_base + local_vertex_index
            if global_vertex_index < 0 or global_vertex_index >= len(mesh.vertices):
                continue

            strip_index, strip_vertex_index, emit_index = vertex_to_strip.get(
                local_vertex_index,
                (0, local_vertex_index, global_vertex_index),
            )
            setMdlIntAttributeValue(point_emit, global_vertex_index, emit_index)
            setMdlIntAttributeValue(point_export, global_vertex_index, local_vertex_index)
            setMdlIntAttributeValue(point_strip, global_vertex_index, strip_index)
            setMdlIntAttributeValue(point_strip_vertex, global_vertex_index, strip_vertex_index)

            raw4 = [0, 0, 0, 0]
            if 0 <= local_vertex_index < len(skin_raw_dwords):
                try:
                    raw4 = list(skin_raw_dwords[local_vertex_index])[:4]
                except Exception:
                    raw4 = [0, 0, 0, 0]
            while len(raw4) < 4:
                raw4.append(0)
            setMdlIntAttributeValue(point_skin_raw0, global_vertex_index, signedInt32ForIdProp(raw4[0]))
            setMdlIntAttributeValue(point_skin_raw1, global_vertex_index, signedInt32ForIdProp(raw4[1]))
            setMdlIntAttributeValue(point_skin_raw2, global_vertex_index, signedInt32ForIdProp(raw4[2]))
            setMdlIntAttributeValue(point_skin_raw3, global_vertex_index, signedInt32ForIdProp(raw4[3]))

        strip_triangle_lookup: Dict[Tuple[int, int, int], Tuple[int, int]] = {}
        for strip_index, strip in enumerate(strips_meta):
            base_vertex_index = int(getattr(strip, "base_vertex_index", 0) or 0)
            vertex_count = int(getattr(strip, "vertex_count", 0) or 0)
            triangle_order = 0
            for i in range(2, max(0, vertex_count)):
                if (i % 2) == 0:
                    tri = (base_vertex_index + i - 2, base_vertex_index + i - 1, base_vertex_index + i)
                else:
                    tri = (base_vertex_index + i - 1, base_vertex_index + i - 2, base_vertex_index + i)
                if tri[0] == tri[1] or tri[1] == tri[2] or tri[2] == tri[0]:
                    continue
                tri_key = tuple(int(v) for v in tri)
                strip_triangle_lookup[tri_key] = (int(strip_index), int(triangle_order))
                strip_triangle_lookup[(tri_key[1], tri_key[0], tri_key[2])] = (int(strip_index), int(triangle_order))
                triangle_order += 1

        fallback_triangle_order = 0
        for local_face_index, face in enumerate(part_faces):
            polygon_index = merged_face_base + local_face_index
            if polygon_index < 0 or polygon_index >= len(mesh.polygons):
                continue
            polygon = mesh.polygons[polygon_index]
            local_tri_vertices = tuple(int(v) for v in list(face)[:3])
            strip_index, strip_triangle_index = strip_triangle_lookup.get(
                local_tri_vertices,
                (0, fallback_triangle_order),
            )
            fallback_triangle_order += 1

            setMdlIntAttributeValue(face_part, polygon_index, part_index)
            setMdlIntAttributeValue(face_material, polygon_index, material_id)
            setMdlIntAttributeValue(face_strip, polygon_index, strip_index)
            setMdlIntAttributeValue(face_strip_tri, polygon_index, strip_triangle_index)

            for local_corner_index, loop_index in enumerate(polygon.loop_indices):
                loop_index = int(loop_index)
                if loop_index < 0 or loop_index >= len(mesh.loops):
                    continue
                global_vertex_index = int(mesh.loops[loop_index].vertex_index)
                local_vertex_index = global_vertex_index - merged_vertex_base
                src_strip_index, src_strip_vertex_index, emit_index = vertex_to_strip.get(
                    local_vertex_index,
                    (int(strip_index), int(local_corner_index), int(loop_index)),
                )
                setMdlIntAttributeValue(corner_emit, loop_index, emit_index)
                setMdlIntAttributeValue(corner_export, loop_index, local_vertex_index)
                setMdlIntAttributeValue(corner_strip, loop_index, src_strip_index)
                setMdlIntAttributeValue(corner_strip_vertex, loop_index, src_strip_vertex_index)

    try:
        mesh["bleeds_mdl_semantic_attributes_version"] = 2
        mesh["bleeds_mdl_semantic_attributes_origin"] = "IMPORTED_PS2_CUT_MERGED"
        mesh["bleeds_mdl_source_part_count"] = int(len(parts))
        mesh["bleeds_mdl_source_part_vertex_starts"] = [int(v) for v in part_vertex_offsets]
        mesh["bleeds_mdl_source_part_vertex_counts"] = [int(v) for v in part_vertex_counts]
        mesh["bleeds_mdl_source_part_face_starts"] = [int(v) for v in part_face_offsets]
        mesh["bleeds_mdl_source_part_face_counts"] = [int(v) for v in part_face_counts]
        mesh["bleeds_mdl_source_part_material_ids"] = [int(v) for v in part_material_ids]
        mesh["bleeds_mdl_source_part_strip_counts"] = [int(v) for v in part_strip_counts]
    except Exception:
        pass

def buildCutsceneActorPartsByMaterial(parts: List[Any]) -> List[Any]:
    grouped_parts: List[Any] = []
    material_to_group: Dict[int, Any] = {}

    for packet_index, part in enumerate(list(parts or [])):
        material_id = int(getattr(part, "material_id", 0) or 0)
        if material_id not in material_to_group:
            grouped = stories_mdl.StoriesPartGeom()
            grouped.material_id = material_id
            grouped.uv_scale = tuple(getattr(part, "uv_scale", (1.0, 1.0)) or (1.0, 1.0))
            grouped.geom_flags = int(getattr(part, "geom_flags", 0) or 0)
            grouped.strip_vertex_count_hint = 0
            grouped.source_packet_indices = []
            grouped.source_packet_material_ids = []
            grouped.source_packet_vertex_starts = []
            grouped.source_packet_face_starts = []
            grouped.source_packet_vertex_counts = []
            grouped.source_packet_face_counts = []
            grouped.normals = []
            grouped.skin_raw_dwords = []
            material_to_group[material_id] = grouped
            grouped_parts.append(grouped)

        grouped = material_to_group[material_id]
        vertex_base = len(grouped.verts)
        face_base = len(grouped.faces)

        verts = list(getattr(part, "verts", []) or [])
        faces = list(getattr(part, "faces", []) or [])
        uvs = list(getattr(part, "uvs", []) or [])
        colors = list(getattr(part, "vertex_colors", None) or getattr(part, "loop_colors", None) or [])
        normals = list(getattr(part, "normals", []) or [])
        skin_raw = list(getattr(part, "skin_raw_dwords", []) or [])

        grouped.source_packet_indices.append(int(packet_index))
        grouped.source_packet_material_ids.append(int(material_id))
        grouped.source_packet_vertex_starts.append(int(vertex_base))
        grouped.source_packet_face_starts.append(int(face_base))
        grouped.source_packet_vertex_counts.append(int(len(verts)))
        grouped.source_packet_face_counts.append(int(len(faces)))

        grouped.verts.extend(verts)
        for i in range(len(verts)):
            if i < len(uvs):
                grouped.uvs.append(uvs[i])
            else:
                grouped.uvs.append((0.0, 0.0))
            if i < len(colors):
                grouped.vertex_colors.append(colors[i])
            else:
                grouped.vertex_colors.append((255, 255, 255, 255))
            if i < len(normals):
                grouped.normals.append(normals[i])
            else:
                grouped.normals.append((0.0, 0.0, 1.0))
            if i < len(skin_raw):
                raw4 = list(skin_raw[i])[:4]
            else:
                raw4 = [0, 0, 0, 0]
            while len(raw4) < 4:
                raw4.append(0)
            grouped.skin_raw_dwords.append([int(v) & 0xFFFFFFFF for v in raw4[:4]])

        for face in faces:
            if len(face) < 3:
                continue
            grouped.faces.append(tuple(vertex_base + int(v) for v in list(face)[:3]))

        for strip in list(getattr(part, "strips_meta", []) or []):
            try:
                new_strip = stories_mdl.StripMeta(
                    base_vertex_index=vertex_base + int(getattr(strip, "base_vertex_index", 0) or 0),
                    vertex_count=int(getattr(strip, "vertex_count", 0) or 0),
                    skin_indices=[list(v) for v in list(getattr(strip, "skin_indices", []) or [])],
                    skin_weights=[list(v) for v in list(getattr(strip, "skin_weights", []) or [])],
                    skin_raw_dwords=[list(v) for v in list(getattr(strip, "skin_raw_dwords", []) or [])],
                )
                grouped.strips_meta.append(new_strip)
                grouped.strip_vertex_count_hint += int(new_strip.vertex_count)
            except Exception:
                pass

    return grouped_parts

def sanitizeVehicleObjectName(name: str) -> str:
    cleaned = str(name or "frame").replace(" ", "_")
    cleaned = "".join(ch if (ch.isalnum() or ch in "_-.") else "_" for ch in cleaned)
    return cleaned or "frame"

def createVehicleFrameObjects(
    stories_ctx: Any,
    collection: bpy.types.Collection,
) -> Tuple[List[bpy.types.Object], Dict[int, bpy.types.Object]]:
    atomic = getattr(stories_ctx, "atomic", None)
    arm_info = getattr(atomic, "armature", None) if atomic is not None else None
    if arm_info is None or not getattr(arm_info, "frame_names", None):
        return [], {}

    base_name = os.path.splitext(os.path.basename(stories_ctx.filepath))[0]
    frame_objects: Dict[int, bpy.types.Object] = {}
    created: List[bpy.types.Object] = []

    for ptr, frame_name in dict(getattr(arm_info, "frame_names", {}) or {}).items():
        ptr_i = int(ptr)
        safe_name = sanitizeVehicleObjectName(str(frame_name))
        obj = bpy.data.objects.new(f"{base_name}_frame_{safe_name}", None)
        obj.empty_display_type = "ARROWS"
        obj.empty_display_size = 0.15
        try:
            obj.matrix_world = getArmatureFrameMatrix(arm_info, "frame_mats_world", ptr_i, Matrix.Identity(4))
        except Exception:
            obj.matrix_world = Matrix.Identity(4)
        writeMdlImportedFrameMatrixAttributes(obj, ptr_i, str(frame_name), arm_info)
        obj["bleeds_mdl_vehicle_frame_empty"] = True
        collection.objects.link(obj)
        frame_objects[ptr_i] = obj
        created.append(obj)

    for ptr_i, obj in frame_objects.items():
        try:
            parent_ptr = int(getattr(arm_info, "frame_parent_ptrs", {}).get(ptr_i, 0) or 0)
        except Exception:
            parent_ptr = 0
        if parent_ptr and parent_ptr in frame_objects and parent_ptr != ptr_i:
            saved_world = obj.matrix_world.copy()
            obj.parent = frame_objects[parent_ptr]
            obj.matrix_parent_inverse = frame_objects[parent_ptr].matrix_world.inverted()
            obj.matrix_world = saved_world

    try:
        setattr(stories_ctx, "vehicle_frame_objects", frame_objects)
    except Exception:
        pass
    return created, frame_objects

def createVehicleAtomicMeshObject(
    *,
    collection: bpy.types.Collection,
    stories_ctx: Any,
    atomic: Any,
    geo: Any,
    parts: List[Any],
    name: str,
    atomic_index: int,
) -> bpy.types.Object:
    merged_verts: List[Tuple[float, float, float]] = []
    merged_faces: List[Tuple[int, int, int]] = []
    merged_uvs: List[Tuple[float, float]] = []
    merged_colors: List[Tuple[int, int, int, int]] = []
    polygon_material_indices: List[int] = []
    part_vertex_starts: List[int] = []
    part_face_starts: List[int] = []
    part_vertex_counts: List[int] = []
    part_face_counts: List[int] = []
    part_material_ids: List[int] = []

    for part in parts:
        verts = list(getattr(part, "verts", []) or [])
        faces = list(getattr(part, "faces", []) or [])
        if not verts:
            continue

        vertex_start = len(merged_verts)
        face_start = len(merged_faces)
        material_id = int(getattr(part, "material_id", 0) or 0)

        part_vertex_starts.append(vertex_start)
        part_face_starts.append(face_start)
        part_vertex_counts.append(len(verts))
        part_face_counts.append(len(faces))
        part_material_ids.append(material_id)

        merged_verts.extend(verts)

        uvs = list(getattr(part, "uvs", []) or [])
        if uvs:
            merged_uvs.extend((float(u), float(v)) for u, v in uvs[:len(verts)])
            if len(uvs) < len(verts):
                merged_uvs.extend((0.0, 0.0) for _ in range(len(verts) - len(uvs)))
        elif merged_uvs:
            merged_uvs.extend((0.0, 0.0) for _ in range(len(verts)))

        colors = list(getattr(part, "vertex_colors", None) or getattr(part, "loop_colors", None) or [])
        if colors:
            merged_colors.extend((int(c[0]), int(c[1]), int(c[2]), int(c[3])) for c in colors[:len(verts)])
            if len(colors) < len(verts):
                merged_colors.extend((255, 255, 255, 255) for _ in range(len(verts) - len(colors)))
        elif merged_colors:
            merged_colors.extend((255, 255, 255, 255) for _ in range(len(verts)))

        for face in faces:
            if len(face) < 3:
                continue
            merged_faces.append(tuple(int(v) + vertex_start for v in face[:3]))
            polygon_material_indices.append(material_id)

    if not merged_verts:
        raise ValueError(f"Vehicle atomic {atomic_index} has no decoded vertices")

    me = bpy.data.meshes.new(name)
    me.from_pydata(merged_verts, [], merged_faces)
    me.update(calc_edges=True)

    materials = list(getattr(geo, "materials", []) or [])
    if materials:
        for material_index, mat_desc in enumerate(materials):
            mat = get_or_create_material_for_stories(mat_desc, material_index)
            if mat is not None:
                me.materials.append(mat)

    if polygon_material_indices and len(me.materials) > 0:
        for poly_index, material_index in enumerate(polygon_material_indices):
            if poly_index >= len(me.polygons):
                break
            me.polygons[poly_index].material_index = max(0, min(int(material_index), len(me.materials) - 1))

    if merged_uvs:
        uv_layer = me.uv_layers.new(name="UVMap")
        uv_data = uv_layer.data
        for poly in me.polygons:
            for loop_index in range(poly.loop_start, poly.loop_start + poly.loop_total):
                if loop_index >= len(me.loops):
                    continue
                vert_index = me.loops[loop_index].vertex_index
                if vert_index < len(merged_uvs):
                    u, v = merged_uvs[vert_index]
                    uv_data[loop_index].uv = (float(u), 1.0 - float(v))

    if merged_colors:
        color_attr = getOrCreateCornerColorLayer(me, "Col")
        if color_attr is None:
            col_data = []
        else:
            col_data = color_attr.data
        for poly in me.polygons:
            for loop_index in range(poly.loop_start, poly.loop_start + poly.loop_total):
                if loop_index >= len(me.loops):
                    continue
                vert_index = me.loops[loop_index].vertex_index
                if vert_index < len(merged_colors) and loop_index < len(col_data):
                    r, g, b, a = merged_colors[vert_index]
                    col_data[loop_index].color = (
                        float(r) / 255.0,
                        float(g) / 255.0,
                        float(b) / 255.0,
                        float(a) / 255.0,
                    )

    obj = bpy.data.objects.new(name, me)
    collection.objects.link(obj)

    try:
        obj["bleeds_mdl_vehicle_mesh"] = True
        obj["bleeds_mdl_vehicle_atomic_index"] = int(atomic_index)
        obj["bleeds_mdl_vehicle_atomic_source"] = str(getattr(atomic, "atomic_source", "") or "")
        obj["bleeds_mdl_atomic_offset"] = int(getattr(atomic, "atomic_offset", 0) or 0)
        obj["bleeds_mdl_atomic_frame_ptr"] = int(getattr(atomic, "frame_ptr", 0) or 0)
        obj["bleeds_mdl_atomic_geom_ptr"] = int(getattr(atomic, "geom_ptr", 0) or 0)
        obj["bleeds_mdl_atomic_render_cb"] = int(getattr(atomic, "render_cb", 0) or 0)
        obj["bleeds_mdl_atomic_model_info_id"] = int(getattr(atomic, "model_info_id", -1) or -1)
        obj["bleeds_mdl_atomic_vis_id_flag"] = int(getattr(atomic, "vis_id_flag", 0) or 0)
        obj["bleeds_mdl_vehicle_source_part_count"] = int(len(parts))
        obj["bleeds_mdl_vehicle_part_material_ids"] = [int(v) for v in part_material_ids]
        obj["bleeds_mdl_vehicle_part_vertex_starts"] = [int(v) for v in part_vertex_starts]
        obj["bleeds_mdl_vehicle_part_face_starts"] = [int(v) for v in part_face_starts]
        obj["bleeds_mdl_vehicle_part_vertex_counts"] = [int(v) for v in part_vertex_counts]
        obj["bleeds_mdl_vehicle_part_face_counts"] = [int(v) for v in part_face_counts]
    except Exception:
        pass

    return obj

def buildVehiclePs2Meshes(
    context: bpy.types.Context,
    stories_ctx: Any,
    collection: bpy.types.Collection,
) -> List[bpy.types.Object]:
    created_objects: List[bpy.types.Object] = []
    frame_empty_objects, frame_object_by_ptr = createVehicleFrameObjects(stories_ctx, collection)
    created_objects.extend(frame_empty_objects)

    base_name = os.path.splitext(os.path.basename(stories_ctx.filepath))[0]
    atomics = list(getattr(stories_ctx, "atomics", []) or [])
    if not atomics and getattr(stories_ctx, "atomic", None) is not None:
        atomics = [stories_ctx.atomic]

    mesh_count = 0
    failed_count = 0

    for atomic_index, atomic in enumerate(atomics):
        geo = getattr(atomic, "ps2_geometry", None)
        if geo is None:
            try:
                stories_ctx.log(f"⚠ VehicleModel atomic[{atomic_index:02d}] skipped: no PS2 geometry decoded")
            except Exception:
                pass
            continue

        parts = list(getattr(geo, "parts", []) or [])
        if not parts:
            try:
                stories_ctx.log(f"⚠ VehicleModel atomic[{atomic_index:02d}] skipped: geometry has no decoded parts")
            except Exception:
                pass
            continue

        frame_ptr = int(getattr(atomic, "frame_ptr", 0) or 0)
        frame_name = "frame"
        try:
            arm_info = getattr(atomic, "armature", None)
            frame_name = str(getattr(arm_info, "frame_names", {}).get(frame_ptr, frame_name))
        except Exception:
            pass
        safe_frame_name = sanitizeVehicleObjectName(frame_name)

        render_cb = int(getattr(atomic, "render_cb", 0) or 0)
        source_name = str(getattr(atomic, "atomic_source", "") or "clump")
        safe_source = sanitizeVehicleObjectName(source_name)
        name = f"{base_name}_{safe_frame_name}_a{atomic_index:02d}_r{render_cb:02X}_{safe_source}"

        try:
            obj = createVehicleAtomicMeshObject(
                collection=collection,
                stories_ctx=stories_ctx,
                atomic=atomic,
                geo=geo,
                parts=parts,
                name=name,
                atomic_index=atomic_index,
            )
            obj["bleeds_mdl_atomic_frame_name"] = str(frame_name)

            frame_obj = frame_object_by_ptr.get(frame_ptr)
            if frame_obj is not None:
                obj.matrix_world = frame_obj.matrix_world.copy()
                parent_object_keep_world(obj, frame_obj)
            else:
                try:
                    stories_ctx.log(
                        f"⚠ VehicleModel atomic[{atomic_index:02d}] has no frame empty for 0x{frame_ptr:X}; left at root space"
                    )
                except Exception:
                    pass

            created_objects.append(obj)
            mesh_count += 1
        except Exception as vehicle_mesh_error:
            failed_count += 1
            try:
                stories_ctx.log(
                    f"⚠ VehicleModel atomic[{atomic_index:02d}] mesh build failed: {vehicle_mesh_error}"
                )
            except Exception:
                pass
            continue

    try:
        stories_ctx.log(
            f"✔ VehicleModel import: decoded {len(atomics)} atomic(s), created {mesh_count} atomic mesh object(s), "
            f"failed {failed_count}, frame empties {len(frame_empty_objects)}."
        )
    except Exception:
        pass
    return created_objects

def build_ps2_cutscene_actor_mesh(
    context: bpy.types.Context,
    stories_ctx: Any,
    collection: bpy.types.Collection,
    arm_obj: bpy.types.Object,
) -> List[bpy.types.Object]:
    atomic = stories_ctx.atomic
    geo = atomic.ps2_geometry
    base_name = os.path.splitext(os.path.basename(stories_ctx.filepath))[0]
    name = f"{base_name}_ps2_actor"

    merged_verts: List[Tuple[float, float, float]] = []
    merged_faces: List[Tuple[int, int, int]] = []
    merged_uvs: List[Tuple[float, float]] = []
    merged_colors: List[Tuple[int, int, int, int]] = []
    merged_normals: List[Tuple[float, float, float]] = []
    polygon_material_indices: List[int] = []
    part_vertex_offsets: List[int] = []
    part_face_offsets: List[int] = []

    parts = list(getattr(geo, "parts", []) or [])
    for part in parts:
        verts = list(getattr(part, "verts", []) or [])
        faces = list(getattr(part, "faces", []) or [])
        uvs = list(getattr(part, "uvs", []) or [])
        colors = list(getattr(part, "vertex_colors", None) or getattr(part, "loop_colors", None) or [])
        normals = list(getattr(part, "normals", []) or [])

        vertex_base = len(merged_verts)
        face_base = len(merged_faces)
        part_vertex_offsets.append(vertex_base)
        part_face_offsets.append(face_base)

        merged_verts.extend(verts)

        for i in range(len(verts)):
            if i < len(uvs):
                merged_uvs.append((float(uvs[i][0]), float(uvs[i][1])))
            else:
                merged_uvs.append((0.0, 0.0))

            if i < len(colors):
                c = colors[i]
                merged_colors.append((int(c[0]), int(c[1]), int(c[2]), int(c[3])))
            else:
                merged_colors.append((255, 255, 255, 255))

            if i < len(normals):
                n = normals[i]
                merged_normals.append((float(n[0]), float(n[1]), float(n[2])))
            else:
                merged_normals.append((0.0, 0.0, 1.0))

        for face in faces:
            if len(face) < 3:
                continue
            merged_faces.append(tuple(vertex_base + int(v) for v in list(face)[:3]))
            polygon_material_indices.append(int(getattr(part, "material_id", 0) or 0))

    me = bpy.data.meshes.new(name)
    me.from_pydata(merged_verts, [], merged_faces)
    me.update(calc_edges=True)

    if merged_uvs and len(me.loops) > 0:
        uv_layer = me.uv_layers.new(name="UVMap")
        uv_data = uv_layer.data
        for poly in me.polygons:
            for loop_index in range(poly.loop_start, poly.loop_start + poly.loop_total):
                if loop_index >= len(me.loops):
                    continue
                vert_index = me.loops[loop_index].vertex_index
                if vert_index < len(merged_uvs):
                    u, v = merged_uvs[vert_index]
                    uv_data[loop_index].uv = (u, 1.0 - v)

    if merged_colors and len(me.loops) > 0:
        color_attr = getOrCreateCornerColorLayer(me, "Col")
        if color_attr is None:
            col_data = []
        else:
            col_data = color_attr.data
        for poly in me.polygons:
            for loop_index in range(poly.loop_start, poly.loop_start + poly.loop_total):
                if loop_index >= len(me.loops):
                    continue
                vert_index = me.loops[loop_index].vertex_index
                if vert_index < len(merged_colors) and loop_index < len(col_data):
                    r, g, b, a = merged_colors[vert_index]
                    col_data[loop_index].color = (
                        r / 255.0,
                        g / 255.0,
                        b / 255.0,
                        a / 255.0,
                    )

    obj = bpy.data.objects.new(name, me)
    collection.objects.link(obj)

    if getattr(geo, "materials", None):
        for material_index, mat_desc in enumerate(list(geo.materials)):
            mat = get_or_create_material_for_stories(mat_desc, material_index)
            if mat is not None:
                obj.data.materials.append(mat)

    for poly_index, material_index in enumerate(polygon_material_indices):
        if poly_index >= len(me.polygons):
            break
        if len(obj.data.materials) > 0:
            me.polygons[poly_index].material_index = max(0, min(int(material_index), len(obj.data.materials) - 1))

    if arm_obj is not None:
        match_mesh_to_armature_space(obj, stories_ctx, arm_obj)
        assign_ps2_skin_merged(obj, parts, part_vertex_offsets, stories_ctx.import_type, arm_obj)

    writeMergedPs2MdlSemanticAttributes(me, parts, part_vertex_offsets, part_face_offsets)
    writeMdlPartMatrixProperties(obj, 0)

    try:
        obj["bleeds_mdl_cutscene_merged_mesh"] = True
        obj["bleeds_mdl_source_packet_count"] = int(len(parts))
        obj["bleeds_mdl_part_index"] = 0
        obj["bleeds_mdl_part_material_id"] = -1
        obj["bleeds_mdl_cutscene_packet_material_ids"] = [int(getattr(part, "material_id", 0) or 0) for part in parts]
        obj["bleeds_mdl_cutscene_packet_vertex_starts"] = [int(v) for v in part_vertex_offsets]
        obj["bleeds_mdl_cutscene_packet_face_starts"] = [int(v) for v in part_face_offsets]
    except Exception:
        pass

    try:
        if merged_normals:
            obj["bleeds_imported_normals"] = [(float(n[0]), float(n[1]), float(n[2])) for n in merged_normals]
    except Exception:
        pass

    try:
        if merged_uvs:
            obj["bleeds_imported_uvs"] = [(float(uv[0]), float(uv[1])) for uv in merged_uvs]
    except Exception:
        pass

    try:
        if merged_colors:
            obj["bleeds_imported_colors"] = [(int(c[0]), int(c[1]), int(c[2]), int(c[3])) for c in merged_colors]
    except Exception:
        pass

    try:
        stories_ctx.log(
            f"✔ Cutscene actor import: merged {len(parts)} source geometry packets into one mesh object '{name}'."
        )
    except Exception:
        pass

    return [obj]

MDL_FACE_ATTRIBUTES = (
    "bleeds_mdl_part_index",
    "bleeds_mdl_material_index",
    "bleeds_mdl_source_strip_index",
    "bleeds_mdl_source_strip_triangle_index",
)

MDL_CORNER_ATTRIBUTES = (
    "bleeds_mdl_corner_source_emit_index",
    "bleeds_mdl_corner_source_export_vertex_index",
    "bleeds_mdl_corner_source_strip_index",
    "bleeds_mdl_corner_source_strip_vertex_index",
)

MDL_POINT_ATTRIBUTES = (
    "bleeds_mdl_point_source_emit_index",
    "bleeds_mdl_point_source_export_vertex_index",
    "bleeds_mdl_point_source_strip_index",
    "bleeds_mdl_point_source_strip_vertex_index",
    "bleeds_mdl_point_skin_raw0",
    "bleeds_mdl_point_skin_raw1",
    "bleeds_mdl_point_skin_raw2",
    "bleeds_mdl_point_skin_raw3",
)

def getMdlAttributeDomainSize(mesh: bpy.types.Mesh, domain: str) -> int:
    domain_key = str(domain or "").upper().strip()
    if domain_key == 'POINT':
        return len(mesh.vertices)
    if domain_key == 'FACE':
        return len(mesh.polygons)
    if domain_key == 'CORNER':
        return len(mesh.loops)
    if domain_key == 'EDGE':
        return len(mesh.edges)
    return 0

def ensureMdlIntAttribute(mesh: bpy.types.Mesh, name: str, domain: str) -> Any:
    if mesh is None:
        return None

    domain_key = str(domain or "").upper().strip()
    try:
        mesh.update(calc_edges=False)
    except Exception:
        try:
            mesh.update()
        except Exception:
            pass

    expected_count = getMdlAttributeDomainSize(mesh, domain_key)
    attribute = getMeshAttribute(mesh, name)

    if attribute is not None:
        try:
            existing_domain = str(getattr(attribute, "domain", "") or "").upper().strip()
        except Exception:
            existing_domain = domain_key

        if existing_domain and existing_domain != domain_key:
            try:
                removeMeshAttribute(mesh, attribute)
                attribute = None
            except Exception:
                return attribute

    if attribute is None:
        try:
            attribute = ensureMeshAttribute(mesh, name, 'INT', domain_key)
        except Exception:
            return None

    try:
        current_count = len(attribute.data)
    except Exception:
        current_count = 0

    if expected_count > 0 and current_count == 0:
        try:
            mesh.update(calc_edges=False)
        except Exception:
            try:
                mesh.update()
            except Exception:
                pass
        try:
            current_count = len(attribute.data)
        except Exception:
            current_count = 0

    if expected_count > 0 and current_count == 0:
        try:
            removeMeshAttribute(mesh, attribute)
            attribute = ensureMeshAttribute(mesh, name, 'INT', domain_key)
        except Exception:
            pass

    return attribute

def setMdlIntAttributeValue(attribute: Any, index: int, value: int) -> bool:
    if attribute is None:
        return False
    try:
        target_index = int(index)
    except Exception:
        return False
    if target_index < 0:
        return False
    try:
        if target_index >= len(attribute.data):
            return False
        attribute.data[target_index].value = int(value)
        return True
    except Exception:
        return False

def ensureMdlFloatAttribute(mesh: bpy.types.Mesh, name: str, domain: str) -> Any:
    if mesh is None:
        return None
    domain_key = str(domain or 'POINT').upper().strip()
    try:
        expected_count = {
            'POINT': len(mesh.vertices),
            'FACE': len(mesh.polygons),
            'CORNER': len(mesh.loops),
            'EDGE': len(mesh.edges),
        }.get(domain_key, 0)
    except Exception:
        expected_count = 0

    try:
        attribute = getMeshAttribute(mesh, name)
    except Exception:
        attribute = None

    if attribute is not None:
        try:
            existing_domain = str(getattr(attribute, "domain", "") or "").upper().strip()
            existing_type = str(getattr(attribute, "data_type", "") or "").upper().strip()
        except Exception:
            existing_domain = domain_key
            existing_type = 'FLOAT'
        if (existing_domain and existing_domain != domain_key) or (existing_type and existing_type != 'FLOAT'):
            try:
                removeMeshAttribute(mesh, attribute)
                attribute = None
            except Exception:
                return attribute

    if attribute is None:
        try:
            attribute = ensureMeshAttribute(mesh, name, 'FLOAT', domain_key)
        except Exception:
            return None

    try:
        current_count = len(attribute.data)
    except Exception:
        current_count = 0
    if expected_count > 0 and current_count == 0:
        try:
            mesh.update(calc_edges=False)
        except Exception:
            try:
                mesh.update()
            except Exception:
                pass
    return attribute

def setMdlFloatAttributeValue(attribute: Any, index: int, value: float) -> bool:
    if attribute is None:
        return False
    try:
        target_index = int(index)
    except Exception:
        return False
    if target_index < 0:
        return False
    try:
        if target_index >= len(attribute.data):
            return False
        attribute.data[target_index].value = float(value)
        return True
    except Exception:
        return False

def decodePs2PedSkinWordToNodeWeight(raw_value: int) -> Tuple[int, float]:
    raw = int(raw_value) & 0xFFFFFFFF
    node_index = int(raw & 0xFF) // 4
    weight_raw = raw & 0xFFFFFF00
    try:
        weight = struct.unpack('<f', struct.pack('<I', weight_raw))[0]
    except Exception:
        weight = 0.0
    if not (-1000000.0 < float(weight) < 1000000.0):
        weight = 0.0
    if weight < 0.0:
        weight = 0.0
    return int(node_index), float(weight)

def normalizeMdlSkinNodeWeights(nodes: List[int], weights: List[float]) -> Tuple[List[int], List[float]]:
    pairs: List[Tuple[int, float]] = []
    for node, weight in zip(list(nodes)[:4], list(weights)[:4]):
        try:
            node_i = int(node)
            weight_f = float(weight)
        except Exception:
            continue
        if node_i < 0 or weight_f <= 1.0e-8:
            continue
        pairs.append((node_i, weight_f))
    pairs.sort(key=lambda item: item[1], reverse=True)
    pairs = pairs[:4]
    total = sum(w for _, w in pairs)
    if total > 1.0e-8:
        pairs = [(n, w / total) for n, w in pairs]
    while len(pairs) < 4:
        pairs.append((0, 0.0))
    return [int(n) for n, _w in pairs[:4]], [float(w) for _n, w in pairs[:4]]

def buildPedHierarchyNodeOrder(arm_info: Any, filepath: str = "", hierarchy_ptr: int = 0) -> List[Tuple[int, str]]:
    frame_names = dict(getattr(arm_info, "frame_names", {}) or {})
    if not frame_names:
        return []

    child_ptrs = dict(getattr(arm_info, "frame_child_ptrs", {}) or {})
    sibling_ptrs = dict(getattr(arm_info, "frame_sibling_ptrs", {}) or {})

    anchor_ptr = 0
    try:
        hp = int(hierarchy_ptr or 0)
        if hp > 0 and filepath:
            with open(filepath, "rb") as f:
                f.seek(hp + 0x34)
                raw = f.read(4)
            if len(raw) == 4:
                anchor_ptr = int.from_bytes(raw, "little") & 0xFFFFFFFF
                if 0x80000000 <= anchor_ptr <= 0x8FFFFFFF:
                    anchor_ptr -= 0x80000000
    except Exception:
        anchor_ptr = 0

    if anchor_ptr not in frame_names:
        for ptr, name in frame_names.items():
            if str(name).lower() == "root":
                anchor_ptr = int(ptr)
                break
    if anchor_ptr not in frame_names:

        for ptr, name in frame_names.items():
            low = str(name).lower()
            if "base" not in low:
                anchor_ptr = int(ptr)
                break
    if anchor_ptr not in frame_names:
        anchor_ptr = int(next(iter(frame_names.keys())))

    ordered: List[Tuple[int, str]] = []
    seen: set = set()

    def walk(ptr: int) -> None:
        ptr = int(ptr)
        if ptr == 0 or ptr in seen or ptr not in frame_names:
            return
        seen.add(ptr)
        ordered.append((ptr, str(frame_names[ptr])))
        child = int(child_ptrs.get(ptr, 0) or 0)
        if child:
            walk(child)
        sibling = int(sibling_ptrs.get(ptr, 0) or 0)
        if sibling:
            walk(sibling)

    walk(anchor_ptr)

    for ptr, name in frame_names.items():
        low = str(name).lower()
        if int(ptr) in seen or "base" in low:
            continue
        ordered.append((int(ptr), str(name)))
        seen.add(int(ptr))

    return ordered

def buildPedHierarchyEntryMaps(arm_info: Any) -> Tuple[Dict[str, Dict[str, Any]], Dict[int, Dict[str, Any]]]:
    by_name: Dict[str, Dict[str, Any]] = {}
    by_node_index: Dict[int, Dict[str, Any]] = {}
    try:
        entries = list(getattr(arm_info, "hierarchy_entries", []) or [])
    except Exception:
        entries = []
    for entry in entries:
        try:
            name = str(entry.get("frame_name", ""))
            canon = stories_mdl.canon_frame_name(name)
            node_index = int(entry.get("node_index", -1))
        except Exception:
            continue
        if canon:
            by_name[canon] = entry
        if node_index >= 0:
            by_node_index[node_index] = entry
    return by_name, by_node_index

def writeRawPedHierarchyBoneIdAttributes(bone: Any, entry: Dict[str, Any]) -> None:
    if bone is None or not entry:
        return
    try:
        raw_bone_id = int(entry.get("bone_id", 0xFF)) & 0xFF
        node_index = int(entry.get("node_index", -1))
        bone_type = int(entry.get("bone_type", 0)) & 0xFF
        packed = int(entry.get("packed", 0)) & 0xFFFFFFFF
    except Exception:
        return

    try:
        bone["bleeds_mdl_hierarchy_bone_id"] = raw_bone_id
        bone["bleeds_mdl_raw_hanim_bone_id"] = raw_bone_id
        bone["bleeds_hierarchy_bone_id"] = raw_bone_id
        bone["bleeds_raw_hanim_bone_id"] = raw_bone_id
        bone["bleeds_mdl_hierarchy_bone_type"] = bone_type
        bone["bleeds_mdl_hierarchy_packed"] = packed
        if node_index >= 0:
            bone["bleeds_mdl_hierarchy_node_index"] = int(node_index)
            bone["node_index"] = int(node_index)
            bone["bleeds_anim_table_index"] = int(node_index)

    except Exception:
        pass

def writePedHierarchyNodeAttributes(owner: Any, node_order: List[Tuple[int, str]]) -> None:
    if owner is None or not node_order:
        return
    try:
        owner["bleeds_mdl_hierarchy_node_ptrs"] = [int(ptr) for ptr, _name in node_order]
        owner["bleeds_mdl_hierarchy_node_names"] = [str(name) for _ptr, name in node_order]
        owner["bleeds_mdl_hierarchy_node_indices"] = [int(i) for i in range(len(node_order))]
        owner["bleeds_mdl_hierarchy_node_count"] = int(len(node_order))
    except Exception:
        pass

def writePs2MdlSemanticAttributes(mesh: bpy.types.Mesh, part: Any, part_index: int) -> None:
    if mesh is None:
        return

    try:
        mesh.update(calc_edges=True)
    except Exception:
        try:
            mesh.update()
        except Exception:
            pass

    face_part = ensureMdlIntAttribute(mesh, "bleeds_mdl_part_index", 'FACE')
    face_material = ensureMdlIntAttribute(mesh, "bleeds_mdl_material_index", 'FACE')
    face_strip = ensureMdlIntAttribute(mesh, "bleeds_mdl_source_strip_index", 'FACE')
    face_strip_tri = ensureMdlIntAttribute(mesh, "bleeds_mdl_source_strip_triangle_index", 'FACE')

    corner_emit = ensureMdlIntAttribute(mesh, "bleeds_mdl_corner_source_emit_index", 'CORNER')
    corner_export = ensureMdlIntAttribute(mesh, "bleeds_mdl_corner_source_export_vertex_index", 'CORNER')
    corner_strip = ensureMdlIntAttribute(mesh, "bleeds_mdl_corner_source_strip_index", 'CORNER')
    corner_strip_vertex = ensureMdlIntAttribute(mesh, "bleeds_mdl_corner_source_strip_vertex_index", 'CORNER')

    point_emit = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_source_emit_index", 'POINT')
    point_export = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_source_export_vertex_index", 'POINT')
    point_strip = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_source_strip_index", 'POINT')
    point_strip_vertex = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_source_strip_vertex_index", 'POINT')
    point_skin_raw0 = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_skin_raw0", 'POINT')
    point_skin_raw1 = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_skin_raw1", 'POINT')
    point_skin_raw2 = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_skin_raw2", 'POINT')
    point_skin_raw3 = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_skin_raw3", 'POINT')
    skin_node_attrs = [
        ensureMdlIntAttribute(mesh, "bleeds_skin_node_0", 'POINT'),
        ensureMdlIntAttribute(mesh, "bleeds_skin_node_1", 'POINT'),
        ensureMdlIntAttribute(mesh, "bleeds_skin_node_2", 'POINT'),
        ensureMdlIntAttribute(mesh, "bleeds_skin_node_3", 'POINT'),
    ]
    skin_weight_attrs = [
        ensureMdlFloatAttribute(mesh, "bleeds_skin_weight_0", 'POINT'),
        ensureMdlFloatAttribute(mesh, "bleeds_skin_weight_1", 'POINT'),
        ensureMdlFloatAttribute(mesh, "bleeds_skin_weight_2", 'POINT'),
        ensureMdlFloatAttribute(mesh, "bleeds_skin_weight_3", 'POINT'),
    ]
    skin_source_part = ensureMdlIntAttribute(mesh, "bleeds_skin_source_part", 'POINT')
    skin_source_vertex = ensureMdlIntAttribute(mesh, "bleeds_skin_source_vertex", 'POINT')
    skin_is_imported = ensureMdlIntAttribute(mesh, "bleeds_skin_is_imported", 'POINT')
    skin_is_modified = ensureMdlIntAttribute(mesh, "bleeds_skin_is_modified", 'POINT')
    skin_confidence = ensureMdlFloatAttribute(mesh, "bleeds_skin_confidence", 'POINT')

    material_id = int(getattr(part, "material_id", 0))
    strips_meta = list(getattr(part, "strips_meta", []) or [])
    skin_raw_dwords = list(getattr(part, "skin_raw_dwords", []) or [])

    vertex_to_strip: Dict[int, Tuple[int, int, int]] = {}
    source_emit = 0
    for strip_index, strip in enumerate(strips_meta):
        base_vertex_index = int(getattr(strip, "base_vertex_index", 0))
        vertex_count = int(getattr(strip, "vertex_count", 0))
        for local_index in range(max(0, vertex_count)):
            vertex_index = base_vertex_index + local_index
            vertex_to_strip[int(vertex_index)] = (
                int(strip_index),
                int(local_index),
                int(source_emit),
            )
            source_emit += 1

    for vertex in mesh.vertices:
        vertex_index = int(vertex.index)
        strip_index, strip_vertex_index, emit_index = vertex_to_strip.get(
            vertex_index,
            (0, vertex_index, vertex_index),
        )
        setMdlIntAttributeValue(point_emit, vertex_index, emit_index)
        setMdlIntAttributeValue(point_export, vertex_index, vertex_index)
        setMdlIntAttributeValue(point_strip, vertex_index, strip_index)
        setMdlIntAttributeValue(point_strip_vertex, vertex_index, strip_vertex_index)

        raw4 = [0, 0, 0, 0]
        if 0 <= vertex_index < len(skin_raw_dwords):
            try:
                raw4 = list(skin_raw_dwords[vertex_index])[:4]
            except Exception:
                raw4 = [0, 0, 0, 0]
        while len(raw4) < 4:
            raw4.append(0)
        setMdlIntAttributeValue(point_skin_raw0, vertex_index, signedInt32ForIdProp(raw4[0]))
        setMdlIntAttributeValue(point_skin_raw1, vertex_index, signedInt32ForIdProp(raw4[1]))
        setMdlIntAttributeValue(point_skin_raw2, vertex_index, signedInt32ForIdProp(raw4[2]))
        setMdlIntAttributeValue(point_skin_raw3, vertex_index, signedInt32ForIdProp(raw4[3]))

        decoded_nodes: List[int] = []
        decoded_weights: List[float] = []
        for raw_word in raw4[:4]:
            node_index, weight = decodePs2PedSkinWordToNodeWeight(int(raw_word))
            decoded_nodes.append(int(node_index))
            decoded_weights.append(float(weight))
        decoded_nodes, decoded_weights = normalizeMdlSkinNodeWeights(decoded_nodes, decoded_weights)
        for slot_index in range(4):
            setMdlIntAttributeValue(skin_node_attrs[slot_index], vertex_index, int(decoded_nodes[slot_index]))
            setMdlFloatAttributeValue(skin_weight_attrs[slot_index], vertex_index, float(decoded_weights[slot_index]))
        setMdlIntAttributeValue(skin_source_part, vertex_index, int(part_index))
        setMdlIntAttributeValue(skin_source_vertex, vertex_index, int(vertex_index))
        setMdlIntAttributeValue(skin_is_imported, vertex_index, 1)
        setMdlIntAttributeValue(skin_is_modified, vertex_index, 0)
        setMdlFloatAttributeValue(skin_confidence, vertex_index, 1.0)

    strip_triangle_lookup: Dict[Tuple[int, int, int], Tuple[int, int]] = {}
    for strip_index, strip in enumerate(strips_meta):
        base_vertex_index = int(getattr(strip, "base_vertex_index", 0))
        vertex_count = int(getattr(strip, "vertex_count", 0))
        triangle_order = 0
        for i in range(2, max(0, vertex_count)):
            if (i % 2) == 0:
                tri = (
                    base_vertex_index + i - 2,
                    base_vertex_index + i - 1,
                    base_vertex_index + i,
                )
            else:
                tri = (
                    base_vertex_index + i - 1,
                    base_vertex_index + i - 2,
                    base_vertex_index + i,
                )
            if tri[0] == tri[1] or tri[1] == tri[2] or tri[2] == tri[0]:
                continue
            tri_key = tuple(int(v) for v in tri)
            strip_triangle_lookup[tri_key] = (int(strip_index), int(triangle_order))
            strip_triangle_lookup[(tri_key[1], tri_key[0], tri_key[2])] = (int(strip_index), int(triangle_order))
            triangle_order += 1

    fallback_triangle_order = 0
    for polygon in mesh.polygons:
        polygon_index = int(polygon.index)
        tri_vertices = tuple(int(v) for v in polygon.vertices[:3])
        strip_index, strip_triangle_index = strip_triangle_lookup.get(
            tri_vertices,
            (0, fallback_triangle_order),
        )
        fallback_triangle_order += 1

        setMdlIntAttributeValue(face_part, polygon_index, part_index)
        setMdlIntAttributeValue(face_material, polygon_index, material_id)
        setMdlIntAttributeValue(face_strip, polygon_index, strip_index)
        setMdlIntAttributeValue(face_strip_tri, polygon_index, strip_triangle_index)

        for local_corner_index, loop_index in enumerate(polygon.loop_indices):
            loop_index = int(loop_index)
            if loop_index < 0 or loop_index >= len(mesh.loops):
                continue
            vertex_index = int(mesh.loops[loop_index].vertex_index)
            src_strip_index, src_strip_vertex_index, emit_index = vertex_to_strip.get(
                vertex_index,
                (int(strip_index), int(local_corner_index), int(loop_index)),
            )
            setMdlIntAttributeValue(corner_emit, loop_index, emit_index)
            setMdlIntAttributeValue(corner_export, loop_index, vertex_index)
            setMdlIntAttributeValue(corner_strip, loop_index, src_strip_index)
            setMdlIntAttributeValue(corner_strip_vertex, loop_index, src_strip_vertex_index)

    strip_counts = [int(getattr(strip, "vertex_count", 0)) for strip in strips_meta]
    try:
        mesh["bleeds_mdl_semantic_attributes_version"] = 2
        mesh["bleeds_mdl_skin_attribute_schema"] = "RSLTANIM_NODE_FLOAT_POINT_V1"
        mesh["bleeds_mdl_semantic_attributes_origin"] = "IMPORTED_PS2"
        mesh["bleeds_mdl_source_part_index"] = int(part_index)
        mesh["bleeds_mdl_source_material_index"] = int(material_id)
        mesh["bleeds_mdl_source_part_vertex_count"] = int(len(mesh.vertices))
        mesh["bleeds_mdl_source_part_face_count"] = int(len(mesh.polygons))
        mesh["bleeds_mdl_source_loop_count"] = int(len(mesh.loops))
        mesh["bleeds_mdl_source_strip_count"] = int(len(strip_counts))
        mesh["bleeds_mdl_source_strip_counts"] = [int(v) for v in strip_counts]
    except Exception:
        pass

def assign_ps2_skin(
    obj: bpy.types.Object,
    part: Any,
    import_type: int,
    arm_obj: bpy.types.Object,
) -> None:
    if arm_obj is None:
        return

    me = obj.data
    vertex_count = len(me.vertices)
    if vertex_count == 0:
        return

    obj.vertex_groups.clear()

    bone_names = getPs2PedSkinPaletteBoneNames(import_type, arm_obj)
    stampPs2PedSkinPaletteAttributes(obj, import_type, arm_obj)
    try:
        stampPs2PedSkinPaletteAttributes(obj.data, import_type, arm_obj)
    except Exception:
        pass

    assignments: Dict[int, Dict[str, float]] = {}

    for strip in list(getattr(part, "strips_meta", []) or []):
        base = int(getattr(strip, "base_vertex_index", 0) or 0)
        count = int(getattr(strip, "vertex_count", 0) or 0)

        if not getattr(strip, "skin_indices", None) or not getattr(strip, "skin_weights", None):
            continue

        for local_i in range(max(0, count)):
            vert_index = base + local_i
            if vert_index < 0 or vert_index >= vertex_count:
                continue
            if local_i >= len(strip.skin_indices) or local_i >= len(strip.skin_weights):
                continue

            for bone_index, weight in zip(strip.skin_indices[local_i], strip.skin_weights[local_i]):
                accumulateMdlVertexSkinWeight(assignments, vert_index, bone_index, weight, bone_names)

    writeMdlVertexSkinAssignments(obj, assignments)

def assign_psp_skin(
    obj: bpy.types.Object,
    mesh_data: Any,
    import_type: int,
    arm_obj: bpy.types.Object,
) -> None:
    if arm_obj is None:
        return

    me = obj.data
    vertex_count = len(me.vertices)
    if vertex_count == 0:
        return

    obj.vertex_groups.clear()

    bone_names = get_bone_name_list(import_type)
    vg_by_index: Dict[int, bpy.types.VertexGroup] = {}

    def get_vg(bone_index: int) -> bpy.types.VertexGroup:
        if bone_index not in vg_by_index:
            if 0 <= bone_index < len(bone_names):
                name = bone_names[bone_index]
            else:
                name = f"bone_{bone_index:02d}"
            vg_by_index[bone_index] = obj.vertex_groups.new(name=name)
        return vg_by_index[bone_index]

    if not getattr(mesh_data, "bone_indices", None) or not getattr(mesh_data, "bone_weights", None):
        return

    for vert_index in range(vertex_count):
        if vert_index >= len(mesh_data.bone_indices):
            break
        indices = mesh_data.bone_indices[vert_index]
        weights = mesh_data.bone_weights[vert_index]
        for bone_index, weight in zip(indices, weights):
            if weight <= 0.0:
                continue
            vg = get_vg(bone_index)
            vg.add([vert_index], weight, "REPLACE")

def build_ps2_meshes(
    context: bpy.types.Context,
    stories_ctx: Any,
    collection: bpy.types.Collection,
    arm_obj: bpy.types.Object,
) -> List[bpy.types.Object]:
    atomic = stories_ctx.atomic
    geo = atomic.ps2_geometry

    mdl_type_u = str(getattr(stories_ctx, "mdl_type", "") or "").upper().strip()

    created_objects: List[bpy.types.Object] = []
    if mdl_type_u == "VEH":
        return buildVehiclePs2Meshes(context, stories_ctx, collection)

    base_name = os.path.splitext(os.path.basename(stories_ctx.filepath))[0]
    parts_to_import = list(getattr(geo, "parts", []) or [])
    if mdl_type_u == "CUT":
        original_packet_count = len(parts_to_import)
        parts_to_import = buildCutsceneActorPartsByMaterial(parts_to_import)
        try:
            stories_ctx.log(
                f"✔ Cutscene actor import: grouped {original_packet_count} source DMA packets into {len(parts_to_import)} material part meshes."
            )
        except Exception:
            pass

    for part_index, part in enumerate(parts_to_import):
        if mdl_type_u == "CUT":
            name = f"{base_name}_ps2_part{part_index:02d}_mat{int(getattr(part, 'material_id', 0) or 0):02d}"
        else:
            name = f"{base_name}_ps2_p{part_index:02d}"

        verts = list(part.verts)
        faces = list(part.faces)

        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        me.update(calc_edges=True)

        uvs = getattr(part, "uvs", None)
        if uvs:
            uv_layer = me.uv_layers.new(name="UVMap")
            uv_data = uv_layer.data
            for poly in me.polygons:
                for loop_index in range(poly.loop_start, poly.loop_start + poly.loop_total):
                    if loop_index >= len(me.loops):
                        continue
                    vert_index = me.loops[loop_index].vertex_index
                    if vert_index < len(uvs):
                        u, v = uvs[vert_index]
                        uv_data[loop_index].uv = (u, 1.0 - v)

        colors = getattr(part, "vertex_colors", None)
        if not colors:
            colors = getattr(part, "loop_colors", None)
        if colors:
            color_attr = getOrCreateCornerColorLayer(me, "Col")
            if color_attr is None:
                col_data = []
            else:
                col_data = color_attr.data
            for poly in me.polygons:
                for loop_index in range(poly.loop_start, poly.loop_start + poly.loop_total):
                    if loop_index >= len(me.loops):
                        continue
                    vert_index = me.loops[loop_index].vertex_index
                    if vert_index < len(colors) and loop_index < len(col_data):
                        r, g, b, a = colors[vert_index]
                        col_data[loop_index].color = (
                            r / 255.0,
                            g / 255.0,
                            b / 255.0,
                            a / 255.0,
                        )

        obj = bpy.data.objects.new(name, me)
        collection.objects.link(obj)
        writePs2MdlSemanticAttributes(me, part, part_index)

        if geo.materials and 0 <= part.material_id < len(geo.materials):
            mat_desc = geo.materials[part.material_id]
            try:
                texture_name = str(getattr(mat_desc, "texture", "") or "")
                obj["bleeds_mdl_part_texture_name"] = texture_name
                me["bleeds_mdl_part_texture_name"] = texture_name
                obj["bleeds_mdl_material_name"] = texture_name
                me["bleeds_mdl_material_name"] = texture_name
            except Exception:
                pass
            mat = get_or_create_material_for_stories(mat_desc, part.material_id)
            if mat is not None:
                if len(obj.data.materials) == 0:
                    obj.data.materials.append(mat)
                else:
                    obj.data.materials[0] = mat

        if arm_obj is not None:

            match_mesh_to_armature_space(obj, stories_ctx, arm_obj)

            assign_ps2_skin(obj, part, stories_ctx.import_type, arm_obj)

        writeMdlPartMatrixProperties(obj, part_index)

        created_objects.append(obj)

        try:
            obj["bleeds_mdl_part_index"] = int(part_index)
            obj["bleeds_mdl_part_material_id"] = int(getattr(part, "material_id", 0))
            obj["bleeds_mdl_part_uv_scale"] = [float(v) for v in getattr(part, "uv_scale", (1.0, 1.0))[:2]]
            obj["bleeds_mdl_part_geom_flags"] = signedInt32ForIdProp(getattr(part, "geom_flags", 0))
            obj["bleeds_mdl_part_strip_vertex_count"] = int(getattr(part, "strip_vertex_count_hint", 0))
            if mdl_type_u == "CUT" and hasattr(part, "source_packet_indices"):
                obj["bleeds_mdl_cutscene_grouped_part"] = True
                obj["bleeds_mdl_cutscene_source_packet_indices"] = [int(v) for v in getattr(part, "source_packet_indices", [])]
                obj["bleeds_mdl_cutscene_source_packet_count"] = int(len(getattr(part, "source_packet_indices", []) or []))
                obj["bleeds_mdl_cutscene_source_packet_vertex_starts"] = [int(v) for v in getattr(part, "source_packet_vertex_starts", [])]
                obj["bleeds_mdl_cutscene_source_packet_face_starts"] = [int(v) for v in getattr(part, "source_packet_face_starts", [])]

            try:
                if hasattr(part, "entry_unknown0"):
                    obj["bleeds_mdl_part_entry_unknown0"] = signedInt32ForIdProp(getattr(part, "entry_unknown0", 0))
                if hasattr(part, "entry_unknowns"):
                    obj["bleeds_mdl_part_entry_unknowns"] = signedInt32ListForIdProp(getattr(part, "entry_unknowns", []), 6)
                if hasattr(part, "entry_unknown_short"):
                    obj["bleeds_mdl_part_entry_unknown_short"] = int(getattr(part, "entry_unknown_short", 0))
                if hasattr(part, "entry_trailing"):
                    obj["bleeds_mdl_part_entry_trailing"] = signedInt32ListForIdProp(getattr(part, "entry_trailing", []), 3)
            except Exception:
                pass
            bbox_i16 = list(getattr(part, "bbox_i16", []) or [])
            if bbox_i16:
                obj["bleeds_mdl_part_bbox_i16"] = [int(v) for v in bbox_i16[:6]]
            sphere = list(getattr(part, "sphere", (0.0, 0.0, 0.0, 0.0)) or [])
            if len(sphere) >= 4:
                obj["bleeds_mdl_part_sphere"] = [float(sphere[0]), float(sphere[1]), float(sphere[2]), float(sphere[3])]
        except Exception:
            pass

        try:
            norms = getattr(part, "normals", None)
            if norms:
                obj["bleeds_imported_normals"] = [
                    (float(n[0]), float(n[1]), float(n[2])) for n in norms
                ]
        except Exception:
            pass

        try:
            imported_uvs = getattr(part, "uvs", None)
            if imported_uvs:
                obj["bleeds_imported_uvs"] = [
                    (float(uv[0]), float(uv[1])) for uv in imported_uvs
                ]
        except Exception:
            pass

        try:
            imported_colors = getattr(part, "vertex_colors", None) or getattr(part, "loop_colors", None)
            if imported_colors:
                obj["bleeds_imported_colors"] = [
                    (int(c[0]), int(c[1]), int(c[2]), int(c[3])) for c in imported_colors
                ]
        except Exception:
            pass

        try:
            skin_raw = getattr(part, "skin_raw_dwords", None)
            if skin_raw:
                flat_skin_raw = []
                for raw4 in skin_raw:
                    vals = list(raw4)[:4]
                    while len(vals) < 4:
                        vals.append(0)
                    for value in vals[:4]:
                        flat_skin_raw.append(signedInt32ForIdProp(value))
                obj["bleeds_imported_skin_raw_dword_flat"] = flat_skin_raw
                obj["bleeds_imported_skin_raw_dword_count"] = int(len(flat_skin_raw) // 4)
        except Exception:
            pass

    return created_objects

def build_psp_meshes(
    context: bpy.types.Context,
    stories_ctx: Any,
    collection: bpy.types.Collection,
    arm_obj: bpy.types.Object,
) -> List[bpy.types.Object]:
    atomic = stories_ctx.atomic
    geo = atomic.psp_geometry

    created_objects: List[bpy.types.Object] = []
    base_name = os.path.splitext(os.path.basename(stories_ctx.filepath))[0]

    for mesh_index, mesh_data in enumerate(geo.meshes):
        name = f"{base_name}_psp_m{mesh_index:02d}"

        verts: List[Tuple[float, float, float]] = list(mesh_data.verts)
        faces: List[Tuple[int, int, int]] = list(mesh_data.faces)

        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        me.update(calc_edges=True)

        if getattr(mesh_data, "uvs", None):
            uv_layer = me.uv_layers.new(name="UVMap")
            uv_data = uv_layer.data
            for poly in me.polygons:
                for loop_index in range(poly.loop_start, poly.loop_start + poly.loop_total):
                    if loop_index >= len(me.loops):
                        continue
                    vert_index = me.loops[loop_index].vertex_index
                    if vert_index < len(mesh_data.uvs):
                        u, v = mesh_data.uvs[vert_index]
                        uv_data[loop_index].uv = (u, 1.0 - v)

        colors = getattr(mesh_data, "colors", None)
        if colors:
            color_attr = getOrCreateCornerColorLayer(me, "Col")
            if color_attr is None:
                col_data = []
            else:
                col_data = color_attr.data
            for poly in me.polygons:
                for loop_index in range(poly.loop_start, poly.loop_start + poly.loop_total):
                    if loop_index >= len(me.loops):
                        continue
                    vert_index = me.loops[loop_index].vertex_index
                    if vert_index < len(colors) and loop_index < len(col_data):
                        r, g, b, a = colors[vert_index]
                        col_data[loop_index].color = (
                            r / 255.0,
                            g / 255.0,
                            b / 255.0,
                            a / 255.0,
                        )

        obj = bpy.data.objects.new(name, me)
        collection.objects.link(obj)

        if geo.materials and 0 <= mesh_data.mat_id < len(geo.materials):
            mat_desc = geo.materials[mesh_data.mat_id]
            mat = get_or_create_material_for_stories(mat_desc, mesh_data.mat_id)
            if mat is not None:
                if len(obj.data.materials) == 0:
                    obj.data.materials.append(mat)
                else:
                    obj.data.materials[0] = mat

        if arm_obj is not None:
            match_mesh_to_armature_space(obj, stories_ctx, arm_obj)
            assign_psp_skin(obj, mesh_data, stories_ctx.import_type, arm_obj)

        created_objects.append(obj)

    return created_objects

def build_stories_armature_from_frame_mats(
    context,
    arm_info: stories_mdl.StoriesArmatureInfo,
    armature_name: str,
    collection: bpy.types.Collection,
    debug: bool = False,
) -> bpy.types.Object:
    frame_mats_world = arm_info.frame_mats_world
    frame_names = arm_info.frame_names

    arm_data = bpy.data.armatures.new(armature_name)
    armature_obj = bpy.data.objects.new(armature_name, arm_data)
    collection.objects.link(armature_obj)

    bones_by_ptr: Dict[int, bpy.types.EditBone] = {}

    setActiveObject(context, armature_obj)
    safeSelectObject(armature_obj, True)
    bpy.ops.object.mode_set(mode='EDIT')

    for frame_ptr, name in frame_names.items():
        if frame_ptr not in frame_mats_world:
            continue

        world_mat = frame_mats_world[frame_ptr]

        eb = arm_data.edit_bones.new(name)
        alignEditBoneToFrameMatrix(eb, world_mat, default_length=0.1)
        bones_by_ptr[frame_ptr] = eb

    bpy.ops.object.mode_set(mode='OBJECT')

    try:
        writeMdlArmatureFrameMatrixArrays(armature_obj, arm_info)
        writeMdlArmatureFrameMatrixArrays(arm_data, arm_info)
        for frame_ptr, name in frame_names.items():
            bone = arm_data.bones.get(str(name))
            if bone is not None:
                writeMdlImportedFrameMatrixAttributes(bone, int(frame_ptr), str(name), arm_info)
                writeBlenderRestMatrixAttributes(bone, arm_data, str(name))
    except Exception:
        pass

    if debug:
        print(f"Created armature '{armature_name}' with {len(bones_by_ptr)} bones")

    return armature_obj

def import_stories_mdl(
    context: bpy.types.Context,
    filepath: str,
    platform: str,
    mdl_type: str,
    collection_name: str,
    create_armature: bool,
    link_to_scene: bool,
) -> List[bpy.types.Object]:
    stories_reader = stories_mdl.read_stories(filepath, platform, mdl_type)
    ctx_raw = stories_reader.read()

    stories_ctx = StoriesImportContext(
        filepath=ctx_raw.filepath,
        platform=ctx_raw.platform,
        mdl_type=ctx_raw.mdl_type,
        shrink=ctx_raw.shrink,
        import_type=ctx_raw.import_type,
        atomic=ctx_raw.atomic,
        debug_log=list(ctx_raw.debug_log),
    )

    for attr_name in (
        "atomics",
        "clump_ptr",
        "clump_root_frame_ptr",
        "clump_first_atomic_ptr",
        "clump_last_atomic_ptr",
        "vehicle_extra_count",
        "vehicle_extra_array_ptr",
        "vehicle_primary_material_ptrs",
        "vehicle_secondary_material_ptrs",
    ):
        if hasattr(ctx_raw, attr_name):
            try:
                setattr(stories_ctx, attr_name, getattr(ctx_raw, attr_name))
            except Exception:
                pass

    if collection_name and collection_name in bpy.data.collections:
        collection = bpy.data.collections[collection_name]
    else:
        collection = bpy.data.collections.new(collection_name or "Stories_MDL")
        if link_to_scene:
            context.scene.collection.children.link(collection)

    base_name = os.path.splitext(os.path.basename(filepath))[0]
    root_name = f"{base_name}_ROOT"
    root_obj = bpy.data.objects.new(root_name, None)
    root_obj.empty_display_type = "PLAIN_AXES"
    root_obj.empty_display_size = 0.5
    collection.objects.link(root_obj)

    scale_base = (1.0, 1.0, 1.0)
    pos_base = (0.0, 0.0, 0.0)
    atomic = stories_ctx.atomic
    if platform == "PS2" and getattr(atomic, "ps2_geometry", None) is not None:
        geo = atomic.ps2_geometry
        scale_base = (float(geo.x_scale), float(geo.y_scale), float(geo.z_scale))
        pos_base = (float(geo.translation[0]), float(geo.translation[1]), float(geo.translation[2]))
    elif platform != "PS2" and getattr(atomic, "psp_geometry", None) is not None:
        geo = atomic.psp_geometry
        scale_base = (float(geo.scale[0]), float(geo.scale[1]), float(geo.scale[2]))
        pos_base = (float(geo.pos[0]), float(geo.pos[1]), float(geo.pos[2]))

    try:
        root_obj.bleeds_is_mdl_root = True
        root_obj.bleeds_mdl_platform = platform
        root_obj.bleeds_mdl_type = mdl_type
        root_obj.bleeds_mdl_filepath = filepath
        root_obj.bleeds_leeds_scale_base = scale_base
        root_obj.bleeds_leeds_pos_base = pos_base
    except Exception:
        root_obj["bleeds_is_mdl_root"] = True
        root_obj["bleeds_mdl_platform"] = str(platform)
        root_obj["bleeds_mdl_type"] = str(mdl_type)
        root_obj["bleeds_mdl_filepath"] = str(filepath)
        root_obj["bleeds_leeds_scale_base"] = [float(scale_base[0]), float(scale_base[1]), float(scale_base[2])]
        root_obj["bleeds_leeds_pos_base"] = [float(pos_base[0]), float(pos_base[1]), float(pos_base[2])]

    try:
        root_obj["bleeds_mdl_import_type"] = int(getattr(stories_ctx, "import_type", 0))
        root_obj["bleeds_mdl_geom_ptr"] = int(getattr(atomic, "geom_ptr", 0))
        root_obj["bleeds_mdl_frame_ptr"] = int(getattr(atomic, "frame_ptr", 0))
        root_obj["bleeds_mdl_hierarchy_ptr"] = int(getattr(atomic, "hierarchy_ptr", 0))
        root_obj["bleeds_mdl_material_ptr"] = int(getattr(atomic, "material_ptr", 0))
        root_obj["bleeds_mdl_render_cb"] = int(getattr(atomic, "render_cb", 0))
        root_obj["bleeds_mdl_model_info_id"] = int(getattr(atomic, "model_info_id", -1))
        root_obj["bleeds_mdl_vis_id_flag"] = int(getattr(atomic, "vis_id_flag", 0))
        root_obj["bleeds_mdl_source_filepath"] = str(filepath)

        try:
            source_template = mdl_lib._load_ped_source_template_blocks({
                "source_filepath": str(filepath),
                "frame_ptr": int(getattr(atomic, "frame_ptr", 0) or 0),
                "geom_ptr": int(getattr(atomic, "geom_ptr", 0) or 0),
                "hierarchy_ptr": int(getattr(atomic, "hierarchy_ptr", 0) or 0),
            })
            bind_bytes = (source_template.get("bind_matrix_table_bytes") or source_template.get("inverse_matrix_table_bytes") or b"")
            if isinstance(bind_bytes, (bytes, bytearray)) and bind_bytes:
                root_obj["bleeds_mdl_inverse_matrix_table_u8"] = [int(v) & 0xFF for v in bytes(bind_bytes)]
                root_obj["bleeds_mdl_inverse_matrix_count"] = int(len(bind_bytes) // 0x40)
        except Exception:
            pass

        try:
            hierarchy_ptr = int(getattr(atomic, "hierarchy_ptr", 0) or 0)
            frame_ptr = int(getattr(atomic, "frame_ptr", 0) or 0)
            if hierarchy_ptr > 0 and frame_ptr > hierarchy_ptr:
                header_size = 0x38
                with open(filepath, "rb") as hierarchy_file:
                    hierarchy_file.seek(hierarchy_ptr + 0x30)
                    entries_ptr_raw = hierarchy_file.read(4)
                    if len(entries_ptr_raw) == 4:
                        entries_ptr = int.from_bytes(entries_ptr_raw, "little")
                        if 0x80000000 <= entries_ptr <= 0x8FFFFFFF:
                            entries_ptr -= 0x80000000
                        candidate_size = int(entries_ptr - hierarchy_ptr)
                        max_size = max(0x38, min(int(frame_ptr - hierarchy_ptr), 0x80))
                        if 0x38 <= candidate_size <= max_size:
                            header_size = candidate_size
                    hierarchy_file.seek(hierarchy_ptr)
                    hierarchy_header = hierarchy_file.read(header_size)
                if len(hierarchy_header) >= 0x38:
                    root_obj["bleeds_mdl_hierarchy_header_hex"] = hierarchy_header.hex()
                    root_obj["bleeds_mdl_hierarchy_header_size"] = int(len(hierarchy_header))
                    root_obj["bleeds_mdl_hierarchy_hash_value"] = int.from_bytes(hierarchy_header[0x28:0x2C], "little")
                    root_obj["bleeds_mdl_hierarchy_tail_value"] = int.from_bytes(hierarchy_header[0x2C:0x30], "little")
        except Exception:
            pass

        ps2g = getattr(atomic, "ps2_geometry", None)
        gh = getattr(ps2g, "leeds_global_header", None) if ps2g is not None else None
        if isinstance(gh, dict) and gh:
            if gh.get("sphere") is not None:
                root_obj["bleeds_mdl_leeds_global_sphere"] = [float(v) for v in list(gh.get("sphere"))[:4]]
            if gh.get("bbox_i16") is not None:
                root_obj["bleeds_mdl_leeds_global_bbox_i16"] = [int(v) for v in list(gh.get("bbox_i16"))[:6]]
            if gh.get("scale") is not None:
                root_obj["bleeds_mdl_leeds_scale"] = [float(v) for v in list(gh.get("scale"))[:3]]
            if gh.get("translation") is not None:
                root_obj["bleeds_mdl_leeds_translation"] = [float(v) for v in list(gh.get("translation"))[:3]]
            root_obj["bleeds_mdl_leeds_vertex_section_flags"] = int(gh.get("vertex_section_flags", 0))
            root_obj["bleeds_mdl_leeds_total_vertex_count"] = int(gh.get("total_vertex_count", 0))
            root_obj["bleeds_mdl_leeds_first_tristrip_offset"] = int(gh.get("first_tristrip_offset", 0))
            root_obj["bleeds_mdl_leeds_packed_size_and_matcount"] = int(gh.get("packed_size_and_material_count", 0))

        ps2g = getattr(atomic, "ps2_geometry", None)
        if ps2g is not None and getattr(ps2g, "materials", None):
            material_names = []
            material_vcols = []
            for mat_desc in list(getattr(ps2g, "materials", []) or []):
                material_names.append(str(getattr(mat_desc, "texture", "") or "default"))
                try:
                    material_vcols.append(int(getattr(mat_desc, "rgba", 0xFFFFFFFF)) & 0xFFFFFFFF)
                except Exception:
                    material_vcols.append(0xFFFFFFFF)
            root_obj["bleeds_mdl_material_names"] = material_names
            root_obj["bleeds_mdl_material_vcols"] = material_vcols
            root_obj["bleeds_mdl_material_count"] = int(len(material_names))
    except Exception:
        pass

    try:
        arm_info = getattr(atomic, "armature", None)
        if arm_info is not None:
            frame_names_by_ptr = dict(getattr(arm_info, "frame_names", {}) or {})
            atomic_frame_ptr = int(getattr(atomic, "frame_ptr", 0) or 0)
            if atomic_frame_ptr in frame_names_by_ptr:
                root_obj["bleeds_mdl_atomic_frame_name"] = str(frame_names_by_ptr[atomic_frame_ptr])
                root_obj["bleeds_base_frame_name"] = str(frame_names_by_ptr[atomic_frame_ptr])
            writeMdlArmatureFrameMatrixArrays(root_obj, arm_info)
            hierarchy_order = buildPedHierarchyNodeOrder(
                arm_info,
                filepath=str(filepath),
                hierarchy_ptr=int(getattr(atomic, "hierarchy_ptr", 0) or 0),
            )
            writePedHierarchyNodeAttributes(root_obj, hierarchy_order)
    except Exception:
        pass

    created_objects: List[bpy.types.Object] = []

    strip_counts: list[int] = []
    try:
        dbg = getattr(stories_ctx, "debug_log", None)
        if dbg:
            import re
            for line in dbg:
                m = re.search(r"curStripVertCount:\s*(\d+)", str(line))
                if m:
                    try:
                        strip_counts.append(int(m.group(1)))
                    except Exception:
                        pass

        if strip_counts:
            try:

                root_obj.bleeds_imported_strip_counts = [int(x) for x in strip_counts]
            except Exception:
                root_obj["bleeds_imported_strip_counts"] = [int(x) for x in strip_counts]
    except Exception:

        pass

    arm_obj: bpy.types.Object = None
    if create_armature and str(mdl_type or "").upper().strip() in {"PED", "CUT"}:
        arm_obj = create_armature_from_context(
            context=context,
            stories_ctx=stories_ctx,
            collection=collection,
            name_suffix="Arm",
        )

    if platform == "PS2":
        created_objects.extend(
            build_ps2_meshes(
                context=context,
                stories_ctx=stories_ctx,
                collection=collection,
                arm_obj=arm_obj,
            )
        )
    else:
        created_objects.extend(
            build_psp_meshes(
                context=context,
                stories_ctx=stories_ctx,
                collection=collection,
                arm_obj=arm_obj,
            )
        )

    if arm_obj is None:
        mdl_type_u = str(mdl_type or "").upper().strip()
        if mdl_type_u == "VEH":
            for obj in created_objects:
                if obj is not None and obj.parent is None:
                    parent_object_keep_world(obj, root_obj)
        else:
            for obj in created_objects:
                if obj is not None and obj.type == "MESH":
                    parent_object_keep_world(obj, root_obj)
    if arm_obj is not None:
        parent_object_keep_world(arm_obj, root_obj)
        created_objects.insert(0, arm_obj)

    created_objects.insert(0, root_obj)

    return created_objects
