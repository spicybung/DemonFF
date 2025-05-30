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
import time

from ..ops.state import State
from ..gtaLib import txd as txd_lib
from bpy_extras.io_utils import ImportHelper, ExportHelper
from ..ops import dff_exporter, dff_importer, col_importer, samp_exporter, txd_importer


#######################################################
class EXPORT_OT_dff_custom(bpy.types.Operator, ExportHelper):
    
    bl_idname = "export_dff_custom.scene"
    bl_description = "Export a Renderware .DFF or .COL File"
    bl_label = "DFF/Col Export (.dff/.col)"
    filename_ext = ".dff"

    filepath: bpy.props.StringProperty(name="File path",
                                       maxlen=1024,
                                       default="",
                                       subtype='FILE_PATH')
    
    filter_glob: bpy.props.StringProperty(default="*.dff;*.col",
                                          options={'HIDDEN'})
    
    directory: bpy.props.StringProperty(maxlen=1024,
                                        default="",
                                        subtype='FILE_PATH')

    mass_export: bpy.props.BoolProperty(
        name="Mass Export",
        default=False
    )

    export_coll: bpy.props.BoolProperty(
        name="Export Collision",
        default=True
    )
    
    export_frame_names: bpy.props.BoolProperty(
        name="Export Frame Names",
        default=True
    )

    truncate_frame_names: bpy.props.BoolProperty(
        name="Truncate Frame Names",
        description="Truncate object name and frame names to >24 bytes",
        default=False
    )

    
    only_selected: bpy.props.BoolProperty(
        name="Only Selected",
        default=False
    )

    preserve_positions     : bpy.props.BoolProperty(
        name            = "Preserve Positions",
        description     = "Don't set object positions to (0,0,0)",
        default         = True
    )

    preserve_rotations     : bpy.props.BoolProperty(
        name            = "Preserve Rotations",
        description     = "Don't set object rotations to (0,0,0)",
        default         = True
    )
    
    reset_positions: bpy.props.BoolProperty(
        name="Preserve Positions",
        description="Don't set object positions to (0,0,0)",
        default=False
    )

    exclude_geo_faces   : bpy.props.BoolProperty(
        name            = "Exclude Geometry Faces",
        description     = "Exclude faces from the Geometry section and force export Bin Mesh PLG",
        default         = False
    )

    export_format: bpy.props.EnumProperty(
        items=(
            ('DEFAULT', "Default", "Export with the default col format for .DFF"),
            ('SAMP', "SAMP", "Export with SAMP collision"),
        ),
        name="Collision",
        description="Choose the collision format to export with the model",
        default='DEFAULT'
    )

    export_version: bpy.props.EnumProperty(
        items=(
            ('0x33002', "GTA 3 (v3.3.0.2)", "Grand Theft Auto 3 PC (v3.3.0.2)"),
            ('0x34003', "GTA VC (v3.4.0.3)", "Grand Theft Auto VC PC (v3.4.0.3)"),
            ('0x36003', "GTA SA (v3.6.0.3)", "Grand Theft Auto SA PC (v3.6.0.3)"),
            ('custom', "Custom", "Custom RW Version")
        ),
        name="Version Export"
    )
    
    custom_version: bpy.props.StringProperty(
        maxlen=7,
        default="",
        name="Custom Version")

    export_tristrips: bpy.props.BoolProperty(
        name="Export as TriStrips",
        description="Export the model using triangle strips",
        default=False
    )
    #######################################################
    def verify_rw_version(self):
        if len(self.custom_version) != 7:
            return False

        for i, char in enumerate(self.custom_version):
            if i % 2 == 0 and not char.isdigit():
                return False
            if i % 2 == 1 and not char == '.':
                return False

        return True
    #######################################################
    def draw(self, context):
        layout = self.layout

        layout.prop(self, "mass_export")

        if self.mass_export:
            box = layout.box()
            row = box.row()
            row.label(text="Mass Export:")

            row = box.row()
            row.prop(self, "reset_positions")

        layout.prop(self, "only_selected")
        layout.prop(self, "export_coll")
        layout.prop(self, "export_frame_names")
        layout.prop(self, "truncate_frame_names")
        layout.prop(self, "export_tristrips")
        layout.prop(self, "export_format")
        layout.prop(self, "export_version")

        if self.export_version == 'custom':
            col = layout.column()
            col.alert = not self.verify_rw_version()
            icon = "ERROR" if col.alert else "NONE"
            
            col.prop(self, "custom_version", icon=icon)
    #######################################################
    def get_selected_rw_version(self):
        if self.export_version != "custom":
            return int(self.export_version, 0)
        else:
            return int(
                "0x%c%c%c0%c" % (self.custom_version[0],
                                 self.custom_version[2],
                                 self.custom_version[4],
                                 self.custom_version[6]), 0)
    #######################################################
    def execute(self, context):
        if self.export_version == "custom":
            if not self.verify_rw_version():
                self.report({"ERROR_INVALID_INPUT"}, "Invalid RW Version")
                return {'FINISHED'}

        start = time.time()
        try:
            objects_to_export = bpy.context.selected_objects if self.only_selected else bpy.context.scene.objects

            export_options = {
                "file_name": self.filepath,
                "directory": self.directory,
                "selected": self.only_selected,
                "mass_export": self.mass_export,
                "preserve_positions" : self.preserve_positions,
                "preserve_rotations" : self.preserve_rotations,
                "version": self.get_selected_rw_version(),
                "export_coll": self.export_coll,
                "export_frame_names": self.export_frame_names,
                "export_tristrips": self.export_tristrips,
                "objects": objects_to_export,
                "truncate_frame_names": self.truncate_frame_names
            }

            if self.export_format == 'DEFAULT':
                dff_exporter.export_dff(export_options)
            elif self.export_format == 'SAMP':
                samp_exporter.export_dff(export_options)

            self.report({"INFO"}, f"Finished export in {time.time() - start:.2f}s")

        except dff_exporter.DffExportException as e:
            self.report({"ERROR"}, str(e))

        context.scene['custom_imported_version'] = self.export_version
        context.scene['custom_custom_version'] = self.custom_version
            
        return {'FINISHED'}
    #######################################################
    def invoke(self, context, event):
        if 'custom_imported_version' in context.scene:
            self.export_version = context.scene['custom_imported_version']
        if 'custom_custom_version' in context.scene:
            self.custom_version = context.scene['custom_custom_version']
        
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


#######################################################
class IMPORT_OT_txd(bpy.types.Operator, ImportHelper):

    bl_idname      = "import_scene.txd"
    bl_description = 'Import a Renderware TXD File'
    bl_label       = "Import TXD (.txd)"

    filter_glob   : bpy.props.StringProperty(default="*.txd",
                                              options={'HIDDEN'})

    directory     : bpy.props.StringProperty(maxlen=1024,
                                              default="",
                                              subtype='FILE_PATH',
                                              options={'HIDDEN'})

    # Stores all the file names to read (not just the firsst)
    files : bpy.props.CollectionProperty(
        type    = bpy.types.OperatorFileListElement,
        options = {'HIDDEN'}
    )

    # Stores a single file path
    filepath : bpy.props.StringProperty(
         name        = "File Path",
         description = "Filepath used for importing the TXD file",
         maxlen      = 1024,
         default     = "",
         options     = {'HIDDEN'}
     )

    skip_mipmaps :  bpy.props.BoolProperty(
        name        = "Skip Mipmaps",
        default     = True
    )

    pack : bpy.props.BoolProperty(
        name        = "Pack Images",
        description = "Pack images as embedded data into the .blend file",
        default     = True
    )

    apply_to_objects : bpy.props.BoolProperty(
        name        = "Apply To Objects",
        description = "Apply to objects with missing textures in the scene",
        default     = True
    )

    #######################################################
    def draw(self, context):
        layout = self.layout

        layout.prop(self, "skip_mipmaps")
        layout.prop(self, "pack")
        layout.prop(self, "apply_to_objects")

    #######################################################
    def execute(self, context):

        for file in [os.path.join(self.directory, file.name) for file in self.files] if self.files else [self.filepath]:

            txd_images = txd_importer.import_txd(
                {
                    'file_name'      : file,
                    'skip_mipmaps'   : self.skip_mipmaps,
                    'pack'           : self.pack
                }
            ).images

            if self.apply_to_objects:
                for obj in context.scene.objects:
                    for mat_slot in obj.material_slots:
                        mat = mat_slot.material
                        if not mat:
                            continue

                        node_tree = mat.node_tree
                        if not node_tree:
                            continue

                        for node in node_tree.nodes:
                            if node.type != 'TEX_IMAGE':
                                continue

                            txd_img = txd_images.get(node.label)
                            if txd_img and (not node.image or not node.image.pixels):
                                node.image = txd_img[0]

        return {'FINISHED'}

    #######################################################
    def invoke(self, context, event):

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
#######################################################
class IMPORT_OT_txd_samp(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.txd_samp"
    bl_description = 'Import TXD and save overflow textures (over 1000) into a new TXD'
    bl_label = "Import TXD (SAMP)"
    filename_ext = ".txd"

    filter_glob: bpy.props.StringProperty(default="*.txd", options={'HIDDEN'})
    filepath: bpy.props.StringProperty(name="File Path", subtype='FILE_PATH')

    def execute(self, context):

        full_path = self.filepath
        base_dir = os.path.dirname(full_path)
        base_name = os.path.splitext(os.path.basename(full_path))[0]

        original_txd = txd_lib.txd()
        original_txd.load_file(full_path)

        tex_count = len(original_txd.native_textures)

        if tex_count <= 1000:
            self.report({'INFO'}, f"TXD has {tex_count} textures, no overflow.")
            return {'FINISHED'}

        # Split the TXD into main (first 1000) and overflow
        main_textures = original_txd.native_textures[:1000]
        overflow_textures = original_txd.native_textures[1000:]

        overflow_txd = txd_lib.txd()
        overflow_txd.native_textures = overflow_textures
        overflow_path = os.path.join(base_dir, f"{base_name}_2.txd")
        overflow_txd.save_file(overflow_path)

        original_txd.native_textures = main_textures
        original_txd.save_file(full_path)

        self.report({'INFO'}, f"Saved {len(main_textures)} in original, {len(overflow_textures)} to {os.path.basename(overflow_path)}")
        return {'FINISHED'}

#######################################################
class SCENE_OT_dff_frame_move(bpy.types.Operator):

    bl_idname           = "scene.dff_frame_move"
    bl_description      = "Move the active frame up/down in the list"
    bl_label            = "Move Frame"

    direction           : bpy.props.EnumProperty(
        items =
        (
            ("UP", "", ""),
            ("DOWN", "", "")
        )
    )

    #######################################################
    def execute(self, context):
        #######################################################
        def append_children_recursive(ob):
            for ch in ob.children:
                children.add(ch)
                append_children_recursive(ch)

        State.update_scene(context.scene)

        step = -1 if self.direction == "UP" else 1
        scene_dff = context.scene.dff
        old_index = scene_dff.frames_active
        frames_num = len(scene_dff.frames)

        obj1 = scene_dff.frames[old_index].obj
        active_collections = {obj1.users_collection}

        if (3, 1, 0) > bpy.app.version:
            children = set()
            append_children_recursive(obj1)
        else:
            children = {ch for ch in obj1.children_recursive}

        new_index = old_index + step
        while new_index >= 0 and new_index < frames_num:
            obj2 = scene_dff.frames[new_index].obj
            no_filter = not scene_dff.filter_collection or active_collections.issubset({obj2.users_collection})
            if step < 0:
                no_parent = obj1.parent != obj2
            else:
                no_parent = obj2 not in children

            if no_filter and no_parent:
                for idx in range(old_index, new_index, step):
                    scene_dff.frames[idx].obj.dff.frame_index += step
                obj2.dff.frame_index = old_index
                scene_dff.frames.move(new_index, old_index)
                scene_dff.frames_active = old_index + step
                return {'FINISHED'}

            new_index += step

        return {'CANCELLED'}

#######################################################
class SCENE_OT_dff_atomic_move(bpy.types.Operator):

    bl_idname           = "scene.dff_atomic_move"
    bl_description      = "Move the active atomic up/down in the list"
    bl_label            = "Move Atomic"

    direction           : bpy.props.EnumProperty(
        items =
        (
            ("UP", "", ""),
            ("DOWN", "", "")
        )
    )

    #######################################################
    def execute(self, context):
        State.update_scene(context.scene)

        step = -1 if self.direction == "UP" else 1
        scene_dff = context.scene.dff
        old_index = scene_dff.atomics_active
        atomics_num = len(scene_dff.atomics)

        obj1 = scene_dff.atomics[old_index].obj
        active_collections = {obj1.users_collection}

        new_index = old_index + step
        while new_index >= 0 and new_index < atomics_num:
            obj2 = scene_dff.atomics[new_index].obj
            no_filter = not scene_dff.filter_collection or active_collections.issubset({obj2.users_collection})

            if no_filter:
                for idx in range(old_index, new_index, step):
                    scene_dff.atomics[idx].obj.dff.atomic_index += step
                obj2.dff.atomic_index = old_index
                scene_dff.atomics.move(new_index, old_index)
                scene_dff.atomics_active = old_index + step
                return {'FINISHED'}

            new_index += step

        return {'CANCELLED'}

#######################################################
class SCENE_OT_dff_update(bpy.types.Operator):

    bl_idname           = "scene.dff_update"
    bl_description      = "Update the list of objects"
    bl_label            = "Update Scene"


    #######################################################
    def execute(self, context):
        State.update_scene(context.scene)
        return {'FINISHED'}

#######################################################
class OBJECT_OT_dff_generate_bone_props(bpy.types.Operator):

    bl_idname           = "object.dff_generate_bone_props"
    bl_description      = "Generate HAnim data for selected bones"
    bl_label            = "Generate Bone Properties"

    #######################################################
    def execute(self, context):
        selected_objects = context.selected_objects
        if not selected_objects:
            selected_objects = [context.object]

        for obj in selected_objects:
            used_bone_ids = set()
            for e_bone in obj.data.edit_bones:
                if 'bone_id' in e_bone:
                    used_bone_ids.add(e_bone['bone_id'])

            for i, e_bone in enumerate(obj.data.edit_bones):
                if not e_bone.select:
                    continue

                if 'bone_id' not in e_bone:
                    bone_id = i
                    while bone_id in used_bone_ids:
                        bone_id += 1
                    e_bone['bone_id'] = bone_id
                    used_bone_ids.add(bone_id)

                bone_type = 2
                if not e_bone.children:
                    bone_type = 1
                elif not e_bone.parent or e_bone.parent.children[-1] == e_bone:
                    bone_type = 0
                e_bone['type'] = bone_type

        return {'FINISHED'}

#######################################################
class OBJECT_OT_dff_set_parent_bone(bpy.types.Operator):

    bl_idname           = "object.dff_set_parent_bone"
    bl_description      = "Set the object's parenting"
    bl_label            = "Set Parent Bone"

    #######################################################
    def execute(self, context):
        objects = [obj for obj in context.selected_objects if obj.type in ("MESH", "EMPTY")]
        if not objects:
            return {'CANCELLED'}

        if not context.active_bone:
            return {'CANCELLED'}

        armature = context.active_object
        bone_name = context.active_bone.name

        for obj in objects:
            dff_importer.set_parent_bone(obj, armature, bone_name)

        return {'FINISHED'}

#######################################################
class OBJECT_OT_dff_clear_parent_bone(bpy.types.Operator):

    bl_idname           = "object.dff_clear_parent_bone"
    bl_description      = "Clear the object's parenting"
    bl_label            = "Clear Parent Bone"

    #######################################################
    def execute(self, context):
        objects = [obj for obj in context.selected_objects if obj.type in ("MESH", "EMPTY")]
        if not objects:
            return {'CANCELLED'}

        armature = context.active_object

        for obj in objects:
            obj.matrix_world = armature.matrix_world
            obj.parent_bone = ""

        return {'FINISHED'}
#######################################################
class EXPORT_OT_samp_custom(bpy.types.Operator, ExportHelper):  # too lazy to finish tbh
    """Operator for exporting DFF in SAMP format."""
    bl_idname = "export_dff_samp_custom.scene"
    bl_label = "Export DFF (SAMP)"
    filename_ext = ".dff"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH", default="untitled.dff")

    def execute(self, context):
        start = time.time()
        try:
            samp_exporter.export_dff({
                "file_name": self.filepath,
                "directory": os.path.dirname(self.filepath),
                "selected": True,
                "mass_export": False,
                "version": "0x36003",
                "export_coll": False,
                "export_frame_names": True,
                "export_tristrips": False,
                "truncate_frame_names": self.truncate_frame_names
            })
            self.report({"INFO"}, f"Finished export in {time.time() - start:.2f}s")
        except Exception as e:
            self.report({"ERROR"}, str(e))
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

#######################################################
class IMPORT_OT_dff_custom(bpy.types.Operator, ImportHelper):
    
    bl_idname = "import_scene.dff_custom"
    bl_description = 'Import a Renderware .DFF or .COL File'
    bl_label = "DFF/Col Import (.dff/.col)"

    filter_glob: bpy.props.StringProperty(default="*.dff;*.col",
                                          options={'HIDDEN'})
    
    directory: bpy.props.StringProperty(maxlen=1024,
                                        default="",
                                        subtype='FILE_PATH',
                                        options={'HIDDEN'})

    files: bpy.props.CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN'}
    )

    filepath: bpy.props.StringProperty(
         name="File Path",
         description="Filepath used for importing the DFF/COL file",
         maxlen=1024,
         default="",
         options={'HIDDEN'}
     )

    load_txd: bpy.props.BoolProperty(
        name="Load TXD file",
        default=True
    )

    connect_bones: bpy.props.BoolProperty(
        name="Connect Bones",
        description="Whether to connect bones (not recommended for anim editing)",
        default=True
    )

    read_mat_split: bpy.props.BoolProperty(
        name="Read Material Split",
        description="Whether to read material split for loading triangles",
        default=True
    )

    load_images: bpy.props.BoolProperty(
        name="Scan for Images",
        default=True
    )

    remove_doubles: bpy.props.BoolProperty(
        name="Use Edge Split",
        default=True
    )
    group_materials: bpy.props.BoolProperty(
        name="Group Similar Materials",
        default=True
    )

    import_normals: bpy.props.BoolProperty(
        name="Import Custom Normals",
        default=False
    )

    materials_naming :  bpy.props.EnumProperty(
        items =
        (
            ("DEF", "Default", "Use the object name and material properties"),
            ("TEX", "Texture", "Use the name of the first texture")
        ),
        name        = "Materials Naming",
        description = "How to name materials"
    )
    
    image_ext: bpy.props.EnumProperty(
        items=(
            ("PNG", ".PNG", "Load a PNG image"),
            ("JPG", ".JPG", "Load a JPG image"),
            ("JPEG", ".JPEG", "Load a JPEG image"),
            ("TGA", ".TGA", "Load a TGA image"),
            ("BMP", ".BMP", "Load a BMP image"),
            ("TIF", ".TIF", "Load a TIF image"),
            ("TIFF", ".TIFF", "Load a TIFF image")
        ),
        name="Extension",
        description="Image extension to search textures in"
    )
    #######################################################
    def draw(self, context):
        layout = self.layout

        layout.prop(self, "load_txd")
        layout.prop(self, "connect_bones")
        
        box = layout.box()
        box.prop(self, "load_images")
        if self.load_images:
            box.prop(self, "image_ext")
        
        layout.prop(self, "read_mat_split")
        layout.prop(self, "remove_doubles")
        layout.prop(self, "import_normals")
        layout.prop(self, "group_materials")
    #######################################################    
    def execute(self, context):
        start = time.time()

        for file in [os.path.join(self.directory, file.name) for file in self.files] if self.files else [self.filepath]:
            if file.endswith(".col"):
                col_importer.import_col_file(file, os.path.basename(file))
            else:
                image_ext = self.image_ext if self.load_images else None
                    
                importer = dff_importer.import_dff(
                    {
                        'file_name': file,
                        'load_txd': False,
                        'txd_filename': "",
                        'skip_mipmaps': True,
                        'txd_pack': True,
                        'image_ext': image_ext,
                        'connect_bones': self.connect_bones,
                        'use_mat_split': self.read_mat_split,
                        'remove_doubles': self.remove_doubles,
                        'group_materials': self.group_materials,
                        'import_normals': self.import_normals,
                        'materials_naming' : self.materials_naming,
                    }, 
                )

                print(f"Imported DFF {file} successfully")

                if importer.warning != "":
                    self.report({'WARNING'}, importer.warning)

                version = importer.version

                if version in ['0x33002', '0x34003', '0x36003']:
                    context.scene['custom_imported_version'] = version
                else:
                    context.scene['custom_imported_version'] = "custom"
                    context.scene['custom_custom_version'] = "{}.{}.{}.{}".format(
                        version[2] if len(version) > 2 else '0',
                        version[3] if len(version) > 3 else '0',
                        version[4] if len(version) > 4 else '0',
                        version[6] if len(version) > 6 else '0',
                    )
        
        self.report({"INFO"}, f"Finished import in {time.time() - start:.2f}s")

        return {'FINISHED'}
    #######################################################
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
#######################################################