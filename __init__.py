# DemonFF - Blender scripts for working with Renderware & R*/SA-MP/open.mp formats in Blender
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
from .gui import gui, pie_menus
from .ops import map_importer, map_exporter, img_importer

from bpy.utils import register_class, unregister_class

bl_info = {
    "name": "GTA DemonFF",
    "author": "SpicyBung",
    "version": (0, 0, 5),
    "blender": (2, 80, 0),      # Tested and working on 3.x & 4.x
    "category": "Import-Export",
    "location": "File > Import/Export",
    "description": "Importer and Exporter for GTA Formats"
}

# Class list to register
_classes = [
    gui.IMPORT_OT_dff_custom,
    gui.EXPORT_OT_dff_custom,
    gui.IMPORT_OT_mdl_custom,
    gui.IMPORT_OT_txd,
    gui.IMPORT_OT_txd_samp,
    gui.EXPORT_OT_col,
    gui.DFFFrameProps,
    gui.DFFAtomicProps,
    gui.DFF_UL_FrameItems,
    gui.DFF_UL_AtomicItems,
    gui.SCENE_PT_dffFrames,
    gui.SCENE_PT_dffAtomics,
    gui.SCENE_OT_dff_frame_move,
    gui.SCENE_OT_dff_atomic_move,
    gui.OBJECT_OT_set_collision_objects,
    gui.MATERIAL_PT_dffMaterials,
    gui.OBJECT_OT_dff_generate_bone_props,
    gui.OBJECT_OT_dff_set_parent_bone,
    gui.OBJECT_OT_dff_clear_parent_bone,
    gui.OBJECT_PT_dffObjects,
    gui.OBJECT_OT_join_similar_named_meshes,
    gui.SCENE_OT_duplicate_all_as_objects,
    gui.OBJECT_PT_dff_misc_panel,
    gui.OBJECT_OT_force_doubleside_mesh,
    gui.OBJECT_OT_recalculate_normals_outward,
    gui.OBJECT_OT_recalculate_normals_inward,
    gui.OBJECT_OT_optimize_mesh,
    gui.COLLECTION_OT_nuke_matched,
    gui.COLLECTION_OT_organize_scene_collection,
    gui.COLLECTION_OT_remove_empty_collections,
    gui.COLLECTION_PT_custom_cleanup_panel,
    gui.OBJECT_OT_remove_frames,
    gui.OBJECT_OT_truncate_material_names,
    gui.OBJECT_OT_truncate_frame_names,
    gui.EXT2DFXObjectProps,
    gui.Light2DFXObjectProps,
    gui.DFFMaterialProps,
    gui.DFFObjectProps,
    img_importer.IMPORT_PT_img_panel,
    img_importer.IMPORT_OT_img,
    gui.TXDImportPanel,
    gui.IDEPathItem,
    gui.DEMONFF_UL_ide_paths,
    gui.DFFSceneProps,
    gui.MapImportPanel,
    gui.AddIDEPathOperator,
    gui.RemoveIDEPathOperator,
    gui.DFF_MT_ImportChoice,
    gui.DFF_MT_ExportChoice,
    gui.DFF_MT_EditArmature,
    gui.DFF_MT_Pose,
    gui.SCENE_OT_dff_update,
    gui.SCENE_OT_select_ipl_and_import,
    gui.SCENE_OT_ipl_select,
    gui.SCENE_OT_duplicate_all_as_collision,
    map_importer.Map_Import_Operator,
    map_importer.Binary_Map_Import_Operator,
    map_exporter.SAMP_IDE_Import_Operator,
    map_exporter.Mass_IDE_Import_Operator,
    map_exporter.RemoveBuildingForPlayerOperator,
    map_exporter.ExportToIPLOperator,
    map_exporter.ExportToIDEOperator,
    map_exporter.ExportToPawnOperator,
    map_exporter.DemonFFMapExportPanel,
    map_exporter.DemonFFPawnPanel,
    gui.DEMONFF_PT_DFF2DFX,
    gui.SAEFFECTS_OT_AddLightInfo,
    gui.SAEFFECTS_OT_AddParticleInfo,
    gui.SAEFFECTS_OT_AddTextInfo,
    gui.SAEFFECTS_OT_ExportInfo,
    gui.SAEFFECTS_OT_ExportTextInfo,
    gui.SAEFFECTS_OT_CreateLightsFromOmni,
    gui.SAEFFECTS_OT_ViewLightInfo,
    gui.SAEEFFECTS_OT_CreateLightsFromEntries,
    gui.OBJECT_PT_SDFXLightInfoPanel,
    gui.SAEEFFECTS_PT_Panel,
    gui.IMPORT_OT_ifp,
    gui.EXPORT_OT_ifp,
    gui.MESSAGE_OT_missing_bones,
    gui.DFF_MT_ToolWheel
]


# Register and unregister functions
def register():
    for cls in _classes:
        register_class(cls)

    bpy.types.Scene.dff = bpy.props.PointerProperty(type=gui.DFFSceneProps)

    bpy.types.Scene.saeffects_export_path = bpy.props.StringProperty(
        name="Binary",
        description="Path to export the effects binary file",
        subtype='FILE_PATH'
    )
    bpy.types.Scene.saeffects_text_export_path = bpy.props.StringProperty(
        name="Text",
        description="Path to export the effects text file",
        subtype='FILE_PATH'
    )



    if (2, 80, 0) > bpy.app.version:
        bpy.types.INFO_MT_file_import.append(gui.import_dff_func)
        bpy.types.INFO_MT_file_export.append(gui.export_dff_func)
    else:
        bpy.types.TOPBAR_MT_file_import.append(gui.import_dff_func)
        bpy.types.TOPBAR_MT_file_export.append(gui.export_dff_func)
        
    pie_menus.register_keymaps()


def unregister():
    if (2, 80, 0) > bpy.app.version:
        bpy.types.INFO_MT_file_import.remove(gui.import_dff_func)
        bpy.types.INFO_MT_file_export.remove(gui.export_dff_func)
    else:
        bpy.types.TOPBAR_MT_file_import.remove(gui.import_dff_func)
        bpy.types.TOPBAR_MT_file_export.remove(gui.export_dff_func)

    for cls in reversed(_classes):
        unregister_class(cls)

    pie_menus.unregister_keymaps()

    del bpy.types.Scene.saeffects_export_path
    del bpy.types.Scene.saeffects_text_export_path

if __name__ == "__main__":
    register()