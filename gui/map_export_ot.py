# DemonFF - Blender map export operators
# 2023 - 2026 spicybung

import bpy
import os

from bpy.props import CollectionProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from ..ops import map_exporter


class ExportToIPLOperator(bpy.types.Operator, ExportHelper):
    bl_idname = "object.export_to_ipl"
    bl_label = "Export to IPL"
    bl_description = "Export selected objects as an IPL file"
    filename_ext = ".ipl"

    filter_glob: bpy.props.StringProperty(default="*.ipl", options={'HIDDEN'})

    def execute(self, context):
        if not map_exporter.collect_ipl_export_objects(context, only_selected=True):
            self.report({'INFO'}, "No exportable map mesh selected")
            return {'CANCELLED'}

        output_file, written = map_exporter.export_ipl_file(
            context,
            self.filepath,
            only_selected=True,
            skip_lod=context.scene.dff.skip_lod,
            game_id=context.scene.dff.game_version_dropdown,
        )

        self.report({'INFO'}, f"Exported {written} IPL object(s) to {output_file}")
        return {'FINISHED'}


class ExportToIDEOperator(bpy.types.Operator, ExportHelper):
    bl_idname = "object.export_to_ide"
    bl_label = "Export to IDE"
    bl_description = "Export scene objects as an IDE file"
    filename_ext = ".ide"

    filter_glob: bpy.props.StringProperty(default="*.ide", options={'HIDDEN'})

    def execute(self, context):
        output_file, written = map_exporter.export_ide_file(
            context,
            self.filepath,
            skip_lod=context.scene.dff.skip_lod,
        )

        if written == 0:
            self.report({'INFO'}, "No exportable map object definitions found")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported {written} IDE object definition(s) to {output_file}")
        return {'FINISHED'}


class ExportToPawnOperator(bpy.types.Operator, ExportHelper):
    bl_idname = "object.export_to_pawn"
    bl_label = "Export to Pawn Script"
    bl_description = "Export selected objects as CreateDynamicObject lines and artconfig AddSimpleModel lines"
    filename_ext = ".pwn"

    filter_glob: bpy.props.StringProperty(default="*.pwn;*.inc", options={'HIDDEN'})
    model_directory: bpy.props.StringProperty(name="Model Directory", default="", description="Model directory for artconfig DFF paths")
    texture_directory: bpy.props.StringProperty(name="Texture Directory", default="", description="Texture directory for artconfig TXD paths. Blank uses the model directory.")
    skip_lod: bpy.props.BoolProperty(name="Skip LOD Objects", default=True)
    stream_distance: bpy.props.FloatProperty(name="Stream Distance", default=300.0)
    draw_distance: bpy.props.FloatProperty(name="Draw Distance", default=300.0)
    x_offset: bpy.props.FloatProperty(name="X Offset", default=0.0)
    y_offset: bpy.props.FloatProperty(name="Y Offset", default=0.0)
    z_offset: bpy.props.FloatProperty(name="Z Offset", default=0.0)
    force_all_worlds_interiors: bpy.props.BoolProperty(
        name="Ignore IPL Interior/World",
        default=True,
        description="Write CreateDynamicObject world/interior as -1/-1 so VCS IPL interior values do not hide exterior map objects",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "model_directory")
        layout.prop(self, "texture_directory")
        layout.prop(self, "skip_lod")
        layout.prop(self, "stream_distance")
        layout.prop(self, "draw_distance")
        layout.prop(self, "x_offset")
        layout.prop(self, "y_offset")
        layout.prop(self, "z_offset")
        layout.prop(self, "force_all_worlds_interiors")

    def execute(self, context):
        map_exporter.export_pawn({
            "file_name": self.filepath,
            "only_selected": True,
            "model_directory": self.model_directory,
            "texture_directory": self.texture_directory,
            "skip_lod": self.skip_lod,
            "stream_distance": self.stream_distance,
            "draw_distance": self.draw_distance,
            "x_offset": self.x_offset,
            "y_offset": self.y_offset,
            "z_offset": self.z_offset,
            "force_all_worlds_interiors": self.force_all_worlds_interiors,
        })

        if not map_exporter.pwn_exporter.total_objects_num:
            self.report({'ERROR'}, "No exportable selected meshes found")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported {map_exporter.pwn_exporter.total_objects_num} selected object(s)")
        return {'FINISHED'}


class RemoveBuildingForPlayerOperator(bpy.types.Operator):
    bl_idname = "object.remove_building_for_player"
    bl_label = "Remove Building For Player"
    bl_description = "Print RemoveBuildingForPlayer lines for the selected map objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        objects = [obj for obj in context.selected_objects if map_exporter.object_is_exportable_map_instance(obj)]
        for line in map_exporter.make_remove_building_lines(objects):
            print(line)
        self.report({'INFO'}, f"Printed {len(objects)} RemoveBuildingForPlayer line(s) to the console")
        return {'FINISHED'}
