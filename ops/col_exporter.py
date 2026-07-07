# DemonFF - Blender scripts for working with Renderware & R*/SA-MP/open.mp formats in Blender
# 2023 - 2026 spicybung

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

import bpy
import os
import re
import math
import bmesh
import mathutils

from ..gtaLib import col


#######################################################
class col_exporter:

    coll = None
    filename = "" # Whether it will return a bytes file (not write to a file), if no file name is specified
    version = None
    only_selected = False
    objects = None
    preserve_positions = True

    #######################################################
    def is_finite_number(value):
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError, OverflowError):
            return False

    #######################################################
    def is_finite_vector(values):
        try:
            return all(col_exporter.is_finite_number(value) for value in values)
        except TypeError:
            return False

    #######################################################
    def get_collision_surface(obj, face):
        surface = [0, 0, 0, 0]
        try:
            if obj.data.materials and face.material_index < len(obj.data.materials):
                mat = obj.data.materials[face.material_index]
                surface[0] = mat.dff.col_mat_index
                surface[1] = mat.dff.col_flags
                surface[2] = mat.dff.col_brightness
                surface[3] = mat.dff.col_light
        except (IndexError, AttributeError):
            pass
        return surface

    #######################################################
    def get_stored_source_matrix(obj):
        try:
            rows = obj.get("demonff_collision_source_matrix_world")
        except Exception:
            rows = None

        if not rows:
            return None

        try:
            return mathutils.Matrix(rows)
        except Exception:
            return None

    #######################################################
    def matrix_is_identity(matrix):
        try:
            identity = mathutils.Matrix.Identity(4)
            for row in range(4):
                for column in range(4):
                    if abs(matrix[row][column] - identity[row][column]) > 0.000001:
                        return False
            return True
        except Exception:
            return False

    #######################################################
    def get_local_mesh_bounds(obj):
        if obj.type != 'MESH' or obj.data is None or not obj.data.vertices:
            return None

        minimum = mathutils.Vector((math.inf, math.inf, math.inf))
        maximum = mathutils.Vector((-math.inf, -math.inf, -math.inf))

        for vertex in obj.data.vertices:
            co = vertex.co
            minimum.x = min(minimum.x, co.x)
            minimum.y = min(minimum.y, co.y)
            minimum.z = min(minimum.z, co.z)
            maximum.x = max(maximum.x, co.x)
            maximum.y = max(maximum.y, co.y)
            maximum.z = max(maximum.z, co.z)

        return minimum, maximum

    #######################################################
    def mesh_data_looks_baked_to_source_space(obj, source_matrix):
        bounds = col_exporter.get_local_mesh_bounds(obj)
        if bounds is None or source_matrix is None:
            return False

        minimum, maximum = bounds
        center = (minimum + maximum) * 0.5
        extent = (maximum - minimum).length
        source_position = source_matrix.to_translation()

        if source_position.length <= 0.0001:
            return False

        distance = (center - source_position).length
        threshold = max(1.0, extent * 0.25)
        return distance <= threshold

    #######################################################
    def is_transform_baked(obj):
        try:
            baked = bool(obj.get("demonff_collision_transform_applied", False))
        except Exception:
            baked = False

        if not baked:
            return False

        source_matrix = col_exporter.get_stored_source_matrix(obj)
        if source_matrix is not None and not col_exporter.mesh_data_looks_baked_to_source_space(obj, source_matrix):
            return False

        return True

    #######################################################
    def get_export_matrix(obj):
        if not col_exporter.preserve_positions:
            return mathutils.Matrix.Identity(4)

        if col_exporter.is_transform_baked(obj):
            return mathutils.Matrix.Identity(4)

        source_matrix = col_exporter.get_stored_source_matrix(obj)

        try:
            matrix = obj.matrix_world.copy()
        except Exception:
            matrix = None

        if matrix is not None and not col_exporter.matrix_is_identity(matrix):
            return matrix

        if source_matrix is not None:
            return source_matrix

        if matrix is not None:
            return matrix

        return mathutils.Matrix.Identity(4)

    #######################################################
    def transform_point(obj, point):
        return col_exporter.get_export_matrix(obj) @ point

    #######################################################
    def _process_mesh(obj, verts, faces, face_groups=None):

        self = col_exporter
        mesh = obj.data
        bm = None
        free_bm = False

        if obj.mode == "EDIT":
            bm = bmesh.from_edit_mesh(mesh)
        else:
            bm = bmesh.new()
            bm.from_mesh(mesh)
            free_bm = True

        try:
            bmesh.ops.triangulate(bm, faces=bm.faces[:])
            bm.verts.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            vertex_map = {}
            valid_coords = {}

            for vert in bm.verts:
                transformed_coord = self.transform_point(obj, vert.co)
                coord = (float(transformed_coord.x), float(transformed_coord.y), float(transformed_coord.z))
                if not self.is_finite_vector(coord):
                    self.skipped_invalid_vertices += 1
                    continue
                vertex_map[vert] = len(verts)
                valid_coords[vert] = coord
                verts.append(coord)

            layer = bm.faces.layers.int.get("face group")
            group_data = {}

            for face in bm.faces:
                face_verts = list(face.verts)
                if len(face_verts) != 3:
                    self.skipped_invalid_faces += 1
                    continue

                if any(vert not in vertex_map for vert in face_verts):
                    self.skipped_invalid_faces += 1
                    continue

                try:
                    area = face.calc_area()
                except ValueError:
                    area = 0.0

                if not self.is_finite_number(area) or area <= 0.000000001:
                    self.skipped_invalid_faces += 1
                    continue

                surface = self.get_collision_surface(obj, face)

                if col.Sections.version == 1:
                    faces.append(col.TFace._make(
                        [vertex_map[face_verts[0]], vertex_map[face_verts[2]], vertex_map[face_verts[1]]] + [
                            col.TSurface(*surface)
                        ]
                    ))
                else:
                    faces.append(col.TFace._make(
                        [vertex_map[face_verts[0]], vertex_map[face_verts[2]], vertex_map[face_verts[1]]] + [
                            surface[0], surface[3]
                        ]
                    ))

                if layer and face_groups is not None and col.Sections.version > 1:
                    group_index = face[layer]
                    output_index = len(faces) - 1
                    coords = [valid_coords[vert] for vert in face_verts]

                    if group_index not in group_data:
                        group_data[group_index] = {
                            "min": [coords[0][0], coords[0][1], coords[0][2]],
                            "max": [coords[0][0], coords[0][1], coords[0][2]],
                            "start": output_index,
                            "end": output_index,
                        }

                    group = group_data[group_index]
                    group["start"] = min(group["start"], output_index)
                    group["end"] = max(group["end"], output_index)

                    for coord in coords:
                        group["min"] = [min(a, b) for a, b in zip(group["min"], coord)]
                        group["max"] = [max(a, b) for a, b in zip(group["max"], coord)]

            if face_groups is not None and group_data:
                for group in sorted(group_data.values(), key=lambda item: item["start"]):
                    face_groups.append(col.TFaceGroup._make([
                        group["min"],
                        group["max"],
                        group["start"],
                        group["end"],
                    ]))

        finally:
            if free_bm and bm is not None:
                bm.free()

    #######################################################
    def _update_bounds(obj):

        # Don't include shadow meshes in bounds calculations
        if obj.dff.type == 'SHA':
            return

        self = col_exporter

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

        else:
            coords = [self.transform_point(obj, mathutils.Vector(corner)) for corner in obj.bound_box]
            if not coords:
                return
            lower_bounds = [min(coord[i] for coord in coords) for i in range(3)]
            upper_bounds = [max(coord[i] for coord in coords) for i in range(3)]
            center = [(lower_bounds[i] + upper_bounds[i]) / 2.0 for i in range(3)]
            dimensions = [upper_bounds[i] - lower_bounds[i] for i in range(3)]

        if not self.is_finite_vector(center) or not self.is_finite_vector(dimensions):
            self.skipped_invalid_vertices += 1
            return

        if obj.type == 'EMPTY':
            upper_bounds = [x + (y / 2) for x, y in zip(center, dimensions)]
            lower_bounds = [x - (y / 2) for x, y in zip(center, dimensions)]

        if not self.is_finite_vector(upper_bounds) or not self.is_finite_vector(lower_bounds):
            self.skipped_invalid_vertices += 1
            return

        self.coll.bounds = [
            [max(x, y) for x, y in zip(self.coll.bounds[0], upper_bounds)],
            [min(x, y) for x, y in zip(self.coll.bounds[1], lower_bounds)]
        ]

    #######################################################
    def _convert_bounds():
        self = col_exporter

        radius = 0.0
        center = [0, 0, 0]
        rect_min = [0, 0, 0]
        rect_max = [0, 0, 0]

        if self.coll.bounds is not None:
            rect_min = self.coll.bounds[0]
            rect_max = self.coll.bounds[1]

            if not self.is_finite_vector(rect_min) or not self.is_finite_vector(rect_max):
                rect_min = [0, 0, 0]
                rect_max = [0, 0, 0]

            center = [(x + y) / 2 for x, y in zip(rect_min, rect_max)]
            radius = (
                mathutils.Vector(rect_min) - mathutils.Vector(rect_max)
            ).magnitude / 2

            if not self.is_finite_number(radius):
                radius = 0.0

        self.coll.bounds = col.TBounds(max = col.TVector(*rect_min),
                                       min = col.TVector(*rect_max),
                                       center = col.TVector(*center),
                                       radius = radius
        )   
        
        pass
        
    #######################################################
    def _process_spheres(obj):
        self = col_exporter
        
        matrix = self.get_export_matrix(obj)
        scale = matrix.to_scale()
        center = matrix.translation
        radius = max(abs(x) * obj.empty_display_size for x in scale)
        if not self.is_finite_number(radius) or not self.is_finite_vector(center):
            self.skipped_invalid_vertices += 1
            return

        centre = col.TVector(*center)
        surface = col.TSurface(
            obj.dff.col_material,
            obj.dff.col_flags,
            obj.dff.col_brightness,
            obj.dff.col_light
        )

        self.coll.spheres.append(col.TSphere(radius=radius,
                                         surface=surface,
                                         center=centre
        ))
        
        pass
                
    #######################################################
    def _process_boxes(obj):
        self = col_exporter

        matrix = self.get_export_matrix(obj)
        center = matrix.translation
        scale = matrix.to_scale()
        box_min = center - mathutils.Vector((abs(scale.x), abs(scale.y), abs(scale.z)))
        box_max = center + mathutils.Vector((abs(scale.x), abs(scale.y), abs(scale.z)))

        if not self.is_finite_vector(box_min) or not self.is_finite_vector(box_max):
            self.skipped_invalid_vertices += 1
            return

        min = col.TVector(*box_min)
        max = col.TVector(*box_max)

        surface = col.TSurface(
            obj.dff.col_material,
            obj.dff.col_flags,
            obj.dff.col_brightness,
            obj.dff.col_light
        )

        self.coll.boxes.append(col.TBox(min=min,
                                        max=max,
                                        surface=surface,
        ))

        pass

    #######################################################
    def _process_obj(obj):
        self = col_exporter
        
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
                                   self.coll.mesh_faces,
                                   self.coll.face_groups
                )
                    
        elif obj.type == 'EMPTY':
            if obj.empty_display_type == 'SPHERE':
                self._process_spheres(obj)
            else:
                self._process_boxes(obj)

        self._update_bounds(obj)

    #######################################################
    def export_col(collection, name, objects=None):
        self = col_exporter

        col.Sections.init_sections(self.version)

        self.coll = col.ColModel()
        self.coll.version = self.version
        self.coll.model_name = os.path.basename(name)
        self.skipped_invalid_vertices = 0
        self.skipped_invalid_faces = 0

        bounds_found = False

        # Get original import bounds from collection (some collisions come in as just bounds with no other items)
        if collection.get('bounds min') and collection.get('bounds max'):
            bounds_found = True
            self.coll.bounds = [collection['bounds min'], collection['bounds max']]

        total_objects = 0
        object_source = objects if objects is not None else collection.objects
        for obj in object_source:
            if obj.dff.type == 'COL' or obj.dff.type == 'SHA':
                if not self.only_selected or obj.select_get():
                    self._process_obj(obj)
                    total_objects += 1

        if self.skipped_invalid_vertices or self.skipped_invalid_faces:
            print(
                f"DemonFF collision export: skipped {self.skipped_invalid_vertices} invalid vertex entries "
                f"and {self.skipped_invalid_faces} invalid/degenerate faces while exporting {name}"
            )

        self._convert_bounds()

        face_count = len(self.coll.mesh_faces)
        shadow_face_count = len(self.coll.shadow_faces)
        if face_count > 65535 or shadow_face_count > 65535:
            raise RuntimeError(
                "Embedded collision is too large for COL3: "
                f"{face_count} mesh faces, {shadow_face_count} shadow faces. "
                "This usually means the DFF exporter matched too many .col objects. "
                "Use one master collision object or split/reduce the collision before embedding."
            )

        if total_objects == 0 and (col_exporter.only_selected or not bounds_found):
            return b''

        return col.coll(self.coll).write_memory()

#######################################################
def split_blender_duplicate_suffix(name):
    name = str(name or "")
    if len(name) > 4 and name[-4] == "." and name[-3:].isdigit():
        return name[:-4], name[-4:]
    return name, ""

#######################################################
def get_duplicate_suffix_index(name):
    base, suffix = split_blender_duplicate_suffix(name)
    if not suffix:
        return 0

    try:
        return int(suffix[1:]) + 1
    except Exception:
        return 999999

#######################################################
def strip_col_extension_and_duplicate_suffix(name):
    name = os.path.basename(str(name or ""))

    source_extensions = (
        '.col',
        '.dff',
        '.txd',
        '.ipl',
        '.ide',
    )

    for i in range(4):
        previous_name = name
        name, suffix = split_blender_duplicate_suffix(name)

        lower_name = name.lower()
        for extension in source_extensions:
            if lower_name.endswith(extension):
                name = name[:-len(extension)]
                break

        if name == previous_name:
            break

    name = name.strip()

    if not name:
        name = 'unnamed'

    return name

#######################################################
def get_col_collection_name(collection, parent_collection=None):
    name = collection.name

    if parent_collection and parent_collection != collection:
        prefix = parent_collection.name + "."
        if name.startswith(prefix):
            name = name[len(prefix):]

    if ".col." in name.lower():
        match = re.search(r"\.col\.", name, re.IGNORECASE)
        if match:
            name = name[match.end():]

    return strip_col_extension_and_duplicate_suffix(name)

#######################################################
def get_export_file_key(name):
    name = strip_col_extension_and_duplicate_suffix(name)
    name = re.sub(r"\s+", "", name)
    return name.lower()

#######################################################
def collection_children(collection):
    try:
        return list(collection.children)
    except Exception:
        return []

#######################################################
def walk_collections(collection):
    yield collection
    for child in collection_children(collection):
        yield from walk_collections(child)

#######################################################
def is_collision_export_object(obj):
    try:
        return obj.dff.type == 'COL' or obj.dff.type == 'SHA'
    except Exception:
        return False

#######################################################
def is_selected(obj):
    try:
        return obj.select_get()
    except Exception:
        return bool(getattr(obj, 'select', False))

#######################################################
def get_collection_collision_objects(collection, selected_only=False):
    objects = []

    for obj in collection.objects:
        if not is_collision_export_object(obj):
            continue

        if selected_only and not is_selected(obj):
            continue

        objects.append(obj)

    return objects

#######################################################
def get_mass_export_candidates(root_collection):
    candidates = []
    seen = set()

    for collection in walk_collections(root_collection):
        key = collection.as_pointer()
        if key in seen:
            continue
        seen.add(key)

        objects = get_collection_collision_objects(collection, col_exporter.only_selected)
        if not objects:
            continue

        name = get_col_collection_name(collection, root_collection)
        candidates.append((
            get_export_file_key(name),
            get_duplicate_suffix_index(collection.name),
            collection.name.lower(),
            collection,
            name,
            objects,
        ))

    return candidates

#######################################################
def export_mass_col(options):
    file_name = options.get('file_name') or ''
    base_dir = options.get('directory') or os.path.dirname(file_name) or os.getcwd()
    os.makedirs(base_dir, exist_ok=True)

    scene_collection = bpy.context.scene.collection
    root_collection = col_exporter.collection or scene_collection

    output = b''
    exported_keys = set()
    exported_count = 0

    for export_key, suffix_index, collection_name, collection, name, objects in sorted(get_mass_export_candidates(root_collection), key=lambda item: item[:3]):
        if not export_key or export_key in exported_keys:
            print('DemonFF collision mass export: skipped duplicate collision collection %s' % collection.name)
            continue

        chunk = col_exporter.export_col(collection, name, objects)
        if not chunk:
            print('DemonFF collision mass export: skipped empty collision collection %s' % collection.name)
            continue

        exported_keys.add(export_key)
        export_path = os.path.join(base_dir, name + '.col')

        with open(export_path, mode='wb') as file:
            file.write(chunk)

        output += chunk
        exported_count += 1

    if exported_count == 0:
        print('DemonFF collision mass export: found no selected collision objects to export.' if col_exporter.only_selected else 'DemonFF collision mass export: found no collision objects to export.')

    if options.get('memory'):
        return output

    return None

#######################################################
def export_col(options):

    col_exporter.version = options['version']
    col_exporter.collection = options['collection']
    col_exporter.only_selected = options['only_selected']
    col_exporter.objects = options.get('objects')
    col_exporter.preserve_positions = options.get('preserve_positions', True)

    if options.get('mass_export'):
        return export_mass_col(options)

    file_name = options['file_name']
    output = b''

    if col_exporter.objects is not None:
        if not col_exporter.collection:
            return b''

        name = get_col_collection_name(col_exporter.collection)
        output += col_exporter.export_col(col_exporter.collection, name, col_exporter.objects)

    elif not col_exporter.collection:
        scene_collection = bpy.context.scene.collection
        root_collections = scene_collection.children.values() + [scene_collection]

        exported_collections = []
        for root_collection in root_collections:
            for c in root_collection.children.values() + [root_collection]:
                if c not in exported_collections:
                    name = get_col_collection_name(c, root_collection)
                    output += col_exporter.export_col(c, name)
                    exported_collections.append(c)

    else:
        root_collection = col_exporter.collection
        exported_collections = []
        for c in root_collection.children.values() + [root_collection]:
            if c not in exported_collections:
                name = get_col_collection_name(c, root_collection)
                output += col_exporter.export_col(c, name)
                exported_collections.append(c)

    if file_name:
        with open(file_name, mode='wb') as file:
            file.write(output)
        return

    return output
