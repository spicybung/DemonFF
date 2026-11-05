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

import math

import bmesh

from ..gtaLib.water import (
    WATER_VERTEX_DEFAULTS, WATER_VERTEX_LAYERS, WaterSector,
    parseWaterFlags, validateWaterSector, waterFaceOrder,
)


def initializeWaterObject(obj, game_format='SA'):
    obj['water_format'] = obj.get('water_format', game_format)
    obj['water_flags'] = str(obj.get('water_flags', '0'))
    for name, value in zip(WATER_VERTEX_LAYERS, WATER_VERTEX_DEFAULTS):
        if name not in obj:
            obj[name] = value if game_format == 'SA' else 0.0
    if 'water_sector' not in obj:
        obj['water_sector'] = 0


def getWaterVertexDefaults(obj, game_format='SA'):
    defaults = WATER_VERTEX_DEFAULTS if game_format == 'SA' else (0.0,) * 4
    values = tuple(float(obj.get(name, value)) for name, value in zip(WATER_VERTEX_LAYERS, defaults))
    if not all(math.isfinite(value) for value in values):
        raise ValueError('Water flow and wave values must be finite')
    return values


def waterSignedFlags(flags):
    flags = parseWaterFlags(flags)
    return flags if flags <= 2147483647 else flags - 4294967296


def createWaterMesh(mesh, sectors, tile_size, sector_start=0):
    positions = [vertex[:3] for sector in sectors for vertex in sector.vertices]
    origin = tuple(sum(position[axis] for position in positions) / len(positions) for axis in range(3))
    bm = bmesh.new()
    try:
        vertex_layers = [bm.verts.layers.float.new(name) for name in WATER_VERTEX_LAYERS]
        flags_layer = bm.faces.layers.int.new('water_flags')
        sector_layer = bm.faces.layers.int.new('water_sector')
        line_layer = bm.faces.layers.int.new('water_line')
        level_layer = bm.faces.layers.int.new('water_level')
        uv_layer = bm.loops.layers.uv.new('UVMap')
        for sector_index, sector in enumerate(sectors, sector_start):
            vertices = []
            for source in sector.vertices:
                vertex = bm.verts.new(tuple(source[axis] - origin[axis] for axis in range(3)))
                for layer, value in zip(vertex_layers, source[3:]):
                    vertex[layer] = value
                vertices.append(vertex)
            face = bm.faces.new([vertices[index] for index in waterFaceOrder(sector.vertices)])
            face[flags_layer] = waterSignedFlags(sector.flags)
            face[sector_layer] = sector_index
            face[line_layer] = sector.line_number
            face[level_layer] = sector.level_index
            for loop in face.loops:
                loop[uv_layer].uv = ((loop.vert.co.x + origin[0]) / tile_size,
                                     (loop.vert.co.y + origin[1]) / tile_size)
        bm.normal_update()
        bm.to_mesh(mesh)
        mesh.update()
    finally:
        bm.free()
    return origin



def applyWaterObjectSettings(obj, selected_only=False):
    if obj.type != 'MESH':
        raise ValueError('Select a mesh object')
    initializeWaterObject(obj, obj.get('water_format', 'SA'))
    values = getWaterVertexDefaults(obj, obj['water_format'])
    flags = waterSignedFlags(obj['water_flags'])
    edit_mode = obj.data.is_editmode
    bm = bmesh.from_edit_mesh(obj.data) if edit_mode else bmesh.new()
    try:
        if not edit_mode:
            bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        legacy = obj.get('water_vertex_data', ())
        use_legacy = len(bm.faces) == 1 and len(legacy) == len(bm.verts) * 7
        vertex_layers = []
        for index, (name, value) in enumerate(zip(WATER_VERTEX_LAYERS, values)):
            layer = bm.verts.layers.float.get(name)
            if layer is None:
                layer = bm.verts.layers.float.new(name)
                for vertex in bm.verts:
                    vertex[layer] = legacy[vertex.index * 7 + 3 + index] if use_legacy else value
            vertex_layers.append(layer)
        existing_flags = bm.faces.layers.int.get('water_flags')
        flags_layer = existing_flags or bm.faces.layers.int.new('water_flags')
        if existing_flags is None:
            for face in bm.faces:
                face[flags_layer] = flags
        for vertex in bm.verts:
            if not selected_only or vertex.select:
                for layer, value in zip(vertex_layers, values):
                    vertex[layer] = value
        for face in bm.faces:
            if not selected_only or face.select:
                face[flags_layer] = flags
        if edit_mode:
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        else:
            bm.to_mesh(obj.data)
            obj.data.update()
    finally:
        if not edit_mode:
            bm.free()


def waterSectorsFromMesh(obj, mesh, game_format, snap_xy=False, triangulate_ngons=False):
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        bm.faces.ensure_lookup_table()
        if triangulate_ngons:
            ngons = [face for face in bm.faces if len(face.verts) > 4]
            if ngons:
                bmesh.ops.triangulate(bm, faces=ngons)
        bm.faces.index_update()
        vertex_layers = [bm.verts.layers.float.get(name) for name in WATER_VERTEX_LAYERS]
        flags_layer = bm.faces.layers.int.get('water_flags')
        sector_layer = bm.faces.layers.int.get('water_sector')
        line_layer = bm.faces.layers.int.get('water_line')
        level_layer = bm.faces.layers.int.get('water_level')
        defaults = getWaterVertexDefaults(obj, game_format)
        legacy = obj.get('water_vertex_data', ())
        use_legacy = len(bm.faces) == 1 and len(legacy) == len(bm.verts) * 7
        output = []
        faces = sorted(bm.faces, key=lambda face: (face[sector_layer] if sector_layer else face.index, face.index))
        for face in faces:
            try:
                if len(face.verts) not in (3, 4):
                    raise ValueError('Use triangles/quads or enable Triangulate N-gons')
                vertices = []
                for vertex in face.verts:
                    position = obj.matrix_world @ vertex.co
                    x, y, z = tuple(position)
                    if snap_xy and game_format == 'SA':
                        if not math.isfinite(x) or not math.isfinite(y):
                            raise ValueError('Water coordinates must be finite')
                        x, y = round(x), round(y)
                    parameters = []
                    for index, layer in enumerate(vertex_layers):
                        if layer is not None:
                            value = vertex[layer]
                        elif use_legacy:
                            value = legacy[vertex.index * 7 + 3 + index]
                        else:
                            value = defaults[index]
                        parameters.append(float(value))
                    vertices.append((x, y, z, *parameters))
                flags = face[flags_layer] & 4294967295 if flags_layer is not None else parseWaterFlags(obj.get('water_flags', '0'))
                line = face[line_layer] if line_layer is not None else int(obj.get('water_line', 0))
                level = face[level_layer] if level_layer is not None else -1
                sector = WaterSector(tuple(vertices), flags, line, game_format, level)
                validateWaterSector(sector)
                output.append(sector)
            except (ValueError, OverflowError) as error:
                raise ValueError(f'{obj.name}, face {face.index}: {error}') from error
        if not output:
            raise ValueError(obj.name + ': no water faces found')
        return output
    finally:
        bm.free()
