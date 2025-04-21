import bpy

addon_keymaps = []

class DFF_MT_ToolWheel(bpy.types.Menu):
    bl_label = "DemonFF Quick Menu"
    bl_idname = "DFF_MT_tool_wheel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'

    def draw(self, context):
        print("🌀 Pie menu triggered")
        pie = self.layout.menu_pie()
        pie.operator("wm.call_menu", text="Import DFF").name = "DFF_MT_ImportChoice"
        pie.operator("wm.call_menu", text="Export DFF").name = "DFF_MT_ExportChoice"

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
