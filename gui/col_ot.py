import bpy
from bpy_extras.io_utils import ExportHelper
from ..ops import col_samp_exporter

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

    #######################################################
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "export_version")
        layout.prop(self, "only_selected")
        layout.prop(self, "mass_export")
        layout.prop(self, "directory")
        return None

    #######################################################
    def execute(self, context):
        options = {
            "file_name": self.filepath,
            "version": int(self.export_version),
            "collection": None,
            "memory": False,
            "mass_export": self.mass_export,
            "only_selected": self.only_selected
        }

        if self.mass_export:
            options["directory"] = self.directory

        col_samp_exporter.export_col_samp(options)

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
    bpy.utils.register_class(EXPORT_OT_col)

def unregister():
    bpy.utils.unregister_class(EXPORT_OT_col)

if __name__ == "__main__":
    register()
