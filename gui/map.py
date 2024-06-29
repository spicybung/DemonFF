import bpy
import os
from mathutils import Quaternion, Euler
from ..data import map_data  # Ensure this is the correct import path
from ..ops.importer_common import game_version  # Ensure this is the correct import path

# Function to convert quaternion to rotation in degrees using Blender's mathutils
def quat_to_degrees(quat):
    euler = quat.to_euler('XYZ')
    return euler.x * (180 / 3.141592653589793), euler.y * (180 / 3.141592653589793), euler.z * (180 / 3.141592653589793)

# Function to convert Euler to rotation in degrees using three.js convention
def euler_to_degrees(euler):
    return euler.x * (180 / 3.141592653589793), euler.y * (180 / 3.141592653589793), euler.z * (180 / 3.141592653589793)

# Example mapping from IDE IDs to SAMP 0.3DL object IDs (to be extended as needed)
IDE_TO_SAMP_DL_IDS = {i: -(1000 + i) for i in range(29000)}

#######################################################
class DFFSceneProps(bpy.types.PropertyGroup):
    def update_map_sections(self, context):
        return map_data.data[self.game_version_dropdown]['IPL_paths']

    game_version_dropdown : bpy.props.EnumProperty(
        name = 'Game',
        items = (
            (game_version.III, 'GTA III', 'GTA III map segments'),
            (game_version.VC, 'GTA VC', 'GTA VC map segments'),
            (game_version.SA, 'GTA SA', 'GTA SA map segments'),
            (game_version.LCS, 'GTA LCS', 'GTA LCS map segments'),
            (game_version.VCS, 'GTA VCS', 'GTA VCS map segments'),
        )
    )

    map_sections : bpy.props.EnumProperty(
        name = 'Map segment',
        items = update_map_sections
    )

    skip_lod: bpy.props.BoolProperty(
        name        = "Skip LOD Objects",
        default     = False
    )

    game_root : bpy.props.StringProperty(
        name = 'Game root',
        default = 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\',
        description = "Folder with the game's executable",
        subtype = 'DIR_PATH'
    )

    dff_folder : bpy.props.StringProperty(
        name = 'Dff folder',
        default = 'C:\\Users\\blaha\\Documents\\GitHub\\DragonFF\\tests\\dff',
        description = "Define a folder where all of the dff models are stored.",
        subtype = 'DIR_PATH'
    )

    # Add the stream_distance, draw_distance, x_offset, and y_offset properties
    stream_distance: bpy.props.FloatProperty(
        name = "Stream Distance",
        default = 300.0,
        description = "Stream distance for dynamic objects"
    )

    draw_distance: bpy.props.FloatProperty(
        name = "Draw Distance",
        default = 300.0,
        description = "Draw distance for objects"
    )

    x_offset: bpy.props.FloatProperty(
        name = "X Offset",
        default = 0.0,
        description = "Offset for the x coordinate of the objects"
    )

    y_offset: bpy.props.FloatProperty(
        name = "Y Offset",
        default = 0.0,
        description = "Offset for the y coordinate of the objects"
    )

    @classmethod
    def register(cls):
        bpy.types.Scene.dff = bpy.props.PointerProperty(type=cls)

    @classmethod
    def unregister(cls):
        del bpy.types.Scene.dff

# Function to import IDE file and assign IDs and TXD names to similar named objects
def import_ide(filepath, context):
    if not os.path.isfile(filepath):
        print("File not found")
        return

    with open(filepath, 'r') as file:
        lines = file.readlines()

    obj_data = {}
    in_obj_section = False

    for line in lines:
        line = line.strip()
        if line.lower().startswith("objs"):
            in_obj_section = True
            continue
        elif line.lower().startswith("end"):
            in_obj_section = False
        else:
            if in_obj_section and line and not line.startswith("#"):
                parts = line.split(",")
                if len(parts) > 3:
                    obj_id = int(parts[0].strip())
                    obj_name = parts[1].strip()
                    txd_name = parts[2].strip()
                    obj_data[obj_name] = (obj_id, txd_name)

    for obj in context.scene.objects:
        base_name = obj.name.split('.')[0]
        if base_name in obj_data:
            obj["IDE_ID"] = obj_data[base_name][0]
            obj["TXD_Name"] = obj_data[base_name][1]
            print(f"Assigned ID {obj_data[base_name][0]} and TXD {obj_data[base_name][1]} to {obj.name}")
        else:
            print(f"No matching ID found for {obj.name}")

    print("IDE import completed")

class IDE_Import_Operator(bpy.types.Operator):
    """Import .IDE File"""
    bl_idname = "object.ide_import"
    bl_label = "Import .IDE File"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH", default="", options={'HIDDEN'}, maxlen=1024)
    filter_glob: bpy.props.StringProperty(default="*.ide", options={'HIDDEN'})

    def execute(self, context):
        import_ide(self.filepath, context)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

def menu_func_import(self, context):
    self.layout.operator(IDE_Import_Operator.bl_idname, text="Import .IDE File")

#######################################################
class ExportToIPLOperator(bpy.types.Operator):
    bl_idname = "object.export_to_ipl"
    bl_label = "Export Selected Objects to IPL"
    filename_ext = ".ipl"
    
    # Properties
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    
    def execute(self, context):
        def export_to_ipl(file_path, objects):
            name_mapping = {}
            with open(file_path, 'w') as f:
                f.write("inst\n")
                
                for obj in objects:
                    position = obj.location
                    rotation = euler_to_degrees(obj.rotation_euler)  # Convert Euler to rotation in degrees using three.js convention
                    object_id = obj.get('IDE_ID', 0)  # Default to 0 if IDE_ID is not set
                    object_id = int(object_id)  # Ensure object_id is an integer
                    if object_id in IDE_TO_SAMP_DL_IDS:
                        object_id = IDE_TO_SAMP_DL_IDS[object_id]  # Convert to SAMP 0.3DL object ID
                    else:
                        object_id = -object_id  # Ensure ID is negative
                    interior = obj.get('Interior', 0)
                    lod_index = obj.get('LODIndex', -1)

                    # Ensure the object name does not include the numeric suffix
                    base_name = obj.name.split('.')[0]
                    if base_name not in name_mapping:
                        name_mapping[base_name] = obj.name

                    line = f"{object_id}, {name_mapping[base_name]}, {interior}, {position.x:.6f}, {position.y:.6f}, {position.z:.6f}, " \
                           f"{rotation[0]:.6f}, {rotation[1]:.6f}, {rotation[2]:.6f}, {lod_index}  # {obj.name}\n"
                    f.write(line)
                    print(f"Exporting {obj.name} with ID {object_id}")

                f.write("end\n")
                print(f"Exported IPL to {file_path}")
        
        # Select objects for export
        selected_objects = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
        if not selected_objects:
            self.report({'INFO'}, "No mesh objects selected. Export cancelled.")
            return {'CANCELLED'}
        
        # Ensure file path has the correct extension
        output_file = self.filepath if self.filepath.endswith('.ipl') else self.filepath + '.ipl'
        
        # Export selected objects to IPL format
        export_to_ipl(output_file, selected_objects)
        
        self.report({'INFO'}, f"Exported {len(selected_objects)} objects to {output_file}")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

#######################################################
class ExportToIDEOperator(bpy.types.Operator):
    bl_idname = "object.export_to_ide"
    bl_label = "Export Scene Objects to IDE"
    filename_ext = ".ide"
    
    # Properties
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    
    def execute(self, context):
        def export_to_ide(file_path, objects):
            name_mapping = {}
            with open(file_path, 'w') as f:
                f.write("objs\n")
                
                for obj in objects:
                    object_id = obj.get('IDE_ID', 0)  # Default to 0 if IDE_ID is not set
                    object_id = int(object_id)  # Ensure object_id is an integer
                    base_name = obj.name.split('.')[0]
                    txd_name = obj.get('TXD_Name', 'default_txd')  # Ensure TXD name is set
                    if base_name not in name_mapping:
                        name_mapping[base_name] = obj.name

                    line = f"{object_id}, {name_mapping[base_name]}, {txd_name}, 1, {obj.get('DrawDistance', 300.0)}, 0  # {obj.name}\n"
                    f.write(line)
                    print(f"Exporting {obj.name} with ID {object_id} and TXD {txd_name}")

                f.write("end\n")
                print(f"Exported IDE to {file_path}")
        
        # Select objects for export
        scene_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
        if not scene_objects:
            self.report({'INFO'}, "No mesh objects in scene. Export cancelled.")
            return {'CANCELLED'}
        
        # Ensure file path has the correct extension
        output_file = self.filepath if self.filepath.endswith('.ide') else self.filepath + '.ide'
        
        # Export scene objects to IDE format
        export_to_ide(output_file, scene_objects)
        
        self.report({'INFO'}, f"Exported {len(scene_objects)} objects to {output_file}")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

#######################################################
class ExportToPawnOperator(bpy.types.Operator):
    bl_idname = "object.export_to_pawn"
    bl_label = "Export Selected Objects to Pawn Script"
    filename_ext = ".pwn"
    
    # Properties
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
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
            with open(file_path, 'w') as f, open(artconfig_path, 'w') as artconfig:
                current_id = -1000  # Starting ID
                max_id = -30000  # Maximum ID

                name_mapping = {}
                for obj in objects:
                    # Skip objects with ".ColMesh" suffix
                    if obj.name.endswith(".ColMesh"):
                        continue

                    if current_id <= max_id:
                        self.report({'ERROR'}, "Maximum ID limit reached. Export cancelled.")
                        break

                    position = obj.location
                    position.x += self.x_offset
                    position.y += self.y_offset
                    rotation = euler_to_degrees(obj.rotation_euler)  # Convert Euler to rotation in degrees using three.js convention
                    base_name = obj.name.split('.')[0]

                    if base_name not in name_mapping:
                        name_mapping[base_name] = current_id
                        current_id -= 1
                    object_id = name_mapping[base_name]

                    interior = obj.get('Interior', -1)
                    stream_distance = self.stream_distance
                    draw_distance = self.draw_distance

                    dff_name = obj.get('DFF_Name', base_name)  # Default to object name without suffix
                    txd_name = obj.get('TXD_Name', 'default_txd')  # Ensure TXD name is set

                    quat = obj.rotation_quaternion
                    quat_w = quat.w

                    # Formatting the CreateDynamicObject line with explicit "-" for IDs
                    line = f"CreateDynamicObject({object_id}, {position.x:.6f}, {position.y:.6f}, {position.z:.6f}, " \
                           f"{rotation[0]:.6f}, {rotation[1]:.6f}, {rotation[2]:.6f}, {quat_w:.6f}, {interior}, 0, -1, {stream_distance:.2f}, {draw_distance:.2f});  // {obj.name}\n"
                    f.write(line)
                    print(f"Exporting {obj.name} with ID {object_id}")

                    # Write to artconfig.txt
                    artconfig_line = f"AddSimpleModel(-1, {object_id}, \"{dff_name}.dff\", \"{txd_name}.txd\");  // {obj.name}\n"
                    artconfig.write(artconfig_line)
                    print(f"Writing to artconfig: {artconfig_line.strip()}")

                print(f"Exported Pawn script to {file_path}")
                print(f"Exported artconfig to {artconfig_path}")

        # Select objects for export
        selected_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
        if not selected_objects:
            self.report({'INFO'}, "No mesh objects selected. Export cancelled.")
            return {'CANCELLED'}
        
        # Ensure file path has the correct extension
        output_file = self.filepath if self.filepath.endswith('.pwn') else self.filepath + '.pwn'
        
        # Export selected objects to Pawn script
        export_to_pawn(output_file, selected_objects)
        
        self.report({'INFO'}, f"Exported {len(selected_objects)} objects to {output_file}")
        self.report({'INFO'}, f"Exported artconfig.txt to {os.path.dirname(output_file)}")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "stream_distance")
        layout.prop(self, "draw_distance")
        layout.prop(self, "x_offset")
        layout.prop(self, "y_offset")

#######################################################
class ExportArtConfigOperator(bpy.types.Operator):
    bl_idname = "object.export_artconfig"
    bl_label = "Export ArtConfig"
    filename_ext = ".txt"
    
    # Properties
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    
    def execute(self, context):
        def export_artconfig(file_path, objects):
            with open(file_path, 'w') as artconfig:
                current_id = -1000  # Starting ID
                max_id = -30000  # Maximum ID
                name_mapping = {}

                for obj in objects:
                    if current_id <= max_id:
                        self.report({'ERROR'}, "Maximum ID limit reached. Export cancelled.")
                        break

                    base_name = obj.name.split('.')[0]

                    if base_name not in name_mapping:
                        name_mapping[base_name] = current_id
                        current_id -= 1
                    object_id = name_mapping[base_name]

                    dff_name = obj.get('DFF_Name', base_name)  # Default to object name without suffix
                    txd_name = obj.get('TXD_Name', 'default_txd')  # Ensure TXD name is set

                    # Write to artconfig.txt
                    artconfig_line = f"AddSimpleModel(-1, {object_id}, \"{dff_name}.dff\", \"{txd_name}.txd\");  // {obj.name}\n"
                    artconfig.write(artconfig_line)
                    print(f"Writing to artconfig: {artconfig_line.strip()}")

                print(f"Exported artconfig to {file_path}")

        # Select objects for export
        scene_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
        if not scene_objects:
            self.report({'INFO'}, "No mesh objects in scene. Export cancelled.")
            return {'CANCELLED'}
        
        # Ensure file path has the correct extension
        output_file = self.filepath if self.filepath.endswith('.txt') else self.filepath + '.txt'
        
        # Export selected objects to artconfig
        export_artconfig(output_file, scene_objects)
        
        self.report({'INFO'}, f"Exported artconfig.txt to {output_file}")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

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

        flow = layout.grid_flow(row_major=True,
                                columns=0,
                                even_columns=True,
                                even_rows=False,
                                align=True)

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
class MapExportPanel(bpy.types.Panel):
    """Creates a Panel in the scene context of the properties editor"""
    bl_label = "DemonFF - Map Export(Experimental)"
    bl_idname = "SCENE_PT_map_export"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("object.export_to_ipl", text="Export to IPL")
        row.operator("object.export_to_ide", text="Export to IDE")
        row.operator("object.ide_import", text="Import IDE")

#######################################################
class DemonFFPawnPanel(bpy.types.Panel):
    """Creates a Panel in the scene context of the properties editor"""
    bl_label = "DemonFF - Pawn SAMP"
    bl_idname = "SCENE_PT_demonff_pawn"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("object.export_to_pawn", text="Export .pwn")
        row.operator("object.export_artconfig", text="Export artconfig")

def register():
    bpy.utils.register_class(DFFSceneProps)
    bpy.utils.register_class(IDE_Import_Operator)
    bpy.utils.register_class(ExportToIPLOperator)
    bpy.utils.register_class(ExportToIDEOperator)
    bpy.utils.register_class(ExportToPawnOperator)
    bpy.utils.register_class(ExportArtConfigOperator)
    bpy.utils.register_class(MapImportPanel)
    bpy.utils.register_class(MapExportPanel)
    bpy.utils.register_class(DemonFFPawnPanel)
    DFFSceneProps.register()
    bpy.types.VIEW3D_MT_object.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(DFFSceneProps)
    bpy.utils.unregister_class(IDE_Import_Operator)
    bpy.utils.unregister_class(ExportToIPLOperator)
    bpy.utils.unregister_class(ExportToIDEOperator)
    bpy.utils.unregister_class(ExportToPawnOperator)
    bpy.utils.unregister_class(ExportArtConfigOperator)
    bpy.utils.unregister_class(MapImportPanel)
    bpy.utils.unregister_class(MapExportPanel)
    bpy.utils.unregister_class(DemonFFPawnPanel)
    DFFSceneProps.unregister()
    bpy.types.VIEW3D_MT_object.remove(menu_func_import)

if __name__ == "__main__":
    register()
