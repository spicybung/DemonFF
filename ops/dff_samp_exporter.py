# DemonFF - Blender scripts for working with Renderware & R*/SA-MP/open.mp formats in Blender
# 2023 - 2026 spicybung

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

# NOTE: Keeping seperate track for SAMP DFF model exporting here

import os
import bpy
import bmesh
import os.path
import re
import mathutils

from ..gtaLib import dff_samp
from collections import defaultdict
from .col_samp_exporter import export_col
from ..ops.ext_2dfx_exporter import ext_2dfx_exporter


#######################################################
def clear_extension(string):
    
    k = string.rfind('.')
    return string if k < 0 else string[:k]
    
#######################################################
class material_helper:

    """ Material Helper for Blender 2.7x and 2.8 compatibility"""

    #######################################################
    def get_base_color(self):

        if self.principled:
            node = self.principled.node_principled_bsdf.inputs["Base Color"]
            return dff_samp.RGBA._make(
                list(int(255 * x) for x in node.default_value)
            )
        alpha = int(self.material.alpha * 255)
        return dff_samp.RGBA._make(
                    list(int(255*x) for x in self.material.diffuse_color) + [alpha]
                )

    #######################################################
    def get_texture(self):

        texture = dff_samp.Texture()
        texture.filters = 0 # <-- find a way to store this in Blender
        
        # 2.8         
        if self.principled:
            if self.principled.base_color_texture.image is not None:

                node_label = self.principled.base_color_texture.node_image.label
                image_name = self.principled.base_color_texture.image.name

                # Use node label if it is a substring of image name, else
                # use image name
                
                texture.name = clear_extension(
                    node_label
                    if node_label in image_name and node_label != ""
                    else image_name
                )
                if texture.name[:3].lower() == "tex" and texture.name[3:].isdigit():
                    texture.name = texture.name.lower()
                return texture
            return None

        # Blender Internal
        try:
            texture.name = clear_extension(
                self.material.texture_slots[0].texture.image.name
            )
            if texture.name[:3].lower() == "tex" and texture.name[3:].isdigit():
                texture.name = texture.name.lower()
            return texture

        except BaseException:
            return None

    #######################################################
    def get_surface_properties(self):

        if self.principled:
            specular = self.principled.specular
            diffuse = self.principled.roughness
            ambient = self.material.dff.ambient
            
        else:

            specular = self.material.specular_intensity
            diffuse  = self.material.diffuse_intensity
            ambient  = self.material.ambient
            
        return dff_samp.GeomSurfPro(ambient, specular, diffuse)

    #######################################################
    def get_normal_map(self):

        bump_texture = None
        height_texture = dff_samp.Texture()

        if not self.material.dff.export_bump_map:
            return None
        
        # 2.8
        if self.principled:
            
            if self.principled.normalmap_texture.image is not None:

                bump_texture = dff_samp.Texture()
                
                node_label = self.principled.node_normalmap.label
                image_name = self.principled.normalmap_texture.image.name

                bump_texture.name = clear_extension(
                    node_label
                    if node_label in image_name and node_label != ""
                    else image_name
                )
                intensity = self.principled.normalmap_strength

        height_texture.name = self.material.dff.bump_map_tex
        if height_texture.name == "":
            height_texture = None

        if bump_texture is not None:
            return dff_samp.BumpMapFX(intensity, height_texture, bump_texture)

        return None

    #######################################################
    def get_environment_map(self):

        if not self.material.dff.export_env_map:
            return None

        texture_name = self.material.dff.env_map_tex
        coef         = self.material.dff.env_map_coef
        use_fb_alpha  = self.material.dff.env_map_fb_alpha

        texture = dff_samp.Texture()
        texture.name = texture_name
        texture.filters = 0
        
        return dff_samp.EnvMapFX(coef, use_fb_alpha, texture)

    #######################################################
    def get_specular_material(self):

        props = self.material.dff
        
        if not props.export_specular:
            return None

        return dff_samp.SpecularMat(props.specular_level,
                               props.specular_texture.encode('ascii'))

    #######################################################
    def get_reflection_material(self):

        props = self.material.dff

        if not props.export_reflection:
            return None

        return dff_samp.ReflMat(
            props.reflection_scale_x, props.reflection_scale_y,
            props.reflection_offset_x, props.reflection_offset_y,
            props.reflection_intensity
        )

    #######################################################
    def get_user_data(self):

        if 'dff_user_data' not in self.material:
            return None
        
        return dff_samp.UserData.from_mem(
                self.material['dff_user_data'])
    
    #######################################################
    def get_uv_animation(self):

        anim = dff_samp.UVAnim()

        # See if export_animation checkbox is checked
        if not self.material.dff.export_animation:
            return None

        anim.name = self.material.dff.animation_name
        
        if self.principled:
            if self.principled.base_color_texture.has_mapping_node():
                anim_data = self.material.node_tree.animation_data
                
                fps = bpy.context.scene.render.fps
                
                if anim_data:
                    for curve in anim_data.action.fcurves:

                        # Rw doesn't support Z texture coordinate.
                        if curve.array_index > 1:
                            continue

                        # Offset in the UV array
                        uv_offset = {
                            'nodes["Mapping"].inputs[1].default_value': 4,
                            'nodes["Mapping"].inputs[3].default_value': 1,
                        }

                        if curve.data_path not in uv_offset:
                            continue
                        
                        off = uv_offset[curve.data_path]
                        
                        for i, frame in enumerate(curve.keyframe_points):
                            
                            if len(anim.frames) <= i:
                                anim.frames.append(dff_samp.UVFrame(0,[0]*6, i-1))

                            _frame = list(anim.frames[i])
                                
                            uv = _frame[1]
                            uv[off + curve.array_index] = frame.co[1]

                            _frame[0] = frame.co[0] / fps

                            anim.frames[i] = dff_samp.UVFrame._make(_frame)
                            anim.duration = max(anim.frames[i].time,anim.duration)
                            
                    return anim
    
    #######################################################
    def __init__(self, material):
        self.material = material
        self.principled = None

        if bpy.app.version >= (2, 80, 0):
            from bpy_extras.node_shader_utils import PrincipledBSDFWrapper
            
            self.principled = PrincipledBSDFWrapper(self.material,
                                                    is_readonly=False)
        
        

#######################################################
def edit_bone_matrix(edit_bone):

    """ A helper function to return correct matrix from any
        bone setup there might. 
        
        Basically resets the Tail to +0.05 in Y Axis to make a correct
        prediction
    """

    return edit_bone.matrix
    
    # What I wrote above is rubbish, by the way. This is a hack-ish solution
    original_tail = list(edit_bone.tail)
    edit_bone.tail = edit_bone.head + mathutils.Vector([0, 0.05, 0])
    matrix = edit_bone.matrix

    edit_bone.tail = original_tail
    return matrix

class DffExportException(Exception):
    pass

#######################################################
class dff_exporter:

    selected = False
    mass_export = False
    file_name = ""
    dff = None
    version = None
    frames = {}
    bones = {}
    frame_objects = {}
    parent_queue = {}
    collection = None
    collision_objects = None
    export_coll = False
    preserve_collision_positions = True
    force_collision_to_dff_transform = True


    #######################################################
    @staticmethod
    def multiply_matrix(a, b):
        # For compatibility with 2.79
        if bpy.app.version < (2, 80, 0):
            return a * b
        return a @ b

    #######################################################
    @staticmethod
    def get_rotation_only_matrix(matrix):
        try:
            rotation = matrix.to_quaternion().to_matrix()
        except Exception:
            rotation = matrix.to_3x3().normalized()

        return rotation.transposed()
    #######################################################    
    @staticmethod
    def get_object_parent(obj):
        if type(obj) is bpy.types.Object and obj.parent_bone:
            parent = obj.parent.data.bones.get(obj.parent_bone)
            if parent:
                return parent

        return obj.parent
    
    #######################################################
    @staticmethod
    def create_frame(obj, append=True, set_parent=True, matrix_local=None):
        self = dff_exporter
        
        frame       = dff_samp.Frame()
        frame_index = len(self.dff.frame_list)
        
        # Get rid of everything before the last period
        if self.export_frame_names:
            frame.name = clear_extension(obj.name)
            if self.truncate_frame_names:
                frame.name = self.truncate_frame_name(frame.name)  # Apply truncation

        # Is obj a bone?
        is_bone = type(obj) is bpy.types.Bone

        matrix = matrix_local or obj.matrix_local
        if is_bone and obj.parent is not None:
            matrix = self.multiply_matrix(obj.parent.matrix_local.inverted(), matrix)

        parent = self.get_object_parent(obj)

        if is_bone or parent:
            position = matrix.to_translation()
            rotation_matrix = matrix.to_3x3().transposed()
        else:
            if self.preserve_positions:
                position = matrix.to_translation()
            else:
                position = (0, 0, 0)

            rotation_matrix = matrix.to_3x3().transposed()

        frame.creation_flags  =  0
        frame.parent          = -1
        frame.position        = position
        frame.rotation_matrix = dff_samp.Matrix._make(rotation_matrix)

        if "dff_user_data" in obj:
            frame.user_data = dff_samp.UserData.from_mem(obj["dff_user_data"])

        if set_parent and parent is not None:

            if parent not in self.frame_objects:
                raise DffExportException(f"Failed to set parent for {obj.name} "
                                         f"to {parent.name}.")

            parent_frame_idx = self.frame_objects[parent]
            frame.parent = parent_frame_idx

        if append:
            self.dff.frame_list.append(frame)

        self.frame_objects[obj] = frame_index
        return frame
    
    #######################################################
    @staticmethod
    def get_last_frame_index():
        return len(dff_exporter.dff.frame_list) - 1

    #######################################################
    @staticmethod
    def make_default_material():
        material = dff_samp.Material()
        material.color = dff_samp.RGBA._make((255, 255, 255, 255))
        material.surface_properties = dff_samp.GeomSurfPro._make((1.0, 1.0, 1.0))
        return material

    #######################################################
    @staticmethod
    def generate_material_list(obj):
        materials = []
        self = dff_exporter

        for b_material in obj.data.materials:

            if b_material is None:
                continue
            
            material = dff_samp.Material()
            helper = material_helper(b_material)

            material.color             = helper.get_base_color()
            material.surface_properties = helper.get_surface_properties()
            
            texture = helper.get_texture()
            if texture:
                material.textures.append(texture)

            # Materials
            material.add_plugin('bump_map', helper.get_normal_map())
            material.add_plugin('env_map', helper.get_environment_map())
            material.add_plugin('spec', helper.get_specular_material())
            material.add_plugin('refl', helper.get_reflection_material())
            material.add_plugin('udata', helper.get_user_data())

            anim = helper.get_uv_animation()
            if anim:
                material.add_plugin('uv_anim', anim.name)
                self.dff.uvanim_dict.append(anim)
                
            materials.append(material)

        if not materials:
            materials.append(self.make_default_material())

        return materials

    #######################################################
    @staticmethod
    def clamp_triangle_materials_to_material_list(geometry):
        if not geometry.materials:
            geometry.materials.append(dff_exporter.make_default_material())

        max_material_index = len(geometry.materials) - 1
        if max_material_index < 0:
            return

        fixed_triangles = []
        changed_count = 0
        for triangle in geometry.triangles:
            material_index = triangle.material
            if material_index < 0 or material_index > max_material_index:
                material_index = 0
                changed_count += 1

            fixed_triangles.append(dff_samp.Triangle._make((
                triangle.b,
                triangle.a,
                material_index,
                triangle.c,
            )))

        if changed_count:
            geometry.triangles = fixed_triangles


    #######################################################
    @staticmethod
    def get_skin_plg_and_bone_groups(obj, mesh):

        # Returns a SkinPLG object if the object has an armature modifier
        armature = None
        for modifier in obj.modifiers:
            if modifier.type == 'ARMATURE':
                armature = modifier.object
                break
            
        if armature is None:
            return (None, {})
        
        skin = dff_samp.SkinPLG()
        
        bones = armature.data.bones
        skin.num_bones = len(bones)

        bone_groups = {} # This variable will store the bone groups
                         # to export keyed by their indices
                         
        for index, bone in enumerate(bones):
            matrix = bone.matrix_local.inverted().transposed()
            skin.bone_matrices.append(
                matrix
            )
            try:
                bone_groups[obj.vertex_groups[bone.name].index] = index

            except KeyError:
                pass
            
        return (skin, bone_groups)

    #######################################################
    @staticmethod
    def get_vertex_shared_loops(vertex, layers_list, funcs):
        #temp = [[None] * len(layers) for layers in layers_list]
        shared_loops = {}

        for loop in vertex.link_loops:
            start_loop = vertex.link_loops[0]
            
            shared = False
            for i, layers in enumerate(layers_list):
               
                for layer in layers:

                    if funcs[i](start_loop[layer], loop[layer]):
                        shared = True
                        break

                if shared:
                    shared_loops[loop] = True
                    break
                
        return shared_loops.keys()

    #######################################################
    @staticmethod
    def get_delta_morph_entries(obj, mesh):
        dm_entries = []
        self = dff_exporter

        if mesh.shape_keys and len(mesh.shape_keys.key_blocks) > 1:
            for kb in mesh.shape_keys.key_blocks[1:]:
                min_corner = mathutils.Vector(min(v.co[i] for v in kb.data) for i in range(3))
                max_corner = mathutils.Vector(max(v.co[i] for v in kb.data) for i in range(3))
                dimensions = mathutils.Vector(max_corner[i] - min_corner[i] for i in range(3))

                sphere_center = 0.5 * (min_corner + max_corner)
                sphere_center = self.multiply_matrix(obj.matrix_world, sphere_center)
                sphere_radius = 1.732 * max(*dimensions) / 2

                entrie = dff_samp.DeltaMorph()
                entrie.name = kb.name
                entrie.bounding_sphere = dff_samp.Sphere._make(
                    list(sphere_center) + [sphere_radius]
                )

                dm_entries.append(entrie)

        return dm_entries

    #######################################################
    @staticmethod
    def triangulate_mesh(mesh):
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.to_mesh(mesh)
        bm.free()

    #######################################################
    @staticmethod
    def find_vert_idx_by_tmp_idx(verts, idx):
        for i, vert in enumerate(verts):
            if vert['tmp_idx'] == idx:
                return i

    #######################################################
    @staticmethod
    def populate_geometry_from_vertices_data(vertices_list, skin_plg, dm_entries,
                                             mesh, obj, geometry, num_vcols):

        has_prelit_colors = num_vcols > 0 and obj.dff.day_cols
        has_night_colors  = num_vcols > 1 and obj.dff.night_cols

        # This number denotes what the maximum number of uv maps exported will be.
        # If obj.dff.uv_map2 is set (i.e second UV map WILL be exported), the
        # maximum will be 2. If obj.dff.uv_map1 is NOT set, the maximum cannot
        # be greater than 0.
        max_uv_layers = (obj.dff.uv_map2 + 1) * obj.dff.uv_map1
        max_uv_layers = (obj.dff.uv_map2 + 1) * obj.dff.uv_map1

        extra_vert = None
        if has_night_colors:
            extra_vert = dff_samp.ExtraVertColorExtension([])

        delta_morph_plg = None
        if dm_entries:
            delta_morph_plg = dff_samp.DeltaMorphPLG()
            for entrie in dm_entries:
                delta_morph_plg.append_entry(entrie)
           
        for idx, vertex in enumerate(vertices_list):
            geometry.vertices.append(dff_samp.Vector._make(vertex['co']))
            geometry.normals.append(dff_samp.Vector._make(vertex['normal']))

            # vcols
            #######################################################
            if has_prelit_colors:
                geometry.prelit_colors.append(dff_samp.RGBA._make(
                    int(col * 255) for col in vertex['vert_cols'][0]))
            if has_night_colors:
                extra_vert.colors.append(dff_samp.RGBA._make(
                    int(col * 255) for col in vertex['vert_cols'][1]))

            # uv layers
            #######################################################
            for index, uv in enumerate(vertex['uvs']):
                if index >= max_uv_layers:
                    break

                while index >= len(geometry.uv_layers):
                    geometry.uv_layers.append([])

                geometry.uv_layers[index].append(dff_samp.TexCoords(uv.x, 1-uv.y))

            # bones
            #######################################################
            if skin_plg is not None:
                skin_plg.vertex_bone_indices.append([0,0,0,0])
                skin_plg.vertex_bone_weights.append([0,0,0,0])

                for index, bone in enumerate(vertex['bones']):
                    skin_plg.vertex_bone_indices[-1][index] = bone[0]
                    skin_plg.vertex_bone_weights[-1][index] = bone[1]

            # delta_morph
            #######################################################
            if delta_morph_plg is not None:
                sk_cos = vertex['sk_cos']
                for index, co in enumerate(sk_cos[1:]):
                    pos = mathutils.Vector(co) - mathutils.Vector(sk_cos[0])
                    if sum(pos) == 0.0:
                        continue

                    entrie = dm_entries[index]
                    entrie.indices.append(idx)
                    entrie.positions.append(pos)

        if skin_plg is not None:
            geometry.extensions['skin'] = skin_plg
        if extra_vert:
            geometry.extensions['extra_vert_color'] = extra_vert
        if delta_morph_plg is not None:
            geometry.extensions['delta_morph'] = delta_morph_plg

    #######################################################
    @staticmethod
    def populate_geometry_from_faces_data(faces_list, geometry):
        material_count = len(geometry.materials)
        max_material_index = material_count - 1

        for face in faces_list:
            verts = face['verts']
            if len(verts) < 3:
                continue

            try:
                material_index = int(face.get('mat_idx', 0))
            except Exception:
                material_index = 0

            if material_count <= 0 or material_index < 0 or material_index > max_material_index:
                material_index = 0

            geometry.triangles.append(
                dff_samp.Triangle._make((
                    verts[1], #b
                    verts[0], #a
                    material_index, #material
                    verts[2] #c
                ))
            )

    #######################################################
    @staticmethod
    def convert_slinear_to_srgb (col):
        color = mathutils.Color (col[:3])
        return tuple(color.from_scene_linear_to_srgb ()) + (col[3],)

    #######################################################
    @staticmethod
    def get_vertex_colors(mesh : bpy.types.Mesh):
        self = dff_exporter

        v_cols = []

        if bpy.app.version < (3, 2, 0):
            for layer in mesh.vertex_colors:
                v_cols.append([list(i.color) for i in layer.data])
            return v_cols

        for attrib in mesh.color_attributes[:2]:
            # Already per loop
            if attrib.domain == 'CORNER':
                v_cols.append(
                    [
                        list(self.convert_slinear_to_srgb(i.color))
                        for i in attrib.data
                    ]
                )

            # Per-vertex, need to convert to per-loop
            else:
                colors = {}
                for polygon in mesh.polygons:
                    for v_ix, l_ix in zip(polygon.vertices, polygon.loop_indices):
                        colors[l_ix] = self.convert_slinear_to_srgb(
                            list(attrib.data[v_ix].color))
                v_cols.append(colors)

        return v_cols

    #######################################################
    #######################################################
    @staticmethod
    def populate_geometry_with_mesh_data(obj, geometry):
        self = dff_exporter

        mesh = self.convert_to_mesh(obj)
        self.triangulate_mesh(mesh)

        # Ensure compatibility with Blender versions
        if bpy.app.version < (4, 0, 0) and hasattr(mesh, 'calc_loop_triangles'):
            mesh.calc_loop_triangles()

        vcols = self.get_vertex_colors(mesh)
        verts_indices = {}
        vertices_list = []
        faces_list = []

        skin_plg, bone_groups = self.get_skin_plg_and_bone_groups(obj, mesh)
        dm_entries = self.get_delta_morph_entries(obj, mesh)

        # Clamp vertices if they exceed the limit
        if len(mesh.vertices) > 0xFFFF:
            print(f"Clamping vertices in mesh ({obj.name}). Too many vertices: {len(mesh.vertices)}/65535")
            mesh = self.clamp_mesh_vertices(mesh)

        for polygon in mesh.polygons:
            face = {"verts": [], "mat_idx": polygon.material_index}

            for loop_index in polygon.loop_indices:
                loop = mesh.loops[loop_index]
                vertex = mesh.vertices[loop.vertex_index]
                uvs = []
                vert_cols = []
                bones = []
                sk_cos = []

                for uv_layer in mesh.uv_layers:
                    uvs.append(uv_layer.data[loop_index].uv)

                for vert_col in vcols:
                    vert_cols.append(vert_col[loop_index])

                for group in vertex.groups:
                    if len(bones) >= 4:
                        break

                    if group.group in bone_groups and group.weight > 0:
                        bones.append((bone_groups[group.group], group.weight))

                if mesh.shape_keys:
                    for kb in mesh.shape_keys.key_blocks:
                        sk_cos.append(kb.data[loop.vertex_index].co)

                key = (loop.vertex_index,
                    tuple(loop.normal),
                    tuple(tuple(uv) for uv in uvs))

                normal = loop.normal if obj.dff.export_split_normals else vertex.normal

                if key not in verts_indices:
                    face['verts'].append(len(vertices_list))
                    verts_indices[key] = len(vertices_list)
                    vertices_list.append({"idx": loop.vertex_index,
                                        "co": vertex.co,
                                        "normal": normal,
                                        "uvs": uvs,
                                        "vert_cols": vert_cols,
                                        "bones": bones,
                                        "sk_cos": sk_cos})
                else:
                    face['verts'].append(verts_indices[key])

            faces_list.append(face)

        # Check vertices count after deduplication and clamp if necessary
        if len(vertices_list) > 0xFFFF:
            print(f"Clamping deduplicated vertices in mesh ({obj.name}). Too many vertices: {len(vertices_list)}/65535")
            vertices_list = vertices_list[:0xFFFF]
            faces_list = self.clamp_faces_to_vertices(faces_list, len(vertices_list))

        self.populate_geometry_from_vertices_data(
            vertices_list, skin_plg, dm_entries, mesh, obj, geometry, len(vcols))

        self.populate_geometry_from_faces_data(faces_list, geometry)

    #######################################################
    @staticmethod
    def clamp_mesh_vertices(mesh):
        """
        Clamps vertices to the first 65535.
        """
        new_mesh = mesh.copy()
        new_mesh.vertices.foreach_set('select', [False] * len(new_mesh.vertices))  # Deselect all vertices

        for i in range(65535):
            new_mesh.vertices[i].select = True

        # Return clamped mesh
        return new_mesh

    #######################################################
    @staticmethod
    def clamp_faces_to_vertices(faces_list, max_vertices):
        """
        Clamps faces to use vertices within the max_vertices range.
        """
        clamped_faces = []
        for face in faces_list:
            clamped_verts = [v for v in face['verts'] if v < max_vertices]
            if len(clamped_verts) == len(face['verts']):
                clamped_faces.append(face)  # Only add if all vertices are within range
        return clamped_faces
        
    
    #######################################################
    @staticmethod
    def convert_to_mesh(obj):

        """ 
        A Blender 2.8 <=> 2.7 compatibility function for bpy.types.Object.to_mesh
        """
        
        # Temporarily disable armature
        disabled_modifiers = []
        for modifier in obj.modifiers:
            if modifier.type == 'ARMATURE':
                modifier.show_viewport = False
                disabled_modifiers.append(modifier)

        # Temporarily reset key shape values
        key_shape_values = {}
        if obj.data.shape_keys:
            for kb in obj.data.shape_keys.key_blocks:
                key_shape_values[kb] = kb.value
                kb.value = 0.0

        if bpy.app.version < (2, 80, 0):
            mesh = obj.to_mesh(bpy.context.scene, True, 'PREVIEW')
        else:
            
            depsgraph   = bpy.context.evaluated_depsgraph_get()
            object_eval = obj.evaluated_get(depsgraph)
            mesh        = object_eval.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
            

        # Re enable disabled modifiers
        for modifier in disabled_modifiers:
            modifier.show_viewport = True

        # Restore key shape values
        for kb, v in key_shape_values.items():
            kb.value = v

        return mesh
    
    #######################################################
    def populate_atomic(obj, frame_index=None):
            self = dff_exporter

            # Get frame index from parent
            if frame_index is None:
                parent = self.get_object_parent(obj)
                if parent:
                    frame_index = self.frame_objects.get(parent)

            # Get frame index from armature modifier
            if frame_index is None:
                for modifier in obj.modifiers:
                    if modifier.type == 'ARMATURE':
                        frame_index = self.frame_objects.get(modifier.object)
                        if frame_index is not None:
                            break

            # Create new frame if there is no parent
            if frame_index is None:
                self.create_frame(obj, set_parent=False)
                frame_index = self.get_last_frame_index()

            # Create geometry
            geometry = dff_samp.Geometry()
            geometry.materials = self.generate_material_list(obj)
            self.populate_geometry_with_mesh_data (obj, geometry)

            # Bounding sphere
            # RenderWare geometry bounds are geometry-local.
            # Do not write obj.matrix_world here: the frame already carries that transform.
            # A world-space geometry sphere plus a non-zero frame translates the cull bounds twice,
            # which makes some otherwise valid custom models disappear in-game.
            geometry.bounding_sphere = self.calculate_geometry_bounding_sphere(geometry.vertices)

            geometry.surface_properties = (0,0,0)
            self.clamp_triangle_materials_to_material_list(geometry)

            geometry.export_flags['export_normals'] = obj.dff.export_normals
            geometry.export_flags['write_mesh_plg'] = obj.dff.export_binsplit
            geometry.export_flags['light'] = obj.dff.light
            geometry.export_flags['modulate_color'] = obj.dff.modulate_color

            
            if "dff_user_data" in obj.data:
                geometry.extensions['user_data'] = dff_samp.UserData.from_mem(
                    obj.data['dff_user_data'])

            # Add Geometry to list
            self.dff.geometry_list.append(geometry)

            # Create Atomic from geometry and frame
            atomic          = dff_samp.Atomic('frame', 'geometry', 'flags', 'unk')
            atomic.frame    = frame_index
            atomic.geometry = len(self.dff.geometry_list) - 1
            atomic.flags    = 0x4

            try:
                if obj.dff.pipeline != 'NONE':
                    if obj.dff.pipeline == 'CUSTOM':
                        atomic.extensions['pipeline'] = int(obj.dff.custom_pipeline, 0)
                    else:
                        atomic.extensions['pipeline'] = int(obj.dff.pipeline, 0)

            except ValueError:
                print("Invalid (Custom) Pipeline")

            if "skin" in geometry.extensions:
                right_to_render = dff_samp.RightToRender._make((0x0116,
                    obj.dff.right_to_render
                ))
                atomic.extensions['right_to_render'] = right_to_render

            self.dff.atomic_list.append(atomic)



    #######################################################
    @staticmethod
    def object_has_armature_modifier(obj):
        try:
            for modifier in obj.modifiers:
                if modifier.type == 'ARMATURE':
                    return True
        except Exception:
            return False

        return False

    #######################################################
    @staticmethod
    def should_merge_static_map_atomcs(objects):
        self = dff_exporter

        mesh_objects = [
            obj for obj in objects
            if self.is_atomic_export_object(obj) and obj.type == 'MESH'
        ]

        if len(mesh_objects) <= 1:
            return False

        for obj in objects:
            if getattr(obj, "type", None) == "ARMATURE":
                return False

        for obj in mesh_objects:
            if self.object_has_armature_modifier(obj):
                return False

        return True

    #######################################################
    @staticmethod
    def append_default_vertex_color(colors, count):
        for _index in range(count):
            colors.append(dff_samp.RGBA._make((255, 255, 255, 255)))

    #######################################################
    @staticmethod
    def ensure_merged_geometry_prelit_state(geometry, needed):
        self = dff_exporter

        if not needed:
            return

        if len(geometry.prelit_colors) == len(geometry.vertices):
            return

        self.append_default_vertex_color(
            geometry.prelit_colors,
            len(geometry.vertices) - len(geometry.prelit_colors)
        )

    #######################################################
    @staticmethod
    def ensure_merged_geometry_uv_layers(geometry, needed_count):
        while len(geometry.uv_layers) < needed_count:
            geometry.uv_layers.append([
                dff_samp.TexCoords(0.0, 0.0)
                for _index in range(len(geometry.vertices))
            ])

    #######################################################
    @staticmethod
    def append_merged_geometry_uvs(geometry, source_geometry, source_vertex_index):
        self = dff_exporter
        self.ensure_merged_geometry_uv_layers(geometry, len(source_geometry.uv_layers))

        for layer_index, uv_layer in enumerate(geometry.uv_layers):
            if layer_index < len(source_geometry.uv_layers):
                uv_layer.append(source_geometry.uv_layers[layer_index][source_vertex_index])
            else:
                uv_layer.append(dff_samp.TexCoords(0.0, 0.0))

    #######################################################
    @staticmethod
    def append_merged_geometry_vertex_colors(geometry, source_geometry, source_vertex_index):
        self = dff_exporter

        if source_geometry.prelit_colors:
            self.ensure_merged_geometry_prelit_state(geometry, True)
            geometry.prelit_colors.append(source_geometry.prelit_colors[source_vertex_index])
            return

        if geometry.prelit_colors:
            geometry.prelit_colors.append(dff_samp.RGBA._make((255, 255, 255, 255)))

    #######################################################
    @staticmethod
    def transform_normal_to_frame_space(source_object, frame_matrix, normal):
        try:
            source_normal_matrix = source_object.matrix_world.to_3x3().inverted().transposed()
            world_normal = source_normal_matrix @ mathutils.Vector(normal)
            frame_normal = frame_matrix.to_3x3().transposed() @ world_normal
            frame_normal.normalize()
            return frame_normal
        except Exception:
            return mathutils.Vector(normal)

    #######################################################
    @staticmethod
    def calculate_geometry_bounding_sphere(vertices):
        if not vertices:
            return dff_samp.Sphere._make((0.0, 0.0, 0.0, 0.0))

        points = [mathutils.Vector(vertex) for vertex in vertices]
        min_corner = mathutils.Vector((
            min(point.x for point in points),
            min(point.y for point in points),
            min(point.z for point in points),
        ))
        max_corner = mathutils.Vector((
            max(point.x for point in points),
            max(point.y for point in points),
            max(point.z for point in points),
        ))
        center = (min_corner + max_corner) * 0.5
        radius = max((point - center).length for point in points)

        return dff_samp.Sphere._make((center.x, center.y, center.z, radius))

    #######################################################
    @staticmethod
    def populate_merged_geometry_with_mesh_objects(mesh_objects, frame_matrix, geometry):
        self = dff_exporter

        frame_inverse = frame_matrix.inverted()
        vertex_offset = 0
        material_offset = 0
        merged_vertices_for_bounds = []

        for obj in mesh_objects:
            source_geometry = dff_samp.Geometry()
            source_geometry.materials = self.generate_material_list(obj)
            self.populate_geometry_with_mesh_data(obj, source_geometry)
            self.clamp_triangle_materials_to_material_list(source_geometry)

            next_vertex_count = vertex_offset + len(source_geometry.vertices)
            if next_vertex_count > 0xFFFF:
                raise DffExportException(
                    "cannot merge {0} mesh pieces into one SA-MP atomic: {1} would push the merged geometry to {2} vertices. RenderWare geometry triangles store vertex indices as unsigned 16-bit values, so one geometry cannot exceed 65535 vertices. Split or reduce this model before using single-atomic SA-MP export.".format(
                        len(mesh_objects),
                        obj.name,
                        next_vertex_count,
                    )
                )

            for vertex_index, vertex in enumerate(source_geometry.vertices):
                local_vertex = mathutils.Vector(vertex)
                world_vertex = obj.matrix_world @ local_vertex
                frame_vertex = frame_inverse @ world_vertex

                geometry.vertices.append(dff_samp.Vector._make(frame_vertex))
                merged_vertices_for_bounds.append(frame_vertex)

                if vertex_index < len(source_geometry.normals):
                    frame_normal = self.transform_normal_to_frame_space(
                        obj,
                        frame_matrix,
                        source_geometry.normals[vertex_index]
                    )
                    geometry.normals.append(dff_samp.Vector._make(frame_normal))

                self.append_merged_geometry_uvs(geometry, source_geometry, vertex_index)
                self.append_merged_geometry_vertex_colors(geometry, source_geometry, vertex_index)

            for material in source_geometry.materials:
                geometry.materials.append(material)

            for triangle in source_geometry.triangles:
                triangle_a = triangle.a + vertex_offset
                triangle_b = triangle.b + vertex_offset
                triangle_c = triangle.c + vertex_offset

                if triangle_a > 0xFFFF or triangle_b > 0xFFFF or triangle_c > 0xFFFF:
                    raise DffExportException(
                        "cannot merge {0} mesh pieces into one SA-MP atomic: {1} produced a triangle index above 65535. Split or reduce this model before using single-atomic SA-MP export.".format(
                            len(mesh_objects),
                            obj.name,
                        )
                    )

                geometry.triangles.append(dff_samp.Triangle._make((
                    triangle_b,
                    triangle_a,
                    triangle.material + material_offset,
                    triangle_c,
                )))

            vertex_offset += len(source_geometry.vertices)
            material_offset += len(source_geometry.materials)

        self.clamp_triangle_materials_to_material_list(geometry)
        geometry.bounding_sphere = self.calculate_geometry_bounding_sphere(merged_vertices_for_bounds)

    #######################################################
    @staticmethod
    def copy_master_geometry_export_settings(master_object, geometry):
        geometry.surface_properties = (0, 0, 0)

        geometry.export_flags['export_normals'] = master_object.dff.export_normals
        geometry.export_flags['write_mesh_plg'] = master_object.dff.export_binsplit
        geometry.export_flags['light'] = master_object.dff.light
        geometry.export_flags['modulate_color'] = master_object.dff.modulate_color

        if "dff_user_data" in master_object.data:
            geometry.extensions['user_data'] = dff_samp.UserData.from_mem(
                master_object.data['dff_user_data']
            )

    #######################################################
    @staticmethod
    def populate_merged_static_atomic(mesh_objects):
        self = dff_exporter

        mesh_objects = sorted(mesh_objects, key=lambda obj: obj.dff.atomic_index)
        master_object = mesh_objects[0]

        self.create_frame(master_object, set_parent=False)
        frame_index = self.get_last_frame_index()

        frame_matrix = self.get_exported_collision_frame_matrix_for_object(master_object)

        geometry = dff_samp.Geometry()
        self.populate_merged_geometry_with_mesh_objects(mesh_objects, frame_matrix, geometry)
        self.copy_master_geometry_export_settings(master_object, geometry)

        self.dff.geometry_list.append(geometry)

        atomic = dff_samp.Atomic('frame', 'geometry', 'flags', 'unk')
        atomic.frame = frame_index
        atomic.geometry = len(self.dff.geometry_list) - 1
        atomic.flags = 0x4

        try:
            if master_object.dff.pipeline != 'NONE':
                if master_object.dff.pipeline == 'CUSTOM':
                    atomic.extensions['pipeline'] = int(master_object.dff.custom_pipeline, 0)
                else:
                    atomic.extensions['pipeline'] = int(master_object.dff.pipeline, 0)
        except ValueError:
            print("Invalid (Custom) Pipeline")

        self.dff.atomic_list.append(atomic)

        print(
            "DemonFF SA-MP DFF export: merged {0} mesh atomics into one SA-MP atomic for {1}.".format(
                len(mesh_objects),
                master_object.name
            )
        )



    #######################################################
    @staticmethod
    def calculate_parent_depth(obj):
        parent = obj.parent
        depth = 0
        
        while parent is not None:
            parent = parent.parent
            depth += 1

        return depth        

    #######################################################
    @staticmethod
    def check_armature_parent(obj):

        # This function iterates through all modifiers of the parent's modifier,
        # and check if its parent has an armature modifier set to obj.
        
        for modifier in obj.parent.modifiers:
            if modifier.type == 'ARMATURE':
                if modifier.object == obj:
                    return True

        return False

    #######################################################
    @staticmethod
    def validate_bone_for_export (obj, bone):
        if "bone_id" not in bone or "type" not in bone:
            raise DffExportException(f"Bone ID/Type not found in bone ({bone.name}) "
                                     f"in armature ({obj.name}). Please ensure "
                                     "you're using an armature imported from an "
                                     "existing DFF file")

    #######################################################
    @staticmethod
    def export_armature(obj, parent):
        self = dff_exporter
        
        for index, bone in enumerate(obj.data.bones):

            self.validate_bone_for_export (obj, bone)

            # Create a special bone (contains information for all subsequent bones)
            if index == 0:
                frame = self.create_frame(bone, False)

                # set the first bone's parent to armature's parent
                frame.parent = self.frames[parent.name]

                bone_data = dff_samp.HAnimPLG()
                bone_data.header = dff_samp.HAnimHeader(
                    0x100,
                    bone["bone_id"],
                    len(obj.data.bones)
                )
                
                # Make bone array in the root bone
                for _index, _bone in enumerate(obj.data.bones):
                    self.validate_bone_for_export (obj, _bone)

                    bone_data.bones.append(
                        dff_samp.Bone(
                                _bone["bone_id"],
                                _index,
                                _bone["type"])
                    )

                frame.bone_data = bone_data
                self.dff.frame_list.append(frame)
                continue

            # Create a regular Bone
            frame = self.create_frame(bone, False)

            # Set bone data
            bone_data = dff_samp.HAnimPLG()
            bone_data.header = dff_samp.HAnimHeader(
                0x100,
                bone["bone_id"],
                0
            )
            frame.bone_data = bone_data
            self.dff.frame_list.append(frame)
    #######################################################
    def truncate_frame_name(name):
        """Truncates the frame name to 22 bytes to leave space for null termination."""
        name_bytes = name.encode('utf-8')
        if len(name_bytes) > 24:
            return name_bytes[:22].decode('utf-8', 'ignore')  # Truncate to 22 bytes
        return name

    #######################################################
    @staticmethod
    def export_empty(obj):
        self = dff_exporter

        parent = self.get_object_parent(obj)
        set_parent = False
        matrix_local = None

        if parent in self.frame_objects:
            set_parent = True
            if obj.parent_type == "BONE":
                matrix_local = obj.matrix_basis

        # Create new frame
        self.create_frame(obj, set_parent=set_parent, matrix_local=matrix_local)

    #######################################################
    @staticmethod
    def export_objects(objects, name=None):
        self = dff_exporter

        self.dff = dff_samp.dff()

        # Skip empty collections
        if len(objects) < 1:
            return

        export_name = name if name is not None else os.path.basename(self.file_name)
        effect_objects = self.get_effect_objects_for_export(objects, export_name)
        self.skipped_imported_2dfx_light_frames = 0

        if self.should_merge_static_map_atomcs(objects):
            mesh_objects = [
                obj for obj in objects
                if self.is_atomic_export_object(obj) and obj.type == 'MESH'
            ]
            self.populate_merged_static_atomic(mesh_objects)
        else:
            atomics_data = []

            for obj in objects:

                if self.is_redundant_imported_2dfx_light_frame(obj, effect_objects):
                    self.skipped_imported_2dfx_light_frames += 1
                    continue

                # We can just ignore collision meshes here as the DFF exporter will still look for
                # them in their own nested collection later if export_coll is true.
                if obj.dff.type != 'OBJ':
                    continue

                # create atomic in this case
                if obj.type == "MESH":
                    frame_index = None
                    # create an empty frame
                    if obj.dff.is_frame:
                        self.export_empty(obj)
                        frame_index = self.get_last_frame_index()
                    atomics_data.append((obj, frame_index))

                # create an empty frame
                elif obj.type == "EMPTY":
                    self.export_empty(obj)

                elif obj.type == "ARMATURE":
                    self.export_armature(obj)

            atomics_data = sorted(atomics_data, key=lambda a: a[0].dff.atomic_index)

            for mesh, frame_index in atomics_data:
                self.populate_atomic(mesh, frame_index)

        if len(self.dff.geometry_list) == 0:
            export_name = name if name is not None else os.path.basename(self.file_name)
            print('DemonFF SA-MP DFF export: skipped %s because it has no mesh geometry to export.' % export_name)
            return

        if self.mass_export and len(self.dff.geometry_list) > 1:
            export_name = name if name is not None else os.path.basename(self.file_name)
            raise DffExportException(
                'refusing to write %s as a SA-MP custom object because it still has %d geometries / %d atomics. Export one master atomic, split it, or reduce it first.' % (
                    export_name,
                    len(self.dff.geometry_list),
                    len(self.dff.atomic_list),
                )
            )

        for geometry in self.dff.geometry_list:
            geometry.ensure_materials_for_export()

        # 2DFX
        root_objects = self.get_root_atomic_objects_from_export_objects(objects)
        location_overrides = self.get_2dfx_location_overrides(effect_objects, root_objects)
        ext_2dfx_exporter(self.dff.ext_2dfx, location_overrides).export_objects(effect_objects)
        self.export_2dfx_light_structs(effect_objects, objects)

        self.last_export_verify = self.get_export_verify_counts(objects, effect_objects)
        self.print_export_verify(export_name, self.last_export_verify)

        # Collision
        if self.export_coll:
            collision_collection = self.get_collision_export_collection()
            collision_objects = self.collision_objects

            # Never let embedded DFF collision fall back to "everything in the collection".
            # Mass export must embed only the collision object(s) paired with this DFF.
            if collision_objects is None:
                collision_objects = self.get_collision_objects_for_export_objects(self.collection, objects)

            if collision_objects is None:
                collision_objects = []

            if len(collision_objects) != 0:
                collision_name = collision_collection.name if collision_collection is not None else '<direct object list>'
                collision_face_count = sum(self.get_mesh_face_count(obj) for obj in collision_objects)
                export_name = name if name is not None else os.path.basename(self.file_name)
                print(
                    'DemonFF SA-MP DFF export: embedding collision %s into %s (%d object(s), %d face(s)).' % (
                        collision_name,
                        export_name,
                        len(collision_objects),
                        collision_face_count,
                    )
                )
                try:
                    mem = export_col({
                        'file_name'     : name if name is not None else os.path.basename(self.file_name),
                        'memory'        : True,
                        'version'       : 3,
                        'collection'    : collision_collection,
                        'only_selected' : False,
                        'mass_export'   : False,
                        'objects'       : collision_objects,
                        'preserve_positions': True if self.force_collision_to_dff_transform else self.preserve_collision_positions,
                        'embedded_local_matrix_world': self.get_exported_collision_frame_matrix_for_export_objects(objects),
                    })
                except RuntimeError as error:
                    print(self.build_embedded_collision_skip_message(name, objects, collision_objects, error))
                    mem = b''

                max_embedded_collision_size = 100 * 1024
                if len(mem) > max_embedded_collision_size:
                    print(
                        'DemonFF SA-MP DFF export: skipped embedded collision for %s because the COL3 chunk is %d bytes after vertex deduplication, over the %d byte SA-MP safety limit. The DFF will still be written without embedded collision.' % (
                            export_name,
                            len(mem),
                            max_embedded_collision_size,
                        )
                    )
                    mem = b''

                if len(mem) != 0:
                    self.dff.collisions = [mem]

        if name is None:
            self.dff.write_file(self.file_name, self.version)
        else:
            os.makedirs(self.path, exist_ok=True)
            filename = os.path.join(self.path, name)
            if not filename.endswith('.dff'):
                filename += '.dff'
            self.dff.write_file(filename, self.version)


    #######################################################
    @staticmethod
    def is_selected(obj):
        if bpy.app.version < (2, 80, 0):
            return obj.select
        return obj.select_get()
            
    #######################################################
    @staticmethod
    def collection_children(collection):
        if bpy.app.version < (2, 80, 0):
            return []
        return list(collection.children)

    @staticmethod
    def walk_collections(collection):
        yield collection
        for child in dff_exporter.collection_children(collection):
            yield from dff_exporter.walk_collections(child)

    @staticmethod
    def is_collision_collection(collection):
        name = collection.name.lower()
        return name.endswith('.col') or '.col.' in name

    @staticmethod
    def split_blender_suffix(name):
        if len(name) > 4 and name[-4] == "." and name[-3:].isdigit():
            return name[:-4], name[-4:]
        return name, ""

    @staticmethod
    def split_export_duplicate_suffix(name):
        name = str(name or "")

        match = re.match(r"^(?P<base>.+?\.dff)(?P<suffix>\.\d{3})(?P<trailing>\.dff)?$", name, re.IGNORECASE)
        if match:
            return match.group("base"), match.group("suffix")

        match = re.match(r"^(?P<base>.+?)(?P<suffix>\.\d{3})(?P<trailing>\.dff)?$", name, re.IGNORECASE)
        if match:
            return match.group("base"), match.group("suffix")

        return name, ""

    @staticmethod
    def get_duplicate_suffix_index(name):
        base, suffix = dff_exporter.split_export_duplicate_suffix(name)
        if not suffix:
            return 0

        try:
            return int(suffix[1:]) + 1
        except Exception:
            return 999999

    @staticmethod
    def strip_dff_export_suffix(name):
        name = os.path.basename(str(name or ""))
        name, suffix = dff_exporter.split_export_duplicate_suffix(name)

        if name.lower().endswith('.dff'):
            name = name[:-4]

        name, suffix = dff_exporter.split_export_duplicate_suffix(name)
        if name.lower().endswith('.dff'):
            name = name[:-4]

        return clear_extension(name)

    @staticmethod
    def get_dff_collection_key(collection_name):
        match = re.match(r"^(?P<base>.+?)\.dff(?P<suffix>\.\d{3})?$", str(collection_name), re.IGNORECASE)
        if not match:
            return None
        return match.group('base').lower(), match.group('suffix') or ""

    @staticmethod
    def get_col_collection_key(collection_name):
        name = str(collection_name or "")
        lower_name = name.lower()

        if '.col.' in lower_name:
            model_part = re.split(r"\.col\.", name, maxsplit=1, flags=re.IGNORECASE)[1]
            model, suffix = dff_exporter.split_blender_suffix(model_part)
            model = dff_exporter.strip_dff_export_suffix(model)
            return model.lower(), suffix

        match = re.match(r"^(?P<base>.+?)\.col(?P<suffix>\.\d{3})?$", name, re.IGNORECASE)
        if match:
            model = dff_exporter.strip_dff_export_suffix(match.group('base'))
            return model.lower(), match.group('suffix') or ""

        return None

    @staticmethod
    def get_collection_parent(target_collection):
        if target_collection is None:
            return None

        scene_collection = bpy.context.scene.collection
        if target_collection.name in scene_collection.children.keys():
            return scene_collection

        for collection in bpy.data.collections:
            if target_collection.name in collection.children.keys():
                return collection

        return None

    @staticmethod
    def get_collection_child_index(parent, child):
        if parent is None or child is None:
            return None

        try:
            for index, collection in enumerate(parent.children):
                if collection == child:
                    return index
        except Exception:
            return None

        return None

    @staticmethod
    def get_collection_collision_objects(collection, recursive=True):
        self = dff_exporter

        if collection is None:
            return []

        objects = []
        seen = set()

        def add_collection_objects(source_collection):
            for obj in source_collection.objects:
                if getattr(getattr(obj, "dff", None), "type", None) not in {"COL", "SHA"}:
                    continue

                key = obj.as_pointer()
                if key in seen:
                    continue

                seen.add(key)
                objects.append(obj)

        add_collection_objects(collection)

        if recursive:
            for child_collection in self.collection_children(collection):
                for nested_collection in self.walk_collections(child_collection):
                    add_collection_objects(nested_collection)

        return objects

    @staticmethod
    def collection_has_collision_objects(collection, recursive=True):
        return len(dff_exporter.get_collection_collision_objects(collection, recursive)) != 0

    @staticmethod
    def get_custom_property(owner, key, default=""):
        try:
            value = owner.get(key, default)
        except Exception:
            value = default
        return value if value is not None else default

    @staticmethod
    def get_collection_source_collection_name(collection):
        return str(dff_exporter.get_custom_property(collection, "demonff_collision_source_collection", ""))

    @staticmethod
    def get_collection_source_model_key(collection):
        value = str(dff_exporter.get_custom_property(collection, "demonff_collision_source_model", ""))
        return dff_exporter.normalize_export_name_key(value) if value else ""

    @staticmethod
    def get_object_source_object_name(obj):
        return str(dff_exporter.get_custom_property(obj, "demonff_collision_source_object", ""))

    @staticmethod
    def get_object_source_model_key(obj):
        value = str(dff_exporter.get_custom_property(obj, "demonff_collision_source_model", ""))
        return dff_exporter.normalize_export_name_key(value) if value else ""

    @staticmethod
    def get_object_2dfx_source_model_key(obj):
        for key in ("demonff_2dfx_source_model", "demonff_2dfx_source_model_key", "demonff_2dfx_source_dff", "DFF_Name"):
            value = str(dff_exporter.get_custom_property(obj, key, ""))
            if value:
                return dff_exporter.normalize_export_name_key(value)
        return ""

    @staticmethod
    def get_object_source_object_key(obj):
        value = str(dff_exporter.get_custom_property(obj, "demonff_collision_source_object_key", ""))
        return dff_exporter.normalize_export_name_key(value) if value else ""

    @staticmethod
    def get_object_source_mesh_key(obj):
        value = str(dff_exporter.get_custom_property(obj, "demonff_collision_source_mesh_key", ""))
        return dff_exporter.normalize_export_name_key(value) if value else ""

    @staticmethod
    def get_collision_objects_matching_export_objects(collision_objects, objects):
        self = dff_exporter
        atomic_objects = [obj for obj in objects if self.is_atomic_export_object(obj)]

        if not atomic_objects:
            return []

        source_names = set(getattr(obj, "name", "") for obj in atomic_objects)
        source_object_keys = set(self.normalize_export_name_key(getattr(obj, "name", "")) for obj in atomic_objects)
        source_mesh_keys = set(self.get_mesh_data_key(obj) for obj in atomic_objects if self.get_mesh_data_key(obj))

        has_stamps = False
        matched = []
        seen = set()

        for collision_object in collision_objects:
            source_name = self.get_object_source_object_name(collision_object)
            source_object_key = self.get_object_source_object_key(collision_object)
            source_mesh_key = self.get_object_source_mesh_key(collision_object)

            if source_name or source_object_key or source_mesh_key:
                has_stamps = True

            if source_name and source_name in source_names:
                key = collision_object.as_pointer()
                if key not in seen:
                    seen.add(key)
                    matched.append(collision_object)
                continue

            if source_object_key and source_object_key in source_object_keys:
                key = collision_object.as_pointer()
                if key not in seen:
                    seen.add(key)
                    matched.append(collision_object)
                continue

            if source_mesh_key and source_mesh_key in source_mesh_keys:
                key = collision_object.as_pointer()
                if key not in seen:
                    seen.add(key)
                    matched.append(collision_object)

        if has_stamps:
            return matched

        return collision_objects

    @staticmethod
    def collection_stamped_for_dff_collection(collision_collection, dff_collection):
        if collision_collection is None or dff_collection is None:
            return False

    @staticmethod
    def collection_name_matches_dff(collection, dff_collection):
        if collection is None or dff_collection is None:
            return False

        dff_key = dff_exporter.get_dff_collection_key(dff_collection.name)
        col_key = dff_exporter.get_col_collection_key(collection.name)

        if dff_key is not None and col_key is not None:
            if col_key == dff_key:
                return True
            if col_key[0] == dff_key[0] and not col_key[1]:
                return True

        if dff_exporter.collection_stamped_for_dff_collection(collection, dff_collection):
            return True

        dff_model_key = dff_exporter.get_collection_model_key(dff_collection)
        col_model_key = dff_exporter.get_collection_model_key(collection)
        col_source_key = dff_exporter.get_collection_source_model_key(collection)

        if col_source_key and col_source_key == dff_model_key:
            return True

        if col_model_key and col_model_key == dff_model_key:
            return True

        return False

    @staticmethod
    def is_embedded_collision_collection_for_dff(collection, dff_collection):
        if collection is None or dff_collection is None:
            return False

        try:
            if bool(collection.get("demonff_embedded_collision", False)):
                return True
        except Exception:
            pass

        dff_key = dff_exporter.get_dff_collection_key(dff_collection.name)
        if dff_key is None:
            return False

        model_name = dff_key[0]
        collection_name = str(collection.name or "").lower()

        # Embedded collision imported from a DFF is named like:
        #   bollardlight.col.bollardlight
        # Generated Duplicate All collision is normally:
        #   bollardlight.col
        # Prefer the original embedded collection when both exist.
        if collection_name.startswith(model_name + ".col."):
            return True

        return False

    @staticmethod
    def sort_collision_collection_for_dff(collection, dff_collection):
        embedded_priority = 0 if dff_exporter.is_embedded_collision_collection_for_dff(collection, dff_collection) else 1
        return (
            embedded_priority,
            dff_exporter.get_duplicate_suffix_index(collection.name),
            collection.name.lower(),
        )

    @staticmethod
    def get_collection_collision_face_count(collection):
        face_count = 0
        for obj in dff_exporter.get_collection_collision_objects(collection, True):
            face_count += dff_exporter.get_mesh_face_count(obj)
        return face_count

    @staticmethod
    def get_valid_collision_child_collections(collection):
        valid_collections = []
        if collection is None:
            return valid_collections

        for child in dff_exporter.collection_children(collection):
            if not dff_exporter.is_collision_collection(child):
                continue
            if not dff_exporter.collection_has_collision_objects(child, True):
                continue
            valid_collections.append(child)

        return valid_collections

    @staticmethod
    def get_valid_collision_sibling_above(dff_collection):
        parent = dff_exporter.get_collection_parent(dff_collection)
        if parent is None:
            return None

        dff_index = dff_exporter.get_collection_child_index(parent, dff_collection)
        if dff_index is None:
            return None

        children = list(parent.children)

        # DragonFF-style layout is immediate/near sibling order:
        #     model.col
        #     model.dff
        # Do not search through an older model's .dff to grab a far-away .col.
        for index in range(dff_index - 1, -1, -1):
            candidate = children[index]

            if dff_exporter.get_dff_collection_key(candidate.name) is not None:
                break

            if not dff_exporter.is_collision_collection(candidate):
                continue

            if not dff_exporter.collection_has_collision_objects(candidate, True):
                continue

            return candidate

        return None

    @staticmethod
    def get_matching_collision_collection(dff_collection):
        if dff_collection is None:
            return None

        # Imported embedded collisions usually sit inside the model collection.
        # That is safer than checking the whole scene because it cannot steal another model's collision.
        child_collections = dff_exporter.get_valid_collision_child_collections(dff_collection)
        child_matches = [
            collection for collection in child_collections
            if dff_exporter.collection_name_matches_dff(collection, dff_collection)
        ]

        if child_matches:
            return sorted(
                child_matches,
                key=lambda collection: dff_exporter.sort_collision_collection_for_dff(collection, dff_collection)
            )[0]

        if len(child_collections) == 1:
            return child_collections[0]

        # Duplicate All as Collision creates the old DragonFF layout above the .dff.
        sibling_above = dff_exporter.get_valid_collision_sibling_above(dff_collection)
        if sibling_above is not None:
            return sibling_above

        # Conservative fallback: only direct siblings with matching names/stamps.
        parent = dff_exporter.get_collection_parent(dff_collection)
        if parent is not None:
            sibling_matches = []
            for collection in parent.children:
                if collection == dff_collection:
                    continue
                if not dff_exporter.is_collision_collection(collection):
                    continue
                if not dff_exporter.collection_has_collision_objects(collection, True):
                    continue
                if not dff_exporter.collection_name_matches_dff(collection, dff_collection):
                    continue
                sibling_matches.append(collection)

            if sibling_matches:
                return sorted(
                    sibling_matches,
                    key=lambda collection: dff_exporter.sort_collision_collection_for_dff(collection, dff_collection)
                )[0]

        return None

    @staticmethod
    def get_collision_export_collection():
        self = dff_exporter

        if self.collection is None:
            return None

        return self.get_matching_collision_collection(self.collection)

    @staticmethod
    def get_dff_type(obj):
        dff_props = getattr(obj, 'dff', None)
        if dff_props is None:
            return None
        return getattr(dff_props, 'type', None)

    @staticmethod
    def is_atomic_export_object(obj):
        if obj.type not in {'MESH', 'EMPTY', 'ARMATURE'}:
            return False
        return dff_exporter.get_dff_type(obj) == 'OBJ'

    @staticmethod
    def is_2dfx_export_object(obj):
        if obj.type not in {'MESH', 'EMPTY', 'LIGHT', 'FONT'}:
            return False
        return dff_exporter.get_dff_type(obj) == '2DFX'

    @staticmethod
    def is_exportable_dff_object(obj):
        return dff_exporter.is_atomic_export_object(obj) or dff_exporter.is_2dfx_export_object(obj)

    @staticmethod
    def walk_exportable_object_collections(collection):
        if collection is None:
            return

        yield collection

        for child in dff_exporter.collection_children(collection):
            if dff_exporter.is_collision_collection(child):
                continue
            yield from dff_exporter.walk_exportable_object_collections(child)

    @staticmethod
    def collection_has_exportable_objects(collection):
        for source_collection in dff_exporter.walk_exportable_object_collections(collection):
            for obj in source_collection.objects:
                if dff_exporter.is_atomic_export_object(obj):
                    return True
        return False

    @staticmethod
    def collection_has_selected_exportable_objects(collection):
        for source_collection in dff_exporter.walk_exportable_object_collections(collection):
            for obj in source_collection.objects:
                if dff_exporter.is_atomic_export_object(obj) and dff_exporter.is_selected(obj):
                    return True
        return False

    @staticmethod
    def collection_has_direct_exportable_objects(collection):
        if collection is None:
            return False

        for obj in collection.objects:
            if dff_exporter.is_atomic_export_object(obj):
                return True
        return False

    @staticmethod
    def collection_has_dff_descendant(collection):
        if collection is None:
            return False

        for child in dff_exporter.collection_children(collection):
            if dff_exporter.get_dff_collection_key(child.name) is not None:
                return True
            if dff_exporter.collection_has_dff_descendant(child):
                return True

        return False

    @staticmethod
    def has_dff_collection_ancestor(collection):
        parent = dff_exporter.get_collection_parent(collection)
        seen = set()

        while parent is not None:
            key = parent.as_pointer()
            if key in seen:
                break
            seen.add(key)

            if dff_exporter.get_dff_collection_key(parent.name) is not None:
                return True

            if parent == bpy.context.scene.collection:
                break

            parent = dff_exporter.get_collection_parent(parent)

        return False

    @staticmethod
    def get_mass_export_collections():
        self = dff_exporter

        if bpy.app.version < (2, 80, 0):
            return [bpy.data]

        root_collection = bpy.context.scene.collection
        collections = []
        seen = set()

        for collection in self.walk_collections(root_collection):
            if collection == root_collection:
                continue

            key = collection.as_pointer()
            if key in seen:
                continue
            seen.add(key)

            if self.is_collision_collection(collection):
                continue

            is_dff_collection = self.get_dff_collection_key(collection.name) is not None

            if not is_dff_collection and self.has_dff_collection_ancestor(collection):
                continue

            if not self.collection_has_exportable_objects(collection):
                continue

            # If this is only an organizer collection containing real .dff children, do not
            # export the organizer as one giant broken DFF.  Export the .dff children.
            if not is_dff_collection and self.collection_has_dff_descendant(collection) and not self.collection_has_direct_exportable_objects(collection):
                continue

            if self.selected and not self.collection_has_selected_exportable_objects(collection):
                continue

            collections.append(collection)

        if not collections and self.collection_has_exportable_objects(root_collection):
            if not self.selected or self.collection_has_selected_exportable_objects(root_collection):
                collections.append(root_collection)

        def collection_sort_key(collection):
            return (
                self.get_collection_model_key(collection),
                self.get_duplicate_suffix_index(collection.name),
                collection.name.lower(),
            )

        sorted_collections = sorted(collections, key=collection_sort_key)

        # Mass export writes one master DFF per model.  Do not even build export
        # groups for duplicate *.dff.001 / *.dff.002 placement collections; doing
        # that caused noisy "no matching .col" reports before the later duplicate
        # output filter had a chance to skip them.
        filtered_collections = []
        exported_dff_model_keys = set()

        for collection in sorted_collections:
            dff_key = self.get_dff_collection_key(collection.name)
            if dff_key is not None:
                model_key = self.normalize_export_name_key(dff_key[0])
                if model_key in exported_dff_model_keys:
                    print('DemonFF mass export: skipped duplicate DFF collection %s before collision matching.' % collection.name)
                    continue
                exported_dff_model_keys.add(model_key)

            filtered_collections.append(collection)

        return filtered_collections

    @staticmethod
    def get_single_export_objects():
        self = dff_exporter
        objects = {}

        if bpy.app.version < (2, 80, 0):
            object_source = bpy.data.objects
        else:
            object_source = bpy.context.scene.objects

        for obj in object_source:
            if not self.is_exportable_dff_object(obj):
                continue

            if self.selected and not self.is_selected(obj):
                continue

            objects[obj] = self.calculate_parent_depth(obj)

        return sorted(objects, key=objects.get)

    @staticmethod
    def get_collection_export_objects(collection):
        self = dff_exporter
        objects = {}
        collection_selected_for_export = self.collection_has_selected_exportable_objects(collection)

        for source_collection in self.walk_exportable_object_collections(collection):
            for obj in source_collection.objects:
                if self.is_atomic_export_object(obj):
                    if self.selected and not self.is_selected(obj):
                        continue
                elif self.is_2dfx_export_object(obj):
                    if self.selected and not collection_selected_for_export and not self.is_selected(obj):
                        continue
                else:
                    continue

                objects[obj] = self.calculate_parent_depth(obj)

        return sorted(objects, key=objects.get)

    @staticmethod
    def get_blender_name_suffix(name):
        match = re.match(r"^(?P<base>.*?)(?P<suffix>\.\d{3})?$", str(name))
        if not match:
            return str(name), ""
        return match.group("base"), match.group("suffix") or ""

    @staticmethod
    def get_export_object_location(obj):
        try:
            return obj.matrix_world.translation.copy()
        except Exception:
            return mathutils.Vector((0.0, 0.0, 0.0))

    @staticmethod
    def get_nearest_atomic_object(obj, atomic_objects):
        if not atomic_objects:
            return None

        obj_location = dff_exporter.get_export_object_location(obj)
        nearest_object = None
        nearest_distance = None

        for atomic in atomic_objects:
            distance = (obj_location - dff_exporter.get_export_object_location(atomic)).length_squared
            if nearest_distance is None or distance < nearest_distance:
                nearest_object = atomic
                nearest_distance = distance

        return nearest_object

    @staticmethod
    def normalize_export_name_key(name):
        name = str(name or "")
        name = os.path.basename(name)
        name = re.sub(r"\.(dff|col)$", "", name, flags=re.IGNORECASE)
        name = dff_exporter.strip_dff_export_suffix(name)
        name = re.sub(r"\.(dff|col)$", "", name, flags=re.IGNORECASE)
        name = re.sub(r"\s+", "", name)
        return name.lower()

    @staticmethod
    def get_object_model_key(obj):
        if obj is None:
            return ""

        for prop_name, field_name in (
            ("dff_map", "model_name"),
            ("dff_map", "ide_model_name"),
            ("ide", "model_name"),
        ):
            props = getattr(obj, prop_name, None)
            if props is None:
                continue
            try:
                value = getattr(props, field_name, "")
            except Exception:
                value = ""
            if value:
                return dff_exporter.normalize_export_name_key(value)

        for key in ("DFF_Name", "IDE_Model_Name", "model_name", "Model_Name"):
            try:
                value = obj.get(key, "")
            except Exception:
                value = ""
            if value:
                return dff_exporter.normalize_export_name_key(value)

        return dff_exporter.normalize_export_name_key(obj.name)

    @staticmethod
    def get_mesh_data_key(obj):
        data = getattr(obj, "data", None)
        if data is None:
            return ""
        return dff_exporter.normalize_export_name_key(getattr(data, "name", ""))

    @staticmethod
    def get_object_piece_key(obj):
        data = getattr(obj, "data", None)

        try:
            vertex_count = len(data.vertices)
        except Exception:
            vertex_count = 0

        try:
            face_count = len(data.polygons)
        except Exception:
            face_count = 0

        return (
            dff_exporter.get_mesh_data_key(obj),
            vertex_count,
            face_count,
        )

    @staticmethod
    def get_unique_root_atomic_objects(collection, root_objects):
        self = dff_exporter
        kept_roots = []
        used_piece_keys = set()
        skipped_roots = []

        for obj in sorted(root_objects, key=self.choose_master_atomic_object_sort_key):
            piece_key = self.get_object_piece_key(obj)
            if piece_key in used_piece_keys:
                skipped_roots.append(obj)
                continue
            used_piece_keys.add(piece_key)
            kept_roots.append(obj)

        return kept_roots, skipped_roots

    @staticmethod
    def get_unique_export_objects_for_real_dff_collection(collection, objects):
        self = dff_exporter

        if self.get_dff_collection_key(collection.name) is None:
            return objects

        root_objects = self.get_root_atomic_objects_from_export_objects(objects)
        if len(root_objects) <= 1:
            return objects

        kept_roots, skipped_roots = self.get_unique_root_atomic_objects(collection, root_objects)
        if not skipped_roots:
            return objects

        result = []
        seen = set()

        def add_object(obj):
            if obj is None:
                return
            key = obj.as_pointer()
            if key in seen:
                return
            seen.add(key)
            result.append(obj)

        all_root_objects = root_objects
        for root in kept_roots:
            for obj in self.get_atomic_descendants_for_export(collection, root):
                if obj in objects:
                    add_object(obj)
            for obj in self.get_effect_objects_for_atomic(collection, root, all_root_objects):
                if obj in objects:
                    add_object(obj)

        # Keep non-atomic frame helpers that were part of the original export list.
        for obj in objects:
            if self.is_atomic_export_object(obj) or self.is_2dfx_export_object(obj):
                continue
            add_object(obj)

        skipped_text = ", ".join(getattr(obj, "name", "<unnamed>") for obj in skipped_roots[:8])
        if len(skipped_roots) > 8:
            skipped_text += ", ..."

        print(
            "DemonFF SA-MP DFF export: ignored %d repeated duplicate object(s) inside %s; using %d unique source object(s). Skipped: %s" % (
                len(skipped_roots),
                collection.name,
                len(kept_roots),
                skipped_text if skipped_text else "<none>",
            )
        )

        return sorted(result, key=self.calculate_parent_depth)

    @staticmethod
    def get_collection_model_key(collection):
        if collection is None:
            return ""

        dff_key = dff_exporter.get_dff_collection_key(collection.name)
        if dff_key is not None:
            return dff_exporter.normalize_export_name_key(dff_key[0])

        return dff_exporter.normalize_export_name_key(collection.name)

    @staticmethod
    def is_object_in_collection(obj, collection):
        if obj is None or collection is None:
            return False
        try:
            return obj.name in collection.objects.keys()
        except Exception:
            return obj in collection.objects[:]

    @staticmethod
    def object_has_atomic_parent_in_collection(obj, collection):
        parent = getattr(obj, "parent", None)
        while parent is not None:
            if dff_exporter.is_object_in_collection(parent, collection) and dff_exporter.is_atomic_export_object(parent):
                return True
            parent = getattr(parent, "parent", None)
        return False

    @staticmethod
    def is_descendant_of_object(obj, root):
        parent = getattr(obj, "parent", None)
        while parent is not None:
            if parent == root:
                return True
            parent = getattr(parent, "parent", None)
        return False

    @staticmethod
    def get_collection_atomic_objects(collection, selected_only=False):
        self = dff_exporter
        atomic_objects = []
        seen = set()

        for source_collection in self.walk_exportable_object_collections(collection):
            for obj in source_collection.objects:
                if not self.is_atomic_export_object(obj):
                    continue
                if selected_only and not self.is_selected(obj):
                    continue
                key = obj.as_pointer()
                if key in seen:
                    continue
                seen.add(key)
                atomic_objects.append(obj)

        return atomic_objects

    @staticmethod
    def get_collection_root_atomic_objects(collection, selected_only=False):
        self = dff_exporter
        root_objects = []

        for obj in self.get_collection_atomic_objects(collection, selected_only):
            if self.object_has_atomic_parent_in_collection(obj, collection):
                continue
            root_objects.append(obj)

        return root_objects

    @staticmethod
    def get_primary_collection_for_export_objects(objects):
        self = dff_exporter

        atomic_objects = [obj for obj in objects if self.is_atomic_export_object(obj)]
        if not atomic_objects:
            return None

        candidates = []
        seen = set()

        for obj in atomic_objects:
            for collection in getattr(obj, "users_collection", []):
                if collection is None or self.is_collision_collection(collection):
                    continue

                key = collection.as_pointer()
                if key in seen:
                    continue
                seen.add(key)

                score = 0
                if self.get_dff_collection_key(collection.name) is not None:
                    score -= 100
                if self.get_collection_model_key(collection) == self.get_object_model_key(obj):
                    score -= 50
                if self.collection_has_exportable_objects(collection):
                    score -= 10

                candidates.append((score, collection.name.lower(), collection))

        if not candidates:
            return None

        return sorted(candidates, key=lambda item: (item[0], item[1]))[0][2]

    @staticmethod
    def get_root_atomic_objects_from_export_objects(objects):
        self = dff_exporter
        object_set = set(objects)
        root_objects = []

        for obj in objects:
            if not self.is_atomic_export_object(obj):
                continue

            parent = getattr(obj, "parent", None)
            has_export_parent = False
            while parent is not None:
                if parent in object_set and self.is_atomic_export_object(parent):
                    has_export_parent = True
                    break
                parent = getattr(parent, "parent", None)

            if not has_export_parent:
                root_objects.append(obj)

        return root_objects

    @staticmethod
    def get_mesh_face_count(obj):
        data = getattr(obj, "data", None)
        if data is None:
            return 0
        try:
            return len(data.polygons)
        except Exception:
            return 0

    @staticmethod
    def get_exported_collision_frame_matrix_for_object(obj):
        self = dff_exporter

        try:
            source_matrix = obj.matrix_world.copy()
        except Exception:
            return mathutils.Matrix.Identity(4)

        if self.force_collision_to_dff_transform:
            return source_matrix

        if self.preserve_positions:
            return source_matrix

        frame_matrix = source_matrix.copy()
        frame_matrix.translation = mathutils.Vector((0.0, 0.0, 0.0))
        return frame_matrix

    @staticmethod
    def get_exported_collision_frame_matrix_for_export_objects(objects):
        self = dff_exporter

        for obj in objects:
            try:
                if obj.type == 'MESH' and obj.dff.type == 'OBJ':
                    matrix = self.get_exported_collision_frame_matrix_for_object(obj)
                    return [list(row) for row in matrix]
            except Exception:
                continue

        for obj in objects:
            try:
                if obj.dff.type == 'OBJ':
                    matrix = self.get_exported_collision_frame_matrix_for_object(obj)
                    return [list(row) for row in matrix]
            except Exception:
                continue

        return None

    @staticmethod
    def get_object_debug_name(obj):
        return getattr(obj, "name", "<unnamed>")

    @staticmethod
    def build_embedded_collision_skip_message(name, dff_objects, collision_objects, error):
        self = dff_exporter
        export_name = name if name is not None else os.path.basename(self.file_name)
        dff_names = [self.get_object_debug_name(obj) for obj in dff_objects if self.is_atomic_export_object(obj)]
        col_names = [self.get_object_debug_name(obj) for obj in collision_objects]
        largest_collision = None
        largest_faces = -1

        for obj in collision_objects:
            face_count = self.get_mesh_face_count(obj)
            if face_count > largest_faces:
                largest_faces = face_count
                largest_collision = obj

        if largest_collision is not None:
            largest_text = " Largest collision object: {0} ({1} mesh faces).".format(
                self.get_object_debug_name(largest_collision),
                largest_faces
            )
        else:
            largest_text = ""

        return (
            "DemonFF SA-MP DFF export: skipped embedded collision for {0}: {1}.{2} "
            "DFF object(s): {3}. Collision object(s): {4}."
        ).format(
            export_name,
            error,
            largest_text,
            ", ".join(dff_names) if dff_names else "<none>",
            ", ".join(col_names) if col_names else "<none>",
        )

    @staticmethod
    def get_collision_objects_for_export_objects(collection, objects):
        self = dff_exporter

        if collection is None:
            return []

        collision_collection = self.get_matching_collision_collection(collection)
        if collision_collection is None:
            print('DemonFF SA-MP DFF export: no matching .col collection found for %s; exporting DFF without embedded collision.' % collection.name)
            return []

        all_collision_objects = self.get_collection_collision_objects(collision_collection, True)
        if not all_collision_objects:
            print('DemonFF SA-MP DFF export: matching .col collection %s has no collision objects.' % collision_collection.name)
            return []

        roots = self.get_root_atomic_objects_from_export_objects(objects)

        # For a real model collection, the sibling *.col collection is the collision
        # for this DFF.  If Duplicate All as Collision stamped source objects, keep
        # only the collision pieces that belong to the source objects being exported.
        # This stops repeated map instances like bollardlight.001/.002 from being
        # shoved into the one master bollardlight.dff.
        if self.get_dff_collection_key(collection.name) is not None:
            matched_collision_objects = self.get_collision_objects_matching_export_objects(all_collision_objects, objects)
            if len(matched_collision_objects) != len(all_collision_objects):
                print(
                    'DemonFF SA-MP DFF export: ignored %d repeated collision duplicate(s) from %s for %s.' % (
                        len(all_collision_objects) - len(matched_collision_objects),
                        collision_collection.name,
                        collection.name,
                    )
                )
            return matched_collision_objects

        if len(roots) <= 1:
            return all_collision_objects

        collision_objects = []
        seen = set()

        for root in roots:
            assigned_objects = self.get_collision_objects_for_atomic(collection, root)
            if not assigned_objects:
                continue

            for obj in assigned_objects:
                key = obj.as_pointer()
                if key in seen:
                    continue
                seen.add(key)
                collision_objects.append(obj)

        return collision_objects

    @staticmethod
    def collection_needs_instance_split(collection):
        self = dff_exporter

        # A real imported model collection named *.dff is already the export unit.
        # Splitting it by root atomics breaks multi-piece models, drops some 2DFX,
        # and can leave the embedded collision incomplete.
        if self.get_dff_collection_key(collection.name) is not None:
            return False

        root_objects = self.get_collection_root_atomic_objects(collection, False)

        if len(root_objects) <= 1:
            return False

        # Only loose organizer collections need this split.
        if self.mass_export and self.export_coll:
            return True

        by_model_key = defaultdict(list)
        for obj in root_objects:
            by_model_key[self.get_object_model_key(obj)].append(obj)

        if any(len(objects) > 1 for objects in by_model_key.values()):
            return True

        collection_key = self.get_collection_model_key(collection)
        if collection_key and len(by_model_key.get(collection_key, [])) > 1:
            return True

        return False

    @staticmethod
    def get_collision_objects_for_atomic(collection, atomic_object):
        self = dff_exporter
        collision_collection = self.get_matching_collision_collection(collection)
        if collision_collection is None:
            return None

        collision_objects = self.get_collection_collision_objects(collision_collection, True)

        if not collision_objects:
            return []

        atomic_source_name = getattr(atomic_object, "name", "")
        atomic_model_key = self.get_object_model_key(atomic_object)

        stamped_object_matches = []
        stamped_model_matches = []
        has_collision_stamps = False

        for collision_object in collision_objects:
            source_object_name = self.get_object_source_object_name(collision_object)
            source_model_key = self.get_object_source_model_key(collision_object)

            if source_object_name or source_model_key:
                has_collision_stamps = True

            if source_object_name and source_object_name == atomic_source_name:
                stamped_object_matches.append(collision_object)
                continue

            if source_model_key and source_model_key == atomic_model_key:
                stamped_model_matches.append(collision_object)

        if stamped_model_matches:
            return stamped_model_matches

        if stamped_object_matches:
            return stamped_object_matches

        if has_collision_stamps:
            return []

        root_atomic_objects = self.get_collection_root_atomic_objects(collection, False)
        if not root_atomic_objects:
            root_atomic_objects = [obj for obj in collection.objects if self.is_atomic_export_object(obj)]

        if len(root_atomic_objects) <= 1:
            return collision_objects

        assigned_objects = []
        for collision_object in collision_objects:
            nearest_object = self.get_nearest_atomic_object(collision_object, root_atomic_objects)
            if nearest_object == atomic_object:
                assigned_objects.append(collision_object)

        return assigned_objects

    @staticmethod
    def get_effect_target_model_keys(objects, export_name=None):
        self = dff_exporter
        keys = set()

        if export_name:
            key = self.normalize_export_name_key(export_name)
            if key:
                keys.add(key)

        for obj in objects:
            if not self.is_atomic_export_object(obj):
                continue

            for key in (
                self.get_object_model_key(obj),
                self.get_object_source_model_key(obj),
                self.normalize_export_name_key(getattr(obj, "name", "")),
            ):
                if key:
                    keys.add(key)

        return keys

    @staticmethod
    def get_effect_objects_for_atomic(collection, atomic_object, all_root_atomic_objects, target_model_keys=None, allow_unstamped=False):
        self = dff_exporter
        assigned_objects = []
        atomic_model_key = self.get_object_model_key(atomic_object)
        atomic_source_model_key = self.get_object_source_model_key(atomic_object)

        valid_model_keys = set()
        for key in (atomic_model_key, atomic_source_model_key):
            if key:
                valid_model_keys.add(key)

        if target_model_keys:
            valid_model_keys.update(target_model_keys)

        for source_collection in self.walk_exportable_object_collections(collection):
            for obj in source_collection.objects:
                if not self.is_2dfx_export_object(obj):
                    continue

                source_model_key = self.get_object_2dfx_source_model_key(obj)
                if source_model_key and valid_model_keys and source_model_key not in valid_model_keys:
                    continue

                if source_model_key and not valid_model_keys:
                    continue

                if not source_model_key and not allow_unstamped:
                    continue

                if self.is_descendant_of_object(obj, atomic_object):
                    assigned_objects.append(obj)
                    continue

                nearest_object = self.get_nearest_atomic_object(obj, all_root_atomic_objects)
                if nearest_object == atomic_object:
                    assigned_objects.append(obj)

        return assigned_objects

    @staticmethod
    def add_unique_object(result, seen, obj):
        if obj is None:
            return

        try:
            key = obj.as_pointer()
        except Exception:
            key = id(obj)

        if key in seen:
            return

        seen.add(key)
        result.append(obj)

    @staticmethod
    def add_matching_2dfx_object(result, seen, obj, target_model_keys, allow_unstamped):
        self = dff_exporter

        if not self.is_2dfx_export_object(obj):
            return

        source_model_key = self.get_object_2dfx_source_model_key(obj)
        if source_model_key:
            if source_model_key in target_model_keys:
                self.add_unique_object(result, seen, obj)
            return

        if allow_unstamped:
            self.add_unique_object(result, seen, obj)

    @staticmethod
    def collection_has_stamped_2dfx(collection):
        self = dff_exporter

        if collection is None:
            return False

        for source_collection in self.walk_exportable_object_collections(collection):
            for obj in source_collection.objects:
                if self.is_2dfx_export_object(obj) and self.get_object_2dfx_source_model_key(obj):
                    return True

        return False

    @staticmethod
    def get_2dfx_effect_id(obj):
        try:
            return int(obj.dff.ext_2dfx.effect)
        except Exception:
            return -1

    @staticmethod
    def get_2dfx_local_location(obj, root_objects):
        self = dff_exporter
        nearest_object = self.get_nearest_atomic_object(obj, root_objects)

        try:
            location = obj.matrix_world.translation.copy()
        except Exception:
            location = mathutils.Vector(obj.location)

        if nearest_object is None:
            return location

        try:
            return nearest_object.matrix_world.inverted() @ location
        except Exception:
            return location

    @staticmethod
    def get_2dfx_light_signature_values(obj):
        values = []

        try:
            values.extend(round(float(v), 4) for v in obj.data.color)
        except Exception:
            pass

        settings = getattr(getattr(obj, "data", None), "ext_2dfx", None)
        if settings is not None:
            for name in (
                "alpha",
                "corona_far_clip",
                "point_light_range",
                "corona_size",
                "shadow_size",
                "corona_show_mode",
                "corona_enable_reflection",
                "corona_flare_type",
                "shadow_color_multiplier",
                "corona_tex_name",
                "shadow_tex_name",
                "shadow_z_distance",
                "flag1_corona_check_obstacles",
                "flag1_fog_type",
                "flag1_without_corona",
                "flag1_corona_only_at_long_distance",
                "flag1_at_day",
                "flag1_at_night",
                "flag1_blinking1",
                "flag2_corona_only_from_below",
                "flag2_blinking2",
                "flag2_udpdate_height_above_ground",
                "flag2_check_view_vector",
                "flag2_blinking3",
            ):
                try:
                    value = getattr(settings, name)
                except Exception:
                    continue

                if isinstance(value, float):
                    value = round(value, 4)

                values.append((name, value))

        return tuple(values)

    @staticmethod
    def get_2dfx_signature(obj, root_objects):
        self = dff_exporter
        local = self.get_2dfx_local_location(obj, root_objects)

        signature = [
            self.get_2dfx_effect_id(obj),
            round(float(local.x), 3),
            round(float(local.y), 3),
            round(float(local.z), 3),
        ]

        if getattr(obj, "type", None) == "LIGHT":
            signature.append(self.get_2dfx_light_signature_values(obj))
        else:
            settings = getattr(getattr(obj, "dff", None), "ext_2dfx", None)
            if settings is not None:
                for name in ("val_str24_1", "val_str8_1", "val_float_1", "val_float_2", "val_byte_1", "val_byte_2", "val_byte_3", "val_byte_4"):
                    try:
                        value = getattr(settings, name)
                    except Exception:
                        continue
                    if isinstance(value, float):
                        value = round(value, 4)
                    signature.append((name, value))

        return tuple(signature)

    @staticmethod
    def dedupe_2dfx_objects(effect_objects, root_objects):
        self = dff_exporter
        result = []
        seen = set()
        skipped = 0

        for obj in effect_objects:
            signature = self.get_2dfx_signature(obj, root_objects)
            if signature in seen:
                skipped += 1
                continue

            seen.add(signature)
            result.append(obj)

        if skipped:
            print("DemonFF SA-MP DFF export verify: skipped %d duplicate 2DFX object(s) after local-signature dedupe." % skipped)

        return result

    @staticmethod
    def get_2dfx_location_overrides(effect_objects, root_objects):
        self = dff_exporter
        overrides = {}

        for obj in effect_objects:
            try:
                key = obj.as_pointer()
            except Exception:
                key = id(obj)

            overrides[key] = self.get_2dfx_local_location(obj, root_objects)

        return overrides

    @staticmethod
    def get_effect_objects_for_export(objects, export_name=None):
        self = dff_exporter

        result = []
        seen = set()
        target_model_keys = self.get_effect_target_model_keys(objects, export_name)

        stamped_objects_exist = self.collection_has_stamped_2dfx(self.collection)
        allow_unstamped = not stamped_objects_exist

        for obj in objects:
            self.add_matching_2dfx_object(result, seen, obj, target_model_keys, True)

        root_objects = self.get_root_atomic_objects_from_export_objects(objects)

        if self.collection is None or not root_objects:
            return self.dedupe_2dfx_objects(sorted(result, key=self.calculate_parent_depth), root_objects)

        all_root_objects = self.get_collection_root_atomic_objects(self.collection, False)
        if not all_root_objects:
            all_root_objects = root_objects

        for root in root_objects:
            for obj in self.get_effect_objects_for_atomic(
                self.collection,
                root,
                all_root_objects,
                target_model_keys,
                allow_unstamped
            ):
                self.add_unique_object(result, seen, obj)

        return self.dedupe_2dfx_objects(sorted(result, key=self.calculate_parent_depth), root_objects)

    @staticmethod
    def count_2dfx_entries(extension):
        try:
            return len(extension.entries)
        except Exception:
            return 0

    @staticmethod
    def get_export_verify_counts(objects, effect_objects):
        self = dff_exporter

        return {
            "objects": len(objects),
            "atomic_objects": sum(1 for obj in objects if self.is_atomic_export_object(obj)),
            "explicit_2dfx_objects": sum(1 for obj in objects if self.is_2dfx_export_object(obj)),
            "resolved_2dfx_objects": len(effect_objects),
            "resolved_2dfx_lights": sum(1 for obj in effect_objects if self.is_2dfx_light_object(obj)),
            "resolved_text_ide_2dfx_objects": sum(1 for obj in effect_objects if bool(obj.get("demonff_text_ide_2dfx", False))),
            "non_blender_light_2dfx_lights": sum(1 for obj in effect_objects if self.is_2dfx_light_object(obj) and getattr(obj, "type", None) != 'LIGHT'),
            "2dfx_entries": self.count_2dfx_entries(self.dff.ext_2dfx),
            "rw_light_structs": len(getattr(self.dff, "light_list", [])),
            "skipped_imported_2dfx_light_frames": getattr(self, "skipped_imported_2dfx_light_frames", 0),
            "geometries": len(self.dff.geometry_list),
            "atomics": len(self.dff.atomic_list),
            "frames": len(self.dff.frame_list),
        }

    @staticmethod
    def get_2dfx_effect_id(obj):
        try:
            return int(obj.dff.ext_2dfx.effect)
        except Exception:
            return -1

    @staticmethod
    def is_2dfx_light_object(obj):
        self = dff_exporter

        if obj is None:
            return False

        if not self.is_2dfx_export_object(obj):
            return False

        return self.get_2dfx_effect_id(obj) == 0

    @staticmethod
    def get_object_world_location(obj):
        try:
            return obj.matrix_world.translation.copy()
        except Exception:
            return mathutils.Vector(getattr(obj, "location", (0.0, 0.0, 0.0)))

    @staticmethod
    def has_atomic_export_child(obj):
        self = dff_exporter

        try:
            children = obj.children
        except Exception:
            return False

        for child in children:
            if self.is_atomic_export_object(child):
                return True

        return False

    @staticmethod
    def is_redundant_imported_2dfx_light_frame(obj, effect_objects):
        self = dff_exporter

        if obj is None or obj.type != 'EMPTY':
            return False

        if self.is_2dfx_export_object(obj):
            return False

        if self.get_dff_type(obj) != 'OBJ':
            return False

        if self.has_atomic_export_child(obj):
            return False

        obj_location = self.get_object_world_location(obj)

        for effect_object in effect_objects:
            if not self.is_2dfx_light_object(effect_object):
                continue

            effect_location = self.get_object_world_location(effect_object)

            if (obj_location - effect_location).length <= 0.05:
                return True

        return False

    @staticmethod
    def get_2dfx_light_alpha(obj):
        try:
            settings = getattr(getattr(obj, "data", None), "ext_2dfx", None)
            if settings is None:
                settings = obj.dff.ext_2dfx
            alpha = float(settings.alpha)
        except Exception:
            alpha = 1.0

        if alpha <= 1.0:
            alpha *= 255.0

        if alpha < 0.0:
            alpha = 0.0

        if alpha > 255.0:
            alpha = 255.0

        return alpha

    @staticmethod
    def get_2dfx_light_color(obj):
        try:
            color = obj.data.color
            return (
                max(0.0, min(1.0, float(color[0]))),
                max(0.0, min(1.0, float(color[1]))),
                max(0.0, min(1.0, float(color[2]))),
            )
        except Exception:
            return (1.0, 1.0, 1.0)

    @staticmethod
    def get_2dfx_light_parent_object(obj, atomic_objects):
        self = dff_exporter

        parent = self.get_object_parent(obj)
        if parent in self.frame_objects:
            return parent

        nearest = self.get_nearest_atomic_object(obj, atomic_objects)
        if nearest in self.frame_objects:
            return nearest

        return None

    @staticmethod
    def make_2dfx_light_frame(obj, parent_obj):
        self = dff_exporter

        frame = dff_samp.Frame()

        try:
            source_matrix = obj.matrix_world.copy()
        except Exception:
            source_matrix = mathutils.Matrix.Translation(obj.location)

        if parent_obj is not None:
            try:
                frame_matrix = parent_obj.matrix_world.inverted() @ source_matrix
            except Exception:
                frame_matrix = source_matrix
            parent_frame = self.frame_objects.get(parent_obj, -1)
        else:
            frame_matrix = source_matrix
            parent_frame = -1

        frame.position = frame_matrix.to_translation()
        frame.rotation_matrix = dff_samp.Matrix._make(mathutils.Matrix.Identity(3))
        frame.parent = parent_frame
        frame.creation_flags = 3
        frame.name = self.truncate_frame_name(getattr(obj, "name", "Light"))

        return frame

    @staticmethod
    def export_2dfx_light_structs(effect_objects, objects):
        self = dff_exporter

        atomic_objects = [obj for obj in objects if self.is_atomic_export_object(obj)]
        written_lights = 0

        for obj in effect_objects:
            if not self.is_2dfx_light_object(obj):
                continue

            parent_obj = self.get_2dfx_light_parent_object(obj, atomic_objects)
            frame = self.make_2dfx_light_frame(obj, parent_obj)

            self.dff.frame_list.append(frame)
            light_frame_index = self.get_last_frame_index()

            light = dff_samp.Light()
            light.frame = light_frame_index
            light.radius = self.get_2dfx_light_alpha(obj)
            light.color = self.get_2dfx_light_color(obj)
            light.minus_cos_angle = 0.0
            light.flags = 0x00800003

            self.dff.light_list.append(light)
            written_lights += 1

        return written_lights

    @staticmethod
    def print_export_verify(export_name, counts):
        print(
            "DemonFF SA-MP DFF export verify: %s: objects=%d, atomic_objects=%d, explicit_2dfx_objects=%d, resolved_2dfx_objects=%d, resolved_2dfx_lights=%d, non_blender_light_2dfx_lights=%d, written_2dfx_entries=%d, rw_light_structs=%d, skipped_imported_2dfx_light_frames=%d, frames=%d, geometries=%d, atomics=%d." % (
                export_name,
                counts.get("objects", 0),
                counts.get("atomic_objects", 0),
                counts.get("explicit_2dfx_objects", 0),
                counts.get("resolved_2dfx_objects", 0),
                counts.get("resolved_2dfx_lights", 0),
                counts.get("non_blender_light_2dfx_lights", 0),
                counts.get("2dfx_entries", 0),
                counts.get("rw_light_structs", 0),
                counts.get("skipped_imported_2dfx_light_frames", 0),
                counts.get("frames", 0),
                counts.get("geometries", 0),
                counts.get("atomics", 0),
            )
        )

        if counts.get("resolved_2dfx_objects", 0) != counts.get("2dfx_entries", 0):
            message = (
                "DemonFF SA-MP DFF export refused %s: resolved %d 2DFX object(s), but serialized %d 2DFX entrie(s). "
                "The DFF was not allowed to continue because exporting it would strip or duplicate 2DFX data."
                % (
                    export_name,
                    counts.get("resolved_2dfx_objects", 0),
                    counts.get("2dfx_entries", 0),
                )
            )
            print(message)
            raise DffExportException(message)

        if counts.get("resolved_text_ide_2dfx_objects", 0) > 0 and counts.get("2dfx_entries", 0) == 0:
            message = (
                "DemonFF SA-MP DFF export refused %s: ReLCS text-IDE 2DFX objects were found, but no RenderWare 2DFX extension entries were written."
                % export_name
            )
            print(message)
            raise DffExportException(message)

        if counts.get("resolved_2dfx_lights", 0) != counts.get("rw_light_structs", 0):
            print(
                "DemonFF SA-MP DFF export warning: %s resolved %d 2DFX light(s), but wrote %d RW Light struct(s)." % (
                    export_name,
                    counts.get("resolved_2dfx_lights", 0),
                    counts.get("rw_light_structs", 0),
                )
            )

    @staticmethod
    def add_export_totals(totals, counts):
        for key in ("objects", "atomic_objects", "explicit_2dfx_objects", "resolved_2dfx_objects", "resolved_2dfx_lights", "non_blender_light_2dfx_lights", "2dfx_entries", "rw_light_structs", "skipped_imported_2dfx_light_frames", "frames", "geometries", "atomics"):
            totals[key] = totals.get(key, 0) + counts.get(key, 0)

    @staticmethod
    def print_mass_export_verify(exported_count, candidate_count, totals):
        print(
            "DemonFF SA-MP DFF mass export verify: dffs_written=%d, candidates=%d, objects=%d, atomic_objects=%d, explicit_2dfx_objects=%d, resolved_2dfx_objects=%d, resolved_2dfx_lights=%d, non_blender_light_2dfx_lights=%d, written_2dfx_entries=%d, rw_light_structs=%d, skipped_imported_2dfx_light_frames=%d, frames=%d, geometries=%d, atomics=%d." % (
                exported_count,
                candidate_count,
                totals.get("objects", 0),
                totals.get("atomic_objects", 0),
                totals.get("explicit_2dfx_objects", 0),
                totals.get("resolved_2dfx_objects", 0),
                totals.get("resolved_2dfx_lights", 0),
                totals.get("non_blender_light_2dfx_lights", 0),
                totals.get("2dfx_entries", 0),
                totals.get("rw_light_structs", 0),
                totals.get("skipped_imported_2dfx_light_frames", 0),
                totals.get("frames", 0),
                totals.get("geometries", 0),
                totals.get("atomics", 0),
            )
        )

        if totals.get("resolved_2dfx_objects", 0) != totals.get("2dfx_entries", 0):
            print(
                "DemonFF SA-MP DFF mass export warning: resolved %d 2DFX object(s), but wrote %d 2DFX entrie(s)." % (
                    totals.get("resolved_2dfx_objects", 0),
                    totals.get("2dfx_entries", 0),
                )
            )

    @staticmethod
    def get_atomic_descendants_for_export(collection, atomic_object):
        self = dff_exporter
        objects = [atomic_object]

        for obj in collection.objects:
            if obj == atomic_object:
                continue
            if not self.is_atomic_export_object(obj):
                continue
            if self.is_descendant_of_object(obj, atomic_object):
                objects.append(obj)

        return objects

    @staticmethod
    def get_atomic_export_file_name(atomic_object):
        self = dff_exporter

        for prop_name, field_name in (
            ("dff_map", "model_name"),
            ("dff_map", "ide_model_name"),
            ("ide", "model_name"),
        ):
            props = getattr(atomic_object, prop_name, None)
            if props is None:
                continue
            try:
                value = getattr(props, field_name, "")
            except Exception:
                value = ""
            if value:
                return self.clean_export_collection_name(clear_extension(os.path.basename(str(value))))

        for key in ("DFF_Name", "IDE_Model_Name", "model_name", "Model_Name"):
            try:
                value = atomic_object.get(key, "")
            except Exception:
                value = ""
            if value:
                return self.clean_export_collection_name(clear_extension(os.path.basename(str(value))))

        base_name, suffix = self.split_blender_suffix(atomic_object.name)
        return self.clean_export_collection_name(clear_extension(base_name))

    @staticmethod
    def choose_master_atomic_object_sort_key(obj):
        self = dff_exporter
        base_name, suffix = self.split_blender_suffix(obj.name)
        suffix_index = 0
        if suffix:
            try:
                suffix_index = int(suffix[1:]) + 1
            except Exception:
                suffix_index = 999999
        return (suffix_index, base_name.lower(), obj.name.lower())

    @staticmethod
    def choose_master_atomic_object(objects):
        self = dff_exporter
        return sorted(objects, key=self.choose_master_atomic_object_sort_key)[0]

    @staticmethod
    def get_collection_export_groups(collection):
        self = dff_exporter

        if not self.collection_needs_instance_split(collection):
            objects = self.get_collection_export_objects(collection)
            if not objects:
                return []
            objects = self.get_unique_export_objects_for_real_dff_collection(collection, objects)
            if not objects:
                return []
            collision_objects = self.get_collision_objects_for_export_objects(collection, objects)
            return [(self.clean_export_collection_name(collection.name), objects, collision_objects)]

        all_root_objects = self.get_collection_root_atomic_objects(collection, False)
        if not all_root_objects:
            return []

        selected_root_objects = self.get_collection_root_atomic_objects(collection, self.selected)
        if self.selected and not selected_root_objects:
            return []

        export_model_keys = set()
        if self.selected:
            for atomic_object in selected_root_objects:
                export_model_keys.add(self.get_object_model_key(atomic_object))
        else:
            for atomic_object in all_root_objects:
                export_model_keys.add(self.get_object_model_key(atomic_object))

        root_objects_by_model = defaultdict(list)
        for atomic_object in all_root_objects:
            model_key = self.get_object_model_key(atomic_object)
            if model_key in export_model_keys:
                root_objects_by_model[model_key].append(atomic_object)

        groups = []
        used_names = set()

        for model_key in sorted(root_objects_by_model):
            model_objects = root_objects_by_model[model_key]
            if not model_objects:
                continue

            master_object = self.choose_master_atomic_object(model_objects)
            export_name = self.get_atomic_export_file_name(master_object)
            export_name_key = export_name.lower()

            if export_name_key in used_names:
                continue
            used_names.add(export_name_key)

            export_objects = self.get_atomic_descendants_for_export(collection, master_object)
            export_objects.extend(self.get_effect_objects_for_atomic(collection, master_object, all_root_objects))
            export_objects = sorted(set(export_objects), key=self.calculate_parent_depth)

            collision_objects = self.get_collision_objects_for_atomic(collection, master_object)
            groups.append((export_name, export_objects, collision_objects))

        return groups

    @staticmethod
    def clean_export_collection_name(name):
        name = dff_exporter.strip_dff_export_suffix(name)
        if not name:
            name = 'unnamed'
        return name + '.dff'

    @staticmethod
    def get_export_file_key(export_name):
        return dff_exporter.normalize_export_name_key(export_name)

    @staticmethod
    def get_export_group_sort_key(collection, export_name, objects):
        suffix_index = dff_exporter.get_duplicate_suffix_index(collection.name if collection is not None else export_name)

        for obj in objects:
            if dff_exporter.is_atomic_export_object(obj):
                suffix_index = min(suffix_index, dff_exporter.get_duplicate_suffix_index(obj.name))

        return (
            dff_exporter.get_export_file_key(export_name),
            suffix_index,
            collection.name.lower() if collection is not None else '',
            str(export_name).lower(),
        )

    @staticmethod
    def reset_export_state():
        self = dff_exporter
        self.frame_objects = {}
        self.bones = {}
        self.parent_queue = {}
        self.last_export_verify = {}
        self.skipped_imported_2dfx_light_frames = 0

    @staticmethod
    def export_dff(filename):
        self = dff_exporter

        self.file_name = filename

        if self.mass_export:
            if not self.path:
                self.path = os.path.dirname(filename)
            if not self.path:
                self.path = os.getcwd()
            os.makedirs(self.path, exist_ok=True)

            export_candidates = []
            for collection in self.get_mass_export_collections():
                export_groups = self.get_collection_export_groups(collection)

                for export_name, objects, collision_objects in export_groups:
                    if not objects:
                        continue

                    export_candidates.append((
                        self.get_export_group_sort_key(collection, export_name, objects),
                        collection,
                        export_name,
                        objects,
                        collision_objects,
                    ))

            exported_count = 0
            exported_model_keys = set()
            export_totals = {}

            for sort_key, collection, export_name, objects, collision_objects in sorted(export_candidates, key=lambda item: item[0]):
                export_key = self.get_export_file_key(export_name)
                if not export_key:
                    continue

                if export_key in exported_model_keys:
                    print('DemonFF mass export: skipped duplicate model instance %s from collection %s' % (export_name, collection.name))
                    continue

                exported_model_keys.add(export_key)

                self.collection = collection
                self.collision_objects = collision_objects
                self.reset_export_state()

                clean_export_name = self.clean_export_collection_name(export_name)
                target_file = os.path.join(self.path, clean_export_name)
                if os.path.exists(target_file):
                    os.remove(target_file)

                try:
                    self.export_objects(objects, clean_export_name)
                    if os.path.exists(target_file) and os.path.getsize(target_file) > 0:
                        exported_count += 1
                        self.add_export_totals(export_totals, getattr(self, "last_export_verify", {}))
                    else:
                        print('DemonFF SA-MP DFF mass export: skipped %s from collection %s because no valid DFF was written.' % (
                            clean_export_name,
                            collection.name if collection is not None else '<no collection>',
                        ))
                except Exception as error:
                    if os.path.exists(target_file):
                        os.remove(target_file)
                    print(
                        'DemonFF SA-MP DFF mass export: skipped %s from collection %s: %s' % (
                            export_name,
                            collection.name if collection is not None else '<no collection>',
                            error,
                        )
                    )

            self.collision_objects = None

            self.print_mass_export_verify(exported_count, len(export_candidates), export_totals)

            if exported_count == 0:
                raise DffExportException('Mass export found no DFF object collections to export.')

            return

        objects = self.get_single_export_objects()
        self.collection = self.get_primary_collection_for_export_objects(objects)
        self.collision_objects = self.get_collision_objects_for_export_objects(self.collection, objects)

        self.reset_export_state()
        self.export_objects(objects)

        self.collision_objects = None

                
#######################################################
def export_dff(options):
    # Setup options for export without changing directory structures
    dff_exporter.selected = options['selected']
    dff_exporter.export_frame_names = options['export_frame_names']
    dff_exporter.truncate_frame_names = options.get('truncate_frame_names', False)
    dff_exporter.mass_export = options['mass_export']
    dff_exporter.preserve_positions = options['preserve_positions']
    dff_exporter.path = options.get('directory') or os.path.dirname(os.path.normpath(options['file_name']))
    dff_exporter.version = options['version']
    dff_exporter.export_coll = options['export_coll']
    dff_exporter.preserve_collision_positions = options.get('preserve_collision_positions', True)
    dff_exporter.force_collision_to_dff_transform = options.get('force_collision_to_dff_transform', True)
    

    # Normalize and attempt forced read on file path without directory checks
    file_path = os.path.normpath(options['file_name'])

    try:
        # Bypass directory check and attempt to read directly
        dff_exporter.export_dff(file_path)
    except FileNotFoundError:
        # Provide a clear notice for a missing file
        print(f"Path '{file_path}' could not be accessed. Ensure file and directory are accessible.")