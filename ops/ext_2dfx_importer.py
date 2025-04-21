# DemonFF - Blender scripts to edit basic GTA formats to work in conjunction with SAMP/open.mp
# 2023 - 2025 SpicyBung

# This is a fork of DragonFF by Parik - maintained by Psycrow, and various others!

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

from mathutils import Vector

from ..gtaLib import dff

#######################################################
def create_arrow_mesh(name):
    arrow_mesh = bpy.data.meshes.get(name)
    if arrow_mesh is None:
        arrow_mesh = bpy.data.meshes.new(name=name)
        verts = [
            (-0.0100, 0.0000, 0.0100),
            (-0.0100, 0.2500, 0.0100),
            (-0.0100, 0.0000, -0.0100),
            (-0.0100, 0.2500, -0.0100),
            (0.0100, 0.0000, 0.0100),
            (0.0100, 0.2500, 0.0100),
            (0.0100, 0.0000, -0.0100),
            (0.0100, 0.2500, -0.0100),
            (-0.0350, 0.2500, 0.0350),
            (-0.0350, 0.2500, -0.0350),
            (0.0350, 0.2500, 0.0350),
            (0.0350, 0.2500, -0.0350),
            (0.0000, 0.5000, 0.0000),
        ]
        edges = []
        faces = [
            (0, 1, 3, 2),
            (2, 3, 7, 6),
            (6, 7, 5, 4),
            (4, 5, 1, 0),
            (3, 1, 8, 9),
            (10, 11, 12),
            (1, 5, 10, 8),
            (7, 3, 9, 11),
            (5, 7, 11, 10),
            (9, 8, 12),
            (8, 10, 12),
            (11, 9, 12),
        ]
        arrow_mesh.from_pydata(verts, edges, faces)

    return arrow_mesh

#######################################################
class ext_2dfx_importer:

    """ Helper class for 2dfx importing """

    #######################################################
    def __init__(self, effects):
        self.effects = effects

    #######################################################
    def import_light(self, entry):
        FL1, FL2 = dff.Light2dfx.Flags1, dff.Light2dfx.Flags2

        data = bpy.data.lights.new(name="2dfx_light", type='POINT')
        data.color = [i / 255 for i in entry.color[:3]]

        settings = data.ext_2dfx
        settings.alpha = entry.color[3] / 255
        settings.corona_far_clip = entry.coronaFarClip
        settings.point_light_range = entry.pointlightRange
        settings.corona_size = entry.coronaSize
        settings.shadow_size = entry.shadowSize
        settings.corona_show_mode = str(entry.coronaShowMode)
        settings.corona_enable_reflection = entry.coronaEnableReflection != 0
        settings.corona_flare_type = entry.coronaFlareType
        settings.shadow_color_multiplier = entry.shadowColorMultiplier
        settings.corona_tex_name = entry.coronaTexName
        settings.shadow_tex_name = entry.shadowTexName
        settings.shadow_z_distance = entry.shadowZDistance

        settings.flag1_corona_check_obstacles = entry.check_flag(FL1.CORONA_CHECK_OBSTACLES)
        settings.flag1_fog_type |= entry.check_flag(FL1.FOG_TYPE)
        settings.flag1_fog_type |= entry.check_flag(FL1.FOG_TYPE2) << 1
        settings.flag1_without_corona = entry.check_flag(FL1.WITHOUT_CORONA)
        settings.flag1_corona_only_at_long_distance = entry.check_flag(FL1.CORONA_ONLY_AT_LONG_DISTANCE)
        settings.flag1_at_day = entry.check_flag(FL1.AT_DAY)
        settings.flag1_at_night = entry.check_flag(FL1.AT_NIGHT)
        settings.flag1_blinking1 = entry.check_flag(FL1.BLINKING1)

        settings.flag2_corona_only_from_below = entry.check_flag2(FL2.CORONA_ONLY_FROM_BELOW)
        settings.flag2_blinking2 = entry.check_flag2(FL2.BLINKING2)
        settings.flag2_udpdate_height_above_ground = entry.check_flag2(FL2.UDPDATE_HEIGHT_ABOVE_GROUND)
        settings.flag2_check_view_vector = entry.check_flag2(FL2.CHECK_DIRECTION)
        settings.flag2_blinking3 = entry.check_flag2(FL2.BLINKING3)

        obj = bpy.data.objects.new("2dfx_light", data)

        if entry.lookDirection is not None:
            settings.view_vector = entry.lookDirection
            settings.export_view_vector = True

        return obj

    #######################################################
    def import_particle(self, entry):
        obj = bpy.data.objects.new("2dfx_particle", None)

        settings = obj.dff.ext_2dfx
        settings.val_str24_1 = entry.effect

        return obj

    #######################################################
    def import_sun_glare(self, entry):
        obj = bpy.data.objects.new("2dfx_sun_glare", None)

        return obj
    #######################################################
    def import_enter_exit(self, entry):
        obj = bpy.data.objects.new("2dfx_enter_exit", None)

        settings = obj.dff.ext_2dfx
        settings.val_degree_1 = math.degrees(entry.enter_angle)
        settings.val_float_1 = entry.approximation_radius_x
        settings.val_float_2 = entry.approximation_radius_y
        settings.val_vector_1 = entry.exit_location
        settings.val_degree_2 = entry.exit_angle
        settings.val_short_1 = entry.interior
        settings.val_byte_1 = entry._flags1
        settings.val_byte_2 = entry.sky_color
        settings.val_str8_1 = entry.interior_name
        settings.val_hour_1 = entry.time_on
        settings.val_hour_2 = entry.time_off
        settings.val_byte_3 = entry._flags2
        settings.val_byte_4 = entry.unk

        return obj

    #######################################################
    def import_road_sign(self, entry):
        lines_num = {0:4, 1:1, 2:2, 3:3}[entry.flags & 0b11]
        max_chars_num = {0:16, 1:2, 2:4, 3:8}[(entry.flags >> 2) & 0b11]

        body = ""
        for line in (entry.text1, entry.text2, entry.text3, entry.text4)[:lines_num]:
            body = body + "\n" if body else body
            body += line.replace("_", " ")[:max_chars_num]

        font = bpy.data.fonts.get("DejaVu Sans Mono Book")
        if not font:
            font_path = os.path.join(bpy.utils.system_resource('DATAFILES'), "fonts", "DejaVuSansMono.woff2")
            if os.path.isfile(font_path):
                font = bpy.data.fonts.load(font_path)

        data = bpy.data.curves.new(name="2dfx_road_sign", type='FONT')
        data.body = body
        data.align_x = data.align_y = 'CENTER'
        data.size = 0.5

        if font:
            data.font = font

        settings = data.ext_2dfx
        settings.size = entry.size
        settings.color = str((entry.flags >> 4) & 0b11)

        obj = bpy.data.objects.new("2dfx_road_sign", data)
        obj.rotation_mode = 'ZXY'
        obj.rotation_euler = Vector((
            entry.rotation.x * (math.pi / 180),
            entry.rotation.y * (math.pi / 180),
            entry.rotation.z * (math.pi / 180)
        ))

        return obj
    #######################################################
    def import_trigger_point(self, entry):
        obj = bpy.data.objects.new("2dfx_trigger_point", None)

        settings = obj.dff.ext_2dfx
        settings.val_int_1 = entry.point_id

        return obj

    #######################################################
    def import_cover_point(self, entry):
        mesh = create_arrow_mesh("_2dfx_cover_point")
        obj = bpy.data.objects.new("2dfx_cover_point", mesh)
        obj.lock_rotation[0] = True
        obj.lock_rotation[1] = True

        settings = obj.dff.ext_2dfx
        settings.val_int_1 = entry.cover_type

        direction = Vector((entry.direction_x, entry.direction_y, 0))
        obj.rotation_euler = direction.to_track_quat('Y', 'Z').to_euler()

        return obj
   #######################################################
    def import_escalator(self, entry):
        # Create the escalator object
        obj = bpy.data.objects.new("2dfx_escalator", None)
        obj.empty_display_type = 'PLAIN_AXES'
        obj.empty_display_size = 0.5

        # Assign 2DFX settings to the OBJECT, not data
        settings = obj.dff.ext_2dfx
        settings.standart_pos = entry.standart_pos
        settings.bottom_pos = entry.bottom
        settings.top_pos = entry.top
        settings.end_pos = entry.end
        settings.direction = str(entry.direction)

        settings.standart_pos_rotation = entry.rotation
        settings.standart_pos_pitch = entry.pitch
        settings.standart_pos_yaw = entry.yaw

        settings.bottom_rotation = entry.bottom_rotation
        settings.bottom_pitch = entry.bottom_pitch
        settings.bottom_yaw = entry.bottom_yaw

        settings.top_rotation = entry.top_rotation
        settings.top_pitch = entry.top_pitch
        settings.top_yaw = entry.top_yaw

        settings.end_rotation = entry.end_rotation
        settings.end_pitch = entry.end_pitch
        settings.end_yaw = entry.end_yaw

        return obj


    #######################################################
    def get_objects(self):

        """ Import and return the list of imported objects """

        global entries

        functions = {
            0: self.import_light,
            1: self.import_particle,
            4: self.import_sun_glare,
            8: self.import_trigger_point,
            9: self.import_cover_point,
            10: self.import_escalator,
        }

        objects = []

        for entry in self.effects.entries:
                obj = functions[entry.effect_id](entry)
                obj.dff.type = '2DFX'
                obj.dff.ext_2dfx.effect = str(entry.effect_id)
                obj.location = entry.loc
                objects.append(obj)

        return objects