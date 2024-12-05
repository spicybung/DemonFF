import os
import bpy
import time
from bpy_extras.io_utils import ImportHelper, ExportHelper
from ..ops import dff_exporter, dff_importer, col_importer, samp_exporter

class EXPORT_OT_dff_custom(bpy.types.Operator, ExportHelper):
    
    bl_idname = "export_dff_custom.scene"
    bl_description = "Export a Custom Renderware DFF or COL File"
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
    
    only_selected: bpy.props.BoolProperty(
        name="Only Selected",
        default=False
    )
    
    reset_positions: bpy.props.BoolProperty(
        name="Preserve Positions",
        description="Don't set object positions to (0,0,0)",
        default=False
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

    def verify_rw_version(self):
        if len(self.custom_version) != 7:
            return False

        for i, char in enumerate(self.custom_version):
            if i % 2 == 0 and not char.isdigit():
                return False
            if i % 2 == 1 and not char == '.':
                return False

        return True
    
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
        layout.prop(self, "export_format")
        layout.prop(self, "export_version")

        if self.export_version == 'custom':
            col = layout.column()
            col.alert = not self.verify_rw_version()
            icon = "ERROR" if col.alert else "NONE"
            
            col.prop(self, "custom_version", icon=icon)
        
        layout.prop(self, "export_tristrips")

    def get_selected_rw_version(self):
        if self.export_version != "custom":
            return int(self.export_version, 0)
        else:
            return int(
                "0x%c%c%c0%c" % (self.custom_version[0],
                                 self.custom_version[2],
                                 self.custom_version[4],
                                 self.custom_version[6]), 0)

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
                "version": self.get_selected_rw_version(),
                "export_coll": self.export_coll,
                "export_frame_names": self.export_frame_names,
                "export_tristrips": self.export_tristrips,
                "objects": objects_to_export
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

    def invoke(self, context, event):
        if 'custom_imported_version' in context.scene:
            self.export_version = context.scene['custom_imported_version']
        if 'custom_custom_version' in context.scene:
            self.custom_version = context.scene['custom_custom_version']
        
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class EXPORT_OT_samp_custom(bpy.types.Operator, ExportHelper):
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
                "export_tristrips": False
            })
            self.report({"INFO"}, f"Finished export in {time.time() - start:.2f}s")
        except Exception as e:
            self.report({"ERROR"}, str(e))
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class IMPORT_OT_dff_custom(bpy.types.Operator, ImportHelper):
    
    bl_idname = "import_scene.dff_custom"
    bl_description = 'Import a Custom Renderware DFF or COL File'
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
                        'image_ext': image_ext,
                        'connect_bones': self.connect_bones,
                        'use_mat_split': self.read_mat_split,
                        'remove_doubles': self.remove_doubles,
                        'group_materials': self.group_materials,
                        'import_normals': self.import_normals
                    }, 
                    context
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

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


def register():
    bpy.utils.register_class(EXPORT_OT_dff_custom)
    bpy.utils.register_class(EXPORT_OT_samp_custom)
    bpy.utils.register_class(IMPORT_OT_dff_custom)

def unregister():
    bpy.utils.unregister_class(EXPORT_OT_dff_custom)
    bpy.utils.unregister_class(EXPORT_OT_samp_custom)
    bpy.utils.unregister_class(IMPORT_OT_dff_custom)

if __name__ == "__main__":
    register()
