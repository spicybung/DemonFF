# DemonFF - Blender scripts to edit basic GTA formats to work in conjunction with SAMP/open.mp
# 2023 - 2025 SpicyBung

# This is a fork of DragonFF by Parik - maintained by Psycrow, and various others!

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
import struct
import re
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator, Panel
from .dff_importer import import_dff

def sanitize_filename(filename):
    return re.sub(r'[^\w\-_\. ]', '_', filename)

class ImgImporter:
    def __init__(self, img_path):
        self.img_path = img_path
        self.entries = []

    def read_directory(self):
        with open(self.img_path, 'rb') as img_file:
            header = img_file.read(8)
            num_entries = struct.unpack('<I', header[4:8])[0]

            for _ in range(num_entries):
                entry_data = img_file.read(32)
                offset, streaming_size, _, name = struct.unpack('<IHH24s', entry_data)
                name = sanitize_filename(name.decode('latin-1').strip('\x00'))
                self.entries.append({
                    'offset': offset,
                    'streaming_size': streaming_size,
                    'name': name
                })

    def extract_dff_files(self):
        with open(self.img_path, 'rb') as img_file:
            for entry in self.entries:
                if entry['name'].lower().endswith('.dff'):
                    img_file.seek(entry['offset'] * 2048)
                    file_data = img_file.read(entry['streaming_size'] * 2048)
                    self.import_dff(file_data, entry['name'])

    def import_dff(self, dff_data, dff_name):
        dff_name = sanitize_filename(dff_name)
        output_path = os.path.join(bpy.app.tempdir, dff_name)

        with open(output_path, 'wb') as temp_dff_file:
            temp_dff_file.write(dff_data)

        options = {
            'file_name': output_path,
            'image_ext': 'png',  # Adjust if necessary
            'connect_bones': False,
            'use_mat_split': False,
            'remove_doubles': False,
            'group_materials': False,
            'import_normals': False
        }

        import_dff(options)

        dff_mesh = bpy.data.meshes.new(dff_name)
        dff_obj = bpy.data.objects.new(dff_name, dff_mesh)

        bpy.context.collection.objects.link(dff_obj)
        bpy.context.view_layer.objects.active = dff_obj
        dff_obj.select_set(True)

    def create_dir_file(self):
        dir_filepath = os.path.splitext(self.img_path)[0] + ".dir"
        with open(dir_filepath, 'wb') as dir_file:
            for entry in self.entries:
                packed_entry = struct.pack(
                    '<II24s',
                    entry['offset'] * 2048,
                    entry['streaming_size'] * 2048,
                    entry['name'].ljust(24, '\x00').encode('latin-1')
                )
                dir_file.write(packed_entry)

    def import_img(self):
        self.read_directory()
        self.extract_dff_files()
        self.create_dir_file()

class IMPORT_OT_img(Operator, ImportHelper):
    bl_idname = "import_scene.img"
    bl_label = "Import IMG File"
    filename_ext = ".img"

    filter_glob: StringProperty(
        default="*.img",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        importer = ImgImporter(self.filepath)
        importer.import_img()
        self.report({'INFO'}, f"Successfully imported IMG and created DIR: {os.path.splitext(self.filepath)[0]}.dir")
        return {'FINISHED'}

class IMPORT_PT_img_panel(Panel):
    bl_idname = "IMPORT_PT_img_panel"
    bl_label = "DemonFF - IMG Importer"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"
    bl_category = 'DemonFF'

    def draw(self, context):
        layout = self.layout
        layout.operator("import_scene.img", text="Import IMG File")


def menu_func_import(self, context):
    self.layout.operator(IMPORT_OT_img.bl_idname, text="Import IMG File")

def register():
    bpy.utils.register_class(IMPORT_OT_img)
    bpy.utils.register_class(IMPORT_PT_img_panel)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(IMPORT_OT_img)
    bpy.utils.unregister_class(IMPORT_PT_img_panel)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register()
