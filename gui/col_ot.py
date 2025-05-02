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
from bpy_extras.io_utils import ExportHelper
from ..ops import col_exporter, col_samp_exporter

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

    

    #######################################################
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "exporter_type")
        layout.prop(self, "export_version")
        layout.prop(self, "only_selected")
        layout.prop(self, "mass_export")
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
    bpy.utils.register_class(EXPORT_OT_col)

def unregister():
    bpy.utils.unregister_class(EXPORT_OT_col)

if __name__ == "__main__":
    register()
