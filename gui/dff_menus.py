import bpy
import struct
from .dff_ot import EXPORT_OT_dff_custom, IMPORT_OT_dff_custom
from .col_ot import EXPORT_OT_col

# Global variables
fx_images = ["coronastar", "shad_exp"]
fx_psystems = ["prt_blood", "prt_boatsplash"]
effectfile = ""
textfile = ""  # New variable to hold the path to the .txt file

def join_similar_named_meshes(context):
    # Create a dictionary to store objects by their base names
    base_name_dict = {}
    
    # Iterate through all objects in the scene
    for obj in context.scene.objects:
        if obj.type == 'MESH':
            # Split the name by the dot to separate the base name and the suffix
            name_parts = obj.name.split('.')
            base_name = name_parts[0]
            
            if base_name not in base_name_dict:
                base_name_dict[base_name] = []
            
            base_name_dict[base_name].append(obj)
    
    # Iterate through the dictionary and join objects with similar names
    for base_name, objects in base_name_dict.items():
        if len(objects) > 1:
            context.view_layer.objects.active = objects[0]
            bpy.ops.object.select_all(action='DESELECT')
            
            for obj in objects:
                obj.select_set(True)
            
            bpy.ops.object.join()

# Operator to call the join_similar_named_meshes function
class OBJECT_OT_join_similar_named_meshes(bpy.types.Operator):
    bl_idname = "object.join_similar_named_meshes"
    bl_label = "Join Similar Named Meshes"
    bl_description = "Join meshes with similar names"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        join_similar_named_meshes(context)
        return {'FINISHED'}

# Panel to add the Join Similar Named Meshes button
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

# Function to add light info to selected light objects
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

# Function to add particle info to selected empty objects
def add_particle_info(context):
    for obj in context.selected_objects:
        if obj.type == 'EMPTY':
            obj["sdfx_psys"] = fx_psystems[0]  # Default particle system
            print(f"Added GTA Particle system info to {obj.name}")

# Function to add 2D text info to selected plane objects
def add_text_info(context):
    for obj in context.selected_objects:
        if obj.type == 'MESH' and "Plane" in obj.name:
            obj["sdfx_text1"] = ""
            obj["sdfx_text2"] = ""
            obj["sdfx_text3"] = ""
            obj["sdfx_text4"] = ""
            print(f"Added GTA 2D Text info to {obj.name}")

# Function to export info to a binary file
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
                export_particle_info(effect_stream, obj)
            elif obj.type == 'MESH' and "Plane" in obj.name:
                export_text_info(effect_stream, obj)

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

def export_particle_info(effect_stream, obj):
    pos = obj.location
    print(f"Particle Position: {pos}")
    effect_stream.write(bytearray(struct.pack("f", pos.x)))
    effect_stream.write(bytearray(struct.pack("f", pos.y)))
    effect_stream.write(bytearray(struct.pack("f", pos.z)))
    effect_stream.write(len(obj["sdfx_psys"]).to_bytes(4, byteorder='little'))
    effect_stream.write(obj["sdfx_psys"].encode('utf-8'))

def export_text_info(effect_stream, obj):
    pos = obj.location
    print(f"Text Position: {pos}")
    effect_stream.write(bytearray(struct.pack("f", pos.x)))
    effect_stream.write(bytearray(struct.pack("f", pos.y)))
    effect_stream.write(bytearray(struct.pack("f", pos.z)))
    text_data = obj["sdfx_text1"] + obj["sdfx_text2"] + obj["sdfx_text3"] + obj["sdfx_text4"]
    effect_stream.write(len(text_data).to_bytes(4, byteorder='little'))
    effect_stream.write(text_data.encode('utf-8'))

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

class SAEFFECTS_OT_AddLightInfo(bpy.types.Operator):
    bl_idname = "saeffects.add_light_info"
    bl_label = "Add Light Info"
    
    def execute(self, context):
        add_light_info(context)
        return {'FINISHED'}

class SAEFFECTS_OT_AddParticleInfo(bpy.types.Operator):
    bl_idname = "saeffects.add_particle_info"
    bl_label = "Add Particle Info"
    
    def execute(self, context):
        add_particle_info(context)
        return {'FINISHED'}

class SAEFFECTS_OT_AddTextInfo(bpy.types.Operator):
    bl_idname = "saeffects.add_text_info"
    bl_label = "Add 2D Text Info"
    
    def execute(self, context):
        add_text_info(context)
        return {'FINISHED'}

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

# Integrating SA Effects with DemonFF Menus
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

#######################################################@
class DFF_MT_ExportChoice(bpy.types.Menu):
    bl_label = "DemonFF"

    def draw(self, context):
        self.layout.operator(EXPORT_OT_dff_custom.bl_idname,
                             text="DemonFF DFF (.dff)")
        self.layout.operator(EXPORT_OT_col.bl_idname,
                             text="DemonFF Collision (.col)")


#######################################################
def import_dff_func(self, context):
    self.layout.operator(IMPORT_OT_dff_custom.bl_idname, text="DemonFF DFF (.dff)")


#######################################################
def export_dff_func(self, context):
    self.layout.menu("DFF_MT_ExportChoice", text="DemonFF")


#######################################################
class OBJECT_PT_dffObjects(bpy.types.Panel):
    bl_idname = "OBJECT_PT_dffObjects"
    bl_label = "DemonFF - Export Object"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

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
        box.prop(settings, "pipeline", text="Pipeline")
        if settings.pipeline == 'CUSTOM':
            col = box.column()

            col.alert = not self.validate_pipeline(settings.custom_pipeline)
            icon = "ERROR" if col.alert else "NONE"

            col.prop(settings, "custom_pipeline", icon=icon, text="Custom Pipeline")

        box.prop(settings, "export_normals", text="Export Normals")
        box.prop(settings, "export_split_normals", text="Export Custom Split Normals")
        box.prop(settings, "export_binsplit", text="Export Bin Mesh PLG")
        box.prop(settings, "light", text="Enable Lighting")
        box.prop(settings, "modulate_color", text="Enable Modulate Material Color")

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
    # Atomic Properties
    type: bpy.props.EnumProperty(
        items=(
            ('OBJ', 'Object', 'Object will be exported as a mesh or a dummy'),
            ('COL', 'Collision Object', 'Object is a collision object'),
            ('SHA', 'Shadow Object', 'Object is a shadow object'),
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

    def register():
        bpy.types.Object.dff = bpy.props.PointerProperty(type=DFFObjectProps)

# Register the SA Effects along with DemonFF
def register():
    register_saeffects()
    bpy.utils.register_class(MATERIAL_PT_dffMaterials)
    bpy.utils.register_class(DFF_MT_ExportChoice)
    bpy.utils.register_class(OBJECT_PT_dffObjects)
    bpy.utils.register_class(DFFMaterialProps)
    bpy.utils.register_class(DFFObjectProps)
    bpy.utils.register_class(OBJECT_OT_join_similar_named_meshes)
    bpy.utils.register_class(OBJECT_PT_join_similar_meshes_panel)

def unregister():
    unregister_saeffects()
    bpy.utils.unregister_class(MATERIAL_PT_dffMaterials)
    bpy.utils.unregister_class(DFF_MT_ExportChoice)
    bpy.utils.unregister_class(OBJECT_PT_dffObjects)
    bpy.utils.unregister_class(DFFMaterialProps)
    bpy.utils.unregister_class(DFFObjectProps)
    bpy.utils.unregister_class(OBJECT_OT_join_similar_named_meshes)
    bpy.utils.unregister_class(OBJECT_PT_join_similar_meshes_panel)

if __name__ == "__main__":
    register()
