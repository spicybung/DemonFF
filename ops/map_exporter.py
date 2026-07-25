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
import os
import re
import time
import ast
import operator
import mathutils

from ..data import map_data
from ..ops.importer_common import game_version
from .map_transform import (
    blender_quaternion_to_ipl,
    gta_euler_degrees_to_quaternion,
    quaternion_to_gta_euler_degrees,
)
from . import dff_importer
from .state import State



#######################################################
def radians_to_degrees(value):
    return value * (180.0 / 3.141592653589793)

#######################################################
def euler_to_degrees(euler):
    return (
        radians_to_degrees(euler.x),
        radians_to_degrees(euler.y),
        radians_to_degrees(euler.z),
    )

#######################################################
def quat_to_degrees(quat):
    return quaternion_to_gta_euler_degrees(quat)

IDE_TO_SAMP_DL_IDS = {i: 0 + i for i in range(50000)}

#######################################################
def clean_map_name(name):
    return name.split('.')[0]

#######################################################
def get_metadata_source(obj):
    if obj is None:
        return None
    parent = getattr(obj, 'parent', None)
    if parent is not None and getattr(parent, 'type', None) == 'EMPTY':
        return parent
    return obj

#######################################################
def get_custom_prop(obj, key, default=None):
    for source in (obj, get_metadata_source(obj)):
        if source is None:
            continue
        try:
            if key in source:
                return source[key]
        except Exception:
            pass
    return default

#######################################################
def get_dff_type(obj):
    for source in (obj, get_metadata_source(obj)):
        if source is not None and hasattr(source, 'dff') and hasattr(source.dff, 'type'):
            return source.dff.type
    return ""

#######################################################
def get_map_props(obj):
    for source in (obj, get_metadata_source(obj)):
        if source is not None and hasattr(source, 'dff_map'):
            return source.dff_map
    return None

#######################################################
def first_good_value(*values, default=None):
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value == "":
            continue
        return value
    return default

#######################################################
def is_placeholder_txd_name(value):
    clean_value = str(value or "").strip().lower()
    if clean_value.endswith(".txd"):
        clean_value = clean_value[:-4]
    return clean_value in {"", "default", "default_txd", "none", "null"}

#######################################################
def first_good_txd_value(*values, default=None):
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip() == "":
                continue
            if is_placeholder_txd_name(value):
                continue
        return value
    return default

#######################################################
def set_map_identity_props(obj, ide_id, model_name, txd_name, samp_id=None):
    obj["IDE_ID"] = ide_id
    obj["DFF_Name"] = model_name
    obj["TXD_Name"] = txd_name
    if samp_id is not None:
        obj["SAMP_ID"] = samp_id

    if hasattr(obj, "ide"):
        obj.ide.obj_id = str(ide_id)
        obj.ide.model_name = str(model_name)
        obj.ide.txd_name = str(txd_name)

    if hasattr(obj, "dff_map"):
        obj.dff_map.object_id = int(ide_id) if str(ide_id).lstrip('-').isdigit() else 0
        obj.dff_map.model_name = str(model_name)
        obj.dff_map.ide_object_id = int(ide_id) if str(ide_id).lstrip('-').isdigit() else 0
        obj.dff_map.ide_model_name = str(model_name)
        obj.dff_map.ide_txd_name = str(txd_name)
        if not obj.dff_map.pawn_model_name:
            obj.dff_map.pawn_model_name = str(model_name)
        if not obj.dff_map.pawn_txd_name:
            obj.dff_map.pawn_txd_name = str(txd_name)

#######################################################
def get_object_model_name(obj):
    props = get_map_props(obj)
    if props:
        return str(first_good_value(props.model_name, props.ide_model_name, props.pawn_model_name, default=clean_map_name(obj.name)))
    if hasattr(obj, "ide") and obj.ide.model_name:
        return obj.ide.model_name
    return str(get_custom_prop(obj, "DFF_Name", clean_map_name(obj.name)))

#######################################################
def get_object_txd_name(obj):
    props = get_map_props(obj)
    if props:
        return str(first_good_txd_value(props.ide_txd_name, props.pawn_txd_name, default=None) or get_custom_prop(obj, "TXD_Name", "default_txd"))
    if hasattr(obj, "ide") and obj.ide.txd_name and not is_placeholder_txd_name(obj.ide.txd_name):
        return obj.ide.txd_name
    custom_value = get_custom_prop(obj, "TXD_Name", "default_txd")
    return str(custom_value if not is_placeholder_txd_name(custom_value) else "default_txd")

#######################################################
def get_pawn_model_name(obj):
    props = get_map_props(obj)
    if props and props.pawn_model_name:
        return props.pawn_model_name
    return get_object_model_name(obj)

#######################################################
def get_pawn_txd_name(obj):
    props = get_map_props(obj)
    if props and props.pawn_txd_name and not is_placeholder_txd_name(props.pawn_txd_name):
        return props.pawn_txd_name
    return get_object_txd_name(obj)

#######################################################
def get_object_ide_id(obj, default=0):
    props = get_map_props(obj)
    if props:
        value = first_good_value(props.object_id, props.ide_object_id, default=None)
        if value not in (None, 0):
            return value
    if hasattr(obj, "ide") and obj.ide.obj_id:
        return obj.ide.obj_id
    return get_custom_prop(obj, "IDE_ID", default)

#######################################################
def get_object_samp_id(obj, default=None):
    if "SAMP_ID" in obj:
        return obj["SAMP_ID"]
    return default

#######################################################
def get_object_interior(obj, default=0):
    props = get_map_props(obj)
    if props and props.interior not in (None, 0):
        return props.interior
    if hasattr(obj, "ipl") and obj.ipl.interior:
        return obj.ipl.interior
    return get_custom_prop(obj, "Interior", default)

#######################################################
def get_stream_world_and_interior(obj, default_world=-1, default_interior=-1):
    interior = get_object_interior(obj, default_interior)

    # The third field in Stories/VC-derived text IPL rows is frequently an
    # area value rather than a usable SA-MP virtual world. Optimize for SAMP
    # stamps explicit Pawn world/interior metadata during import.
    if getattr(pwn_exporter, "force_all_worlds_interiors", True):
        return -1, -1

    world = get_custom_prop(obj, "Pawn_World_ID", default_world)
    pawn_interior = get_custom_prop(obj, "Pawn_Interior_ID", interior)
    return world, pawn_interior

#######################################################
def get_object_lod(obj, default=-1):
    props = get_map_props(obj)
    if props and props.lod not in (None, 0):
        return props.lod
    if hasattr(obj, "ipl") and obj.ipl.lod:
        return obj.ipl.lod
    return get_custom_prop(obj, "LODIndex", default)

#######################################################
def get_object_flags(obj, default=0):
    props = get_map_props(obj)
    if props and props.ide_flags:
        return props.ide_flags
    if hasattr(obj, "ide") and obj.ide.flags:
        return obj.ide.flags
    return get_custom_prop(obj, "IDE_Flags", default)

#######################################################
def get_object_draw_distances(obj):
    props = get_map_props(obj)
    if props:
        distances = []
        for value in (props.ide_draw1, props.ide_draw2, props.ide_draw3):
            if value:
                distances.append(str(value))
        if not distances and props.ide_draw_distance:
            distances.append(str(props.ide_draw_distance))
        if distances:
            return distances

    if hasattr(obj, "ide"):
        distances = []
        if obj.ide.draw_distance:
            distances.append(obj.ide.draw_distance)
        if obj.ide.draw_distance1:
            distances.append(obj.ide.draw_distance1)
        if obj.ide.draw_distance2:
            distances.append(obj.ide.draw_distance2)
        if obj.ide.draw_distance3:
            distances.append(obj.ide.draw_distance3)
        if distances:
            return distances
    return [str(get_custom_prop(obj, "DrawDistance", 300.0))]

#######################################################
def get_object_ide_section(obj):
    props = get_map_props(obj)
    if props and props.ide_section:
        return props.ide_section
    if hasattr(obj, "ide") and obj.ide.obj_type:
        return obj.ide.obj_type
    return "objs"

#######################################################
def object_is_lod(obj):
    name = obj.name.lower()
    return name.startswith("lod") or ".colmesh" in name or get_dff_type(obj) == 'COL'

#######################################################
def object_is_synthetic_chunk(obj):
    names = [
        getattr(obj, 'name', ''),
        get_object_model_name(obj),
        get_pawn_model_name(obj),
    ]

    for name in names:
        clean_name = clean_map_name(str(name or '')).strip()
        clean_name = re.sub(r'\.\d+$', '', clean_name)
        if clean_name.lower() == 'chunk':
            return True

    return False

#######################################################
def object_is_primary_empty_child(obj):
    parent = getattr(obj, 'parent', None)
    if parent is None or getattr(parent, 'type', None) != 'EMPTY':
        return True

    mesh_children = [child for child in parent.children if child.type == 'MESH' and not object_is_lod(child)]
    if len(mesh_children) <= 1:
        return True

    parent_name = clean_map_name(parent.name).lower()
    object_name = clean_map_name(obj.name).lower()
    model_name = clean_map_name(get_object_model_name(obj)).lower()

    if object_name in {parent_name, model_name}:
        return True

    sorted_children = sorted(mesh_children, key=lambda child: child.name.lower())
    return obj == sorted_children[0]

#######################################################
def object_is_exportable_map_instance(obj):
    if obj.type != 'MESH':
        return False

    dff_type = get_dff_type(obj)
    if dff_type and dff_type != 'OBJ':
        return False

    if obj.parent and obj.parent.type != 'EMPTY':
        return False

    if not object_is_primary_empty_child(obj):
        return False

    return True

#######################################################
def object_is_2dfx_pawn_helper(obj):
    names = [
        obj.name,
        clean_map_name(obj.name),
        get_object_model_name(obj),
        get_pawn_model_name(obj),
    ]

    for name in names:
        if not name:
            continue

        clean_name = str(name).lower().split('.')[0]
        if clean_name.startswith("2dfx_"):
            return True

    return get_dff_type(obj) == '2DFX'

#######################################################
def get_transform_source(obj):
    if obj.parent and obj.parent.type == 'EMPTY':
        return obj.parent
    return obj

#######################################################
def get_export_matrix(obj):
    source = get_transform_source(obj)
    return source.matrix_world.copy()

#######################################################
def get_export_transform(obj):
    matrix = get_export_matrix(obj)
    position, rotation, scale = matrix.decompose()
    rotation.normalize()
    return position, rotation, scale

#######################################################
def get_pawn_rotation(obj):
    position, rotation, scale = get_export_transform(obj)
    return quaternion_to_gta_euler_degrees(rotation)


#######################################################
def normalize_map_lookup_name(value):
    clean_value = str(value or "").strip().replace('\\', '/')
    clean_value = os.path.basename(clean_value)
    clean_value = os.path.splitext(clean_value)[0]
    clean_value = clean_value.split('.')[0]
    return clean_value.lower()

#######################################################
def normalize_export_asset_name(value, extension):
    clean_value = str(value or "").strip().replace('\\', '/')
    clean_value = os.path.basename(clean_value)
    clean_value = clean_value.split('.')[0]

    if extension and clean_value.lower().endswith(extension.lower()):
        clean_value = clean_value[:-len(extension)]

    return clean_value

#######################################################
def normalize_export_directory(value):
    clean_value = str(value or "").strip().replace('\\', '/')
    clean_value = clean_value.strip('/')
    return clean_value

#######################################################
def make_artconfig_asset_path(directory, name, extension):
    clean_directory = normalize_export_directory(directory)
    clean_name = normalize_export_asset_name(name, extension)

    if not clean_name:
        clean_name = "default_txd" if extension.lower() == ".txd" else "model"

    filename = clean_name + extension
    return f"{clean_directory}/{filename}" if clean_directory else filename

#######################################################
def make_addsimplemodel_line(virtual_world, base_model_id, model_id, dff_directory, txd_directory, model_name, txd_name):
    dff_path = make_artconfig_asset_path(dff_directory, model_name, ".dff")
    txd_path = make_artconfig_asset_path(txd_directory, txd_name, ".txd")
    comment_name = normalize_export_asset_name(model_name, ".dff")
    return f"AddSimpleModel({virtual_world}, {base_model_id}, {model_id}, \"{dff_path}\", \"{txd_path}\");  // {comment_name}\n", dff_path, txd_path

#######################################################

#######################################################
def parse_ide_model_records(filepath):
    records = {}
    section = None
    supported_sections = {"objs", "tobj", "anim"}

    if not filepath or not os.path.isfile(filepath):
        return records

    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            lines = file.readlines()
    except UnicodeDecodeError:
        with open(filepath, 'r', encoding='latin-1', errors='replace') as file:
            lines = file.readlines()

    for line_number, line in enumerate(lines, 1):
        line = line.split('#', 1)[0].strip()
        if not line:
            continue

        lower_line = line.lower()
        if lower_line in supported_sections:
            section = lower_line
            continue

        if lower_line == "end":
            section = None
            continue

        if section not in supported_sections:
            continue

        parts = [part.strip() for part in line.split(',')]
        if len(parts) < 3:
            continue

        try:
            object_id = int(parts[0], 0)
        except Exception:
            continue

        model_name = parts[1]
        txd_name = parts[2]
        key = normalize_map_lookup_name(model_name)
        if not key:
            continue

        records[key] = {
            "object_id": object_id,
            "model_name": model_name,
            "txd_name": txd_name,
            "section": section,
            "filepath": filepath,
            "line": line_number,
        }

    return records

#######################################################
def collect_scene_ide_filepaths(context, output_file=None):
    paths = []
    scene = getattr(context, 'scene', None)
    scene_dff = getattr(scene, 'dff', None) if scene is not None else None

    if scene_dff is not None and hasattr(scene_dff, 'ide_paths'):
        for item in scene_dff.ide_paths:
            path = getattr(item, 'name', '')
            if path and path.lower().endswith('.ide'):
                paths.append(bpy.path.abspath(path))

    search_dirs = []
    if output_file:
        search_dirs.append(os.path.dirname(os.path.abspath(output_file)))
    try:
        if bpy.data.filepath:
            search_dirs.append(os.path.dirname(os.path.abspath(bpy.data.filepath)))
    except Exception:
        pass

    for directory in search_dirs:
        if not directory or not os.path.isdir(directory):
            continue
        for filename in os.listdir(directory):
            if filename.lower().endswith('.ide'):
                paths.append(os.path.join(directory, filename))

    unique_paths = []
    seen = set()
    for path in paths:
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_paths.append(path)
    return unique_paths

#######################################################
def collect_ide_txd_lookup(context, output_file=None):
    lookup = {}
    for filepath in collect_scene_ide_filepaths(context, output_file):
        lookup.update(parse_ide_model_records(filepath))
    return lookup

#######################################################
def apply_ide_record_to_object(obj, record, samp_id=None):
    if obj is None or record is None:
        return
    set_map_identity_props(
        obj,
        record.get("object_id", 0),
        record.get("model_name", clean_map_name(obj.name)),
        record.get("txd_name", "default_txd"),
        samp_id,
    )

#######################################################
def resolve_export_txd_name(obj, ide_txd_lookup=None):
    txd_name = get_pawn_txd_name(obj)
    if not is_placeholder_txd_name(txd_name):
        return normalize_export_asset_name(txd_name, ".txd")

    lookup = ide_txd_lookup or {}
    model_name = get_pawn_model_name(obj)

    lookup_names = [
        model_name,
        obj.name,
        clean_map_name(obj.name),
    ]

    parent = getattr(obj, 'parent', None)
    if parent is not None:
        lookup_names.extend([parent.name, clean_map_name(parent.name)])

    record = None
    for lookup_name in lookup_names:
        record = lookup.get(normalize_map_lookup_name(lookup_name))
        if record is not None:
            break

    if record is not None and not is_placeholder_txd_name(record.get("txd_name")):
        apply_ide_record_to_object(get_metadata_source(obj), record, get_object_samp_id(obj))
        return normalize_export_asset_name(record.get("txd_name"), ".txd")

    custom_value = get_custom_prop(obj, "TXD_Name", None)
    if not is_placeholder_txd_name(custom_value):
        return normalize_export_asset_name(custom_value, ".txd")

    return "default_txd"

#######################################################
def import_ide(filepaths, context):
    for filepath in filepaths:
        if not os.path.isfile(filepath):
            print(f"File not found: {filepath}")
            continue

        try:
            # Attempt to open and read as UTF-8
            with open(filepath, 'r', encoding='utf-8') as file:
                lines = file.readlines()
        except UnicodeDecodeError:
            print(f"UTF-8 decoding failed for {filepath}, attempting ASCII decoding.")
            try:
                # Fallback to ASCII encoding
                with open(filepath, 'r', encoding='ascii', errors='replace') as file:
                    lines = file.readlines()
            except UnicodeDecodeError:
                print(f"Error decoding file: {filepath}")
                continue

        obj_data = {}
        for key, record in parse_ide_model_records(filepath).items():
            obj_id = record["object_id"]
            obj_name = record["model_name"]
            txd_name = record["txd_name"]
            samp_id = IDE_TO_SAMP_DL_IDS.get(obj_id, obj_id)
            obj_data[key] = (samp_id, obj_name, txd_name, record)

        for obj in context.scene.objects:
            base_name = normalize_map_lookup_name(obj.name)
            if base_name in obj_data:
                samp_id, obj_name, txd_name, record = obj_data[base_name]
                set_map_identity_props(obj, abs(int(samp_id)), obj_name, txd_name, samp_id)
                print(f"Assigned SAMP ID {samp_id} and TXD {txd_name} to {obj.name}")
            else:
                print(f"No matching SAMP ID found for {obj.name}")

    print("SAMP IDE import completed for all files")
#######################################################
def mass_import_samp_ide(filepaths, context):
    for filepath in filepaths:
        if not filepath.endswith('.ide'):
            print(f"Skipped non-IDE file: {filepath}")
            continue

        print(f"Importing SAMP IDE from {filepath}")
        if not os.path.isfile(filepath):
            print(f"File not found: {filepath}")
            continue

        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                lines = file.readlines()
        except UnicodeDecodeError:
            print(f"UTF-8 decoding failed for {filepath}, attempting ASCII decoding.")
            try:
                with open(filepath, 'r', encoding='ascii', errors='replace') as file:
                    lines = file.readlines()
            except UnicodeDecodeError:
                print(f"Error decoding file: {filepath}")
                continue

        obj_data = {}
        for key, record in parse_ide_model_records(filepath).items():
            obj_id = record["object_id"]
            obj_name = record["model_name"]
            txd_name = record["txd_name"]
            samp_id = IDE_TO_SAMP_DL_IDS.get(obj_id, obj_id)
            obj_data[key] = (samp_id, obj_name, txd_name, record)

        # Match objects in the scene with the IDE data and apply SAMP ID and TXD name
        for obj in context.scene.objects:
            base_name = normalize_map_lookup_name(obj.name)
            if base_name in obj_data:
                samp_id, obj_name, txd_name, record = obj_data[base_name]
                samp_id = -abs(samp_id)
                set_map_identity_props(obj, abs(int(samp_id)), obj_name, txd_name, samp_id)
                print(f"Assigned SAMP ID {samp_id} and TXD {txd_name} to {obj.name}")
            else:
                print(f"No matching SAMP ID found for {obj.name}")

    print("Mass SAMP IDE import completed")
#######################################################
#######################################################
def collect_ipl_export_objects(context, only_selected=True):
    objects = []
    for obj in context.scene.objects:
        if only_selected and not obj.select_get():
            continue
        if not object_is_exportable_map_instance(obj):
            continue
        objects.append(obj)
    return objects

#######################################################
def format_ipl_inst_line(context, obj, game_id=None):
    if game_id is None:
        game_id = context.scene.dff.game_version_dropdown
    object_id = get_object_ide_id(obj, 0)
    model_name = get_object_model_name(obj)
    interior = get_object_interior(obj, 0)
    lod_index = get_object_lod(obj, -1)
    position, rotation, scale = get_export_transform(obj)
    rot_x, rot_y, rot_z, rot_w = blender_quaternion_to_ipl(rotation)

    if game_id == game_version.III:
        return (
            f"{object_id}, {model_name}, "
            f"{position.x:.6f}, {position.y:.6f}, {position.z:.6f}, "
            f"{scale.x:.6f}, {scale.y:.6f}, {scale.z:.6f}, "
            f"{rot_x:.6f}, {rot_y:.6f}, {rot_z:.6f}, {rot_w:.6f}"
        )

    if game_id == game_version.VC:
        return (
            f"{object_id}, {model_name}, {interior}, "
            f"{position.x:.6f}, {position.y:.6f}, {position.z:.6f}, "
            f"{scale.x:.6f}, {scale.y:.6f}, {scale.z:.6f}, "
            f"{rot_x:.6f}, {rot_y:.6f}, {rot_z:.6f}, {rot_w:.6f}"
        )

    return (
        f"{object_id}, {model_name}, {interior}, "
        f"{position.x:.6f}, {position.y:.6f}, {position.z:.6f}, "
        f"{rot_x:.6f}, {rot_y:.6f}, {rot_z:.6f}, {rot_w:.6f}, {lod_index}"
    )

#######################################################
def export_ipl_file(context, filename, only_selected=True, skip_lod=False, game_id=None):
    output_file = filename if filename.lower().endswith('.ipl') else filename + '.ipl'
    objects = collect_ipl_export_objects(context, only_selected)
    written = 0
    with open(output_file, 'w', encoding='latin-1') as file:
        file.write('inst\n')
        for obj in objects:
            if skip_lod and object_is_lod(obj):
                continue
            file.write(format_ipl_inst_line(context, obj, game_id) + f"  # {obj.name}\n")
            written += 1
        file.write('end\n')
    return output_file, written

#######################################################
def format_ide_objs_line(obj):
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

#######################################################
def format_ide_tobj_line(obj):
    base_line = format_ide_objs_line(obj)
    time_on = obj.ide.time_on if hasattr(obj, 'ide') and obj.ide.time_on else '0'
    time_off = obj.ide.time_off if hasattr(obj, 'ide') and obj.ide.time_off else '24'
    return f"{base_line}, {time_on}, {time_off}"

#######################################################
def export_ide_file(context, filename, skip_lod=False):
    output_file = filename if filename.lower().endswith('.ide') else filename + '.ide'
    scene_objects = [obj for obj in context.scene.objects if object_is_exportable_map_instance(obj)]
    seen_ids = set()
    objs_lines = []
    tobj_lines = []
    for obj in scene_objects:
        if skip_lod and object_is_lod(obj):
            continue
        object_id = str(get_object_ide_id(obj, 0))
        seen_key = object_id if object_id not in ('', '0') else get_object_model_name(obj)
        if seen_key in seen_ids:
            continue
        seen_ids.add(seen_key)
        if hasattr(obj, 'ide') and obj.ide.obj_type == 'tobj':
            tobj_lines.append(format_ide_tobj_line(obj) + f"  # {obj.name}")
        else:
            objs_lines.append(format_ide_objs_line(obj) + f"  # {obj.name}")
    with open(output_file, 'w', encoding='latin-1') as file:
        if objs_lines:
            file.write('objs\n')
            for line in objs_lines:
                file.write(line + '\n')
            file.write('end\n')
        if tobj_lines:
            file.write('tobj\n')
            for line in tobj_lines:
                file.write(line + '\n')
            file.write('end\n')
    return output_file, len(objs_lines) + len(tobj_lines)

#######################################################
def make_remove_building_lines(objects):
    lines = []
    for obj in objects:
        obj_id = get_object_ide_id(obj, -1)
        position, rotation, scale = get_export_transform(obj)
        radius = 200.0
        lines.append(f"RemoveBuildingForPlayer(playerid, {obj_id}, {position.x:.2f}, {position.y:.2f}, {position.z:.2f}, {radius:.2f});")
    return lines

#######################################################
class ide_exporter:
    total_definitions_num = 0

#######################################################
def export_ide(options):
    from . import ide_exporter as ide_exporter_module

    ide_exporter_module.export_ide(options)
    total = len(getattr(ide_exporter_module.ide_exporter, "objs_objects", []))
    total += len(getattr(ide_exporter_module.ide_exporter, "tobj_objects", []))
    total += len(getattr(ide_exporter_module.ide_exporter, "anim_objects", []))
    ide_exporter.total_definitions_num = total


#######################################################
def strip_pawn_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    lines = []
    for line in text.splitlines():
        comment = ""
        if "//" in line:
            line, comment = line.split("//", 1)
            comment = comment.strip()
        lines.append((line, comment))
    return lines

#######################################################
def split_pawn_args(args_text):
    args = []
    current = []
    in_string = False
    escape = False

    for char in args_text:
        if in_string:
            current.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            current.append(char)
            continue

        if char == ',':
            args.append(''.join(current).strip())
            current = []
            continue

        current.append(char)

    if current or args_text.strip():
        args.append(''.join(current).strip())

    return args

#######################################################
def clean_pawn_string(value):
    value = str(value).strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1]
    return value.replace('\\\\', '\\').replace('\\"', '"')

#######################################################
def normalize_pawn_numeric_expression(value):
    expression = str(value or '').strip()
    expression = re.sub(
        r"\b(?:Float|bool|PlayerText|Text|Menu|DB|DBResult|File|INI|XML|Node|BitStream):",
        "",
        expression,
        flags=re.IGNORECASE,
    )
    expression = re.sub(r"(?<=\d)[fF]\b", "", expression)
    expression = re.sub(r"\btrue\b", "1", expression, flags=re.IGNORECASE)
    expression = re.sub(r"\bfalse\b", "0", expression, flags=re.IGNORECASE)
    return expression.strip()

#######################################################
def evaluate_pawn_numeric_expression(value, constants=None, default=None):
    expression = normalize_pawn_numeric_expression(value)
    if not expression:
        return default

    constants = constants or {}
    binary_operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.LShift: operator.lshift,
        ast.RShift: operator.rshift,
        ast.BitOr: operator.or_,
        ast.BitAnd: operator.and_,
        ast.BitXor: operator.xor,
    }
    unary_operators = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
        ast.Invert: operator.invert,
    }

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in constants:
                raise ValueError('unresolved Pawn symbol: %s' % node.id)
            return constants[node.id]
        if isinstance(node, ast.UnaryOp) and type(node.op) in unary_operators:
            return unary_operators[type(node.op)](evaluate(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in binary_operators:
            return binary_operators[type(node.op)](
                evaluate(node.left),
                evaluate(node.right),
            )
        raise ValueError('unsupported Pawn numeric expression')

    try:
        tree = ast.parse(expression, mode='eval')
        result = evaluate(tree)
        if isinstance(result, bool):
            return int(result)
        if isinstance(result, (int, float)):
            return result
    except Exception:
        pass
    return default

#######################################################
def parse_pawn_numeric_constants(raw_text):
    clean_text = re.sub(r"/\*.*?\*/", "", raw_text, flags=re.DOTALL)
    pending = []

    for raw_line in clean_text.splitlines():
        line = raw_line.split('//', 1)[0].strip()
        if not line:
            continue

        define_match = re.match(
            r"^#define\s+([A-Za-z_][A-Za-z0-9_]*)\s+(.+?)\s*$",
            line,
        )
        if define_match:
            pending.append((define_match.group(1), define_match.group(2).strip()))
            continue

        const_match = re.match(
            r"^(?:(?:static|new)\s+)*const(?:\s+[A-Za-z_][A-Za-z0-9_]*:)?\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^;]+)\s*;",
            line,
            flags=re.IGNORECASE,
        )
        if const_match:
            pending.append((const_match.group(1), const_match.group(2).strip()))

    constants = {}
    unresolved = list(pending)
    for _pass_index in range(max(1, len(unresolved))):
        if not unresolved:
            break

        next_unresolved = []
        resolved_this_pass = 0
        for name, expression in unresolved:
            value = evaluate_pawn_numeric_expression(
                expression,
                constants,
                default=None,
            )
            if value is None:
                next_unresolved.append((name, expression))
                continue
            constants[name] = value
            resolved_this_pass += 1

        unresolved = next_unresolved
        if resolved_this_pass == 0:
            break

    return constants

#######################################################
def pawn_to_int(value, default=0, constants=None):
    resolved = evaluate_pawn_numeric_expression(value, constants, default=None)
    if resolved is None:
        return default
    try:
        return int(resolved)
    except Exception:
        return default

#######################################################
def pawn_to_float(value, default=0.0, constants=None):
    resolved = evaluate_pawn_numeric_expression(value, constants, default=None)
    if resolved is None:
        return default
    try:
        return float(resolved)
    except Exception:
        return default

#######################################################
def clean_pawn_model_name(path_value):
    name = os.path.basename(clean_pawn_string(path_value).replace('\\', '/'))
    return os.path.splitext(name)[0]

#######################################################
def clean_pawn_comment_model_name(comment_value):
    value = clean_pawn_string(comment_value or '').strip()
    if not value:
        return ''

    value = value.replace('\\', '/')
    labelled_match = re.fullmatch(
        r"\s*(?:model|dff)\s*[:=]\s*[\"']?([^\"'\s,;]+)[\"']?\s*",
        value,
        flags=re.IGNORECASE,
    )

    if labelled_match:
        candidate = labelled_match.group(1)
    else:
        # VCS2OMP writes a single DFF/object name after each placement. Do not
        # treat prose such as "Command for making it day time" as an asset name.
        unlabelled_match = re.fullmatch(
            r"\s*([A-Za-z0-9_@#$%+\-.]+)\s*",
            value,
        )
        if unlabelled_match is None:
            return ''
        candidate = unlabelled_match.group(1)

    candidate = candidate.strip('.,;:()[]{}<>\"\'')
    if not candidate or candidate.lstrip('+-').isdigit():
        return ''

    ignored_tokens = {
        'a', 'an', 'and', 'as', 'at', 'by', 'command', 'create',
        'createdynamicobject', 'createobject', 'day', 'dff', 'do', 'for',
        'from', 'id', 'in', 'instance', 'it', 'lod', 'making', 'model',
        'night', 'object', 'of', 'on', 'or', 'placement', 'player', 'spawn',
        'the', 'this', 'time', 'to', 'when', 'with', 'xyz',
    }
    if candidate.lower() in ignored_tokens:
        return ''

    candidate = os.path.basename(candidate)
    candidate = re.sub(r"\.dff$", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"\.\d{3,}$", "", candidate)
    return candidate

#######################################################
def parse_pawn_script(filename):
    with open(filename, 'r', encoding='latin-1', errors='ignore') as handle:
        raw_text = handle.read()

    constants = parse_pawn_numeric_constants(raw_text)
    simple_models = {}
    created_objects = []
    lines = strip_pawn_comments(raw_text)
    statement = ""

    for line, comment in lines:
        if not line.strip() and not statement:
            continue

        statement += line + "\n"
        if ';' not in line:
            continue

        statement_comment = comment.strip() if comment else ""
        pieces = statement.split(';')
        for piece in pieces[:-1]:
            stmt = piece.strip()
            if not stmt:
                continue

            add_match = re.search(
                r"\bAddSimpleModel\s*\((.*)\)",
                stmt,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if add_match:
                args = split_pawn_args(add_match.group(1))
                if len(args) >= 5:
                    model_id = pawn_to_int(args[2], None, constants)
                    if model_id is None:
                        continue

                    virtual_world = pawn_to_int(args[0], -1, constants)
                    base_id = pawn_to_int(args[1], 19379, constants)
                    dff_path = clean_pawn_string(args[3])
                    txd_path = clean_pawn_string(args[4])
                    if not dff_path.lower().endswith('.dff'):
                        continue

                    simple_models[model_id] = {
                        'virtual_world': virtual_world,
                        'base_id': base_id,
                        'model_id': model_id,
                        'dff_path': dff_path,
                        'txd_path': txd_path,
                        'model_name': clean_pawn_model_name(dff_path),
                        'txd_name': clean_pawn_model_name(txd_path),
                        'comment': statement_comment,
                    }
                continue

            create_match = re.search(
                r"(?:[A-Za-z_][A-Za-z0-9_]*\s*=\s*)?"
                r"\b(CreateDynamicObject|CreateObject)\s*\((.*)\)",
                stmt,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if not create_match:
                continue

            args = split_pawn_args(create_match.group(2))
            if len(args) < 7:
                continue

            required_values = (
                pawn_to_int(args[0], None, constants),
                pawn_to_float(args[1], None, constants),
                pawn_to_float(args[2], None, constants),
                pawn_to_float(args[3], None, constants),
                pawn_to_float(args[4], None, constants),
                pawn_to_float(args[5], None, constants),
                pawn_to_float(args[6], None, constants),
            )
            if any(value is None for value in required_values):
                # Runtime loops, array expressions, function parameters and other
                # non-constant calls cannot be represented as one fixed placement.
                # Skipping them is safer than silently importing them at 0, 0, 0.
                continue

            model_id, x, y, z, rx, ry, rz = required_values
            created_objects.append({
                'function': create_match.group(1),
                'model_id': model_id,
                'x': x,
                'y': y,
                'z': z,
                'rx': rx,
                'ry': ry,
                'rz': rz,
                'world_id': pawn_to_int(args[7], -1, constants) if len(args) > 7 else -1,
                'interior_id': pawn_to_int(args[8], -1, constants) if len(args) > 8 else -1,
                'player_id': pawn_to_int(args[9], -1, constants) if len(args) > 9 else -1,
                'stream_distance': pawn_to_float(args[10], 300.0, constants) if len(args) > 10 else 300.0,
                'draw_distance': pawn_to_float(args[11], 300.0, constants) if len(args) > 11 else 300.0,
                'comment': statement_comment,
                'comment_model_name': clean_pawn_comment_model_name(statement_comment),
            })

        statement = pieces[-1]

    return simple_models, created_objects

#######################################################
def ensure_collection(name):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    return collection

#######################################################
def link_object_to_collection(obj, collection):
    if obj.name not in collection.objects:
        collection.objects.link(obj)

    for source_collection in list(obj.users_collection):
        if source_collection != collection:
            try:
                source_collection.objects.unlink(obj)
            except Exception:
                pass

#######################################################
def set_pawn_import_props(obj, created, model_info, set_dff_type=True):
    model_id = created['model_id']
    model_name = model_info.get('model_name') if model_info else str(model_id)
    txd_name = model_info.get('txd_name') if model_info else 'default_txd'
    dff_path = model_info.get('dff_path') if model_info else ''
    txd_path = model_info.get('txd_path') if model_info else ''
    base_id = model_info.get('base_id') if model_info else 19379

    obj['Pawn_Model_ID'] = model_id
    obj['DemonFF_Pawn_Instance'] = True
    obj['Pawn_Function'] = created.get('function', 'CreateDynamicObject')
    obj['Pawn_World_ID'] = created.get('world_id', -1)
    obj['Pawn_Interior_ID'] = created.get('interior_id', -1)
    obj['Pawn_Player_ID'] = created.get('player_id', -1)
    obj['Pawn_Stream_Distance'] = created.get('stream_distance', 300.0)
    obj['Pawn_Draw_Distance'] = created.get('draw_distance', 300.0)
    obj['Pawn_Comment'] = created.get('comment', '')
    obj['Pawn_DFF_Path'] = dff_path
    obj['Pawn_TXD_Path'] = txd_path
    obj['SAMP_ID'] = model_id
    obj['IDE_ID'] = base_id
    obj['DFF_Name'] = model_name
    obj['TXD_Name'] = txd_name

    if set_dff_type and hasattr(obj, 'dff'):
        obj.dff.type = 'OBJ'

    if hasattr(obj, 'dff_map'):
        obj.dff_map.object_id = int(base_id) if str(base_id).lstrip('-').isdigit() else 0
        obj.dff_map.model_name = str(model_name)
        obj.dff_map.interior = int(created.get('interior_id', -1)) if str(created.get('interior_id', -1)).lstrip('-').isdigit() else -1
        obj.dff_map.lod = -1
        obj.dff_map.ide_object_id = int(base_id) if str(base_id).lstrip('-').isdigit() else 0
        obj.dff_map.ide_model_name = str(model_name)
        obj.dff_map.ide_txd_name = str(txd_name)
        obj.dff_map.pawn_model_name = str(model_name)
        obj.dff_map.pawn_txd_name = str(txd_name)

#######################################################
def normalize_pawn_asset_path(path_value):
    value = clean_pawn_string(path_value or '').strip().replace('\\', '/')
    while value.startswith('./'):
        value = value[2:]
    return value.lstrip('/')

#######################################################
def normalize_pawn_root(root_value):
    value = str(root_value or '').strip()
    if not value:
        return ''
    return os.path.normpath(bpy.path.abspath(value))

#######################################################
def build_pawn_asset_index(root_path, extension, recursive=True):
    root_path = normalize_pawn_root(root_path)
    index = {
        'root': root_path,
        'relative': {},
        'basename': {},
    }

    if not root_path or not os.path.isdir(root_path):
        return index

    extension = extension.lower()
    if recursive:
        iterator = os.walk(root_path)
    else:
        try:
            names = os.listdir(root_path)
        except OSError:
            names = []
        iterator = [(root_path, [], names)]

    for directory, _subdirectories, filenames in iterator:
        for filename in filenames:
            if not filename.lower().endswith(extension):
                continue

            full_path = os.path.normpath(os.path.join(directory, filename))
            relative_path = os.path.relpath(full_path, root_path).replace('\\', '/')
            relative_key = relative_path.lower()
            basename_key = filename.lower()

            index['relative'].setdefault(relative_key, []).append(full_path)
            index['basename'].setdefault(basename_key, []).append(full_path)

    return index

#######################################################
def choose_pawn_asset_match(matches):
    if not matches:
        return None
    return sorted(
        set(matches),
        key=lambda path: (path.count(os.sep), len(path), path.lower()),
    )[0]

#######################################################
def resolve_pawn_asset(asset_index, path_value, extension):
    root_path = asset_index.get('root', '')
    clean_path = normalize_pawn_asset_path(path_value)
    if not clean_path:
        return None

    if not clean_path.lower().endswith(extension.lower()):
        clean_path += extension

    native_path = os.path.normpath(clean_path.replace('/', os.sep))
    if os.path.isabs(native_path) and os.path.isfile(native_path):
        return native_path

    candidates = [clean_path]
    lower_path = clean_path.lower()
    for prefix in ('models/', 'model/', 'dff/', 'txd/'):
        if lower_path.startswith(prefix):
            candidates.append(clean_path[len(prefix):])

    if root_path:
        for candidate in candidates:
            direct_path = os.path.normpath(
                os.path.join(root_path, candidate.replace('/', os.sep))
            )
            if os.path.isfile(direct_path):
                return direct_path

        for candidate in candidates:
            matches = asset_index['relative'].get(candidate.lower())
            selected = choose_pawn_asset_match(matches)
            if selected:
                return selected

    basename = os.path.basename(clean_path).lower()
    return choose_pawn_asset_match(asset_index['basename'].get(basename))

#######################################################
def make_pawn_comment_model_info(created, official_info=None):
    # AddSimpleModel custom assets use negative IDs. A positive ID is a stock
    # GTA model and must not inherit an arbitrary English word from a comment.
    if int(created.get('model_id', 0)) >= 0:
        return None

    model_name = created.get('comment_model_name', '')
    if not model_name:
        return None

    official_info = official_info or {}
    txd_path = official_info.get('txd_path', '')
    txd_name = official_info.get('txd_name', '')

    return {
        'virtual_world': official_info.get('virtual_world', -1),
        'base_id': official_info.get('base_id', 19379),
        'model_id': created.get('model_id', 0),
        'dff_path': model_name + '.dff',
        'txd_path': txd_path,
        'model_name': model_name,
        'txd_name': txd_name,
        'comment': created.get('comment', ''),
        'mapping_source': 'placement comment',
    }

#######################################################
def pawn_model_info_candidates(created, simple_models):
    official_info = simple_models.get(created.get('model_id'))
    candidates = []

    if official_info is not None:
        official_copy = dict(official_info)
        official_copy['mapping_source'] = 'AddSimpleModel'
        candidates.append(official_copy)

    comment_info = make_pawn_comment_model_info(created, official_info)
    if comment_info is not None:
        candidates.append(comment_info)

    unique_candidates = []
    seen = set()
    for candidate in candidates:
        key = (
            normalize_pawn_asset_path(candidate.get('dff_path', '')).lower(),
            normalize_pawn_asset_path(candidate.get('txd_path', '')).lower(),
            str(candidate.get('model_name', '')).lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique_candidates.append(candidate)

    return unique_candidates

#######################################################
def resolve_pawn_model_assets(
    created,
    simple_models,
    dff_index,
    txd_index,
    import_textures,
):
    candidates = pawn_model_info_candidates(created, simple_models)
    first_info = candidates[0] if candidates else None

    for model_info in candidates:
        dff_path = resolve_pawn_asset(
            dff_index,
            model_info.get('dff_path', ''),
            '.dff',
        )
        if dff_path is None:
            continue

        txd_path = None
        if import_textures:
            txd_candidates = []
            configured_txd = model_info.get('txd_path', '')
            if configured_txd:
                txd_candidates.append(configured_txd)

            dff_basename = os.path.splitext(os.path.basename(dff_path))[0]
            txd_candidates.extend((
                dff_basename + '.txd',
                model_info.get('model_name', '') + '.txd',
            ))

            seen_txd_candidates = set()
            for txd_candidate in txd_candidates:
                normalized_candidate = normalize_pawn_asset_path(txd_candidate).lower()
                if not normalized_candidate or normalized_candidate in seen_txd_candidates:
                    continue
                seen_txd_candidates.add(normalized_candidate)
                txd_path = resolve_pawn_asset(txd_index, txd_candidate, '.txd')
                if txd_path is not None:
                    break

        resolved_info = dict(model_info)
        resolved_info['resolved_dff_path'] = dff_path
        resolved_info['resolved_txd_path'] = txd_path or ''
        if not resolved_info.get('model_name'):
            resolved_info['model_name'] = os.path.splitext(os.path.basename(dff_path))[0]
        if txd_path and not resolved_info.get('txd_name'):
            resolved_info['txd_name'] = os.path.splitext(os.path.basename(txd_path))[0]

        return resolved_info, dff_path, txd_path

    return first_info, None, None

#######################################################
def remove_pawn_collection_tree(collection):
    if collection is None:
        return 0, 0

    collections = []
    objects = set()
    pending = [collection]

    while pending:
        current = pending.pop()
        collections.append(current)
        pending.extend(list(current.children))
        objects.update(list(current.objects))

    object_count = len(objects)
    collection_count = len(collections)

    batch_remove = getattr(bpy.data, 'batch_remove', None)
    if callable(batch_remove):
        if objects:
            batch_remove(ids=tuple(objects))
        if collections:
            batch_remove(ids=tuple(reversed(collections)))
        return object_count, collection_count

    for current in reversed(collections):
        for obj in list(current.objects):
            if bpy.data.objects.get(obj.name) is obj:
                bpy.data.objects.remove(obj, do_unlink=True)

        if bpy.data.collections.get(current.name) is current:
            bpy.data.collections.remove(current)

    return object_count, collection_count

#######################################################
def remove_pawn_collection_shell(collection):
    if collection is None:
        return 0

    collections = []
    pending = [collection]
    seen = set()

    while pending:
        current = pending.pop()
        try:
            key = current.as_pointer()
        except Exception:
            key = id(current)
        if key in seen:
            continue
        seen.add(key)
        collections.append(current)
        pending.extend(list(current.children))

    for current in reversed(collections):
        for obj in list(current.objects):
            try:
                current.objects.unlink(obj)
            except RuntimeError:
                pass

        if bpy.data.collections.get(current.name) is current:
            bpy.data.collections.remove(current)

    return len(collections)


def create_pawn_source_collection(collection_name):
    source_name = '.%s Model Sources' % (collection_name or 'Pawn Import')
    old_collection = bpy.data.collections.get(source_name)
    if old_collection is not None:
        remove_pawn_collection_tree(old_collection)

    source_collection = bpy.data.collections.new(source_name)
    bpy.context.scene.collection.children.link(source_collection)
    source_collection.hide_viewport = True
    source_collection.hide_render = True
    return source_collection

#######################################################
def move_pawn_import_collection(import_collection, source_collection):
    if source_collection.children.get(import_collection.name) is None:
        source_collection.children.link(import_collection)

    scene_root = bpy.context.scene.collection
    if scene_root.children.get(import_collection.name) is not None:
        scene_root.children.unlink(import_collection)

    for collection in list(bpy.data.collections):
        if collection == source_collection:
            continue
        if collection.children.get(import_collection.name) is not None:
            try:
                collection.children.unlink(import_collection)
            except RuntimeError:
                pass

#######################################################
def get_pawn_collection_objects(collection):
    try:
        return list(collection.all_objects)
    except AttributeError:
        return list(collection.objects)

#######################################################
def is_pawn_2dfx_object(obj):
    if obj is None:
        return False

    try:
        if getattr(getattr(obj, 'dff', None), 'type', '') == '2DFX':
            return True
    except Exception:
        pass

    try:
        if bool(obj.get('demonff_2dfx_source_dff', '')):
            return True
    except Exception:
        pass

    return str(getattr(obj, 'name', '')).lower().startswith('2dfx_')

#######################################################
def attach_pawn_helpers_to_primary(source_objects, primary_source):
    if primary_source is None:
        return 0, 0

    attached_2dfx = 0
    attached_collision = 0
    primary_world = primary_source.matrix_world.copy()

    for obj in source_objects:
        if obj == primary_source:
            continue

        is_2dfx = is_pawn_2dfx_object(obj)
        is_collision = is_pawn_collision_object(obj)
        if not is_2dfx and not is_collision:
            continue

        world_matrix = obj.matrix_world.copy()
        obj.parent = primary_source
        obj.matrix_parent_inverse = primary_world.inverted_safe()
        obj.matrix_world = world_matrix

        if is_2dfx:
            obj['DemonFF_Pawn_Attached_2DFX'] = True
            attached_2dfx += 1
        if is_collision:
            obj['DemonFF_Pawn_Attached_Collision'] = True
            attached_collision += 1

    return attached_2dfx, attached_collision

#######################################################
def load_pawn_model_template(
    model_info,
    dff_path,
    txd_path,
    source_collection,
    import_collisions=False,
):
    importer = dff_importer.import_dff(
        {
            'file_name': dff_path,
            'load_txd': bool(txd_path),
            'txd_filename': txd_path or '',
            'skip_mipmaps': True,
            'txd_pack': True,
            'image_ext': None,
            'connect_bones': False,
            'use_mat_split': True,
            'remove_doubles': False,
            'create_backfaces': False,
            'group_materials': True,
            'import_normals': True,
            'materials_naming': 'DEF',
            'defer_scene_update': True,
            'import_collisions': bool(import_collisions),
        }
    )

    imported_collection = importer.current_collection
    move_pawn_import_collection(imported_collection, source_collection)
    imported_collection.hide_viewport = True
    imported_collection.hide_render = True

    source_objects = get_pawn_collection_objects(imported_collection)
    source_set = set(source_objects)
    roots = [
        obj for obj in source_objects
        if obj.parent is None or obj.parent not in source_set
    ]

    if not source_objects or not roots:
        raise RuntimeError('DFF imported without usable objects')

    source_display_names = {
        source_obj: source_obj.name
        for source_obj in source_objects
    }
    source_tag = os.path.splitext(os.path.basename(dff_path))[0]
    for source_index, source_obj in enumerate(source_objects):
        source_obj.name = '.DemonFF_PWN_SOURCE_%s_%04d' % (
            source_tag,
            source_index,
        )

    template = {
        'collection': imported_collection,
        'objects': source_objects,
        'roots': roots,
        'object_set': source_set,
        'display_names': source_display_names,
        'model_info': model_info,
        'dff_path': dff_path,
        'txd_path': txd_path,
        'activated': False,
        'import_collisions': bool(import_collisions),
    }

    primary_source = choose_pawn_primary_source(template)
    attached_2dfx, attached_collision = attach_pawn_helpers_to_primary(
        source_objects,
        primary_source,
    )

    template['primary_source'] = primary_source
    template['attached_2dfx_count'] = attached_2dfx
    template['attached_collision_count'] = attached_collision
    template['original_parent'] = {
        source_obj: source_obj.parent
        for source_obj in source_objects
    }
    template['original_matrix_local'] = {
        source_obj: source_obj.matrix_local.copy()
        for source_obj in source_objects
    }
    template['original_matrix_world'] = {
        source_obj: source_obj.matrix_world.copy()
        for source_obj in source_objects
    }

    return template

#######################################################
def remap_pawn_object_links(source_to_copy):
    for source_obj, copy_obj in source_to_copy.items():
        for modifier in copy_obj.modifiers:
            if hasattr(modifier, 'object') and modifier.object in source_to_copy:
                modifier.object = source_to_copy[modifier.object]

        for constraint in copy_obj.constraints:
            if hasattr(constraint, 'target') and constraint.target in source_to_copy:
                constraint.target = source_to_copy[constraint.target]

        if copy_obj.parent in source_to_copy:
            copy_obj.parent = source_to_copy[copy_obj.parent]

#######################################################
def choose_pawn_primary_source(template):
    roots = list(template.get('roots', []))
    objects = list(template.get('objects', []))

    for source_obj in roots:
        if getattr(source_obj, 'type', None) == 'MESH':
            return source_obj

    for source_obj in objects:
        if getattr(source_obj, 'type', None) == 'MESH':
            return source_obj

    if roots:
        return roots[0]
    if objects:
        return objects[0]
    return None

#######################################################
def pawn_source_display_name(template, source_obj):
    source_name = template.get('display_names', {}).get(source_obj)
    if not source_name:
        source_name = getattr(source_obj, 'name', '') or 'part'
    return re.sub(r"\.\d{3,}$", "", source_name)

#######################################################
def get_pawn_placement_object_name(template, source_obj, model_name):
    primary_source = template.get('primary_source') or choose_pawn_primary_source(template)
    if source_obj == primary_source:
        return model_name

    part_name = pawn_source_display_name(template, source_obj)
    if part_name.lower() == model_name.lower():
        return model_name
    return '%s_%s' % (model_name, part_name)

#######################################################
def is_pawn_collision_object(obj):
    if obj is None:
        return False

    try:
        if getattr(getattr(obj, 'dff', None), 'type', '') == 'COL':
            return True
    except Exception:
        pass

    try:
        if bool(obj.get('demonff_embedded_collision', False)):
            return True
    except Exception:
        pass

    return '.col.' in str(getattr(obj, 'name', '')).lower()

#######################################################
def prepare_pawn_placement_object(obj, name, created, model_info, template):
    obj.name = name
    obj.hide_viewport = False
    obj.hide_render = False
    try:
        obj.hide_set(False)
    except Exception:
        pass

    preserve_special_type = is_pawn_2dfx_object(obj) or is_pawn_collision_object(obj)
    set_pawn_import_props(
        obj,
        created,
        model_info,
        not preserve_special_type,
    )
    obj['DemonFF_Pawn_Model_Source'] = template['dff_path']
    obj['DemonFF_Pawn_Model_Key'] = str(
        model_info.get('model_name') or created.get('model_id', '')
    ).lower()
    obj['DemonFF_Pawn_Model_ID'] = int(created.get('model_id', 0))
    obj['DemonFF_Pawn_Placement_ID'] = int(
        created.get('_demonff_placement_index', 0)
    )

    if is_pawn_collision_object(obj):
        obj.hide_render = True
        obj.show_wire = True
        obj.show_in_front = True

#######################################################
def activate_pawn_template_as_first_placement(
    template,
    created,
    model_info,
    collection,
    placement_matrix,
):
    source_objects = list(template['objects'])
    original_parent = template['original_parent']
    original_matrix_local = template['original_matrix_local']
    original_matrix_world = template['original_matrix_world']

    for source_obj in source_objects:
        link_object_to_collection(source_obj, collection)
        prepare_pawn_placement_object(
            source_obj,
            get_pawn_placement_object_name(template, source_obj, model_info.get('model_name') or str(created.get('model_id', 0))),
            created,
            model_info,
            template,
        )

    for source_obj in source_objects:
        parent = original_parent.get(source_obj)
        if parent in template['object_set']:
            source_obj.parent = parent
            source_obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)
            source_obj.matrix_local = original_matrix_local[source_obj].copy()
        else:
            source_obj.parent = None
            source_obj.matrix_world = placement_matrix @ original_matrix_world[source_obj]

    imported_collection = template.get('collection')
    if imported_collection is not None:
        remove_pawn_collection_shell(imported_collection)
        template['collection'] = None

    template['activated'] = True
    return source_objects

#######################################################
def copy_pawn_template_placement(
    template,
    created,
    model_info,
    collection,
    placement_matrix,
):
    source_objects = list(template['objects'])
    original_parent = template['original_parent']
    original_matrix_local = template['original_matrix_local']
    original_matrix_world = template['original_matrix_world']
    source_to_copy = {}
    model_name = model_info.get('model_name') or str(created.get('model_id', 0))

    for source_obj in source_objects:
        copy_obj = source_obj.copy()
        if source_obj.data is not None:
            copy_obj.data = source_obj.data

        prepare_pawn_placement_object(
            copy_obj,
            get_pawn_placement_object_name(template, source_obj, model_name),
            created,
            model_info,
            template,
        )
        collection.objects.link(copy_obj)
        source_to_copy[source_obj] = copy_obj

    for source_obj, copy_obj in source_to_copy.items():
        parent = original_parent.get(source_obj)
        if parent in source_to_copy:
            copy_obj.parent = source_to_copy[parent]
            copy_obj.matrix_parent_inverse = mathutils.Matrix.Identity(4)
            copy_obj.matrix_local = original_matrix_local[source_obj].copy()
        else:
            copy_obj.parent = None
            copy_obj.matrix_world = placement_matrix @ original_matrix_world[source_obj]

    remap_pawn_object_links(source_to_copy)
    return list(source_to_copy.values())

#######################################################
def instantiate_pawn_model(template, created, model_info, collection):
    placement_matrix = (
        mathutils.Matrix.Translation((created['x'], created['y'], created['z']))
        @ gta_euler_degrees_to_quaternion(
            created['rx'],
            created['ry'],
            created['rz'],
        ).to_matrix().to_4x4()
    )

    if not template.get('activated', False):
        return activate_pawn_template_as_first_placement(
            template,
            created,
            model_info,
            collection,
            placement_matrix,
        )

    return copy_pawn_template_placement(
        template,
        created,
        model_info,
        collection,
        placement_matrix,
    )

#######################################################
class pwn_importer:
    total_objects_num = 0
    parsed_objects_num = 0
    processed_objects_num = 0
    skipped_objects_num = 0
    total_models_num = 0
    loaded_models_num = 0
    real_model_instances_num = 0
    placeholder_objects_num = 0
    comment_mapped_models_num = 0
    missing_model_info_num = 0
    missing_dff_num = 0
    missing_txd_num = 0
    failed_dff_num = 0
    progress_percent = 0.0
    progress_message = ""
    last_progress_print_at = 0.0
    last_progress_print_index = -1

    @staticmethod
    def format_progress_duration(seconds):
        seconds = max(0, int(float(seconds)))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours:
            return "%d:%02d:%02d" % (hours, minutes, seconds)
        return "%02d:%02d" % (minutes, seconds)

    @staticmethod
    def update_progress(
        progress_callback,
        started_at,
        stage,
        percent,
        current,
        total,
        imported,
        skipped,
        loaded_models,
        detail='',
        force_console=False,
        force_redraw=False,
    ):
        percent = max(0.0, min(100.0, float(percent)))
        elapsed = max(0.0, time.perf_counter() - started_at)

        stage_names = {
            'reading Pawn script': 'Reading file',
            'parsed Pawn script': 'Reading file',
            'clearing existing collection': 'Clearing old import',
            'indexing DFF files': 'Finding models',
            'indexing TXD files': 'Finding textures',
            'importing placements': 'Importing models',
            'loading DFF': 'Loading model',
            'removing temporary model sources': 'Cleaning up',
            'completing import': 'Finishing',
            'complete': 'Done',
        }
        friendly_stage = stage_names.get(stage, stage)

        if total > 0:
            message = (
                "PWN import %.1f%%: %d/%d placements, %d imported, %d skipped"
                % (percent, current, total, imported, skipped)
            )
        else:
            message = "PWN import %.1f%%: %s" % (percent, friendly_stage)

        simple_detail = str(detail or '').strip()
        if simple_detail:
            if os.path.sep in simple_detail or ('/' in simple_detail and not simple_detail.lower().endswith('.dff')):
                simple_detail = os.path.basename(os.path.normpath(simple_detail))
            if simple_detail and simple_detail not in ('DFF', 'TXD'):
                message += " - %s" % simple_detail

        if total > 0 and friendly_stage not in ('Importing models', 'Loading model'):
            message += " - %s" % friendly_stage

        pwn_importer.progress_percent = percent
        pwn_importer.progress_message = message
        pwn_importer.processed_objects_num = current

        if progress_callback is not None:
            try:
                progress_callback({
                    'stage': friendly_stage,
                    'percent': percent,
                    'current': current,
                    'total': total,
                    'imported': imported,
                    'skipped': skipped,
                    'loaded_models': loaded_models,
                    'detail': simple_detail,
                    'elapsed': elapsed,
                    'message': message,
                    'force_redraw': force_redraw,
                })
            except Exception:
                pass

        now = time.perf_counter()
        should_print = force_console
        if not should_print and now - pwn_importer.last_progress_print_at >= 1.0:
            should_print = True
        if not should_print and current - pwn_importer.last_progress_print_index >= 100:
            should_print = True

        if should_print:
            print(message, flush=True)
            pwn_importer.last_progress_print_at = now
            pwn_importer.last_progress_print_index = current

    @staticmethod
    def import_pawn(
        filename,
        collection_name='Pawn Import',
        clear_existing=False,
        dff_root='',
        txd_root='',
        recursive_search=True,
        import_textures=True,
        import_collisions=False,
        progress_callback=None,
    ):
        started_at = time.perf_counter()

        pwn_importer.total_objects_num = 0
        pwn_importer.parsed_objects_num = 0
        pwn_importer.processed_objects_num = 0
        pwn_importer.skipped_objects_num = 0
        pwn_importer.total_models_num = 0
        pwn_importer.loaded_models_num = 0
        pwn_importer.real_model_instances_num = 0
        pwn_importer.placeholder_objects_num = 0
        pwn_importer.comment_mapped_models_num = 0
        pwn_importer.missing_model_info_num = 0
        pwn_importer.missing_dff_num = 0
        pwn_importer.missing_txd_num = 0
        pwn_importer.failed_dff_num = 0
        pwn_importer.progress_percent = 0.0
        pwn_importer.progress_message = ""
        pwn_importer.last_progress_print_at = 0.0
        pwn_importer.last_progress_print_index = -1

        pwn_importer.update_progress(
            progress_callback,
            started_at,
            'reading Pawn script',
            0.0,
            0,
            0,
            0,
            0,
            0,
            os.path.basename(filename),
            force_console=True,
            force_redraw=True,
        )

        simple_models, created_objects = parse_pawn_script(filename)
        total_placements = len(created_objects)
        pwn_importer.parsed_objects_num = total_placements
        pwn_importer.total_models_num = len(simple_models)

        pwn_importer.update_progress(
            progress_callback,
            started_at,
            'parsed Pawn script',
            1.0,
            0,
            total_placements,
            0,
            0,
            0,
            "%d model definitions" % len(simple_models),
            force_console=True,
            force_redraw=True,
        )

        collection = ensure_collection(collection_name or 'Pawn Import')

        if clear_existing:
            existing_count = len(collection.objects)
            pwn_importer.update_progress(
                progress_callback,
                started_at,
                'clearing existing collection',
                2.0,
                0,
                total_placements,
                0,
                0,
                0,
                "%d existing object(s)" % existing_count,
                force_console=True,
            )
            for obj in list(collection.objects):
                bpy.data.objects.remove(obj, do_unlink=True)

        pwn_directory = os.path.dirname(os.path.abspath(filename))
        dff_root = normalize_pawn_root(dff_root)
        if not dff_root:
            models_subdirectory = os.path.join(pwn_directory, 'models')
            dff_root = models_subdirectory if os.path.isdir(models_subdirectory) else pwn_directory

        txd_root = normalize_pawn_root(txd_root)
        if not txd_root:
            txd_root = dff_root

        pwn_importer.update_progress(
            progress_callback,
            started_at,
            'indexing DFF files',
            2.5,
            0,
            total_placements,
            0,
            0,
            0,
            '',
            force_console=True,
            force_redraw=True,
        )
        dff_index = build_pawn_asset_index(dff_root, '.dff', recursive_search)
        indexed_dff_count = sum(len(paths) for paths in dff_index['relative'].values())

        pwn_importer.update_progress(
            progress_callback,
            started_at,
            'indexing TXD files',
            4.0,
            0,
            total_placements,
            0,
            0,
            0,
            "%d model files found" % indexed_dff_count,
            force_console=True,
            force_redraw=True,
        )
        txd_index = build_pawn_asset_index(txd_root, '.txd', recursive_search)
        indexed_txd_count = sum(len(paths) for paths in txd_index['relative'].values())

        source_collection = create_pawn_source_collection(collection_name)
        template_cache = {}

        imported = 0
        skipped = 0
        loaded_models = 0
        real_instances = 0
        attached_2dfx_count = 0
        attached_collision_count = 0
        comment_mapped_ids = set()
        missing_model_ids = set()
        missing_dff_keys = set()
        missing_txd_keys = set()
        failed_dff_keys = set()

        pwn_importer.update_progress(
            progress_callback,
            started_at,
            'importing placements',
            5.0,
            0,
            total_placements,
            imported,
            skipped,
            loaded_models,
            "%d model files and %d texture files found" % (
                indexed_dff_count,
                indexed_txd_count,
            ),
            force_console=True,
            force_redraw=True,
        )

        for placement_index, created in enumerate(created_objects, 1):
            created['_demonff_placement_index'] = placement_index
            model_id = created.get('model_id', 0)
            progress_detail = "Starting placement"

            try:
                candidates = pawn_model_info_candidates(created, simple_models)
                if not candidates:
                    skipped += 1
                    progress_detail = "Skipped placement"
                    missing_model_ids.add(model_id)
                    continue

                model_info, dff_path, txd_path = resolve_pawn_model_assets(
                    created,
                    simple_models,
                    dff_index,
                    txd_index,
                    import_textures,
                )

                if model_info is not None and model_info.get('mapping_source') == 'placement comment':
                    comment_mapped_ids.add(model_id)

                if dff_path is None:
                    skipped += 1
                    requested_dff = ''
                    if model_info is not None:
                        requested_dff = model_info.get('dff_path', '')
                    missing_key = (model_id, requested_dff.lower())
                    progress_detail = "skipped %s" % (
                        requested_dff or created.get('comment_model_name', '') or model_id
                    )
                    missing_dff_keys.add(missing_key)
                    continue

                dff_name = os.path.basename(dff_path)
                progress_detail = dff_name
                configured_txd = model_info.get('txd_path', '') if model_info else ''
                if import_textures and configured_txd and txd_path is None:
                    missing_key = (model_id, configured_txd.lower())
                    missing_txd_keys.add(missing_key)

                cache_key = (
                    os.path.normcase(os.path.abspath(dff_path)),
                    os.path.normcase(os.path.abspath(txd_path)) if txd_path else '',
                )

                if cache_key not in template_cache:
                    progress_detail = "loading %s" % dff_name
                    if total_placements:
                        loading_percent = 5.0 + (
                            float(placement_index - 1) / float(total_placements)
                        ) * 93.0
                    else:
                        loading_percent = 5.0
                    pwn_importer.update_progress(
                        progress_callback,
                        started_at,
                        'loading DFF',
                        loading_percent,
                        placement_index,
                        total_placements,
                        imported,
                        skipped,
                        loaded_models,
                        progress_detail,
                    )
                    try:
                        template_cache[cache_key] = load_pawn_model_template(
                            model_info,
                            dff_path,
                            txd_path,
                            source_collection,
                            import_collisions,
                        )
                        loaded_models += 1
                        attached_2dfx_count += int(
                            template_cache[cache_key].get('attached_2dfx_count', 0)
                        )
                        attached_collision_count += int(
                            template_cache[cache_key].get('attached_collision_count', 0)
                        )
                        progress_detail = "loaded %s" % dff_name
                    except Exception as error:
                        template_cache[cache_key] = None
                        progress_detail = "failed %s" % dff_name
                        failed_dff_keys.add(cache_key)

                template = template_cache.get(cache_key)
                if template is None:
                    skipped += 1
                    continue

                instantiate_pawn_model(
                    template,
                    created,
                    model_info,
                    collection,
                )
                imported += 1
                real_instances += 1
                progress_detail = dff_name
            finally:
                if total_placements:
                    percent = 5.0 + (float(placement_index) / float(total_placements)) * 93.0
                else:
                    percent = 98.0

                pwn_importer.update_progress(
                    progress_callback,
                    started_at,
                    'importing placements',
                    percent,
                    placement_index,
                    total_placements,
                    imported,
                    skipped,
                    loaded_models,
                    progress_detail,
                    force_console=(placement_index == total_placements),
                    force_redraw=(placement_index == total_placements),
                )

        source_object_count = 0
        source_collection_count = 0
        try:
            source_object_count = sum(
                len([
                    obj for obj in template.get('objects', ())
                    if any(collection == source_collection for collection in obj.users_collection)
                ])
                for template in template_cache.values()
                if template is not None
            )
            source_collection_count = 1 + sum(
                1
                for template in template_cache.values()
                if template is not None and template.get('collection') is not None
            )
        except Exception:
            source_object_count = 0
            source_collection_count = 0

        pwn_importer.update_progress(
            progress_callback,
            started_at,
            'removing temporary model sources',
            98.5,
            total_placements,
            total_placements,
            imported,
            skipped,
            loaded_models,
            "Cleaning up",
            force_console=True,
            force_redraw=True,
        )

        removed_objects, removed_collections = remove_pawn_collection_tree(
            source_collection
        )
        template_cache.clear()

        pwn_importer.update_progress(
            progress_callback,
            started_at,
            'completing import',
            99.8,
            total_placements,
            total_placements,
            imported,
            skipped,
            loaded_models,
            "Almost done",
            force_console=True,
            force_redraw=True,
        )

        pwn_importer.total_objects_num = imported
        pwn_importer.parsed_objects_num = total_placements
        pwn_importer.processed_objects_num = total_placements
        pwn_importer.skipped_objects_num = skipped
        pwn_importer.total_models_num = len(simple_models)
        pwn_importer.loaded_models_num = loaded_models
        pwn_importer.real_model_instances_num = real_instances
        pwn_importer.placeholder_objects_num = 0
        pwn_importer.comment_mapped_models_num = len(comment_mapped_ids)
        pwn_importer.missing_model_info_num = len(missing_model_ids)
        pwn_importer.missing_dff_num = len(missing_dff_keys)
        pwn_importer.missing_txd_num = len(missing_txd_keys)
        pwn_importer.failed_dff_num = len(failed_dff_keys)

        elapsed = max(0.0, time.perf_counter() - started_at)
        pwn_importer.update_progress(
            progress_callback,
            started_at,
            'complete',
            100.0,
            total_placements,
            total_placements,
            imported,
            skipped,
            loaded_models,
            pwn_importer.format_progress_duration(elapsed),
            force_console=True,
            force_redraw=True,
        )

        summary = (
            "PWN import finished: %d of %d placements imported; %d skipped; %s."
            % (
                imported,
                total_placements,
                skipped,
                pwn_importer.format_progress_duration(elapsed),
            )
        )
        if missing_dff_keys:
            summary += " %d model file(s) were not found." % len(missing_dff_keys)
        if failed_dff_keys:
            summary += " %d model file(s) could not be opened." % len(failed_dff_keys)
        print(summary, flush=True)


        return imported

#######################################################
def import_pawn(options):
    scene_settings = getattr(getattr(bpy.context, 'scene', None), 'dff', None)
    previous_real_time_update = None

    if scene_settings is not None and hasattr(scene_settings, 'real_time_update'):
        previous_real_time_update = bool(scene_settings.real_time_update)
        if previous_real_time_update:
            scene_settings.real_time_update = False

    try:
        return pwn_importer.import_pawn(
            options['file_name'],
            options.get('collection_name', 'Pawn Import'),
            options.get('clear_existing', False),
            options.get('dff_root', ''),
            options.get('txd_root', ''),
            options.get('recursive_search', True),
            options.get('import_textures', True),
            options.get('import_collisions', False),
            options.get('progress_callback'),
        )
    finally:
        if (
            scene_settings is not None
            and previous_real_time_update is not None
            and hasattr(scene_settings, 'real_time_update')
        ):
            scene_settings.real_time_update = previous_real_time_update

#######################################################
class pwn_exporter:
    only_selected = False
    model_directory = ""
    texture_directory = ""
    skip_lod = True
    stream_distance = 300.0
    draw_distance = 300.0
    model_id_start = -1000
    x_offset = 0.0
    y_offset = 0.0
    z_offset = 0.0
    force_all_worlds_interiors = True
    total_objects_num = 0

    @staticmethod
    def collect_objects(context):
        objects = []
        for obj in context.scene.objects:
            if not object_is_exportable_map_instance(obj):
                continue
            if pwn_exporter.only_selected and not obj.select_get():
                continue
            if object_is_lod(obj):
                continue
            if object_is_synthetic_chunk(obj):
                continue
            if object_is_2dfx_pawn_helper(obj):
                continue
            objects.append(obj)
        return objects

    @staticmethod
    def get_or_create_model_id(model_name, txd_name, name_mapping, current_id):
        key = (
            normalize_export_asset_name(model_name, ".dff").lower(),
            normalize_export_asset_name(txd_name, ".txd").lower(),
        )

        if key in name_mapping:
            return name_mapping[key], current_id

        if current_id > -1000:
            current_id = min(-1000, max(-30000, int(pwn_exporter.model_id_start)))

        if current_id < -30000:
            raise RuntimeError(
                "No free SA-MP custom model IDs remain in the supported -1000 through -30000 range."
            )

        name_mapping[key] = current_id
        assigned_id = current_id
        current_id -= 1
        return assigned_id, current_id

    @staticmethod
    def export_pawn(filename):
        self = pwn_exporter
        objects = self.collect_objects(bpy.context)
        self.total_objects_num = 0

        output_file = filename if filename.lower().endswith('.pwn') else filename + '.pwn'
        artconfig_path = os.path.join(os.path.dirname(output_file), 'artconfig.txt')
        model_directory = self.model_directory.strip().replace('\\', '/')
        texture_directory = self.texture_directory.strip().replace('\\', '/')
        base_model_id = 19379
        current_id = min(-1000, max(-30000, int(self.model_id_start)))
        name_mapping = {}
        written_models = {}
        addsimplemodel_written = 0
        addsimplemodel_skipped = 0
        addsimplemodel_conflicts = 0

        ide_txd_lookup = collect_ide_txd_lookup(bpy.context, output_file)

        with open(output_file, 'w', encoding='latin-1', newline='\n') as pawn_file, open(artconfig_path, 'w', encoding='latin-1', newline='\n') as artconfig_file:
            pawn_file.write("// Generated by DemonFF\n")
            pawn_file.write("public OnGameModeInit()\n{\n")

            for obj in objects:
                model_name = normalize_export_asset_name(get_pawn_model_name(obj), ".dff")
                txd_name = normalize_export_asset_name(resolve_export_txd_name(obj, ide_txd_lookup), ".txd")
                model_id, current_id = self.get_or_create_model_id(
                    model_name,
                    txd_name,
                    name_mapping,
                    current_id,
                )
                position, rotation_quat, scale = get_export_transform(obj)
                position.x += self.x_offset
                position.y += self.y_offset
                position.z += self.z_offset
                rotation = get_pawn_rotation(obj)
                world_id, interior = get_stream_world_and_interior(obj, -1, -1)
                safe_model_dir = normalize_export_directory(model_directory)
                safe_texture_dir = normalize_export_directory(texture_directory) or safe_model_dir
                addsimplemodel_line, dff_path, txd_path = make_addsimplemodel_line(
                    -1,
                    base_model_id,
                    model_id,
                    safe_model_dir,
                    safe_texture_dir,
                    model_name,
                    txd_name,
                )

                pawn_file.write(
                    f"    CreateDynamicObject({model_id}, {position.x:.2f}, {position.y:.2f}, {position.z:.2f}, "
                    f"{rotation[0]:.2f}, {rotation[1]:.2f}, {rotation[2]:.2f}, "
                    f"{world_id}, {interior}, -1, {self.stream_distance:.2f}, {self.draw_distance:.2f});  // {obj.name}\n"
                )

                model_key = str(model_id).strip().lower()
                model_paths = (dff_path.lower(), txd_path.lower())
                existing_paths = written_models.get(model_key)

                if existing_paths is None:
                    written_models[model_key] = model_paths
                    artconfig_file.write(addsimplemodel_line)
                    addsimplemodel_written += 1
                elif existing_paths == model_paths:
                    addsimplemodel_skipped += 1
                    print(
                        "DemonFF Pawn export: skipped duplicate AddSimpleModel for model ID %s (%s, %s) from %s." % (
                            model_id,
                            dff_path,
                            txd_path,
                            obj.name,
                        )
                    )
                else:
                    addsimplemodel_skipped += 1
                    addsimplemodel_conflicts += 1
                    print(
                        "DemonFF Pawn export warning: skipped conflicting duplicate AddSimpleModel for model ID %s from %s. Already wrote (%s, %s), new request was (%s, %s)." % (
                            model_id,
                            obj.name,
                            existing_paths[0],
                            existing_paths[1],
                            dff_path.lower(),
                            txd_path.lower(),
                        )
                    )


                self.total_objects_num += 1

            pawn_file.write("    return 1;\n}\n")

        print(
            "DemonFF Pawn export verify: objects=%d, AddSimpleModel_written=%d, AddSimpleModel_duplicates_skipped=%d, AddSimpleModel_conflicts=%d." % (
                self.total_objects_num,
                addsimplemodel_written,
                addsimplemodel_skipped,
                addsimplemodel_conflicts,
            )
        )

#######################################################
def export_pawn(options):
    pwn_exporter.only_selected = options.get('only_selected', False)
    pwn_exporter.model_directory = options.get('model_directory', '')
    pwn_exporter.texture_directory = options.get('texture_directory', '')
    pwn_exporter.skip_lod = True
    pwn_exporter.stream_distance = options.get('stream_distance', 300.0)
    pwn_exporter.draw_distance = options.get('draw_distance', 300.0)
    pwn_exporter.model_id_start = min(-1000, max(-30000, int(options.get('model_id_start', -1000))))
    pwn_exporter.x_offset = options.get('x_offset', 0.0)
    pwn_exporter.y_offset = options.get('y_offset', 0.0)
    pwn_exporter.z_offset = options.get('z_offset', 0.0)
    pwn_exporter.force_all_worlds_interiors = options.get('force_all_worlds_interiors', True)
    pwn_exporter.export_pawn(options['file_name'])
