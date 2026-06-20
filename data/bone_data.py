# DemonFF - Scripts for working with R* Leeds (GTA Stories, Chinatown Wars, Manhunt 2, etc) formats in Blender
# Author: spicybung
# Years: 2025 - 2026

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

from typing import List, Dict, Tuple

#######################################################
# These are interesting... it seems AK73 was working on Stories animation rigging
# === LCS Bone Arrays ===

commonBoneOrder: Tuple[str, ...] = (
    "Root", "Pelvis", "Spine", "Spine1", "Neck", "Head",
    "Bip01 L Clavicle", "L UpperArm", "L Forearm", "L Hand", "L Finger", "Bip01 R Clavicle",
    "R UpperArm", "R Forearm", "R Hand", "R Finger", "L Thigh", "L Calf",
    "L Foot", "L Toe0", "R Thigh", "R Calf", "R Foot", "R Toe0"
)

commonBoneNamesLCS: Tuple[str, ...] = commonBoneOrder

kamBoneID: Tuple[int, ...] = (
    0, 1, 2, 3, 4, 5, 31, 32, 33, 34, 35, 21, 22, 23, 24, 25, 41, 42, 43, 2000, 51, 52, 53, 2001
)

kamFrameName: Tuple[str, ...] = (
    "Root", "Pelvis", "Spine", "Spine1", "Neck", "Head",
    "Bip01~L~Clavicle", "L~UpperArm", "L~Forearm", "L~Hand", "L~Finger", "Bip01~R~Clavicle",
    "R~UpperArm", "R~Forearm", "R~Hand", "R~Finger", "L~Thigh", "L~Calf",
    "L~Foot", "L~Toe0", "R~Thigh", "R~Calf", "R~Foot", "R~Toe0"
)

kamBoneType: Tuple[int, ...] = (
    0, 0, 0, 2, 0, 3, 2, 0, 0, 0, 1, 0, 0, 0, 0, 1, 2, 0, 0, 1, 0, 0, 0, 1
)

kamBoneIndex: Tuple[str, ...] = (
    "00", "01", "02", "03", "04", "05", "06", "07", "08", "09",
    "10", "11", "12", "13", "14", "15", "16", "17", "18", "19",
    "20", "21", "22", "23"
)

commonBoneParentsLCS: Dict[str, str] = {
    "Pelvis": "Root",
    "Spine": "Pelvis",
    "Spine1": "Spine",
    "Neck": "Spine1",
    "Head": "Neck",
    "Bip01 L Clavicle": "Spine1",
    "L UpperArm": "Bip01 L Clavicle",
    "L Forearm": "L UpperArm",
    "L Hand": "L Forearm",
    "L Finger": "L Hand",
    "Bip01 R Clavicle": "Spine1",
    "R UpperArm": "Bip01 R Clavicle",
    "R Forearm": "R UpperArm",
    "R Hand": "R Forearm",
    "R Finger": "R Hand",
    "L Thigh": "Pelvis",
    "L Calf": "L Thigh",
    "L Foot": "L Calf",
    "L Toe0": "L Foot",
    "R Thigh": "Pelvis",
    "R Calf": "R Thigh",
    "R Foot": "R Calf",
    "R Toe0": "R Foot",
}

commonBoneOrderVCS: Tuple[str, ...] = (
    "root", "pelvis", "spine", "spine1", "neck", "head",
    "jaw", "bip01_l_clavicle", "l_upperarm", "l_forearm", "l_hand", "l_finger",
    "bip01_r_clavicle", "r_upperarm", "r_forearm", "r_hand", "r_finger", "l_thigh",
    "l_calf", "l_foot", "l_toe0", "r_thigh", "r_calf", "r_foot", "r_toe0"
)

commonBoneNamesVCS: Tuple[str, ...] = (
    "root", "pelvis", "spine", "spine1", "neck", "head",
    "jaw", "bip01_l_clavicle", "l_upperarm", "l_forearm", "l_hand", "l_finger",
    "bip01_r_clavicle", "r_upperarm", "r_forearm", "r_hand", "r_finger", "l_thigh",
    "l_calf", "l_foot", "l_toe0", "r_thigh", "r_calf", "r_foot", "r_toe0"
)

kamBoneIDVCS: Tuple[int, ...] = (
    0, 1, 2, 3, 4, 5,
    8, 31, 32, 33, 34, 35,
    21, 22, 23, 24, 25, 41,
    42, 43, 2000, 51, 52, 53,
    2001
)

kamFrameNameVCS: Tuple[str, ...] = (
    "root", "pelvis", "spine", "spine1", "neck", "head",
    "jaw", "bip01_l_clavicle", "l_upperarm", "l_forearm", "l_hand", "l_finger",
    "bip01_r_clavicle", "r_upperarm", "r_forearm", "r_hand", "r_finger", "l_thigh",
    "l_calf", "l_foot", "l_toe0", "r_thigh", "r_calf", "r_foot", "r_toe0"
)

kamBoneTypeVCS: Tuple[int, ...] = (
    0, 0, 0, 2, 0, 2,
    3, 2, 0, 0, 0, 1,
    0, 0, 0, 0, 1, 2,
    0, 0, 1, 0, 0, 0,
    1
)

kamBoneIndexVCS: Tuple[str, ...] = (
    "00", "01", "02", "03", "04", "05", "06", "07",
    "08", "09", "10", "11", "12", "13", "14", "15",
    "16", "17", "18", "19", "20", "21", "22", "23"
)

commonBoneParentsVCS: Dict[str, str] = {
    "pelvis": "root",
    "spine": "pelvis",
    "spine1": "spine",
    "neck": "spine1",
    "head": "neck",
    "jaw": "head",
    "bip01_l_clavicle": "spine1",
    "l_upperarm": "bip01_l_clavicle",
    "l_forearm": "l_upperarm",
    "l_hand": "l_forearm",
    "l_finger": "l_hand",
    "bip01_r_clavicle": "spine1",
    "r_upperarm": "bip01_r_clavicle",
    "r_forearm": "r_upperarm",
    "r_hand": "r_forearm",
    "r_finger": "r_hand",
    "l_thigh": "pelvis",
    "l_calf": "l_thigh",
    "l_foot": "l_calf",
    "l_toe0": "l_foot",
    "r_thigh": "pelvis",
    "r_calf": "r_thigh",
    "r_foot": "r_calf",
    "r_toe0": "r_foot",
}

DIRECT_ID_PROPERTY_NAMES: Tuple[str, ...] = (
    "bleeds_anim_bone_id",
    "bleeds_mdl_anim_bone_id",
    "bleeds_ped_anim_bone_id",
    "bleeds_hanim_bone_id",
    "BoneID",
    "bone_id",
    "bleeds_bone_id",
    "bleeds_boneid",
    "leeds_anim_bone_id",
    "anim_bone_id",
)

BONE_KEY_PROPERTY_NAMES: Tuple[str, ...] = (
    "bleeds_anim_bone_key",
    "bleeds_mdl_anim_bone_key",
    "leeds_anim_bone_key",
    "anim_bone_key",
)

HASH16_PROPERTY_NAMES: Tuple[str, ...] = (
    "bleeds_anim_hash16",
    "bleeds_mdl_anim_hash16",
    "leeds_anim_hash16",
    "anim_hash16",
)

TABLE_INDEX_PROPERTY_NAMES: Tuple[str, ...] = (
    "bleeds_anim_table_index",
    "anim_table_index",
    "bleeds_mdl_hierarchy_node_index",
    "node_index",
)

PED_ANIM_HASH16_TO_DIRECT_ID: Dict[int, int] = {
    0xDF9E: 0,
    0xB88A: 1,
    0x9A64: 2,
    0xBCFC: 3,
    0xE97B: 4,
    0x6E99: 5,
    0x8935: 21,
    0x1157: 22,
    0x7A50: 23,
    0xFE09: 24,
    0xC8F4: 25,
    0x5E16: 25,
    0xB052: 31,
    0x2830: 32,
    0x1E52: 33,
    0xC7D5: 34,
    0xA1C5: 35,
    0x3A14: 35,
    0xCDD3: 41,
    0xCCEC: 42,
    0x2938: 43,
    0xFA32: 51,
    0xF530: 52,
    0x10E4: 53,
}

DIRECT_ID_NAME_HINTS: Dict[int, Tuple[str, ...]] = {
    0: ("root", "scene_root", "Root", "ROOT", "ped_root", "ped root"),
    1: ("pelvis", "Pelvis", "male_base", "female_base", "base", "Bip01 Pelvis", "bip01 pelvis"),
    2: ("spine", "Spine", "spine0", "Bip01 Spine", "bip01 spine"),
    3: ("spine1", "Spine1", "spine_1", "Bip01 Spine1", "bip01 spine1"),
    4: ("neck", "Neck", "Bip01 Neck", "bip01 neck"),
    5: ("head", "Head", "Bip01 Head", "bip01 head"),
    21: ("bip01_r_clavicle", "bip01 r clavicle", "r_clavicle", "right_clavicle", "clavicle_r", "RightClavicle", "right clavicle"),
    22: ("r_upperarm", "right_upperarm", "upperarm_r", "RightUpperArm", "Bip01 R UpperArm", "bip01 r upperarm", "right upperarm", "right upper arm"),
    23: ("r_forearm", "right_forearm", "forearm_r", "lowerarm_r", "RightForeArm", "Bip01 R Forearm", "bip01 r forearm", "right forearm", "right lowerarm"),
    24: ("r_hand", "right_hand", "hand_r", "RightHand", "Bip01 R Hand", "bip01 r hand", "right hand"),
    25: ("r_finger", "right_finger", "finger_r", "RightFinger", "Bip01 R Finger", "bip01 r finger", "right finger"),
    31: ("bip01_l_clavicle", "bip01 l clavicle", "l_clavicle", "left_clavicle", "clavicle_l", "LeftClavicle", "left clavicle"),
    32: ("l_upperarm", "left_upperarm", "upperarm_l", "LeftUpperArm", "Bip01 L UpperArm", "bip01 l upperarm", "left upperarm", "left upper arm"),
    33: ("l_forearm", "left_forearm", "forearm_l", "lowerarm_l", "LeftForeArm", "Bip01 L Forearm", "bip01 l forearm", "left forearm", "left lowerarm"),
    34: ("l_hand", "left_hand", "hand_l", "LeftHand", "Bip01 L Hand", "bip01 l hand", "left hand"),
    35: ("l_finger", "left_finger", "finger_l", "LeftFinger", "Bip01 L Finger", "bip01 l finger", "left finger"),
    41: ("l_thigh", "left_thigh", "thigh_l", "LeftThigh", "Bip01 L Thigh", "bip01 l thigh", "left thigh"),
    42: ("l_calf", "left_calf", "calf_l", "shin_l", "LeftCalf", "Bip01 L Calf", "bip01 l calf", "left calf", "left shin"),
    43: ("l_foot", "left_foot", "foot_l", "LeftFoot", "Bip01 L Foot", "bip01 l foot", "left foot"),
    51: ("r_thigh", "right_thigh", "thigh_r", "RightThigh", "Bip01 R Thigh", "bip01 r thigh", "right thigh"),
    52: ("r_calf", "right_calf", "calf_r", "shin_r", "RightCalf", "Bip01 R Calf", "bip01 r calf", "right calf", "right shin"),
    53: ("r_foot", "right_foot", "foot_r", "RightFoot", "Bip01 R Foot", "bip01 r foot", "right foot"),
    255: ("jaw", "Jaw", "Bip01 Jaw", "bip01 jaw"),
}

def normalizeAnimBoneName(name: str) -> str:
    text = str(name or "").strip().lower()
    if not text:
        return ""
    for old, new_value in ((".", "_"), ("-", "_"), (" ", "_")):
        text = text.replace(old, new_value)
    while "__" in text:
        text = text.replace("__", "_")
    if text.startswith("bip01_"):
        text = text[6:]
    text = text.replace("right_", "r_").replace("left_", "l_")
    text = text.replace("upper_arm", "upperarm").replace("lower_arm", "forearm")
    text = text.replace("lowerarm", "forearm")
    text = text.replace("shin", "calf")
    return text.strip("_")

def buildNormalizedNameToDirectId() -> Dict[str, int]:
    out: Dict[str, int] = {}
    for direct_id, names in DIRECT_ID_NAME_HINTS.items():
        for raw_name in names:
            norm = normalizeAnimBoneName(raw_name)
            if norm:
                out.setdefault(norm, int(direct_id))
    return out

NORMALIZED_NAME_TO_DIRECT_ID: Dict[str, int] = buildNormalizedNameToDirectId()

def directIdFromBoneName(name: str):
    norm = normalizeAnimBoneName(name)
    if not norm:
        return None
    if norm in NORMALIZED_NAME_TO_DIRECT_ID:
        return int(NORMALIZED_NAME_TO_DIRECT_ID[norm])
    if norm.startswith("bip01_") and norm[6:] in NORMALIZED_NAME_TO_DIRECT_ID:
        return int(NORMALIZED_NAME_TO_DIRECT_ID[norm[6:]])
    return None

def getCommonBoneNames(game: str = "VCS") -> Tuple[str, ...]:
    token = str(game or "VCS").strip().upper()
    if token == "LCS":
        return commonBoneNamesLCS
    return commonBoneNamesVCS

def getCommonBoneParents(game: str = "VCS") -> Dict[str, str]:
    token = str(game or "VCS").strip().upper()
    if token == "LCS":
        return dict(commonBoneParentsLCS)
    return dict(commonBoneParentsVCS)
