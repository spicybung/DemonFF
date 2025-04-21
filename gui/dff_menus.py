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
import bmesh
import gpu
import struct
from .dff_ot import EXPORT_OT_dff_custom, IMPORT_OT_dff_custom, \
    IMPORT_OT_txd, \
    OBJECT_OT_dff_generate_bone_props, \
    OBJECT_OT_dff_set_parent_bone, OBJECT_OT_dff_clear_parent_bone
from .dff_ot import SCENE_OT_dff_frame_move, SCENE_OT_dff_atomic_move, SCENE_OT_dff_update
from .col_ot import EXPORT_OT_col
from .ifp_ot import IMPORT_OT_ifp

from .ext_2dfx_menus import EXT2DFXObjectProps, EXT2DFXMenus

# Global variables
fx_images = ["coronastar", "shad_exp"]
fx_psystems = ["prt_blood", "prt_boatsplash"]
effectfile = ""
textfile = ""

#######################################################
class OBJECT_PT_dff_misc_panel(bpy.types.Panel):
    bl_label = "DemonFF - Miscellaneous"
    bl_idname = "OBJECT_PT_dff_misc"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'

    def draw(self, context):
        layout = self.layout
        layout.label(text="Mesh Operations:")
        layout.operator("object.join_similar_named_meshes", text="Join Similar Named Meshes")
        layout.operator("scene.duplicate_all_as_objects", text="Duplicate All as Objects")
        layout.operator("object.optimize_mesh", text="Optimize Mesh(SLOW)")

        layout.label(text="Normals Operations:")
        layout.operator("object.force_doubleside_mesh", text="Force Doubleside Mesh")
        layout.operator("object.recalculate_normals_outward", text="Recalculate Normals (Outward)")
        layout.operator("object.recalculate_normals_inward", text="Recalculate Normals (Inward)")

        layout.label(text="Collision Operations:")
        layout.operator("object.set_collision_objects", text="Set All As Collision Objects")
        layout.operator("scene.duplicate_all_as_collision", text="Duplicate All as Collision")
        
        layout.label(text="Frame Operations:")
        layout.operator("object.remove_frames", text="Remove Frames")
        layout.operator("object.truncate_frame_names", text="Truncate Frame Names")
#######################################################
class Light2DFXObjectProps(bpy.types.PropertyGroup):

    alpha : bpy.props.FloatProperty(
        min = 0,
        max = 1
    )

    corona_far_clip : bpy.props.FloatProperty(
        description = "Corona visibility distance"
    )

    point_light_range : bpy.props.FloatProperty(
        description = "Point light source radius"
    )

    export_view_vector : bpy.props.BoolProperty()

    view_vector : bpy.props.IntVectorProperty(
        min = -128,
        max = 127
    )

    corona_size : bpy.props.FloatProperty()

    shadow_size : bpy.props.FloatProperty()

    corona_show_mode : bpy.props.EnumProperty(
        items = (
            ('0', 'DEFAULT', ''),
            ('1', 'RANDOM_FLASHING', ''),
            ('2', 'RANDOM_FLASHIN_ALWAYS_AT_WET_WEATHER', ''),
            ('3', 'LIGHTS_ANIM_SPEED_4X', ''),
            ('4', 'LIGHTS_ANIM_SPEED_2X', ''),
            ('5', 'LIGHTS_ANIM_SPEED_1X', ''),
            ('6', 'WARNLIGHT', ''),
            ('7', 'TRAFFICLIGHT', ''),
            ('8', 'TRAINCROSSLIGHT', ''),
            ('9', 'DISABLED', ''),
            ('10', 'AT_RAIN_ONLY', 'Enables only in rainy weather'),
            ('11', '5S_ON_5S_OFF', '5s - on, 5s - off'),
            ('12', '6S_ON_4S_OFF', '6s - on, 4s - off'),
            ('13', '6S_ON_4S_OFF_2', '6s - on, 4s - off'),
        )
    )

    corona_flare_type : bpy.props.IntProperty(
        min = 0,
        max = 2,
        description = "Type of highlights for the corona"
    )

    shadow_color_multiplier : bpy.props.IntProperty(
        min = 0,
        max = 255,
        description = "Shadow intensity"
    )

    corona_enable_reflection : bpy.props.BoolProperty(
        description = "Enable corona reflection on wet asphalt"
    )

    shadow_z_distance : bpy.props.IntProperty(
        min = 0,
        max = 255,
        description = "Maximum distance for drawing shadow"
    )

    flag1_corona_check_obstacles : bpy.props.BoolProperty(
        description = "If there are any objects between the corona and the camera, the corona will not be rendered"
    )

    flag1_fog_type : bpy.props.IntProperty(
        min = 0,
        max = 3,
        description = "Fog type for point light source"
    )

    flag1_without_corona : bpy.props.BoolProperty()

    flag1_corona_only_at_long_distance : bpy.props.BoolProperty()

    flag1_at_day : bpy.props.BoolProperty()

    flag1_at_night : bpy.props.BoolProperty()

    flag1_blinking1 : bpy.props.BoolProperty(
        description = "Blinks (almost imperceptibly)"
    )

    flag2_corona_only_from_below : bpy.props.BoolProperty(
        description = "The corona is visible only from below (when the height of the camera position is less than the height of the light source)"
    )

    flag2_blinking2 : bpy.props.BoolProperty(
        description = "Blinks (very fast)"
    )

    flag2_udpdate_height_above_ground : bpy.props.BoolProperty()

    flag2_check_view_vector : bpy.props.BoolProperty(
        description = "Works only if the camera is in a certain position (View Vector)"
    )

    flag2_blinking3 : bpy.props.BoolProperty(
        description = "Blinks (randomly)"
    )

    # Missing corona_tex_name property
    corona_tex_name: bpy.props.StringProperty(
        name="Corona Texture Name",
        description="Name of the texture used for the light's corona effect",
        default=""
    )

        # Add the missing property
    shadow_tex_name: bpy.props.StringProperty(
        name="Shadow Texture Name",
        description="Name of the texture used for the light's shadow effect",
        default=""
    )

    #######################################################
    def register():
        bpy.types.Light.ext_2dfx = bpy.props.PointerProperty(type=Light2DFXObjectProps)
#######################################################
class Escalator2DFXObjectProps(bpy.types.PropertyGroup):
    # Vector Positions (combined XYZ)
    standart_pos: bpy.props.FloatVectorProperty(name="Standart Position", size=3)
    bottom_pos: bpy.props.FloatVectorProperty(name="Bottom", size=3)
    top_pos: bpy.props.FloatVectorProperty(name="Top", size=3)
    end_pos: bpy.props.FloatVectorProperty(name="End", size=3)

    # Direction
    direction: bpy.props.EnumProperty(
        name="Direction",
        items=[('0', 'Down', ''), ('1', 'Up', '')],
        default='1'
    )

    # Standard Position Vectors
    standart_pos_rotation: bpy.props.FloatProperty(name="Standard Pos Rotation")
    standart_pos_pitch: bpy.props.FloatProperty(name="Standard Pos Pitch")
    standart_pos_yaw: bpy.props.FloatProperty(name="Standard Pos Yaw")

    # Bottom Position
    bottom_rotation: bpy.props.FloatProperty(name="Bottom Rotation")
    bottom_pitch: bpy.props.FloatProperty(name="Bottom Pitch")
    bottom_yaw: bpy.props.FloatProperty(name="Bottom Yaw")

    # Top Position
    top_rotation: bpy.props.FloatProperty(name="Top Rotation")
    top_pitch: bpy.props.FloatProperty(name="Top Pitch")
    top_yaw: bpy.props.FloatProperty(name="Top Yaw")

    # End Position
    end_rotation: bpy.props.FloatProperty(name="End Rotation")
    end_pitch: bpy.props.FloatProperty(name="End Pitch")
    end_yaw: bpy.props.FloatProperty(name="End Yaw")
        
#######################################################
def join_similar_named_meshes(context):
    import bpy

    # Build dictionary of base names to list of mesh objects
    base_name_dict = {}

    for obj in context.scene.objects:
        if obj.type == 'MESH':
            base_name = obj.name.split('.')[0]
            base_name_dict.setdefault(base_name, []).append(obj)

    for base_name, objects in base_name_dict.items():
        if len(objects) <= 1:
            continue

        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        target = objects[0]

        others = [obj for obj in objects[1:] if obj != target]

        for obj in others:
            if obj.name not in target.users_collection[0].objects:
                target.users_collection[0].objects.link(obj)

        for obj in context.selected_objects:
            obj.select_set(False)
        target.select_set(True)
        for obj in others:
            obj.select_set(True)

        context.view_layer.objects.active = target
        bpy.ops.object.join()

#######################################################
class OBJECT_OT_join_similar_named_meshes(bpy.types.Operator):
    bl_idname = "object.join_similar_named_meshes"
    bl_label = "Join Similar Named Meshes"
    bl_description = "Join meshes with similar names"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        join_similar_named_meshes(context)
        return {'FINISHED'}
#######################################################
class OBJECT_PT_join_similar_meshes_panel(bpy.types.Panel):
    bl_label = "Join Similar Meshes"
    bl_idname = "OBJECT_PT_join_similar_meshes"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("object.join_similar_named_meshes", text="Join Similar Meshes")
#######################################################
class OBJECT_OT_optimize_mesh(bpy.types.Operator):
    bl_idname = "object.optimize_mesh"
    bl_label = "Optimize Mesh(Slow)"
    bl_description = "Fix and/or optimize broken mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import bmesh
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')

                bm = bmesh.from_edit_mesh(obj.data)
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
                bmesh.update_edit_mesh(obj.data, loop_triangles=True)

                bpy.ops.mesh.remove_doubles(threshold=0.0001)
                bpy.ops.mesh.delete_loose()
                bpy.ops.mesh.normals_make_consistent(inside=False)
                bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, "Optimized selected meshes")
        return {'FINISHED'}
#######################################################   
class SCENE_OT_duplicate_all_as_objects(bpy.types.Operator):
    bl_idname = "scene.duplicate_all_as_objects"
    bl_label = "Duplicate All as Objects"
    bl_description = "Duplicate all mesh objects into new '.dff' collections and select only the duplicates"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        root_collection = context.scene.collection
        duplicated_objects = []
        collection_pairs = []

        used_names = {obj.name for obj in bpy.data.objects}

        for obj in context.scene.objects:
            if obj.type != 'MESH' or not obj.users_collection:
                continue

            # Generate a unique name like bonerific.001 manually
            base = obj.name
            count = 1
            new_name = f"{base}.{str(count).zfill(3)}"
            while new_name in used_names:
                count += 1
                new_name = f"{base}.{str(count).zfill(3)}"
            used_names.add(new_name)

            duplicate = bpy.data.objects.new(obj.name, obj.data.copy())
            duplicate.name = new_name

            dff_collection_name = f"{base}.dff"
            dff_collection = bpy.data.collections.new(dff_collection_name)
            root_collection.children.link(dff_collection)
            dff_collection.objects.link(duplicate)

            if hasattr(duplicate, "dff"):
                duplicate.dff.type = 'OBJ'

            duplicate.select_set(True)
            duplicated_objects.append(duplicate)

            original_collection = obj.users_collection[0]
            collection_pairs.append((dff_collection, original_collection))

        for dff_collection, original_collection in collection_pairs:
            if original_collection.name in root_collection.children:
                root_collection.children.unlink(bpy.data.collections[original_collection.name])
            if dff_collection.name in root_collection.children:
                root_collection.children.unlink(bpy.data.collections[dff_collection.name])
            root_collection.children.link(bpy.data.collections[dff_collection.name])
            root_collection.children.link(bpy.data.collections[original_collection.name])

        if duplicated_objects:
            context.view_layer.objects.active = duplicated_objects[-1]

        self.report({'INFO'}, f"Duplicated {len(duplicated_objects)} mesh objects into '.dff' collections.")
        return {'FINISHED'}

#######################################################   
class OBJECT_OT_force_doubleside_mesh(bpy.types.Operator):
    """Extrudes faces along their normals for all selected objects by 0.001523M"""
    bl_idname = "object.force_doubleside_mesh"
    bl_label = "Force Doubleside Mesh"
    bl_description = "Extrude faces along normals for all selected objects by 0.001523M"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type == 'MESH':

                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.mode_set(mode='EDIT')

                # Create a BMesh object from the mesh data
                bm = bmesh.from_edit_mesh(obj.data)

                # Extrude the faces
                extrude_result = bmesh.ops.extrude_face_region(bm, geom=bm.faces)

                # Collect new vertices created by the extrusion
                new_verts = [v for v in extrude_result['geom'] if isinstance(v, bmesh.types.BMVert)]

                
                for face in bm.faces:
                    normal = face.normal  # Get face normal
                    for vert in new_verts:
                        if vert in face.verts:  
                            vert.co += normal * 0.001523

                
                bmesh.update_edit_mesh(obj.data)
                bpy.ops.object.mode_set(mode='OBJECT')

        self.report({'INFO'}, "Forced doubleside mesh for selected objects (extruded along normals by 0.001523M)")
        return {'FINISHED'}
#######################################################
class OBJECT_OT_recalculate_normals_outward(bpy.types.Operator):
    bl_idname = "object.recalculate_normals_outward"
    bl_label = "Recalculate Normals (Outward)"
    bl_description = "Quickly fix normals of selected meshes to face outward"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import bmesh

        processed_meshes = []

        print("Recalculating normals (outward) - please wait...")
        self.report({'INFO'}, "Recalculating normals (outward) - please wait...")

        for obj in context.selected_objects:
            if obj.type == 'MESH':
                mesh = obj.data

                bm = bmesh.new()
                bm.from_mesh(mesh)
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
                bm.to_mesh(mesh)
                bm.free()

                processed_meshes.append(obj.name)

        if processed_meshes:
            report_msg = f"Normals recalculated outward for: {', '.join(processed_meshes)}"
        else:
            report_msg = "No mesh objects were processed."

        self.report({'INFO'}, report_msg)
        print(report_msg)
        return {'FINISHED'}

#######################################################
class OBJECT_OT_recalculate_normals_inward(bpy.types.Operator):
    bl_idname = "object.recalculate_normals_inward"
    bl_label = "Recalculate Normals (Inward)"
    bl_description = "Quickly fix normals of selected meshes to face inward"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import bmesh

        processed_meshes = []

        print("Recalculating normals (inward) - please wait...")
        self.report({'INFO'}, "Recalculating normals (inward) - please wait...")

        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue

            mesh = obj.data
            bm = bmesh.new()
            bm.from_mesh(mesh)

            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

            bmesh.ops.reverse_faces(bm, faces=bm.faces)

            bm.to_mesh(mesh)
            bm.free()

            processed_meshes.append(obj.name)

        if processed_meshes:
            report_msg = f"Normals recalculated inward for: {', '.join(processed_meshes)}"
        else:
            report_msg = "No mesh objects were processed."

        self.report({'INFO'}, report_msg)
        print(report_msg)
        return {'FINISHED'}


#######################################################
class OBJECT_OT_set_collision_objects(bpy.types.Operator):
    bl_idname = "object.set_collision_objects"
    bl_label = "Set All As Collision Objects"
    bl_description = "Set all selected objects to collision objects"
    bl_options = {'REGISTER', 'UNDO'}

    def set_collision_objects(context):
        for obj in context.selected_objects:
            obj.dff.type = 'COL'
            print(f"Set {obj.name} as a collision object")

    def execute(self, context):
        set_collision_objects(context)
        return {'FINISHED'}
#######################################################   
class OBJECT_OT_remove_frames(bpy.types.Operator):
    bl_idname = "object.remove_frames"
    bl_label = "Remove Frames"
    bl_description = "Remove all frame-type empties from the current scene"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        removed_count = 0
        for obj in list(context.scene.objects):
            if obj.type == 'EMPTY' and obj.dff.is_frame:
                bpy.data.objects.remove(obj, do_unlink=True)
                removed_count += 1
        self.report({'INFO'}, f"Removed {removed_count} frame objects.")
        return {'FINISHED'}

#######################################################
class OBJECT_OT_truncate_frame_names(bpy.types.Operator):
    bl_idname = "object.truncate_frame_names"
    bl_label = "Truncate Frame Names"
    bl_description = "Truncate frame names to 22 bytes, excluding specific names (2dfx, Omni, Root)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        truncated_count = 0

        for obj in context.selected_objects:
            if obj.type == 'EMPTY' and not any(x in obj.name for x in ["2dfx", "Omni", "Root"]):
                original_name = obj.name
                truncated_name = original_name.encode('utf-8')[:22].decode('utf-8', 'ignore')
                
                if truncated_name != original_name:
                    obj.name = truncated_name
                    truncated_count += 1

        self.report({'INFO'}, f"Truncated names of {truncated_count} frames.")
        return {'FINISHED'}
#######################################################

def add_light_info(context):
    for obj in context.selected_objects:
        if obj.type == 'LIGHT':
            obj["sdfx_drawdis"] = 100.0
            obj["sdfx_outerrange"] = 18.0
            obj["sdfx_size"] = 1.0
            obj["sdfx_innerrange"] = 8.0
            obj["sdfx_corona"] = "coronastar"
            obj["sdfx_shad"] = "shad_exp"
            obj["sdfx_lighttype"] = 1
            obj["sdfx_color"] = (15, 230, 0, 200)  # Default color (RGBA)
            obj["sdfx_OnAllDay"] = 1  # Default value for OnAllDay
            obj["sdfx_showmode"] = 4
            obj["sdfx_reflection"] = 0
            obj["sdfx_flaretype"] = 0
            obj["sdfx_shadcolormp"] = 40
            obj["sdfx_shadowzdist"] = 0
            obj["sdfx_flags2"] = 0
            obj["sdfx_viewvector"] = (0, 156, 0)
            print(f"Added GTA Light info to {obj.name}")

def add_particle_info(context):
    for obj in context.selected_objects:
        if obj.type == 'EMPTY':
            obj["sdfx_psys"] = fx_psystems[0]  # Default particle system
            print(f"Added GTA Particle system info to {obj.name}")

def add_text_info(context):
    for obj in context.selected_objects:
        if obj.type == 'MESH' and "Plane" in obj.name:
            obj["sdfx_text1"] = ""
            obj["sdfx_text2"] = ""
            obj["sdfx_text3"] = ""
            obj["sdfx_text4"] = ""
            print(f"Added GTA 2D Text info to {obj.name}")

def export_info(context):
    global effectfile
    global textfile
    obj_to_exp = [obj for obj in context.selected_objects if any(key.startswith("sdfx_") for key in obj.keys())]
    
    if not obj_to_exp:
        print("No objects with custom properties found for export.")
        return

    with open(effectfile, "wb") as effect_stream, open(textfile, "w") as text_stream:
        # Write header info for binary file
        effect_stream.write(len(obj_to_exp).to_bytes(4, byteorder='little'))
        print(f"Number of objects to export: {len(obj_to_exp)}")
        
        # Write header info for text file
        text_stream.write(f"NumEntries {len(obj_to_exp)}\n")
        
        for i, obj in enumerate(obj_to_exp, start=1):
            print(f"Exporting object: {obj.name}, Type: {obj.type}")
            text_stream.write(f"######################### {i} #########################\n")
            if obj.type == 'LIGHT':
                export_light_info(effect_stream, text_stream, obj)
            elif obj.type == 'EMPTY':
                export_particle_info(effect_stream, text_stream, obj)
            elif obj.type == 'MESH' and "Plane" in obj.name:
                export_text_info(effect_stream, text_stream, obj)

def export_light_info(effect_stream, text_stream, obj):
    pos = obj.location
    color = obj["sdfx_color"]
    corona_far_clip = obj["sdfx_drawdis"]
    pointlight_range = obj["sdfx_outerrange"]
    corona_size = obj["sdfx_size"]
    shadow_size = obj["sdfx_innerrange"]
    corona_show_mode = obj["sdfx_showmode"]
    corona_enable_reflection = obj["sdfx_reflection"]
    corona_flare_type = obj["sdfx_flaretype"]
    shadow_color_multiplier = obj["sdfx_shadcolormp"]
    flags1 = obj["sdfx_OnAllDay"]
    corona_tex_name = obj["sdfx_corona"]
    shadow_tex_name = obj["sdfx_shad"]
    shadow_z_distance = obj["sdfx_shadowzdist"]
    flags2 = obj["sdfx_flags2"]
    view_vector = obj["sdfx_viewvector"]

    print(f"Light Position: {pos}, Color: {color}")

    effect_stream.write(bytearray(struct.pack("f", pos.x)))
    effect_stream.write(bytearray(struct.pack("f", pos.y)))
    effect_stream.write(bytearray(struct.pack("f", pos.z)))
    effect_stream.write(bytearray(struct.pack("4B", int(color[0]), int(color[1]), int(color[2]), int(color[3]))))
    effect_stream.write(bytearray(struct.pack("f", corona_far_clip)))
    effect_stream.write(bytearray(struct.pack("f", pointlight_range)))
    effect_stream.write(bytearray(struct.pack("f", corona_size)))
    effect_stream.write(bytearray(struct.pack("f", shadow_size)))
    effect_stream.write(bytearray(struct.pack("B", corona_show_mode)))
    effect_stream.write(bytearray(struct.pack("B", corona_enable_reflection)))
    effect_stream.write(bytearray(struct.pack("B", corona_flare_type)))
    effect_stream.write(bytearray(struct.pack("B", shadow_color_multiplier)))
    effect_stream.write(bytearray(struct.pack("B", flags1)))
    effect_stream.write(bytearray(corona_tex_name.encode('utf-8')).ljust(24, b'\0'))
    effect_stream.write(bytearray(shadow_tex_name.encode('utf-8')).ljust(24, b'\0'))
    effect_stream.write(bytearray(struct.pack("B", shadow_z_distance)))
    effect_stream.write(bytearray(struct.pack("B", flags2)))
    effect_stream.write(bytearray(struct.pack("B", 0)))  # padding

    # Write to text file
    text_stream.write(f"2dfxType         LIGHT\n")
    text_stream.write(f"Position         {pos.x} {pos.y} {pos.z}\n")
    text_stream.write(f"Color            {int(color[0])} {int(color[1])} {int(color[2])} {int(color[3])}\n")
    text_stream.write(f"CoronaFarClip    {corona_far_clip}\n")
    text_stream.write(f"PointlightRange  {pointlight_range}\n")
    text_stream.write(f"CoronaSize       {corona_size}\n")
    text_stream.write(f"ShadowSize       {shadow_size}\n")
    text_stream.write(f"CoronaShowMode   {corona_show_mode}\n")
    text_stream.write(f"CoronaReflection {corona_enable_reflection}\n")
    text_stream.write(f"CoronaFlareType  {corona_flare_type}\n")
    text_stream.write(f"ShadowColorMP    {shadow_color_multiplier}\n")
    text_stream.write(f"ShadowZDistance  {shadow_z_distance}\n")
    text_stream.write(f"CoronaTexName    {corona_tex_name}\n")
    text_stream.write(f"ShadowTexName    {shadow_tex_name}\n")
    text_stream.write(f"Flags1           {flags1}\n")
    text_stream.write(f"Flags2           {flags2}\n")
    text_stream.write(f"ViewVector       {view_vector[0]} {view_vector[1]} {view_vector[2]}\n")

def export_particle_info(effect_stream, text_stream, obj):
    pos = obj.location
    print(f"Particle Position: {pos}")
    effect_stream.write(bytearray(struct.pack("f", pos.x)))
    effect_stream.write(bytearray(struct.pack("f", pos.y)))
    effect_stream.write(bytearray(struct.pack("f", pos.z)))
    effect_stream.write(len(obj["sdfx_psys"]).to_bytes(4, byteorder='little'))
    effect_stream.write(obj["sdfx_psys"].encode('utf-8'))

    # Write to text file
    text_stream.write(f"2dfxType         PARTICLE\n")
    text_stream.write(f"Position         {pos.x} {pos.y} {pos.z}\n")
    text_stream.write(f"ParticleSystem   {obj['sdfx_psys']}\n")

def export_text_info(effect_stream, text_stream, obj):
    pos = obj.location
    print(f"Text Position: {pos}")
    effect_stream.write(bytearray(struct.pack("f", pos.x)))
    effect_stream.write(bytearray(struct.pack("f", pos.y)))
    effect_stream.write(bytearray(struct.pack("f", pos.z)))
    text_data = obj["sdfx_text1"] + obj["sdfx_text2"] + obj["sdfx_text3"] + obj["sdfx_text4"]
    effect_stream.write(len(text_data).to_bytes(4, byteorder='little'))
    effect_stream.write(text_data.encode('utf-8'))

    # Write to text(.TXT) file
    text_stream.write(f"2dfxType         TEXT\n")
    text_stream.write(f"Position         {pos.x} {pos.y} {pos.z}\n")
    text_stream.write(f"TextData         {obj['sdfx_text1']} {obj['sdfx_text2']} {obj['sdfx_text3']} {obj['sdfx_text4']}\n")
#######################################################
class SAEEFFECTS_PT_Panel(bpy.types.Panel):
    bl_label = "DemonFF - 2DFX"
    bl_idname = "SAEEFFECTS_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "DemonFF"

    def draw(self, context):
        layout = self.layout
        layout.operator("saeeffects.create_lights_from_entries", text="Create Lights from Entries")

#######################################################
class SAEffectsPanel(bpy.types.Panel):
    bl_label = "SA Effects"
    bl_idname = "OBJECT_PT_saeffects"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'
    bl_parent_id = "OBJECT_PT_dffObjects"  # Ensures it appears under the DemonFF - Export Object panel

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("saeffects.add_light_info", text="Add Light Info")
        row = layout.row()
        row.operator("saeffects.add_particle_info", text="Add Particle Info")
        row = layout.row()
        row.operator("saeffects.add_text_info", text="Add 2D Text Info")
        row = layout.row()
        row.prop(context.scene, "saeffects_export_path")
        row = layout.row()
        row.prop(context.scene, "saeffects_text_export_path")
        row = layout.row()
        row.operator("saeffects.export_info", text="Export Binary Info")
#######################################################
class SAEFFECTS_OT_AddLightInfo(bpy.types.Operator):
    bl_idname = "saeffects.add_light_info"
    bl_label = "Add Light Info"
    
    def execute(self, context):
        add_light_info(context)
        return {'FINISHED'}
#######################################################
class SAEFFECTS_OT_AddParticleInfo(bpy.types.Operator):
    bl_idname = "saeffects.add_particle_info"
    bl_label = "Add Particle Info"
    
    def execute(self, context):
        add_particle_info(context)
        return {'FINISHED'}
#######################################################
class SAEFFECTS_OT_AddTextInfo(bpy.types.Operator):
    bl_idname = "saeffects.add_text_info"
    bl_label = "Add 2D Text Info"
    
    def execute(self, context):
        add_text_info(context)
        return {'FINISHED'}
#######################################################
class SAEFFECTS_OT_ExportInfo(bpy.types.Operator):
    bl_idname = "saeffects.export_info"
    bl_label = "Export Binary Info"
    
    def execute(self, context):
        global effectfile
        global textfile
        effectfile = bpy.path.abspath(context.scene.saeffects_export_path)
        textfile = bpy.path.abspath(context.scene.saeffects_text_export_path)
        export_info(context)
        return {'FINISHED'}

def register_saeffects():
    bpy.types.Scene.saeffects_export_path = bpy.props.StringProperty(
        name="Binary Path",
        description="Path to export the effects binary file",
        subtype='FILE_PATH'
    )
    bpy.types.Scene.saeffects_text_export_path = bpy.props.StringProperty(
        name="Text Path",
        description="Path to export the effects text file",
        subtype='FILE_PATH'
    )
    bpy.utils.register_class(SAEffectsPanel)
    bpy.utils.register_class(SAEFFECTS_OT_AddLightInfo)
    bpy.utils.register_class(SAEFFECTS_OT_AddParticleInfo)
    bpy.utils.register_class(SAEFFECTS_OT_AddTextInfo)
    bpy.utils.register_class(SAEFFECTS_OT_ExportInfo)

def unregister_saeffects():
    bpy.utils.unregister_class(SAEffectsPanel)
    bpy.utils.unregister_class(SAEFFECTS_OT_AddLightInfo)
    bpy.utils.unregister_class(SAEFFECTS_OT_AddParticleInfo)
    bpy.utils.unregister_class(SAEFFECTS_OT_AddTextInfo)
    bpy.utils.unregister_class(SAEFFECTS_OT_ExportInfo)
    del bpy.types.Scene.saeffects_export_path
    del bpy.types.Scene.saeffects_text_export_path

#######################################################
class MATERIAL_PT_dffMaterials(bpy.types.Panel):

    bl_idname = "MATERIAL_PT_dffMaterials"
    bl_label = "DemonFF - Export Material"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"

    ambient: bpy.props.BoolProperty(
        name="Export Material",
        default=False
    )

    #######################################################
    def draw_col_menu(self, context):
        layout = self.layout
        settings = context.material.dff

        props = [["col_mat_index", "Material"],
                 ["col_flags", "Flags"],
                 ["col_brightness", "Brightness"],
                 ["col_light", "Light"]]

        for prop in props:
            self.draw_labelled_prop(layout.row(), settings, [prop[0]], prop[1])

    #######################################################
    def draw_labelled_prop(self, row, settings, props, label, text=""):
        row.label(text=label)
        for prop in props:
            row.prop(settings, prop, text=text)

    #######################################################
    def draw_env_map_box(self, context, box):
        settings = context.material.dff

        box.row().prop(context.material.dff, "export_env_map")
        if settings.export_env_map:
            box.row().prop(settings, "env_map_tex", text="Texture")

            self.draw_labelled_prop(
                box.row(), settings, ["env_map_coef"], "Coefficient")
            self.draw_labelled_prop(
                box.row(), settings, ["env_map_fb_alpha"], "Use FB Alpha")

    #######################################################
    def draw_bump_map_box(self, context, box):
        settings = context.material.dff
        box.row().prop(settings, "export_bump_map")

        if settings.export_bump_map:
            box.row().prop(settings, "bump_map_tex", text="Height Map Texture")

    #######################################################
    def draw_uv_anim_box(self, context, box):
        settings = context.material.dff

        box.row().prop(settings, "export_animation")
        if settings.export_animation:
            box.row().prop(settings, "animation_name", text="Name")

    #######################################################
    def draw_refl_box(self, context, box):
        settings = context.material.dff
        box.row().prop(settings, "export_reflection")

        if settings.export_reflection:
            self.draw_labelled_prop(
                box.row(), settings, ["reflection_scale_x", "reflection_scale_y"],
                "Scale"
            )
            self.draw_labelled_prop(
                box.row(), settings, ["reflection_offset_x", "reflection_offset_y"],
                "Offset"
            )
            self.draw_labelled_prop(
                box.row(), settings, ["reflection_intensity"], "Intensity"
            )

    #######################################################
    def draw_specl_box(self, context, box):
        settings = context.material.dff
        box.row().prop(settings, "export_specular")

        if settings.export_specular:
            self.draw_labelled_prop(
                box.row(), settings, ["specular_level"], "Level"
            )
            box.row().prop(settings, "specular_texture", text="Texture")

    #######################################################
    def draw_mesh_menu(self, context):
        layout = self.layout
        settings = context.material.dff

        layout.prop(settings, "ambient")

        # This is for conveniently setting the base colour from the settings
        # without removing the texture node

        try:
            if bpy.app.version >= (2, 80, 0):
                prop = context.material.node_tree.nodes["Principled BSDF"].inputs[0]
                prop_val = "default_value"
            else:
                prop = context.material
                prop_val = "diffuse_color"

            row = layout.row()
            row.prop(
                prop,
                prop_val,
                text="Color")

            row.prop(settings,
                     "preset_mat_cols",
                     text="",
                     icon="MATERIAL",
                     icon_only=True
                     )

        except Exception:
            pass

        self.draw_env_map_box(context, layout.box())
        self.draw_bump_map_box(context, layout.box())
        self.draw_refl_box(context, layout.box())
        self.draw_specl_box(context, layout.box())
        self.draw_uv_anim_box(context, layout.box())

    #######################################################
    # Callback function from preset_mat_cols enum
    def set_preset_color(self, context):
        try:
            color = eval(context.material.dff.preset_mat_cols)
            color = [i / 255 for i in color]

            if bpy.app.version >= (2, 80, 0):
                node = context.material.node_tree.nodes["Principled BSDF"]
                node.inputs[0].default_value = color

            # Viewport color in Blender 2.8 and Material color in 2.79.
            context.material.diffuse_color = color[:-1]

        except Exception as e:
            print(e)

    #######################################################
    def draw(self, context):
        if not context.material or not context.material.dff:
            return

        if context.object.dff.type == 'COL':
            self.draw_col_menu(context)
            return

        self.draw_mesh_menu(context)
#######################################################
class DFF_MT_ImportChoice(bpy.types.Menu):
    bl_label = "DemonFF"

    def draw(self, context):
        layout = self.layout
        layout.operator(IMPORT_OT_dff_custom.bl_idname, 
                        text="DemonFF DFF (.dff/.col)")
        layout.operator(IMPORT_OT_ifp.bl_idname, 
                        text="DemonFF IFP (.ifp)")

#######################################################@
class DFF_MT_ExportChoice(bpy.types.Menu):
    bl_label = "DemonFF"

    def draw(self, context):
        self.layout.operator(EXPORT_OT_dff_custom.bl_idname,
                             text="DemonFF DFF (.dff/.col)")
        self.layout.operator(EXPORT_OT_col.bl_idname,
                             text="DemonFF Collision (.col)")

#######################################################
def import_dff_func(self, context):
    self.layout.menu("DFF_MT_ImportChoice", text="DemonFF")
#######################################################
def export_dff_func(self, context):
    self.layout.menu("DFF_MT_ExportChoice", text="DemonFF")

#######################################################
#######################################################@
class DFF_MT_EditArmature(bpy.types.Menu):
    bl_label = "DemonFF"

    def draw(self, context):
        self.layout.operator(OBJECT_OT_dff_generate_bone_props.bl_idname, text="Generate Bone Properties")

#######################################################
def edit_armature_dff_func(self, context):
    self.layout.separator()
    self.layout.menu("DFF_MT_EditArmature", text="DemonFF")

#######################################################@
class DFF_MT_Pose(bpy.types.Menu):
    bl_label = "DemonFF"

    def draw(self, context):
        self.layout.operator(OBJECT_OT_dff_set_parent_bone.bl_idname, text="Set Object Parent To Bone")
        self.layout.operator(OBJECT_OT_dff_clear_parent_bone.bl_idname, text="Clear Object Parent")

#######################################################
def pose_dff_func(self, context):
    self.layout.separator()
    self.layout.menu("DFF_MT_Pose", text="DemonFF")

#######################################################
class OBJECT_PT_dffObjects(bpy.types.Panel):

    bl_idname      = "OBJECT_PT_dffObjects"
    bl_label       = "DemonFF - Export Object"
    bl_space_type  = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context     = "object"

    #######################################################
    def draw_labelled_prop(self, row, settings, props, label, text=""):
        
        row.label(text=label)
        for prop in props:
            row.prop(settings, prop, text=text)


    #######################################################
    def validate_pipeline(self, pipeline):

        try:
            int(pipeline, 0)
        except ValueError:
            return False

        return True
            
    #######################################################
    def draw_mesh_menu(self, context):

        layout = self.layout
        settings = context.object.dff

        box = layout.box()
        box.prop(settings, "export_normals", text="Export Normals")
        box.prop(settings, "export_split_normals", text="Export Custom Split Normals")
        box.prop(settings, "export_binsplit", text="Export Bin Mesh PLG")
        box.prop(settings, "light", text="Enable Lighting")
        box.prop(settings, "modulate_color", text="Enable Modulate Material Color")

        row = box.row()
        if settings.is_frame_locked:
            row.enabled = False
        row.prop(settings, "is_frame", text="Export As Frame")

        properties = [
            ["day_cols", "Day Vertex Colours"],
            ["night_cols", "Night Vertex Colours"],
        ]

        box = layout.box()
        box.label(text="Export Vertex Colours")
        
        for property in properties:
            box.prop(settings, property[0], text=property[1])

        box = layout.box()
        box.label(text="Export UV Maps")

        box.prop(settings, "uv_map1", text="UV Map 1")

        # Second UV Map can only be disabled if the first UV map is enabled.
        if settings.uv_map1:
            box.prop(settings, "uv_map2", text="UV Map 2")

        box = layout.box()
        box.label(text="Atomic")
        box.prop(settings, "pipeline", text="Pipeline")
        if settings.pipeline == 'CUSTOM':
            col = box.column()

            col.alert = not self.validate_pipeline(settings.custom_pipeline)
            icon = "ERROR" if col.alert else "NONE"

            col.prop(settings, "custom_pipeline", icon=icon, text="Custom Pipeline")

        box.prop(settings, "right_to_render", text="Right To Render")

    #######################################################
    def draw_col_menu(self, context):
        layout = self.layout
        settings = context.object.dff

        box = layout.box()
        box.label(text="Material Surface")

        box.prop(settings, "col_material", text="Material")
        box.prop(settings, "col_flags", text="Flags")
        box.prop(settings, "col_brightness", text="Brightness")
        box.prop(settings, "col_light", text="Light")

        pass
    #######################################################
    def draw_2dfx_menu(self, context):
        layout = self.layout
        settings = context.object.dff.ext_2dfx

        layout.prop(settings, "effect", text="Effect")
        EXT2DFXMenus.draw_menu(int(settings.effect), layout, context)
    #######################################################
    def draw_obj_menu(self, context):
        layout = self.layout
        settings = context.object.dff

        layout.prop(settings, "type", text="Type")

        if settings.type == 'OBJ':
            if context.object.type == 'MESH':
                self.draw_mesh_menu(context)

        elif settings.type == 'COL':
            if context.object.type == 'EMPTY':
                self.draw_col_menu(context)

        elif settings.type == '2DFX':
            self.draw_2dfx_menu(context)

    #######################################################
    def draw(self, context):
        if not context.object.dff:
            return

        self.draw_obj_menu(context)

# Custom properties
#######################################################
class DFFMaterialProps(bpy.types.PropertyGroup):
    ambient: bpy.props.FloatProperty(name="Ambient Shading", default=1)

    # Environment Map
    export_env_map: bpy.props.BoolProperty(name="Environment Map")
    env_map_tex: bpy.props.StringProperty()
    env_map_coef: bpy.props.FloatProperty()
    env_map_fb_alpha: bpy.props.BoolProperty()

    # Bump Map
    export_bump_map: bpy.props.BoolProperty(name="Bump Map")
    bump_map_tex: bpy.props.StringProperty()

    # Reflection
    export_reflection: bpy.props.BoolProperty(name="Reflection Material")
    reflection_scale_x: bpy.props.FloatProperty()
    reflection_scale_y: bpy.props.FloatProperty()
    reflection_offset_x: bpy.props.FloatProperty()
    reflection_offset_y: bpy.props.FloatProperty()
    reflection_intensity: bpy.props.FloatProperty()

    # Specularity
    export_specular: bpy.props.BoolProperty(name="Specular Material")
    specular_level: bpy.props.FloatProperty()
    specular_texture: bpy.props.StringProperty()

    # Collision Data
    col_flags: bpy.props.IntProperty()
    col_brightness: bpy.props.IntProperty()
    col_light: bpy.props.IntProperty()
    col_mat_index: bpy.props.IntProperty()

    # UV Animation
    export_animation: bpy.props.BoolProperty(name="UV Animation")
    animation_name: bpy.props.StringProperty()

    # Pre-set Material Colours
    preset_mat_cols: bpy.props.EnumProperty(
        items=(
            ("[255, 60, 0, 255]", "Right Tail Light", ""),
            ("[185, 255, 0, 255]", "Left Tail Light", ""),
            ("[0, 255, 200, 255]", "Right Headlight", ""),
            ("[255, 175, 0, 255]", "Left Headlight", ""),
            ("[0, 255, 255, 255]", "4 Colors Paintjob", ""),
            ("[255, 0, 255, 255]", "Fourth Color", ""),
            ("[0, 255, 255, 255]", "Third Color", ""),
            ("[255, 0, 175, 255]", "Secondary Color", ""),
            ("[60, 255, 0, 255]", "Primary Color", ""),
            ("[184, 255, 0, 255]", "ImVehFT - Breaklight L", ""),
            ("[255, 59, 0, 255]", "ImVehFT - Breaklight R", ""),
            ("[255, 173, 0, 255]", "ImVehFT - Revlight L", ""),
            ("[0, 255, 198, 255]", "ImVehFT - Revlight R", ""),
            ("[255, 174, 0, 255]", "ImVehFT - Foglight L", ""),
            ("[0, 255, 199, 255]", "ImVehFT - Foglight R", ""),
            ("[183, 255, 0, 255]", "ImVehFT - Indicator LF", ""),
            ("[255, 58, 0, 255]", "ImVehFT - Indicator RF", ""),
            ("[182, 255, 0, 255]", "ImVehFT - Indicator LM", ""),
            ("[255, 57, 0, 255]", "ImVehFT - Indicator RM", ""),
            ("[181, 255, 0, 255]", "ImVehFT - Indicator LR", ""),
            ("[255, 56, 0, 255]", "ImVehFT - Indicator RR", ""),
            ("[0, 16, 255, 255]", "ImVehFT - Light Night", ""),
            ("[0, 17, 255, 255]", "ImVehFT - Light All-day", ""),
            ("[0, 18, 255, 255]", "ImVehFT - Default Day", "")
        ),
        update=MATERIAL_PT_dffMaterials.set_preset_color
    )

    def register():
        bpy.types.Material.dff = bpy.props.PointerProperty(type=DFFMaterialProps)


#######################################################
class DFFObjectProps(bpy.types.PropertyGroup):

    ext_2dfx: bpy.props.PointerProperty(type=EXT2DFXObjectProps)

    is_frame : bpy.props.BoolProperty(
        default     = False,
        description = "Object will be exported as a frame"
    )

    # Atomic Properties
    type: bpy.props.EnumProperty(
        items=(
            ('OBJ', 'Object', 'Object will be exported as a mesh or a dummy'),
            ('COL', 'Collision Object', 'Object is a collision object'),
            ('SHA', 'Shadow Object', 'Object is a shadow object'),
            ('2DFX', '2DFX', 'Object is a 2dfx object'),
            ('NON', "Don't export", 'Object will NOT be exported.')
        )
    )

    # Mesh properties
    pipeline: bpy.props.EnumProperty(
        items=(
            ('NONE', 'None', 'Export without setting a pipeline'),
            ('0x53F20098', 'Buildings', 'Refl. Building Pipleine (0x53F20098)'),
            (
                '0x53F2009A',
                'Night Vertex Colors',
                'Night Vertex Colors (0x53F2009C)'
            ),
            ('CUSTOM', 'Custom Pipeline', 'Set a different pipeline')
        ),
        name="Pipeline",
        description="Select the Engine rendering pipeline"
    )
    custom_pipeline: bpy.props.StringProperty(name="Custom Pipeline")

    export_normals: bpy.props.BoolProperty(
        default=True,
        description="Whether Normals will be exported. (Disable for Map objects)"
    )

    export_split_normals: bpy.props.BoolProperty(
        default=False,
        description="Whether Custom Split Normals will be exported (Flat Shading)."
    )
    
    export_tristrips: bpy.props.BoolProperty(
        default=False,
        description="Export using TriStrips"
    )

    light: bpy.props.BoolProperty(
        default=True,
        description="Enable rpGEOMETRYLIGHT flag"
    )

    modulate_color: bpy.props.BoolProperty(
        default=True,
        description="Enable rpGEOMETRYMODULATEMATERIALCOLOR flag"
    )

    uv_map1: bpy.props.BoolProperty(
        default=True,
        description="First UV Map will be exported")

    uv_map2: bpy.props.BoolProperty(
        default=True,
        description="Second UV Map will be exported"
    )

    day_cols: bpy.props.BoolProperty(
        default=True,
        description="Whether Day Vertex Prelighting Colours will be exported"
    )

    night_cols: bpy.props.BoolProperty(
        default=True,
        description="Extra prelighting colours. (Tip: Disable export normals)"
    )

    export_binsplit: bpy.props.BoolProperty(
        default=True,
        description="Enabling will increase file size, but will increase\
compatibiility with DFF Viewers"
    )

    col_material: bpy.props.IntProperty(
        default=12,
        description="Material used for the Sphere/Cone"
    )

    col_flags: bpy.props.IntProperty(
        default=0,
        description="Flags for the Sphere/Cone"
    )

    col_brightness: bpy.props.IntProperty(
        default=0,
        description="Brightness used for the Sphere/Cone"
    )

    col_light: bpy.props.IntProperty(
        default=0,
        description="Light used for the Sphere/Cone"
    )

    right_to_render : bpy.props.IntProperty(
        default = 1,
        min = 0,
        description = "Right To Render value (only for skinned object)"
    )

    frame_index : bpy.props.IntProperty(
        default = 2**31-1,
        min = 0,
        max = 2**31-1,
        options = {'SKIP_SAVE', 'HIDDEN'}
    )

    atomic_index : bpy.props.IntProperty(
        default = 2**31-1,
        min = 0,
        max = 2**31-1,
        options = {'SKIP_SAVE', 'HIDDEN'}
    )

    # 2DFX properties
    ext_2dfx : bpy.props.PointerProperty(type=EXT2DFXObjectProps)

    # Miscellaneous properties
    is_frame_locked : bpy.props.BoolProperty()

    def register():
        bpy.types.Object.dff = bpy.props.PointerProperty(type=DFFObjectProps)

#######################################################
class COLLECTION_OT_nuke_matched(bpy.types.Operator):
    bl_idname = "collection.nuke_matched_collections"
    bl_label = "Clean Empty .col/.dff Collections"
    bl_description = "Remove empty .col collections and matching .dff collections with their objects"

    def execute(self, context):
        def normalize(name):
            return name.strip().lower().replace(" ", "")

        def find_collections_recursive(root):
            all_cols = []
            def recurse(layer):
                all_cols.append(layer.collection)
                for child in layer.children:
                    recurse(child)
            recurse(root)
            return all_cols

        context = bpy.context
        view_layer = context.view_layer
        all_layer_collections = find_collections_recursive(view_layer.layer_collection)

        col_dict = {normalize(col.name): col for col in bpy.data.collections}
        to_delete_names = set()

        for col in all_layer_collections:
            col_name = normalize(col.name)

            if col_name.endswith(".col") or ".col." in col_name:
                if not col.objects and not col.children:
                    base = col_name.replace(".col", "").split(".")[0]
                    dff_key = f"{base}.dff"

                    if dff_key in col_dict:
                        col_target = col
                        dff_target = col_dict[dff_key]

                        print(f"🧠 Match found: {col_target.name} ↔ {dff_target.name}")
                        to_delete_names.add(col_target.name)
                        to_delete_names.add(dff_target.name)

                        for obj in list(dff_target.objects):
                            try:
                                if obj.name in bpy.data.objects:
                                    bpy.data.objects.remove(obj, do_unlink=True)
                                    print(f"🚮 Deleted object: {obj.name}")
                            except:
                                continue

        for name in to_delete_names:
            col = bpy.data.collections.get(name)
            if col:
                print(f"🗑️ Removing collection: {col.name}")
                for parent in bpy.data.collections:
                    if col.name in parent.children:
                        parent.children.unlink(col)
                if col.name in context.scene.collection.children:
                    context.scene.collection.children.unlink(col)
                try:
                    bpy.data.collections.remove(col)
                except:
                    pass

        self.report({'INFO'}, "Cleaned empty and matched collections.")
        return {'FINISHED'}
#######################################################    
class COLLECTION_OT_organize_scene_collection(bpy.types.Operator):
    bl_idname = "collection.organize_scene_collection"
    bl_label = "Organize Scene Collection"
    bl_description = "Organize .col above matching .dff collections"

    def execute(self, context):

        def get_base_name(name):
            if ".dff" in name:
                return name.split(".dff")[0]
            elif ".col" in name:
                return name.split(".col")[0]
            return name

        def organize_pairs(scene):
            all_colls = list(scene.collection.children)

            pairs = []
            others = []

            pair_map = {}

            for col in all_colls:
                base = get_base_name(col.name)

                if base not in pair_map:
                    pair_map[base] = {"col": None, "dff": None}

                if ".col" in col.name:
                    pair_map[base]["col"] = col
                elif ".dff" in col.name:
                    pair_map[base]["dff"] = col
                else:
                    others.append(col)

            # Unlink all first
            for c in all_colls:
                scene.collection.children.unlink(c)

            # Link back in pairwise order: .col first, .dff next
            for base in sorted(pair_map.keys()):
                pair = pair_map[base]
                if pair["col"]:
                    scene.collection.children.link(pair["col"])
                if pair["dff"]:
                    scene.collection.children.link(pair["dff"])

            # Link the rest (non .col/.dff) last
            for col in sorted(others, key=lambda c: c.name):
                scene.collection.children.link(col)

        organize_pairs(context.scene)
        self.report({'INFO'}, ".col collections are now above their matching .dff collections.")
        return {'FINISHED'}
    
#######################################################
class COLLECTION_OT_remove_empty_collections(bpy.types.Operator):
    bl_idname = "collection.remove_empty_collections"
    bl_label = "Remove Empty Collections"
    bl_description = "Remove all empty collections from the scene"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        removed_count = 0
        for collection in list(bpy.data.collections):
            if not collection.objects and not collection.children:
                bpy.data.collections.remove(collection)
                removed_count += 1
        self.report({'INFO'}, f"Removed {removed_count} empty collections.")
        return {'FINISHED'}
   

#######################################################
class SCENE_OT_duplicate_all_as_collision(bpy.types.Operator):
    bl_idname = "scene.duplicate_all_as_collision"
    bl_label = "Duplicate All as Collision"
    bl_description = "Duplicate all mesh objects in the scene as collision meshes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        root_collection = bpy.context.scene.collection
        collection_pairs = []

        for obj in context.scene.objects:
            if not obj.users_collection or obj.type != 'MESH':
                continue

            col_name = f"{obj.name}.col.{obj.name}"

            duplicate = obj.copy()
            duplicate.data = obj.data.copy() if obj.data else None
            duplicate.name = col_name

            col_collection = bpy.data.collections.new(col_name)
            root_collection.children.link(col_collection)
            col_collection.objects.link(duplicate)

            if hasattr(duplicate, "dff"):
                duplicate.dff.type = 'COL'


            original_collection = obj.users_collection[0]
            collection_pairs.append((col_collection, original_collection))

        # Reorder so col comes first
        for col_collection, dff_collection in collection_pairs:
            if dff_collection in root_collection.children:
                root_collection.children.unlink(dff_collection)
            if col_collection in root_collection.children:
                root_collection.children.unlink(col_collection)
            root_collection.children.link(col_collection)
            root_collection.children.link(dff_collection)

        self.report({'INFO'}, "Objects duplicated as .COL objects.")
        return {'FINISHED'}

#######################################################    
class COLLECTION_PT_custom_cleanup_panel(bpy.types.Panel):
    bl_label = "DemonFF - Collection Tools"
    bl_idname = "COLLECTION_PT_custom_cleanup_panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "collection"

    def draw(self, context):
        layout = self.layout
        layout.operator("collection.nuke_matched_collections", icon='TRASH')
        layout.operator("collection.organize_scene_collection", icon='SORTALPHA')
        layout.operator("collection.remove_empty_collections", icon='X')

####################################################### 
class SCENE_PT_animation_browser(bpy.types.Panel):
    bl_label = "DemonFF - Animation Browser"
    bl_idname = "SCENE_PT_animation_browser"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'

    def draw(self, context):
        layout = self.layout
        layout.label(text="Available Actions", icon='ACTION')

        obj = context.object
        actions = bpy.data.actions

        if obj and obj.type == 'ARMATURE':
            for action in actions:
                row = layout.row()
                row.prop(action, "name", text="", emboss=False, icon='ANIM')
                assign = row.operator("scene.assign_action_to_object", text="", icon='FILE_TICK')
                assign.action_name = action.name
        else:
            layout.label(text="Select an armature to assign animations.", icon='INFO')


#######################################################
class SCENE_OT_assign_action_to_object(bpy.types.Operator):
    bl_idname = "scene.assign_action_to_object"
    bl_label = "Assign Action to Armature"
    
    action_name: bpy.props.StringProperty()

    def execute(self, context):
        obj = context.object
        action = bpy.data.actions.get(self.action_name)

        if not obj or obj.type != 'ARMATURE':
            self.report({'WARNING'}, "You must select an armature object.")
            return {'CANCELLED'}

        if action is None:
            self.report({'WARNING'}, f"Action '{self.action_name}' not found.")
            return {'CANCELLED'}

        # Ensure animation_data exists
        if obj.animation_data is None:
            obj.animation_data_create()

        obj.animation_data.action = action

        # Optionally reset timeline to match action
        context.scene.frame_start = int(action.frame_range[0])
        context.scene.frame_end = int(action.frame_range[1])
        context.scene.frame_current = int(action.frame_range[0])

        self.report({'INFO'}, f"Assigned '{action.name}' to '{obj.name}'")
        return {'FINISHED'}

#######################################################
class DFFCollectionProps(bpy.types.PropertyGroup):

    type : bpy.props.EnumProperty(
        items = (
            ('CMN',   'Common', 'Common collection'),
            ('NON',   "Don't export", 'Objects in this collection will NOT be exported')
        )
    )

    auto_bounds: bpy.props.BoolProperty(
        default = True,
        description = "Calculate bounds automatically"
    )

    bounds_min: bpy.props.FloatVectorProperty()
    bounds_max: bpy.props.FloatVectorProperty()

    #######################################################
    def draw_bounds():
        if not bpy.context.scene.dff.draw_bounds:
            return

        col = bpy.context.collection
        if col and not col.dff.auto_bounds:
            settings = col.dff

            bounds_min = settings.bounds_min
            bounds_max= settings.bounds_max

            coords = (
                (bounds_min[0], bounds_min[1], bounds_min[2]),
                (bounds_min[0], bounds_min[1], bounds_max[2]),
                (bounds_min[0], bounds_max[1], bounds_min[2]),
                (bounds_min[0], bounds_max[1], bounds_max[2]),
                (bounds_max[0], bounds_min[1], bounds_min[2]),
                (bounds_max[0], bounds_min[1], bounds_max[2]),
                (bounds_max[0], bounds_max[1], bounds_min[2]),
                (bounds_max[0], bounds_max[1], bounds_max[2]),
            )

            if (4, 0, 0) > bpy.app.version:
                shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
            else:
                shader = gpu.shader.from_builtin('UNIFORM_COLOR')

            batch = batch_for_shader(shader, 'LINES', {"pos": coords}, indices=box_indices)

            shader.bind()
            shader.uniform_float("color", (0.84, 0.84, 0.54, 1))
            batch.draw(shader)

    #######################################################
    def register():
        bpy.types.Collection.dff = bpy.props.PointerProperty(type=DFFCollectionProps)

#######################################################
class TXDImportPanel(bpy.types.Panel):

    bl_label       = "DemonFF - TXD Import"
    bl_idname      = "SCENE_PT_txdImport"
    bl_space_type  = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context     = "scene"
    bl_options     = {'DEFAULT_CLOSED'}

    #######################################################
    def draw(self, context):
        layout = self.layout
        layout.operator(IMPORT_OT_txd.bl_idname)

#######################################################
class DFF_UL_FrameItems(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if item and item.obj:
            layout.label(text=item.obj.name, icon=item.icon)

    def draw_filter(self, context, layout):
        layout.prop(context.scene.dff, "filter_collection", toggle=True)

    def filter_items(self, context, data, propname):
        frames = context.scene.dff.frames
        frames_num = len(frames)

        flt_flags = [self.bitflag_filter_item | (1 << 0)] * frames_num

        active_object = context.view_layer.objects.active
        active_collections = {active_object.users_collection} if active_object else None

        if active_collections and context.scene.dff.filter_collection:
            for i, frame in enumerate(frames):
                if not active_collections.issubset({frame.obj.users_collection}):
                    flt_flags[i] &= ~self.bitflag_filter_item

        return flt_flags, list(range(frames_num))

#######################################################
class DFF_UL_AtomicItems(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if item and item.obj:
            text = item.obj.name
            if item.frame_obj and not item.obj.dff.is_frame:
                text += " [%s]" % item.frame_obj.name
            layout.label(text=text, icon='MESH_DATA')

    def draw_filter(self, context, layout):
        layout.prop(context.scene.dff, "filter_collection", toggle=True)

    def filter_items(self, context, data, propname):
        atomics = context.scene.dff.atomics
        atomics_num = len(atomics)

        flt_flags = [self.bitflag_filter_item | (1 << 0)] * atomics_num

        active_object = context.view_layer.objects.active
        active_collections = {active_object.users_collection} if active_object else None

        if active_collections and context.scene.dff.filter_collection:
            for i, atomic in enumerate(atomics):
                if not active_collections.issubset({atomic.obj.users_collection}):
                    flt_flags[i] &= ~self.bitflag_filter_item

        return flt_flags, list(range(atomics_num))

#######################################################
class SCENE_PT_dffFrames(bpy.types.Panel):

    bl_idname      = "SCENE_PT_dffFrames"
    bl_label       = "DemonFF - Frames"
    bl_space_type  = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context     = "scene"
    bl_options     = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene_dff = context.scene.dff

        layout = self.layout
        row = layout.row()

        col = row.column()
        col.template_list(
            "DFF_UL_FrameItems",
            "",
            scene_dff,
            "frames",
            scene_dff,
            "frames_active",
            rows=3,
            maxrows=8,
            sort_lock=True
        )

        if len(scene_dff.frames) > 1:
            col = row.column(align=True)
            col.operator(SCENE_OT_dff_frame_move.bl_idname, icon='TRIA_UP', text="").direction = 'UP'
            col.operator(SCENE_OT_dff_frame_move.bl_idname, icon='TRIA_DOWN', text="").direction = 'DOWN'

        row = layout.row()
        col = row.column()
        col.prop(scene_dff, "real_time_update", toggle=True)
        if not scene_dff.real_time_update:
            col = row.column()
            col.operator(SCENE_OT_dff_update.bl_idname, icon='FILE_REFRESH', text="")

#######################################################
class SCENE_PT_dffAtomics(bpy.types.Panel):

    bl_idname      = "SCENE_PT_dffAtomics"
    bl_label       = "DemonFF - Atomics"
    bl_space_type  = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context     = "scene"
    bl_options     = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene_dff = context.scene.dff

        layout = self.layout
        row = layout.row()

        col = row.column()
        col.template_list(
            "DFF_UL_AtomicItems",
            "",
            scene_dff,
            "atomics",
            scene_dff,
            "atomics_active",
            rows=3,
            maxrows=8,
            sort_lock=True
        )

        if len(scene_dff.atomics) > 1:
            col = row.column(align=True)
            col.operator(SCENE_OT_dff_atomic_move.bl_idname, icon='TRIA_UP', text="").direction = 'UP'
            col.operator(SCENE_OT_dff_atomic_move.bl_idname, icon='TRIA_DOWN', text="").direction = 'DOWN'

        row = layout.row()
        col = row.column()
        col.prop(scene_dff, "real_time_update", toggle=True)
        if not scene_dff.real_time_update:
            col = row.column()
            col.operator(SCENE_OT_dff_update.bl_idname, icon='FILE_REFRESH', text="")

def register():
    register_saeffects()
    bpy.utils.register_class(MATERIAL_PT_dffMaterials)
    bpy.utils.register_class(DFF_MT_ExportChoice)
    bpy.utils.register_class(OBJECT_PT_dffObjects)
    bpy.utils.register_class(DFFMaterialProps)
    bpy.utils.register_class(DFFObjectProps)
    bpy.utils.register_class(OBJECT_OT_join_similar_named_meshes)
    bpy.utils.register_class(OBJECT_PT_join_similar_meshes_panel)
    bpy.utils.register_class(OBJECT_OT_set_collision_objects)
    bpy.utils.register_class(SCENE_OT_duplicate_all_as_collision)
    bpy.utils.register_class(SAEEFFECTS_PT_Panel)
    bpy.utils.register_class(OBJECT_OT_force_doubleside_mesh)
    bpy.utils.register_class(OBJECT_PT_dff_misc_panel)
    bpy.utils.register_class
    bpy.utils.register_class(OBJECT_OT_recalculate_normals_outward)
    bpy.utils.register_class(OBJECT_OT_optimize_mesh)
    bpy.utils.register_class(COLLECTION_OT_nuke_matched)
    bpy.utils.register_class(COLLECTION_OT_organize_scene_collection)
    bpy.utils.register_class(COLLECTION_PT_custom_cleanup_panel)
    bpy.utils.register_class(SCENE_OT_assign_action_to_object)
    bpy.utils.register_class(SCENE_PT_animation_browser)
    bpy.utils.register_class(SCENE_OT_duplicate_all_as_objects)    


def unregister():
    unregister_saeffects()
    bpy.utils.unregister_class(MATERIAL_PT_dffMaterials)
    bpy.utils.unregister_class(DFF_MT_ExportChoice)
    bpy.utils.unregister_class(OBJECT_PT_dffObjects)
    bpy.utils.unregister_class(DFFMaterialProps)
    bpy.utils.unregister_class(DFFObjectProps)
    bpy.utils.unregister_class(OBJECT_OT_join_similar_named_meshes)
    bpy.utils.unregister_class(OBJECT_PT_join_similar_meshes_panel)
    bpy.utils.unregister_class(OBJECT_OT_set_collision_objects)
    bpy.utils.unregister_class(SCENE_OT_duplicate_all_as_collision)
    bpy.utils.unregister_class(SAEEFFECTS_PT_Panel)
    bpy.utils.unregister_class(OBJECT_OT_force_doubleside_mesh)
    bpy.utils.unregister_class(OBJECT_PT_dff_misc_panel)
    bpy.utils.unregister_class(OBJECT_OT_recalculate_normals_outward)
    bpy.utils.unregister_class(OBJECT_OT_optimize_mesh)
    bpy.utils.unregister_class(COLLECTION_OT_nuke_matched)
    bpy.utils.unregister_class(COLLECTION_PT_custom_cleanup_panel)
    bpy.utils.unregister_class(COLLECTION_OT_organize_scene_collection)
    bpy.utils.unregister_class(SCENE_OT_assign_action_to_object)
    bpy.utils.unregister_class(SCENE_PT_animation_browser)
    bpy.utils.unregister_class(SCENE_OT_duplicate_all_as_objects)   


if __name__ == "__main__":
    register()