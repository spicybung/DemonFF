import bpy
import struct
from bpy.props import StringProperty, FloatProperty, FloatVectorProperty
from bpy.types import Operator, Panel, PropertyGroup

# Global variables
fx_images = ["coronastar", "shad_exp"]
fx_psystems = ["prt_blood", "prt_boatsplash"]
effectfile = ""
textfile = ""  # New variable to hold the path to the .txt file

# Function to add light info to selected light objects
def add_light_info(context, obj=None):
    if obj is None:
        objs = context.selected_objects
    else:
        objs = [obj]
    for obj in objs:
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
def add_particle_info(context, obj=None):
    if obj is None:
        objs = context.selected_objects
    else:
        objs = [obj]
    for obj in objs:
        if obj.type == 'EMPTY':
            obj["sdfx_psys"] = fx_psystems[0]  # Default particle system
            print(f"Added GTA Particle system info to {obj.name}")

# Function to add escalator info to selected objects
def add_escalator_info(context, obj=None):
    if obj is None:
        objs = context.selected_objects
    else:
        objs = [obj]
    for obj in objs:
        if obj.type in ['MESH', 'EMPTY']:
            obj["sdfx_escalator_bottom"] = obj.location[:]  # Default bottom position
            obj["sdfx_escalator_top"] = (obj.location.x, obj.location.y, obj.location.z + 10.0)  # Default top position
            obj["sdfx_escalator_end"] = (obj.location.x, obj.location.y, obj.location.z + 10.0)  # Default end position
            obj["sdfx_escalator_direction"] = 1  # Default direction (up)
            print(f"Added GTA Escalator info to {obj.name}")

# Function to export info to a binary file
def export_info(context):
    global effectfile
    global textfile
    obj_to_exp = [obj for obj in context.selected_objects if any(key.startswith("sdfx_") for key in obj.keys()) or obj.type in ['LIGHT', 'EMPTY', 'MESH']]
    
    if not obj_to_exp:
        print("No objects with relevant properties found for export.")
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
            elif obj.get("sdfx_escalator_bottom"):
                export_escalator_info(effect_stream, None, obj)

# Function to export info to a text file
def export_text(context):
    global textfile
    obj_to_exp = [obj for obj in context.selected_objects if any(key.startswith("sdfx_") for key in obj.keys()) or obj.type in ['LIGHT', 'EMPTY', 'MESH']]
    
    if not obj_to_exp:
        print("No objects with relevant properties found for export.")
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
            elif obj.get("sdfx_escalator_bottom"):
                export_escalator_info(None, text_stream, obj)

def export_light_info(effect_stream, text_stream, obj):
    pos = obj.location
    color = obj.get("sdfx_color", (255, 255, 255, 255))
    corona_far_clip = obj.get("sdfx_drawdis", 100.0)
    pointlight_range = obj.get("sdfx_outerrange", 18.0)
    corona_size = obj.get("sdfx_size", 1.0)
    shadow_size = obj.get("sdfx_innerrange", 8.0)
    corona_show_mode = obj.get("sdfx_showmode", 4)
    corona_enable_reflection = obj.get("sdfx_reflection", 0)
    corona_flare_type = obj.get("sdfx_flaretype", 0)
    shadow_color_multiplier = obj.get("sdfx_shadcolormp", 40)
    flags1 = obj.get("sdfx_OnAllDay", 1)
    corona_tex_name = obj.get("sdfx_corona", "coronastar")
    shadow_tex_name = obj.get("sdfx_shad", "shad_exp")
    shadow_z_distance = obj.get("sdfx_shadowzdist", 0)
    flags2 = obj.get("sdfx_flags2", 0)
    view_vector = obj.get("sdfx_viewvector", (0, 156, 0))

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
    psys = obj.get("sdfx_psys", fx_psystems[0])
    print(f"Particle Position: {pos}, Particle System: {psys}")

    if effect_stream:
        effect_stream.write(bytearray(struct.pack("f", pos.x)))
        effect_stream.write(bytearray(struct.pack("f", pos.y)))
        effect_stream.write(bytearray(struct.pack("f", pos.z)))
        effect_stream.write(len(psys).to_bytes(4, byteorder='little'))
        effect_stream.write(psys.encode('utf-8'))

    if text_stream:
        text_stream.write(f"2dfxType         PARTICLE\n")
        text_stream.write(f"Position         {pos.x} {pos.y} {pos.z}\n")
        text_stream.write(f"ParticleSystem   {psys}\n")

def export_text_info(effect_stream, text_stream, obj):
    pos = obj.location
    text_data = (obj.get("sdfx_text1", "") +
                 obj.get("sdfx_text2", "") +
                 obj.get("sdfx_text3", "") +
                 obj.get("sdfx_text4", ""))
    print(f"Text Position: {pos}, Text Data: {text_data}")

    if effect_stream:
        effect_stream.write(bytearray(struct.pack("f", pos.x)))
        effect_stream.write(bytearray(struct.pack("f", pos.y)))
        effect_stream.write(bytearray(struct.pack("f", pos.z)))
        effect_stream.write(len(text_data).to_bytes(4, byteorder='little'))
        effect_stream.write(text_data.encode('utf-8'))

    if text_stream:
        text_stream.write(f"2dfxType         TEXT\n")
        text_stream.write(f"Position         {pos.x} {pos.y} {pos.z}\n")
        text_stream.write(f"TextData         {text_data}\n")

def export_escalator_info(effect_stream, text_stream, obj):
    bottom = obj.get("sdfx_escalator_bottom", obj.location[:])
    top = obj.get("sdfx_escalator_top", (obj.location.x, obj.location.y, obj.location.z + 10.0))
    end = obj.get("sdfx_escalator_end", (obj.location.x, obj.location.y, obj.location.z + 10.0))
    direction = obj.get("sdfx_escalator_direction", 1)

    print(f"Escalator Bottom: {bottom}, Top: {top}, End: {end}, Direction: {direction}")

    if effect_stream:
        effect_stream.write(bytearray(struct.pack("f", bottom[0])))
        effect_stream.write(bytearray(struct.pack("f", bottom[1])))
        effect_stream.write(bytearray(struct.pack("f", bottom[2])))
        effect_stream.write(bytearray(struct.pack("f", top[0])))
        effect_stream.write(bytearray(struct.pack("f", top[1])))
        effect_stream.write(bytearray(struct.pack("f", top[2])))
        effect_stream.write(bytearray(struct.pack("f", end[0])))
        effect_stream.write(bytearray(struct.pack("f", end[1])))
        effect_stream.write(bytearray(struct.pack("f", end[2])))
        effect_stream.write(bytearray(struct.pack("I", direction)))

    if text_stream:
        text_stream.write(f"2dfxType         ESCALATOR\n")
        text_stream.write(f"Bottom           {bottom[0]} {bottom[1]} {bottom[2]}\n")
        text_stream.write(f"Top              {top[0]} {top[1]} {top[2]}\n")
        text_stream.write(f"End              {end[0]} {end[1]} {end[2]}\n")
        text_stream.write(f"Direction        {direction}\n")

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

class DFF2DFX_PT_Panel(Panel):
    bl_label = "DemonFF - 2DFX"
    bl_idname = "DFF2DFX_PT_Panel"
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
        row.operator("saeffects.add_escalator_info", text="Add Escalator Info")
        row = box.row()
        row.operator("saeffects.add_text_info", text="Add 2D Text Info")
        
        row = box.row()
        row.operator("saeffects.set_escalator_bottom", text="Set Escalator Bottom")
        row = box.row()
        row.operator("saeffects.set_escalator_top", text="Set Escalator Top")
        row = box.row()
        row.operator("saeffects.set_escalator_end", text="Set Escalator End")

        row = box.row()
        row.prop(context.scene, "saeffects_export_path")
        row = box.row()
        row.prop(context.scene, "saeffects_text_export_path")
        row = box.row()
        row.operator("saeffects.export_info", text="Export Binary Info")
        row = box.row()
        row.operator("saeffects.export_text_info", text="Export Text Info")
        row = box.row()
        row.operator("saeffects.export_escalator_info", text="Export Escalator Info")
        row = box.row()
        row.operator("saeffects.create_lights_from_omni", text="Create Lights from Omni Frames")
        row = box.row()
        row.operator("saeffects.view_light_info", text="View Light Info")
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

class SAEFFECTS_OT_AddEscalatorInfo(Operator):
    bl_idname = "saeffects.add_escalator_info"
    bl_label = "Add Escalator Info"
    
    def execute(self, context):
        add_escalator_info(context)
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

class SAEFFECTS_OT_ExportEscalatorInfo(Operator):
    bl_idname = "saeffects.export_escalator_info"
    bl_label = "Export Escalator Info"
    
    filepath: StringProperty(subtype="FILE_PATH")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        global effectfile
        effectfile = self.filepath
        export_info(context)
        return {'FINISHED'}

class SAEFFECTS_OT_CreateLightsFromOmni(Operator):
    bl_idname = "saeffects.create_lights_from_omni"
    bl_label = "Create Lights from Omni Frames"
    
    def execute(self, context):
        create_lights_from_omni_frames()
        return {'FINISHED'}

class SAEFFECTS_OT_ViewLightInfo(Operator):
    bl_idname = "saeffects.view_light_info"
    bl_label = "View Light Info"

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type == 'LIGHT':
                context.view_layer.objects.active = obj
                bpy.ops.wm.properties_add(data_path='object')
        return {'FINISHED'}

class OBJECT_PT_SDFXLightInfoPanel(Panel):
    bl_label = "SDFX Light Info"
    bl_idname = "OBJECT_PT_sdfx_light_info"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'LIGHT' and "sdfx_drawdis" in context.object
    
    def draw(self, context):
        layout = self.layout
        obj = context.object
        
        layout.prop(obj, '["sdfx_drawdis"]', text="Draw Distance")
        layout.prop(obj, '["sdfx_outerrange"]', text="Outer Range")
        layout.prop(obj, '["sdfx_size"]', text="Size")
        layout.prop(obj, '["sdfx_innerrange"]', text="Inner Range")
        layout.prop(obj, '["sdfx_corona"]', text="Corona")
        layout.prop(obj, '["sdfx_shad"]', text="Shadow")
        layout.prop(obj, '["sdfx_lighttype"]', text="Light Type")
        layout.prop(obj, '["sdfx_color"]', text="Color")
        layout.prop(obj, '["sdfx_OnAllDay"]', text="On All Day")
        layout.prop(obj, '["sdfx_showmode"]', text="Show Mode")
        layout.prop(obj, '["sdfx_reflection"]', text="Reflection")
        layout.prop(obj, '["sdfx_flaretype"]', text="Flare Type")
        layout.prop(obj, '["sdfx_shadcolormp"]', text="Shadow Color Multiplier")
        layout.prop(obj, '["sdfx_shadowzdist"]', text="Shadow Z Distance")
        layout.prop(obj, '["sdfx_flags2"]', text="Flags 2")
        layout.prop(obj, '["sdfx_viewvector"]', text="View Vector")

#######################################################
# Operators to set escalator positions

class SAEFFECTS_OT_SetEscalatorBottom(Operator):
    bl_idname = "saeffects.set_escalator_bottom"
    bl_label = "Set Escalator Bottom"
    
    def execute(self, context):
        for obj in context.selected_objects:
            obj["sdfx_escalator_bottom"] = obj.location[:]
            print(f"Set Escalator Bottom for {obj.name} to {obj.location[:]}")
        return {'FINISHED'}

class SAEFFECTS_OT_SetEscalatorTop(Operator):
    bl_idname = "saeffects.set_escalator_top"
    bl_label = "Set Escalator Top"
    
    def execute(self, context):
        for obj in context.selected_objects:
            obj["sdfx_escalator_top"] = obj.location[:]
            print(f"Set Escalator Top for {obj.name} to {obj.location[:]}")
        return {'FINISHED'}

class SAEFFECTS_OT_SetEscalatorEnd(Operator):
    bl_idname = "saeffects.set_escalator_end"
    bl_label = "Set Escalator End"
    
    def execute(self, context):
        for obj in context.selected_objects:
            obj["sdfx_escalator_end"] = obj.location[:]
            print(f"Set Escalator End for {obj.name} to {obj.location[:]}")
        return {'FINISHED'}

#######################################################

def register():
    bpy.utils.register_class(DFF2DFX_PT_Panel)
    bpy.utils.register_class(SAEFFECTS_OT_AddLightInfo)
    bpy.utils.register_class(SAEFFECTS_OT_AddParticleInfo)
    bpy.utils.register_class(SAEFFECTS_OT_AddEscalatorInfo)
    bpy.utils.register_class(SAEFFECTS_OT_AddTextInfo)
    bpy.utils.register_class(SAEFFECTS_OT_ExportInfo)
    bpy.utils.register_class(SAEFFECTS_OT_ExportTextInfo)
    bpy.utils.register_class(SAEFFECTS_OT_ExportEscalatorInfo)
    bpy.utils.register_class(SAEFFECTS_OT_CreateLightsFromOmni)
    bpy.utils.register_class(SAEFFECTS_OT_ViewLightInfo)
    bpy.utils.register_class(SAEFFECTS_OT_Import2dfx)
    bpy.utils.register_class(OBJECT_PT_SDFXLightInfoPanel)
    bpy.utils.register_class(SAEFFECTS_OT_SetEscalatorBottom)
    bpy.utils.register_class(SAEFFECTS_OT_SetEscalatorTop)
    bpy.utils.register_class(SAEFFECTS_OT_SetEscalatorEnd)
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
    bpy.utils.unregister_class(DFF2DFX_PT_Panel)
    bpy.utils.unregister_class(SAEFFECTS_OT_AddLightInfo)
    bpy.utils.unregister_class(SAEFFECTS_OT_AddParticleInfo)
    bpy.utils.unregister_class(SAEFFECTS_OT_AddEscalatorInfo)
    bpy.utils.unregister_class(SAEFFECTS_OT_AddTextInfo)
    bpy.utils.unregister_class(SAEFFECTS_OT_ExportInfo)
    bpy.utils.unregister_class(SAEFFECTS_OT_ExportTextInfo)
    bpy.utils.unregister_class(SAEFFECTS_OT_ExportEscalatorInfo)
    bpy.utils.unregister_class(SAEFFECTS_OT_CreateLightsFromOmni)
    bpy.utils.unregister_class(SAEFFECTS_OT_ViewLightInfo)
    bpy.utils.unregister_class(SAEFFECTS_OT_Import2dfx)
    bpy.utils.unregister_class(OBJECT_PT_SDFXLightInfoPanel)
    bpy.utils.unregister_class(SAEFFECTS_OT_SetEscalatorBottom)
    bpy.utils.unregister_class(SAEFFECTS_OT_SetEscalatorTop)
    bpy.utils.unregister_class(SAEFFECTS_OT_SetEscalatorEnd)
    del bpy.types.Scene.saeffects_export_path
    del bpy.types.Scene.saeffects_text_export_path

#######################################################

if __name__ == "__main__":
    register()
