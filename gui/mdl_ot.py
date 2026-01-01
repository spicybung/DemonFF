# DemonFF - MDL Import/Export Operators
# 2023 - 2025 SpicyBung

import os
import bpy
import time

from bpy_extras.io_utils import ImportHelper, ExportHelper
from ..ops import dff_importer, mdl_stories_importer

#######################################################
class IMPORT_OT_mdl_custom(bpy.types.Operator, ImportHelper):

    bl_idname = "import_scene.mdl_custom"
    bl_description = "Import a Leeds MDL file"
    bl_label = "DemonFF MDL Import (.mdl)"
    filename_ext = ".mdl"

    filter_glob: bpy.props.StringProperty(default="*.mdl", options={'HIDDEN'})
    directory: bpy.props.StringProperty(maxlen=1024, default="", subtype='FILE_PATH', options={'HIDDEN'})

    files: bpy.props.CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN'}
    )
    filepath: bpy.props.StringProperty(
        name="File Path",
        description="Filepath used for importing the MDL file",
        maxlen=1024,
        default="",
        options={'HIDDEN'}
    )

    mdl_type: bpy.props.EnumProperty(
        name="MDL Type",
        description="Choose type for import (affects internal file pointer logic)",
        items=[
            ('PED', "Ped", "Import as Pedestrian Model"),
            ('BUILDING', "Building", "Import as Building/Prop Model"),
        ],
        default='PED'
    )

    #######################################################
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "mdl_type")

    #######################################################
    def execute(self, context):
        start = time.time()
        for file in [os.path.join(self.directory, file.name) for file in self.files] if self.files else [self.filepath]:
            # Call the MDL Stories importer operator logic, but with our DemonFF branding
            try:
                # Use the underlying operator as a callable function
                result = mdl_stories_importer.ImportMDLOperator.read_mdl(self, file)
            except Exception as e:
                import traceback
                traceback.print_exc()
                return {'CANCELLED'}
        return {'FINISHED'}
    

    #######################################################
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
def register():
    bpy.utils.register_class(IMPORT_OT_mdl_custom)
def unregister():
    bpy.utils.unregister_class(IMPORT_OT_mdl_custom)
if __name__ == "__main__":
    register()

