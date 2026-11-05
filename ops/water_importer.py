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
import hashlib
import math
from pathlib import Path

import bpy

from ..gtaLib.water import WATER_VERTEX_LAYERS, readWaterFile
from ..gtaLib.water import readWaterProFile, waterProSectors
from .water_mesh import createWaterMesh, initializeWaterObject


DEFAULT_WATER_TEXTURE = Path(__file__).resolve().parents[1] / 'resources' / 'water' / 'sa_waterclear256.png'


def createWaterMaterial(texture_path):
    texture_key = str(Path(texture_path).resolve())
    for material in bpy.data.materials:
        if material.get('demonff_water_texture') == texture_key and material.use_nodes:
            texture = material.node_tree.nodes.get('Water Texture')
            if texture is not None and texture.image is not None:
                return material
    image = bpy.data.images.load(texture_key, check_existing=True)
    if not image.packed_file:
        image.pack()
    material = bpy.data.materials.new('DemonFF Water')
    material['demonff_water_texture'] = texture_key
    material.use_nodes = True
    material.diffuse_color = (0.25, 0.55, 0.65, 1.0)
    nodes = material.node_tree.nodes
    shader = nodes.get('Principled BSDF')
    shader.inputs['Roughness'].default_value = 0.2
    texture = nodes.new('ShaderNodeTexImage')
    texture.name = 'Water Texture'
    texture.label = 'waterclear256'
    texture.image = image
    texture.extension = 'REPEAT'
    texture.location = (-500, 200)
    coordinates = nodes.new('ShaderNodeUVMap')
    coordinates.uv_map = 'UVMap'
    coordinates.location = (-750, 200)
    material.node_tree.links.new(coordinates.outputs['UV'], texture.inputs['Vector'])
    material.node_tree.links.new(texture.outputs['Color'], shader.inputs['Base Color'])
    material.node_tree.links.new(texture.outputs['Alpha'], shader.inputs['Alpha'])
    if hasattr(material, 'surface_render_method'):
        material.surface_render_method = 'DITHERED'
    elif hasattr(material, 'blend_method'):
        material.blend_method = 'HASHED'
    return material


def storeWaterProSource(document):
    digest = hashlib.sha256(document.raw).hexdigest()
    for text in bpy.data.texts:
        if text.get('waterpro_hash') == digest and text.get('waterpro_profile') == document.profile:
            return text
    text = bpy.data.texts.new('DemonFF WATERPRO source')
    text.write(base64.b64encode(document.raw).decode('ascii'))
    text['waterpro_hash'] = digest
    text['waterpro_profile'] = document.profile
    text.use_fake_user = True
    return text


def importWaterFile(context, filepath, game_format='AUTO', texture_path='', tile_size=32.0,
                    combine_meshes=False, skip_invalid=False, warnings=None, binary_profile='VC'):
    if context.mode != 'OBJECT':
        raise ValueError('Switch to Object Mode before importing water')
    if not math.isfinite(tile_size) or tile_size <= 0.0:
        raise ValueError('Texture tile size must be finite and positive')
    filepath = bpy.path.abspath(str(filepath))
    document = None
    binary = b'\x00' in Path(filepath).read_bytes()
    if binary or game_format == 'WATERPRO':
        if game_format not in {'AUTO', 'WATERPRO'}:
            raise ValueError('This is binary WATERPRO; select Automatic or WATERPRO format')
        document = readWaterProFile(filepath, binary_profile)
        sectors = waterProSectors(document)
    else:
        sectors = readWaterFile(filepath, game_format, skip_invalid, warnings)
    if not sectors:
        raise ValueError('This water file contains no wet sectors to import')
    texture_file = Path(bpy.path.abspath(str(texture_path))) if texture_path else DEFAULT_WATER_TEXTURE
    if not texture_file.is_file():
        raise ValueError('Water texture not found: ' + str(texture_file))
    objects = []
    meshes = []
    collection = None
    old_materials = set(bpy.data.materials)
    old_images = set(bpy.data.images)
    old_texts = set(bpy.data.texts)
    try:
        material = createWaterMaterial(texture_file)
        binary_text = storeWaterProSource(document) if document is not None else None
        collection = bpy.data.collections.new('Water - ' + Path(filepath).stem)
        context.scene.collection.children.link(collection)
        collection['water_source'] = str(Path(filepath).resolve())
        collection['water_format'] = sectors[0].format
        collection['demonff_water'] = True
        if binary_text is not None:
            collection['waterpro_source'] = binary_text.name
            collection['waterpro_profile'] = document.profile
        groups = [sectors] if combine_meshes else [[sector] for sector in sectors]
        for index, group in enumerate(groups):
            name = 'WaterMesh' if combine_meshes else f'WaterSector_{index:04d}'
            mesh = bpy.data.meshes.new(name)
            meshes.append(mesh)
            origin = createWaterMesh(mesh, group, tile_size, 0 if combine_meshes else index)
            mesh.materials.append(material)
            obj = bpy.data.objects.new(name, mesh)
            objects.append(obj)
            collection.objects.link(obj)
            obj.location = origin
            initializeWaterObject(obj, sectors[0].format)
            obj['water_sector'] = index
            obj['water_flags'] = str(group[0].flags)
            obj['water_line'] = group[0].line_number
            obj['water_source'] = collection['water_source']
            if binary_text is not None:
                obj['waterpro_source'] = binary_text.name
                obj['waterpro_profile'] = document.profile
            obj['water_tile_size'] = tile_size
            for field, value in zip(WATER_VERTEX_LAYERS, group[0].vertices[0][3:]):
                obj[field] = value
    except Exception:
        for obj in objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in meshes:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        if collection is not None:
            bpy.data.collections.remove(collection)
        for material in list(bpy.data.materials):
            if material not in old_materials and material.users == 0:
                bpy.data.materials.remove(material)
        for image in list(bpy.data.images):
            if image not in old_images and image.users == 0:
                bpy.data.images.remove(image)
        for text in list(bpy.data.texts):
            if text not in old_texts:
                bpy.data.texts.remove(text)
        raise
    for obj in context.selected_objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    context.view_layer.objects.active = objects[0]
    context.view_layer.update()
    return objects
