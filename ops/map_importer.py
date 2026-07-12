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
import bpy
import random
import struct
import tempfile

from ..ops import dff_importer, col_importer
from ..gtaLib import map as map_utilites
from .importer_common import (hide_object)
from .ipl.cull_importer import cull_importer
from .ipl.grge_importer import grge_importer
from .ipl.enex_importer import enex_importer


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
            obj.location = (float(record.posX), float(record.posY), float(record.posZ))
            obj.parent = root_object

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

    if created:
        print("Imported %d text IDE 2DFX effect(s) for model %s" % (len(created), records[0].id))

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

    settings = None
    #######################################################
    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene.dff, "import_as_binary")
    #######################################################
    def stamp_map_properties(self, obj, inst):
        ide_data = get_instance_model_data(inst, self._object_data)
        if ide_data is None:
            return

        model_name = getattr(ide_data, "modelName", obj.name.split('.')[0])
        txd_name = getattr(ide_data, "txdName", obj.get("TXD_Name", ""))

        obj["IDE_ID"] = int(inst.id) if str(inst.id).lstrip('-').isdigit() else inst.id
        obj["DFF_Name"] = str(model_name)
        obj["TXD_Name"] = str(txd_name)

        if hasattr(inst, "interior"):
            obj["Interior"] = int(inst.interior) if str(inst.interior).lstrip('-').isdigit() else inst.interior
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
                obj.ipl.interior = str(inst.interior)
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
            props.interior = int(getattr(inst, "interior", 0)) if str(getattr(inst, "interior", 0)).lstrip('-').isdigit() else 0
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
                    self.stamp_map_properties(obj, inst)

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
                self.stamp_map_properties(obj, inst)

            text_effects = self._effects_2dfx.get(str(inst.id), [])
            if root_objects and text_effects:
                existing_text_effects = [
                    obj for obj in collection_objects
                    if bool(obj.get("demonff_text_ide_2dfx", False))
                ]
                if not existing_text_effects:
                    collection_objects.extend(
                        import_text_ide_2dfx(importer, text_effects, root_objects[0], inst)
                    )

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
            num = 0

            # First run through all instances and determine which .col files to load
            if self.settings.load_collisions and self._check_collisions:
                for i in range(len(self._object_instances)):
                    id = self._object_instances[i].id
                    # Deleted objects that Rockstar forgot to remove?
                    objdata = get_instance_model_data(self._object_instances[i], self._object_data)
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

            # Load collision files first if there are any left to load
            elif len(self._col_files) > 0:
                filename = self._col_files[self._col_index]
                self._col_index += 1
                if self._col_index >= len(self._col_files):
                    self._col_files.clear()
                collection = bpy.data.collections.new(filename)
                self._collision_collection.children.link(collection)
                col_list = col_importer.import_col_file(os.path.join(self.settings.dff_folder, filename), filename)
                # Move all collisions to a top collection named for the file they came from
                for c in col_list:
                    context.scene.collection.children.unlink(c)
                    collection.children.link(c)

                # Hide this collection in the viewport (individual collision meshes will be linked and transformed
                # as needed to their respective map sections, this collection is just for export)
                context.view_layer.active_layer_collection = context.view_layer.layer_collection.children[-1]
                context.view_layer.active_layer_collection.hide_viewport = True

                # Update cursor progress indicator if something needs to be loaded
                num = (
                        float(self._col_index) / float(len(self._col_files))
                ) if self._col_files else 0

            else:
                # As the number of objects increases, loading performance starts to get crushed by scene updates, so
                # we try to keep loading at least 5% of the total scene object count on each timer pulse.
                num_objects_at_once = max(10, int(0.05 * len(bpy.data.objects)))

                # Now load the actual objects
                for x in range(num_objects_at_once):
                    try:
                        self.import_object(context)
                    except:
                        print("Can`t import model... skipping")

                # Update cursor progress indicator if something needs to be loaded
                num = (
                    float(self._inst_index) / float(len(self._object_instances))
                ) if self._object_instances else 0

            bpy.context.window_manager.progress_update(num)

            # Update dependency graph
            # in 2.7x it's context.scene.update()
            dg = context.evaluated_depsgraph_get()
            dg.update() 

            self._updating = False

        if self._calcs_done:
            self.cancel(context)
            return {'FINISHED'}

        return {'PASS_THROUGH'}
    #######################################################
    def execute(self, context):


        self.settings = context.scene.dff
        self._model_cache = {}

        if self.settings.use_custom_map_section:
            map_section = self.settings.custom_ipl_path
        else:
            map_section = self.settings.map_sections

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
                return {'CANCELLED'}
        else:
            ide_paths = [] 

        # Get all the necessary IDE and IPL data
        if self.settings.use_binary_ipl:
            ide_paths = [entry.name for entry in self.settings.ide_paths if entry.name.strip()]
            if not ide_paths:
                self.report({'ERROR'}, "No IDEs specified for Binary IPL import.")
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

        self._object_instances = map_data['object_instances']
        self._object_data = map_data['object_data']
        self._effects_2dfx = map_data.get('effects_2dfx', {})

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
        self._ipl_collection = bpy.data.collections.new(collection_name)
        self._mesh_collection.children.link(self._ipl_collection)
        link_optional_map_entries(context, self._ipl_collection, map_data, self.settings)

        # Get a list of the .col files available
        for filename in os.listdir(self.settings.dff_folder):
            if filename.endswith(".col"):
                self._col_files_all.add(filename)

        wm = context.window_manager
        wm.progress_begin(0, 100.0)
        
         # Call the "modal" function every 0.1s
        self._timer = wm.event_timer_add(0.1, window=context.window)
        
        wm.modal_handler_add(self)

        return {'RUNNING_MODAL'}
    #######################################################
    def cancel(self, context):
        wm = context.window_manager
        wm.progress_end()
        wm.event_timer_remove(self._timer)
    #######################################################
    def apply_transformation_to_object(obj, inst):
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
                    objdata = get_instance_model_data(self._object_instances[i], self._object_data)
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
