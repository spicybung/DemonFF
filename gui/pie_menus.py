# DemonFF - Blender scripts to edit basic GTA formats to work in conjunction with SAMP/open.mp
# 2023 - 2025 SpicyBung

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

addon_keymaps = []

#######################################################
class DFF_MT_ToolWheel(bpy.types.Menu):
    bl_label = "DemonFF - Quick Menu"
    bl_idname = "DFF_MT_tool_wheel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'

    def draw(self, context):
        pie = self.layout.menu_pie()
        pie.operator("wm.call_menu", text="Import DFF").name = "DFF_MT_ImportChoice"
        pie.operator("import_scene.txd", text="Import TXD")
        pie.operator("import_scene.img", text="Import IMG")
        pie.operator("object.export_to_ipl", text="Export IPL")
        pie.operator("object.force_doubleside_mesh", text="Force Doubleside Mesh")


def register_keymaps():
    wm = bpy.context.window_manager
    if wm.keyconfigs.addon:
        km = wm.keyconfigs.addon.keymaps.new(name="3D View", space_type='VIEW_3D')
        kmi = km.keymap_items.new("wm.call_menu_pie", type='F', value='PRESS')
        kmi.properties.name = "DFF_MT_tool_wheel"
        addon_keymaps.append((km, kmi))

def unregister_keymaps():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
