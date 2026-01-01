# DemonFF - Blender scripts for working with Renderware & R*/SA-MP/open.mp formats in Blender
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

import re
import bpy
import gpu
import bmesh
import struct

from .mdl_ot import IMPORT_OT_mdl_custom

class MDL_MT_ImportChoice(bpy.types.Menu):
    bl_label = "DemonFF"

    def draw(self, context):
        layout = self.layout
        layout.operator(IMPORT_OT_mdl_custom.bl_idname, text="DemonFF MDL (.mdl)")

def import_mdl_func(self, context):
    self.layout.menu("MDL_MT_ImportChoice", text="DemonFF")

def menu_func_import(self, context):
    self.layout.menu(MDL_MT_ImportChoice.bl_idname, text="DemonFF")

def register():
    bpy.utils.register_class(MDL_MT_ImportChoice)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(MDL_MT_ImportChoice)

if __name__ == "__main__":
    register()