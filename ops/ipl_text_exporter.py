# DemonFF - Blender scripts for working with Renderware & R*/SA-MP/open.mp formats in Blender
# 2023 - 2026 spicybung

# This is a fork of DragonFF by Parik27 - maintained by Psycrow, and various others!
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

from bpy_extras.io_utils import ExportHelper

from .importer_common import game_version
from . import map_exporter


#######################################################
class EXPORT_OT_demonff_ipl(bpy.types.Operator, ExportHelper):
    bl_idname = "scene.demonff_export_ipl"
    bl_label = "Export IPL (Text)"
    bl_description = "Export object instances to a text .ipl file (inst section)"
    filename_ext = ".ipl"

    filter_glob: bpy.props.StringProperty(default="*.ipl", options={'HIDDEN'})

    only_selected: bpy.props.BoolProperty(
        name="Only Selected",
        default=False
    )

    skip_lod: bpy.props.BoolProperty(
        name="Skip LOD",
        description="Skip LOD objects named like LOD* or *.ColMesh",
        default=False
    )

    game: bpy.props.EnumProperty(
        name="Game",
        items=(
            (game_version.III, "GTA III", "GTA III text IPL"),
            (game_version.VC, "GTA VC", "GTA Vice City text IPL"),
            (game_version.SA, "GTA SA", "GTA San Andreas text IPL"),
        ),
        default=game_version.SA,
    )

    #######################################################
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "game")
        layout.prop(self, "only_selected")
        layout.prop(self, "skip_lod")

    #######################################################
    def collect_objects(self, context):
        objects = []

        for obj in context.scene.objects:
            if self.only_selected and not obj.select_get():
                continue
            if not map_exporter.object_is_exportable_map_instance(obj):
                continue
            if self.skip_lod and map_exporter.object_is_lod(obj):
                continue
            objects.append(obj)

        return objects

    #######################################################
    def format_inst_line(self, obj):
        return map_exporter.format_ipl_inst_line(bpy.context, obj, self.game)

    #######################################################
    def execute(self, context):
        objects = self.collect_objects(context)

        with open(self.filepath, "w", encoding="latin-1") as file:
            file.write("inst\n")

            for obj in objects:
                file.write(self.format_inst_line(obj) + f"  # {obj.name}\n")

            file.write("end\n")

        self.report({'INFO'}, f"Exported {len(objects)} IPL entries")
        return {'FINISHED'}
