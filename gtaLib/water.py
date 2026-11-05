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

import math
import os
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path


WATER_VERTEX_LAYERS = ('water_flow_x', 'water_flow_y', 'water_big_waves', 'water_small_waves')
WATER_VERTEX_DEFAULTS = (0.0, 0.0, 1.0, 0.5)
WATER_FACE_LAYERS = ('water_flags', 'water_sector', 'water_line')


@dataclass
class WaterSector:
    vertices: tuple
    flags: int = 0
    line_number: int = 0
    format: str = 'SA'
    level_index: int = -1


def parseWaterFlags(value):
    text = str(value).strip()
    try:
        flags = int(text, 16) if text.lower().startswith('0x') else int(text, 10)
    except ValueError as error:
        raise ValueError('Flags must be an unsigned 32-bit integer') from error
    if not 0 <= flags <= 4294967295:
        raise ValueError('Flags must be an unsigned 32-bit integer')
    return flags


def validateWaterSector(sector):
    if sector.format not in {'SA', 'III_VC', 'WATERPRO'}:
        raise ValueError('Unknown water format: ' + str(sector.format))
    if len(sector.vertices) not in (3, 4):
        raise ValueError('Water sectors must have three or four vertices')
    for vertex in sector.vertices:
        if len(vertex) != 7 or not all(math.isfinite(value) for value in vertex):
            raise ValueError('Each water vertex must contain seven finite numbers')
    parseWaterFlags(sector.flags)
    waterFaceOrder(sector.vertices)


def parseWaterText(text, game_format='AUTO', skip_invalid=False, warnings=None):
    if game_format not in {'AUTO', 'SA', 'III_VC'}:
        raise ValueError('Unknown water format: ' + game_format)
    sectors = []
    detected_format = None
    for line_number, raw_line in enumerate(text.lstrip('\ufeff').splitlines(), 1):
        line = raw_line
        for marker in ('#', ';', '//'):
            line = line.split(marker, 1)[0]
        fields = line.replace(',', ' ').split()
        if not fields:
            continue
        if len(fields) == 1 and fields[0].lower() == 'processed':
            continue
        try:
            record_format = 'III_VC' if len(fields) == 5 else 'SA'
            if game_format != 'AUTO' and record_format != game_format:
                raise ValueError('Record does not match the selected game format')
            if detected_format is not None and detected_format != record_format:
                raise ValueError('Mixed game formats are not supported')
            if record_format == 'III_VC':
                height, left, bottom, right, top = tuple(float(field) for field in fields)
                if right <= left or top <= bottom:
                    raise ValueError('Rectangle bounds must have positive width and height')
                vertices = tuple((x, y, height, 0.0, 0.0, 0.0, 0.0) for x, y in (
                    (left, bottom), (right, bottom), (right, top), (left, top)))
                flags = 0
            else:
                if len(fields) not in (21, 22, 28, 29):
                    raise ValueError('Expected 21/22 triangle fields, 28/29 quad fields, or 5 rectangle fields')
                count = 3 if len(fields) in (21, 22) else 4
                values = tuple(float(field) for field in fields[:count * 7])
                flags = parseWaterFlags(fields[-1]) if len(fields) == count * 7 + 1 else 0
                vertices = tuple(values[index * 7:index * 7 + 7] for index in range(count))
            sector = WaterSector(vertices, flags, line_number, record_format)
            validateWaterSector(sector)
            sectors.append(sector)
            detected_format = record_format
        except ValueError as error:
            message = f'water.dat line {line_number}: {error}'
            if not skip_invalid:
                raise ValueError(message) from error
            if warnings is not None:
                warnings.append(message)
    if not sectors:
        raise ValueError('No valid water sectors found')
    return sectors


def readWaterFile(filepath, game_format='AUTO', skip_invalid=False, warnings=None):
    data = Path(filepath).read_bytes()
    if b'\x00' in data:
        raise ValueError('Expected a text water.dat file; binary waterpro.dat is not supported')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = data.decode('cp1252', errors='replace')
    return parseWaterText(text, game_format, skip_invalid, warnings)


def waterFaceOrder(vertices):
    if len(vertices) not in (3, 4):
        raise ValueError('Water sectors must have three or four vertices')
    if not all(len(vertex) >= 3 and all(math.isfinite(value) for value in vertex[:3]) for vertex in vertices):
        raise ValueError('Water positions must contain finite XYZ coordinates')
    center_x = sum(vertex[0] for vertex in vertices) / len(vertices)
    center_y = sum(vertex[1] for vertex in vertices) / len(vertices)
    order = tuple(sorted(range(len(vertices)), key=lambda index: math.atan2(
        vertices[index][1] - center_y, vertices[index][0] - center_x)))
    if len({(vertex[0], vertex[1]) for vertex in vertices}) != len(vertices):
        raise ValueError('Water sector contains duplicate XY coordinates')
    for index in range(len(order)):
        a = vertices[order[index - 1]]
        b = vertices[order[index]]
        c = vertices[order[(index + 1) % len(order)]]
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if cross <= 0.0:
            raise ValueError('Water sector must form a nondegenerate convex polygon')
    return order


def waterRectangleValues(vertices, tolerance=0.0001):
    if len(vertices) != 4:
        raise ValueError('Rectangle format requires four vertices per sector')
    left = min(vertex[0] for vertex in vertices)
    right = max(vertex[0] for vertex in vertices)
    bottom = min(vertex[1] for vertex in vertices)
    top = max(vertex[1] for vertex in vertices)
    height = vertices[0][2]
    corners = set()
    for x, y, z, *rest in vertices:
        x_side = 0 if abs(x - left) <= tolerance else 1 if abs(x - right) <= tolerance else -1
        y_side = 0 if abs(y - bottom) <= tolerance else 1 if abs(y - top) <= tolerance else -1
        if x_side < 0 or y_side < 0 or abs(z - height) > tolerance:
            raise ValueError('GTA III / Vice City needs horizontal, axis-aligned rectangles')
        corners.add((x_side, y_side))
    if len(corners) != 4:
        raise ValueError('Rectangle corners are missing or duplicated')
    return (height, left, bottom, right, top)


def validateSanAndreasGeometry(vertices):
    if any(not -3000 <= vertex[axis] <= 3000 for vertex in vertices for axis in (0, 1)):
        raise ValueError('San Andreas water XY coordinates must be within -3000 to 3000')
    if any(vertex[axis] != math.trunc(vertex[axis]) for vertex in vertices for axis in (0, 1)):
        raise ValueError('San Andreas uses integer XY positions; enable Snap XY to Integers')
    if len(vertices) == 4:
        flat_vertices = tuple((vertex[0], vertex[1], 0.0) for vertex in vertices)
        try:
            waterRectangleValues(flat_vertices)
        except ValueError as error:
            raise ValueError('San Andreas water quads must be axis-aligned rectangles') from error
    else:
        if len({vertex[1] for vertex in vertices}) != 2:
            raise ValueError('San Andreas water triangles need a horizontal edge (two equal Y coordinates)')


def formatWaterNumber(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Cannot write a non-finite water value')
    return format(value, '.9g') if value != 0.0 else '0'


def formatWaterText(sectors, game_format='AUTO', validate_game=False):
    sectors = list(sectors)
    if not sectors:
        raise ValueError('No water sectors to export')
    if game_format not in {'AUTO', 'SA', 'III_VC'}:
        raise ValueError('Unknown water format: ' + str(game_format))
    target_format = sectors[0].format if game_format == 'AUTO' else game_format
    if game_format == 'AUTO' and any(sector.format != target_format for sector in sectors):
        raise ValueError('Mixed source formats; select an explicit export format')
    lines = ['processed'] if target_format == 'SA' else ['; DemonFF water.dat', '; Format: ' + target_format]
    for index, sector in enumerate(sectors):
        try:
            validateWaterSector(sector)
            if target_format == 'III_VC':
                if sector.flags != 0 or any(any(value != 0.0 for value in vertex[3:]) for vertex in sector.vertices):
                    raise ValueError('Rectangle format cannot preserve SA flow, wave values or flags')
                values = waterRectangleValues(sector.vertices)
                line = ', '.join(formatWaterNumber(value) for value in values)
            else:
                if validate_game:
                    validateSanAndreasGeometry(sector.vertices)
                vertices = sorted(sector.vertices, key=lambda vertex: (vertex[1], vertex[0]))
                line = ' '.join(formatWaterNumber(value) for vertex in vertices for value in vertex)
                line += ' ' + str(parseWaterFlags(sector.flags))
            lines.append(line)
        except ValueError as error:
            raise ValueError(f'Water sector {index}: {error}') from error
    text = '\n'.join(lines) + '\n'
    parseWaterText(text, target_format)
    return text


def writeWaterFile(filepath, sectors, game_format='AUTO', validate_game=False):
    text = formatWaterText(sectors, game_format, validate_game)
    return writeWaterData(filepath, text.encode('ascii'))


def writeWaterData(filepath, data):
    destination = Path(filepath)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb',
                                         dir=destination.parent, prefix=destination.name + '.',
                                         suffix='.tmp', delete=False) as stream:
            temporary_name = stream.name
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, destination)
    finally:
        if temporary_name is not None and os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return len(data)


WATERPRO_SIZE = 21444
WATERPRO_LEVEL_COUNT = 48
WATERPRO_COARSE_OFFSET = 964
WATERPRO_FINE_OFFSET = 5060
WATERPRO_DRY = 128
WATERPRO_PROFILES = {'III': (-2048.0, -2048.0), 'VC': (-2448.0, -2048.0)}


@dataclass
class WaterProData:
    count: int
    levels: tuple
    rectangles: tuple
    coarse: bytes
    fine: bytes
    profile: str
    raw: bytes


def parseWaterProBytes(data, profile='VC'):
    if profile not in WATERPRO_PROFILES:
        raise ValueError('Choose the GTA III or Vice City WATERPRO grid profile')
    if len(data) != WATERPRO_SIZE:
        raise ValueError(f'WATERPRO.DAT must be {WATERPRO_SIZE} bytes; got {len(data)}')
    count = struct.unpack_from('<I', data)[0]
    if count > WATERPRO_LEVEL_COUNT:
        raise ValueError('WATERPRO supports at most 48 water levels')
    levels = struct.unpack_from('<48f', data, 4)
    rectangles = tuple(struct.unpack_from('<4f', data, 196 + index * 16) for index in range(48))
    for index in range(count):
        if not math.isfinite(levels[index]) or not all(math.isfinite(value) for value in rectangles[index]):
            raise ValueError(f'WATERPRO level {index} contains non-finite values')
    coarse = data[WATERPRO_COARSE_OFFSET:WATERPRO_FINE_OFFSET]
    fine = data[WATERPRO_FINE_OFFSET:]
    for name, grid in (('coarse', coarse), ('fine', fine)):
        for index, value in enumerate(grid):
            if not value & WATERPRO_DRY and value >= count:
                raise ValueError(f'WATERPRO {name} cell {index} references missing level {value}')
    return WaterProData(count, levels, rectangles, coarse, fine, profile, bytes(data))


def readWaterProFile(filepath, profile='VC'):
    return parseWaterProBytes(Path(filepath).read_bytes(), profile)


def waterProSectors(document):
    start_x, start_y = WATERPRO_PROFILES[document.profile]
    used = bytearray(128 * 128)
    sectors = []
    for x in range(128):
        for y in range(128):
            offset = x * 128 + y
            level = document.fine[offset]
            if used[offset] or level & WATERPRO_DRY:
                continue
            end_y = y + 1
            while end_y < 128 and not used[x * 128 + end_y] and document.fine[x * 128 + end_y] == level:
                end_y += 1
            end_x = x + 1
            while end_x < 128 and all(not used[end_x * 128 + row] and
                                     document.fine[end_x * 128 + row] == level for row in range(y, end_y)):
                end_x += 1
            for column in range(x, end_x):
                used[column * 128 + y:column * 128 + end_y] = bytes([1]) * (end_y - y)
            left, right = start_x + x * 32, start_x + end_x * 32
            bottom, top = start_y + y * 32, start_y + end_y * 32
            height = document.levels[level]
            vertices = tuple((vx, vy, height, 0.0, 0.0, 0.0, 0.0) for vx, vy in (
                (left, bottom), (right, bottom), (right, top), (left, top)))
            sectors.append(WaterSector(vertices, 0, 0, 'WATERPRO', level))
    if not sectors:
        raise ValueError('WATERPRO contains no wet fine-grid cells')
    return sectors


def emptyWaterPro(profile):
    data = bytearray(WATERPRO_SIZE)
    data[WATERPRO_COARSE_OFFSET:] = bytes([WATERPRO_DRY]) * (4096 + 16384)
    return parseWaterProBytes(bytes(data), profile)


def waterProFloat(value):
    try:
        value = struct.unpack('<f', struct.pack('<f', value))[0]
    except (OverflowError, struct.error) as error:
        raise ValueError('Water height cannot be stored as a 32-bit float') from error
    if not math.isfinite(value):
        raise ValueError('Water height must be finite')
    return value


def buildWaterProBytes(sectors, profile='VC', source=None):
    sectors = list(sectors)
    if not sectors:
        raise ValueError('No water sectors to export')
    document = source if source is not None else emptyWaterPro(profile)
    if document.profile != profile:
        raise ValueError('Source WATERPRO grid profile differs from the export profile')
    start_x, start_y = WATERPRO_PROFILES[profile]
    records = []
    for index, sector in enumerate(sectors):
        try:
            validateWaterSector(sector)
            if sector.flags or any(any(value != 0 for value in vertex[3:]) for vertex in sector.vertices):
                raise ValueError('WATERPRO cannot store SA flow, wave values or flags')
            height, left, bottom, right, top = waterRectangleValues(sector.vertices)
            coordinates = ((left - start_x) / 32, (bottom - start_y) / 32,
                           (right - start_x) / 32, (top - start_y) / 32)
            if any(abs(value - round(value)) > 0.00001 for value in coordinates):
                raise ValueError(f'WATERPRO edges must align to the 32-unit tile grid (origin {start_x}, {start_y})')
            x1, y1, x2, y2 = tuple(round(value) for value in coordinates)
            if not (0 <= x1 < x2 <= 128 and 0 <= y1 < y2 <= 128):
                raise ValueError('Water rectangle is outside the selected WATERPRO grid')
            records.append((waterProFloat(height), x1, y1, x2, y2, sector.level_index))
        except ValueError as error:
            raise ValueError(f'WATERPRO sector {index}: {error}') from error
    requested = {}
    for height, x1, y1, x2, y2, original_level in records:
        if 0 <= original_level < document.count:
            requested.setdefault(original_level, set()).add(height)
    levels = list(document.levels)
    assignments = {}
    reserved = set()
    for original_level, heights in sorted(requested.items()):
        if len(heights) == 1:
            height = next(iter(heights))
            assignments[(original_level, height)] = original_level
            levels[original_level] = height
            reserved.add(original_level)
        elif levels[original_level] in heights:
            assignments[(original_level, levels[original_level])] = original_level
            reserved.add(original_level)
    count = document.count
    fine = bytearray(value if value & WATERPRO_DRY else WATERPRO_DRY for value in document.fine)
    for height, x1, y1, x2, y2, original_level in records:
        key = (original_level, height)
        level = assignments.get(key)
        if level is None:
            level = next((index for index in sorted(reserved) if levels[index] == height), None)
            if level is None:
                level = next((index for index in range(48) if index not in reserved), None)
                if level is None:
                    raise ValueError('WATERPRO supports at most 48 distinct water levels')
                levels[level] = height
                reserved.add(level)
            assignments[key] = level
        count = max(count, level + 1)
        for x in range(x1, x2):
            for y in range(y1, y2):
                offset = x * 128 + y
                if not fine[offset] & WATERPRO_DRY and fine[offset] != level:
                    raise ValueError(f'Overlapping water heights at grid cell ({x}, {y})')
                fine[offset] = level
    output = bytearray(document.raw)
    struct.pack_into('<I', output, 0, count)
    for index in reserved:
        if levels[index] != document.levels[index]:
            struct.pack_into('<f', output, 4 + index * 4, levels[index])
    if bytes(fine) != document.fine:
        coarse = bytearray(document.coarse)
        changed_levels = set()
        for before, after in zip(document.fine, fine):
            if before != after:
                if not before & WATERPRO_DRY:
                    changed_levels.add(before)
                if not after & WATERPRO_DRY:
                    changed_levels.add(after)
        bounds = {}
        for x in range(128):
            for y in range(128):
                level = fine[x * 128 + y]
                if level & WATERPRO_DRY:
                    continue
                if level not in bounds:
                    bounds[level] = [x, y, x + 1, y + 1]
                else:
                    box = bounds[level]
                    box[0], box[1] = min(box[0], x), min(box[1], y)
                    box[2], box[3] = max(box[2], x + 1), max(box[3], y + 1)
        for x in range(64):
            for y in range(64):
                children = [fine[(2*x + dx) * 128 + 2*y + dy] for dx in (0, 1) for dy in (0, 1)]
                wet = [value for value in children if not value & WATERPRO_DRY]
                previous_children = [document.fine[(2*x + dx) * 128 + 2*y + dy] for dx in (0, 1) for dy in (0, 1)]
                if children != previous_children:
                    original = document.coarse[x * 64 + y]
                    coarse[x * 64 + y] = original if original in wet else wet[0] if wet else WATERPRO_DRY
        for level in changed_levels:
            if level not in bounds:
                struct.pack_into('<4f', output, 196 + level * 16, 0.0, 0.0, 0.0, 0.0)
                continue
            x1, y1, x2, y2 = bounds[level]
            struct.pack_into('<4f', output, 196 + level * 16,
                             start_x + x1 * 32, start_y + y2 * 32,
                             start_x + x2 * 32, start_y + y1 * 32)
        output[WATERPRO_COARSE_OFFSET:WATERPRO_FINE_OFFSET] = coarse
        output[WATERPRO_FINE_OFFSET:] = fine
    parseWaterProBytes(bytes(output), profile)
    return bytes(output)


# GTA SA PC 1.0, CWaterLevel::CalculateWavesOnlyForCoordinate (0x6E6EF0).
# Multiplier tables verified in the supplied gta_sa.exe at 0x8D38C8/0x8D38E8.
SA_WAVE_MULTIPLIERS_X = (1.0, 0.85, 0.73, 0.77, 0.75, 0.8, 0.73, 0.8)
SA_WAVE_MULTIPLIERS_Y = (0.75, 0.9, 0.95, 0.82, 0.7, 0.75, 0.9, 1.0)


def calculateSanAndreasWave(x, y, seconds, big_waves=1.0, small_waves=0.5, wavyness=1.0):
    """Return SA PC rendered wave displacement, with its 256-entry sine lookup.

    Time is relative to the game's water time offset. Weather wavyness is a
    preview input, not a water.dat field. Coordinates follow the integer routine.
    """
    if not all(math.isfinite(v) for v in (x, y, seconds, big_waves, small_waves, wavyness)):
        raise ValueError('Wave inputs must be finite')
    x, y = abs(int(x)), abs(int(y))
    multiplier = SA_WAVE_MULTIPLIERS_X[(x // 2) % 8] * SA_WAVE_MULTIPLIERS_Y[(y // 2) % 8] * wavyness
    milliseconds = int(seconds * 1000) & 0xffffffff
    height = 0.0
    for period, frequency_x, frequency_y, amplitude in (
            (5000, 1 / 64, 1 / 64, 2 * big_waves),
            (3500, 1 / 26, 1 / 52, small_waves),
            (3000, 0, 1 / 20, 0.5 * small_waves)):
        phase = (milliseconds % period) / period + x * frequency_x + y * frequency_y
        sine_index = int(phase * 256) & 255
        height += math.sin(sine_index * math.tau / 256) * multiplier * amplitude
    return height
