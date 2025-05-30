# DemonFF - Blender scripts for working with Renderware & R*/SA-MP/open.mp formats in Blender
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

# See: https://gtamods.com/wiki/2d_Effect_(RW_Section)

import bpy

from bpy_extras.io_utils import ImportHelper

from ..gtaLib import txd

particle_txd_names = [
    'wincrack_32', 'white', 'waterwake', 'waterclear256', 'txgrassbig1',
    'txgrassbig0', 'target256', 'shad_rcbaron', 'shad_ped', 'shad_heli',
    'shad_exp', 'shad_car', 'shad_bike', 'seabd32', 'roadsignfont',
    'particleskid', 'lunar', 'lockonFire', 'lockon', 'lamp_shad_64',
    'headlight1', 'headlight', 'handman', 'finishFlag', 'coronastar',
    'coronaringb', 'coronareflect', 'coronamoon', 'coronaheadlightline', 'cloudmasked',
    'cloudhigh', 'cloud1', 'carfx1', 'bloodpool_64'
]

#######################################################
def particle_txd_search_func(props, context, edit_text):
    return particle_txd_names

#######################################################
class IMPORT_OT_ParticleTXDNames(bpy.types.Operator, ImportHelper):

    bl_idname = "import.particle_txd_names"
    bl_label = "Import texture names from particle.txd"
    bl_description = 'Import texture names from particle.txd'

    filename : bpy.props.StringProperty(subtype='FILE_PATH')

    filter_glob : bpy.props.StringProperty(default="*.txd",
                                              options={'HIDDEN'})

    def execute(self, context):
        global particle_txd_names
        txd_file = txd.txd()
        txd_file.load_file(self.filepath)
        particle_txd_names = [tex.name for tex in txd_file.native_textures]
        return {'FINISHED'}

#######################################################
class EXT2DFXObjectProps(bpy.types.PropertyGroup):

    effect : bpy.props.EnumProperty(
            items = (
                ('0', 'Light', 'Light'),
                ('1', 'Particle', 'Particle'),
                ('3', 'Ped Attractor', 'Ped Attractor'),
                ('4', 'Sun Glare', 'Sun Glare'),
                ('6', 'Enter Exit', 'Enter Exit'),
                ('7', 'Road Sign', 'Road Sign'),
                ('8', 'Trigger Point', 'Trigger Point'),
                ('9', 'Cover Point', 'Cover Point'),
                ('10', 'Escalator', 'Escalator')
            )
        )

    val_byte_1 : bpy.props.IntProperty(min = 0, max = 255)
    val_byte_2 : bpy.props.IntProperty(min = 0, max = 255)
    val_byte_3 : bpy.props.IntProperty(min = 0, max = 255)
    val_byte_4 : bpy.props.IntProperty(min = 0, max = 255)

    val_short_1 : bpy.props.IntProperty(min = 0, max = 65535)

    val_int_1 : bpy.props.IntProperty()

    val_float_1 : bpy.props.FloatProperty()
    val_float_2 : bpy.props.FloatProperty()

    val_str8_1 : bpy.props.StringProperty(maxlen = 7)

    val_str24_1 : bpy.props.StringProperty(maxlen = 23)

    val_vector_1 : bpy.props.FloatVectorProperty(default = [0, 0, 0])

    val_degree_1 : bpy.props.FloatProperty(
        min = -180,
        max = 180
    )

    val_degree_2 : bpy.props.FloatProperty(
        min = -180,
        max = 180
    )

    val_hour_1 : bpy.props.IntProperty(min = 0, max = 24)
    val_hour_2 : bpy.props.IntProperty(min = 0, max = 24)

    standart_pos: bpy.props.FloatVectorProperty(name="Standard Position", size=3)
    bottom_pos: bpy.props.FloatVectorProperty(name="Bottom Position", size=3)
    top_pos: bpy.props.FloatVectorProperty(name="Top Position", size=3)
    end_pos: bpy.props.FloatVectorProperty(name="End Position", size=3)

    standart_pos_rotation: bpy.props.FloatProperty(name="Standard Rotation")
    standart_pos_pitch: bpy.props.FloatProperty(name="Standard Pitch")
    standart_pos_yaw: bpy.props.FloatProperty(name="Standard Yaw")

    bottom_rotation: bpy.props.FloatProperty(name="Bottom Rotation")
    bottom_pitch: bpy.props.FloatProperty(name="Bottom Pitch")
    bottom_yaw: bpy.props.FloatProperty(name="Bottom Yaw")

    top_rotation: bpy.props.FloatProperty(name="Top Rotation")
    top_pitch: bpy.props.FloatProperty(name="Top Pitch")
    top_yaw: bpy.props.FloatProperty(name="Top Yaw")

    end_rotation: bpy.props.FloatProperty(name="End Rotation")
    end_pitch: bpy.props.FloatProperty(name="End Pitch")
    end_yaw: bpy.props.FloatProperty(name="End Yaw")

    direction: bpy.props.EnumProperty(
        name="Direction",
        items=[('0', 'Down', ''), ('1', 'Up', '')],
        default='1'
    )

    queue_dir: bpy.props.FloatVectorProperty(name="Queue Direction", size=3)
    use_dir: bpy.props.FloatVectorProperty(name="Use Direction", size=3)
    forward_dir: bpy.props.FloatVectorProperty(name="Forward Direction", size=3)
    script_name: bpy.props.StringProperty(name="External Script", maxlen=8)
    ped_probability: bpy.props.IntProperty(name="Ped Spawn Chance", min=0, max=100)
    attractor_type: bpy.props.IntProperty(name="Attractor Type", min=0, max=9)

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

    corona_tex_name : bpy.props.StringProperty(
        maxlen = 23,
        description = "Corona texture name in particle.txd",
        search = particle_txd_search_func
    )

    shadow_tex_name : bpy.props.StringProperty(
        maxlen = 23,
        description = "Shadow texture name in particle.txd",
        search = particle_txd_search_func
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

    #######################################################
    def register():
        bpy.types.Light.ext_2dfx = bpy.props.PointerProperty(type=Light2DFXObjectProps)
#######################################################
class EXT2DFXMenus:

    #######################################################
    def draw_light_menu(layout, context):
        obj = context.object
        box = layout.box()

        if obj.type != 'LIGHT':
            box.label(text="This effect is only available for light objects", icon="ERROR")
            return

        settings = obj.data.ext_2dfx

        box.prop(obj.data, "color", text="Color")
        box.prop(settings, "alpha", text="Alpha")
        box.prop(settings, "point_light_range", text="Point Light Range")
        box.prop(settings, "export_view_vector", text="Export View Vector")
        if settings.export_view_vector:
            box.prop(settings, "view_vector", text="View Vector")

        box = layout.box()
        box.label(text="Corona")
        box.prop(settings, "corona_show_mode", text="Show Mode")
        box.prop(settings, "corona_far_clip", text="Far Clip")
        box.prop(settings, "corona_size", text="Size")
        box.prop(settings, "corona_enable_reflection", text="Enable Reflection")
        box.prop(settings, "corona_flare_type", text="Flare Type")
        box.prop(settings, "corona_tex_name", text="Texture")

        box = layout.box()
        box.label(text="Shadow")
        box.prop(settings, "shadow_size", text="Size")
        box.prop(settings, "shadow_color_multiplier", text="Color Multiplier")
        box.prop(settings, "shadow_z_distance", text="Z Distance")
        box.prop(settings, "shadow_tex_name", text="Texture")

        box = layout.box()
        box.label(text="Flags")
        box.prop(settings, "flag1_corona_check_obstacles", text="Corona Check Obstacles")
        box.prop(settings, "flag1_fog_type", text="Fog Type")
        box.prop(settings, "flag1_without_corona", text="Without Corona")
        box.prop(settings, "flag1_corona_only_at_long_distance", text="Corona Only At Long Distance")
        box.prop(settings, "flag2_corona_only_from_below", text="Corona Only From Below")
        box.prop(settings, "flag1_at_day", text="At Day")
        box.prop(settings, "flag1_at_night", text="At Night")
        box.prop(settings, "flag2_udpdate_height_above_ground", text="Udpdate Height Above Ground")
        box.prop(settings, "flag2_check_view_vector", text="Check View Vector")
        box.prop(settings, "flag1_blinking1", text="Blinking 1")
        box.prop(settings, "flag2_blinking2", text="Blinking 2")
        box.prop(settings, "flag2_blinking3", text="Blinking 3")

        box = layout.box()
        box.operator(IMPORT_OT_ParticleTXDNames.bl_idname)

    #######################################################
    def draw_particle_menu(layout, context):
        obj = context.object
        settings = obj.dff.ext_2dfx
        box.label(text="Particle Settings", icon='FORCE_FORCE')

        box = layout.box()
        box.prop(settings, "val_str24_1", text="Effect Name")

    #######################################################
    def draw_ped_attractor_menu(layout, context):
        obj = context.object
        settings = obj.dff.ext_2dfx

        box = layout.box()
        box.label(text="Ped Attractor Settings", icon='ARMATURE_DATA')
        box.prop(settings, "attractor_type", text="Attractor Type")         # int32
        box.prop(settings, "ped_probability", text="Ped Spawn Probability") # int32
        box.prop(settings, "queue_dir", text="Queue Direction")             # Vector3
        box.prop(settings, "use_dir", text="Use Direction")                 # Vector3
        box.prop(settings, "forward_dir", text="Forward Direction")         # Vector3
        box.prop(settings, "script_name", text="External Script")           # CHAR[8]
        box.prop(settings, "val_byte_1", text="Unknown Byte 1")             # BYTE
        box.prop(settings, "val_byte_2", text="Unused Byte 2")              # BYTE
        box.prop(settings, "val_byte_3", text="Unknown Byte 3")             # BYTE
        box.prop(settings, "val_byte_4", text="Unused Byte 4")              # BYTE


    #######################################################
    def draw_sun_glare_menu(layout, context):
        layout.label(text="Sun Glare Settings", icon='LIGHT_SUN')
        pass
    #######################################################   
    def draw_enter_exit_menu(layout, context):
        obj = context.object
        settings = obj.dff.ext_2dfx

        box = layout.box()
        box.prop(settings, "val_degree_1", text="Enter Angle")
        box.prop(settings, "val_float_1", text="Approximation Radius X")
        box.prop(settings, "val_float_2", text="Approximation Radius Y")
        box.prop(settings, "val_vector_1", text="Exit Location")
        box.prop(settings, "val_degree_2", text="Exit Angle")
        box.prop(settings, "val_short_1", text="Interior")
        box.prop(settings, "val_byte_1", text="Flags")
        box.prop(settings, "val_byte_2", text="Sky Color")
        box.prop(settings, "val_str8_1", text="Interior Name")
        box.prop(settings, "val_hour_1", text="Time On")
        box.prop(settings, "val_hour_2", text="Time Off")
        box.prop(settings, "val_byte_3", text="Flags 2")
        box.prop(settings, "val_byte_4", text="Unknown")

    #######################################################
    def draw_road_sign_menu(layout, context):
        obj = context.object
        box = layout.box()
        box.label(text="Road Sign Settings", icon='FONT_DATA')


        if obj.type != 'FONT':
            box.label(text="This effect is only available for text objects", icon="ERROR")
            return

        settings = obj.data.ext_2dfx

        box.prop(settings, "size", text="Size")
        box.prop(settings, "color", text="Color")
    #######################################################
    def draw_trigger_point_menu(layout, context):
        obj = context.object
        settings = obj.dff.ext_2dfx
        box.label(text="Trigger Point Settings", icon='KEYFRAME')


        box = layout.box()
        box.prop(settings, "val_int_1", text="Point ID")

    #######################################################
    def draw_cover_point_menu(layout, context):
        obj = context.object
        settings = obj.dff.ext_2dfx
        box.label(text="Cover Point Settings", icon='MOD_PHYSICS')

        box = layout.box()
        box.prop(settings, "val_int_1", text="Cover Type")
    #######################################################
    def draw_escalator_menu(layout, context):
        obj = context.object

        if not obj or obj.type != 'EMPTY':
            layout.label(text="This effect is only available for empty objects", icon="ERROR")
            return


        settings = obj.dff.ext_2dfx

        box = layout.box()
        box.label(text="Escalator Settings", icon="MOD_ARRAY")

        # Standard Position
        col = box.column()
        col.label(text="Standard Position:")
        col.prop(settings, "standart_pos", text="Vector")
        col.prop(settings, "standart_pos_rotation")
        col.prop(settings, "standart_pos_pitch")
        col.prop(settings, "standart_pos_yaw")

        # Bottom Position
        col = box.column()
        col.label(text="Bottom Position:")
        col.prop(settings, "bottom_pos", text="Vector")
        col.prop(settings, "bottom_rotation")
        col.prop(settings, "bottom_pitch")
        col.prop(settings, "bottom_yaw")

        # Top Position
        col = box.column()
        col.label(text="Top Position:")
        col.prop(settings, "top_pos", text="Vector")
        col.prop(settings, "top_rotation")
        col.prop(settings, "top_pitch")
        col.prop(settings, "top_yaw")

        # End Position
        col = box.column()
        col.label(text="End Position:")
        col.prop(settings, "end_pos", text="Vector")
        col.prop(settings, "end_rotation")
        col.prop(settings, "end_pitch")
        col.prop(settings, "end_yaw")

        # Direction
        box.prop(settings, "direction", text="Direction")

    #######################################################
    def draw_menu(effect, layout, context):
        self = EXT2DFXMenus

        functions = {
            0: self.draw_light_menu,
            1: self.draw_particle_menu,
            3: self.draw_ped_attractor_menu,
            4: self.draw_sun_glare_menu,
            6: self.draw_enter_exit_menu,
            7: self.draw_road_sign_menu,
            8: self.draw_trigger_point_menu,
            9: self.draw_cover_point_menu,
            10: self.draw_escalator_menu,
        }

        functions[effect](layout, context)

def register():
    bpy.utils.register_class(IMPORT_OT_ParticleTXDNames)

def unregister():
    bpy.utils.unregister_class(IMPORT_OT_ParticleTXDNames)
    del bpy.types.Object.ext_2dfx

if __name__ == "__main__":
    register()
