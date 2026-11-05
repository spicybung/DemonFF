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

import bpy
import bmesh
from bpy.app.handlers import persistent
from mathutils import Vector

from ..gtaLib.water import calculateSanAndreasWave, WATER_VERTEX_LAYERS
from .water_mesh import getWaterVertexDefaults

PREVIEW_VERTEX_LIMIT = 250000


def waterSourceObject(obj):
    source = obj.get('water_preview_source')
    return source if isinstance(source, bpy.types.Object) else obj


def removeWaterPreview(source):
    for obj in list(bpy.data.objects):
        if obj.get('water_preview_source') == source:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
    if 'water_preview_hidden' in source:
        source.hide_set(bool(source['water_preview_hidden']))
        source.hide_render = bool(source.get('water_preview_render_hidden', False))
        del source['water_preview_hidden']
        if 'water_preview_render_hidden' in source:
            del source['water_preview_render_hidden']


def createWaterPreview(context, source, spacing=4.0):
    source = waterSourceObject(source)
    if source.type != 'MESH' or source.get('water_format') != 'SA':
        raise ValueError('Wave preview requires a San Andreas water mesh')
    if source.mode != 'OBJECT':
        raise ValueError('Leave Edit Mode before building the wave preview')
    if not math.isfinite(spacing) or spacing <= 0:
        raise ValueError('Preview spacing must be positive')
    bm = bmesh.new()
    mesh = None
    preview = None
    try:
        bm.from_mesh(source.data)
        defaults = getWaterVertexDefaults(source)
        for name, value in zip(WATER_VERTEX_LAYERS, defaults):
            if bm.verts.layers.float.get(name) is None:
                layer = bm.verts.layers.float.new(name)
                for vertex in bm.verts:
                    vertex[layer] = value
        # Each imported sector has independent edges, retaining discontinuous values.
        if not bm.faces:
            raise ValueError('No water sectors to preview')
        plans = []
        estimate = 0
        for face in bm.faces:
            if len(face.verts) not in (3, 4):
                raise ValueError('Preview water must contain triangles or quads')
            length = max((source.matrix_world.to_3x3() @ (e.verts[0].co - e.verts[1].co)).length for e in face.edges)
            segments = max(1, math.ceil(length / spacing))
            estimate += (segments + 1) ** 2 * 2
            plans.append((list(face.edges), segments - 1))
        if estimate > PREVIEW_VERTEX_LIMIT:
            raise ValueError('Wave preview is too dense; increase Preview Spacing or select fewer sectors')
        # Group edges to avoid subdividing shared boundaries twice.
        cuts_by_edge = {}
        for edges, cuts in plans:
            for edge in edges:
                cuts_by_edge[edge] = max(cuts_by_edge.get(edge, 0), cuts)
        for cuts in sorted(set(cuts_by_edge.values())):
            edges = [edge for edge, count in cuts_by_edge.items() if count == cuts and edge.is_valid]
            if cuts and edges:
                bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts, use_grid_fill=True)
        if len(bm.verts) > PREVIEW_VERTEX_LIMIT:
            raise ValueError('Wave preview exceeds the vertex budget; increase Preview Spacing')
        mesh = bpy.data.meshes.new(source.name + ' Wave Preview')
        bm.to_mesh(mesh)
        # Base positions persist with the blend; never accumulate displacements.
        if hasattr(mesh, 'attributes'):
            base = mesh.attributes.new('water_preview_base', 'FLOAT_VECTOR', 'POINT')
            for vertex, item in zip(mesh.vertices, base.data):
                item.vector = vertex.co
        else:
            mesh['water_preview_base_positions'] = [component for vertex in mesh.vertices for component in vertex.co]
        for material in source.data.materials:
            mesh.materials.append(material)
        for polygon in mesh.polygons:
            polygon.use_smooth = True
        preview = bpy.data.objects.new(source.name + ' Waves', mesh)
        context.collection.objects.link(preview)
        removeWaterPreview(source)
        preview['water_preview_source'] = source
        preview['water_preview_spacing'] = spacing
        source['water_preview_hidden'] = source.hide_get()
        source['water_preview_render_hidden'] = source.hide_render
        source.hide_set(True)
        source.hide_render = True
        context.view_layer.objects.active = preview
        source.select_set(False)
        preview.select_set(True)
        updateWaterWaves(context.scene)
        return preview
    except Exception:
        if preview is not None:
            if preview.get('water_preview_source') == source:
                removeWaterPreview(source)
                mesh = None
            else:
                bpy.data.objects.remove(preview, do_unlink=True)
        if mesh is not None and bpy.data.meshes.get(mesh.name) == mesh and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        raise
    finally:
        bm.free()


@persistent
def updateWaterWaves(scene, depsgraph=None):
    if scene.render.fps <= 0:
        return
    seconds = (scene.frame_current_final - scene.frame_start) * scene.render.fps_base / scene.render.fps
    seconds = seconds * float(scene.get('water_wave_speed', 1.0)) + float(scene.get('water_wave_time', 0.0))
    wavyness = float(scene.get('water_wavyness', 1.0))
    if not all(math.isfinite(value) for value in (seconds, wavyness)):
        return
    for preview in scene.objects:
        source = preview.get('water_preview_source')
        if not isinstance(source, bpy.types.Object) or source.type != 'MESH':
            continue
        if preview.type != 'MESH' or preview.mode == 'EDIT':
            continue
        mesh = preview.data
        attributes = mesh.attributes if hasattr(mesh, 'attributes') else None
        base = attributes.get('water_preview_base') if attributes is not None else None
        legacy_base = mesh.get('water_preview_base_positions', ())
        count = len(mesh.vertices)
        if source.mode == 'EDIT' or (base is None and len(legacy_base) != count * 3):
            continue
        if base is not None and len(base.data) != count:
            continue
        preview.matrix_world = source.matrix_world
        inverse = source.matrix_world.inverted_safe().to_3x3()
        float_layers = attributes if attributes is not None else mesh.vertex_layers_float
        big = float_layers.get('water_big_waves')
        small = float_layers.get('water_small_waves')
        if (big is not None and len(big.data) != count) or (small is not None and len(small.data) != count):
            continue
        for index, vertex in enumerate(mesh.vertices):
            position = base.data[index].vector.copy() if base is not None else Vector(legacy_base[index * 3:index * 3 + 3])
            world = source.matrix_world @ position
            big_value = big.data[index].value if big is not None else 1.0
            small_value = small.data[index].value if small is not None else 0.5
            if not all(math.isfinite(value) for value in (world.x, world.y, big_value, small_value)):
                continue
            displacement = calculateSanAndreasWave(world.x, world.y, seconds,
                                                   big_value, small_value, wavyness)
            vertex.co = position + inverse @ Vector((0, 0, displacement))
        mesh.update()


def registerWaterSimulation():
    if updateWaterWaves not in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.append(updateWaterWaves)
    if updateWaterWavesAfterLoad not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(updateWaterWavesAfterLoad)


@persistent
def updateWaterWavesAfterLoad(dummy):
    for scene in bpy.data.scenes:
        updateWaterWaves(scene)


def unregisterWaterSimulation():
    sources = [obj for obj in bpy.data.objects if 'water_preview_hidden' in obj]
    for source in sources:
        removeWaterPreview(source)
    for handlers, callback in ((bpy.app.handlers.frame_change_pre, updateWaterWaves),
                               (bpy.app.handlers.load_post, updateWaterWavesAfterLoad)):
        if callback in handlers:
            handlers.remove(callback)
