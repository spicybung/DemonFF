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
import struct
import math
import mathutils
from bpy.props import StringProperty, FloatProperty, IntProperty, FloatVectorProperty, BoolProperty
from bpy.types import Operator, Panel, PropertyGroup

#Information taken from https://gtamods.com/wiki/2DFX
# & https://gtamods.com/wiki/2d_Effect_(RW_Section)

global entries
# Global variables
fx_images = ["coronastar", "shad_exp"]
fx_psystems = ["prt_blood", "prt_boatsplash"]
effectfile = ""
textfile = "" 
entries = []

def import_light(entry, collection):
    light_data = bpy.data.lights.new(name="Omni_Light", type='POINT')
    light_object = bpy.data.objects.new(name=f"Omni_Light", object_data=light_data)
    collection.objects.link(light_object)

    # Assign light properties
    light_data.color = (
        entry.color[0] / 255,
        entry.color[1] / 255,
        entry.color[2] / 255,
    )
    light_object.location = entry.loc

    # Add custom properties

    light_object.location = entry.loc
    light_object["sdfx_drawdis"] = entry.corona_far_clip
    light_object["sdfx_outerrange"] = entry.pointlightRange
    light_object["sdfx_size"] = entry.coronaSize
    light_object["sdfx_innerrange"] = entry.shadowSize
    light_object["sdfx_corona"] = entry.coronaTexName
    light_object["sdfx_shad"] = entry.shadowTexName
    light_object["sdfx_OnAllDay"] = entry.coronaEnableReflection != 0
    light_object["sdfx_showmode"] = entry.coronaShowMode
    light_object["sdfx_reflection"] = entry.coronaEnableReflection != 0
    light_object["sdfx_flaretype"] = entry.coronaFlareType
    light_object["sdfx_shadcolormp"] = entry.shadowColorMultiplier
    light_object["sdfx_shadowzdist"] = entry.shadowZDistance
    light_object["sdfx_viewvector"] = entry.lookDirection or (0, 0, 0)

    return light_object


class SAEEFFECTS_OT_CreateLightsFromEntries(Operator):
    """Create lights in Blender from the parsed 2DFX entries."""
    bl_idname = "saeeffects.create_lights_from_entries"
    bl_label = "Create Lights from Entries"

    def execute(self, context):
        global entries

        if not entries:  # Check if entries exist
            self.report({'ERROR'}, "No 2DFX entries available. Import first!")
            return {'CANCELLED'}

        # Create lights for each entry
        collection = context.scene.collection
        for entry in entries:

            light_data = bpy.data.lights.new(name="2DFX_Light", type='POINT')
            light_object = bpy.data.objects.new(name="2DFX_Light", object_data=light_data)
            collection.objects.link(light_object)


            sdfx_color = (
                entry.color[0],  # RGB values in range 0-255
                entry.color[1],
                entry.color[2],
                entry.color[3],  # Alpha value
            )
            light_object["sdfx_color"] = sdfx_color 


            normalized_color = (
                sdfx_color[0] / 255,
                sdfx_color[1] / 255,
                sdfx_color[2] / 255,
            )
            light_data.color = normalized_color

            # Assign other light properties
            light_object.location = entry.loc
            light_object["sdfx_drawdis"] = entry.corona_far_clip
            light_object["sdfx_outerrange"] = entry.pointlightRange
            light_object["sdfx_size"] = entry.coronaSize
            light_object["sdfx_innerrange"] = entry.shadowSize
            light_object["sdfx_corona"] = entry.coronaTexName
            light_object["sdfx_shad"] = entry.shadowTexName
            light_object["sdfx_OnAllDay"] = entry.coronaEnableReflection != 0
            light_object["sdfx_showmode"] = entry.coronaShowMode
            light_object["sdfx_reflection"] = entry.coronaEnableReflection != 0
            light_object["sdfx_flaretype"] = entry.coronaFlareType
            light_object["sdfx_shadcolormp"] = entry.shadowColorMultiplier
            light_object["sdfx_shadowzdist"] = entry.shadowZDistance
            light_object["sdfx_viewvector"] = entry.lookDirection or (0, 0, 0)

        self.report({'INFO'}, f"Created {len(entries)} lights from entries.")
        return {'FINISHED'}




def add_light_info(dff):
    # Determine the collection to which objects will be linked
    if isinstance(frames, bpy.types.Context):
        collection = frames.scene.collection
    elif isinstance(frames, bpy.types.Collection):
        collection = frames
    elif hasattr(frames, "objects"):  # Handles bpy.context.scene.objects or similar
        collection = bpy.context.scene.collection
    elif isinstance(frames, (list, tuple)) and all(isinstance(obj, bpy.types.Object) for obj in frames):
        collection = bpy.context.scene.collection
    else:
        print(f"Warning: Unrecognized 'frames' type ({type(frames)}). Defaulting to scene collection.")
        collection = bpy.context.scene.collection

    # Process each light entry
    for entry in entries:

        light_data = bpy.data.lights.new(name="2DFX_Light", type='POINT')
        light_object = bpy.data.objects.new(name="2DFX_Light", object_data=light_data)
        collection.objects.link(light_object)


        # Debugging information
        print(f"Added Point Light: {light_object.name}")
        print(f"  Position: {light_object.location}")
        print(f"  Color: {light_data.color}")

    for frame, entry in zip(dff):
        light_objects = [obj for obj in frame.objects if obj.type == 'LIGHT']
        if not light_objects:
            print(f"No light objects found in frame: {frame.name}")
            continue

        for obj in light_objects:
            obj["sdfx_drawdis"] = getattr(entry, 'corona_far_clip', 100.0)
            obj["sdfx_outerrange"] = getattr(entry, 'pointlight_range', 18.0)
            obj["sdfx_size"] = getattr(entry, 'corona_size', 1.0)
            obj["sdfx_innerrange"] = getattr(entry, 'shadow_size', 8.0)
            obj["sdfx_corona"] = getattr(entry, 'corona_tex_name', "coronastar")
            obj["sdfx_shad"] = getattr(entry, 'shadow_tex_name', "shad_exp")
            obj["sdfx_lighttype"] = getattr(entry, 'flags1', 1)
            obj["sdfx_color"] = getattr(entry, 'color', (15, 230, 0, 200))
            obj["sdfx_OnAllDay"] = getattr(entry, 'corona_enable_reflection', 1)
            obj["sdfx_showmode"] = getattr(entry, 'corona_show_mode', 4)
            obj["sdfx_reflection"] = getattr(entry, 'corona_enable_reflection', 0)
            obj["sdfx_flaretype"] = getattr(entry, 'corona_flare_type', 0)
            obj["sdfx_shadcolormp"] = getattr(entry, 'shadow_color_multiplier', 40)
            obj["sdfx_shadowzdist"] = getattr(entry, 'shadow_z_distance', 0)
            obj["sdfx_flags2"] = getattr(entry, 'flags2', 0)
            obj["sdfx_viewvector"] = getattr(entry, 'look_direction', (0, 156, 0))

            print(f"Added 2DFX light info to {obj.name} in frame {frame.name}")

def process_2dfx_lights(self, effects, context):
    """
    Process each 2DFX light entry and add it to Blender using add_light_info.

    Args:
        effects: Parsed 2DFX effects containing LightEntries.
        context: Blender context.
    """
    for i, entry in enumerate(effects.entries):
        if entry.effect_id == 0:  # Only process light entries (effect_id = 0)
            print(f"Processing Light Entry {i + 1}/{len(effects.entries)}...")
            add_light_info(context, entry)

def import_2dfx(self, effects, context):
    """
    Import 2DFX effects into Blender.

    Args:
        effects: Parsed 2DFX effects containing entries.
        context: Blender context.
    """
    print("Importing 2DFX effects...")
    self.process_2dfx_lights(effects, context)


def add_particle_info(context, obj=None):
    if obj is None:
        objs = context.selected_objects
    else:
        objs = [obj]
    for obj in objs:
        if obj.type == 'EMPTY':
            obj["sdfx_psys"] = fx_psystems[0]  # Default particle system
            print(f"Added GTA Particle system info to {obj.name}")

def add_text_info(context, obj=None):
    if obj is None:
        objs = context.selected_objects
    else:
        objs = [obj]
    for obj in objs:
        if obj.type == 'MESH' and "Plane" in obj.name:
            obj["sdfx_text1"] = ""
            obj["sdfx_text2"] = ""
            obj["sdfx_text3"] = ""
            obj["sdfx_text4"] = ""
            print(f"Added GTA 2D Text info to {obj.name}")

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

def create_lights_from_omni_frames():
    for obj in bpy.data.objects:
        if "Omni" in obj.name:
            print(f"Found frame named 'Omni': {obj.name}")
            # Create a new light object
            bpy.ops.object.light_add(type='POINT', location=obj.location)
            light = bpy.context.object
            light.name = obj.name + "_Light"
            # Add the light info properties
            add_light_info(bpy.context, light)
            print(f"Created light for frame: {obj.name}, at location {obj.location}")

def import_2dfx(filepath):
    with open(filepath, 'r', encoding='latin-1') as file:
        obj = None
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if parts[0] == "2dfxType":
                obj = bpy.data.objects.new("Imported_Object", None)
                bpy.context.collection.objects.link(obj)
                if parts[1] == "LIGHT":
                    bpy.ops.object.light_add(type='POINT', location=(0, 0, 0))
                    light = bpy.context.object
                    light.name = f"Imported_Light_{len(bpy.data.objects)}"
                    obj = light
                add_light_info(bpy.context, obj)
            if obj and parts[0] == "Position":
                obj.location = (float(parts[1]), float(parts[2]), float(parts[3]))
            elif obj and parts[0] == "Color":
                obj["sdfx_color"] = (int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4]))
            elif obj and parts[0] == "CoronaFarClip":
                obj["sdfx_drawdis"] = float(parts[1])
            elif obj and parts[0] == "PointlightRange":
                obj["sdfx_outerrange"] = float(parts[1])
            elif obj and parts[0] == "CoronaSize":
                obj["sdfx_size"] = float(parts[1])
            elif obj and parts[0] == "ShadowSize":
                obj["sdfx_innerrange"] = float(parts[1])
            elif obj and parts[0] == "CoronaShowMode":
                obj["sdfx_showmode"] = int(parts[1])
            elif obj and parts[0] == "CoronaReflection":
                obj["sdfx_reflection"] = int(parts[1])
            elif obj and parts[0] == "CoronaFlareType":
                obj["sdfx_flaretype"] = int(parts[1])
            elif obj and parts[0] == "ShadowColorMP":
                obj["sdfx_shadcolormp"] = int(parts[1])
            elif obj and parts[0] == "ShadowZDistance":
                obj["sdfx_shadowzdist"] = int(parts[1])
            elif obj and parts[0] == "CoronaTexName":
                obj["sdfx_corona"] = parts[1]
            elif obj and parts[0] == "ShadowTexName":
                obj["sdfx_shad"] = parts[1]
            elif obj and parts[0] == "Flags1":
                obj["sdfx_OnAllDay"] = int(parts[1])
            elif obj and parts[0] == "Flags2":
                obj["sdfx_flags2"] = int(parts[1])
            elif obj and parts[0] == "ViewVector":
                obj["sdfx_viewvector"] = (float(parts[1]), float(parts[2]), float(parts[3]))

#######################################################

class DEMONFF_PT_DFF2DFX(Panel):
    bl_label = "DemonFF - 2DFX"
    bl_idname = "DEMONFF_PT_DFF2DFX"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    def draw(self, context):
        layout = self.layout

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
        row.operator("saeffects.view_light_info", text="View Light Info")

#######################################################

class SAEFFECTS_OT_AddLightInfo(Operator):
    bl_idname = "saeffects.add_light_info"
    bl_label = "Add Light Info"
    

    def execute(self, context):

        entries = []
        frames = context.scene.collection.children 
        add_light_info(dff)
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
        
        # Draw custom properties
        layout.prop(obj, '["sdfx_drawdis"]', text="Draw Distance")
        layout.prop(obj, '["sdfx_outerrange"]', text="Outer Range")
        layout.prop(obj, '["sdfx_size"]', text="Size")
        layout.prop(obj, '["sdfx_innerrange"]', text="Inner Range")
        layout.prop(obj, '["sdfx_corona"]', text="Corona")
        layout.prop(obj, '["sdfx_shad"]', text="Shadow")
        
        layout.prop(obj, '["sdfx_OnAllDay"]', text="On All Day")
        layout.prop(obj, '["sdfx_showmode"]', text="Show Mode")
        layout.prop(obj, '["sdfx_reflection"]', text="Reflection")
        layout.prop(obj, '["sdfx_flaretype"]', text="Flare Type")
        layout.prop(obj, '["sdfx_shadcolormp"]', text="Shadow Color Multiplier")
        layout.prop(obj, '["sdfx_shadowzdist"]', text="Shadow Z Distance")
        layout.prop(obj, '["sdfx_viewvector"]', text="View Vector")

    def set_light_color(obj, color):
        """
        Safely set the color of a Blender light object.
        
        Args:
            obj: The Blender light object.
            color: A tuple (R, G, B) where values are between 0 and 255.
        """
        if obj and obj.type == 'LIGHT':
            # Ensure color is normalized
            normalized_color = (
                color[0] / 255,  # Normalize R
                color[1] / 255,  # Normalize G
                color[2] / 255,  # Normalize B
            )
            obj.data.color = normalized_color


#######################################################

def register():
    bpy.utils.register_class(DFF2dfxPanel)
    bpy.utils.register_class(SAEFFECTS_OT_AddLightInfo)
    bpy.utils.register_class(SAEFFECTS_OT_AddParticleInfo)
    bpy.utils.register_class(SAEFFECTS_OT_AddTextInfo)
    bpy.utils.register_class(SAEFFECTS_OT_ExportInfo)
    bpy.utils.register_class(SAEFFECTS_OT_ExportTextInfo)
    bpy.utils.register_class(SAEFFECTS_OT_CreateLightsFromOmni)
    bpy.utils.register_class(SAEFFECTS_OT_ViewLightInfo)
    bpy.utils.register_class(SAEFFECTS_OT_Import2dfx)
    bpy.utils.register_class(SAEEFFECTS_OT_CreateLightsFromEntries)
    bpy.utils.register_class(OBJECT_PT_SDFXLightInfoPanel)
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
    bpy.utils.unregister_class(SAEFFECTS_OT_ViewLightInfo)
    bpy.utils.unregister_class(SAEFFECTS_OT_Import2dfx)
    bpy.utils.unregister_class(SAEEFFECTS_OT_CreateLightsFromEntries)
    bpy.utils.unregister_class(OBJECT_PT_SDFXLightInfoPanel)
    del bpy.types.Scene.saeffects_export_path
    del bpy.types.Scene.saeffects_text_export_path

#######################################################

if __name__ == "__main__":
    register()
