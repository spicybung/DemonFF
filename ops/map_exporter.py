# DemonFF - Blender scripts to edit basic GTA formats to work in conjunction with SAMP/open.mp
# 2023 - 2025 SpicyBung

# This is a fork of DragonFF by Parik - maintained by Psycrow, and various others!
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
from ..data import map_data
from ..ops.importer_common import game_version
from bpy.props import StringProperty, CollectionProperty

def quat_to_degrees(quat):
    euler = quat.to_euler('XYZ')
    return (euler.x * (180 / 3.141592653589793),
            abs(euler.y * (180 / 3.141592653589793)),  # Euler to GTAQuat method
            euler.z * (180 / 3.141592653589793))

IDE_TO_SAMP_DL_IDS = {i: 0 + i for i in range(50000)}

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

    def update_map_sections(self, context):
        return map_data.data[self.game_version_dropdown]['IPL_paths']

    game_version_dropdown: bpy.props.EnumProperty(
        name='Game',
        items=(
            (game_version.III, 'GTA III', 'GTA III map segments'),
            (game_version.VC, 'GTA VC', 'GTA VC map segments'),
            (game_version.SA, 'GTA SA', 'GTA SA map segments'),
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
        default='C:\\Program Files (x86)\\Steam\\steamapps\\common\\',
        description="Folder with the game's executable",
        subtype='DIR_PATH'
    )

    dff_folder: bpy.props.StringProperty(
        name='Dff folder',
        default='C:\\Users\\blaha\\Documents\\GitHub\\DragonFF\\tests\\dff',
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
                obj["SAMP_ID"] = samp_id
                obj["TXD_Name"] = txd_name
                print(f"Assigned SAMP ID {samp_id} and TXD {txd_name} to {obj.name}")
            else:
                print(f"No matching SAMP ID found for {obj.name}")

    print("SAMP IDE import completed for all files")

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

class Mass_IDE_Import_Operator(bpy.types.Operator):
    """Import .IDE Files"""
    bl_idname = "object.samp_mass_ide_import"
    bl_label = "Import .IDE Files"
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

class ExportToIPLOperator(bpy.types.Operator):
    bl_idname = "object.export_to_ipl"
    bl_label = "Export Selected Objects to IPL"
    filename_ext = ".ipl"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        def export_to_ipl(file_path, objects):
            with open(file_path, 'w') as f:
                f.write("inst\n")

                for obj in objects:
                    if context.scene.dff.skip_lod and (obj.name.startswith("LOD") or ".ColMesh" in obj.name):
                        continue

                    # Determine if the mesh is parented to an empty - export the XYZ of the empty for proper coords
                    parent = obj.parent
                    if parent and parent.type == 'EMPTY':
                        position = parent.location
                        rotation = quat_to_degrees(parent.rotation_quaternion)
                    else:
                        position = obj.location
                        rotation = quat_to_degrees(obj.rotation_quaternion)

                    # Use IDE_ID from the object
                    object_id = obj.get("IDE_ID", 0)  # Use stored IDE_ID if present

                    interior = obj.get('Interior', 0)
                    lod_index = obj.get('LODIndex', -1)

                    base_name = obj.name.split('.')[0]

                    line = f"{object_id}, {base_name}, {interior}, {position.x:.2f}, {position.y:.2f}, {position.z:.2f}, " \
                           f"{rotation[0]:.2f}, {rotation[1]:.2f}, {rotation[2]:.2f}, {lod_index}  # {obj.name}\n"
                    f.write(line)
                    print(f"Exporting {obj.name} with IDE ID {object_id}")

                f.write("end\n")
                print(f"Exported IPL to {file_path}")

        selected_objects = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
        if not selected_objects:
            self.report({'INFO'}, "No mesh objects selected. Export cancelled.")
            return {'CANCELLED'}

        output_file = self.filepath if self.filepath.endswith('.ipl') else self.filepath + '.ipl'

        export_to_ipl(output_file, selected_objects)

        self.report({'INFO'}, f"Exported {len(selected_objects)} objects to {output_file}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class ExportToIDEOperator(bpy.types.Operator):
    bl_idname = "object.export_to_ide"
    bl_label = "Export Scene Objects to IDE"
    filename_ext = ".ide"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        def export_to_ide(file_path, objects):
            name_mapping = {}
            with open(file_path, 'w') as f:
                f.write("objs\n")

                for obj in objects:
                    if context.scene.dff.skip_lod and (obj.name.startswith("LOD") or ".ColMesh" in obj.name):
                        continue

                    object_id = obj.get('IDE_ID', 0)  # Default to 0 if IDE_ID is not set
                    base_name = obj.name.split('.')[0]
                    txd_name = obj.get('TXD_Name', 'default_txd')  # Ensure TXD name is set
                    if base_name not in name_mapping:
                        name_mapping[base_name] = obj.name

                    line = f"{object_id}, {name_mapping[base_name]}, {txd_name}, 1, {obj.get('DrawDistance', 300.0)}, 0  # {obj.name}\n"
                    f.write(line)
                    print(f"Exporting {obj.name} with ID {object_id} and TXD {txd_name}")

                f.write("end\n")
                print(f"Exported IDE to {file_path}")

        scene_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
        if not scene_objects:
            self.report({'INFO'}, "No mesh objects in scene. Export cancelled.")
            return {'CANCELLED'}

        output_file = self.filepath if self.filepath.endswith('.ide') else self.filepath + '.ide'

        export_to_ide(output_file, scene_objects)

        self.report({'INFO'}, f"Exported {len(scene_objects)} objects to {output_file}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class ExportToPawnOperator(bpy.types.Operator):
    bl_idname = "object.export_to_pawn"
    bl_label = "Export Selected Objects to Pawn Script"
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

    def execute(self, context):
        def export_to_pawn(file_path, objects):
            artconfig_path = os.path.join(os.path.dirname(file_path), 'artconfig.txt')
            baseid = 19379
            model_directory = self.model_directory.strip()
            with open(file_path, 'w') as f, open(artconfig_path, 'w') as artconfig:
                current_id = -1000  # Starting ID
                max_id = -40000  # Maximum ID

                name_mapping = {}
                for obj in objects:
                    if self.skip_lod and (obj.name.startswith("LOD") or ".ColMesh" in obj.name):
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

                    base_name = obj.name.split('.')[0]

                    if base_name not in name_mapping:
                        name_mapping[base_name] = current_id
                        current_id -= 1  # Decrement for unique IDs
                    object_id = name_mapping[base_name]

                    interior = obj.get('Interior', -1)
                    stream_distance = self.stream_distance
                    draw_distance = self.draw_distance

                    dff_name = obj.get('DFF_Name', base_name)  # Default to object name without suffix
                    txd_name = obj.get('TXD_Name', 'default_txd')  # Ensure TXD name is set

                    line = f"CreateDynamicObject({object_id}, {position.x:.2f}, {position.y:.2f}, {position.z:.2f}, " \
                           f"{rotation[0]:.2f}, {rotation[1]:.2f}, {rotation[2]:.2f}, {interior}, 0, -1, {stream_distance:.2f}, {draw_distance:.2f});  // {obj.name}\n"
                    f.write(line)
                    print(f"Exporting {obj.name} with ID {object_id}")

                    artconfig_line = f"AddSimpleModel(-1, {baseid}, {object_id}, \"{model_directory}/{dff_name}.dff\", \"{model_directory}/{txd_name}.txd\");  // {obj.name}\n"
                    artconfig.write(artconfig_line)
                    print(f"Writing to artconfig: {artconfig_line.strip()}")

                    if 'LODIndex' in obj:
                        lod_index = obj['LODIndex']
                        lod_line = f"CreateDynamicObject({lod_index}, {position.x:.2f}, {position.y:.2f}, {position.z:.2f}, " \
                                   f"{rotation[0]:.2f}, {rotation[1]:.2f}, {rotation[2]:.2f}, {interior}, 0, -1, {stream_distance:.2f}, {draw_distance:.2f});  // LOD for {obj.name}\n"
                        f.write(lod_line)
                        print(f"Exporting LOD for {obj.name} with LODIndex {lod_index}")

                print(f"Exported Pawn script to {file_path}")
                print(f"Exported artconfig to {artconfig_path}")

        selected_objects = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
        if not selected_objects:
            self.report({'INFO'}, "No mesh objects selected. Export cancelled.")
            return {'CANCELLED'}

        output_file = self.filepath if self.filepath.endswith('.pwn') else self.filepath + '.pwn'

        export_to_pawn(output_file, selected_objects)

        self.report({'INFO'}, f"Exported {len(selected_objects)} objects to {output_file}")
        self.report({'INFO'}, f"Exported artconfig.txt to {os.path.dirname(output_file)}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "model_directory")
        layout.prop(self, "skip_lod")
        layout.prop(self, "stream_distance")
        layout.prop(self, "draw_distance")
        layout.prop(self, "x_offset")
        layout.prop(self, "y_offset")

class RemoveBuildingForPlayerOperator(bpy.types.Operator):
    bl_idname = "object.remove_building_for_player"
    bl_label = "Remove Building For Player"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            obj_id = obj.get("IDE_ID", -1)
            position = obj.location
            radius = 200.0  # Default radius, can be adjusted
            line = f"RemoveBuildingForPlayer(playerid, {obj_id}, {position.x:.2f}, {position.y:.2f}, {position.z:.2f}, {radius:.2f});"
            print(line)
        return {'FINISHED'}
    
class MapImportPanel(bpy.types.Panel):
    """Creates a Panel in the scene context of the properties editor"""
    bl_label = "DemonFF - Map Import"
    bl_idname = "SCENE_PT_map_import"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

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

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("object.export_to_ipl", text="Export IPL")
        row.operator("object.export_to_ide", text="Export IDE")
        row.operator("object.samp_mass_ide_import", text="Import IDE")

class DemonFFPawnPanel(bpy.types.Panel):
    bl_label = "DemonFF - Pawn"
    bl_idname = "SCENE_PT_demonff_pawn"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("object.export_to_pawn", text="Export .pwn")
        row.operator("object.remove_building_for_player", text="Remove Building For Player")

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
    bpy.utils.register_class(DemonFFPawnPanel)
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
    bpy.utils.unregister_class(DemonFFPawnPanel)
    DFFSceneProps.unregister()

if __name__ == "__main__":
    register()
