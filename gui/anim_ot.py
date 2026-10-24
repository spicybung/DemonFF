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
    bl_label = "Import ANIM"
    bl_description = "Import animations from GTA Liberty City Stories or Vice City Stories"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".anim"
    filter_glob: StringProperty(
        default="*.anim",
        options={"HIDDEN"},
        maxlen=255,
    )

    import_all_animations: BoolProperty(
        name="Import All Animations",
        description="Create a separate Blender action for each animation in the file",
        default=True,
    )

    print_txt_log: BoolProperty(
        name="Save Text Log",
        description="Save a dated .txt log next to the animation file",
        default=False,
    )

    animation_index: IntProperty(
        name="Animation Number",
        description="Animation to import; 0 is the first animation in the file",
        default=0,
        min=0,
    )

    apply_to_selected_armature: BoolProperty(
        name="Apply to Selected Model",
        description="Apply the animation to the selected model or armature; disable to read the file only",
        default=True,
    )

    create_text_summary: BoolProperty(
        name="Save Report in Blender",
        description="Keep an import report in Blender's Text Editor",
        default=True,
    )

    apply_rotation: BoolProperty(
        name="Bone Rotation",
        description="Import changes to bone angles",
        default=True,
    )

    apply_translation: BoolProperty(
        name="Bone Movement",
        description="Import changes to bone positions",
        default=False,
    )

    apply_root_motion: BoolProperty(
        name="Move Whole Model",
        description="Include movement of the root bone",
        default=False,
    )

    pose_space_mode: EnumProperty(
        name="Animation Method",
        description="How the animation is applied to the model's bones",
        items=(
            (
                "MDL_REST_DELTA",
                "Match Model",
                "Adjust the animation to the model's original bone positions and angles",
            ),
            (
                "PLR_REST_ROTATION_DELTA",
                "Relative Rotation",
                "Treat the file's bone rotations as changes from the model's original pose",
            ),
            (
                "MDL_ABSOLUTE_POSE",
                "Use File Pose",
                "Use the file's bone angles and any enabled movement directly",
            ),
            (
                "RAW_BASIS",
                "Direct Values",
                "Apply the animation values directly to Blender's bones",
            ),
        ),
        default="MDL_REST_DELTA",
    )

    translation_scale: FloatProperty(
        name="Movement Scale",
        description="Scale imported bone movement",
        default=1.0,
        precision=6,
    )

    use_scene_fps: BoolProperty(
        name="Use Scene Frame Rate",
        description="Use the scene frame rate so imported seconds play at the correct speed",
        default=True,
    )

    fps: FloatProperty(
        name="Frame Rate",
        description="Frame rate used to import the animation",
        default=30.0,
        min=1.0,
        max=240.0,
    )

    start_frame: FloatProperty(
        name="Start Frame",
        description="Frame where the animation starts",
        default=1.0,
    )

    use_name_fallback: BoolProperty(
        name="Match Bone Names",
        description="Try bone names when a bone cannot be matched by its number",
        default=True,
    )

    use_table_index_fallback: BoolProperty(
        name="Match Bone Order",
        description="Try the order of bones in the file when their names and numbers do not match",
        default=False,
    )

    clear_existing_action: BoolProperty(
        name="Create New Action",
        description="Create a new Action instead of writing into the active Action",
        default=True,
    )

    print_log: BoolProperty(
        name="Console Log",
        description="Write import details to Blender's System Console",
        default=False,
    )

    show_advanced: BoolProperty(
        name="Advanced",
        description="Show animation methods and bone matching options",
        default=False,
        options={'SKIP_SAVE'},
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        column = layout.column(align=True)
        column.prop(self, "import_all_animations")
        if not self.import_all_animations:
            column.prop(self, "animation_index")
        column.prop(self, "apply_to_selected_armature")
        if not self.import_all_animations:
            column.prop(self, "clear_existing_action")

        box = layout.box()
        box.label(text="Bone Animation")
        column = box.column(align=True)
        column.prop(self, "apply_rotation")
        column.prop(self, "apply_translation")
        movement = column.column(align=True)
        movement.enabled = self.apply_translation
        movement.prop(self, "apply_root_motion")
        movement.prop(self, "translation_scale")

        box = layout.box()
        box.label(text="Playback")
        column = box.column(align=True)
        column.prop(self, "use_scene_fps")
        if not self.use_scene_fps:
            column.prop(self, "fps")
        column.prop(self, "start_frame")

        box = layout.box()
        box.label(text="Reports")
        column = box.column(align=True)
        column.prop(self, "create_text_summary")
        column.prop(self, "print_log")
        column.prop(self, "print_txt_log")

        layout.prop(self, "show_advanced", icon='TRIA_DOWN' if self.show_advanced else 'TRIA_RIGHT', emboss=False)
        if self.show_advanced:
            box = layout.box()
            box.prop(self, "pose_space_mode")
            box.label(text="Bone Matching")
            column = box.column(align=True)
            column.prop(self, "use_name_fallback")
            column.prop(self, "use_table_index_fallback")

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
            self.report({"ERROR"}, "No animations were found in this file")
            return {"CANCELLED"}

        if not self.import_all_animations and self.animation_index >= len(anim_file.animations):
            self.report({'ERROR'}, 'Animation Number must be between 0 and ' + str(len(anim_file.animations) - 1))
            return {'CANCELLED'}
        selected_armature = anim_importer.findSelectedArmature(context)
        if self.apply_to_selected_armature and selected_armature is None:
            self.report({'ERROR'}, 'Select a model or armature to animate')
            return {'CANCELLED'}
        if self.apply_to_selected_armature:
            selected_game = str(selected_armature.get('bleeds_model_game', '') or '').upper().strip()
            if selected_game in {'MH2', 'MANHUNT_2', 'MH1', 'MANHUNT', 'MANHUNT_1'}:
                self.report({'ERROR'}, 'Import Manhunt animations with Import IFP')
                return {'CANCELLED'}
        effective_fps = context.scene.render.fps / max(context.scene.render.fps_base, 1e-8) if self.use_scene_fps else self.fps
        entries = anim_file.animations if self.import_all_animations else [anim_file.animations[self.animation_index]]
        summaries = ['DemonFF 0.6.9b ANIM Import Log', 'importer_build=ANIMATION-28']
        created_actions = []
        mapped_total = 0
        source_total = sum(len(entry.bones) for entry in entries)
        try:
            for entry in entries:
                mapped_count = 0
                keyed_count = 0
                mapping_lines = []
                if self.apply_to_selected_armature:
                    mapped_count, keyed_count, mapping_lines = anim_importer.applyAnimEntryToArmature(
                        selected_armature, entry, self.filepath,
                        fps=effective_fps, start_frame=self.start_frame,
                        apply_rotation=self.apply_rotation, apply_translation=self.apply_translation,
                        translation_scale=self.translation_scale, use_name_fallback=self.use_name_fallback,
                        use_table_index_fallback=self.use_table_index_fallback,
                        clear_existing_action=True if self.import_all_animations else self.clear_existing_action,
                        pose_space_mode=self.pose_space_mode, apply_root_motion=self.apply_root_motion,
                    )
                    created_actions.append(selected_armature.animation_data.action)
                mapped_total += mapped_count
                summaries.append(anim_importer.buildImportSummary(
                    anim_file, entry, self.filepath, armature_object=selected_armature,
                    mapped_count=mapped_count, keyed_count=keyed_count, mapping_lines=mapping_lines))
            if created_actions:
                from ..ops.animation_channels import resetUnkeyedActionChannels
                selected_armature.animation_data.action = created_actions[0]
                resetUnkeyedActionChannels(selected_armature, created_actions[0])
                context.scene.frame_set(int(self.start_frame), subframe=self.start_frame - int(self.start_frame))
        except Exception as error:
            summaries.append('ERROR: ' + str(error))
            anim_importer.ensureTextBlock('DemonFF_ANIM_import_failed', '\n\n'.join(summaries))
            self.report({'ERROR'}, 'Could not apply ANIM: ' + str(error))
            return {'CANCELLED'}
        summary = '\n\n'.join(summaries)
        if self.create_text_summary:
            anim_importer.ensureTextBlock('DemonFF_ANIM_' + Path(self.filepath).stem[:40], summary)
        if self.print_log:
            print(summary)
        if self.print_txt_log:
            from datetime import datetime
            source = Path(self.filepath)
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            log_path = source.with_name(source.name + '.DemonFF-0.6.9b-anim-' + stamp + '.txt')
            try:
                with log_path.open('x', encoding='utf-8', newline='\n') as output:
                    output.write('Import time: ' + datetime.now().isoformat(timespec='microseconds') + '\n')
                    output.write('Imported file: ' + str(source.resolve()) + '\n\n' + summary + '\n')
                self.report({'INFO'}, 'ANIM log saved: ' + str(log_path))
            except OSError as error:
                self.report({'WARNING'}, 'Could not save ANIM log: ' + str(error))
        message = f'Imported {len(entries)} animations; matched {mapped_total} of {source_total} bones' if self.apply_to_selected_armature else f'Read {len(entries)} animations'
        self.report({'INFO'}, message)
        return {'FINISHED'}


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

    action = armature.animation_data.action if armature.animation_data else None
    mode = str(action.get("DemonFF_ANIM_Pose_Space_Mode", "MDL_REST_DELTA")) if action else "MDL_REST_DELTA"
    if mode == 'RAW_BASIS':
        return basis_matrix.copy()
    if mode in ('MDL_ABSOLUTE_POSE', 'ABSOLUTE_POSE', 'ABSOLUTE_MDL_POSE'):
        return anim_importer.getBlenderRestLocalMatrix(armature, pose_bone) @ basis_matrix
    source_rot = anim_importer.rotationOnlyMatrix(mdl_rest)
    blender_rot = anim_importer.rotationOnlyMatrix(blender_rest)
    if source_rot is None or blender_rot is None:
        return mdl_rest @ basis_matrix

    source_to_blender = anim_importer.safeMatrixInverted(blender_rot) @ source_rot
    blender_to_source = anim_importer.safeMatrixInverted(source_to_blender)
    source_delta = blender_to_source @ basis_matrix @ source_to_blender
    if mode in ('PLR_REST_ROTATION_DELTA', 'RAW_REST_ROTATION_DELTA', 'DEBUG_PLR_REST_ROTATION_DELTA'):
        source_delta.translation = basis_matrix.translation
        return source_delta
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

    action_frames = []
    for pose_bone in armature.pose.bones:
        bone_frames, _has_location_curve, _has_scale_curve = getActionBoneFrames(action, pose_bone.name)
        action_frames.extend(bone_frames)
    if not action_frames:
        raise ValueError("Active Action contains no pose-bone keyframes")

    if bool(action.get("DemonFF_ANIM_Imported_Action", False)):
        try:
            export_time_origin_frame = float(action.get("DemonFF_ANIM_Start_Frame", 0.0) or 0.0)
        except (TypeError, ValueError):
            export_time_origin_frame = 0.0
        if not math.isfinite(export_time_origin_frame):
            export_time_origin_frame = 0.0
    else:
        export_time_origin_frame = min(action_frames)

    try:
        for pose_bone in armature.pose.bones:
            frames, has_location_curve, has_scale_curve = getActionBoneFrames(action, pose_bone.name)
            source_metadata = track_metadata.get(str(pose_bone.name), {})
            if not frames and source_metadata.get('source_frames'):
                frames = sorted({
                    export_time_origin_frame + float(sample[0]) * fps
                    for sample in source_metadata['source_frames']
                })
            if not frames:
                continue
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

            export_frames = []
            for frame_number in frames:
                from ..ops.animation_channels import sampleActionBoneBasis
                basis = sampleActionBoneBasis(action, pose_bone.name, frame_number, pose_bone.rotation_mode)
                mdl_local = blenderBasisToMdlLocal(armature, pose_bone, basis)
                quaternion = mdl_local.to_quaternion().normalized()
                location = mdl_local.to_translation()
                if export_translation_channel and source_metadata:
                    location = location / imported_translation_scale
                scale = mdl_local.to_scale()
                time = max(0.0, (float(frame_number) - export_time_origin_frame) / max(fps, 1e-8))
                source_frames = source_metadata.get('source_frames', []) if source_metadata else []
                if source_frames:
                    nearest = min(source_frames, key=lambda sample: abs(float(sample[0]) - time))
                    if abs(float(nearest[0]) - time) < 0.0001:
                        if not bool(action.get('DemonFF_ANIM_Rotation_Applied', True)):
                            quaternion = anim_importer.normalizeAnimQuaternion(tuple(nearest[1]))
                        translation_disabled = not bool(action.get('DemonFF_ANIM_Translation_Applied', True))
                        root_locked = direct_id == 0 and not bool(action.get('DemonFF_ANIM_Root_Motion_Applied', True))
                        if (translation_disabled or root_locked) and not has_location_curve:
                            location = anim_importer.Vector(nearest[2])
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
                    extra_flags=source_flags & ~0x0017,
                )
            )
    finally:
        try:
            context.scene.frame_set(int(old_frame), subframe=float(old_subframe))
        except TypeError:
            context.scene.frame_set(int(old_frame))

    unmapped_tracks = json.loads(str(action.get('DemonFF_ANIM_Unmapped_Tracks', '[]')))
    for track in unmapped_tracks:
        flags = int(track['flags'])
        frames = [anim_format.AnimExportFrame(float(frame[0]), tuple(frame[1]), tuple(frame[2]), tuple(frame[3])) for frame in track['frames']]
        export_bones.append(anim_format.AnimExportBone(
            int(track['bone_key']), int(track['direct_bone_id'] if track['direct_bone_id'] is not None else -1), frames,
            bool(flags & 1), bool(flags & 2) and export_translation, bool(flags & 4) and export_scale,
            bool(flags & 0x10), flags & ~0x17))
    if not export_bones:
        raise ValueError("Active Action has no animated bones with GTA/Stories animation BoneIDs")

    try:
        unk0 = int(action.get("DemonFF_ANIM_Unk0", 0))
    except Exception:
        unk0 = 0
    source_name = str(action.get("DemonFF_ANIM_Source_Name", "") or action.name)
    total_time_override = None
    if bool(action.get("DemonFF_ANIM_Imported_Action", False)):
        try:
            total_time_override = float(action.get("DemonFF_ANIM_Total_Time", 0.0) or 0.0)
        except (TypeError, ValueError):
            total_time_override = None
        if total_time_override is not None and (not math.isfinite(total_time_override) or total_time_override < 0.0):
            total_time_override = None
    return anim_format.AnimExportEntry(
        name=source_name,
        bones=export_bones,
        unk0=unk0,
        total_time=total_time_override,
    )


class EXPORT_OT_animation(Operator, ExportHelper):
    bl_idname = "export_scene.demonff_animation"
    bl_label = "Export Animation"
    bl_description = "Export the active armature Action as GTA IFP or GTA Stories ANIM"
    bl_options = {"REGISTER"}

    filename_ext = ".ifp"
    filter_glob: StringProperty(default="*.ifp;*.anim", options={"HIDDEN"}, maxlen=255)

    target_game: EnumProperty(
        name="Target Game",
        description="Write the animation format used by the selected game",
        items=(
            ('GTA_III', 'GTA III', 'ANPK IFP with named bone tracks'),
            ('VICE_CITY', 'GTA Vice City', 'ANPK IFP with named bone tracks'),
            ('SAN_ANDREAS', 'GTA San Andreas', 'ANP3 IFP with tagged and named bone tracks'),
            ('LCS', 'GTA Liberty City Stories', 'Leeds ANIM'),
            ('VCS', 'GTA Vice City Stories', 'Leeds ANIM'),
            ('MANHUNT_1', 'Manhunt', 'ANCT IFP with SEQU tracks and Manhunt Animation BoneIDs'),
        ),
        default='SAN_ANDREAS',
    )

    block_name: StringProperty(
        name='Block Name',
        description='Animation block name; leave empty to retain the imported block name',
        default='',
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
        layout.prop(self, "target_game")
        if self.target_game not in ('LCS', 'VCS'):
            layout.prop(self, 'block_name')
        layout.prop(self, "export_translation")
        if self.target_game in ('GTA_III', 'VICE_CITY', 'LCS', 'VCS'):
            layout.prop(self, 'export_scale')
        if self.target_game in ('LCS', 'VCS'):
            layout.prop(self, 'pad_anim_to_sector')

    def check(self, context):
        wanted = '.anim' if self.target_game in ('LCS', 'VCS') else '.ifp' 
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
                self.filepath = safe_name + ('.anim' if self.target_game in ('LCS', 'VCS') else '.ifp')
        return super().invoke(context, event)

    def execute(self, context):
        try:
            self.check(context)
            if self.target_game in ('LCS', 'VCS'):
                entry = collectStoriesAnimEntry(context, self.export_translation, self.export_scale)
                output = anim_format.buildAnimBytes([entry], pad_to_sector=self.pad_anim_to_sector)
            else:
                from ..gtaLib.animation_conversion import ifpDataToConversionClips, buildTargetAnimationBytes
                if self.target_game == 'MANHUNT_1':
                    from ..ops.manhunt_retarget import collectManhunt1Clip
                    clips = [collectManhunt1Clip(context, self.export_translation)]
                    armature = getAnimationExportArmature(context)
                    action = armature.animation_data.action
                    package_name = str(action.get('DemonFF_IFP_Block_Name', '') or action.get('DemonFF_IFP_Package_Name', '') or 'DemonFF')
                else:
                    from .ifp_ot import collect_animation_data
                    data = collect_animation_data(context)
                    clips = ifpDataToConversionClips(data, self.export_translation, self.export_scale)
                    package_name = data.name
                package_name = self.block_name.strip() or package_name
                output = buildTargetAnimationBytes(clips, self.target_game, package_name)
            Path(self.filepath).write_bytes(output)
            self.report({'INFO'}, f'Exported {self.target_game}: {len(output)} bytes')
            return {'FINISHED'}
        except Exception as error:
            self.report({'ERROR'}, 'Animation export failed: ' + str(error))
            return {'CANCELLED'}



class CONVERT_OT_animation_file(Operator, ImportHelper):
    bl_idname = "demonff.convert_animation_file"
    bl_label = "Convert Animation File"
    bl_description = "Convert all clips between Stories ANIM and San Andreas ANP3 IFP without a selected rig"
    filename_ext = ".anim"
    filter_glob: StringProperty(default="*.anim;*.ifp", options={'HIDDEN'})
    from ..gtaLib.animation_conversion import TARGET_GAME_ITEMS
    target_game: EnumProperty(name='Target Game', items=TARGET_GAME_ITEMS, default='SAN_ANDREAS')

    def draw(self, context):
        self.layout.prop(self, 'target_game')

    def execute(self, context):
        from ..gtaLib.animation_conversion import convertAnimationFile
        source = Path(self.filepath)
        try:
            magic = source.read_bytes()[:4]
            extension = '.anim' if self.target_game in ('LCS', 'VCS') else '.ifp'
            destination = source.with_name(source.stem + '-converted' + extension)
            suffix = 2
            while destination.exists():
                destination = source.with_name(source.stem + '-converted-' + str(suffix) + extension)
                suffix += 1
            count, byte_count = convertAnimationFile(source, destination, self.target_game)
            self.report({'INFO'}, f'Converted {count} clips: {destination.name}')
            return {'FINISHED'}
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
