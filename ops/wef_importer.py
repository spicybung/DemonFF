import bpy
import struct
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator
from bpy.props import StringProperty
from bpy_extras.object_utils import object_data_add
import bmesh

class ImportWEF(bpy.types.Operator, ImportHelper):
    """Import a WEF File"""
    bl_idname = "import_scene.wef"
    bl_label = "Import WEF"
    filename_ext = ".wef"
    
    filter_glob: StringProperty(
        default="*.wef",
        options={'HIDDEN'},
    )

    def execute(self, context):
        return self.read_wef(context, self.filepath)

    def read_wef(self, context, filepath):
        with open(filepath, 'rb') as f:
            obj_count = struct.unpack('i', f.read(4))[0]
            
            for t in range(obj_count):
                vert = []
                norm = []
                tvert = []
                face = []

                vert_count = struct.unpack('i', f.read(4))[0]
                
                # Vertices
                for i in range(vert_count):
                    x, y, z = struct.unpack('fff', f.read(12))
                    vert.append((x, y, z))

                # Normals
                for i in range(vert_count):
                    x, y, z = struct.unpack('fff', f.read(12))
                    norm.append((x, y, z))

                # Texture Vertices
                for i in range(vert_count):
                    u, v = struct.unpack('ff', f.read(8))
                    tvert.append((u, v))
                
                face_count = struct.unpack('i', f.read(4))[0]
                
                # Faces
                for i in range(face_count):
                    f1, f2, f3 = struct.unpack('hhh', f.read(6))
                    face.append((f1, f2, f3))
                
                # Create mesh
                mesh = bpy.data.meshes.new(name=f"Mesh_{t}")
                mesh.from_pydata(vert, [], face)
                
                # Create UV map
                mesh.uv_layers.new(name='UVMap')
                uv_layer = mesh.uv_layers.active.data
                
                # Assign UVs
                for poly in mesh.polygons:
                    for loop_index in poly.loop_indices:
                        loop = mesh.loops[loop_index]
                        uv = tvert[loop.vertex_index]
                        uv_layer[loop_index].uv = uv
                
                # Add mesh to scene
                obj = object_data_add(context, mesh)
                
                # Create and assign material
                mat = bpy.data.materials.new(name=f"Material_{t}")
                if mesh.materials:
                    mesh.materials[0] = mat
                else:
                    mesh.materials.append(mat)
                
        self.report({'INFO'}, "Done")
        return {'FINISHED'}

def menu_func_import(self, context):
    self.layout.operator(ImportWEF.bl_idname, text="WEF Importer (.wef)")

def register():
    bpy.utils.register_class(ImportWEF)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(ImportWEF)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register()
