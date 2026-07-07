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

import os
import zipfile

import bpy
import bmesh

from ..gtaLib import col
from ..data import col_materials as mats
from .importer_common import (
    link_object, create_collection, material_helper
)


#######################################################
def clean_col_match_name(name):
    if name is None:
        return ""

    name = os.path.basename(str(name)).strip()
    name = name.replace("\\", "/").split("/")[-1]

    # Blender and collision object names often end in .001/.002.
    while "." in name and name.rsplit(".", 1)[-1].isdigit():
        name = name.rsplit(".", 1)[0]

    # Strip object role/file suffixes after numeric suffix cleanup.
    changed = True
    while changed:
        changed = False
        lower_name = name.lower()

        for suffix in (
            ".colmesh",
            ".shadowmesh",
            ".sphere",
            ".box",
            ".dff",
            ".col"
        ):
            if lower_name.endswith(suffix):
                name = name[:len(name) - len(suffix)]
                changed = True
                break

        while "." in name and name.rsplit(".", 1)[-1].isdigit():
            name = name.rsplit(".", 1)[0]
            changed = True

    # Library imports use names like COLvcs.airport.modelname.
    # The model name is the last section.
    if "." in name:
        name = name.rsplit(".", 1)[-1]

    return name.strip().lower()

#######################################################
def collection_contains_dff_object(collection):
    for obj in collection.objects:
        if obj.type != 'MESH':
            continue

        if getattr(obj, "dff", None) and obj.dff.type in {'COL', 'SHA'}:
            continue

        return True

    return False

#######################################################
def find_dff_collection_for_col_model(model_name):
    target_name = clean_col_match_name(model_name)

    if target_name == "":
        return None

    best_collection = None
    best_score = -1

    for collection in bpy.data.collections:
        collection_name = clean_col_match_name(collection.name)

        if collection_name != target_name:
            continue

        score = 0

        if collection_contains_dff_object(collection):
            score += 10

        if collection.name.lower().endswith(".dff"):
            score += 5

        if collection.name.lower() == target_name:
            score += 2

        if score > best_score:
            best_collection = collection
            best_score = score

    return best_collection

#######################################################
def link_collection_to_parent(parent_collection, child_collection):
    if parent_collection is None or child_collection is None:
        return False

    try:
        parent_collection.children.link(child_collection)
    except RuntimeError:
        pass

    # A collection can be linked in multiple places. If it was already linked
    # to the scene root, remove that root link so the same COL does not show up
    # both inside and outside its DFF collection.
    unlink_collection_from_scene_root(child_collection)
    return True

#######################################################
def link_collection_to_scene(child_collection):
    try:
        bpy.context.scene.collection.children.link(child_collection)
        return True
    except RuntimeError:
        return False

#######################################################
def unlink_collection_from_scene_root(child_collection):
    if child_collection is None:
        return False

    try:
        bpy.context.scene.collection.children.unlink(child_collection)
        return True
    except RuntimeError:
        return False

#######################################################
def get_surface_from_face(face):
    if hasattr(face, "surface"):
        return face.surface

    return col.TSurface(face.material, 0, 1, face.light)

#######################################################
def get_first_model_surface(model):
    if model.mesh_faces:
        return get_surface_from_face(model.mesh_faces[0])

    if model.boxes:
        return model.boxes[0].surface

    if model.spheres:
        return model.spheres[0].surface

    return None

#######################################################
def collect_model_surfaces(model):
    surfaces = []

    for face in model.mesh_faces:
        surfaces.append(get_surface_from_face(face))

    for box in model.boxes:
        surfaces.append(box.surface)

    for sphere in model.spheres:
        surfaces.append(sphere.surface)

    return surfaces

#######################################################
def make_col_material(surface):
    colour = mats.groups[mats.default['group']][1]
    name = mats.groups[mats.default['group']][0]

    try:
        if col.Sections.version == 3 or surface.material >= 34:
            mat_info = mats.sa_mats[surface.material]
        else:
            mat_info = mats.vc_mats[surface.material]

        colour = mats.groups[mat_info[0]][1]
        name = "%s - %s" % (mats.groups[mat_info[0]][0], mat_info[1])

    except KeyError:
        name = "COL Material %d" % surface.material

    colour = [colour[0:2], colour[2:4], colour[4:6], "FF"]
    colour = [int(x, 16) for x in colour]

    material = bpy.data.materials.new(name)
    material.dff.col_mat_index = surface.material
    material.dff.col_brightness = surface.brightness
    material.dff.col_light = surface.light

    helper = material_helper(material)
    helper.set_base_color(colour)

    return helper.material

#######################################################
def set_object_surface_info(obj, surface):
    if surface is None:
        return

    obj.dff.type = 'COL'
    obj.dff.col_material = surface.material
    obj.dff.col_flags = surface.flags
    obj.dff.col_brightness = surface.brightness
    obj.dff.col_light = surface.light

#######################################################
def apply_surfaces_to_mesh(obj, surfaces, face_surfaces=None):
    if obj.type != 'MESH' or not obj.data or not surfaces:
        return

    obj.data.materials.clear()

    surface_to_index = {}

    for surface in surfaces:
        if surface not in surface_to_index:
            surface_to_index[surface] = len(surface_to_index)
            obj.data.materials.append(make_col_material(surface))

    if face_surfaces and len(face_surfaces) == len(obj.data.polygons):
        for polygon, surface in zip(obj.data.polygons, face_surfaces):
            polygon.material_index = surface_to_index.get(surface, 0)
    else:
        for polygon in obj.data.polygons:
            polygon.material_index = 0

#######################################################
def get_col_model_map_from_memory(memory):
    collision = col.coll()
    collision.load_memory(memory)

    model_map = {}

    for model in collision.models:
        key = clean_col_match_name(model.model_name)
        if key:
            model_map[key] = model

    return model_map

#######################################################
def load_col_model_map_from_file(file_path):
    model_map = {}

    if not os.path.exists(file_path):
        lower_path = file_path.lower()

        if lower_path.endswith(".zip.col"):
            candidate = file_path[:-4]
            if os.path.exists(candidate):
                file_path = candidate
        elif lower_path.endswith(".col"):
            candidate = file_path[:-4] + ".zip"
            if os.path.exists(candidate):
                file_path = candidate

    if zipfile.is_zipfile(file_path):
        with zipfile.ZipFile(file_path, "r") as archive:
            for member_name in archive.namelist():
                if member_name.endswith("/") or not member_name.lower().endswith(".col"):
                    continue

                member_map = get_col_model_map_from_memory(archive.read(member_name))
                model_map.update(member_map)

        return model_map

    with open(file_path, "rb") as file:
        model_map.update(get_col_model_map_from_memory(file.read()))

    return model_map

#######################################################
def get_object_col_candidate_names(obj):
    names = []

    for key in ("demonff_col_model_name", "DFF_Name", "Pawn_DFF_Path", "Pawn_Model_ID"):
        value = obj.get(key)
        if value not in (None, ""):
            names.append(value)

    if hasattr(obj, "dff_map"):
        for value in (
            getattr(obj.dff_map, "model_name", ""),
            getattr(obj.dff_map, "ide_model_name", "")
        ):
            if value not in (None, ""):
                names.append(value)

    if hasattr(obj, "ide"):
        value = getattr(obj.ide, "model_name", "")
        if value not in (None, ""):
            names.append(value)

    names.append(obj.name)

    for collection in obj.users_collection:
        names.append(collection.name)

    return [clean_col_match_name(name) for name in names if clean_col_match_name(name)]

#######################################################
def object_is_col_library_import(obj):
    if obj.get("demonff_col_source_file") not in (None, ""):
        return True

    if obj.get("demonff_col_library") not in (None, ""):
        return True

    for collection in obj.users_collection:
        if collection.get("demonff_col_source_file") not in (None, ""):
            return True

        if collection.get("demonff_col_library") not in (None, ""):
            return True

    return False

#######################################################
def apply_col_model_info_to_object(obj, model, source_file=""):
    surface = get_first_model_surface(model)

    if surface is None:
        return False

    # Import COL Info is an overwrite/update operation. It must not create
    # reference COL geometry and it must not mark the target as an imported
    # library object.
    set_object_surface_info(obj, surface)

    if obj.type == 'MESH':
        face_surfaces = [get_surface_from_face(face) for face in model.mesh_faces]
        surfaces = face_surfaces if face_surfaces else collect_model_surfaces(model)

        if not surfaces:
            surfaces = [surface]

        apply_surfaces_to_mesh(obj, surfaces, face_surfaces)

    obj["demonff_col_info_applied"] = True
    obj["demonff_col_info_source_file"] = source_file
    obj["demonff_col_info_model_name"] = model.model_name
    obj["demonff_col_info_model_id"] = int(model.model_id)
    obj["demonff_col_info_version"] = int(model.version)

    return True

#######################################################
def apply_col_info_from_file(file_path, selected_only=False):
    model_map = load_col_model_map_from_file(file_path)

    if selected_only:
        objects = bpy.context.selected_objects
    else:
        objects = bpy.context.scene.objects

    applied = 0
    missing = 0
    skipped_source_imports = 0
    skipped_not_collision = 0

    for obj in objects:
        if getattr(obj, "dff", None) is None:
            continue

        if obj.dff.type not in {'COL', 'SHA'}:
            skipped_not_collision += 1
            continue

        # Do not update COL geometry that came from COL-library importing.
        # Import COL Info is supposed to overwrite details on the scene's
        # existing duplicated/embedded collision objects.
        if object_is_col_library_import(obj):
            skipped_source_imports += 1
            continue

        model = None

        for candidate_name in get_object_col_candidate_names(obj):
            model = model_map.get(candidate_name)

            if model is not None:
                break

        if model is None:
            missing += 1
            continue

        if apply_col_model_info_to_object(obj, model, file_path):
            applied += 1

    print(
        "DemonFF COL info import verify: source=%s, models=%d, applied_objects=%d, missing_objects=%d, skipped_col_library_imports=%d, skipped_not_collision=%d." % (
            file_path,
            len(model_map),
            applied,
            missing,
            skipped_source_imports,
            skipped_not_collision
        )
    )

    return applied

#######################################################        
class col_importer:
    
    #######################################################
    def __init__(self, col):
        self.col = col

    #######################################################
    def from_file(filename):

        collision = col.coll()
        collision.load_file(filename)

        return col_importer(collision)

    #######################################################
    def from_mem(memory):

        collision = col.coll()
        collision.load_memory(memory)

        return col_importer(collision)

    #######################################################
    def model_count(self):
        return len(self.col.models)
    
    #######################################################
    def __add_spheres(self, collection, array):

        for index, entity in enumerate(array):
            name = collection.name + ".Sphere.%d" % (index)
        
            obj  = bpy.data.objects.new(name, None)
            
            obj.location = entity.center
            obj.scale = [entity.radius] * 3
            if (2, 80, 0) > bpy.app.version:
                obj.empty_draw_type = 'SPHERE'
            else:
                obj.empty_display_type = 'SPHERE'

            obj.dff.type = 'COL'
            obj.dff.col_material = entity.surface.material
            obj.dff.col_flags = entity.surface.flags
            obj.dff.col_brightness = entity.surface.brightness
            obj.dff.col_light = entity.surface.light
            
            link_object(obj, collection)

    #######################################################
    def __get_vector_values(self, vector):
        if hasattr(vector, "x"):
            return (vector.x, vector.y, vector.z)

        return (vector[0], vector[1], vector[2])

    #######################################################
    def __add_boxes(self, collection, array):

        for index, entity in enumerate(array):
            name = collection.name + ".Box.%d" % index

            min_x, min_y, min_z = self.__get_vector_values(entity.min)
            max_x, max_y, max_z = self.__get_vector_values(entity.max)

            verts = [
                (min_x, min_y, min_z),
                (max_x, min_y, min_z),
                (max_x, max_y, min_z),
                (min_x, max_y, min_z),
                (min_x, min_y, max_z),
                (max_x, min_y, max_z),
                (max_x, max_y, max_z),
                (min_x, max_y, max_z),
            ]

            faces = [
                (0, 1, 2, 3),
                (4, 7, 6, 5),
                (0, 4, 5, 1),
                (1, 5, 6, 2),
                (2, 6, 7, 3),
                (3, 7, 4, 0),
            ]

            mesh = bpy.data.meshes.new(name)
            mesh.from_pydata(verts, [], faces)
            mesh.update()

            obj = bpy.data.objects.new(name, mesh)
            obj.dff.type = 'COL'
            obj.dff.col_material = entity.surface.material
            obj.dff.col_flags = entity.surface.flags
            obj.dff.col_brightness = entity.surface.brightness
            obj.dff.col_light = entity.surface.light

            self.__add_mesh_mats(obj, [entity.surface])

            for face in mesh.polygons:
                face.material_index = 0

            link_object(obj, collection)

    #######################################################
    def __add_mesh_mats(self, object, materials):

        for surface in materials:
            
            colour = mats.groups[mats.default['group']][1]
            name = mats.groups[mats.default['group']][0]
            
            try:
                # SA
                if col.Sections.version == 3 or surface.material >= 34:
                    mat = mats.sa_mats[surface.material]
                    
                # VC/III
                else:
                    mat = mats.vc_mats[surface.material]
                
                # Generate names
                colour = mats.groups[mat[0]][1]
                name = "%s - %s" % (mats.groups[mat[0]][0], mat[1])

            except KeyError:
                pass

            # Convert hex to a value Blender understands
            colour = [colour[0:2], colour[2: 4], colour[4: 6], "FF"]
            colour = [int(x, 16) for x in colour]

            mat = bpy.data.materials.new(name)
            mat.dff.col_mat_index   = surface.material
            mat.dff.col_brightness  = surface.brightness
            mat.dff.col_light       = surface.light

            helper = material_helper(mat)
            helper.set_base_color(colour)
            
            object.data.materials.append(helper.material)
            
    #######################################################
    def __add_mesh(self, collection, name, verts, faces, shadow=False):

        mesh      = bpy.data.meshes.new(name)
        materials = {}
        
        bm = bmesh.new()

        for v in verts:
            bm.verts.new(v)

        bm.verts.ensure_lookup_table()
            
        for f in faces:
            try:
                face = bm.faces.new(
                    [
                        bm.verts[f.a],
                        bm.verts[f.b],
                        bm.verts[f.c]
                    ]
                )
                if hasattr(f, "surface"):
                    surface = f.surface
                else:
                    surface = col.TSurface(f.material, 0, 1, f.light)

                if surface not in materials:
                    materials[surface] = len(materials)
                
                face.material_index = materials[surface]

            except Exception as e:
                print(e)
                
            bm.to_mesh(mesh)
        
        obj = bpy.data.objects.new(name, mesh)
        obj.dff.type = 'SHA' if shadow else 'COL'
        
        link_object(obj, collection)

        self.__add_mesh_mats(obj, materials)
            
    #######################################################
    def add_to_scene(self, collection_prefix, link=True, skip_empty_models=True, organize_by_dff=False, parent_collection=None):

        collection_list = []

        for model_index, model in enumerate(self.col.models):

            if skip_empty_models and not (
                model.spheres or
                model.boxes or
                model.mesh_verts or
                model.shadow_verts or
                model.lines
            ):
                continue

            model_name = model.model_name if model.model_name else "unnamed_%04d" % model_index
            target_collection = find_dff_collection_for_col_model(model_name) if organize_by_dff else None
            link_to_scene_now = link and target_collection is None and parent_collection is None

            collection = create_collection("%s.%s" % (collection_prefix,
                                                           model_name),
                                           link_to_scene_now
            )

            collection["demonff_col_library"] = collection_prefix
            collection["demonff_col_model_name"] = model_name
            collection["demonff_col_model_id"] = int(model.model_id)
            collection["demonff_col_version"] = int(model.version)
            collection["demonff_col_model_index"] = int(model_index)

            if target_collection is not None:
                collection["demonff_col_attached_to_dff_collection"] = target_collection.name

            self.__add_spheres(collection, model.spheres)
            self.__add_boxes(collection, model.boxes)

            if len(model.mesh_verts) > 0:
                self.__add_mesh(collection,
                                collection.name + ".ColMesh",
                                model.mesh_verts,
                                model.mesh_faces)

            if len(model.shadow_verts) > 0:
                self.__add_mesh(collection,
                                collection.name + ".ShadowMesh",
                                model.shadow_verts,
                                model.shadow_faces,
                                True)

            for obj in collection.objects:
                obj["demonff_col_library"] = collection_prefix
                obj["demonff_col_model_name"] = model_name
                obj["demonff_col_model_id"] = int(model.model_id)
                obj["demonff_col_version"] = int(model.version)
                obj["demonff_col_model_index"] = int(model_index)

                if target_collection is not None:
                    obj["demonff_col_attached_to_dff_collection"] = target_collection.name

            if target_collection is not None:
                link_collection_to_parent(target_collection, collection)
            elif parent_collection is not None:
                link_collection_to_parent(parent_collection, collection)
            elif not link_to_scene_now:
                link_collection_to_scene(collection)

            collection_list.append(collection)

        return collection_list


#######################################################
def import_col_file(filename, collection_prefix, link=True, skip_empty_models=True, organize_by_dff=False, parent_collection=None):

    col = col_importer.from_file(filename)
    return col.add_to_scene(collection_prefix, link, skip_empty_models, organize_by_dff, parent_collection)

#######################################################
def import_col_mem(mem, collection_prefix, link=True, skip_empty_models=True, organize_by_dff=False, parent_collection=None):

    col = col_importer.from_mem(mem)
    return col.add_to_scene(collection_prefix, link, skip_empty_models, organize_by_dff, parent_collection)
#######################################################
def import_col_zip_file(filename, collection_prefix=None, link=True, skip_empty_models=True, organize_by_dff=True, parent_collection=None):
    if collection_prefix is None:
        collection_prefix = os.path.splitext(os.path.basename(filename))[0]

    collection_list = []
    imported_files = 0
    skipped_members = 0

    with zipfile.ZipFile(filename, "r") as archive:
        for member_name in archive.namelist():
            if member_name.endswith("/") or not member_name.lower().endswith(".col"):
                skipped_members += 1
                continue

            member_prefix = "%s.%s" % (
                collection_prefix,
                os.path.splitext(os.path.basename(member_name))[0]
            )

            collection_list.extend(
                import_col_mem(
                    archive.read(member_name),
                    member_prefix,
                    link,
                    skip_empty_models,
                    organize_by_dff,
                    parent_collection
                )
            )
            imported_files += 1

    print(
        "DemonFF COL zip import verify: %s: col_files=%d, skipped_members=%d, imported_collections=%d." % (
            filename,
            imported_files,
            skipped_members,
            len(collection_list)
        )
    )

    return collection_list
