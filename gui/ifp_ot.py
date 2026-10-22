# DemonFF - Blender scripts for working with Renderware & R*/SA-MP/open.mp formats in Blender
# 2023 - 2026 spicybung

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
import io
import json
import math
import struct
import zlib

from os import SEEK_CUR
from dataclasses import dataclass
from mathutils import Matrix, Vector, Quaternion

from ..data.bone_data import (
    DIRECT_ID_PROPERTY_NAMES,
    directIdFromBoneName,
    normalizeAnimBoneName,
)

# LCS/VCS/Manhunt2 bone names mapped to standard GTA SA/RenderWare bone names
LCS_VCS_TO_GTA_SA_BONE_MAP = {
    "jaw": "Jaw",
    "l_foot": "L Foot",
    "l_calf": "L Calf",
    "l_thigh": "L Thigh",
    "r_toe0": "R Toe0",
    "r_foot": "R Foot",
    "r_calf": "R Calf",
    "r_thigh": "R Thigh",
    "spine": "Spine",
    "pelvis": "Pelvis",
    "root": "Root",
    "pivots": "Root",         # Could be ignored/skipped, or mapped to Root
    "male_base": "Root",      # Ditto
    "scene_root": "Root",     # Ditto
    "l_finger": "L Finger",
    "l_hand": "L Hand",
    "l_forearm": "L Forearm",
    "l_upperarm": "L UpperArm",
    "bip01_l_clavicle": "L Clavicle",
    "r_finger": "R Finger",
    "r_hand": "R Hand",
    "r_forearm": "R Forearm",
    "r_upperarm": "R UpperArm",
    "bip01_r_clavicle": "R Clavicle",
    "neck": "Neck",
    "spine1": "Spine1",
    "l_toe0": "L Toe0",
    "head": "Head"
}

# Semantic Manhunt 2 humanoid names -> GTA RenderWare pedestrian names.
# The IFP itself stores numeric animation BoneIDs only; when DemonFF has a
# Manhunt humanoid semantic aliases used by the automatic GTA retarget path.
# Numeric Animation BoneIDs are mapped below, so a separate source rig is not
# required for cross-game conversion.
MH2_TO_GTA_SA_BONE_MAP = {
    "root": "Root",
    "pelvis": "Pelvis",
    "spine": "Spine",
    "spine0": "Spine",
    "spine1": "Spine1",
    "spine2": "Spine1",
    "spine3": "Spine1",
    "neck": "Neck",
    "head": "Head",
    "jaw": "Jaw",
    "l_clavicle": "Bip01 L Clavicle",
    "left_clavicle": "Bip01 L Clavicle",
    "l_shoulder": "L UpperArm",
    "left_shoulder": "L UpperArm",
    "l_upperarm": "L UpperArm",
    "left_upperarm": "L UpperArm",
    "l_elbow": "L Forearm",
    "left_elbow": "L Forearm",
    "l_forearm": "L Forearm",
    "left_forearm": "L Forearm",
    "l_wrist": "L Hand",
    "left_wrist": "L Hand",
    "l_hand": "L Hand",
    "left_hand": "L Hand",
    "l_finger": "L Finger",
    "left_finger": "L Finger",
    "r_clavicle": "Bip01 R Clavicle",
    "right_clavicle": "Bip01 R Clavicle",
    "r_shoulder": "R UpperArm",
    "right_shoulder": "R UpperArm",
    "r_upperarm": "R UpperArm",
    "right_upperarm": "R UpperArm",
    "r_elbow": "R Forearm",
    "right_elbow": "R Forearm",
    "r_forearm": "R Forearm",
    "right_forearm": "R Forearm",
    "r_wrist": "R Hand",
    "right_wrist": "R Hand",
    "r_hand": "R Hand",
    "right_hand": "R Hand",
    "r_finger": "R Finger",
    "right_finger": "R Finger",
    "l_hip": "L Thigh",
    "left_hip": "L Thigh",
    "l_thigh": "L Thigh",
    "left_thigh": "L Thigh",
    "l_knee": "L Calf",
    "left_knee": "L Calf",
    "l_calf": "L Calf",
    "left_calf": "L Calf",
    "l_ankle": "L Foot",
    "left_ankle": "L Foot",
    "l_foot": "L Foot",
    "left_foot": "L Foot",
    "l_toe": "L Toe0",
    "l_toe0": "L Toe0",
    "r_hip": "R Thigh",
    "right_hip": "R Thigh",
    "r_thigh": "R Thigh",
    "right_thigh": "R Thigh",
    "r_knee": "R Calf",
    "right_knee": "R Calf",
    "r_calf": "R Calf",
    "right_calf": "R Calf",
    "r_ankle": "R Foot",
    "right_ankle": "R Foot",
    "r_foot": "R Foot",
    "right_foot": "R Foot",
    "r_toe": "R Toe0",
    "r_toe0": "R Toe0",

    # Common character-rig aliases seen in Manhunt/Manhunt 2 tooling and
    # intermediate DCC rigs.  These are semantic aliases only; numeric MH2
    # Animation BoneIDs are still learned from the source MH armature.
    "chr_pelvis": "Pelvis",
    "chr_spine1": "Spine",
    "chr_spine2": "Spine1",
    "chr_ribcage": "Spine1",
    "chr_head": "Head",
    "chr_larmupper": "L UpperArm",
    "chr_larmforearm": "L Forearm",
    "chr_larmpalm": "L Hand",
    "chr_rarmupper": "R UpperArm",
    "chr_rarmforearm": "R Forearm",
    "chr_rarmpalm": "R Hand",
    "chr_lthigh": "L Thigh",
    "chr_lcalf": "L Calf",
    "chr_lankle": "L Foot",
    "chr_ltoe1": "L Toe0",
    "chr_rthigh": "R Thigh",
    "chr_rcalf": "R Calf",
    "chr_rankle": "R Foot",
    "chr_rtoe1": "R Toe0",
}

# Retail Manhunt humanoid Animation BoneIDs.  These are the semantic body
# channels used by the working V22 retarget path.  A native Manhunt rig still
# wins by exact BoneID; this table is only used when the selected destination
# is a GTA RenderWare/HAnim-style rig with different numeric IDs.
MH2_GTA_HUMANOID_BONES = {
    1000: ("Root", 100),
    1045: ("Pelvis", 100),
    1094: ("Spine", 100),
    1095: ("Spine1", 40),
    1096: ("Spine1", 100),
    1040: ("Neck", 100),
    1001: ("Head", 100),

    1003: ("Bip01 L Clavicle", 100),
    1039: ("L UpperArm", 100),
    1020: ("L Forearm", 100),
    1021: ("L Hand", 100),
    1004: ("L Finger", 100),
    1006: ("L Finger", 60),
    1005: ("L Finger", 50),
    1011: ("L Finger", 40),
    1008: ("L Finger", 30),
    1013: ("L Finger", 20),

    1057: ("Bip01 R Clavicle", 100),
    1093: ("R UpperArm", 100),
    1074: ("R Forearm", 100),
    1075: ("R Hand", 100),
    1058: ("R Finger", 100),
    1060: ("R Finger", 60),
    1059: ("R Finger", 50),
    1065: ("R Finger", 40),
    1062: ("R Finger", 30),
    1067: ("R Finger", 20),

    1023: ("L Thigh", 100),
    1002: ("L Calf", 100),
    1019: ("L Foot", 100),
    1024: ("L Toe0", 100),
    1077: ("R Thigh", 100),
    1056: ("R Calf", 100),
    1073: ("R Foot", 100),
    1078: ("R Toe0", 100),
}

# Accessory/attachment channels present in retail MH2 animation packs.  They
# are not GTA pedestrian body bones, so cross-game retargeting intentionally
# ignores them instead of reporting them as missing body tracks.
MH2_AUXILIARY_BONE_IDS = {
    3333, 4444, 5555, 6666,
    5001, 5002, 5003, 5004, 5005, 5006, 5007, 5008,
    5013, 5014, 5015, 5017, 5018, 5019, 5020, 5021,
}

# Kept for old call-sites which only need to recognize known Manhunt IDs.
MH2_SAFE_ID_FALLBACK = {bone_id: name for bone_id, (name, _priority) in MH2_GTA_HUMANOID_BONES.items()}


#######################################################
bl_info = {
    "name": "GTA IFP Import/Export",
    "blender": (3, 0, 0),
    "category": "Import-Export",
}
#######################################################
POSEDATA_PREFIX = 'pose.bones["%s"].'
#######################################################
def invalid_active_object(self, context):
    self.layout.label(text='You need to select the armature to import animation')
#######################################################
def set_keyframe(curves, frame, values):
    for i, c in enumerate(curves):
        c.keyframe_points.add(1)
        c.keyframe_points[-1].co = frame, values[i]
        c.keyframe_points[-1].interpolation = 'LINEAR'
#######################################################
def get_bone_direct_id(bone):
    for property_name in DIRECT_ID_PROPERTY_NAMES:
        try:
            value = bone.get(property_name)
        except (AttributeError, ReferenceError, RuntimeError):
            value = None
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue

    return directIdFromBoneName(getattr(bone, "name", ""))


def find_bone_by_id(arm_obj, bone_id):
    try:
        wanted_id = int(bone_id)
    except (TypeError, ValueError):
        return None

    for bone in arm_obj.data.bones:
        if get_bone_direct_id(bone) == wanted_id:
            return bone
    return None

#######################################################
# Helper functions for reading and writing data
def _read_exact(fd, size, what='data'):
    offset = fd.tell()
    data = fd.read(size)
    if len(data) != size:
        raise EOFError(
            f'Unexpected end of IFP while reading {what} at 0x{offset:X}: '
            f'wanted {size} bytes, got {len(data)}'
        )
    return data

def read_int16(fd, num=1, en='<'):
    res = struct.unpack('%s%dh' % (en, num), _read_exact(fd, 2 * num, 'int16'))
    return res if num > 1 else res[0]
#######################################################
def read_int32(fd, num=1, en='<'):
    res = struct.unpack('%s%di' % (en, num), _read_exact(fd, 4 * num, 'int32'))
    return res if num > 1 else res[0]
#######################################################
def read_uint16(fd, num=1, en='<'):
    res = struct.unpack('%s%dH' % (en, num), _read_exact(fd, 2 * num, 'uint16'))
    return res if num > 1 else res[0]
#######################################################
def read_uint32(fd, num=1, en='<'):
    res = struct.unpack('%s%dI' % (en, num), _read_exact(fd, 4 * num, 'uint32'))
    return res if num > 1 else res[0]
#######################################################
def read_float32(fd, num=1, en='<'):
    res = struct.unpack('%s%df' % (en, num), _read_exact(fd, 4 * num, 'float32'))
    return res if num > 1 else res[0]
#######################################################
def read_str(fd, max_len):
    if max_len < 0:
        raise ValueError(f'Negative IFP string length: {max_len}')
    if max_len > 16 * 1024 * 1024:
        raise ValueError(f'Unreasonable IFP string length: {max_len}')

    raw = _read_exact(fd, max_len, 'string')
    raw = raw.split(b'\x00', 1)[0]
    # GTA-era animation names are effectively 8-bit strings.  Using UTF-8
    # here made otherwise valid files fail on a single high-bit byte.
    return raw.decode('latin-1')
#######################################################
def write_val(fd, vals, t, en='<'):
    data = vals if hasattr(vals, '__len__') else (vals, )
    data = struct.pack('%s%d%s' % (en, len(data), t), *data)
    fd.write(data)
#######################################################
def write_uint16(fd, vals, en='<'):
    write_val(fd, vals, 'H', en)
#######################################################
def write_int32(fd, vals, en='<'):
    write_val(fd, vals, 'i', en)
#######################################################
def write_uint32(fd, vals, en='<'):
    write_val(fd, vals, 'I', en)
#######################################################
def write_float32(fd, vals, en='<'):
    write_val(fd, vals, 'f', en)
#######################################################
def write_str(fd, val, max_len):
    fd.write(val.encode())
    fd.write(b'\x00' * (max_len - len(val)))
#######################################################       
class MESSAGE_OT_missing_bones(bpy.types.Operator):
    bl_idname = "message.missing_bones"
    bl_label = "Missing Bones"

    message: bpy.props.StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=400)

    def draw(self, context):
        layout = self.layout
        for line in self.message.split('\n'):
            layout.label(text=line)
    #######################################################
    def execute(self, context):
        return {'FINISHED'}

#######################################################
def build_armature_bone_lookup(arm_obj):
    by_id = {}
    by_name = {}

    for bone in arm_obj.data.bones:
        direct_id = get_bone_direct_id(bone)
        if direct_id is not None:
            by_id.setdefault(int(direct_id), bone)

        normalized_name = normalizeAnimBoneName(bone.name)
        if normalized_name:
            by_name.setdefault(normalized_name, bone)

    return by_id, by_name


def get_ifp_bone_name_candidates(ifp_bone_name):
    raw_name = str(ifp_bone_name or "").strip()
    candidates = [raw_name]

    mapped_name = LCS_VCS_TO_GTA_SA_BONE_MAP.get(raw_name)
    if mapped_name:
        candidates.append(mapped_name)

    for leeds_name, gta_name in LCS_VCS_TO_GTA_SA_BONE_MAP.items():
        if raw_name.casefold() == gta_name.casefold():
            candidates.append(leeds_name)

    normalized_candidates = []
    seen = set()
    for candidate in candidates:
        normalized = normalizeAnimBoneName(candidate)
        if normalized and normalized not in seen:
            seen.add(normalized)
            normalized_candidates.append(normalized)

    return normalized_candidates


def resolve_ifp_track_bone_scored(ifp_bone, bone_by_id, bone_by_name):
    # Prefer explicit HAnim/bone IDs over inferred names.  Besides making
    # retargeting deterministic, this lets us resolve duplicate aliases
    # (for example Root / scene_root / pivots) before F-Curves are created.
    if getattr(ifp_bone, "use_bone_id", False):
        try:
            direct_id = int(ifp_bone.bone_id)
        except (TypeError, ValueError):
            direct_id = None
        if direct_id is not None and direct_id in bone_by_id:
            return bone_by_id[direct_id], 400

    inferred_id = directIdFromBoneName(getattr(ifp_bone, "name", ""))
    if inferred_id is not None and inferred_id in bone_by_id:
        return bone_by_id[inferred_id], 300

    candidates = get_ifp_bone_name_candidates(ifp_bone.name)
    for index, normalized_name in enumerate(candidates):
        bone = bone_by_name.get(normalized_name)
        if bone is not None:
            # First candidate is the literal normalized IFP name; aliases
            # have a lower score so they cannot displace an exact match.
            return bone, 250 if index == 0 else 200

    return None, 0


def _bone_source_names(bone):
    names = []
    for candidate in (
        getattr(bone, "name", ""),
        bone.get("bleeds_frame_name") if hasattr(bone, "get") else None,
        bone.get("frame_name") if hasattr(bone, "get") else None,
    ):
        if candidate and str(candidate) not in names:
            names.append(str(candidate))
    return names


def _mh2_name_to_gta_candidates(source_name):
    raw = str(source_name or "").strip()
    norm = normalizeAnimBoneName(raw)
    candidates = [raw]

    # DCC/source rigs sometimes retain CHR_LArmDigitXX / CHR_RArmDigitXX
    # names.  GTA pedestrian rigs generally collapse those extra fingers
    # onto the hand/finger chain, so map them deterministically instead of
    # dropping their animation tracks.
    if norm.startswith("chr_larmdigit"):
        mapped = "L Hand"
    elif norm.startswith("chr_rarmdigit"):
        mapped = "R Hand"
    else:
        mapped = MH2_TO_GTA_SA_BONE_MAP.get(norm)
    if mapped:
        candidates.insert(0, mapped)
    # GTA-style names on the MH2 source are already useful.
    direct_id = directIdFromBoneName(raw)
    if direct_id is not None:
        for candidate_name in LCS_VCS_TO_GTA_SA_BONE_MAP.values():
            if directIdFromBoneName(candidate_name) == direct_id:
                candidates.append(candidate_name)
    out = []
    seen = set()
    for candidate in candidates:
        n = normalizeAnimBoneName(candidate)
        if n and n not in seen:
            seen.add(n)
            out.append((candidate, n))
    return out


def get_manhunt_track_source_id(ifp_bone):
    if not getattr(ifp_bone, "use_bone_id", False):
        return None
    try:
        return int(ifp_bone.bone_id)
    except (TypeError, ValueError, AttributeError):
        return None


def findManhuntReferenceArmature(context, target_armature):
    best = None
    best_score = -1
    scene_objects = getattr(getattr(context, "scene", None), "objects", ())
    for obj in scene_objects:
        if obj == target_armature or getattr(obj, "type", None) != 'ARMATURE':
            continue

        score = 0
        try:
            game = str(obj.get("bleeds_model_game", "") or "").upper()
        except Exception:
            game = ""
        if game in ("MH2", "MANHUNT2", "MANHUNT_2", "MH1", "MANHUNT", "MANHUNT_1"):
            score += 1000

        try:
            for source_bone in obj.data.bones:
                source_id = get_bone_direct_id(source_bone)
                if source_id is not None and int(source_id) >= 1000:
                    score += 1
        except Exception:
            continue

        if score > best_score:
            best = obj
            best_score = score

    return best if best_score > 0 else None


def is_manhunt_auxiliary_track(ifp_bone, game_version='AUTO'):
    if not str(game_version or '').startswith('MANHUNT'):
        return False
    source_id = get_manhunt_track_source_id(ifp_bone)
    return source_id in MH2_AUXILIARY_BONE_IDS


def resolve_static_manhunt_gta_target(ifp_bone, target_by_id, target_by_name):
    source_id = get_manhunt_track_source_id(ifp_bone)
    mapping = MH2_GTA_HUMANOID_BONES.get(source_id)
    if mapping is None:
        return None

    target_name, _priority = mapping
    normalized = normalizeAnimBoneName(target_name)
    target = target_by_name.get(normalized)
    if target is not None:
        return target

    target_id = directIdFromBoneName(target_name)
    if target_id is not None:
        return target_by_id.get(int(target_id))
    return None


def resolve_ifp_track_target_scored(
    ifp_bone, target_by_id, target_by_name, source_by_id=None,
    game_version='AUTO', retarget_mode='AUTO'
):
    # Exact destination IDs/names are authoritative.  This preserves native
    # GTA->GTA and Manhunt->Manhunt imports without passing through retargeting.
    target, score = resolve_ifp_track_bone_scored(
        ifp_bone, target_by_id, target_by_name
    )
    if target is not None:
        if str(game_version).startswith('MANHUNT') and score >= 400:
            return target, score, target
        return target, score, None

    if retarget_mode == 'NATIVE':
        return None, 0, None

    game_token = str(game_version or '')
    if not game_token.startswith('MANHUNT'):
        return None, 0, None

    # Prefer a real Manhunt source-rest bone when one is already present in
    # the scene.  This is automatic and intentionally has no "MH Source" UI
    # field: the source skeleton is only an internal retarget reference.
    source = None
    source_id = get_manhunt_track_source_id(ifp_bone)
    if source_by_id is not None and source_id is not None:
        source = source_by_id.get(source_id)
    if source is not None:
        for source_name in _bone_source_names(source):
            for raw_name, normalized in _mh2_name_to_gta_candidates(source_name):
                target = target_by_name.get(normalized)
                if target is not None:
                    return target, 390, source
                target_id = directIdFromBoneName(raw_name)
                if target_id is not None and target_id in target_by_id:
                    return target_by_id[target_id], 395, source

    # Source-less cross-game fallback.  BoneIDs still determine the semantic
    # GTA target, while create_action() calibrates each track against its first
    # decoded pose instead of applying Manhunt bind orientations directly to a
    # GTA rest skeleton.
    target = resolve_static_manhunt_gta_target(
        ifp_bone, target_by_id, target_by_name
    )
    if target is not None:
        return target, 320, None

    return None, 0, source


def resolve_ifp_track_bone(ifp_bone, bone_by_id, bone_by_name):
    bone, _score = resolve_ifp_track_bone_scored(
        ifp_bone, bone_by_id, bone_by_name
    )
    return bone


def ifp_track_quality(ifp_bone, match_score):
    keyframe_type = getattr(ifp_bone, 'keyframe_type', '') or ''
    has_translation = len(keyframe_type) > 2 and keyframe_type[2] == 'T'
    has_scale = len(keyframe_type) > 3 and keyframe_type[3] == 'S'
    source_id = get_manhunt_track_source_id(ifp_bone)
    semantic_priority = 0
    if source_id in MH2_GTA_HUMANOID_BONES:
        semantic_priority = int(MH2_GTA_HUMANOID_BONES[source_id][1])
    return (
        int(match_score),
        semantic_priority,
        1 if has_translation else 0,
        1 if has_scale else 0,
        len(getattr(ifp_bone, 'keyframes', ()) or ()),
    )

def get_bone_rest_local_matrix(bone, global_matrix):
    matrix_local = bone.matrix_local.copy()
    if bone.parent is not None:
        return bone.parent.matrix_local.inverted_safe() @ matrix_local
    return global_matrix @ matrix_local


def compose_transform_matrix(location, rotation, scale):
    scale_matrix = Matrix.Identity(4)
    scale_matrix[0][0] = float(scale.x)
    scale_matrix[1][1] = float(scale.y)
    scale_matrix[2][2] = float(scale.z)
    return (
        Matrix.Translation(location)
        @ rotation.to_matrix().to_4x4()
        @ scale_matrix
    )


def normalized_quaternion(quaternion):
    result = quaternion.copy()
    if result.magnitude > 0.000001:
        result.normalize()
    else:
        result = Quaternion((1.0, 0.0, 0.0, 0.0))
    return result


def make_quaternion_continuous(rotation, previous_rotation):
    if previous_rotation is None:
        return rotation

    negated = rotation.copy()
    negated.negate()
    if rotation.dot(previous_rotation) < negated.dot(previous_rotation):
        return negated
    return rotation


def canonical_quaternion_tuple(quaternion):
    q = normalized_quaternion(quaternion)
    values = (float(q.w), float(q.x), float(q.y), float(q.z))
    for value in values:
        if abs(value) <= 1e-9:
            continue
        if value < 0.0:
            values = tuple(-component for component in values)
        break
    return values


def buildManhuntRestRotationProfile(ifp_data):
    samples_by_id = {}
    for animation in getattr(ifp_data, "animations", ()):
        for track in getattr(animation, "bones", ()):
            source_id = get_manhunt_track_source_id(track)
            if source_id not in MH2_GTA_HUMANOID_BONES:
                continue
            keyframes = getattr(track, "keyframes", None) or ()
            if not keyframes:
                continue
            values = canonical_quaternion_tuple(keyframes[0].rot)
            samples_by_id.setdefault(int(source_id), []).append(values)

    profile = {}
    for source_id, samples in samples_by_id.items():
        if not samples:
            continue

        bins = {}
        for values in samples:
            # Manhunt quaternions are 1/4096 fixed point. Three decimals keeps
            # repeated bind/reference orientations together while separating
            # genuinely posed first frames.
            key = tuple(round(component, 3) for component in values)
            bins.setdefault(key, []).append(values)
        densest = max(bins.values(), key=len)
        seed = densest[0]

        seed_q = Quaternion(seed)
        cluster = []
        for values in samples:
            sample_q = Quaternion(values)
            if abs(seed_q.dot(sample_q)) >= 0.996194698:  # <= 10 degrees
                if seed_q.dot(sample_q) < 0.0:
                    values = tuple(-component for component in values)
                cluster.append(values)
        if not cluster:
            cluster = densest

        count = float(len(cluster))
        averaged = Quaternion(tuple(sum(v[i] for v in cluster) / count for i in range(4)))
        profile[int(source_id)] = normalized_quaternion(averaged)

    return profile


def create_action(arm_obj, anim, fps, global_matrix, game_version='AUTO', retarget_mode='AUTO', source_armature=None, source_rest_profile=None):
    action = bpy.data.actions.new(anim.name)
    # Only the last imported action is assigned to the armature.  Preserve
    # the rest of an imported IFP pack across save/reload as well.
    action.use_fake_user = True
    missing_bones = set()
    bone_by_id, bone_by_name = build_armature_bone_lookup(arm_obj)
    source_by_id = None
    if source_armature is not None:
        source_by_id, _source_by_name = build_armature_bone_lookup(source_armature)

    # Resolve all tracks before creating any F-Curves.  Old DemonFF created
    # curves immediately, so two source aliases resolving to one target bone
    # triggered Blender's "F-Curve ... already exists" exception.
    selected_tracks = {}
    duplicate_target_count = 0

    for ifp_bone in anim.bones:
        if not getattr(ifp_bone, 'keyframes', None):
            continue

        bone, match_score, source_bone = resolve_ifp_track_target_scored(
            ifp_bone, bone_by_id, bone_by_name, source_by_id,
            game_version=game_version, retarget_mode=retarget_mode
        )
        if bone is None:
            if is_manhunt_auxiliary_track(ifp_bone, game_version):
                continue
            missing_bones.add(
                "%s [%s]" % (ifp_bone.name, getattr(ifp_bone, "bone_id", "?"))
            )
            continue

        quality = ifp_track_quality(ifp_bone, match_score)
        existing = selected_tracks.get(bone.name)
        if existing is not None:
            duplicate_target_count += 1
            if quality <= existing[2]:
                continue

        selected_tracks[bone.name] = (ifp_bone, bone, quality, source_bone, match_score)

    for bone_name, (ifp_bone, bone, _quality, source_bone, match_score) in selected_tracks.items():
        pose_bone = arm_obj.pose.bones.get(bone_name)
        if pose_bone is None:
            missing_bones.add(bone_name)
            continue

        pose_bone.rotation_mode = 'QUATERNION'
        group = action.groups.new(name=bone_name)
        data_path = POSEDATA_PREFIX % bone_name

        keyframe_type = str(getattr(ifp_bone, 'keyframe_type', '') or '').ljust(4, '0')[:4]
        has_rotation = keyframe_type[1] == 'R'
        has_translation = keyframe_type[2] == 'T'
        has_scale = keyframe_type[3] == 'S'

        rotation_curves = None
        if has_rotation:
            rotation_curves = [
                action.fcurves.new(
                    data_path=data_path + 'rotation_quaternion',
                    index=index,
                )
                for index in range(4)
            ]
            for curve in rotation_curves:
                curve.group = group

        location_curves = None
        if has_translation:
            location_curves = [
                action.fcurves.new(
                    data_path=data_path + 'location',
                    index=index,
                )
                for index in range(3)
            ]
            for curve in location_curves:
                curve.group = group

        scale_curves = None
        if has_scale:
            scale_curves = [
                action.fcurves.new(
                    data_path=data_path + 'scale',
                    index=index,
                )
                for index in range(3)
            ]
            for curve in scale_curves:
                curve.group = group

        rest_local = get_bone_rest_local_matrix(bone, global_matrix)
        rest_inverse = rest_local.inverted_safe()
        rest_location = rest_local.to_translation()
        rest_scale = rest_local.to_scale()

        source_rest_local = None
        source_rest_inverse = None
        retarget_axis = None
        if source_bone is not None and source_bone != bone:
            source_rest_local = get_bone_rest_local_matrix(source_bone, global_matrix)
            source_rest_inverse = source_rest_local.inverted_safe()
            source_rot = source_rest_local.to_quaternion().to_matrix().to_4x4()
            target_rot = rest_local.to_quaternion().to_matrix().to_4x4()
            # Conjugate source local deltas into the target bone's rest axes.
            retarget_axis = target_rot.inverted_safe() @ source_rot

        previous_rotation = None

        cross_game_source_less = (
            str(game_version or '').startswith('MANHUNT')
            and source_bone is None
            and int(match_score) < 400
            and get_manhunt_track_source_id(ifp_bone) in MH2_GTA_HUMANOID_BONES
        )
        source_first_inverse = None
        profiled_source_rest_inverse = None
        profiled_retarget_axis = None
        if cross_game_source_less and ifp_bone.keyframes:
            first_keyframe = ifp_bone.keyframes[0]
            first_location = (
                first_keyframe.pos.copy()
                if location_curves is not None
                else Vector((0.0, 0.0, 0.0))
            )
            first_rotation = normalized_quaternion(first_keyframe.rot)
            first_scale = (
                first_keyframe.scl.copy()
                if scale_curves is not None
                else Vector((1.0, 1.0, 1.0))
            )

            source_id = get_manhunt_track_source_id(ifp_bone)
            profiled_rotation = None
            if source_rest_profile:
                profiled_rotation = source_rest_profile.get(int(source_id))

            if profiled_rotation is not None:
                profiled_source_rest = compose_transform_matrix(
                    first_location,
                    profiled_rotation,
                    Vector((1.0, 1.0, 1.0)),
                )
                profiled_source_rest_inverse = profiled_source_rest.inverted_safe()
                source_rot = profiled_rotation.to_matrix().to_4x4()
                target_rot = rest_local.to_quaternion().to_matrix().to_4x4()
                profiled_retarget_axis = target_rot.inverted_safe() @ source_rot
            else:
                source_first_inverse = compose_transform_matrix(
                    first_location,
                    first_rotation,
                    first_scale,
                ).inverted_safe()

        for keyframe in ifp_bone.keyframes:
            frame = float(keyframe.time) * float(fps)
            target_location = (
                keyframe.pos.copy()
                if location_curves is not None
                else (source_rest_local.to_translation().copy() if source_rest_local is not None else rest_location.copy())
            )
            if has_rotation:
                target_rotation = normalized_quaternion(keyframe.rot)
            elif source_rest_local is not None:
                target_rotation = normalized_quaternion(source_rest_local.to_quaternion())
            else:
                target_rotation = normalized_quaternion(rest_local.to_quaternion())

            target_scale = (
                keyframe.scl.copy()
                if scale_curves is not None
                else (source_rest_local.to_scale().copy() if source_rest_local is not None else rest_scale.copy())
            )

            target_local = compose_transform_matrix(
                target_location,
                target_rotation,
                target_scale,
            )
            if source_rest_inverse is not None and retarget_axis is not None:
                source_basis = source_rest_inverse @ target_local
                basis_matrix = retarget_axis @ source_basis @ retarget_axis.inverted_safe()
            elif profiled_source_rest_inverse is not None and profiled_retarget_axis is not None:
                source_basis = profiled_source_rest_inverse @ target_local
                basis_matrix = profiled_retarget_axis @ source_basis @ profiled_retarget_axis.inverted_safe()
            elif source_first_inverse is not None:
                # A Manhunt local quaternion contains the source rig's static
                # bone orientation. Applying that absolute orientation through
                # a GTA rest inverse folds the character into itself.  When no
                # source rest rig is available, transfer motion relative to the
                # clip's first local pose so frame zero is the GTA bind pose and
                # subsequent frames carry only the Manhunt animation delta.
                basis_matrix = source_first_inverse @ target_local
            else:
                basis_matrix = rest_inverse @ target_local
            basis_location = basis_matrix.to_translation()
            basis_rotation = normalized_quaternion(basis_matrix.to_quaternion())
            basis_rotation = make_quaternion_continuous(
                basis_rotation,
                previous_rotation,
            )
            basis_scale = basis_matrix.to_scale()
            previous_rotation = basis_rotation.copy()

            if rotation_curves is not None:
                set_keyframe(rotation_curves, frame, basis_rotation)
            if location_curves is not None:
                set_keyframe(location_curves, frame, basis_location)
            if scale_curves is not None:
                set_keyframe(scale_curves, frame, basis_scale)

    track_metadata = {}
    for target_bone_name, (source_track, _target_bone, _quality, _source_bone, _match_score) in selected_tracks.items():
        track_metadata[str(target_bone_name)] = {
            "source_name": str(getattr(source_track, "name", "") or ""),
            "bone_id": int(getattr(source_track, "bone_id", -1)),
            "keyframe_type": str(getattr(source_track, "keyframe_type", "KR00") or "KR00"),
            "use_bone_id": bool(getattr(source_track, "use_bone_id", True)),
        }

    action["DemonFF_IFP_Retarget_Version"] = 25
    action["DemonFF_IFP_Missing_Bone_Count"] = len(missing_bones)
    action["DemonFF_IFP_Duplicate_Target_Count"] = duplicate_target_count
    action["DemonFF_IFP_Source_Reference_Used"] = bool(source_armature is not None)
    action["DemonFF_IFP_Applied_Track_Count"] = len(selected_tracks)
    action["DemonFF_IFP_Track_Metadata"] = json.dumps(track_metadata, separators=(",", ":"), sort_keys=True)
    return action, missing_bones

#######################################################
IFP_GAME_ITEMS = (
    ('AUTO', "Auto Detect", "Detect the IFP family from the file"),
    ('GTA_III', "GTA III", "Grand Theft Auto III IFP (ANPK)"),
    ('VICE_CITY', "Vice City", "Grand Theft Auto: Vice City IFP (ANPK)"),
    ('SAN_ANDREAS', "San Andreas", "Grand Theft Auto: San Andreas IFP (ANP3)"),
    ('MANHUNT_1', "Manhunt", "Manhunt IFP (ANCT / SEQU)"),
    ('MANHUNT_2', "Manhunt 2", "Manhunt 2 IFP (ANCT / SEQT; compressed files supported)"),
)

IFP_GAME_LABELS = {
    'AUTO': "Auto Detect",
    'GTA_III': "GTA III",
    'VICE_CITY': "Vice City",
    'GTA_III_VC': "GTA III / Vice City",
    'SAN_ANDREAS': "San Andreas",
    'MANHUNT_1': "Manhunt",
    'MANHUNT_2': "Manhunt 2",
}


IFP_RETARGET_ITEMS = (
    ('AUTO', "Auto Retarget", "Use native IDs when possible and automatically map Manhunt humanoid Animation BoneIDs onto GTA III/VC/SA pedestrian rigs"),
    ('GTA_HUMANOID', "GTA RenderWare Humanoid", "Map Manhunt humanoid Animation BoneIDs directly onto GTA RenderWare/HAnim pedestrian bone names"),
    ('NATIVE', "Native IDs / Names", "Only apply tracks whose source IDs or names already exist on the selected armature"),
)


def _try_zlib_decompress(blob, wbits):
    try:
        return zlib.decompress(blob, wbits)
    except (zlib.error, ValueError):
        return None


def _decode_manhunt_ifp_blob(raw):
    """Return an uncompressed ANCT stream if *raw* is a Manhunt IFP.

    Manhunt 2 distributions can wrap the ANCT stream in zlib/deflate.
    Allen/Leeao's format documentation describes the decompressed payload as
    ANCT -> BLOC -> ANPK -> NAME -> SEQT.  Different game/platform builds have
    appeared with a small prefix before the compressed stream, so this probes
    common wrapper offsets as well as standard zlib/raw-deflate streams.
    """
    if raw.startswith(b'ANCT'):
        return raw, False

    attempts = []
    # Whole-file zlib, gzip-compatible and raw-deflate streams.
    for wbits in (zlib.MAX_WBITS, zlib.MAX_WBITS | 16, -zlib.MAX_WBITS):
        attempts.append((0, wbits))

    # Some archives prefix the compressed payload with a size/header.
    for offset in (4, 8, 12, 16, 20, 24, 28, 32):
        if offset < len(raw):
            attempts.append((offset, zlib.MAX_WBITS))
            attempts.append((offset, -zlib.MAX_WBITS))

    # Also locate a valid-looking zlib CMF/FLG pair near the beginning.
    scan_limit = min(len(raw) - 1, 128)
    for offset in range(max(0, scan_limit)):
        cmf = raw[offset]
        flg = raw[offset + 1]
        if (cmf & 0x0F) == 8 and ((cmf << 8) | flg) % 31 == 0:
            attempts.append((offset, zlib.MAX_WBITS))

    seen = set()
    for offset, wbits in attempts:
        key = (offset, wbits)
        if key in seen:
            continue
        seen.add(key)
        unpacked = _try_zlib_decompress(raw[offset:], wbits)
        if unpacked and unpacked.startswith(b'ANCT'):
            return unpacked, True

    return None, False


def _detect_anct_game(blob):
    # Allen's Manhunt format uses SEQU for MH1 and SEQT for MH2.
    # Search only after decompression; these FourCCs are structural tags.
    has_seqt = b'SEQT' in blob
    has_sequ = b'SEQU' in blob
    if has_seqt and not has_sequ:
        return 'MANHUNT_2'
    if has_sequ and not has_seqt:
        return 'MANHUNT_1'
    if has_seqt:
        return 'MANHUNT_2'
    if has_sequ:
        return 'MANHUNT_1'
    return 'MANHUNT_2'


def _validate_game_magic(game_version, magic):
    expected = {
        'GTA_III': 'ANPK',
        'VICE_CITY': 'ANPK',
        'SAN_ANDREAS': 'ANP3',
        'MANHUNT_1': 'ANCT',
        'MANHUNT_2': 'ANCT',
    }
    expected_magic = expected.get(game_version)
    if expected_magic and magic != expected_magic:
        raise ValueError(
            f"{IFP_GAME_LABELS.get(game_version, game_version)} expects "
            f"{expected_magic} IFP data, but this file contains {magic or 'unknown'}"
        )


def load_ifp(filepath, game_version='AUTO'):
    requested_game = game_version or 'AUTO'

    with open(filepath, 'rb') as source_fd:
        raw = source_fd.read()

    if len(raw) < 4:
        raise ValueError('IFP file is too small')

    blob = raw
    was_compressed = False
    raw_magic = raw[:4].decode('latin-1', errors='replace')

    if raw[:4] not in (b'ANP3', b'ANPK', b'ANCT'):
        # Only Manhunt uses the compressed wrapper among the formats exposed
        # by the Game Version selector.
        if requested_game in ('AUTO', 'MANHUNT_1', 'MANHUNT_2'):
            decoded, was_compressed = _decode_manhunt_ifp_blob(raw)
            if decoded is not None:
                blob = decoded

    magic = blob[:4].decode('latin-1', errors='replace')
    if magic not in ('ANP3', 'ANPK', 'ANCT'):
        if raw_magic != magic:
            detail = f"{raw_magic!r} (decoded {magic!r})"
        else:
            detail = repr(magic)
        raise ValueError(f'Unsupported IFP file format/magic: {detail}')

    _validate_game_magic(requested_game, magic)

    if requested_game == 'AUTO':
        if magic == 'ANP3':
            detected_game = 'SAN_ANDREAS'
        elif magic == 'ANPK':
            # GTA III and Vice City share the ANPK container.  Parsing is the
            # same; use the explicit selector when the distinction matters.
            detected_game = 'GTA_III_VC'
        else:
            detected_game = _detect_anct_game(blob)
    else:
        detected_game = requested_game

    expected_sequence = None
    if detected_game == 'MANHUNT_1':
        expected_sequence = 'SEQU'
    elif detected_game == 'MANHUNT_2':
        expected_sequence = 'SEQT'

    fd = io.BytesIO(blob)
    version = read_str(fd, 4)

    if version == 'ANCT':
        data = Anct.read(fd, expected_sequence=expected_sequence)
    else:
        anim_cls = ANIM_CLASSES.get(version)
        if not anim_cls:
            raise ValueError(f'Unsupported IFP file format: {version}')
        data = anim_cls.read(fd)

    result = Ifp(version, data, detected_game)
    result.was_compressed = bool(was_compressed)
    result.source_size = len(raw)
    result.decoded_size = len(blob)
    return result
#######################################################
def reset_armature_pose_to_rest(arm_obj):
    if arm_obj is None or getattr(arm_obj, 'pose', None) is None:
        return
    for pose_bone in arm_obj.pose.bones:
        try:
            pose_bone.matrix_basis = Matrix.Identity(4)
        except Exception:
            pose_bone.location = Vector((0.0, 0.0, 0.0))
            pose_bone.rotation_mode = 'QUATERNION'
            pose_bone.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
            pose_bone.scale = Vector((1.0, 1.0, 1.0))


def activate_action_on_armature(context, arm_obj, action):
    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()
    reset_armature_pose_to_rest(arm_obj)
    arm_obj.animation_data.action = action

    if action is not None:
        try:
            start_frame = int(action.frame_range[0])
            end_frame = int(action.frame_range[1])
            context.scene.frame_start = start_frame
            context.scene.frame_end = max(start_frame, end_frame)
            context.scene.frame_set(start_frame)
        except Exception:
            pass


def apply_ifp_to_armature(context, ifp, fps, global_matrix, retarget_mode='AUTO'):
    arm_obj = context.view_layer.objects.active
    if not arm_obj or type(arm_obj.data) != bpy.types.Armature:
        context.window_manager.popup_menu(invalid_active_object, title='Error', icon='ERROR')
        return {'CANCELLED'}

    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()

    created_actions = []
    missing_bones = set()
    game_version = getattr(ifp, "game_version", "AUTO")
    source_armature = None
    source_rest_profile = None
    if str(game_version or '').startswith('MANHUNT') and retarget_mode != 'NATIVE':
        source_armature = findManhuntReferenceArmature(context, arm_obj)
        if source_armature is None:
            source_rest_profile = buildManhuntRestRotationProfile(ifp.data)

    for anim in ifp.data.animations:
        act, mb = create_action(
            arm_obj, anim, fps, global_matrix,
            game_version=game_version,
            retarget_mode=retarget_mode,
            source_armature=source_armature,
            source_rest_profile=source_rest_profile,
        )
        act.name = anim.name
        act["DemonFF_IFP_Container"] = ifp.version
        act["DemonFF_IFP_Game_Version"] = game_version
        act["DemonFF_IFP_Retarget_Mode"] = retarget_mode
        act["DemonFF_IFP_Package_Name"] = str(getattr(getattr(ifp, "data", None), "name", "") or "DemonFF")
        if source_armature is not None:
            act["DemonFF_IFP_Source_Armature"] = source_armature.name
        created_actions.append(act)
        missing_bones.update(mb)

    playable_action = None
    for action in created_actions:
        try:
            if int(action.get("DemonFF_IFP_Applied_Track_Count", 0)) > 0:
                playable_action = action
                break
        except Exception:
            pass
    if playable_action is None and created_actions:
        playable_action = created_actions[0]

    if playable_action is not None:
        activate_action_on_armature(context, arm_obj, playable_action)

    if missing_bones:
        bpy.ops.message.missing_bones(
            'INVOKE_DEFAULT',
            message='\n'.join(sorted(missing_bones)),
        )

    return {'FINISHED'}

#######################################################
def buildIfpImportLog(ifp, filepath, context, retarget_mode, result):
    lines = []
    game_version = str(getattr(ifp, "game_version", "AUTO") or "AUTO")
    game_label = IFP_GAME_LABELS.get(game_version, game_version)
    arm_obj = getattr(context.view_layer.objects, "active", None)

    lines.append("DemonFF 0.6.9 IFP Import Log")
    lines.append(f"file={filepath}")
    lines.append(f"container={getattr(ifp, 'version', 'UNKNOWN')}")
    lines.append(f"detected_game={game_label}")
    lines.append(f"retarget_mode={retarget_mode}")
    lines.append(f"compressed={bool(getattr(ifp, 'was_compressed', False))}")
    lines.append(f"source_size={int(getattr(ifp, 'source_size', 0) or 0)}")
    lines.append(f"decoded_size={int(getattr(ifp, 'decoded_size', 0) or 0)}")
    lines.append(f"target_armature={getattr(arm_obj, 'name', None)}")
    lines.append(f"result={result}")

    animations = list(getattr(getattr(ifp, "data", None), "animations", ()) or ())
    lines.append(f"animation_count={len(animations)}")

    action_by_name = {}
    for action in getattr(bpy.data, "actions", ()):
        try:
            if str(action.get("DemonFF_IFP_Game_Version", "")) == game_version:
                action_by_name.setdefault(action.name, action)
        except Exception:
            continue

    for animation_index, animation in enumerate(animations):
        bones = list(getattr(animation, "bones", ()) or ())
        action = action_by_name.get(str(getattr(animation, "name", "")))
        applied_tracks = None
        missing_bones = None
        duplicate_targets = None
        retarget_version = None
        if action is not None:
            try:
                applied_tracks = int(action.get("DemonFF_IFP_Applied_Track_Count", 0))
                missing_bones = int(action.get("DemonFF_IFP_Missing_Bone_Count", 0))
                duplicate_targets = int(action.get("DemonFF_IFP_Duplicate_Target_Count", 0))
                retarget_version = int(action.get("DemonFF_IFP_Retarget_Version", 0))
            except Exception:
                pass

        lines.append(
            "animation[{0}] name={1!r} tracks={2} applied={3} missing={4} duplicates={5} retarget_version={6}".format(
                animation_index,
                getattr(animation, "name", ""),
                len(bones),
                applied_tracks,
                missing_bones,
                duplicate_targets,
                retarget_version,
            )
        )

        for bone in bones:
            keyframes = list(getattr(bone, "keyframes", ()) or ())
            sequence_flag = getattr(bone, "sequence_flag", "")
            frame_type = getattr(bone, "frame_type", None)
            lines.append(
                "  track name={0!r} bone_id={1} type={2} sequence={3} frame_type={4} keys={5}".format(
                    getattr(bone, "name", ""),
                    getattr(bone, "bone_id", None),
                    getattr(bone, "keyframe_type", ""),
                    sequence_flag,
                    frame_type,
                    len(keyframes),
                )
            )

    return "\n".join(lines)


class IMPORT_OT_ifp(bpy.types.Operator):
    bl_idname = "import_scene.ifp"
    bl_label = "Import IFP"
    bl_description = "Import RenderWare .IFP animation data with automatic game/format detection"
    filename_ext = ".ifp"
    filter_glob: bpy.props.StringProperty(
        default="*.ifp",
        options={'HIDDEN'},
    )
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    retarget_mode: bpy.props.EnumProperty(
        name="Retarget Mode",
        description="How animation tracks are matched to the selected armature",
        items=IFP_RETARGET_ITEMS,
        default='AUTO',
    )
    print_log: bpy.props.BoolProperty(
        name="Print Log",
        description="Print detailed IFP parsing and retarget information to Blender's System Console",
        default=False,
    )
    #######################################################
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "retarget_mode", text="Retarget Mode")
        layout.prop(self, "print_log")
    #######################################################
    def execute(self, context):
        try:
            ifp = load_ifp(self.filepath, 'AUTO')
            scene_fps = context.scene.render.fps / max(context.scene.render.fps_base, 1e-8)
            result = apply_ifp_to_armature(
                context, ifp, scene_fps, Matrix.Identity(4),
                retarget_mode=self.retarget_mode,
            )

            if self.print_log:
                print()
                print(buildIfpImportLog(ifp, self.filepath, context, self.retarget_mode, result))
                print()

            if result == {'FINISHED'}:
                detected_game = getattr(ifp, "game_version", "AUTO")
                game_label = IFP_GAME_LABELS.get(detected_game, detected_game)
                compression = " (decompressed)" if getattr(ifp, "was_compressed", False) else ""
                self.report(
                    {'INFO'},
                    f"Imported {game_label} {ifp.version} IFP{compression}"
                )
            return result
        except Exception as e:
            if self.print_log:
                print()
                print("DemonFF 0.6.9 IFP Import Log")
                print(f"file={self.filepath}")
                print(f"ERROR: {e}")
                print()
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
    #######################################################
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
#######################################################
def menu_func_import(self, context):
    self.layout.operator(IMPORT_OT_ifp.bl_idname, text="DemonFF IFP(.ifp)")
#######################################################
def register():
    bpy.utils.register_class(IMPORT_OT_ifp)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(IMPORT_OT_ifp)

if __name__ == "__main__":
    register()

#######################################################
# Additional IFP reading and writing logic
@dataclass
class Keyframe:
    time: float
    pos: Vector
    rot: Quaternion
    scl: Vector
#######################################################
@dataclass
class Bone:
    name: str
    keyframe_type: str
    use_bone_id: bool
    bone_id: int
    sibling_x: int
    sibling_y: int
    keyframes: []
#######################################################
@dataclass
class Animation:
    name: str
    bones: []
#######################################################
@dataclass
class IfpData:
    name: str
    animations: []
#######################################################
class Anp3Bone(Bone):
    def get_keyframes_size(self):
        s = 16 if self.keyframe_type[2] == 'T' else 10
        return len(self.keyframes) * s

    def get_size(self):
        return 36 + self.get_keyframes_size()

    @classmethod
    def read(cls, fd):
        name = read_str(fd, 24)
        frame_type = read_uint32(fd)
        keyframes_num = read_uint32(fd)
        # Bone IDs are signed in the file.  0xFFFFFFFF (-1) is used by
        # real ANP3s and must not become the bogus ID 4294967295.
        bone_id = read_int32(fd)

        if frame_type not in (3, 4):
            raise ValueError(
                f'Unsupported ANP3 frame type {frame_type} for bone {name!r}'
            )
        if keyframes_num > 10_000_000:
            raise ValueError(
                f'Unreasonable ANP3 keyframe count {keyframes_num} for bone {name!r}'
            )

        keyframe_type = 'KRT0' if frame_type == 4 else 'KR00'
        keyframes = []
        for _ in range(keyframes_num):
            qx, qy, qz, qw = read_int16(fd, 4)
            raw_time = read_uint16(fd)
            px, py, pz = (
                read_int16(fd, 3)
                if frame_type == 4
                else (0, 0, 0)
            )
            kf = Keyframe(
                raw_time / 60.0,
                Vector((px / 4096.0, py / 4096.0, pz / 4096.0)),
                Quaternion((qw / 4096.0, qx / 4096.0, qy / 4096.0, qz / 4096.0)),
                Vector((1, 1, 1))
            )
            keyframes.append(kf)

        return cls(name, keyframe_type, True, bone_id, 0, 0, keyframes)
#######################################################
class Anp3Animation(Animation):
    @staticmethod
    def get_bone_class():
        return Anp3Bone

    def get_size(self):
        return 36 + sum(b.get_size() for b in self.bones)

    @classmethod
    def read(cls, fd):
        name = read_str(fd, 24)
        bones_num, keyframes_size, unk = read_uint32(fd, 3)
        bones = [Anp3Bone.read(fd) for _ in range(bones_num)]
        return cls(name, bones)
#######################################################
class Anp3(IfpData):
    @staticmethod
    def get_animation_class():
        return Anp3Animation

    @classmethod
    def read(cls, fd):
        size = read_uint32(fd)
        name = read_str(fd, 24)
        animations_num = read_uint32(fd)
        animations = [cls.get_animation_class().read(fd) for _ in range(animations_num)]
        return cls(name, animations)
#######################################################
class AnpkBone(Bone):
    @staticmethod
    def keyframe_stride(keyframe_type):
        keyframe_type = str(keyframe_type or '').ljust(4, '0')[:4]
        if keyframe_type[0] != 'K':
            raise ValueError(f"Invalid ANPK keyframe type {keyframe_type!r}")
        if keyframe_type[1] not in ('R', '0'):
            raise ValueError(f"Invalid ANPK rotation channel {keyframe_type!r}")
        if keyframe_type[2] not in ('T', '0'):
            raise ValueError(f"Invalid ANPK translation channel {keyframe_type!r}")
        if keyframe_type[3] not in ('S', '0'):
            raise ValueError(f"Invalid ANPK scale channel {keyframe_type!r}")

        stride = 4
        if keyframe_type[1] == 'R':
            stride += 16
        if keyframe_type[2] == 'T':
            stride += 12
        if keyframe_type[3] == 'S':
            stride += 12
        return stride

    def get_keyframes_size(self):
        return len(self.keyframes) * self.keyframe_stride(self.keyframe_type)

    def get_size(self):
        if self.use_bone_id:
            anim_len = 44
        else:
            anim_len = 48
        return self.get_keyframes_size() + anim_len + 24

    @classmethod
    def read(cls, fd):
        cpan_tag = read_str(fd, 4)
        if cpan_tag != 'CPAN':
            raise ValueError(f'Expected CPAN, got {cpan_tag!r}')
        bone_len = read_uint32(fd)
        anim_tag = read_str(fd, 4)
        if anim_tag != 'ANIM':
            raise ValueError(f'Expected ANIM, got {anim_tag!r}')
        anim_len = read_uint32(fd)
        name = read_str(fd, 28)
        keyframes_num = read_uint32(fd)
        fd.seek(8, SEEK_CUR)  # unk

        if anim_len not in (44, 48):
            raise ValueError(f'Unsupported ANPK ANIM header length: {anim_len}')

        if anim_len == 44:
            bone_id = read_int32(fd)
            sibling_x, sibling_y = 0, 0
            use_bone_id = True
        else:
            bone_id = 0
            sibling_x, sibling_y = read_int32(fd, 2)
            use_bone_id = False

        if keyframes_num:
            keyframe_type = read_str(fd, 4)
            keyframes_len = read_uint32(fd)
            expected_stride = cls.keyframe_stride(keyframe_type)
            expected_size = keyframes_num * expected_stride
            if keyframes_len < expected_size:
                raise ValueError(
                    f'ANPK keyframe block for {name!r} is too short: '
                    f'{keyframes_len} < {expected_size}'
                )

            keyframes = []
            for _ in range(keyframes_num):
                if keyframe_type[1] == 'R':
                    qx, qy, qz, qw = read_float32(fd, 4)
                    rot = Quaternion((qw, qx, qy, qz))
                    rot.conjugate()
                else:
                    rot = Quaternion((1.0, 0.0, 0.0, 0.0))

                px, py, pz = read_float32(fd, 3) if keyframe_type[2] == 'T' else (0, 0, 0)
                sx, sy, sz = read_float32(fd, 3) if keyframe_type[3] == 'S' else (1, 1, 1)
                time = read_float32(fd)

                kf = Keyframe(
                    time,
                    Vector((px, py, pz)),
                    rot,
                    Vector((sx, sy, sz)),
                )
                keyframes.append(kf)

            trailing_size = keyframes_len - expected_size
            if trailing_size > 0:
                fd.seek(trailing_size, SEEK_CUR)
        else:
            keyframe_type = 'K000'
            keyframes = []

        return cls(name, keyframe_type, use_bone_id, bone_id, sibling_x, sibling_y, keyframes)
    
#######################################################
class AnpkAnimation(Animation):
    @staticmethod
    def get_bone_class():
        return AnpkBone
    #######################################################
    def get_size(self):
        name_len = len(self.name) + 1
        name_align_len = (4 - name_len % 4) % 4
        return 32 + name_len + name_align_len + sum(b.get_size() for b in self.bones)
    #######################################################
    @classmethod
    def read(cls, fd):
        name_tag = read_str(fd, 4)
        if name_tag != 'NAME':
            raise ValueError(f'Expected NAME, got {name_tag!r}')
        name_len = read_uint32(fd)
        name = read_str(fd, name_len)
        fd.seek((4 - name_len % 4) % 4, SEEK_CUR)

        dgan_tag = read_str(fd, 4)
        if dgan_tag != 'DGAN':
            raise ValueError(f'Expected DGAN, got {dgan_tag!r}')
        animation_size = read_uint32(fd)

        info_tag = read_str(fd, 4)
        if info_tag != 'INFO':
            raise ValueError(f'Expected INFO, got {info_tag!r}')
        unk_size, bones_num = read_uint32(fd, 2)
        fd.seek(unk_size - 4, SEEK_CUR)
        bones = [AnpkBone.read(fd) for _ in range(bones_num)]
        return cls(name, bones)
    
#######################################################
class Anpk(IfpData):
    @staticmethod
    def get_animation_class():
        return AnpkAnimation

    @classmethod
    def read(cls, fd):
        size = read_uint32(fd)
        info_tag = read_str(fd, 4)
        if info_tag != 'INFO':
            raise ValueError(f'Expected INFO, got {info_tag!r}')
        info_len, animations_num = read_uint32(fd, 2)
        name = read_str(fd, info_len - 4)
        fd.seek((4 - info_len % 4) % 4, SEEK_CUR)

        animations = [cls.get_animation_class().read(fd) for _ in range(animations_num)]
        return cls(name, animations)
#######################################################    
class AnctSequenceBone(Bone):
    """Manhunt SEQU/SEQT animation track."""

    @staticmethod
    def decode_manhunt_quaternion(qx, qy, qz, qw, sequence_flag):
        if sequence_flag == 'SEQT':
            # MH2 stores Max-style XYZW values.  V22 parity first inverts the
            # source quaternion and then changes from the Max coordinate basis
            # into DemonFF/Blender's local basis (+90 degrees around X).
            rot = Quaternion((
                qw / 4096.0,
                -qx / 4096.0,
                qz / 4096.0,
                -qy / 4096.0,
            ))
        else:
            # MH1 SEQU uses the same signed 12-bit quaternion scale but does
            # not use the MH2 coordinate-basis conversion.
            rot = Quaternion((
                qw / 4096.0,
                qx / 4096.0,
                qy / 4096.0,
                qz / 4096.0,
            ))

        if rot.magnitude > 0.000001:
            rot.normalize()
        else:
            rot = Quaternion((1.0, 0.0, 0.0, 0.0))
        return rot

    @staticmethod
    def decode_manhunt_translation(tx, ty, tz, sequence_flag):
        if sequence_flag == 'SEQT':
            return Vector((
                tx / 2048.0,
                -tz / 2048.0,
                ty / 2048.0,
            ))
        return Vector((tx / 2048.0, ty / 2048.0, tz / 2048.0))

    @classmethod
    def read(cls, fd, frame_times_count=0.0, expected_sequence=None):
        sequence_offset = fd.tell()
        flag = read_str(fd, 4)
        if flag not in ('SEQU', 'SEQT'):
            raise ValueError(
                f"Expected Manhunt SEQU/SEQT at 0x{sequence_offset:X}, got {flag!r}"
            )
        if expected_sequence and flag != expected_sequence:
            game_name = "Manhunt 2" if expected_sequence == 'SEQT' else "Manhunt"
            raise ValueError(
                f"{game_name} was selected, but animation contains {flag} tracks"
            )

        bone_id = read_int16(fd)
        frame_type = struct.unpack('<B', _read_exact(fd, 1, 'Manhunt frame type'))[0]
        frame_count = read_uint16(fd)

        if frame_type not in (1, 2, 3):
            raise ValueError(
                f"Unsupported Manhunt frame type {frame_type} for BoneID {bone_id}"
            )
        if frame_count > 1_000_000:
            raise ValueError(
                f"Unreasonable Manhunt frame count {frame_count} for BoneID {bone_id}"
            )

        start_time_offset = fd.tell()
        start_time = read_int16(fd)

        # For KR00/KRT0 tracks StartTime==0 means those two bytes are the first
        # variable delta, not a stored StartTime field.
        if frame_type < 3 and start_time == 0:
            fd.seek(start_time_offset)
            start_time = 0

        # FrameType 3 stores one constant rotation in the header, followed by
        # per-frame translation.  Treating these four words as translation was
        # the regression that destroyed the MH2 root orientation.
        frame3_rotation = Quaternion((1.0, 0.0, 0.0, 0.0))
        if frame_type == 3:
            qx, qy, qz, qw = read_int16(fd, 4)
            frame3_rotation = cls.decode_manhunt_quaternion(
                qx, qy, qz, qw, flag
            )

        keyframes = []
        time_accum_ticks = 0

        for frame_index in range(frame_count):
            if start_time == 0:
                # FrameType 3 keeps its constant quaternion in the track
                # header.  For its first sample there is no delta-time word:
                # the sample starts at t=0 and translation follows
                # immediately.  Consuming a uint16 here shifts the stream by
                # two bytes and eventually makes the next SEQU/SEQT FourCC
                # appear as "QU..".  This occurs in retail Manhunt IFPs.
                if frame_type == 3 and frame_index == 0:
                    time = 0.0
                else:
                    delta_ticks = read_uint16(fd)
                    time_accum_ticks += delta_ticks
                    time = time_accum_ticks / 2048.0
            else:
                # Retail MH2 parity: the first stored sample is one 30 Hz step
                # before StartTime/2048.  Bone 1000 in ALLANIMS therefore begins
                # at -0.0001302083 s when StartTime is 68.
                time = start_time / 2048.0 + (frame_index - 1) / 30.0

            if frame_type < 3:
                qx, qy, qz, qw = read_int16(fd, 4)
                rot = cls.decode_manhunt_quaternion(qx, qy, qz, qw, flag)
            else:
                rot = frame3_rotation.copy()

            if frame_type > 1:
                tx, ty, tz = read_int16(fd, 3)
                pos = cls.decode_manhunt_translation(tx, ty, tz, flag)
            else:
                pos = Vector((0.0, 0.0, 0.0))

            keyframes.append(
                Keyframe(time, pos, rot, Vector((1.0, 1.0, 1.0)))
            )

        last_frame_time = None
        if flag == 'SEQT':
            last_frame_time = read_float32(fd)

        keyframe_type = 'KR00' if frame_type == 1 else 'KRT0'
        track = cls(
            name=f"Bone_{bone_id}",
            keyframe_type=keyframe_type,
            use_bone_id=True,
            bone_id=bone_id,
            sibling_x=0,
            sibling_y=0,
            keyframes=keyframes,
        )
        track.sequence_flag = flag
        track.frame_type = frame_type
        track.frame_times_count = float(frame_times_count)
        track.start_time = int(start_time)
        track.frame3_rotation = frame3_rotation.copy()
        track.last_frame_time = last_frame_time
        return track


#######################################################
class AnctAnimation(Animation):
    @classmethod
    def read(cls, fd, block_name="", expected_sequence=None):
        name_offset = fd.tell()
        name_tag = read_str(fd, 4)
        if name_tag != 'NAME':
            raise ValueError(
                f"Expected Manhunt NAME at 0x{name_offset:X}, got {name_tag!r}"
            )

        name_len = read_uint32(fd)
        if name_len > 1024 * 1024:
            raise ValueError(f"Unreasonable Manhunt animation-name length: {name_len}")
        name = read_str(fd, name_len)

        bones_num = read_uint32(fd)
        chunk_size = read_uint32(fd)
        frame_times_count = read_float32(fd)

        if bones_num > 100_000:
            raise ValueError(
                f"Unreasonable Manhunt bone-track count {bones_num} in {name!r}"
            )

        tracks_start = fd.tell()
        bones = [
            AnctSequenceBone.read(
                fd,
                frame_times_count=frame_times_count,
                expected_sequence=expected_sequence,
            )
            for _ in range(bones_num)
        ]
        tracks_end = fd.tell()

        # Allen's ChunkSize counts only per-track payload bytes; it excludes
        # each 9-byte SEQU/SEQT header and, for MH2 SEQT, the trailing
        # 4-byte float.  Retail ALLANIMS.IFP matches this exactly.  Keep the
        # measured values so malformed/desynchronised files are diagnosable
        # without rejecting legitimate platform variants outright.
        structural_bytes = 0
        for track in bones:
            structural_bytes += 9
            if getattr(track, "sequence_flag", "") == "SEQT":
                structural_bytes += 4
        measured_payload_size = (tracks_end - tracks_start) - structural_bytes
        chunk_size_matches = int(chunk_size) == int(measured_payload_size)

        # Particle/effect command table follows every animation.
        particle_header_offset = fd.tell()
        header_size = read_uint32(fd)
        particle_unknown = read_float32(fd)
        each_entry_size = read_uint32(fd)
        num_entries = read_uint32(fd)

        if num_entries > 1_000_000:
            raise ValueError(
                f"Unreasonable Manhunt particle-entry count {num_entries} in {name!r}"
            )
        particle_bytes = each_entry_size * num_entries
        if particle_bytes > 512 * 1024 * 1024:
            raise ValueError(
                f"Unreasonable Manhunt particle block size {particle_bytes} in {name!r}"
            )
        if particle_bytes:
            _read_exact(fd, particle_bytes, 'Manhunt particle/effect entries')

        anim = cls(name, bones)
        anim.source_block = block_name
        anim.frame_times_count = frame_times_count
        anim.chunk_size = chunk_size
        anim.sequence_bytes = tracks_end - tracks_start
        anim.sequence_payload_bytes = measured_payload_size
        anim.chunk_size_matches = bool(chunk_size_matches)
        anim.particle_header_size = header_size
        anim.particle_unknown = particle_unknown
        anim.particle_entry_size = each_entry_size
        anim.particle_entry_count = num_entries
        anim.particle_header_offset = particle_header_offset
        return anim


#######################################################
class AnctBlock:
    @classmethod
    def read(cls, fd, expected_sequence=None):
        block_offset = fd.tell()
        tag = read_str(fd, 4)
        if tag != 'BLOC':
            raise ValueError(
                f"Expected Manhunt BLOC at 0x{block_offset:X}, got {tag!r}"
            )

        block_name_len = read_uint32(fd)
        if block_name_len > 1024 * 1024:
            raise ValueError(f"Unreasonable Manhunt block-name length: {block_name_len}")
        block_name = read_str(fd, block_name_len)

        anpk_offset = fd.tell()
        anpk_tag = read_str(fd, 4)
        if anpk_tag != 'ANPK':
            raise ValueError(
                f"Expected Manhunt ANPK at 0x{anpk_offset:X}, got {anpk_tag!r}"
            )

        animation_count = read_uint32(fd)
        if animation_count > 1_000_000:
            raise ValueError(
                f"Unreasonable Manhunt animation count {animation_count} "
                f"in block {block_name!r}"
            )

        animations = [
            AnctAnimation.read(
                fd,
                block_name=block_name,
                expected_sequence=expected_sequence,
            )
            for _ in range(animation_count)
        ]

        block = cls()
        block.name = block_name
        block.animations = animations
        return block


#######################################################
class Anct(IfpData):
    @classmethod
    def read(cls, fd, expected_sequence=None):
        # load_ifp() has already consumed the top-level ANCT FourCC.
        num_blocks = read_uint32(fd)
        if num_blocks > 100_000:
            raise ValueError(f"Unreasonable Manhunt BLOC count: {num_blocks}")

        blocks = [
            AnctBlock.read(fd, expected_sequence=expected_sequence)
            for _ in range(num_blocks)
        ]

        animations = []
        for block in blocks:
            animations.extend(block.animations)

        data = cls("Manhunt", animations)
        data.blocks = blocks
        data.block_count = num_blocks
        return data


#######################################################
ANIM_CLASSES = {
    'ANP3': Anp3,
    'ANPK': Anpk,
    'ANCT': Anct, 
}

#######################################################
@dataclass
class Ifp:
    version: str
    data: object
    game_version: str = 'AUTO'

    @classmethod
    def read(cls, fd):
        version = read_str(fd, 4)

        anim_cls = ANIM_CLASSES.get(version)
        if not anim_cls:
            raise Exception('Unknown IFP version')

        data = anim_cls.read(fd)
        detected_game = (
            'SAN_ANDREAS' if version == 'ANP3'
            else 'GTA_III_VC' if version == 'ANPK'
            else 'AUTO'
        )
        return cls(version, data, detected_game)

    def write(self, fd):
        write_str(fd, self.version, 4)
        self.data.write(fd)
        fd.write(b'\x00' * (2048 - (fd.tell() % 2048)))

    @classmethod
    def load(cls, filepath, game_version='AUTO'):
        # Route through the same multi-game loader used by the Blender
        # operator so compressed Manhunt 2 streams and explicit game
        # validation behave consistently for programmatic callers too.
        return load_ifp(filepath, game_version)

    def save(self, filepath):
        with open(filepath, 'wb') as fd:
            return self.write(fd)
#######################################################
def clampInt16(value):
    return max(-32768, min(32767, int(round(float(value)))))


def encodeIfpName(value, size=24):
    raw = str(value or '').encode('ascii', errors='replace')[:int(size)]
    return raw.ljust(int(size), b'\x00')


def export_anp3(ifp_data, fd):
    fd.write(b'ANP3')
    size_placeholder = fd.tell()
    fd.write(struct.pack('<I', 0))

    internal_name = encodeIfpName(ifp_data.name, 24)
    fd.write(internal_name)
    fd.write(struct.pack('<I', len(ifp_data.animations)))

    for anim in ifp_data.animations:
        anim_name = encodeIfpName(anim.name, 24)
        fd.write(anim_name)
        fd.write(struct.pack('<I', len(anim.bones)))

        keyframe_bytes_pos = fd.tell()
        fd.write(struct.pack('<I', 0))
        fd.write(struct.pack('<I', 1))

        keyframe_payload_size = 0
        for bone in anim.bones:
            bone_name = encodeIfpName(bone.name, 24)
            has_translation = len(bone.keyframe_type) > 2 and bone.keyframe_type[2] == 'T'
            frame_type = 4 if has_translation else 3
            fd.write(bone_name)
            fd.write(struct.pack('<IIi', frame_type, len(bone.keyframes), int(bone.bone_id)))

            frame_stride = 16 if has_translation else 10
            keyframe_payload_size += len(bone.keyframes) * frame_stride

            for frame in bone.keyframes:
                quat = normalized_quaternion(frame.rot)
                time = max(0, min(65535, int(round(float(frame.time) * 60.0))))

                fd.write(struct.pack(
                    '<hhhhH',
                    clampInt16(quat.x * 4096.0),
                    clampInt16(quat.y * 4096.0),
                    clampInt16(quat.z * 4096.0),
                    clampInt16(quat.w * 4096.0),
                    time,
                ))

                if has_translation:
                    fd.write(struct.pack(
                        '<hhh',
                        clampInt16(frame.pos.x * 4096.0),
                        clampInt16(frame.pos.y * 4096.0),
                        clampInt16(frame.pos.z * 4096.0),
                    ))

        current_pos = fd.tell()
        fd.seek(keyframe_bytes_pos)
        fd.write(struct.pack('<I', keyframe_payload_size))
        fd.seek(current_pos)

    logical_end = fd.tell()
    fd.seek(size_placeholder)
    fd.write(struct.pack('<I', max(0, logical_end - 8)))
    fd.seek(logical_end)

    padding = (-logical_end) % 2048
    if padding:
        fd.write(b'\x00' * padding)

#######################################################
def getExportBoneId(pose_bone):
    owners = (pose_bone, getattr(pose_bone, "bone", None))
    for owner in owners:
        if owner is None:
            continue
        for property_name in DIRECT_ID_PROPERTY_NAMES:
            try:
                if property_name in owner:
                    return int(owner[property_name])
            except Exception:
                continue
    fallback = directIdFromBoneName(getattr(pose_bone, "name", ""))
    return int(fallback) if fallback is not None else -1


def actionBoneFrames(action, bone_name):
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


def collect_animation_data(context):
    arm_obj = context.object
    if arm_obj is None or getattr(arm_obj, "type", None) != 'ARMATURE':
        raise ValueError("Select an armature with an active Action")
    if arm_obj.animation_data is None or arm_obj.animation_data.action is None:
        raise ValueError("Selected armature has no active Action")

    action = arm_obj.animation_data.action
    fps = context.scene.render.fps / max(context.scene.render.fps_base, 1e-8)
    old_frame = context.scene.frame_current

    source_track_metadata = {}
    try:
        source_container = str(action.get("DemonFF_IFP_Container", "") or "").upper()
        if source_container in ("ANP3", "ANPK"):
            source_track_metadata = json.loads(str(action.get("DemonFF_IFP_Track_Metadata", "") or "{}"))
            if not isinstance(source_track_metadata, dict):
                source_track_metadata = {}
    except Exception:
        source_track_metadata = {}
    old_subframe = getattr(context.scene, "frame_subframe", 0.0)
    bones = []

    try:
        for pose_bone in arm_obj.pose.bones:
            frames, has_location, _has_scale = actionBoneFrames(action, pose_bone.name)
            if not frames:
                continue

            source_metadata = source_track_metadata.get(str(pose_bone.name), {})
            direct_id = getExportBoneId(pose_bone)
            if source_metadata and bool(source_metadata.get("use_bone_id", True)):
                try:
                    direct_id = int(source_metadata.get("bone_id", direct_id))
                except Exception:
                    pass
            source_bone_name = str(source_metadata.get("source_name", "") or pose_bone.name)

            rest_local = get_bone_rest_local_matrix(pose_bone.bone, Matrix.Identity(4))
            keyframes = []
            first_frame = float(frames[0])
            for frame_number in frames:
                whole = math.floor(float(frame_number))
                subframe = float(frame_number) - float(whole)
                try:
                    context.scene.frame_set(whole, subframe=subframe)
                except TypeError:
                    context.scene.frame_set(whole)

                matrix_basis = pose_bone.matrix_basis.copy()
                game_local = rest_local @ matrix_basis
                rotation = game_local.to_quaternion().normalized()
                location = game_local.to_translation()
                scale = game_local.to_scale()
                time = max(0.0, (float(frame_number) - first_frame) / max(fps, 1e-8))
                keyframes.append(
                    Keyframe(
                        time=time,
                        pos=location.copy(),
                        rot=rotation.copy(),
                        scl=scale.copy(),
                    )
                )

            bone = Bone(
                name=source_bone_name,
                keyframe_type='KRT0' if has_location else 'KR00',
                use_bone_id=True,
                bone_id=direct_id,
                sibling_x=0,
                sibling_y=0,
                keyframes=keyframes,
            )
            bones.append(bone)
    finally:
        try:
            context.scene.frame_set(int(old_frame), subframe=float(old_subframe))
        except TypeError:
            context.scene.frame_set(int(old_frame))

    if not bones:
        raise ValueError("Active Action contains no pose-bone keyframes")

    package_name = "DemonFF"
    try:
        stored_package_name = str(action.get("DemonFF_IFP_Package_Name", "") or "").strip()
        if stored_package_name:
            package_name = stored_package_name
    except Exception:
        pass

    return IfpData(name=package_name, animations=[Animation(name=action.name, bones=bones)])


class EXPORT_OT_ifp(bpy.types.Operator):
    bl_idname = "export_scene.ifp"
    bl_label = "Export IFP (.ifp)"
    filename_ext = ".ifp"
    filter_glob: bpy.props.StringProperty(default="*.ifp", options={'HIDDEN'})
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        try:
            ifp_data = collect_animation_data(context)
            with open(self.filepath, 'wb') as fd:
                export_anp3(ifp_data, fd)
            self.report({'INFO'}, f"IFP file exported: {self.filepath}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


def export_menu_func(self, context):
    self.layout.operator(EXPORT_OT_ifp.bl_idname, text="DemonFF Export IFP (.ifp)")


