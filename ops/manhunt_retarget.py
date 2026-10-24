# DemonFF - Manhunt animation transfer
# 2026 spicybung

import bisect
import json
import math

from mathutils import Matrix, Quaternion, Vector

from ..data.bone_data import normalizeAnimBoneName


MANHUNT_PARENTS = {
    1000: None, 1045: 1000, 1094: 1045, 1095: 1094,
    1096: 1095, 1040: 1096, 1001: 1040,
    1003: 1040, 1039: 1003, 1020: 1039, 1021: 1020, 1004: 1021,
    1057: 1040, 1093: 1057, 1074: 1093, 1075: 1074, 1058: 1075,
    1023: 1094, 1002: 1023, 1019: 1002, 1024: 1019,
    1077: 1094, 1056: 1077, 1073: 1056, 1078: 1073,
}


def manhuntBipedRestRotations():
    half = math.sqrt(0.5)
    rotations = {source_id: Quaternion() for source_id in MANHUNT_PARENTS}
    rotations.update({
        1000: Quaternion((half, 0.0, half, 0.0)),
        1045: Quaternion((0.5, -0.5, -0.5, 0.5)),
        1003: Quaternion((0.0, -half, -half, 0.0)),
        1057: Quaternion((0.0, half, -half, 0.0)),
        1021: Quaternion((half, -half, 0.0, 0.0)),
        1075: Quaternion((half, half, 0.0, 0.0)),
        1023: Quaternion((0.0, 0.0, 0.0, 1.0)),
        1077: Quaternion((0.0, 0.0, 0.0, 1.0)),
        1024: Quaternion((half, 0.0, half, 0.0)),
        1078: Quaternion((half, 0.0, half, 0.0)),
    })
    return rotations


def makeBodyFrame(side, up):
    side = side.normalized()
    up = (up - side * side.dot(up)).normalized()
    if side.length < 0.5 or up.length < 0.5:
        raise ValueError('Cannot determine the selected armature body axes')
    front = side.cross(up).normalized()
    return Matrix((side, up, front)).transposed().to_quaternion()


def prepareManhuntTrack(track):
    frames = sorted(track.keyframes, key=lambda key: float(key.time))
    return frames, [float(key.time) for key in frames]


def sampleManhuntTrack(prepared, time):
    frames, times = prepared
    index = bisect.bisect_right(times, time)
    if index == 0:
        key = frames[0]
        return key.rot.normalized(), key.pos.copy()
    if index >= len(frames):
        key = frames[-1]
        return key.rot.normalized(), key.pos.copy()
    start = frames[index - 1]
    end = frames[index]
    duration = float(end.time) - float(start.time)
    factor = (time - float(start.time)) / duration if duration > 0.0 else 1.0
    return start.rot.normalized().slerp(end.rot.normalized(), factor), start.pos.lerp(end.pos, factor)


def reduceManhuntSamples(samples, tolerance=0.000001):
    if len(samples) <= 2:
        return samples
    first_values = samples[0][1]
    if all(max(abs(value - first_values[index]) for index, value in enumerate(values)) <= tolerance
           for frame, values in samples):
        return [samples[0]]
    keep = {0, len(samples) - 1}
    pending = [(0, len(samples) - 1)]
    while pending:
        start, end = pending.pop()
        start_time, start_values = samples[start]
        end_time, end_values = samples[end]
        duration = end_time - start_time
        worst_error = tolerance
        worst_index = None
        for index in range(start + 1, end):
            frame, values = samples[index]
            factor = (frame - start_time) / duration if duration > 0.0 else 0.0
            error = max(abs(value - (start_values[component] +
                        (end_values[component] - start_values[component]) * factor))
                        for component, value in enumerate(values))
            if error > worst_error:
                worst_error = error
                worst_index = index
        if worst_index is not None:
            keep.add(worst_index)
            pending.append((start, worst_index))
            pending.append((worst_index, end))
    return [samples[index] for index in sorted(keep)]


def writeManhuntCurves(action, bone_name, channel, samples):
    samples = reduceManhuntSamples(samples)
    path = 'pose.bones[' + json.dumps(bone_name) + '].' + channel
    width = len(samples[0][1])
    for component in range(width):
        curve = action.fcurves.new(path, index=component, action_group=bone_name)
        curve.keyframe_points.add(len(samples))
        coordinates = []
        for frame, values in samples:
            coordinates.extend((frame, float(values[component])))
        curve.keyframe_points.foreach_set('co', coordinates)
        for key in curve.keyframe_points:
            key.interpolation = 'LINEAR'
        curve.update()


def adaptiveManhuntRotations(evaluate, times, fps, tolerance=math.radians(0.1)):
    samples = []
    cosine_limit = math.cos(tolerance * 0.5)

    def appendInterval(begin_time, begin, end_time, end, depth):
        if begin.dot(end) < 0.0:
            end = -end
        split = False
        for factor in (0.25, 0.5, 0.75):
            time = begin_time + (end_time - begin_time) * factor
            actual = evaluate(time)
            interpolated = Quaternion(tuple(begin[index] * (1.0 - factor) + end[index] * factor for index in range(4))).normalized()
            if abs(actual.dot(interpolated)) < cosine_limit:
                split = True
                break
        if split and depth < 10 and end_time - begin_time > 0.00001:
            middle_time = (begin_time + end_time) * 0.5
            middle = evaluate(middle_time)
            appendInterval(begin_time, begin, middle_time, middle, depth + 1)
            appendInterval(middle_time, middle, end_time, end, depth + 1)
        else:
            previous = Quaternion(samples[-1][1]) if samples else begin
            if previous.dot(end) < 0.0:
                end = -end
            samples.append((end_time * fps, tuple(end)))

    first_time = times[0]
    first = evaluate(first_time)
    samples.append((first_time * fps, tuple(first)))
    for begin_time, end_time in zip(times, times[1:]):
        appendInterval(begin_time, evaluate(begin_time), end_time, evaluate(end_time), 0)
    return samples


def createManhuntHumanoidAction(armature, animation, fps, global_matrix, mapping, lookup, source_positions=None):
    import bpy

    bones_by_id, bones_by_name = lookup(armature)
    rest_rotations = manhuntBipedRestRotations()
    source_rest_world = {}
    for source_id, parent_id in MANHUNT_PARENTS.items():
        rotation = rest_rotations[source_id]
        source_rest_world[source_id] = (
            source_rest_world[parent_id] @ rotation if parent_id is not None else rotation
        )

    targets = {}
    for source_id, (name, priority) in mapping.items():
        if source_id not in MANHUNT_PARENTS:
            continue
        normalized = normalizeAnimBoneName(name)
        target = bones_by_name.get(normalized)
        if target is not None:
            previous = targets.get(target.name)
            if previous is None or priority > previous[1]:
                targets[target.name] = (source_id, priority, target)

    def targetFor(source_id):
        return next((item[2] for item in targets.values() if item[0] == source_id), None)

    left = targetFor(1039)
    right = targetFor(1093)
    pelvis = targetFor(1045)
    neck = targetFor(1040)
    if any(bone is None for bone in (left, right, pelvis, neck)):
        raise ValueError('Manhunt transfer needs pelvis, neck and both upper arms on the selected rig')
    body_frame = makeBodyFrame(
        left.matrix_local.translation - right.matrix_local.translation,
        neck.matrix_local.translation - pelvis.matrix_local.translation,
    )
    source_frame = makeBodyFrame(Vector((-1.0, 0.0, 0.0)), Vector((0.0, 1.0, 0.0)))
    alignment = body_frame @ source_frame.inverted()
    alignment_inverse = alignment.inverted()

    prepared = {}
    tracks = {}
    missing = set()
    for track in animation.bones:
        source_id = int(track.bone_id)
        if not track.keyframes:
            continue
        if source_id in MANHUNT_PARENTS:
            prepared[source_id] = prepareManhuntTrack(track)
            tracks[source_id] = track
        elif source_id in mapping and source_id not in (1006, 1005, 1011, 1008, 1013, 1060, 1059, 1065, 1062, 1067):
            missing.add(str(source_id))

    all_times = [float(key.time) for track in tracks.values() for key in track.keyframes]
    end_time = max([0.0] + all_times)
    bones = sorted(armature.data.bones, key=lambda bone: len(bone.parent_recursive))
    root_bone = targetFor(1000)
    root_reference = Vector((0.0, 0.0, 0.0))
    if source_positions and 1000 in source_positions:
        root_reference = source_positions[1000].copy()
    elif 1000 in prepared:
        root_reference = prepared[1000][0][0].pos.copy()
    scale = 1.0
    if abs(root_reference.y) > 0.01:
        feet = [targetFor(source_id) for source_id in (1019, 1073)]
        feet = [bone for bone in feet if bone is not None]
        if feet:
            up = body_frame @ Vector((0.0, 1.0, 0.0))
            floor = sum(bone.matrix_local.translation.dot(up) for bone in feet) / len(feet)
            height = pelvis.matrix_local.translation.dot(up) - floor
            if height > 0.0:
                scale = height / abs(root_reference.y)

    action = bpy.data.actions.new(animation.name)
    action.use_fake_user = True
    action.use_frame_range = True
    action.frame_start = 0.0
    action.frame_end = end_time * fps
    metadata = {}
    sampled_count = 0
    for bone in bones:
        entry = targets.get(bone.name)
        if entry is None:
            continue
        source_id = entry[0]
        ancestor = bone.parent
        while ancestor is not None and ancestor.name not in targets:
            ancestor = ancestor.parent
        ancestor_id = targets[ancestor.name][0] if ancestor is not None else None
        chain = []
        current = source_id
        while current is not None and current != ancestor_id:
            chain.append(current)
            current = MANHUNT_PARENTS[current]
        if current != ancestor_id:
            raise ValueError('The source and destination bone chains cannot be matched')
        chain.reverse()
        active_ids = [item for item in chain if item in prepared]
        if not active_ids:
            continue
        target_rest_rotation = bone.matrix_local.to_quaternion().normalized()
        ancestor_rest = source_rest_world[ancestor_id] if ancestor_id is not None else Quaternion()
        left = target_rest_rotation.inverted() @ alignment @ ancestor_rest
        right = source_rest_world[source_id].inverted() @ alignment_inverse @ target_rest_rotation

        def rotationAt(time):
            relative = Quaternion()
            for item in chain:
                rotation = sampleManhuntTrack(prepared[item], time)[0] if item in prepared else rest_rotations[item]
                relative = relative @ rotation
            return (left @ relative @ right).normalized()

        key_times = {0.0, end_time}
        for item in active_ids:
            key_times.update(max(0.0, value) for value in prepared[item][1])
        ordered_times = sorted(key_times)
        samples = adaptiveManhuntRotations(rotationAt, ordered_times, fps)
        sampled_count += len(samples)
        armature.pose.bones[bone.name].rotation_mode = 'QUATERNION'
        writeManhuntCurves(action, bone.name, 'rotation_quaternion', samples)

        if root_bone is not None and bone == root_bone and 1000 in prepared:
            parent_rest = bone.parent.matrix_local if bone.parent else Matrix.Identity(4)
            local_rest = parent_rest.inverted_safe() @ bone.matrix_local
            positions = []
            for time in ordered_times:
                position = sampleManhuntTrack(prepared[1000], time)[1]
                location = local_rest.to_3x3().inverted_safe() @ (alignment @ (position - root_reference) * scale)
                positions.append((time * fps, tuple(location)))
            if any(max(abs(value) for value in values) > 0.000001 for frame, values in positions):
                writeManhuntCurves(action, bone.name, 'location', positions)

        track = tracks.get(source_id)
        if track is not None:
            metadata[bone.name] = {
                'source_name': track.name, 'bone_id': source_id,
                'keyframe_type': track.keyframe_type, 'use_bone_id': True,
            }
            if source_id == 1096 and 1095 in tracks:
                metadata[bone.name]['merged_source_ids'] = [1095, 1096]
    action['DemonFF_IFP_Source_Root_Position'] = tuple(root_reference)
    action['DemonFF_IFP_Source_Root_Scale'] = float(scale)
    action['DemonFF_IFP_Duration'] = end_time
    action['DemonFF_IFP_Sampled_Rotations'] = sampled_count
    action['DemonFF_IFP_Retarget_Version'] = 28
    action['DemonFF_IFP_Solver'] = 'MH1_SPARSE_BONE_CHAINS'
    action['DemonFF_IFP_Source_Rest'] = 'Canonical Manhunt biped axes'
    action['DemonFF_IFP_Hierarchy_Corrections'] = 0
    action['DemonFF_IFP_Missing_Bone_Count'] = len(missing)
    action['DemonFF_IFP_Duplicate_Target_Count'] = 0
    action['DemonFF_IFP_Source_Reference_Used'] = False
    action['DemonFF_IFP_Applied_Track_Count'] = len(metadata)
    action['DemonFF_IFP_Track_Metadata'] = json.dumps(metadata, separators=(',', ':'), sort_keys=True)
    return action, missing


def collectManhunt1Clip(context, export_translation=True):
    from ..gui.ifp_ot import build_armature_bone_lookup, MH2_GTA_HUMANOID_BONES
    from .anim_importer import findSelectedArmature
    from .animation_channels import sampleActionBoneBasis
    from ..gtaLib.animation_conversion import ConversionClip, ConversionTrack
    from ..gtaLib.anim import AnimExportFrame

    armature = findSelectedArmature(context)
    if armature is None or armature.animation_data is None or armature.animation_data.action is None:
        raise ValueError('Select an armature with an active Action')
    action = armature.animation_data.action
    fps = context.scene.render.fps / max(context.scene.render.fps_base, 0.000001)
    by_id, by_name = build_armature_bone_lookup(armature)
    bones = sorted(armature.data.bones, key=lambda bone: len(bone.parent_recursive))
    frame_times = sorted({float(key.co.x) for curve in action.fcurves for key in curve.keyframe_points})
    if not frame_times:
        raise ValueError('The active Action has no animation keys')
    begin = min(frame_times)
    duration = max(frame_times) - begin
    stored_duration = float(action.get('DemonFF_IFP_Duration', 0.0))
    duration = max(duration / fps, stored_duration)
    frame_times = sorted(set(frame_times) | {begin + duration * fps})
    clip = ConversionClip(str(action.get('DemonFF_IFP_Source_Name', '') or action.get('DemonFF_ANIM_Source_Name', '') or action.name), duration=duration)

    if any(source_id in by_id for source_id in MANHUNT_PARENTS):
        for source_id, bone in by_id.items():
            prefix = 'pose.bones[' + json.dumps(bone.name) + '].'
            curves = [curve for curve in action.fcurves if curve.data_path.startswith(prefix)]
            if not curves:
                continue
            if source_id < 1000:
                raise ValueError('Assign a Manhunt Animation BoneID to ' + bone.name)
            parent_rest = bone.parent.matrix_local if bone.parent else Matrix.Identity(4)
            local_rest = parent_rest.inverted_safe() @ bone.matrix_local
            translation = export_translation and any(curve.data_path.endswith('.location') for curve in curves)
            frames = []
            for frame in frame_times:
                local = local_rest @ sampleActionBoneBasis(action, bone.name, frame)
                rotation = local.to_quaternion().normalized()
                frames.append(AnimExportFrame((frame - begin) / fps, (rotation.x, rotation.y, rotation.z, rotation.w), tuple(local.translation)))
            clip.tracks.append(ConversionTrack(source_id, bone.name, frames, translation))
        return clip

    source_targets = {}
    for source_id, (name, priority) in MH2_GTA_HUMANOID_BONES.items():
        if source_id in MANHUNT_PARENTS and source_id != 1095:
            bone = by_name.get(normalizeAnimBoneName(name))
            if bone is not None:
                source_targets[source_id] = bone
    if not all(source_id in source_targets for source_id in (1000, 1045, 1040, 1039, 1093)):
        raise ValueError('The selected rig needs a root, pelvis, neck and both upper arms for Manhunt export')
    unmapped = json.loads(str(action.get('DemonFF_ANIM_Unmapped_Tracks', '[]')))
    if unmapped:
        raise ValueError('These source channels need matching Manhunt bones before export: ' + ', '.join(f"0x{int(track['bone_key']):08X}" for track in unmapped))
    mapped_names = {bone.name for bone in source_targets.values()}
    for bone in bones:
        prefix = 'pose.bones[' + json.dumps(bone.name) + '].'
        if bone.name not in mapped_names and any(curve.data_path.startswith(prefix) for curve in action.fcurves):
            raise ValueError('Assign a Manhunt Animation BoneID to animated bone ' + bone.name)
    body = makeBodyFrame(source_targets[1039].head_local - source_targets[1093].head_local,
                         source_targets[1040].head_local - source_targets[1045].head_local)
    source_body = makeBodyFrame(Vector((-1.0, 0.0, 0.0)), Vector((0.0, 1.0, 0.0)))
    alignment = body @ source_body.inverted()
    rest = manhuntBipedRestRotations()
    rest_world = {}
    for source_id, parent_id in MANHUNT_PARENTS.items():
        rest_world[source_id] = rest_world[parent_id] @ rest[source_id] if parent_id is not None else rest[source_id]
    samples = {source_id: [] for source_id in source_targets}
    root_name = source_targets[1000].name
    root_path = 'pose.bones[' + json.dumps(root_name) + '].location'
    has_root_translation = export_translation and any(curve.data_path == root_path for curve in action.fcurves)
    if has_root_translation and 'DemonFF_IFP_Source_Root_Position' not in action:
        raise ValueError('Export root translation on a native Manhunt rig, or use an Action imported by this version')
    root_reference = Vector(action.get('DemonFF_IFP_Source_Root_Position', (0.0, 0.0, 0.0)))
    root_scale = float(action.get('DemonFF_IFP_Source_Root_Scale', 1.0))
    for frame in frame_times:
        target_world = {}
        for bone in bones:
            parent = bone.parent
            parent_rest = parent.matrix_local if parent else Matrix.Identity(4)
            local_rest = parent_rest.inverted_safe() @ bone.matrix_local
            parent_pose = target_world[parent.name] if parent else Matrix.Identity(4)
            target_world[bone.name] = parent_pose @ local_rest @ sampleActionBoneBasis(action, bone.name, frame)
        source_world = {}
        for source_id, parent_id in MANHUNT_PARENTS.items():
            bone = source_targets.get(source_id)
            if bone is None:
                source_world[source_id] = source_world[parent_id] @ rest[source_id] if parent_id is not None else rest[source_id]
                continue
            delta = target_world[bone.name].to_quaternion() @ bone.matrix_local.to_quaternion().inverted()
            world = alignment.inverted() @ delta @ alignment @ rest_world[source_id]
            source_world[source_id] = world
            local = source_world[parent_id].inverted() @ world if parent_id is not None else world
            local.normalize()
            location = Vector((0.0, 0.0, 0.0))
            if source_id == 1000 and has_root_translation:
                delta_position = target_world[bone.name].translation - bone.matrix_local.translation
                location = root_reference + alignment.inverted() @ delta_position / max(root_scale, 0.000001)
            samples[source_id].append(AnimExportFrame((frame - begin) / fps, (local.x, local.y, local.z, local.w), tuple(location)))
    for source_id, bone in source_targets.items():
        clip.tracks.append(ConversionTrack(source_id, bone.name, samples[source_id], source_id == 1000 and has_root_translation))
    return clip
