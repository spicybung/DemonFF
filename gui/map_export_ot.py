# DemonFF - Blender map export operators
# 2023 - 2026 spicybung

import bpy
import os
import math
import mathutils

from bpy.props import CollectionProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from ..ops import map_exporter


class ExportToIPLOperator(bpy.types.Operator, ExportHelper):
    bl_idname = "object.export_to_ipl"
    bl_label = "Export to IPL"
    bl_description = "Export selected objects as an IPL file"
    filename_ext = ".ipl"

    filter_glob: bpy.props.StringProperty(default="*.ipl", options={'HIDDEN'})

    def execute(self, context):
        if not [obj for obj in context.selected_objects if map_exporter.object_is_exportable_map_instance(obj)]:
            self.report({'INFO'}, "No exportable map mesh selected")
            return {'CANCELLED'}

        output_file, written = map_exporter.export_ipl_file(
            context,
            self.filepath,
            only_selected=True,
            skip_lod=context.scene.dff.skip_lod,
            game_id=context.scene.dff.game_version_dropdown,
        )

        self.report({'INFO'}, f"Exported {written} IPL object(s) to {output_file}")
        return {'FINISHED'}


class ExportToIDEOperator(bpy.types.Operator, ExportHelper):
    bl_idname = "object.export_to_ide"
    bl_label = "Export to IDE"
    bl_description = "Export scene objects as an IDE file"
    filename_ext = ".ide"

    filter_glob: bpy.props.StringProperty(default="*.ide", options={'HIDDEN'})

    def execute(self, context):
        output_file, written = map_exporter.export_ide_file(
            context,
            self.filepath,
            skip_lod=context.scene.dff.skip_lod,
        )

        if written == 0:
            self.report({'INFO'}, "No exportable map object definitions found")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported {written} IDE object definition(s) to {output_file}")
        return {'FINISHED'}


class ExportToPawnOperator(bpy.types.Operator, ExportHelper):
    bl_idname = "object.export_to_pawn"
    bl_label = "Export to Pawn Script"
    bl_description = "Export selected objects as CreateDynamicObject lines and artconfig AddSimpleModel lines"
    filename_ext = ".pwn"

    filter_glob: bpy.props.StringProperty(default="*.pwn;*.inc", options={'HIDDEN'})
    model_directory: bpy.props.StringProperty(name="Model Directory", default="", description="Model directory for artconfig DFF paths")
    texture_directory: bpy.props.StringProperty(name="Texture Directory", default="", description="Texture directory for artconfig TXD paths. Blank uses the model directory.")
    txd_mode: bpy.props.EnumProperty(
        name="TXD Packing",
        items=(
            ('REFERENCE', "Use Existing TXD Names", "Write the existing object or IDE TXD names without generating texture dictionaries"),
            ('PER_MODEL', "One TXD Per Model", "Create one TXD containing all Blender material textures used by each exported model"),
            ('NEIGHBORHOOD', "Pack TXDs Per Neighborhood", "Share TXDs between models in the same marked or spatially inferred neighborhood"),
        ),
        default='REFERENCE',
    )
    txd_output_directory: bpy.props.StringProperty(
        name="Generated TXD Folder",
        default="",
        subtype='DIR_PATH',
        description="Physical output folder for generated TXDs. Blank creates them below the PWN folder using Texture Directory or Model Directory",
    )
    maximum_textures_per_txd: bpy.props.IntProperty(
        name="Maximum Textures Per TXD",
        default=256,
        min=1,
        max=999,
        description="Neighborhood packs split before exceeding this many unique texture names",
    )
    neighborhood_cell_size: bpy.props.FloatProperty(
        name="Neighborhood Cell Size",
        default=600.0,
        min=1.0,
        description="XY cell size used when objects have not been organized into marked neighborhood collections",
    )
    skip_lod: bpy.props.BoolProperty(name="Skip LOD Objects", default=True)
    stream_distance: bpy.props.FloatProperty(name="Stream Distance", default=300.0)
    draw_distance: bpy.props.FloatProperty(name="Draw Distance", default=300.0)
    x_offset: bpy.props.FloatProperty(name="X Offset", default=0.0)
    y_offset: bpy.props.FloatProperty(name="Y Offset", default=0.0)
    z_offset: bpy.props.FloatProperty(name="Z Offset", default=0.0)
    force_all_worlds_interiors: bpy.props.BoolProperty(
        name="Ignore IPL Interior/World",
        default=True,
        description="Write CreateDynamicObject world/interior as -1/-1 so VCS IPL interior values do not hide exterior map objects",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "model_directory")
        layout.prop(self, "texture_directory")
        layout.prop(self, "txd_mode")
        if self.txd_mode != 'REFERENCE':
            layout.prop(self, "txd_output_directory")
            layout.prop(self, "maximum_textures_per_txd")
        if self.txd_mode == 'NEIGHBORHOOD':
            layout.prop(self, "neighborhood_cell_size")
        layout.prop(self, "skip_lod")
        layout.prop(self, "stream_distance")
        layout.prop(self, "draw_distance")
        layout.prop(self, "x_offset")
        layout.prop(self, "y_offset")
        layout.prop(self, "z_offset")
        layout.prop(self, "force_all_worlds_interiors")

    def execute(self, context):
        map_exporter.export_pawn({
            "file_name": self.filepath,
            "only_selected": True,
            "model_directory": self.model_directory,
            "texture_directory": self.texture_directory,
            "txd_mode": self.txd_mode,
            "txd_output_directory": self.txd_output_directory,
            "maximum_textures_per_txd": self.maximum_textures_per_txd,
            "neighborhood_cell_size": self.neighborhood_cell_size,
            "skip_lod": self.skip_lod,
            "stream_distance": self.stream_distance,
            "draw_distance": self.draw_distance,
            "x_offset": self.x_offset,
            "y_offset": self.y_offset,
            "z_offset": self.z_offset,
            "force_all_worlds_interiors": self.force_all_worlds_interiors,
        })

        if not map_exporter.pwn_exporter.total_objects_num:
            self.report({'ERROR'}, "No exportable selected meshes found")
            return {'CANCELLED'}

        summary = map_exporter.pwn_exporter.last_export_summary
        message = "Exported %d selected object(s)" % map_exporter.pwn_exporter.total_objects_num
        if summary.get("generated_txd_count", 0):
            message += "; generated %d TXD pack(s) with %d texture(s)" % (
                summary["generated_txd_count"],
                summary.get("generated_texture_count", 0),
            )
        if summary.get("asset_warning_count", 0):
            message += "; %d asset warning(s) are listed in the manifest and console" % summary["asset_warning_count"]
        self.report({'INFO'}, message)
        return {'FINISHED'}


class OrganizeObjNeighborhoodsOperator(bpy.types.Operator):
    bl_idname = "object.demonff_organize_obj_neighborhoods"
    bl_label = "Organize OBJ Neighborhoods"
    bl_description = "Group a flat OBJ city scene into spatial neighborhood collections for Pawn and TXD export"
    bl_options = {'REGISTER', 'UNDO'}

    only_selected: bpy.props.BoolProperty(
        name="Only Selected",
        default=True,
        description="Organize selected mesh hierarchies only. Disable to organize every mesh in the scene",
    )
    root_collection_name: bpy.props.StringProperty(
        name="Root Collection",
        default="Empire Bay Neighborhoods",
    )
    neighborhood_cell_size: bpy.props.FloatProperty(
        name="Neighborhood Cell Size",
        default=600.0,
        min=1.0,
        description="Width and height of each XY neighborhood region",
    )
    keep_existing_collection_links: bpy.props.BoolProperty(
        name="Keep Existing Collection Links",
        default=False,
        description="Keep objects linked to their old import collections as well as the new neighborhood collections",
    )
    recenter_geometry: bpy.props.BoolProperty(
        name="Recenter OBJ Geometry",
        default=True,
        description="Move world-space OBJ vertices around a local model origin while preserving their visible world position, so DFF and Pawn placement export use sane coordinates",
    )
    use_empty_parent_hierarchies: bpy.props.BoolProperty(
        name="Empty Parents Define Models",
        default=False,
        description="Keep mesh children grouped under Empty parents as one model. Leave disabled for OBJ imports that use one shared scene Empty",
    )

    @staticmethod
    def get_hierarchy_root(obj, use_empty_parent_hierarchies):
        if not use_empty_parent_hierarchies:
            return obj

        root = obj
        while root.parent is not None and root.parent.type == 'EMPTY':
            root = root.parent
        return root

    @staticmethod
    def get_hierarchy_objects(root):
        objects = []
        pending = [root]
        seen = set()

        while pending:
            obj = pending.pop()
            try:
                object_key = obj.as_pointer()
            except Exception:
                object_key = id(obj)
            if object_key in seen:
                continue
            seen.add(object_key)
            objects.append(obj)
            pending.extend(list(obj.children))

        return objects

    @staticmethod
    def get_hierarchy_center(objects, fallback_root):
        minimum = None
        maximum = None

        for obj in objects:
            if obj.type != 'MESH' or not getattr(obj, 'bound_box', None):
                continue

            for corner in obj.bound_box:
                world_corner = obj.matrix_world @ mathutils.Vector(corner)
                if minimum is None:
                    minimum = world_corner.copy()
                    maximum = world_corner.copy()
                else:
                    minimum.x = min(minimum.x, world_corner.x)
                    minimum.y = min(minimum.y, world_corner.y)
                    minimum.z = min(minimum.z, world_corner.z)
                    maximum.x = max(maximum.x, world_corner.x)
                    maximum.y = max(maximum.y, world_corner.y)
                    maximum.z = max(maximum.z, world_corner.z)

        if minimum is not None:
            return (minimum + maximum) * 0.5

        return fallback_root.matrix_world.translation.copy()

    @staticmethod
    def recenter_hierarchy(root, objects, world_center):
        stored_world_matrices = {
            obj.as_pointer(): obj.matrix_world.copy()
            for obj in objects
            if obj != root
        }

        if root.type == 'MESH' and root.data is not None:
            if root.data.users > 1:
                root.data = root.data.copy()

            original_matrix = root.matrix_world.copy()
            try:
                local_center = original_matrix.inverted() @ world_center
            except Exception:
                local_center = mathutils.Vector((0.0, 0.0, 0.0))

            if local_center.length > 1e-7:
                root.data.transform(mathutils.Matrix.Translation(-local_center))
                root.matrix_world = original_matrix @ mathutils.Matrix.Translation(local_center)
                root.data.update()
        else:
            root_matrix = root.matrix_world.copy()
            if (root_matrix.translation - world_center).length > 1e-7:
                root_matrix.translation = world_center
                root.matrix_world = root_matrix

        for obj in objects:
            if obj == root:
                continue
            stored_matrix = stored_world_matrices.get(obj.as_pointer())
            if stored_matrix is not None:
                obj.matrix_world = stored_matrix

        try:
            root["DemonFF_OBJ_Recentered"] = True
        except Exception:
            pass

    @staticmethod
    def ensure_child_collection(parent, name):
        collection = bpy.data.collections.get(name)
        if collection is None:
            collection = bpy.data.collections.new(name)
        if parent.children.get(collection.name) is None:
            parent.children.link(collection)
        return collection

    @staticmethod
    def get_hierarchy_model_name(objects, root):
        for obj in objects:
            if obj.type != 'MESH':
                continue
            model_name = map_exporter.normalize_export_asset_name(
                map_exporter.get_pawn_model_name(obj),
                ".dff",
            )
            if model_name:
                return model_name

        return map_exporter.normalize_export_asset_name(root.name, ".dff") or "model"

    @staticmethod
    def ensure_model_collection(parent, model_name, extension, neighborhood_name):
        model_key = model_name.lower()
        collection_kind = extension.lower().lstrip('.')

        for child in parent.children:
            try:
                child_model_key = str(child.get("demonff_model_key", "") or "").lower()
                child_kind = str(child.get("demonff_model_collection_kind", "") or "").lower()
                child_neighborhood = str(child.get("demonff_neighborhood_name", "") or "")
            except Exception:
                continue

            if (
                child_model_key == model_key
                and child_kind == collection_kind
                and child_neighborhood == neighborhood_name
            ):
                return child

        collection = bpy.data.collections.new(model_name + extension)
        parent.children.link(collection)
        collection["demonff_model_key"] = model_key
        collection["demonff_model_name"] = model_name
        collection["demonff_model_collection_kind"] = collection_kind
        collection["demonff_neighborhood_name"] = neighborhood_name
        return collection

    @staticmethod
    def move_object_to_collection(obj, target_collection, keep_existing_links):
        if target_collection.objects.get(obj.name) is None:
            target_collection.objects.link(obj)

        if keep_existing_links:
            return

        for source_collection in list(obj.users_collection):
            if source_collection == target_collection:
                continue
            try:
                source_collection.objects.unlink(obj)
            except Exception:
                pass

    @staticmethod
    def get_category_name(objects):
        for obj in objects:
            if obj.type != 'MESH':
                continue
            dff_type = map_exporter.get_dff_type(obj)
            lower_name = obj.name.lower()
            if dff_type in {'COL', 'SHA'} or '.colmesh' in lower_name or lower_name.endswith('.col'):
                return "Collision"

        if any(obj.type == 'MESH' for obj in objects):
            return "Models"
        return "Helpers"

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "only_selected")
        layout.prop(self, "root_collection_name")
        layout.prop(self, "neighborhood_cell_size")
        layout.prop(self, "use_empty_parent_hierarchies")
        layout.prop(self, "recenter_geometry")
        layout.prop(self, "keep_existing_collection_links")

    def execute(self, context):
        mesh_objects = [obj for obj in context.scene.objects if obj.type == 'MESH']
        if self.only_selected:
            selected_mesh_objects = {}
            pending = list(context.selected_objects)
            visited = set()

            while pending:
                obj = pending.pop()
                try:
                    object_key = obj.as_pointer()
                except Exception:
                    object_key = id(obj)
                if object_key in visited:
                    continue
                visited.add(object_key)

                if obj.type == 'MESH':
                    selected_mesh_objects[object_key] = obj
                pending.extend(list(obj.children))

            mesh_objects = list(selected_mesh_objects.values())

        if not mesh_objects:
            self.report({'WARNING'}, "No mesh objects were available for neighborhood organization.")
            return {'CANCELLED'}

        hierarchy_units = {}
        for obj in mesh_objects:
            if (
                not self.use_empty_parent_hierarchies
                and obj.parent is not None
                and obj.parent.type == 'EMPTY'
            ):
                world_matrix = obj.matrix_world.copy()
                obj.parent = None
                obj.matrix_world = world_matrix

            root = self.get_hierarchy_root(
                obj,
                self.use_empty_parent_hierarchies,
            )
            hierarchy_units[root.as_pointer()] = {
                "root": root,
                "objects": self.get_hierarchy_objects(root),
            }

        units = list(hierarchy_units.values())
        recentered_units = 0
        for unit in units:
            unit["center"] = self.get_hierarchy_center(unit["objects"], unit["root"])
            if self.recenter_geometry:
                self.recenter_hierarchy(
                    unit["root"],
                    unit["objects"],
                    unit["center"],
                )
                recentered_units += 1

        minimum_x = min(unit["center"].x for unit in units)
        minimum_y = min(unit["center"].y for unit in units)
        cell_size = max(float(self.neighborhood_cell_size), 1.0)

        root_name = self.root_collection_name.strip() or "Neighborhoods"
        root_collection = bpy.data.collections.get(root_name)
        if root_collection is None:
            root_collection = bpy.data.collections.new(root_name)
        if context.scene.collection.children.get(root_collection.name) is None:
            context.scene.collection.children.link(root_collection)
        root_collection["demonff_neighborhood_root"] = True
        root_collection["demonff_neighborhood_cell_size"] = cell_size

        moved_objects = 0
        neighborhood_names = set()

        for unit in sorted(units, key=lambda item: (item["center"].y, item["center"].x, item["root"].name.lower())):
            x_index = int(math.floor((unit["center"].x - minimum_x) / cell_size))
            y_index = int(math.floor((unit["center"].y - minimum_y) / cell_size))
            neighborhood_short_name = "Neighborhood_%02d_%02d" % (x_index, y_index)
            neighborhood_collection_name = "%s %s" % (root_name, neighborhood_short_name)
            neighborhood_collection = self.ensure_child_collection(
                root_collection,
                neighborhood_collection_name,
            )
            neighborhood_collection["demonff_neighborhood"] = True
            neighborhood_collection["demonff_neighborhood_name"] = neighborhood_short_name
            neighborhood_collection["demonff_neighborhood_x"] = x_index
            neighborhood_collection["demonff_neighborhood_y"] = y_index

            category_name = self.get_category_name(unit["objects"])
            category_collection = self.ensure_child_collection(
                neighborhood_collection,
                "%s %s" % (neighborhood_collection_name, category_name),
            )
            category_collection["demonff_neighborhood_category"] = category_name

            model_name = self.get_hierarchy_model_name(unit["objects"], unit["root"])
            if category_name == "Models":
                target_collection = self.ensure_model_collection(
                    category_collection,
                    model_name,
                    ".dff",
                    neighborhood_short_name,
                )
            elif category_name == "Collision":
                target_collection = self.ensure_model_collection(
                    category_collection,
                    model_name,
                    ".col",
                    neighborhood_short_name,
                )
            else:
                target_collection = category_collection

            for obj in unit["objects"]:
                self.move_object_to_collection(
                    obj,
                    target_collection,
                    self.keep_existing_collection_links,
                )
                try:
                    obj["DemonFF_Neighborhood"] = neighborhood_short_name
                    if category_name == "Models" and obj.type == 'MESH':
                        obj["DFF_Name"] = model_name
                except Exception:
                    pass
                moved_objects += 1

            neighborhood_names.add(neighborhood_short_name)

        self.report(
            {'INFO'},
            "Organized %d hierarchy object(s) into %d spatial neighborhood(s) below '%s'; recentered %d hierarchy root(s)." % (
                moved_objects,
                len(neighborhood_names),
                root_collection.name,
                recentered_units,
            ),
        )
        return {'FINISHED'}


class RemoveBuildingForPlayerOperator(bpy.types.Operator):
    bl_idname = "object.remove_building_for_player"
    bl_label = "Remove Building For Player"
    bl_description = "Mark selected retail buildings for Pawn removal and print the commands"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        objects = [obj for obj in context.selected_objects if map_exporter.object_is_exportable_map_instance(obj)]
        catalog = map_exporter.collect_samp_retail_catalog(context)
        marked = 0
        for obj in objects:
            lines = map_exporter.make_remove_building_lines((obj,), catalog)
            if not lines:
                continue
            for line in lines:
                print(line)
            source = map_exporter.get_metadata_source(obj)
            source["DemonFF_RemoveBuilding"] = True
            marked += 1
        self.report({'INFO'}, f"Marked {marked} building(s) for Pawn removal and printed their lines")
        return {'FINISHED'}
