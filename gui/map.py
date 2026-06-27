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

import bpy
import os
import gpu
import random
import numpy as np

from ..data import map_data

from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper, ExportHelper
from gpu_extras.batch import batch_for_shader
from ..ops.importer_common import game_version
from ..ops import ide_text_exporter, ipl_text_exporter
from bpy.props import StringProperty, CollectionProperty


#######################################################
class SCENE_OT_demonff_map_filebrowser(bpy.types.Operator, ImportHelper):
    """Opens file browser to select custom IPL, then imports it"""
    bl_idname = "scene.demonff_map_filebrowser"
    bl_label = "Import Map Section (.ipl)"

    filename_ext = ".ipl"
    filter_glob: StringProperty(default="*.ipl", options={'HIDDEN'})
    #######################################################
    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene.dff, "ipl_version")       # GTA III, VC, SA
        layout.prop(context.scene.dff, "import_as_binary")  # Faster processing?
    #######################################################
    def execute(self, context):
        settings = context.scene.dff
        settings.binary_ipl_path = self.filepath
        settings.custom_ipl_path = self.filepath
        settings.use_custom_map_section = True

        bpy.ops.scene.demonff_map_import('INVOKE_DEFAULT')
        return {'FINISHED'}
#######################################################
def quat_to_degrees(quat):
    euler = quat.to_euler('XYZ')
    return (euler.x * (180 / 3.141592653589793),
            abs(euler.y * (180 / 3.141592653589793)),  # Euler to GTAQuat method
            euler.z * (180 / 3.141592653589793))

IDE_TO_SAMP_DL_IDS = {i: 0 + i for i in range(50000)}
#######################################################
class IDEPathItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="IDE Path")
#######################################################
class DEMONFF_UL_ide_paths(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=item.name)
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=item.name)

#######################################################
class IDEObjectProps(bpy.types.PropertyGroup):
    obj_id: bpy.props.StringProperty(
        name="Object ID",
        description="Unique object ID in IDE files",
        default=""
    )

    model_name: bpy.props.StringProperty(
        name="Model Name",
        description="Model name to write in IDE/IPL lines",
        default=""
    )

    txd_name: bpy.props.StringProperty(
        name="TXD Name",
        description="Texture dictionary name",
        default=""
    )

    flags: bpy.props.StringProperty(
        name="Flags",
        description="IDE object flags",
        default="0"
    )

    draw_distance: bpy.props.StringProperty(
        name="Draw Distance",
        description="Single draw distance",
        default="100"
    )

    draw_distance1: bpy.props.StringProperty(
        name="Draw Distance 1",
        description="First draw distance for multi-distance objects",
        default=""
    )

    draw_distance2: bpy.props.StringProperty(
        name="Draw Distance 2",
        description="Second draw distance for multi-distance objects",
        default=""
    )

    draw_distance3: bpy.props.StringProperty(
        name="Draw Distance 3",
        description="Third draw distance for multi-distance objects",
        default=""
    )

    obj_type: bpy.props.EnumProperty(
        name="Object Type",
        description="IDE object section",
        items=(
            ('objs', 'Regular Object', 'Standard object'),
            ('tobj', 'Time Object', 'Time-based object'),
            ('anim', 'Animation Object', 'Animation object')
        ),
        default='objs'
    )

    ifp_name: bpy.props.StringProperty(
        name="IFP Name",
        description="Animation file name without extension",
        default=""
    )

    time_on: bpy.props.StringProperty(
        name="Time On",
        description="Hour when this object appears",
        default="0"
    )

    time_off: bpy.props.StringProperty(
        name="Time Off",
        description="Hour when this object disappears",
        default="24"
    )

#######################################################
class IPLObjectProps(bpy.types.PropertyGroup):
    interior: bpy.props.StringProperty(
        name="Interior",
        description="Interior ID",
        default="0"
    )

    lod: bpy.props.StringProperty(
        name="LOD",
        description="LOD object ID",
        default="-1"
    )

class DFFMapObjectProps(bpy.types.PropertyGroup):
    def sync_custom_property(self, context, key, value):
        obj = context.active_object
        if obj and hasattr(obj, "dff_map") and obj.dff_map == self:
            obj[key] = value

    ipl_section: bpy.props.EnumProperty(
        name="IPL Section",
        items=(
            ("inst", "inst", "Instance placement"),
            ("cull", "cull", "CULL zone"),
            ("enex", "enex", "Entrance/exit"),
            ("grge", "grge", "Garage"),
        ),
        default="inst"
    )

    object_id: bpy.props.IntProperty(name="Object ID", default=0)
    model_name: bpy.props.StringProperty(name="Model Name", default="")
    interior: bpy.props.IntProperty(name="Interior", default=0)
    lod: bpy.props.IntProperty(name="LOD", default=-1)

    ide_section: bpy.props.EnumProperty(
        name="Section",
        items=(
            ("objs", "objs", "Regular object"),
            ("tobj", "tobj", "Time object"),
            ("anim", "anim", "Animated object"),
        ),
        default="objs"
    )
    ide_object_id: bpy.props.IntProperty(name="Object ID", default=0)
    ide_model_name: bpy.props.StringProperty(name="Model Name", default="")
    ide_txd_name: bpy.props.StringProperty(name="TXD Name", default="")
    ide_meshes: bpy.props.IntProperty(name="Mesh Count", default=1, min=1)
    ide_draw_distance: bpy.props.FloatProperty(name="Draw Distance", default=0.0, min=0.0)
    ide_draw1: bpy.props.FloatProperty(name="DrawDist 1", default=0.0, min=0.0)
    ide_draw2: bpy.props.FloatProperty(name="DrawDist 2", default=0.0, min=0.0)
    ide_draw3: bpy.props.FloatProperty(name="DrawDist 3", default=0.0, min=0.0)
    ide_flags: bpy.props.IntProperty(name="Flags", default=0)
    ide_time_on: bpy.props.IntProperty(name="Time On", default=0, min=0, max=24)
    ide_time_off: bpy.props.IntProperty(name="Time Off", default=24, min=0, max=24)
    ide_anim: bpy.props.StringProperty(name="Anim", default="")

    pawn_model_name: bpy.props.StringProperty(name="Model Name", default="")
    pawn_txd_name: bpy.props.StringProperty(name="Texture Name", default="")

#######################################################
class DFFFrameProps(bpy.types.PropertyGroup):
    obj  : bpy.props.PointerProperty(type=bpy.types.Object)
    icon : bpy.props.StringProperty()
#######################################################
class DFFAtomicProps(bpy.types.PropertyGroup):
    obj       : bpy.props.PointerProperty(type=bpy.types.Object)
    frame_obj : bpy.props.PointerProperty(type=bpy.types.Object)
#######################################################
class DFFSceneProps(bpy.types.PropertyGroup):

    #######################################################
    def update_map_sections(self, context):
        return map_data.data[self.game_version_dropdown]['IPL_paths']
    #######################################################
    def frames_active_changed(self, context):
        scene_dff = context.scene.dff

        frames_num = len(scene_dff.frames)
        if not frames_num:
            return

        if scene_dff.frames_active >= frames_num:
            scene_dff.frames_active = frames_num - 1
            return

        frame_object = scene_dff.frames[scene_dff.frames_active].obj

        for a in scene_dff.frames: a.obj.select_set(False)
        frame_object.select_set(True)
        context.view_layer.objects.active = frame_object

    #######################################################
    def atomics_active_changed(self, context):
        scene_dff = context.scene.dff

        atomics_num = len(scene_dff.atomics)
        if not atomics_num:
            return

        if scene_dff.atomics_active >= atomics_num:
            scene_dff.atomics_active = atomics_num - 1
            return

        atomic_object = scene_dff.atomics[scene_dff.atomics_active].obj

        for a in scene_dff.atomics: a.obj.select_set(False)
        atomic_object.select_set(True)
        context.view_layer.objects.active = atomic_object

    game_version_dropdown : bpy.props.EnumProperty(
        name = 'Game',
        items = (
            (game_version.III, 'GTA III', 'GTA III map segments'),
            (game_version.VC, 'GTA VC', 'GTA VC map segments'),
            (game_version.SA, 'GTA SA', 'GTA SA map segments'),
            (game_version.SS, 'GTA S&S', 'GTA S&S map segments'),
            (game_version.MX, 'GTA MX', 'GTA Mixed map segments'),
            (game_version.LCS, 'GTA LCS', 'GTA LCS map segments'),
            (game_version.VCS, 'GTA VCS', 'GTA VCS map segments'),
            (game_version.IV, 'GTA IV', 'GTA IV map segments'),
        )
    )

    map_sections : bpy.props.EnumProperty(
        name = 'Map segment',
        items = update_map_sections
    )

    use_binary_ipl: bpy.props.BoolProperty(
        name="Use Binary IPL",
        description="Use binary IPL",
        default=False
    )

    ide_paths: bpy.props.CollectionProperty(
        type=IDEPathItem 
    )

    ide_index: bpy.props.IntProperty(
        name="IDE Index",
        default=0
    )

    binary_ipl_path: bpy.props.StringProperty(
        name="Binary IPL",
        description="Path to IPL file",
        default="",
        subtype='FILE_PATH'
    )

    import_as_binary: bpy.props.BoolProperty(
        name="Import as Binary",
        description="Convert selected text IPL into binary before reading",
        default=False
    )

    ipl_version: bpy.props.EnumProperty(
        name="IPL Version",
        description="Choose IPL format (structure) to interpret .ipl files",
        items=[
            ("III", "GTA III", "GTA III IPL structure (13 fields)"),
            ("VC", "GTA Vice City", "Vice City IPL structure (14 fields)"),
            ("SA", "GTA San Andreas", "San Andreas IPL structure (12 fields)"),
        ],
        default="SA"
    )

    custom_ipl_path: bpy.props.StringProperty(
        name="Custom IPL",
        description="Path to IPL file",
        default="",
        subtype='FILE_PATH'
    )
 
    use_custom_map_section : bpy.props.BoolProperty(
        name        = "Use Custom Map Section",
        default     = False
    )
 

    skip_lod: bpy.props.BoolProperty(
        name        = "Skip LOD Objects",
        description = "Skip map models named like LOD/LODf instead of using the SA IPL lod field backwards",
        default     = True
    )

    load_txd: bpy.props.BoolProperty(
        name        = "Load TXD files",
        default     = False
    )

    txd_pack: bpy.props.BoolProperty(
        name        = "Pack Images",
        description = "Pack imported TXD images into the .blend file",
        default     = False
    )

    read_mat_split  :  bpy.props.BoolProperty(
        name        = "Read Material Split",
        description = "Use the DFF bin mesh/material split while importing map DFFs",
        default     = True
    )

    create_backfaces: bpy.props.BoolProperty(
        name        = "Create Backfaces",
        description = "Keep duplicate/backface triangles by creating separate vertices for them",
        default     = False
    )

    load_collisions: bpy.props.BoolProperty(
        name        = "Load Map Collisions",
        default     = False
    )


    load_cull: bpy.props.BoolProperty(
        name        = "Load Map CULL",
        default     = False
    )

    load_grge: bpy.props.BoolProperty(
        name        = "Load Map GRGE",
        default     = False
    )

    load_enex: bpy.props.BoolProperty(
        name        = "Load Map ENEX",
        default     = False
    )

    game_root : bpy.props.StringProperty(
        name = 'Game root',
        default = '',
        description = "Folder with the game's executable",
        subtype = 'DIR_PATH'
    )

    dff_folder : bpy.props.StringProperty(
        name = 'Dff folder',
        default = '',
        description = "Define a folder where all of the dff models are stored.",
        subtype = 'DIR_PATH'
    )

    draw_facegroups : bpy.props.BoolProperty(
        name="Draw Face Groups",
        description="Display the Face Groups of the active object (if they exist) in the viewport",
        default=False
    )

    draw_bounds: bpy.props.BoolProperty(
        name="Draw Bounds",
        description = "Display the bounds of the active collection in the viewport",
        default = False
    )

    face_group_min : bpy.props.IntProperty(
        name = 'Face Group Minimum Size',
        description="Don't generate groups below this size",
        default = 20,
        min = 5,
        max = 200
    )

    face_group_max : bpy.props.IntProperty(
        name = 'Face Group Maximum Size',
        description="Don't generate groups above this size (minimum size overrides this if larger)",
        default = 50,
        min = 5,
        max = 200
    )

    face_group_avoid_smalls : bpy.props.BoolProperty(
        name = "Avoid overly small groups",
        description="Combine really small groups with their neighbor to avoid pointless isolated groups",
        default = True
    )

    frames : bpy.props.CollectionProperty(
        type    = DFFFrameProps,
        options = {'SKIP_SAVE','HIDDEN'}
    )

    frames_active : bpy.props.IntProperty(
        name    = "Active frame",
        default = 0,
        min     = 0,
        update  = frames_active_changed
    )

    atomics : bpy.props.CollectionProperty(
        type    = DFFAtomicProps,
        options = {'SKIP_SAVE','HIDDEN'}
    )

    atomics_active : bpy.props.IntProperty(
        name    = "Active atomic",
        default = 0,
        min     = 0,
        update  = atomics_active_changed
    )

    real_time_update : bpy.props.BoolProperty(
        name        = "Real Time Update",
        description = "Update the list of objects in real time",
        default     = True
    )

    filter_collection : bpy.props.BoolProperty(
        name        = "Filter Collection",
        description = "Filter frames and atomics by active collection",
        default     = True
    )
    #######################################################
    def draw_fg():
        if not bpy.context.scene.dff.draw_facegroups:
            return
        o = bpy.context.active_object
        if o and o.select_get() and o.type == 'MESH' and o.data.attributes.get('face group'):
            mesh = bpy.context.active_object.data
            attr = mesh.attributes['face group'].data
            if len(attr) == 0:
                return
            mesh.calc_loop_triangles()

            # As the face groups are stored as face attributes, we'll generate unique vertices across the whole overlay
            # because the colors of different faces can't be shared across vertices
            size = 3 * len(mesh.loop_triangles)
            vertices = np.empty((size, 3), 'f')
            vertex_colors = np.empty((size, 4), 'f')
            indices = np.arange(0, size, dtype='i')

            # Each face group gets a random color, but set an explicit seed so the resulting color array remains
            # deterministic across redraws
            random.seed(10)
            color = []
            grp = -1
            idx = 0
            for i, face in enumerate(mesh.loop_triangles):
                vertices[idx  ] = mesh.vertices[face.vertices[0]].co
                vertices[idx+1] = mesh.vertices[face.vertices[1]].co
                vertices[idx+2] = mesh.vertices[face.vertices[2]].co
                if grp != attr[i].value:
                    color = random.uniform(0.2, 1.0), random.uniform(0.2, 1.0), random.uniform(0.2, 1.0), 1.0
                    grp = attr[i].value
                vertex_colors[idx  ] = color
                vertex_colors[idx+1] = color
                vertex_colors[idx+2] = color
                idx += 3

            shader = gpu.shader.from_builtin('FLAT_COLOR')
            batch = batch_for_shader(
                shader, 'TRIS',
                {"pos": vertices, "color": vertex_colors},
                indices=indices,
            )

            # Draw the overlay over the existing collision object faces. There will be z-fighting as the object
            # location falls further from the origin, which it especially does for map objects. Unfortunate, but
            # probably fine for a simple visualization of the face groups.
            gpu.state.depth_test_set('LESS_EQUAL')
            gpu.state.depth_mask_set(True)
            gpu.matrix.push()
            gpu.matrix.multiply_matrix(bpy.context.active_object.matrix_local)
            batch.draw(shader)
            gpu.matrix.pop()
            gpu.state.depth_mask_set(False)

    #######################################################
    def register():
        bpy.types.Scene.dff = bpy.props.PointerProperty(type=DFFSceneProps)
#######################################################
class SCENE_OT_select_binary_ipl_and_import(bpy.types.Operator, ImportHelper):
    """Select Binary IPL file and immediately import"""
    bl_idname = "scene.select_binary_ipl_and_import"
    bl_label = "Select and Import Binary IPL"

    filename_ext = ".ipl"
    filter_glob: StringProperty(default="*.ipl", options={'HIDDEN'})
    #######################################################
    def execute(self, context):
        scene = context.scene
        dff = scene.dff

        if os.path.splitext(self.filepath)[-1].lower() == ".ipl":
            filepath = os.path.normpath(self.filepath)
            sep_pos = filepath.upper().find(f"DATA{os.sep}MAPS")
            if sep_pos != -1:
                game_root = filepath[:sep_pos]
                dff.game_root = game_root
                dff.binary_ipl_path = os.path.normpath(self.filepath)
            else:
                dff.binary_ipl_path = filepath

            dff.use_binary_ipl = True


            bpy.ops.scene.binary_import_ipl('INVOKE_DEFAULT')
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Not a valid .ipl file")
            return {'CANCELLED'}
    #######################################################
    def invoke(self, context, event):
        return context.window_manager.fileselect_add(self)

#######################################################
class SCENE_OT_select_ipl_and_import(bpy.types.Operator, ImportHelper):
    """Select IPL file and immediately import"""
    bl_idname = "scene.select_ipl_and_import"
    bl_label = "Select and Import IPL"

    filename_ext = ".ipl"
    filter_glob: StringProperty(default="*.ipl", options={'HIDDEN'})
    #######################################################
    def execute(self, context):
        scene = context.scene
        dff = scene.dff

        if os.path.splitext(self.filepath)[-1].lower() == ".ipl":
            filepath = os.path.normpath(self.filepath)
            sep_pos = filepath.upper().find(f"DATA{os.sep}MAPS")
            if sep_pos != -1:
                game_root = filepath[:sep_pos]
                dff.game_root = game_root
                dff.custom_ipl_path = os.path.normpath(self.filepath)
            else:
                dff.custom_ipl_path = filepath

            dff.use_custom_map_section = True

            bpy.ops.scene.select_ipl_and_import('INVOKE_DEFAULT')
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Not a valid .ipl file")
            return {'CANCELLED'}
    #######################################################
    def invoke(self, context, event):
        return context.window_manager.fileselect_add(self)

#######################################################
class SCENE_OT_ipl_select(bpy.types.Operator, ImportHelper):
 
    bl_idname = "scene.select_ipl"
    bl_label = "Select IPL File"
 
    filename_ext = ".ipl"
 
    filter_glob : bpy.props.StringProperty(
        default="*.ipl",
        options={'HIDDEN'})
    #######################################################
    def invoke(self, context, event):
        if not context.scene.dff.game_root:
            self.report({'WARNING'}, "Specify game root folder first")
            return {'CANCELLED'}
 
        self.filepath = context.scene.dff.game_root + "/DATA/MAPS/"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    #######################################################
    def execute(self, context):
        if os.path.splitext(self.filepath)[-1] == self.filename_ext:
             filepath = os.path.normpath(self.filepath)
             sep_pos = filepath.upper().find(f"DATA{os.sep}MAPS")
             game_root = filepath[:sep_pos]
             context.scene.dff.game_root = game_root
             context.scene.dff.custom_ipl_path = os.path.relpath(filepath, game_root)
        return {'FINISHED'}
 
#######################################################
def import_ide(filepaths, context):
    for filepath in filepaths:
        if not os.path.isfile(filepath):
            print(f"File not found: {filepath}")
            continue

        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                lines = file.readlines()
        except UnicodeDecodeError:
            print(f"UTF-8 decoding failed for {filepath}, attempting ASCII decoding.")
            try:
                with open(filepath, 'r', encoding='ascii', errors='replace') as file:
                    lines = file.readlines()
            except UnicodeDecodeError:
                print(f"Error decoding file: {filepath}")
                continue

        obj_data = {}
        in_obj_section = False

        for line in lines:
            line = line.strip()
            if line.lower().startswith("objs"):
                in_obj_section = True
            elif line.lower().startswith("end"):
                in_obj_section = False
            elif in_obj_section and line and not line.startswith("#"):
                parts = line.split(",")
                if len(parts) > 3:
                    obj_id = int(parts[0].strip())
                    obj_name = parts[1].strip()
                    txd_name = parts[2].strip()
                    samp_id = IDE_TO_SAMP_DL_IDS.get(obj_id, obj_id)  # Convert to SAMP 0.3DL/open.mp ID or keep positive
                    obj_data[obj_name] = (samp_id, txd_name)

        for obj in context.scene.objects:
            base_name = obj.name.split('.')[0]
            if base_name in obj_data:
                samp_id, txd_name = obj_data[base_name]
                obj["SAMP_ID"] = samp_id
                obj["TXD_Name"] = txd_name
                print(f"Assigned SAMP ID {samp_id} and TXD {txd_name} to {obj.name}")
            else:
                print(f"No matching SAMP ID found for {obj.name}")

    print("SAMP IDE import completed for all files")
#######################################################
def mass_import_samp_ide(filepaths, context):
    for filepath in filepaths:
        if not filepath.endswith('.ide'):
            print(f"Skipped non-IDE file: {filepath}")
            continue

        print(f"Importing SAMP IDE from {filepath}")
        if not os.path.isfile(filepath):
            print(f"File not found: {filepath}")
            continue

        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                lines = file.readlines()
        except UnicodeDecodeError:
            print(f"UTF-8 decoding failed for {filepath}, attempting ASCII decoding.")
            try:
                with open(filepath, 'r', encoding='ascii', errors='replace') as file:
                    lines = file.readlines()
            except UnicodeDecodeError:
                print(f"Error decoding file: {filepath}")
                continue

        obj_data = {}
        in_obj_section = False

        # Read and parse the objs section of the .ide file
        for line in lines:
            line = line.strip()
            if line.lower().startswith("objs"):
                in_obj_section = True
            elif line.lower().startswith("end"):
                in_obj_section = False
            elif in_obj_section and line and not line.startswith("#"):
                parts = line.split(",")
                if len(parts) > 3:
                    obj_id = int(parts[0].strip())  # SAMP ID or Object ID
                    obj_name = parts[1].strip()  # Model Name
                    txd_name = parts[2].strip()  # TXD Name
                    samp_id = IDE_TO_SAMP_DL_IDS.get(obj_id, obj_id)  # Convert to SAMP 0.3DL/open.mp ID or keep positive
                    obj_data[obj_name] = (samp_id, txd_name)

        # Match objects in the scene with the IDE data and apply SAMP ID and TXD name
        for obj in context.scene.objects:
            base_name = obj.name.split('.')[0]  # Get the base name of the object in the scene
            if base_name in obj_data:  # If the object name matches one from the IDE file
                samp_id, txd_name = obj_data[base_name]
                samp_id = -abs(samp_id)  # Apply '-' to the second argument (modelid)
                obj["SAMP_ID"] = samp_id  # Assign SAMP ID
                obj["TXD_Name"] = txd_name  # Assign TXD Name
                print(f"Assigned SAMP ID {samp_id} and TXD {txd_name} to {obj.name}")
            else:
                print(f"No matching SAMP ID found for {obj.name}")

    print("Mass SAMP IDE import completed")
#######################################################
class SAMP_IDE_Import_Operator(bpy.types.Operator):
    """Import SAMP .IDE File"""
    bl_idname = "object.samp_ide_import"
    bl_label = "Import SAMP .IDE File"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH", default="", options={'HIDDEN'}, maxlen=1024)
    filter_glob: bpy.props.StringProperty(default="*.ide", options={'HIDDEN'})

    def execute(self, context):
        import_ide([self.filepath], context)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
#######################################################
class Mass_IDE_Import_Operator(bpy.types.Operator):
    """Import .IDE Files"""
    bl_idname = "object.samp_mass_ide_import"
    bl_label = "Import IDE(s)"
    bl_options = {'REGISTER', 'UNDO'}

    files: CollectionProperty(type=bpy.types.PropertyGroup)
    directory: StringProperty(subtype="DIR_PATH")

    filter_glob: StringProperty(default="*.ide", options={'HIDDEN'})

    def execute(self, context):
        filepaths = [os.path.join(self.directory, f.name) for f in self.files]
        import_ide(filepaths, context)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
#######################################################
class DEMONFF_UL_ide_paths(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "name", text="", emboss=True)
#######################################################
class AddIDEPathOperator(bpy.types.Operator):
    bl_idname = "scene.add_ide_path"
    bl_label = "Add IDE Path"
    def execute(self, context):
        context.scene.dff.ide_paths.add()
        return {'FINISHED'}
#######################################################
class RemoveIDEPathOperator(bpy.types.Operator):
    bl_idname = "scene.remove_ide_path"
    bl_label = "Remove IDE Path"
    def execute(self, context):
        paths = context.scene.dff.ide_paths
        idx = context.scene.dff.ide_index
        if idx < len(paths):
            paths.remove(idx)
            context.scene.dff.ide_index = max(0, idx - 1)
        return {'FINISHED'}
#######################################################
class MapImportPanel(bpy.types.Panel):
    bl_label = "DemonFF - Map I/O"
    bl_idname = "SCENE_PT_map_import"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.dff

        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=True
        )
        col = flow.column()

        col.prop(settings, "game_version_dropdown", text="Game")

        if settings.use_custom_map_section:
            row = col.row(align=True)
            row.prop(settings, "custom_ipl_path", text="IPL path")
            row.operator("scene.select_ipl", text="", icon='FILEBROWSER')
        elif not settings.use_binary_ipl:
            col.prop(settings, "map_sections", text="Map segment")

        col.prop(settings, "use_custom_map_section", text="Use Custom Map Section")
        col.prop(settings, "use_binary_ipl", text="Use binary IPL")
        col.separator()

        box = col.box()
        box.prop(settings, "load_txd", text="Load TXD files")
        if settings.load_txd and hasattr(settings, "txd_pack"):
            box.prop(settings, "txd_pack", text="Pack Images")

        col.prop(settings, "skip_lod", text="Skip LOD Objects")
        col.prop(settings, "read_mat_split", text="Read Material Split")
        col.prop(settings, "create_backfaces", text="Create Backfaces")
        col.prop(settings, "load_collisions", text="Load Map Collisions")

        box = col.box()
        box.label(text="Import Entries")
        grid = box.grid_flow(columns=3, even_columns=True, even_rows=True)
        grid.prop(settings, "load_cull", text="CULL")
        grid.prop(settings, "load_grge", text="GRGE")
        grid.prop(settings, "load_enex", text="ENEX")

        if settings.use_binary_ipl or settings.use_custom_map_section:
            layout.separator()
            layout.label(text="IDE paths")
            layout.template_list("DEMONFF_UL_ide_paths", "", settings, "ide_paths", settings, "ide_index")

            row = layout.row(align=True)
            row.operator("scene.add_ide_path", text="Add IDE")
            row.operator("scene.remove_ide_path", text="Remove IDE")

        layout.separator()
        layout.prop(settings, "game_root", text="Game root")
        layout.prop(settings, "dff_folder", text="Dff folder")

        if settings.use_binary_ipl:
            layout.operator("scene.binary_import_ipl", text="Import binary IPL", icon='FILE_FOLDER')
        else:
            layout.operator("scene.demonff_map_import", text="Import map section", icon='FILE_FOLDER')

        layout.separator()

        row = layout.row()
        row.operator("object.export_to_ipl", text="Export IPL")

        row = layout.row()
        row.operator("object.export_to_ide", text="Export IDE")

        row = layout.row()
        row.operator("object.samp_mass_ide_import", text="Import IDE Data")
#######################################################
class DemonFFMapExportPanel(bpy.types.Panel):
    bl_label = "DemonFF - Map Export"
    bl_idname = "SCENE_PT_map_export"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"
    #######################################################
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("object.export_to_ipl", text="Export IPL")
        row.operator("object.export_to_ide", text="Export IDE")
        row.operator("object.samp_mass_ide_import", text="Import IDE")
#######################################################
class DemonFFPawnPanel(bpy.types.Panel):
    bl_label = "DemonFF - Pawn"
    bl_idname = "SCENE_PT_demonff_pawn"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    @classmethod
    def poll(cls, context):
        return False

    #######################################################
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("object.export_to_pawn", text="Export PWN")
        row.operator("object.remove_building_for_player", text="Remove Building For Player")
#######################################################
class MapObjectPanel(bpy.types.Panel):
    bl_label = "DemonFF - Map Properties"
    bl_idname = "OBJECT_PT_demonff_map_props"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        obj = context.object

        has_ide = hasattr(obj, "ide")
        has_ipl = hasattr(obj, "ipl")
        has_map = hasattr(obj, "dff_map")

        if not has_ide or not has_ipl:
            layout.label(text="Map properties are not registered for this object.")
            return

        box = layout.box()
        box.label(text="IPL Data", icon='OUTLINER_OB_EMPTY')
        col = box.column(align=True)
        col.prop(obj.ide, "obj_id")
        col.prop(obj.ide, "model_name")
        col.prop(obj.ipl, "interior")
        if context.scene.dff.game_version_dropdown == game_version.SA:
            col.prop(obj.ipl, "lod")

        col.separator()
        col.label(text=f"Position: {obj.location.x:.3f}, {obj.location.y:.3f}, {obj.location.z:.3f}")
        rot = obj.rotation_quaternion
        col.label(text=f"Rotation: {rot.x:.3f}, {rot.y:.3f}, {rot.z:.3f}, {rot.w:.3f}")

        box = layout.box()
        box.label(text="IDE Data", icon='OUTLINER_DATA_MESH')
        col = box.column(align=True)
        col.prop(obj.ide, "obj_type")
        col.prop(obj.ide, "txd_name")
        col.prop(obj.ide, "flags")

        col.separator()
        col.label(text="Draw Distances")
        if obj.ide.draw_distance1 or obj.ide.draw_distance2 or obj.ide.draw_distance3:
            col.prop(obj.ide, "draw_distance1")
            col.prop(obj.ide, "draw_distance2")
            col.prop(obj.ide, "draw_distance3")
        else:
            col.prop(obj.ide, "draw_distance")

        if obj.ide.obj_type == 'tobj':
            col.separator()
            col.label(text="Time Object")
            row = col.row(align=True)
            row.prop(obj.ide, "time_on")
            row.prop(obj.ide, "time_off")
        elif obj.ide.obj_type == 'anim':
            col.separator()
            col.label(text="Animation Object")
            col.prop(obj.ide, "ifp_name")

        if has_map:
            props = obj.dff_map
            box = layout.box()
            box.label(text="DemonFF Map Data")
            box.prop(props, "ipl_section")

            if props.ipl_section == "inst":
                col = box.column(align=True)
                col.prop(props, "object_id")
                col.prop(props, "model_name")
                col.prop(props, "interior")
                col.prop(props, "lod")

                box = layout.box()
                box.label(text="IDE Definition")
                row = box.row(align=True)
                row.prop(props, "ide_section")
                row.prop(props, "ide_flags")
                col = box.column(align=True)
                col.prop(props, "ide_object_id")
                col.prop(props, "ide_model_name")
                col.prop(props, "ide_txd_name")
                col.prop(props, "ide_meshes")
                col.prop(props, "ide_draw1")
                col.prop(props, "ide_draw2")
                col.prop(props, "ide_draw3")

                if props.ide_section == 'tobj':
                    row = col.row(align=True)
                    row.prop(props, "ide_time_on")
                    row.prop(props, "ide_time_off")
                elif props.ide_section == 'anim':
                    col.prop(props, "ide_anim")

                box = layout.box()
                box.label(text="Pawn Data")
                box.prop(props, "pawn_model_name")
                box.prop(props, "pawn_txd_name")
            else:
                layout.label(text=f"Section: {props.ipl_section}")

class SCENE_OT_import_ide(bpy.types.Operator):
    bl_idname = "scene.ide_import"
    bl_label = "Import IDE"
    bl_description = "Import IDE object data into selected scene objects"
    bl_options = {'REGISTER', 'UNDO'}

    files: CollectionProperty(type=bpy.types.PropertyGroup)
    directory: StringProperty(subtype="DIR_PATH")
    filter_glob: StringProperty(default="*.ide", options={'HIDDEN'})

    def read_ide_records(self, filepaths):
        records = {}

        def try_float(value, default=0.0):
            try:
                return float(value.strip())
            except Exception:
                return default

        def try_int(value, default=0):
            try:
                return int(float(value.strip()))
            except Exception:
                return default

        for filepath in filepaths:
            if not os.path.isfile(filepath):
                print(f"File not found: {filepath}")
                continue

            try:
                with open(filepath, 'r', encoding='utf-8') as file:
                    lines = file.readlines()
            except UnicodeDecodeError:
                with open(filepath, 'r', encoding='latin-1', errors='replace') as file:
                    lines = file.readlines()

            section = None
            for raw_line in lines:
                line = raw_line.split('#', 1)[0].strip()
                if not line:
                    continue

                lower = line.lower()
                if lower in {'objs', 'tobj', 'anim'}:
                    section = lower
                    continue
                if lower == 'end':
                    section = None
                    continue
                if section is None:
                    continue

                parts = [part.strip() for part in line.split(',')]
                if len(parts) < 5:
                    continue

                object_id = try_int(parts[0])
                model_name = parts[1]
                txd_name = parts[2]
                record = {
                    "section": section,
                    "object_id": object_id,
                    "model_name": model_name,
                    "txd_name": txd_name,
                    "mesh_count": 1,
                    "draw_distances": [],
                    "flags": 0,
                    "time_on": 0,
                    "time_off": 24,
                    "anim_name": "",
                }

                if section == 'tobj':
                    record["draw_distances"] = [try_float(parts[3], 100.0)]
                    record["time_on"] = try_int(parts[4], 0) if len(parts) > 4 else 0
                    record["time_off"] = try_int(parts[5], 24) if len(parts) > 5 else 24
                    record["flags"] = try_int(parts[6], 0) if len(parts) > 6 else 0
                elif section == 'anim':
                    record["anim_name"] = parts[-1]
                    core = parts[:-1]
                    if len(core) >= 6:
                        record["mesh_count"] = try_int(core[3], 1)
                        record["draw_distances"] = [try_float(value, 0.0) for value in core[4:-1]]
                        record["flags"] = try_int(core[-1], 0)
                    else:
                        record["draw_distances"] = [try_float(parts[3], 100.0)]
                        record["flags"] = try_int(parts[4], 0)
                else:
                    if len(parts) == 5:
                        record["draw_distances"] = [try_float(parts[3], 100.0)]
                        record["flags"] = try_int(parts[4], 0)
                    elif len(parts) >= 6:
                        record["mesh_count"] = try_int(parts[3], 1)
                        record["draw_distances"] = [try_float(value, 0.0) for value in parts[4:-1]]
                        record["flags"] = try_int(parts[-1], 0)

                if not record["draw_distances"]:
                    record["draw_distances"] = [100.0]

                records[model_name.lower()] = record

        return records

    def apply_record(self, obj, record):
        object_id = record["object_id"]
        model_name = record["model_name"]
        txd_name = record["txd_name"]
        flags = record["flags"]
        draw_distances = record["draw_distances"]

        obj["IDE_ID"] = object_id
        obj["DFF_Name"] = model_name
        obj["TXD_Name"] = txd_name
        obj["IDE_Flags"] = flags
        obj["DrawDistance"] = draw_distances[0]
        obj["SAMP_ID"] = -abs(object_id) if object_id else 0

        if hasattr(obj, "ide"):
            obj.ide.obj_id = str(object_id)
            obj.ide.model_name = model_name
            obj.ide.txd_name = txd_name
            obj.ide.flags = str(flags)
            obj.ide.obj_type = record["section"]
            obj.ide.draw_distance = str(draw_distances[0])
            obj.ide.draw_distance1 = str(draw_distances[0]) if len(draw_distances) > 0 else ""
            obj.ide.draw_distance2 = str(draw_distances[1]) if len(draw_distances) > 1 else ""
            obj.ide.draw_distance3 = str(draw_distances[2]) if len(draw_distances) > 2 else ""
            if record["section"] == 'tobj':
                obj.ide.time_on = str(record["time_on"])
                obj.ide.time_off = str(record["time_off"])
            elif record["section"] == 'anim':
                obj.ide.ifp_name = record["anim_name"]

        if hasattr(obj, "dff_map"):
            props = obj.dff_map
            props.ipl_section = "inst"
            props.object_id = object_id
            props.model_name = model_name
            props.ide_section = record["section"]
            props.ide_object_id = object_id
            props.ide_model_name = model_name
            props.ide_txd_name = txd_name
            props.ide_flags = flags
            props.ide_meshes = int(record["mesh_count"] or 1)
            props.ide_draw1 = float(draw_distances[0]) if len(draw_distances) > 0 else 0.0
            props.ide_draw2 = float(draw_distances[1]) if len(draw_distances) > 1 else 0.0
            props.ide_draw3 = float(draw_distances[2]) if len(draw_distances) > 2 else 0.0
            props.ide_time_on = int(record["time_on"] or 0)
            props.ide_time_off = int(record["time_off"] or 24)
            props.ide_anim = record["anim_name"] or ""
            if not props.pawn_model_name:
                props.pawn_model_name = model_name
            if not props.pawn_txd_name:
                props.pawn_txd_name = txd_name

    def execute(self, context):
        filepaths = [os.path.join(self.directory, item.name) for item in self.files]
        records = self.read_ide_records(filepaths)
        assigned = 0

        for obj in context.scene.objects:
            base_name = obj.name.split('.')[0].lower()
            record = records.get(base_name)
            if not record:
                continue
            self.apply_record(obj, record)
            assigned += 1
            print(f"Assigned IDE/Pawn data to {obj.name}")

        self.report({'INFO'}, f"Assigned IDE data to {assigned} object(s)")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class IMPORT_OT_pawn(bpy.types.Operator, ImportHelper):
    bl_idname = "scene.pwn_import"
    bl_label = "DemonFF Pawn Import"
    bl_description = "Import AddSimpleModel and CreateDynamicObject lines from a Pawn script"
    filename_ext = ".pwn"

    filter_glob: bpy.props.StringProperty(default="*.pwn;*.inc", options={'HIDDEN'})
    collection_name: bpy.props.StringProperty(name="Collection", default="Pawn Import")
    clear_existing: bpy.props.BoolProperty(name="Clear Existing Collection", default=False)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "collection_name")
        layout.prop(self, "clear_existing")

    def execute(self, context):
        from ..ops import map_exporter
        map_exporter.import_pawn({
            "file_name": self.filepath,
            "collection_name": self.collection_name,
            "clear_existing": self.clear_existing,
        })

        if not map_exporter.pwn_importer.total_objects_num:
            self.report({'ERROR'}, "No CreateDynamicObject lines found")
            return {'CANCELLED'}

        self.report({'INFO'}, "Imported %d Pawn object(s)" % map_exporter.pwn_importer.total_objects_num)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class EXPORT_OT_pawn(bpy.types.Operator, ExportHelper):
    bl_idname = "scene.pwn_export"
    bl_label = "DemonFF Pawn Export"
    bl_description = "Export Pawn and artconfig data for the current scene"
    filename_ext = ".pwn"

    only_selected: bpy.props.BoolProperty(name="Only Selected", default=False)
    model_directory: bpy.props.StringProperty(name="Model Directory", default="", description="Model directory for artconfig paths")
    skip_lod: bpy.props.BoolProperty(name="Skip LOD Objects", default=True)
    stream_distance: bpy.props.FloatProperty(name="Stream Distance", default=300.0)
    draw_distance: bpy.props.FloatProperty(name="Draw Distance", default=300.0)
    x_offset: bpy.props.FloatProperty(name="X Offset", default=0.0)
    y_offset: bpy.props.FloatProperty(name="Y Offset", default=0.0)
    z_offset: bpy.props.FloatProperty(name="Z Offset", default=0.0)
    force_all_worlds_interiors: bpy.props.BoolProperty(
        name="Ignore IPL Interior/World",
        default=True,
        description="Write CreateDynamicObject world/interior as -1/-1 so VCS IPL interior values do not hide exterior map objects"
    )
    filter_glob: bpy.props.StringProperty(default="*.pwn;*.inc", options={'HIDDEN'})

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "only_selected")
        layout.prop(self, "model_directory")
        layout.prop(self, "skip_lod")
        layout.prop(self, "stream_distance")
        layout.prop(self, "draw_distance")
        layout.prop(self, "x_offset")
        layout.prop(self, "y_offset")
        layout.prop(self, "z_offset")
        layout.prop(self, "force_all_worlds_interiors")

    def execute(self, context):
        from ..ops import map_exporter
        map_exporter.export_pawn({
            "file_name": self.filepath,
            "only_selected": self.only_selected,
            "model_directory": self.model_directory,
            "skip_lod": self.skip_lod,
            "stream_distance": self.stream_distance,
            "draw_distance": self.draw_distance,
            "x_offset": self.x_offset,
            "y_offset": self.y_offset,
            "z_offset": self.z_offset,
            "force_all_worlds_interiors": self.force_all_worlds_interiors,
        })

        if not map_exporter.pwn_exporter.total_objects_num:
            self.report({'ERROR'}, "No exportable meshes found")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported {map_exporter.pwn_exporter.total_objects_num} object(s)")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class DemonFFNewPawnPanel(bpy.types.Panel):
    bl_label = "DemonFF - Pawn I/O"
    bl_idname = "SCENE_PT_demonff_pawn_io"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator("scene.pwn_import", text="Import PWN")
        col.operator("scene.pwn_export", text="Export PWN + artconfig")
        col.separator()
        col.operator("object.remove_building_for_player", text="RemoveBuilding")

#######################################################
def register():
    bpy.utils.register_class(DFFFrameProps)
    bpy.utils.register_class(DFFAtomicProps)
    bpy.utils.register_class(DFFSceneProps)
    bpy.utils.register_class(SAMP_IDE_Import_Operator)
    bpy.utils.register_class(Mass_IDE_Import_Operator)
    bpy.utils.register_class(MapImportPanel)
    bpy.utils.register_class(DemonFFMapExportPanel)
    bpy.utils.register_class(DFFMapObjectProps)
    bpy.utils.register_class(MapObjectPanel)
    bpy.utils.register_class(SCENE_OT_import_ide)
    bpy.utils.register_class(IMPORT_OT_pawn)
    bpy.utils.register_class(EXPORT_OT_pawn)
    bpy.utils.register_class(DemonFFNewPawnPanel)
    bpy.utils.register_class(DEMONFF_UL_ide_paths)
    bpy.utils.register_class(AddIDEPathOperator)
    bpy.utils.register_class(RemoveIDEPathOperator)

def unregister():
    bpy.utils.unregister_class(DFFFrameProps)
    bpy.utils.unregister_class(DFFAtomicProps)
    bpy.utils.unregister_class(DFFSceneProps)
    bpy.utils.unregister_class(SAMP_IDE_Import_Operator)
    bpy.utils.unregister_class(Mass_IDE_Import_Operator)
    bpy.utils.unregister_class(MapImportPanel)
    bpy.utils.unregister_class(DemonFFMapExportPanel)
    bpy.utils.unregister_class(DFFMapObjectProps)
    bpy.utils.unregister_class(MapObjectPanel)
    bpy.utils.unregister_class(SCENE_OT_import_ide)
    bpy.utils.unregister_class(IMPORT_OT_pawn)
    bpy.utils.unregister_class(EXPORT_OT_pawn)
    bpy.utils.unregister_class(DemonFFNewPawnPanel)
    del bpy.types.Scene.dff.ide_paths
    del bpy.types.Scene.dff.ide_index
    bpy.utils.unregister_class(DEMONFF_UL_ide_paths)
    bpy.utils.unregister_class(AddIDEPathOperator)
    bpy.utils.unregister_class(RemoveIDEPathOperator)

if __name__ == "__main__":
    register()
