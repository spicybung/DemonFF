import bpy
from bpy_extras.io_utils import ExportHelper
from ..ops import col_exporter

#######################################################
class EXPORT_OT_col(bpy.types.Operator, ExportHelper):
    
    bl_idname      = "export_col.scene"
    bl_description = "Export a GTA III/VC/SA Collision File"
    bl_label       = "DemonFF Collision (.col)"
    filename_ext   = ".col"

    filepath       : bpy.props.StringProperty(name="File path",
                                              maxlen=1024,
                                              default="",
                                              subtype='FILE_PATH')
    
    filter_glob    : bpy.props.StringProperty(default="*.col",
                                              options={'HIDDEN'})
    
    directory      : bpy.props.StringProperty(maxlen=1024,
                                              default="",
                                              subtype='FILE_PATH')

    only_selected   :  bpy.props.BoolProperty(
        name        = "Only Selected",
        default     = False
    )
    
    export_version  : bpy.props.EnumProperty(
        items =
        (
            ('3', "GTA SAMP PC/Android (COL3)", "Grand Theft Auto SAMP (PC/Android) - Version 5"),

        ),
        name = "Version Export"
    )

    #######################################################
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "export_version")
        layout.prop(self, "only_selected")
        return None

    #######################################################
    def execute(self, context):
        
        col_exporter.export_col(
            {
                "file_name"      : self.filepath,
                "version"        : int(self.export_version),
                "collection"     : None,
                "memory"         : False,
                "mass_export"    : True,
                "only_selected"  : self.only_selected
            }
        )

        # Save settings of the export in scene custom properties for later
        context.scene['demonff_imported_version_col'] = self.export_version
            
        return {'FINISHED'}

    #######################################################
    def invoke(self, context, event):
        if 'demonff_imported_version_col' in context.scene:
            self.export_version = context.scene['demonff_imported_version_col']
        
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
