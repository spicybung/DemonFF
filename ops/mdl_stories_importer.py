# BLeeds - Scripts for working with R* Leeds (GTA Stories, Chinatown Wars, Manhunt 2, etc) formats in Blender
# Author: spicybung
# Years: 2025 - 

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
import math
import struct
import traceback

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper
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


#######################################################
# These are interesting... it seems AK73 was working on Stories animation rigging, indirectly at the least.
# === LCS Bone Arrays ===
commonBoneOrder = (
    "Root", "Pelvis", "Spine", "Spine1", "Neck", "Head",
    "Bip01 L Clavicle", "L UpperArm", "L Forearm", "L Hand", "L Finger", "Bip01 R Clavicle",
    "R UpperArm", "R Forearm", "R Hand", "R Finger", "L Thigh", "L Calf",
    "L Foot", "L Toe0", "R Thigh", "R Calf", "R Foot", "R Toe0"
)
kamBoneID = (
    0, 1, 2, 3, 4, 5, 31, 32, 33, 34, 35, 21, 22, 23, 24, 25, 41, 42, 43, 2000, 51, 52, 53, 2001
)
kamFrameName = (
    "Root", "Pelvis", "Spine", "Spine1", "Neck", "Head",
    "Bip01~L~Clavicle", "L~UpperArm", "L~Forearm", "L~Hand", "L~Finger", "Bip01~R~Clavicle",
    "R~UpperArm", "R~Forearm", "R~Hand", "R~Finger", "L~Thigh", "L~Calf",
    "L~Foot", "L~Toe0", "R~Thigh", "R~Calf", "R~Foot", "R~Toe0"
)
kamBoneType = (
    0, 0, 0, 2, 0, 3, 2, 0, 0, 0, 1, 0, 0, 0, 0, 1, 2, 0, 0, 1, 0, 0, 0, 1
)
kamBoneIndex = (
    "00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23"
)

commonBoneParentsLCS = {
    "Pelvis": "Root",
    "Spine": "Pelvis",
    "Spine1": "Spine",
    "Neck": "Spine1",
    "Head": "Neck",
    "Bip01 L Clavicle": "Spine1",
    "L UpperArm": "Bip01 L Clavicle",
    "L Forearm": "L UpperArm",
    "L Hand": "L Forearm",
    "L Finger": "L Hand",
    "Bip01 R Clavicle": "Spine1",
    "R UpperArm": "Bip01 R Clavicle",
    "R Forearm": "R UpperArm",
    "R Hand": "R Forearm",
    "R Finger": "R Hand",
    "L Thigh": "Pelvis",
    "L Calf": "L Thigh",
    "L Foot": "L Calf",
    "L Toe0": "L Foot",
    "R Thigh": "Pelvis",
    "R Calf": "R Thigh",
    "R Foot": "R Calf",
    "R Toe0": "R Foot"
} # o_O...
# === VCS Bone Arrays ===
commonBoneOrderVCS = (
    "root", "pelvis", "spine", "spine1", "neck", "head",
    "jaw", "bip01_l_clavicle", "l_upperarm", "l_forearm", "l_hand", "l_finger",
    "bip01_r_clavicle", "r_upperarm", "r_forearm", "r_hand", "r_finger", "l_thigh",
    "l_calf", "l_foot", "l_toe0", "r_thigh", "r_calf", "r_foot", "r_toe0"
)

commonBoneNamesVCS = (
    "Root", "Pelvis", "Spine", "Spine1", "Neck", "Head",
    "Jaw", "Bip01 L Clavicle", "L UpperArm", "L Forearm", "L Hand", "L Finger",
    "Bip01 R Clavicle", "R UpperArm", "R Forearm", "R Hand", "R Finger", "L Thigh",
    "L Calf", "L Foot", "L Toe0", "R Thigh", "R Calf", "R Foot", "R Toe0"
)

kamBoneIDVCS = (
    0, 1, 2, 3, 4, 5,
    8, 31, 32, 33, 34, 35,
    21, 22, 23, 24, 25, 41,
    42, 43, 2000, 51, 52, 53,
    2001
)

kamFrameNameVCS = (
    "Root", "Pelvis", "Spine", "Spine1", "Neck", "Head",
    "Jaw", "Bip01~L~Clavicle", "L~UpperArm", "L~Forearm", "L~Hand", "L~Finger",
    "Bip01~R~Clavicle", "R~UpperArm", "R~Forearm", "R~Hand", "R~Finger", "L~Thigh",
    "L~Calf", "L~Foot", "L~Toe0", "R~Thigh", "R~Calf", "R~Foot", "R~Toe0"
)

kamBoneTypeVCS = (
    0, 0, 0, 2, 0, 2,
    3, 2, 0, 0, 0, 1,
    0, 0, 0, 0, 1, 2,
    0, 0, 1, 0, 0, 0,
    1
)

kamBoneIndexVCS = (
    "00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23"
)    # for compatibility with Kams Scripts(3DSMax)

commonBoneParentsVCS = {
    "pelvis": "root",
    "spine": "pelvis",
    "spine1": "spine",
    "neck": "spine1",
    "head": "neck",
    "jaw": "head",
    "bip01_l_clavicle": "spine1",
    "l_upperarm": "bip01_l_clavicle",
    "l_forearm": "l_upperarm",
    "l_hand": "l_forearm",
    "l_finger": "l_hand",
    "bip01_r_clavicle": "spine1",
    "r_upperarm": "bip01_r_clavicle",
    "r_forearm": "r_upperarm",
    "r_hand": "r_forearm",
    "r_finger": "r_hand",
    "l_thigh": "pelvis",
    "l_calf": "l_thigh",
    "l_foot": "l_calf",
    "l_toe0": "l_foot",
    "r_thigh": "pelvis",
    "r_calf": "r_thigh",
    "r_foot": "r_calf",
    "r_toe0": "r_foot"
} # o_O...

# === Global variables ===
section_type = 0
file_size = 0
ptr2_before_tex = 0
ptr2_tex_name_list = 0
ptr2_ptr2_tex_name_list = 0
ptr_found = False
top_level_ptr = 0
x_scale = 0.0
y_scale = 0.0
z_scale = 0.0
atomics = []
imported_objects = []
strips = []
tex_coords = []
vertex_colors = []
normals = []
part_materials = []
part_offsets = []
cur_part = 0
valid_faces_indices = []
textures = []
atomics_count = 0
cur_atomic = 0
next_atomic = 0
imp_object_count = 0
vert_stage = 0
cur_strip_vert_count = 0
cur_strip_tvert_count = 0
cur_strip_vert_color_count = 0
cur_strip_normals_count = 0
cur_strip_face_count = 0
strip_count = 0
unknown_section_ptr = 0
cur_mat_id = 1
cur_strip_skin_data = []
cur_strip_skin_data_count = 0
cur_skin_data = None
bone_list = []
skin_modifier = None
first_frame = 0
frame_data_list = []
cur_frame_data = None
import_type = 0 
root_dummy = None
root_names = {"dummy"}
debug_log = []
found_6C018000 = False
actor_mdl = False 
local_matrix_index = 0
global_matrix_index = 0
# TODO: sort these out

# === Model Rendering Flags ===
FLAG_DRAWLAST             = 0x4 | 0x8
FLAG_ADDITIVE             = 0x8
FLAG_NO_ZWRITE            = 0x40
FLAG_NO_SHADOWS           = 0x80
FLAG_NO_BACKFACE_CULLING  = 0x200000


#######################################################
class ImportMDLOperator(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.mdl_stories"
    bl_label = "Import LCS/VCS .MDL"
    filename_ext = ".mdl"
    filter_glob: StringProperty(default="*.mdl", options={'HIDDEN'})
    
    platform: EnumProperty(
        name="Platform",
        description="Choose game/platform (PS2/PSP)",
        items=[
            ('PS2', "PS2", "Import as PS2 format (LCS/VCS PS2)"),
            ('PSP', "PSP", "Import as PSP format (LCS/VCS PSP)"),
        ],
        default='PS2'
    )

    mdl_type: EnumProperty(
        name="MDL Type",
        description="Choose type for import (affects internal file pointer logic)",
        items=[
            ('PED', "Ped", "Import as Pedestrian Model"),
            ('PROP', "Prop", "Import as Prop Model"),
        ],
        default='PED'
    )

    #######################################################
    def execute(self, context):
        return self.parse_mdl(self.filepath)
    #######################################################
    def parse_mdl(self, filepath):
        try:
            with open(filepath, "rb") as f:
                
                import_type = 0
                section_type = 0
                frame_mats = {}
                frame_mats_local = {}   # local 4x4 per frame
                frame_mats_world = {}   # global/world 4x4 per frame
                blender_mats = []
                

                #######################################################
                def add_modifiers_to_mesh(mesh_obj, armature_obj=None):
                    # Remove duplicates
                    for mod in mesh_obj.modifiers:
                        if mod.type in {'ARMATURE', 'EDGE_SPLIT'}:
                            mesh_obj.modifiers.remove(mod)

                    edge_split = mesh_obj.modifiers.new(name="EdgeSplit", type='EDGE_SPLIT')
                    edge_split.split_angle = 1.0 # seems ok
                    edge_split.use_edge_angle = True
                    edge_split.use_edge_sharp = True

                    if armature_obj:
                        arm_mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
                        arm_mod.object = armature_obj

                #######################################################
                def log(msg):
                    debug_log.append(str(msg))
                    print(msg)
                #######################################################
                def assign_skinning(obj, armature_obj, skin_indices, skin_weights, index_to_bonename):
                    # Create vertex groups
                    for bone_name in index_to_bonename.values() if isinstance(index_to_bonename, dict) else index_to_bonename:
                        if bone_name and not obj.vertex_groups.get(bone_name):
                            obj.vertex_groups.new(name=bone_name)
                    # Assign weights per vertex
                    for v_idx, (indices, weights) in enumerate(zip(skin_indices, skin_weights)):
                        for bone_i, weight in zip(indices, weights):
                            if weight > 0.0001:
                                # Map bone index to name
                                try:
                                    bone_name = index_to_bonename[bone_i]
                                except Exception:
                                    continue
                                if not bone_name:
                                    continue
                                group = obj.vertex_groups.get(bone_name)
                                if group:
                                    group.add([v_idx], weight, 'REPLACE')
                #######################################################
                def get_render_flag_names(render_flags):
                    names = []
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
                #######################################################
                def _fmt4(a, b, c, d):
                    return f"[{a: .6f}  {b: .6f}  {c: .6f}  {d: .6f}]"
                #######################################################
                def _print_matrix4(label, M: Matrix):
                    # prints in a readable 4-line block
                    print(f"{label}:")
                    print(_fmt4(M[0][0], M[0][1], M[0][2], M[0][3]))
                    print(_fmt4(M[1][0], M[1][1], M[1][2], M[1][3]))
                    print(_fmt4(M[2][0], M[2][1], M[2][2], M[2][3]))
                    print(_fmt4(M[3][0], M[3][1], M[3][2], M[3][3]))
                #######################################################
                def _is_near_identity(mat, eps=1e-4):
                    I = Matrix.Identity(4)
                    for r in range(4):
                        for c in range(4):
                            if abs(mat[r][c] - I[r][c]) > eps:
                                return False
                    return True
                #######################################################
                def read_global_matrix(f, offset, *, verbose=False, name="global@0x50", eps=1e-4) -> Matrix:

                    cur = f.tell()
                    f.seek(offset)

                    row1 = read_point3(f)  # rot
                    f.read(4)

                    row2 = read_point3(f) # rot
                    f.read(4)

                    row3 = read_point3(f) # rot
                    f.read(4)

                    row4 = read_point3(f) # position
                    f.read(4)

                    # Now go back to pointer
                    f.seek(cur)

                    scale_factor = 1.0
          
                    # Multiply 4x4 translation by the scale factor
                    x = row4.x * scale_factor
                    y = row4.y * scale_factor
                    z = row4.z * scale_factor 

                    row4_scaled = Vector((x, y, z))

                    print(f"row4 original: {row4}, row4 scaled (before translation): {row4_scaled}")
                    print(f"row4 scaled (after translation): {row4_scaled}")

                    M = Matrix((
                        (row1.x, row2.x, row3.x, row4_scaled.x),
                        (row1.y, row2.y, row3.y, row4_scaled.y),
                        (row1.z, row2.z, row3.z, row4_scaled.z),
                        (0.0,    0.0,    0.0,    1.0)
                    )) 

                    return M
                #######################################################
                def canon_frame_name(name: str) -> str:
                    return name.lower().replace("~", "_").replace(" ", "_")
                #######################################################
                def demote_nonpalette_frames(
                    arm_obj,
                    *,
                    delete_bones=True,
                    parent_to_armature=True,
                    make_axes="Y",
                    empty_size=0.05,
                    report=print
                ):
                    if not arm_obj or arm_obj.type != 'ARMATURE':
                        return

                    # Build allowed set from palettes
                    allow = set(canon_frame_name(n) for n in (list(kamFrameName) + list(kamFrameNameVCS)))

                    view_layer = bpy.context.view_layer
                    for _o in view_layer.objects:
                        _o.select_set(False)
                    arm_obj.select_set(True)
                    view_layer.objects.active = arm_obj

                    _win = bpy.context.window
                    _scr = _win.screen if _win else None
                    _area = None
                    _region = None
                    if _scr:
                        for _a in _scr.areas:
                            if _a.type == 'VIEW_3D':
                                _area = _a
                                break
                        if _area:
                            for _r in _area.regions:
                                if _r.type == 'WINDOW':
                                    _region = _r
                                    break

                    if _area and _region:
                        with bpy.context.temp_override(window=_win, area=_area, region=_region,
                                                    scene=bpy.context.scene,
                                                    view_layer=bpy.context.view_layer,
                                                    object=arm_obj, active_object=arm_obj):
                            bpy.ops.object.mode_set(mode='OBJECT')
                    else:
                        bpy.ops.object.mode_set(mode='OBJECT')

                    to_demote = []
                    for bone in arm_obj.data.bones:
                        if canon_frame_name(bone.name) not in allow:
                            # Object space rest matrix for this bone, then to world
                            M_obj = bone.matrix_local.to_4x4()
                            M_world = arm_obj.matrix_world @ M_obj

                            head_w = arm_obj.matrix_world @ bone.head_local
                            tail_w = arm_obj.matrix_world @ bone.tail_local

                            y_axis = (tail_w - head_w)
                            if y_axis.length < 1e-8:
                                R = Matrix.Identity(3)
                            else:
                                y_axis.normalize()
                                seed_x = Vector((1.0, 0.0, 0.0))
                                if abs(seed_x.dot(y_axis)) > 0.99:
                                    seed_x = Vector((0.0, 1.0, 0.0))
                                x_axis = (seed_x - y_axis * seed_x.dot(y_axis)).normalized()
                                z_axis = x_axis.cross(y_axis).normalized()
                                R = Matrix((x_axis, y_axis, z_axis)).transposed()

                            M_rot = R.to_4x4()
                            M_rot.translation = head_w

                            to_demote.append({
                                "name": bone.name,
                                "parent_name": bone.parent.name if bone.parent else None,
                                "M_world": M_rot,         # orientation from head->tail
                                "fallback_world": M_world # (unused but kept for reference)
                            })

                    if not to_demote:
                        report("No non-palette bones to demote.")
                        return

                    created = {}
                    for item in to_demote:
                        bpy.ops.object.empty_add(type='PLAIN_AXES')
                        emp = bpy.context.active_object
                        emp.name = f"{item['name']}"
                        emp.empty_display_size = empty_size
                        emp.matrix_world = item["M_world"]
                        if parent_to_armature:
                            emp.parent = arm_obj
                        created[item["name"]] = emp

                    for item in to_demote:
                        p = item["parent_name"]
                        if p and p in created:
                            created[item["name"]].parent = created[p]

                    if delete_bones:
                        if _area and _region:
                            with bpy.context.temp_override(window=_win, area=_area, region=_region,
                                                        scene=bpy.context.scene,
                                                        view_layer=bpy.context.view_layer,
                                                        object=arm_obj, active_object=arm_obj):
                                bpy.ops.object.mode_set(mode='EDIT')
                        else:
                            bpy.ops.object.mode_set(mode='EDIT')
                        ebones = arm_obj.data.edit_bones

                        for item in to_demote:
                            b = ebones.get(item["name"])
                            if b:
                                parent = b.parent
                                for child in b.children:
                                    child.parent = parent
                                ebones.remove(b)
                        if _area and _region:
                            with bpy.context.temp_override(window=_win, area=_area, region=_region,
                                                        scene=bpy.context.scene,
                                                        view_layer=bpy.context.view_layer,
                                                        object=arm_obj, active_object=arm_obj):
                                bpy.ops.object.mode_set(mode='OBJECT')
                        else:
                            bpy.ops.object.mode_set(mode='OBJECT')

                    report(f"Demoted {len(to_demote)} non-palette bones to empties.")
                #######################################################
                def process_frame(f, frame_ptr, parent_world=None, parent_dummy=None, dummies_list=None, log=None):
                    global local_matrix_index, global_matrix_index
                    if frame_ptr == 0:
                        return
                    
                    if parent_world is None:
                        parent_world = Matrix.Identity(4)

                    # === Read the bone name ===
                    if self.platform == 'PS2':
                        f.seek(frame_ptr + 0xA4)
                    elif self.platform == 'PSP':
                        f.seek(frame_ptr + 0xA8)
                    # For VCS import_type==2, skip 4 more bytes
                    if import_type == 2:
                        f.seek(4, 1)
                    bone_name_ptr = struct.unpack('<I', f.read(4))[0]
                    if bone_name_ptr != 0:
                        cur = f.tell()
                        f.seek(bone_name_ptr)
                        name_bytes = bytearray()
                        while True:
                            b = f.read(1)
                            if b == b'\x00' or not b:
                                break
                            name_bytes.append(b[0])
                        bone_name = name_bytes.decode('utf-8', errors='ignore')
                        f.seek(cur)
                    else:
                        bone_name = "Bone"

                    # === Filter out helpers === 
                    skip_names = {"dummy"}
                    if bone_name.lower() in skip_names:
                        if log:
                            log(f"🗑️ Skipping dummy '{bone_name}' (not imported)")
       
                    else:
                        # === Read the 3x4 matrix for this bone ===
                        f.seek(frame_ptr + 0x10)  # local matrix starts here
                        mat, _, _, = read_local_matrix(f)

                        local_matrix_index += 1
                        log(f"Local 4x4 Matrix {local_matrix_index}: {mat}")

                        M_world = parent_world @ mat
                        
                        frame_mats[frame_ptr] = mat 
                        frame_mats_world[frame_ptr] = M_world

                        R = Matrix.Rotation(-3.14159265 / 2, 4, 'X')
                        
                        # There's a global matrix here that acts as an identity in LCS(not the case for VCS it seems)
                        mat_global = read_global_matrix(f, frame_ptr + 0x50, verbose=True, name=f"Root or special: 0x{frame_ptr:X} '{bone_name}'")
                        
                        global_matrix_index += 1
                        log(f"Global 4x4 Matrix {global_matrix_index}: {mat_global}")

                        bone_name_lc = bone_name.lower()
                        if bone_name_lc in root_names:
                            # Create the root dummy as an Empty
                            bpy.ops.object.empty_add(type='PLAIN_AXES')
                            cur_dummy = bpy.context.active_object
                            cur_dummy.empty_display_size = 0.05
                            cur_dummy.name = bone_name
                            cur_dummy.matrix_world = R @ M_world 
                            # Save reference
                            root_dummy = cur_dummy
                            if log:
                                log(f"✔ Created root dummy '{bone_name}' at 0x{frame_ptr:X}")
                            # Test: Do NOT add root_dummy to dummies_list (so it's not converted to a bone)
                        else:
                            bpy.ops.object.empty_add(type='PLAIN_AXES')
                            cur_dummy = bpy.context.active_object
                            cur_dummy.empty_display_size = 0.05
                            cur_dummy.name = bone_name

                            M = frame_mats.get(current_frame_ptr)

                            if M is not None:
                                cur_dummy.matrix_world = mat
                            if parent_dummy:
                                cur_dummy.parent = parent_dummy
                            if dummies_list is not None:
                                dummies_list.append(cur_dummy)
                            if log:
                                log(f"✔ Created dummy '{bone_name}' at 0x{frame_ptr:X}, parent='{parent_dummy.name if parent_dummy else 'None'}'")
                        
                    # === Recursively process children and siblings ===
                    # Find the first child pointer (at offset 0x90)
                    f.seek(frame_ptr + 0x90)
                    child_ptr = struct.unpack('<I', f.read(4))[0]
                    # Siblings (next frame) pointer at 0x94
                    f.seek(frame_ptr + 0x94)
                    sibling_ptr = struct.unpack('<I', f.read(4))[0]

                    # Only parent real dummies, not helpers
                    real_parent = cur_dummy if bone_name.lower() not in skip_names else parent_dummy

                    # Recursively process first child (if any)
                    if child_ptr != 0:
                        process_frame(
                            f,
                            child_ptr,
                            parent_world=M_world,
                            parent_dummy=cur_dummy if bone_name.lower() not in {"dummy"} else parent_dummy,
                            dummies_list=dummies_list,
                            log=log,
                        )

                    # Recursively process next sibling (if any)
                    if sibling_ptr != 0:
                        process_frame(
                            f,
                            sibling_ptr,
                            parent_world=parent_world,
                            parent_dummy=parent_dummy,
                            dummies_list=dummies_list,
                            log=log,
                        )

                #######################################################   
                def dummies_to_armature(dummies, armature_name="Armature", bone_size=0.05, delete_dummies=True):

                    if not dummies:
                        print("No dummies provided to dummies_to_armature")
                        return None

                    # Record parent relationships by object name
                    dummy_name_to_obj = {obj.name: obj for obj in dummies}
                    dummy_parents = {obj.name: obj.parent.name if obj.parent and obj.parent in dummies else None for obj in dummies}

                    # Create armature and object
                    arm_data = bpy.data.armatures.new(armature_name)
                    arm_obj = bpy.data.objects.new(armature_name, arm_data)
                    bpy.context.collection.objects.link(arm_obj)
                    bpy.context.view_layer.objects.active = arm_obj
                    bpy.ops.object.mode_set(mode='EDIT')

                    name_to_bone = {}

                    # Use world matrix to position bones (head at dummy, tail +Y in local)
                    for dummy in dummies:
                        world_matrix = dummy.matrix_world
                        local_matrix = arm_obj.matrix_world.inverted() @ world_matrix
                        bone = arm_data.edit_bones.new(dummy.name)
                        head = local_matrix.to_translation()
                        tail = head + local_matrix.to_3x3() @ Vector((0, bone_size, 0))
                        bone.head = head
                        bone.tail = tail
                        bone.roll = 0
                        name_to_bone[dummy.name] = bone

                    # Set parenting on bones
                    for dummy in dummies:
                        parent_name = dummy_parents[dummy.name]
                        if parent_name and parent_name in name_to_bone:
                            name_to_bone[dummy.name].parent = name_to_bone[parent_name]

                    bpy.ops.object.mode_set(mode='OBJECT')

                    # delete our helper empties/dummies
                    if delete_dummies:
                        bpy.ops.object.select_all(action='DESELECT')
                        for dummy in dummies:
                            dummy.select_set(True)
                        bpy.ops.object.delete()

                    print(f"Converted {len(dummies)} dummies to bones in '{armature_name}'")
                    return arm_obj    
                #######################################################
                def read_point3(f):
                    """Reads 3 float32s from the file and returns a Vector."""
                    return Vector(struct.unpack('<3f', f.read(12))) 
                #######################################################
                def read_local_matrix(f):
                    """Reads a 3x4 matrix and logs the starting offset before reading."""
                    matrix_offset = f.tell()  
                    
                    row1 = read_point3(f)  # rot
                    f.read(4)

                    row2 = read_point3(f) # rot
                    f.read(4)

                    row3 = read_point3(f) # rot
                    f.read(4)

                    row4 = read_point3(f) # position
                    f.read(4)

                    scale_factor = 1.0
                    # scaleFactor = 100 # always >100, never lower!
                    # multiply matrix translation row by scale factor
                    x = row4.x * scale_factor
                    y = row4.y * scale_factor
                    z = row4.z * scale_factor 

                    row4_scaled = Vector((x, y, z))

                    print(f"row4 original: {row4}, row4 scaled (before translation): {row4_scaled}")
                    print(f"row4 scaled (after translation): {row4_scaled}")

                    mat = Matrix((
                        (row1.x, row2.x, row3.x, row4_scaled.x),
                        (row1.y, row2.y, row3.y, row4_scaled.y),
                        (row1.z, row2.z, row3.z, row4_scaled.z),
                        (0.0,    0.0,    0.0,    1.0)
                    )) 
                    return mat, matrix_offset, (row1, row2, row3, row4_scaled) # Read 3x4 Matrix transposed as 4x4
                #######################################################
                def assign_strip_weights(
                    big_obj, arm_obj,
                    strip_skin_idx, strip_skin_wts,
                    index_to_bonename, vbase,
                    normalize=True, per_vertex_replace=True, eps=1e-8
                ):
                    assert big_obj.type == 'MESH'
                    assert arm_obj and arm_obj.type == 'ARMATURE'
                    assert len(strip_skin_idx) == len(strip_skin_wts)

                    arm_mod = next((m for m in big_obj.modifiers if m.type == 'ARMATURE'), None)
                    if arm_mod is None:
                        arm_mod = big_obj.modifiers.new("Armature", 'ARMATURE')
                    arm_mod.object = arm_obj
                    #######################################################
                    def ensure_group(name: str):
                        vg = big_obj.vertex_groups.get(name)
                        return vg if vg else big_obj.vertex_groups.new(name=name)

                    for local_v, (inds, wts) in enumerate(zip(strip_skin_idx, strip_skin_wts)):
                        vidx = vbase + local_v
                        if vidx >= len(big_obj.data.vertices):
                            raise RuntimeError(f"Strip write OOB: vidx={vidx}, total={len(big_obj.data.vertices)}")

                        if per_vertex_replace:
                            for vg in big_obj.vertex_groups:
                                try: vg.remove([vidx])
                                except RuntimeError: pass

                        if normalize:
                            s = sum(max(0.0, float(w)) for w in wts)
                            wts = [(float(w)/s if s > 0.0 else 0.0) for w in wts]
                        else:
                            wts = [float(w) if (w is not None and w > 0.0) else 0.0 for w in wts]

                        for bi, w in zip(inds, wts):
                            if w <= eps:
                                continue
                            bone_name = index_to_bonename.get(int(bi))
                            if not bone_name:
                                continue
                            vg = ensure_group(bone_name)
                            vg.add([vidx], w, 'REPLACE')
                #######################################################
                def build_index_to_bonename(armature_obj, log=print):
                    lcs_palette = list(commonBoneOrder) if 'commonBoneOrder' in globals() else []
                    vcs_palette = list(commonBoneNamesVCS) if 'commonBoneNamesVCS' in globals() else []

                    def canon(s):
                        return s.lower().replace("~", "_").replace(" ", "_")

                    arma_names = [b.name for b in armature_obj.data.bones]
                    arma_set = {canon(n) for n in arma_names}

                    def score(palette):
                        return sum(1 for n in palette if canon(n) in arma_set)

                    candidates = []
                    if lcs_palette: candidates.append(("LCS", lcs_palette, score(lcs_palette)))
                    if vcs_palette: candidates.append(("VCS", vcs_palette, score(vcs_palette)))
                    candidates.sort(key=lambda x: x[2], reverse=True)

                    chosen = None
                    if candidates and candidates[0][2] > 0:
                        chosen = candidates[0][1]
                        log(f"✔ Bone palette: {candidates[0][0]} (matched {candidates[0][2]} names)")
                    else:
                        chosen = sorted(arma_names, key=lambda s: canon(s))
                        log("⚠ No canonical palette matched; using name-sorted armature order as palette")

                    index_to_bonename = {}
                    canon_to_real = {canon(n): n for n in arma_names}
                    for i, palette_name in enumerate(chosen):
                        c = canon(palette_name)
                        real = canon_to_real.get(c)
                        if real:
                            index_to_bonename[i] = real
                        else:
                            index_to_bonename[i] = None

                    return index_to_bonename
                #######################################################
                def _ensure_color_layer(mesh, name="Col", *, prefer_byte=True):
                    # Use BYTE_COLOR for 0–255 RGBA, FLOAT_COLOR for 0.0–1.0
                    ca = mesh.color_attributes.get(name)
                    if ca is None:
                        ca_type = 'BYTE_COLOR' if prefer_byte else 'FLOAT_COLOR'
                        ca = mesh.color_attributes.new(name=name, type=ca_type, domain='CORNER')
                    else:
                        if ca.domain != 'CORNER' or ca.data_type not in {'BYTE_COLOR', 'FLOAT_COLOR'}:
                            mesh.color_attributes.remove(ca)
                            ca = mesh.color_attributes.new(name=name, type='BYTE_COLOR' if prefer_byte else 'FLOAT_COLOR', domain='CORNER')
                    return ca
                #######################################################
                def _blit_vertex_colors(mesh, faces, colors_any, *, assume_255=True):
                    prefer_byte = assume_255
                    ca = _ensure_color_layer(mesh, "Col", prefer_byte=prefer_byte)
                    loop_data = ca.data
                    verts = mesh.vertices
                    loops = mesh.loops

                    def _norm(c):
                        # Normalize to 0..1 float for assignment; Blender accepts both,
                        # but we convert consistently here.
                        if not c:
                            return (1.0, 1.0, 1.0, 1.0)
                        if len(c) == 3:
                            r, g, b = c
                            a = 255 if assume_255 and isinstance(r, int) else 1.0
                        else:
                            r, g, b, a = c[:4]
                        if isinstance(r, int) or isinstance(g, int) or isinstance(b, int) or isinstance(a, int):
                            # Treat numbers as 0–255
                            return (r/255.0, g/255.0, b/255.0, (a/255.0 if a is not None else 1.0))
                        return (float(r), float(g), float(b), float(a if a is not None else 1.0))

                    per_vertex = (len(colors_any) == len(verts))
                    per_corner = (len(colors_any) == len(loops))

                    if per_corner:
                        for li in range(len(loops)):
                            loop_data[li].color = _norm(colors_any[li])
                        return

                    if per_vertex:
                        # Map each loop's vertex_index to a color
                        for li, loop in enumerate(loops):
                            vi = loop.vertex_index
                            loop_data[li].color = _norm(colors_any[vi])
                        return

                    total_loops = sum(len(p) for p in faces)
                    if len(colors_any) == total_loops:
                        cursor = 0
                        for poly in mesh.polygons:
                            for li in range(poly.loop_start, poly.loop_start + poly.loop_total):
                                loop_data[li].color = _norm(colors_any[cursor])
                                cursor += 1
                        return

                    # If we got here, shape doesn't match so fill white so that the layer exists.
                    for li in range(len(loops)):
                        loop_data[li].color = (1.0, 1.0, 1.0, 1.0)

                #######################################################
                def create_material(desc, *, index=0, report=print):
                    tex_name = desc.get("texture") or f"mat_{index:02d}"
                    rgba_u32 = desc.get("rgba")
                    spec = desc.get("specular")

                    mat_name = f"{tex_name}"
                    material = bpy.data.materials.get(mat_name)
                    if material is None:
                        material = bpy.data.materials.new(mat_name)
                    material.use_nodes = True

                    nt = material.node_tree
                    nodes = nt.nodes
                    links = nt.links

                    out = nodes.get("Material Output")
                    if out is None:
                        out = nodes.new("ShaderNodeOutputMaterial")
                    for n in [n for n in nodes if n != out]:
                        nodes.remove(n)

                    principled = nodes.new("ShaderNodeBsdfPrincipled")
                    principled.location = (-200, 0)
                    out.location = (200, 0)
                    links.new(principled.outputs["BSDF"], out.inputs["Surface"])

                    # Color from RGBA (AARRGGBB)
                    if isinstance(rgba_u32, int):
                        a = ((rgba_u32 >> 24) & 0xFF) / 255.0
                        r = ((rgba_u32 >> 16) & 0xFF) / 255.0
                        g = ((rgba_u32 >>  8) & 0xFF) / 255.0
                        b = ((rgba_u32 >>  0) & 0xFF) / 255.0
                        principled.inputs["Base Color"].default_value = (r, g, b, 1.0)
                        principled.inputs["Alpha"].default_value = a
                        if a < 0.999:
                            material.blend_method = 'BLEND'
                            material.shadow_method = 'HASHED'
                    else:
                        principled.inputs["Base Color"].default_value = (0.8, 0.8, 0.8, 1.0)

                    if spec is not None:
                        principled.inputs["Specular"].default_value = max(0.0, min(1.0, float(spec)))

                    report(f"✔ Built Blender material: {mat_name}")
                    return material
                #######################################################
                def _ensure_material_slots(obj, mats, *, report=print):
                    me = obj.data
                    me.materials.clear()
                    for m in mats:
                        me.materials.append(m)
                    id_to_slot = {i: i for i in range(len(mats))}
                    report(f"✔ Assigned {len(mats)} material slots to object '{obj.name}'")
                    return id_to_slot
                #######################################################
                def _ensure_single_material(obj, mat, *, report=print):
                    me = obj.data
                    me.materials.clear()
                    me.materials.append(mat)
                    report(f"✔ Set single material '{mat.name}' on object '{obj.name}'")
                #######################################################
                def read_i8():
                    return struct.unpack('<b', f.read(1))[0]    # Reads a signed 8-bit integer
                #######################################################
                def read_u8():
                    return struct.unpack("<B", f.read(1))[0]    # Reads an unsigned 8-bit integer
                #######################################################
                def read_i16():
                    return struct.unpack('<h', f.read(2))[0]    # Reads a signed 16-bit integer
                #######################################################
                def read_u16():
                    return struct.unpack("<H", f.read(2))[0]    # Reads an unsigned 16-bit integer
                #######################################################
                def read_i32():
                    return struct.unpack("<i", f.read(4))[0]    # Reads a signed 32-bit integer
                #######################################################
                def read_u32():
                    return struct.unpack("<I", f.read(4))[0]    # Reads an unsigned 32-bit integer
                #######################################################
                def read_bu32():
                    return struct.unpack(">I", f.read(4))[0]    # Reads a big endian unsigned 32-bit integer
                #######################################################
                def read_f32():
                    return struct.unpack("<f", f.read(4))[0]    # Reads a float-32
                #######################################################
                def read_string(ptr):
                    if ptr == 0:
                        return None
                    current = f.tell()
                    f.seek(ptr)
                    s = b""
                    while True:
                        c = f.read(1)
                        if c == b"\x00" or c == b"":
                            break
                        s += c
                    f.seek(current)
                    return s.decode("utf-8", errors="ignore")
                #######################################################
                # === Read Stories PS2/PSP MDL Header ===
                log(f"✔ Opened: {filepath}")
                if f.read(4) != b'ldm\x00':  # ModelInfo identifier for file(i.e PedModel) - where we begin to read the file(TODO: WRLD)
                    self.report({'ERROR'}, "Invalid Stories MDL header") # Not a Stories MDL?
                    return {'CANCELLED'}     # eject process if invalid
                shrink = read_u32()          # 1 if GTAG resource image, else always 0(file not shrank). Bytes also used in Global/Master/Slave WRLDs
                file_len = read_u32()        # physical fiile size
                local_numTable = read_u32()  # local reallocation table (NOTE: if local_numTable = global_numTable, than file = global/one table only)
                global_numTable = read_u32() # global pointer reallocation table
                
                # --- If PSP, skip 4 bytes after global_numTable ---
                is_psp = (self.platform == 'PSP') # import_type = 3
                if is_psp:
                    log("Detected PSP MDL: Skipping 4 bytes after global_numTable.")
                    f.seek(-4, 1)  # Skip 4 bytes (unknown, only on PSP)

                if global_numTable == (local_numTable + 4): # if global_numTable after local than = VCS else LCS
                    actor_MDL = True    # than this is an actor/ped or building/prop
                    log(f"✔ Ped/actor or prop MDL detected.")
                else:
                    f.seek(-4, 1)
                    numEntries = read_u32()  # read number of entries after local numTable?(=/= VCS)
                    log(f"✔ Non-actor MDL detected: possibly a prop.") # than modelinfo =/= ped, although props may use an armature
                    if is_psp: 
                        f.seek(4, 1)
                
                numEntries = read_u32()  # number of entries
                ptr2_before_tex = read_u32()
                allocMem = read_u32()  # amount of memory allocated to file(maximum file size)

                # Peek at the DWORD just after allocMem, without consuming it for flow
                next_ptr_offset = f.tell()
                possible_ptr = read_u32()
                log(f"Pointer after allocMem (offset 0x{next_ptr_offset:X}): 0x{possible_ptr:X}")

                def is_known_vtable(val):
                    KNOWN_VTABLES = {
                        0xAA02,        # VCSCLUMP (PS2)
                        0x00000002,    # LCSCLUMP or CLUMPPSP
                    }
                    return val in KNOWN_VTABLES or (val & 0xFFFF) in KNOWN_VTABLES

                peek_type = "unknown"
                string_val = ""
                file_current = f.tell()
                # Defensive: check if within file
                if 0 < possible_ptr < file_len:
                    f.seek(possible_ptr)
                    peek_bytes = f.read(8)
                    # Try to decode as string (ascii+null)
                    s = peek_bytes.split(b'\x00')[0]
                    if s and all(32 <= b <= 126 for b in s):
                        string_val = s.decode('ascii', errors='ignore')
                        peek_type = "string"
                    else:
                        # Try if it's a vtable or struct
                        val = struct.unpack('<I', peek_bytes[:4])[0]
                        if is_known_vtable(val):
                            peek_type = "vtable"
                        else:
                            peek_type = "struct_or_flags"
                    f.seek(file_current)
                else:
                    # It might just be a local offset (not a global pointer)
                    # Try interpreting as a direct value (for vtable/flags)
                    if is_known_vtable(possible_ptr):
                        peek_type = "vtable"
                    elif 32 <= (possible_ptr & 0xFF) <= 126:
                        peek_type = "string_candidate"
                    else:
                        peek_type = "unknown"
                log(f"Analysis: pointer after allocMem is {peek_type}" + (f" ('{string_val}')" if string_val else ""))

                if peek_type == "vtable":
                    log("This pointer is a vtable/top-level struct (Clump/Atomic etc).")
                    # Top-level pointer, proceed to read top ptr, section parsing as before
                    renderflags_offset = None
                    top_level_ptr = possible_ptr
                elif peek_type == "string" or peek_type == "string_candidate":
                    log(f"This pointer is a string (probably a material/texture name): '{string_val}'")
                    renderflags_offset = None
                elif peek_type == "struct_or_flags":
                    log("This pointer appears to point to a struct or flags; treat as renderflags offset or substruct.")
                    renderflags_offset = possible_ptr
                    if self.mdl_type == 'PROP':
                        f.seek(-4, 1)
                    top_level_ptr = read_u32()

                else:
                    log("Pointer after allocMem type could not be determined; treating as unknown/flags.")
                    renderflags_offset = possible_ptr
                    top_level_ptr = read_u32()

                log(f"File Size: 0x{file_len}")
                log(f"Local Realloc Table: 0x{local_numTable:X}, Global Realloc Table: 0x{global_numTable:X}")
                log(f"Number of entries: 0x{numEntries}")
                log(f"Ptr2BeforeTexNameList: 0x{ptr2_before_tex:X}")
                log(f"Allocated memory: 0x{allocMem}")
                log(f"Top-level ptr or magic value: 0x{top_level_ptr:X}")

                f.seek(top_level_ptr)

                top_magic = read_u32()

                # Markers(vTables?) for R* Leeds section extensions since Leeds Engine doesn't use RW plug-ins
                LCSCLUMPPS2 = 0x00000002     # shared in LCS across all platforms, as well as VCS PSP 
                VCSCLUMPPS2 = 0x0000AA02
                CLUMPPSP   = 0x00000002
                LCSATOMIC1 = 0x01050001      # renders first?
                LCSATOMIC2 = 0x01000001      # renders last?
                VCSATOMIC1 = 0x0004AA01      # renders first?
                VCSATOMIC2 = 0x00AA0003      # renders last? props only?
                VCSATOMICPSP1 = 0x01F40400   # this structure appears similar to VCSATOMIC1&2
                VCSATOMICPSP2 = 0x01F40400   # (?)
                # VCSPS2FRAME1  = 0x0003AA01  # the root frame for PS2 models
                # VCSPS2FRAME2  = 0x0180AA00  # subsequent frames
                # VCSFRAMEPSP1  = 0X0380B100  # the root frame for PSP models
                # VCSFRAMEPSP2  = 0x0180B200  # subsequent frames

                if top_magic in (LCSCLUMPPS2, VCSCLUMPPS2):
                    section_type = 7
                    if self.platform == 'PSP':
                        if top_magic == CLUMPPSP:
                            log(f" Top magic matches PSP values, setting import type 3.")
                            import_type = 3 
                    else:
                        import_type = 1 if top_magic == LCSCLUMPPS2 else 2
                elif top_magic in (LCSATOMIC1, LCSATOMIC2, VCSATOMIC1, VCSATOMIC2):
                    section_type = 2
                    import_type = 1 if top_magic in (LCSATOMIC1, LCSATOMIC2) else 2
                elif top_magic in (VCSATOMICPSP1, VCSATOMICPSP2):
                    section_type = 2
                    import_type = 3 if top_magic in (VCSATOMICPSP1, VCSATOMICPSP2) else 2

                log(f"Section Type: {section_type}, Import Type: {import_type}")
                
                # === Update parsing state to Section Type: 7 (Clump) if successful ===
                if section_type == 7:
                    log("✔ Detected Section Type: 7 (Clump)")
                    #RslElementGroup
                    clump_id = read_u32()       # vTable??
                    first_frame = read_u32()    # our entry into frames
                    first_atomic = read_u32()   # our entry into atomics
                    atomic_seek = first_atomic - 0x1C   # we'll start by seeking & reading atomics to see if we can get frames
                    f.seek(atomic_seek)
                    section_type = 2    # change section type to 2(atomics)
                    
                # === Update parsing state to Section Type: 2 (Atomic) if successful -
                if section_type == 2: 
                    log("✔ Detected Section Type: 2 (Atomic)")
                
                    atomics = []
                    frame_data_list = [] # if theres frames, we create a list
                    dummies = []    # dummylist for bones
                    bone_list = []  # if there's bones, we create a list
                    frame_ptr_list = []
                    root_bone_link = not actor_mdl # not dun goofing here anymore, it would appear
                    cur_atomic_index = 1
                    
                    # RslElement
                    atomic_start = f.tell()
                    log(f"Atomic section begins at: 0x{atomic_start:X}")

                    if self.mdl_type == 'PROP':
                        f.seek(-4, 1)
                        log("MDL type is Prop: performed f.seek(-4, 1) before reading atomic_id.")
                    else:
                        log("MDL type is Ped: did NOT perform f.seek(-4, 1) before reading atomic_id.")

                    atomic_id = read_u32()  # vTable?
                    
                    frame_ptr = read_u32()  # our entry into the frame(s)

                    current_frame_ptr = frame_ptr
                    
                    prev_link = read_u32() # prev atomic ptr
                    
                    prev_link2 = read_u32() # prev atomic ptr again
                    
                    padAAAA = read_u32()       # AAAAAAAA (necessary for Leeds Engine rendering)

                    geom_ptr = read_u32()   # our entry into the geometry
                    
                    f.seek(4, 1)    # seeking back and forth feels like violating the MDL file
                    
                    clump_ptr = read_u32()  # link back to Clump
                    link_ptr = read_u32()   # RSLLLink
                    
                    render_cb = read_u32()  # render callback - maybe reading this wrong?(TODO: verify for export)
                    model_info_id = struct.unpack("<h", f.read(2))[0]
                    vis_id_flag = struct.unpack("<H", f.read(2))[0]
                    hierarchy_ptr = read_u32()

                    log(f"frame_ptr: 0x{frame_ptr:X}")
                    
                    log(f"previous link: {prev_link:X}")
                    log(f"previous link 2: {prev_link2:X}")
                    
                    log(f"pad AAAA: {padAAAA:X}")
                    
                    log(f"geom_ptr:      0x{geom_ptr:X}")
                    
                    log(f"clump_ptr:     0x{clump_ptr:X}")
                    log(f"link_ptr:      0x{link_ptr:X}")
                    
                    log(f"render_cb:     0x{render_cb:X}")
                    log(f"model_info_id: {model_info_id}")
                    log(f"vis_id_flag:   0x{vis_id_flag:X}")
                    log(f"hierarchy_ptr: 0x{hierarchy_ptr:X}")

                    # Save current pos to return later
                    return_pos = f.tell()

                    cur_frame_ptr = frame_ptr
                    first_frame = cur_frame_ptr
                    dummies = []
                    
                    if self.mdl_type == 'PED':
                        
                        # === Frame/bone loop ===
                        process_frame(f, frame_ptr, parent_world=None, parent_dummy=None, dummies_list=dummies, log=log)
                        
                        # === Map bone names to dummy objects ===
                        def canonical_bone_name(name):
                            return name.lower().replace("~", "_").replace(" ", "_")

                        bone_name_to_dummy = {canonical_bone_name(obj.name): obj for obj in dummies}
                        
                        # === Use our dummy helpers to create bones & set up armature ===
                        armature_obj = dummies_to_armature(dummies, armature_name="Armature", bone_size=0.05, delete_dummies=True)
                        
                        demote_nonpalette_frames(armature_obj, delete_bones=True, parent_to_armature=True, empty_size=0.05, report=log)

                    # For BUILDING/PROP: skip ALL bone logic, just continue to geometry
                    f.seek(geom_ptr)
                    section_type = 3
                    
                    # === Update parsing state to section type 3 (Geometry) if successful ===                     
                    if section_type == 3:
                        log("Detected Section Type: 3 (Geometry)")

                        if self.platform == 'PS2':
                                     
                            #RslMaterialList
                            part_materials = []
                            part_offsets = []
                            current_atomic_material_list = []

                            _ = read_u32()  # unknown0
                            _ = read_u32()  # unknown1
                            _ = read_u32()  # unknown2 (TODO: what are these?)

                            material_list_ptr = read_u32()
                            material_count = read_u32()

                            log(f"🧵 Material List Ptr: 0x{material_list_ptr:X}")
                            log(f"🎨 Material Count: {material_count}")

                            if material_count > 0:
                                old_pos = f.tell()
                                f.seek(material_list_ptr)

                                for i in range(material_count):
                                    log(f"  ↪ Reading Material {i + 1}/{material_count}")
                                    current_material = {
                                        "offset": 0,
                                        "texture": None,
                                        "rgba": None,
                                        "specular": None
                                    }
                                    
                                    #RslMaterial
                                    cur_mat_ptr = read_u32()
                                    log(f"    ⤷ Material Ptr: 0x{cur_mat_ptr:X}")
                                    old_mat_pos = f.tell()
                                    f.seek(cur_mat_ptr)

                                    tex_ptr = read_u32()
                                    log(f"    ⤷ Texture Ptr: 0x{tex_ptr:X}")
                                    if tex_ptr > 0:
                                        temp_pos = f.tell()
                                        f.seek(tex_ptr)
                                        tex_name = read_string(tex_ptr)
                                        current_material["texture"] = tex_name
                                        log(f"    🎯 Texture Name: {tex_name}")
                                        f.seek(temp_pos)

                                    rgba = read_u32()
                                    current_material["rgba"] = rgba
                                    log(f"    🎨 RGBA Value: 0x{rgba:08X}")

                                    _ = read_u32()  # Unknown value (what is this?)

                                    spec_ptr = read_u32()
                                    log(f"    ⤷ Specular Ptr: 0x{spec_ptr:X}")
                                    if spec_ptr > 0:
                                        temp_pos = f.tell()
                                        f.seek(spec_ptr)
                                        _ = read_u32()
                                        _ = read_u32()
                                        specular_value = read_f32()
                                        current_material["specular"] = specular_value
                                        log(f"    ✨ Specular: {specular_value:.6f}")
                                        f.seek(temp_pos)

                                    f.seek(old_mat_pos)
                                    current_atomic_material_list.append(current_material)

                                    # TODO: MatFX here?

                                f.seek(old_pos)

                                # === Build Blender materials for this atomic, in the same order as material_id ===
                                blender_mats.clear()
                                for i, mdesc in enumerate(current_atomic_material_list):
                                    bm = create_material(mdesc, index=i, report=log)
                                    blender_mats.append(bm)
                                
                                # Skip 13 DWORDs
                                for i in range(13):
                                    f.read(4)
                                log("✔ Skipped 13 DWORDs")

                                # Read X, Y, Z scale as floats
                                
                                xscale_offset = f.tell()
                                xScale = struct.unpack('<f', f.read(4))[0]
                                yscale_offset = f.tell()
                                yScale = struct.unpack('<f', f.read(4))[0]
                                zscale_offset = f.tell()
                                zScale = struct.unpack('<f', f.read(4))[0]

                                log(f"🟧 xScale is at file offset: 0x{xscale_offset:X}")
                                log(f"🟧 yScale is at file offset: 0x{yscale_offset-4:X}")
                                log(f"🟧 zScale is at file offset: 0x{zscale_offset-4:X}")
                                log(f"✔ xScale: {xScale}, yScale: {yScale}, zScale: {zScale}")

                                # Read overall translation for meshes
                                scaleFactor = 100

                                # Read overall translation X, multiply by scale factor, divide by 100
                                offset_x = f.tell()
                                tx = struct.unpack('<f', f.read(4))[0] * scaleFactor / 100
                                log(f"✔ TranslationFactor X read at file offset: 0x{offset_x:X} ({offset_x})")

                                # Read overall translation Y, multiply by scale factor, divide by 100
                                offset_y = f.tell()
                                ty = struct.unpack('<f', f.read(4))[0] * scaleFactor / 100
                                log(f"✔ TranslationFactor Y read at file offset: 0x{offset_y:X} ({offset_y})")

                                # Read overall translation Z, multiply by scale factor, divide by 100
                                offset_z = f.tell()
                                tz = struct.unpack('<f', f.read(4))[0] * scaleFactor / 100
                                log(f"✔ TranslationFactor Z read at file offset: 0x{offset_z:X} ({offset_z})")

                                # Store overall Translation as tuple
                                TranslationFactor = (tx, ty, tz)

                                log(f"✔ TranslationFactor: {TranslationFactor}")
                                
                                # Parse part offsets/materials
                                partOffsets = []
                                partMaterials = []

                                temp = struct.unpack('<I', f.read(4))[0]
                                while (temp & 0x60000000) != 0x60000000:
                                    # 6 DWORDs, skipped
                                    for i in range(6):
                                        f.read(4)
                                    temp_offset = struct.unpack('<I', f.read(4))[0]
                                    partOffsets.append(temp_offset)
                                    short1 = struct.unpack('<H', f.read(2))[0]  # unused
                                    temp_mat = struct.unpack('<H', f.read(2))[0]
                                    partMaterials.append(temp_mat)
                                    f.read(4)  # skip
                                    f.read(4)  # skip
                                    f.read(4)  # skip
                                    temp = struct.unpack('<I', f.read(4))[0]
                                    temp = temp & 0x60000000
                                log(f"✔ partOffsets: {partOffsets}")
                                log(f"✔ partMaterials: {partMaterials}")

                                # Seek back 4 bytes
                                f.seek(-4, 1)

                                # Geometry Parts Sub-Section
                                # - going through our splits here 
                                strips = []
                                stripCount = 0
                                geoStart = f.tell()
                                log(f"geoStart: 0x{geoStart:X}")

                                # Iterate through each geometry part using its offset in the file
                                for part_index, part_offset in enumerate(partOffsets):
                                    # Calculate the absolute file offset for the start of this geometry part
                                    part_addr = geoStart + part_offset

                                    # Prepare empty lists to accumulate the vertices and faces for this part
                                    part_verts = []
                                    part_faces = []
                                    strips_meta = []
                                    part_vcols = []
                                    part_loop_colors = []

                                    # vert_base is always zero for each part; it would be used if vertex indices were global
                                    vert_base = 0

                                    # Determine the file offset for the next part (or end of section if this is the last part)
                                    if part_index + 1 < len(partOffsets):
                                        # If not the last part, next_part_addr is the offset of the next part
                                        next_part_addr = geoStart + partOffsets[part_index + 1]
                                    else:
                                        # If this is the last part, seek to the end of the file/section to set the boundary
                                        f.seek(0, 2)
                                        next_part_addr = f.tell()
                                    
                                    # Move the file pointer to the start of this geometry part
                                    f.seek(part_addr)
                                    
                                    # Log which part we are about to read and its absolute offset in the file
                                    log(f"\n🔄 Reading geometry dmaOffset {part_index + 1}/{len(partOffsets)} (Offset: 0x{part_addr:X})")
                               
                                    if 'partOffsets' in locals():
                                        log("====== Geometry dmaPacket Offsets ======")
                                        for i, part_offset in enumerate(partOffsets): 
                                            log(f"Part {i+1}: dmaPacket offset 0x{geoStart + part_offset:X}")
                                        log("===================================")
                                    
                                    while f.tell() < next_part_addr:
                                        # Save the current offset in case we want to log where we start looking for markers
                                        marker_seek = f.tell()
                                        log(f"🔎 Looking for triangle strip marker at offset: 0x{marker_seek:X}")

                                        # Read 4 bytes as a potential marker
                                        marker = struct.unpack('<I', f.read(4))[0]
                                        log(f"   Read marker 0x{marker:08X} at 0x{marker_seek:X}")

                                        if marker == 0x6C018000:
                                            split_flag_offset = marker_seek
                                            log(f"✔ 0x6C018000 split flag found at 0x{split_flag_offset:X} -- reading split section header...")

                                            # Read and log each split block header field (these are always in this order)
                                            marker_bytes = f.read(4) 
                                            log(f"  [0x{f.tell()-4:X}] marker: {marker_bytes.hex()} (should be 00 80 01 6C)")

                                            zeros1_offset = f.tell()
                                            zeros1 = f.read(4)
                                            log(f"  [0x{zeros1_offset:X}] zeros1: {zeros1.hex()} (should be 00 00 00 00)")

                                            zeros2_offset = f.tell()
                                            zeros2 = f.read(4)
                                            log(f"  [0x{zeros2_offset:X}] zeros2: {zeros2.hex()} (should be 00 00 00 00)")

                                            vert_count1_offset = f.tell()
                                            vert_count1 = struct.unpack('<B', f.read(1))[0]
                                            log(f"  [0x{vert_count1_offset:X}] vert_count1: {vert_count1}")

                                            pad3_offset = f.tell()
                                            pad3 = f.read(3)
                                            log(f"  [0x{pad3_offset:X}] pad3: {pad3.hex()} (should be 00 00 00)")

                                            vert_count2_offset = f.tell()
                                            vert_count2 = struct.unpack('<B', f.read(1))[0]
                                            log(f"  [0x{vert_count2_offset:X}] vert_count2: {vert_count2}")

                                            flags_offset = f.tell()
                                            flags = struct.unpack('<H', f.read(2))[0]
                                            vert_count_dma = flags & 0x7FFF
                                            culling_disabled = bool(flags & 0x8000)
                                            log(f"  [0x{flags_offset:X}] flags: 0x{flags:04X}")
                                            log(f"     - vert_count_dma (flags & 0x7FFF): {vert_count_dma}")
                                            log(f"     - culling_disabled (flags & 0x8000): {culling_disabled}")

                                            pad4_offset = f.tell()
                                            pad4 = f.read(4)
                                            log(f"  [0x{pad4_offset:X}] pad4: {pad4.hex()}")

                                            tech1_offset = f.tell()
                                            tech1 = f.read(4)
                                            log(f"  [0x{tech1_offset:X}] tech1: {tech1.hex()} (typically 40404020)")

                                            tech2_offset = f.tell()
                                            tech2 = f.read(4)
                                            log(f"  [0x{tech2_offset:X}] tech2: {tech2.hex()}")
                                        
                                        f.seek(16, 1)

                                        # Loop: skip chunks until we find a valid strip marker (top marker bits == 0x60000000)
                                        while (marker & 0x60000000) != 0x60000000 and f.tell() < next_part_addr:
                                            log(f"      Not a tri-strip flag (got 0x{marker:08X}). Skipping 44 bytes (11 DWORDs) at 0x{f.tell():X}")
                                            for _ in range(11):
                                                f.read(4)  # Skip 4 bytes, 11 times (44 bytes total)
                                            skip_offset = f.tell()
                                            marker = struct.unpack('<I', f.read(4))[0]
                                            log(f"      Checked tri-strip marker 0x{marker:08X} at 0x{skip_offset:X}")

                                        # If we didn't find a valid tri-strip geometry flag, break out
                                        if (marker & 0x60000000) != 0x60000000:
                                            log(f"✗ No valid strip marker found, breaking out at offset 0x{f.tell():X}")
                                            break  # No more strips in this part

                                        if marker == 0x60000000:
                                            log(f"✔ 0x60000000 tri-strip flag found at 0x{marker_seek:X}, skipping 16 bytes to 0x{marker_seek + 16:X}")
                                            f.seek(marker_seek, 0)  # move pointer to 16 bytes after marker
                                        elif marker == 0x6C018000:
                                            log(f"✔ 0x6C018000 split section marker found at 0x{marker_seek:X}, rewinding to flag for detailed breakdown")
                                            f.seek(marker_seek, 0)
                                            # === Read and log the full 0x6C018000 split section ===
                                            flag_offset = f.tell()
                                            marker_bytes = f.read(4)
                                            log(f"  [0x{flag_offset:X}] marker: {marker_bytes.hex()} (should be 00 80 01 6C)")
                                            
                                            zeros1_offset = f.tell()
                                            zeros1 = f.read(4)
                                            log(f"  [0x{zeros1_offset:X}] zeros1: {zeros1.hex()} (should be 00 00 00 00)")

                                            zeros2_offset = f.tell()
                                            zeros2 = f.read(4)
                                            log(f"  [0x{zeros2_offset:X}] zeros2: {zeros2.hex()} (should be 00 00 00 00)")

                                            vert_count1_offset = f.tell()
                                            vert_count1 = struct.unpack('<B', f.read(1))[0]
                                            log(f"  [0x{vert_count1_offset:X}] vert_count1: {vert_count1}")
                                            
                                            pad3_offset = f.tell()
                                            pad3 = f.read(3)
                                            log(f"  [0x{pad3_offset:X}] pad3: {pad3.hex()} (should be 00 00 00)")

                                            vert_count2_offset = f.tell()
                                            vert_count2 = struct.unpack('<B', f.read(1))[0]
                                            log(f"  [0x{vert_count2_offset:X}] vert_count2: {vert_count2}")

                                            flags_offset = f.tell()     # necessary stuff for Leeds Engine rendering
                                            flags = struct.unpack('<H', f.read(2))[0]
                                            vert_count_dma = flags & 0x7FFF
                                            culling_disabled = bool(flags & 0x8000)
                                            log(f"  [0x{flags_offset:X}] flags: 0x{flags:04X}")
                                            log(f"     - vert_count_dma (flags & 0x7FFF): {vert_count_dma}")
                                            log(f"     - culling_disabled (flags & 0x8000): {culling_disabled}")

                                            pad4_offset = f.tell()
                                            pad4 = f.read(4)
                                            log(f"  [0x{pad4_offset:X}] pad4: {pad4.hex()}")

                                            tech1_offset = f.tell() # necessary stuff for Leeds Engine rendering
                                            tech1 = f.read(4)
                                            log(f"  [0x{tech1_offset:X}] tech1: {tech1.hex()} (typically 40404020)")

                                            tech2_offset = f.tell()
                                            tech2 = f.read(4)
                                            log(f"  [0x{tech2_offset:X}] tech2: {tech2.hex()}")
                                            
                                            f.seek(marker_seek)
                                            
                                            if vert_count1 != vert_count2:
                                                log(f"  WARNING: vert_count1 ({vert_count1}) != vert_count2 ({vert_count2}) at 0x{f.tell():X}")
                                            else:
                                                log(f"✔ Vertex counts match: {vert_count1}")

                                            log(f"=== END OF 0x6C018000 SPLIT BLOCK ===")
                                            # continue reading vertex data for this split section               
                                        else:
                                            log(f"✔ Valid tri-strip flag (0x{marker:08X}) found at 0x{marker_seek:X}, rewinding to flag")
                                            f.seek(-4, 1)
                                        
                                        for _ in range(4):
                                            f.read(4)
                                            
                                        tri_strip_start = f.tell()
                                        log(f"  Tri-Strip Start: 0x{tri_strip_start:X}")

                                        for _ in range(8):
                                            f.read(4)
                                        _ = struct.unpack('<H', f.read(2))[0]
                                        curStripVertCount = struct.unpack('<B', f.read(1))[0]
                                        padByte = struct.unpack('<B', f.read(1))[0]
                                        log(f"    - curStripVertCount: {curStripVertCount} (padByte={padByte}) at 0x{f.tell():X}")
                                        
                                        vertex_data_offset = f.tell()  # Get current file pointer position
                                        log(f"    🧊 Vertex data begins at file offset: 0x{vertex_data_offset:X} ({vertex_data_offset})")
                                        
                                         # we'll collect all the new vertices for this strip in here before adding them to the main list.
                                        verts = []
          
                                        skin_indices = []
                                        skin_weights = []

                                        # remember how many verts we already had for this part
                                        base_idx = len(part_verts)

                                        globalScale = scaleFactor * 0.00000030518203134641490805874367518203

                                        if TranslationFactor is None:
                                            tx = ty = tz = 0.0
                                        else:
                                            tx, ty, tz = float(TranslationFactor[0]), float(TranslationFactor[1]), float(TranslationFactor[2])

                                        for vi in range(curStripVertCount):
                                            offset_x = f.tell()
                                            x_raw = struct.unpack('<h', f.read(2))[0]
                                            offset_y = f.tell()
                                            y_raw = struct.unpack('<h', f.read(2))[0]
                                            offset_z = f.tell()
                                            z_raw = struct.unpack('<h', f.read(2))[0]

                                            x = x_raw * xScale * globalScale + tx
                                            y = y_raw * yScale * globalScale + ty
                                            z = z_raw * zScale * globalScale + tz

                                            verts.append((x, y, z))

                                            log(f"        🧊 Vertex {vi}:")
                                            log(f"           • X Offset: 0x{offset_x:X}, Raw: {x_raw}, Final: {x:.6f}")
                                            log(f"           • Y Offset: 0x{offset_y:X}, Raw: {y_raw}, Final: {y:.6f}")
                                            log(f"           • Z Offset: 0x{offset_z:X}, Raw: {z_raw}, Final: {z:.6f}")
                                        
                                        part_verts.extend(verts)
                                        
                                        # Now create faces for this strip:
                                        for i in range(2, curStripVertCount):
                                            if (i % 2) == 0:
                                                v0 = base_idx + i - 2
                                                v1 = base_idx + i - 1
                                                v2 = base_idx + i
                                            else:
                                                v0 = base_idx + i - 1
                                                v1 = base_idx + i - 2
                                                v2 = base_idx + i
                                            if v0 != v1 and v1 != v2 and v2 != v0:
                                                part_faces.append((v0, v1, v2))

                                        # === Now we proceed to UV sub-section ===
                                        f.seek(28, 1) # violating the MDL file(again)
                                        # -- Padding short if odd vertex count
                                        if (curStripVertCount % 2) == 1:
                                            
                                            pad_short = struct.unpack('<h', f.read(2))[0]
                                            log(f"    ⬛ Padding short after verts (odd count): {pad_short} at 0x{f.tell():X}")

                                        # -- Read sub-section: short, tvert count, extra byte
                                        _ = struct.unpack('<H', f.read(2))[0]  # Skip/Read short
                                        curStripTVertCount = struct.unpack('<B', f.read(1))[0]
                                        padByte2 = struct.unpack('<B', f.read(1))[0]
                                        log(f"    ⬛ curStripTVertCount: {curStripTVertCount} (pad2={padByte2}) at 0x{f.tell():X}")
                                        
                                        UV_SCALE = 32768.0 #  PS2 divides by 32767
                                        
                                        uvs = []
                                        for i in range(curStripTVertCount):
                                            u = struct.unpack('<h', f.read(2))[0]
                                            v = struct.unpack('<h', f.read(2))[0]
                                            u_f = u / UV_SCALE
                                            v_f = v / UV_SCALE
                                            uvs.append((u_f, v_f))
                                            log(f"      🟪 UV {i}: U={u_f:.6f}, V={v_f:.6f} (raw: {u}, {v})")
                                        
                                        # -After reading UVs:
                                        section_padding = 4 - ((2 * curStripTVertCount * 2) % 4)  # 2 shorts (4 bytes) per UV
                                        if section_padding != 4:
                                            f.read(section_padding)
                                            log(f"    🟦 Padding after UVs: {section_padding} bytes")

                                        # === Read all per-strip attribute subsections (vertcol, normals, skin, etc) ===
                                        while True:
                                            subsection_pos = f.tell()
                                            header = f.read(4)
                                            if len(header) < 4:
                                                break  # End of file or bad read

                                            # Interpret as both int and bytes
                                            marker_val = struct.unpack('<I', header)[0]
                                            b0, b1, b2, b3 = header[0], header[1], header[2], header[3]

                                            if marker_val == 0x60000000:
                                                # For 0x60000000, skip 16 bytes forward from current pos
                                                log(f"✔ Found 0x60000000 strip marker at 0x{subsection_pos:X} -- skipping 16 bytes")
                                                f.seek(16, 1)  # Move forward 16 bytes from current position
                                                break  # Exit the per-strip attribute subsection handling

                                            elif marker_val == 0x6C018000:
                                                # For 0x6C018000, rewind to this split flag for the outer loop to handle
                                                log(f"✔ Found 0x6C018000 split flag at 0x{subsection_pos:X} -- rewinding to marker")
                                                f.seek(subsection_pos, 0)  # Go back to start of flag/marker
                                                rewound_pos = f.tell()
                                                log(f"📍 Rewound to file offset: 0x{rewound_pos:X} ({rewound_pos})")
                                                break
      
                                            # === If it's a known split attribute subsection ===
                                            elif b1 == 0x80 and b3 in (0x6F, 0x6A, 0x6C):
                                                # We have a split attribute header!
                                                section_count = b2
                                                log(f"   >> Subsection header: b1={b1:02X}, count={section_count}, b3={b3:02X} at 0x{subsection_pos:X}")
                                                
                                                                                          
                                                if b3 == 0x6F:
                                                    # Read as BGRA
                                                    log(f"      🎨 Reading {section_count} vertex colors")
                                                    for i in range(section_count):
                                                        vcolor = struct.unpack('<H', f.read(2))[0]
                                                        r = (vcolor & 0x1F) * (1.0 / 32.0)
                                                        g = ((vcolor >> 5) & 0x1F) * (1.0 / 32.0)
                                                        b = ((vcolor >> 10) & 0x1F) * (1.0 / 32.0)
                                                        a = ((vcolor >> 15) & 0x01) * 1.0
                                                        log(f"         R={r:.3f} G={g:.3f} B={b:.3f} A={a:.1f} (raw=0x{vcolor:04X})")
                                                    pad = 2 - ((2 * section_count) % 4)
                                                    if pad != 4:
                                                        f.read(pad)

                                                elif b3 == 0x6A:
                                                    log(f"      🧲 Reading {section_count} normals")
                                                    for i in range(section_count):
                                                        nx = struct.unpack('<b', f.read(1))[0] / 128.0
                                                        ny = struct.unpack('<b', f.read(1))[0] / 128.0
                                                        nz = struct.unpack('<b', f.read(1))[0] / 128.0
                                                        log(f"         N={nx:.4f} {ny:.4f} {nz:.4f}")
                                                    pad = 4 - ((3 * section_count) % 4)
                                                    if pad != 4:
                                                        f.read(pad)

                                                elif b3 == 0x6C:
                                                    log(f"      🦴 Reading {section_count} skin weights")
                                                    for i in range(section_count):
                                                        bone1 = struct.unpack('<H', f.read(2))[0] // 4
                                                        f.read(1)
                                                        w1 = struct.unpack('<B', f.read(1))[0] / 128.0
                                                        bone2 = struct.unpack('<H', f.read(2))[0] // 4
                                                        f.read(1)
                                                        w2 = struct.unpack('<B', f.read(1))[0] / 128.0
                                                        bone3 = struct.unpack('<H', f.read(2))[0] // 4
                                                        f.read(1)
                                                        w3 = struct.unpack('<B', f.read(1))[0] / 128.0
                                                        bone4 = struct.unpack('<H', f.read(2))[0] // 4
                                                        f.read(1)
                                                        w4 = struct.unpack('<B', f.read(1))[0] / 128.0


                                                        # build the per-vertex lists
                                                        indices  = [bone1, bone2, bone3, bone4]
                                                        weights  = [w1,    w2,    w3,    w4   ]

                                                        log(f"         B1={bone1} W1={w1:.4f} B2={bone2} W2={w2:.4f} B3={bone3} W3={w3:.4f} B4={bone4} W4={w4:.4f}")

                                                        skin_indices.append(indices)
                                                        skin_weights.append(weights)
                                                    

                                                continue  # After reading this split subsection, see if there's another

                                        # === After UVs and attribute subsections, once skin_indices/skin_weights are populated ===
                                        if len(skin_indices) != curStripVertCount or len(skin_weights) != curStripVertCount:
                                            log(f"[WARN] strip verts={curStripVertCount}, skin_idx={len(skin_indices)}, skin_wts={len(skin_weights)} — padding zeros to match")
                                            # pad if file omits some weights for this strip, which we want to avoid or diagnose
                                            while len(skin_indices) < curStripVertCount:
                                                skin_indices.append([0, 0, 0, 0])
                                                skin_weights.append([0.0, 0.0, 0.0, 0.0])
                                            skin_indices = skin_indices[:curStripVertCount]
                                            skin_weights = skin_weights[:curStripVertCount]

                                        # Record where this strip was appended into the part mesh’s vertex list
                                        strips_meta.append(
                                            (base_idx, curStripVertCount, list(skin_indices), list(skin_weights))
                                        )

                                        # reset, start new strip
                                        skin_indices.clear()
                                        skin_weights.clear()
                                    
                                    root_empty = bpy.data.objects.get("scene_root")
                                    if root_empty is None:
                                        root_empty = bpy.data.objects.new("scene_root", None)
                                        bpy.context.collection.objects.link(root_empty)
                                        root_empty.empty_display_size = 0.05
                                    else:
                                        if bpy.context.collection not in root_empty.users_collection:
                                            bpy.context.collection.objects.link(root_empty)
                                    # Fix root
                                    root_empty.location = (0, 0, 0)

                                    # If we have any vertices collected for this part,
                                    # proceed to create a Blender mesh object for it
                                    if part_verts:
                                        # Create a new Blender mesh data block for this part,
                                        # naming it uniquely by the part index
                                        mesh = bpy.data.meshes.new(f"Mesh_{part_index}")
                                        
                                        # Create a new Blender object that uses this mesh
                                        obj = bpy.data.objects.new(f"Mesh_{part_index}", mesh)

                                        # For this part:
                                        part_mat_id = int(partMaterials[part_index])
                                        if 0 <= part_mat_id < len(blender_mats):
                                            _ensure_single_material(obj, blender_mats[part_mat_id], report=log)
                                        else:
                                            log(f"⚠ part_mat_id {part_mat_id} out of range (0..{len(blender_mats)-1}). Leaving default material.")

                                        
                                        # Link the object to the current Blender collection,
                                        # so it actually appears in the scene
                                        bpy.context.collection.objects.link(obj)

                                        part_mat_id = int(partMaterials[part_index])
                                        if 0 <= part_mat_id < len(blender_mats):
                                            _ensure_single_material(obj, blender_mats[part_mat_id], report=log)
                                        else:
                                            log(f"⚠ part_mat_id {part_mat_id} out of range (0..{len(blender_mats)-1}). Leaving default material.")
                                        
                                        add_modifiers_to_mesh(obj, armature_obj)
                                        
                                        # Fill the mesh
                                        mesh.from_pydata(part_verts, [], part_faces)

                                        # --- Vertex colors ---
                                        assume_255 = True 
                                        try:
                                            if 'part_loop_colors' in locals() and part_loop_colors:
                                                _blit_vertex_colors(mesh, part_faces, part_loop_colors, assume_255=assume_255)
                                            elif 'part_vcols' in locals() and part_vcols:
                                                _blit_vertex_colors(mesh, part_faces, part_vcols, assume_255=assume_255)
                                            elif 'mesh_colors' in locals() and mesh_colors:
                                                _blit_vertex_colors(mesh, part_faces, mesh_colors, assume_255=assume_255)
                                            elif vertex_colors:
                                                _blit_vertex_colors(mesh, part_faces, vertex_colors, assume_255=assume_255)
                                            else:
                                                # ensure a visible layer even if a model has no colors
                                                _blit_vertex_colors(mesh, part_faces, [(255,255,255,255)] * len(mesh.loops), assume_255=assume_255)
                                        except Exception as e:
                                            log(f"Vertex-color write failed: {e}")


                                        # --- Vertex color assignment (safe + unified) ---
                                        # Only run if we actually collected any colors
                                        if 'mesh_colors' in locals() and mesh_colors:
                                            # Create/ensure a CORNER (per-loop) layer so shared verts can differ by face
                                            ca = mesh.color_attributes.get("Col")
                                            if ca is None:
                                                # BYTE_COLOR is perfect for 0–255 data we read from the file
                                                ca = mesh.color_attributes.new(name="Col", type='BYTE_COLOR', domain='CORNER')

                                            loops = mesh.loops

                                            def as_float_rgba(c):
                                                # Accept (r,g,b) or (r,g,b,a) in either 0–255 ints or 0–1 floats
                                                if not c:
                                                    return (1.0, 1.0, 1.0, 1.0)
                                                if len(c) == 3:
                                                    r, g, b = c; a = 255 if isinstance(r, int) else 1.0
                                                else:
                                                    r, g, b, a = c[:4]
                                                if isinstance(r, int) or isinstance(g, int) or isinstance(b, int) or isinstance(a, int):
                                                    return (r/255.0, g/255.0, b/255.0, (a/255.0 if a is not None else 1.0))
                                                return (float(r), float(g), float(b), float(a if a is not None else 1.0))

                                            if len(mesh_colors) == len(mesh.vertices):
                                                # Map each loop’s vertex_index to that vertex’s color
                                                for li, loop in enumerate(loops):
                                                    vi = loop.vertex_index
                                                    ca.data[li].color = as_float_rgba(mesh_colors[vi])
                                            elif len(mesh_colors) == len(loops):
                                                for li in range(len(loops)):
                                                    ca.data[li].color = as_float_rgba(mesh_colors[li])
                                            else:
                                                for li in range(len(loops)):
                                                    ca.data[li].color = (1.0, 1.0, 1.0, 1.0)

                                            mesh.color_attributes.active_color = ca
                                            mesh.color_attributes.render_color = ca

                                        # Build palette-based mapping: fileIndex -> boneName
                                        index_to_bonename = build_index_to_bonename(armature_obj, log)

                                        # Assign weights per strip
                                        for vbase, count, s_idx, s_wts in strips_meta:
                                            assign_strip_weights(
                                                obj, armature_obj, s_idx, s_wts, index_to_bonename, vbase,
                                                normalize=True, per_vertex_replace=True
                                            )
                                        
                                        # Update the mesh, which tells Blender to finish calculating face normals
                                        mesh.update()
                                        
                                        log(f"✔ Imported mesh part {part_index} with {len(part_verts)} verts")
                                                                                
                                        imported_meshes = [obj for obj in bpy.context.collection.objects if obj.name.startswith("Mesh_")]
                                                        
                                        # === PARENT ARMATURE TO MDL_ROOT(male/female base) ===
                                        armature_obj.parent = root_empty
                                        print(f"✔ Parented armature '{armature_obj.name}' to '{root_empty.name}'.")

                                        # === ARMATURE MODIFIER + PARENT TO ARMATURE FOR ALL MESHES ===
                                        for mesh_obj in imported_meshes:
                                            # Remove all old armature modifiers to prevent duplicates
                                            for mod in mesh_obj.modifiers:
                                                if mod.type == 'ARMATURE':
                                                    mesh_obj.modifiers.remove(mod)
                                            # Add armature modifier
                                            arm_mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
                                            arm_mod.object = armature_obj
                                            print(f"✔ Assigned armature modifier to {mesh_obj.name}")
 
                                            M_world = frame_mats.get(current_frame_ptr)
                                            R = Matrix.Rotation(-math.pi/2, 4, 'X')

                                            M_world = frame_mats_world.get(frame_ptr)  # world for the parent frame
                                            if M_world is not None:
                                                # match the mesh(es) to armature space
                                                obj.matrix_world = M_world

                                            obj.parent = armature_obj
                                            obj.matrix_parent_inverse = armature_obj.matrix_world.inverted()

                                        # Move only the mesh object upward in local space
                                        for obj in imported_meshes:
                                            obj.parent = root_empty
                                    else:
                                        log(f"✗ No vertices found to import in part {part_index}!")
                            
                            # Going off on our own here now, using librwgta as a ref...
                            # === PSP geometry struct logic ===
                        elif self.platform == 'PSP':
                            log(f" Attempting PSP Stories MDL read...")
                            geo_start = f.tell()
                            header_offset = geo_start 
                            f.seek(header_offset)
                            
                            log(f" Reading PSP Materials...")
                            
                             #RslMaterialList
                            part_materials = []
                            part_offsets = []
                            current_atomic_material_list = []

                            _ = read_u32()  # unknown0
                            _ = read_u32()  # unknown1
                            _ = read_u32()  # unknown2

                            material_list_ptr = read_u32()
                            material_count = read_u32()

                            log(f"🧵 Material List Ptr: 0x{material_list_ptr:X}")
                            log(f"🎨 Material Count: {material_count}")

                            if material_count > 0:
                                old_pos = f.tell()
                                f.seek(material_list_ptr)

                                for i in range(material_count):
                                    log(f"  ↪ Reading Material {i + 1}/{material_count}")
                                    current_material = {
                                        "offset": 0,
                                        "texture": None,
                                        "rgba": None,
                                        "specular": None
                                    }
                                    
                                    #RslMaterial
                                    cur_mat_ptr = read_u32()
                                    log(f"    ⤷ Material Ptr: 0x{cur_mat_ptr:X}")
                                    old_mat_pos = f.tell()
                                    f.seek(cur_mat_ptr)

                                    tex_ptr = read_u32()
                                    log(f"    ⤷ Texture Ptr: 0x{tex_ptr:X}")
                                    if tex_ptr > 0:
                                        temp_pos = f.tell()
                                        f.seek(tex_ptr)
                                        tex_name = read_string(tex_ptr)
                                        current_material["texture"] = tex_name
                                        log(f"    🎯 Texture Name: {tex_name}")
                                        f.seek(temp_pos)

                                    rgba = read_u32()
                                    current_material["rgba"] = rgba
                                    log(f"    🎨 RGBA Value: 0x{rgba:08X}")

                                    _ = read_u32()  # Unknown value

                                    spec_ptr = read_u32()
                                    log(f"    ⤷ Specular Ptr: 0x{spec_ptr:X}")
                                    if spec_ptr > 0:
                                        temp_pos = f.tell()
                                        f.seek(spec_ptr)
                                        _ = read_u32()
                                        _ = read_u32()
                                        specular_value = read_f32()
                                        current_material["specular"] = specular_value
                                        log(f"    ✨ Specular: {specular_value:.6f}")
                                        f.seek(temp_pos)

                                    f.seek(old_mat_pos)
                                    current_atomic_material_list.append(current_material)


                                    # TODO: MatFX here?

                                f.seek(old_pos)
                            f.seek(12, 1)
                            # this is where things get screwy - if they werent already
                            psp_header = f.read(0x48)
                            if len(psp_header) != 0x48:
                                raise Exception("Not enough bytes for PSP geometry header!")

                            (
                                size,            # uint32
                                flags,           # uint32
                                numStrips,       # uint32
                                unk1,            # uint32
                                bound0, bound1, bound2, bound3,   # float32 x 4
                                scale_x, scale_y, scale_z,        # float32 x 3
                                numVerts,        # int32 (signed) / total number of vertices(global)
                                pos_x, pos_y, pos_z,              # float32 x 3
                                unk2,            # int32 (signed)
                                offset,          # uint32 (vertex offset from struct start)
                                unk3             # float32
                            ) = struct.unpack('<4I4f3fi3fiIf', psp_header)
                            
                            known_flag_formats = {0x120, 0x121, 0x115, 0x114, 0xA1, 0x1C321}
                            if flags not in known_flag_formats:
                                log(f"⚠️ Unknown PSP geometry flags format: 0x{flags:X}")
                                raise Exception(f"Unknown PSP geometry flags format: 0x{flags:X}")
                            else:
                                log(f"✔ Known PSP geometry flags format: 0x{flags:X}")
                                
                            uvfmt   = flags & 0x3
                            colfmt  = (flags >> 2) & 0x7
                            normfmt = (flags >> 5) & 0x3
                            posfmt  = (flags >> 7) & 0x3
                            wghtfmt = (flags >> 9) & 0x3
                            idxfmt  = (flags >> 11) & 0x3
                            nwght   = ((flags >> 14) & 0x7) + 1

                            log("----- Flags Format Case Breakdown -----")

                            # uvfmt: only 0 and 1 allowed
                            if uvfmt == 0:
                                log("  uvfmt   = 0: No UV coordinates (case 0) [OK]")
                            elif uvfmt == 1:
                                log("  uvfmt   = 1: U8 UVs (case 1) [OK]")
                            else:
                                log(f"  uvfmt   = {uvfmt}: Unsupported UV format! [ERROR]")
                                raise Exception(f"Unsupported tex coord format (uvfmt={uvfmt})")

                            # colfmt: only 0 and 5 allowed
                            if colfmt == 0:
                                log("  colfmt  = 0: No vertex color (case 0) [OK]")
                            elif colfmt == 5:
                                log("  colfmt  = 5: 16-bit RGBA5551 color (case 5) [OK]")
                            else:
                                log(f"  colfmt  = {colfmt}: Unsupported vertex color format! [ERROR]")
                                raise Exception(f"Unsupported color format (colfmt={colfmt})")

                            # normfmt: only 0 and 1 allowed
                            if normfmt == 0:
                                log("  normfmt = 0: No normals (case 0) [OK]")
                            elif normfmt == 1:
                                log("  normfmt = 1: S8 normals (case 1) [OK]")
                            else:
                                log(f"  normfmt = {normfmt}: Unsupported normal format! [ERROR]")
                                raise Exception(f"Unsupported normal format (normfmt={normfmt})")

                            # posfmt: only 1 and 2 allowed
                            if posfmt == 1:
                                log("  posfmt  = 1: S8 positions (case 1) [OK]")
                            elif posfmt == 2:
                                log("  posfmt  = 2: S16 positions (case 2) [OK]")
                            else:
                                log(f"  posfmt  = {posfmt}: Unsupported vertex position format! [ERROR]")
                                raise Exception(f"Unsupported vertex format (posfmt={posfmt})")

                            # wghtfmt: only 0 and 1 allowed
                            if wghtfmt == 0:
                                log("  wghtfmt = 0: No weights/skin [OK]")
                            elif wghtfmt == 1:
                                log("  wghtfmt = 1: U8 weights/skin [OK]")
                            else:
                                log(f"  wghtfmt = {wghtfmt}: Unsupported weights format! [ERROR]")
                                raise Exception(f"Unsupported weight format (wghtfmt={wghtfmt})")

                            # idxfmt: must be 0 (assert)
                            if idxfmt == 0:
                                log("  idxfmt  = 0: Index format [OK]")
                            else:
                                log(f"  idxfmt  = {idxfmt}: Unsupported/invalid index format! [ERROR]")
                                raise Exception(f"idxfmt must be 0 (got {idxfmt})")

                            log(f"  nwght   = {nwght}: Number of weights per vertex (parsed as ((flags>>14) & 7) + 1)")
                            log("--------------------------------------")

                            log("----- PSP Geometry Struct -----")
                            log(f"  size      (header+data): {size} (0x{size:08X})")
                            log(f"  flags     (VTYPE)      : {flags} (0x{flags:08X})")
                            log(f"  numStrips              : {numStrips}")
                            log(f"  unk1                   : {unk1} (0x{unk1:08X})")
                            log(f"  bound   [0]            : {bound0}")
                            log(f"  bound   [1]            : {bound1}")
                            log(f"  bound   [2]            : {bound2}")
                            log(f"  bound   [3]            : {bound3}")
                            log(f"  scale_x                : {scale_x}")
                            log(f"  scale_y                : {scale_y}")
                            log(f"  scale_z                : {scale_z}")
                            log(f"  numVerts               : {numVerts}")
                            log(f"  pos_x                  : {pos_x}")
                            log(f"  pos_y                  : {pos_y}")
                            log(f"  pos_z                  : {pos_z}")
                            log(f"  unk2                   : {unk2} (0x{unk2:08X})")
                            log(f"  offset (to vertices)   : {offset} (0x{offset:08X})")
                            log(f"  unk3                   : {unk3}")
                            log("--------------------------------")

                            # reading and logging our sPspGeometryMesh structs
                            mesh_list = []
                            for i in range(numStrips):
                                mesh_offset = f.tell()
                                mesh_bytes = f.read(0x30)
                                if len(mesh_bytes) != 0x30:
                                    log(f"✗ ERROR: Could not read 0x30 bytes for sPspGeometryMesh[{i}] at 0x{mesh_offset:X}")
                                    break

                                (
                                    m_offset,             # uint32: Offset to triangle/strip data, relative to vertex buffer
                                    m_numTriangles,       # uint16: Number of triangles in this strip/mesh
                                    m_matID,              # uint16: Material index
                                    m_unk1,               # float32: Unknown, usually zero
                                    m_uvScale0,           # float32: U scale
                                    m_uvScale1,           # float32: V scale
                                    m_unk2_0, m_unk2_1, m_unk2_2, m_unk2_3,  # float32 x4: Unknowns, usually zero
                                    m_unk3,               # float32: Unknown, often zero
                                    *m_bonemap            # 8 bytes: Bone map indices (uint8 x8)
                                ) = struct.unpack('<I H H f 2f 4f f 8B', mesh_bytes)

                                log(f"\n---- [sPspGeometryMesh {i+1}/{numStrips}] ----")
                                log(f"  File Offset        : 0x{mesh_offset:X}")
                                log(f"  offset (to tris)   : 0x{m_offset:08X}")
                                log(f"  numTriangles       : {m_numTriangles}")
                                log(f"  matID              : {m_matID}")
                                log(f"  unk1               : {m_unk1}")
                                log(f"  uvScale            : ({m_uvScale0}, {m_uvScale1})")
                                log(f"  unk2[0..3]         : ({m_unk2_0}, {m_unk2_1}, {m_unk2_2}, {m_unk2_3})")
                                log(f"  unk3               : {m_unk3}")
                                log(f"  bonemap            : {list(m_bonemap)}")
                                mesh_dict = {
                                    "offset": m_offset,
                                    "numTriangles": m_numTriangles,
                                    "matID": m_matID,
                                    "unk1": m_unk1,
                                    "uvScale": (m_uvScale0, m_uvScale1),
                                    "unk2": (m_unk2_0, m_unk2_1, m_unk2_2, m_unk2_3),
                                    "unk3": m_unk3,
                                    "bonemap": list(m_bonemap),
                                    "raw_bytes": mesh_bytes,
                                    "file_offset": mesh_offset,
                                }
                                mesh_list.append(mesh_dict)

                            log(f"✔ Finished reading {len(mesh_list)} sPspGeometryMesh structs (expected: {numStrips})\n")
                            
                            # === Now parse actual vertex/index data and build Blender meshes for each PSP mesh/strip ===
                            # Calculate vertex buffer file offset
                            vertex_buffer_file_offset = header_offset + offset - 168
                            log(f"Vertex buffer begins at file offset: 0x{vertex_buffer_file_offset:X}")

                            # Seek to vertex buffer start
                            f.seek(vertex_buffer_file_offset)
                            vertex_buffer = f.read(numVerts * 24)  # VCS PSP Geometry List String Length: = 24 bytes

                            if len(vertex_buffer) < numVerts:
                                raise Exception("Not enough data for vertex buffer!")
                            
                            part_verts = []
                            part_faces = []
                            vert_offset = 0 

                            for mesh_index, mesh in enumerate(mesh_list):
                                log(f"--- Building mesh for sPspGeometryMesh {mesh_index+1}/{len(mesh_list)} ---")
                                mesh_verts = []
                                mesh_faces = []
                                mesh_uvs = []
                                mesh_colors = []
                                mesh_normals = []
                                mesh_weights = []
                                mesh_indices = []

                                # For PSP, the triangle strips are typically indexed implicitly, not with explicit index buffers.
                                # We'll read vertices in order, build triangle strips according to mesh['numTriangles'].
                                # The offset to the strip data is relative to the vertex buffer file offset.
                                tri_strip_offset = vertex_buffer_file_offset + mesh['offset']
                                f.seek(tri_strip_offset)
                                # align the first & subsequent strips to avoid overread/degenerates
                                bytes_per_vert = 20 
                                verts_to_skip = 10
                                skip_bytes = bytes_per_vert * verts_to_skip
                                f.seek(skip_bytes, 1)
                                log(f"⏩ Skipped first {verts_to_skip} verts ({skip_bytes} bytes) for mesh {mesh_index}")

                                num_verts_to_read = mesh['numTriangles'] + 2 - verts_to_skip
                                log(f"🟩 [PSP] Reading Mesh/Strip {mesh_index}: Vertex data starts at file offset 0x{tri_strip_offset:X} ({tri_strip_offset})")
                                
                                # Calculate number of vertices for this strip:
                                # For a triangle strip, number of vertices = numTriangles + 2
                                num_strip_verts = mesh['numTriangles'] + 2
                        
                                log(f"  Tri-strip data for mesh {mesh_index}: offset=0x{tri_strip_offset:X}, numTriangles={mesh['numTriangles']}, thus numVertices={num_strip_verts}")

                                # parse the data according to flags per strip
                                strip_verts = []
                                o = 0
                                for vi in range(num_strip_verts):
                                    vertex_data = f.read(20)  # read max size - never >20 or below!!
                                    if len(vertex_data) < 8:  # fail safe
                                        log(f"    ! Not enough data for vertex {vi} of strip {mesh_index}")
                                        break

                                    v = {}
                                    local_o = 0

                                    # === Weights (PSP) ===
                                    if wghtfmt:

                                        weights_raw = [vertex_data[local_o + j] for j in range(nwght)]
                                        local_o += nwght 

                                        K = min(4, nwght)
                                        w4 = [weights_raw[j] / 128.0 for j in range(K)]
                                        if K < 4:
                                            w4.extend([0.0] * (4 - K))

                                        palette = mesh.get('bonemap') or []
                                        idx4 = []
                                        for j in range(K):
                                            idx4.append(palette[j] if j < len(palette) else 0)
                                        if K < 4:
                                            idx4.extend([0] * (4 - K))

                                        s = sum(w4)
                                        if s > 0.0:
                                            w4 = [w / s for w in w4]

                                        if nwght > 4 and any(x != 0 for x in weights_raw[4:]):
                                            log(f"PSP: vertex had {nwght} weights; extra bytes beyond 4 were non-zero and ignored: {weights_raw[4:]}")

                                        v['w'] = w4
                                        v['i'] = idx4
                                        mesh_weights.append(w4)
                                        mesh_indices.append(idx4)
                                    # === UVs ===
                                    if uvfmt == 1:
                                        v['u'] = vertex_data[local_o]/128.0 * mesh['uvScale'][0]
                                        v['v'] = vertex_data[local_o+1]/128.0 * mesh['uvScale'][1]
                                        mesh_uvs.append((v['u'], v['v']))
                                        local_o += 2

                                    # === Vertex Color(read as BGRA) ===
                                    if colfmt == 5:
                                        local_o = ((local_o + 1) // 2) * 2  # align to 2 bytes
                                        col = struct.unpack_from('<H', vertex_data, local_o)[0]
                                        r = (col & 0x1f) * 255 // 0x1F
                                        g = ((col >> 5) & 0x1f) * 255 // 0x1F
                                        b = ((col >> 10) & 0x1f) * 255 // 0x1F
                                        a = 0xFF if (col & 0x8000) else 0
                                        mesh_colors.append((r, g, b, a))
                                        local_o += 2

                                    # === Normals ===
                                    if normfmt == 1:
                                        v['nx'] = struct.unpack_from('<b', vertex_data, local_o)[0] / 128.0
                                        v['ny'] = struct.unpack_from('<b', vertex_data, local_o+1)[0] / 128.0
                                        v['nz'] = struct.unpack_from('<b', vertex_data, local_o+2)[0] / 128.0
                                        mesh_normals.append((v['nx'], v['ny'], v['nz']))
                                        local_o += 3
                                    
                                    # === Position ===
                                    if posfmt == 1: # like that'll ever happen, what a load of--
                                        v['x'] = struct.unpack_from('<b', vertex_data, local_o)[0] / 128.0 * scale_x + pos_x
                                        v['y'] = struct.unpack_from('<b', vertex_data, local_o+1)[0] / 128.0 * scale_y + pos_y
                                        v['z'] = struct.unpack_from('<b', vertex_data, local_o+2)[0] / 128.0 * scale_z + pos_z
                                        mesh_verts.append((v['x'], v['y'], v['z']))
                                        local_o += 3
                                    elif posfmt == 2:
                                        local_o = ((local_o + 1) // 2) * 2  # align to 2 bytes
                                        v['x'] = struct.unpack_from('<h', vertex_data, local_o)[0] / 32768.0 * scale_x + pos_x 
                                        v['y'] = struct.unpack_from('<h', vertex_data, local_o+2)[0] / 32768.0 * scale_y + pos_y 
                                        v['z'] = struct.unpack_from('<h', vertex_data, local_o+4)[0] / 32768.0 * scale_z + pos_z 
                                        
                                        mesh_verts.append((v['x'], v['y'], v['z']))
                                        local_o += 6

                                    # Log vertex info
                                    log(f"    Vertex {vi}: pos=({v.get('x')}, {v.get('y')}, {v.get('z')})  uv=({v.get('u')}, {v.get('v')})  color={mesh_colors[-1] if mesh_colors else None}  normal={mesh_normals[-1] if mesh_normals else None}  weight={mesh_weights[-1] if mesh_weights else None}")

                                # Build faces for the triangle strip
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
                                        mesh_faces.append((v0, v1, v2))
                                        
                                # Create Blender mesh object for this mesh/strip
                                # This is also the point I read that The_Hero and LCS Team updated
                                # Alex(AK73)'s 3DSMax MDL Importer from 1.0.0 to 3.0.0 10+ years ago lol
                                # ... yet it's nowhere to be found

                                mesh_verts, mesh_faces = (mesh_verts, mesh_faces)
                                mesh_data = bpy.data.meshes.new(f"PSP_Mesh_{mesh_index}")
                                mesh_obj = bpy.data.objects.new(f"PSP_Mesh_{mesh_index}", mesh_data)
                                bpy.context.collection.objects.link(mesh_obj)
                            
                                mesh_data.from_pydata(mesh_verts, [], mesh_faces)
                                mesh_data.update()

                                M_world = frame_mats_world.get(frame_ptr)
                                mesh_obj.matrix_world = M_world
                                
                                log(f"✔ Built Blender mesh: PSP_Mesh_{mesh_index}, verts={len(mesh_verts)}, faces={len(mesh_faces)}")
                                # TODO: handle UVs, colors, normals, weights here by creating layers and assigning them
                            log("✔ All PSP geometry meshes have been imported and created in Blender.")
                            

                            

        except Exception as e:
            tb_str = traceback.format_exc()
            self.report({'ERROR'}, f"Import error: {e}\n{tb_str}")
            # Try to write a failure log too
            txt_path = os.path.splitext(filepath)[0] + "_import_log.txt"
            try:
                with open(txt_path, 'w', encoding='utf-8') as outf:
                    outf.write('\n'.join(debug_log))
                    outf.write('\n')
                    outf.write(tb_str)
            except Exception:
                pass
            return {'CANCELLED'}

        txt_path = os.path.splitext(filepath)[0] + "_import_log.txt"
        try:
            with open(txt_path, 'w', encoding='utf-8') as outf:
                outf.write('\n'.join(debug_log))
            log(f"✔ Debug log written to: {txt_path}")
        except Exception as e:
            log(f"✗ Failed to write debug log: {e}")

        return {'FINISHED'}
#######################################################
def menu_func_import(self, context):
    self.layout.operator(ImportMDLOperator.bl_idname, text="R* Leeds: Stories Model (.mdl)")

def register():
    bpy.utils.register_class(ImportMDLOperator)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(ImportMDLOperator)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register()  