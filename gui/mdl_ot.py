# DemonFF - Blender scripts for working with Renderware & R*/SA-MP/open.mp formats in Blender
# 2023 - 2026 spicybung

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

import bpy
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy.props import (
    IntProperty,
    StringProperty,
    BoolProperty,
    EnumProperty,
)

from ..ops import mdl_importer
from ..gtaLib import mdl as mdl_core
from ..ops import tex_importer


def resolve_export_defaults_from_root(context: bpy.types.Context) -> tuple[str, bool]:
    from ..ops import mdl_exporter

    try:
        root = mdl_exporter.find_mdl_root(context)
    except Exception:
        return ("SIM", False)

    mdl_type = "SIM"
    use_normals = False

    try:
        if hasattr(root, "bleeds_mdl_type"):
            mdl_type = str(root.bleeds_mdl_type or "SIM")
        elif "bleeds_mdl_type" in root:
            mdl_type = str(root.get("bleeds_mdl_type", "SIM"))
    except Exception:
        mdl_type = "SIM"

    mdl_type_u = mdl_type.upper().strip()
    if mdl_type_u in ("PED", "CUT"):
        mdl_type = "PED"
        use_normals = True

    try:
        if hasattr(root, "bleeds_export_use_normals"):
            use_normals = bool(use_normals or root.bleeds_export_use_normals)
        elif "bleeds_export_use_normals" in root:
            use_normals = bool(use_normals or root.get("bleeds_export_use_normals", False))
    except Exception:
        pass

    return (mdl_type if mdl_type in {"SIM", "PED"} else "SIM", bool(use_normals))


class IMPORT_OT_mdl_custom(Operator, ImportHelper):
    bl_idname = "import_scene.mdl_custom"
    bl_label = "DemonFF MDL Import (.mdl)"
    bl_description = "Import a Rockstar Leeds MDL file"
    bl_options = {"PRESET", "UNDO"}

    filename_ext = ".mdl"
    filter_glob: StringProperty(
        default="*.mdl",
        options={"HIDDEN"},
        maxlen=255,
    )

    import_game: EnumProperty(
        name="Type",
        description="Leeds game family to import",
        items=(
            ("LCS", "LCS", "Grand Theft Auto: Liberty City Stories"),
            ("VCS", "VCS", "Grand Theft Auto: Vice City Stories"),
            ("MH2", "MH2", "Manhunt 2"),
        ),
        default="VCS",
    )

    platform: EnumProperty(
        name="Platform",
        description="Platform this Stories MDL was built for",
        items=(
            ("PS2", "PS2", "PlayStation 2 (Liberty City Stories / Vice City Stories)"),
            ("PSP", "PSP", "PlayStation Portable (Liberty City Stories / Vice City Stories)"),
        ),
        default="PS2",
    )

    mdl_type: EnumProperty(
        name="Model Type",
        description="Whether this MDL is a ped/actor or a prop",
        items=(
            ("SIM", "SimpleModel", "Simple / prop model without bones"),
            ("PED", "PedModel / Actor", "Pedestrian / actor model with bones"),
            ("CUT", "CutsceneModel / Actor", "Cutscene / actor model with bones"),
            ("VEH", "VehicleModel", "Vehicle model"),
        ),
        default="SIM",
    )

    import_texture: BoolProperty(
        name="Import Texture",
        description="Attempt to import a same-name Leeds texture dictionary (.xtx/.chk/.tex) beside the MDL and apply it to matching MDL materials",
        default=False,
    )

    create_armature: BoolProperty(
        name="Internal Armature Import",
        description="Internal: imports frame data as an armature when appropriate",
        default=True,
        options={"HIDDEN"},
    )

    link_to_scene: BoolProperty(
        name="Internal Collection Link",
        description="Internal: links the imported collection to the active scene",
        default=True,
        options={"HIDDEN"},
    )

    collection_name: StringProperty(
        name="Internal Collection",
        description="Internal: optional collection override",
        default="",
        maxlen=1024,
        options={"HIDDEN"},
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(align=True)
        col.prop(self, "import_game")

        if self.import_game != "MH2":
            col.prop(self, "platform")
            col.prop(self, "mdl_type")

        col.prop(self, "import_texture")

    def execute(self, context):
        filepath = self.filepath
        collection_name = self.collection_name

        try:
            if self.import_game == "MH2":
                mdl_core.import_mh2(
                    path=filepath,
                    context=context,
                    collection_name=(collection_name or None),
                )
                self.report({"INFO"}, f"Imported MH2 MDL: {filepath}")
                return {"FINISHED"}

            created_objects = mdl_importer.import_stories_mdl(
                context=context,
                filepath=filepath,
                platform=self.platform,
                mdl_type=self.mdl_type,
                collection_name=collection_name,
                create_armature=self.create_armature,
                link_to_scene=self.link_to_scene,
            )

            if self.import_texture:
                texture_platform = "ps2" if self.platform == "PS2" else "psp"
                texture_path, texture_images, texture_matched, texture_missing = tex_importer.import_sidecar_texture_for_mdl(
                    mdl_path=filepath,
                    imported_objects=created_objects,
                    platform=texture_platform,
                )
                if texture_path is None:
                    self.report({"WARNING"}, "Import Texture enabled, but no same-name .xtx/.chk/.tex was found beside the MDL.")
                elif not texture_images:
                    self.report({"WARNING"}, f"Import Texture enabled, but no textures decoded from: {texture_path}")
                else:
                    self.report({"INFO"}, f"Imported Leeds textures: {len(texture_images)} images, {texture_matched} materials matched.")

            if created_objects:
                for obj in created_objects:
                    obj.select_set(True)
                if created_objects[0] is not None:
                    context.view_layer.objects.active = created_objects[0]

            self.report({"INFO"}, f"Imported Stories MDL: {filepath}")
            return {"FINISHED"}

        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.report({"ERROR"}, f"Failed to import MDL: {exc}")
            return {"CANCELLED"}


class EXPORT_SCENE_OT_stories_mdl_ps2(bpy.types.Operator, ExportHelper):
    bl_idname = "export_scene.demonff_stories_mdl"
    bl_label = "Export R* Leeds Stories MDL"
    bl_options = {"UNDO"}

    filename_ext = ".mdl"
    filter_glob: StringProperty(
        default="*.mdl",
        options={"HIDDEN"},
        maxlen=255,
    )

    export_game: EnumProperty(
        name="3D Models",
        description="Target Leeds 3D model family",
        items=(
            ("LCS", "LCS", "Grand Theft Auto: Liberty City Stories"),
            ("VCS", "VCS", "Grand Theft Auto: Vice City Stories"),
            ("MH2", "MH2", "Manhunt 2"),
        ),
        default="VCS",
    )

    mdl_type: EnumProperty(
        name="Type",
        description="Export type (PROP uses Atomic root; PED uses Clump+Atomic)",
        items=(
            ("SIM", "SIM", "Prop / SimpleModel"),
            ("PED", "PED", "Ped / Clump"),
        ),
        default="SIM",
    )

    max_batch_verts: IntProperty(
        name="Max Batch Verts",
        description="Maximum vertices per VIF segment. When set to 0, the exporter automatically chooses an appropriate size based on the mesh.",
        default=0,
        min=0,
        max=255,
        options={"HIDDEN"},
    )

    rounding_mode: EnumProperty(
        name="Internal Quantize",
        description="Internal fixed quantization mode for Stories PS2 position encoding.",
        items=(("ROUND", "Round", "round()"),),
        default="ROUND",
        options={"HIDDEN"},
    )

    use_normals: BoolProperty(
        name="Export Normals",
        description="Include the normals stream in the PS2 DMA payload if exists",
        default=False,
    )

    imported_export_mode: EnumProperty(
        name="Internal PED Rebuild",
        description="Internal: imported PEDs are rebuilt from calculated live data",
        items=(("REBUILD", "Rebuild", "Rebuild from calculated pointers, live geometry, and ped_atomic_bind basis"),),
        default="REBUILD",
        options={"HIDDEN"},
    )

    def invoke(self, context, event):
        from ..ops import mdl_exporter

        root_mdl_type, root_use_normals = resolve_export_defaults_from_root(context)
        if root_mdl_type == "PED":
            self.mdl_type = "PED"
        self.use_normals = bool(root_use_normals)

        try:
            root = mdl_exporter.find_mdl_root(context)
        except Exception:
            root = None

        try:
            if root is not None:
                if hasattr(root, "bleeds_model_game"):
                    self.export_game = str(root.bleeds_model_game or self.export_game)
                elif "bleeds_model_game" in root:
                    self.export_game = str(root.get("bleeds_model_game", self.export_game))
        except Exception:
            pass

        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        from ..ops import mdl_exporter

        root_mdl_type, root_use_normals = resolve_export_defaults_from_root(context)
        mdl_type = self.mdl_type
        use_normals = self.use_normals

        if root_mdl_type == "PED" and mdl_type == "SIM":
            mdl_type = "PED"
        if mdl_type == "PED":
            use_normals = True
        else:
            use_normals = bool(use_normals or root_use_normals)

        try:
            mdl_exporter.export_stories_mdl_ps2(
                context=context,
                filepath=self.filepath,
                mdl_type=mdl_type,
                max_batch_verts=self.max_batch_verts,
                rounding_mode=self.rounding_mode,
                use_normals=use_normals,
                imported_export_mode="REBUILD",
                export_game=self.export_game,
            )
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.report({"ERROR"}, f"Export Stories MDL failed: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Exported Stories MDL: {self.filepath}")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(IMPORT_OT_mdl_custom)
    bpy.utils.register_class(EXPORT_SCENE_OT_stories_mdl_ps2)


def unregister():
    bpy.utils.unregister_class(EXPORT_SCENE_OT_stories_mdl_ps2)
    bpy.utils.unregister_class(IMPORT_OT_mdl_custom)


if __name__ == "__main__":
    register()
