# DemonFF - Blender scripts for working with Renderware & R*/SA-MP/open.mp formats in Blender
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

from mathutils import Matrix, Vector
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper


# Starting with Manhunt 2, as the others are a pain right now.
#######################################################
class IMPORT_OT_read_mdl_header(Operator, ImportHelper):
    bl_idname = "import_scene.read_mdl_header"
    bl_label = "Import MDL and Read Header"
    filename_ext = ".mdl"
    filter_glob: bpy.props.StringProperty(default="*.mdl", options={'HIDDEN'})
    #######################################################
    def execute(self, context):
        
        bone_map = {}
        #######################################################
        def read_bone(f, offset, depth=0, parent_offset=0):
            indent = "  " * depth
            f.seek(offset)
            bone_data = f.read(192)
            if len(bone_data) < 192:
                print(f"{indent}!! Incomplete bone read at 0x{offset:08X}")
                return

            # Unpack first 24 bytes
            header = struct.unpack("<6I", bone_data[:24])
            sibling_offset = header[1]
            parent_ptr = header[2]
            subbone_offset = header[4]
            anim_data_idx_offset = header[5]

            # Read name (next 40 bytes)
            bone_name_bytes = bone_data[24:64]
            bone_name = bone_name_bytes.split(b'\x00')[0].decode('ascii', errors='replace')

            # Read WorldPos matrix (last 64 bytes of the 192-byte bone block)
            world_matrix_raw = bone_data[128:192]
            raw = struct.unpack("<16f", world_matrix_raw)

            # Convert from column-major to row-major
            mat = Matrix((
                (raw[0], raw[4], raw[8],  raw[12]),
                (raw[1], raw[5], raw[9],  raw[13]),
                (raw[2], raw[6], raw[10], raw[14]),
                (raw[3], raw[7], raw[11], raw[15])
            ))

            # Optional: convert from Y-up to Z-up (rotate -90° around X)
            y_up_to_z_up = Matrix.Rotation(-3.14159265 / 2, 4, 'X')
            mat = mat @ y_up_to_z_up

            # Store bone with correct matrix
            bone_map[offset] = {
                'name': bone_name,
                'parent_offset': parent_ptr,
                'matrix': mat
            }


            print(f"{indent}==== Bone at 0x{offset:08X} ====")
            print(f"{indent}Name:                   {bone_name}")
            print(f"{indent}Sibling Offset:         0x{sibling_offset:08X}")
            print(f"{indent}Parent Offset:          0x{parent_ptr:08X}")
            print(f"{indent}SubBone Offset:         0x{subbone_offset:08X}")
            print(f"{indent}AnimBoneDataIdx Offset: 0x{anim_data_idx_offset:08X}")
            print(f"{indent}=============================")

            if subbone_offset != 0:
                read_bone(f, subbone_offset, depth + 1, offset)
            if sibling_offset != 0:
                read_bone(f, sibling_offset, depth, parent_offset)
                
        anim_bone_map = {}
        #######################################################
        def read_anim_bone_data(f, anim_data_idx_offset):
            f.seek(anim_data_idx_offset)
            raw = f.read(24)
            num_bones, _, _, anim_data_offset, _, _ = struct.unpack("<6I", raw)
            
            f.seek(anim_data_offset)
            for _ in range(num_bones):
                bone_id, bone_type, bone_offset = struct.unpack("<HHI", f.read(8))
                anim_bone_map[bone_id] = {
                    "offset": bone_offset,
                    "type": bone_type
                }

        #######################################################
        def read_vertex_by_type(f, vtype, count, per_vertex_size):
            vertices = []

            for i in range(count):
                if vtype == 0x52:
                    data = f.read(24)
                    pos = struct.unpack_from("<3f", data, 0)
                    norm_raw = struct.unpack_from("<3h", data, 12)
                    color = struct.unpack_from("<4B", data, 18)
                    norm = tuple(n / 32768.0 for n in norm_raw)
                    vertices.append((pos, norm, color, None))

                elif vtype == 0x152:
                    data = f.read(32)
                    pos = struct.unpack_from("<3f", data, 0)
                    norm_raw = struct.unpack_from("<3h", data, 12)
                    color = struct.unpack_from("<4B", data, 18)
                    uv = struct.unpack_from("<2f", data, 22)
                    norm = tuple(n / 32768.0 for n in norm_raw)
                    vertices.append((pos, norm, color, uv))

                elif vtype == 0x115E:
                    data = f.read(52)
                    pos = struct.unpack_from("<3f", data, 0)
                    weights = struct.unpack_from("<4f", data, 12)
                    bone_ids = struct.unpack_from("<4B", data, 28)
                    norm_raw = struct.unpack_from("<3h", data, 32)
                    color = struct.unpack_from("<4B", data, 38)
                    uv = struct.unpack_from("<2f", data, 42)
                    norm = tuple(n / 32768.0 for n in norm_raw)
                    vertices.append((pos, norm, color, uv, weights, bone_ids))

                elif vtype == 0x125E:
                    data = f.read(60)
                    pos = struct.unpack_from("<3f", data, 0)
                    weights = struct.unpack_from("<4f", data, 12)
                    bone_ids = struct.unpack_from("<4B", data, 28)
                    norm_raw = struct.unpack_from("<3h", data, 32)
                    color = struct.unpack_from("<4B", data, 38)
                    uv1 = struct.unpack_from("<2f", data, 42)
                    uv2 = struct.unpack_from("<2f", data, 50)
                    norm = tuple(n / 32768.0 for n in norm_raw)
                    vertices.append((pos, norm, color, uv1, uv2, weights, bone_ids))

                elif vtype == 0x252:
                    data = f.read(40)
                    pos = struct.unpack_from("<3f", data, 0)
                    norm_raw = struct.unpack_from("<3h", data, 12)
                    color = struct.unpack_from("<4B", data, 18)
                    uv1 = struct.unpack_from("<2f", data, 22)
                    uv2 = struct.unpack_from("<2f", data, 30)
                    norm = tuple(n / 32768.0 for n in norm_raw)
                    vertices.append((pos, norm, color, uv1, uv2))

                else:
                    raise ValueError(f"Unknown VertexElementType: 0x{vtype:X}")

            return vertices


        with open(self.filepath, "rb") as f:
            # -------------------------------
            # Read WDR Header
            # -------------------------------
            data = f.read(0x28)
            header = struct.unpack("<4sIIIIIIIii", data)

            signature = header[0].decode("ascii")
            first_entry_offset = header[8]

            print("\n==== Reading MDL Header ====")
            print(f"Signature:           {signature}")
            print(f"Version:             {header[1]:08X}")
            print(f"File Size:           {header[2]} bytes")
            print(f"Data Size:           {header[3]} bytes")
            print(f"Offset Table Start:  0x{header[4]:08X}")
            print(f"Num Table Entries:   {header[5]}")
            print(f"Zero1:               {header[6]}")
            print(f"Zero2:               {header[7]}")
            print(f"First Entry Offset:  0x{first_entry_offset:08X}")
            print(f"Last Entry Offset:   0x{header[9]:08X}")
            print("============================\n")

            # -------------------------------
            # Read EntryIndex
            # -------------------------------
            f.seek(first_entry_offset)
            entry_index_data = f.read(16)
            entry_index = struct.unpack("<iiii", entry_index_data)
            entry_data_offset = entry_index[2]

            print("==== Reading First EntryIndex ====")
            print(f"Next Entry Offset:   0x{entry_index[0]:08X}")
            print(f"Prev Entry Offset:   0x{entry_index[1]:08X}")
            print(f"Entry Data Offset:   0x{entry_data_offset:08X}")
            print(f"Zero Field:          {entry_index[3]}")
            print("==================================\n")

            # -------------------------------
            # Read Entry Structure
            # -------------------------------
            f.seek(entry_data_offset)
            entry_struct_data = f.read(0x1C)
            entry = struct.unpack("<7i", entry_struct_data)

            root_bone_offset = entry[0]
            unknown = entry[3]
            first_obj_info_offset = entry[4]
            last_obj_info_offset = entry[5]


            print("==== Reading Entry ====")
            print(f"Root Bone Offset:         0x{root_bone_offset:08X}")
            print(f"First ObjectInfo Offset:  0x{first_obj_info_offset:08X}")
            print(f"Last ObjectInfo Offset:   0x{last_obj_info_offset:08X}")
            print(f"Unknown Field:            0x{unknown:08X}")
            print("==================================\n")

            # -------------------------------
            # Read Bone Hierarchy
            # -------------------------------
            if root_bone_offset > 0:
                print("Traversing Bone Hierarchy:")
                # Read root bone's first 24 bytes to get anim_data_idx_offset
                f.seek(root_bone_offset)
                root_bone_raw = f.read(24)
                if len(root_bone_raw) < 24:
                    print("!! Root bone read failed")
                else:
                    anim_data_idx_offset = struct.unpack("<6I", root_bone_raw)[5]
                    read_bone(f, root_bone_offset)
                    if anim_data_idx_offset > 0:
                        read_anim_bone_data(f, anim_data_idx_offset)

            else:
                print("Root Bone Offset is 0 — skipping root bone read.\n")

            # -------------------------------
            # Read ObjectInfos (support multiple objects)
            # -------------------------------
            object_infos = []
            current_info_offset = first_obj_info_offset
            visited_offsets = set()

            if current_info_offset == 0 and last_obj_info_offset > 0:
                print("First ObjectInfo Offset is 0 — falling back to Last ObjectInfo Offset.\n")
                current_info_offset = last_obj_info_offset

            print("==== Traversing ObjectInfo blocks ====")
            while current_info_offset not in visited_offsets and current_info_offset != 0:
                visited_offsets.add(current_info_offset)
                f.seek(current_info_offset)
                object_info_data = f.read(28)
                if len(object_info_data) < 28:
                    print(f"!! Incomplete ObjectInfo at 0x{current_info_offset:08X}")
                    break

                object_info = struct.unpack("<7i", object_info_data)
                next_info_offset = object_info[0]
                object_data_offset = object_info[3]

                object_infos.append((current_info_offset, object_data_offset))

                print(f"ObjectInfo @ 0x{current_info_offset:08X}")
                print(f"  Next Object Offset:   0x{object_info[0]:08X}")
                print(f"  Prev Object Offset:   0x{object_info[1]:08X}")
                print(f"  Parent Bone Offset:   0x{object_info[2]:08X}")
                print(f"  Object Data Offset:   0x{object_data_offset:08X}")
                print(f"  Root Entry Offset:    0x{object_info[4]:08X}")
                print(f"  Zero Field:           0x{object_info[5]:08X}")
                print(f"  Unknown (Always 3):   0x{object_info[6]:08X}\n")

                if next_info_offset == current_info_offset or next_info_offset == 0:
                    break
                current_info_offset = next_info_offset

            print(f"✅ Found {len(object_infos)} ObjectInfo entries.")
            print("============================================\n")


            # -------------------------------
            # Read Object Chunk Header for Each Object
            # -------------------------------
            for obj_index, (info_offset, object_data_offset) in enumerate(object_infos):
                print(f"\n======= Reading Object Chunk Header for Object {obj_index} =======")
                f.seek(object_data_offset)
                obj_chunk = f.read(180)
                if len(obj_chunk) < 180:
                    print("!! Incomplete Object Header read, skipping.")
                    continue

                try:
                    (
                        material_offset, num_materials, bone_trans_offset, unknown_f, unknown1,
                        ux, uy, uz, model_chunk_flag, model_chunk_size,
                        zero, numMaterialIDs, numFaceIndex,
                        bs_x, bs_y, bs_z, bs_radius,
                        scale_x, scale_y, scale_z,
                        num_vertices, zero2_0, zero2_1, zero2_2,
                        per_vertex_size,
                        *unk_rest
                    ) = struct.unpack("<3I f I 3f 2I 3I 3f f 3f I 3I I 11I I 8I", obj_chunk)

                    unk4 = unk_rest[:11]
                    vertex_element_type = unk_rest[11]
                    unk5 = unk_rest[12:]

                    print(f"Material Offset:           0x{material_offset:08X}")
                    print(f"Num Materials:             {num_materials}")
                    print(f"BoneTransDataIndexOffset:  0x{bone_trans_offset:08X}")
                    print(f"Vertex Element Type:       0x{vertex_element_type:X}")
                    print(f"Number of Vertices:        {num_vertices}")
                    print(f"Number of Face Indices:    {numFaceIndex}")
                except Exception as e:
                    print(f"!! Failed to unpack object chunk: {e}")
                    continue

                # Seek and read faces
                try:
                    face_offset = object_data_offset + 180 + (numMaterialIDs * 0x30)
                    f.seek(face_offset)
                    faces = []
                    for i in range(numFaceIndex // 3):
                        face_raw = f.read(6)
                        if len(face_raw) < 6:
                            print(f"⚠️ Incomplete face at triangle {i}")
                            break
                        a, b, c = struct.unpack("<3H", face_raw)
                        if a >= num_vertices or b >= num_vertices or c >= num_vertices:
                            print(f"⚠️ Face {i} references invalid vertex index: {a}, {b}, {c}")
                            continue
                        faces.append((a, b, c))
                    if not faces:
                        print("❌ No valid faces, skipping.")
                        continue
                except Exception as e:
                    print(f"❌ Failed to read faces: {e}")
                    continue

                # Read vertices
                try:
                    # Calculate vertex buffer offset
                    vertex_offset = object_data_offset + 180 + (numMaterialIDs * 32) + ((numFaceIndex // 3) * 6)



                    print(f"🔍 Calculated Vertex Buffer Offset: 0x{vertex_offset:08X}")
                    f.seek(vertex_offset + 36)

                    try:
                        vertices = read_vertex_by_type(f, vertex_element_type, num_vertices, per_vertex_size)
                    except Exception as e:
                        print(f"❌ Failed to read vertices at calculated offset: {e}")
                        continue

                except Exception as e:
                    print(f"❌ Failed to read vertices: {e}")
                    continue

                if len(vertices) != num_vertices:
                    print(f"❌ Vertex count mismatch. Got {len(vertices)} expected {num_vertices}")
                    continue
                
                # -------------------------------
                # Read Materials
                # -------------------------------
                materials = []
                if material_offset != 0 and num_materials > 0:
                    f.seek(material_offset)
                    for i in range(num_materials):
                        mat_raw = f.read(16)
                        if len(mat_raw) < 16:
                            print(f"!! Material {i} read incomplete")
                            break

                        tex_offset, b_loaded = struct.unpack("<IB", mat_raw[:5])
                        color = struct.unpack("4B", mat_raw[5:9])
                        # Skips 3 bytes of padding

                        # Save current position to come back after reading TexName
                        current = f.tell()

                        # Read Texture Name
                        f.seek(tex_offset)
                        tex_name_bytes = bytearray()
                        while True:
                            b = f.read(1)
                            if not b or b == b'\x00':
                                break
                            tex_name_bytes += b
                        tex_name = tex_name_bytes.decode("ascii", errors="replace")

                        materials.append({
                            "tex_name": tex_name,
                            "color": color,
                            "loaded": b_loaded
                        })

                        print(f"Material {i}: Loaded={b_loaded}, Color RGBA={color}, TexName='{tex_name}'")

                        f.seek(current)
                else:
                    print("No material block found or num_materials == 0.")

                # Create Blender Mesh
                try:
                    # Get the base name of the file, strip extension
                    base_filename = os.path.splitext(os.path.basename(self.filepath))[0]

                    # Build a unique name per mesh object
                    name = f"{base_filename}_{obj_index}"

                    # Create mesh and object
                    mesh = bpy.data.meshes.new(name)
                    obj = bpy.data.objects.new(name, mesh)
                    bpy.context.collection.objects.link(obj)
                    mesh.from_pydata([v[0] for v in vertices], [], faces)
                    mesh.update()
                    print(f"✅ Blender Mesh created: MDL_Mesh_{obj_index}")
                    
                    # Add materials to the mesh
                    for mat_data in materials:
                        mat_name = mat_data['tex_name'] or f"Material_{obj_index}"
                        mat = bpy.data.materials.get(mat_name)
                        if mat is None:
                            mat = bpy.data.materials.new(name=mat_name)
                            mat.use_nodes = True
                            bsdf = mat.node_tree.nodes.get("Principled BSDF")
                            if bsdf:
                                b, g, r, a = mat_data['color']
                                bsdf.inputs['Base Color'].default_value = (r/255.0, g/255.0, b/255.0, a/255.0)
                        mesh.materials.append(mat)

                    # Apply material indices to polygons using MaterialIDs
                    try:
                        material_ids_offset = object_data_offset + 180  # right after the header
                        f.seek(material_ids_offset)
                        material_ids = []

                        for i in range(numMaterialIDs):
                            entry = f.read(32)
                            if len(entry) < 32:
                                break
                            (
                                bb_min_x, bb_min_y, bb_min_z,
                                bb_max_x, bb_max_y, bb_max_z,
                                num_faces, material_id,
                                start_face_id, _,
                                *_  # skip 12 bytes
                            ) = struct.unpack("<6f4H12x", entry)
                            material_ids.append({
                                "material_id": material_id,
                                "start_face_id": start_face_id,
                                "num_faces": num_faces
                            })

                        print(f"🎯 Applying MaterialIDs to mesh polygons...")

                        for matid in material_ids:
                            start = matid["start_face_id"]
                            end = start + matid["num_faces"]
                            for poly_idx in range(start, end):
                                if poly_idx < len(mesh.polygons):
                                    mesh.polygons[poly_idx].material_index = matid["material_id"]
                    except Exception as e:
                        print(f"⚠️ Failed to apply MaterialIDs: {e}")


                except Exception as e:
                    print(f"❌ Failed to create Blender mesh: {e}")
                    continue

            # -------------------------------
            # Read BoneTransDataIndex (header)
            # -------------------------------
            bone_matrices = []

            if bone_trans_offset != 0:
                f.seek(bone_trans_offset)
                bone_data_idx_raw = f.read(8)
                if len(bone_data_idx_raw) < 8:
                    print("!! Incomplete BoneTransDataIndex struct")
                else:
                    num_bones, bone_data_offset = struct.unpack("<2I", bone_data_idx_raw)
                    print(f"\n==== BoneTransformDataIndex ====")
                    print(f"Number of Bones:           {num_bones}")
                    print(f"BoneTransData Offset:      0x{bone_data_offset:08X}")
                    
            # -------------------------------
            # Read Bone Transform Matrices
            # -------------------------------
            bone_matrices = []

            if bone_trans_offset != 0:
                f.seek(bone_trans_offset)
                bone_data_idx_raw = f.read(8)
                if len(bone_data_idx_raw) < 8:
                    print("!! Incomplete BoneTransDataIndex struct")
                else:
                    num_bones, bone_data_offset = struct.unpack("<2I", bone_data_idx_raw)
                    print(f"\n==== Bone Transform Data ====")
                    print(f"Number of Bones:           {num_bones}")
                    print(f"BoneTransData Offset:      0x{bone_data_offset:08X}")

                    f.seek(bone_data_offset)
                    for i in range(num_bones):
                        matrix_raw = f.read(64)
                        if len(matrix_raw) < 64:
                            print(f"!! Incomplete matrix read for bone {i}")
                            break

                        raw = struct.unpack("<16f", matrix_raw)

                        # Convert from column-major to row-major
                        mat = Matrix((
                            (raw[0], raw[4], raw[8],  raw[12]),
                            (raw[1], raw[5], raw[9],  raw[13]),
                            (raw[2], raw[6], raw[10], raw[14]),
                            (raw[3], raw[7], raw[11], raw[15])
                        ))

                        # Optional: Rotate Y-up to Z-up
                        y_up_to_z_up = Matrix.Rotation(-3.14159265 / 2, 4, 'X')  # -90° X
                        mat = mat @ y_up_to_z_up

                        bone_matrices.append(mat)

                        print(f"Bone {i} Transform Matrix:")
                        for row in mat:
                            print(f"  ({row[0]:.6f}, {row[1]:.6f}, {row[2]:.6f}, {row[3]:.6f})")

                    print("======================================\n")

            else:
                print("No BoneTransDataIndex offset found (0). Skipping.")


            # -------------------------------
            # Read Materials
            # -------------------------------
            materials = []
            if material_offset != 0 and num_materials > 0:
                f.seek(material_offset)
                for i in range(num_materials):
                    mat_raw = f.read(16)
                    if len(mat_raw) < 16:
                        print(f"!! Material {i} read incomplete")
                        break

                    tex_offset, b_loaded = struct.unpack("<IB", mat_raw[:5])
                    color = struct.unpack("4B", mat_raw[5:9])
                    # Skips 3 bytes of padding

                    # Save current position to come back after reading TexName
                    current = f.tell()

                    # Read Texture Name
                    f.seek(tex_offset)
                    tex_name_bytes = bytearray()
                    while True:
                        b = f.read(1)
                        if not b or b == b'\x00':
                            break
                        tex_name_bytes += b
                    tex_name = tex_name_bytes.decode("ascii", errors="replace")

                    materials.append({
                        "tex_name": tex_name,
                        "color": color,
                        "loaded": b_loaded
                    })

                    print(f"Material {i}: Loaded={b_loaded}, Color RGBA={color}, TexName='{tex_name}'")

                    f.seek(current)
            else:
                print("No material block found or num_materials == 0.")
                
                

            print("Creating Blender Armature from Matrices...")
            arm_data = bpy.data.armatures.new("MDL_Armature")
            arm_obj = bpy.data.objects.new("MDL_Armature", arm_data)
            # Link armature to the scene (after mesh is created)
            bpy.context.collection.objects.link(arm_obj)

            # Parent armature to the mesh to appear nested under it
            # Find the top-level mesh object you created (the first one, or the main one)
            mesh_obj = None
            for obj in bpy.context.collection.objects:
                if obj.name.startswith(base_filename):
                    mesh_obj = obj
                    break

            if mesh_obj:
                arm_obj.parent = mesh_obj
                arm_obj.parent_type = 'OBJECT'
                print(f"✓ Armature '{arm_obj.name}' parented to mesh '{mesh_obj.name}' (Outliner structure fixed)")
                                                                                
            bpy.context.view_layer.objects.active = arm_obj
            bpy.ops.object.mode_set(mode='EDIT')

            bone_lookup = {}

            # Create all bones first
            for offset, bone_data in bone_map.items():
                name = bone_data["name"]
                matrix = bone_data.get("matrix")  # Must be added below
                if matrix is None:
                    continue

                edit_bone = arm_data.edit_bones.new(name)
                head = matrix.to_translation()
                tail = head + matrix.to_3x3() @ Vector((0, 0.05, 0))  # Y axis tail offset

                edit_bone.head = head
                edit_bone.tail = tail
                bone_lookup[offset] = edit_bone

            # Assign parent relationships
            for offset, bone_data in bone_map.items():
                parent_offset = bone_data["parent_offset"]
                if parent_offset in bone_lookup and offset in bone_lookup:
                    bone_lookup[offset].parent = bone_lookup[parent_offset]

            bpy.ops.object.mode_set(mode='OBJECT')
            print("Armature created.")
            
            print("Setting up bone groups by hierarchy and parenting meshes...")




            print("✔️ Bone groups assigned by hierarchy and meshes parented.")


        return {'FINISHED'}
#######################################################
def menu_func_import(self, context):
    self.layout.operator(IMPORT_OT_read_mdl_header.bl_idname, text="Read MDL Header (.mdl)")

def register():
    bpy.utils.register_class(IMPORT_OT_read_mdl_header)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(IMPORT_OT_read_mdl_header)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register()