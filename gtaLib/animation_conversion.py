# DemonFF - animation container conversion
# 2026 spicybung

import math
import struct
from dataclasses import dataclass, field
from pathlib import Path

from .anim import (
    AnimExportBone, AnimExportEntry, AnimExportFrame, buildAnimBytes,
    normalizeRotationXyzw, readAnimFile, resolvePedAnimBoneId, resolveAnimBoneName,
)
from ..data.bone_data import DIRECT_ID_NAME_HINTS, directIdFromBoneName


@dataclass
class ConversionTrack:
    bone_id: int
    name: str
    frames: list
    translation: bool = False
    rotation: bool = True
    scale: bool = False


@dataclass
class ConversionClip:
    name: str
    tracks: list = field(default_factory=list)
    duration: float = 0.0


def fixedName(value):
    return str(value).encode('ascii', errors='replace')[:24].ljust(24, b'\0')


def checkedInt16(value, label):
    if not math.isfinite(value):
        raise ValueError(label + ' is not finite')
    integer = int(round(value))
    if not -32768 <= integer <= 32767:
        raise ValueError(label + ' exceeds the ANP3 signed 16-bit range')
    return integer


def animToConversionClips(anim_file):
    clips = []
    for entry in anim_file.animations:
        clip = ConversionClip(entry.name, duration=float(entry.total_time))
        for bone in entry.bones:
            bone_id, reason = resolvePedAnimBoneId(bone)
            named_target = resolveAnimBoneName(bone)
            if bone_id is None and named_target is None:
                raise ValueError(f'{entry.name}: cannot resolve animation bone key 0x{bone.bone_key:08X}')
            if bone_id is None:
                bone_id = -1
            if len(bone.frames) != bone.frame_count:
                raise ValueError(f'{entry.name}: truncated source track for BoneID {bone_id}')
            if bone.has_scale:
                raise ValueError(f'{entry.name}: scale tracks require ANPK; ANP3 cannot store them')
            if not bone.has_rotation:
                raise ValueError(f'{entry.name}: translation-only tracks need a source skeleton to supply their rotation')
            names = DIRECT_ID_NAME_HINTS.get(bone_id, ())
            name = named_target or (names[0] if names else 'Bone_' + str(bone_id))
            frames = [AnimExportFrame(frame.absolute_time, frame.rotation_xyzw, frame.translation_xyz, frame.scale_xyz) for frame in bone.frames]
            clip.tracks.append(ConversionTrack(bone_id, name, frames, bone.has_translation))
        clips.append(clip)
    return clips


def buildAnp3Bytes(clips, package_name='DemonFF'):
    clips = list(clips)
    if not clips:
        raise ValueError('No animations to convert')
    result = bytearray(b'ANP3' + b'\0' * 4 + fixedName(package_name) + struct.pack('<I', len(clips)))
    for clip in clips:
        if not clip.tracks:
            raise ValueError(f'{clip.name}: no bone tracks')
        payload = bytearray()
        key_bytes = 0
        for track in clip.tracks:
            if not track.frames:
                raise ValueError(f'{clip.name}: bone {track.bone_id} has no frames')
            frames = sorted(track.frames, key=lambda frame: frame.time)
            frames = list(frames)
            if clip.duration > frames[-1].time + 1.0 / 120.0:
                last = frames[-1]
                frames.append(AnimExportFrame(clip.duration, last.rotation_xyzw, last.translation_xyz, last.scale_xyz))
            frame_type = 4 if track.translation else 3
            payload.extend(fixedName(track.name))
            payload.extend(struct.pack('<IIi', frame_type, len(frames), int(track.bone_id)))
            last_tick = -1
            for frame in frames:
                if not math.isfinite(frame.time) or frame.time < 0.0:
                    raise ValueError(f'{clip.name}: invalid key time {frame.time}')
                tick = int(round(frame.time * 60.0))
                if tick > 65535:
                    raise ValueError(f'{clip.name}: duration exceeds the ANP3 time range')
                if tick < last_tick:
                    raise ValueError(f'{clip.name}: keys are not ordered')
                last_tick = tick
                rotation = normalizeRotationXyzw(frame.rotation_xyzw)
                values = [checkedInt16(component * 4096.0, 'Rotation') for component in rotation]
                payload.extend(struct.pack('<hhhhH', *values, tick))
                key_bytes += 10
                if track.translation:
                    position = [checkedInt16(component * 4096.0, 'Translation') for component in frame.translation_xyz]
                    payload.extend(struct.pack('<hhh', *position))
                    key_bytes += 6
        result.extend(fixedName(clip.name))
        result.extend(struct.pack('<III', len(clip.tracks), key_bytes, 1))
        result.extend(payload)
    struct.pack_into('<I', result, 4, len(result) - 8)
    result.extend(b'\0' * ((-len(result)) % 2048))
    return bytes(result)


def readAnp3Bytes(data):
    if len(data) < 36 or data[:4] != b'ANP3':
        raise ValueError('Expected a San Andreas ANP3 IFP')
    logical_size = struct.unpack_from('<I', data, 4)[0] + 8
    if logical_size < 36 or logical_size > len(data):
        raise ValueError('Invalid ANP3 size')
    cursor = 32

    def consume(size):
        nonlocal cursor
        if size < 0 or cursor + size > logical_size:
            raise ValueError(f'Truncated ANP3 record at 0x{cursor:X}')
        value = data[cursor:cursor + size]
        cursor += size
        return value

    def name():
        return consume(24).split(b'\0', 1)[0].decode('latin-1')

    count = struct.unpack('<I', consume(4))[0]
    if count > (logical_size - cursor) // 36:
        raise ValueError('Invalid ANP3 animation count')
    clips = []
    for index in range(count):
        clip = ConversionClip(name())
        bone_count, key_bytes, unknown = struct.unpack('<III', consume(12))
        if bone_count > (logical_size - cursor) // 36:
            raise ValueError('Invalid ANP3 bone count')
        actual_key_bytes = 0
        for bone_index in range(bone_count):
            bone_name = name()
            frame_type, frame_count, bone_id = struct.unpack('<IIi', consume(12))
            if frame_type not in (3, 4):
                raise ValueError(f'Unsupported ANP3 frame type {frame_type}')
            stride = 16 if frame_type == 4 else 10
            if frame_count > (logical_size - cursor) // stride:
                raise ValueError('Truncated ANP3 keyframes')
            track = ConversionTrack(bone_id, bone_name, [], frame_type == 4)
            for frame_index in range(frame_count):
                x, y, z, w, tick = struct.unpack('<hhhhH', consume(10))
                rotation = normalizeRotationXyzw((x / 4096.0, y / 4096.0, z / 4096.0, w / 4096.0))
                translation = (0.0, 0.0, 0.0)
                if track.translation:
                    translation = tuple(value / 4096.0 for value in struct.unpack('<hhh', consume(6)))
                time = tick / 60.0
                if track.frames and time < track.frames[-1].time:
                    raise ValueError('ANP3 times run backwards')
                track.frames.append(AnimExportFrame(time, rotation, translation))
                clip.duration = max(clip.duration, time)
            actual_key_bytes += frame_count * stride
            clip.tracks.append(track)
        if actual_key_bytes != key_bytes:
            raise ValueError(f'{clip.name}: ANP3 keyframe size does not match its header')
        clips.append(clip)
    if cursor != logical_size:
        raise ValueError('ANP3 logical size does not match its animation records')
    return clips


def conversionClipsToAnim(clips, pad_to_sector=True):
    entries = []
    for clip in clips:
        bones = []
        for track in clip.tracks:
            if track.bone_id == -1:
                import zlib
                key = zlib.crc32(track.name.upper().encode('latin-1')) ^ 0xFFFFFFFF
                bones.append(AnimExportBone(key, -1, track.frames, track.rotation, track.translation, track.scale, False))
            elif 0 <= track.bone_id <= 65535:
                bones.append(AnimExportBone(track.bone_id, track.bone_id, track.frames, track.rotation, track.translation, track.scale, True))
            else:
                raise ValueError(f'{clip.name}: bone {track.name!r} has no valid animation BoneID')
        entries.append(AnimExportEntry(clip.name, bones, total_time=clip.duration))
    return buildAnimBytes(entries, pad_to_sector=pad_to_sector)


def convertAnimationFile(source_path, destination_path, target_game=None):
    source = Path(source_path)
    destination = Path(destination_path)
    if source.resolve() == destination.resolve():
        raise ValueError('Choose a different output file')
    magic = source.read_bytes()[:4]
    if magic == b'mina':
        clips = animToConversionClips(readAnimFile(str(source)))
        target_game = target_game or 'SAN_ANDREAS'
    elif magic == b'ANP3':
        clips = readAnp3Bytes(source.read_bytes())
        target_game = target_game or 'VCS'
    elif magic == b'ANPK':
        clips = readAnpkBytes(source.read_bytes())
        target_game = target_game or 'VCS'
    else:
        raise ValueError('Direct conversion reads Stories ANIM, ANP3 IFP and ANPK IFP')
    if target_game == 'MANHUNT_1' and any(track.bone_id < 1000 for clip in clips for track in clip.tracks):
        raise ValueError('Import onto a rig, then export with Target Game set to Manhunt to convert the bone hierarchy')
    output = buildTargetAnimationBytes(clips, target_game, source.stem)
    destination.write_bytes(output)
    return len(clips), len(output)


def chunkBytes(tag, payload):
    return tag + struct.pack('<I', len(payload)) + payload + b'\0' * ((-len(payload)) % 4)


def buildAnpkBytes(clips, package_name='DemonFF'):
    clips = list(clips)
    package_info = struct.pack('<I', len(clips)) + str(package_name).encode('latin-1', errors='replace') + b'\0'
    payload = bytearray(chunkBytes(b'INFO', package_info))
    for clip in clips:
        records = bytearray(chunkBytes(b'INFO', struct.pack('<II', len(clip.tracks), 0)))
        for track in clip.tracks:
            # III/VC bind sequences by frame name. Their ANIM header is 48 bytes.
            header = str(track.name).encode('latin-1', errors='replace')[:28].ljust(28, b'\0')
            header += struct.pack('<IIIII', len(track.frames), 0, 0, 0, 0)
            keys = bytearray()
            for frame in track.frames:
                x, y, z, w = normalizeRotationXyzw(frame.rotation_xyzw)
                if track.rotation:
                    keys.extend(struct.pack('<4f', -x, -y, -z, w))
                if track.translation:
                    keys.extend(struct.pack('<3f', *frame.translation_xyz))
                if track.scale:
                    keys.extend(struct.pack('<3f', *frame.scale_xyz))
                keys.extend(struct.pack('<f', frame.time))
            key_type = ('K' + ('R' if track.rotation else '0') + ('T' if track.translation else '0') + ('S' if track.scale else '0')).encode('ascii')
            records.extend(chunkBytes(b'CPAN', chunkBytes(b'ANIM', header) + chunkBytes(key_type, keys)))
        name = str(clip.name).encode('latin-1', errors='replace') + b'\0'
        payload.extend(chunkBytes(b'NAME', name))
        payload.extend(chunkBytes(b'DGAN', records))
    result = bytearray(b'ANPK' + struct.pack('<I', len(payload)) + payload)
    result.extend(b'\0' * ((-len(result)) % 2048))
    return bytes(result)


def buildManhunt1Bytes(clips, package_name='DemonFF'):
    clips = list(clips)
    name = str(package_name).encode('latin-1', errors='replace') + b'\0'
    output = bytearray(b'ANCT' + struct.pack('<I', 1) + b'BLOC' + struct.pack('<I', len(name)) + name + b'ANPK' + struct.pack('<I', len(clips)))
    for clip in clips:
        sequences = bytearray()
        payload_size = 0
        for track in clip.tracks:
            if not 1000 <= track.bone_id <= 32767:
                raise ValueError('Manhunt export needs a Manhunt Animation BoneID for ' + track.name)
            frames = sorted(track.frames, key=lambda frame: frame.time)
            if not frames:
                raise ValueError('Manhunt track has no keys: ' + track.name)
            if frames[0].time > 0.0:
                first = frames[0]
                frames.insert(0, AnimExportFrame(0.0, first.rotation_xyzw, first.translation_xyz, first.scale_xyz))
            if len(frames) > 65535:
                raise ValueError('Manhunt track has too many keys')
            frame_type = 2 if track.translation else 1
            sequences.extend(b'SEQU' + struct.pack('<hBH', track.bone_id, frame_type, len(frames)))
            previous_tick = 0
            for frame in frames:
                tick = int(round(frame.time * 2048.0))
                delta = tick - previous_tick
                if not 0 <= delta <= 65535:
                    raise ValueError('Manhunt key interval is outside the 16-bit tick range')
                previous_tick = tick
                rotation = normalizeRotationXyzw(frame.rotation_xyzw)
                x, y, z, w = rotation
                values = [checkedInt16(value * 4096.0, 'Manhunt rotation') for value in (-x, -y, -z, w)]
                sequences.extend(struct.pack('<H4h', delta, *values))
                payload_size += 10
                if track.translation:
                    values = [checkedInt16(value * 2048.0, 'Manhunt translation') for value in frame.translation_xyz]
                    sequences.extend(struct.pack('<3h', *values))
                    payload_size += 6
        name = str(clip.name).encode('latin-1', errors='replace') + b'\0'
        output.extend(b'NAME' + struct.pack('<I', len(name)) + name)
        output.extend(struct.pack('<IIf', len(clip.tracks), payload_size, clip.duration))
        output.extend(sequences)
        output.extend(struct.pack('<IfII', 16, 2.0, 64, 0))
    return bytes(output)


def ifpDataToConversionClips(data, export_translation=True, export_scale=False):
    clips = []
    for animation in data.animations:
        clip = ConversionClip(animation.name)
        for bone in animation.bones:
            frames = []
            for key in bone.keyframes:
                quaternion = key.rot.normalized()
                frames.append(AnimExportFrame(key.time, (quaternion.x, quaternion.y, quaternion.z, quaternion.w), tuple(key.pos), tuple(key.scl)))
                clip.duration = max(clip.duration, key.time)
            translation = export_translation and len(bone.keyframe_type) > 2 and bone.keyframe_type[2] == 'T'
            scale = export_scale and any(any(abs(value - 1.0) > 0.000001 for value in frame.scale_xyz) for frame in frames)
            clip.tracks.append(ConversionTrack(int(bone.bone_id), bone.name, frames, translation, True, scale))
        clips.append(clip)
    return clips


def buildTargetAnimationBytes(clips, target_game, package_name='DemonFF'):
    if target_game in ('GTA_III', 'VICE_CITY'):
        return buildAnpkBytes(clips, package_name)
    if target_game == 'SAN_ANDREAS':
        if any(track.scale for clip in clips for track in clip.tracks):
            raise ValueError('San Andreas ANP3 does not support scale tracks')
        return buildAnp3Bytes(clips, package_name)
    if target_game in ('LCS', 'VCS'):
        return conversionClipsToAnim(clips)
    if target_game == 'MANHUNT_1':
        return buildManhunt1Bytes(clips, package_name)
    raise ValueError('Unsupported animation target game: ' + str(target_game))


TARGET_GAME_ITEMS = (
    ('GTA_III', 'GTA III', 'ANPK IFP'),
    ('VICE_CITY', 'GTA Vice City', 'ANPK IFP'),
    ('SAN_ANDREAS', 'GTA San Andreas', 'ANP3 IFP'),
    ('LCS', 'GTA Liberty City Stories', 'Leeds ANIM'),
    ('VCS', 'GTA Vice City Stories', 'Leeds ANIM'),
    ('MANHUNT_1', 'Manhunt', 'ANCT IFP with SEQU tracks'),
)


def readAnpkBytes(data):
    if len(data) < 20 or data[:4] != b'ANPK':
        raise ValueError('Expected an ANPK IFP')
    end = struct.unpack_from('<I', data, 4)[0] + 8
    if end > len(data):
        raise ValueError('Truncated ANPK container')

    def readChunk(offset, limit):
        if offset + 8 > limit:
            raise ValueError('Truncated ANPK chunk header')
        tag = data[offset:offset + 4]
        size = struct.unpack_from('<I', data, offset + 4)[0]
        payload_start = offset + 8
        payload_end = payload_start + size
        if payload_end > limit:
            raise ValueError('Truncated ANPK ' + repr(tag) + ' chunk')
        return tag, payload_start, payload_end, (payload_end + 3) & ~3

    tag, start, stop, cursor = readChunk(8, end)
    if tag != b'INFO' or stop - start < 4:
        raise ValueError('ANPK has no INFO header')
    count = struct.unpack_from('<I', data, start)[0]
    clips = []
    for clip_index in range(count):
        tag, start, stop, cursor = readChunk(cursor, end)
        if tag != b'NAME':
            raise ValueError('ANPK animation has no NAME')
        clip = ConversionClip(data[start:stop].split(b'\0', 1)[0].decode('latin-1'))
        tag, start, stop, cursor = readChunk(cursor, end)
        if tag != b'DGAN':
            raise ValueError('ANPK animation has no DGAN')
        tag, info_start, info_stop, bone_cursor = readChunk(start, stop)
        if tag != b'INFO' or info_stop - info_start < 4:
            raise ValueError('ANPK animation has no bone count')
        bone_count = struct.unpack_from('<I', data, info_start)[0]
        for bone_index in range(bone_count):
            tag, bone_start, bone_stop, bone_cursor = readChunk(bone_cursor, stop)
            if tag != b'CPAN':
                raise ValueError('ANPK bone has no CPAN')
            tag, header_start, header_stop, key_cursor = readChunk(bone_start, bone_stop)
            if tag != b'ANIM' or header_stop - header_start not in (44, 48):
                raise ValueError('Unsupported ANPK bone header')
            name = data[header_start:header_start + 28].split(b'\0', 1)[0].decode('latin-1')
            frame_count = struct.unpack_from('<I', data, header_start + 28)[0]
            bone_id = struct.unpack_from('<i', data, header_start + 40)[0] if header_stop - header_start == 44 else -1
            if bone_id == -1:
                known_id = directIdFromBoneName(name)
                if known_id is not None:
                    bone_id = int(known_id)
            tag, key_start, key_stop, unused = readChunk(key_cursor, bone_stop)
            key_type = tag.decode('ascii')
            if len(key_type) != 4 or key_type[0] != 'K':
                raise ValueError('Unsupported ANPK keyframe tag')
            rotation = key_type[1] == 'R'
            translation = key_type[2] == 'T'
            scale = key_type[3] == 'S'
            stride = 4 + 16 * rotation + 12 * translation + 12 * scale
            if frame_count * stride > key_stop - key_start:
                raise ValueError('Truncated ANPK keyframe block')
            track = ConversionTrack(bone_id, name, [], translation, rotation, scale)
            for frame_index in range(frame_count):
                position = key_start + frame_index * stride
                quaternion = (0.0, 0.0, 0.0, 1.0)
                if rotation:
                    x, y, z, w = struct.unpack_from('<4f', data, position)
                    quaternion = normalizeRotationXyzw((-x, -y, -z, w))
                    position += 16
                location = (0.0, 0.0, 0.0)
                if translation:
                    location = struct.unpack_from('<3f', data, position)
                    position += 12
                scaling = (1.0, 1.0, 1.0)
                if scale:
                    scaling = struct.unpack_from('<3f', data, position)
                    position += 12
                time = struct.unpack_from('<f', data, position)[0]
                track.frames.append(AnimExportFrame(time, quaternion, location, scaling))
                clip.duration = max(clip.duration, time)
            clip.tracks.append(track)
        clips.append(clip)
    return clips
