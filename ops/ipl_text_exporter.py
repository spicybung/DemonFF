
import bpy

from bpy_extras.io_utils import ExportHelper


#######################################################
def quat_to_degrees(quat):
    euler = quat.to_euler('XYZ')
    return (
        euler.x * (180.0 / 3.141592653589793),
        abs(euler.y * (180.0 / 3.141592653589793)),
        euler.z * (180.0 / 3.141592653589793),
    )


#######################################################
class EXPORT_OT_demonff_ipl(bpy.types.Operator, ExportHelper):
    bl_idname = "scene.demonff_export_ipl"
    bl_label = "Export IPL (Text)"
    bl_description = "Export object instances to a text .ipl file (inst section)"
    filename_ext = ".ipl"

    filter_glob: bpy.props.StringProperty(default="*.ipl", options={'HIDDEN'})

    only_selected: bpy.props.BoolProperty(
        name="Only Selected",
        default=False
    )

    skip_lod: bpy.props.BoolProperty(
        name="Skip LOD",
        description="Skip objects named like LOD* or *.ColMesh",
        default=False
    )

    #######################################################
    def execute(self, context):

        inst = []
        for obj in context.scene.objects:
            if self.only_selected and not obj.select_get():
                continue
            if not hasattr(obj, "dff"):
                continue
            if obj.dff.type != 'OBJ':
                continue
            if self.skip_lod and (obj.name.startswith("LOD") or ".ColMesh" in obj.name):
                continue

            ide_id = int(obj.get("IDE_ID", 0) or 0)
            if ide_id <= 0:
                continue

            inst.append(obj)

        with open(self.filepath, "w", encoding="utf-8") as f:
            f.write("inst\n")

            for obj in inst:
                parent = obj.parent
                if parent and parent.type == 'EMPTY':
                    position = parent.location
                    rotation = quat_to_degrees(parent.rotation_quaternion)
                else:
                    position = obj.location
                    rotation = quat_to_degrees(obj.rotation_quaternion)

                ide_id = int(obj.get("IDE_ID", 0) or 0)
                interior = int(obj.get("Interior", 0) or 0)
                lod_index = int(obj.get("LODIndex", -1) or -1)

                base_name = obj.name.split(".")[0]

                f.write(
                    f"{ide_id}, {base_name}, {interior}, "
                    f"{position.x:.6f}, {position.y:.6f}, {position.z:.6f}, "
                    f"{rotation[0]:.6f}, {rotation[1]:.6f}, {rotation[2]:.6f}, {lod_index}\n"
                )

            f.write("end\n")

        self.report({'INFO'}, f"Exported {len(inst)} IPL entries")
        return {'FINISHED'}
