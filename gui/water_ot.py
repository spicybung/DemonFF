# DemonFF - Blender scripts for working with Renderware & R*/SA-MP/open.mp formats in Blender
# 2023 - 2027 spicybung

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
from bpy_extras.io_utils import ImportHelper, ExportHelper

from ..gtaLib.water import WATER_VERTEX_LAYERS
from ..ops.water_importer import importWaterFile
from ..ops.water_exporter import exportWaterFile, isWaterObject
from ..ops.water_simulation import createWaterPreview, removeWaterPreview, waterSourceObject
from ..ops.water_mesh import initializeWaterObject, applyWaterObjectSettings


WATER_FORMAT_ITEMS = (
    ('AUTO', 'Automatic', 'Use the source format; new meshes default to San Andreas'),
    ('SA', 'San Andreas', 'Water triangles and quads with flow, wave values and flags'),
    ('III_VC', 'GTA III / Vice City Text', 'Horizontal, axis-aligned text water rectangles'),
    ('WATERPRO', 'WATERPRO Binary', 'GTA III / Vice City 128 by 128 water tile grid'),
)


WATERPRO_PROFILE_ITEMS = (
    ('VC', 'Vice City', 'Grid starts at X -2448, Y -2048'),
    ('III', 'GTA III', 'Grid starts at X -2048, Y -2048'),
)


class IMPORT_OT_water(bpy.types.Operator, ImportHelper):
    bl_idname = 'import_scene.demonff_water'
    bl_label = 'Import Water (.dat)'
    bl_description = 'Import water.dat sectors with editable water data and a tiled texture'
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = '.dat'

    filter_glob: bpy.props.StringProperty(default='*.dat;*.DAT', options={'HIDDEN'})
    game_format: bpy.props.EnumProperty(name='Format', items=WATER_FORMAT_ITEMS, default='AUTO')
    binary_profile: bpy.props.EnumProperty(
        name='WATERPRO Grid', items=WATERPRO_PROFILE_ITEMS, default='VC',
        description='Binary files contain no game identifier; choose the correct world grid',
    )
    texture_path: bpy.props.StringProperty(
        name='Water Texture', subtype='FILE_PATH',
        description='Leave blank to use the bundled waterclear256 texture', default='',
    )
    tile_size: bpy.props.FloatProperty(
        name='Texture Tile Size',
        description='World units covered by one texture repeat; smaller values give more repeats',
        default=32.0, min=0.001,
    )
    combine_meshes: bpy.props.BoolProperty(
        name='Combine Sectors', default=False,
        description='Import as one mesh, retaining separate faces and per-sector water data',
    )
    skip_invalid: bpy.props.BoolProperty(
        name='Skip Invalid Records', default=False,
        description='Import valid records and report skipped lines instead of cancelling the whole import',
    )

    def draw(self, context):
        for name in ('game_format', 'binary_profile', 'texture_path', 'tile_size', 'combine_meshes', 'skip_invalid'):
            self.layout.prop(self, name)

    def execute(self, context):
        warnings = []
        try:
            objects = importWaterFile(context, self.filepath, self.game_format, self.texture_path,
                                      self.tile_size, self.combine_meshes, self.skip_invalid, warnings, self.binary_profile)
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        for warning in warnings:
            print('DemonFF: ' + warning)
        count = sum(len(obj.data.polygons) for obj in objects)
        if warnings:
            self.report({'WARNING'}, f'Imported {count} sectors; skipped {len(warnings)} records. First: {warnings[0]}')
        else:
            self.report({'INFO'}, f'Imported {count} water sectors in {len(objects)} objects')
        return {'FINISHED'}


class EXPORT_OT_water(bpy.types.Operator, ExportHelper):
    bl_idname = 'export_scene.demonff_water'
    bl_label = 'Export Water (.dat)'
    bl_description = 'Write a new water.dat from current water meshes and object transforms'
    filename_ext = '.dat'

    filter_glob: bpy.props.StringProperty(default='*.dat', options={'HIDDEN'})
    game_format: bpy.props.EnumProperty(name='Format', items=WATER_FORMAT_ITEMS, default='AUTO')
    binary_profile: bpy.props.EnumProperty(
        name='WATERPRO Grid',
        items=(('AUTO', 'From Source / Vice City', 'Use the imported profile; new water defaults to Vice City'),) + WATERPRO_PROFILE_ITEMS,
        default='AUTO',
    )
    scope: bpy.props.EnumProperty(
        name='Export',
        items=(('ALL_WATER', 'All Water in Scene', 'Export all marked water meshes, including hidden water'),
               ('SELECTED', 'Selected Meshes', 'Export selected meshes, including new unmarked geometry'),
               ('ACTIVE_COLLECTION', 'Water in Active Collection', 'Export marked water in the active Outliner collection and its children')),
        default='SELECTED',
    )
    apply_modifiers: bpy.props.BoolProperty(
        name='Apply Modifiers', default=False,
        description='Export evaluated mesh geometry without changing the original mesh',
    )
    snap_xy: bpy.props.BoolProperty(
        name='Snap XY to Integers', default=True,
        description='Round San Andreas XY positions to the integer grid used by the game',
    )
    triangulate_ngons: bpy.props.BoolProperty(
        name='Triangulate N-gons', default=False,
        description='Split faces with more than four vertices into triangles for San Andreas export',
    )
    validate_game: bpy.props.BoolProperty(
        name='San Andreas Geometry Checks', default=True,
        description='Check map bounds, integer XY, rectangular quads and horizontal triangle edges',
    )

    def invoke(self, context, event):
        if not self.filepath:
            binary = self.game_format == 'WATERPRO' or (self.game_format == 'AUTO' and context.object is not None and context.object.get('water_format') == 'WATERPRO')
            self.filepath = 'waterpro_new.dat' if binary else 'water_new.dat'
        return ExportHelper.invoke(self, context, event)

    def draw(self, context):
        self.layout.prop(self, 'scope')
        self.layout.prop(self, 'game_format')
        source_format = context.object.get('water_format', 'SA') if context.object is not None else 'SA'
        output_format = source_format if self.game_format == 'AUTO' else self.game_format
        if output_format == 'WATERPRO':
            self.layout.prop(self, 'binary_profile')
        self.layout.prop(self, 'apply_modifiers')
        options = self.layout.column()
        options.enabled = output_format == 'SA'
        options.prop(self, 'snap_xy')
        options.prop(self, 'triangulate_ngons')
        options.prop(self, 'validate_game')

    def execute(self, context):
        try:
            count = exportWaterFile(context, self.filepath, self.scope, self.game_format,
                                    self.apply_modifiers, self.snap_xy,
                                    self.triangulate_ngons, self.validate_game, self.binary_profile)
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'INFO'}, f'Exported {count} water sectors')
        return {'FINISHED'}


class OBJECT_OT_water_mark(bpy.types.Operator):
    bl_idname = 'object.demonff_water_mark'
    bl_label = 'Mark as Water'
    bl_description = 'Mark selected mesh objects as water and initialize water data'
    bl_options = {'REGISTER', 'UNDO'}

    game_format: bpy.props.EnumProperty(name='Format', items=WATER_FORMAT_ITEMS[1:], default='SA')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type != 'MESH' or 'water_format' in obj or 'water_sector' in obj:
                continue
            initializeWaterObject(obj, self.game_format)
            applyWaterObjectSettings(obj)
        return {'FINISHED'}


class OBJECT_OT_water_apply_settings(bpy.types.Operator):
    bl_idname = 'object.demonff_water_apply_settings'
    bl_label = 'Apply Water Values'
    bl_description = 'Apply object water values to the mesh, or only selected vertices and faces in Edit Mode'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and isWaterObject(waterSourceObject(context.object))

    def execute(self, context):
        try:
            applyWaterObjectSettings(waterSourceObject(context.object), context.object.mode == 'EDIT')
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}


class OBJECT_PT_demonff_water(bpy.types.Panel):
    bl_label = 'DemonFF Water'
    bl_idname = 'OBJECT_PT_demonff_water'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        obj = waterSourceObject(context.object)
        if 'water_format' not in obj and 'water_sector' not in obj:
            row = layout.row()
            row.operator(OBJECT_OT_water_mark.bl_idname, text='Mark as SA Water').game_format = 'SA'
            row.operator(OBJECT_OT_water_mark.bl_idname, text='Mark as III / VC Water').game_format = 'III_VC'
            layout.operator(OBJECT_OT_water_mark.bl_idname, text='Mark as WATERPRO Water').game_format = 'WATERPRO'
            return
        layout.label(text='Format: ' + str(obj.get('water_format', 'SA')))
        if obj.get('water_format') == 'WATERPRO':
            layout.label(text='Grid: ' + obj.get('waterpro_profile', 'VC'))
            layout.label(text='Flat rectangles on the 32-unit tile grid.')
            layout.label(text='Move vertices or objects in Z to edit the level.')
            layout.operator(EXPORT_OT_water.bl_idname, text='Export Selected WATERPRO').scope = 'SELECTED'
            return
        if obj.get('water_format') == 'III_VC':
            layout.label(text='Edit horizontal, axis-aligned rectangle faces.')
            layout.operator(EXPORT_OT_water.bl_idname, text='Export Selected Water').scope = 'SELECTED'
            return
        scene = context.scene
        for name, value in (('water_wavyness', 1.0), ('water_wave_speed', 1.0), ('water_wave_time', 0.0), ('water_preview_spacing', 16.0)):
            if name not in scene:
                scene[name] = value
        layout.label(text='San Andreas Wave Preview (timeline)')
        layout.prop(scene, '["water_wavyness"]', text='Weather Wavyness')
        layout.prop(scene, '["water_wave_speed"]', text='Playback Speed')
        layout.prop(scene, '["water_wave_time"]', text='Time Offset (seconds)')
        layout.prop(scene, '["water_preview_spacing"]', text='Preview Spacing')
        layout.operator('object.demonff_water_preview').spacing = max(0.25, float(scene['water_preview_spacing']))
        layout.operator('object.demonff_water_preview', text='Remove Wave Preview').stop = True
        layout.label(text='Refresh after editing sector geometry or wave values.')
        layout.label(text='Water export always uses the source sectors.')
        layout.label(text='Values to apply:')
        if 'water_flags' in obj:
            layout.prop(obj, '["water_flags"]', text='Flags')
        for name, label in zip(WATER_VERTEX_LAYERS, ('Flow X', 'Flow Y', 'Big Waves', 'Small Waves')):
            if name in obj:
                layout.prop(obj, '["' + name + '"]', text=label)
        label = 'Apply to Selected Vertices / Faces' if obj.mode == 'EDIT' else 'Apply to Entire Mesh'
        layout.operator(OBJECT_OT_water_apply_settings.bl_idname, text=label)
        layout.label(text='Existing vertex/face data is preserved until applied.')
        layout.operator(EXPORT_OT_water.bl_idname, text='Export Selected Water').scope = 'SELECTED'


class OBJECT_OT_water_preview(bpy.types.Operator):
    bl_idname = 'object.demonff_water_preview'
    bl_label = 'Build / Refresh Wave Preview'
    bl_options = {'REGISTER', 'UNDO'}
    spacing: bpy.props.FloatProperty(name='Preview Spacing', default=4.0, min=0.25, max=512.0)
    stop: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

    def execute(self, context):
        source = waterSourceObject(context.object)
        try:
            if self.stop:
                removeWaterPreview(source)
                source.select_set(True)
                context.view_layer.objects.active = source
            else:
                createWaterPreview(context, source, self.spacing)
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}
