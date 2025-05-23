# DemonFF - Blender scripts for working with Renderware & R*/SA-MP/open.mp formats in Blender
# 2023 - 2025 SpicyBung

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
import time

from bpy.app.handlers import depsgraph_update_post, load_post, persistent


#######################################################
class _StateMeta(type):
    def __init__(cls, *args, **kwargs):
        cls.last_export_refresh = 0

#######################################################
class State(metaclass=_StateMeta):

    @classmethod
    def update_scene(cls, scene=None):

        def append_frame_object(ob):
            if ob.parent and ob.parent not in frame_objects_set:
                append_frame_object(ob.parent)
            frame_objects_set.add(ob)
            ordered_frame_objcets.append(ob)

        def update_frame_status(ob):
            is_frame, is_frame_locked = ob.dff.is_frame, False
            if ob.parent and not any(ch.dff.type == 'OBJ' for ch in ob.children):
                if ob.parent.type == 'ARMATURE' and not ob.parent_bone:
                    is_frame, is_frame_locked = False, True
            else:
                is_frame, is_frame_locked = True, True

            if ob.dff.is_frame != is_frame:
                ob.dff.is_frame = is_frame
            if ob.dff.is_frame_locked != is_frame_locked:
                ob.dff.is_frame_locked = is_frame_locked
            return is_frame

        scene = scene or bpy.context.scene
        frame_objects, atomic_objects = [], []

        for ob in scene.objects:
            if ob.dff.type != 'OBJ':
                continue

            if ob.type == 'MESH':
                atomic_objects.append(ob)
                if update_frame_status(ob):
                    frame_objects.append(ob)

            elif ob.type in ('EMPTY', 'ARMATURE'):
                frame_objects.append(ob)

        frame_objects.sort(key=lambda ob: ob.dff.frame_index)
        atomic_objects.sort(key=lambda ob: ob.dff.atomic_index)

        ordered_frame_objcets, frame_objects_set = [], set()
        for ob in frame_objects:
            if ob not in frame_objects_set:
                append_frame_object(ob)
        frame_objects = ordered_frame_objcets

        scene.dff.frames.clear()
        for i, ob in enumerate(frame_objects):
            frame_prop = scene.dff.frames.add()
            frame_prop.obj = ob
            frame_prop.icon = 'ARMATURE_DATA' if ob.type == 'ARMATURE' else 'EMPTY_DATA'
            ob.dff.frame_index = i

        scene.dff.atomics.clear()
        for i, ob in enumerate(atomic_objects):
            atomic_prop = scene.dff.atomics.add()
            atomic_prop.obj = ob

            frame_obj = None
            for modifier in ob.modifiers:
                if modifier.type == 'ARMATURE':
                    frame_obj = modifier.object
                    break
            if frame_obj is None:
                frame_obj = ob.parent
            atomic_prop.frame_obj = frame_obj

            ob.dff.atomic_index = i

        cls.last_export_refresh = time.time()

    @staticmethod
    @persistent
    def _onDepsgraphUpdate(scene):
        if scene.dff.real_time_update:
            if scene == bpy.context.scene and time.time() - State.last_export_refresh > 0.3:
                State.update_scene(scene)

    @staticmethod
    @persistent
    def _onLoad(_):
        State.update_scene()

    @classmethod
    def hook_events(cls):
        if not cls.update_scene in depsgraph_update_post:
            depsgraph_update_post.append(cls._onDepsgraphUpdate)
            load_post.append(cls._onLoad)

    @classmethod
    def unhook_events(cls):
        if cls.update_scene in depsgraph_update_post:
            depsgraph_update_post.remove(cls._onDepsgraphUpdate)
            load_post.remove(cls._onLoad)