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

import os
import math
import bpy
import random
import re
import struct
import tempfile
import time
import traceback

from collections import Counter, deque
from mathutils import Matrix, Quaternion, Vector

from ..ops import dff_importer, col_importer
from ..gtaLib import map as map_utilites
from .importer_common import (hide_object)
from .state import State
from .ipl.cull_importer import cull_importer
from .ipl.grge_importer import grge_importer
from .ipl.enex_importer import enex_importer


LCS_RUNTIME_IPL_SECTIONS = {
    "commer",
    "suburb",
    "overview",
    "indust",
    "interiors",
    "cull",
}

LCS_AUXILIARY_IPL_SECTIONS = {
    "comroad",
    "indroads",
    "subroads",
    "temppart",
    "making",
    "fortstaunton",
    "fortdestroyed",
    "leedsbits",
    "leedsbits2",
    "props",
}


#######################################################
def import_text_ide_2dfx(importer, records, root_object, inst):
    if not records or root_object is None:
        return []

    created = []
    collection = importer.current_collection

    for index, record in enumerate(records):
        try:
            red = max(0.0, min(1.0, float(record.red) / 255.0))
            green = max(0.0, min(1.0, float(record.green) / 255.0))
            blue = max(0.0, min(1.0, float(record.blue) / 255.0))
            alpha = max(0.0, min(1.0, float(record.alpha) / 255.0))

            effect_type = int(float(getattr(record, 'effectType', 0)))
            light_data = None

            if effect_type == 0:
                light_data = bpy.data.lights.new(
                    name="2dfx_light_%s_%d" % (record.id, index),
                    type='POINT'
                )
                light_data.color = (red, green, blue)
                light_data.energy = 10.0
                light_data.shadow_soft_size = 0.25
                obj = bpy.data.objects.new(light_data.name, light_data)
            else:
                obj = bpy.data.objects.new(
                    "2dfx_effect_%s_%d_type_%d" % (record.id, index, effect_type),
                    None
                )
                obj.empty_display_type = 'PLAIN_AXES'
                obj.empty_display_size = 0.35

            obj.dff.type = '2DFX'
            obj.dff.ext_2dfx.effect = str(effect_type)
            obj.parent = root_object
            obj.matrix_parent_inverse = Matrix.Identity(4)
            obj.matrix_basis = Matrix.Translation((
                float(record.posX),
                float(record.posY),
                float(record.posZ),
            ))

            obj["demonff_text_ide_2dfx"] = True
            obj["demonff_2dfx_model_id"] = str(record.id)

            source_model_name = str(root_object.get("DFF_Name", "")).strip()
            if not source_model_name and hasattr(root_object, "dff_map"):
                source_model_name = str(getattr(root_object.dff_map, "model_name", "")).strip()
            if source_model_name:
                obj["demonff_2dfx_source_dff"] = "%s.dff" % source_model_name
                obj["demonff_2dfx_source_model"] = source_model_name
                obj["demonff_2dfx_source_model_key"] = source_model_name
                obj["DFF_Name"] = source_model_name

            obj["demonff_2dfx_alpha"] = alpha
            obj["demonff_2dfx_effect_type"] = str(getattr(record, 'effectType', 0))
            obj["demonff_2dfx_source_ide"] = str(getattr(record, 'filename', ''))

            for field_name in record._fields:
                try:
                    obj["demonff_2dfx_%s" % field_name] = str(getattr(record, field_name))
                except Exception:
                    pass

            settings = getattr(light_data, 'ext_2dfx', None) if light_data is not None else None
            if settings is not None:
                settings.alpha = alpha
                if hasattr(record, 'coronaTexName'):
                    settings.corona_tex_name = str(record.coronaTexName).strip('"')
                if hasattr(record, 'shadowTexName'):
                    settings.shadow_tex_name = str(record.shadowTexName).strip('"')

                numeric = []
                for name in ('param1', 'param2', 'param3', 'param4', 'param5', 'param6', 'param7', 'param8', 'param9'):
                    if hasattr(record, name):
                        try:
                            numeric.append(float(getattr(record, name)))
                        except Exception:
                            numeric.append(0.0)

                if len(numeric) > 0:
                    settings.corona_far_clip = numeric[0]
                if len(numeric) > 1:
                    settings.point_light_range = numeric[1]
                if len(numeric) > 2:
                    settings.corona_size = numeric[2]
                if len(numeric) > 3:
                    settings.shadow_size = numeric[3]

            collection.objects.link(obj)
            created.append(obj)
        except Exception as error:
            print("Could not import text IDE 2DFX for model %s: %s" % (getattr(record, 'id', '?'), error))

    return created

#######################################################
def get_instance_model_data(inst, object_data):
    inst_id = getattr(inst, "id", None)
    model_name = str(getattr(inst, "modelName", "") or "").strip().lower()

    keys = []

    if model_name:
        keys.append((str(inst_id), model_name))
        keys.append(model_name)

    keys.append(inst_id)

    try:
        keys.append(str(inst_id))
    except Exception:
        pass

    try:
        int_id = int(inst_id)
        keys.append(int_id)
        if model_name:
            keys.append((str(int_id), model_name))
    except Exception:
        pass

    seen = set()
    for key in keys:
        marker = repr(key)
        if marker in seen:
            continue
        seen.add(marker)

        if key in object_data:
            return object_data[key]

    return None

#######################################################
def get_instance_cache_key(inst, ide_data):
    model_name = str(getattr(ide_data, "modelName", getattr(inst, "modelName", "")) or "").strip().lower()
    return (str(getattr(inst, "id", "")), model_name)

#######################################################
def get_instance_model_name(inst, object_data):
    ide_data = get_instance_model_data(inst, object_data)

    if ide_data is not None and hasattr(ide_data, "modelName"):
        return str(ide_data.modelName)

    if hasattr(inst, "modelName"):
        return str(inst.modelName)

    return ""

#######################################################
def is_lod_model_name(model_name):
    name = str(model_name or "").strip().lower()
    compact = "".join(ch for ch in name if ch.isalnum())

    if compact.startswith("lod"):
        return True

    # ReLCS stores its global island super-LODs as IslandLOD*. They are
    # ordinary text-IPL entries rather than SA-style LOD links, so name-based
    # filtering must recognize the prefix explicitly.
    if compact.startswith("islandlod"):
        return True

    if compact.startswith("lo") and "lod" in compact[:5]:
        return True

    return False

#######################################################
def is_lod_instance(inst, object_data):
    return is_lod_model_name(get_instance_model_name(inst, object_data))

#######################################################
def link_optional_map_entries(context, parent_collection, map_data, settings):
    entry_sets = (
        ("CULL", bool(getattr(settings, "load_cull", False)), map_data.get("cull_instances", []), cull_importer.import_cull),
        ("GRGE", bool(getattr(settings, "load_grge", False)), map_data.get("grge_instances", []), grge_importer.import_grge),
        ("ENEX", bool(getattr(settings, "load_enex", False)), map_data.get("enex_instances", []), enex_importer.import_enex),
    )

    for name, enabled, entries, importer in entry_sets:
        if not enabled or not entries:
            continue

        collection = bpy.data.collections.new(name)
        parent_collection.children.link(collection)

        for entry in entries:
            try:
                obj = importer(entry)
            except Exception as ex:
                print(f"Could not import {name} entry: {ex}")
                continue

            collection.objects.link(obj)

#######################################################
def get_instance_interior_id(inst):
    value = getattr(inst, "interior", 0)

    try:
        return int(value)
    except (TypeError, ValueError):
        pass

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0

#######################################################
def get_map_section_basename(map_section):
    value = str(map_section or "").replace("\\", "/")
    return os.path.splitext(os.path.basename(value))[0].strip().lower()

#######################################################
def is_explicit_interior_map_section(map_section, object_instances):
    section_name = get_map_section_basename(map_section)
    explicit_tokens = (
        "interior",
        "safehouse",
        "safe_house",
        "missionint",
        "mission_int",
    )

    if any(token in section_name for token in explicit_tokens):
        return True

    interior_ids = {
        get_instance_interior_id(inst)
        for inst in object_instances
    }

    # Small IPLs containing only non-zero interiors are normally dedicated
    # interior placement files even when their filename is custom.
    if (
        object_instances
        and 0 not in interior_ids
        and len(object_instances) <= 512
    ):
        return True

    return False

#######################################################
def get_lcs_ipl_role(map_section):
    section_name = get_map_section_basename(map_section)

    if section_name in LCS_RUNTIME_IPL_SECTIONS:
        return "runtime"
    if section_name in LCS_AUXILIARY_IPL_SECTIONS:
        return "auxiliary"
    return "custom"

#######################################################
def get_lcs_auxiliary_world_id(map_section):
    section_name = get_map_section_basename(map_section)
    ordered_sections = sorted(LCS_AUXILIARY_IPL_SECTIONS)

    try:
        return 1000 + ordered_sections.index(section_name)
    except ValueError:
        return 1099

#######################################################
def get_instance_transform_values(inst):
    position = (
        float(inst.posX),
        float(inst.posY),
        float(inst.posZ),
    )
    quaternion = (
        float(inst.rotX),
        float(inst.rotY),
        float(inst.rotZ),
        float(inst.rotW),
    )
    scale = (
        float(getattr(inst, "scaleX", 1.0)),
        float(getattr(inst, "scaleY", 1.0)),
        float(getattr(inst, "scaleZ", 1.0)),
    )

    values = position + quaternion + scale
    if not all(math.isfinite(value) for value in values):
        raise ValueError(
            "IPL instance contains a non-finite position, quaternion or scale"
        )

    return position, quaternion, scale

#######################################################
def build_instance_matrix(inst):
    position, quaternion, scale_values = get_instance_transform_values(inst)

    location = Vector(position)
    rotation = Quaternion((
        -quaternion[3],
        quaternion[0],
        quaternion[1],
        quaternion[2],
    ))

    if rotation.magnitude > 1.0e-12:
        rotation.normalize()
    else:
        rotation = Quaternion((1.0, 0.0, 0.0, 0.0))

    scale = Vector(scale_values)

    return (
        Matrix.Translation(location)
        @ rotation.to_matrix().to_4x4()
        @ Matrix.Diagonal((scale.x, scale.y, scale.z, 1.0))
    )

#######################################################

 # Converts text IPL to binary IPL for processing
def convert_ipl_to_binary(text_ipl_path):
    with open(text_ipl_path, "r", encoding='latin-1') as f:
        lines = f.readlines()

    entries = []
    reading_inst = False
    for line in lines:
        line = line.strip()
        if line.startswith("inst"):
            reading_inst = True
            continue
        if reading_inst:
            if line.startswith("end"):
                break
            parts = line.split(",")
            if len(parts) >= 11:
                model_id = int(parts[0])
                interior_id = int(parts[2])
                pos = tuple(map(float, parts[3:6]))
                rot = tuple(map(float, parts[6:10]))
                lod_type = int(parts[10])
                entries.append((pos, rot, model_id, interior_id, lod_type))

    # Create a temporary binary file to pass to binary reader
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".iplbin")
    with open(tmp_file.name, "wb") as f:
        header = b'bnry' + (b'\x00' * 28)

#######################################################
_MAP_IMPORT_TIMING_HISTORY = {
    "new_model": deque(maxlen=128),
    "cache": deque(maxlen=1024),
    "finalize": deque(maxlen=16),
}


#######################################################
class Map_Import_Operator(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "scene.demonff_map_import"
    bl_label = "Import IPL/IDE"
    
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    
    _timer = None
    _updating = False
    _calcs_done = False
    _inst_index = 0

    _object_instances = []
    _object_data = []
    _effects_2dfx = {}
    _model_cache = {}
    _col_files_all = set()
    _col_files = []
    _col_index = 0
    _check_collisions = True
    _mesh_collection = None
    _collision_collection = None
    _ipl_collection = None
    _interior_collections = {}
    _model_collections = {}
    _visible_interior = 0
    _map_section_path = ""
    _map_section_role = "custom"
    _preserve_source_interiors = False
    _dff_paths = {}
    _import_started_at = 0.0
    _imported_instances = 0
    _cache_hits = 0
    _new_models = 0
    _missing_models = 0
    _missing_ide_entries = 0
    _skipped_lods = 0
    _imported_2dfx = 0
    _parent_collection_hidden = False
    _collision_total = 0
    _last_progress_print_at = 0.0
    _last_progress_print_index = -1
    _current_progress_detail = ""
    _previous_real_time_update = None
    _scene_state_finalized = False
    _planned_importable_instances = 0
    _planned_unique_models = 0
    _planned_cache_placements = 0
    _planned_missing_models = 0
    _planned_missing_ide_entries = 0
    _planned_skipped_lods = 0
    _planned_model_bytes = 0
    _loaded_model_bytes = 0
    _new_model_durations = None
    _cache_durations = None
    _instance_source_sections = None

    settings = None
    #######################################################
    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene.dff, "import_as_binary")
    #######################################################
    @staticmethod
    def robust_average(values, default_value):
        samples = [float(value) for value in values if value >= 0.0]
        if not samples:
            return float(default_value)

        samples.sort()
        if len(samples) >= 10:
            trim = max(1, int(len(samples) * 0.1))
            samples = samples[trim:-trim]

        return sum(samples) / float(len(samples))

    #######################################################
    def estimate_finalize_seconds(self):
        history = list(_MAP_IMPORT_TIMING_HISTORY["finalize"])
        default_estimate = max(
            2.0,
            self._planned_importable_instances * 0.0035
            + self._planned_unique_models * 0.0025,
        )
        return Map_Import_Operator.robust_average(
            history,
            default_estimate,
        )

    #######################################################
    def estimate_remaining_seconds(self):
        total = len(self._object_instances)
        current = min(self._inst_index, total)
        elapsed = max(
            0.0,
            time.perf_counter() - self._import_started_at,
        )

        if self._scene_state_finalized:
            return 0.0

        finalize_seconds = self.estimate_finalize_seconds()

        if current >= total:
            return finalize_seconds

        local_new = list(self._new_model_durations or ())
        local_cache = list(self._cache_durations or ())

        history_new = list(_MAP_IMPORT_TIMING_HISTORY["new_model"])
        history_cache = list(_MAP_IMPORT_TIMING_HISTORY["cache"])

        new_samples = local_new if local_new else history_new
        cache_samples = local_cache if local_cache else history_cache

        average_new = Map_Import_Operator.robust_average(
            new_samples,
            1.0,
        )
        average_cache = Map_Import_Operator.robust_average(
            cache_samples,
            0.003,
        )

        remaining_new = max(
            0,
            self._planned_unique_models - self._new_models,
        )
        remaining_cache = max(
            0,
            self._planned_cache_placements - self._cache_hits,
        )

        task_estimate = (
            remaining_new * average_new
            + remaining_cache * average_cache
        )

        throughput_estimate = 0.0
        if current > 0 and elapsed > 0.0:
            average_wall_per_entry = elapsed / float(current)
            throughput_estimate = (
                max(0, total - current)
                * average_wall_per_entry
            )

        placement_estimate = max(
            task_estimate,
            throughput_estimate,
        )

        return placement_estimate + finalize_seconds

    #######################################################
    def build_import_plan(self):
        unique_model_keys = set()
        planned_importable = 0
        planned_cache = 0
        planned_missing_models = 0
        planned_missing_ide = 0
        planned_skipped_lods = 0
        planned_model_bytes = 0

        for inst in self._object_instances:
            if self.settings.skip_lod and is_lod_instance(
                inst,
                self._object_data,
            ):
                planned_skipped_lods += 1
                continue

            ide_data = get_instance_model_data(
                inst,
                self._object_data,
            )
            if ide_data is None:
                planned_missing_ide += 1
                continue

            model_name = str(ide_data.modelName)
            dff_path = self._dff_paths.get(model_name.lower())
            if dff_path is None:
                planned_missing_models += 1
                continue

            planned_importable += 1
            cache_key = get_instance_cache_key(inst, ide_data)
            if cache_key in unique_model_keys:
                planned_cache += 1
                continue

            unique_model_keys.add(cache_key)
            try:
                planned_model_bytes += os.path.getsize(dff_path)
            except OSError:
                pass

        self._planned_importable_instances = planned_importable
        self._planned_unique_models = len(unique_model_keys)
        self._planned_cache_placements = planned_cache
        self._planned_missing_models = planned_missing_models
        self._planned_missing_ide_entries = planned_missing_ide
        self._planned_skipped_lods = planned_skipped_lods
        self._planned_model_bytes = planned_model_bytes

        print(
            "Map import plan: %d placements, %d unique DFFs, "
            "%d cached placements, %d missing DFF, %d missing IDE, "
            "%d skipped LOD"
            % (
                planned_importable,
                self._planned_unique_models,
                planned_cache,
                planned_missing_models,
                planned_missing_ide,
                planned_skipped_lods,
            ),
            flush=True,
        )

    #######################################################
    @staticmethod
    def format_progress_duration(seconds):
        seconds = max(
            0,
            int(math.ceil(float(seconds))) if seconds > 0.0 else 0,
        )
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours:
            return "%d:%02d:%02d" % (hours, minutes, seconds)
        return "%02d:%02d" % (minutes, seconds)

    #######################################################
    def update_progress_display(
        self,
        context,
        detail=None,
        force_console=False,
    ):
        total = len(self._object_instances)
        current = min(self._inst_index, total)
        progress = (float(current) / float(total)) if total else 1.0
        percent = progress * 100.0
        elapsed = max(0.0, time.perf_counter() - self._import_started_at)

        if self._scene_state_finalized:
            eta_text = "00:00"
        elif self._planned_unique_models or self._planned_cache_placements:
            eta_text = Map_Import_Operator.format_progress_duration(
                self.estimate_remaining_seconds()
            )
        else:
            eta_text = "--:--"

        elapsed_text = Map_Import_Operator.format_progress_duration(elapsed)
        if detail is not None:
            self._current_progress_detail = str(detail)

        message = (
            "Map import %d/%d (%.1f%%) | models %d/%d | "
            "cached %d/%d | elapsed %s | ETA %s"
            % (
                current,
                total,
                percent,
                self._new_models,
                self._planned_unique_models,
                self._cache_hits,
                self._planned_cache_placements,
                elapsed_text,
                eta_text,
            )
        )

        if self._current_progress_detail:
            message += " | %s" % self._current_progress_detail

        context.window_manager.progress_update(percent)

        try:
            context.workspace.status_text_set(message)
        except Exception:
            pass

        try:
            if context.area is not None:
                context.area.header_text_set(message)
        except Exception:
            pass

        now = time.perf_counter()
        should_print = force_console
        if not should_print and now - self._last_progress_print_at >= 1.0:
            should_print = True
        if not should_print and current - self._last_progress_print_index >= 100:
            should_print = True

        if should_print:
            print(message, flush=True)
            self._last_progress_print_at = now
            self._last_progress_print_index = current

    #######################################################
    def clear_progress_display(self, context):
        try:
            context.workspace.status_text_set(None)
        except Exception:
            pass

        try:
            if context.area is not None:
                context.area.header_text_set(None)
        except Exception:
            pass

    #######################################################
    def suspend_real_time_scene_updates(self):
        if self.settings is None:
            return

        self._previous_real_time_update = bool(
            getattr(self.settings, "real_time_update", False)
        )
        if self._previous_real_time_update:
            self.settings.real_time_update = False

    #######################################################
    def finalize_scene_state(self, context, detail):
        if self._scene_state_finalized:
            return

        self.update_progress_display(
            context,
            detail=detail,
            force_console=True,
        )

        started_at = time.perf_counter()
        State.update_scene(context.scene)
        context.view_layer.update()
        finalize_duration = max(
            0.0,
            time.perf_counter() - started_at,
        )
        _MAP_IMPORT_TIMING_HISTORY["finalize"].append(
            finalize_duration
        )
        self._scene_state_finalized = True

    #######################################################
    def restore_real_time_scene_updates(self):
        if self.settings is None:
            return
        if self._previous_real_time_update is None:
            return

        self.settings.real_time_update = bool(
            self._previous_real_time_update
        )
        self._previous_real_time_update = None

    #######################################################
    def stamp_map_properties(
        self,
        obj,
        inst,
        effective_interior_id=None,
        source_section=None,
    ):
        ide_data = get_instance_model_data(inst, self._object_data)
        if ide_data is None:
            return

        model_name = getattr(ide_data, "modelName", obj.name.split('.')[0])
        txd_name = getattr(ide_data, "txdName", obj.get("TXD_Name", ""))
        source_interior_id = get_instance_interior_id(inst)

        if effective_interior_id is None:
            effective_interior_id = self.get_effective_interior_id(
                inst,
                ide_data,
            )

        obj["IDE_ID"] = int(inst.id) if str(inst.id).lstrip('-').isdigit() else inst.id
        obj["DFF_Name"] = str(model_name)
        obj["TXD_Name"] = str(txd_name)
        obj["IPL_Source_Interior"] = source_interior_id
        obj["IPL_Source_Role"] = str(self._map_section_role)
        if source_section is not None:
            obj["IPL_Source_Section"] = str(source_section)
        obj["Interior"] = int(effective_interior_id)

        pawn_world_id = int(effective_interior_id)
        if (
            getattr(self.settings, "optimize_for_samp", False)
            and self._map_section_role == "auxiliary"
        ):
            pawn_world_id = get_lcs_auxiliary_world_id(
                self._map_section_path
            )

        obj["Pawn_World_ID"] = pawn_world_id
        obj["Pawn_Interior_ID"] = 0
        obj["SAMP_Optimized"] = bool(
            getattr(self.settings, "optimize_for_samp", False)
        )

        position, quaternion, scale = get_instance_transform_values(inst)
        obj["IPL_Position_X"] = position[0]
        obj["IPL_Position_Y"] = position[1]
        obj["IPL_Position_Z"] = position[2]
        obj["IPL_Rotation_X"] = quaternion[0]
        obj["IPL_Rotation_Y"] = quaternion[1]
        obj["IPL_Rotation_Z"] = quaternion[2]
        obj["IPL_Rotation_W"] = quaternion[3]
        obj["IPL_Scale_X"] = scale[0]
        obj["IPL_Scale_Y"] = scale[1]
        obj["IPL_Scale_Z"] = scale[2]
        if hasattr(inst, "lod"):
            obj["LODIndex"] = int(inst.lod) if str(inst.lod).lstrip('-').isdigit() else inst.lod

        if hasattr(ide_data, "drawDistance"):
            obj["DrawDistance"] = float(ide_data.drawDistance)
        if hasattr(ide_data, "flags"):
            obj["IDE_Flags"] = ide_data.flags

        if hasattr(obj, "ide"):
            obj.ide.obj_id = str(inst.id)
            obj.ide.model_name = str(model_name)
            obj.ide.txd_name = str(txd_name)
            obj.ide.flags = str(getattr(ide_data, "flags", obj.get("IDE_Flags", 0)))

            if hasattr(ide_data, "drawDistance"):
                obj.ide.draw_distance = str(ide_data.drawDistance)
            if hasattr(ide_data, "drawDistance1"):
                obj.ide.draw_distance1 = str(ide_data.drawDistance1)
            if hasattr(ide_data, "drawDistance2"):
                obj.ide.draw_distance2 = str(ide_data.drawDistance2)
            if hasattr(ide_data, "drawDistance3"):
                obj.ide.draw_distance3 = str(ide_data.drawDistance3)

            if hasattr(ide_data, "timeOn"):
                obj.ide.obj_type = 'tobj'
                obj.ide.time_on = str(ide_data.timeOn)
                obj.ide.time_off = str(getattr(ide_data, "timeOff", 24))
            else:
                obj.ide.obj_type = 'objs'

        if hasattr(obj, "ipl"):
            if hasattr(inst, "interior"):
                obj.ipl.interior = str(effective_interior_id)
            if hasattr(inst, "lod"):
                obj.ipl.lod = str(inst.lod)

        if hasattr(obj, "dff_map"):
            props = obj.dff_map
            props.ipl_section = "inst"
            try:
                props.object_id = int(inst.id)
            except Exception:
                props.object_id = 0
            props.model_name = str(model_name)
            props.interior = int(effective_interior_id)
            props.lod = int(getattr(inst, "lod", -1)) if str(getattr(inst, "lod", -1)).lstrip('-').isdigit() else -1
            props.ide_section = "tobj" if hasattr(ide_data, "timeOn") else ("anim" if hasattr(ide_data, "animName") else "objs")
            try:
                props.ide_object_id = int(inst.id)
            except Exception:
                props.ide_object_id = 0
            props.ide_model_name = str(model_name)
            props.ide_txd_name = str(txd_name)
            flags_value = getattr(ide_data, "flags", obj.get("IDE_Flags", 0))
            props.ide_flags = int(flags_value) if str(flags_value).lstrip('-').isdigit() else 0
            if hasattr(ide_data, "drawDistance"):
                props.ide_draw1 = float(ide_data.drawDistance)
            if hasattr(ide_data, "drawDistance1"):
                props.ide_draw1 = float(ide_data.drawDistance1)
            if hasattr(ide_data, "drawDistance2"):
                props.ide_draw2 = float(ide_data.drawDistance2)
            if hasattr(ide_data, "drawDistance3"):
                props.ide_draw3 = float(ide_data.drawDistance3)
            if hasattr(ide_data, "timeOn"):
                props.ide_time_on = int(ide_data.timeOn)
                props.ide_time_off = int(getattr(ide_data, "timeOff", 24))
            if hasattr(ide_data, "animName"):
                props.ide_anim = str(ide_data.animName)
            if not props.pawn_model_name:
                props.pawn_model_name = str(model_name)
            if not props.pawn_txd_name:
                props.pawn_txd_name = str(txd_name)

    #######################################################
    def stamp_2dfx_source_properties(self, obj, inst):
        ide_data = get_instance_model_data(inst, self._object_data)
        if ide_data is None:
            return

        model_name = getattr(ide_data, "modelName", obj.get("DFF_Name", ""))
        txd_name = getattr(ide_data, "txdName", obj.get("TXD_Name", ""))

        obj["demonff_2dfx_source_dff"] = "%s.dff" % model_name
        obj["demonff_2dfx_source_model"] = str(model_name)
        obj["demonff_2dfx_source_model_key"] = str(model_name)
        obj["DFF_Name"] = str(model_name)
        obj["TXD_Name"] = str(txd_name)
        obj["IDE_ID"] = int(inst.id) if str(inst.id).lstrip('-').isdigit() else inst.id

    #######################################################
    def copy_object_id_properties(self, source_obj, target_obj):
        for key in source_obj.keys():
            try:
                target_obj[key] = source_obj[key]
            except Exception:
                pass

    #######################################################
    def get_effective_interior_id(self, inst, ide_data=None):
        source_interior_id = get_instance_interior_id(inst)

        if not getattr(self.settings, "optimize_for_samp", False):
            return source_interior_id

        if source_interior_id == 0:
            return 0

        if self._preserve_source_interiors:
            return source_interior_id

        return 0

    #######################################################
    def configure_interior_layout(self):
        self._preserve_source_interiors = (
            is_explicit_interior_map_section(
                self._map_section_path,
                self._object_instances,
            )
        )

        source_counts = Counter(
            get_instance_interior_id(inst)
            for inst in self._object_instances
        )
        effective_counts = Counter(
            self.get_effective_interior_id(
                inst,
                get_instance_model_data(inst, self._object_data),
            )
            for inst in self._object_instances
        )

        if 0 in effective_counts:
            self._visible_interior = 0
        elif effective_counts:
            self._visible_interior = effective_counts.most_common(1)[0][0]
        else:
            self._visible_interior = 0

        self._interior_collections = {}
        self._model_collections = {}

        if source_counts:
            source_summary = ", ".join(
                "%d=%d" % (interior_id, count)
                for interior_id, count in sorted(source_counts.items())
            )
            effective_summary = ", ".join(
                "%d=%d" % (interior_id, count)
                for interior_id, count in sorted(effective_counts.items())
            )

            if getattr(self.settings, "optimize_for_samp", False):
                print(
                    "Map worlds: source %s; import %s"
                    % (source_summary, effective_summary)
                )
            else:
                print(
                    "Map interior layers: %s; visible layer: %d"
                    % (source_summary, self._visible_interior)
                )

    #######################################################
    @staticmethod
    def normalize_ipl_source_name(value):
        name = os.path.basename(str(value or "").replace("\\", "/"))
        return name.strip().lower()

    #######################################################
    @staticmethod
    def scene_contains_ipl_source(source_name):
        normalized = Map_Import_Operator.normalize_ipl_source_name(source_name)
        if not normalized:
            return False

        for collection in bpy.data.collections:
            sources = str(collection.get("DemonFF_IPL_Sources", ""))
            for source in sources.split(";"):
                if (
                    Map_Import_Operator.normalize_ipl_source_name(source)
                    == normalized
                ):
                    return True

            if (
                Map_Import_Operator.normalize_ipl_source_name(collection.name)
                == normalized
            ):
                return True

        return False

    #######################################################
    def should_load_lcs_overview_companion(self, map_section):
        if self.settings.game_version_dropdown != "LCS":
            return False
        if get_lcs_ipl_role(map_section) != "runtime":
            return False
        if not getattr(self.settings, "optimize_for_samp", False):
            return False
        if self.settings.use_custom_map_section or self.settings.use_binary_ipl:
            return False

        section_name = get_map_section_basename(map_section)
        if section_name not in {"commer", "suburb", "indust"}:
            return False

        return not Map_Import_Operator.scene_contains_ipl_source(
            "overview.ipl"
        )

    #######################################################
    def get_instance_source_section(self, instance_index):
        if self._instance_source_sections:
            if 0 <= instance_index < len(self._instance_source_sections):
                return self._instance_source_sections[instance_index]
        return os.path.basename(self._map_section_path)

    #######################################################
    def stamp_instance_source_properties(
        self,
        obj,
        inst,
        instance_index,
        source_section,
        model_name,
    ):
        obj["IPL_Instance_Index"] = int(instance_index)
        obj["IPL_Source_Section"] = str(source_section)
        obj["IPL_Source_Role"] = str(self._map_section_role)
        obj["IPL_Source_Model"] = str(model_name)
        obj["IPL_Source_ID"] = str(getattr(inst, "id", ""))

        position, quaternion, scale = get_instance_transform_values(inst)
        obj["IPL_Source_Position"] = list(position)
        obj["IPL_Source_Quaternion_XYZW"] = list(quaternion)
        obj["IPL_Source_Scale"] = list(scale)

    #######################################################
    def get_interior_collection(self, interior_id):
        collection = self._interior_collections.get(interior_id)
        if collection is not None:
            return collection

        if getattr(self.settings, "optimize_for_samp", False):
            if self._map_section_role == "auxiliary":
                world_id = get_lcs_auxiliary_world_id(
                    self._map_section_path
                )
                section_name = get_map_section_basename(
                    self._map_section_path
                )
                name = "SAMP Auxiliary World %d (%s)" % (
                    world_id,
                    section_name,
                )
            elif interior_id == 0:
                name = "SAMP World 0 (Exterior)"
            else:
                name = "SAMP World %d (Interior)" % interior_id
        elif self._map_section_role == "auxiliary":
            name = "Auxiliary Source Coordinates"
        elif interior_id == 0:
            name = "Interior 0 (Exterior)"
        else:
            name = "Interior %d" % interior_id

        collection = bpy.data.collections.new(name)
        self._ipl_collection.children.link(collection)

        collection.hide_viewport = False
        collection.hide_render = False

        self._interior_collections[interior_id] = collection
        return collection

    #######################################################
    def get_model_collection(
        self,
        context,
        model_cache_key,
        model_name,
        interior_id,
        imported_collection=None,
    ):
        collection_key = (model_cache_key, interior_id)
        collection = self._model_collections.get(collection_key)
        if collection is not None:
            return collection

        interior_collection = self.get_interior_collection(interior_id)

        if imported_collection is None:
            if interior_id == 0:
                collection_name = "%s.dff" % model_name
            else:
                collection_name = "%s.dff [Interior %d]" % (
                    model_name,
                    interior_id,
                )
            collection = bpy.data.collections.new(collection_name)
        else:
            collection = imported_collection
            if interior_id != 0:
                collection.name = "%s.dff [Interior %d]" % (
                    model_name,
                    interior_id,
                )

            try:
                context.scene.collection.children.unlink(collection)
            except RuntimeError:
                pass

        interior_collection.children.link(collection)
        self._model_collections[collection_key] = collection
        return collection

    #######################################################
    def get_pristine_import_local_matrix(
        self,
        importer,
        obj,
        object_set,
    ):
        if obj.dff.type == "OBJ" and bool(
            getattr(obj.dff, "is_frame", False)
        ):
            try:
                frame_index = int(obj.dff.frame_index)
                if 0 <= frame_index < len(importer.dff.frame_list):
                    frame = importer.dff.frame_list[frame_index]
                    return dff_importer.get_frame_local_matrix(
                        frame
                    ).copy()
            except Exception:
                pass

        if obj.parent in object_set:
            return obj.matrix_local.copy()

        return obj.matrix_basis.copy()

    #######################################################
    def build_model_cache_entry(
        self,
        objects,
        root_source_matrices,
        source_local_matrices,
    ):
        object_list = list(objects)
        object_set = set(object_list)
        parent_map = {}
        local_matrices = {}

        for obj in object_list:
            parent = obj.parent if obj.parent in object_set else None
            parent_map[obj] = parent

            source_matrix = source_local_matrices.get(obj)
            if source_matrix is not None:
                local_matrices[obj] = source_matrix.copy()
            elif parent is not None:
                local_matrices[obj] = obj.matrix_local.copy()
            else:
                local_matrices[obj] = obj.matrix_basis.copy()

        roots = [
            obj
            for obj in object_list
            if obj.dff.type == "OBJ"
            and parent_map[obj] is None
        ]

        # Map DFF roots define the model origin. Their frame matrices are
        # authoring/container transforms and must not be composed with the IPL
        # placement. Doing so applies the root offset, rotation or scale a
        # second time and is what displaced generic object_L0 roots,
        # plane_chassis and several large ramp/bridge meshes.
        #
        # Descendant frame matrices remain untouched. This matches the map
        # placement model used by the game: IPL transform at the model root,
        # then the DFF child hierarchy below it.
        original_root_local_matrices = {}
        for root in roots:
            original_root_local_matrices[root] = local_matrices[root].copy()
            root["DFF_Original_Root_Matrix"] = [
                float(local_matrices[root][row][column])
                for row in range(4)
                for column in range(4)
            ]
            local_matrices[root] = Matrix.Identity(4)

        world_matrices = {}
        object_depths = {}

        def calculate_world_matrix(obj, visiting=None):
            if obj in world_matrices:
                return world_matrices[obj]

            if visiting is None:
                visiting = set()
            if obj in visiting:
                world_matrices[obj] = local_matrices[obj].copy()
                object_depths[obj] = 0
                return world_matrices[obj]

            visiting.add(obj)
            parent = parent_map[obj]
            if parent is None:
                world_matrix = local_matrices[obj].copy()
                depth = 0
            else:
                parent_world = calculate_world_matrix(parent, visiting)
                world_matrix = parent_world @ local_matrices[obj]
                depth = object_depths[parent] + 1

            visiting.remove(obj)
            world_matrices[obj] = world_matrix
            object_depths[obj] = depth
            return world_matrix

        for obj in object_list:
            calculate_world_matrix(obj)

        return {
            "objects": object_list,
            "roots": roots,
            "parents": parent_map,
            "root_source_matrices": {
                obj: matrix.copy()
                for obj, matrix in root_source_matrices.items()
            },
            "original_root_local_matrices": original_root_local_matrices,
            "local_matrices": local_matrices,
            "world_matrices": world_matrices,
            "depths": object_depths,
        }

    #######################################################
    @staticmethod
    def normalize_generic_dff_frame_names(
        collection_objects,
        root_objects,
        model_name,
    ):
        generic_pattern = re.compile(
            r"^(?:object|mesh|unnamed[_ ]frame)(?:[_ .-]*l(\d+))?(?:\.\d{3})?$",
            re.IGNORECASE,
        )

        object_set = set(collection_objects)
        root_set = set(root_objects)
        used_names = {obj.name for obj in bpy.data.objects}

        def unique_name(base_name):
            if base_name not in used_names:
                used_names.add(base_name)
                return base_name

            suffix = 1
            while True:
                candidate = "%s.%03d" % (base_name, suffix)
                if candidate not in used_names:
                    used_names.add(candidate)
                    return candidate
                suffix += 1

        for obj in collection_objects:
            match = generic_pattern.match(str(obj.name).strip())
            if match is None:
                continue

            original_name = str(obj.name)
            lod_level = match.group(1)

            if obj in root_set:
                replacement_name = str(model_name)
            elif lod_level is not None:
                replacement_name = "%s_L%s" % (model_name, lod_level)
            else:
                replacement_name = "%s_Frame" % model_name

            obj["DFF_Original_Frame_Name"] = original_name
            obj.name = unique_name(replacement_name)

            if obj.data is not None and hasattr(obj.data, "name"):
                data_name = str(obj.data.name)
                if generic_pattern.match(data_name):
                    obj.data.name = obj.name

    #######################################################
    def duplicate_cached_model(self, cache_entry, target_collection):
        source_objects = cache_entry["objects"]
        new_objects = {}

        for source_obj in source_objects:
            new_obj = source_obj.copy()
            new_obj.parent = None
            new_obj.matrix_parent_inverse = Matrix.Identity(4)
            target_collection.objects.link(new_obj)
            new_objects[source_obj] = new_obj

        ordered_sources = sorted(
            source_objects,
            key=lambda obj: cache_entry["depths"][obj],
        )

        for source_obj in ordered_sources:
            new_obj = new_objects[source_obj]
            source_parent = cache_entry["parents"][source_obj]
            source_local_matrix = cache_entry[
                "local_matrices"
            ][source_obj].copy()

            if source_parent is not None:
                new_obj.parent = new_objects[source_parent]
                new_obj.parent_type = source_obj.parent_type
                new_obj.parent_bone = source_obj.parent_bone
                new_obj.matrix_parent_inverse = Matrix.Identity(4)
                new_obj.matrix_local = source_local_matrix
            else:
                new_obj.parent = None
                new_obj.matrix_parent_inverse = Matrix.Identity(4)
                new_obj.matrix_basis = source_local_matrix

        return new_objects

    #######################################################
    def place_model_hierarchy(
        self,
        cache_entry,
        object_map,
        inst,
    ):
        instance_matrix = build_instance_matrix(inst)
        ordered_sources = sorted(
            cache_entry["objects"],
            key=lambda obj: cache_entry["depths"][obj],
        )

        # Reapply exact canonical local matrices first. Child objects must not
        # receive the IPL matrix independently; doing that asks Blender to
        # decompose an already composed child world matrix back through its
        # parent, which can corrupt duplicates and non-uniformly scaled models.
        for source_obj in ordered_sources:
            target_obj = object_map[source_obj]
            source_parent = cache_entry["parents"][source_obj]
            source_local = cache_entry["local_matrices"][source_obj].copy()

            target_obj.matrix_parent_inverse = Matrix.Identity(4)
            if source_parent is None:
                target_obj.parent = None
                target_obj.matrix_basis = source_local
            else:
                target_obj.parent = object_map[source_parent]
                target_obj.parent_type = source_obj.parent_type
                target_obj.parent_bone = source_obj.parent_bone
                target_obj.matrix_local = source_local

        # Place only hierarchy roots. All descendants inherit the placement
        # through their exact DFF parent-relative matrices. This keeps models
        # such as plane_chassis, railtrax_straight and object_L0 ramp children
        # from receiving a second or decomposed placement transform.
        for source_obj in ordered_sources:
            if cache_entry["parents"][source_obj] is not None:
                continue

            target_obj = object_map[source_obj]
            source_world = cache_entry["world_matrices"][source_obj]
            final_world = instance_matrix @ source_world

            if not all(
                math.isfinite(final_world[row][column])
                for row in range(4)
                for column in range(4)
            ):
                raise ValueError(
                    "Composed IPL/DFF hierarchy matrix is non-finite"
                )

            target_obj.matrix_world = final_world

    #######################################################
    def import_instance_collision(
        self,
        model_name,
        target_collection,
        inst,
    ):
        if not self.settings.load_collisions:
            return

        source_objects = getattr(self._collision_collection, "all_objects", [])
        suffix = "%s.ColMesh" % model_name

        for source_obj in source_objects:
            if source_obj.dff.type != "COL":
                continue
            if not source_obj.name.endswith(suffix):
                continue

            new_obj = source_obj.copy()
            new_obj.data = source_obj.data
            target_collection.objects.link(new_obj)

            source_matrix = source_obj.matrix_basis.copy()
            self.apply_transformation_to_object(
                new_obj,
                inst,
                source_matrix,
            )
            hide_object(new_obj)

    #######################################################
    def import_object(self, context):

        if self._inst_index > len(self._object_instances) - 1:
            self._calcs_done = True
            return "finished"

        instance_index = self._inst_index
        inst = self._object_instances[instance_index]
        source_section = self.get_instance_source_section(instance_index)
        self._inst_index += 1
        operation_started_at = time.perf_counter()

        if self.settings.skip_lod and is_lod_instance(
            inst,
            self._object_data,
        ):
            self._skipped_lods += 1
            return "skipped_lod"

        ide_data = get_instance_model_data(inst, self._object_data)
        if ide_data is None:
            self._missing_ide_entries += 1
            return "missing_ide"

        model = str(ide_data.modelName)
        txd = str(ide_data.txdName)
        interior_id = self.get_effective_interior_id(inst, ide_data)
        model_cache_key = get_instance_cache_key(inst, ide_data)
        cache_entry = self._model_cache.get(model_cache_key)

        if cache_entry is not None:
            target_collection = self.get_model_collection(
                context,
                model_cache_key,
                model,
                interior_id,
            )
            new_objects = self.duplicate_cached_model(
                cache_entry,
                target_collection,
            )

            self.place_model_hierarchy(
                cache_entry,
                new_objects,
                inst,
            )

            for source_root in cache_entry["roots"]:
                new_root = new_objects[source_root]
                self.stamp_map_properties(
                    new_root,
                    inst,
                    interior_id,
                    source_section,
                )

            for source_obj, new_obj in new_objects.items():
                self.stamp_instance_source_properties(
                    new_obj,
                    inst,
                    instance_index,
                    source_section,
                    model,
                )
                if source_obj.dff.type == "2DFX":
                    self.stamp_2dfx_source_properties(new_obj, inst)

            self._cache_hits += 1
            import_result = "cache"

        else:
            dff_path = self._dff_paths.get(model.lower())
            if dff_path is None:
                self._missing_models += 1
                return "missing_dff"

            try:
                model_file_size = os.path.getsize(dff_path)
            except OSError:
                model_file_size = 0

            self.update_progress_display(
                context,
                detail="loading %s.dff" % model,
                force_console=True,
            )

            importer = dff_importer.import_dff(
                {
                    "file_name": dff_path,
                    "load_txd": self.settings.load_txd,
                    "txd_filename": "%s.txd" % txd,
                    "skip_mipmaps": True,
                    "txd_pack": self.settings.txd_pack,
                    "image_ext": "PNG" if self.settings.load_txd else "",
                    "connect_bones": False,
                    "use_mat_split": self.settings.read_mat_split,
                    "remove_doubles": False,
                    "create_backfaces": self.settings.create_backfaces,
                    "group_materials": True,
                    "import_normals": True,
                    "materials_naming": "DEF",
                    "defer_scene_update": True,
                }
            )

            collection_objects = list(importer.current_collection.objects)
            object_set = set(collection_objects)
            root_objects = [
                obj
                for obj in collection_objects
                if obj.dff.type == "OBJ"
                and (obj.parent is None or obj.parent not in object_set)
            ]

            self.normalize_generic_dff_frame_names(
                collection_objects,
                root_objects,
                model,
            )

            source_local_matrices = {}
            for imported_obj in collection_objects:
                source_local_matrices[imported_obj] = (
                    self.get_pristine_import_local_matrix(
                        importer,
                        imported_obj,
                        object_set,
                    )
                )

            # Rebuild the pristine DFF hierarchy before applying any IPL
            # placement. The first placement and every cached placement now
            # use the same parent-relative source matrices.
            for imported_obj in collection_objects:
                source_local_matrix = source_local_matrices[imported_obj]
                imported_obj.matrix_parent_inverse = Matrix.Identity(4)
                if imported_obj.parent in object_set:
                    imported_obj.matrix_local = source_local_matrix.copy()
                else:
                    imported_obj.matrix_basis = source_local_matrix.copy()

            text_effects = self._effects_2dfx.get(str(inst.id), [])
            if root_objects and text_effects:
                existing_text_effects = [
                    obj
                    for obj in collection_objects
                    if bool(obj.get("demonff_text_ide_2dfx", False))
                ]
                if not existing_text_effects:
                    created_effects = import_text_ide_2dfx(
                        importer,
                        text_effects,
                        root_objects[0],
                        inst,
                    )
                    collection_objects.extend(created_effects)
                    self._imported_2dfx += len(created_effects)

            if root_objects:
                root_obj = root_objects[0]
                for obj in collection_objects:
                    if obj.dff.type != "2DFX":
                        continue

                    self.stamp_2dfx_source_properties(obj, inst)
                    if obj.parent is None:
                        effect_local_matrix = obj.matrix_basis.copy()
                        obj.parent = root_obj
                        obj.matrix_parent_inverse = Matrix.Identity(4)
                        obj.matrix_local = effect_local_matrix
                        source_local_matrices[obj] = (
                            effect_local_matrix.copy()
                        )

            # Include effects created after the initial DFF hierarchy scan.
            object_set = set(collection_objects)
            for imported_obj in collection_objects:
                if imported_obj in source_local_matrices:
                    continue
                source_local_matrices[imported_obj] = (
                    self.get_pristine_import_local_matrix(
                        importer,
                        imported_obj,
                        object_set,
                    )
                )

            root_source_matrices = {
                root_obj: source_local_matrices[root_obj].copy()
                for root_obj in root_objects
            }

            cache_entry = self.build_model_cache_entry(
                collection_objects,
                root_source_matrices,
                source_local_matrices,
            )

            self.place_model_hierarchy(
                cache_entry,
                {
                    imported_obj: imported_obj
                    for imported_obj in collection_objects
                },
                inst,
            )

            for root_obj in root_objects:
                self.stamp_map_properties(
                    root_obj,
                    inst,
                    interior_id,
                    source_section,
                )

            target_collection = self.get_model_collection(
                context,
                model_cache_key,
                model,
                interior_id,
                importer.current_collection,
            )
            target_collection.hide_viewport = False
            target_collection.hide_render = False

            for imported_obj in collection_objects:
                self.stamp_instance_source_properties(
                    imported_obj,
                    inst,
                    instance_index,
                    source_section,
                    model,
                )

            self._model_cache[model_cache_key] = cache_entry
            self._new_models += 1
            import_result = "new_model"

        self.import_instance_collision(
            model,
            target_collection,
            inst,
        )

        operation_duration = max(
            0.0,
            time.perf_counter() - operation_started_at,
        )
        if import_result == "new_model":
            self._new_model_durations.append(operation_duration)
            _MAP_IMPORT_TIMING_HISTORY["new_model"].append(
                operation_duration
            )
            self._loaded_model_bytes += model_file_size
        elif import_result == "cache":
            self._cache_durations.append(operation_duration)
            _MAP_IMPORT_TIMING_HISTORY["cache"].append(
                operation_duration
            )

        self._imported_instances += 1
        return import_result

    #######################################################
    # Generates a non-conflicting ID
    def generate_non_conflicting_id(self):
        existing_ids = {inst.id for inst in self._object_instances}
        while True:
            new_id = random.randint(100000, 999999)  # Generate a random 6-digit ID
            if new_id not in existing_ids:
                return new_id
            
    #######################################################
    def modal(self, context, event):

        if event.type in {'ESC'}:
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'TIMER' and not self._updating:
            self._updating = True
            num = 0.0

            try:
                if self.settings.load_collisions and self._check_collisions:
                    prefixes = set()
                    for inst in self._object_instances:
                        objdata = get_instance_model_data(
                            inst,
                            self._object_data,
                        )
                        if objdata is None or not hasattr(objdata, 'filename'):
                            continue
                        prefixes.add(
                            objdata.filename.split('/')[-1][:-4].lower()
                        )

                    for prefix in prefixes:
                        for filename in self._col_files_all:
                            if not filename.startswith(prefix):
                                continue
                            if bpy.data.collections.get(filename):
                                continue
                            if filename not in self._col_files:
                                self._col_files.append(filename)

                    self._col_files.sort()
                    self._collision_total = len(self._col_files)
                    self._check_collisions = False
                    if self._collision_total:
                        self.update_progress_display(
                            context,
                            detail="preparing %d collision files" % self._collision_total,
                            force_console=True,
                        )

                elif len(self._col_files) > 0:
                    filename = self._col_files[self._col_index]
                    self.update_progress_display(
                        context,
                        detail="collision %d/%d: %s" % (
                            self._col_index + 1,
                            self._collision_total,
                            filename,
                        ),
                        force_console=True,
                    )
                    self._col_index += 1
                    if self._col_index >= len(self._col_files):
                        self._col_files.clear()

                    collection = bpy.data.collections.new(filename)
                    self._collision_collection.children.link(collection)
                    col_list = col_importer.import_col_file(
                        os.path.join(self.settings.dff_folder, filename),
                        filename,
                    )
                    for col_collection in col_list:
                        try:
                            context.scene.collection.children.unlink(
                                col_collection
                            )
                        except RuntimeError:
                            pass
                        collection.children.link(col_collection)

                    collection.hide_viewport = True
                    collection.hide_render = True
                    num = (
                        float(self._col_index) / float(self._collision_total)
                    ) if self._collision_total else 1.0

                else:
                    started = time.perf_counter()
                    processed = 0
                    minimum_batch = 8
                    maximum_batch = 128
                    time_budget = 0.04

                    while processed < maximum_batch:
                        if self._calcs_done:
                            break

                        import_result = None
                        try:
                            import_result = self.import_object(context)
                        except Exception as error:
                            print(
                                "Can't import map model at instance index %d: %s"
                                % (self._inst_index - 1, error),
                                flush=True,
                            )
                            traceback.print_exc()

                        processed += 1

                        # A newly parsed DFF can take a noticeable amount of time.
                        # Yield immediately afterward so Blender redraws and handles
                        # window events before loading another unique model.
                        if import_result == "new_model":
                            break

                        if (
                            processed >= minimum_batch
                            and time.perf_counter() - started >= time_budget
                        ):
                            break

                    num = (
                        float(self._inst_index)
                        / float(len(self._object_instances))
                    ) if self._object_instances else 1.0
                    self.update_progress_display(
                        context,
                        detail="placing map objects",
                    )

                if self.settings.load_collisions and not self._calcs_done and self._col_files:
                    context.window_manager.progress_update(num * 100.0)

            finally:
                self._updating = False

        if self._calcs_done:
            self.finish_import(context)
            self.cancel(context)
            return {'FINISHED'}

        return {'PASS_THROUGH'}

    #######################################################
    def execute(self, context):


        self.settings = context.scene.dff
        self._previous_real_time_update = None
        self._scene_state_finalized = False
        self._model_cache = {}
        self._interior_collections = {}
        self._model_collections = {}
        self._instance_source_sections = []
        self._dff_paths = {}
        self._col_files_all = set()
        self._col_files = []
        self._col_index = 0
        self._check_collisions = True
        self._calcs_done = False
        self._inst_index = 0
        self._imported_instances = 0
        self._cache_hits = 0
        self._new_models = 0
        self._missing_models = 0
        self._missing_ide_entries = 0
        self._skipped_lods = 0
        self._imported_2dfx = 0
        self._import_started_at = time.perf_counter()
        self._parent_collection_hidden = False
        self._collision_total = 0
        self._last_progress_print_at = 0.0
        self._last_progress_print_index = -1
        self._current_progress_detail = "starting"
        self._planned_importable_instances = 0
        self._planned_unique_models = 0
        self._planned_cache_placements = 0
        self._planned_missing_models = 0
        self._planned_missing_ide_entries = 0
        self._planned_skipped_lods = 0
        self._planned_model_bytes = 0
        self._loaded_model_bytes = 0
        self._new_model_durations = deque(maxlen=64)
        self._cache_durations = deque(maxlen=512)

        if self.settings.use_custom_map_section:
            map_section = self.settings.custom_ipl_path
        else:
            map_section = self.settings.map_sections

        self._map_section_path = str(map_section)
        if self.settings.game_version_dropdown == "LCS":
            self._map_section_role = get_lcs_ipl_role(map_section)
        else:
            self._map_section_role = "runtime"

        # Get all the necessary IDE and IPL data
        map_data = map_utilites.MapDataUtility.getMapData(
            self.settings.game_version_dropdown,
            self.settings.game_root,
            map_section,
            self.settings.use_custom_map_section)

        if self.settings.use_binary_ipl or self.settings.use_custom_map_section:
            ide_paths = [entry.name for entry in self.settings.ide_paths if entry.name.strip()]
            if not ide_paths:
                self.report({'ERROR'}, "No IDEs specified for import.")
                self.restore_real_time_scene_updates()
                return {'CANCELLED'}
        else:
            ide_paths = [] 

        # Get all the necessary IDE and IPL data
        if self.settings.use_binary_ipl:
            ide_paths = [entry.name for entry in self.settings.ide_paths if entry.name.strip()]
            if not ide_paths:
                self.report({'ERROR'}, "No IDEs specified for Binary IPL import.")
                self.restore_real_time_scene_updates()
                return {'CANCELLED'}

            map_data = map_utilites.MapDataUtility.getBinaryMapData(
                self.settings.game_version_dropdown,
                self.filepath,
                ide_paths
            )
        elif self.settings.use_custom_map_section:
            custom_ide_paths = [entry.name for entry in self.settings.ide_paths if entry.name.strip()]
            if custom_ide_paths:
                map_utilites.MapDataUtility.override_ide_paths(custom_ide_paths)

            map_data = map_utilites.MapDataUtility.getMapData(
                self.settings.game_version_dropdown,
                self.settings.game_root,
                map_section,
                self.settings.use_custom_map_section
            )

        map_utilites.MapDataUtility.forced_ide_paths = None

        main_source_section = os.path.basename(str(map_section))
        self._object_instances = list(map_data['object_instances'])
        self._instance_source_sections = [
            main_source_section
            for _ in self._object_instances
        ]
        self._object_data = map_data['object_data']
        self._effects_2dfx = map_data.get('effects_2dfx', {})

        if self.should_load_lcs_overview_companion(map_section):
            companion_path = "DATA/MAPS/overview.IPL"
            companion_definition = map_utilites.map_data.data[
                self.settings.game_version_dropdown
            ]
            companion_ipl = map_utilites.MapDataUtility.load_ipl_data(
                self.settings.game_root,
                companion_path,
                companion_definition['structures'],
                companion_definition['IPL_aliases'],
            )
            companion_instances = list(companion_ipl.get('inst', []))

            if companion_instances:
                companion_source_section = os.path.basename(companion_path)
                self._object_instances.extend(companion_instances)
                self._instance_source_sections.extend(
                    companion_source_section
                    for _ in companion_instances
                )
                print(
                    "LCS global IPL: added %s (%d placements)"
                    % (
                        companion_source_section,
                        len(companion_instances),
                    ),
                    flush=True,
                )

        # Create collections to organize the scene between geometry and collision
        meshcollname = '%s Meshes' % self.settings.game_version_dropdown
        collcollname = '%s Collisions' % self.settings.game_version_dropdown
        self._mesh_collection = bpy.data.collections.get(meshcollname)
        if not self._mesh_collection:
            self._mesh_collection = bpy.data.collections.new(meshcollname)
            context.scene.collection.children.link(self._mesh_collection)
        self._collision_collection = bpy.data.collections.get(collcollname)
        if not self._collision_collection:
            self._collision_collection = bpy.data.collections.new(collcollname)
            context.scene.collection.children.link(self._collision_collection)

        # Hide Collision collection
        context.view_layer.active_layer_collection = context.view_layer.layer_collection.children[-1]
        context.view_layer.active_layer_collection.hide_viewport = True

        # Create a new collection in Mesh to hold all the subsequent dffs loaded from this map section
        collection_name = os.path.basename(map_section)
        if self._map_section_role == "auxiliary":
            collection_name = "%s [Auxiliary Source]" % collection_name

        self._ipl_collection = bpy.data.collections.new(collection_name)
        self._mesh_collection.children.link(self._ipl_collection)
        self._ipl_collection["DemonFF_IPL_Sources"] = ";".join(
            list(dict.fromkeys(self._instance_source_sections))
        )
        self._ipl_collection["DemonFF_IPL_Role"] = str(
            self._map_section_role
        )
        self._ipl_collection["DemonFF_IPL_Runtime"] = (
            self._map_section_role == "runtime"
        )
        self._ipl_collection["DemonFF_IPL_Auxiliary"] = (
            self._map_section_role == "auxiliary"
        )
        self._ipl_collection.hide_viewport = False
        self._ipl_collection.hide_render = False
        self._parent_collection_hidden = False
        self.configure_interior_layout()
        link_optional_map_entries(context, self._ipl_collection, map_data, self.settings)

        # Index model and collision files once. Avoid repeated filesystem calls
        # for every instance and preserve the actual filename casing.
        with os.scandir(self.settings.dff_folder) as entries:
            for entry in entries:
                if not entry.is_file():
                    continue
                stem, extension = os.path.splitext(entry.name)
                extension = extension.lower()
                if extension == ".dff":
                    self._dff_paths.setdefault(stem.lower(), entry.path)
                elif extension == ".col":
                    self._col_files_all.add(entry.name)

        self.build_import_plan()
        self.suspend_real_time_scene_updates()

        wm = context.window_manager
        wm.progress_begin(0.0, 100.0)

        self._timer = wm.event_timer_add(0.1, window=context.window)
        
        wm.modal_handler_add(self)
        self.update_progress_display(
            context,
            detail=(
                "planned %d unique DFFs and %d cached placements; "
                "press Esc to cancel"
                % (
                    self._planned_unique_models,
                    self._planned_cache_placements,
                )
            ),
            force_console=True,
        )

        return {'RUNNING_MODAL'}
    #######################################################
    def finish_import(self, context):
        if self._ipl_collection is not None and self._parent_collection_hidden:
            self._ipl_collection.hide_viewport = False
            self._ipl_collection.hide_render = False
            self._parent_collection_hidden = False

        self.finalize_scene_state(
            context,
            detail="finalizing frame and atomic data",
        )
        self.restore_real_time_scene_updates()

        self._inst_index = len(self._object_instances)
        self.update_progress_display(
            context,
            detail="complete",
            force_console=True,
        )

        elapsed = max(0.0, time.perf_counter() - self._import_started_at)
        print(
            "Map import complete: %d placed, %d unique models, %d cached "
            "placements, %d 2DFX, %d missing DFF, %d missing IDE, "
            "%d skipped LOD; %.2f seconds"
            % (
                self._imported_instances,
                self._new_models,
                self._cache_hits,
                self._imported_2dfx,
                self._missing_models,
                self._missing_ide_entries,
                self._skipped_lods,
                elapsed,
            ),
            flush=True,
        )
        self.report(
            {'INFO'},
            "Map import complete: %d/%d placements in %.1f seconds"
            % (
                self._imported_instances,
                len(self._object_instances),
                elapsed,
            ),
        )

    #######################################################
    def cancel(self, context):
        if self._ipl_collection is not None and self._parent_collection_hidden:
            self._ipl_collection.hide_viewport = False
            self._ipl_collection.hide_render = False
            self._parent_collection_hidden = False

        if not self._scene_state_finalized and self._imported_instances > 0:
            try:
                self.finalize_scene_state(
                    context,
                    detail="finalizing partial map import",
                )
            except Exception:
                traceback.print_exc()

        self.restore_real_time_scene_updates()
        self.clear_progress_display(context)

        wm = context.window_manager
        wm.progress_end()
        if self._timer is not None:
            wm.event_timer_remove(self._timer)
            self._timer = None
    #######################################################
    @staticmethod
    def apply_transformation_to_object(
        obj,
        inst,
        source_matrix=None,
    ):
        if source_matrix is None:
            source_matrix = Matrix.Identity(4)

        instance_matrix = build_instance_matrix(inst)
        final_matrix = instance_matrix @ source_matrix

        if not all(
            math.isfinite(final_matrix[row][column])
            for row in range(4)
            for column in range(4)
        ):
            raise ValueError("Composed IPL/DFF transform matrix is non-finite")

        if obj.parent is None:
            obj.matrix_basis = final_matrix
        else:
            obj.matrix_world = final_matrix

    #######################################################
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
#######################################################
class Binary_Map_Import_Operator(bpy.types.Operator):
    bl_idname = "scene.binary_import_ipl"
    bl_label = "Import Binary IPL"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    bpy.types.Scene.binary_ipl_path = bpy.props.StringProperty(name="Binary IPL Path")

    _timer = None
    _updating = False
    _calcs_done = False
    _inst_index = 0

    _object_instances = []
    _object_data = []
    _effects_2dfx = {}
    _model_cache = {}
    _col_files_all = set()
    _col_files = []
    _col_index = 0
    _check_collisions = True
    _mesh_collection = None
    _collision_collection = None
    _ipl_collection = None

    settings = None

    #######################################################
    def execute(self, context):
        self.settings = context.scene.dff
        self._model_cache = {}

        # Ask user for IDE paths
        ide_paths = []
        for path in self.settings.ide_paths:
            if path.name.strip():
                ide_paths.append(path.name)


        if not ide_paths:
            self.report({'ERROR'}, "No IDE paths provided in settings.ide_paths")
            return {'CANCELLED'}

        # Load Binary IPL + IDE data
        map_data = map_utilites.MapDataUtility.getBinaryMapData(
            self.settings.game_version_dropdown,
            self.filepath,
            ide_paths
        )

        print("DEBUG: object_data keys →", map_data['object_data'].keys())  
        

        self._object_instances = map_data['object_instances']
        self._object_data = map_data['object_data']
        self._effects_2dfx = map_data.get('effects_2dfx', {})



        # Setup Blender collections
        meshcollname = '%s Meshes' % self.settings.game_version_dropdown
        collcollname = '%s Collisions' % self.settings.game_version_dropdown
        self._mesh_collection = bpy.data.collections.get(meshcollname)
        if not self._mesh_collection:
            self._mesh_collection = bpy.data.collections.new(meshcollname)
            context.scene.collection.children.link(self._mesh_collection)
        self._collision_collection = bpy.data.collections.get(collcollname)
        if not self._collision_collection:
            self._collision_collection = bpy.data.collections.new(collcollname)
            context.scene.collection.children.link(self._collision_collection)

        context.view_layer.active_layer_collection = context.view_layer.layer_collection.children[-1]
        context.view_layer.active_layer_collection.hide_viewport = True

        # Create IPL section container collection
        self._ipl_collection = bpy.data.collections.new(os.path.basename(self.filepath))
        self._mesh_collection.children.link(self._ipl_collection)
        link_optional_map_entries(context, self._ipl_collection, map_data, self.settings)

        # Cache all .col files
        for filename in os.listdir(self.settings.dff_folder):
            if filename.endswith(".col"):
                self._col_files_all.add(filename)

        wm = context.window_manager
        wm.progress_begin(0, 100.0)
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)

        return {'RUNNING_MODAL'}

    #######################################################
    def modal(self, context, event):
        if event.type in {'ESC'}:
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'TIMER' and not self._updating:
            self._updating = True
            num = 0

            if self.settings.load_collisions and self._check_collisions:
                for inst in self._object_instances:
                    id = inst.id
                    objdata = get_instance_model_data(inst, self._object_data)
                    if objdata is None:
                        continue
                    if not hasattr(objdata, 'filename'):
                        continue
                    prefix = objdata.filename.split('/')[-1][:-4].lower()
                    for filename in self._col_files_all:
                        if filename.startswith(prefix):
                            if not bpy.data.collections.get(filename) and filename not in self._col_files:
                                self._col_files.append(filename)
                self._check_collisions = False

            elif len(self._col_files) > 0:
                filename = self._col_files[self._col_index]
                self._col_index += 1
                if self._col_index >= len(self._col_files):
                    self._col_files.clear()
                collection = bpy.data.collections.new(filename)
                self._collision_collection.children.link(collection)
                col_list = col_importer.import_col_file(os.path.join(self.settings.dff_folder, filename), filename)
                for c in col_list:
                    context.scene.collection.children.unlink(c)
                    collection.children.link(c)
                context.view_layer.active_layer_collection = context.view_layer.layer_collection.children[-1]
                context.view_layer.active_layer_collection.hide_viewport = True
                num = (float(self._col_index) / float(len(self._col_files))) if self._col_files else 0

            else:
                num_objects_at_once = max(10, int(0.05 * len(bpy.data.objects)))
                for _ in range(num_objects_at_once):
                    try:
                        self.import_object(context)
                    except:
                        print("Can't import model... skipping")

                num = (float(self._inst_index) / float(len(self._object_instances))) if self._object_instances else 0

            bpy.context.window_manager.progress_update(num)
            context.evaluated_depsgraph_get().update()
            self._updating = False

        if self._calcs_done:
            self.cancel(context)
            return {'FINISHED'}

        return {'PASS_THROUGH'}

    #######################################################
    def import_object(self, context):

        # Are there any IPL entries left to import?
        if self._inst_index > len(self._object_instances) - 1:
            self._calcs_done = True
            return

        # Fetch next inst
        inst = self._object_instances[self._inst_index]
        self._inst_index += 1

        # Skip actual low-detail models, not normal SA instances with lod == -1.
        if self.settings.skip_lod and is_lod_instance(inst, self._object_data):
            return

        # Deleted objects that Rockstar forgot to remove?
        ide_data = get_instance_model_data(inst, self._object_data)
        if ide_data is None:
            return

        model = ide_data.modelName
        txd = ide_data.txdName

        model_cache_key = get_instance_cache_key(inst, ide_data)

        if model_cache_key in self._model_cache:

            # Get model from memory
            new_objects = {}
            model_cache = self._model_cache[model_cache_key]

            cached_objects = [obj for obj in model_cache if obj.dff.type == "OBJ"]
            for obj in cached_objects:
                new_obj = bpy.data.objects.new(model, obj.data)
                new_obj.location = obj.location
                new_obj.rotation_quaternion = obj.rotation_quaternion
                new_obj.scale = obj.scale

                modifier = new_obj.modifiers.new("EdgeSplit", 'EDGE_SPLIT')
                # When added to some objects (empties?), returned modifier is None
                if modifier is not None:
                    modifier.use_edge_angle = False

                if '{}.dff'.format(model) in bpy.data.collections:
                    bpy.data.collections['{}.dff'.format(model)].objects.link(
                        new_obj
                    )
                else:
                    context.collection.objects.link(new_obj)
                new_objects[obj] = new_obj

            # Parenting
            for obj in cached_objects:
                if obj.parent in cached_objects:
                    new_objects[obj].parent = new_objects[obj.parent]

            # Position root object
            for obj in new_objects.values():
                if not obj.parent:
                    Map_Import_Operator.apply_transformation_to_object(
                        obj, inst
                    )
                    Map_Import_Operator.stamp_map_properties(self, obj, inst)

            cached_2dfx = [obj for obj in model_cache if obj.dff.type == "2DFX"]
            for obj in cached_2dfx:
                new_obj = bpy.data.objects.new(obj.name, obj.data)
                new_obj.location = obj.location
                new_obj.rotation_mode = obj.rotation_mode
                new_obj.lock_rotation = obj.lock_rotation
                new_obj.rotation_quaternion = obj.rotation_quaternion
                new_obj.rotation_euler = obj.rotation_euler
                new_obj.scale = obj.scale

                if obj.parent and obj.parent in new_objects:
                    new_obj.parent = new_objects[obj.parent]
                elif cached_objects:
                    root_source = next((cached for cached in cached_objects if not cached.parent), cached_objects[0])
                    new_obj.parent = new_objects[root_source]

                for prop in obj.dff.keys():
                    new_obj.dff[prop] = obj.dff[prop]

                self.copy_object_id_properties(obj, new_obj)
                self.stamp_2dfx_source_properties(new_obj, inst)

                if '{}.dff'.format(model) in bpy.data.collections:
                    bpy.data.collections['{}.dff'.format(model)].objects.link(
                        new_obj
                    )
                else:
                    context.collection.objects.link(new_obj)
                new_objects[obj] = new_obj

            print(str(inst.id) + ' loaded from cache')
        else:

            # Import dff from a file if file exists
            if not os.path.isfile("%s/%s.dff" % (self.settings.dff_folder, model)):
                return
            importer = dff_importer.import_dff(
                {
                    'file_name'      : "%s/%s.dff" % (
                        self.settings.dff_folder, model
                    ),
                    'load_txd'         : self.settings.load_txd,
                    'txd_filename'     : "%s.txd" % txd,
                    'skip_mipmaps'     : True,
                    'txd_pack'         : self.settings.txd_pack,
                    'image_ext'        : 'PNG',
                    'connect_bones'    : False,
                    'use_mat_split'    : self.settings.read_mat_split,
                    'remove_doubles'   : False,
                    'create_backfaces' : self.settings.create_backfaces,
                    'group_materials'  : True,
                    'import_normals'   : True,
                    "materials_naming" : "DEF",
                }
            )

            collection_objects = list(importer.current_collection.objects)
            root_objects = [obj for obj in collection_objects if obj.dff.type == "OBJ" and not obj.parent]

            for obj in root_objects:
                Map_Import_Operator.apply_transformation_to_object(
                    obj, inst
                )
                Map_Import_Operator.stamp_map_properties(self, obj, inst)

            # Set root object as 2DFX parent
            if root_objects:
                for obj in collection_objects:
                    if obj.dff.type == "2DFX":
                        self.stamp_2dfx_source_properties(obj, inst)
                    if obj.dff.type == "2DFX":
                        obj.parent = root_objects[0]

            # Move dff collection to a top collection named for the file it came from
            context.scene.collection.children.unlink(importer.current_collection)
            self._ipl_collection.children.link(importer.current_collection)

            # Save into buffer
            self._model_cache[model_cache_key] = collection_objects
            print(str(inst.id) + ' loaded new')
    
        # Look for collision mesh
        name = self._model_cache[model_cache_key][0].name
        for obj in bpy.data.objects:
            if obj.dff.type == 'COL' and obj.name.endswith("%s.ColMesh" % name):
                new_obj = bpy.data.objects.new(obj.name, obj.data)
                new_obj.dff.type = 'COL'
                new_obj.location = obj.location
                new_obj.rotation_quaternion = obj.rotation_quaternion
                new_obj.scale = obj.scale
                Map_Import_Operator.apply_transformation_to_object(
                    new_obj, inst
                )
                if '{}.dff'.format(name) in bpy.data.collections:
                    bpy.data.collections['{}.dff'.format(name)].objects.link(
                        new_obj
                    )
                hide_object(new_obj)

    #######################################################
    def apply_transformation_to_object(self, obj, inst):
        obj.location.x = float(inst.posX)
        obj.location.y = float(inst.posY)
        obj.location.z = float(inst.posZ)
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion.w = -float(inst.rotW)
        obj.rotation_quaternion.x = float(inst.rotX)
        obj.rotation_quaternion.y = float(inst.rotY)
        obj.rotation_quaternion.z = float(inst.rotZ)

        if hasattr(inst, 'scaleX'):
            obj.scale.x = float(inst.scaleX)
        if hasattr(inst, 'scaleY'):
            obj.scale.y = float(inst.scaleY)
        if hasattr(inst, 'scaleZ'):
            obj.scale.z = float(inst.scaleZ)

    #######################################################
    def cancel(self, context):
        wm = context.window_manager
        wm.progress_end()
        wm.event_timer_remove(self._timer)

    #######################################################
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
#######################################################
def menu_func_import(self, context):
    self.layout.operator(Map_Import_Operator.bl_idname, text="Import IPL")
#######################################################
def menu_func_import_binary(self, context):
    self.layout.operator(Map_Import_Operator.bl_idname, text="Import Binary IPL")
#######################################################
def register():
    bpy.utils.register_class(Map_Import_Operator)
    bpy.utils.register_class(Binary_Map_Import_Operator)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_binary)

def unregister():
    bpy.utils.unregister_class(Map_Import_Operator)
    bpy.utils.unregister_class(Binary_Map_Import_Operator)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_binary)

if __name__ == "__main__":
    register()
