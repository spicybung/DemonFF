
import bpy

from bpy_extras.io_utils import ExportHelper


#######################################################
class EXPORT_OT_demonff_ide(bpy.types.Operator, ExportHelper):
    bl_idname = "scene.demonff_export_ide"
    bl_label = "Export IDE (Text)"
    bl_description = "Export OBJ definitions to a text .ide file (objs section)"
    filename_ext = ".ide"

    filter_glob: bpy.props.StringProperty(default="*.ide", options={'HIDDEN'})

    only_selected: bpy.props.BoolProperty(
        name="Only Selected",
        default=False
    )

    use_unique_ids: bpy.props.BoolProperty(
        name="Unique IDs Only",
        description="Export only one entry per IDE_ID (avoids duplicates)",
        default=True
    )

    #######################################################
    def execute(self, context):

        objs = []
        for obj in context.scene.objects:
            if self.only_selected and not obj.select_get():
                continue
            if not hasattr(obj, "dff"):
                continue
            if obj.dff.type != 'OBJ':
                continue

            ide_id = int(obj.get("IDE_ID", 0) or 0)
            txd_name = str(obj.get("TXD_Name", "") or "").strip()
            if ide_id <= 0 or txd_name == "":
                continue

            objs.append(obj)

        if self.use_unique_ids:
            unique = {}
            for obj in objs:
                unique[int(obj.get("IDE_ID", 0) or 0)] = obj
            objs = list(unique.values())

        # Write IDE
        with open(self.filepath, "w", encoding="utf-8") as f:
            f.write("objs\n")
            for obj in objs:
                ide_id = int(obj.get("IDE_ID", 0) or 0)
                base_name = obj.name.split(".")[0]
                txd_name = str(obj.get("TXD_Name", "") or "").strip()

                # RenderWare IDE line format: id, model, txd, objtype, drawdist, flags
                # DemonFF historically uses flags=1 and geometry alpha=0. We'll keep flags=1 for compatibility.
                drawdist = float(obj.get("DrawDistance", 300.0) or 300.0)
                flags = int(obj.get("IDE_Flags", 0) or 0)

                f.write(f"{ide_id}, {base_name}, {txd_name}, 1, {drawdist:.6f}, {flags}\n")

            f.write("end\n")

        self.report({'INFO'}, f"Exported {len(objs)} IDE entries")
        return {'FINISHED'}
