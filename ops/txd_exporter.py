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
import os
import re

try:
    import numpy as np
except Exception:
    np = None

from ..gtaLib import txd
from ..gtaLib.txd import ImageEncoder
from ..gtaLib.dff import NativePlatformType

#######################################################
def clear_extension(string):
    k = string.rfind('.')
    return string if k < 0 else string[:k]

#######################################################
def strip_blender_numeric_suffix(name):
    return re.sub(r"\.\d{3,}$", "", str(name or ""))

#######################################################
def texture_export_name(label, image_name):
    label = str(label or "").strip()
    if label:
        # Node labels imported from DFF are the authoritative RW lookup name.
        return label
    clean = strip_blender_numeric_suffix(image_name)
    return os.path.splitext(clean)[0]

#######################################################
class txd_exporter:

    mass_export = False
    only_used_textures = True
    version = None
    file_name = ""
    path = ""
    txd = None

    #######################################################
    @staticmethod
    def normalize_texture_name(image_name):
        clean_name = "".join(
            character
            for character in str(image_name or "")
            if character.isalnum() or character in "_-."
        )
        clean_name = clean_name[:31]
        return clean_name or "texture"

    #######################################################
    @staticmethod
    def _read_bgra_pixels(image, width, height):
        value_count = int(width) * int(height) * 4

        if np is not None:
            try:
                rgba = np.empty(value_count, dtype=np.float32)
                image.pixels.foreach_get(rgba)
                np.nan_to_num(rgba, copy=False, nan=0.0, posinf=1.0, neginf=0.0)
                rgba = np.clip(np.rint(rgba * 255.0), 0.0, 255.0).astype(
                    np.uint8,
                    copy=False,
                )
                rgba = rgba.reshape((height, width, 4))
                bgra = rgba[::-1, :, [2, 1, 0, 3]]
                return bgra.tobytes(order="C")
            except Exception:
                pass

        pixels = list(image.pixels)
        rgba_data = bytearray()
        for row_index in range(height - 1, -1, -1):
            offset = row_index * width * 4
            row_pixels = pixels[offset:offset + width * 4]
            rgba_data.extend(
                max(0, min(255, int(round(float(pixel) * 255.0))))
                for pixel in row_pixels
            )

        return ImageEncoder.rgba_to_bgra8888(rgba_data)

    #######################################################
    @staticmethod
    def _create_texture_native_from_image(image, image_name):
        width, height = (int(image.size[0]), int(image.size[1]))
        if width <= 0 or height <= 0:
            raise ValueError("Texture image has no pixel dimensions")

        texture_native = txd.TextureNative()
        texture_native.platform_id = NativePlatformType.D3D9
        texture_native.filter_mode = 0x06
        texture_native.uv_addressing = 0b00010001
        texture_native.name = txd_exporter.normalize_texture_name(image_name)
        texture_native.mask = ""
        texture_native.raster_format_flags = (
            txd.RasterFormat.RASTER_8888 << 8
        ) | 0x05
        texture_native.d3d_format = txd.D3DFormat.D3D_8888
        texture_native.width = width
        texture_native.height = height
        texture_native.depth = 32
        texture_native.num_levels = 1
        texture_native.raster_type = 4
        texture_native.platform_properties = type(
            'PlatformProperties',
            (),
            {
                'alpha': True,
                'cube_texture': False,
                'auto_mipmaps': False,
                'compressed': False,
            },
        )()
        texture_native.palette = b''
        texture_native.pixels = [
            txd_exporter._read_bgra_pixels(image, width, height)
        ]
        return texture_native

    #######################################################
    @staticmethod
    def extract_texture_info_from_name(name):
        """Extract texture info from TXD import naming pattern"""
        pattern = r'^[^/]+\.txd/([^/]+)/(\d+)$'
        match = re.match(pattern, name)
        if match:
            return match.group(1), int(match.group(2))
        else:
            return name, 0

    #######################################################
    @staticmethod
    def get_used_textures(objects_to_scan=None):
        """Collect textures that are used in scene materials"""
        used_textures = set()
        seen_materials = set()
        
        # Use provided objects or all scene objects
        objects = objects_to_scan if objects_to_scan is not None else bpy.context.scene.objects
        
        for obj in objects:
            for mat_slot in obj.material_slots:
                mat = mat_slot.material
                if not mat:
                    continue

                try:
                    material_key = mat.as_pointer()
                except Exception:
                    material_key = id(mat)
                if material_key in seen_materials:
                    continue
                seen_materials.add(material_key)

                node_tree = mat.node_tree
                if not node_tree:
                    continue

                for node in node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image is not None:
                        texture_name = texture_export_name(node.label, node.image.name)
                        used_textures.add((texture_name, node.image))

        return used_textures

    #######################################################
    @staticmethod
    def populate_textures(objects_to_scan=None):
        self = txd_exporter

        self.txd.native_textures = []

        # Determine which textures to export based on context
        if objects_to_scan is not None:
            # Mass export mode: only export textures used by specific objects
            used_textures = self.get_used_textures(objects_to_scan)
        elif self.only_used_textures:
            # Single export with "only used textures" option
            used_textures = self.get_used_textures()
        else:
            # Single export, all textures
            used_textures = set()
            for image in bpy.data.images:
                # Skip invalid/system textures
                if (image.name.startswith("//") or
                    image.name in ["Render Result", "Viewer Node"] or
                    not image.name.strip() or
                    image.size[0] == 0 or image.size[1] == 0):
                    continue

                # Extract texture name from node.label (in case it follows TXD naming pattern)
                texture_name, mipmap_level = self.extract_texture_info_from_name(image.name)

                # Skip mipmaps
                if mipmap_level > 0:
                    continue

                texture_name = texture_export_name("", texture_name)
                used_textures.add((texture_name, image))

        for texture_name, image in used_textures:
            # Skip images without pixel data
            if not hasattr(image, 'pixels') or len(image.pixels) == 0:
                continue

            texture_native = txd_exporter._create_texture_native_from_image(
                image, texture_name
            )
            self.txd.native_textures.append(texture_native)

    #######################################################
    @staticmethod
    def export_texture_items(
        texture_items,
        file_name,
        version=None,
        progress_callback=None,
    ):
        self = txd_exporter

        normalized_items = []
        seen_names = set()
        for texture_name, image in texture_items:
            clean_name = self.normalize_texture_name(texture_name)
            name_key = clean_name.lower()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)

            if image is None:
                continue
            try:
                width, height = int(image.size[0]), int(image.size[1])
                pixel_count = len(image.pixels)
            except Exception:
                continue
            if width <= 0 or height <= 0 or pixel_count < width * height * 4:
                continue

            normalized_items.append((clean_name, image))

        normalized_items.sort(key=lambda item: (item[0].lower(), item[0]))

        self.txd = txd.txd()
        self.txd.device_id = txd.DeviceType.DEVICE_D3D9
        self.txd.native_textures = []

        total = len(normalized_items)
        for index, (texture_name, image) in enumerate(normalized_items, 1):
            self.txd.native_textures.append(
                self._create_texture_native_from_image(image, texture_name)
            )
            if progress_callback is not None:
                progress_callback(index, total, texture_name)

        self.txd.write_file(
            file_name or self.file_name,
            self.version if version is None else version,
        )
        return len(self.txd.native_textures)

    #######################################################
    @staticmethod
    def export_textures(objects_to_scan=None, file_name=None):
        self = txd_exporter

        if objects_to_scan is not None:
            used_textures = self.get_used_textures(objects_to_scan)
        elif self.only_used_textures:
            used_textures = self.get_used_textures()
        else:
            used_textures = set()
            for image in bpy.data.images:
                if (
                    image.name.startswith("//")
                    or image.name in ["Render Result", "Viewer Node"]
                    or not image.name.strip()
                    or image.size[0] == 0
                    or image.size[1] == 0
                ):
                    continue

                texture_name, mipmap_level = self.extract_texture_info_from_name(
                    image.name
                )
                if mipmap_level > 0:
                    continue
                used_textures.add((texture_export_name("", texture_name), image))

        return self.export_texture_items(
            used_textures,
            file_name or self.file_name,
            version=self.version,
        )

    #######################################################
    @staticmethod
    def export_txd(file_name):
        self = txd_exporter

        self.file_name = file_name

        if self.mass_export:
            # Export TXD files per selected object
            selected_objects = bpy.context.selected_objects

            if not selected_objects:
                print("No objects selected for mass export, exporting all textures to single file")
                self.export_textures()
                return

            selected_objects_num = 0

            for obj in bpy.context.selected_objects:
                # Only export for objects that have materials
                if not obj.material_slots:
                    continue

                # Create filename based on object name
                safe_name = "".join(c for c in obj.name if c.isalnum() or c in "_-.")
                file_name = os.path.join(self.path, f"{safe_name}.txd")
                print(f"Exporting textures for object '{obj.name}' to {file_name}")

                # Export textures used by this specific object only
                self.export_textures([obj], file_name)
                selected_objects_num += 1

            print(f"Mass export completed for {selected_objects_num} objects")

        else:
            self.export_textures()

#######################################################
def export_txd(options):

    txd_exporter.mass_export        = options.get('mass_export', False)
    txd_exporter.only_used_textures = options.get('only_used_textures', True)
    txd_exporter.version            = options.get('version', 0x36003)

    txd_exporter.path               = options['directory']

    txd_exporter.export_txd(options['file_name'])
