# DemonFF - Blender scripts for working with Renderware & R*/SA-MP/open.mp formats in Blender
# 2023 - 2027 spicybung

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
import math
import re
from ..gtaLib.binary import writeAtomic

from bpy_extras.io_utils import ExportHelper


#######################################################
class EXPORT_OT_demonff_ide(bpy.types.Operator, ExportHelper):
    bl_idname = "scene.demonff_export_ide"
    bl_label = "Export IDE (Text)"
    bl_description = "Export OBJ definitions to a text .ide file (objs section)"
    filename_ext = ".ide"

    filter_glob: bpy.props.StringProperty(default="*.ide", options={'HIDDEN'})

    only_selected: bpy.props.BoolProperty(
        name="Only Selected",
        default=False
    )

    use_unique_ids: bpy.props.BoolProperty(
        name="Unique IDs Only",
        description="Export only one entry per IDE_ID (avoids duplicates)",
        default=True
    )

    #######################################################
    def execute(self, context):

        objs = []
        for obj in context.scene.objects:
            if self.only_selected and not obj.select_get():
                continue
            if not hasattr(obj, "dff"):
                continue
            if obj.dff.type != 'OBJ':
                continue

            ide_id = int(obj.get("IDE_ID", 0) or 0)
            txd_name = str(obj.get("TXD_Name", "") or "").strip()
            if ide_id <= 0 or txd_name == "":
                continue

            objs.append(obj)

        if self.use_unique_ids:
            unique = {}
            for obj in objs:
                unique[int(obj.get("IDE_ID", 0) or 0)] = obj
            objs = list(unique.values())

        try:
            lines = ['objs']
            for obj in objs:
                ide_id = int(obj.get('IDE_ID', 0) or 0)
                model_name = str(obj.get('DFF_Name', '') or re.sub(r'\.\d{3,}$', '', obj.name)).strip()
                txd_name = str(obj.get('TXD_Name', '') or '').strip()
                if any(character in model_name + txd_name for character in ',\r\n'):
                    raise ValueError('IDE model and texture names cannot contain commas or line breaks')
                drawdist = float(obj.get('DrawDistance', 300.0))
                if not math.isfinite(drawdist) or drawdist < 0:
                    raise ValueError('IDE draw distance must be finite and nonnegative')
                flags = int(obj.get('IDE_Flags', 0) or 0)
                lines.append(f'{ide_id}, {model_name}, {txd_name}, 1, {drawdist:.6f}, {flags}')
            lines.append('end')
            writeAtomic(bpy.path.abspath(self.filepath), ('\n'.join(lines) + '\n').encode('latin-1'))
        except (OSError, ValueError, UnicodeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported {len(objs)} IDE entries")
        return {'FINISHED'}
