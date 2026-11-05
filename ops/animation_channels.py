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

import json
import math

import bpy
from .blender_compat import actionCurves, actionGroups
from bpy.app.handlers import persistent
from mathutils import Euler, Matrix, Quaternion, Vector


def boneChannelPath(bone_name, channel):
    return 'pose.bones[' + json.dumps(str(bone_name)) + '].' + channel


def actionBoneCurveLookup(action, bone_name, owner=None):
    prefix = 'pose.bones[' + json.dumps(str(bone_name)) + '].'
    return {(curve.data_path[len(prefix):], curve.array_index): curve
            for curve in actionCurves(action, owner=owner, create=False) if curve.data_path.startswith(prefix)}


def sampleActionBoneBasis(action, bone_name, frame, rotation_mode='XYZ', owner=None):
    curves = actionBoneCurveLookup(action, bone_name, owner)
    values = {}
    for channel, defaults in (('location', (0.0, 0.0, 0.0)),
                              ('rotation_quaternion', (1.0, 0.0, 0.0, 0.0)),
                              ('scale', (1.0, 1.0, 1.0))):
        values[channel] = [curves[(channel, index)].evaluate(frame)
                           if (channel, index) in curves else default
                           for index, default in enumerate(defaults)]
    quaternion = Quaternion(values['rotation_quaternion'])
    if not any(channel == 'rotation_quaternion' for channel, index in curves):
        if any(channel == 'rotation_euler' for channel, index in curves):
            angles = [curves[('rotation_euler', index)].evaluate(frame) if ('rotation_euler', index) in curves else 0.0 for index in range(3)]
            order = rotation_mode if rotation_mode in ('XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX') else 'XYZ'
            quaternion = Euler(angles, order).to_quaternion()
        elif any(channel == 'rotation_axis_angle' for channel, index in curves):
            angle = curves[('rotation_axis_angle', 0)].evaluate(frame) if ('rotation_axis_angle', 0) in curves else 0.0
            axis = Vector([curves[('rotation_axis_angle', index)].evaluate(frame) if ('rotation_axis_angle', index) in curves else (1.0 if index == 3 else 0.0) for index in range(1, 4)])
            quaternion = Quaternion(axis.normalized(), angle) if axis.length > 0.000001 else Quaternion()
    quaternion.normalize()
    return (Matrix.Translation(Vector(values['location'])) @ quaternion.to_matrix().to_4x4()
            @ Matrix.Diagonal((*values['scale'], 1.0)))


def writeActionChannel(action, bone_name, channel, samples):
    samples = list(samples)
    if not samples:
        return
    widths = {'location': 3, 'scale': 3, 'rotation_euler': 3,
              'rotation_quaternion': 4, 'rotation_axis_angle': 4}
    if channel not in widths:
        raise ValueError('Unsupported bone animation channel ' + str(channel))
    ordered = {}
    for frame, values in samples:
        frame = float(frame)
        values = tuple(float(value) for value in values)
        if len(values) != widths[channel] or not math.isfinite(frame) or not all(math.isfinite(value) for value in values):
            raise ValueError('Animation samples must contain finite frames and complete channel values')
        ordered[frame] = values
    samples = sorted(ordered.items())
    path = boneChannelPath(bone_name, channel)
    for component in range(widths[channel]):
        curve = actionCurves(action).find(path, index=component)
        if curve is not None:
            actionCurves(action).remove(curve)
        curve = actionCurves(action).new(path, index=component, action_group=bone_name)
        curve.keyframe_points.add(len(samples))
        coordinates = []
        for frame, values in samples:
            coordinates.extend((frame, values[component]))
        curve.keyframe_points.foreach_set('co', coordinates)
        for key in curve.keyframe_points:
            key.interpolation = 'LINEAR'
        curve.update()


def resetUnkeyedActionChannels(armature, action):
    keyed = {(curve.data_path, curve.array_index) for curve in actionCurves(action, owner=armature, create=False)} if action else set()
    for bone in armature.pose.bones:
        rotation = 'rotation_quaternion' if bone.rotation_mode == 'QUATERNION' else (
            'rotation_axis_angle' if bone.rotation_mode == 'AXIS_ANGLE' else 'rotation_euler')
        defaults = {'location': (0.0, 0.0, 0.0), 'scale': (1.0, 1.0, 1.0),
                    'rotation_quaternion': (1.0, 0.0, 0.0, 0.0),
                    'rotation_axis_angle': (0.0, 0.0, 0.0, 1.0),
                    'rotation_euler': (0.0, 0.0, 0.0)}
        for channel in ('location', rotation, 'scale'):
            path = boneChannelPath(bone.name, channel)
            values = list(getattr(bone, channel))
            for index, value in enumerate(defaults[channel]):
                if (path, index) not in keyed:
                    values[index] = value
            setattr(bone, channel, values)


@persistent
def resetChangedAnimationActions(scene, depsgraph):
    for obj in scene.objects:
        if obj.type != 'ARMATURE' or obj.animation_data is None:
            continue
        action = obj.animation_data.action
        if action is None or not (action.get('DemonFF_IFP_Retarget_Version') or action.get('DemonFF_ANIM_Imported_Action')):
            if 'DemonFF_Active_Action_State' in obj:
                del obj['DemonFF_Active_Action_State']
            continue
        token = str(action.as_pointer())
        if obj.get('DemonFF_Active_Action_State') == token:
            continue
        obj['DemonFF_Active_Action_State'] = token
        resetUnkeyedActionChannels(obj, action)


def registerAnimationEvents():
    unregisterAnimationEvents()
    bpy.app.handlers.depsgraph_update_post.append(resetChangedAnimationActions)


def unregisterAnimationEvents():
    handlers = bpy.app.handlers.depsgraph_update_post
    for handler in list(handlers):
        if getattr(handler, '__module__', '') == __name__ and getattr(handler, '__name__', '') == 'resetChangedAnimationActions':
            handlers.remove(handler)
