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
import math
import bmesh
import mathutils

from collections import OrderedDict

from ..gtaLib import dff
from ..gtaLib.dff import entries
from .importer_common import (
    link_object, create_collection,
    material_helper, set_object_mode,
    hide_object)
from ..ops import txd_importer
from .col_importer import import_col_mem
from ..ops.ext_2dfx_importer import ext_2dfx_importer
from ..ops.state import State


#######################################################
class dff_importer:

    load_txd           = False
    txd_filename       = ""
    skip_mipmaps       = True
    txd_pack           = True
    image_ext          = "png"
    materials_naming   = "DEF"
    use_bone_connect   = False
    current_collection = None
    use_mat_split      = False
    remove_doubles     = False
    import_normals     = False
    group_materials    = False
    version            = ""
    warning            = ""

    __slots__ = [
        'dff',
        'meshes',
        'objects',
        'file_name',
        'skin_data',
        'bones'
    ]

    #######################################################
    def multiply_matrix(a, b):
        # For compatibility with 2.79
        if bpy.app.version < (2, 80, 0):
            return a * b
        return a @ b
    
    #######################################################
    def _init():
        self = dff_importer

        # Variables
        self.dff = None
        self.meshes = {}
        self.delta_morph = {}
        self.objects = {}
        self.file_name = ""
        self.skin_data = {}
        self.bones = {}
        self.frame_bones = {}
        self.materials = {}
        self.txd_images = {}
        self.warning = ""

    #######################################################
    # TODO: Cyclomatic Complexity too high
    def import_atomics():
        self = dff_importer

        for atomic_index, atomic in enumerate(self.dff.atomic_list):
            frame = self.dff.frame_list[atomic.frame]
            geom = self.dff.geometry_list[atomic.geometry]

            mesh = bpy.data.meshes.new(frame.name)
            bm = bmesh.new()

            mat_order = [split.material for split in geom.split_headers] + list(range(len(geom.materials)))
            mat_order = list(OrderedDict.fromkeys(mat_order))
            mat_indices = sorted(range(len(mat_order)), key=lambda i: mat_order[i])

            # Store temporary mesh flags
            mesh['dragon_normals'] = geom.has_normals
            mesh['dragon_light'] = (geom.flags & dff.rpGEOMETRYLIGHT) != 0
            mesh['dragon_modulate_color'] = (geom.flags & dff.rpGEOMETRYMODULATEMATERIALCOLOR) != 0
            mesh['dragon_triangle_strip'] = (geom.flags & dff.rpGEOMETRYTRISTRIP) != 0

            # Build vertex data
            for v in geom.vertices:
                bm.verts.new(v)

            bm.verts.ensure_lookup_table()
            bm.verts.index_update()

            if 'skin' in geom.extensions:
                if atomic.frame not in self.skin_data:
                    self.skin_data[atomic.frame] = geom.extensions['skin']

            if 'user_data' in geom.extensions:
                mesh['dff_user_data'] = geom.extensions['user_data'].to_mem()[12:]

            # UV and vertex color setup
            uv_layers = [bm.loops.layers.uv.new() for _ in geom.uv_layers]

            vertex_color = None
            if geom.flags & dff.rpGEOMETRYPRELIT:
                vertex_color = bm.loops.layers.color.new()

            extra_vertex_color = None
            if 'extra_vert_color' in geom.extensions:
                extra_vertex_color = bm.loops.layers.color.new()

            faces = (
                geom.extensions['mat_split']
                if (dff_importer.use_mat_split or not geom.triangles) and 'mat_split' in geom.extensions
                else geom.triangles
            )

            use_face_loops = geom.native_platform_type == dff.NativePlatformType.GC
            use_custom_normals = geom.has_normals and self.import_normals
            normals = []
            vert_index = -1
            last_face_index = len(faces) - 1

            for fi, f in enumerate(faces):
                if fi < last_face_index:
                    next_face = faces[fi + 1]
                    if set((f.a, f.b, f.c)) == set((next_face.a, next_face.b, next_face.c)):
                        vert_index += 3
                        continue

                v1 = bm.verts[f.a]
                v2 = bm.verts[f.b]
                v3 = bm.verts[f.c]

                if v1 == v2 or v2 == v3 or v1 == v3:
                    continue

                # Skip if face already exists with the same vertex set
                vert_set = {v1, v2, v3}
                found = False
                for face in bm.faces:
                    if vert_set == set(face.verts):
                        found = True
                        break
                if found:
                    continue

                try:
                    face = bm.faces.new([v1, v2, v3])

                    if len(mat_indices) > 0:
                        face.material_index = mat_indices[f.material]

                    for loop in face.loops:
                        if use_face_loops:
                            for i, layer in enumerate(geom.uv_layers):
                                uv = layer[loop.vert.index]
                                loop[uv_layers[i]].uv = (uv.u, 1 - uv.v)


                    if len(mat_indices) > 0:
                        face.material_index = mat_indices[f.material]

                    for loop in face.loops:
                        if use_face_loops:
                            vert_index += 1
                        else:
                            vert_index = loop.vert.index

                        for i, layer in enumerate(geom.uv_layers):
                            uv = geom.uv_layers[i][vert_index]
                            loop[uv_layers[i]].uv = (uv.u, 1 - uv.v)

                        if vertex_color:
                            loop[vertex_color] = [c / 255.0 for c in geom.prelit_colors[vert_index]]

                        if extra_vertex_color:
                            loop[extra_vertex_color] = [c / 255.0 for c in geom.extensions['extra_vert_color'].colors[vert_index]]

                        if use_custom_normals:
                            normals.append(geom.normals[vert_index])

                    face.smooth = True
                except Exception as e:
                    vert_index += 3
                    print(f"Face error: {e}")

            bm.to_mesh(mesh)

            if normals:
                mesh.normals_split_custom_set(normals)
                if bpy.app.version < (4, 1, 0):
                    mesh.use_auto_smooth = True

            mesh.update()

            # Import materials
            self.import_materials(geom, frame, mesh, mat_order)

            # Create object and link it
            obj = bpy.data.objects.new('mesh', mesh)
            link_object(obj, self.current_collection)
            obj.rotation_mode = 'QUATERNION'

            # Transfer mesh props to object
            obj.dff.export_normals = mesh['dragon_normals']
            obj.dff.light = mesh['dragon_light']
            obj.dff.modulate_color = mesh['dragon_modulate_color']
            obj.dff.triangle_strip = mesh['dragon_triangle_strip']

            # Pipeline
            if 'pipeline' in atomic.extensions:
                pipeline = "0x%X" % (atomic.extensions['pipeline'])
                if pipeline in ["0x53F20098", "0x53F2009A"]:
                    obj.dff.pipeline = pipeline
                    obj.dff.custom_pipeline = ""
                else:
                    obj.dff.pipeline = "CUSTOM"
                    obj.dff.custom_pipeline = pipeline

            if 'right_to_render' in atomic.extensions:
                obj.dff.right_to_render = atomic.extensions['right_to_render'].value2

            obj.dff.atomic_index = atomic_index

            # Remove temp mesh props
            for k in ['dragon_normals', 'dragon_light', 'dragon_modulate_color', 'dragon_triangle_strip']:
                if k in mesh:
                    del mesh[k]

            # Set vertex groups
            if 'skin' in geom.extensions:
                self.set_vertex_groups(obj, geom.extensions['skin'])

            # Store object per atomic frame
            if atomic.frame in self.meshes:
                self.meshes[atomic.frame].append(obj)
                self.delta_morph[atomic.frame].append(geom.extensions.get('delta_morph'))
            else:
                self.meshes[atomic.frame] = [obj]
                self.delta_morph[atomic.frame] = [geom.extensions.get('delta_morph')]



    #######################################################
    def merge_meshes(mesha, meshb):
        bm = bmesh.new()

        bm.from_mesh(mesha)
        bm.from_mesh(meshb)

        bm.to_mesh(mesha)
                
    #######################################################
    def set_empty_draw_properties(empty):
        if (2, 80, 0) > bpy.app.version:
            empty.empty_draw_type = 'CUBE'
            empty.empty_draw_size = 0.05
        else:
            empty.empty_display_type = 'CUBE'
            empty.empty_display_size = 0.05
        pass


    ##################################################################
    def generate_material_name(material, fallback):

        name = None
        
        patterns = {
            "vehiclegeneric": "generic",
            "interior": "interior",
            "vehiclesteering": "steering"
        }

        if material.is_textured:
            texture = material.textures[0].name

            for pattern in patterns:
                if pattern in texture:
                    name = patterns[pattern]

        mat_color = material.color
        if mat_color.a < 200:
            name = "glass"

        colors = {
            "[255, 60, 0, 255]": "right rear light",
            "[185, 255, 0, 255]": "left rear light",
            "[0, 255, 200, 255]": "right front light",
            "[255, 175, 0, 255]": "left front light",
            "[255, 0, 255, 255]": "fourth",
            "[0, 255, 255, 255]": "third",
            "[255, 0, 175, 255]": "secondary",
            "[60, 255, 0, 255]": "primary",
            "[184, 255, 0, 255]": "breaklight l",
            "[255, 59, 0, 255]": "breaklight r",
            "[255, 173, 0, 255]": "revlight L",
            "[0, 255, 198, 255]": "revlight r",
            "[255, 174, 0, 255]": "foglight l",
            "[0, 255, 199, 255]": "foglight r",
            "[183, 255, 0, 255]": "indicator lf",
            "[255, 58, 0, 255]": "indicator rf",
            "[182, 255, 0, 255]": "indicator lm",
            "[255, 57, 0, 255]": "indicator rm",
            "[181, 255, 0, 255]": "indicator lr",
            "[255, 56, 0, 255]": "indicator rr",
            "[0, 16, 255, 255]": "light night",
            "[0, 17, 255, 255]": "light all-day",
            "[0, 18, 255, 255]": "default day"
        }

        for color in colors:
            if eval(color) == list(mat_color):
                name = colors[color]
                
        return name if name else fallback
        
    ##################################################################
    # TODO: MatFX: Dual Textures
    def import_materials(geometry, frame, mesh, mat_order):

        self = dff_importer
        from bpy_extras.image_utils import load_image

        # Refactored
        for index, mat_idx in enumerate(mat_order):
            material = geometry.materials[mat_idx]

            # Check for equal materials
            if self.group_materials and hash(material) in self.materials:
                mesh.materials.append(self.materials[hash(material)])
                continue
            
            # Generate a nice name with index and frame
            name = "%s.%d" % (frame.name, index)
            name = self.generate_material_name(material, name)
            
            mat = bpy.data.materials.new(name)
            mat.blend_method = 'CLIP'
            helper = material_helper(mat)
            
            helper.set_base_color(material.color)

            # Loading Texture
            if material.is_textured == 1:
                texture = material.textures[0]
                image   = None

                if texture.name in self.txd_images:
                    image = self.txd_images[texture.name][0]

                elif self.image_ext:
                    path    = os.path.dirname(self.file_name)
                    image_name = "%s.%s" % (texture.name, self.image_ext)

                    # name.None shouldn't exist, lol / Share loaded images among imported materials
                    if (image_name in bpy.data.images and
                            path == bpy.path.abspath(bpy.data.images[image_name].filepath)):
                        image = bpy.data.images[image_name]
                    else:
                        image = load_image(image_name,
                                        path,
                                        recursive=False,
                                        place_holder=True,
                                        check_existing=True
                                        )
                helper.set_texture(image, texture.name, texture.filters, texture.uv_addressing)

            # Normal Map
            if 'bump_map' in material.plugins:
                mat.dff.export_bump_map = True
                
                for bump_fx in material.plugins['bump_map']:

                    texture = None
                    if bump_fx.height_map is not None:
                        texture = bump_fx.height_map
                        if bump_fx.bump_map is not None:
                            mat.dff.bump_map_tex = bump_fx.bump_map.name

                    elif bump_fx.bump_map is not None:
                        texture = bump_fx.bump_map

                    if texture:
                        image = None

                        if texture.name in self.txd_images:
                            image = self.txd_images[texture.name][0]

                        else:
                            path = os.path.dirname(self.file_name)
                            image_name = "%s.%s" % (texture.name, self.image_ext)

                            # see name.None note above / Share loaded images among imported materials
                            if (image_name in bpy.data.images and
                                    path == bpy.path.abspath(bpy.data.images[image_name].filepath)):
                                image = bpy.data.images[image_name]
                            else:
                                image = load_image(image_name,
                                                path,
                                                recursive=False,
                                                place_holder=True,
                                                check_existing=True
                                               )

                        helper.set_normal_map(image,
                                              texture.name,
                                              bump_fx.intensity
                        )

            # Surface Properties
            if material.surface_properties is not None:
                props = material.surface_properties

            elif geometry.surface_properties is not None:
                props = geometry.surface_properties

            if props is not None:
                helper.set_surface_properties(props)

            # Environment Map
            if 'env_map' in material.plugins:
                plugin = material.plugins['env_map'][0]
                helper.set_environment_map(plugin)

            # Specular Material
            if 'spec' in material.plugins:
                plugin = material.plugins['spec'][0]
                helper.set_specular_material(plugin)

            # Reflection Material
            if 'refl' in material.plugins:
                plugin = material.plugins['refl'][0]
                helper.set_reflection_material(plugin)

            if 'udata' in material.plugins:
                plugin = material.plugins['udata'][0]
                helper.set_user_data(plugin)
                
            # UV Animation
            # TODO: Figure out ways to add multiple uv animations
            if 'uv_anim' in material.plugins:
                plugin = material.plugins['uv_anim'][0]

                for uv_anim in self.dff.uvanim_dict:
                    if uv_anim.name == plugin:
                        helper.set_uv_animation(uv_anim)
                        break
                
            # Add imported material to the object
            mesh.materials.append(helper.material)

            # Add imported material to lookup table for similar materials
            if self.group_materials:
                self.materials[hash(material)] = helper.material


    #######################################################
    def construct_bone_dict():
        self = dff_importer
        
        for index, frame in enumerate(self.dff.frame_list):
            if frame.bone_data:
                bone_id = frame.bone_data.header.id
                if bone_id != -1:
                    self.bones[bone_id] = {'frame': frame,
                                              'index': index}
                        
    #######################################################
    def align_roll( vec, vecz, tarz ):

        sine_roll = vec.normalized().dot(vecz.normalized().cross(tarz.normalized()))

        if 1 < abs(sine_roll):
            sine_roll /= abs(sine_roll)
            
        if 0 < vecz.dot( tarz ):
            return math.asin( sine_roll )
        
        elif 0 < sine_roll:
            return -math.asin( sine_roll ) + math.pi
        
        else:
            return -math.asin( sine_roll ) - math.pi

    #######################################################
    def get_skinned_obj_index(frame, frame_index):
        self = dff_importer

        possible_frames = [
            frame.parent, # The parent frame 
            frame_index - 1, # The previous frame
            0 # The first frame
        ]
        
        for possible_frame in possible_frames:
            
            if possible_frame in self.skin_data:
                return possible_frame

        # Find an arbritary frame
        for _, index in enumerate(self.skin_data):
            return index

        return None
        
        
    #######################################################
    def construct_armature(frame, frame_index):

        self = dff_importer
        
        armature = bpy.data.armatures.new(frame.name)
        obj = bpy.data.objects.new(frame.name, armature)
        link_object(obj, dff_importer.current_collection)

        skinned_obj_data = None
        skinned_objs = []

        skinned_obj_index = self.get_skinned_obj_index(frame, frame_index)

        if skinned_obj_index is not None:
            skinned_obj_data = self.skin_data[skinned_obj_index]

            for _, index in enumerate(self.skin_data):
                skinned_objs += self.meshes[index]

        # armature edit bones are only available in edit mode :/
        set_object_mode(obj, "EDIT")
        edit_bones = obj.data.edit_bones

        bone_list = {}

        for index, bone in enumerate(frame.bone_data.bones):

            bone_frame = self.bones[bone.id]['frame']

            # Set vertex group name of the skinned object
            for skinned_obj in skinned_objs:
                skinned_obj.vertex_groups[index].name = bone_frame.name

            e_bone = edit_bones.new(bone_frame.name)
            e_bone.tail = (0,0.05,0) # Stop bone from getting delete

            e_bone['bone_id'] = bone.id
            e_bone['type'] = bone.type

            if bone_frame.user_data is not None:
                e_bone['dff_user_data'] = bone_frame.user_data.to_mem()[12:]

            if skinned_obj_data is not None:
                matrix = skinned_obj_data.bone_matrices[bone.index]
                matrix = mathutils.Matrix(matrix).transposed()
                matrix = matrix.inverted()

                e_bone.transform(matrix, scale=True, roll=False)
                e_bone.roll = self.align_roll(e_bone.vector,
                                            e_bone.z_axis,
                                            self.multiply_matrix(
                                                matrix.to_3x3(),
                                                mathutils.Vector((0,0,1))
                                            )
                )

            else:
                matrix = mathutils.Matrix(
                    (
                        bone_frame.rotation_matrix.right,
                        bone_frame.rotation_matrix.up,
                        bone_frame.rotation_matrix.at
                    )
                )

                e_bone.matrix = self.multiply_matrix(
                    mathutils.Matrix.Translation(bone_frame.position),
                    matrix.transposed().to_4x4()
                )

            if bone_frame.parent >= frame_index and bone_frame.parent in bone_list:
                e_bone.parent = bone_list[bone_frame.parent][0]
                if skinned_obj_data is None:
                    e_bone.matrix = self.multiply_matrix(e_bone.parent.matrix, e_bone.matrix)

                if self.use_bone_connect:

                    if not bone_list[bone_frame.parent][1]:

                        mat = [e_bone.parent.head, e_bone.parent.tail, e_bone.head]
                        mat = mathutils.Matrix(mat)
                        if abs(mat.determinant()) < 0.0000001:

                            length = (e_bone.parent.head - e_bone.head).length
                            e_bone.length      = length
                            e_bone.use_connect = self.use_bone_connect

                            bone_list[bone_frame.parent][1] = True

            bone_list[self.bones[bone.id]['index']] = [e_bone, False]
            self.frame_bones[self.bones[bone.id]['index']] = {'armature': obj, 'name': e_bone.name}


        set_object_mode(obj, "OBJECT")

        # Add Armature modifier to skinned object
        for skinned_obj in skinned_objs:
            modifier        = skinned_obj.modifiers.new("Armature", 'ARMATURE')
            modifier.object = obj

        return (armature, obj)

    #######################################################
    def set_vertex_groups(obj, skin_data):

        # Allocate vertex groups
        for i in range(skin_data.num_bones):
            obj.vertex_groups.new()

        # vertex_bone_indices stores what 4 bones influence this vertex
        for i in range(len(skin_data.vertex_bone_indices)):

            for j in range(len(skin_data.vertex_bone_indices[i])):

                bone = skin_data.vertex_bone_indices[i][j]
                weight = skin_data.vertex_bone_weights[i][j]
                
                obj.vertex_groups[bone].add([i], weight, 'ADD')

    #######################################################
    def remove_object_doubles():
        self = dff_importer

        for frame in self.meshes:
            for mesh in self.meshes[frame]:
                bm = bmesh.new()
                bm.from_mesh(mesh.data)

                # Mark edges with 1 linked face, sharp
                for edge in bm.edges:
                    if len(edge.link_loops) == 1:
                        edge.smooth = False
                
                bmesh.ops.remove_doubles(bm, verts = bm.verts, dist = 0.00001)

                # Add an edge split modifier
                if not mesh.data.shape_keys:
                    modifier = mesh.modifiers.new("EdgeSplit", 'EDGE_SPLIT')
                    modifier.use_edge_angle = False
                
                bm.to_mesh(mesh.data)

    #######################################################
    def process_2dfx_lights(data, offset, context):
        """
        Process 2DFX lights and call add_light_info for each parsed LightEntry.
        """
        # Read and parse the 2DFX entries
        entries = dff_instance.read_2dfx(data, offset, context)

        # Process each LightEntry
        for i, entry in enumerate(entries):
            print(f"Processing Light Entry {i + 1}/{len(entries)}...")
            add_light_info(context, entry)
    ####################################################### =)
    def link_obj_to_frame_bone(obj, frame_index):
        self = dff_importer

        frame_bone = self.frame_bones[frame_index]
        armature, bone_name = frame_bone['armature'], frame_bone['name']
        #set_parent_bone(obj, armature, bone_name) # Broken

    #######################################################
    def import_frames():
        self = dff_importer

        # Initialise bone indices for use in armature construction
        self.construct_bone_dict()
        #self.import_2dfx(self.dff.ext_2dfx)
        
        for index, frame in enumerate(self.dff.frame_list):

            # Check if the meshes for the frame has been loaded
            meshes = []
            if index in self.meshes:
                meshes = self.meshes[index]

                        # Add shape keys by delta morph
            for mesh_index, mesh in enumerate(meshes):

                delta_morph = self.delta_morph.get(index)[mesh_index]
                if delta_morph:
                    verts = mesh.data.vertices

                    sk_basis = mesh.shape_key_add(name='Basis')
                    sk_basis.interpolation = 'KEY_LINEAR'
                    mesh.data.shape_keys.use_relative = True

                    for dm in delta_morph.entries:
                        sk = mesh.shape_key_add(name=dm.name)
                        sk.interpolation = 'KEY_LINEAR'

                        positions, normals, prelits, uvs = dm.positions, dm.normals, dm.prelits, dm.uvs
                        for i, vi in enumerate(dm.indices):
                            if positions:
                                sk.data[vi].co = verts[vi].co + mathutils.Vector(positions[i])
                            # TODO: normals, prelits and uvs

            obj = None

            # Load rotation matrix
            matrix = mathutils.Matrix(
                (
                    frame.rotation_matrix.right,
                    frame.rotation_matrix.up,
                    frame.rotation_matrix.at
                )
            )
            matrix = self.multiply_matrix(mathutils.Matrix.Translation(frame.position),
                                          matrix.transposed().to_4x4())

            if frame.bone_data is not None:
                
                # Construct an armature
                if frame.bone_data.header.bone_count > 0:
                    _, obj = self.construct_armature(frame, index)

                    for mesh in meshes:
                        mesh.parent = obj  # ensure mesh is parented to armature
                        mesh.dff.is_frame = False

                # Skip bones
                elif frame.bone_data.header.id in self.bones:

                    for mesh in meshes:
                        self.link_obj_to_frame_bone(mesh, index)
                        mesh.dff.is_frame = False

                    continue
                    
            # Create and link the object to the scene
            if obj is None:
                if len(meshes) != 1:
                    frame_name = frame.name if frame.name else "Unnamed_Frame"
                    obj = bpy.data.objects.new(frame_name, None)
                    link_object(obj, dff_importer.current_collection)

                    # Set empty display properties to something decent
                    self.set_empty_draw_properties(obj)

                else:
                    # Use a mesh as a frame object
                    obj = meshes[0]
                    obj.name = frame.name

                obj.rotation_mode = 'QUATERNION'
                obj.matrix_local  = matrix.copy()

            # Link mesh to frame
            for mesh in meshes:
                if obj != mesh:
                    mesh.parent = obj
                    mesh.dff.is_frame = False
                else:
                    mesh.dff.is_frame = True

            if frame.parent != -1:
                if frame.parent in self.frame_bones:
                    self.link_obj_to_frame_bone(obj, frame.parent)
                elif frame.parent in self.objects:
                    obj.parent = self.objects[frame.parent]
                else:
                    print(f"Frame {index} ('{obj.name}') skipped — missing parent frame ID {frame.parent}") # Skip object if no frame parent
                    continue 



            obj.dff.frame_index = index

            self.objects[index] = obj

            # Set a collision model used for export
            obj["gta_coll"] = self.dff.collisions
                
            if frame.user_data is not None:
                obj["dff_user_data"] = frame.user_data.to_mem()[12:]

            if self.remove_doubles:
                self.remove_object_doubles()
    #######################################################
    def preprocess_atomics():
        self = dff_importer

        atomic_frames = []
        to_be_preprocessed = [] #these will be assigned a new frame
        
        for index, atomic in enumerate(self.dff.atomic_list):

            frame = self.dff.frame_list[atomic.frame]

            # For GTA SA bones, which have the frame of the pedestrian
            # (incorrectly?) set in the atomic to a bone
            if frame.bone_data is not None and frame.bone_data.header.id != -1:
                to_be_preprocessed.append(index)

            atomic_frames.append(atomic.frame)

        # Assign every atomic in the list a new (possibly valid) frame
        for atomic in to_be_preprocessed:
            
            for index, frame in enumerate(self.dff.frame_list):

                # Find an empty frame
                if (frame.bone_data is None or frame.bone_data.header.id == -1) \
                   and index not in atomic_frames:
                    old = self.dff.atomic_list[atomic]
                    new = dff.Atomic()
                    new.frame = index
                    new.geometry = old.geometry
                    new.flags = old.flags
                    new.unk = old.unk
                    new.extensions = old.extensions.copy() if hasattr(old, "extensions") else {}
                    self.dff.atomic_list[atomic] = new

                    break
    #######################################################
    def import_2dfx():
        self = dff_importer

        # Validate entries
        for entry in self.dff.ext_2dfx.entries:
            if entry is None or not hasattr(entry, 'effect_id'):
                print("⚠️ Skipping 2DFX import due to invalid entry.")
                return

        importer = ext_2dfx_importer(self.dff.ext_2dfx.entries)
        for obj in importer.get_objects():
            link_object(obj, self.current_collection)

    #######################################################
    def set_parent_bone(obj, armature, bone_name):
        bone = armature.data.bones.get(bone_name)
        if not bone:
            return

        obj.parent = armature
        obj.parent_bone = bone_name

        is_skinned = False
        if obj.type == 'MESH':
            for modifier in obj.modifiers:
                if modifier.type == 'ARMATURE' and modifier.object == armature:
                    is_skinned = True
                    break

        # For skinned mesh use default parent_type, just change matrix_local
        # Otherwise it will break the animations
        if is_skinned:
            obj.rotation_mode = 'QUATERNION'
            obj.matrix_local = armature.pose.bones[bone_name].matrix.copy()
        else:
            obj.parent_type = 'BONE'
            obj.matrix_parent_inverse = mathutils.Matrix.Translation((0, -bone.length, 0))               
            
    #######################################################
    def import_dff(file_name):
        self = dff_importer
        self._init()

        # Load the DFF
        self.dff = dff.dff()
        self.dff.load_file(file_name)
        self.file_name = file_name

        # Load the TXD
        if self.load_txd:
            # Import txd from a file if file exists
            base_path = os.path.dirname(file_name)
            txd_filename = self.txd_filename if self.txd_filename \
                else os.path.basename(file_name)[:-4] + ".txd"
            txd_path = os.path.join(base_path, txd_filename)
            if os.path.isfile(txd_path):
                self.txd_images = txd_importer.import_txd(
                    {
                        'file_name'    : txd_path,
                        'skip_mipmaps' : self.skip_mipmaps,
                        'pack'         : self.txd_pack,
                    }
                ).images

        # Create a new group/collection
        self.current_collection = create_collection(
            os.path.basename(file_name)
        )

        # Create a placeholder frame if there are no frames in the file
        if len(self.dff.frame_list) == 0:
            frame = dff.Frame()
            frame.name            = ""
            frame.position        = (0, 0, 0)
            frame.rotation_matrix = dff.Matrix._make(
                mathutils.Matrix.Identity(3).transposed()
            )
            self.dff.frame_list.append(frame)

            # Attach the created frame to the atomics
            for atomic in self.dff.atomic_list:
                atomic.frame = 0

        self.import_atomics()
        self.import_frames()
        self.import_2dfx()

        # Set imported version
        self.version = "0x%05x" % self.dff.rw_version
        
        # Add collisions
        for collision in self.dff.collisions:
            col = import_col_mem(collision.data, os.path.basename(file_name), False)

            if (2, 80, 0) <= bpy.app.version:
                for collection in col:
                    self.current_collection.children.link(collection)

                    # Hide objects
                    for object in collection.objects:
                        hide_object(object)

        State.update_scene()



#######################################################
def import_dff(options):

    # Shadow function
    dff_importer.load_txd         = options['load_txd']
    dff_importer.txd_filename     = options['txd_filename']
    dff_importer.skip_mipmaps     = options['skip_mipmaps']
    dff_importer.txd_pack         = options['txd_pack']
    dff_importer.image_ext        = options['image_ext']
    dff_importer.use_bone_connect = options['connect_bones']
    dff_importer.use_mat_split    = options['use_mat_split']
    dff_importer.remove_doubles   = options['remove_doubles']
    dff_importer.group_materials  = options['group_materials']
    dff_importer.import_normals   = options['import_normals']
    dff_importer.materials_naming = options['materials_naming']

    dff_importer.import_dff(options['file_name'])

    return dff_importer