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
import bmesh
import os
import math
import mathutils

from ..gtaLib import col_samp

class col_samp_exporter:

    coll = None
    filename = "" # Whether it will return a bytes file (not write to a file), if no file name is specified
    version = None
    only_selected = False

    #######################################################
    def _process_mesh(obj, verts, faces, face_groups=None):

        mesh = obj.data

        if obj.mode == "EDIT":
            bm = bmesh.from_edit_mesh(mesh)
        else:
            bm = bmesh.new()
            bm.from_mesh(mesh)

        bmesh.ops.triangulate(bm, faces=bm.faces[:])

        vert_offset = len(verts)
        
        # Vertices
        for vert in bm.verts:
            verts.append((*vert.co,))

        # Setup for Face Groups
        layer = bm.faces.layers.int.get("face group")
        start_idx = fg_idx = 0
        fg_min = [256] * 3
        fg_max = [-256] * 3

        for i, face in enumerate(bm.faces):

            # Face Groups
            if layer and col_samp.Sections.version > 1:
                lastface = i == len(bm.faces)-1
                idx = face[layer]

                # Evaluate bounds if still the same face group index or this is the last face in the list
                if idx == fg_idx or lastface:
                    fg_min = [min(x, y) for x, y in zip(fg_min, face.verts[0].co)]
                    fg_max = [max(x, y) for x, y in zip(fg_max, face.verts[0].co)]
                    fg_min = [min(x, y) for x, y in zip(fg_min, face.verts[1].co)]
                    fg_max = [max(x, y) for x, y in zip(fg_max, face.verts[1].co)]
                    fg_min = [min(x, y) for x, y in zip(fg_min, face.verts[2].co)]
                    fg_max = [max(x, y) for x, y in zip(fg_max, face.verts[2].co)]

                # Create the face group if the face group index changed or this is the last face in the list
                if idx != fg_idx or lastface:
                    end_idx = i if lastface else i-1
                    face_groups.append(col_samp.TFaceGroup._make([fg_min, fg_max, start_idx, end_idx]))
                    fg_min = [256] * 3
                    fg_max = [-256] * 3
                    start_idx = i
                fg_idx = idx

            bm.verts.index_update()
            surface = [0, 0, 0, 0]
            
            mat = obj.data.materials[face.material_index]
            surface[0] = mat.dff.col_mat_index
            surface[1] = mat.dff.col_flags
            surface[2] = mat.dff.col_brightness
            surface[3] = mat.dff.col_light

            if col_samp.Sections.version == 1:
                faces.append(col_samp.TFace._make(
                    [vert.index + vert_offset for vert in (face.verts[0], face.verts[2], face.verts[1])] + [
                        col_samp.TSurface(*surface)
                    ]
                ))

            else:
                faces.append(col_samp.TFace._make(
                    [vert.index + vert_offset for vert in (face.verts[0], face.verts[2], face.verts[1])] + [
                        surface[0], surface[3]
                    ]
                ))

    #######################################################
    def _update_bounds(obj):

        # Don't include shadow meshes in bounds calculations
        if obj.dff.type == 'SHA':
            return

        self = col_samp_exporter

        if self.coll.bounds is None:
            self.coll.bounds = [
                [-math.inf] * 3,
                [math.inf] * 3
            ]

        dimensions = obj.dimensions
        center = obj.location
            
        # Empties don't have a dimensions array
        if obj.type == 'EMPTY':

            if obj.empty_display_type == 'SPHERE':
                # Multiplied by 2 because empty_display_size is a radius
                dimensions = [
                    max(x * obj.empty_display_size * 2 for x in obj.scale)] * 3
            else:
                dimensions = obj.scale

        # And Meshes require their proper center to be calculated because their transform is identity
        else:
            local_center = sum((mathutils.Vector(b) for b in obj.bound_box), mathutils.Vector()) / 8.0
            center = obj.matrix_world @ local_center

        upper_bounds = [x + (y/2) for x, y in zip(center, dimensions)]
        lower_bounds = [x - (y/2) for x, y in zip(center, dimensions)]

        self.coll.bounds = [
            [max(x, y) for x,y in zip(self.coll.bounds[0], upper_bounds)],
            [min(x, y) for x,y in zip(self.coll.bounds[1], lower_bounds)]
        ]

    #######################################################
    def _convert_bounds():
        self = col_samp_exporter

        radius = 0.0
        center = [0, 0, 0]
        rect_min = [0, 0, 0]
        rect_max = [0, 0, 0]

        if self.coll.bounds is not None:
            rect_min = self.coll.bounds[0]
            rect_max = self.coll.bounds[1]
            center = [(x + y) / 2 for x, y in zip(*self.coll.bounds)]
            radius = (
                mathutils.Vector(rect_min) - mathutils.Vector(rect_max)
            ).magnitude / 2

        self.coll.bounds = col_samp.TBounds(max = col_samp.TVector(*rect_min),
                                       min = col_samp.TVector(*rect_max),
                                       center = col_samp.TVector(*center),
                                       radius = radius
        )   
        
        pass
        
    #######################################################
    def _process_spheres(obj):
        self = col_samp_exporter
        
        radius = max(x * obj.empty_display_size for x in obj.scale)
        centre = col_samp.TVector(*obj.location)
        surface = col_samp.TSurface(
            obj.dff.col_material,
            obj.dff.col_flags,
            obj.dff.col_brightness,
            obj.dff.col_light
        )

        self.coll.spheres.append(col_samp.TSphere(radius=radius,
                                         surface=surface,
                                         center=centre
        ))
        
        pass
                
    #######################################################
    def _process_boxes(obj):
        self = col_samp_exporter

        min = col_samp.TVector(*(obj.location - obj.scale))
        max = col_samp.TVector(*(obj.location + obj.scale))

        surface = col_samp.TSurface(
            obj.dff.col_material,
            obj.dff.col_flags,
            obj.dff.col_brightness,
            obj.dff.col_light
        )

        self.coll.boxes.append(col_samp.TBox(min=min,
                                        max=max,
                                        surface=surface,
        ))

        pass

    #######################################################
    def _process_obj(obj):
        self = col_samp_exporter
        
        if obj.type == 'MESH':
            # Meshes
            if obj.dff.type == 'SHA':
                self._process_mesh(obj,
                                   self.coll.shadow_verts,
                                   self.coll.shadow_faces
                )
                
            else:
                self._process_mesh(obj,
                                   self.coll.mesh_verts,
                                   self.coll.mesh_faces
                )
                    
        elif obj.type == 'EMPTY':
            self._process_spheres(obj)
        
        self._update_bounds(obj)

    #######################################################
    def export_col(name):
        self = col_samp_exporter
        self.file_name = name

        col_samp.Sections.init_sections(self.version)

        self.coll = col_samp.ColModel()
        self.coll.version = self.version
        self.coll.model_name = os.path.basename(name)

        objects = bpy.data.objects
        if self.collection is not None:
            objects = self.collection.objects

        total_objects = 0
        for obj in objects:
            if obj.dff.type == 'COL' or obj.dff.type == 'SHA':
                if not self.only_selected or obj.select_get():
                    self._process_obj(obj)
                    total_objects += 1
                
        self._convert_bounds()
        
        if self.memory:
            if total_objects > 0:
                return col_samp.coll(self.coll).write_memory()
            return b''

        col_samp.coll(self.coll).write_file(name)

#######################################################
def get_col_collection_name(collection, parent_collection=None):
    name = collection.name

    # Strip stuff like vehicles.col. from the name so that
    # for example vehicles.col.infernus changes to just infernus
    if parent_collection and parent_collection != collection:
        prefix = parent_collection.name + "."
        if name.startswith(prefix):
            name = name[len(prefix):]

    return name

#######################################################
def export_col(options):
    # Set exporter properties
    col_samp_exporter.memory = options['memory']
    col_samp_exporter.version = options['version']
    col_samp_exporter.collection = options['collection']
    col_samp_exporter.only_selected = options['only_selected']




    # If mass export mode is enabled
    if options['mass_export']:
        output = b''

        root_collection = bpy.context.scene.collection
        collections = list(root_collection.children) + [root_collection]
        col_samp_exporter.memory = True  # To gather memory output per collection

        # Ensure the directory path exists
        base_dir = options['directory']
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)

        # Process each collection
        for collection in collections:
            col_samp_exporter.collection = collection
            name = collection.name

            # Adjust the collection name for proper file naming
            try:
                name = name[name.index(".col") + len(".col"):]
            except ValueError:
                pass
            
            # Define the export path for each collection
            export_path = os.path.join(base_dir, f"{name}.col")

            # Perform the export and gather output if needed
            collection_output = col_samp_exporter.export_col(name)
            output += collection_output

            # Write each collection's output to its respective file
            with open(export_path, mode='wb') as file:
                file.write(collection_output)

        # Return accumulated output if in-memory output is requested
        if options['memory']:
            return output

    else:
        # Non-mass export: use the specified file name directly
        return col_samp_exporter.export_col(options['file_name'])