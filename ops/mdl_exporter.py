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

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import bpy
import bmesh
import math
import struct
from mathutils import Vector, Matrix

from ..gtaLib import mdl as mdl_lib
from .mdl_blender_api import ensureMeshAttribute, getMeshAttribute, removeMeshAttribute

def natural_sort_key(name: str) -> List[object]:

    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]

def find_mdl_root_from_object(obj: bpy.types.Object) -> Optional[bpy.types.Object]:
    cur = obj
    while cur is not None:
        if getattr(cur, "bleeds_is_mdl_root", False):
            return cur
        if cur.type == "EMPTY" and cur.name.upper().endswith("_ROOT"):
            return cur
        cur = cur.parent
    return None

def find_mdl_root(context: bpy.types.Context) -> bpy.types.Object:

    candidates: List[bpy.types.Object] = []
    if context.active_object is not None:
        candidates.append(context.active_object)
    candidates.extend([o for o in context.selected_objects if o not in candidates])

    for obj in candidates:
        root = find_mdl_root_from_object(obj)
        if root is not None:
            return root

    raise RuntimeError(
        "Couldn't find an MDL ROOT. Select the imported ROOT empty (bleeds_is_mdl_root) "
        "or select any child mesh under it."
    )

def gather_mesh_parts(context: bpy.types.Context, root: bpy.types.Object) -> List[bpy.types.Object]:

    selected_under_root: List[bpy.types.Object] = []
    for obj in context.selected_objects:
        if obj.type != "MESH":
            continue
        cur = obj
        while cur is not None:
            if cur == root:
                selected_under_root.append(obj)
                break
            cur = cur.parent

    exporting_selected_subset = bool(selected_under_root)
    if exporting_selected_subset:
        meshes = selected_under_root
    else:
        meshes = [o for o in root.children_recursive if o.type == "MESH"]

    if not exporting_selected_subset:
        indexed_meshes: List[Tuple[int, bpy.types.Object]] = []
        all_have_part_index = True
        for mesh_obj in meshes:
            try:
                part_index = read_idprop(mesh_obj, "bleeds_mdl_part_index", None)
                if part_index is None:
                    all_have_part_index = False
                    break
                indexed_meshes.append((int(part_index), mesh_obj))
            except Exception:
                all_have_part_index = False
                break

        if all_have_part_index and indexed_meshes:
            indexed_meshes.sort(key=lambda item: (int(item[0]), natural_sort_key(item[1].name)))
            return [mesh_obj for _, mesh_obj in indexed_meshes]

    meshes.sort(key=lambda o: natural_sort_key(o.name))
    return meshes

def resolve_texture_name(mat) -> str:
    if mat is None:
        return "default"

    if hasattr(mat, "use_nodes") and mat.use_nodes and mat.node_tree:
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE" and getattr(node, "image", None):
                name = node.image.name
                name = name.rsplit(".", 1)[0]
                return name

    return mat.name.rsplit(".", 1)[0]

def collect_material_names_in_slot_order(mesh_obj) -> list[str]:
    names = []
    for slot in getattr(mesh_obj, "material_slots", []):
        mat = slot.material
        names.append(resolve_texture_name(mat))
    return names

def readIdProp(obj, key, default=None):
    try:
        if obj is not None and key in obj:
            return obj[key]
    except Exception:
        pass
    return default

def read_idprop(obj, key, default=None):
    return readIdProp(obj, key, default)

MDL_FACE_ATTRIBUTES = (
    "bleeds_mdl_part_index",
    "bleeds_mdl_material_index",
    "bleeds_mdl_source_strip_index",
    "bleeds_mdl_source_strip_triangle_index",
)

MDL_CORNER_ATTRIBUTES = (
    "bleeds_mdl_corner_source_emit_index",
    "bleeds_mdl_corner_source_export_vertex_index",
    "bleeds_mdl_corner_source_strip_index",
    "bleeds_mdl_corner_source_strip_vertex_index",
)

MDL_POINT_ATTRIBUTES = (
    "bleeds_mdl_point_source_emit_index",
    "bleeds_mdl_point_source_export_vertex_index",
    "bleeds_mdl_point_source_strip_index",
    "bleeds_mdl_point_source_strip_vertex_index",
    "bleeds_mdl_point_skin_raw0",
    "bleeds_mdl_point_skin_raw1",
    "bleeds_mdl_point_skin_raw2",
    "bleeds_mdl_point_skin_raw3",
)

def getMdlAttributeDomainSize(mesh: bpy.types.Mesh, domain: str) -> int:
    domain_key = str(domain or "").upper().strip()
    if domain_key == 'POINT':
        return len(mesh.vertices)
    if domain_key == 'FACE':
        return len(mesh.polygons)
    if domain_key == 'CORNER':
        return len(mesh.loops)
    if domain_key == 'EDGE':
        return len(mesh.edges)
    return 0

def ensureMdlIntAttribute(mesh: bpy.types.Mesh, name: str, domain: str) -> Any:
    if mesh is None:
        return None

    domain_key = str(domain or "").upper().strip()
    try:
        mesh.update(calc_edges=False)
    except Exception:
        try:
            mesh.update()
        except Exception:
            pass

    expected_count = getMdlAttributeDomainSize(mesh, domain_key)
    attribute = getMeshAttribute(mesh, name)

    if attribute is not None:
        try:
            existing_domain = str(getattr(attribute, "domain", "") or "").upper().strip()
        except Exception:
            existing_domain = domain_key
        if existing_domain and existing_domain != domain_key:
            try:
                removeMeshAttribute(mesh, attribute)
                attribute = None
            except Exception:
                return attribute

    if attribute is None:
        try:
            attribute = ensureMeshAttribute(mesh, name, 'INT', domain_key)
        except Exception:
            return None

    try:
        current_count = len(attribute.data)
    except Exception:
        current_count = 0

    if expected_count > 0 and current_count == 0:
        try:
            mesh.update(calc_edges=False)
        except Exception:
            try:
                mesh.update()
            except Exception:
                pass
        try:
            current_count = len(attribute.data)
        except Exception:
            current_count = 0

    if expected_count > 0 and current_count == 0:
        try:
            removeMeshAttribute(mesh, attribute)
            attribute = ensureMeshAttribute(mesh, name, 'INT', domain_key)
        except Exception:
            pass

    return attribute

def setMdlIntAttributeValue(attribute: Any, index: int, value: int) -> bool:
    if attribute is None:
        return False
    try:
        target_index = int(index)
    except Exception:
        return False
    if target_index < 0:
        return False
    try:
        if target_index >= len(attribute.data):
            return False
        attribute.data[target_index].value = int(value)
        return True
    except Exception:
        return False

def getMdlIntAttribute(mesh: bpy.types.Mesh, name: str):
    try:
        attribute = getMeshAttribute(mesh, name)
        if attribute is None:
            return None
        return attribute
    except Exception:
        return None

def readMdlIntAttributeValues(mesh: bpy.types.Mesh, name: str, expected_count: int, default_value: int = -1) -> List[int]:
    attribute = getMdlIntAttribute(mesh, name)
    if attribute is None:
        return [int(default_value) for _ in range(int(expected_count))]
    values: List[int] = []
    try:
        for index in range(int(expected_count)):
            if index < len(attribute.data):
                values.append(int(attribute.data[index].value))
            else:
                values.append(int(default_value))
    except Exception:
        return [int(default_value) for _ in range(int(expected_count))]
    return values

def matrixFromFlatMdlProperty(value: Any, fallback: Optional[Matrix] = None) -> Matrix:
    if fallback is None:
        fallback = Matrix.Identity(4)
    try:
        values = list(value)
        if len(values) != 16:
            return fallback.copy()
        return Matrix((
            (float(values[0]),  float(values[1]),  float(values[2]),  float(values[3])),
            (float(values[4]),  float(values[5]),  float(values[6]),  float(values[7])),
            (float(values[8]),  float(values[9]),  float(values[10]), float(values[11])),
            (float(values[12]), float(values[13]), float(values[14]), float(values[15])),
        ))
    except Exception:
        return fallback.copy()

def readMdlMatrixProperty(owner: Any, keys: Tuple[str, ...], fallback: Optional[Matrix] = None) -> Matrix:
    if fallback is None:
        fallback = Matrix.Identity(4)
    if owner is None:
        return fallback.copy()
    for key in keys:
        try:
            if hasattr(owner, "__contains__") and key in owner:
                return matrixFromFlatMdlProperty(owner[key], fallback)
        except Exception:
            pass
        try:
            value = getattr(owner, key)
            if value is not None:
                return matrixFromFlatMdlProperty(value, fallback)
        except Exception:
            pass
    return fallback.copy()

MDL_EXPLICIT_NON_NATIVE_ORIGINS = {
    "DERIVED_EXPORT",
    "REFRESHED_EXPORT",
    "REFRESHED",
    "CUSTOM",
    "CUSTOM_EXPORT",
    "GENERATED",
    "STAMPED_EXPORT",
    "EXPORT_STAMPED",
    "OBJ",
    "DFF",
    "DEMONFF",
    "DRAGONFF",
}

def getMdlSemanticOriginOwners(mesh_obj: Optional[bpy.types.Object]) -> List[Tuple[Any, str]]:
    owners: List[Any] = []
    if mesh_obj is not None:

        owners.append(mesh_obj)
        try:
            mesh = getattr(mesh_obj, "data", None)
            if mesh is not None:
                owners.append(mesh)
        except Exception:
            pass

    result: List[Tuple[Any, str]] = []
    for owner in owners:
        try:
            value = readIdProp(owner, "bleeds_mdl_semantic_attributes_origin", None)
            if value is not None:
                origin = str(value or "").upper().strip()
                if origin:
                    result.append((owner, origin))
        except Exception:
            pass
    return result

def getMdlSemanticOriginUpper(mesh_obj: Optional[bpy.types.Object]) -> str:
    origins = getMdlSemanticOriginOwners(mesh_obj)
    for _owner, origin in origins:
        if origin in MDL_EXPLICIT_NON_NATIVE_ORIGINS:
            return origin
    for _owner, origin in origins:
        if origin:
            return origin
    return ""

def hasExplicitNonNativeMdlOrigin(mesh_obj: Optional[bpy.types.Object]) -> bool:
    for _owner, origin in getMdlSemanticOriginOwners(mesh_obj):
        if origin in MDL_EXPLICIT_NON_NATIVE_ORIGINS:
            return True
        if origin and origin != "IMPORTED_PS2":
            return True
    return False

def hasStrongImportedMdlTopologyProof(mesh_obj: Optional[bpy.types.Object]) -> bool:
    if mesh_obj is None or getattr(mesh_obj, "type", None) != 'MESH':
        return False
    mesh = getattr(mesh_obj, "data", None)
    if mesh is None:
        return False
    try:
        counts = getMdlSourceStripCounts(mesh_obj)
        vertex_count = len(getattr(mesh, "vertices", []) or [])
        if counts and vertex_count > 0 and int(sum(int(v) for v in counts)) == int(vertex_count):
            return True
    except Exception:
        pass
    try:
        source_count = readIdProp(mesh, "bleeds_mdl_source_part_vertex_count", None)
        if source_count is not None and int(source_count) == len(getattr(mesh, "vertices", []) or []):
            return True
    except Exception:
        pass
    return False

def isMdlNativeCoordinateSpaceMesh(mesh_obj: Optional[bpy.types.Object]) -> bool:
    if mesh_obj is None or getattr(mesh_obj, "type", None) != 'MESH':
        return False

    owners = []
    mesh = None
    try:
        mesh = getattr(mesh_obj, "data", None)
        if mesh is not None:
            owners.append(mesh)
    except Exception:
        mesh = None
    owners.append(mesh_obj)

    saw_origin = False
    saw_imported_origin = False
    for _owner, origin in getMdlSemanticOriginOwners(mesh_obj):
        saw_origin = True
        if origin in MDL_EXPLICIT_NON_NATIVE_ORIGINS or (origin and origin != "IMPORTED_PS2"):
            try:
                mesh_obj["bleeds_mdl_native_space_rejected_reason"] = f"semantic_origin_{origin}"
            except Exception:
                pass
            return False
        if origin == "IMPORTED_PS2":
            saw_imported_origin = True

    if saw_imported_origin:
        if hasStrongImportedMdlTopologyProof(mesh_obj):
            return True
        try:
            mesh_obj["bleeds_mdl_native_space_rejected_reason"] = "imported_origin_without_matching_native_topology"
        except Exception:
            pass
        return False

    if saw_origin:
        try:
            mesh_obj["bleeds_mdl_native_space_rejected_reason"] = "semantic_origin_not_imported_ps2"
        except Exception:
            pass
        return False

    for owner in owners:
        try:
            imported_space = readIdProp(owner, "bleeds_mdl_imported_coordinate_space", None)
            if imported_space is not None and bool(imported_space):
                return True
        except Exception:
            pass

    for owner in owners:
        for key in ("bleeds_mdl_part_matrix_export_basis", "bleeds_mdl_part_matrix_world"):
            try:
                if readMdlAnyProperty(owner, key, None) is not None:
                    return True
            except Exception:
                pass

    try:
        counts = getMdlSourceStripCounts(mesh_obj)
        vertex_count = len(getattr(mesh, "vertices", []) or []) if mesh is not None else 0
        if counts and vertex_count > 0 and int(sum(int(v) for v in counts)) == int(vertex_count):
            return True
    except Exception:
        pass

    return False

def findMdlDisplayArmatureForMesh(mesh_obj: Optional[bpy.types.Object], root_obj: Optional[bpy.types.Object] = None) -> Optional[bpy.types.Object]:
    if mesh_obj is None:
        return None

    try:
        parent_obj = getattr(mesh_obj, "parent", None)
        if parent_obj is not None and getattr(parent_obj, "type", None) == 'ARMATURE':
            return parent_obj
    except Exception:
        pass

    try:
        for mod in getattr(mesh_obj, "modifiers", []):
            if getattr(mod, "type", None) == 'ARMATURE':
                arm_obj = getattr(mod, "object", None)
                if arm_obj is not None and getattr(arm_obj, "type", None) == 'ARMATURE':
                    return arm_obj
    except Exception:
        pass

    if root_obj is not None:
        try:
            stack = list(getattr(root_obj, "children", []) or [])
            while stack:
                obj = stack.pop(0)
                if getattr(obj, "type", None) == 'ARMATURE':
                    return obj
                stack.extend(list(getattr(obj, "children", []) or []))
        except Exception:
            pass

    return None

def getMdlAtomicFrameNameCandidates(root_obj: Optional[bpy.types.Object]) -> List[str]:
    candidates: List[str] = []

    def addName(value: Any) -> None:
        try:
            name = str(value or "").strip()
        except Exception:
            name = ""
        if not name:
            return
        if name not in candidates:
            candidates.append(name)
        try:
            canon_name = str(mdl_lib.canon_frame_name(name)).strip()
            if canon_name and canon_name not in candidates:
                candidates.append(canon_name)
        except Exception:
            pass

    if root_obj is not None:
        for key in (
            "bleeds_mdl_atomic_frame_name",
            "bleeds_base_frame_name",
            "bleeds_mdl_base_frame_name",
            "bleeds_mdl_atomic_parent_frame_name",
        ):
            value = readMdlAnyProperty(root_obj, key, None)
            if value is not None:
                addName(value)

        frame_ptr = readMdlAnyProperty(root_obj, "bleeds_mdl_atomic_frame_ptr", None)
        if frame_ptr is None:
            frame_ptr = readMdlAnyProperty(root_obj, "bleeds_mdl_frame_ptr", None)
        if frame_ptr is not None:
            try:
                wanted_ptr = int(frame_ptr) & 0xFFFFFFFF
                ptrs = [int(v) & 0xFFFFFFFF for v in list(readMdlAnyProperty(root_obj, "bleeds_mdl_frame_ptrs", []) or [])]
                names = [str(v) for v in list(readMdlAnyProperty(root_obj, "bleeds_mdl_frame_names", []) or [])]
                for index, ptr in enumerate(ptrs):
                    if ptr == wanted_ptr and index < len(names):
                        addName(names[index])
                        break
            except Exception:
                pass

    for fallback_name in (
        "male_base01",
        "male_base",
        "female_base",
        "female_base01",
        "root",
    ):
        addName(fallback_name)

    return candidates

def matrixFromMdlFlatFrameArray(values: Any, index: int, fallback: Optional[Matrix] = None) -> Optional[Matrix]:
    try:
        flat = list(values or [])
        start = int(index) * 16
        if start < 0 or start + 16 > len(flat):
            return None
        return matrixFromFlatMdlProperty(flat[start:start + 16], fallback or Matrix.Identity(4))
    except Exception:
        return None

def findMdlStoredFrameWorldMatrixOnOwner(owner: Optional[Any], frame_names: List[str]) -> Optional[Tuple[str, Matrix]]:
    if owner is None:
        return None

    wanted_names = set()
    for raw_name in list(frame_names or []):
        try:
            name = str(raw_name or "").strip()
        except Exception:
            name = ""
        if not name:
            continue
        wanted_names.add(name)
        wanted_names.add(name.lower())
        try:
            canon_name = str(mdl_lib.canon_frame_name(name)).strip()
            if canon_name:
                wanted_names.add(canon_name)
                wanted_names.add(canon_name.lower())
        except Exception:
            pass

    try:
        names = [str(v) for v in list(readMdlAnyProperty(owner, "bleeds_mdl_frame_names", []) or [])]
    except Exception:
        names = []
    if not names:
        return None

    match_index = None
    matched_name = ""
    for index, raw_name in enumerate(names):
        try:
            name = str(raw_name or "").strip()
        except Exception:
            name = ""
        if not name:
            continue
        variants = {name, name.lower()}
        try:
            canon_name = str(mdl_lib.canon_frame_name(name)).strip()
            if canon_name:
                variants.add(canon_name)
                variants.add(canon_name.lower())
        except Exception:
            pass
        if variants.intersection(wanted_names):
            match_index = int(index)
            matched_name = str(name)
            break

    if match_index is None:
        return None

    for key in (
        "bleeds_mdl_frame_world_matrices",
        "bleeds_mdl_frame_global_matrices",
        "bleeds_mdl_frame_computed_world_matrices",
        "bleeds_mdl_frame_import_global_matrices",
    ):
        matrix_value = matrixFromMdlFlatFrameArray(readMdlAnyProperty(owner, key, None), match_index)
        if matrix_value is None:
            continue

        return (matched_name or (frame_names[0] if frame_names else "stored_atomic_frame"), matrix_value)

    return None

def findMdlStoredFrameWorldMatrix(
    root_obj: Optional[bpy.types.Object],
    arm_obj: Optional[bpy.types.Object],
    frame_names: List[str],
) -> Optional[Tuple[str, Matrix]]:

    for owner in (
        root_obj,
        arm_obj,
        getattr(arm_obj, "data", None) if arm_obj is not None else None,
    ):
        stored = findMdlStoredFrameWorldMatrixOnOwner(owner, frame_names)
        if stored is not None:
            return stored
    return None

def readOptionalMdlMatrixProperty(owner: Optional[Any], key: str) -> Optional[Matrix]:
    if owner is None:
        return None
    try:
        if hasattr(owner, "__contains__") and key in owner:
            values = list(owner[key])
            if len(values) == 16:
                return matrixFromFlatMdlProperty(values, Matrix.Identity(4))
    except Exception:
        pass
    try:
        value = getattr(owner, key)
        if value is not None:
            values = list(value)
            if len(values) == 16:
                return matrixFromFlatMdlProperty(values, Matrix.Identity(4))
    except Exception:
        pass
    return None

def matrixIsFinite(matrix_value: Matrix) -> bool:
    try:
        for row in range(4):
            for col in range(4):
                value = float(matrix_value[row][col])
                if value != value:
                    return False
                if abs(value) > 1.0e8:
                    return False
        return True
    except Exception:
        return False

def readMdlPartImportDisplayAnchor(owner: Optional[Any]) -> Optional[Tuple[str, Matrix]]:
    if owner is None:
        return None

    for key in (
        "bleeds_mdl_part_matrix_world",
        "bleeds_mdl_part_matrix_export_basis",
        "bleeds_mdl_part_matrix_parent_world",
    ):
        matrix_value = readOptionalMdlMatrixProperty(owner, key)
        if matrix_value is None:
            continue
        if not matrixIsFinite(matrix_value):
            continue
        return (key, matrix_value)

    return None

def walkMdlRootObjects(root_obj: Optional[bpy.types.Object]) -> List[bpy.types.Object]:
    if root_obj is None:
        return []
    result: List[bpy.types.Object] = []
    try:
        stack = list(getattr(root_obj, "children", []) or [])
        while stack:
            obj = stack.pop(0)
            result.append(obj)
            stack.extend(list(getattr(obj, "children", []) or []))
    except Exception:
        pass
    return result

def resolveMdlPartImportDisplayAnchorWorldMatrix(
    mesh_obj: Optional[bpy.types.Object],
    root_obj: Optional[bpy.types.Object],
) -> Optional[Tuple[str, Matrix]]:
    if mesh_obj is None:
        return None

    for owner_name, owner in (
        ("object", mesh_obj),
        ("mesh_data", getattr(mesh_obj, "data", None)),
    ):
        own_anchor = readMdlPartImportDisplayAnchor(owner)
        if own_anchor is not None:
            key, matrix_value = own_anchor
            return (f"{owner_name}:{key}", matrix_value)

    for candidate in walkMdlRootObjects(root_obj):
        if candidate is mesh_obj or getattr(candidate, "type", None) != 'MESH':
            continue
        try:
            candidate_origin = getMdlSemanticOriginUpper(candidate)
        except Exception:
            candidate_origin = ""
        if candidate_origin and candidate_origin != "IMPORTED_PS2":
            continue
        candidate_anchor = None
        for owner_name, owner in (
            ("object", candidate),
            ("mesh_data", getattr(candidate, "data", None)),
        ):
            candidate_anchor = readMdlPartImportDisplayAnchor(owner)
            if candidate_anchor is not None:
                key, matrix_value = candidate_anchor
                return (f"source:{getattr(candidate, 'name', 'mesh')}:{owner_name}:{key}", matrix_value)

    return None

def findMdlBoneRestWorldMatrix(arm_obj: Optional[bpy.types.Object], frame_names: List[str]) -> Optional[Tuple[str, Matrix]]:
    if arm_obj is None or getattr(arm_obj, "type", None) != 'ARMATURE':
        return None

    arm_data = getattr(arm_obj, "data", None)
    bones = getattr(arm_data, "bones", None)
    if bones is None:
        return None

    wanted_names = []
    for raw_name in list(frame_names or []):
        try:
            name = str(raw_name or "").strip()
        except Exception:
            name = ""
        if not name:
            continue
        if name not in wanted_names:
            wanted_names.append(name)
        try:
            canon_name = str(mdl_lib.canon_frame_name(name)).strip()
            if canon_name and canon_name not in wanted_names:
                wanted_names.append(canon_name)
        except Exception:
            pass

    for wanted_name in wanted_names:
        bone = None
        try:
            bone = bones.get(wanted_name)
        except Exception:
            bone = None
        if bone is None:
            wanted_lower = wanted_name.lower()
            try:
                for candidate in bones:
                    if str(getattr(candidate, "name", "") or "").lower() == wanted_lower:
                        bone = candidate
                        break
            except Exception:
                bone = None
        if bone is None:
            continue
        try:
            return (str(getattr(bone, "name", wanted_name)), arm_obj.matrix_world @ bone.matrix_local)
        except Exception:
            continue

    return None

def resolveMdlAtomicFrameWorldMatrix(
    root_obj: Optional[bpy.types.Object],
    arm_obj: Optional[bpy.types.Object],
) -> Optional[Tuple[str, Matrix]]:
    frame_names = getMdlAtomicFrameNameCandidates(root_obj)

    stored_matrix = findMdlStoredFrameWorldMatrix(root_obj, arm_obj, frame_names)
    if stored_matrix is not None:
        return stored_matrix

    bone_result = findMdlBoneRestWorldMatrix(arm_obj, frame_names)
    if bone_result is not None:
        return bone_result

    return None

def matrixIsEffectivelyIdentity(mtx: Matrix, epsilon: float = 1.0e-6) -> bool:
    try:
        identity = Matrix.Identity(4)
        for r in range(4):
            for c in range(4):
                if abs(float(mtx[r][c]) - float(identity[r][c])) > epsilon:
                    return False
        return True
    except Exception:
        return False

def resolveMdlPartExportMatrix(mesh_obj: bpy.types.Object, root_obj: Optional[bpy.types.Object] = None) -> Matrix:
    if mesh_obj is None:
        return Matrix.Identity(4)

    try:
        current_world = mesh_obj.matrix_world.copy()
    except Exception:
        current_world = Matrix.Identity(4)

    native_mdl_part_space = isMdlNativeCoordinateSpaceMesh(mesh_obj)

    imported_ped_root = isImportedPedRootForMdlExport(root_obj)

    if native_mdl_part_space:
        space_name = "IMPORTED_MDL_PART_SPACE_NO_OBJECT_BAKE"
        try:
            mesh_obj["bleeds_mdl_export_position_space"] = space_name
            mesh_obj["bleeds_mdl_export_ignored_matrix_world"] = [float(v) for row in current_world for v in row]
        except Exception:
            pass
        try:
            mesh = getattr(mesh_obj, "data", None)
            if mesh is not None:
                mesh["bleeds_mdl_export_position_space"] = space_name
        except Exception:
            pass
        return Matrix.Identity(4)

    if imported_ped_root and root_obj is not None:
        arm_obj = findMdlDisplayArmatureForMesh(mesh_obj, root_obj)
        export_matrix = None
        space_name = "CUSTOM_ROOT_LOCAL_AUTHORING_SPACE_BAKED"
        atomic_anchor_name = ""
        atomic_anchor_world = None

        atomic_frame_result = resolveMdlAtomicFrameWorldMatrix(root_obj, arm_obj)
        if atomic_frame_result is not None:
            try:
                atomic_anchor_name, atomic_anchor_world = atomic_frame_result
                export_matrix = atomic_anchor_world.inverted() @ current_world
                space_name = "CUSTOM_STORED_ATOMIC_FRAME_LOCAL_AUTHORING_SPACE_BAKED"
            except Exception:
                export_matrix = None

        if export_matrix is None:
            display_anchor_result = resolveMdlPartImportDisplayAnchorWorldMatrix(mesh_obj, root_obj)
            if display_anchor_result is not None:
                try:
                    candidate_anchor_name, candidate_anchor_world = display_anchor_result
                    if not matrixIsEffectivelyIdentity(candidate_anchor_world):
                        atomic_anchor_name, atomic_anchor_world = candidate_anchor_name, candidate_anchor_world
                        export_matrix = atomic_anchor_world.inverted() @ current_world
                        space_name = "CUSTOM_IMPORT_DISPLAY_MATRIX_LOCAL_AUTHORING_SPACE_BAKED_FALLBACK"
                except Exception:
                    export_matrix = None

        if export_matrix is None and arm_obj is not None:
            try:
                arm_world_inv = arm_obj.matrix_world.inverted()
                export_matrix = arm_world_inv @ current_world
                space_name = "CUSTOM_ARMATURE_LOCAL_AUTHORING_SPACE_BAKED_FALLBACK"
            except Exception:
                export_matrix = None

        if export_matrix is None:
            try:
                root_world_inv = root_obj.matrix_world.inverted()
                export_matrix = root_world_inv @ current_world
                space_name = "CUSTOM_ROOT_LOCAL_AUTHORING_SPACE_BAKED_FALLBACK"
            except Exception:
                export_matrix = current_world.copy()
                space_name = "CUSTOM_WORLD_AUTHORING_SPACE_BAKED_FALLBACK"

        try:
            mesh_obj["bleeds_mdl_export_position_space"] = space_name
            mesh_obj["bleeds_mdl_export_matrix"] = [float(v) for row in export_matrix for v in row]
            if arm_obj is not None:
                mesh_obj["bleeds_mdl_export_armature_anchor"] = getattr(arm_obj, "name", "")
                mesh_obj["bleeds_mdl_export_armature_world"] = [float(v) for row in arm_obj.matrix_world for v in row]
            if atomic_anchor_world is not None:
                mesh_obj["bleeds_mdl_export_atomic_frame_anchor"] = str(atomic_anchor_name)
                mesh_obj["bleeds_mdl_export_atomic_frame_world"] = [float(v) for row in atomic_anchor_world for v in row]
        except Exception:
            pass
        try:
            mesh = getattr(mesh_obj, "data", None)
            if mesh is not None:
                mesh["bleeds_mdl_export_position_space"] = space_name
                if atomic_anchor_world is not None:
                    mesh["bleeds_mdl_export_atomic_frame_anchor"] = str(atomic_anchor_name)
        except Exception:
            pass
        return export_matrix

    try:
        mesh_obj["bleeds_mdl_export_position_space"] = "AUTHORING_OBJECT_SPACE_BAKED"
    except Exception:
        pass
    return current_world

def getBaseMeshForMdlExport(mesh_obj: bpy.types.Object) -> Optional[bpy.types.Mesh]:
    try:
        mesh = getattr(mesh_obj, "data", None)
        if mesh is not None:
            mesh.update(calc_edges=True)
        return mesh
    except Exception:
        try:
            return getattr(mesh_obj, "data", None)
        except Exception:
            return None

def readMdlAnyProperty(owner: Optional[Any], key: str, default=None):
    if owner is None:
        return default
    try:
        if hasattr(owner, "__contains__") and key in owner:
            return owner[key]
    except Exception:
        pass
    try:
        value = getattr(owner, key)
        if value is not None:
            return value
    except Exception:
        pass
    return default

def readMdlRootModelTypeUpper(root_obj: Optional[bpy.types.Object]) -> str:
    if root_obj is None:
        return ""
    for key in (
        "bleeds_mdl_type",
        "bleeds_export_mdl_type",
        "bleeds_mdl_model_type",
        "bleeds_stories_mdl_type",
    ):
        try:
            value = readMdlAnyProperty(root_obj, key, None)
            if value is not None:
                text = str(value or "").upper().strip()
                if text:
                    return text
        except Exception:
            pass
    return ""

def readMdlRootImportTypeCode(root_obj: Optional[bpy.types.Object]) -> Optional[int]:
    if root_obj is None:
        return None
    for key in (
        "bleeds_mdl_import_type",
        "bleeds_import_type",
        "bleeds_stories_import_type",
    ):
        try:
            value = readMdlAnyProperty(root_obj, key, None)
        except Exception:
            value = None
        if value is None:
            continue
        try:
            return int(value)
        except Exception:
            pass
        try:
            text = str(value or "").upper().strip()
        except Exception:
            text = ""
        if text in {"PED", "PEDMODEL", "ACTOR", "CLUMP_PED"}:
            return 2
        if text in {"CUT", "CUTSCENE", "CUTSCENE_ACTOR"}:
            return 3
        if text in {"SIM", "SIMPLE", "PROP", "MODEL"}:
            return 1
    return None

def hasMdlImportedRootMarkers(root_obj: Optional[bpy.types.Object]) -> bool:
    if root_obj is None:
        return False
    marker_keys = (
        "bleeds_mdl_frame_names",
        "bleeds_mdl_frame_ptrs",
        "bleeds_mdl_atomic_hash_key",
        "bleeds_mdl_source_path",
        "bleeds_mdl_imported",
        "bleeds_mdl_atomic_frame_ptr",
        "bleeds_mdl_atomic_frame_name",
        "bleeds_mdl_hierarchy_count",
    )
    for key in marker_keys:
        try:
            if readMdlAnyProperty(root_obj, key, None) is not None:
                return True
        except Exception:
            pass

    try:
        for obj in walkMdlRootObjects(root_obj):
            if getattr(obj, "type", None) != 'ARMATURE':
                continue
            for owner in (obj, getattr(obj, "data", None)):
                for key in marker_keys:
                    try:
                        if readMdlAnyProperty(owner, key, None) is not None:
                            return True
                    except Exception:
                        pass
    except Exception:
        pass
    return False

def isImportedPedRootForMdlExport(root_obj: Optional[bpy.types.Object]) -> bool:
    if root_obj is None:
        return False

    try:
        if bool(readMdlAnyProperty(root_obj, "bleeds_mdl_export_force_ped_space", False)):
            return True
    except Exception:
        pass

    root_has_mdl_markers = hasMdlImportedRootMarkers(root_obj)
    if not root_has_mdl_markers:
        return False

    root_import_type = readMdlRootImportTypeCode(root_obj)
    if root_import_type in (2, 3):
        return True

    root_mdl_type = readMdlRootModelTypeUpper(root_obj)
    if root_mdl_type in {"PED", "CUT", "CUTSCENE", "ACTOR", "PEDMODEL"}:
        return True

    try:
        if (
            readMdlAnyProperty(root_obj, "bleeds_mdl_frame_names", None) is not None and
            (
                readMdlAnyProperty(root_obj, "bleeds_mdl_atomic_frame_ptr", None) is not None or
                readMdlAnyProperty(root_obj, "bleeds_mdl_atomic_frame_name", None) is not None or
                readMdlAnyProperty(root_obj, "bleeds_mdl_hierarchy_count", None) is not None
            )
        ):
            return True
    except Exception:
        pass

    return False

def hasVisibleDeformModifiersForMdlExport(mesh_obj: Optional[bpy.types.Object]) -> bool:
    if mesh_obj is None:
        return False
    try:
        for mod in getattr(mesh_obj, "modifiers", []) or []:
            if not getattr(mod, "show_viewport", True):
                continue
            mod_type = str(getattr(mod, "type", "") or "").upper()
            if mod_type in {
                "ARMATURE", "LATTICE", "MESH_DEFORM", "SHRINKWRAP", "SIMPLE_DEFORM",
                "CAST", "CURVE", "DISPLACE", "HOOK", "SMOOTH", "CORRECTIVE_SMOOTH",
                "WEIGHTED_NORMAL", "NORMAL_EDIT", "TRIANGULATE", "MIRROR", "SOLIDIFY",
                "SUBSURF", "MULTIRES", "BEVEL", "WELD", "DECIMATE",
            }:
                return True
    except Exception:
        pass
    return False

def isExplicitCustomPedReplacementMesh(mesh_obj: Optional[bpy.types.Object], root_obj: Optional[bpy.types.Object]) -> bool:
    if mesh_obj is None or getattr(mesh_obj, "type", None) != 'MESH':
        return False
    if not isImportedPedRootForMdlExport(root_obj):
        return False

    owners: List[Any] = []
    try:
        mesh = getattr(mesh_obj, "data", None)
        if mesh is not None:
            owners.append(mesh)
    except Exception:
        pass
    owners.append(mesh_obj)

    for _owner, origin in getMdlSemanticOriginOwners(mesh_obj):
        if origin in MDL_EXPLICIT_NON_NATIVE_ORIGINS or (origin and origin != "IMPORTED_PS2"):
            return True

    custom_markers = (
        "bleeds_mdl_custom_ped_group_source",
        "bleeds_mdl_vertex_groups_rebuilt_from_export_skin",
        "bleeds_mdl_replace_native_part",
        "bleeds_mdl_is_replacement_part",
        "bleeds_mdl_force_custom_ped_skin_rebuild",
    )
    for owner in owners:
        if owner is None:
            continue
        for key in custom_markers:
            try:
                if key in owner and bool(owner[key]):
                    return True
            except Exception:
                continue
        try:
            mode = str(readIdProp(owner, "bleeds_mdl_skin_transfer_mode", "") or "").upper().strip()
        except Exception:
            mode = ""
        if mode in {"NEAREST", "NEAREST_NATIVE", "TRANSFER", "TRANSFER_NATIVE", "SOURCE_NEAREST", "STRICT_NATIVE"}:
            return True

    return False

def isCustomPedMeshUnderImportedRootForMdlExport(mesh_obj: Optional[bpy.types.Object], root_obj: Optional[bpy.types.Object]) -> bool:
    if mesh_obj is None or getattr(mesh_obj, "type", None) != 'MESH':
        return False
    if not isImportedPedRootForMdlExport(root_obj):
        return False
    if isExplicitCustomPedReplacementMesh(mesh_obj, root_obj):
        return True
    if isMdlNativeCoordinateSpaceMesh(mesh_obj):
        return False
    return True

def shouldTransferMdlSkinFromNativeParts(mesh_obj: Optional[bpy.types.Object], root_obj: Optional[bpy.types.Object]) -> bool:
    if not isCustomPedMeshUnderImportedRootForMdlExport(mesh_obj, root_obj):
        return False

    owners = []
    try:
        mesh = getattr(mesh_obj, "data", None)
        if mesh is not None:
            owners.append(mesh)
    except Exception:
        pass
    owners.append(mesh_obj)

    for owner in owners:
        try:
            if bool(readIdProp(owner, "bleeds_mdl_trust_custom_skin_weights", False)):
                return False
        except Exception:
            pass
        try:
            mode = str(readIdProp(owner, "bleeds_mdl_skin_transfer_mode", "") or "").upper().strip()
        except Exception:
            mode = ""
        if mode in {"CUSTOM", "CUSTOM_GROUPS", "VERTEX_GROUPS", "GROUPS", "TRUST_GROUPS"}:
            return False
        if mode in {"NEAREST", "NEAREST_NATIVE", "TRANSFER", "TRANSFER_NATIVE", "SOURCE_NEAREST"}:
            return True

    return True

def shouldUseEvaluatedMeshForMdlExport(mesh_obj: Optional[bpy.types.Object], root_obj: Optional[bpy.types.Object]) -> bool:
    if mesh_obj is None or getattr(mesh_obj, "type", None) != 'MESH':
        return False
    if isMdlNativeCoordinateSpaceMesh(mesh_obj):
        return False
    if not isImportedPedRootForMdlExport(root_obj):
        return False

    try:
        if bool(readIdProp(mesh_obj, "bleeds_mdl_force_evaluated_mesh_export", False)):
            return True
    except Exception:
        pass
    try:
        mesh = getattr(mesh_obj, "data", None)
        if mesh is not None and bool(readIdProp(mesh, "bleeds_mdl_force_evaluated_mesh_export", False)):
            return True
    except Exception:
        pass
    return False

def hasCustomAuthoredMdlExportMesh(mesh_objs: Iterable[bpy.types.Object]) -> bool:
    for obj in mesh_objs or []:
        try:
            if obj is None or getattr(obj, "type", None) != 'MESH':
                continue
            if hasExplicitNonNativeMdlOrigin(obj):
                return True
            if not isMdlNativeCoordinateSpaceMesh(obj):
                return True
        except Exception:
            return True
    return False

def makeSafeScalePosFromBounds(bounds, *, raw_limit: float = 28672.0):
    if bounds is None:
        return None
    min_x, min_y, min_z, max_x, max_y, max_z = bounds
    cx = (float(min_x) + float(max_x)) * 0.5
    cy = (float(min_y) + float(max_y)) * 0.5
    cz = (float(min_z) + float(max_z)) * 0.5

    hx = max(1.0e-6, (float(max_x) - float(min_x)) * 0.5)
    hy = max(1.0e-6, (float(max_y) - float(min_y)) * 0.5)
    hz = max(1.0e-6, (float(max_z) - float(min_z)) * 0.5)

    global_scale = 100.0 * 0.00000030518203134641490805874367518203
    safe_raw = max(1024.0, min(32000.0, float(raw_limit)))
    denom = safe_raw * global_scale

    return mdl_lib.ScalePos((hx / denom, hy / denom, hz / denom), (cx, cy, cz))

def rawUtilizationForScalePos(bounds, scale_pos) -> Tuple[float, float, float]:
    if bounds is None or scale_pos is None:
        return (0.0, 0.0, 0.0)
    min_x, min_y, min_z, max_x, max_y, max_z = bounds
    sx, sy, sz = [float(v) for v in scale_pos.scale[:3]]
    tx, ty, tz = [float(v) for v in scale_pos.pos[:3]]
    global_scale = 100.0 * 0.00000030518203134641490805874367518203

    def axis_util(lo, hi, center, scale):
        if abs(scale) <= 1.0e-12:
            return 999999.0
        return max(abs(float(lo) - center), abs(float(hi) - center)) / (abs(scale) * global_scale)

    return (
        axis_util(min_x, max_x, tx, sx),
        axis_util(min_y, max_y, ty, sy),
        axis_util(min_z, max_z, tz, sz),
    )

def getEvaluatedMeshForMdlExport(
    context: bpy.types.Context,
    mesh_obj: bpy.types.Object,
    root_obj: Optional[bpy.types.Object] = None,
) -> Tuple[Optional[bpy.types.Mesh], Optional[bpy.types.Object], str]:
    base_mesh = getBaseMeshForMdlExport(mesh_obj)
    if mesh_obj is None:
        return base_mesh, None, "BASE_NO_OBJECT"

    if not shouldUseEvaluatedMeshForMdlExport(mesh_obj, root_obj):
        return base_mesh, None, "BASE_NATIVE_OR_NO_VISIBLE_DEFORM"

    try:
        depsgraph = context.evaluated_depsgraph_get() if context is not None else bpy.context.evaluated_depsgraph_get()
    except Exception:
        depsgraph = None

    if depsgraph is None:
        return base_mesh, None, "BASE_NO_DEPSGRAPH"

    try:
        eval_obj = mesh_obj.evaluated_get(depsgraph)
    except Exception:
        eval_obj = None
    if eval_obj is None:
        return base_mesh, None, "BASE_EVAL_OBJECT_FAILED"

    eval_mesh = None
    try:
        eval_mesh = eval_obj.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    except TypeError:
        try:
            eval_mesh = eval_obj.to_mesh(depsgraph=depsgraph)
        except TypeError:
            try:
                eval_mesh = eval_obj.to_mesh()
            except Exception:
                eval_mesh = None
        except Exception:
            eval_mesh = None
    except Exception:
        eval_mesh = None

    if eval_mesh is None:
        return base_mesh, None, "BASE_TO_MESH_FAILED"

    try:
        eval_mesh.update(calc_edges=True)
    except Exception:
        try:
            eval_mesh.update()
        except Exception:
            pass

    try:
        if base_mesh is not None and len(getattr(eval_mesh, "vertices", []) or []) != len(getattr(base_mesh, "vertices", []) or []):
            mesh_obj["bleeds_mdl_export_evaluated_topology_warning"] = (
                f"evaluated vertex count {len(eval_mesh.vertices)} differs from base "
                f"{len(base_mesh.vertices)}; skin still maps by vertex index"
            )
    except Exception:
        pass

    try:
        mesh_obj["bleeds_mdl_export_mesh_source"] = "EVALUATED_VISIBLE_DEFORM_MESH"
        mesh_obj["bleeds_mdl_export_evaluated_vertex_count"] = int(len(getattr(eval_mesh, "vertices", []) or []))
        mesh_obj["bleeds_mdl_export_base_vertex_count"] = int(len(getattr(base_mesh, "vertices", []) or [])) if base_mesh is not None else 0
    except Exception:
        pass
    try:
        if base_mesh is not None:
            base_mesh["bleeds_mdl_export_mesh_source"] = "EVALUATED_VISIBLE_DEFORM_MESH"
    except Exception:
        pass

    return eval_mesh, eval_obj, "EVALUATED_VISIBLE_DEFORM_MESH"

def clearEvaluatedMeshForMdlExport(eval_obj: Optional[bpy.types.Object]) -> None:
    if eval_obj is None:
        return
    try:
        eval_obj.to_mesh_clear()
    except Exception:
        pass

def writeMdlSemanticDefaultsForExport(mesh_obj: bpy.types.Object, export_part_index: int) -> None:
    if mesh_obj is None or getattr(mesh_obj, "type", None) != 'MESH':
        return

    mesh = getattr(mesh_obj, "data", None)
    if mesh is None:
        return

    try:
        mesh.update(calc_edges=True)
    except Exception:
        try:
            mesh.update()
        except Exception:
            pass

    face_part = ensureMdlIntAttribute(mesh, "bleeds_mdl_part_index", 'FACE')
    face_material = ensureMdlIntAttribute(mesh, "bleeds_mdl_material_index", 'FACE')
    face_strip = ensureMdlIntAttribute(mesh, "bleeds_mdl_source_strip_index", 'FACE')
    face_strip_tri = ensureMdlIntAttribute(mesh, "bleeds_mdl_source_strip_triangle_index", 'FACE')

    corner_emit = ensureMdlIntAttribute(mesh, "bleeds_mdl_corner_source_emit_index", 'CORNER')
    corner_export = ensureMdlIntAttribute(mesh, "bleeds_mdl_corner_source_export_vertex_index", 'CORNER')
    corner_strip = ensureMdlIntAttribute(mesh, "bleeds_mdl_corner_source_strip_index", 'CORNER')
    corner_strip_vertex = ensureMdlIntAttribute(mesh, "bleeds_mdl_corner_source_strip_vertex_index", 'CORNER')

    point_emit = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_source_emit_index", 'POINT')
    point_export = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_source_export_vertex_index", 'POINT')
    point_strip = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_source_strip_index", 'POINT')
    point_strip_vertex = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_source_strip_vertex_index", 'POINT')

    imported_origin = isMdlNativeCoordinateSpaceMesh(mesh_obj)

    part_prop = readIdProp(mesh_obj, "bleeds_mdl_part_index", None)
    if part_prop is None:
        part_prop = readIdProp(mesh, "bleeds_mdl_source_part_index", None)
    try:
        part_index = int(part_prop) if part_prop is not None else int(export_part_index)
    except Exception:
        part_index = int(export_part_index)

    material_prop = readIdProp(mesh_obj, "bleeds_mdl_part_material_id", None)
    if material_prop is None:
        material_prop = readIdProp(mesh, "bleeds_mdl_source_material_index", None)
    try:
        fallback_material_index = int(material_prop) if material_prop is not None else 0
    except Exception:
        fallback_material_index = 0

    if not imported_origin:
        for polygon in mesh.polygons:
            polygon_index = int(polygon.index)
            try:
                material_index = int(polygon.material_index)
            except Exception:
                material_index = fallback_material_index
            setMdlIntAttributeValue(face_part, polygon_index, part_index)
            setMdlIntAttributeValue(face_material, polygon_index, material_index)
            setMdlIntAttributeValue(face_strip, polygon_index, 0)
            setMdlIntAttributeValue(face_strip_tri, polygon_index, polygon_index)

        for loop in mesh.loops:
            loop_index = int(loop.index)
            vertex_index = int(loop.vertex_index)
            setMdlIntAttributeValue(corner_emit, loop_index, loop_index)
            setMdlIntAttributeValue(corner_export, loop_index, vertex_index)
            setMdlIntAttributeValue(corner_strip, loop_index, 0)
            setMdlIntAttributeValue(corner_strip_vertex, loop_index, loop_index)

        for vertex in mesh.vertices:
            vertex_index = int(vertex.index)
            setMdlIntAttributeValue(point_emit, vertex_index, vertex_index)
            setMdlIntAttributeValue(point_export, vertex_index, vertex_index)
            setMdlIntAttributeValue(point_strip, vertex_index, 0)
            setMdlIntAttributeValue(point_strip_vertex, vertex_index, vertex_index)

        try:
            mesh["bleeds_mdl_semantic_attributes_origin"] = "DERIVED_EXPORT"
        except Exception:
            pass

    try:
        mesh["bleeds_mdl_semantic_attributes_version"] = 1
        if not imported_origin:
            mesh["bleeds_mdl_source_part_index"] = int(part_index)
            mesh["bleeds_mdl_source_material_index"] = int(fallback_material_index)
            mesh["bleeds_mdl_source_part_vertex_count"] = int(len(mesh.vertices))
            mesh["bleeds_mdl_source_part_face_count"] = int(len(mesh.polygons))
            mesh["bleeds_mdl_source_loop_count"] = int(len(mesh.loops))
            if readIdProp(mesh, "bleeds_mdl_source_strip_counts", None) is None:
                mesh["bleeds_mdl_source_strip_count"] = 0
                mesh["bleeds_mdl_source_strip_counts"] = []
    except Exception:
        pass

    if readIdProp(mesh_obj, "bleeds_mdl_part_index", None) is None:
        try:
            mesh_obj["bleeds_mdl_part_index"] = int(part_index)
        except Exception:
            pass

def hasCompleteUniqueMdlPointEmitAttributes(mesh: bpy.types.Mesh) -> bool:
    if mesh is None:
        return False
    try:
        vertex_count = len(mesh.vertices)
    except Exception:
        return False
    if vertex_count <= 0:
        return False

    required_names = (
        "bleeds_mdl_point_source_emit_index",
        "bleeds_mdl_point_source_export_vertex_index",
        "bleeds_mdl_point_source_strip_index",
        "bleeds_mdl_point_source_strip_vertex_index",
    )

    for name in required_names:
        attr = getMdlIntAttribute(mesh, name)
        if attr is None:
            return False
        try:
            if len(attr.data) < vertex_count:
                return False
        except Exception:
            return False

    emit_attr = getMdlIntAttribute(mesh, "bleeds_mdl_point_source_emit_index")
    export_attr = getMdlIntAttribute(mesh, "bleeds_mdl_point_source_export_vertex_index")
    if emit_attr is None or export_attr is None:
        return False

    seen_emit = set()
    seen_export = set()
    for vertex in mesh.vertices:
        vi = int(vertex.index)
        try:
            emit_index = int(emit_attr.data[vi].value)
            export_index = int(export_attr.data[vi].value)
        except Exception:
            return False
        if emit_index < 0 or emit_index >= vertex_count:
            return False
        if export_index < 0 or export_index >= vertex_count:
            return False
        if emit_index in seen_emit or export_index in seen_export:
            return False
        seen_emit.add(emit_index)
        seen_export.add(export_index)

    return len(seen_emit) == vertex_count and len(seen_export) == vertex_count

def stampMdlPointVertexStreamAttributesForExport(mesh_obj: bpy.types.Object, export_part_index: int) -> bool:
    if mesh_obj is None or getattr(mesh_obj, "type", None) != 'MESH':
        return False

    mesh = getattr(mesh_obj, "data", None)
    if mesh is None:
        return False

    try:
        mesh.update(calc_edges=True)
    except Exception:
        try:
            mesh.update()
        except Exception:
            pass

    try:
        vertex_count = len(mesh.vertices)
    except Exception:
        vertex_count = 0
    if vertex_count <= 0:
        return False

    point_emit = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_source_emit_index", 'POINT')
    point_export = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_source_export_vertex_index", 'POINT')
    point_strip = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_source_strip_index", 'POINT')
    point_strip_vertex = ensureMdlIntAttribute(mesh, "bleeds_mdl_point_source_strip_vertex_index", 'POINT')

    had_complete_unique = hasCompleteUniqueMdlPointEmitAttributes(mesh)

    if not had_complete_unique:
        for vertex in mesh.vertices:
            vi = int(vertex.index)
            setMdlIntAttributeValue(point_emit, vi, vi)
            setMdlIntAttributeValue(point_export, vi, vi)
            setMdlIntAttributeValue(point_strip, vi, 0)
            setMdlIntAttributeValue(point_strip_vertex, vi, vi)

    try:
        part_index_prop = readIdProp(mesh_obj, "bleeds_mdl_part_index", None)
        if part_index_prop is None:
            part_index_prop = readIdProp(mesh, "bleeds_mdl_source_part_index", None)
        if part_index_prop is None:
            part_index_prop = int(export_part_index)
        attribute_mode = "POINT_IMPORTED_SOURCE_PRESERVED" if had_complete_unique else "POINT_IDENTITY_STAMPED_TOPOLOGY_NOT_PROVEN"
        mesh["bleeds_mdl_vertex_stream_attribute_mode"] = attribute_mode
        mesh["bleeds_mdl_vertex_stream_attribute_count"] = int(vertex_count)
        mesh["bleeds_mdl_vertex_stream_attribute_rebuilt"] = 0 if had_complete_unique else 1
        mesh["bleeds_mdl_source_part_vertex_count"] = int(vertex_count)
        mesh["bleeds_mdl_source_part_index"] = int(part_index_prop)
        mesh_obj["bleeds_mdl_vertex_stream_attribute_mode"] = attribute_mode
        mesh_obj["bleeds_mdl_vertex_stream_attribute_count"] = int(vertex_count)
        mesh_obj["bleeds_mdl_vertex_stream_attribute_rebuilt"] = 0 if had_complete_unique else 1
        if readIdProp(mesh_obj, "bleeds_mdl_part_index", None) is None:
            mesh_obj["bleeds_mdl_part_index"] = int(part_index_prop)
    except Exception:
        pass

    return True

def isImportedMdlSemanticMesh(mesh_obj: bpy.types.Object) -> bool:
    return isMdlNativeCoordinateSpaceMesh(mesh_obj)

def getMdlSourceStripCounts(mesh_obj: bpy.types.Object) -> List[int]:
    try:
        mesh = getattr(mesh_obj, "data", None)
        if mesh is None:
            return []
        counts = readIdProp(mesh, "bleeds_mdl_source_strip_counts", None)
        if counts is None:
            counts = readIdProp(mesh_obj, "bleeds_mdl_source_strip_counts", None)
        if counts is None:
            return []
        out = [int(v) for v in list(counts) if int(v) > 0]
        return out
    except Exception:
        return []

def buildPedWriterMaterialNames(root_cache: Dict[str, Any], part_names: List[str], part_headers: List[Dict[str, object]]) -> List[str]:
    names_from_root = []
    try:
        names_from_root = [str(name) for name in list((root_cache or {}).get("material_names") or []) if str(name)]
    except Exception:
        names_from_root = []

    if names_from_root:
        return names_from_root

    unique_names: List[str] = []
    seen: set[str] = set()
    for name in list(part_names or []):
        clean = str(name or "default")
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        unique_names.append(clean)

    if not unique_names:
        unique_names.append("default")

    highest_tex_id = -1
    for header in list(part_headers or []):
        if not isinstance(header, dict):
            continue
        try:
            highest_tex_id = max(highest_tex_id, int(header.get("tex_id", -1)))
        except Exception:
            pass

    while highest_tex_id >= len(unique_names):
        unique_names.append(unique_names[-1])

    return unique_names

def getPointSourceEmitOrder(mesh: bpy.types.Mesh) -> List[int]:
    try:
        attribute = getMeshAttribute(mesh, "bleeds_mdl_point_source_emit_index")
        if attribute is None:
            return list(range(len(mesh.vertices)))
        values: List[Tuple[int, int]] = []
        used = set()
        for vertex in mesh.vertices:
            vertex_index = int(vertex.index)
            if vertex_index >= len(attribute.data):
                return list(range(len(mesh.vertices)))
            emit_index = int(attribute.data[vertex_index].value)
            if emit_index < 0 or emit_index in used:
                return list(range(len(mesh.vertices)))
            used.add(emit_index)
            values.append((emit_index, vertex_index))
        values.sort(key=lambda item: item[0])
        return [vertex_index for _, vertex_index in values]
    except Exception:
        return list(range(len(mesh.vertices)))

def buildVertexLoopLookup(mesh: bpy.types.Mesh) -> Dict[int, int]:
    lookup: Dict[int, int] = {}
    if mesh is None:
        return lookup

    try:
        for loop in mesh.loops:
            vertex_index = int(loop.vertex_index)
            if vertex_index not in lookup:
                lookup[vertex_index] = int(loop.index)
    except Exception:
        return lookup

    return lookup

def getCornerSourceEmitOrder(mesh: bpy.types.Mesh) -> List[int]:
    try:
        attribute = getMeshAttribute(mesh, "bleeds_mdl_corner_source_emit_index")
        if attribute is None:
            return []
        if len(attribute.data) < len(mesh.loops):
            return []

        values: List[Tuple[int, int]] = []
        used = set()
        for loop in mesh.loops:
            loop_index = int(loop.index)
            emit_index = int(attribute.data[loop_index].value)
            if emit_index < 0 or emit_index in used:
                return []
            used.add(emit_index)
            values.append((emit_index, loop_index))

        if not values:
            return []
        values.sort(key=lambda item: item[0])
        return [loop_index for _, loop_index in values]
    except Exception:
        return []

def getPointSourceEmitOrder(mesh: bpy.types.Mesh) -> List[int]:
    try:
        vertex_count = len(mesh.vertices)
    except Exception:
        return []

    fallback = list(range(int(vertex_count)))
    if not fallback:
        return []

    try:
        attribute = getMeshAttribute(mesh, "bleeds_mdl_point_source_emit_index")
        if attribute is None:
            return fallback
        if len(attribute.data) < vertex_count:
            return fallback

        values: List[Tuple[int, int]] = []
        used = set()
        for vertex in mesh.vertices:
            vertex_index = int(vertex.index)
            emit_index = int(attribute.data[vertex_index].value)
            if emit_index < 0 or emit_index in used:
                return fallback
            used.add(emit_index)
            values.append((emit_index, vertex_index))

        if not values:
            return fallback
        values.sort(key=lambda item: (item[0], item[1]))
        return [vertex_index for _, vertex_index in values]
    except Exception:
        return fallback

def readMdlSequenceProperty(owner: Any, key: str) -> List[Any]:
    if owner is None:
        return []
    try:
        if hasattr(owner, "__contains__") and key in owner:
            return list(owner[key])
    except Exception:
        pass
    try:
        value = getattr(owner, key)
        if value is not None:
            return list(value)
    except Exception:
        pass
    return []

def getMdlArmatureObject(mesh_obj: bpy.types.Object) -> Optional[bpy.types.Object]:
    if mesh_obj is None:
        return None
    try:
        if mesh_obj.parent and mesh_obj.parent.type == 'ARMATURE':
            return mesh_obj.parent
    except Exception:
        pass
    try:
        for mod in getattr(mesh_obj, "modifiers", []):
            if getattr(mod, "type", None) == 'ARMATURE' and getattr(mod, "object", None) is not None:
                return mod.object
    except Exception:
        pass
    return None

def readMdlStringListProp(owner: Any, key: str) -> List[str]:
    if owner is None:
        return []
    try:
        if hasattr(owner, "get"):
            value = owner.get(key, [])
        elif hasattr(owner, "__contains__") and key in owner:
            value = owner[key]
        else:
            value = getattr(owner, key, [])
    except Exception:
        return []
    try:
        return [str(item) for item in list(value or [])]
    except Exception:
        return []

def readMdlIntListProp(owner: Any, key: str) -> List[int]:
    if owner is None:
        return []
    try:
        if hasattr(owner, "get"):
            value = owner.get(key, [])
        elif hasattr(owner, "__contains__") and key in owner:
            value = owner[key]
        else:
            value = getattr(owner, key, [])
    except Exception:
        return []
    out: List[int] = []
    try:
        for item in list(value or []):
            try:
                out.append(int(item))
            except Exception:
                out.append(0)
    except Exception:
        return []
    return out

def addMdlNameAlias(name_to_node: Dict[str, int], raw_name: str, node_index: int) -> None:
    name = str(raw_name or "")
    if not name:
        return
    idx = int(node_index)
    aliases = {name, name.lower()}
    try:
        canon_name = str(mdl_lib.canon_frame_name(name))
        aliases.add(canon_name)
        aliases.add(canon_name.lower())
    except Exception:
        pass
    for prefix in ("bip01 ", "bip01_", "bip01-"):
        lower_name = name.lower()
        if lower_name.startswith(prefix):
            stripped = name[len(prefix):]
            aliases.add(stripped)
            aliases.add(stripped.lower())
            try:
                canon_stripped = str(mdl_lib.canon_frame_name(stripped))
                aliases.add(canon_stripped)
                aliases.add(canon_stripped.lower())
            except Exception:
                pass
    for alias in aliases:
        if alias and alias not in name_to_node:
            name_to_node[alias] = idx

def getMdlImportTypeFromOwners(mesh_obj: Optional[bpy.types.Object] = None, root_obj: Optional[bpy.types.Object] = None) -> Optional[int]:
    owners: List[Any] = []
    if root_obj is None and mesh_obj is not None:
        root_obj = find_mdl_root_from_object(mesh_obj)
    arm_obj = getMdlArmatureObject(mesh_obj) if mesh_obj is not None else None
    for owner in (
        root_obj,
        arm_obj,
        getattr(arm_obj, "data", None) if arm_obj is not None else None,
        mesh_obj,
        getattr(mesh_obj, "data", None) if mesh_obj is not None else None,
    ):
        if owner is not None and owner not in owners:
            owners.append(owner)
    for owner in owners:
        try:
            value = readIdProp(owner, "bleeds_mdl_import_type", None)
            if value is not None:
                return int(value)
        except Exception:
            pass
        try:
            if hasattr(owner, "bleeds_mdl_import_type"):
                return int(getattr(owner, "bleeds_mdl_import_type"))
        except Exception:
            pass
    return None

def getMdlCanonicalCompactPedNames(import_type: Optional[int] = None, prefer_vcs: bool = True) -> List[str]:
    try:
        import_type_i = int(import_type) if import_type is not None else None
    except Exception:
        import_type_i = None

    if import_type_i in (0, 1) and not prefer_vcs:
        names = list(getattr(mdl_lib, "commonBoneNamesLCS", []) or getattr(mdl_lib, "commonBoneOrder", []))
    elif import_type_i in (0, 1):
        names = list(getattr(mdl_lib, "commonBoneNamesLCS", []) or getattr(mdl_lib, "commonBoneOrder", []))
    else:
        names = list(getattr(mdl_lib, "commonBoneNamesVCS", []) or getattr(mdl_lib, "commonBoneOrderVCS", []))
        if not names:
            names = list(getattr(mdl_lib, "commonBoneOrder", []))
    return [str(name) for name in names]

def buildMdlCanonicalCompactNameToNodeIndex(import_type: Optional[int] = None, prefer_vcs: bool = True) -> Dict[str, int]:
    name_to_node: Dict[str, int] = {}
    for node_index, bone_name in enumerate(getMdlCanonicalCompactPedNames(import_type, prefer_vcs=prefer_vcs)):
        addMdlNameAlias(name_to_node, str(bone_name), int(node_index))
        addMdlNameAlias(name_to_node, f"bone_{node_index}", int(node_index))
        addMdlNameAlias(name_to_node, f"bone_{node_index:02d}", int(node_index))
    return name_to_node

def buildMdlCanonicalCompactNodeIndexToName(import_type: Optional[int] = None, prefer_vcs: bool = True) -> Dict[int, str]:
    return {int(i): str(name) for i, name in enumerate(getMdlCanonicalCompactPedNames(import_type, prefer_vcs=prefer_vcs))}

def buildMdlCanonicalPedAnimIdByName(import_type: Optional[int] = None) -> Dict[str, int]:
    try:
        import_type_i = int(import_type) if import_type is not None else None
    except Exception:
        import_type_i = None

    if import_type_i in (0, 1):
        raw_pairs = [
            ("root", 0), ("pelvis", 1), ("spine", 2), ("spine1", 3), ("neck", 4), ("head", 5), ("jaw", 0xFF),
            ("bip01_r_clavicle", 21), ("r_upperarm", 22), ("r_forearm", 23), ("r_hand", 24), ("r_finger", 25),
            ("bip01_l_clavicle", 31), ("l_upperarm", 32), ("l_forearm", 33), ("l_hand", 34), ("l_finger", 35),
            ("l_thigh", 41), ("l_calf", 42), ("l_foot", 43), ("l_toe0", 0xFF),
            ("r_thigh", 51), ("r_calf", 52), ("r_foot", 53), ("r_toe0", 0xFF),
        ]
    else:
        raw_pairs = [
            ("root", 0), ("pelvis", 1), ("spine", 2), ("spine1", 3), ("neck", 4), ("head", 5), ("jaw", 0xFF),
            ("bip01_l_clavicle", 31), ("l_upperarm", 32), ("l_forearm", 33), ("l_hand", 34), ("l_finger", 35),
            ("bip01_r_clavicle", 21), ("r_upperarm", 22), ("r_forearm", 23), ("r_hand", 24), ("r_finger", 25),
            ("l_thigh", 41), ("l_calf", 42), ("l_foot", 43), ("l_toe0", 0xFF),
            ("r_thigh", 51), ("r_calf", 52), ("r_foot", 53), ("r_toe0", 0xFF),
        ]

    out: Dict[str, int] = {}
    for raw_name, anim_id in raw_pairs:
        addMdlNameAlias(out, str(raw_name), int(anim_id) & 0xFF)
    return out

def buildMdlCanonicalPedNodeToAnimId(import_type: Optional[int] = None, prefer_vcs: bool = True) -> Dict[int, int]:
    name_to_anim = buildMdlCanonicalPedAnimIdByName(import_type)
    node_to_name = buildMdlCanonicalCompactNodeIndexToName(import_type, prefer_vcs=prefer_vcs)
    node_to_anim: Dict[int, int] = {}
    for node_index, raw_name in node_to_name.items():
        candidates = [str(raw_name), str(raw_name).lower()]
        try:
            canon = str(mdl_lib.canon_frame_name(raw_name))
            candidates.extend([canon, canon.lower()])
        except Exception:
            pass
        anim_id = None
        for candidate in candidates:
            if candidate in name_to_anim:
                anim_id = int(name_to_anim[candidate]) & 0xFF
                break
        if anim_id is None:
            anim_id = 0xFF
        node_to_anim[int(node_index)] = int(anim_id) & 0xFF
    return node_to_anim

def writeMdlCanonicalPedIdentityMapProps(owner: Any, mesh_obj: Optional[bpy.types.Object], root_obj: Optional[bpy.types.Object]) -> None:
    if owner is None:
        return
    try:
        import_type = getMdlImportTypeFromOwners(mesh_obj, root_obj)
    except Exception:
        import_type = None
    try:
        prefer_vcs = detectMdlHierarchyPrefersVcs(mesh_obj, root_obj, [])
    except Exception:
        prefer_vcs = True
    try:
        node_to_name = buildMdlCanonicalCompactNodeIndexToName(import_type, prefer_vcs=prefer_vcs)
        node_to_anim = buildMdlCanonicalPedNodeToAnimId(import_type, prefer_vcs=prefer_vcs)
        owner["bleeds_mdl_canonical_ped_node_names"] = [str(node_to_name.get(i, f"bone_{i:02d}")) for i in range(len(node_to_name))]
        owner["bleeds_mdl_canonical_ped_node_anim_ids"] = [int(node_to_anim.get(i, 0xFF)) for i in range(len(node_to_name))]
        owner["bleeds_mdl_canonical_ped_identity_policy"] = "NODE_INDEX_SKIN_ANIM_ID_SEPARATED"
    except Exception:
        pass

def getMdlNodeIndexFromNameMap(name_to_node: Dict[str, int], raw_name: str) -> Optional[int]:
    name = str(raw_name or "")
    if not name:
        return None
    candidates = [name, name.lower()]
    try:
        canon_name = str(mdl_lib.canon_frame_name(name))
        candidates.append(canon_name)
        candidates.append(canon_name.lower())
    except Exception:
        pass
    if name.startswith('bip01_'):
        candidates.append(name.replace('bip01_', '', 1))
    else:
        candidates.append('bip01_' + name)
    for candidate in candidates:
        if candidate in name_to_node:
            try:
                return int(name_to_node[candidate])
            except Exception:
                return None
    return None

def doesMdlHierarchyMapLookSuspicious(name_to_node: Dict[str, int]) -> bool:
    if not name_to_node:
        return False

    head_index = getMdlNodeIndexFromNameMap(name_to_node, "head")
    if head_index is not None and int(head_index) != 5:
        return True

    jaw_index = getMdlNodeIndexFromNameMap(name_to_node, "jaw")
    if jaw_index is not None and int(jaw_index) != 6:
        return True

    vcs_expected = {
        "root": 0,
        "pelvis": 1,
        "spine": 2,
        "spine1": 3,
        "neck": 4,
        "bip01_l_clavicle": 7,
        "bip01_r_clavicle": 12,
        "l_thigh": 17,
        "r_thigh": 21,
        "r_foot": 23,
        "r_toe0": 24,
    }
    checked = 0
    mismatched = 0
    for bone_name, expected_index in vcs_expected.items():
        node_index = getMdlNodeIndexFromNameMap(name_to_node, bone_name)
        if node_index is None:
            continue
        checked += 1
        if int(node_index) != int(expected_index):
            mismatched += 1
    if checked >= 8 and mismatched >= 4:
        return True

    return False

def buildMdlHierarchyNameMapFromArmatureBoneProperties(arm_obj: Optional[bpy.types.Object]) -> Dict[str, int]:
    name_to_node: Dict[str, int] = {}
    if arm_obj is None:
        return name_to_node
    try:
        bones = list(getattr(getattr(arm_obj, "data", None), "bones", []) or [])
    except Exception:
        bones = []
    for bone in bones:
        raw_name = str(getattr(bone, "name", "") or "")
        if not raw_name:
            continue
        node_index = None
        for key in ("bleeds_mdl_hierarchy_node_index", "hierarchy_node_index", "node_index"):
            try:
                if key in bone:
                    node_index = int(bone[key])
                    break
            except Exception:
                pass
        if node_index is None:
            continue
        addMdlNameAlias(name_to_node, raw_name, int(node_index))
        addMdlNameAlias(name_to_node, f"bone_{int(node_index)}", int(node_index))
        addMdlNameAlias(name_to_node, f"bone_{int(node_index):02d}", int(node_index))
    return name_to_node

def buildMdlHierarchyNameMapFromOwner(owner: Any) -> Dict[str, int]:
    name_to_node: Dict[str, int] = {}
    if owner is None:
        return name_to_node
    names = readMdlStringListProp(owner, "bleeds_mdl_hierarchy_node_names")
    if not names:
        frame_names = readMdlStringListProp(owner, "bleeds_mdl_frame_names")
        if frame_names:
            names = [str(name) for name in frame_names if "base" not in str(name).lower()]
    if not names:
        return name_to_node
    node_indices = readMdlIntListProp(owner, "bleeds_mdl_hierarchy_node_indices")
    for i, raw_name in enumerate(names):
        if i < len(node_indices):
            node_index = int(node_indices[i])
        else:
            node_index = int(i)
        addMdlNameAlias(name_to_node, raw_name, node_index)
        addMdlNameAlias(name_to_node, f"bone_{node_index}", node_index)
        addMdlNameAlias(name_to_node, f"bone_{node_index:02d}", node_index)
    return name_to_node

def detectMdlHierarchyPrefersVcs(mesh_obj: Optional[bpy.types.Object] = None, root_obj: Optional[bpy.types.Object] = None, maps: Optional[List[Dict[str, int]]] = None) -> bool:
    import_type = getMdlImportTypeFromOwners(mesh_obj, root_obj)
    if import_type in (2, 3):
        return True
    if import_type in (0, 1):
        return False
    for name_to_node in list(maps or []):
        if getMdlNodeIndexFromNameMap(name_to_node, "jaw") is not None:
            return True
    return True

def readMdlArmatureBoneHierarchyNodeIndex(arm_obj: Optional[bpy.types.Object], bone_name: str) -> Optional[int]:
    if arm_obj is None or not bone_name:
        return None
    try:
        arm_bone = arm_obj.data.bones.get(bone_name)
    except Exception:
        arm_bone = None
    if arm_bone is None:
        try:
            canon_name = str(mdl_lib.canon_frame_name(bone_name))
        except Exception:
            canon_name = str(bone_name)
        try:
            for candidate in list(arm_obj.data.bones):
                candidate_name = str(getattr(candidate, "name", "") or "")
                try:
                    candidate_canon = str(mdl_lib.canon_frame_name(candidate_name))
                except Exception:
                    candidate_canon = candidate_name
                if candidate_name == bone_name or candidate_name.lower() == bone_name.lower() or candidate_canon == canon_name:
                    arm_bone = candidate
                    break
        except Exception:
            arm_bone = None
    if arm_bone is None:
        return None
    for key in ("bleeds_mdl_hierarchy_node_index", "hierarchy_node_index", "node_index"):
        try:
            if key in arm_bone:
                node_index = int(arm_bone[key])
                if node_index >= 0:
                    return node_index
        except Exception:
            pass
    return None

def buildMdlHierarchyNameToNodeIndex(mesh_obj: bpy.types.Object, root_obj: Optional[bpy.types.Object] = None) -> Dict[str, int]:
    if root_obj is None and mesh_obj is not None:
        root_obj = find_mdl_root_from_object(mesh_obj)
    arm_obj = getMdlArmatureObject(mesh_obj)

    candidate_maps: List[Dict[str, int]] = []

    armature_bone_map = buildMdlHierarchyNameMapFromArmatureBoneProperties(arm_obj)
    if armature_bone_map:
        candidate_maps.append(armature_bone_map)
        if not doesMdlHierarchyMapLookSuspicious(armature_bone_map):
            return armature_bone_map

    owners: List[Any] = []
    for owner in (
        getattr(arm_obj, "data", None) if arm_obj is not None else None,
        arm_obj,
        root_obj,
        mesh_obj,
        getattr(mesh_obj, "data", None) if mesh_obj is not None else None,
    ):
        if owner is not None and owner not in owners:
            owners.append(owner)

    for owner in owners:
        owner_map = buildMdlHierarchyNameMapFromOwner(owner)
        if not owner_map:
            continue
        candidate_maps.append(owner_map)
        if doesMdlHierarchyMapLookSuspicious(owner_map):
            try:
                owner["bleeds_mdl_rejected_stale_hierarchy_node_map"] = True
            except Exception:
                pass
            continue
        return owner_map

    import_type = getMdlImportTypeFromOwners(mesh_obj, root_obj)
    prefer_vcs = detectMdlHierarchyPrefersVcs(mesh_obj, root_obj, candidate_maps)
    canonical_map = buildMdlCanonicalCompactNameToNodeIndex(import_type, prefer_vcs=prefer_vcs)
    return canonical_map

def buildMdlCanonicalNameToBoneIndex(import_type: Optional[int]) -> Dict[str, int]:

    return buildMdlCanonicalPedAnimIdByName(import_type)

def resolveMdlVertexGroupBoneIndex(
    vg_name: str,
    *,
    hierarchy_name_to_node: Dict[str, int],
    canonical_name_to_bone: Dict[str, int],
    arm_obj: Optional[bpy.types.Object],
) -> Optional[int]:
    name = str(vg_name or "")
    if not name:
        return None

    names_to_try = expandMdlVertexGroupNameVariants(name)

    armature_node_index = readMdlArmatureBoneHierarchyNodeIndex(arm_obj, name)
    if armature_node_index is not None:
        return int(armature_node_index)

    normalized_hierarchy = buildNormalizedMdlNameLookup(hierarchy_name_to_node)
    for candidate in names_to_try:
        if candidate in hierarchy_name_to_node:
            return int(hierarchy_name_to_node[candidate])
        key = normalizeMdlVertexGroupLookupKey(candidate)
        if key in normalized_hierarchy:
            return int(normalized_hierarchy[key])

    match = re.match(r'^bone[_\s-]?(\d+)$', name, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except Exception:
            pass

    if arm_obj is not None:
        try:
            arm_bone = arm_obj.data.bones.get(name)
        except Exception:
            arm_bone = None
        if arm_bone is not None:
            for key in ("bleeds_mdl_hierarchy_node_index", "hierarchy_node_index", "node_index"):
                try:
                    if key in arm_bone:
                        return int(arm_bone[key])
                except Exception:
                    pass

    normalized_canonical = buildNormalizedMdlNameLookup(canonical_name_to_bone)
    for candidate in names_to_try:
        if candidate in canonical_name_to_bone:
            return int(canonical_name_to_bone[candidate])
        key = normalizeMdlVertexGroupLookupKey(candidate)
        if key in normalized_canonical:
            return int(normalized_canonical[key])

    if arm_obj is not None:
        try:
            arm_bone = arm_obj.data.bones.get(name)
        except Exception:
            arm_bone = None
        if arm_bone is not None:
            for key in ("BoneID", "bleeds_hanim_bone_id", "bone_id", "bleeds_bone_id", "bleeds_boneid"):
                try:
                    if key in arm_bone:
                        return int(arm_bone[key])
                except Exception:
                    pass

    return None

def buildMdlVertexGroupBoneMap(mesh_obj: bpy.types.Object, root_obj: Optional[bpy.types.Object] = None) -> Dict[int, int]:
    vgroup_to_bone: Dict[int, int] = {}
    if mesh_obj is None:
        return vgroup_to_bone

    if root_obj is None:
        root_obj = find_mdl_root_from_object(mesh_obj)

    import_type = None
    if root_obj is not None:
        try:
            if hasattr(root_obj, "bleeds_mdl_import_type"):
                import_type = int(root_obj.bleeds_mdl_import_type)
            elif "bleeds_mdl_import_type" in root_obj:
                import_type = int(root_obj["bleeds_mdl_import_type"])
        except Exception:
            import_type = None

    hierarchy_name_to_node = buildMdlHierarchyNameToNodeIndex(mesh_obj, root_obj=root_obj)
    canonical_name_to_bone = buildMdlCanonicalNameToBoneIndex(import_type)
    arm_obj = getMdlArmatureObject(mesh_obj)

    for vg in getattr(mesh_obj, "vertex_groups", []):
        bone_i = resolveMdlVertexGroupBoneIndex(
            str(getattr(vg, "name", "") or ""),
            hierarchy_name_to_node=hierarchy_name_to_node,
            canonical_name_to_bone=canonical_name_to_bone,
            arm_obj=arm_obj,
        )
        if bone_i is not None and int(bone_i) >= 0:
            vgroup_to_bone[int(vg.index)] = int(bone_i)

    return vgroup_to_bone

def isMdlRawSkinTupleEmpty(raw4: Tuple[int, int, int, int]) -> bool:
    try:
        return all((int(v) & 0xFFFFFFFF) == 0 for v in raw4)
    except Exception:
        return True

def fillMissingPointRawSkinByNearest(mesh_obj: bpy.types.Object, mesh: bpy.types.Mesh) -> int:
    if mesh is None:
        return 0

    names = (
        "bleeds_mdl_point_skin_raw0",
        "bleeds_mdl_point_skin_raw1",
        "bleeds_mdl_point_skin_raw2",
        "bleeds_mdl_point_skin_raw3",
    )

    try:
        attrs = [getMeshAttribute(mesh, name) for name in names]
    except Exception:
        return 0
    if any(attr is None for attr in attrs):
        return 0

    try:
        vertex_count = len(mesh.vertices)
    except Exception:
        return 0
    if vertex_count <= 0:
        return 0

    raw_by_vertex: List[Tuple[int, int, int, int]] = []
    source_vertices: List[Tuple[int, Tuple[int, int, int, int]]] = []
    missing_vertices: List[int] = []

    for vertex_index in range(vertex_count):
        raw4: List[int] = []
        for attr in attrs:
            try:
                value = int(attr.data[vertex_index].value) & 0xFFFFFFFF
            except Exception:
                value = 0
            raw4.append(value)
        raw_tuple = (raw4[0], raw4[1], raw4[2], raw4[3])
        raw_by_vertex.append(raw_tuple)
        if isMdlRawSkinTupleEmpty(raw_tuple):
            missing_vertices.append(vertex_index)
        else:
            source_vertices.append((vertex_index, raw_tuple))

    if not source_vertices or not missing_vertices:
        return 0

    copied = 0
    try:
        from mathutils.kdtree import KDTree
        kd = KDTree(len(source_vertices))
        source_by_kd_index: List[Tuple[int, Tuple[int, int, int, int]]] = []
        for kd_index, (vertex_index, raw_tuple) in enumerate(source_vertices):
            kd.insert(mesh.vertices[int(vertex_index)].co, int(kd_index))
            source_by_kd_index.append((int(vertex_index), raw_tuple))
        kd.balance()

        for vertex_index in missing_vertices:
            _co, kd_index, _dist = kd.find(mesh.vertices[int(vertex_index)].co)
            _source_index, raw_tuple = source_by_kd_index[int(kd_index)]
            for attr_index, attr in enumerate(attrs):
                try:
                    attr.data[int(vertex_index)].value = int(raw_tuple[attr_index]) & 0xFFFFFFFF
                except Exception:
                    pass
            copied += 1
    except Exception:
        for vertex_index in missing_vertices:
            best_raw: Optional[Tuple[int, int, int, int]] = None
            best_dist = 1.0e30
            try:
                target_co = mesh.vertices[int(vertex_index)].co
            except Exception:
                continue
            for source_index, raw_tuple in source_vertices:
                try:
                    dist = (mesh.vertices[int(source_index)].co - target_co).length_squared
                except Exception:
                    continue
                if dist < best_dist:
                    best_dist = dist
                    best_raw = raw_tuple
            if best_raw is None:
                continue
            for attr_index, attr in enumerate(attrs):
                try:
                    attr.data[int(vertex_index)].value = int(best_raw[attr_index]) & 0xFFFFFFFF
                except Exception:
                    pass
            copied += 1

    if copied:
        try:
            mesh["bleeds_mdl_raw_skin_nearest_filled"] = int(copied)
        except Exception:
            pass
        try:
            mesh_obj["bleeds_mdl_raw_skin_nearest_filled"] = int(copied)
        except Exception:
            pass
    return copied

def readImportedSkinRawDwords(owner: Any) -> List[Tuple[int, int, int, int]]:
    values = readMdlSequenceProperty(owner, "bleeds_imported_skin_raw_dword_flat")
    if not values:
        return []

    unsigned_values: List[int] = []
    for value in values:
        try:
            unsigned_values.append(int(value) & 0xFFFFFFFF)
        except Exception:
            unsigned_values.append(0)

    out: List[Tuple[int, int, int, int]] = []
    for index in range(0, len(unsigned_values) - 3, 4):
        out.append((
            unsigned_values[index + 0] & 0xFFFFFFFF,
            unsigned_values[index + 1] & 0xFFFFFFFF,
            unsigned_values[index + 2] & 0xFFFFFFFF,
            unsigned_values[index + 3] & 0xFFFFFFFF,
        ))
    return out

def readImportedSkinRawDwordsFromPointAttributes(mesh: bpy.types.Mesh) -> List[Tuple[int, int, int, int]]:
    if mesh is None:
        return []
    names = (
        "bleeds_mdl_point_skin_raw0",
        "bleeds_mdl_point_skin_raw1",
        "bleeds_mdl_point_skin_raw2",
        "bleeds_mdl_point_skin_raw3",
    )
    try:
        attrs = [getMeshAttribute(mesh, name) for name in names]
    except Exception:
        return []
    if any(attr is None for attr in attrs):
        return []

    try:
        vertex_count = len(mesh.vertices)
    except Exception:
        return []
    if vertex_count <= 0:
        return []

    for attr in attrs:
        try:
            if len(attr.data) < vertex_count:
                return []
        except Exception:
            return []

    out: List[Tuple[int, int, int, int]] = []
    any_nonzero = False
    for vertex_index in range(vertex_count):
        raw4 = []
        for attr in attrs:
            try:
                value = int(attr.data[vertex_index].value) & 0xFFFFFFFF
            except Exception:
                value = 0
            if value:
                any_nonzero = True
            raw4.append(value)
        out.append((raw4[0], raw4[1], raw4[2], raw4[3]))

    if not any_nonzero:
        return []
    return out

def chooseImportedSkinRawDwords(mesh_obj: bpy.types.Object, mesh: bpy.types.Mesh) -> List[Tuple[int, int, int, int]]:
    allow_roundtrip = False
    try:
        if bool(readIdProp(mesh_obj, "bleeds_mdl_allow_imported_skin_raw_roundtrip", False)):
            allow_roundtrip = True
    except Exception:
        pass
    try:
        if mesh is not None and bool(readIdProp(mesh, "bleeds_mdl_allow_imported_skin_raw_roundtrip", False)):
            allow_roundtrip = True
    except Exception:
        pass

    if not allow_roundtrip:
        try:
            if mesh_obj is not None:
                mesh_obj["bleeds_mdl_export_skin_source"] = "LIVE_VERTEX_GROUPS_NO_RAW_ROUNDTRIP"
        except Exception:
            pass
        try:
            if mesh is not None:
                mesh["bleeds_mdl_export_skin_source"] = "LIVE_VERTEX_GROUPS_NO_RAW_ROUNDTRIP"
        except Exception:
            pass
        return []

    try:
        source_mesh = getattr(mesh_obj, "data", None)
    except Exception:
        source_mesh = None

    from_attributes: List[Tuple[int, int, int, int]] = []
    try:
        if source_mesh is not None:
            from_attributes = readImportedSkinRawDwordsFromPointAttributes(source_mesh)
    except Exception:
        from_attributes = []
    if not from_attributes:
        try:
            if mesh is not None and mesh is not source_mesh:
                from_attributes = readImportedSkinRawDwordsFromPointAttributes(mesh)
        except Exception:
            from_attributes = []
    if from_attributes:
        try:
            mesh_obj["bleeds_mdl_export_skin_source"] = "EXPLICIT_RAW_ROUNDTRIP_POINT_ATTRIBUTES"
        except Exception:
            pass
        return from_attributes

    flat_raw = readImportedSkinRawDwords(mesh_obj)
    if not flat_raw and mesh is not None:
        flat_raw = readImportedSkinRawDwords(mesh)
    if flat_raw:
        try:
            mesh_obj["bleeds_mdl_export_skin_source"] = "EXPLICIT_RAW_ROUNDTRIP_FLAT_PROPERTY"
        except Exception:
            pass
        return flat_raw

    return []

SKIN_NODE_ATTRIBUTE_NAMES = (
    "bleeds_skin_node_0",
    "bleeds_skin_node_1",
    "bleeds_skin_node_2",
    "bleeds_skin_node_3",
)
SKIN_WEIGHT_ATTRIBUTE_NAMES = (
    "bleeds_skin_weight_0",
    "bleeds_skin_weight_1",
    "bleeds_skin_weight_2",
    "bleeds_skin_weight_3",
)

def ensureMdlAttribute(mesh: bpy.types.Mesh, name: str, data_type: str, domain: str = 'POINT') -> Any:
    if mesh is None:
        return None
    domain_key = str(domain or 'POINT').upper().strip()
    data_type_key = str(data_type or 'INT').upper().strip()
    try:
        attr = getMeshAttribute(mesh, name)
    except Exception:
        attr = None
    if attr is not None:
        try:
            existing_domain = str(getattr(attr, 'domain', '') or '').upper().strip()
            existing_type = str(getattr(attr, 'data_type', '') or '').upper().strip()
        except Exception:
            existing_domain = domain_key
            existing_type = data_type_key
        if (existing_domain and existing_domain != domain_key) or (existing_type and existing_type != data_type_key):
            try:
                removeMeshAttribute(mesh, attr)
                attr = None
            except Exception:
                return attr
    if attr is None:
        try:
            attr = ensureMeshAttribute(mesh, name, data_type_key, domain_key)
        except Exception:
            return None
    return attr

def getMdlPointIntAttribute(mesh: bpy.types.Mesh, name: str) -> Any:
    return ensureMdlAttribute(mesh, name, 'INT', 'POINT')

def getMdlPointFloatAttribute(mesh: bpy.types.Mesh, name: str) -> Any:
    return ensureMdlAttribute(mesh, name, 'FLOAT', 'POINT')

def normalizeMdlSkinPairs(pairs: List[Tuple[int, float]]) -> List[Tuple[int, float]]:
    cleaned: List[Tuple[int, float]] = []
    for node_index, weight in list(pairs or []):
        try:
            node_i = int(node_index)
            weight_f = float(weight)
        except Exception:
            continue
        if node_i < 0 or weight_f <= 1.0e-8:
            continue
        cleaned.append((node_i, weight_f))
    cleaned.sort(key=lambda item: item[1], reverse=True)
    cleaned = cleaned[:4]
    total = sum(weight for _node, weight in cleaned)
    if total > 1.0e-8:
        cleaned = [(node, weight / total) for node, weight in cleaned]
    if not cleaned:
        cleaned = [(0, 1.0)]
    return cleaned[:4]

def readMdlSkinPairsFromAttributes(mesh: bpy.types.Mesh, vertex_index: int) -> List[Tuple[int, float]]:
    if mesh is None:
        return []
    try:
        vi = int(vertex_index)
        if vi < 0 or vi >= len(mesh.vertices):
            return []
    except Exception:
        return []

    try:
        node_attrs = [getMeshAttribute(mesh, name) for name in SKIN_NODE_ATTRIBUTE_NAMES]
        weight_attrs = [getMeshAttribute(mesh, name) for name in SKIN_WEIGHT_ATTRIBUTE_NAMES]
    except Exception:
        return []
    if any(attr is None for attr in node_attrs) or any(attr is None for attr in weight_attrs):
        return []

    pairs: List[Tuple[int, float]] = []
    for slot in range(4):
        try:
            node_index = int(node_attrs[slot].data[vi].value)
            weight = float(weight_attrs[slot].data[vi].value)
        except Exception:
            continue
        if weight > 1.0e-8:
            pairs.append((node_index, weight))
    return normalizeMdlSkinPairs(pairs) if pairs else []

def readMdlSkinPairsFromVertexGroups(
    mesh_obj: bpy.types.Object,
    mesh: bpy.types.Mesh,
    vertex_index: int,
    vgroup_to_bone: Dict[int, int],
) -> List[Tuple[int, float]]:
    if mesh_obj is None or mesh is None:
        return []
    try:
        vi = int(vertex_index)
        if vi < 0 or vi >= len(mesh.vertices):
            return []
    except Exception:
        return []

    pairs: List[Tuple[int, float]] = []
    try:
        vertex = mesh.vertices[vi]
        for group_ref in vertex.groups:
            node_index = vgroup_to_bone.get(int(group_ref.group))
            if node_index is None:
                continue
            weight = float(group_ref.weight)
            if weight <= 1.0e-8:
                continue
            pairs.append((int(node_index), weight))
    except Exception:
        return []
    return normalizeMdlSkinPairs(pairs) if pairs else []

def writeMdlSkinPairsToAttributes(mesh: bpy.types.Mesh, vertex_index: int, pairs: List[Tuple[int, float]], source: str, confidence: float = 1.0) -> None:
    if mesh is None:
        return
    try:
        vi = int(vertex_index)
        if vi < 0 or vi >= len(mesh.vertices):
            return
    except Exception:
        return

    pairs = normalizeMdlSkinPairs(pairs)
    node_attrs = [getMdlPointIntAttribute(mesh, name) for name in SKIN_NODE_ATTRIBUTE_NAMES]
    weight_attrs = [getMdlPointFloatAttribute(mesh, name) for name in SKIN_WEIGHT_ATTRIBUTE_NAMES]
    for slot in range(4):
        node = int(pairs[slot][0]) if slot < len(pairs) else 0
        weight = float(pairs[slot][1]) if slot < len(pairs) else 0.0
        try:
            if node_attrs[slot] is not None and vi < len(node_attrs[slot].data):
                node_attrs[slot].data[vi].value = int(node)
        except Exception:
            pass
        try:
            if weight_attrs[slot] is not None and vi < len(weight_attrs[slot].data):
                weight_attrs[slot].data[vi].value = float(weight)
        except Exception:
            pass

    try:
        source_attr = getMdlPointIntAttribute(mesh, "bleeds_skin_source_vertex")
        if source_attr is not None and vi < len(source_attr.data):
            source_attr.data[vi].value = int(vi)
        imported_attr = getMdlPointIntAttribute(mesh, "bleeds_skin_is_imported")
        if imported_attr is not None and vi < len(imported_attr.data):
            imported_attr.data[vi].value = 0 if source != "import" else 1
        modified_attr = getMdlPointIntAttribute(mesh, "bleeds_skin_is_modified")
        if modified_attr is not None and vi < len(modified_attr.data):
            modified_attr.data[vi].value = 1 if source != "import" else 0
        conf_attr = getMdlPointFloatAttribute(mesh, "bleeds_skin_confidence")
        if conf_attr is not None and vi < len(conf_attr.data):
            conf_attr.data[vi].value = float(confidence)
    except Exception:
        pass

def findMdlSkinSourceMeshes(root_obj: Optional[bpy.types.Object], current_obj: bpy.types.Object) -> List[bpy.types.Object]:
    if root_obj is None:
        root_obj = find_mdl_root_from_object(current_obj)
    if root_obj is None:
        return []

    native_sources_only = shouldTransferMdlSkinFromNativeParts(current_obj, root_obj)

    out: List[bpy.types.Object] = []
    try:
        objects = list(bpy.data.objects)
    except Exception:
        objects = []
    for obj in objects:
        if obj is current_obj or getattr(obj, 'type', None) != 'MESH':
            continue
        if find_mdl_root_from_object(obj) is not root_obj:
            continue
        if native_sources_only and not isMdlNativeCoordinateSpaceMesh(obj):
            continue
        mesh = getattr(obj, 'data', None)
        if mesh is None:
            continue
        try:
            if getMeshAttribute(mesh, "bleeds_skin_node_0") is None or getMeshAttribute(mesh, "bleeds_skin_weight_0") is None:
                continue
        except Exception:
            continue
        out.append(obj)
    return out

def filterMdlSkinPairsForAllowedNodes(pairs: List[Tuple[int, float]], allowed_nodes: Optional[set]) -> List[Tuple[int, float]]:
    if not allowed_nodes:
        return normalizeMdlSkinPairs(pairs) if pairs else []
    allowed = {int(v) for v in allowed_nodes}
    filtered: List[Tuple[int, float]] = []
    rejected_weight = 0.0
    kept_weight = 0.0
    for node_index, weight in list(pairs or []):
        try:
            node_i = int(node_index)
            weight_f = float(weight)
        except Exception:
            continue
        if weight_f <= 1.0e-8:
            continue
        if node_i in allowed:
            filtered.append((node_i, weight_f))
            kept_weight += weight_f
        else:
            rejected_weight += weight_f

    if kept_weight <= 1.0e-8:
        return []
    if rejected_weight > 0.0 and kept_weight < 0.25:
        return []
    return normalizeMdlSkinPairs(filtered)

def normalizeMdlVertexGroupLookupKey(name: str) -> str:
    text = str(name or "").strip().lower()
    if not text:
        return ""
    try:
        text = str(mdl_lib.canon_frame_name(text)).strip().lower()
    except Exception:
        pass
    text = text.replace("bip01 ", "bip01_")
    text = text.replace("bip01-", "bip01_")
    text = text.replace("bip01.", "bip01_")
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    text = text.replace("left_", "l_").replace("right_", "r_")
    text = text.replace("_left_", "_l_").replace("_right_", "_r_")
    return text

def expandMdlVertexGroupNameVariants(name: str) -> List[str]:
    base = str(name or "").strip()
    variants: List[str] = []

    def add(value: Any) -> None:
        try:
            value_s = str(value or "").strip()
        except Exception:
            value_s = ""
        if not value_s:
            return
        if value_s not in variants:
            variants.append(value_s)
        lower = value_s.lower()
        if lower and lower not in variants:
            variants.append(lower)
        key = normalizeMdlVertexGroupLookupKey(value_s)
        if key and key not in variants:
            variants.append(key)

    add(base)
    try:
        add(mdl_lib.canon_frame_name(base))
    except Exception:
        pass

    key = normalizeMdlVertexGroupLookupKey(base)
    if key.startswith("bip01_"):
        add(key[6:])
    else:
        add("bip01_" + key)

    dff_aliases = {
        "bip01_pelvis": "pelvis",
        "bip01_spine": "spine",
        "bip01_spine1": "spine1",
        "bip01_neck": "neck",
        "bip01_head": "head",
        "bip01_jaw": "jaw",
        "bip01_l_clavicle": "bip01_l_clavicle",
        "l_clavicle": "bip01_l_clavicle",
        "bip01_r_clavicle": "bip01_r_clavicle",
        "r_clavicle": "bip01_r_clavicle",
        "bip01_l_upperarm": "l_upperarm",
        "bip01_l_forearm": "l_forearm",
        "bip01_l_hand": "l_hand",
        "bip01_l_finger": "l_finger",
        "bip01_r_upperarm": "r_upperarm",
        "bip01_r_forearm": "r_forearm",
        "bip01_r_hand": "r_hand",
        "bip01_r_finger": "r_finger",
        "bip01_l_thigh": "l_thigh",
        "bip01_l_calf": "l_calf",
        "bip01_l_foot": "l_foot",
        "bip01_l_toe0": "l_toe0",
        "bip01_l_toe": "l_toe0",
        "bip01_r_thigh": "r_thigh",
        "bip01_r_calf": "r_calf",
        "bip01_r_foot": "r_foot",
        "bip01_r_toe0": "r_toe0",
        "bip01_r_toe": "r_toe0",
    }
    alias = dff_aliases.get(key)
    if alias:
        add(alias)
    return variants

def buildNormalizedMdlNameLookup(name_to_node: Dict[str, int]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for raw_name, node_index in dict(name_to_node or {}).items():
        for variant in expandMdlVertexGroupNameVariants(str(raw_name)):
            key = normalizeMdlVertexGroupLookupKey(variant)
            if key and key not in out:
                try:
                    out[key] = int(node_index)
                except Exception:
                    pass
    return out

def buildMdlNodeRestWorldMatrices(mesh_obj: Optional[bpy.types.Object], root_obj: Optional[bpy.types.Object]) -> Dict[int, Matrix]:
    node_to_name = buildMdlNodeIndexToHierarchyName(mesh_obj, root_obj=root_obj)
    arm_obj = getMdlArmatureObject(mesh_obj) if mesh_obj is not None else None
    out: Dict[int, Matrix] = {}

    for node_index, raw_name in dict(node_to_name or {}).items():
        try:
            node_i = int(node_index)
        except Exception:
            continue
        name = str(raw_name or "").strip()
        if not name:
            continue
        stored = findMdlStoredFrameWorldMatrix(root_obj, arm_obj, expandMdlVertexGroupNameVariants(name))
        if stored is not None:
            out[node_i] = stored[1].copy()
            continue
        if arm_obj is not None:
            for variant in expandMdlVertexGroupNameVariants(name):
                try:
                    bone = arm_obj.data.bones.get(variant)
                except Exception:
                    bone = None
                if bone is None:
                    continue
                try:
                    out[node_i] = arm_obj.matrix_world @ bone.matrix_local
                    break
                except Exception:
                    pass
    return out

def inferMdlSkinPairsFromRestSkeleton(
    mesh_obj: bpy.types.Object,
    mesh: bpy.types.Mesh,
    vertex_index: int,
    allowed_nodes: Optional[set],
    root_obj: Optional[bpy.types.Object],
) -> List[Tuple[int, float]]:
    if mesh_obj is None or mesh is None:
        return []
    try:
        vi = int(vertex_index)
        if vi < 0 or vi >= len(mesh.vertices):
            return []
        vertex_world = mesh_obj.matrix_world @ mesh.vertices[vi].co
    except Exception:
        return []

    matrices = buildMdlNodeRestWorldMatrices(mesh_obj, root_obj)
    if not matrices:
        return []

    allowed = {int(v) for v in allowed_nodes} if allowed_nodes else set(matrices.keys())
    candidates: List[Tuple[float, int]] = []
    for node_i, matrix in matrices.items():
        if node_i not in allowed:
            continue
        try:
            pos = matrix.to_translation()
            delta = vertex_world - pos
            dist2 = float(delta.x * delta.x + delta.y * delta.y + delta.z * delta.z)
        except Exception:
            continue
        candidates.append((dist2, int(node_i)))
    if not candidates:
        return []
    candidates.sort(key=lambda item: item[0])

    nearest = candidates[:2]
    if len(nearest) == 1:
        return [(nearest[0][1], 1.0)]
    first_dist = max(float(nearest[0][0]), 1.0e-6)
    second_dist = max(float(nearest[1][0]), 1.0e-6)
    if second_dist > first_dist * 4.0:
        return [(nearest[0][1], 1.0)]
    weighted = []
    for dist2, node_i in nearest:
        weighted.append((node_i, 1.0 / max(float(dist2), 1.0e-6)))
    return normalizeMdlSkinPairs(weighted)

def resolveMdlSkinAllowedNodesForObject(mesh_obj: bpy.types.Object, root_obj: Optional[bpy.types.Object] = None) -> Optional[set]:
    if mesh_obj is None:
        return None
    if root_obj is None:
        root_obj = find_mdl_root_from_object(mesh_obj)

    name_to_node = buildMdlHierarchyNameToNodeIndex(mesh_obj, root_obj=root_obj)
    if not name_to_node:
        return None

    text_bits: List[str] = []
    for owner in (mesh_obj, getattr(mesh_obj, 'data', None)):
        if owner is None:
            continue
        for key in (
            'name',
            'bleeds_mdl_part_texture_name',
            'bleeds_mdl_texture_name',
            'bleeds_mdl_material_name',
            'bleeds_mdl_source_material_name',
        ):
            try:
                if key == 'name':
                    value = getattr(owner, 'name', '')
                elif key in owner:
                    value = owner[key]
                else:
                    value = ''
                if value:
                    text_bits.append(str(value))
            except Exception:
                pass
    try:
        for mat in getattr(mesh_obj, 'material_slots', []):
            mat_obj = getattr(mat, 'material', None)
            if mat_obj is not None:
                text_bits.append(str(getattr(mat_obj, 'name', '') or ''))
                try:
                    if 'bleeds_texture_name' in mat_obj:
                        text_bits.append(str(mat_obj['bleeds_texture_name']))
                except Exception:
                    pass
    except Exception:
        pass

    text = ' '.join(text_bits).lower()

    def nodes_for(*names: str) -> set:
        out = set()
        for name in names:
            candidates = [name, name.lower()]
            try:
                canon = str(mdl_lib.canon_frame_name(name))
                candidates.extend([canon, canon.lower()])
            except Exception:
                pass
            if name.startswith('bip01_'):
                candidates.append(name.replace('bip01_', '', 1))
            else:
                candidates.append('bip01_' + name)
            for candidate in candidates:
                if candidate in name_to_node:
                    out.add(int(name_to_node[candidate]))
        return out

    head_nodes = nodes_for('neck', 'head', 'jaw', 'spine1', 'bip01_l_clavicle', 'bip01_r_clavicle')
    torso_nodes = nodes_for('pelvis', 'spine', 'spine1', 'neck', 'bip01_l_clavicle', 'bip01_r_clavicle', 'l_upperarm', 'r_upperarm')
    arm_nodes = nodes_for('bip01_l_clavicle', 'l_upperarm', 'l_forearm', 'l_hand', 'l_finger', 'bip01_r_clavicle', 'r_upperarm', 'r_forearm', 'r_hand', 'r_finger', 'spine1', 'neck')
    left_arm_nodes = nodes_for('bip01_l_clavicle', 'l_upperarm', 'l_forearm', 'l_hand', 'l_finger', 'spine1', 'neck')
    right_arm_nodes = nodes_for('bip01_r_clavicle', 'r_upperarm', 'r_forearm', 'r_hand', 'r_finger', 'spine1', 'neck')
    leg_nodes = nodes_for('pelvis', 'l_thigh', 'l_calf', 'l_foot', 'l_toe0', 'r_thigh', 'r_calf', 'r_foot', 'r_toe0')
    left_leg_nodes = nodes_for('pelvis', 'l_thigh', 'l_calf', 'l_foot', 'l_toe0')
    right_leg_nodes = nodes_for('pelvis', 'r_thigh', 'r_calf', 'r_foot', 'r_toe0')
    left_foot_nodes = nodes_for('l_calf', 'l_foot', 'l_toe0', 'pelvis')
    right_foot_nodes = nodes_for('r_calf', 'r_foot', 'r_toe0', 'pelvis')
    left_hand_nodes = nodes_for('l_forearm', 'l_hand', 'l_finger', 'l_upperarm')
    right_hand_nodes = nodes_for('r_forearm', 'r_hand', 'r_finger', 'r_upperarm')

    try:
        part_index = int(readIdProp(mesh_obj, 'bleeds_mdl_part_index', -1))
    except Exception:
        part_index = -1
    if part_index >= 0:
        if isExplicitCustomPedReplacementMesh(mesh_obj, root_obj):
            part_region_map = {
                0: torso_nodes | arm_nodes | head_nodes,
                1: right_hand_nodes or right_arm_nodes,
                2: right_arm_nodes,
                3: left_arm_nodes,
                4: left_hand_nodes or left_arm_nodes,
                5: leg_nodes | torso_nodes,
                6: head_nodes,
                7: right_foot_nodes or right_leg_nodes,
                8: left_foot_nodes or left_leg_nodes,
                10: head_nodes,
            }
            region = part_region_map.get(part_index)
            return region or None
        if part_index == 10:
            return head_nodes or None
        return None

    if any(token in text for token in ('head', 'face', 'hair', 'jaw')):
        return head_nodes or None
    if any(token in text for token in ('boot', 'shoe', 'foot', 'feet')):
        return leg_nodes or None
    if any(token in text for token in ('trouser', 'pants', 'leg', 'camo')):
        return leg_nodes or None
    if any(token in text for token in ('arm', 'tattoo', 'sleeve', 'hand')):
        if '_l_' in text or 'left' in text:
            return left_arm_nodes or arm_nodes or None
        if '_r_' in text or 'right' in text:
            return right_arm_nodes or arm_nodes or None
        return arm_nodes or None
    if any(token in text for token in ('shirt', 'torso', 'body', 'back', 'chest', 'dtag', 'dogtag')):
        return torso_nodes or None

    return None

def defaultMdlSkinPairsForAllowedNodes(allowed_nodes: Optional[set], mesh_obj: Optional[bpy.types.Object] = None, root_obj: Optional[bpy.types.Object] = None) -> List[Tuple[int, float]]:
    if not allowed_nodes:
        return [(0, 1.0)]
    if mesh_obj is not None:
        name_to_node = buildMdlHierarchyNameToNodeIndex(mesh_obj, root_obj=root_obj)
    else:
        name_to_node = {}

    preferred_names = ('head', 'neck', 'spine1', 'spine', 'pelvis', 'l_upperarm', 'r_upperarm', 'l_thigh', 'r_thigh')
    for name in preferred_names:
        candidates = [name, name.lower()]
        try:
            canon = str(mdl_lib.canon_frame_name(name))
            candidates.extend([canon, canon.lower()])
        except Exception:
            pass
        for candidate in candidates:
            if candidate in name_to_node and int(name_to_node[candidate]) in allowed_nodes:
                return [(int(name_to_node[candidate]), 1.0)]
    return [(int(sorted(allowed_nodes)[0]), 1.0)]

def nearestMdlSkinPairsFromOtherParts(root_obj: Optional[bpy.types.Object], mesh_obj: bpy.types.Object, vertex_co: Vector, allowed_nodes: Optional[set] = None) -> List[Tuple[int, float]]:
    try:
        target_world = mesh_obj.matrix_world @ vertex_co
    except Exception:
        target_world = vertex_co.copy()
    best_pairs: List[Tuple[int, float]] = []
    best_dist = 1.0e30
    for other in findMdlSkinSourceMeshes(root_obj, mesh_obj):
        other_mesh = getattr(other, 'data', None)
        if other_mesh is None:
            continue
        try:
            for vertex in other_mesh.vertices:
                pairs = readMdlSkinPairsFromAttributes(other_mesh, int(vertex.index))
                pairs = filterMdlSkinPairsForAllowedNodes(pairs, allowed_nodes)
                if not pairs:
                    continue
                world_co = other.matrix_world @ vertex.co
                dist = (world_co - target_world).length_squared
                if dist < best_dist:
                    best_dist = float(dist)
                    best_pairs = pairs
        except Exception:
            continue
    return normalizeMdlSkinPairs(best_pairs) if best_pairs else []

def ensureMdlLiveSkinAttributesForMesh(
    mesh_obj: bpy.types.Object,
    mesh: bpy.types.Mesh,
    vgroup_to_bone: Dict[int, int],
    root_obj: Optional[bpy.types.Object] = None,
) -> None:
    if mesh_obj is None or mesh is None:
        return
    try:
        count = len(mesh.vertices)
    except Exception:
        return
    if count <= 0:
        return

    for name in SKIN_NODE_ATTRIBUTE_NAMES:
        getMdlPointIntAttribute(mesh, name)
    for name in SKIN_WEIGHT_ATTRIBUTE_NAMES:
        getMdlPointFloatAttribute(mesh, name)
    getMdlPointIntAttribute(mesh, "bleeds_skin_source_part")
    getMdlPointIntAttribute(mesh, "bleeds_skin_source_vertex")
    getMdlPointIntAttribute(mesh, "bleeds_skin_is_imported")
    getMdlPointIntAttribute(mesh, "bleeds_skin_is_modified")
    getMdlPointFloatAttribute(mesh, "bleeds_skin_confidence")

    allowed_nodes = resolveMdlSkinAllowedNodesForObject(mesh_obj, root_obj=root_obj)
    transfer_from_native = shouldTransferMdlSkinFromNativeParts(mesh_obj, root_obj)

    filled_from_groups = 0
    filled_from_nearest = 0
    filled_from_default = 0
    repaired_region_mismatch = 0
    rejected_node_count = 0
    already_valid = 0
    for vertex in mesh.vertices:
        vi = int(vertex.index)

        if transfer_from_native:

            pairs = nearestMdlSkinPairsFromOtherParts(root_obj, mesh_obj, vertex.co, allowed_nodes=allowed_nodes)
            if pairs:
                writeMdlSkinPairsToAttributes(mesh, vi, pairs, "nearest_native_mdl_surface", 0.95)
                filled_from_nearest += 1
                continue
            pairs = readMdlSkinPairsFromVertexGroups(mesh_obj, mesh, vi, vgroup_to_bone)
            pairs = filterMdlSkinPairsForAllowedNodes(pairs, allowed_nodes)
            if pairs:
                writeMdlSkinPairsToAttributes(mesh, vi, pairs, "canonical_groups_after_native_transfer_miss", 0.9)
                filled_from_groups += 1
                continue
            pairs = inferMdlSkinPairsFromRestSkeleton(mesh_obj, mesh, vi, allowed_nodes, root_obj)
            pairs = filterMdlSkinPairsForAllowedNodes(pairs, allowed_nodes)
            if pairs:
                writeMdlSkinPairsToAttributes(mesh, vi, pairs, "rest_skeleton_inferred_after_native_transfer_miss", 0.55)
                filled_from_nearest += 1
                continue
            pairs = defaultMdlSkinPairsForAllowedNodes(allowed_nodes, mesh_obj, root_obj)
            writeMdlSkinPairsToAttributes(mesh, vi, pairs, "default_after_all_skin_sources_miss", 0.25)
            filled_from_default += 1
            continue

        existing_raw = readMdlSkinPairsFromAttributes(mesh, vi)
        existing = filterMdlSkinPairsForAllowedNodes(existing_raw, allowed_nodes)
        if existing_raw:
            try:
                raw_nodes = [int(node) for node, weight in existing_raw if float(weight) > 1.0e-8]
                kept_nodes = [int(node) for node, weight in existing if float(weight) > 1.0e-8]
                rejected_node_count += max(0, len(raw_nodes) - len(kept_nodes))
            except Exception:
                pass
        if existing:
            if existing != existing_raw:
                writeMdlSkinPairsToAttributes(mesh, vi, existing, "region_filtered", 0.9)
                repaired_region_mismatch += 1
            already_valid += 1
            continue

        if existing_raw and not existing:
            repaired_region_mismatch += 1

        pairs = readMdlSkinPairsFromVertexGroups(mesh_obj, mesh, vi, vgroup_to_bone)
        pairs = filterMdlSkinPairsForAllowedNodes(pairs, allowed_nodes)
        if pairs:
            writeMdlSkinPairsToAttributes(mesh, vi, pairs, "groups", 1.0)
            filled_from_groups += 1
            continue
        pairs = nearestMdlSkinPairsFromOtherParts(root_obj, mesh_obj, vertex.co, allowed_nodes=allowed_nodes)
        if pairs:
            writeMdlSkinPairsToAttributes(mesh, vi, pairs, "nearest_region", 0.75)
            filled_from_nearest += 1
            continue
        pairs = defaultMdlSkinPairsForAllowedNodes(allowed_nodes, mesh_obj, root_obj)
        writeMdlSkinPairsToAttributes(mesh, vi, pairs, "default_region", 0.25)
        filled_from_default += 1

    try:
        mesh["bleeds_mdl_skin_attribute_schema"] = "RSLTANIM_NODE_FLOAT_POINT_V3_COMPACT_NODE_AUTHORITY"
        mesh["bleeds_mdl_export_skin_source_policy"] = "NATIVE_TRANSFER_THEN_CANONICAL_GROUPS_THEN_REST_INFER" if transfer_from_native else "CUSTOM_ATTRIBUTES_THEN_GROUPS"
        mesh["bleeds_mdl_live_skin_attribute_valid_count"] = int(already_valid + filled_from_groups + filled_from_nearest)
        mesh["bleeds_mdl_live_skin_attribute_filled_from_groups"] = int(filled_from_groups)
        mesh["bleeds_mdl_live_skin_attribute_filled_from_nearest"] = int(filled_from_nearest)
        mesh["bleeds_mdl_live_skin_attribute_filled_from_default"] = int(filled_from_default)
        mesh["bleeds_mdl_live_skin_attribute_region_repaired"] = int(repaired_region_mismatch)
        mesh["bleeds_mdl_live_skin_attribute_rejected_node_count"] = int(rejected_node_count)
        if allowed_nodes:
            mesh["bleeds_mdl_live_skin_allowed_nodes"] = [int(v) for v in sorted(allowed_nodes)]
        mesh_obj["bleeds_mdl_skin_attribute_schema"] = "RSLTANIM_NODE_FLOAT_POINT_V3_COMPACT_NODE_AUTHORITY"
        mesh_obj["bleeds_mdl_export_skin_source_policy"] = "NATIVE_TRANSFER_THEN_CANONICAL_GROUPS_THEN_REST_INFER" if transfer_from_native else "CUSTOM_ATTRIBUTES_THEN_GROUPS"
        mesh_obj["bleeds_mdl_live_skin_attribute_filled_from_groups"] = int(filled_from_groups)
        mesh_obj["bleeds_mdl_live_skin_attribute_filled_from_nearest"] = int(filled_from_nearest)
        mesh_obj["bleeds_mdl_live_skin_attribute_filled_from_default"] = int(filled_from_default)
        mesh_obj["bleeds_mdl_live_skin_attribute_region_repaired"] = int(repaired_region_mismatch)
        mesh_obj["bleeds_mdl_live_skin_attribute_rejected_node_count"] = int(rejected_node_count)
        if allowed_nodes:
            mesh_obj["bleeds_mdl_live_skin_allowed_nodes"] = [int(v) for v in sorted(allowed_nodes)]
    except Exception:
        pass

def shouldRewriteMdlCustomPedVertexGroupsForExport(mesh_obj: Optional[bpy.types.Object], root_obj: Optional[bpy.types.Object]) -> bool:
    if mesh_obj is None or getattr(mesh_obj, "type", None) != 'MESH':
        return False
    if not isCustomPedMeshUnderImportedRootForMdlExport(mesh_obj, root_obj):
        return False

    owners: List[Any] = []
    try:
        mesh = getattr(mesh_obj, "data", None)
        if mesh is not None:
            owners.append(mesh)
    except Exception:
        pass
    owners.append(mesh_obj)

    for owner in owners:
        try:
            if bool(readIdProp(owner, "bleeds_mdl_preserve_custom_vertex_groups", False)):
                return False
        except Exception:
            pass
        try:
            mode = str(readIdProp(owner, "bleeds_mdl_vertex_group_rebuild_mode", "") or "").upper().strip()
        except Exception:
            mode = ""
        if mode in {"OFF", "KEEP", "PRESERVE", "CUSTOM", "TRUST_CUSTOM"}:
            return False
        if mode in {"ON", "REBUILD", "EXPORT_SKIN", "NORMALIZE", "LEEDS", "CANONICAL"}:
            return True

    return True

def getMdlCompactNodeNameForVertexGroup(node_index: int, mesh_obj: Optional[bpy.types.Object], root_obj: Optional[bpy.types.Object]) -> str:
    try:
        import_type = getMdlImportTypeFromOwners(mesh_obj, root_obj)
    except Exception:
        import_type = None
    try:
        prefer_vcs = detectMdlHierarchyPrefersVcs(mesh_obj, root_obj, [])
    except Exception:
        prefer_vcs = True
    try:
        node_to_name = buildMdlCanonicalCompactNodeIndexToName(import_type, prefer_vcs=prefer_vcs)
        name = node_to_name.get(int(node_index))
        if name:
            return str(name)
    except Exception:
        pass
    return f"bone_{int(node_index):02d}"

def clearMdlVertexGroups(obj: bpy.types.Object) -> None:
    if obj is None:
        return
    try:
        obj.vertex_groups.clear()
        return
    except Exception:
        pass

    try:
        while len(obj.vertex_groups) > 0:
            obj.vertex_groups.remove(obj.vertex_groups[0])
    except Exception:
        pass

def rebuildMdlVertexGroupsFromSkinPairs(
    mesh_obj: bpy.types.Object,
    mesh: bpy.types.Mesh,
    pairs_by_vertex: List[List[Tuple[int, float]]],
    root_obj: Optional[bpy.types.Object],
) -> int:
    if mesh_obj is None or mesh is None:
        return 0

    try:
        vertex_count = len(mesh.vertices)
    except Exception:
        vertex_count = 0
    if vertex_count <= 0:
        return 0

    used_nodes: List[int] = []
    for pairs in pairs_by_vertex:
        for node_index, weight in pairs:
            try:
                node_i = int(node_index)
                weight_f = float(weight)
            except Exception:
                continue
            if weight_f <= 1.0e-8:
                continue
            if node_i not in used_nodes:
                used_nodes.append(node_i)

    used_nodes.sort()
    node_to_group: Dict[int, bpy.types.VertexGroup] = {}
    clearMdlVertexGroups(mesh_obj)

    for node_i in used_nodes:
        group_name = getMdlCompactNodeNameForVertexGroup(node_i, mesh_obj, root_obj)
        try:
            node_to_group[int(node_i)] = mesh_obj.vertex_groups.new(name=group_name)
        except Exception:
            pass

    assigned_vertices = 0
    for vertex_index, pairs in enumerate(pairs_by_vertex):
        if vertex_index < 0 or vertex_index >= vertex_count:
            continue
        clean: List[Tuple[int, float]] = []
        total = 0.0
        for node_index, weight in pairs:
            try:
                node_i = int(node_index)
                weight_f = float(weight)
            except Exception:
                continue
            if weight_f <= 1.0e-8 or node_i not in node_to_group:
                continue
            clean.append((node_i, weight_f))
            total += weight_f
        if total <= 1.0e-8:
            continue
        for node_i, weight_f in clean:
            try:
                node_to_group[node_i].add([int(vertex_index)], float(weight_f) / float(total), 'REPLACE')
            except Exception:
                pass
        assigned_vertices += 1

    try:
        mesh_obj["bleeds_mdl_vertex_groups_rebuilt_from_export_skin"] = True
        mesh_obj["bleeds_mdl_vertex_groups_rebuilt_vertex_count"] = int(assigned_vertices)
        mesh_obj["bleeds_mdl_vertex_groups_rebuilt_group_count"] = int(len(node_to_group))
        mesh_obj["bleeds_mdl_vertex_groups_rebuilt_nodes"] = [int(v) for v in used_nodes]
        mesh_obj["bleeds_mdl_vertex_groups_rebuild_policy"] = "CANONICAL_PED_NODE_INDEX_SKIN_AUTHORITY"
        mesh["bleeds_mdl_vertex_groups_rebuilt_from_export_skin"] = True
        mesh["bleeds_mdl_vertex_groups_rebuilt_vertex_count"] = int(assigned_vertices)
        mesh["bleeds_mdl_vertex_groups_rebuilt_group_count"] = int(len(node_to_group))
        mesh["bleeds_mdl_vertex_groups_rebuild_policy"] = "CANONICAL_PED_NODE_INDEX_SKIN_AUTHORITY"
        writeMdlCanonicalPedIdentityMapProps(mesh_obj, mesh_obj, root_obj)
        writeMdlCanonicalPedIdentityMapProps(mesh, mesh_obj, root_obj)
    except Exception:
        pass

    return assigned_vertices

def normalizeMdlCustomPedVertexGroupsForExport(
    mesh_obj: bpy.types.Object,
    root_obj: Optional[bpy.types.Object] = None,
    *,
    mesh: Optional[bpy.types.Mesh] = None,
) -> int:
    if mesh_obj is None or getattr(mesh_obj, "type", None) != 'MESH':
        return 0
    if root_obj is None:
        root_obj = find_mdl_root_from_object(mesh_obj)
    if not shouldRewriteMdlCustomPedVertexGroupsForExport(mesh_obj, root_obj):
        return 0
    if mesh is None:
        mesh = getattr(mesh_obj, "data", None)
    if mesh is None:
        return 0

    vgroup_to_bone = buildMdlVertexGroupBoneMap(mesh_obj, root_obj=root_obj)
    ensureMdlLiveSkinAttributesForMesh(mesh_obj, mesh, vgroup_to_bone, root_obj)

    pairs_by_vertex: List[List[Tuple[int, float]]] = []
    try:
        vertices = list(mesh.vertices)
    except Exception:
        vertices = []
    for vertex in vertices:
        vi = int(getattr(vertex, "index", len(pairs_by_vertex)))
        pairs = getMdlLiveSkinPairsForVertex(mesh_obj, mesh, vi, vgroup_to_bone, root_obj)
        pairs = normalizeMdlSkinPairs(pairs)
        pairs_by_vertex.append(pairs)

    if not pairs_by_vertex:
        return 0

    assigned = rebuildMdlVertexGroupsFromSkinPairs(mesh_obj, mesh, pairs_by_vertex, root_obj)
    try:
        mesh_obj["bleeds_mdl_custom_ped_group_source"] = "NATIVE_TRANSFER_THEN_CANONICAL_GROUPS_THEN_REST_INFER"
        mesh["bleeds_mdl_custom_ped_group_source"] = "NATIVE_TRANSFER_THEN_CANONICAL_GROUPS_THEN_REST_INFER"
        mesh_obj["bleeds_mdl_custom_group_fallback_disabled"] = False
        mesh["bleeds_mdl_custom_group_fallback_disabled"] = False
    except Exception:
        pass
    return assigned

def getMdlLiveSkinPairsForVertex(
    mesh_obj: bpy.types.Object,
    mesh: bpy.types.Mesh,
    vertex_index: int,
    vgroup_to_bone: Dict[int, int],
    root_obj: Optional[bpy.types.Object] = None,
) -> List[Tuple[int, float]]:
    allowed_nodes = resolveMdlSkinAllowedNodesForObject(mesh_obj, root_obj=root_obj)

    if shouldTransferMdlSkinFromNativeParts(mesh_obj, root_obj):
        try:
            if mesh is not None and 0 <= int(vertex_index) < len(mesh.vertices):
                pairs = nearestMdlSkinPairsFromOtherParts(root_obj, mesh_obj, mesh.vertices[int(vertex_index)].co, allowed_nodes=allowed_nodes)
            else:
                pairs = []
        except Exception:
            pairs = []
        if pairs:
            try:
                writeMdlSkinPairsToAttributes(mesh, vertex_index, pairs, "nearest_native_mdl_surface", 0.95)
            except Exception:
                pass
            return pairs

        pairs = readMdlSkinPairsFromVertexGroups(mesh_obj, mesh, vertex_index, vgroup_to_bone)
        pairs = filterMdlSkinPairsForAllowedNodes(pairs, allowed_nodes)
        if pairs:
            try:
                writeMdlSkinPairsToAttributes(mesh, vertex_index, pairs, "canonical_groups_after_native_transfer_miss", 0.9)
            except Exception:
                pass
            return pairs

        pairs = inferMdlSkinPairsFromRestSkeleton(mesh_obj, mesh, vertex_index, allowed_nodes, root_obj)
        pairs = filterMdlSkinPairsForAllowedNodes(pairs, allowed_nodes)
        if pairs:
            try:
                writeMdlSkinPairsToAttributes(mesh, vertex_index, pairs, "rest_skeleton_inferred_after_native_transfer_miss", 0.55)
            except Exception:
                pass
            return pairs

        pairs = defaultMdlSkinPairsForAllowedNodes(allowed_nodes, mesh_obj, root_obj)
        try:
            writeMdlSkinPairsToAttributes(mesh, vertex_index, pairs, "default_after_all_skin_sources_miss", 0.25)
        except Exception:
            pass
        return pairs

    pairs = readMdlSkinPairsFromAttributes(mesh, vertex_index)
    pairs = filterMdlSkinPairsForAllowedNodes(pairs, allowed_nodes)
    if pairs:
        return pairs

    pairs = readMdlSkinPairsFromVertexGroups(mesh_obj, mesh, vertex_index, vgroup_to_bone)
    pairs = filterMdlSkinPairsForAllowedNodes(pairs, allowed_nodes)
    if pairs:
        try:
            writeMdlSkinPairsToAttributes(mesh, vertex_index, pairs, "groups", 1.0)
        except Exception:
            pass
        return pairs
    try:
        if mesh is not None and 0 <= int(vertex_index) < len(mesh.vertices):
            pairs = nearestMdlSkinPairsFromOtherParts(root_obj, mesh_obj, mesh.vertices[int(vertex_index)].co, allowed_nodes=allowed_nodes)
    except Exception:
        pairs = []
    if pairs:
        try:
            writeMdlSkinPairsToAttributes(mesh, vertex_index, pairs, "nearest_region", 0.75)
        except Exception:
            pass
        return pairs
    pairs = defaultMdlSkinPairsForAllowedNodes(allowed_nodes, mesh_obj, root_obj)
    try:
        writeMdlSkinPairsToAttributes(mesh, vertex_index, pairs, "default_region", 0.25)
    except Exception:
        pass
    return pairs

def buildMdlNodeIndexToHierarchyName(mesh_obj: Optional[bpy.types.Object], root_obj: Optional[bpy.types.Object] = None) -> Dict[int, str]:
    if root_obj is None and mesh_obj is not None:
        root_obj = find_mdl_root_from_object(mesh_obj)
    import_type = getMdlImportTypeFromOwners(mesh_obj, root_obj)
    prefer_vcs = True
    name_to_node = buildMdlHierarchyNameToNodeIndex(mesh_obj, root_obj=root_obj) if mesh_obj is not None else {}
    if name_to_node:
        prefer_vcs = detectMdlHierarchyPrefersVcs(mesh_obj, root_obj, [name_to_node])
    out = buildMdlCanonicalCompactNodeIndexToName(import_type, prefer_vcs=prefer_vcs)

    arm_obj = getMdlArmatureObject(mesh_obj) if mesh_obj is not None else None
    armature_map = buildMdlHierarchyNameMapFromArmatureBoneProperties(arm_obj)
    if armature_map and not doesMdlHierarchyMapLookSuspicious(armature_map):
        for bone in list(getattr(getattr(arm_obj, "data", None), "bones", []) or []):
            try:
                node_index = readMdlArmatureBoneHierarchyNodeIndex(arm_obj, str(getattr(bone, "name", "") or ""))
                if node_index is not None:
                    out[int(node_index)] = str(getattr(bone, "name", "") or out.get(int(node_index), f"node_{int(node_index)}"))
            except Exception:
                pass
        return out

    owners: List[Any] = []
    for owner in (
        getattr(arm_obj, "data", None) if arm_obj is not None else None,
        arm_obj,
        root_obj,
        mesh_obj,
        getattr(mesh_obj, "data", None) if mesh_obj is not None else None,
    ):
        if owner is not None and owner not in owners:
            owners.append(owner)
    for owner in owners:
        owner_map = buildMdlHierarchyNameMapFromOwner(owner)
        if not owner_map or doesMdlHierarchyMapLookSuspicious(owner_map):
            continue
        names = readMdlStringListProp(owner, "bleeds_mdl_hierarchy_node_names")
        if not names:
            frame_names = readMdlStringListProp(owner, "bleeds_mdl_frame_names")
            if frame_names:
                names = [str(name) for name in frame_names if "base" not in str(name).lower()]
        node_indices = readMdlIntListProp(owner, "bleeds_mdl_hierarchy_node_indices")
        for i, name in enumerate(names):
            node_index = int(node_indices[i]) if i < len(node_indices) else int(i)
            out[int(node_index)] = str(name)
        return out
    return out

def buildMdlPedSkinExportStats(
    mesh_obj: bpy.types.Object,
    strip: List[mdl_lib.Ps2Vertex],
    sub_strips: List[List[mdl_lib.Ps2Vertex]],
    root_obj: Optional[bpy.types.Object] = None,
) -> Dict[str, object]:
    node_to_name = buildMdlNodeIndexToHierarchyName(mesh_obj, root_obj=root_obj)
    node_usage: Dict[int, int] = {}
    node_weight_sum: Dict[int, float] = {}
    zero_weight_vertices = 0
    invalid_node_vertices = 0
    not_normalized_vertices = 0
    weight_sum_min = 999999.0
    weight_sum_max = -999999.0
    nonzero_weight_min = 999999.0
    nonzero_weight_max = 0.0

    vertices = list(strip or [])
    for vertex in vertices:
        try:
            indices = [int(v) for v in tuple(getattr(vertex, "bone_indices", (0, 0, 0, 0)))[:4]]
            weights = [float(v) for v in tuple(getattr(vertex, "bone_weights", (0.0, 0.0, 0.0, 0.0)))[:4]]
        except Exception:
            indices = [0, 0, 0, 0]
            weights = [0.0, 0.0, 0.0, 0.0]
        pairs = [(indices[i] if i < len(indices) else 0, weights[i] if i < len(weights) else 0.0) for i in range(4)]
        nonzero = [(node, weight) for node, weight in pairs if weight > 1.0e-8]
        if not nonzero:
            zero_weight_vertices += 1
        weight_sum = sum(weight for _node, weight in nonzero)
        weight_sum_min = min(weight_sum_min, weight_sum)
        weight_sum_max = max(weight_sum_max, weight_sum)
        if abs(weight_sum - 1.0) > 0.01:
            not_normalized_vertices += 1
        for node, weight in nonzero:
            if node < 0 or node > 255:
                invalid_node_vertices += 1
                continue
            node_usage[node] = int(node_usage.get(node, 0)) + 1
            node_weight_sum[node] = float(node_weight_sum.get(node, 0.0)) + float(weight)
            nonzero_weight_min = min(nonzero_weight_min, float(weight))
            nonzero_weight_max = max(nonzero_weight_max, float(weight))

    if weight_sum_min == 999999.0:
        weight_sum_min = 0.0
    if weight_sum_max == -999999.0:
        weight_sum_max = 0.0
    if nonzero_weight_min == 999999.0:
        nonzero_weight_min = 0.0

    mesh = getattr(mesh_obj, "data", None) if mesh_obj is not None else None
    def prop_int(owner: Any, key: str) -> int:
        try:
            return int(readIdProp(owner, key, 0) or 0)
        except Exception:
            return 0

    allowed_nodes = []
    try:
        allowed_nodes = [int(v) for v in list(readIdProp(mesh_obj, "bleeds_mdl_live_skin_allowed_nodes", []) or [])]
    except Exception:
        allowed_nodes = []
    if not allowed_nodes and mesh is not None:
        try:
            allowed_nodes = [int(v) for v in list(readIdProp(mesh, "bleeds_mdl_live_skin_allowed_nodes", []) or [])]
        except Exception:
            allowed_nodes = []

    node_usage_rows = []
    for node in sorted(node_usage.keys()):
        node_usage_rows.append({
            "node": int(node),
            "name": str(node_to_name.get(int(node), f"node_{int(node)}")),
            "count": int(node_usage[node]),
            "weight_sum": float(node_weight_sum.get(node, 0.0)),
        })

    return {
        "object_name": str(getattr(mesh_obj, "name", "") or ""),
        "mesh_vertex_count": int(len(getattr(mesh, "vertices", []) or [])) if mesh is not None else 0,
        "emitted_vertex_count": int(len(vertices)),
        "emitted_sub_strip_count": int(sum(1 for sub in list(sub_strips or []) if len(sub) >= 3)),
        "node_usage": node_usage_rows,
        "used_node_count": int(len(node_usage_rows)),
        "allowed_nodes": [int(v) for v in sorted(set(allowed_nodes))],
        "allowed_node_names": [str(node_to_name.get(int(v), f"node_{int(v)}")) for v in sorted(set(allowed_nodes))],
        "attribute_valid_count": prop_int(mesh, "bleeds_mdl_live_skin_attribute_valid_count"),
        "regenerated_from_groups": prop_int(mesh_obj, "bleeds_mdl_live_skin_attribute_filled_from_groups") or prop_int(mesh, "bleeds_mdl_live_skin_attribute_filled_from_groups"),
        "regenerated_from_nearest": prop_int(mesh_obj, "bleeds_mdl_live_skin_attribute_filled_from_nearest") or prop_int(mesh, "bleeds_mdl_live_skin_attribute_filled_from_nearest"),
        "regenerated_from_default": prop_int(mesh_obj, "bleeds_mdl_live_skin_attribute_filled_from_default") or prop_int(mesh, "bleeds_mdl_live_skin_attribute_filled_from_default"),
        "region_repaired_vertices": prop_int(mesh_obj, "bleeds_mdl_live_skin_attribute_region_repaired") or prop_int(mesh, "bleeds_mdl_live_skin_attribute_region_repaired"),
        "rejected_node_count": prop_int(mesh_obj, "bleeds_mdl_live_skin_attribute_rejected_node_count") or prop_int(mesh, "bleeds_mdl_live_skin_attribute_rejected_node_count"),
        "zero_weight_vertices": int(zero_weight_vertices),
        "invalid_node_vertices": int(invalid_node_vertices),
        "not_normalized_vertices": int(not_normalized_vertices),
        "weight_sum_min": float(weight_sum_min),
        "weight_sum_max": float(weight_sum_max),
        "nonzero_weight_min": float(nonzero_weight_min),
        "nonzero_weight_max": float(nonzero_weight_max),
    }

def hasAuthoritativeMdlPointSourceStream(mesh_obj: bpy.types.Object) -> bool:
    if mesh_obj is None or getattr(mesh_obj, "type", None) != 'MESH':
        return False

    mesh = getattr(mesh_obj, "data", None)
    if mesh is None:
        return False

    try:
        vertex_count = len(mesh.vertices)
    except Exception:
        vertex_count = 0
    if vertex_count <= 0:
        return False

    if not hasCompleteUniqueMdlPointEmitAttributes(mesh):
        return False

    rebuilt_values = []
    for owner in (mesh, mesh_obj):
        try:
            value = readIdProp(owner, "bleeds_mdl_vertex_stream_attribute_rebuilt", None)
        except Exception:
            value = None
        if value is not None:
            try:
                rebuilt_values.append(int(value))
            except Exception:
                rebuilt_values.append(1)
    if rebuilt_values and any(value != 0 for value in rebuilt_values):
        return False

    imported_origin = False
    for owner in (mesh, mesh_obj):
        try:
            origin = str(readIdProp(owner, "bleeds_mdl_semantic_attributes_origin", "") or "").upper().strip()
            if origin == "IMPORTED_PS2":
                imported_origin = True
                break
        except Exception:
            pass

    source_counts = getMdlSourceStripCounts(mesh_obj)
    source_count_sum = 0
    try:
        source_count_sum = int(sum(int(value) for value in source_counts))
    except Exception:
        source_count_sum = 0

    source_vertex_count = None
    for owner in (mesh, mesh_obj):
        try:
            value = readIdProp(owner, "bleeds_mdl_source_part_vertex_count", None)
            if value is not None:
                source_vertex_count = int(value)
                break
        except Exception:
            pass

    if source_count_sum > 0 and source_count_sum != vertex_count:
        return False
    if source_vertex_count is not None and int(source_vertex_count) != vertex_count:
        return False

    if imported_origin:
        return True
    if source_counts and source_count_sum == vertex_count:
        return True

    return False

def build_source_point_vertices_world(
    context: bpy.types.Context,
    mesh_obj: bpy.types.Object,
    *,
    use_normals: bool = True,
    root_obj: Optional[bpy.types.Object] = None,
) -> List[mdl_lib.Ps2Vertex]:
    def clamp_u8(x: int) -> int:
        if x < 0:
            return 0
        if x > 255:
            return 255
        return int(x)

    def readVector2List(owner: Any, key: str) -> List[Tuple[float, float]]:
        out: List[Tuple[float, float]] = []
        for item in readMdlSequenceProperty(owner, key):
            try:
                vals = list(item)
                if len(vals) >= 2:
                    out.append((float(vals[0]), float(vals[1])))
            except Exception:
                pass
        return out

    def readVector3List(owner: Any, key: str) -> List[Tuple[float, float, float]]:
        out: List[Tuple[float, float, float]] = []
        for item in readMdlSequenceProperty(owner, key):
            try:
                vals = list(item)
                if len(vals) >= 3:
                    out.append((float(vals[0]), float(vals[1]), float(vals[2])))
            except Exception:
                pass
        return out

    def readColorList(owner: Any, key: str) -> List[Tuple[int, int, int, int]]:
        out: List[Tuple[int, int, int, int]] = []
        for item in readMdlSequenceProperty(owner, key):
            try:
                vals = list(item)
                if len(vals) >= 4:
                    out.append((clamp_u8(int(vals[0])), clamp_u8(int(vals[1])), clamp_u8(int(vals[2])), clamp_u8(int(vals[3]))))
            except Exception:
                pass
        return out

    def getActiveColorLayer(mesh: bpy.types.Mesh):
        if hasattr(mesh, "color_attributes"):
            color_attributes = getattr(mesh, "color_attributes", None)
            if color_attributes and getattr(color_attributes, "active", None):
                return color_attributes.active.data
        vertex_colors = getattr(mesh, "vertex_colors", None)
        if vertex_colors and getattr(vertex_colors, "active", None):
            return vertex_colors.active.data
        return None

    mesh = getBaseMeshForMdlExport(mesh_obj)
    if mesh is None:
        return []

    if not hasAuthoritativeMdlPointSourceStream(mesh_obj):
        return []

    try:
        try:
            mesh.calc_normals_split()
        except Exception:
            try:
                mesh.calc_normals()
            except Exception:
                pass

        vertex_order = getPointSourceEmitOrder(mesh)
        if not vertex_order:
            return []

        uv_layer = mesh.uv_layers.active.data if (mesh.uv_layers.active) else None
        color_layer = getActiveColorLayer(mesh)
        first_loop_for_vertex = buildVertexLoopLookup(mesh)
        imported_uvs = readVector2List(mesh_obj, "bleeds_imported_uvs")
        imported_normals = readVector3List(mesh_obj, "bleeds_imported_normals")
        imported_colors = readColorList(mesh_obj, "bleeds_imported_colors")
        imported_skin_raw = chooseImportedSkinRawDwords(mesh_obj, mesh)

        world_mtx: Matrix = resolveMdlPartExportMatrix(mesh_obj, root_obj)
        normal_mtx: Matrix = world_mtx.to_3x3()

        resolved_root = root_obj
        if resolved_root is None:
            try:
                resolved_root = find_mdl_root(context)
            except Exception:
                resolved_root = None

        import_type = None
        if resolved_root is not None:
            try:
                if hasattr(resolved_root, "bleeds_mdl_import_type"):
                    import_type = int(resolved_root.bleeds_mdl_import_type)
                elif "bleeds_mdl_import_type" in resolved_root:
                    import_type = int(resolved_root["bleeds_mdl_import_type"])
            except Exception:
                import_type = None

        if import_type in (0, 1):
            canonical_bones = list(getattr(mdl_lib, "commonBoneNamesLCS", []) or getattr(mdl_lib, "commonBoneOrder", []))
        elif import_type in (2, 3):
            canonical_bones = list(getattr(mdl_lib, "commonBoneNamesVCS", []) or getattr(mdl_lib, "commonBoneOrderVCS", []))
        else:
            canonical_bones = []

        name_to_bone: Dict[str, int] = {}
        for bone_i, bone_name in enumerate(canonical_bones):
            raw = str(bone_name)
            name_to_bone[raw] = int(bone_i)
            name_to_bone[raw.lower()] = int(bone_i)
            try:
                canon_raw = str(mdl_lib.canon_frame_name(raw))
                name_to_bone[canon_raw] = int(bone_i)
                name_to_bone[canon_raw.replace("bip01_", "")] = int(bone_i)
            except Exception:
                pass

        alias_to_canon = {
            "bip01": "root",
            "bip01_pelvis": "pelvis",
            "bip01_spine": "spine",
            "bip01_spine1": "spine1",
            "bip01_neck": "neck",
            "bip01_head": "head",
            "bip01_jaw": "jaw",
            "bip01_l_clavicle": "bip01_l_clavicle",
            "bip01_l_upperarm": "l_upperarm",
            "bip01_l_forearm": "l_forearm",
            "bip01_l_hand": "l_hand",
            "bip01_l_finger": "l_finger",
            "bip01_r_clavicle": "bip01_r_clavicle",
            "bip01_r_upperarm": "r_upperarm",
            "bip01_r_forearm": "r_forearm",
            "bip01_r_hand": "r_hand",
            "bip01_r_finger": "r_finger",
            "bip01_l_thigh": "l_thigh",
            "bip01_l_calf": "l_calf",
            "bip01_l_foot": "l_foot",
            "bip01_l_toe0": "l_toe0",
            "bip01_r_thigh": "r_thigh",
            "bip01_r_calf": "r_calf",
            "bip01_r_foot": "r_foot",
            "bip01_r_toe0": "r_toe0",
        }
        for alias_name, canon_target in alias_to_canon.items():
            try:
                target_key = str(mdl_lib.canon_frame_name(canon_target))
                if target_key in name_to_bone:
                    name_to_bone[alias_name] = name_to_bone[target_key]
                    name_to_bone[alias_name.lower()] = name_to_bone[target_key]
                    name_to_bone[str(mdl_lib.canon_frame_name(alias_name))] = name_to_bone[target_key]
            except Exception:
                pass

        arm_obj = None
        try:
            if mesh_obj.parent and mesh_obj.parent.type == 'ARMATURE':
                arm_obj = mesh_obj.parent
        except Exception:
            arm_obj = None
        if arm_obj is None:
            try:
                for mod in getattr(mesh_obj, "modifiers", []):
                    if getattr(mod, "type", None) == 'ARMATURE' and getattr(mod, "object", None) is not None:
                        arm_obj = mod.object
                        break
            except Exception:
                arm_obj = None

        vgroup_to_bone: Dict[int, int] = {}
        for vg in getattr(mesh_obj, 'vertex_groups', []):
            bone_i = None
            vg_name = str(getattr(vg, 'name', '') or '')
            if vg_name in name_to_bone:
                bone_i = name_to_bone[vg_name]
            elif vg_name.lower() in name_to_bone:
                bone_i = name_to_bone[vg_name.lower()]
            else:
                try:
                    canon_name = str(mdl_lib.canon_frame_name(vg_name))
                    if canon_name in name_to_bone:
                        bone_i = name_to_bone[canon_name]
                except Exception:
                    pass
                if bone_i is None:
                    m = re.match(r'^bone[_\s-]?(\d+)$', vg_name, re.IGNORECASE)
                    if m:
                        try:
                            bone_i = int(m.group(1))
                        except Exception:
                            bone_i = None
            if bone_i is None and arm_obj is not None:
                try:
                    arm_bone = arm_obj.data.bones.get(vg_name)
                    if arm_bone is not None and "BoneID" in arm_bone:
                        bone_i = int(arm_bone["BoneID"])
                except Exception:
                    bone_i = None
            if bone_i is not None and bone_i >= 0:
                vgroup_to_bone[int(vg.index)] = int(bone_i)

        hierarchy_vgroup_to_bone = buildMdlVertexGroupBoneMap(mesh_obj, root_obj=resolved_root)
        if hierarchy_vgroup_to_bone:
            vgroup_to_bone = hierarchy_vgroup_to_bone
        ensureMdlLiveSkinAttributesForMesh(mesh_obj, mesh, vgroup_to_bone, resolved_root)

        out: List[mdl_lib.Ps2Vertex] = []
        for vertex_index in vertex_order:
            if vertex_index < 0 or vertex_index >= len(mesh.vertices):
                continue

            vert = mesh.vertices[int(vertex_index)]
            wp = world_mtx @ vert.co

            u = 0.0
            vv = 0.0
            if vertex_index < len(imported_uvs):
                u, vv = imported_uvs[int(vertex_index)]
            else:
                loop_index = first_loop_for_vertex.get(int(vertex_index), -1)
                if uv_layer is not None and 0 <= loop_index < len(uv_layer):
                    try:
                        uv = uv_layer[int(loop_index)].uv
                        u = float(uv.x)
                        vv = float(uv.y)
                    except Exception:
                        u = 0.0
                        vv = 0.0

            nx, ny, nz = 0.0, 0.0, 1.0
            if use_normals:
                if vertex_index < len(imported_normals):
                    nx, ny, nz = imported_normals[int(vertex_index)]
                else:
                    try:
                        normal = vert.normal
                        normal_world = (normal_mtx @ normal).normalized()
                        nx = float(normal_world.x)
                        ny = float(normal_world.y)
                        nz = float(normal_world.z)
                    except Exception:
                        nx, ny, nz = 0.0, 0.0, 1.0

            ri = gi = bi = ai = 255
            if vertex_index < len(imported_colors):
                ri, gi, bi, ai = imported_colors[int(vertex_index)]
            else:
                loop_index = first_loop_for_vertex.get(int(vertex_index), -1)
                if color_layer is not None and 0 <= loop_index < len(color_layer):
                    try:
                        color = getattr(color_layer[int(loop_index)], "color", None)
                        if color is not None:
                            ri = clamp_u8(int(round(float(color[0]) * 255.0)))
                            gi = clamp_u8(int(round(float(color[1]) * 255.0)))
                            bi = clamp_u8(int(round(float(color[2]) * 255.0)))
                            ai = clamp_u8(int(round(float(color[3] if len(color) >= 4 else 1.0) * 255.0)))
                    except Exception:
                        ri = gi = bi = ai = 255

            skin_pairs = getMdlLiveSkinPairsForVertex(mesh_obj, mesh, int(vertex_index), vgroup_to_bone, resolved_root)

            bone_indices = [0, 0, 0, 0]
            bone_weights = [0.0, 0.0, 0.0, 0.0]
            for slot_index, (bone_index, weight) in enumerate(skin_pairs[:4]):
                bone_indices[slot_index] = int(bone_index)
                bone_weights[slot_index] = float(weight)

            skin_raw_dwords = None
            if int(vertex_index) < len(imported_skin_raw):
                skin_raw_dwords = imported_skin_raw[int(vertex_index)]

            out.append(mdl_lib.Ps2Vertex(
                x=float(wp.x), y=float(wp.y), z=float(wp.z),
                u=float(u), v=float(vv),
                nx=float(nx), ny=float(ny), nz=float(nz),
                r=int(ri), g=int(gi), b=int(bi), a=int(ai),
                bone_indices=tuple(bone_indices),
                bone_weights=tuple(bone_weights),
                skin_raw_dwords=skin_raw_dwords,
            ))

        return out
    finally:
        pass

def build_source_corner_vertices_world(
    context: bpy.types.Context,
    mesh_obj: bpy.types.Object,
    *,
    use_normals: bool = True,
    root_obj: Optional[bpy.types.Object] = None,
) -> List[mdl_lib.Ps2Vertex]:
    def clamp_u8(x: int) -> int:
        if x < 0:
            return 0
        if x > 255:
            return 255
        return x

    def get_active_vcol_layer(mesh: bpy.types.Mesh):
        if hasattr(mesh, "color_attributes"):
            ca = getattr(mesh, "color_attributes", None)
            if ca and getattr(ca, "active", None):
                return ca.active.data
        vc = getattr(mesh, "vertex_colors", None)
        if vc and getattr(vc, "active", None):
            return vc.active.data
        return None

    mesh_eval = getBaseMeshForMdlExport(mesh_obj)
    if mesh_eval is None:
        return []
    try:
        try:
            mesh_eval.calc_normals_split()
        except Exception:
            try:
                mesh_eval.calc_normals()
            except Exception:
                pass

        loop_order = getCornerSourceEmitOrder(mesh_eval)
        if not loop_order:
            return []

        uv_layer = mesh_eval.uv_layers.active.data if (mesh_eval.uv_layers.active) else None
        vcol_layer = get_active_vcol_layer(mesh_eval)

        world_mtx: Matrix = resolveMdlPartExportMatrix(mesh_obj, root_obj)
        normal_mtx: Matrix = world_mtx.to_3x3()

        src_mesh = getattr(mesh_obj, "data", None)
        imported_skin_raw = chooseImportedSkinRawDwords(mesh_obj, mesh_eval)
        vgroup_to_bone: Dict[int, int] = {}

        resolved_root = root_obj
        if resolved_root is None:
            try:
                resolved_root = find_mdl_root(context)
            except Exception:
                resolved_root = None

        import_type = None
        if resolved_root is not None:
            try:
                if hasattr(resolved_root, "bleeds_mdl_import_type"):
                    import_type = int(resolved_root.bleeds_mdl_import_type)
                elif "bleeds_mdl_import_type" in resolved_root:
                    import_type = int(resolved_root["bleeds_mdl_import_type"])
            except Exception:
                import_type = None

        if import_type in (0, 1):
            canonical_bones = list(getattr(mdl_lib, "commonBoneNamesLCS", []) or getattr(mdl_lib, "commonBoneOrder", []))
        elif import_type in (2, 3):
            canonical_bones = list(getattr(mdl_lib, "commonBoneNamesVCS", []) or getattr(mdl_lib, "commonBoneOrderVCS", []))
        else:
            canonical_bones = []

        name_to_bone: Dict[str, int] = {}
        for bone_i, bone_name in enumerate(canonical_bones):
            raw = str(bone_name)
            name_to_bone[raw] = int(bone_i)
            name_to_bone[raw.lower()] = int(bone_i)
            try:
                canon_raw = str(mdl_lib.canon_frame_name(raw))
                name_to_bone[canon_raw] = int(bone_i)
                name_to_bone[canon_raw.replace("bip01_", "")] = int(bone_i)
            except Exception:
                pass

        alias_to_canon = {
            "bip01": "root",
            "bip01_pelvis": "pelvis",
            "bip01_spine": "spine",
            "bip01_spine1": "spine1",
            "bip01_neck": "neck",
            "bip01_head": "head",
            "bip01_jaw": "jaw",
            "bip01_l_clavicle": "bip01_l_clavicle",
            "bip01_l_upperarm": "l_upperarm",
            "bip01_l_forearm": "l_forearm",
            "bip01_l_hand": "l_hand",
            "bip01_l_finger": "l_finger",
            "bip01_r_clavicle": "bip01_r_clavicle",
            "bip01_r_upperarm": "r_upperarm",
            "bip01_r_forearm": "r_forearm",
            "bip01_r_hand": "r_hand",
            "bip01_r_finger": "r_finger",
            "bip01_l_thigh": "l_thigh",
            "bip01_l_calf": "l_calf",
            "bip01_l_foot": "l_foot",
            "bip01_l_toe0": "l_toe0",
            "bip01_r_thigh": "r_thigh",
            "bip01_r_calf": "r_calf",
            "bip01_r_foot": "r_foot",
            "bip01_r_toe0": "r_toe0",
        }
        for alias_name, canon_target in alias_to_canon.items():
            try:
                target_key = str(mdl_lib.canon_frame_name(canon_target))
                if target_key in name_to_bone:
                    name_to_bone[alias_name] = name_to_bone[target_key]
                    name_to_bone[alias_name.lower()] = name_to_bone[target_key]
                    name_to_bone[str(mdl_lib.canon_frame_name(alias_name))] = name_to_bone[target_key]
            except Exception:
                pass

        arm_obj = None
        try:
            if mesh_obj.parent and mesh_obj.parent.type == 'ARMATURE':
                arm_obj = mesh_obj.parent
        except Exception:
            arm_obj = None
        if arm_obj is None:
            try:
                for mod in getattr(mesh_obj, "modifiers", []):
                    if getattr(mod, "type", None) == 'ARMATURE' and getattr(mod, "object", None) is not None:
                        arm_obj = mod.object
                        break
            except Exception:
                arm_obj = None

        for vg in getattr(mesh_obj, 'vertex_groups', []):
            bone_i = None
            vg_name = str(getattr(vg, 'name', '') or '')
            if vg_name in name_to_bone:
                bone_i = name_to_bone[vg_name]
            elif vg_name.lower() in name_to_bone:
                bone_i = name_to_bone[vg_name.lower()]
            else:
                try:
                    canon_name = str(mdl_lib.canon_frame_name(vg_name))
                    if canon_name in name_to_bone:
                        bone_i = name_to_bone[canon_name]
                except Exception:
                    pass
                if bone_i is None:
                    m = re.match(r'^bone[_\s-]?(\d+)$', vg_name, re.IGNORECASE)
                    if m:
                        try:
                            bone_i = int(m.group(1))
                        except Exception:
                            bone_i = None
            if bone_i is None and arm_obj is not None:
                try:
                    arm_bone = arm_obj.data.bones.get(vg_name)
                    if arm_bone is not None and "BoneID" in arm_bone:
                        bone_i = int(arm_bone["BoneID"])
                except Exception:
                    bone_i = None
            if bone_i is not None and bone_i >= 0:
                vgroup_to_bone[int(vg.index)] = int(bone_i)

        hierarchy_vgroup_to_bone = buildMdlVertexGroupBoneMap(mesh_obj, root_obj=resolved_root)
        if hierarchy_vgroup_to_bone:
            vgroup_to_bone = hierarchy_vgroup_to_bone
        if src_mesh is not None:
            ensureMdlLiveSkinAttributesForMesh(mesh_obj, src_mesh, vgroup_to_bone, resolved_root)

        out: List[mdl_lib.Ps2Vertex] = []
        for loop_index in loop_order:
            if loop_index < 0 or loop_index >= len(mesh_eval.loops):
                continue
            loop = mesh_eval.loops[int(loop_index)]
            vi = int(loop.vertex_index)
            if vi < 0 or vi >= len(mesh_eval.vertices):
                continue
            vert = mesh_eval.vertices[vi]
            wp = world_mtx @ vert.co

            u = 0.0
            vv = 0.0
            if uv_layer is not None and loop_index < len(uv_layer):
                try:
                    uv = uv_layer[int(loop_index)].uv
                    u = float(uv.x)
                    vv = float(uv.y)
                except Exception:
                    u = 0.0
                    vv = 0.0

            nx, ny, nz = 0.0, 0.0, 1.0
            if use_normals:
                try:
                    n = loop.normal
                    nw = (normal_mtx @ n).normalized()
                    nx, ny, nz = float(nw.x), float(nw.y), float(nw.z)
                except Exception:
                    nx, ny, nz = 0.0, 0.0, 1.0

            ri = gi = bi = ai = 255
            if vcol_layer is not None and loop_index < len(vcol_layer):
                try:
                    col = getattr(vcol_layer[int(loop_index)], "color", None)
                    if col is not None:
                        ri = clamp_u8(int(round(float(col[0]) * 255.0)))
                        gi = clamp_u8(int(round(float(col[1]) * 255.0)))
                        bi = clamp_u8(int(round(float(col[2]) * 255.0)))
                        ai = clamp_u8(int(round(float(col[3] if len(col) >= 4 else 1.0) * 255.0)))
                except Exception:
                    ri = gi = bi = ai = 255

            skin_pairs = getMdlLiveSkinPairsForVertex(mesh_obj, src_mesh, int(vi), vgroup_to_bone, resolved_root)

            bone_idx_out = [0, 0, 0, 0]
            bone_wt_out = [0.0, 0.0, 0.0, 0.0]
            for si, (bidx, wt) in enumerate(skin_pairs[:4]):
                bone_idx_out[si] = int(bidx)
                bone_wt_out[si] = float(wt)

            skin_raw_dwords = None
            if int(vi) < len(imported_skin_raw):
                skin_raw_dwords = imported_skin_raw[int(vi)]

            out.append(mdl_lib.Ps2Vertex(
                x=float(wp.x), y=float(wp.y), z=float(wp.z),
                u=float(u), v=float(vv),
                nx=float(nx), ny=float(ny), nz=float(nz),
                r=int(ri), g=int(gi), b=int(bi), a=int(ai),
                bone_indices=tuple(bone_idx_out),
                bone_weights=tuple(bone_wt_out),
                skin_raw_dwords=skin_raw_dwords,
            ))

        return out
    finally:
        pass

def stitch_strips_into_one(strip: List[mdl_lib.Ps2Vertex], next_strip: List[mdl_lib.Ps2Vertex]) -> None:
    if not strip:
        strip.extend(next_strip)
        return
    if not next_strip:
        return

    last = strip[-1]
    next_first = next_strip[0]

    strip.append(last)
    strip.append(next_first)

    strip.extend(next_strip)

    if (len(strip) % 2) == 1:
        strip.append(next_first)

def build_strip_vertices_world(
    context: bpy.types.Context,
    mesh_obj: bpy.types.Object,
    *,
    use_normals: bool = True,
    root_obj: Optional[bpy.types.Object] = None,
) -> List[mdl_lib.Ps2Vertex]:
    try:
        build_strip_vertices_world.last_topology_segments = []
    except Exception:
        pass

    def clamp_u8(x: int) -> int:
        if x < 0:
            return 0
        if x > 255:
            return 255
        return x

    def round_key_f(x: float, places: int = 6) -> float:

        return float(round(float(x), places))

    def get_active_vcol_layer(mesh: bpy.types.Mesh):

        if hasattr(mesh, "color_attributes"):
            ca = getattr(mesh, "color_attributes", None)
            if ca and getattr(ca, "active", None):
                return ca.active.data
        vc = getattr(mesh, "vertex_colors", None)
        if vc and getattr(vc, "active", None):
            return vc.active.data
        return None

    def stitch_key_strips_into_one(strip_keys: List[tuple], next_keys: List[tuple]) -> None:
        if not strip_keys:
            strip_keys.extend(next_keys)
            return
        if not next_keys:
            return

        last = strip_keys[-1]
        nxt0 = next_keys[0]

        strip_keys.append(last)
        strip_keys.append(last)
        strip_keys.append(nxt0)
        strip_keys.append(nxt0)

        strip_keys.extend(next_keys)

        if (len(strip_keys) % 2) == 1:
            strip_keys.append(nxt0)

    def build_directed_edge_map(tris_keys: List[tuple]) -> dict:
        directed = {}
        for ti, (a, b, c) in enumerate(tris_keys):
            directed.setdefault((a, b), []).append((ti, c))
            directed.setdefault((b, c), []).append((ti, a))
            directed.setdefault((c, a), []).append((ti, b))
        return directed

    def rotate_tri(a, b, c, rot: int):
        if rot == 0:
            return (a, b, c)
        if rot == 1:
            return (b, c, a)
        return (c, a, b)

    def try_build_strip_from_seed(
        seed_tri_index: int,
        rot: int,
        tris_keys: List[tuple],
        directed_edges: dict,
        unused_set: set,
    ) -> (List[tuple], set):
        a, b, c = tris_keys[seed_tri_index]
        a, b, c = rotate_tri(a, b, c, rot)

        strip = [a, b, c]
        used = {seed_tri_index}

        while True:

            next_tri_index = len(strip) - 2
            if (next_tri_index % 2) == 0:
                edge = (strip[-2], strip[-1])
            else:
                edge = (strip[-1], strip[-2])

            candidates = directed_edges.get(edge)
            if not candidates:
                break

            picked = None
            for (ti, opp) in candidates:
                if ti in used:
                    continue
                if ti not in unused_set:
                    continue

                if opp == strip[-1] or opp == strip[-2]:
                    continue
                picked = (ti, opp)
                break

            if picked is None:
                break

            ti, opp = picked
            used.add(ti)
            strip.append(opp)

        return strip, used

    mesh_eval, eval_owner, mesh_source_name = getEvaluatedMeshForMdlExport(context, mesh_obj, root_obj)
    if mesh_eval is None:
        return []
    try:
        try:
            mesh_obj["bleeds_mdl_export_strip_mesh_source"] = str(mesh_source_name)
        except Exception:
            pass
        mesh_eval.calc_loop_triangles()
        try:
            mesh_eval.calc_normals_split()
        except Exception:
            try:
                mesh_eval.calc_normals()
            except Exception:
                pass

        uv_layer = mesh_eval.uv_layers.active.data if (mesh_eval.uv_layers.active) else None
        vcol_layer = get_active_vcol_layer(mesh_eval)

        world_mtx: Matrix = resolveMdlPartExportMatrix(mesh_obj, root_obj)
        normal_mtx: Matrix = world_mtx.to_3x3()

        imported_normals = None

        src_mesh = getattr(mesh_obj, "data", None)
        imported_skin_raw = chooseImportedSkinRawDwords(mesh_obj, mesh_eval)
        vgroup_to_bone: Dict[int, int] = {}

        resolved_root = root_obj
        if resolved_root is None:
            try:
                resolved_root = find_mdl_root(context)
            except Exception:
                resolved_root = None

        import_type = None
        if resolved_root is not None:
            try:
                if hasattr(resolved_root, "bleeds_mdl_import_type"):
                    import_type = int(resolved_root.bleeds_mdl_import_type)
                elif "bleeds_mdl_import_type" in resolved_root:
                    import_type = int(resolved_root["bleeds_mdl_import_type"])
            except Exception:
                import_type = None

        if import_type in (0, 1):
            canonical_bones = list(getattr(mdl_lib, "commonBoneNamesLCS", []) or getattr(mdl_lib, "commonBoneOrder", []))
        elif import_type in (2, 3):
            canonical_bones = list(getattr(mdl_lib, "commonBoneNamesVCS", []) or getattr(mdl_lib, "commonBoneOrderVCS", []))
        else:
            canonical_bones = []

        name_to_bone: Dict[str, int] = {}
        for bone_i, bone_name in enumerate(canonical_bones):
            raw = str(bone_name)
            name_to_bone[raw] = int(bone_i)
            name_to_bone[raw.lower()] = int(bone_i)
            try:
                canon_raw = str(mdl_lib.canon_frame_name(raw))
                name_to_bone[canon_raw] = int(bone_i)
                name_to_bone[canon_raw.replace("bip01_", "")] = int(bone_i)
            except Exception:
                pass
        alias_to_canon = {
            "bip01": "root", "bip01_pelvis": "pelvis",
            "bip01_spine": "spine", "bip01_spine1": "spine1",
            "bip01_neck": "neck", "bip01_head": "head", "bip01_jaw": "jaw",
            "bip01_l_clavicle": "bip01_l_clavicle", "bip01_l_upperarm": "l_upperarm",
            "bip01_l_forearm": "l_forearm", "bip01_l_hand": "l_hand", "bip01_l_finger": "l_finger",
            "bip01_r_clavicle": "bip01_r_clavicle", "bip01_r_upperarm": "r_upperarm",
            "bip01_r_forearm": "r_forearm", "bip01_r_hand": "r_hand", "bip01_r_finger": "r_finger",
            "bip01_l_thigh": "l_thigh", "bip01_l_calf": "l_calf", "bip01_l_foot": "l_foot", "bip01_l_toe0": "l_toe0",
            "bip01_r_thigh": "r_thigh", "bip01_r_calf": "r_calf", "bip01_r_foot": "r_foot", "bip01_r_toe0": "r_toe0",
        }
        for alias_name, canon_target in alias_to_canon.items():
            try:
                target_key = str(mdl_lib.canon_frame_name(canon_target))
                if target_key in name_to_bone:
                    name_to_bone[alias_name] = name_to_bone[target_key]
                    name_to_bone[alias_name.lower()] = name_to_bone[target_key]
                    name_to_bone[str(mdl_lib.canon_frame_name(alias_name))] = name_to_bone[target_key]
            except Exception:
                pass

        arm_obj = None
        try:
            if mesh_obj.parent and mesh_obj.parent.type == 'ARMATURE':
                arm_obj = mesh_obj.parent
        except Exception:
            arm_obj = None

        for vg in getattr(mesh_obj, 'vertex_groups', []):
            bone_i = None
            vg_name = str(getattr(vg, 'name', '') or '')
            if vg_name in name_to_bone:
                bone_i = name_to_bone[vg_name]
            elif vg_name.lower() in name_to_bone:
                bone_i = name_to_bone[vg_name.lower()]
            else:
                try:
                    canon_name = str(mdl_lib.canon_frame_name(vg_name))
                    if canon_name in name_to_bone:
                        bone_i = name_to_bone[canon_name]
                except Exception:
                    pass
                if bone_i is None:
                    m = re.match(r'^bone[_\s-]?(\d+)$', vg_name, re.IGNORECASE)
                    if m:
                        try:
                            bone_i = int(m.group(1))
                        except Exception:
                            bone_i = None
            if bone_i is None and arm_obj is not None:
                try:
                    arm_bone = arm_obj.data.bones.get(vg_name)
                    if arm_bone is not None and "BoneID" in arm_bone:
                        bone_i = int(arm_bone["BoneID"])
                except Exception:
                    bone_i = None
            if bone_i is not None and bone_i >= 0:
                vgroup_to_bone[int(vg.index)] = int(bone_i)

        hierarchy_vgroup_to_bone = buildMdlVertexGroupBoneMap(mesh_obj, root_obj=resolved_root)
        if hierarchy_vgroup_to_bone:
            vgroup_to_bone = hierarchy_vgroup_to_bone
        if src_mesh is not None:
            ensureMdlLiveSkinAttributesForMesh(mesh_obj, src_mesh, vgroup_to_bone, resolved_root)

        enable_skin_export = bool(vgroup_to_bone)

        key_to_vertex: dict = {}

        def get_corner_key(loop_index: int, vert_index: int) -> tuple:
            v = mesh_eval.vertices[vert_index]
            wp = world_mtx @ v.co

            if uv_layer is not None:
                uv = uv_layer[loop_index].uv
                u = float(uv.x)
                vv = float(uv.y)
            else:
                u, vv = 0.0, 0.0

            if use_normals:

                if imported_normals and vert_index < len(imported_normals):
                    try:
                        nx, ny, nz = imported_normals[vert_index]
                    except Exception:
                        nx, ny, nz = 0.0, 0.0, 1.0
                else:
                    n = mesh_eval.vertices[vert_index].normal
                    nw = (normal_mtx @ n).normalized()
                    nx, ny, nz = float(nw.x), float(nw.y), float(nw.z)
            else:
                nx, ny, nz = 0.0, 0.0, 1.0

            if vcol_layer is not None:

                col = getattr(vcol_layer[loop_index], "color", None)
                if col is None:
                    r, g, b, a = 1.0, 1.0, 1.0, 1.0
                else:

                    r = float(col[0])
                    g = float(col[1])
                    b = float(col[2])
                    a = float(col[3]) if (len(col) >= 4) else 1.0
            else:
                r, g, b, a = 1.0, 1.0, 1.0, 1.0

            ri = clamp_u8(int(round(r * 255.0)))
            gi = clamp_u8(int(round(g * 255.0)))
            bi = clamp_u8(int(round(b * 255.0)))
            ai = clamp_u8(int(round(a * 255.0)))

            skin_pairs = getMdlLiveSkinPairsForVertex(mesh_obj, src_mesh, int(vert_index), vgroup_to_bone, resolved_root) if enable_skin_export else []

            bone_indices = [0, 0, 0, 0]
            bone_weights = [0.0, 0.0, 0.0, 0.0]
            for si, (bi_idx, wt_val) in enumerate(skin_pairs[:4]):
                bone_indices[si] = int(bi_idx)
                bone_weights[si] = float(wt_val)

            raw_skin_for_vertex = None
            if 0 <= int(vert_index) < len(imported_skin_raw):
                raw_skin_for_vertex = imported_skin_raw[int(vert_index)]

            key = (
                int(vert_index),
                round_key_f(u), round_key_f(vv),
                int(ri), int(gi), int(bi), int(ai),
                int(bone_indices[0]), int(bone_indices[1]), int(bone_indices[2]), int(bone_indices[3]),
                round_key_f(bone_weights[0]), round_key_f(bone_weights[1]), round_key_f(bone_weights[2]), round_key_f(bone_weights[3]),
                None,
            )

            if key not in key_to_vertex:
                key_to_vertex[key] = mdl_lib.Ps2Vertex(
                    x=float(wp.x), y=float(wp.y), z=float(wp.z),
                    u=float(u), v=float(vv),
                    nx=float(nx), ny=float(ny), nz=float(nz),
                    r=int(ri), g=int(gi), b=int(bi), a=int(ai),
                    bone_indices=bone_indices,
                    bone_weights=bone_weights,
                    skin_raw_dwords=raw_skin_for_vertex,
                )
            return key

        tris_keys: List[tuple] = []
        for tri in mesh_eval.loop_triangles:
            loops = tri.loops
            verts = tri.vertices
            k0 = get_corner_key(int(loops[0]), int(verts[0]))
            k1 = get_corner_key(int(loops[1]), int(verts[1]))
            k2 = get_corner_key(int(loops[2]), int(verts[2]))
            tris_keys.append((k0, k1, k2))

        if not tris_keys:
            return []

        directed_edges = build_directed_edge_map(tris_keys)

        unused = set(range(len(tris_keys)))
        built_strips_keys: List[List[tuple]] = []

        while unused:
            seed = next(iter(unused))

            best_strip = None
            best_used = None

            for rot in (0, 1, 2):
                strip_keys, used_tris = try_build_strip_from_seed(
                    seed_tri_index=seed,
                    rot=rot,
                    tris_keys=tris_keys,
                    directed_edges=directed_edges,
                    unused_set=unused,
                )
                if best_strip is None or (len(strip_keys) > len(best_strip)):
                    best_strip = strip_keys
                    best_used = used_tris

            if best_strip is None or best_used is None:

                a, b, c = tris_keys[seed]
                best_strip = [a, b, c]
                best_used = {seed}

            unused.difference_update(best_used)
            built_strips_keys.append(best_strip)

        topology_segments: List[List[mdl_lib.Ps2Vertex]] = []
        for strip_key_list in built_strips_keys:
            segment = [key_to_vertex[k] for k in strip_key_list if k in key_to_vertex]
            if len(segment) >= 3:
                topology_segments.append(segment)
        try:
            build_strip_vertices_world.last_topology_segments = topology_segments
        except Exception:
            pass

        stitched_keys: List[tuple] = []
        for s in built_strips_keys:
            stitch_key_strips_into_one(stitched_keys, s)

        out: List[mdl_lib.Ps2Vertex] = []
        for k in stitched_keys:
            out.append(key_to_vertex[k])

        return out
    finally:
        try:
            clearEvaluatedMeshForMdlExport(eval_owner)
        except Exception:
            pass

def build_simple_vertices_world(
    context: bpy.types.Context,
    mesh_obj: bpy.types.Object,
    *,
    use_normals: bool = True,
    root_obj: Optional[bpy.types.Object] = None,
) -> List[mdl_lib.Ps2Vertex]:
    def clamp_u8(x: int) -> int:
        if x < 0:
            return 0
        if x > 255:
            return 255
        return x

    def get_active_vcol_layer(mesh: bpy.types.Mesh):

        if hasattr(mesh, "color_attributes"):
            ca = getattr(mesh, "color_attributes", None)
            if ca and getattr(ca, "active", None):
                return ca.active.data
        vc = getattr(mesh, "vertex_colors", None)
        if vc and getattr(vc, "active", None):
            return vc.active.data
        return None

    mesh_eval, eval_owner, mesh_source_name = getEvaluatedMeshForMdlExport(context, mesh_obj, root_obj)
    if mesh_eval is None:
        return []
    try:
        try:
            mesh_obj["bleeds_mdl_export_simple_mesh_source"] = str(mesh_source_name)
        except Exception:
            pass

        try:
            mesh_eval.calc_normals_split()
        except Exception:
            try:
                mesh_eval.calc_normals()
            except Exception:
                pass

        uv_layer = mesh_eval.uv_layers.active.data if (mesh_eval.uv_layers.active) else None
        vcol_layer = get_active_vcol_layer(mesh_eval)

        loops_by_vertex = {}
        for li, loop in enumerate(mesh_eval.loops):
            vi = int(loop.vertex_index)
            if vi not in loops_by_vertex:
                loops_by_vertex[vi] = li

        world_mtx: Matrix = resolveMdlPartExportMatrix(mesh_obj, root_obj)
        normal_mtx: Matrix = world_mtx.to_3x3()

        src_mesh = getattr(mesh_obj, "data", None)
        imported_skin_raw = chooseImportedSkinRawDwords(mesh_obj, mesh_eval)
        vgroup_to_bone: Dict[int, int] = {}

        resolved_root = root_obj
        if resolved_root is None:
            try:
                resolved_root = find_mdl_root(context)
            except Exception:
                resolved_root = None

        import_type = None
        if resolved_root is not None:
            try:
                if hasattr(resolved_root, "bleeds_mdl_import_type"):
                    import_type = int(resolved_root.bleeds_mdl_import_type)
                elif "bleeds_mdl_import_type" in resolved_root:
                    import_type = int(resolved_root["bleeds_mdl_import_type"])
            except Exception:
                import_type = None

        if import_type in (0, 1):
            canonical_bones = list(getattr(mdl_lib, "commonBoneNamesLCS", []) or getattr(mdl_lib, "commonBoneOrder", []))
        elif import_type in (2, 3):
            canonical_bones = list(getattr(mdl_lib, "commonBoneNamesVCS", []) or getattr(mdl_lib, "commonBoneOrderVCS", []))
        else:
            canonical_bones = []

        name_to_bone: Dict[str, int] = {}
        for bone_i, bone_name in enumerate(canonical_bones):
            name_to_bone[str(bone_name)] = int(bone_i)
            name_to_bone[str(bone_name).lower()] = int(bone_i)

        arm_obj = None
        try:
            if mesh_obj.parent and mesh_obj.parent.type == 'ARMATURE':
                arm_obj = mesh_obj.parent
        except Exception:
            arm_obj = None

        for vg in getattr(mesh_obj, 'vertex_groups', []):
            bone_i = None
            vg_name = str(getattr(vg, 'name', '') or '')
            if vg_name in name_to_bone:
                bone_i = name_to_bone[vg_name]
            elif vg_name.lower() in name_to_bone:
                bone_i = name_to_bone[vg_name.lower()]
            else:
                m = re.match(r'^bone[_\s-]?(\d+)$', vg_name, re.IGNORECASE)
                if m:
                    try:
                        bone_i = int(m.group(1))
                    except Exception:
                        bone_i = None
            if bone_i is None and arm_obj is not None:
                try:
                    arm_bone = arm_obj.data.bones.get(vg_name)
                    if arm_bone is not None and "BoneID" in arm_bone:
                        bone_i = int(arm_bone["BoneID"])
                except Exception:
                    bone_i = None
            if bone_i is not None and bone_i >= 0:
                vgroup_to_bone[int(vg.index)] = int(bone_i)

        hierarchy_vgroup_to_bone = buildMdlVertexGroupBoneMap(mesh_obj, root_obj=resolved_root)
        if hierarchy_vgroup_to_bone:
            vgroup_to_bone = hierarchy_vgroup_to_bone
        if src_mesh is not None:
            ensureMdlLiveSkinAttributesForMesh(mesh_obj, src_mesh, vgroup_to_bone, resolved_root)

        enable_skin_export = bool(vgroup_to_bone)

        out: List[mdl_lib.Ps2Vertex] = []

        imported_normals = None

        source_emit_order = getPointSourceEmitOrder(mesh_eval)

        for vi in source_emit_order:
            if vi < 0 or vi >= len(mesh_eval.vertices):
                continue
            vert = mesh_eval.vertices[int(vi)]

            wp = world_mtx @ vert.co

            u = 0.0
            vv = 0.0

            nx = 0.0
            ny = 0.0
            nz = 1.0

            ri = 255
            gi = 255
            bi = 255
            ai = 255

            loop_index = loops_by_vertex.get(vi)
            if loop_index is not None:

                if uv_layer is not None:
                    try:
                        uv = uv_layer[loop_index].uv
                        u = float(uv.x)
                        vv = float(uv.y)
                    except Exception:
                        u, vv = 0.0, 0.0

                if use_normals:

                    if imported_normals and vi < len(imported_normals):
                        try:
                            nx, ny, nz = imported_normals[vi]
                        except Exception:
                            nx, ny, nz = 0.0, 0.0, 1.0
                    else:
                        try:
                            n = mesh_eval.loops[loop_index].normal
                            nw = (normal_mtx @ n).normalized()
                            nx, ny, nz = float(nw.x), float(nw.y), float(nw.z)
                        except Exception:
                            nx, ny, nz = 0.0, 0.0, 1.0

                if vcol_layer is not None:
                    try:
                        col = getattr(vcol_layer[loop_index], "color", None)
                        if col is not None:
                            r = float(col[0]); g = float(col[1]); b = float(col[2])
                            a = float(col[3]) if (len(col) >= 4) else 1.0
                            ri = clamp_u8(int(round(r * 255.0)))
                            gi = clamp_u8(int(round(g * 255.0)))
                            bi = clamp_u8(int(round(b * 255.0)))
                            ai = clamp_u8(int(round(a * 255.0)))
                    except Exception:
                        pass

            skin_pairs = getMdlLiveSkinPairsForVertex(mesh_obj, src_mesh, int(vi), vgroup_to_bone, resolved_root) if enable_skin_export else []

            bone_idx_out = [0, 0, 0, 0]
            bone_wt_out = [0.0, 0.0, 0.0, 0.0]
            for si, (bidx, wt) in enumerate(skin_pairs[:4]):
                bone_idx_out[si] = int(bidx)
                bone_wt_out[si] = float(wt)

            skin_raw_dwords = None
            if int(vi) < len(imported_skin_raw):
                skin_raw_dwords = imported_skin_raw[int(vi)]

            out.append(mdl_lib.Ps2Vertex(
                x=float(wp.x), y=float(wp.y), z=float(wp.z),
                u=float(u), v=float(vv),
                nx=float(nx), ny=float(ny), nz=float(nz),
                r=int(ri), g=int(gi), b=int(bi), a=int(ai),
                bone_indices=tuple(bone_idx_out),
                bone_weights=tuple(bone_wt_out),
                skin_raw_dwords=skin_raw_dwords,
            ))

        return out
    finally:
        try:
            clearEvaluatedMeshForMdlExport(eval_owner)
        except Exception:
            pass

def export_stories_mdl_ps2(
    context: bpy.types.Context,
    filepath: str,
    *,
    mdl_type: str = "SIM",
    max_batch_verts: int = 0,
    rounding_mode: str = "ROUND",
    use_normals: bool = True,
    imported_export_mode: str = "REBUILD",
    export_game: str = "VCS",
) -> None:
    root = find_mdl_root(context)
    export_game = str(export_game or "VCS").upper().strip()
    if export_game not in {"LCS", "VCS", "MH2"}:
        export_game = "VCS"
    try:
        if root is not None:
            root["bleeds_model_game"] = export_game
    except Exception:
        pass

    root_mdl_type = None
    try:
        if hasattr(root, "bleeds_mdl_type"):
            root_mdl_type = str(root.bleeds_mdl_type)
        elif "bleeds_mdl_type" in root:
            root_mdl_type = str(root["bleeds_mdl_type"])
    except Exception:
        root_mdl_type = None

    normalized_root_type = str(root_mdl_type or "").upper().strip()
    normalized_req_type = str(mdl_type or "SIM").upper().strip()
    if normalized_root_type in ("PED", "CUT") and normalized_req_type == "SIM":
        mdl_type = "PED"

    root_export_normals = None
    try:
        if hasattr(root, "bleeds_export_use_normals"):
            root_export_normals = bool(root.bleeds_export_use_normals)
        elif "bleeds_export_use_normals" in root:
            root_export_normals = bool(root["bleeds_export_use_normals"])
    except Exception:
        root_export_normals = None

    try:
        root_imported_export_mode = None
        if root is not None:
            if hasattr(root, "bleeds_imported_export_mode"):
                root_imported_export_mode = str(root.bleeds_imported_export_mode or "")
            elif "bleeds_imported_export_mode" in root:
                root_imported_export_mode = str(root.get("bleeds_imported_export_mode", ""))
    except Exception:
        root_imported_export_mode = None

    imported_export_mode = "REBUILD"

    live_logical_ped_compile = (str(mdl_type or "").upper().strip() == "PED")

    if live_logical_ped_compile:
        try:
            root["bleeds_mdl_export_force_ped_space"] = True
        except Exception:
            pass
        try:
            for obj in walkMdlRootObjects(root):
                if getattr(obj, "type", None) == 'ARMATURE':
                    obj["bleeds_mdl_export_force_ped_space"] = True
                    if getattr(obj, "data", None) is not None:
                        obj.data["bleeds_mdl_export_force_ped_space"] = True
        except Exception:
            pass

    if str(mdl_type or "").upper().strip() == "PED":
        use_normals = True
    elif root_export_normals is not None:
        use_normals = bool(use_normals or root_export_normals)
    meshes = gather_mesh_parts(context, root)

    if not meshes:
        raise RuntimeError("No mesh parts found under ROOT. Nothing to export.")

    rebuilt_custom_vertex_group_vertices = 0
    for export_part_index, mesh_obj in enumerate(meshes):
        writeMdlSemanticDefaultsForExport(mesh_obj, export_part_index)
        stampMdlPointVertexStreamAttributesForExport(mesh_obj, export_part_index)
        if live_logical_ped_compile:
            rebuilt_custom_vertex_group_vertices += int(normalizeMdlCustomPedVertexGroupsForExport(mesh_obj, root) or 0)

    if live_logical_ped_compile:
        try:
            writeMdlCanonicalPedIdentityMapProps(root, None, root)
            for obj in walkMdlRootObjects(root):
                if getattr(obj, "type", None) == 'ARMATURE':
                    writeMdlCanonicalPedIdentityMapProps(obj, None, root)
                    if getattr(obj, "data", None) is not None:
                        writeMdlCanonicalPedIdentityMapProps(obj.data, None, root)
        except Exception:
            pass
    if rebuilt_custom_vertex_group_vertices:
        try:
            root["bleeds_mdl_export_custom_vertex_group_rebuilt_vertices"] = int(rebuilt_custom_vertex_group_vertices)
            root["bleeds_mdl_export_custom_vertex_group_policy"] = "CANONICAL_PED_NODE_INDEX_SKIN_AUTHORITY"
        except Exception:
            pass

    try:
        if live_logical_ped_compile:
            print("[BLeeds] LIVE_LOGICAL_PED_COMPILE enabled: POINT attributes are always stamped; imported native POINT streams are used only when topology authority is proven; custom meshes use face-strip topology and importer display-matrix local transform anchoring under imported PED roots.")
        print("[BLeeds] PED export position-space policy:")
        for export_part_index, mesh_obj in enumerate(meshes):
            export_mtx_probe = resolveMdlPartExportMatrix(mesh_obj, root)
            space_name = readIdProp(mesh_obj, "bleeds_mdl_export_position_space", "UNKNOWN")
            print(
                f"[BLeeds]   part {export_part_index:02d} {getattr(mesh_obj, 'name', '<mesh>')}: "
                f"{space_name}; matrix_is_identity={export_mtx_probe == Matrix.Identity(4)}"
            )
    except Exception as exc:
        print(f"[BLeeds] PED export position-space policy logging failed: {exc}")

    GLOBAL_SCALE = 100.0 * 0.00000030518203134641490805874367518203

    scale_pos_root = mdl_lib.compute_effective_scale_pos(root)

    def compute_export_bounds(mesh_objs):
        min_x = min_y = min_z =  1.0e30
        max_x = max_y = max_z = -1.0e30

        any_point = False

        for obj in mesh_objs:
            if obj is None or getattr(obj, "type", None) != 'MESH':
                continue

            me, eval_owner_for_bounds, bounds_mesh_source = getEvaluatedMeshForMdlExport(context, obj, root)
            export_mtx = resolveMdlPartExportMatrix(obj, root)

            if me is not None and len(getattr(me, "vertices", [])) > 0:
                try:
                    for v in me.vertices:
                        p = export_mtx @ v.co
                        min_x = min(min_x, float(p.x)); max_x = max(max_x, float(p.x))
                        min_y = min(min_y, float(p.y)); max_y = max(max_y, float(p.y))
                        min_z = min(min_z, float(p.z)); max_z = max(max_z, float(p.z))
                    any_point = True
                    try:
                        obj["bleeds_mdl_export_bounds_mesh_source"] = str(bounds_mesh_source)
                    except Exception:
                        pass
                    try:
                        clearEvaluatedMeshForMdlExport(eval_owner_for_bounds)
                    except Exception:
                        pass
                    continue
                except Exception:
                    try:
                        clearEvaluatedMeshForMdlExport(eval_owner_for_bounds)
                    except Exception:
                        pass

            try:
                bb = getattr(obj, 'bound_box', None)
                if not bb:
                    continue
                for corner in bb:
                    p = export_mtx @ Vector((corner[0], corner[1], corner[2]))
                    min_x = min(min_x, float(p.x)); max_x = max(max_x, float(p.x))
                    min_y = min(min_y, float(p.y)); max_y = max(max_y, float(p.y))
                    min_z = min(min_z, float(p.z)); max_z = max(max_z, float(p.z))
                any_point = True
            except Exception:
                continue

        if not any_point or min_x > max_x or min_y > max_y or min_z > max_z:
            return None

        return (min_x, min_y, min_z, max_x, max_y, max_z)

    bounds = compute_export_bounds(meshes)

    scale_pos = None
    contains_custom_authored_mesh = hasCustomAuthoredMdlExportMesh(meshes)
    safe_raw_limit = 28672.0
    force_live_ped_scale = (str(mdl_type or "").upper().strip() == "PED")

    try:
        if bounds is not None:
            root["bleeds_mdl_export_bounds_min"] = [float(bounds[0]), float(bounds[1]), float(bounds[2])]
            root["bleeds_mdl_export_bounds_max"] = [float(bounds[3]), float(bounds[4]), float(bounds[5])]
            root["bleeds_mdl_export_contains_custom_authored_mesh"] = bool(contains_custom_authored_mesh)
            root["bleeds_mdl_export_force_live_ped_scale"] = bool(force_live_ped_scale)
    except Exception:
        pass

    if (force_live_ped_scale or contains_custom_authored_mesh) and bounds is not None:
        scale_pos = makeSafeScalePosFromBounds(bounds, raw_limit=safe_raw_limit)
        try:
            ux, uy, uz = rawUtilizationForScalePos(bounds, scale_pos)
            root["bleeds_mdl_export_scale_policy"] = "LIVE_PED_BOUNDS_RECOMPUTED_SAFE_RAW_HEADROOM" if force_live_ped_scale else "CUSTOM_RECOMPUTED_SAFE_RAW_HEADROOM"
            root["bleeds_mdl_export_scale"] = [float(scale_pos.scale[0]), float(scale_pos.scale[1]), float(scale_pos.scale[2])]
            root["bleeds_mdl_export_pos"] = [float(scale_pos.pos[0]), float(scale_pos.pos[1]), float(scale_pos.pos[2])]
            root["bleeds_mdl_export_scale_raw_utilization"] = [float(ux), float(uy), float(uz)]
            root["bleeds_mdl_export_scale_raw_limit"] = float(safe_raw_limit)
        except Exception:
            pass
        print("[BLeeds] PED live geometry detected: recomputed geometry scale/translation from live transformed bounds; old imported ROOT ScalePos is not reused.")

    if scale_pos is None and scale_pos_root is not None and bounds is not None:
        try:
            sx0, sy0, sz0 = [float(v) for v in scale_pos_root.scale[:3]]
            tx0, ty0, tz0 = [float(v) for v in scale_pos_root.pos[:3]]

            eps = 1.0e-5
            min_x, min_y, min_z, max_x, max_y, max_z = bounds

            fits = True
            if sx0 <= 0.0 or sy0 <= 0.0 or sz0 <= 0.0:
                fits = False
            if min_x < (tx0 - sx0 - eps) or max_x > (tx0 + sx0 + eps):
                fits = False
            if min_y < (ty0 - sy0 - eps) or max_y > (ty0 + sy0 + eps):
                fits = False
            if min_z < (tz0 - sz0 - eps) or max_z > (tz0 + sz0 + eps):
                fits = False

            ux, uy, uz = rawUtilizationForScalePos(bounds, scale_pos_root)
            if max(ux, uy, uz) > safe_raw_limit:
                fits = False
                print(
                    "[BLeeds] ROOT stored scale/translation technically fits but would use "
                    f"raw range ({ux:.1f}, {uy:.1f}, {uz:.1f}); recomputing with headroom."
                )

            if fits:
                scale_pos = scale_pos_root
                try:
                    root["bleeds_mdl_export_scale_policy"] = "REUSED_IMPORTED_ROOT_SCALEPOS"
                    root["bleeds_mdl_export_scale_raw_utilization"] = [float(ux), float(uy), float(uz)]
                except Exception:
                    pass
            else:
                print("[BLeeds] ROOT stored scale/translation does not fit current mesh bounds; recomputing for export.")
        except Exception:
            scale_pos = None

    if scale_pos is None and scale_pos_root is not None and bounds is None and not contains_custom_authored_mesh:
        scale_pos = scale_pos_root

    if scale_pos is None:
        if bounds is None:
            raise RuntimeError("Could not compute bounds for export (no valid mesh bounds).")

        scale_pos = makeSafeScalePosFromBounds(bounds, raw_limit=safe_raw_limit)
        try:
            ux, uy, uz = rawUtilizationForScalePos(bounds, scale_pos)
            root["bleeds_mdl_export_scale_policy"] = "RECOMPUTED_SAFE_RAW_HEADROOM"
            root["bleeds_mdl_export_scale_raw_utilization"] = [float(ux), float(uy), float(uz)]
            root["bleeds_mdl_export_scale_raw_limit"] = float(safe_raw_limit)
        except Exception:
            pass

    dma_packets: List[bytearray] = []

    texture_names: List[str] = []

    part_material_names: List[str] = []
    part_leeds_headers: List[Dict[str, object]] = []
    mdl_type_u_for_split = (mdl_type or "SIM").upper().strip()
    if mdl_type_u_for_split == "PED":
        ps2_max_strip_verts = getattr(mdl_lib, "PS2_MAX_TRISTRIP_VERTS_PED", 42)
    else:
        ps2_max_strip_verts = getattr(mdl_lib, "PS2_MAX_TRISTRIP_VERTS", 70)

    def clamp_i16(value: float) -> int:
        iv = int(round(value))
        if iv < -32768:
            return -32768
        if iv > 32767:
            return 32767
        return iv

    def encode_bbox_i16_from_vertices(vertices, sp):
        if not vertices:
            return [0, 0, 0, 0, 0, 0]

        min_x = min(v.x for v in vertices)
        min_y = min(v.y for v in vertices)
        min_z = min(v.z for v in vertices)
        max_x = max(v.x for v in vertices)
        max_y = max(v.y for v in vertices)
        max_z = max(v.z for v in vertices)

        GLOBAL_SCALE = 100.0 * 0.00000030518203134641490805874367518203

        sx = sp.scale[0] if abs(sp.scale[0]) > 1.0e-12 else 1.0
        sy = sp.scale[1] if abs(sp.scale[1]) > 1.0e-12 else 1.0
        sz = sp.scale[2] if abs(sp.scale[2]) > 1.0e-12 else 1.0
        tx = sp.pos[0]
        ty = sp.pos[1]
        tz = sp.pos[2]

        return [
            clamp_i16((min_x - tx) / (sx * GLOBAL_SCALE)),
            clamp_i16((min_y - ty) / (sy * GLOBAL_SCALE)),
            clamp_i16((min_z - tz) / (sz * GLOBAL_SCALE)),
            clamp_i16((max_x - tx) / (sx * GLOBAL_SCALE)),
            clamp_i16((max_y - ty) / (sy * GLOBAL_SCALE)),
            clamp_i16((max_z - tz) / (sz * GLOBAL_SCALE)),
        ]

    def compute_sphere_from_vertices(vertices):
        if not vertices:
            return (0.0, 0.0, 0.0, 0.0)

        min_x = min(v.x for v in vertices)
        min_y = min(v.y for v in vertices)
        min_z = min(v.z for v in vertices)
        max_x = max(v.x for v in vertices)
        max_y = max(v.y for v in vertices)
        max_z = max(v.z for v in vertices)

        cx = (min_x + max_x) * 0.5
        cy = (min_y + max_y) * 0.5
        cz = (min_z + max_z) * 0.5

        radius = 0.0
        for v in vertices:
            dx = v.x - cx
            dy = v.y - cy
            dz = v.z - cz
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            if dist > radius:
                radius = dist

        return (float(cx), float(cy), float(cz), float(radius))

    def merge_ps2_dma_packets_for_logical_part(packet_a: bytearray, packet_b: bytearray) -> bytearray:
        if not packet_a:
            return bytearray(packet_b or b"")
        if not packet_b:
            return bytearray(packet_a or b"")

        body_a = bytearray(packet_a[16:]) if len(packet_a) >= 16 else bytearray(packet_a)
        body_b = bytearray(packet_b[16:]) if len(packet_b) >= 16 else bytearray(packet_b)
        merged_body = bytearray()
        merged_body.extend(body_a)
        merged_body.extend(body_b)

        while len(merged_body) % 16:
            merged_body.append(0)

        qwc_total = len(merged_body) // 16
        merged = bytearray()
        merged.extend(mdl_lib.write_u32(0x60000000 | (qwc_total & 0xFFFF)))
        merged.extend(mdl_lib.write_u32(0))
        merged.extend(mdl_lib.write_u32(0))
        merged.extend(mdl_lib.write_u32(0))
        merged.extend(merged_body)
        return merged

    def merge_i16_bbox(a_values, b_values) -> List[int]:
        a = [int(v) for v in list(a_values or [0, 0, 0, 0, 0, 0])[:6]]
        b = [int(v) for v in list(b_values or [0, 0, 0, 0, 0, 0])[:6]]
        if len(a) < 6:
            a = [0, 0, 0, 0, 0, 0]
        if len(b) < 6:
            b = [0, 0, 0, 0, 0, 0]

        return [
            min(a[0], b[0]),
            min(a[1], b[1]),
            min(a[2], b[2]),
            max(a[3], b[3]),
            max(a[4], b[4]),
            max(a[5], b[5]),
        ]

    def merge_spheres(a_values, b_values) -> List[float]:
        try:
            ax, ay, az, ar = [float(v) for v in list(a_values)[:4]]
            bx, by, bz, br = [float(v) for v in list(b_values)[:4]]
        except Exception:
            return [0.0, 0.0, 0.0, 0.0]

        dx = bx - ax
        dy = by - ay
        dz = bz - az
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)

        if ar >= distance + br:
            return [ax, ay, az, ar]
        if br >= distance + ar:
            return [bx, by, bz, br]

        new_radius = (distance + ar + br) * 0.5
        if distance <= 1.0e-9:
            return [ax, ay, az, max(ar, br)]

        t = (new_radius - ar) / distance
        return [
            ax + dx * t,
            ay + dy * t,
            az + dz * t,
            new_radius,
        ]

    def merge_ped_part_header_for_logical_part(dst: Dict[str, object], src: Dict[str, object]) -> Dict[str, object]:
        merged = dict(dst)
        merged["strip_vertex_count"] = int(dst.get("strip_vertex_count", 0)) + int(src.get("strip_vertex_count", 0))
        for count_key in ("runtime_vertex_count", "emitted_runtime_vertex_count", "emitted_sub_strip_count", "emitted_setup_vertex_count"):
            try:
                merged[count_key] = int(dst.get(count_key, 0)) + int(src.get(count_key, 0))
            except Exception:
                pass
        merged["bbox_i16"] = merge_i16_bbox(dst.get("bbox_i16"), src.get("bbox_i16"))
        merged["sphere"] = merge_spheres(dst.get("sphere"), src.get("sphere"))

        if not merged.get("flags") and src.get("flags"):
            merged["flags"] = int(src.get("flags", 0))
        if not merged.get("uv_scale_u") and src.get("uv_scale_u") is not None:
            merged["uv_scale_u"] = float(src.get("uv_scale_u"))
        if not merged.get("uv_scale_v") and src.get("uv_scale_v") is not None:
            merged["uv_scale_v"] = float(src.get("uv_scale_v"))

        merged["source_had_part_index"] = bool(dst.get("source_had_part_index")) or bool(src.get("source_had_part_index"))
        return merged

    def compact_ped_logical_parts(
        dma_list: List[bytearray],
        material_name_list: List[str],
        header_list: List[Dict[str, object]],
        imported_indexed_meshes_present: bool,
    ) -> Tuple[List[bytearray], List[str], List[Dict[str, object]]]:
        compact_dma: List[bytearray] = []
        compact_names: List[str] = []
        compact_headers: List[Dict[str, object]] = []
        slot_by_part_index: Dict[int, int] = {}

        for old_index, packet in enumerate(dma_list):
            header = dict(header_list[old_index]) if old_index < len(header_list) else {}
            name = str(material_name_list[old_index]) if old_index < len(material_name_list) else "default"

            source_had_part_index = bool(header.get("source_had_part_index"))
            if imported_indexed_meshes_present and not source_had_part_index:
                print(
                    "[BLeeds] PED logical-parts: skipped unindexed mesh fragment/accessory "
                    f"near imported parts: {name}"
                )
                continue

            try:
                logical_part_index = int(header.get("part_index", old_index))
            except Exception:
                logical_part_index = int(old_index)

            if logical_part_index in slot_by_part_index:
                dst_index = slot_by_part_index[logical_part_index]
                compact_dma[dst_index] = merge_ps2_dma_packets_for_logical_part(compact_dma[dst_index], packet)
                compact_headers[dst_index] = merge_ped_part_header_for_logical_part(compact_headers[dst_index], header)
                print(
                    "[BLeeds] PED logical-parts: merged duplicate mesh fragment into "
                    f"part {logical_part_index}: {name}"
                )
                continue

            slot_by_part_index[logical_part_index] = len(compact_dma)
            compact_dma.append(bytearray(packet))
            compact_names.append(name)
            compact_headers.append(header)

        for new_index, header in enumerate(compact_headers):

            header["part_index"] = int(new_index)

        return compact_dma, compact_names, compact_headers

    root_cache = {}
    try:

        if hasattr(root, "bleeds_mdl_atomic_hash_key"):
            root_cache["hash_key"] = int(root.bleeds_mdl_atomic_hash_key)
        if hasattr(root, "bleeds_mdl_material_names"):
            root_cache["material_names"] = list(root.bleeds_mdl_material_names)
        if hasattr(root, "bleeds_mdl_material_vcols"):
            root_cache["material_vcols"] = list(root.bleeds_mdl_material_vcols)
        if hasattr(root, "bleeds_mdl_bounds"):
            root_cache["bounds"] = tuple(float(x) for x in root.bleeds_mdl_bounds)
        if hasattr(root, "bleeds_mdl_unknown_geom_ints"):
            root_cache["unknown_geom_ints"] = [int(x) for x in root.bleeds_mdl_unknown_geom_ints]
        if hasattr(root, "bleeds_mdl_geom_block"):

            try:
                root_cache["geom_block"] = bytes.fromhex(str(root.bleeds_mdl_geom_block))
            except Exception:
                root_cache["geom_block"] = None
        if hasattr(root, "bleeds_mdl_part_batch_verts"):
            root_cache["part_batch_verts"] = [int(x) for x in root.bleeds_mdl_part_batch_verts]

    except Exception:

        try:
            if "bleeds_mdl_atomic_hash_key" in root:
                root_cache["hash_key"] = int(root["bleeds_mdl_atomic_hash_key"])
            if "bleeds_mdl_material_names" in root:
                root_cache["material_names"] = list(root["bleeds_mdl_material_names"])
            if "bleeds_mdl_material_vcols" in root:
                root_cache["material_vcols"] = [int(v) for v in root["bleeds_mdl_material_vcols"]]
            if "bleeds_mdl_bounds" in root:
                b = root["bleeds_mdl_bounds"]
                root_cache["bounds"] = (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
            if "bleeds_mdl_unknown_geom_ints" in root:
                root_cache["unknown_geom_ints"] = [int(x) for x in root["bleeds_mdl_unknown_geom_ints"]]
            if "bleeds_mdl_geom_block" in root:
                try:
                    root_cache["geom_block"] = bytes.fromhex(str(root["bleeds_mdl_geom_block"]))
                except Exception:
                    root_cache["geom_block"] = None
            if "bleeds_mdl_part_batch_verts" in root:
                root_cache["part_batch_verts"] = [int(x) for x in root["bleeds_mdl_part_batch_verts"]]
        except Exception:
            pass

    ped_atomic_meta = {}
    ped_global_header = {}
    import_type = None

    def read_idprop(obj, key, default=None):
        try:
            if obj is not None and key in obj:
                return obj[key]
        except Exception:
            pass
        return default

    if root is not None:
        for src_key, dst_key in (
            ("bleeds_mdl_render_cb", "render_cb"),
            ("bleeds_mdl_model_info_id", "model_info_id"),
            ("bleeds_mdl_vis_id_flag", "vis_id_flag"),
            ("bleeds_mdl_frame_ptr", "frame_ptr"),
            ("bleeds_mdl_hierarchy_ptr", "hierarchy_ptr"),
            ("bleeds_mdl_material_ptr", "material_ptr"),
            ("bleeds_mdl_geom_ptr", "geom_ptr"),
        ):
            value = read_idprop(root, src_key, None)
            if value is not None:
                try:
                    ped_atomic_meta[dst_key] = int(value)
                except Exception:
                    pass

        for src_key, dst_key in (
            ("bleeds_mdl_source_filepath", "source_filepath"),
            ("bleeds_mdl_filepath", "source_filepath"),
        ):
            value = read_idprop(root, src_key, None)
            if value is not None and "source_filepath" not in ped_atomic_meta:
                ped_atomic_meta[dst_key] = str(value)

        for src_key, dst_key in (
            ("bleeds_mdl_hierarchy_hash_value", "hierarchy_hash_value"),
            ("bleeds_mdl_hierarchy_tail_value", "hierarchy_tail_value"),
            ("bleeds_mdl_hierarchy_header_size", "hierarchy_header_size"),
        ):
            value = read_idprop(root, src_key, None)
            if value is not None:
                try:
                    ped_atomic_meta[dst_key] = int(value) & 0xFFFFFFFF
                except Exception:
                    pass
        value = read_idprop(root, "bleeds_mdl_hierarchy_header_hex", None)
        if value is not None:
            try:
                ped_atomic_meta["hierarchy_header_hex"] = str(value)
            except Exception:
                pass

        import_type = None
        _it = read_idprop(root, "bleeds_mdl_import_type", None)
        if _it is not None:
            try:
                import_type = int(_it)
            except Exception:
                import_type = None

        sphere = read_idprop(root, "bleeds_mdl_leeds_global_sphere", None)
        if sphere is not None:
            try:
                ped_global_header["sphere"] = [float(v) for v in list(sphere)[:4]]
            except Exception:
                pass
        bbox_i16 = read_idprop(root, "bleeds_mdl_leeds_global_bbox_i16", None)
        if bbox_i16 is not None:
            try:
                ped_global_header["bbox_i16"] = [int(v) for v in list(bbox_i16)[:6]]
            except Exception:
                pass
        scale = read_idprop(root, "bleeds_mdl_leeds_scale", None)
        if scale is not None:
            try:
                ped_global_header["scale"] = [float(v) for v in list(scale)[:3]]
            except Exception:
                pass
        translation = read_idprop(root, "bleeds_mdl_leeds_translation", None)
        if translation is not None:
            try:
                ped_global_header["translation"] = [float(v) for v in list(translation)[:3]]
            except Exception:
                pass
        for src_key, dst_key in (
            ("bleeds_mdl_leeds_vertex_section_flags", "vertex_section_flags"),
            ("bleeds_mdl_leeds_total_vertex_count", "total_vertex_count"),
            ("bleeds_mdl_leeds_first_tristrip_offset", "first_tristrip_offset"),
            ("bleeds_mdl_leeds_packed_size_and_matcount", "packed_size_and_material_count"),
        ):
            value = read_idprop(root, src_key, None)
            if value is not None:
                try:
                    ped_global_header[dst_key] = int(value)
                except Exception:
                    pass

    try:
        override_normals = None
        if root is not None:
            if hasattr(root, "bleeds_export_use_normals"):
                override_normals = bool(root.bleeds_export_use_normals)
            elif "bleeds_export_use_normals" in root:
                override_normals = bool(root["bleeds_export_use_normals"])
        if override_normals is not None:
            use_normals = override_normals
    except Exception:
        pass

    for mesh_obj in meshes:

        mesh_source_strip_counts = []
        mesh_has_imported_semantics = isImportedMdlSemanticMesh(mesh_obj)
        root_imported_counts = None
        is_imported_part = (read_idprop(mesh_obj, "bleeds_mdl_part_index", None) is not None)
        source_stream_used = False
        source_counts_for_stream = []
        prebuilt_sub_strips: Optional[List[List[mdl_lib.Ps2Vertex]]] = None

        if mdl_type_u_for_split == "PED":
            strip = build_source_point_vertices_world(context, mesh_obj, use_normals=use_normals, root_obj=root)
            source_stream_used = bool(strip)
            if source_stream_used:
                source_counts_for_stream = getMdlSourceStripCounts(mesh_obj)
                try:
                    if source_counts_for_stream and int(sum(int(c) for c in source_counts_for_stream)) == int(len(strip)):
                        prebuilt_sub_strips = []
                        source_cursor = 0
                        for source_count in source_counts_for_stream:
                            count_i = int(source_count)
                            if count_i >= 3:
                                prebuilt_sub_strips.append(strip[source_cursor:source_cursor + count_i])
                            source_cursor += max(0, count_i)
                except Exception:
                    prebuilt_sub_strips = None
            if not strip:
                stitched_topology_strip = build_strip_vertices_world(context, mesh_obj, use_normals=use_normals, root_obj=root)
                source_stream_used = False
                topology_segments = list(getattr(build_strip_vertices_world, "last_topology_segments", []) or [])
                if topology_segments:
                    prebuilt_sub_strips = []
                    for topology_segment in topology_segments:
                        if len(topology_segment) < 3:
                            continue
                        if len(topology_segment) > int(ps2_max_strip_verts):
                            prebuilt_sub_strips.extend(
                                mdl_lib.split_ps2_tristrip_vertices(
                                    topology_segment,
                                    max_verts=int(ps2_max_strip_verts),
                                    overlap=2,
                                )
                            )
                        else:
                            prebuilt_sub_strips.append(topology_segment)
                    strip = [vertex for sub_strip in prebuilt_sub_strips for vertex in sub_strip]
                else:
                    strip = stitched_topology_strip
            if not strip:
                strip = build_simple_vertices_world(context, mesh_obj, use_normals=use_normals, root_obj=root)
                source_stream_used = False
                prebuilt_sub_strips = None
        else:
            strip = build_strip_vertices_world(context, mesh_obj, use_normals=use_normals, root_obj=root)

        if not strip:
            try:
                me_dbg = getBaseMeshForMdlExport(mesh_obj)
                print(
                    "[BLeeds] skipped mesh with no exportable PS2 vertices: "
                    f"{getattr(mesh_obj, 'name', '<unnamed>')} "
                    f"verts={len(getattr(me_dbg, 'vertices', []) or [])} "
                    f"faces={len(getattr(me_dbg, 'polygons', []) or [])} "
                    f"loops={len(getattr(me_dbg, 'loops', []) or [])}"
                )
            except Exception:
                pass
            continue

        if "material_names" in root_cache and len(root_cache["material_names"]) == len(meshes):
            base_mat_name = str(root_cache["material_names"][len(texture_names)])
        else:
            slot_names = collect_material_names_in_slot_order(mesh_obj)
            if slot_names:
                base_mat_name = str(slot_names[0])
            else:
                base_mat_name = str(mesh_obj.name)

        texture_names.append(base_mat_name)

        sub_strips: List[List[mdl_lib.Ps2Vertex]]

        imported_counts = None
        using_mesh_source_counts = False

        if prebuilt_sub_strips is not None:
            sub_strips = [list(sub) for sub in prebuilt_sub_strips if len(sub) >= 3]
        elif imported_counts:

            counts_to_use: List[int] = []
            total = 0
            consumed = 0
            for c in imported_counts:
                counts_to_use.append(int(c))
                total += int(c)
                consumed += 1
                if total >= len(strip):
                    break

            if not using_mesh_source_counts and root_cache is not None:
                if total == len(strip):
                    root_cache["strip_counts"] = imported_counts[consumed:]
                else:
                    root_cache["strip_counts"] = []

            if total != len(strip):
                if mdl_type_u_for_split == "PED":
                    sub_strips = mdl_lib.split_ps2_ped_vif_segments(
                        strip,
                        max_verts=int(ps2_max_strip_verts),
                    )
                else:
                    sub_strips = mdl_lib.split_ps2_tristrip_vertices(
                        strip,
                        max_verts=int(ps2_max_strip_verts),
                        overlap=2,
                    )
            else:

                sub_strips = []
                idx0 = 0
                for cnt in counts_to_use:
                    sub_strips.append(strip[idx0: idx0 + cnt])
                    idx0 += cnt
        else:
            if mdl_type_u_for_split == "PED":
                sub_strips = mdl_lib.split_ps2_ped_vif_segments(
                    strip,
                    max_verts=int(ps2_max_strip_verts),
                )
            else:
                sub_strips = mdl_lib.split_ps2_tristrip_vertices(
                    strip,
                    max_verts=int(ps2_max_strip_verts),
                    overlap=2,
                )

        part_vif = bytearray()

        for sub in sub_strips:
            if len(sub) < 3:
                continue

            per_strip_max = len(sub)
            vif_payload, _ = mdl_lib.build_ps2_dma_for_strip(
                sub,
                emit_dma_tag=False,
                use_normals=use_normals,
                max_batch_verts=per_strip_max,
                scale_pos_override=scale_pos,
                rounding_mode=rounding_mode,
                vif_profile=("PED" if mdl_type_u_for_split == "PED" else "SIM"),
                include_split_header=(mdl_type_u_for_split == "PED"),
            )
            part_vif.extend(vif_payload)

        mesh_dma = bytearray()
        if part_vif:

            qwc_total = len(part_vif) // 16
            dma_tag = 0x60000000 | (qwc_total & 0xFFFF)
            mesh_dma.extend(mdl_lib.write_u32(dma_tag))
            mesh_dma.extend(mdl_lib.write_u32(0))
            mesh_dma.extend(mdl_lib.write_u32(0))
            mesh_dma.extend(mdl_lib.write_u32(0))
            mesh_dma.extend(part_vif)
            mdl_lib.validate_dma_ref_packet(
                bytes(mesh_dma),
                vif_profile=("PED" if mdl_type_u_for_split == "PED" else "SIM"),
            )

        if mesh_dma:
            dma_packets.append(mesh_dma)
            part_material_names.append(base_mat_name)

            strip_vertex_count = 0
            emitted_sub_strip_count = 0
            emitted_runtime_vertex_count = 0
            for _sub in sub_strips:
                if len(_sub) >= 3:
                    emitted_sub_strip_count += 1
                    emitted_runtime_vertex_count += len(_sub)

                    strip_vertex_count += len(_sub)

            if source_stream_used:
                strip_vertex_count = int(sum(len(_sub) for _sub in sub_strips if len(_sub) >= 3))
                emitted_runtime_vertex_count = int(strip_vertex_count)

            source_part_index_prop = None
            source_had_part_index = False
            logical_part_index = len(part_leeds_headers)

            skin_export_stats = buildMdlPedSkinExportStats(mesh_obj, strip, sub_strips, root_obj=root) if mdl_type_u_for_split == "PED" else {}

            header_entry = {
                "part_index": int(logical_part_index),
                "source_had_part_index": bool(source_had_part_index),
                "skin_export_stats": skin_export_stats,
                "sphere": compute_sphere_from_vertices(strip),
                "uv_scale_u": 1.0,
                "uv_scale_v": 1.0,
                "flags": 0x10,
                "strip_vertex_count": strip_vertex_count,
                "runtime_vertex_count": int(emitted_runtime_vertex_count),
                "emitted_runtime_vertex_count": int(emitted_runtime_vertex_count),
                "emitted_sub_strip_count": int(emitted_sub_strip_count),
                "emitted_setup_vertex_count": int(0),
                "vertex_stream_attribute_mode": "POINT_IMPORTED_SOURCE_AUTHORITY" if source_stream_used else "FACE_TOPOLOGY_INDEPENDENT_STRIPS",
                "tex_id": (len(part_material_names) - 1),
                "bbox_i16": encode_bbox_i16_from_vertices(strip, scale_pos),
            }

            part_leeds_headers.append(header_entry)

    mdl_type_u = (mdl_type or "SIM").upper().strip()
    if mdl_type_u == "PED":

        imported_indexed_meshes_present = False

        dma_packets, part_material_names, part_leeds_headers = compact_ped_logical_parts(
            dma_packets,
            part_material_names,
            part_leeds_headers,
            imported_indexed_meshes_present,
        )

    if not dma_packets:
        diagnostics: List[str] = []
        try:
            for mesh_obj in meshes:
                me_dbg = getBaseMeshForMdlExport(mesh_obj)
                vert_count = len(getattr(me_dbg, "vertices", []) or []) if me_dbg is not None else 0
                face_count = len(getattr(me_dbg, "polygons", []) or []) if me_dbg is not None else 0
                loop_count = len(getattr(me_dbg, "loops", []) or []) if me_dbg is not None else 0
                origin = ""
                try:
                    origin = str(readIdProp(me_dbg, "bleeds_mdl_semantic_attributes_origin", "") or "")
                except Exception:
                    origin = ""
                diagnostics.append(
                    f"{getattr(mesh_obj, 'name', '<unnamed>')}: "
                    f"verts={vert_count}, faces={face_count}, loops={loop_count}, origin={origin}"
                )
        except Exception:
            diagnostics = []

        detail = ""
        if diagnostics:
            detail = "\nMesh diagnostics:\n  " + "\n  ".join(diagnostics[:32])
        raise RuntimeError(
            "No exportable PS2 DMA packets were produced. "
            "Meshes were found, but every mesh produced zero emitted vertices after the export builders ran."
            + detail
        )

    if mdl_type_u == "PED":
        ped_armature = None
        for mesh_obj in meshes:
            try:
                if getattr(mesh_obj, "parent", None) is not None and getattr(mesh_obj.parent, "type", None) == 'ARMATURE':
                    ped_armature = mesh_obj.parent
                    break
            except Exception:
                pass
            try:
                for mod in getattr(mesh_obj, "modifiers", []):
                    if getattr(mod, "type", None) == 'ARMATURE' and getattr(mod, "object", None) is not None:
                        ped_armature = mod.object
                        break
            except Exception:
                pass
            if ped_armature is not None:
                break
        if ped_armature is None and root is not None and getattr(root, "type", None) == 'ARMATURE':
            ped_armature = root

        if ped_armature is None:
            try:
                ao = getattr(context, "active_object", None)
                if ao is not None and getattr(ao, "type", None) == 'ARMATURE':
                    ped_armature = ao
            except Exception:
                pass

        if ped_armature is None and root is not None:
            try:
                for o in [root] + list(getattr(root, "children_recursive", []) or []):
                    if getattr(o, "type", None) == 'ARMATURE':
                        ped_armature = o
                        break
            except Exception:
                pass

        if ped_armature is None:
            raise RuntimeError("PED export requires an Armature object with bones under the MDL ROOT.")

        ped_atomic_meta_export: Dict[str, object] = {}
        try:
            for _k in (
                "render_cb",
                "model_info_id",
                "vis_id_flag",
                "frame_ptr",
                "hierarchy_ptr",
                "material_ptr",
                "geom_ptr",
                "source_filepath",
                "hierarchy_hash_value",
                "hierarchy_tail_value",
                "hierarchy_header_size",
                "hierarchy_header_hex",
            ):
                if _k in ped_atomic_meta:
                    ped_atomic_meta_export[_k] = ped_atomic_meta[_k]
            ped_atomic_meta_export["imported_export_mode"] = "REBUILD"
        except Exception:
            ped_atomic_meta_export = {"imported_export_mode": str(imported_export_mode)}

        custom_ped_weight_meshes_present = False
        try:
            for mesh_obj_for_skin in meshes:
                if mesh_obj_for_skin is None or getattr(mesh_obj_for_skin, "type", None) != 'MESH':
                    continue
                if isMdlNativeCoordinateSpaceMesh(mesh_obj_for_skin):
                    continue
                custom_ped_weight_meshes_present = True
                break
        except Exception:
            custom_ped_weight_meshes_present = False

        if custom_ped_weight_meshes_present:

            ped_atomic_meta_export["preserve_imported_frame_matrices"] = True
            ped_atomic_meta_export["frame_matrix_authority"] = "IMPORTED_STORIES_FRAME_MATRICES_FOR_ANIM_COMPAT"
            ped_atomic_meta_export["bind_matrix_authority"] = "IMPORTED_STORIES_BIND_PALETTE_FOR_ANIM_COMPAT"

            try:
                bind_u8 = None
                for bind_owner in (root, ped_armature, getattr(ped_armature, "data", None)):
                    if bind_owner is None:
                        continue
                    bind_u8 = readMdlAnyProperty(bind_owner, "bleeds_mdl_inverse_matrix_table_u8", None)
                    if bind_u8 is not None:
                        break
                if bind_u8 is not None:
                    bind_list = [int(v) & 0xFF for v in list(bind_u8)]
                    if len(bind_list) >= 0x40:
                        ped_atomic_meta_export["source_bind_matrix_table_u8"] = bind_list
                        ped_atomic_meta_export["source_bind_matrix_table_count"] = int(len(bind_list) // 0x40)
            except Exception:
                pass

            try:
                root["bleeds_mdl_export_bind_matrix_authority"] = "IMPORTED_STORIES_BIND_PALETTE_FOR_ANIM_COMPAT"
                root["bleeds_mdl_export_frame_matrix_authority"] = "IMPORTED_STORIES_FRAME_MATRICES_FOR_ANIM_COMPAT"
            except Exception:
                pass

        ped_writer_material_names = buildPedWriterMaterialNames(
            root_cache,
            part_material_names,
            part_leeds_headers,
        )

        ped_material_vcols = []
        try:
            if "material_vcols" in root_cache and root_cache["material_vcols"]:
                ped_material_vcols = [int(v) for v in root_cache["material_vcols"]]
        except Exception:
            ped_material_vcols = []

        if str(mdl_type or "").upper().strip() == "PED":
            ped_global_header = dict(ped_global_header or {})
            ped_global_header["scale"] = [
                float(scale_pos.scale[0]),
                float(scale_pos.scale[1]),
                float(scale_pos.scale[2]),
            ]
            ped_global_header["translation"] = [
                float(scale_pos.pos[0]),
                float(scale_pos.pos[1]),
                float(scale_pos.pos[2]),
            ]
            ped_global_header["force_scale_pos"] = True
            try:
                root["bleeds_mdl_written_header_scale"] = [float(v) for v in ped_global_header["scale"]]
                root["bleeds_mdl_written_header_translation"] = [float(v) for v in ped_global_header["translation"]]
                root["bleeds_mdl_written_header_scale_authority"] = "LIVE_VIF_PACK_SCALE_POS"
            except Exception:
                pass

            try:
                if bounds is not None:
                    min_x, min_y, min_z, max_x, max_y, max_z = [float(v) for v in bounds]
                    GLOBAL_SCALE_FOR_BBOX = 100.0 * 0.00000030518203134641490805874367518203

                    sx = float(scale_pos.scale[0]) if abs(float(scale_pos.scale[0])) > 1.0e-12 else 1.0
                    sy = float(scale_pos.scale[1]) if abs(float(scale_pos.scale[1])) > 1.0e-12 else 1.0
                    sz = float(scale_pos.scale[2]) if abs(float(scale_pos.scale[2])) > 1.0e-12 else 1.0
                    tx = float(scale_pos.pos[0])
                    ty = float(scale_pos.pos[1])
                    tz = float(scale_pos.pos[2])

                    ped_global_header["bbox_i16"] = [
                        clamp_i16((min_x - tx) / (sx * GLOBAL_SCALE_FOR_BBOX)),
                        clamp_i16((min_y - ty) / (sy * GLOBAL_SCALE_FOR_BBOX)),
                        clamp_i16((min_z - tz) / (sz * GLOBAL_SCALE_FOR_BBOX)),
                        clamp_i16((max_x - tx) / (sx * GLOBAL_SCALE_FOR_BBOX)),
                        clamp_i16((max_y - ty) / (sy * GLOBAL_SCALE_FOR_BBOX)),
                        clamp_i16((max_z - tz) / (sz * GLOBAL_SCALE_FOR_BBOX)),
                    ]

                    cx = (min_x + max_x) * 0.5
                    cy = (min_y + max_y) * 0.5
                    cz = (min_z + max_z) * 0.5
                    dx = max(abs(min_x - cx), abs(max_x - cx))
                    dy = max(abs(min_y - cy), abs(max_y - cy))
                    dz = max(abs(min_z - cz), abs(max_z - cz))
                    ped_global_header["sphere"] = [
                        float(cx),
                        float(cy),
                        float(cz),
                        float(math.sqrt((dx * dx) + (dy * dy) + (dz * dz))),
                    ]
            except Exception:
                pass

        mdl_lib.write_simplemodel_ps2_ped_mdl(
            filepath,
            scale_pos=scale_pos,
            dma_packets=dma_packets,
            material_names=ped_writer_material_names,
            part_headers=part_leeds_headers,
            global_header=(ped_global_header if ped_global_header else None),
            atomic_meta=(ped_atomic_meta_export if ped_atomic_meta_export else None),
            armature_obj=ped_armature,
            import_type_hint=import_type,
            material_vcols=ped_material_vcols,
            imported_export_mode="REBUILD",
        )
    else:

        kwargs = {}
        if "hash_key" in root_cache:
            kwargs["atomic_hash_key"] = int(root_cache["hash_key"])
        if "material_vcols" in root_cache and root_cache["material_vcols"]:

            vcols = list(root_cache["material_vcols"])
            if len(vcols) < len(texture_names):
                vcols.extend([vcols[-1]] * (len(texture_names) - len(vcols)))
            kwargs["material_vcols"] = vcols
        if "bounds" in root_cache:
            kwargs["bounds"] = tuple(float(x) for x in root_cache["bounds"])
        if "unknown_geom_ints" in root_cache:
            kwargs["unknown_geom_ints"] = [int(x) for x in root_cache["unknown_geom_ints"]]
        if "geom_block" in root_cache and root_cache["geom_block"]:
            kwargs["geom_block_override"] = root_cache["geom_block"]
        mdl_lib.write_simplemodel_ps2_prop_mdl(
            filepath,
            scale_pos=scale_pos,
            dma_packets=dma_packets,
            material_names=texture_names,
            part_headers=part_leeds_headers,
            vertex_section_flags=(7 if use_normals else 3),
            **kwargs,
        )
