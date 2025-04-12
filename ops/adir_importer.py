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

import os
import struct
import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from bpy.types import Operator
from .dff_importer import import_dff

class ImportDIR(Operator, ImportHelper):
    """Import a Rockstar .DIR file to read and import DFF files"""
    bl_idname = "import_scene.dir"
    bl_label = "Import DIR"
    
    # ImportHelper mixin class uses this
    filename_ext = ".DIR"
    
    filter_glob: StringProperty(
        default="*.DIR",
        options={'HIDDEN'},
    )

    def execute(self, context):
        return self.read_dir_file(context, self.filepath)

    def read_dir_file(self, context, filepath):
        try:
            with open(filepath, 'rb') as f:
                while True:
                    entry_data = f.read(32)
                    if len(entry_data) < 32:
                        break  # End of file
                    
                    # Each entry is 32 bytes: 4 bytes offset, 4 bytes size, 24 bytes filename
                    offset, size = struct.unpack('<II', entry_data[:8])
                    filename = entry_data[8:32].decode('latin-1').strip('\x00')
                    
                    # Construct full path to the DFF file
                    dff_path = os.path.join(os.path.dirname(filepath), filename)
                    
                    # Check if the DFF file exists, then import it
                    if os.path.exists(dff_path) and filename.lower().endswith('.dff'):
                        self.import_dff_file(context, dff_path)
                    
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read DIR file: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}

    def import_dff_file(self, context, dff_path):
        """Use the DFF importer to import the file."""
        import_dff(dff_path, context)

def menu_func_import(self, context):
    self.layout.operator(ImportDIR.bl_idname, text="Rockstar DIR (.DIR)")

def register():
    bpy.utils.register_class(ImportDIR)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(ImportDIR)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register()
