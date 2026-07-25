import math

from mathutils import Euler, Matrix, Quaternion, Vector


GTA_EULER_ORDER = 'XYZ'


def normalized_quaternion(quaternion):
    rotation = quaternion.copy()
    if rotation.magnitude > 1.0e-12:
        rotation.normalize()
    else:
        rotation = Quaternion((1.0, 0.0, 0.0, 0.0))
    return rotation


def ipl_quaternion_to_blender(rot_x, rot_y, rot_z, rot_w):
    # GTA reads IPL quaternions as axis + W, then applies a negative angle.
    # Blender's equivalent quaternion is (-W, X, Y, Z).
    return normalized_quaternion(
        Quaternion((
            -float(rot_w),
            float(rot_x),
            float(rot_y),
            float(rot_z),
        ))
    )


def blender_quaternion_to_ipl(quaternion):
    # This is the exact inverse of ipl_quaternion_to_blender.
    rotation = normalized_quaternion(quaternion)
    return rotation.x, rotation.y, rotation.z, -rotation.w


def gta_euler_degrees_to_quaternion(rot_x, rot_y, rot_z):
    # CreateObject and CreateDynamicObject consume X, Y, Z Euler angles.
    return Euler(
        (
            math.radians(float(rot_x)),
            math.radians(float(rot_y)),
            math.radians(float(rot_z)),
        ),
        GTA_EULER_ORDER,
    ).to_quaternion()


def quaternion_to_gta_euler_degrees(quaternion):
    rotation = normalized_quaternion(quaternion)
    euler = rotation.to_euler(GTA_EULER_ORDER)
    return (
        math.degrees(euler.x),
        math.degrees(euler.y),
        math.degrees(euler.z),
    )


def build_ipl_instance_matrix(position, quaternion, scale):
    location = Vector((
        float(position[0]),
        float(position[1]),
        float(position[2]),
    ))
    rotation = ipl_quaternion_to_blender(
        quaternion[0],
        quaternion[1],
        quaternion[2],
        quaternion[3],
    )
    scale_vector = Vector((
        float(scale[0]),
        float(scale[1]),
        float(scale[2]),
    ))

    return (
        Matrix.Translation(location)
        @ rotation.to_matrix().to_4x4()
        @ Matrix.Diagonal((
            scale_vector.x,
            scale_vector.y,
            scale_vector.z,
            1.0,
        ))
    )
