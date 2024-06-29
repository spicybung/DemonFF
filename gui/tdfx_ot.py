import bpy
import struct
from bpy.props import StringProperty
from bpy.types import Operator, Panel

# Global variables
fx_images = ["coronastar", "shad_exp"]
fx_psystems = ["prt_blood", "prt_boatsplash"]
effectfile = ""
textfile = ""  # New variable to hold the path to the .txt file

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

    with open(effectfile, "wb") as effect_stream:
        # Write header info for binary file
        effect_stream.write(len(obj_to_exp).to_bytes(4, byteorder='little'))
        print(f"Number of objects to export: {len(obj_to_exp)}")
        
        for i, obj in enumerate(obj_to_exp, start=1):
            if obj.type == 'LIGHT':
                export_light_info(effect_stream, None, obj)
            elif obj.type == 'EMPTY':
                export_particle_info(effect_stream, None, obj)
            elif obj.type == 'MESH' and "Plane" in obj.name:
                export_text_info(effect_stream, None, obj)

# Function to export info to a text file
def export_text(context):
    global textfile
    obj_to_exp = [obj for obj in context.selected_objects if any(key.startswith("sdfx_") for key in obj.keys())]
    
    if not obj_to_exp:
        print("No objects with custom properties found for export.")
        return

    with open(textfile, "w") as text_stream:
        # Write header info for text file
        text_stream.write(f"NumEntries {len(obj_to_exp)}\n")
        print(f"Number of objects to export: {len(obj_to_exp)}")
        
        for i, obj in enumerate(obj_to_exp, start=1):
            print(f"Exporting object: {obj.name}, Type: {obj.type}")
            text_stream.write(f"######################### {i} #########################\n")
            if obj.type == 'LIGHT':
                export_light_info(None, text_stream, obj)
            elif obj.type == 'EMPTY':
                export_particle_info(None, text_stream, obj)
            elif obj.type == 'MESH' and "Plane" in obj.name:
                export_text_info(None, text_stream, obj)

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

    if effect_stream:
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

    if text_stream:
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

    if effect_stream:
        effect_stream.write(bytearray(struct.pack("f", pos.x)))
        effect_stream.write(bytearray(struct.pack("f", pos.y)))
        effect_stream.write(bytearray(struct.pack("f", pos.z)))
        effect_stream.write(len(obj["sdfx_psys"]).to_bytes(4, byteorder='little'))
        effect_stream.write(obj["sdfx_psys"].encode('utf-8'))

    if text_stream:
        text_stream.write(f"2dfxType         PARTICLE\n")
        text_stream.write(f"Position         {pos.x} {pos.y} {pos.z}\n")
        text_stream.write(f"ParticleSystem   {obj['sdfx_psys']}\n")

def export_text_info(effect_stream, text_stream, obj):
    pos = obj.location
    print(f"Text Position: {pos}")

    if effect_stream:
        effect_stream.write(bytearray(struct.pack("f", pos.x)))
        effect_stream.write(bytearray(struct.pack("f", pos.y)))
        effect_stream.write(bytearray(struct.pack("f", pos.z)))
        text_data = obj["sdfx_text1"] + obj["sdfx_text2"] + obj["sdfx_text3"] + obj["sdfx_text4"]
        effect_stream.write(len(text_data).to_bytes(4, byteorder='little'))
        effect_stream.write(text_data.encode('utf-8'))

    if text_stream:
        text_stream.write(f"2dfxType         TEXT\n")
        text_stream.write(f"Position         {pos.x} {pos.y} {pos.z}\n")
        text_stream.write(f"TextData         {obj['sdfx_text1']} {obj['sdfx_text2']} {obj['sdfx_text3']} {obj['sdfx_text4']}\n")

# Function to create lights from frames named "Omni"
def create_lights_from_omni_frames():
    for obj in bpy.data.objects:
        if "Omni" in obj.name:
            print(f"Found frame named 'Omni': {obj.name}")
            # Create a new light object
            bpy.ops.object.light_add(type='POINT', location=obj.location)
            light = bpy.context.object
            light.name = obj.name + "_Light"
            # Add the light info properties
            add_light_info(bpy.context)
            print(f"Created light for frame: {obj.name}, at location {obj.location}")

# Function to import 2DFX files and create lights
def import_2dfx(filepath):
    with open(filepath, 'r', encoding='latin-1') as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if parts[0] == "2dfxType" and parts[1] == "LIGHT":
                # Read the position and create a light
                pos_x = float(parts[3])
                pos_y = float(parts[4])
                pos_z = float(parts[5])
                bpy.ops.object.light_add(type='POINT', location=(pos_x, pos_y, pos_z))
                light = bpy.context.object
                light.name = f"Imported_Light_{len(bpy.data.objects)}"
                add_light_info(bpy.context)
                print(f"Created light at position ({pos_x}, {pos_y}, {pos_z})")

class SAEFFECTS_OT_Import2dfx(Operator):
    bl_idname = "saeffects.import_2dfx"
    bl_label = "Import 2DFX File"
    
    filename_ext = ".2dfx"
    filter_glob: StringProperty(default="*.2dfx", options={'HIDDEN'})
    filepath: StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        import_2dfx(self.filepath)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

#######################################################

class DFF2dfxPanel(Panel):
    bl_label = "DemonFF - 2DFX"
    bl_idname = "PT_DFF2DFX"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    def draw(self, context):
        layout = self.layout

        # Adding SA Effects options
        box = layout.box()
        row = box.row()
        row.operator("saeffects.add_light_info", text="Add Light Info")
        row = box.row()
        row.operator("saeffects.add_particle_info", text="Add Particle Info")
        row = box.row()
        row.operator("saeffects.add_text_info", text="Add 2D Text Info")
        row = box.row()
        row.prop(context.scene, "saeffects_export_path")
        row = box.row()
        row.prop(context.scene, "saeffects_text_export_path")
        row = box.row()
        row.operator("saeffects.export_info", text="Export Binary Info")
        row = box.row()
        row.operator("saeffects.export_text_info", text="Export Text Info")
        row = box.row()
        row.operator("saeffects.create_lights_from_omni", text="Create Lights from Omni Frames")
        row = box.row()
        row.operator("saeffects.import_2dfx", text="Import 2DFX File")

#######################################################

class SAEFFECTS_OT_AddLightInfo(Operator):
    bl_idname = "saeffects.add_light_info"
    bl_label = "Add Light Info"
    
    def execute(self, context):
        add_light_info(context)
        return {'FINISHED'}

class SAEFFECTS_OT_AddParticleInfo(Operator):
    bl_idname = "saeffects.add_particle_info"
    bl_label = "Add Particle Info"
    
    def execute(self, context):
        add_particle_info(context)
        return {'FINISHED'}

class SAEFFECTS_OT_AddTextInfo(Operator):
    bl_idname = "saeffects.add_text_info"
    bl_label = "Add 2D Text Info"
    
    def execute(self, context):
        add_text_info(context)
        return {'FINISHED'}

class SAEFFECTS_OT_ExportInfo(Operator):
    bl_idname = "saeffects.export_info"
    bl_label = "Export Binary Info"
    
    def execute(self, context):
        global effectfile
        effectfile = bpy.path.abspath(context.scene.saeffects_export_path)
        export_info(context)
        return {'FINISHED'}

class SAEFFECTS_OT_ExportTextInfo(Operator):
    bl_idname = "saeffects.export_text_info"
    bl_label = "Export Text Info"
    
    filepath: StringProperty(subtype="FILE_PATH")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        global textfile
        textfile = self.filepath
        export_text(context)
        return {'FINISHED'}

class SAEFFECTS_OT_CreateLightsFromOmni(Operator):
    bl_idname = "saeffects.create_lights_from_omni"
    bl_label = "Create Lights from Omni Frames"
    
    def execute(self, context):
        create_lights_from_omni_frames()
        return {'FINISHED'}

#######################################################

def register():
    bpy.utils.register_class(DFF2dfxPanel)
    bpy.utils.register_class(SAEFFECTS_OT_AddLightInfo)
    bpy.utils.register_class(SAEFFECTS_OT_AddParticleInfo)
    bpy.utils.register_class(SAEFFECTS_OT_AddTextInfo)
    bpy.utils.register_class(SAEFFECTS_OT_ExportInfo)
    bpy.utils.register_class(SAEFFECTS_OT_ExportTextInfo)
    bpy.utils.register_class(SAEFFECTS_OT_CreateLightsFromOmni)
    bpy.utils.register_class(SAEFFECTS_OT_Import2dfx)
    bpy.types.Scene.saeffects_export_path = StringProperty(
        name="Export Path",
        description="Path to export the effects binary file",
        subtype='FILE_PATH'
    )
    bpy.types.Scene.saeffects_text_export_path = StringProperty(
        name="Text Export Path",
        description="Path to export the effects text file",
        subtype='FILE_PATH'
    )

#######################################################

def unregister():
    bpy.utils.unregister_class(DFF2dfxPanel)
    bpy.utils.unregister_class(SAEFFECTS_OT_AddLightInfo)
    bpy.utils.unregister_class(SAEFFECTS_OT_AddParticleInfo)
    bpy.utils.unregister_class(SAEFFECTS_OT_AddTextInfo)
    bpy.utils.unregister_class(SAEFFECTS_OT_ExportInfo)
    bpy.utils.unregister_class(SAEFFECTS_OT_ExportTextInfo)
    bpy.utils.unregister_class(SAEFFECTS_OT_CreateLightsFromOmni)
    bpy.utils.unregister_class(SAEFFECTS_OT_Import2dfx)
    del bpy.types.Scene.saeffects_export_path
    del bpy.types.Scene.saeffects_text_export_path

#######################################################

if __name__ == "__main__":
    register()
