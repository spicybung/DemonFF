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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import bpy

addon_keymaps = []


class DFF_OT_import_from_pie(bpy.types.Operator):
    bl_idname = "demonff.import_dff_from_pie"
    bl_label = "Import DFF/Col"
    bl_description = "Open DemonFF's DFF/Col importer"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        try:
            return bpy.ops.import_scene.dff_custom('INVOKE_DEFAULT')
        except RuntimeError as error:
            self.report({'ERROR'}, f"Could not open DemonFF DFF import: {error}")
            return {'CANCELLED'}

    def execute(self, context):
        try:
            return bpy.ops.import_scene.dff_custom('INVOKE_DEFAULT')
        except RuntimeError as error:
            self.report({'ERROR'}, f"Could not open DemonFF DFF import: {error}")
            return {'CANCELLED'}


class DFF_MT_ToolWheel(bpy.types.Menu):
    bl_label = "DemonFF - Quick Menu"
    bl_idname = "DFF_MT_tool_wheel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'

    def draw(self, context):
        pie = self.layout.menu_pie()

        pie.operator(
            DFF_OT_import_from_pie.bl_idname,
            text="Import DFF/Col",
            icon='IMPORT',
        )
        pie.operator(
            "import_scene.txd",
            text="Import TXD",
            icon='TEXTURE',
        )
        pie.operator(
            "import_scene.img",
            text="Import IMG",
            icon='FILE_FOLDER',
        )
        pie.operator(
            "object.export_to_ipl",
            text="Export IPL",
            icon='EXPORT',
        )
        pie.operator(
            "import_scene.txd_samp",
            text="Import TXD (SAMP)",
            icon='TEXTURE',
        )


def register_keymaps():
    wm = bpy.context.window_manager
    addon_keyconfig = wm.keyconfigs.addon
    if addon_keyconfig is None:
        return

    unregister_keymaps()

    keymap = addon_keyconfig.keymaps.new(
        name="3D View",
        space_type='VIEW_3D',
    )
    keymap_item = keymap.keymap_items.new(
        "wm.call_menu_pie",
        type='F',
        value='PRESS',
    )
    keymap_item.properties.name = DFF_MT_ToolWheel.bl_idname
    addon_keymaps.append((keymap, keymap_item))


def unregister_keymaps():
    for keymap, keymap_item in addon_keymaps:
        try:
            keymap.keymap_items.remove(keymap_item)
        except (ReferenceError, RuntimeError):
            pass

    addon_keymaps.clear()
