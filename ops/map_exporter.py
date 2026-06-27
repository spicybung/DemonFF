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
import re
import mathutils

from ..data import map_data
from ..ops.importer_common import game_version

from bpy.props import StringProperty, CollectionProperty


#######################################################
def quat_to_degrees(quat):
    euler = quat.to_euler('XYZ')
    return (euler.x * (180 / 3.141592653589793),
            abs(euler.y * (180 / 3.141592653589793)),  # Euler to GTAQuat method
            euler.z * (180 / 3.141592653589793))

IDE_TO_SAMP_DL_IDS = {i: 0 + i for i in range(50000)}

#######################################################
def clean_map_name(name):
    return name.split('.')[0]

#######################################################
def get_custom_prop(obj, key, default=None):
    return obj[key] if key in obj else default

#######################################################
def get_dff_type(obj):
    if hasattr(obj, "dff") and hasattr(obj.dff, "type"):
        return obj.dff.type
    return ""

#######################################################
def get_map_props(obj):
    return obj.dff_map if hasattr(obj, "dff_map") else None

#######################################################
def first_good_value(*values, default=None):
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value == "":
            continue
        return value
    return default

#######################################################
def set_map_identity_props(obj, ide_id, model_name, txd_name, samp_id=None):
    obj["IDE_ID"] = ide_id
    obj["DFF_Name"] = model_name
    obj["TXD_Name"] = txd_name
    if samp_id is not None:
        obj["SAMP_ID"] = samp_id

    if hasattr(obj, "ide"):
        obj.ide.obj_id = str(ide_id)
        obj.ide.model_name = str(model_name)
        obj.ide.txd_name = str(txd_name)

    if hasattr(obj, "dff_map"):
        obj.dff_map.object_id = int(ide_id) if str(ide_id).lstrip('-').isdigit() else 0
        obj.dff_map.model_name = str(model_name)
        obj.dff_map.ide_object_id = int(ide_id) if str(ide_id).lstrip('-').isdigit() else 0
        obj.dff_map.ide_model_name = str(model_name)
        obj.dff_map.ide_txd_name = str(txd_name)
        if not obj.dff_map.pawn_model_name:
            obj.dff_map.pawn_model_name = str(model_name)
        if not obj.dff_map.pawn_txd_name:
            obj.dff_map.pawn_txd_name = str(txd_name)

#######################################################
def get_object_model_name(obj):
    props = get_map_props(obj)
    if props:
        return str(first_good_value(props.model_name, props.ide_model_name, props.pawn_model_name, default=clean_map_name(obj.name)))
    if hasattr(obj, "ide") and obj.ide.model_name:
        return obj.ide.model_name
    return str(get_custom_prop(obj, "DFF_Name", clean_map_name(obj.name)))

#######################################################
def get_object_txd_name(obj):
    props = get_map_props(obj)
    if props:
        return str(first_good_value(props.ide_txd_name, props.pawn_txd_name, default=None) or get_custom_prop(obj, "TXD_Name", "default_txd"))
    if hasattr(obj, "ide") and obj.ide.txd_name:
        return obj.ide.txd_name
    return str(get_custom_prop(obj, "TXD_Name", "default_txd"))

#######################################################
def get_pawn_model_name(obj):
    props = get_map_props(obj)
    if props and props.pawn_model_name:
        return props.pawn_model_name
    return get_object_model_name(obj)

#######################################################
def get_pawn_txd_name(obj):
    props = get_map_props(obj)
    if props and props.pawn_txd_name:
        return props.pawn_txd_name
    return get_object_txd_name(obj)

#######################################################
def get_object_ide_id(obj, default=0):
    props = get_map_props(obj)
    if props:
        value = first_good_value(props.object_id, props.ide_object_id, default=None)
        if value not in (None, 0):
            return value
    if hasattr(obj, "ide") and obj.ide.obj_id:
        return obj.ide.obj_id
    return get_custom_prop(obj, "IDE_ID", default)

#######################################################
def get_object_samp_id(obj, default=None):
    if "SAMP_ID" in obj:
        return obj["SAMP_ID"]
    return default

#######################################################
def get_object_interior(obj, default=0):
    props = get_map_props(obj)
    if props and props.interior not in (None, 0):
        return props.interior
    if hasattr(obj, "ipl") and obj.ipl.interior:
        return obj.ipl.interior
    return get_custom_prop(obj, "Interior", default)

#######################################################
def get_stream_world_and_interior(obj, default_world=-1, default_interior=-1):
    interior = get_object_interior(obj, default_interior)

    # The third field in VCS text IPL inst lines is a VCS interior/area value.
    # It is not a SA-MP/open.mp virtual world.  For converted exterior maps,
    # exporting it into CreateDynamicObject's world/interior slots hides objects
    # from players in world 0/interior 0.
    if getattr(pwn_exporter, "force_all_worlds_interiors", True):
        return -1, -1

    return default_world, interior

#######################################################
def get_object_lod(obj, default=-1):
    props = get_map_props(obj)
    if props and props.lod not in (None, 0):
        return props.lod
    if hasattr(obj, "ipl") and obj.ipl.lod:
        return obj.ipl.lod
    return get_custom_prop(obj, "LODIndex", default)

#######################################################
def get_object_flags(obj, default=0):
    props = get_map_props(obj)
    if props and props.ide_flags:
        return props.ide_flags
    if hasattr(obj, "ide") and obj.ide.flags:
        return obj.ide.flags
    return get_custom_prop(obj, "IDE_Flags", default)

#######################################################
def get_object_draw_distances(obj):
    props = get_map_props(obj)
    if props:
        distances = []
        for value in (props.ide_draw1, props.ide_draw2, props.ide_draw3):
            if value:
                distances.append(str(value))
        if not distances and props.ide_draw_distance:
            distances.append(str(props.ide_draw_distance))
        if distances:
            return distances

    if hasattr(obj, "ide"):
        distances = []
        if obj.ide.draw_distance:
            distances.append(obj.ide.draw_distance)
        if obj.ide.draw_distance1:
            distances.append(obj.ide.draw_distance1)
        if obj.ide.draw_distance2:
            distances.append(obj.ide.draw_distance2)
        if obj.ide.draw_distance3:
            distances.append(obj.ide.draw_distance3)
        if distances:
            return distances
    return [str(get_custom_prop(obj, "DrawDistance", 300.0))]

#######################################################
def get_object_ide_section(obj):
    props = get_map_props(obj)
    if props and props.ide_section:
        return props.ide_section
    if hasattr(obj, "ide") and obj.ide.obj_type:
        return obj.ide.obj_type
    return "objs"

#######################################################
def object_is_lod(obj):
    name = obj.name.lower()
    return name.startswith("lod") or ".colmesh" in name or get_dff_type(obj) == 'COL'

#######################################################
def object_is_2dfx_pawn_helper(obj):
    names = [
        obj.name,
        clean_map_name(obj.name),
        get_object_model_name(obj),
        get_pawn_model_name(obj),
    ]

    for name in names:
        if not name:
            continue

        clean_name = str(name).lower().split('.')[0]
        if clean_name.startswith("2dfx_"):
            return True

    return get_dff_type(obj) == '2DFX'

#######################################################
def get_transform_source(obj):
    if obj.parent and obj.parent.type == 'EMPTY':
        return obj.parent
    return obj

#######################################################
def get_export_transform(obj):
    source = get_transform_source(obj)
    position = source.location.copy()
    rotation = source.matrix_world.to_quaternion()
    scale = source.scale.copy()
    return position, rotation, scale

class DFFFrameProps(bpy.types.PropertyGroup):
    obj  : bpy.props.PointerProperty(type=bpy.types.Object)
    icon : bpy.props.StringProperty()

#######################################################
class DFFAtomicProps(bpy.types.PropertyGroup):
    obj       : bpy.props.PointerProperty(type=bpy.types.Object)
    frame_obj : bpy.props.PointerProperty(type=bpy.types.Object)
#######################################################
class DFFSceneProps(bpy.types.PropertyGroup):

    def update_map_sections(self, context):
        return map_data.data[self.game_version_dropdown]['IPL_paths']

    game_version_dropdown: bpy.props.EnumProperty(
        name='Game',
        items=(
            (game_version.III, 'GTA III', 'GTA III map segments'),
            (game_version.VC, 'GTA VC', 'GTA VC map segments'),
            (game_version.SA, 'GTA SA', 'GTA SA map segments'),
            (game_version.SS, 'GTA S&S', 'GTA S&S map segments'),
            (game_version.MX, 'GTA SA', 'GTA SA map segments'),
            (game_version.LCS, 'GTA LCS', 'GTA LCS map segments'),
            (game_version.VCS, 'GTA VCS', 'GTA VCS map segments'),
            (game_version.IV, 'GTA IV', 'GTA IV map segments'),
        )
    )
    map_sections: bpy.props.EnumProperty(
        name='Map segment',
        items=update_map_sections
    )

    skip_lod: bpy.props.BoolProperty(
        name="Skip LOD Objects",
        default=False
    )

    game_root: bpy.props.StringProperty(
        name='Game root',
        default='',
        description="Folder with the game's executable",
        subtype='DIR_PATH'
    )

    dff_folder: bpy.props.StringProperty(
        name='Dff folder',
        default='',
        description="Define a folder where all of the dff models are stored.",
        subtype='DIR_PATH'
    )

    stream_distance: bpy.props.FloatProperty(
        name="Stream Distance",
        default=300.0,
        description="Stream distance for dynamic objects"
    )

    draw_distance: bpy.props.FloatProperty(
        name="Draw Distance",
        default=300.0,
        description="Draw distance for objects"
    )

    x_offset: bpy.props.FloatProperty(
        name="X Offset",
        default=0.0,
        description="Offset for the x coordinate of the objects"
    )

    y_offset: bpy.props.FloatProperty(
        name="Y Offset",
        default=0.0,
        description="Offset for the y coordinate of the objects"
    )

    frames: bpy.props.CollectionProperty(type=DFFFrameProps)

    @classmethod
    def register(cls):
        bpy.types.Scene.dff = bpy.props.PointerProperty(type=cls)

    @classmethod
    def unregister(cls):
        del bpy.types.Scene.dff
#######################################################
def import_ide(filepaths, context):
    for filepath in filepaths:
        if not os.path.isfile(filepath):
            print(f"File not found: {filepath}")
            continue

        try:
            # Attempt to open and read as UTF-8
            with open(filepath, 'r', encoding='utf-8') as file:
                lines = file.readlines()
        except UnicodeDecodeError:
            print(f"UTF-8 decoding failed for {filepath}, attempting ASCII decoding.")
            try:
                # Fallback to ASCII encoding
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
                set_map_identity_props(obj, abs(int(samp_id)), base_name, txd_name, samp_id)
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
                set_map_identity_props(obj, abs(int(samp_id)), base_name, txd_name, samp_id)
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
    #######################################################
    def execute(self, context):
        import_ide([self.filepath], context)
        return {'FINISHED'}
    #######################################################
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
    #######################################################
    def execute(self, context):
        filepaths = [os.path.join(self.directory, f.name) for f in self.files]
        import_ide(filepaths, context)
        return {'FINISHED'}
    #######################################################
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
#######################################################
class ExportToIPLOperator(bpy.types.Operator):
    bl_idname = "object.export_to_ipl"
    bl_label = "Export to IPL"
    bl_description = "Export selected objects as an IPL file"
    filename_ext = ".ipl"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    #######################################################
    def format_inst_line(self, context, obj):
        game_id = context.scene.dff.game_version_dropdown
        object_id = get_object_ide_id(obj, 0)
        model_name = get_object_model_name(obj)
        interior = get_object_interior(obj, 0)
        lod_index = get_object_lod(obj, -1)
        position, rotation, scale = get_export_transform(obj)

        rot_w = -rotation.w
        rot_x = rotation.x
        rot_y = rotation.y
        rot_z = rotation.z

        if game_id == game_version.III:
            return (
                f"{object_id}, {model_name}, "
                f"{position.x:.6f}, {position.y:.6f}, {position.z:.6f}, "
                f"{scale.x:.6f}, {scale.y:.6f}, {scale.z:.6f}, "
                f"{rot_x:.6f}, {rot_y:.6f}, {rot_z:.6f}, {rot_w:.6f}"
            )

        if game_id == game_version.VC:
            return (
                f"{object_id}, {model_name}, {interior}, "
                f"{position.x:.6f}, {position.y:.6f}, {position.z:.6f}, "
                f"{scale.x:.6f}, {scale.y:.6f}, {scale.z:.6f}, "
                f"{rot_x:.6f}, {rot_y:.6f}, {rot_z:.6f}, {rot_w:.6f}"
            )

        return (
            f"{object_id}, {model_name}, {interior}, "
            f"{position.x:.6f}, {position.y:.6f}, {position.z:.6f}, "
            f"{rot_x:.6f}, {rot_y:.6f}, {rot_z:.6f}, {rot_w:.6f}, {lod_index}"
        )

    #######################################################
    def execute(self, context):
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected_objects:
            self.report({'INFO'}, "No mesh objects selected. Export cancelled.")
            return {'CANCELLED'}

        output_file = self.filepath if self.filepath.lower().endswith('.ipl') else self.filepath + '.ipl'

        with open(output_file, 'w', encoding='latin-1') as file:
            file.write("inst\n")
            written = 0
            for obj in selected_objects:
                if context.scene.dff.skip_lod and object_is_lod(obj):
                    continue
                file.write(self.format_inst_line(context, obj) + f"  # {obj.name}\n")
                print(f"Exporting {obj.name} with IDE ID {get_object_ide_id(obj, 0)}")
                written += 1
            file.write("end\n")

        self.report({'INFO'}, f"Exported {written} objects to {output_file}")
        return {'FINISHED'}

    #######################################################
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

#######################################################
class ExportToIDEOperator(bpy.types.Operator):
    bl_idname = "object.export_to_ide"
    bl_label = "Export to IDE"
    bl_description = "Export scene objects as an IDE file"
    filename_ext = ".ide"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    #######################################################
    def format_objs_line(self, obj):
        object_id = get_object_ide_id(obj, 0)
        model_name = get_object_model_name(obj)
        txd_name = get_object_txd_name(obj)
        flags = get_object_flags(obj, 0)
        distances = get_object_draw_distances(obj)

        if len(distances) == 1:
            return f"{object_id}, {model_name}, {txd_name}, {distances[0]}, {flags}"
        if len(distances) == 2:
            return f"{object_id}, {model_name}, {txd_name}, 1, {distances[0]}, {distances[1]}, {flags}"
        return f"{object_id}, {model_name}, {txd_name}, 1, {distances[0]}, {distances[1]}, {distances[2]}, {flags}"

    #######################################################
    def format_tobj_line(self, obj):
        base_line = self.format_objs_line(obj)
        time_on = obj.ide.time_on if hasattr(obj, "ide") and obj.ide.time_on else "0"
        time_off = obj.ide.time_off if hasattr(obj, "ide") and obj.ide.time_off else "24"
        return f"{base_line}, {time_on}, {time_off}"

    #######################################################
    def execute(self, context):
        scene_objects = [obj for obj in context.scene.objects if obj.type == 'MESH']
        if not scene_objects:
            self.report({'INFO'}, "No mesh objects in scene. Export cancelled.")
            return {'CANCELLED'}

        output_file = self.filepath if self.filepath.lower().endswith('.ide') else self.filepath + '.ide'
        seen_ids = set()
        objs_lines = []
        tobj_lines = []

        for obj in scene_objects:
            if context.scene.dff.skip_lod and object_is_lod(obj):
                continue

            object_id = str(get_object_ide_id(obj, 0))
            seen_key = object_id if object_id not in ('', '0') else get_object_model_name(obj)
            if seen_key in seen_ids:
                continue
            seen_ids.add(seen_key)

            if hasattr(obj, "ide") and obj.ide.obj_type == 'tobj':
                tobj_lines.append(self.format_tobj_line(obj) + f"  # {obj.name}")
            else:
                objs_lines.append(self.format_objs_line(obj) + f"  # {obj.name}")

            print(f"Exporting {obj.name} with ID {object_id} and TXD {get_object_txd_name(obj)}")

        with open(output_file, 'w', encoding='latin-1') as file:
            if objs_lines:
                file.write("objs\n")
                for line in objs_lines:
                    file.write(line + "\n")
                file.write("end\n")
            if tobj_lines:
                file.write("tobj\n")
                for line in tobj_lines:
                    file.write(line + "\n")
                file.write("end\n")

        self.report({'INFO'}, f"Exported {len(objs_lines) + len(tobj_lines)} object definitions to {output_file}")
        return {'FINISHED'}

    #######################################################
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

#######################################################
class ExportToPawnOperator(bpy.types.Operator):
    bl_idname = "object.export_to_pawn"
    bl_label = "Export to Pawn Script"
    bl_description = "Export selected objects as a DynamicObject pawn script"
    filename_ext = ".pwn"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    model_directory: bpy.props.StringProperty(
        name="Model Directory",
        default="",
        description="Model directory for the artconfig paths"
    )
    skip_lod: bpy.props.BoolProperty(
        name="Skip LOD Objects",
        default=False,
        description="Skip LOD objects in the .pwn and artconfig scripts"
    )
    stream_distance: bpy.props.FloatProperty(
        name="Stream Distance",
        default=300.0,
        description="Stream distance for dynamic objects"
    )
    draw_distance: bpy.props.FloatProperty(
        name="Draw Distance",
        default=300.0,
        description="Draw distance for objects"
    )
    x_offset: bpy.props.FloatProperty(
        name="X Offset",
        default=0.0,
        description="Offset for the x coordinate of the objects"
    )
    y_offset: bpy.props.FloatProperty(
        name="Y Offset",
        default=0.0,
        description="Offset for the y coordinate of the objects"
    )
    #######################################################
    def execute(self, context):
        #######################################################
        def export_to_pawn(file_path, objects):
            artconfig_path = os.path.join(os.path.dirname(file_path), 'artconfig.txt')
            baseid = 19379
            model_directory = self.model_directory.strip()
            with open(file_path, 'w') as f, open(artconfig_path, 'w') as artconfig:
                current_id = -1000  # Starting ID
                max_id = -40000  # Maximum ID

                name_mapping = {}
                written_addsimplemodels = {}
                addsimplemodel_written = 0
                addsimplemodel_skipped = 0
                addsimplemodel_conflicts = 0

                for obj in objects:
                    if self.skip_lod and (obj.name.startswith("LOD") or ".ColMesh" in obj.name):
                        continue
                    if object_is_2dfx_pawn_helper(obj):
                        continue

                    if current_id <= max_id:
                        self.report({'INFO'}, "Maximum ID limit reached. Exporting now...")
                        # Reset current_id to continue the export process
                        current_id = -100000 # Lets hope this number never gets reached :P

                    # Determine if the mesh is parented to an empty
                    parent = obj.parent
                    if parent and parent.type == 'EMPTY':
                        position = parent.location.copy()
                        position.x += self.x_offset
                        position.y += self.y_offset
                        rotation = quat_to_degrees(parent.rotation_quaternion)
                    else:
                        position = obj.location.copy()
                        position.x += self.x_offset
                        position.y += self.y_offset
                        rotation = quat_to_degrees(obj.rotation_quaternion)

                    base_name = clean_map_name(obj.name)

                    explicit_samp_id = get_object_samp_id(obj)
                    if explicit_samp_id is not None:
                        object_id = explicit_samp_id
                    else:
                        if base_name not in name_mapping:
                            name_mapping[base_name] = current_id
                            current_id -= 1
                        object_id = name_mapping[base_name]

                    world_id = -1
                    interior = -1
                    stream_distance = self.stream_distance
                    draw_distance = self.draw_distance

                    dff_name = get_object_model_name(obj)
                    txd_name = get_object_txd_name(obj)

                    line = f"CreateDynamicObject({object_id}, {position.x:.2f}, {position.y:.2f}, {position.z:.2f}, " \
                           f"{rotation[0]:.2f}, {rotation[1]:.2f}, {rotation[2]:.2f}, {world_id}, {interior}, -1, {stream_distance:.2f}, {draw_distance:.2f});  // {obj.name}\n"
                    f.write(line)
                    print(f"Exporting {obj.name} with ID {object_id}")

                    dff_path = f"{model_directory}/{dff_name}.dff"
                    txd_path = f"{model_directory}/{txd_name}.txd"
                    model_key = str(object_id).strip().lower()
                    model_paths = (dff_path.lower(), txd_path.lower())
                    existing_paths = written_addsimplemodels.get(model_key)

                    if existing_paths is None:
                        written_addsimplemodels[model_key] = model_paths
                        artconfig_line = f"AddSimpleModel(-1, {baseid}, {object_id}, \"{dff_path}\", \"{txd_path}\");  // {dff_name}\\n"
                        artconfig.write(artconfig_line)
                        addsimplemodel_written += 1
                        print(f"Writing to artconfig: {artconfig_line.strip()}")
                    elif existing_paths == model_paths:
                        addsimplemodel_skipped += 1
                        print(f"DemonFF Pawn export: skipped duplicate AddSimpleModel for model ID {object_id} ({dff_path}, {txd_path}) from {obj.name}.")
                    else:
                        addsimplemodel_skipped += 1
                        addsimplemodel_conflicts += 1
                        print(
                            f"DemonFF Pawn export warning: skipped conflicting duplicate AddSimpleModel for model ID {object_id} from {obj.name}. "
                            f"Already wrote ({existing_paths[0]}, {existing_paths[1]}), new request was ({dff_path.lower()}, {txd_path.lower()})."
                        )

                    lod_value = get_object_lod(obj, None)
                    if lod_value is not None and str(lod_value) != '-1':
                        lod_index = lod_value
                        lod_line = f"CreateDynamicObject({lod_index}, {position.x:.2f}, {position.y:.2f}, {position.z:.2f}, " \
                                   f"{rotation[0]:.2f}, {rotation[1]:.2f}, {rotation[2]:.2f}, {world_id}, {interior}, -1, {stream_distance:.2f}, {draw_distance:.2f});  // LOD for {obj.name}\n"
                        f.write(lod_line)
                        print(f"Exporting LOD for {obj.name} with LODIndex {lod_index}")

                print(f"Exported Pawn script to {file_path}")
                print(f"Exported artconfig to {artconfig_path}")
                print(
                    f"DemonFF Pawn export verify: objects={len(objects)}, AddSimpleModel_written={addsimplemodel_written}, "
                    f"AddSimpleModel_duplicates_skipped={addsimplemodel_skipped}, AddSimpleModel_conflicts={addsimplemodel_conflicts}."
                )

        selected_objects = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
        if not selected_objects:
            self.report({'INFO'}, "No mesh objects selected. Export cancelled.")
            return {'CANCELLED'}

        output_file = self.filepath if self.filepath.endswith('.pwn') else self.filepath + '.pwn'

        export_to_pawn(output_file, selected_objects)

        self.report({'INFO'}, f"Exported {len(selected_objects)} objects to {output_file}")
        self.report({'INFO'}, f"Exported artconfig.txt to {os.path.dirname(output_file)}")
        return {'FINISHED'}
    #######################################################
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    #######################################################
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "model_directory")
        layout.prop(self, "skip_lod")
        layout.prop(self, "stream_distance")
        layout.prop(self, "draw_distance")
        layout.prop(self, "x_offset")
        layout.prop(self, "y_offset")
#######################################################
class RemoveBuildingForPlayerOperator(bpy.types.Operator):
    bl_idname = "object.remove_building_for_player"
    bl_label = "Remove Building For Player"
    bl_description = "Export RemoveBuilding script to console"
    bl_options = {'REGISTER', 'UNDO'}
    #######################################################
    def execute(self, context):
        for obj in context.selected_objects:
            obj_id = get_object_ide_id(obj, -1)
            position = obj.location
            radius = 200.0  # Default radius, can be adjusted
            line = f"RemoveBuildingForPlayer(playerid, {obj_id}, {position.x:.2f}, {position.y:.2f}, {position.z:.2f}, {radius:.2f});"
            print(line)
        return {'FINISHED'}
#######################################################
class MapImportPanel(bpy.types.Panel):
    """Creates a Panel in the scene context of the properties editor"""
    bl_label = "DemonFF - Map Import"
    bl_idname = "SCENE_PT_map_import"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"
    #######################################################
    def draw(self, context):
        layout = self.layout
        settings = context.scene.dff

        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=True)

        col = flow.column()
        col.prop(settings, "game_version_dropdown", text="Game")
        col.prop(settings, "map_sections", text="Map segment")
        col.separator()
        col.prop(settings, "skip_lod", text="Skip LOD objects")

        layout.separator()

        layout.prop(settings, 'game_root')
        layout.prop(settings, 'dff_folder')

        row = layout.row()
        row.operator("scene.demonff_map_import")

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
def register():
    bpy.utils.register_class(DFFFrameProps)
    bpy.utils.register_class(DFFAtomicProps)
    bpy.utils.register_class(DFFSceneProps)
    bpy.utils.register_class(SAMP_IDE_Import_Operator)
    bpy.utils.register_class(Mass_IDE_Import_Operator)
    bpy.utils.register_class(ExportToIPLOperator)
    bpy.utils.register_class(ExportToIDEOperator)
    bpy.utils.register_class(ExportToPawnOperator)
    bpy.utils.register_class(RemoveBuildingForPlayerOperator)
    bpy.utils.unregister_class(MapImportPanel)
    bpy.utils.register_class(DemonFFMapExportPanel)
    DFFSceneProps.register()

def unregister():
    bpy.utils.unregister_class(DFFFrameProps)
    bpy.utils.unregister_class(DFFAtomicProps)
    bpy.utils.unregister_class(DFFSceneProps)
    bpy.utils.unregister_class(SAMP_IDE_Import_Operator)
    bpy.utils.unregister_class(Mass_IDE_Import_Operator)
    bpy.utils.unregister_class(ExportToIPLOperator)
    bpy.utils.unregister_class(ExportToIDEOperator)
    bpy.utils.unregister_class(ExportToPawnOperator)
    bpy.utils.unregister_class(RemoveBuildingForPlayerOperator)
    bpy.utils.unregister_class(MapImportPanel)
    bpy.utils.unregister_class(DemonFFMapExportPanel)
    DFFSceneProps.unregister()

if __name__ == "__main__":
    register()

#######################################################
class ide_exporter:
    total_definitions_num = 0

#######################################################
def export_ide(options):
    from . import ide_exporter as ide_exporter_module

    ide_exporter_module.export_ide(options)
    total = len(getattr(ide_exporter_module.ide_exporter, "objs_objects", []))
    total += len(getattr(ide_exporter_module.ide_exporter, "tobj_objects", []))
    total += len(getattr(ide_exporter_module.ide_exporter, "anim_objects", []))
    ide_exporter.total_definitions_num = total


#######################################################
def strip_pawn_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    lines = []
    for line in text.splitlines():
        comment = ""
        if "//" in line:
            line, comment = line.split("//", 1)
            comment = comment.strip()
        lines.append((line, comment))
    return lines

#######################################################
def split_pawn_args(args_text):
    args = []
    current = []
    in_string = False
    escape = False

    for char in args_text:
        if in_string:
            current.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            current.append(char)
            continue

        if char == ',':
            args.append(''.join(current).strip())
            current = []
            continue

        current.append(char)

    if current or args_text.strip():
        args.append(''.join(current).strip())

    return args

#######################################################
def clean_pawn_string(value):
    value = str(value).strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1]
    return value.replace('\\\\', '\\').replace('\\"', '"')

#######################################################
def pawn_to_int(value, default=0):
    try:
        return int(str(value).strip(), 0)
    except Exception:
        try:
            return int(float(str(value).strip()))
        except Exception:
            return default

#######################################################
def pawn_to_float(value, default=0.0):
    try:
        return float(str(value).strip())
    except Exception:
        return default

#######################################################
def clean_pawn_model_name(path_value):
    name = os.path.basename(clean_pawn_string(path_value).replace('\\', '/'))
    return os.path.splitext(name)[0]

#######################################################
def parse_pawn_script(filename):
    with open(filename, 'r', encoding='latin-1', errors='ignore') as handle:
        raw_text = handle.read()

    simple_models = {}
    created_objects = []
    lines = strip_pawn_comments(raw_text)
    statement = ""
    statement_comment = ""

    for line, comment in lines:
        if not line.strip() and not statement:
            continue

        statement += line + "\n"
        if comment and not statement_comment:
            statement_comment = comment

        if ';' not in line:
            continue

        pieces = statement.split(';')
        for piece in pieces[:-1]:
            stmt = piece.strip()
            if not stmt:
                continue

            add_match = re.search(r"AddSimpleModel\s*\((.*)\)", stmt, flags=re.IGNORECASE | re.DOTALL)
            if add_match:
                args = split_pawn_args(add_match.group(1))
                if len(args) >= 5:
                    virtual_world = pawn_to_int(args[0], -1)
                    base_id = pawn_to_int(args[1], 19379)
                    model_id = pawn_to_int(args[2], 0)
                    dff_path = clean_pawn_string(args[3])
                    txd_path = clean_pawn_string(args[4])
                    simple_models[model_id] = {
                        'virtual_world': virtual_world,
                        'base_id': base_id,
                        'model_id': model_id,
                        'dff_path': dff_path,
                        'txd_path': txd_path,
                        'model_name': clean_pawn_model_name(dff_path),
                        'txd_name': clean_pawn_model_name(txd_path),
                        'comment': statement_comment,
                    }
                continue

            create_match = re.search(r"(?:[A-Za-z_][A-Za-z0-9_]*\s*=\s*)?(CreateDynamicObject|CreateObject)\s*\((.*)\)", stmt, flags=re.IGNORECASE | re.DOTALL)
            if create_match:
                args = split_pawn_args(create_match.group(2))
                if len(args) >= 7:
                    model_id = pawn_to_int(args[0], 0)
                    created_objects.append({
                        'function': create_match.group(1),
                        'model_id': model_id,
                        'x': pawn_to_float(args[1]),
                        'y': pawn_to_float(args[2]),
                        'z': pawn_to_float(args[3]),
                        'rx': pawn_to_float(args[4]),
                        'ry': pawn_to_float(args[5]),
                        'rz': pawn_to_float(args[6]),
                        'world_id': pawn_to_int(args[7], -1) if len(args) > 7 else -1,
                        'interior_id': pawn_to_int(args[8], -1) if len(args) > 8 else -1,
                        'player_id': pawn_to_int(args[9], -1) if len(args) > 9 else -1,
                        'stream_distance': pawn_to_float(args[10], 300.0) if len(args) > 10 else 300.0,
                        'draw_distance': pawn_to_float(args[11], 300.0) if len(args) > 11 else 300.0,
                        'comment': statement_comment,
                    })

        statement = pieces[-1]
        statement_comment = ""

    return simple_models, created_objects

#######################################################
def ensure_collection(name):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    return collection

#######################################################
def link_object_to_collection(obj, collection):
    if obj.name not in collection.objects:
        collection.objects.link(obj)

    for source_collection in list(obj.users_collection):
        if source_collection != collection:
            try:
                source_collection.objects.unlink(obj)
            except Exception:
                pass

#######################################################
def make_pawn_placeholder_mesh(name):
    mesh = bpy.data.meshes.new(name + '_mesh')
    verts = [
        (-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5),
        (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5),
    ]
    faces = [
        (0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
        (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0),
    ]
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    return obj

#######################################################
def set_pawn_import_props(obj, created, model_info):
    model_id = created['model_id']
    model_name = model_info.get('model_name') if model_info else str(model_id)
    txd_name = model_info.get('txd_name') if model_info else 'default_txd'
    dff_path = model_info.get('dff_path') if model_info else ''
    txd_path = model_info.get('txd_path') if model_info else ''
    base_id = model_info.get('base_id') if model_info else 19379

    obj['Pawn_Model_ID'] = model_id
    obj['Pawn_Function'] = created.get('function', 'CreateDynamicObject')
    obj['Pawn_World_ID'] = created.get('world_id', -1)
    obj['Pawn_Interior_ID'] = created.get('interior_id', -1)
    obj['Pawn_Player_ID'] = created.get('player_id', -1)
    obj['Pawn_Stream_Distance'] = created.get('stream_distance', 300.0)
    obj['Pawn_Draw_Distance'] = created.get('draw_distance', 300.0)
    obj['Pawn_Comment'] = created.get('comment', '')
    obj['Pawn_DFF_Path'] = dff_path
    obj['Pawn_TXD_Path'] = txd_path
    obj['SAMP_ID'] = model_id
    obj['IDE_ID'] = base_id
    obj['DFF_Name'] = model_name
    obj['TXD_Name'] = txd_name

    if hasattr(obj, 'dff'):
        obj.dff.type = 'OBJ'

    if hasattr(obj, 'dff_map'):
        obj.dff_map.object_id = int(base_id) if str(base_id).lstrip('-').isdigit() else 0
        obj.dff_map.model_name = str(model_name)
        obj.dff_map.interior = int(created.get('interior_id', -1)) if str(created.get('interior_id', -1)).lstrip('-').isdigit() else -1
        obj.dff_map.lod = -1
        obj.dff_map.ide_object_id = int(base_id) if str(base_id).lstrip('-').isdigit() else 0
        obj.dff_map.ide_model_name = str(model_name)
        obj.dff_map.ide_txd_name = str(txd_name)
        obj.dff_map.pawn_model_name = str(model_name)
        obj.dff_map.pawn_txd_name = str(txd_name)

#######################################################
class pwn_importer:
    total_objects_num = 0
    total_models_num = 0
    missing_model_info_num = 0

    @staticmethod
    def import_pawn(filename, collection_name='Pawn Import', clear_existing=False):
        simple_models, created_objects = parse_pawn_script(filename)
        collection = ensure_collection(collection_name or 'Pawn Import')

        if clear_existing:
            for obj in list(collection.objects):
                bpy.data.objects.remove(obj, do_unlink=True)

        imported = 0
        missing_model_info = 0

        for index, created in enumerate(created_objects):
            model_info = simple_models.get(created['model_id'])
            if model_info is None:
                missing_model_info += 1

            model_name = model_info.get('model_name') if model_info else str(created['model_id'])
            obj_name = '%s_%03d' % (model_name, index)
            obj = make_pawn_placeholder_mesh(obj_name)
            obj.location = (created['x'], created['y'], created['z'])
            obj.rotation_euler = (
                created['rx'] * 3.141592653589793 / 180.0,
                created['ry'] * 3.141592653589793 / 180.0,
                created['rz'] * 3.141592653589793 / 180.0,
            )
            obj.rotation_mode = 'XYZ'
            link_object_to_collection(obj, collection)
            set_pawn_import_props(obj, created, model_info)
            imported += 1

        pwn_importer.total_objects_num = imported
        pwn_importer.total_models_num = len(simple_models)
        pwn_importer.missing_model_info_num = missing_model_info

        print(
            "DemonFF Pawn import verify: AddSimpleModel=%d, CreateDynamicObject=%d, imported_objects=%d, missing_AddSimpleModel_info=%d." % (
                len(simple_models),
                len(created_objects),
                imported,
                missing_model_info,
            )
        )

        return imported

#######################################################
def import_pawn(options):
    return pwn_importer.import_pawn(
        options['file_name'],
        options.get('collection_name', 'Pawn Import'),
        options.get('clear_existing', False),
    )

#######################################################
class pwn_exporter:
    only_selected = False
    model_directory = ""
    skip_lod = False
    stream_distance = 300.0
    draw_distance = 300.0
    x_offset = 0.0
    y_offset = 0.0
    z_offset = 0.0
    force_all_worlds_interiors = True
    total_objects_num = 0

    @staticmethod
    def collect_objects(context):
        objects = []
        for obj in context.scene.objects:
            if obj.type != 'MESH':
                continue
            if pwn_exporter.only_selected and not obj.select_get():
                continue
            if pwn_exporter.skip_lod and object_is_lod(obj):
                continue
            if object_is_2dfx_pawn_helper(obj):
                continue
            objects.append(obj)
        return objects

    @staticmethod
    def get_or_create_model_id(obj, name_mapping, current_id):
        samp_id = get_object_samp_id(obj)
        if samp_id not in (None, ""):
            try:
                return int(samp_id), current_id
            except Exception:
                return samp_id, current_id

        key = get_pawn_model_name(obj).lower()
        if key not in name_mapping:
            name_mapping[key] = current_id
            current_id -= 1
        return name_mapping[key], current_id

    @staticmethod
    def export_pawn(filename):
        self = pwn_exporter
        objects = self.collect_objects(bpy.context)
        self.total_objects_num = 0

        output_file = filename if filename.lower().endswith('.pwn') else filename + '.pwn'
        artconfig_path = os.path.join(os.path.dirname(output_file), 'artconfig.txt')
        model_directory = self.model_directory.strip().replace('\\', '/')
        base_model_id = 19379
        current_id = -1000
        name_mapping = {}
        written_models = {}
        addsimplemodel_written = 0
        addsimplemodel_skipped = 0
        addsimplemodel_conflicts = 0

        with open(output_file, 'w', encoding='latin-1') as pawn_file, open(artconfig_path, 'w', encoding='latin-1') as artconfig_file:
            pawn_file.write("// Generated by DemonFF\n")
            pawn_file.write("public OnGameModeInit()\n{\n")

            for obj in objects:
                model_id, current_id = self.get_or_create_model_id(obj, name_mapping, current_id)
                source = get_transform_source(obj)
                position = source.location.copy()
                position.x += self.x_offset
                position.y += self.y_offset
                position.z += self.z_offset
                rotation = quat_to_degrees(source.rotation_quaternion)
                world_id, interior = get_stream_world_and_interior(obj, -1, -1)
                model_name = get_pawn_model_name(obj)
                txd_name = get_pawn_txd_name(obj)
                safe_model_dir = model_directory.strip('/')
                dff_path = f"{safe_model_dir}/{model_name}.dff" if safe_model_dir else f"{model_name}.dff"
                txd_path = f"{safe_model_dir}/{txd_name}.txd" if safe_model_dir else f"{txd_name}.txd"

                pawn_file.write(
                    f"    CreateDynamicObject({model_id}, {position.x:.2f}, {position.y:.2f}, {position.z:.2f}, "
                    f"{rotation[0]:.2f}, {rotation[1]:.2f}, {rotation[2]:.2f}, "
                    f"{world_id}, {interior}, -1, {self.stream_distance:.2f}, {self.draw_distance:.2f});  // {obj.name}\n"
                )

                model_key = str(model_id).strip().lower()
                model_paths = (dff_path.lower(), txd_path.lower())
                existing_paths = written_models.get(model_key)

                if existing_paths is None:
                    written_models[model_key] = model_paths
                    artconfig_file.write(
                        f"AddSimpleModel(-1, {base_model_id}, {model_id}, \"{dff_path}\", \"{txd_path}\");  // {model_name}\\n"
                    )
                    addsimplemodel_written += 1
                elif existing_paths == model_paths:
                    addsimplemodel_skipped += 1
                    print(
                        "DemonFF Pawn export: skipped duplicate AddSimpleModel for model ID %s (%s, %s) from %s." % (
                            model_id,
                            dff_path,
                            txd_path,
                            obj.name,
                        )
                    )
                else:
                    addsimplemodel_skipped += 1
                    addsimplemodel_conflicts += 1
                    print(
                        "DemonFF Pawn export warning: skipped conflicting duplicate AddSimpleModel for model ID %s from %s. Already wrote (%s, %s), new request was (%s, %s)." % (
                            model_id,
                            obj.name,
                            existing_paths[0],
                            existing_paths[1],
                            dff_path.lower(),
                            txd_path.lower(),
                        )
                    )

                lod_index = get_object_lod(obj, None)
                if lod_index not in (None, "", -1, "-1"):
                    pawn_file.write(
                        f"    CreateDynamicObject({lod_index}, {position.x:.2f}, {position.y:.2f}, {position.z:.2f}, "
                        f"{rotation[0]:.2f}, {rotation[1]:.2f}, {rotation[2]:.2f}, "
                        f"{world_id}, {interior}, -1, {self.stream_distance:.2f}, {self.draw_distance:.2f});  // LOD for {obj.name}\n"
                    )

                self.total_objects_num += 1

            pawn_file.write("    return 1;\n}\n")

        print(
            "DemonFF Pawn export verify: objects=%d, AddSimpleModel_written=%d, AddSimpleModel_duplicates_skipped=%d, AddSimpleModel_conflicts=%d." % (
                self.total_objects_num,
                addsimplemodel_written,
                addsimplemodel_skipped,
                addsimplemodel_conflicts,
            )
        )

#######################################################
def export_pawn(options):
    pwn_exporter.only_selected = options.get('only_selected', False)
    pwn_exporter.model_directory = options.get('model_directory', '')
    pwn_exporter.skip_lod = options.get('skip_lod', False)
    pwn_exporter.stream_distance = options.get('stream_distance', 300.0)
    pwn_exporter.draw_distance = options.get('draw_distance', 300.0)
    pwn_exporter.x_offset = options.get('x_offset', 0.0)
    pwn_exporter.y_offset = options.get('y_offset', 0.0)
    pwn_exporter.z_offset = options.get('z_offset', 0.0)
    pwn_exporter.force_all_worlds_interiors = options.get('force_all_worlds_interiors', True)
    pwn_exporter.export_pawn(options['file_name'])
