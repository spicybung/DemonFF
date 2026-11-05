"""Checks shared by the regular and SA-MP DFF writers."""
from math import isfinite


def validateGeometry(geometry):
    vertex_count = len(geometry.vertices)
    if len(geometry.uv_layers) > 255:
        raise ValueError('DFF geometry has more than 255 UV layers')
    channels = [('positions', geometry.vertices, 3)]
    if geometry.normals and geometry.export_flags.get('export_normals', True):
        channels.append(('normals', geometry.normals, 3))
    if geometry.prelit_colors:
        channels.append(('vertex colors', geometry.prelit_colors, 4))
    for layer in geometry.uv_layers:
        channels.append(('UV coordinates', layer, 2))
    for name, values, width in channels:
        if len(values) != vertex_count:
            raise ValueError('DFF %s count does not match its vertex count' % name)
        for value in values:
            if len(value) != width or any(not isfinite(component) for component in value):
                raise ValueError('DFF %s contain invalid values' % name)
    for face in geometry.triangles:
        if any(not 0 <= index < vertex_count for index in (face.a, face.b, face.c)):
            raise ValueError('DFF triangle references a vertex outside its geometry')
        if any(index > 65535 for index in (face.a, face.b, face.c)):
            raise ValueError('DFF triangle index does not fit its 16-bit triangle record')
        if not 0 <= face.material < len(geometry.materials):
            raise ValueError('DFF triangle references a material outside its geometry')
    skin = geometry.extensions.get('skin')
    if skin is not None:
        if len(skin.vertex_bone_indices) != vertex_count or len(skin.vertex_bone_weights) != vertex_count:
            raise ValueError('DFF skin count does not match its vertex count')
        if len(skin.bone_matrices) != skin.num_bones:
            raise ValueError('DFF skin matrix count does not match its bone count')
        for indices, weights in zip(skin.vertex_bone_indices, skin.vertex_bone_weights):
            if len(indices) != 4 or len(weights) != 4:
                raise ValueError('DFF skin must store four weight slots per vertex')
            for bone, weight in zip(indices, weights):
                if not isfinite(weight) or weight < 0:
                    raise ValueError('DFF skin contains an invalid weight')
                if weight > 0 and not 0 <= bone < skin.num_bones:
                    raise ValueError('DFF skin references a bone outside its skeleton')
