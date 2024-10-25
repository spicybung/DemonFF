import bpy
import os
import struct
import re
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator, Panel
from .dff_importer import import_dff  # Ensure you have a valid import_dff

# Function to sanitize file names by removing illegal characters
def sanitize_filename(filename):
    return re.sub(r'[^\w\-_\. ]', '_', filename)

class ImgImporter:
    def __init__(self, img_path):
        self.img_path = img_path
        self.entries = []

    def read_directory(self):
        """ Read the directory entries from the IMG file (GTA SA Version 2) """
        with open(self.img_path, 'rb') as img_file:
            # First, read the 8-byte header
            header = img_file.read(8)
            if header[:4] != b'VER2':
                raise ValueError("Not a GTA SA Version 2 IMG file")
            num_entries = struct.unpack('<I', header[4:8])[0]

            # Read the directory entries (32 bytes each)
            for _ in range(num_entries):
                entry_data = img_file.read(32)
                offset, streaming_size, _size_in_archive, name = struct.unpack('<IHH24s', entry_data)
                name = name.decode('latin-1').strip('\x00')
                name = sanitize_filename(name)
                self.entries.append({
                    'offset': offset,
                    'streaming_size': streaming_size,
                    'name': name
                })

    def extract_dff_files(self):
        """ Extract and import the DFF files from the IMG """
        with open(self.img_path, 'rb') as img_file:
            for entry in self.entries:
                if entry['name'].lower().endswith('.dff'):
                    # Seek to the position of the file (offset is in sectors, so multiply by 2048)
                    img_file.seek(entry['offset'] * 2048)

                    # Read the file data (streaming size in sectors, so multiply by 2048)
                    file_data = img_file.read(entry['streaming_size'] * 2048)

                    # Pass the DFF data to the importer
                    self.import_dff(file_data, entry['name'])

    def import_dff(self, dff_data, dff_name):
        """ Import the extracted DFF file into Blender """
        dff_name = sanitize_filename(dff_name)
        output_path = os.path.join(bpy.app.tempdir, dff_name)

        # Write DFF data to a temporary file
        with open(output_path, 'wb') as temp_dff_file:
            temp_dff_file.write(dff_data)

        # Prepare import options
        options = {
            'file_name': output_path,
            'image_ext': 'png',  # Adjust this if necessary
            'connect_bones': False,
            'use_mat_split': False,
            'remove_doubles': False,
            'group_materials': False,
            'import_normals': False
        }

        # Use the correct method for importing DFF with options
        import_dff(options)

        # After import, ensure mesh is attached to the scene
        dff_mesh = bpy.data.meshes.new(dff_name)  # Create a new mesh
        dff_obj = bpy.data.objects.new(dff_name, dff_mesh)  # Create a new object with the mesh

        # Link the object to the active collection in the current scene
        bpy.context.collection.objects.link(dff_obj)

        # Ensure the object appears in the scene
        bpy.context.view_layer.objects.active = dff_obj
        dff_obj.select_set(True)

    def import_img(self):
        """ Main function to read and import the IMG file """
        # Read the directory entries
        self.read_directory()

        # Extract and import the DFF files
        self.extract_dff_files()

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
        return {'FINISHED'}

class IMPORT_PT_img_panel(Panel):
    bl_idname = "IMPORT_PT_img_panel"
    bl_label = "IMG Importer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Import'

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
