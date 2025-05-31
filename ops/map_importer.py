# DemonFF - Blender scripts for working with Renderware & R*/SA-MP/open.mp formats in Blender
# 2023 - 2025 SpicyBung

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
        layout.prop(self, "import_as_binary")
    #######################################################
    def import_object(self, context):

        # Are there any IPL entries left to import?
        if self._inst_index > len(self._object_instances) - 1:
            self._calcs_done = True
            return

        # Fetch next inst
        inst = self._object_instances[self._inst_index]
        self._inst_index += 1

        # Skip LODs if user selects this
        if hasattr(inst, 'lod') and int(inst.lod) == -1 and self.settings.skip_lod:
            return

        # Deleted objects that Rockstar forgot to remove?
        if inst.id not in self._object_data:
            return

        model = self._object_data[inst.id].modelName
        txd = self._object_data[inst.id].txdName

        if inst.id in self._model_cache:

            # Get model from memory
            new_objects = {}
            model_cache = self._model_cache[inst.id]

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

            cached_2dfx = [obj for obj in model_cache if obj.dff.type == "2DFX"]
            for obj in cached_2dfx:
                new_obj = bpy.data.objects.new(obj.name, obj.data)
                new_obj.location = obj.location
                new_obj.rotation_mode = obj.rotation_mode
                new_obj.lock_rotation = obj.lock_rotation
                new_obj.rotation_quaternion = obj.rotation_quaternion
                new_obj.rotation_euler = obj.rotation_euler
                new_obj.scale = obj.scale

                if obj.parent:
                    new_obj.parent = new_objects[obj.parent]

                for prop in obj.dff.keys():
                    new_obj.dff[prop] = obj.dff[prop]

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
                    'txd_pack'         : False,
                    'image_ext'        : 'PNG',
                    'connect_bones'    : False,
                    'use_mat_split'    : self.settings.read_mat_split,
                    'remove_doubles'   : True,
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

            # Set root object as 2DFX parent
            if root_objects:
                for obj in collection_objects:
                    # Skip Road Signs
                    if obj.dff.type == "2DFX" and obj.dff.ext_2dfx.effect != '7':
                        obj.parent = root_objects[0]

            # Move dff collection to a top collection named for the file it came from
            context.scene.collection.children.unlink(importer.current_collection)
            self._ipl_collection.children.link(importer.current_collection)

            # Save into buffer
            self._model_cache[inst.id] = collection_objects
            print(str(inst.id) + ' loaded new')
    
        # Look for collision mesh
        name = self._model_cache[inst.id][0].name
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
                    if id not in self._object_data:
                        continue
                    objdata = self._object_data[id]
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

        ide_paths = [entry.name for entry in self.settings.ide_paths if entry.name.strip()]
        if not ide_paths:
            self.report({'ERROR'}, "No IDEs specified for import.")
            return

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
                    if id not in self._object_data:
                        continue
                    objdata = self._object_data[id]
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

        # Skip LODs if user selects this
        if hasattr(inst, 'lod') and int(inst.lod) == -1 and self.settings.skip_lod:
            return

        # Deleted objects that Rockstar forgot to remove?
        if inst.id not in self._object_data:
            return

        model = self._object_data[inst.id].modelName
        txd = self._object_data[inst.id].txdName

        if inst.id in self._model_cache:

            # Get model from memory
            new_objects = {}
            model_cache = self._model_cache[inst.id]

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

            cached_2dfx = [obj for obj in model_cache if obj.dff.type == "2DFX"]
            for obj in cached_2dfx:
                new_obj = bpy.data.objects.new(obj.name, obj.data)
                new_obj.location = obj.location
                new_obj.rotation_mode = obj.rotation_mode
                new_obj.lock_rotation = obj.lock_rotation
                new_obj.rotation_quaternion = obj.rotation_quaternion
                new_obj.rotation_euler = obj.rotation_euler
                new_obj.scale = obj.scale

                if obj.parent:
                    new_obj.parent = new_objects[obj.parent]

                for prop in obj.dff.keys():
                    new_obj.dff[prop] = obj.dff[prop]

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
                    'txd_pack'         : False,
                    'image_ext'        : 'PNG',
                    'connect_bones'    : False,
                    'use_mat_split'    : self.settings.read_mat_split,
                    'remove_doubles'   : True,
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

            # Set root object as 2DFX parent
            if root_objects:
                for obj in collection_objects:
                    # Skip Road Signs
                    if obj.dff.type == "2DFX" and obj.dff.ext_2dfx.effect != '7':
                        obj.parent = root_objects[0]

            # Move dff collection to a top collection named for the file it came from
            context.scene.collection.children.unlink(importer.current_collection)
            self._ipl_collection.children.link(importer.current_collection)

            # Save into buffer
            self._model_cache[inst.id] = collection_objects
            print(str(inst.id) + ' loaded new')
    
        # Look for collision mesh
        name = self._model_cache[inst.id][0].name
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
