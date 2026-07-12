# DemonFF - Blender scripts for working with Renderware & R*/SA-MP/open.mp formats in Blender
# 2023 - 2026 spicybung

import bpy
import math
import os
import re
import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET

from . import col_samp_exporter
from . import dff_samp_exporter
from . import map_exporter
from . import txd_exporter


class MTAExportError(RuntimeError):
    pass


class MTAImportError(RuntimeError):
    pass


def clean_extension(value):
    value = os.path.basename(str(value or "").replace("\\", "/"))
    return os.path.splitext(value)[0]


def sanitize_resource_name(value):
    value = clean_extension(value).strip().lower()
    value = re.sub(r"[^a-z0-9_-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_-")
    return value or "demonff_mta_resource"


def sanitize_asset_name(value):
    value = clean_extension(value).strip()
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_-")
    return value or "model"


def normalize_model_key(value):
    return sanitize_asset_name(value).lower()


def lua_quote(value):
    value = str(value or "")
    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    value = value.replace("\r", "\\r")
    value = value.replace("\n", "\\n")
    return '"%s"' % value


def lua_bool(value):
    return "true" if bool(value) else "false"


def format_float(value):
    value = float(value)
    if abs(value) < 0.0000005:
        value = 0.0
    text = "%.8f" % value
    text = text.rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        text = "0"
    if "." not in text:
        text += ".0"
    return text


def iter_collection_objects(collection):
    seen = set()

    def visit(current):
        for obj in current.objects:
            pointer = obj.as_pointer()
            if pointer in seen:
                continue
            seen.add(pointer)
            yield obj

        for child in current.children:
            yield from visit(child)

    yield from visit(collection)


def get_scope_objects(context, scope):
    if scope == "SELECTED":
        return list(context.selected_objects)

    if scope == "ACTIVE_COLLECTION":
        layer_collection = getattr(context.view_layer, "active_layer_collection", None)
        collection = getattr(layer_collection, "collection", None)
        if collection is not None:
            return list(iter_collection_objects(collection))

    return list(context.scene.objects)


def get_mta_object_settings(obj):
    try:
        return obj.mta
    except Exception:
        return None


def get_bool_property(obj, property_name, default):
    settings = get_mta_object_settings(obj)
    if settings is not None and hasattr(settings, property_name):
        return bool(getattr(settings, property_name))

    custom_name = "MTA_%s" % property_name
    try:
        if custom_name in obj:
            return bool(obj[custom_name])
    except Exception:
        pass

    return bool(default)


def get_int_property(obj, property_name, default):
    settings = get_mta_object_settings(obj)
    if settings is not None and hasattr(settings, property_name):
        try:
            value = int(getattr(settings, property_name))
            if value != 0 or default == 0:
                return value
        except Exception:
            pass

    custom_name = "MTA_%s" % property_name
    try:
        if custom_name in obj:
            return int(obj[custom_name])
    except Exception:
        pass

    return int(default)


def get_float_property(obj, property_name, default):
    settings = get_mta_object_settings(obj)
    if settings is not None and hasattr(settings, property_name):
        try:
            value = float(getattr(settings, property_name))
            if value != 0.0 or default == 0.0:
                return value
        except Exception:
            pass

    custom_name = "MTA_%s" % property_name
    try:
        if custom_name in obj:
            return float(obj[custom_name])
    except Exception:
        pass

    return float(default)


def get_string_property(obj, property_name, default):
    settings = get_mta_object_settings(obj)
    if settings is not None and hasattr(settings, property_name):
        value = str(getattr(settings, property_name) or "").strip()
        if value:
            return value

    custom_name = "MTA_%s" % property_name
    try:
        if custom_name in obj:
            value = str(obj[custom_name] or "").strip()
            if value:
                return value
    except Exception:
        pass

    return str(default or "")


def get_placement_model_name(obj):
    custom_name = get_string_property(obj, "model_key", "")
    if custom_name:
        return clean_extension(custom_name)
    return clean_extension(map_exporter.get_object_model_name(obj))


def get_object_dimension(obj, default_dimension):
    settings = get_mta_object_settings(obj)
    if settings is not None and getattr(settings, "use_custom_dimension", False):
        return int(settings.dimension)

    try:
        if "MTA_Dimension" in obj:
            return int(obj["MTA_Dimension"])
    except Exception:
        pass

    parent = getattr(obj, "parent", None)
    try:
        if parent is not None and "MTA_Dimension" in parent:
            return int(parent["MTA_Dimension"])
    except Exception:
        pass

    return int(default_dimension)


def get_object_interior(obj, default_interior, use_map_interior):
    settings = get_mta_object_settings(obj)
    if settings is not None and getattr(settings, "use_custom_interior", False):
        return int(settings.interior)

    try:
        if "MTA_Interior" in obj:
            return int(obj["MTA_Interior"])
    except Exception:
        pass

    parent = getattr(obj, "parent", None)
    try:
        if parent is not None and "MTA_Interior" in parent:
            return int(parent["MTA_Interior"])
    except Exception:
        pass

    if use_map_interior:
        try:
            return int(map_exporter.get_object_interior(obj, default_interior))
        except Exception:
            pass

    return int(default_interior)


def get_draw_distance(obj, default_distance):
    custom_distance = get_float_property(obj, "lod_distance", 0.0)
    if custom_distance > 0.0:
        return custom_distance

    try:
        values = map_exporter.get_object_draw_distances(obj)
        for value in values:
            distance = float(value)
            if distance > 0.0:
                return distance
    except Exception:
        pass

    return float(default_distance)


def collect_placements(context, options):
    placements = []
    source_objects = get_scope_objects(context, options.get("scope", "SCENE"))
    skip_lod = bool(options.get("skip_lod", True))
    default_dimension = int(options.get("default_dimension", 0))
    default_interior = int(options.get("default_interior", 0))
    use_map_interior = bool(options.get("use_map_interior", True))
    default_lod_distance = float(options.get("default_lod_distance", 300.0))

    for obj in source_objects:
        if not map_exporter.object_is_exportable_map_instance(obj):
            continue
        if map_exporter.object_is_2dfx_pawn_helper(obj):
            continue
        if skip_lod and map_exporter.object_is_lod(obj):
            continue

        model_name = get_placement_model_name(obj)
        if not model_name:
            continue

        position, rotation, scale = map_exporter.get_export_transform(obj)
        rotation_euler = rotation.to_euler("XYZ")
        settings = get_mta_object_settings(obj)

        placement = {
            "source_object": obj,
            "name": obj.name,
            "model_name": model_name,
            "model_key": normalize_model_key(model_name),
            "x": float(position.x),
            "y": float(position.y),
            "z": float(position.z),
            "rx": math.degrees(rotation_euler.x),
            "ry": math.degrees(rotation_euler.y),
            "rz": math.degrees(rotation_euler.z),
            "scale_x": float(scale.x),
            "scale_y": float(scale.y),
            "scale_z": float(scale.z),
            "interior": get_object_interior(obj, default_interior, use_map_interior),
            "dimension": get_object_dimension(obj, default_dimension),
            "lod_distance": get_draw_distance(obj, default_lod_distance),
            "double_sided": bool(getattr(settings, "double_sided", False)) if settings is not None else False,
            "collisions_enabled": bool(getattr(settings, "collisions_enabled", True)) if settings is not None else True,
            "frozen": bool(getattr(settings, "frozen", True)) if settings is not None else True,
            "breakable": bool(getattr(settings, "breakable", False)) if settings is not None else False,
            "alpha": int(getattr(settings, "alpha", 255)) if settings is not None else 255,
            "target_model_id": get_int_property(obj, "target_model_id", 0),
            "parent_model_id": get_int_property(obj, "parent_model_id", int(options.get("default_parent_model_id", 1337))),
            "alpha_transparency": bool(getattr(settings, "alpha_transparency", True)) if settings is not None else True,
            "filtering_enabled": bool(getattr(settings, "filtering_enabled", False)) if settings is not None else False,
        }
        placements.append(placement)

    return placements


def collect_export_groups():
    exporter = dff_samp_exporter.dff_exporter
    previous_selected = exporter.selected
    previous_mass_export = exporter.mass_export
    groups = {}

    try:
        exporter.selected = False
        exporter.mass_export = True

        for collection in exporter.get_mass_export_collections():
            for export_name, objects, collision_objects in exporter.get_collection_export_groups(collection):
                model_name = clean_extension(export_name)
                model_key = normalize_model_key(model_name)
                if not model_key or model_key in groups:
                    continue

                groups[model_key] = {
                    "model_name": model_name,
                    "model_key": model_key,
                    "collection": collection,
                    "objects": list(objects),
                    "collision_objects": list(collision_objects or []),
                }
    finally:
        exporter.selected = previous_selected
        exporter.mass_export = previous_mass_export

    return groups


def find_case_insensitive_file(directory, filename):
    if not directory or not os.path.isdir(directory):
        return None

    exact_path = os.path.join(directory, filename)
    if os.path.isfile(exact_path):
        return exact_path

    wanted = filename.lower()
    try:
        for root, directories, files in os.walk(directory):
            directories.sort()
            for entry in files:
                if entry.lower() == wanted:
                    return os.path.join(root, entry)
    except OSError:
        return None

    return None


def unique_objects(objects):
    result = []
    seen = set()
    for obj in objects:
        pointer = obj.as_pointer()
        if pointer in seen:
            continue
        seen.add(pointer)
        result.append(obj)
    return result


def get_txd_name_for_placement(placement):
    obj = placement["source_object"]
    txd_name = clean_extension(map_exporter.get_object_txd_name(obj))
    if not txd_name or map_exporter.is_placeholder_txd_name(txd_name):
        txd_name = placement["model_name"]
    return sanitize_asset_name(txd_name)


def build_assets(placements, options):
    mode = options.get("model_mode", "REQUEST_NEW")
    next_target_id = max(1, int(options.get("replacement_start_id", 1337)))
    default_parent_id = max(1, int(options.get("default_parent_model_id", 1337)))
    used_target_ids = set()
    assets = {}

    for placement in placements:
        model_key = placement["model_key"]
        asset = assets.get(model_key)
        if asset is None:
            explicit_target = int(placement.get("target_model_id", 0) or 0)
            parent_model_id = int(placement.get("parent_model_id", default_parent_id) or default_parent_id)

            asset = {
                "model_key": model_key,
                "model_name": sanitize_asset_name(placement["model_name"]),
                "txd_name": get_txd_name_for_placement(placement),
                "target_model_id": explicit_target,
                "parent_model_id": parent_model_id,
                "dynamic": mode == "REQUEST_NEW",
                "alpha_transparency": bool(placement.get("alpha_transparency", True)),
                "filtering_enabled": bool(placement.get("filtering_enabled", False)),
                "lod_distance": float(placement.get("lod_distance", options.get("default_lod_distance", 300.0))),
                "placements": [],
                "dff_path": None,
                "txd_path": None,
                "col_path": None,
                "export_group": None,
            }
            assets[model_key] = asset

        asset["placements"].append(placement)
        asset["lod_distance"] = max(asset["lod_distance"], float(placement.get("lod_distance", 0.0)))

        if not asset["target_model_id"] and placement.get("target_model_id"):
            asset["target_model_id"] = int(placement["target_model_id"])

    if mode == "REPLACE_EXISTING":
        for asset in assets.values():
            target_id = int(asset["target_model_id"] or 0)
            if target_id > 0 and target_id not in used_target_ids:
                used_target_ids.add(target_id)
                continue

            while next_target_id in used_target_ids:
                next_target_id += 1

            asset["target_model_id"] = next_target_id
            used_target_ids.add(next_target_id)
            next_target_id += 1

            if options.get("write_model_ids_to_scene", True):
                for placement in asset["placements"]:
                    obj = placement["source_object"]
                    obj["MTA_Model_ID"] = asset["target_model_id"]
                    settings = get_mta_object_settings(obj)
                    if settings is not None:
                        settings.target_model_id = asset["target_model_id"]

    return assets


def configure_dff_exporter(options, models_directory):
    exporter = dff_samp_exporter.dff_exporter
    state_names = (
        "selected",
        "mass_export",
        "preserve_positions",
        "path",
        "version",
        "export_coll",
        "preserve_collision_positions",
        "force_collision_to_dff_transform",
        "export_frame_names",
        "truncate_frame_names",
        "collection",
        "collision_objects",
    )
    previous_state = {name: getattr(exporter, name, None) for name in state_names}

    exporter.selected = False
    exporter.mass_export = False
    exporter.preserve_positions = False
    exporter.path = models_directory
    exporter.version = int(options.get("rw_version", 0x36003))
    exporter.export_coll = options.get("collision_mode", "SEPARATE") == "EMBEDDED"
    exporter.preserve_collision_positions = True
    exporter.force_collision_to_dff_transform = True
    exporter.export_frame_names = True
    exporter.truncate_frame_names = bool(options.get("truncate_frame_names", False))
    return previous_state


def restore_dff_exporter(previous_state):
    exporter = dff_samp_exporter.dff_exporter
    for name, value in previous_state.items():
        setattr(exporter, name, value)


def export_dff_asset(asset, group, options, models_directory):
    exporter = dff_samp_exporter.dff_exporter
    file_name = asset["model_name"] + ".dff"
    output_path = os.path.join(models_directory, file_name)

    exporter.collection = group["collection"]
    exporter.collision_objects = group["collision_objects"]
    exporter.reset_export_state()

    if os.path.isfile(output_path):
        os.remove(output_path)

    exporter.export_objects(group["objects"], file_name)

    if not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
        raise MTAExportError("DFF export produced no file for model %s" % asset["model_name"])

    asset["dff_path"] = "models/%s" % file_name
    return output_path


def export_separate_collision(asset, group, models_directory):
    collision_objects = list(group.get("collision_objects") or [])
    if not collision_objects:
        return None

    output_name = asset["model_name"] + ".col"
    output_path = os.path.join(models_directory, output_name)
    exporter = dff_samp_exporter.dff_exporter
    local_matrix = exporter.get_exported_collision_frame_matrix_for_export_objects(group["objects"])
    matrix_rows = [list(row) for row in local_matrix]

    col_samp_exporter.export_col({
        "file_name": output_path,
        "memory": False,
        "version": 3,
        "collection": group["collection"],
        "only_selected": False,
        "mass_export": False,
        "objects": collision_objects,
        "preserve_positions": True,
        "embedded_local_matrix_world": matrix_rows,
    })

    if not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
        return None

    asset["col_path"] = "models/%s" % output_name
    return output_path


def export_txd_assets(assets, groups, options, models_directory):
    if not options.get("export_txd", True):
        return []

    objects_by_txd = {}
    assets_by_txd = {}

    for asset in assets.values():
        txd_name = asset["txd_name"]
        group = groups.get(asset["model_key"])
        if group is not None:
            objects_by_txd.setdefault(txd_name, []).extend(group["objects"])
        assets_by_txd.setdefault(txd_name, []).append(asset)

    exported_files = []
    source_directory = options.get("source_assets_directory", "")
    txd_exporter.txd_exporter.version = int(options.get("rw_version", 0x36003))

    for txd_name, target_assets in sorted(assets_by_txd.items()):
        output_name = sanitize_asset_name(txd_name) + ".txd"
        output_path = os.path.join(models_directory, output_name)
        objects = unique_objects(objects_by_txd.get(txd_name, []))
        used_textures = txd_exporter.txd_exporter.get_used_textures(objects) if objects else set()

        if used_textures:
            txd_exporter.txd_exporter.export_textures(objects, output_path)
        elif options.get("copy_existing_assets", True):
            source_path = find_case_insensitive_file(source_directory, output_name)
            if source_path:
                shutil.copy2(source_path, output_path)

        if os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
            relative_path = "models/%s" % output_name
            exported_files.append(output_path)
            for asset in target_assets:
                asset["txd_path"] = relative_path

    return exported_files


def copy_missing_model_assets(assets, options, models_directory):
    if not options.get("copy_existing_assets", True):
        return []

    source_directory = options.get("source_assets_directory", "")
    copied = []
    collision_mode = options.get("collision_mode", "SEPARATE")

    for asset in assets.values():
        candidates = []
        if asset["dff_path"] is None:
            candidates.append((asset["model_name"] + ".dff", "dff_path"))
        if asset["txd_path"] is None and options.get("export_txd", True):
            candidates.append((asset["txd_name"] + ".txd", "txd_path"))
        if asset["col_path"] is None and collision_mode == "SEPARATE":
            candidates.append((asset["model_name"] + ".col", "col_path"))

        for filename, field_name in candidates:
            source_path = find_case_insensitive_file(source_directory, filename)
            if not source_path:
                continue

            output_path = os.path.join(models_directory, filename)
            shutil.copy2(source_path, output_path)
            asset[field_name] = "models/%s" % filename
            copied.append(output_path)

    return copied


def write_models_lua(resource_directory, assets):
    path = os.path.join(resource_directory, "models.lua")
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        file.write("-- Generated by DemonFF 0.5.2\n")
        file.write("DemonFFMTAModels = {\n")

        for asset in sorted(assets.values(), key=lambda item: item["model_key"]):
            if not asset["dff_path"]:
                continue

            file.write("    { ")
            file.write("key = %s, " % lua_quote(asset["model_key"]))
            file.write("name = %s, " % lua_quote(asset["model_name"]))
            file.write("dynamic = %s, " % lua_bool(asset["dynamic"]))
            file.write("replaceId = %d, " % int(asset["target_model_id"] or 0))
            file.write("parentId = %d, " % int(asset["parent_model_id"]))
            file.write("dff = %s, " % lua_quote(asset["dff_path"]))
            file.write("txd = %s, " % (lua_quote(asset["txd_path"]) if asset["txd_path"] else "false"))
            file.write("col = %s, " % (lua_quote(asset["col_path"]) if asset["col_path"] else "false"))
            file.write("alphaTransparency = %s, " % lua_bool(asset["alpha_transparency"]))
            file.write("filteringEnabled = %s, " % lua_bool(asset["filtering_enabled"]))
            file.write("lodDistance = %s " % format_float(asset["lod_distance"]))
            file.write("},\n")

        file.write("}\n")

    return path


def write_placements_lua(resource_directory, placements):
    path = os.path.join(resource_directory, "placements.lua")
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        file.write("-- Generated by DemonFF 0.5.2\n")
        file.write("DemonFFMTAPlacements = {\n")

        for index, placement in enumerate(placements, 1):
            file.write("    { ")
            file.write("id = %s, " % lua_quote("demonff_%05d" % index))
            file.write("name = %s, " % lua_quote(placement["name"]))
            file.write("model = %s, " % lua_quote(placement["model_key"]))
            file.write("x = %s, y = %s, z = %s, " % (
                format_float(placement["x"]),
                format_float(placement["y"]),
                format_float(placement["z"]),
            ))
            file.write("rx = %s, ry = %s, rz = %s, " % (
                format_float(placement["rx"]),
                format_float(placement["ry"]),
                format_float(placement["rz"]),
            ))
            file.write("scaleX = %s, scaleY = %s, scaleZ = %s, " % (
                format_float(placement["scale_x"]),
                format_float(placement["scale_y"]),
                format_float(placement["scale_z"]),
            ))
            file.write("interior = %d, dimension = %d, " % (
                int(placement["interior"]),
                int(placement["dimension"]),
            ))
            file.write("doubleSided = %s, " % lua_bool(placement["double_sided"]))
            file.write("collisionsEnabled = %s, " % lua_bool(placement["collisions_enabled"]))
            file.write("frozen = %s, " % lua_bool(placement["frozen"]))
            file.write("breakable = %s, " % lua_bool(placement["breakable"]))
            file.write("alpha = %d " % int(max(0, min(255, placement["alpha"]))))
            file.write("},\n")

        file.write("}\n")

    return path


def write_client_lua(resource_directory, create_placements=True):
    path = os.path.join(resource_directory, "client.lua")
    content = '''-- Generated by DemonFF 0.5.2

local loadedModels = {}
local modelIds = {}
local createdObjects = {}
local loadedElements = {}

local function rememberElement(element)
    if element and isElement(element) then
        loadedElements[#loadedElements + 1] = element
    end
    return element
end

local function loadCustomModel(definition)
    local modelId = definition.replaceId

    if definition.dynamic then
        modelId = engineRequestModel("object", definition.parentId)
        if not modelId then
            outputDebugString("DemonFF MTA: engineRequestModel failed for " .. definition.key, 1)
            return false
        end
    end

    if definition.col then
        local collision = rememberElement(engineLoadCOL(definition.col))
        if not collision or not engineReplaceCOL(collision, modelId) then
            outputDebugString("DemonFF MTA: failed to load/replace COL for " .. definition.key, 2)
        end
    end

    if definition.txd then
        local texture = rememberElement(engineLoadTXD(definition.txd, definition.filteringEnabled))
        if not texture or not engineImportTXD(texture, modelId) then
            outputDebugString("DemonFF MTA: failed to load/import TXD for " .. definition.key, 2)
        end
    end

    local model = rememberElement(engineLoadDFF(definition.dff))
    if not model then
        outputDebugString("DemonFF MTA: failed to load DFF for " .. definition.key, 1)
        if definition.dynamic then
            engineFreeModel(modelId)
        end
        return false
    end

    if not engineReplaceModel(model, modelId, definition.alphaTransparency) then
        outputDebugString("DemonFF MTA: failed to replace model for " .. definition.key, 1)
        if definition.dynamic then
            engineFreeModel(modelId)
        end
        return false
    end

    if definition.lodDistance and definition.lodDistance > 0 then
        engineSetModelLODDistance(modelId, definition.lodDistance)
    end

    loadedModels[#loadedModels + 1] = {
        modelId = modelId,
        dynamic = definition.dynamic,
    }
    modelIds[definition.key] = modelId
    return true
end

local function createPlacement(definition)
    local modelId = modelIds[definition.model]
    if not modelId then
        outputDebugString("DemonFF MTA: no model ID was loaded for placement " .. tostring(definition.model), 2)
        return false
    end

    local object = createObject(
        modelId,
        definition.x,
        definition.y,
        definition.z,
        definition.rx,
        definition.ry,
        definition.rz
    )

    if not object then
        outputDebugString("DemonFF MTA: createObject failed for " .. tostring(definition.model), 1)
        return false
    end

    setElementID(object, definition.id)
    setObjectScale(object, definition.scaleX, definition.scaleY, definition.scaleZ)
    setElementInterior(object, definition.interior)
    setElementDimension(object, definition.dimension)
    setElementDoubleSided(object, definition.doubleSided)
    setElementCollisionsEnabled(object, definition.collisionsEnabled)
    setElementFrozen(object, definition.frozen)
    setObjectBreakable(object, definition.breakable)
    setElementAlpha(object, definition.alpha)

    createdObjects[#createdObjects + 1] = object
    return true
end

local function startDemonFFResource()
    for _, definition in ipairs(DemonFFMTAModels or {}) do
        loadCustomModel(definition)
    end

    if CREATE_DEMONFF_PLACEMENTS then
        for _, definition in ipairs(DemonFFMTAPlacements or {}) do
            createPlacement(definition)
        end
    end

    outputDebugString(
        "DemonFF MTA: loaded " .. tostring(#loadedModels) ..
        " model(s) and created " .. tostring(#createdObjects) .. " object(s).",
        3
    )
end

local function stopDemonFFResource()
    for index = #createdObjects, 1, -1 do
        local object = createdObjects[index]
        if object and isElement(object) then
            destroyElement(object)
        end
    end
    createdObjects = {}

    for index = #loadedModels, 1, -1 do
        local definition = loadedModels[index]
        engineRestoreModel(definition.modelId)
        engineRestoreCOL(definition.modelId)
        if engineResetModelLODDistance then
            engineResetModelLODDistance(definition.modelId)
        end
        if definition.dynamic then
            engineFreeModel(definition.modelId)
        end
    end
    loadedModels = {}
    modelIds = {}

    for index = #loadedElements, 1, -1 do
        local element = loadedElements[index]
        if element and isElement(element) then
            destroyElement(element)
        end
    end
    loadedElements = {}
end

addEventHandler("onClientResourceStart", resourceRoot, startDemonFFResource)
addEventHandler("onClientResourceStop", resourceRoot, stopDemonFFResource)
'''

    content = "local CREATE_DEMONFF_PLACEMENTS = %s\n\n" % lua_bool(create_placements) + content

    with open(path, "w", encoding="utf-8", newline="\n") as file:
        file.write(content)

    return path


def write_map_file(resource_directory, placements, assets):
    root = ET.Element("map")
    root.set("mod", "deathmatch")

    for index, placement in enumerate(placements, 1):
        asset = assets.get(placement["model_key"])
        if asset is None or asset["dynamic"] or not asset["target_model_id"]:
            continue

        element = ET.SubElement(root, "object")
        element.set("id", "demonff_%05d" % index)
        element.set("model", str(int(asset["target_model_id"])))
        element.set("posX", format_float(placement["x"]))
        element.set("posY", format_float(placement["y"]))
        element.set("posZ", format_float(placement["z"]))
        element.set("rotX", format_float(placement["rx"]))
        element.set("rotY", format_float(placement["ry"]))
        element.set("rotZ", format_float(placement["rz"]))
        element.set("scale", format_float(placement["scale_x"]))
        element.set("interior", str(int(placement["interior"])))
        element.set("dimension", str(int(placement["dimension"])))
        element.set("doublesided", "true" if placement["double_sided"] else "false")
        element.set("collisions", "true" if placement["collisions_enabled"] else "false")
        element.set("frozen", "true" if placement["frozen"] else "false")
        element.set("breakable", "true" if placement["breakable"] else "false")
        element.set("alpha", str(int(max(0, min(255, placement["alpha"])))))

    path = os.path.join(resource_directory, "placements.map")
    tree = ET.ElementTree(root)
    try:
        ET.indent(tree, space="    ")
    except AttributeError:
        pass
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path


def write_meta_xml(resource_directory, options, asset_files, include_map_file):
    root = ET.Element("meta")
    info = ET.SubElement(root, "info")
    info.set("author", str(options.get("author", "")))
    info.set("name", str(options.get("resource_name", "DemonFF MTA Resource")))
    info.set("description", str(options.get("description", "Generated by DemonFF")))
    info.set("version", "0.5.2")
    info.set("type", "script")

    for script_name in ("models.lua", "placements.lua", "client.lua"):
        script = ET.SubElement(root, "script")
        script.set("src", script_name)
        script.set("type", "client")
        script.set("cache", "false")

    if include_map_file:
        map_element = ET.SubElement(root, "map")
        map_element.set("src", "placements.map")
        map_element.set("dimension", str(int(options.get("default_dimension", 0))))

    for absolute_path in sorted(set(asset_files)):
        relative_path = os.path.relpath(absolute_path, resource_directory).replace("\\", "/")
        file_element = ET.SubElement(root, "file")
        file_element.set("src", relative_path)

    path = os.path.join(resource_directory, "meta.xml")
    tree = ET.ElementTree(root)
    try:
        ET.indent(tree, space="    ")
    except AttributeError:
        pass
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path


def write_readme(resource_directory, options, assets, placements, missing_models):
    path = os.path.join(resource_directory, "README.txt")
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        file.write("DemonFF MTA resource\n")
        file.write("====================\n\n")
        file.write("Resource: %s\n" % options.get("resource_name", ""))
        file.write("Model mode: %s\n" % options.get("model_mode", "REQUEST_NEW"))
        file.write("Collision mode: %s\n" % options.get("collision_mode", "SEPARATE"))
        file.write("Models written: %d\n" % sum(1 for asset in assets.values() if asset["dff_path"]))
        file.write("Placements written: %d\n" % len(placements))
        file.write("Missing model binaries: %d\n\n" % len(missing_models))

        if missing_models:
            file.write("Missing models\n")
            file.write("--------------\n")
            for model_name in sorted(missing_models):
                file.write("%s\n" % model_name)

    return path


def zip_resource(resource_directory):
    zip_path = resource_directory.rstrip(os.sep) + ".zip"
    if os.path.isfile(zip_path):
        os.remove(zip_path)

    base_directory = os.path.dirname(resource_directory)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for root, directories, files in os.walk(resource_directory):
            directories.sort()
            files.sort()
            for filename in files:
                absolute_path = os.path.join(root, filename)
                archive_name = os.path.relpath(absolute_path, base_directory).replace("\\", "/")
                archive.write(absolute_path, archive_name)

    return zip_path


def export_mta_resource(options):
    context = bpy.context
    resource_name = sanitize_resource_name(options.get("resource_name", "demonff_mta_resource"))
    output_directory = os.path.abspath(os.path.expanduser(options.get("output_directory", "")))
    if not output_directory:
        raise MTAExportError("No MTA output directory was selected.")

    resource_directory = os.path.join(output_directory, resource_name)
    models_directory = os.path.join(resource_directory, "models")

    if options.get("clean_output", True) and os.path.isdir(resource_directory):
        shutil.rmtree(resource_directory)

    os.makedirs(models_directory, exist_ok=True)
    options = dict(options)
    options["resource_name"] = resource_name

    placements = collect_placements(context, options)
    if not placements:
        raise MTAExportError("No exportable map/model placements were found in the chosen scope.")

    assets = build_assets(placements, options)
    export_groups = collect_export_groups()
    asset_files = []
    missing_models = []

    previous_state = configure_dff_exporter(options, models_directory)
    try:
        for asset in sorted(assets.values(), key=lambda item: item["model_key"]):
            group = export_groups.get(asset["model_key"])
            asset["export_group"] = group
            if group is None or not options.get("export_dff", True):
                continue

            try:
                asset_files.append(export_dff_asset(asset, group, options, models_directory))
            except Exception as error:
                print("DemonFF MTA export: failed DFF %s: %s" % (asset["model_name"], error))

            if options.get("collision_mode", "SEPARATE") == "SEPARATE":
                try:
                    col_path = export_separate_collision(asset, group, models_directory)
                    if col_path:
                        asset_files.append(col_path)
                except Exception as error:
                    print("DemonFF MTA export: failed COL %s: %s" % (asset["model_name"], error))
    finally:
        restore_dff_exporter(previous_state)

    asset_files.extend(export_txd_assets(assets, export_groups, options, models_directory))
    asset_files.extend(copy_missing_model_assets(assets, options, models_directory))

    for asset in assets.values():
        if not asset["dff_path"]:
            missing_models.append(asset["model_name"])

    if missing_models and options.get("fail_on_missing_models", True):
        raise MTAExportError(
            "MTA resource export is missing DFF files for: %s" % ", ".join(sorted(missing_models))
        )

    write_models_lua(resource_directory, assets)
    write_placements_lua(resource_directory, placements)

    include_map_file = bool(options.get("write_map_file", False)) and options.get("model_mode") == "REPLACE_EXISTING"
    write_client_lua(resource_directory, create_placements=not include_map_file)

    if include_map_file:
        write_map_file(resource_directory, placements, assets)

    write_meta_xml(resource_directory, options, asset_files, include_map_file)
    write_readme(resource_directory, options, assets, placements, missing_models)

    zip_path = zip_resource(resource_directory) if options.get("create_zip", True) else None

    result = {
        "resource_directory": resource_directory,
        "zip_path": zip_path,
        "placements": len(placements),
        "models": sum(1 for asset in assets.values() if asset["dff_path"]),
        "missing_models": missing_models,
    }

    print(
        "DemonFF MTA export verify: resource=%s models=%d placements=%d missing_models=%d zip=%s" % (
            resource_directory,
            result["models"],
            result["placements"],
            len(missing_models),
            zip_path or "none",
        )
    )

    return result


def parse_lua_scalar(value):
    value = value.strip().rstrip(",")
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "nil":
        return None
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        content = value[1:-1]
        content = content.replace("\\n", "\n")
        content = content.replace("\\r", "\r")
        content = content.replace('\\"', '"')
        content = content.replace("\\\\", "\\")
        return content
    try:
        return int(value, 10)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def parse_lua_table_entries(text, table_name):
    marker = re.search(r"\b%s\s*=\s*\{" % re.escape(table_name), text)
    if not marker:
        return []

    start = text.find("{", marker.start())
    if start < 0:
        return []

    entries = []
    depth = 0
    in_string = False
    escaped = False
    entry_start = None

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            depth += 1
            if depth == 2:
                entry_start = index + 1
            continue

        if char == "}":
            if depth == 2 and entry_start is not None:
                entry_text = text[entry_start:index]
                record = {}
                for match in re.finditer(
                    r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\"(?:\\.|[^\"])*\"|true|false|nil|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)",
                    entry_text,
                ):
                    record[match.group(1)] = parse_lua_scalar(match.group(2))
                if record:
                    entries.append(record)
                entry_start = None
            depth -= 1
            if depth == 0:
                break

    return entries


def parse_create_object_lines(text):
    placements = []
    variables = {}
    number = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
    pattern = re.compile(
        r"(?:(?:local\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*)?createObject\s*\(\s*([^,]+)\s*,\s*(%s)\s*,\s*(%s)\s*,\s*(%s)(?:\s*,\s*(%s)\s*,\s*(%s)\s*,\s*(%s))?\s*\)" % (
            number,
            number,
            number,
            number,
            number,
            number,
        )
    )

    for match in pattern.finditer(text):
        variable = match.group(1) or "object_%d" % (len(placements) + 1)
        model_expression = match.group(2).strip()
        model_value = parse_lua_scalar(model_expression)
        placement = {
            "id": variable,
            "name": variable,
            "model": model_value,
            "x": float(match.group(3)),
            "y": float(match.group(4)),
            "z": float(match.group(5)),
            "rx": float(match.group(6) or 0.0),
            "ry": float(match.group(7) or 0.0),
            "rz": float(match.group(8) or 0.0),
            "scaleX": 1.0,
            "scaleY": 1.0,
            "scaleZ": 1.0,
            "interior": 0,
            "dimension": 0,
            "doubleSided": False,
            "collisionsEnabled": True,
            "frozen": True,
            "breakable": False,
            "alpha": 255,
        }
        placements.append(placement)
        variables[variable] = placement

    modifier_patterns = (
        ("interior", re.compile(r"setElementInterior\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*(%s)\s*\)" % number)),
        ("dimension", re.compile(r"setElementDimension\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*(%s)\s*\)" % number)),
        ("alpha", re.compile(r"setElementAlpha\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*(%s)\s*\)" % number)),
        ("doubleSided", re.compile(r"setElementDoubleSided\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*(true|false)\s*\)")),
        ("collisionsEnabled", re.compile(r"setElementCollisionsEnabled\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*(true|false)\s*\)")),
        ("frozen", re.compile(r"setElementFrozen\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*(true|false)\s*\)")),
        ("breakable", re.compile(r"setObjectBreakable\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*(true|false)\s*\)")),
    )

    for field_name, modifier_pattern in modifier_patterns:
        for match in modifier_pattern.finditer(text):
            placement = variables.get(match.group(1))
            if placement is not None:
                placement[field_name] = parse_lua_scalar(match.group(2))

    scale_pattern = re.compile(
        r"setObjectScale\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*(%s)(?:\s*,\s*(%s)\s*,\s*(%s))?\s*\)" % (
            number,
            number,
            number,
        )
    )
    for match in scale_pattern.finditer(text):
        placement = variables.get(match.group(1))
        if placement is None:
            continue
        scale_x = float(match.group(2))
        placement["scaleX"] = scale_x
        placement["scaleY"] = float(match.group(3) or scale_x)
        placement["scaleZ"] = float(match.group(4) or scale_x)

    return placements


def parse_map_xml(path):
    tree = ET.parse(path)
    root = tree.getroot()
    placements = []

    for element in root.iter():
        if element.tag.lower().split("}")[-1] not in {"object", "building"}:
            continue

        attributes = element.attrib
        model_value = attributes.get("model", attributes.get("modelID", "0"))
        placements.append({
            "id": attributes.get("id", "object_%d" % (len(placements) + 1)),
            "name": attributes.get("name", attributes.get("id", "object_%d" % (len(placements) + 1))),
            "model": parse_lua_scalar(model_value),
            "x": float(attributes.get("posX", attributes.get("x", 0.0))),
            "y": float(attributes.get("posY", attributes.get("y", 0.0))),
            "z": float(attributes.get("posZ", attributes.get("z", 0.0))),
            "rx": float(attributes.get("rotX", attributes.get("rx", 0.0))),
            "ry": float(attributes.get("rotY", attributes.get("ry", 0.0))),
            "rz": float(attributes.get("rotZ", attributes.get("rz", 0.0))),
            "scaleX": float(attributes.get("scaleX", attributes.get("scale", 1.0))),
            "scaleY": float(attributes.get("scaleY", attributes.get("scale", 1.0))),
            "scaleZ": float(attributes.get("scaleZ", attributes.get("scale", 1.0))),
            "interior": int(attributes.get("interior", 0)),
            "dimension": int(attributes.get("dimension", 0)),
            "doubleSided": str(attributes.get("doublesided", "false")).lower() == "true",
            "collisionsEnabled": str(attributes.get("collisions", "true")).lower() == "true",
            "frozen": str(attributes.get("frozen", "true")).lower() == "true",
            "breakable": str(attributes.get("breakable", "false")).lower() == "true",
            "alpha": int(attributes.get("alpha", 255)),
        })

    return placements


def read_text_file(path):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return file.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="latin-1", errors="replace") as file:
            return file.read()


def find_resource_files(resource_directory):
    result = {
        "models": None,
        "placements": None,
        "client": None,
        "map": None,
    }

    meta_path = os.path.join(resource_directory, "meta.xml")
    if os.path.isfile(meta_path):
        try:
            tree = ET.parse(meta_path)
            root = tree.getroot()
            for element in root:
                tag = element.tag.lower().split("}")[-1]
                src = element.attrib.get("src")
                if not src:
                    continue
                absolute_path = os.path.join(resource_directory, src.replace("/", os.sep))
                if tag == "script":
                    base_name = os.path.basename(src).lower()
                    if base_name == "models.lua":
                        result["models"] = absolute_path
                    elif base_name == "placements.lua":
                        result["placements"] = absolute_path
                    elif result["client"] is None:
                        result["client"] = absolute_path
                elif tag == "map" and result["map"] is None:
                    result["map"] = absolute_path
        except Exception:
            pass

    for key, filename in (
        ("models", "models.lua"),
        ("placements", "placements.lua"),
        ("client", "client.lua"),
        ("map", "placements.map"),
    ):
        if result[key] is None:
            path = os.path.join(resource_directory, filename)
            if os.path.isfile(path):
                result[key] = path

    return result


def parse_resource_input(filepath):
    temporary_directory = None
    input_path = os.path.abspath(filepath)

    if input_path.lower().endswith(".zip"):
        temporary_directory = tempfile.mkdtemp(prefix="demonff_mta_")
        with zipfile.ZipFile(input_path, "r") as archive:
            archive.extractall(temporary_directory)

        meta_candidates = []
        for root, directories, files in os.walk(temporary_directory):
            directories.sort()
            if "meta.xml" in files:
                meta_candidates.append(os.path.join(root, "meta.xml"))

        if meta_candidates:
            input_path = sorted(meta_candidates)[0]
        else:
            input_path = temporary_directory

    if os.path.isdir(input_path):
        resource_directory = input_path
    elif os.path.basename(input_path).lower() == "meta.xml":
        resource_directory = os.path.dirname(input_path)
    else:
        resource_directory = os.path.dirname(input_path)

    models = []
    placements = []
    files = find_resource_files(resource_directory)

    model_path = files.get("models")
    if model_path and os.path.isfile(model_path):
        models = parse_lua_table_entries(read_text_file(model_path), "DemonFFMTAModels")

    placement_path = files.get("placements")
    if placement_path and os.path.isfile(placement_path):
        placements = parse_lua_table_entries(read_text_file(placement_path), "DemonFFMTAPlacements")

    if not placements and input_path.lower().endswith((".map", ".xml")) and os.path.isfile(input_path):
        placements = parse_map_xml(input_path)

    if not placements and files.get("map") and os.path.isfile(files["map"]):
        placements = parse_map_xml(files["map"])

    if not placements:
        lua_path = input_path if input_path.lower().endswith(".lua") else files.get("client")
        if lua_path and os.path.isfile(lua_path):
            text = read_text_file(lua_path)
            placements = parse_lua_table_entries(text, "DemonFFMTAPlacements")
            if not placements:
                placements = parse_create_object_lines(text)
            if not models:
                models = parse_lua_table_entries(text, "DemonFFMTAModels")

    return models, placements, resource_directory, temporary_directory


def build_source_collections():
    by_name = {}
    by_model_id = {}

    for collection in bpy.data.collections:
        if not collection.objects:
            continue

        collection_key = normalize_model_key(collection.name)
        by_name.setdefault(collection_key, collection)

        for obj in collection.objects:
            names = [
                obj.name,
                map_exporter.get_object_model_name(obj),
                get_string_property(obj, "model_key", ""),
            ]
            for name in names:
                key = normalize_model_key(name)
                if key:
                    by_name.setdefault(key, collection)

            model_ids = [
                get_int_property(obj, "target_model_id", 0),
                map_exporter.get_object_samp_id(obj, 0),
                map_exporter.get_object_ide_id(obj, 0),
            ]
            for model_id in model_ids:
                try:
                    model_id = int(model_id)
                except Exception:
                    continue
                if model_id:
                    by_model_id.setdefault(model_id, collection)

    return by_name, by_model_id


def duplicate_collection_objects(source_collection, destination_collection, placement_name):
    source_objects = list(iter_collection_objects(source_collection))
    source_set = set(source_objects)
    object_map = {}

    for source in source_objects:
        duplicate = source.copy()
        if source.data is not None:
            duplicate.data = source.data
        duplicate.animation_data_clear()
        destination_collection.objects.link(duplicate)
        object_map[source] = duplicate

    for source, duplicate in object_map.items():
        if source.parent in source_set:
            duplicate.parent = object_map[source.parent]
            duplicate.matrix_parent_inverse = source.matrix_parent_inverse.copy()

    roots = [object_map[source] for source in source_objects if source.parent not in source_set]
    placement_root = bpy.data.objects.new(placement_name, None)
    placement_root.empty_display_type = "PLAIN_AXES"
    destination_collection.objects.link(placement_root)

    for root in roots:
        root.parent = placement_root

    return placement_root, list(object_map.values())


def create_placeholder(destination_collection, placement_name):
    root = bpy.data.objects.new(placement_name, None)
    root.empty_display_type = "CUBE"
    root.empty_display_size = 1.0
    destination_collection.objects.link(root)
    return root, []


def apply_imported_placement(root, duplicated_objects, placement, model_key, model_id):
    root.location = (
        float(placement.get("x", 0.0)),
        float(placement.get("y", 0.0)),
        float(placement.get("z", 0.0)),
    )
    root.rotation_mode = "XYZ"
    root.rotation_euler = (
        math.radians(float(placement.get("rx", 0.0))),
        math.radians(float(placement.get("ry", 0.0))),
        math.radians(float(placement.get("rz", 0.0))),
    )
    root.scale = (
        float(placement.get("scaleX", placement.get("scale", 1.0))),
        float(placement.get("scaleY", placement.get("scale", 1.0))),
        float(placement.get("scaleZ", placement.get("scale", 1.0))),
    )

    all_objects = [root] + duplicated_objects
    for obj in all_objects:
        obj["MTA_Model_Key"] = str(model_key)
        obj["MTA_Model_ID"] = int(model_id or 0)
        obj["MTA_Interior"] = int(placement.get("interior", 0))
        obj["MTA_Dimension"] = int(placement.get("dimension", 0))
        obj["MTA_Double_Sided"] = bool(placement.get("doubleSided", False))
        obj["MTA_Collisions_Enabled"] = bool(placement.get("collisionsEnabled", True))
        obj["MTA_Frozen"] = bool(placement.get("frozen", True))
        obj["MTA_Breakable"] = bool(placement.get("breakable", False))
        obj["MTA_Alpha"] = int(placement.get("alpha", 255))

        settings = get_mta_object_settings(obj)
        if settings is not None:
            settings.model_key = str(model_key)
            settings.target_model_id = int(model_id or 0)
            settings.use_custom_interior = True
            settings.interior = int(placement.get("interior", 0))
            settings.use_custom_dimension = True
            settings.dimension = int(placement.get("dimension", 0))
            settings.double_sided = bool(placement.get("doubleSided", False))
            settings.collisions_enabled = bool(placement.get("collisionsEnabled", True))
            settings.frozen = bool(placement.get("frozen", True))
            settings.breakable = bool(placement.get("breakable", False))
            settings.alpha = int(placement.get("alpha", 255))


def import_mta_file(options):
    filepath = options.get("file_name", "")
    if not filepath:
        raise MTAImportError("No MTA Lua, map, resource, or zip file was selected.")

    models, placements, resource_directory, temporary_directory = parse_resource_input(filepath)
    try:
        if not placements:
            raise MTAImportError("No static MTA createObject placements were found.")

        model_key_by_id = {}
        model_id_by_key = {}
        for model in models:
            key = normalize_model_key(model.get("key", model.get("name", "")))
            if not key:
                continue
            model_id = int(model.get("replaceId", 0) or 0)
            parent_id = int(model.get("parentId", 0) or 0)
            model_id_by_key[key] = model_id
            if model_id:
                model_key_by_id[model_id] = key
            if parent_id:
                model_key_by_id.setdefault(parent_id, key)

        source_by_name, source_by_id = build_source_collections()
        collection_name = options.get("collection_name", "") or (sanitize_asset_name(clean_extension(filepath)) + " MTA Import")
        destination_collection = bpy.data.collections.get(collection_name)

        if destination_collection is None:
            destination_collection = bpy.data.collections.new(collection_name)
            bpy.context.scene.collection.children.link(destination_collection)
        elif options.get("clear_existing", False):
            for obj in list(destination_collection.objects):
                bpy.data.objects.remove(obj, do_unlink=True)

        imported = 0
        placeholders = 0
        missing = {}

        for index, placement in enumerate(placements, 1):
            raw_model = placement.get("model", 0)
            model_id = 0
            model_key = ""

            if isinstance(raw_model, str):
                expression_match = re.search(r"\[\s*\"([^\"]+)\"\s*\]", raw_model)
                if expression_match:
                    model_key = normalize_model_key(expression_match.group(1))
                else:
                    model_key = normalize_model_key(raw_model)
            else:
                try:
                    model_id = int(raw_model)
                except Exception:
                    model_id = 0
                model_key = model_key_by_id.get(model_id, "")

            if model_key and not model_id:
                model_id = int(model_id_by_key.get(model_key, 0) or 0)

            source_collection = source_by_name.get(model_key) if model_key else None
            if source_collection is None and model_id:
                source_collection = source_by_id.get(model_id)

            placement_name = str(placement.get("name", placement.get("id", "mta_%05d" % index)))
            if source_collection is not None and options.get("use_imported_models", True):
                root, duplicated_objects = duplicate_collection_objects(
                    source_collection,
                    destination_collection,
                    placement_name,
                )
            elif options.get("create_placeholders", True):
                root, duplicated_objects = create_placeholder(destination_collection, placement_name)
                placeholders += 1
                missing[model_key or str(model_id)] = missing.get(model_key or str(model_id), 0) + 1
            else:
                missing[model_key or str(model_id)] = missing.get(model_key or str(model_id), 0) + 1
                continue

            apply_imported_placement(root, duplicated_objects, placement, model_key, model_id)
            imported += 1

        print(
            "DemonFF MTA import verify: file=%s placements=%d imported=%d placeholders=%d missing_models=%d resource=%s" % (
                filepath,
                len(placements),
                imported,
                placeholders,
                len(missing),
                resource_directory,
            )
        )

        return {
            "placements": len(placements),
            "imported": imported,
            "placeholders": placeholders,
            "missing": missing,
            "collection": destination_collection.name,
        }
    finally:
        if temporary_directory:
            shutil.rmtree(temporary_directory, ignore_errors=True)
