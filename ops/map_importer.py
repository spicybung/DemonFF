# DemonFF - Blender scripts to edit basic GTA formats to work in conjunction with SAMP/open.mp
# 2023 - 2025 SpicyBung

# This is a fork of DragonFF by Parik - maintained by Psycrow, and various others!
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
import random
from ..gtaLib import map as map_utilites
from ..ops import dff_importer

class Map_Import_Operator(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "scene.demonff_map_import"
    bl_label = "Import map section"
    
    # Define file path property
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    
    _timer = None
    _updating = False
    _calcs_done = False
    _inst_index = 0
    
    _object_instances = []
    _object_data = []
    _model_cache = {}

    settings = None

    def import_object(self, context):
        if self._inst_index > len(self._object_instances) - 1:
            self._calcs_done = True
            return

        inst = self._object_instances[self._inst_index]
        self._inst_index += 1

        if hasattr(inst, 'lod') and int(inst.lod) == -1 and self.settings.skip_lod:
            return

        # Assign a random, non-conflicting IDE ID if not found in _object_data
        if inst.id not in self._object_data:
            inst.id = self.generate_non_conflicting_id()
            print(f"Generated new ID for object: {inst.id}")

        model = self._object_data[inst.id].modelName

        if inst.id in self._model_cache:
            objGroup = self._model_cache[inst.id]
            newGroup = []
            for obj in objGroup:
                new_obj = bpy.data.objects.new(model, obj.data)
                new_obj.location = obj.location
                new_obj.rotation_quaternion = obj.rotation_quaternion
                new_obj.scale = obj.scale

                modifier = new_obj.modifiers.new("EdgeSplit", 'EDGE_SPLIT')
                if(modifier is not None):
                    modifier.use_edge_angle = False

                if '{}.dff'.format(model) in bpy.data.collections:
                    bpy.data.collections['{}.dff'.format(model)].objects.link(new_obj)
                else:
                    context.collection.objects.link(new_obj)
                newGroup.append(new_obj)

            for obj in objGroup:
                if obj.parent in objGroup:
                    newGroup[objGroup.index(obj)].parent = newGroup[objGroup.index(obj.parent)]
            if len(newGroup) > 0:
                Map_Import_Operator.apply_transformation_to_object(newGroup[0], inst)
            print(str(inst.id) + ' loaded from cache')
        else:
            if not os.path.isfile("%s/%s.dff" % (self.settings.dff_folder, model)):
                return
            importer = dff_importer.import_dff({
                'file_name': "%s/%s.dff" % (self.settings.dff_folder, model),
                'image_ext': 'PNG',
                'connect_bones': False,
                'use_mat_split': True,
                'remove_doubles': True,
                'group_materials': True,
                'import_normals': True
            })

            if len(importer.objects) > 0:
                Map_Import_Operator.apply_transformation_to_object(importer.objects[0], inst)

            self._model_cache[inst.id] = importer.objects
            print(str(inst.id) + ' loaded new')

    # Generates a non-conflicting ID
    def generate_non_conflicting_id(self):
        existing_ids = {inst.id for inst in self._object_instances}
        while True:
            new_id = random.randint(100000, 999999)  # Generate a random 6-digit ID
            if new_id not in existing_ids:
                return new_id

    def modal(self, context, event):
        if event.type in {'ESC'}:
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'TIMER' and not self._updating:
            self._updating = True

            for x in range(10):
                try:
                    self.import_object(context)
                except:
                    print("Can`t import model... skipping")

            num = (
                float(self._inst_index) / float(len(self._object_instances))
            ) if self._object_instances else 0
            bpy.context.window_manager.progress_update(num)

            dg = context.evaluated_depsgraph_get()
            dg.update()

            self._updating = False

        if self._calcs_done:
            self.cancel(context)
            return {'FINISHED'}

        return {'PASS_THROUGH'}

    def execute(self, context):
        self.settings = context.scene.dff
        self._model_cache = {}

        # Get all the necessary IDE and IPL data
        map_data = map_utilites.MapDataUtility.getMapData(
            self.settings.game_version_dropdown,
            self.settings.game_root,
            self.settings.map_sections
        )
        
        self._object_instances = map_data['object_instances']
        self._object_data = map_data['object_data']

        wm = context.window_manager
        wm.progress_begin(0, 100.0)
        
        self._timer = wm.event_timer_add(0.1, window=context.window)
        
        wm.modal_handler_add(self)

        return {'RUNNING_MODAL'}

    def cancel(self, context):
        wm = context.window_manager
        wm.progress_end()
        wm.event_timer_remove(self._timer)

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

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

def menu_func_import(self, context):
    self.layout.operator(Map_Import_Operator.bl_idname, text="Import GTA IPL")

def register():
    bpy.utils.register_class(Map_Import_Operator)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(Map_Import_Operator)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register()
