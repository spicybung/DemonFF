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

import os
from typing import List, Dict, Tuple, Optional, Any, Iterable

import numpy as np
import bpy

from ..gtaLib.tex import (
    PspTexHeader,
    Ps2TexHeader,
    read_u32,
    slot_base_from_slot_ptr,
    parse_container,
    parse_psp_header,
    parse_ps2_header,
    decode_psp_texture,
    decode_ps2_texture,
)

def normalize_leeds_texture_name(name: str) -> str:
    value = str(name or "").strip().lower()
    if value.endswith(".png") or value.endswith(".tga") or value.endswith(".dds") or value.endswith(".bmp"):
        value = os.path.splitext(value)[0]
    if value.endswith(".001") or value.endswith(".002") or value.endswith(".003") or value.endswith(".004"):
        stem, suffix = value.rsplit(".", 1)
        if suffix.isdigit():
            value = stem
    return value

LEEDS_TEXTURE_SIDECAR_EXTENSIONS: Tuple[str, ...] = (".xtx", ".chk", ".tex")

def find_sidecar_texture_for_mdl(mdl_path: str) -> Optional[str]:
    if not mdl_path:
        return None

    base, _ext = os.path.splitext(os.path.abspath(mdl_path))
    candidates: List[str] = []
    for ext in LEEDS_TEXTURE_SIDECAR_EXTENSIONS:
        candidates.append(base + ext)
        candidates.append(base + ext.upper())
        candidates.append(base + ext.capitalize())

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    folder = os.path.dirname(base)
    wanted_stem = os.path.basename(base).lower()
    wanted_exts = set(LEEDS_TEXTURE_SIDECAR_EXTENSIONS)
    try:
        for entry in os.listdir(folder or "."):
            stem, ext = os.path.splitext(entry)
            if stem.lower() == wanted_stem and ext.lower() in wanted_exts:
                candidate = os.path.join(folder, entry)
                if os.path.isfile(candidate):
                    return candidate
    except Exception:
        pass

    return None

def find_sidecar_txd_for_mdl(mdl_path: str) -> Optional[str]:
    return find_sidecar_texture_for_mdl(mdl_path)

def get_image_original_texture_name(image: bpy.types.Image) -> str:
    try:
        value = image.get("bleeds_texture_name", "")
        if value:
            return str(value)
    except Exception:
        pass
    try:
        return str(image.name).split(".")[0]
    except Exception:
        return ""

def build_image_lookup(images: Iterable[bpy.types.Image]) -> Dict[str, bpy.types.Image]:
    lookup: Dict[str, bpy.types.Image] = {}
    for image in list(images or []):
        if image is None:
            continue
        names = []
        try:
            names.append(str(image.name))
        except Exception:
            pass
        try:
            original = image.get("bleeds_texture_name", "")
            if original:
                names.append(str(original))
        except Exception:
            pass
        for name in names:
            key = normalize_leeds_texture_name(name)
            if key and key not in lookup:
                lookup[key] = image
    return lookup

def find_principled_bsdf_node(material: bpy.types.Material) -> Optional[bpy.types.Node]:
    if material is None or not material.use_nodes or material.node_tree is None:
        return None
    for node in material.node_tree.nodes:
        if getattr(node, "type", "") == "BSDF_PRINCIPLED":
            return node
    return None

def find_or_create_output_node(material: bpy.types.Material) -> Optional[bpy.types.Node]:
    if material is None or material.node_tree is None:
        return None
    nodes = material.node_tree.nodes
    for node in nodes:
        if getattr(node, "type", "") == "OUTPUT_MATERIAL":
            return node
    try:
        return nodes.new(type="ShaderNodeOutputMaterial")
    except Exception:
        return None

def find_or_create_principled_bsdf_node(material: bpy.types.Material) -> Optional[bpy.types.Node]:
    if material is None:
        return None
    try:
        material.use_nodes = True
    except Exception:
        return None
    if material.node_tree is None:
        return None

    node = find_principled_bsdf_node(material)
    if node is not None:
        return node

    try:
        node = material.node_tree.nodes.new(type="ShaderNodeBsdfPrincipled")
        node.location = (0, 0)
    except Exception:
        return None

    out = find_or_create_output_node(material)
    try:
        if out is not None and "BSDF" in node.outputs and "Surface" in out.inputs:
            material.node_tree.links.new(node.outputs["BSDF"], out.inputs["Surface"])
    except Exception:
        pass
    return node

def remove_existing_bleeds_texture_links(material: bpy.types.Material, bsdf_node: bpy.types.Node) -> None:
    if material is None or material.node_tree is None or bsdf_node is None:
        return
    links = material.node_tree.links
    for socket_name in ("Base Color", "Alpha"):
        try:
            socket = bsdf_node.inputs.get(socket_name)
            if socket is None:
                continue
            for link in list(socket.links):
                links.remove(link)
        except Exception:
            pass

def apply_image_to_material(material: bpy.types.Material, image: bpy.types.Image) -> bool:
    if material is None or image is None:
        return False

    try:
        material.use_nodes = True
    except Exception:
        return False

    if material.node_tree is None:
        return False

    bsdf = find_or_create_principled_bsdf_node(material)
    if bsdf is None:
        return False

    nodes = material.node_tree.nodes
    links = material.node_tree.links

    existing_node = None
    for node in nodes:
        try:
            if getattr(node, "type", "") == "TEX_IMAGE" and (node.get("bleeds_auto_texture_node", False) or node.get("bleeds_auto_txd_node", False)):
                existing_node = node
                break
        except Exception:
            pass

    if existing_node is None:
        try:
            existing_node = nodes.new(type="ShaderNodeTexImage")
            existing_node.location = (-350, 120)
        except Exception:
            return False

    try:
        existing_node.image = image
        existing_node.label = "BLeeds Texture"
        existing_node.name = "BLeeds_Texture_Image"
        existing_node["bleeds_auto_texture_node"] = True
        existing_node["bleeds_auto_txd_node"] = True
    except Exception:
        pass

    remove_existing_bleeds_texture_links(material, bsdf)

    try:
        if "Color" in existing_node.outputs and "Base Color" in bsdf.inputs:
            links.new(existing_node.outputs["Color"], bsdf.inputs["Base Color"])
    except Exception:
        pass

    try:
        if "Alpha" in existing_node.outputs and "Alpha" in bsdf.inputs:
            links.new(existing_node.outputs["Alpha"], bsdf.inputs["Alpha"])
            material.blend_method = "BLEND"
            material.use_screen_refraction = False
            if hasattr(material, "show_transparent_back"):
                material.show_transparent_back = True
    except Exception:
        pass

    try:
        material["bleeds_texture_image_name"] = str(image.name)
        material["bleeds_texture_texture_name"] = get_image_original_texture_name(image)
        material["bleeds_txd_image_name"] = str(image.name)
        material["bleeds_txd_texture_name"] = get_image_original_texture_name(image)
    except Exception:
        pass

    return True

def texture_names_for_material(material: bpy.types.Material) -> List[str]:
    names: List[str] = []
    if material is None:
        return names

    for key in (
        "bleeds_mdl_texture_name",
        "bleeds_mdl_part_texture_name",
        "bleeds_mdl_material_name",
        "bleeds_texture_texture_name",
        "bleeds_txd_texture_name",
    ):
        try:
            value = material.get(key, "")
            if value:
                names.append(str(value))
        except Exception:
            pass

    try:
        if material.name:
            names.append(str(material.name))
    except Exception:
        pass

    return names

def texture_names_for_object_material_slot(obj: bpy.types.Object, material: bpy.types.Material) -> List[str]:
    names = texture_names_for_material(material)
    if obj is None:
        return names

    for datablock in (obj, getattr(obj, "data", None)):
        if datablock is None:
            continue
        for key in (
            "bleeds_mdl_texture_name",
            "bleeds_mdl_part_texture_name",
            "bleeds_mdl_material_name",
        ):
            try:
                value = datablock.get(key, "")
                if value:
                    names.append(str(value))
            except Exception:
                pass

    return names

def apply_images_to_imported_mdl_materials(
    images: Iterable[bpy.types.Image],
    imported_objects: Iterable[bpy.types.Object],
) -> Tuple[int, int, List[str]]:
    image_lookup = build_image_lookup(images)
    matched_materials = 0
    visited_materials = set()
    missing_names: List[str] = []

    for obj in list(imported_objects or []):
        if obj is None or getattr(obj, "type", None) != "MESH":
            continue
        data = getattr(obj, "data", None)
        if data is None:
            continue
        for material in list(getattr(data, "materials", []) or []):
            if material is None:
                continue
            material_key = getattr(material, "name", str(id(material)))
            if material_key in visited_materials:
                continue

            candidate_names = texture_names_for_object_material_slot(obj, material)
            image = None
            best_name = ""
            for name in candidate_names:
                lookup_key = normalize_leeds_texture_name(name)
                if lookup_key in image_lookup:
                    image = image_lookup[lookup_key]
                    best_name = name
                    break

            if image is None:
                for name in candidate_names:
                    lookup_key = normalize_leeds_texture_name(name)
                    if lookup_key and lookup_key not in missing_names:
                        missing_names.append(lookup_key)
                continue

            if apply_image_to_material(material, image):
                matched_materials += 1
                visited_materials.add(material_key)
                try:
                    material["bleeds_texture_matched_from"] = str(best_name)
                    material["bleeds_txd_matched_from"] = str(best_name)
                except Exception:
                    pass

    return matched_materials, len(image_lookup), missing_names

def import_sidecar_texture_for_mdl(
    mdl_path: str,
    imported_objects: Iterable[bpy.types.Object],
    platform: str = "auto",
) -> Tuple[Optional[str], List[bpy.types.Image], int, List[str]]:
    texture_path = find_sidecar_texture_for_mdl(mdl_path)
    if not texture_path:
        return None, [], 0, []

    decode_platform = str(platform or "auto").strip().lower()
    if decode_platform not in {"auto", "psp", "ps2"}:
        decode_platform = "auto"

    images = decode_chk_to_blender_images(
        texture_path,
        platform=decode_platform,
        prefix="",
    )
    matched_materials, _image_count, missing_names = apply_images_to_imported_mdl_materials(
        images,
        imported_objects,
    )
    return texture_path, images, matched_materials, missing_names

def decode_chk_to_blender_images(
    input_path: str,
    platform: str = 'auto',
    prefix: str = '',
) -> List[bpy.types.Image]:

    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input file '{input_path}' does not exist")
    with open(input_path, 'rb') as f:
        data = f.read()

    hdr = {
        'sig': data[0:4].decode('ascii', 'replace'),
        'plat': read_u32(data, 0x04),
        'coll_size': read_u32(data, 0x08),
        'glob1': read_u32(data, 0x0C),
        'glob2': read_u32(data, 0x10),
        'glob_count': read_u32(data, 0x14),
        'cont_byte': data[0x20],
        'flags24': data[0x21] | (data[0x22] << 8) | (data[0x23] << 16),
        'first_slot': read_u32(data, 0x28),
        'last_slot': read_u32(data, 0x2C),
    }
    first_slot = hdr['first_slot']
    last_slot = hdr['last_slot']
    visited: set[int] = set()

    textures: List[Tuple[str, int, object]] = []
    base = slot_base_from_slot_ptr(first_slot)
    last_base = slot_base_from_slot_ptr(last_slot) if last_slot else None

    while True:
        if base in visited:
            break
        visited.add(base)
        cinfo = parse_container(data, base)
        if not cinfo:
            break
        name = cinfo['name']

        if name and all(32 <= ord(ch) < 127 for ch in name):

            tex_off = cinfo['tex_off']
            hdr_psp: Optional[PspTexHeader] = None
            hdr_ps2: Optional[Ps2TexHeader] = None
            if platform in ('auto', 'psp'):
                hdr_psp = parse_psp_header(data, tex_off)
            if platform in ('auto', 'ps2'):
                hdr_ps2 = parse_ps2_header(data, tex_off)
            header_obj: Optional[object] = None
            if platform == 'psp':
                header_obj = hdr_psp
            elif platform == 'ps2':
                header_obj = hdr_ps2
            else:

                def is_plausible_psp(h: Optional[PspTexHeader]) -> bool:
                    if not h:
                        return False

                    if h.bpp not in (4, 8, 32):
                        return False
                    if h.width < 4 or h.height < 4:
                        return False
                    return True

                def is_plausible_ps2(h: Optional[Ps2TexHeader]) -> bool:
                    if not h:
                        return False

                    if h.bpp not in (4, 8, 16, 32):
                        return False
                    if h.width < 4 or h.height < 4:
                        return False
                    return True

                has_psp = is_plausible_psp(hdr_psp)
                has_ps2 = is_plausible_ps2(hdr_ps2)
                if has_psp and not has_ps2:
                    header_obj = hdr_psp
                elif has_ps2 and not has_psp:
                    header_obj = hdr_ps2
                elif has_psp and has_ps2:

                    size_psp = hdr_psp.width * hdr_psp.height
                    size_ps2 = hdr_ps2.width * hdr_ps2.height
                    if size_psp >= size_ps2:
                        header_obj = hdr_psp
                    else:
                        header_obj = hdr_ps2
                else:

                    header_obj = hdr_psp if hdr_psp else hdr_ps2
            if header_obj:
                textures.append((name, cinfo['tex_off'], header_obj))

        next_slot = cinfo['next_slot']
        if next_slot == 0:
            break
        next_base = slot_base_from_slot_ptr(next_slot)
        if next_base == base:
            break
        base = next_base
    if not textures:
        return []

    textures_sorted = []
    for name, tex_off, header in textures:
        if isinstance(header, PspTexHeader):
            roff = header.raster_offset
        elif isinstance(header, Ps2TexHeader):
            roff = header.raster_offset
        else:
            continue
        textures_sorted.append((name, tex_off, header, roff))
    textures_sorted.sort(key=lambda x: x[3])
    offsets = [hdr_info[3] for hdr_info in textures_sorted]
    block_sizes: List[int] = []
    for i in range(len(offsets)):
        start = offsets[i]
        if i + 1 < len(offsets):
            end = offsets[i + 1]
        else:
            glob_candidates = [hdr['glob1'], hdr['glob2'], hdr['coll_size'], len(data)]
            end_candidates = [ec for ec in glob_candidates if ec > start]
            end = min(end_candidates) if end_candidates else len(data)
        block_sizes.append(max(0, end - start))
    blender_images: List[bpy.types.Image] = []

    for ((name, tex_off, header, roff), blk_size) in zip(textures_sorted, block_sizes):
        if isinstance(header, PspTexHeader):
            rgba = decode_psp_texture(data, header, blk_size, palette_override=None)
        elif isinstance(header, Ps2TexHeader):
            rgba = decode_ps2_texture(data, header, blk_size, palette_override=None)
        else:
            rgba = None
        if rgba is None:
            continue
        h, w, _ = rgba.shape

        rgba_flat = rgba.reshape((-1, 4)).astype(np.float32) / 255.0

        pixels = rgba_flat.flatten().tolist()

        image_name = f"{prefix}{name}"

        img = bpy.data.images.new(name=image_name, width=w, height=h, alpha=True)
        try:
            img["bleeds_texture_name"] = str(name)
            img["bleeds_texture_source_path"] = str(input_path)
            img["bleeds_texture_platform"] = str(platform)
        except Exception:
            pass

        img.pixels = pixels
        blender_images.append(img)
    return blender_images

def import_sidecar_txd_for_mdl(mdl_path: str, imported_objects: Iterable[bpy.types.Object], platform: str = "auto") -> Tuple[Optional[str], List[bpy.types.Image], int, List[str]]:
    return import_sidecar_texture_for_mdl(mdl_path, imported_objects, platform=platform)
