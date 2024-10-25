import bpy
import os
from ..data import map_data
from ..ops.importer_common import game_version
from bpy.props import StringProperty, FloatProperty, BoolProperty

class DFFSceneProps(bpy.types.PropertyGroup):

    def update_map_sections(self, context):
        return map_data.data[self.game_version_dropdown]['IPL_paths']
        
    game_version_dropdown: bpy.props.EnumProperty(
        name='Game',
        items=(
            (game_version.III, 'GTA III', 'GTA III map segments'),
            (game_version.VC, 'GTA VC', 'GTA VC map segments'),
            (game_version.SA, 'GTA SA', 'GTA SA map segments'),
            (game_version.LCS, 'GTA LCS', 'GTA LCS map segments(uses PC Edition)'),
            (game_version.VCS, 'GTA VCS', 'GTA VCS map segments(uses PC Edition)'),
            (game_version.IV, 'GTA IV', 'GTA IV map segments(uses VxIV2SA)'),
        )
    )
    map_sections: bpy.props.EnumProperty(
        name='Map segment',
        items=update_map_sections
    )

    skip_lod: bpy.props.BoolProperty(
        name="Skip LOD Objects",
        default=False
    )

    game_root: bpy.props.StringProperty(
        name='Game root',
        default='C:\\Program Files (x86)\\Steam\\steamapps\\common\\',
        description="Folder with the game's executable",
        subtype='DIR_PATH'
    )

    dff_folder: bpy.props.StringProperty(
        name='Dff folder',
        default='C:\\Users\\blaha\\Documents\\GitHub\\DragonFF\\tests\\dff',
        description="Define a folder where all of the dff models are stored.",
        subtype='DIR_PATH'
    )

    stream_distance: bpy.props.FloatProperty(
        name="Stream Distance",
        default=300.0,
        description="Stream distance for dynamic objects"
    )

    draw_distance: bpy.props.FloatProperty(
        name="Draw Distance",
        default=300.0,
        description="Draw distance for objects"
    )

    x_offset: bpy.props.FloatProperty(
        name="X Offset",
        default=0.0,
        description="Offset for the x coordinate of the objects"
    )

    y_offset: bpy.props.FloatProperty(
        name="Y Offset",
        default=0.0,
        description="Offset for the y coordinate of the objects"
    )

    @classmethod
    def register(cls):
        bpy.types.Scene.dff = bpy.props.PointerProperty(type=cls)

    @classmethod
    def unregister(cls):
        del bpy.types.Scene.dff

class MapImportPanel(bpy.types.Panel):
    """Creates a Panel in the scene context of the properties editor"""
    bl_label = "DemonFF - Map Import"
    bl_idname = "SCENE_PT_layout"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.dff

        flow = layout.grid_flow(row_major=True,
                                columns=0,
                                even_columns=True,
                                even_rows=False,
                                align=True)

        col = flow.column()
        col.prop(settings, "game_version_dropdown", text="Game")
        col.prop(settings, "map_sections", text="Map segment")
        col.separator()
        col.prop(settings, "skip_lod", text="Skip LOD objects")

        layout.separator()

        layout.prop(settings, 'game_root')
        layout.prop(settings, 'dff_folder')

        row = layout.row()
        row.operator("scene.demonff_map_import")

def register():
    bpy.utils.register_class(DFFSceneProps)
    bpy.utils.register_class(MapImportPanel)
    DFFSceneProps.register()

def unregister():
    bpy.utils.unregister_class(DFFSceneProps)
    bpy.utils.unregister_class(MapImportPanel)
    DFFSceneProps.unregister()

if __name__ == "__main__":
    register()
