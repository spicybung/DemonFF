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

import os
import zipfile

import bpy
from bpy_extras.io_utils import ImportHelper, ExportHelper
from ..ops import col_exporter, col_importer, col_samp_exporter

#######################################################
class IMPORT_OT_col(bpy.types.Operator, ImportHelper):

    bl_idname = "import_scene.col"
    bl_description = "Import GTA COL files"
    bl_label = "DemonFF COL (.col)"
    filename_ext = ""

    filepath: bpy.props.StringProperty(
        name="File path",
        maxlen=1024,
        default="",
        subtype='FILE_PATH'
    )

    filter_glob: bpy.props.StringProperty(
        default="*.col;*.COL;*.zip;*.ZIP",
        options={'HIDDEN'}
    )

    directory: bpy.props.StringProperty(
        maxlen=1024,
        default="",
        subtype='DIR_PATH',
        options={'HIDDEN'}
    )

    files: bpy.props.CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN'}
    )

    make_parent_collection: bpy.props.BoolProperty(
        name="Make Parent Collection",
        description="Put imported collision models under a parent collection named after the source COL",
        default=True
    )

    skip_empty_models: bpy.props.BoolProperty(
        name="Skip Empty Models",
        description="Do not create collections for COL models that contain no spheres, boxes, mesh, shadow mesh, or lines",
        default=True
    )

    organize_by_dff: bpy.props.BoolProperty(
        name="Organize By DFF",
        description="When a matching DFF collection exists, put the imported COL collection under it",
        default=True
    )

    #######################################################
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "make_parent_collection")
        layout.prop(self, "skip_empty_models")
        layout.prop(self, "organize_by_dff")
        return None

    #######################################################
    @staticmethod
    def get_import_paths(operator):
        paths = [os.path.join(operator.directory, file.name) for file in operator.files] if operator.files else [operator.filepath]
        fixed_paths = []

        for file_path in paths:
            fixed_paths.append(IMPORT_OT_col.fix_import_path(file_path))

        return fixed_paths

    #######################################################
    @staticmethod
    def fix_import_path(file_path):
        if not file_path:
            return file_path

        if os.path.exists(file_path):
            return file_path

        lower_path = file_path.lower()

        # Blender can be annoying with filename_ext on import operators.
        # If an older install/session produced something like COLvcs.zip.col,
        # strip the forced .col and use the real zip.
        if lower_path.endswith(".zip.col"):
            candidate = file_path[:-4]
            if os.path.exists(candidate):
                return candidate

        if lower_path.endswith(".col"):
            candidate = file_path[:-4] + ".zip"
            if os.path.exists(candidate):
                return candidate

        return file_path

    #######################################################
    @staticmethod
    def get_or_create_parent_collection(context, name):
        if (2, 80, 0) > bpy.app.version:
            return None

        collection = bpy.data.collections.get(name)
        if collection is None:
            collection = bpy.data.collections.new(name)

        try:
            context.scene.collection.children.link(collection)
        except RuntimeError:
            pass

        return collection

    #######################################################
    @staticmethod
    def link_child_collection(parent, child):
        if parent is None or child is None:
            return

        try:
            parent.children.link(child)
        except RuntimeError:
            pass

    #######################################################
    def import_col_memory(self, context, memory, collection_prefix, parent_collection=None, source_file=""):
        collections = col_importer.import_col_mem(
            memory,
            collection_prefix,
            not self.make_parent_collection and not self.organize_by_dff,
            self.skip_empty_models,
            self.organize_by_dff,
            parent_collection if self.make_parent_collection else None
        )

        for collection in collections:
            collection["demonff_col_source_file"] = source_file

            for obj in collection.objects:
                obj["demonff_col_source_file"] = source_file

        return len(collections)

    #######################################################
    def import_col_file(self, context, file_path):
        collection_prefix = os.path.splitext(os.path.basename(file_path))[0]
        parent_collection = None

        if self.make_parent_collection:
            parent_collection = self.get_or_create_parent_collection(context, collection_prefix)
            if parent_collection is not None:
                parent_collection["demonff_col_source_file"] = file_path
                parent_collection["demonff_col_library"] = collection_prefix

        with open(file_path, "rb") as file:
            memory = file.read()

        return self.import_col_memory(
            context,
            memory,
            collection_prefix,
            parent_collection,
            file_path
        )

    #######################################################
    def import_col_zip(self, context, file_path):
        zip_prefix = os.path.splitext(os.path.basename(file_path))[0]
        parent_collection = None

        if self.make_parent_collection:
            parent_collection = self.get_or_create_parent_collection(context, zip_prefix)
            if parent_collection is not None:
                parent_collection["demonff_col_source_file"] = file_path
                parent_collection["demonff_col_library"] = zip_prefix

        imported_models = 0
        imported_files = 0
        skipped_members = 0
        first_members = []

        with zipfile.ZipFile(file_path, "r") as archive:
            for member_name in archive.namelist():
                if len(first_members) < 8:
                    first_members.append(member_name)

                if member_name.endswith("/") or not member_name.lower().endswith(".col"):
                    skipped_members += 1
                    continue

                memory = archive.read(member_name)
                member_prefix = "%s.%s" % (
                    zip_prefix,
                    os.path.splitext(os.path.basename(member_name))[0]
                )

                imported_models += self.import_col_memory(
                    context,
                    memory,
                    member_prefix,
                    parent_collection,
                    "%s:%s" % (file_path, member_name)
                )
                imported_files += 1

        if imported_files == 0:
            print(
                "DemonFF COL zip import warning: %s contained no .col members. First members: %s" % (
                    file_path,
                    first_members
                )
            )

        print(
            "DemonFF COL zip import verify: %s: col_files=%d, skipped_members=%d, models=%d." % (
                file_path,
                imported_files,
                skipped_members,
                imported_models
            )
        )

        return imported_models

    #######################################################
    def execute(self, context):
        imported_models = 0
        imported_sources = 0

        for file_path in self.get_import_paths(self):
            if not file_path:
                continue

            lower_path = file_path.lower()

            if zipfile.is_zipfile(file_path):
                imported_models += self.import_col_zip(context, file_path)
                imported_sources += 1
            elif lower_path.endswith(".zip"):
                self.report({'ERROR'}, "Could not open ZIP: %s" % file_path)
            elif lower_path.endswith(".col"):
                imported_models += self.import_col_file(context, file_path)
                imported_sources += 1
            else:
                self.report({'WARNING'}, "Skipped unsupported COL import source: %s" % file_path)

        print(
            "DemonFF COL import verify: sources=%d, models=%d." % (
                imported_sources,
                imported_models
            )
        )

        self.report(
            {'INFO'},
            "Imported %d collision model(s) from %d source(s)" % (
                imported_models,
                imported_sources
            )
        )

        return {'FINISHED'}

    #######################################################
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


#######################################################
class EXPORT_OT_col(bpy.types.Operator, ExportHelper):
    
    bl_idname = "export_col.scene"
    bl_description = "Export a GTA III/VC/SA Collision File"
    bl_label = "DemonFF Collision (.col)"
    filename_ext = ".col"

    filepath: bpy.props.StringProperty(
        name="File path",
        maxlen=1024,
        default="",
        subtype='FILE_PATH'
    )
    
    filter_glob: bpy.props.StringProperty(
        default="*.col",
        options={'HIDDEN'}
    )
    
    directory: bpy.props.StringProperty(
        maxlen=1024,
        default="",
        subtype='DIR_PATH'
    )

    only_selected: bpy.props.BoolProperty(
        name="Only Selected",
        default=False
    )

    exporter_type: bpy.props.EnumProperty(
        name="Exporter Type",
        description="Choose between standard and SA-MP optimized collision exporter",
        items=[
            ('Original', "Normal Exporter", "Use normal collision"),
            ('SAMP', "SA-MP Exporter", "Use SA-MP optimized collision")
        ],
        default='Original'
    )

    
    export_version  : bpy.props.EnumProperty(
        items =
        (
            ('1', "GTA 3/VC (COLL)", "Grand Theft Auto 3 and Vice City (PC) - Version 1"),
            ('2', "GTA SA PS2 (COL2)", "Grand Theft Auto SA (PS2) - Version 2"),
            ('3', "GTA SA PC/Xbox/Mobile (COL3)", "Grand Theft Auto SA (PC/Xbox/Mobile) - Version 3"),
        ),
        name = "Version Export"
    )

    mass_export: bpy.props.BoolProperty(
        name="Mass Export",
        default=False
    )

    preserve_positions: bpy.props.BoolProperty(
        name="Preserve Collision Positions",
        description="Export collision vertices using object/source transforms instead of forcing them to local origin",
        default=True
    )

    

    #######################################################
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "exporter_type")
        layout.prop(self, "export_version")
        layout.prop(self, "only_selected")
        layout.prop(self, "mass_export")
        layout.prop(self, "preserve_positions")
        return None

    #######################################################
    def execute(self, context):
        options = {
            "file_name": self.filepath,
            "version": int(self.export_version),
            "collection": None,
            "memory": False,
            "only_selected": self.only_selected,
            "mass_export": self.mass_export,
            "preserve_positions": self.preserve_positions,
        }

        if self.mass_export:
            options["directory"] = self.directory

        # Call the correct exporter based on user selection
        if self.exporter_type == 'SAMP':
            col_samp_exporter.export_col(options)
        else:
            col_exporter.export_col(options)

        # Save settings of the export in scene custom properties for later
        context.scene['demonff_imported_version_col'] = self.export_version
            
        return {'FINISHED'}


    #######################################################
    def invoke(self, context, event):
        if 'demonff_imported_version_col' in context.scene:
            self.export_version = context.scene['demonff_imported_version_col']
        
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

def register():
    bpy.utils.register_class(IMPORT_OT_col)
    bpy.utils.register_class(EXPORT_OT_col)

def unregister():
    bpy.utils.unregister_class(EXPORT_OT_col)
    bpy.utils.unregister_class(IMPORT_OT_col)

if __name__ == "__main__":
    register()
