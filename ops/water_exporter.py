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

import base64

import bpy

from ..gtaLib.water import validateSanAndreasGeometry, writeWaterFile, writeWaterData
from ..gtaLib.water import buildWaterProBytes, parseWaterProBytes
from .water_mesh import waterSectorsFromMesh
from .water_simulation import waterSourceObject


def isWaterObject(obj):
    return obj.type == 'MESH' and not obj.get('water_preview_source') and (
        'water_sector' in obj or 'water_format' in obj or
        any(collection.get('demonff_water', False) for collection in obj.users_collection))


def getWaterExportObjects(context, scope):
    if scope == 'SELECTED':
        objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
    elif scope == 'ALL_WATER':
        objects = [obj for obj in context.scene.objects if isWaterObject(obj)]
    elif scope == 'ACTIVE_COLLECTION':
        collection = context.view_layer.active_layer_collection.collection
        objects = [obj for obj in collection.all_objects if isWaterObject(obj)]
    else:
        raise ValueError('Unknown water export scope')
    if not objects:
        raise ValueError('No water meshes found; import water or choose Selected Meshes to export new geometry')
    objects = list({waterSourceObject(obj) for obj in objects})
    return sorted(objects, key=lambda obj: (str(obj.get('water_source', '')), int(obj.get('water_sector', 0)), obj.name))


def collectWaterSectors(context, scope='ALL_WATER', game_format='AUTO', apply_modifiers=False,
                        snap_xy=True, triangulate_ngons=False, validate_game=True):
    objects = getWaterExportObjects(context, scope)
    if game_format == 'AUTO':
        formats = {obj.get('water_format', 'SA') for obj in objects}
        if len(formats) != 1:
            raise ValueError('Mixed water formats; choose an explicit export format')
        game_format = formats.pop()
    if game_format not in {'SA', 'III_VC', 'WATERPRO'}:
        raise ValueError('Choose San Andreas, GTA III / Vice City rectangles, or binary WATERPRO')
    context.view_layer.update()
    depsgraph = context.evaluated_depsgraph_get() if apply_modifiers else None
    sectors = []
    for obj in objects:
        if obj.mode == 'EDIT':
            obj.update_from_editmode()
        evaluated = None
        try:
            if apply_modifiers:
                evaluated = obj.evaluated_get(depsgraph)
                mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
            else:
                mesh = obj.data
            object_sectors = waterSectorsFromMesh(obj, mesh, game_format, snap_xy, triangulate_ngons)
            if game_format == 'SA' and validate_game:
                for index, sector in enumerate(object_sectors):
                    try:
                        validateSanAndreasGeometry(sector.vertices)
                    except ValueError as error:
                        raise ValueError(f'{obj.name}, sector {index}: {error}') from error
            sectors.extend(object_sectors)
        finally:
            if evaluated is not None:
                evaluated.to_mesh_clear()
    return sectors


def getWaterProSource(context, scope, binary_profile):
    objects = getWaterExportObjects(context, scope)
    source_names = {obj.get('waterpro_source') for obj in objects if obj.get('waterpro_source')}
    profiles = {obj.get('waterpro_profile') for obj in objects if obj.get('waterpro_profile')}
    if len(source_names) > 1 or len(profiles) > 1:
        raise ValueError('Select water from one WATERPRO source/profile at a time')
    profile = next(iter(profiles)) if binary_profile == 'AUTO' and profiles else binary_profile
    if profile == 'AUTO':
        profile = 'VC'
    source = None
    if source_names:
        name = next(iter(source_names))
        text = bpy.data.texts.get(name)
        if text is None:
            raise ValueError('Original WATERPRO data block is missing: ' + name)
        stored_profile = text.get('waterpro_profile', profile)
        if profile != stored_profile:
            raise ValueError('Export grid profile differs from the imported WATERPRO profile')
        try:
            data = base64.b64decode(text.as_string(), validate=True)
        except ValueError as error:
            raise ValueError('Original WATERPRO data block is corrupt') from error
        source = parseWaterProBytes(data, profile)
    return source, profile


def exportWaterFile(context, filepath, scope='ALL_WATER', game_format='AUTO', apply_modifiers=False,
                    snap_xy=True, triangulate_ngons=False, validate_game=True, binary_profile='AUTO'):
    sectors = collectWaterSectors(context, scope, game_format, apply_modifiers,
                                  snap_xy, triangulate_ngons, validate_game)
    output_format = sectors[0].format
    if output_format == 'WATERPRO':
        source, profile = getWaterProSource(context, scope, binary_profile)
        data = buildWaterProBytes(sectors, profile, source)
        writeWaterData(bpy.path.abspath(str(filepath)), data)
    else:
        writeWaterFile(bpy.path.abspath(str(filepath)), sectors, game_format, validate_game)
    return len(sectors)
