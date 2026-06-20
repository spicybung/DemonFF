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

from .importer_common import game_version
from .map_exporter import (
    get_object_ide_id,
    get_object_model_name,
    get_object_interior,
    get_object_lod,
    get_export_transform,
    object_is_lod,
)


class ipl_exporter:
    only_selected = False
    game_id = None
    export_inst = True
    export_cull = False
    inst_objects = []
    cull_objects = []
    total_objects_num = 0

    @staticmethod
    def collect_objects(context):
        self = ipl_exporter
        self.inst_objects = []
        self.cull_objects = []

        for obj in context.scene.objects:
            if self.only_selected and not obj.select_get():
                continue
            if self.export_inst and obj.type == 'MESH' and not object_is_lod(obj):
                self.inst_objects.append(obj)

        self.total_objects_num = len(self.inst_objects)

    @staticmethod
    def format_inst_line(obj):
        self = ipl_exporter
        object_id = get_object_ide_id(obj, 0)
        model_name = get_object_model_name(obj)
        interior = get_object_interior(obj, 0)
        lod = get_object_lod(obj, -1)
        position, rotation, scale = get_export_transform(obj)

        rot_w = -rotation.w
        rot_x = rotation.x
        rot_y = rotation.y
        rot_z = rotation.z

        if self.game_id == game_version.III:
            return (
                f"{object_id}, {model_name}, "
                f"{position.x:.6f}, {position.y:.6f}, {position.z:.6f}, "
                f"{scale.x:.6f}, {scale.y:.6f}, {scale.z:.6f}, "
                f"{rot_x:.6f}, {rot_y:.6f}, {rot_z:.6f}, {rot_w:.6f}"
            )

        if self.game_id == game_version.VC:
            return (
                f"{object_id}, {model_name}, {interior}, "
                f"{position.x:.6f}, {position.y:.6f}, {position.z:.6f}, "
                f"{scale.x:.6f}, {scale.y:.6f}, {scale.z:.6f}, "
                f"{rot_x:.6f}, {rot_y:.6f}, {rot_z:.6f}, {rot_w:.6f}"
            )

        return (
            f"{object_id}, {model_name}, {interior}, "
            f"{position.x:.6f}, {position.y:.6f}, {position.z:.6f}, "
            f"{rot_x:.6f}, {rot_y:.6f}, {rot_z:.6f}, {rot_w:.6f}, {lod}"
        )

    @staticmethod
    def export_ipl(filename):
        self = ipl_exporter
        self.collect_objects(bpy.context)

        with open(filename, 'w', encoding='latin-1') as file:
            if self.export_inst:
                file.write('inst\n')
                for obj in self.inst_objects:
                    file.write(self.format_inst_line(obj) + f"  # {obj.name}\n")
                file.write('end\n')


def export_ipl(options):
    ipl_exporter.only_selected = options.get('only_selected', False)
    ipl_exporter.game_id = options.get('game_id', game_version.SA)
    ipl_exporter.export_inst = options.get('export_inst', True)
    ipl_exporter.export_cull = options.get('export_cull', False)
    ipl_exporter.export_ipl(options['file_name'])
