# DemonFF - action channels
# 2026 spicybung

import json

import bpy
from bpy.app.handlers import persistent
from mathutils import Euler, Matrix, Quaternion, Vector


def boneChannelPath(bone_name, channel):
    return 'pose.bones[' + json.dumps(str(bone_name)) + '].' + channel


def actionBoneCurveLookup(action, bone_name):
    prefix = 'pose.bones[' + json.dumps(str(bone_name)) + '].'
    return {(curve.data_path[len(prefix):], curve.array_index): curve
            for curve in action.fcurves if curve.data_path.startswith(prefix)}


def sampleActionBoneBasis(action, bone_name, frame, rotation_mode='XYZ'):
    curves = actionBoneCurveLookup(action, bone_name)
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
    if not samples:
        return
    path = boneChannelPath(bone_name, channel)
    for component in range(len(samples[0][1])):
        curve = action.fcurves.find(path, index=component)
        if curve is not None:
            action.fcurves.remove(curve)
        curve = action.fcurves.new(path, index=component, action_group=bone_name)
        curve.keyframe_points.add(len(samples))
        coordinates = []
        for frame, values in samples:
            coordinates.extend((float(frame), float(values[component])))
        curve.keyframe_points.foreach_set('co', coordinates)
        for key in curve.keyframe_points:
            key.interpolation = 'LINEAR'
        curve.update()


def resetUnkeyedActionChannels(armature, action):
    paths = {curve.data_path for curve in action.fcurves} if action else set()
    for bone in armature.pose.bones:
        if boneChannelPath(bone.name, 'location') not in paths:
            bone.location = (0.0, 0.0, 0.0)
        if boneChannelPath(bone.name, 'rotation_quaternion') not in paths:
            bone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        if boneChannelPath(bone.name, 'scale') not in paths:
            bone.scale = (1.0, 1.0, 1.0)


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
