# DemonFF - Blender scripts for working with Renderware & R*/SA-MP/open.mp formats in Blender
# 2023 - 2025 SpicyBung

import bpy

from .map_exporter import (
    get_object_ide_id,
    get_object_model_name,
    get_object_txd_name,
    get_object_flags,
    get_object_draw_distances,
    object_is_lod,
)


class ide_exporter:
    only_selected = False
    objs_objects = []
    tobj_objects = []
    anim_objects = []

    @staticmethod
    def collect_objects(context):
        self = ide_exporter
        self.objs_objects = []
        self.tobj_objects = []
        self.anim_objects = []
        seen = set()

        for obj in context.scene.objects:
            if obj.type != 'MESH':
                continue
            if self.only_selected and not obj.select_get():
                continue
            if object_is_lod(obj):
                continue

            object_id = str(get_object_ide_id(obj, 0))
            seen_key = object_id if object_id not in ('', '0') else get_object_model_name(obj)
            if seen_key in seen:
                continue
            seen.add(seen_key)

            obj_section = object_is_lod(obj) and 'lod' or None
            if hasattr(obj, 'ide') and obj.ide.obj_type == 'tobj':
                self.tobj_objects.append(obj)
            elif hasattr(obj, 'ide') and obj.ide.obj_type == 'anim':
                if not hasattr(self, 'anim_objects'):
                    self.anim_objects = []
                self.anim_objects.append(obj)
            else:
                self.objs_objects.append(obj)

    @staticmethod
    def format_objs_line(obj):
        object_id = get_object_ide_id(obj, 0)
        model_name = get_object_model_name(obj)
        txd_name = get_object_txd_name(obj)
        flags = get_object_flags(obj, 0)
        distances = get_object_draw_distances(obj)

        if len(distances) == 1:
            return f"{object_id}, {model_name}, {txd_name}, {distances[0]}, {flags}"
        if len(distances) == 2:
            return f"{object_id}, {model_name}, {txd_name}, 1, {distances[0]}, {distances[1]}, {flags}"
        return f"{object_id}, {model_name}, {txd_name}, 1, {distances[0]}, {distances[1]}, {distances[2]}, {flags}"

    @staticmethod
    def format_tobj_line(obj):
        time_on = obj.ide.time_on if hasattr(obj, 'ide') and obj.ide.time_on else '0'
        time_off = obj.ide.time_off if hasattr(obj, 'ide') and obj.ide.time_off else '24'
        return f"{ide_exporter.format_objs_line(obj)}, {time_on}, {time_off}"

    @staticmethod
    def export_ide(filename):
        self = ide_exporter
        self.collect_objects(bpy.context)

        with open(filename, 'w', encoding='latin-1') as file:
            if self.objs_objects:
                file.write('objs\n')
                for obj in self.objs_objects:
                    file.write(self.format_objs_line(obj) + f"  # {obj.name}\n")
                file.write('end\n')

            if self.tobj_objects:
                file.write('tobj\n')
                for obj in self.tobj_objects:
                    file.write(self.format_tobj_line(obj) + f"  # {obj.name}\n")
                file.write('end\n')


def export_ide(options):
    ide_exporter.only_selected = options.get('only_selected', False)
    ide_exporter.export_ide(options['file_name'])
