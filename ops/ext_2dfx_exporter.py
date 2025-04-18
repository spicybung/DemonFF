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

from mathutils import Vector

from ..gtaLib import dff
from ..gtaLib.dff import entries



#######################################################
class ext_2dfx_exporter:

    """ Helper class for 2dfx exporting """

    #######################################################
    def __init__(self, effects):
        self.effects = effects

    #######################################################
    def export_light(self, obj):
        global entries

        if obj.type != 'LIGHT':
            print(f"[DEBUG] Skipping object {obj.name} - Not a light.")
            return

        print(f"[DEBUG] Exporting light: {obj.name}")
        FL1, FL2 = dff.Light2dfx.Flags1, dff.Light2dfx.Flags2
        settings = obj.data.ext_2dfx

        # Initialize the entry with location
        entry = dff.Light2dfx(obj.location)
        print(f"[DEBUG] Initialized Light2dfx entry for {obj.name} with location: {obj.location}")

        # Set view direction if applicable
        if settings.export_view_vector:
            print(f"[DEBUG] Setting view vector for {obj.name} to: {settings.view_vector}")
            entry.lookDirection = settings.view_vector

        # Set color with alpha
        entry.color = dff.RGBA._make(
            list(int(255 * x) for x in list(obj.data.color) + [settings.alpha])
        )
        print(f"[DEBUG] Set color for {obj.name} to RGBA: {entry.color}")

        # Set additional light parameters
        entry.coronaFarClip = settings.corona_far_clip
        entry.pointlightRange = settings.point_light_range
        entry.coronaSize = settings.corona_size
        entry.shadowSize = settings.shadow_size
        entry.coronaShowMode = int(settings.corona_show_mode)
        entry.coronaEnableReflection = int(settings.corona_enable_reflection)
        entry.coronaFlareType = settings.corona_flare_type
        entry.shadowColorMultiplier = settings.shadow_color_multiplier
        entry.coronaTexName = settings.corona_tex_name
        entry.shadowTexName = settings.shadow_tex_name
        entry.shadowZDistance = settings.shadow_z_distance

        print(f"[DEBUG] Set parameters for {obj.name}:")
        print(f"        Corona Far Clip: {entry.coronaFarClip}")
        print(f"        Point Light Range: {entry.pointlightRange}")
        print(f"        Corona Size: {entry.coronaSize}")
        print(f"        Shadow Size: {entry.shadowSize}")
        print(f"        Corona Show Mode: {entry.coronaShowMode}")
        print(f"        Corona Enable Reflection: {entry.coronaEnableReflection}")
        print(f"        Corona Flare Type: {entry.coronaFlareType}")
        print(f"        Shadow Color Multiplier: {entry.shadowColorMultiplier}")
        print(f"        Corona Texture Name: {entry.coronaTexName}")
        print(f"        Shadow Texture Name: {entry.shadowTexName}")
        print(f"        Shadow Z Distance: {entry.shadowZDistance}")

        # Log flags being set
        print(f"[DEBUG] Setting flags for light: {obj.name}")
        if settings.flag1_corona_check_obstacles:
            entry.set_flag(FL1.CORONA_CHECK_OBSTACLES.value)
            print(f"        Flag set: CORONA_CHECK_OBSTACLES")

        entry.set_flag(settings.flag1_fog_type << 1)
        print(f"        Flag set: Fog Type << 1 ({settings.flag1_fog_type << 1})")

        if settings.flag1_without_corona:
            entry.set_flag(FL1.WITHOUT_CORONA.value)
            print(f"        Flag set: WITHOUT_CORONA")

        if settings.flag1_corona_only_at_long_distance:
            entry.set_flag(FL1.CORONA_ONLY_AT_LONG_DISTANCE.value)
            print(f"        Flag set: CORONA_ONLY_AT_LONG_DISTANCE")

        if settings.flag1_at_day:
            entry.set_flag(FL1.AT_DAY.value)
            print(f"        Flag set: AT_DAY")

        if settings.flag1_at_night:
            entry.set_flag(FL1.AT_NIGHT.value)
            print(f"        Flag set: AT_NIGHT")

        if settings.flag1_blinking1:
            entry.set_flag(FL1.BLINKING1.value)
            print(f"        Flag set: BLINKING1")

        if settings.flag2_corona_only_from_below:
            entry.set_flag2(FL2.CORONA_ONLY_FROM_BELOW.value)
            print(f"        Flag set2: CORONA_ONLY_FROM_BELOW")

        if settings.flag2_blinking2:
            entry.set_flag2(FL2.BLINKING2.value)
            print(f"        Flag set2: BLINKING2")

        if settings.flag2_udpdate_height_above_ground:
            entry.set_flag2(FL2.UDPDATE_HEIGHT_ABOVE_GROUND.value)
            print(f"        Flag set2: UDPDATE_HEIGHT_ABOVE_GROUND")

        if settings.flag2_check_view_vector:
            entry.set_flag2(FL2.CHECK_DIRECTION.value)
            print(f"        Flag set2: CHECK_DIRECTION")

        if settings.flag2_blinking3:
            entry.set_flag2(FL2.BLINKING3.value)
            print(f"        Flag set2: BLINKING3")

        print(f"[DEBUG] Light export completed for {obj.name}: {entry}")
        return entry

    #######################################################
    def export_particle(self, obj):
        settings = obj.dff.ext_2dfx

        entry = dff.Particle2dfx(obj.location)
        entry.effect = settings.val_str24_1

        return entry

    #######################################################
    def export_sun_glare(self, obj):
        entry = dff.SunGlare2dfx(obj.location)

        return entry
    
    #######################################################
    def export_enter_exit(self, obj):
        settings = obj.dff.ext_2dfx

        entry = dff.EnterExit2dfx(obj.location)
        entry.enter_angle = math.radians(settings.val_degree_1)
        entry.approximation_radius_x = settings.val_float_1
        entry.approximation_radius_y = settings.val_float_2
        entry.exit_location = settings.val_vector_1
        entry.exit_angle = settings.val_degree_2
        entry.interior = settings.val_short_1
        entry._flags1 = settings.val_byte_1
        entry.sky_color = settings.val_byte_2
        entry.interior_name = settings.val_str8_1
        entry.time_on = settings.val_hour_1
        entry.time_off = settings.val_hour_2
        entry._flags2 = settings.val_byte_3
        entry.unk = settings.val_byte_4

        return entry

    #######################################################
    def export_road_sign(self, obj):
        if obj.type != 'FONT':
            return

        lines = obj.data.body.split("\n")[:4]
        if not lines:
            return

        lines_num = len(lines)
        while len(lines) < 4:
            lines.append("_" * 16)

        max_chars_num = 2
        for i, line in enumerate(lines):
            if len(line) < 16:
                line += (16 - len(line)) * "_"
            line = line.replace(" ", "_")[:16]
            lines[i] = line

            line_chars_num = len(line.rstrip("_"))
            if max_chars_num < line_chars_num:
                max_chars_num = line_chars_num

        max_chars_num = next((i for i in (2, 4, 8, 16) if max_chars_num <= i), max_chars_num)

        settings = obj.data.ext_2dfx

        flags = {1:1, 2:2, 3:3, 4:0}[lines_num]
        flags |= {2:1, 4:2, 8:3, 16:0}[max_chars_num] << 2
        flags |= int(settings.color) << 4

        rotation = obj.matrix_local.to_euler('ZXY')

        entry = dff.RoadSign2dfx(obj.location)

        entry.rotation = Vector((
            rotation.x * (180 / math.pi),
            rotation.y * (180 / math.pi),
            rotation.z * (180 / math.pi)
        ))

        entry.text1, entry.text2, \
        entry.text3, entry.text4 = lines

        entry.size = settings.size
        entry.flags = flags

        return entry

    #######################################################
    def export_trigger_point(self, obj):
        settings = obj.dff.ext_2dfx

        entry = dff.TriggerPoint2dfx(obj.location)
        entry.point_id = settings.val_int_1

        return entry

    #######################################################
    def export_cover_point(self, obj):
        settings = obj.dff.ext_2dfx

        entry = dff.CoverPoint2dfx(obj.location)
        entry.cover_type = settings.val_int_1

        if obj.rotation_mode in ('QUATERNION', 'AXIS_ANGLE'):
            direction = obj.rotation_quaternion @ Vector((0.0, 1.0, 0.0))
        else:
            direction = obj.rotation_euler.to_quaternion() @ Vector((0.0, 1.0, 0.0))

        direction.z = 0
        direction.normalize()

        entry.direction_x = direction.x
        entry.direction_y = direction.y

        return entry
    
    #######################################################
    def export_escalator(self, obj):
        settings = obj.dff.ext_2dfx

        entry = dff.Escalator2DFX(obj.location) #effect_id begins after position vector for escalators

        # Vectors
        entry.standart_pos = settings.standart_pos
        entry.rotation = settings.standart_pos_rotation
        entry.pitch = settings.standart_pos_pitch
        entry.yaw = settings.standart_pos_yaw

        entry.effect_id = 10

        # Bottom
        entry.bottom = settings.bottom_pos
        entry.bottom_rotation = settings.bottom_rotation
        entry.bottom_pitch = settings.bottom_pitch
        entry.bottom_yaw = settings.bottom_yaw

        # Top
        entry.top = settings.top_pos
        entry.top_rotation = settings.top_rotation
        entry.top_pitch = settings.top_pitch
        entry.top_yaw = settings.top_yaw

        # End
        entry.end = settings.end_pos
        entry.end_rotation = settings.end_rotation
        entry.end_pitch = settings.end_pitch
        entry.end_yaw = settings.end_yaw

        # Direction
        entry.direction = int(settings.direction)

        return entry

    #######################################################
    def export_objects(self, objects):

        """ Export objects and fill 2dfx entries """

        functions = {
            0: self.export_light,
            1: self.export_particle,
            4: self.export_sun_glare,
            8: self.export_trigger_point,
            9: self.export_cover_point,
            10: self.export_escalator,
        }

        for obj in objects:
            if obj.dff.type != '2DFX':
                continue

            entry = functions[int(obj.dff.ext_2dfx.effect)](obj)
            if entry:
                self.effects.append_entry(entry)
