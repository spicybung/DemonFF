# DemonFF - GTA Stories .anim import operator

import json
import math
from pathlib import Path
from typing import List

import bpy
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

from ..ops import anim_importer
from ..gtaLib import anim as anim_format
from ..data.bone_data import DIRECT_ID_PROPERTY_NAMES, PED_ANIM_HASH16_TO_DIRECT_ID, directIdFromBoneName


class IMPORT_OT_anim(Operator, ImportHelper):
    bl_idname = "import_scene.demonff_anim"
    bl_label = "Import DemonFF ANIM"
    bl_description = "Import GTA Liberty City Stories / Vice City Stories .anim animation data"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".anim"
    filter_glob: StringProperty(
        default="*.anim",
        options={"HIDDEN"},
        maxlen=255,
    )

    animation_index: IntProperty(
        name="Animation Index",
        description="Zero-based animation index inside the ANIM container",
        default=0,
        min=0,
    )

    apply_to_selected_armature: BoolProperty(
        name="Apply to Selected Armature",
        description="Create an Action on the selected/imported GTA Stories armature",
        default=True,
    )

    create_text_summary: BoolProperty(
        name="Create Text Summary",
        description="Create a Blender Text datablock with parsed animation and mapping information",
        default=True,
    )

    apply_rotation: BoolProperty(
        name="Apply Rotation",
        description="Key quaternion rotation channels from the ANIM file",
        default=True,
    )

    apply_translation: BoolProperty(
        name="Apply Translation",
        description="Key translation channels; normally leave off for weapon/body PED clips",
        default=False,
    )

    apply_root_motion: BoolProperty(
        name="Apply Root Translation",
        description="Apply ANIM bone-id 0 translation in addition to root rotation",
        default=False,
    )

    pose_space_mode: EnumProperty(
        name="Pose Space",
        description="How decoded Stories ANIM local transforms are converted into Blender pose channels",
        items=(
            (
                "MDL_REST_DELTA",
                "Blender-Space Rest Delta",
                "Default for DemonFF/BLeeds Stories ped rigs; solve decoded ANIM transforms against the imported MDL rest pose",
            ),
            (
                "PLR_REST_ROTATION_DELTA",
                "Raw ANIM Quaternion Delta",
                "Debug mode using decoded ANIM rotations as raw rest-relative deltas",
            ),
            (
                "MDL_ABSOLUTE_POSE",
                "MDL Absolute Pose",
                "Solve the complete pose recursively through the imported MDL hierarchy",
            ),
            (
                "RAW_BASIS",
                "Raw Blender Basis",
                "Write decoded ANIM quaternions directly to Blender pose-bone basis channels",
            ),
        ),
        default="MDL_REST_DELTA",
    )

    translation_scale: FloatProperty(
        name="Translation Scale",
        description="Multiplier for decoded half-float translation values",
        default=1.0,
        precision=6,
    )

    fps: FloatProperty(
        name="FPS",
        description="Seconds-to-Blender-frames multiplier",
        default=30.0,
        min=1.0,
        max=240.0,
    )

    start_frame: FloatProperty(
        name="Start Frame",
        description="Blender frame used for ANIM time zero",
        default=1.0,
    )

    use_name_fallback: BoolProperty(
        name="Use Name Fallback",
        description="Use GTA-style bone names when imported numeric ID properties are unavailable",
        default=True,
    )

    use_table_index_fallback: BoolProperty(
        name="Use Table Index Fallback",
        description="Use bone-table order only when the destination armature order matches the ANIM table",
        default=False,
    )

    clear_existing_action: BoolProperty(
        name="Create New Action",
        description="Create a new Action instead of writing into the active Action",
        default=True,
    )

    print_log: BoolProperty(
        name="Print Log",
        description="Print ANIM parser and mapping diagnostics to Blender's System Console",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        column = layout.column(align=True)
        column.prop(self, "animation_index")
        column.prop(self, "apply_to_selected_armature")
        column.prop(self, "create_text_summary")

        box = layout.box()
        box.label(text="Channels")
        column = box.column(align=True)
        column.prop(self, "apply_rotation")
        column.prop(self, "apply_translation")
        column.prop(self, "pose_space_mode")
        column.prop(self, "apply_root_motion")
        column.prop(self, "translation_scale")

        box = layout.box()
        box.label(text="Timing")
        column = box.column(align=True)
        column.prop(self, "fps")
        column.prop(self, "start_frame")

        box = layout.box()
        box.label(text="Mapping")
        column = box.column(align=True)
        column.prop(self, "use_name_fallback")
        column.prop(self, "use_table_index_fallback")
        column.prop(self, "clear_existing_action")
        column.prop(self, "print_log")

    def execute(self, context):
        try:
            anim_file = anim_importer.readAnimFile(
                self.filepath,
                use_logical_size=True,
                verbose=self.print_log,
            )
        except Exception as exc:
            if self.print_log:
                print()
                print("DemonFF 0.6.9 ANIM Import Log")
                print(f"file={self.filepath}")
                print(f"ERROR: {exc}")
                print()
            self.report({"ERROR"}, f"Failed to read ANIM: {exc}")
            return {"CANCELLED"}

        if not anim_file.animations:
            self.report({"ERROR"}, "ANIM file parsed but contains no animations")
            return {"CANCELLED"}

        if self.animation_index >= len(anim_file.animations):
            self.report(
                {"ERROR"},
                f"Animation Index {self.animation_index} is out of range; file has {len(anim_file.animations)} animation(s)",
            )
            return {"CANCELLED"}

        entry = anim_file.animations[self.animation_index]
        selected_armature = anim_importer.findSelectedArmature(context)

        if self.apply_to_selected_armature and selected_armature is None:
            self.report({"ERROR"}, "Select an armature, an imported MDL mesh part, or its imported MDL root")
            return {"CANCELLED"}

        if self.apply_to_selected_armature:
            try:
                selected_game = str(selected_armature.get("bleeds_model_game", "") or "").upper().strip()
            except Exception:
                selected_game = ""
            if selected_game in {"MH2", "MANHUNT_2", "MH1", "MANHUNT", "MANHUNT_1"}:
                self.report(
                    {"ERROR"},
                    "Stories .anim is not a Manhunt animation container. Use DemonFF IFP (.ifp) for Manhunt animations.",
                )
                return {"CANCELLED"}

        mapping_lines: List[str] = []
        mapped_count = 0
        keyed_count = 0

        if self.apply_to_selected_armature:
            try:
                mapped_count, keyed_count, mapping_lines = anim_importer.applyAnimEntryToArmature(
                    selected_armature,
                    entry,
                    self.filepath,
                    fps=self.fps,
                    start_frame=self.start_frame,
                    apply_rotation=self.apply_rotation,
                    apply_translation=self.apply_translation,
                    translation_scale=self.translation_scale,
                    use_name_fallback=self.use_name_fallback,
                    use_table_index_fallback=self.use_table_index_fallback,
                    clear_existing_action=self.clear_existing_action,
                    pose_space_mode=self.pose_space_mode,
                    apply_root_motion=self.apply_root_motion,
                )
            except Exception as exc:
                summary = anim_importer.buildImportSummary(
                    anim_file,
                    entry,
                    self.filepath,
                    armature_object=selected_armature,
                    mapped_count=0,
                    keyed_count=0,
                    mapping_lines=["ERROR: " + str(exc)],
                )
                anim_importer.ensureTextBlock("DemonFF_ANIM_import_failed", summary)
                self.report({"ERROR"}, f"Could not apply ANIM: {exc}")
                return {"CANCELLED"}

        if self.create_text_summary or self.print_log:
            summary = anim_importer.buildImportSummary(
                anim_file,
                entry,
                self.filepath,
                armature_object=selected_armature,
                mapped_count=mapped_count,
                keyed_count=keyed_count,
                mapping_lines=mapping_lines,
            )

            if self.create_text_summary:
                text_name = "DemonFF_ANIM_" + Path(self.filepath).stem[:40]
                anim_importer.ensureTextBlock(text_name, summary)

            if self.print_log:
                print()
                print("DemonFF 0.6.9 ANIM Import Log")
                print(summary)
                print()

        if self.apply_to_selected_armature:
            unmapped = len(entry.bones) - mapped_count
            if mapped_count == 0:
                self.report(
                    {"WARNING"},
                    f"Parsed {entry.name}, but mapped 0 bones. Check the DemonFF_ANIM text summary for missing IDs/keys.",
                )
            else:
                self.report(
                    {"INFO"},
                    f"Imported {entry.name}: mapped {mapped_count}/{len(entry.bones)} bones, keyed {keyed_count} channels, unmapped {unmapped}",
                )
        else:
            self.report({"INFO"}, f"Parsed {Path(self.filepath).name}; created summary only")

        return {"FINISHED"}

ANIM_BONE_KEY_PROPERTY_NAMES = (
    "bleeds_anim_bone_key",
    "bleeds_mdl_anim_bone_key",
    "leeds_anim_bone_key",
    "anim_bone_key",
)

ANIM_HASH16_PROPERTY_NAMES = (
    "bleeds_anim_hash16",
    "bleeds_mdl_anim_hash16",
    "leeds_anim_hash16",
    "anim_hash16",
)


def getAnimationExportArmature(context):
    obj = context.object
    if obj is not None and getattr(obj, "type", None) == 'ARMATURE':
        return obj
    return anim_importer.findSelectedArmature(context)


def getAnimationBoneProperty(pose_bone, names):
    for owner in (pose_bone, getattr(pose_bone, "bone", None)):
        if owner is None:
            continue
        for property_name in names:
            try:
                if property_name in owner:
                    return int(owner[property_name])
            except Exception:
                continue
    return None


def getAnimationDirectId(pose_bone):
    direct_id = getAnimationBoneProperty(pose_bone, DIRECT_ID_PROPERTY_NAMES)
    if direct_id is not None:
        return int(direct_id)
    fallback = directIdFromBoneName(getattr(pose_bone, "name", ""))
    return int(fallback) if fallback is not None else None


def getAnimationBoneKey(pose_bone, direct_id):
    existing_key = getAnimationBoneProperty(pose_bone, ANIM_BONE_KEY_PROPERTY_NAMES)
    if existing_key is not None:
        return int(existing_key) & 0xFFFFFFFF

    existing_hash = getAnimationBoneProperty(pose_bone, ANIM_HASH16_PROPERTY_NAMES)
    if existing_hash is not None:
        return ((int(existing_hash) & 0xFFFF) << 16) | (int(direct_id) & 0xFFFF)

    inverse_hashes = {}
    for hash16, mapped_id in PED_ANIM_HASH16_TO_DIRECT_ID.items():
        inverse_hashes.setdefault(int(mapped_id), int(hash16))
    hash16 = inverse_hashes.get(int(direct_id), 0)
    return ((hash16 & 0xFFFF) << 16) | (int(direct_id) & 0xFFFF)


def getActionBoneFrames(action, bone_name):
    prefix = 'pose.bones["{}"]'.format(str(bone_name).replace('\\', '\\\\').replace('"', '\\"'))
    frames = set()
    has_location = False
    has_scale = False
    for curve in getattr(action, "fcurves", ()):
        if not str(getattr(curve, "data_path", "")).startswith(prefix):
            continue
        data_path = str(curve.data_path)
        if data_path.endswith('.location'):
            has_location = True
        elif data_path.endswith('.scale'):
            has_scale = True
        for point in curve.keyframe_points:
            frames.add(float(point.co[0]))
    return sorted(frames), has_location, has_scale


def loadAnimTrackMetadata(action):
    try:
        raw = action.get("DemonFF_ANIM_Track_Metadata", "")
    except Exception:
        return {}
    if not raw:
        return {}
    try:
        decoded = json.loads(str(raw))
        return decoded if isinstance(decoded, dict) else {}
    except Exception:
        return {}


def actionCurveHasMeaningfulValues(action, bone_name, channel, default_value, epsilon=1e-6):
    prefix = 'pose.bones["{}"]'.format(str(bone_name).replace('\\', '\\\\').replace('"', '\\"'))
    suffix = '.' + str(channel)
    found = False
    for curve in getattr(action, "fcurves", ()):
        data_path = str(getattr(curve, "data_path", ""))
        if not data_path.startswith(prefix) or not data_path.endswith(suffix):
            continue
        found = True
        for point in getattr(curve, "keyframe_points", ()):
            if abs(float(point.co[1]) - float(default_value)) > float(epsilon):
                return True
    return False if found else False


def blenderBasisToMdlLocal(armature, pose_bone, basis_matrix):
    mdl_rest, _mdl_source = anim_importer.getImportedMdlRestLocalMatrix(armature, pose_bone)
    blender_rest, _blender_source = anim_importer.getImportedBlenderRestLocalMatrix(armature, pose_bone)
    if mdl_rest is None:
        mdl_rest = anim_importer.getBlenderRestLocalMatrix(armature, pose_bone)
    if blender_rest is None:
        blender_rest = anim_importer.getBlenderRestLocalMatrix(armature, pose_bone)

    source_rot = anim_importer.rotationOnlyMatrix(mdl_rest)
    blender_rot = anim_importer.rotationOnlyMatrix(blender_rest)
    if source_rot is None or blender_rot is None:
        return mdl_rest @ basis_matrix

    source_to_blender = anim_importer.safeMatrixInverted(blender_rot) @ source_rot
    blender_to_source = anim_importer.safeMatrixInverted(source_to_blender)
    source_delta = blender_to_source @ basis_matrix @ source_to_blender
    return mdl_rest @ source_delta


def collectStoriesAnimEntry(context, export_translation=True, export_scale=False):
    armature = getAnimationExportArmature(context)
    if armature is None:
        raise ValueError("Select an armature with an active Action")
    if armature.animation_data is None or armature.animation_data.action is None:
        raise ValueError("Selected armature has no active Action")

    action = armature.animation_data.action
    fps = context.scene.render.fps / max(context.scene.render.fps_base, 1e-8)
    old_frame = context.scene.frame_current
    old_subframe = getattr(context.scene, "frame_subframe", 0.0)
    export_bones = []
    track_metadata = loadAnimTrackMetadata(action)
    try:
        imported_translation_scale = float(action.get("DemonFF_ANIM_Translation_Scale", 1.0))
    except Exception:
        imported_translation_scale = 1.0
    if abs(imported_translation_scale) <= 1e-8:
        imported_translation_scale = 1.0

    try:
        for pose_bone in armature.pose.bones:
            frames, has_location_curve, has_scale_curve = getActionBoneFrames(action, pose_bone.name)
            if not frames:
                continue

            source_metadata = track_metadata.get(str(pose_bone.name), {})
            source_flags = int(source_metadata.get("flags", 0)) if source_metadata else 0

            direct_id = source_metadata.get("direct_bone_id") if source_metadata else None
            if direct_id is None:
                direct_id = getAnimationDirectId(pose_bone)
            if direct_id is None:
                continue
            direct_id = int(direct_id)

            if source_metadata and source_metadata.get("bone_key") is not None:
                bone_key = int(source_metadata["bone_key"]) & 0xFFFFFFFF
            else:
                bone_key = getAnimationBoneKey(pose_bone, direct_id)

            source_has_rotation = bool(source_flags & 0x0001) if source_metadata else True
            source_has_translation = bool(source_flags & 0x0002) if source_metadata else False
            source_has_scale = bool(source_flags & 0x0004) if source_metadata else False
            source_has_direct_id = bool(source_flags & 0x0010) if source_metadata else True

            meaningful_location = actionCurveHasMeaningfulValues(
                action, pose_bone.name, "location", 0.0
            )
            meaningful_scale = actionCurveHasMeaningfulValues(
                action, pose_bone.name, "scale", 1.0
            )

            export_rotation_channel = source_has_rotation
            if not source_metadata:
                export_rotation_channel = True
            if source_metadata:
                export_translation_channel = bool(export_translation and source_has_translation)
                export_scale_channel = bool(export_scale and source_has_scale)
            else:
                export_translation_channel = bool(export_translation and has_location_curve and meaningful_location)
                export_scale_channel = bool(export_scale and has_scale_curve and meaningful_scale)

            if not (export_rotation_channel or export_translation_channel or export_scale_channel):
                continue

            first_frame = float(frames[0])
            export_frames = []
            for frame_number in frames:
                whole = math.floor(float(frame_number))
                subframe = float(frame_number) - float(whole)
                try:
                    context.scene.frame_set(whole, subframe=subframe)
                except TypeError:
                    context.scene.frame_set(whole)

                basis = pose_bone.matrix_basis.copy()
                mdl_local = blenderBasisToMdlLocal(armature, pose_bone, basis)
                quaternion = mdl_local.to_quaternion().normalized()
                location = mdl_local.to_translation()
                if export_translation_channel and source_metadata:
                    location = location / imported_translation_scale
                scale = mdl_local.to_scale()
                time = max(0.0, (float(frame_number) - first_frame) / max(fps, 1e-8))
                export_frames.append(
                    anim_format.AnimExportFrame(
                        time=time,
                        rotation_xyzw=(quaternion.x, quaternion.y, quaternion.z, quaternion.w),
                        translation_xyz=(location.x, location.y, location.z),
                        scale_xyz=(scale.x, scale.y, scale.z),
                    )
                )

            export_bones.append(
                anim_format.AnimExportBone(
                    bone_key=bone_key,
                    direct_bone_id=direct_id,
                    frames=export_frames,
                    export_rotation=bool(export_rotation_channel),
                    export_translation=bool(export_translation_channel),
                    export_scale=bool(export_scale_channel),
                    direct_id_marker=bool(source_has_direct_id),
                )
            )
    finally:
        try:
            context.scene.frame_set(int(old_frame), subframe=float(old_subframe))
        except TypeError:
            context.scene.frame_set(int(old_frame))

    if not export_bones:
        raise ValueError("Active Action has no animated bones with GTA/Stories animation BoneIDs")

    try:
        unk0 = int(action.get("DemonFF_ANIM_Unk0", 0))
    except Exception:
        unk0 = 0
    source_name = str(action.get("DemonFF_ANIM_Source_Name", "") or action.name)
    return anim_format.AnimExportEntry(name=source_name, bones=export_bones, unk0=unk0)


class EXPORT_OT_animation(Operator, ExportHelper):
    bl_idname = "export_scene.demonff_animation"
    bl_label = "Export Animation"
    bl_description = "Export the active armature Action as GTA IFP or GTA Stories ANIM"
    bl_options = {"REGISTER"}

    filename_ext = ".ifp"
    filter_glob: StringProperty(default="*.ifp;*.anim", options={"HIDDEN"}, maxlen=255)

    export_format: EnumProperty(
        name="Format",
        description="Animation format to write",
        items=(
            ("IFP", "IFP (.ifp)", "Export GTA RenderWare ANP3 IFP"),
            ("ANIM", "Stories ANIM (.anim)", "Export GTA LCS/VCS relocatable ANIM"),
        ),
        default="IFP",
    )

    export_translation: BoolProperty(
        name="Export Translation",
        description="Write keyed pose-bone location channels when the destination format supports them",
        default=True,
    )

    export_scale: BoolProperty(
        name="Export Scale",
        description="Write keyed scale channels to Stories ANIM; normally leave disabled for pedestrian animations",
        default=False,
    )

    pad_anim_to_sector: BoolProperty(
        name="Pad ANIM to 2048 Bytes",
        description="Pad Stories ANIM output to a 2048-byte sector boundary without changing its logical file size",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "export_format")
        layout.prop(self, "export_translation")
        if self.export_format == "ANIM":
            layout.prop(self, "export_scale")
            layout.prop(self, "pad_anim_to_sector")

    def check(self, context):
        wanted = ".ifp" if self.export_format == "IFP" else ".anim"
        current = str(self.filepath or "")
        lowered = current.lower()
        if lowered.endswith(".anim"):
            current = current[:-5]
        elif lowered.endswith(".ifp"):
            current = current[:-4]
        updated = current + wanted
        if updated != self.filepath:
            self.filepath = updated
            return True
        return False

    def invoke(self, context, event):
        armature = getAnimationExportArmature(context)
        if armature is not None and armature.animation_data is not None and armature.animation_data.action is not None:
            action_name = str(armature.animation_data.action.name or "animation")
            safe_name = "".join(character if character not in '<>:"/\\|?*' else '_' for character in action_name)
            if safe_name:
                self.filepath = safe_name + (".ifp" if self.export_format == "IFP" else ".anim")
        return super().invoke(context, event)

    def execute(self, context):
        try:
            self.check(context)
            if self.export_format == "IFP":
                from .ifp_ot import collect_animation_data, export_anp3
                ifp_data = collect_animation_data(context)
                with open(self.filepath, 'wb') as file_stream:
                    export_anp3(ifp_data, file_stream)
                self.report({"INFO"}, "Exported IFP: {}".format(self.filepath))
                return {"FINISHED"}

            entry = collectStoriesAnimEntry(
                context,
                export_translation=self.export_translation,
                export_scale=self.export_scale,
            )
            byte_count = anim_format.writeAnimFile(
                self.filepath,
                [entry],
                pad_to_sector=self.pad_anim_to_sector,
            )
            self.report({"INFO"}, "Exported Stories ANIM: {} bytes".format(byte_count))
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, "Animation export failed: {}".format(exc))
            return {"CANCELLED"}

