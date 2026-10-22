# DemonFF RenderWare 4 Blender importer

import os
import bpy

from ..gtaLib import rw4
from .importer_common import create_collection
from .state import State


class rw4_import_result:
    version = ''
    warning = ''
    profile = ''
    current_collection = None
    mesh_count = 0
    resource_count = 0


def link_object_to_collection(obj, collection):
    collection.objects.link(obj)


def create_empty(collection, name, properties=None):
    obj = bpy.data.objects.new(name, None)
    link_object_to_collection(obj, collection)
    if properties:
        for key, value in properties.items():
            try:
                obj[key] = value
            except Exception:
                pass
    return obj


def import_parsed_mesh(collection, parsed_mesh, profile):
    mesh = bpy.data.meshes.new(parsed_mesh.name)
    mesh.from_pydata(parsed_mesh.vertices, [], parsed_mesh.triangles)
    mesh.update(calc_edges=True)

    obj = bpy.data.objects.new(parsed_mesh.name, mesh)
    collection.objects.link(obj)
    obj['demonff_rw4_profile'] = rw4.PROFILE_LABELS[profile]
    obj['demonff_rw4_mesh_index'] = parsed_mesh.source_mesh_index

    if parsed_mesh.uvs and any(uv is not None for uv in parsed_mesh.uvs):
        uv_layer = mesh.uv_layers.new(name='UVMap')
        for loop in mesh.loops:
            if loop.vertex_index < len(parsed_mesh.uvs):
                uv = parsed_mesh.uvs[loop.vertex_index]
                if uv is not None:
                    uv_layer.data[loop.index].uv = (uv[0], -uv[1])

    if parsed_mesh.colors and any(color is not None for color in parsed_mesh.colors):
        try:
            color_layer = mesh.color_attributes.new(name='RW4Color', type='BYTE_COLOR', domain='CORNER')
            for loop in mesh.loops:
                if loop.vertex_index < len(parsed_mesh.colors):
                    color = parsed_mesh.colors[loop.vertex_index]
                    if color is not None:
                        color_layer.data[loop.index].color = color
        except Exception:
            pass

    if parsed_mesh.normals and all(normal is not None for normal in parsed_mesh.normals):
        try:
            loop_normals = [parsed_mesh.normals[loop.vertex_index] for loop in mesh.loops]
            mesh.normals_split_custom_set(loop_normals)
        except Exception:
            pass

    return obj


def import_spore(file_name, data, detection):
    result = rw4_import_result()
    result.version = '4.5.0.1'
    result.profile = rw4.PROFILE_SPORE
    collection = create_collection(os.path.basename(file_name))
    result.current_collection = collection

    arena = rw4.parse_spore_arena(data, detection.arena_offset)
    try:
        collection['demonff_rw4_profile'] = rw4.PROFILE_LABELS[rw4.PROFILE_SPORE]
        collection['demonff_rw4_platform'] = arena.platform
        collection['demonff_rw4_version_text'] = arena.version_text
        collection['demonff_rw4_section_count'] = arena.section_count
    except Exception:
        pass

    for parsed_mesh in arena.parsed_meshes:
        import_parsed_mesh(collection, parsed_mesh, rw4.PROFILE_SPORE)
        result.mesh_count += 1

    if result.mesh_count == 0:
        create_empty(collection, 'RW4 Resource', {
            'demonff_rw4_profile': rw4.PROFILE_LABELS[rw4.PROFILE_SPORE],
            'demonff_rw4_section_count': arena.section_count,
            'demonff_rw4_type_code': arena.rw_type_code,
        })
        result.warning = 'Spore (4.5.0.1) RW4 parsed, but no supported mesh sections were found.'
    return result


def import_crackdown(file_name, data, detection):
    result = rw4_import_result()
    result.version = '4.1.0.1'
    result.profile = rw4.PROFILE_CRACKDOWN
    collection = create_collection(os.path.basename(file_name))
    result.current_collection = collection
    container = rw4.parse_crackdown_container(data)

    try:
        collection['demonff_rw4_profile'] = rw4.PROFILE_LABELS[rw4.PROFILE_CRACKDOWN]
        collection['demonff_rw4_resource_count'] = len(container.resources)
        collection['demonff_rw4_arena_count'] = len(container.arenas)
    except Exception:
        pass

    classes_collection = bpy.data.collections.new('Classes')
    resources_collection = bpy.data.collections.new('Resources')
    arenas_collection = bpy.data.collections.new('RW4 Arenas')
    geometry_collection = bpy.data.collections.new('Geometry')
    collection.children.link(classes_collection)
    collection.children.link(resources_collection)
    collection.children.link(arenas_collection)
    collection.children.link(geometry_collection)

    for class_name in container.classes:
        create_empty(classes_collection, class_name, {'demonff_rw4_class': class_name})

    for resource in container.resources:
        create_empty(resources_collection, resource.name, {
            'demonff_rw4_resource_kind': resource.kind,
            'demonff_rw4_source_offset': resource.offset,
        })
        result.resource_count += 1

    for index, arena_info in enumerate(container.arenas):
        arena_name = 'Arena_%03d_%s' % (index, arena_info.platform or 'unknown')
        create_empty(arenas_collection, arena_name, {
            'demonff_rw4_profile': rw4.PROFILE_LABELS[rw4.PROFILE_CRACKDOWN],
            'demonff_rw4_source_offset': arena_info.offset,
            'demonff_rw4_platform': arena_info.platform,
            'demonff_rw4_footer_offset': arena_info.footer_offset,
            'demonff_rw4_section_count': arena_info.section_count,
            'demonff_rw4_mesh_count': len(arena_info.parsed_meshes),
            'demonff_rw4_resource_name': arena_info.resource_name,
        })

        if arena_info.parsed_meshes:
            child_name = arena_info.resource_name or arena_name
            arena_geometry = bpy.data.collections.new(child_name)
            geometry_collection.children.link(arena_geometry)
            try:
                arena_geometry['demonff_rw4_profile'] = rw4.PROFILE_LABELS[rw4.PROFILE_CRACKDOWN]
                arena_geometry['demonff_rw4_source_offset'] = arena_info.offset
                arena_geometry['demonff_rw4_resource_name'] = arena_info.resource_name
            except Exception:
                pass
            for parsed_mesh in arena_info.parsed_meshes:
                obj = import_parsed_mesh(arena_geometry, parsed_mesh, rw4.PROFILE_CRACKDOWN)
                try:
                    obj['demonff_rw4_arena_offset'] = arena_info.offset
                    obj['demonff_rw4_resource_name'] = arena_info.resource_name
                except Exception:
                    pass
                result.mesh_count += 1
        elif arena_info.platform == 'w32':
            try:
                arena = rw4.parse_spore_arena(data, arena_info.offset)
            except Exception:
                arena = None
            if arena is not None:
                child_name = arena_info.resource_name or arena_name
                arena_geometry = bpy.data.collections.new(child_name)
                geometry_collection.children.link(arena_geometry)
                for parsed_mesh in arena.parsed_meshes:
                    import_parsed_mesh(arena_geometry, parsed_mesh, rw4.PROFILE_CRACKDOWN)
                    result.mesh_count += 1

    if result.mesh_count == 0:
        result.warning = 'Crackdown (4.1.0.1) RW4 parsed, but no supported geometry was found.'
    return result


def import_rw4(file_name, forced_profile=rw4.PROFILE_AUTO, defer_scene_update=False):
    data = rw4.read_file_bytes(file_name)
    detection = rw4.detect_bytes(data, forced_profile)
    if detection is None:
        raise rw4.RW4Error('Not a supported RenderWare 4 file')

    if detection.profile == rw4.PROFILE_SPORE:
        result = import_spore(file_name, data, detection)
    elif detection.profile == rw4.PROFILE_CRACKDOWN:
        result = import_crackdown(file_name, data, detection)
    else:
        raise rw4.RW4Error('Unsupported RenderWare 4 profile')

    if not defer_scene_update:
        State.update_scene()
    return result
