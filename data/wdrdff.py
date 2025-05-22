import bpy
import struct
import zlib
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from bpy.types import Operator, Panel

# WDR data structure
class WDRHeader:
    def __init__(self):
        self.header_length = 0
        self.shader_group_offset = 0
        self.skeleton_data_offset = 0
        self.center = [0, 0, 0, 0]
        self.bounds_min = [0, 0, 0, 0]
        self.bounds_max = [0, 0, 0, 0]
        self.model_collection_offset = 0
        self.object_count = 0

class WDRModel:
    def __init__(self):
        self.geometry = []

class WDRGeometry:
    def __init__(self):
        self.vertices = []
        self.indices = []
        self.vertex_stride = 0
        self.vertex_count = 0
        self.index_count = 0
        self.face_count = 0

# WDR file handling class
class WDRFile:
    def __init__(self, filepath):
        self.filepath = filepath
        self.header = WDRHeader()
        self.models = []

    def _read_long(self, data, offset):
        return struct.unpack_from('<L', data, offset)[0]

    def _read_short(self, data, offset):
        return struct.unpack_from('<H', data, offset)[0]

    def _read_float(self, data, offset):
        return struct.unpack_from('<f', data, offset)[0]

    def _parse_header(self, data):
        self.header.header_length = self._read_long(data, 0x04)
        self.header.shader_group_offset = self._read_long(data, 0x08)
        self.header.skeleton_data_offset = self._read_long(data, 0x0C)
        self.header.center = [
            self._read_float(data, 0x10),
            self._read_float(data, 0x14),
            self._read_float(data, 0x18),
            self._read_float(data, 0x1C),
        ]
        self.header.bounds_min = [
            self._read_float(data, 0x20),
            self._read_float(data, 0x24),
            self._read_float(data, 0x28),
            self._read_float(data, 0x2C),
        ]
        self.header.bounds_max = [
            self._read_float(data, 0x30),
            self._read_float(data, 0x34),
            self._read_float(data, 0x38),
            self._read_float(data, 0x3C),
        ]
        self.header.model_collection_offset = self._read_long(data, 0x40)

    def _parse_model_collection(self, data):
        model_collection_offset = self.header.model_collection_offset
        pointer_offset = self._read_long(data, model_collection_offset)
        model_count = self._read_short(data, model_collection_offset + 4)

        # Parse models
        for i in range(model_count):
            model_offset = self._read_long(data, pointer_offset + i * 4)
            model = WDRModel()

            self._parse_geometry(data, model_offset, model)

            self.models.append(model)

    def _parse_geometry(self, data, model_offset, model):
        geometry_count_offset = model_offset + 0x18
        geometry_count = self._read_short(data, geometry_count_offset)

        for i in range(geometry_count):
            geometry_offset = self._read_long(data, model_offset + 0x04 + i * 4)
            geometry = WDRGeometry()

            vertex_buffer_offset = self._read_long(data, geometry_offset + 0x0C)
            index_buffer_offset = self._read_long(data, geometry_offset + 0x1C)
            geometry.vertex_stride = self._read_short(data, geometry_offset + 0x3C)
            geometry.vertex_count = self._read_short(data, geometry_offset + 0x34)
            geometry.index_count = self._read_long(data, geometry_offset + 0x2C)

            # Extract vertices and indices
            geometry.vertices = data[vertex_buffer_offset : vertex_buffer_offset + geometry.vertex_count * geometry.vertex_stride]
            geometry.indices = data[index_buffer_offset : index_buffer_offset + geometry.index_count * 6]

            model.geometry.append(geometry)

    def load(self):
        with open(self.filepath, 'rb') as file:
            raw_data = file.read()

            try:
                decompressed_data = zlib.decompress(raw_data)
            except zlib.error:
                decompressed_data = raw_data

            self._parse_header(decompressed_data)
            self._parse_model_collection(decompressed_data)

# Blender operator for importing WDR files
class ImportWDR2DFF(Operator, ImportHelper):
    bl_idname = "import_wdr.wdr2dff"
    bl_label = "Import WDR File"
    filename_ext = ".wdr"

    filepath: StringProperty(
        name="File Path",
        description="Filepath for WDR file",
        maxlen=1024,
        default=""
    )

    def execute(self, context):
        wdr = WDRFile(self.filepath)
        wdr.load()

        bpy.ops.object.select_all(action='DESELECT')  # Deselect all objects
        mesh = bpy.data.meshes.new("WDR_Mesh")
        obj = bpy.data.objects.new("WDR_Object", mesh)
        context.collection.objects.link(obj)

        # Further conversion to Blender mesh would be added here

        return {'FINISHED'}

# Panel for Blender's 3D view
class ImportWDR2DFFPanel(Panel):
    bl_idname = "VIEW3D_PT_import_wdr2dff"
    bl_label = "Import WDR2DFF"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        layout.operator(ImportWDR2DFF.bl_idname, text="Import WDR File")

# Registering the add-on and integrating with Blender's file import menu
def menu_func_import(self, context):
    self.layout.operator(ImportWDR2DFF.bl_idname, text="Import WDR File")

def register():
    bpy.utils.register_class(ImportWDR2DFF)
    bpy.utils.register_class(ImportWDR2DFFPanel)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(ImportWDR2DFF)
    bpy.utils.unregister_class(ImportWDR2DFFPanel)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register()
