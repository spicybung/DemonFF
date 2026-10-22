# DemonFF RenderWare 4 support
# Native RW4 reader for Spore arenas and Realtime Worlds/Crackdown Xenon xb2 resources.

import os
import re
import struct
from dataclasses import dataclass, field

RW4_MAGIC_PREFIX = b'\x89RW4'
RW4_SECONDARY_MAGIC = b'\x0d\x0a\x1a\x0a'

PROFILE_AUTO = 'AUTO'
PROFILE_CRACKDOWN = 'CRACKDOWN_4101'
PROFILE_SPORE = 'SPORE_4501'

PROFILE_LABELS = {
    PROFILE_CRACKDOWN: 'Crackdown (4.1.0.1)',
    PROFILE_SPORE: 'Spore (4.5.0.1)',
}

TYPE_BASE_RESOURCE = 0x10030
TYPE_RASTER = 0x20003
TYPE_VERTEX_DESCRIPTION = 0x20004
TYPE_VERTEX_BUFFER = 0x20005
TYPE_INDEX_BUFFER = 0x20007
TYPE_MESH = 0x20009
TYPE_MESH_COMPILED_STATE_LINK = 0x2001A

RWDECL_POSITION = 0
RWDECL_NORMAL = 2
RWDECL_COLOR0 = 3
RWDECL_COLOR1 = 5
RWDECL_TEXCOORD0 = 6
RWDECL_TEXCOORD1 = 7
RWDECL_TEXCOORD2 = 8
RWDECL_TEXCOORD3 = 9
RWDECL_BLENDINDICES = 14
RWDECL_BLENDWEIGHTS = 15
RWDECL_TANGENT = 19
RWDECL_BINORMAL = 20

D3DPT_TRIANGLELIST = 4
D3DPT_TRIANGLESTRIP = 5
D3DFMT_INDEX16 = 101
D3DFMT_INDEX32 = 102


class RW4Error(Exception):
    pass


@dataclass
class RW4Detection:
    profile: str
    label: str
    kind: str
    arena_offset: int = -1
    platform: str = ''
    version_text: str = ''


@dataclass
class SectionInfo:
    index: int
    p_data: int
    field_04: int
    data_size: int
    alignment: int
    type_code_index: int
    type_code: int


@dataclass
class VertexElement:
    stream: int
    offset: int
    element_type: int
    method: int
    usage: int
    usage_index: int
    rw_decl: int


@dataclass
class VertexDescription:
    elements: list = field(default_factory=list)
    vertex_size: int = 0


@dataclass
class VertexBuffer:
    description_ref: int = -1
    base_vertex_index: int = 0
    vertex_count: int = 0
    vertex_size: int = 0
    data_ref: int = -1


@dataclass
class IndexBuffer:
    start_index: int = 0
    index_count: int = 0
    usage: int = 0
    index_format: int = D3DFMT_INDEX16
    primitive_type: int = D3DPT_TRIANGLELIST
    data_ref: int = -1


@dataclass
class Mesh:
    primitive_type: int = D3DPT_TRIANGLELIST
    index_buffer_ref: int = -1
    triangle_count: int = 0
    first_index: int = 0
    primitive_count: int = 0
    first_vertex: int = 0
    vertex_count: int = 0
    vertex_buffer_refs: list = field(default_factory=list)


@dataclass
class ParsedMesh:
    name: str
    vertices: list
    triangles: list
    uvs: list = field(default_factory=list)
    normals: list = field(default_factory=list)
    colors: list = field(default_factory=list)
    source_mesh_index: int = -1


@dataclass
class CrackdownResource:
    name: str
    offset: int
    kind: str


@dataclass
class CrackdownArena:
    offset: int
    platform: str
    footer_offset: int
    size_to_eof: int
    section_count: int = 0
    sections: list = field(default_factory=list)
    objects: dict = field(default_factory=dict)
    parsed_meshes: list = field(default_factory=list)
    resource_name: str = ''


@dataclass
class CrackdownContainer:
    resources: list = field(default_factory=list)
    arenas: list = field(default_factory=list)
    classes: list = field(default_factory=list)


@dataclass
class SporeArena:
    platform: str
    version_text: str
    rw_type_code: int
    section_count: int
    section_infos_offset: int
    buffer_data_offset: int
    sections: list = field(default_factory=list)
    objects: dict = field(default_factory=dict)
    parsed_meshes: list = field(default_factory=list)


def read_file_bytes(path):
    with open(path, 'rb') as stream:
        return stream.read()


def find_arena_offset(data):
    return data.find(RW4_MAGIC_PREFIX)


def looks_like_rw3_dff(data):
    if len(data) < 12:
        return False
    chunk_type, size, version = struct.unpack_from('<III', data, 0)
    if chunk_type not in (0x10, 0x16, 0x0E, 0x0F):
        return False
    return size <= max(0, len(data) - 12) and version != 0


def detect_bytes(data, forced_profile=PROFILE_AUTO):
    if forced_profile == PROFILE_CRACKDOWN:
        arena_offset = find_arena_offset(data)
        return RW4Detection(PROFILE_CRACKDOWN, PROFILE_LABELS[PROFILE_CRACKDOWN], 'crackdown', arena_offset)
    if forced_profile == PROFILE_SPORE:
        arena_offset = find_arena_offset(data)
        return RW4Detection(PROFILE_SPORE, PROFILE_LABELS[PROFILE_SPORE], 'spore', arena_offset)

    arena_offset = find_arena_offset(data)
    if arena_offset >= 0 and arena_offset + 12 <= len(data):
        platform = data[arena_offset + 4:arena_offset + 8].rstrip(b'\0').decode('ascii', 'replace')
        if platform == 'w32':
            version = data[arena_offset + 16:arena_offset + 24].split(b'\0')[0].decode('ascii', 'replace')
            return RW4Detection(PROFILE_SPORE, PROFILE_LABELS[PROFILE_SPORE], 'spore', arena_offset, platform, version)
        if platform == 'xb2':
            return RW4Detection(PROFILE_CRACKDOWN, PROFILE_LABELS[PROFILE_CRACKDOWN], 'crackdown', arena_offset, platform)

    # Crackdown's .dff world/object stream does not have to start with the RW4 arena.
    # These names are serialized immediately in known Realtime Worlds files.
    signatures = (b'cStaticEnvironment', b'cStreamingDataHolder', 'Streaming\\'.encode('utf-16le'))
    if any(signature in data[:min(len(data), 0x20000)] for signature in signatures):
        return RW4Detection(PROFILE_CRACKDOWN, PROFILE_LABELS[PROFILE_CRACKDOWN], 'crackdown', arena_offset)

    return None


def detect_file(path, forced_profile=PROFILE_AUTO):
    return detect_bytes(read_file_bytes(path), forced_profile)


def is_rw4_file(path, forced_profile=PROFILE_AUTO):
    try:
        return detect_file(path, forced_profile) is not None
    except OSError:
        return False


def decode_ref(value):
    # RW4 uses the upper bits to distinguish object/no-object/subreference handles.
    section_type = (value >> 22) & 0x3FF
    index = value & 0x3FFFFF
    if section_type == 0:
        return index
    if section_type == 1 and index == 0:
        return -1
    # Subreferences cannot stand in for complete mesh/buffer objects here.
    return index if section_type == 0 else -1


def unpack_value(data, offset, fmt, endian='<'):
    size = struct.calcsize(endian + fmt)
    if offset < 0 or offset + size > len(data):
        raise RW4Error('RW4 read outside file at 0x%X' % offset)
    return struct.unpack_from(endian + fmt, data, offset)


def parse_vertex_description(data, section, endian='<'):
    offset = section.p_data
    if offset + 20 > len(data):
        raise RW4Error('Truncated vertex description')
    element_count = struct.unpack_from(endian + 'H', data, offset + 12)[0]
    vertex_size = data[offset + 15]
    elements = []
    cursor = offset + 20
    for _ in range(element_count):
        if cursor + 12 > offset + section.data_size or cursor + 12 > len(data):
            break
        stream, element_offset, element_type, method, usage, usage_index, rw_decl = struct.unpack_from(
            endian + 'hhbbbbi', data, cursor)
        elements.append(VertexElement(stream, element_offset, element_type, method, usage, usage_index, rw_decl))
        cursor += 12
    return VertexDescription(elements, vertex_size)


def parse_vertex_buffer(data, section, endian='<'):
    values = struct.unpack_from(endian + '7I', data, section.p_data)
    return VertexBuffer(
        description_ref=decode_ref(values[0]),
        base_vertex_index=values[2],
        vertex_count=values[3],
        vertex_size=values[5],
        data_ref=decode_ref(values[6]),
    )


def parse_index_buffer(data, section, endian='<'):
    values = struct.unpack_from(endian + '7I', data, section.p_data)
    return IndexBuffer(
        start_index=values[1],
        index_count=values[2],
        usage=values[3],
        index_format=values[4],
        primitive_type=values[5],
        data_ref=decode_ref(values[6]),
    )


def parse_mesh(data, section, endian='<'):
    base = struct.unpack_from(endian + '9I', data, section.p_data)
    count = base[4]
    refs = []
    cursor = section.p_data + 36
    for _ in range(count):
        if cursor + 4 > section.p_data + section.data_size:
            break
        refs.append(decode_ref(struct.unpack_from(endian + 'I', data, cursor)[0]))
        cursor += 4
    return Mesh(
        primitive_type=base[1],
        index_buffer_ref=decode_ref(base[2]),
        triangle_count=base[3],
        first_index=base[5],
        primitive_count=base[6],
        first_vertex=base[7],
        vertex_count=base[8],
        vertex_buffer_refs=refs,
    )


def component_size(element_type):
    return {
        0: 4, 1: 8, 2: 12, 3: 16, 4: 4, 5: 4, 6: 4, 7: 8,
        8: 4, 9: 4, 10: 8, 11: 4, 12: 8,
        13: 4, 14: 4, 15: 4, 16: 8,
    }.get(element_type, 0)


def decode_dec3n(raw):
    x = raw & 0x3FF
    y = (raw >> 10) & 0x3FF
    z = (raw >> 20) & 0x3FF
    def signed10(v):
        if v & 0x200:
            v -= 0x400
        return max(-1.0, min(1.0, v / 511.0))
    return signed10(x), signed10(y), signed10(z)


def decode_vertex_element(blob, base, element, endian='<'):
    offset = base + element.offset
    t = element.element_type
    if t == 0:
        return struct.unpack_from(endian + 'f', blob, offset)
    if t == 1:
        return struct.unpack_from(endian + '2f', blob, offset)
    if t == 2:
        return struct.unpack_from(endian + '3f', blob, offset)
    if t == 3:
        return struct.unpack_from(endian + '4f', blob, offset)
    if t == 4:
        raw = struct.unpack_from(endian + 'I', blob, offset)[0]
        return ((raw >> 16) & 255, (raw >> 8) & 255, raw & 255, (raw >> 24) & 255)
    if t in (5, 8):
        values = struct.unpack_from('4B', blob, offset)
        return tuple(v / 255.0 for v in values) if t == 8 else values
    if t == 6:
        return struct.unpack_from(endian + '2h', blob, offset)
    if t == 7:
        return struct.unpack_from(endian + '4h', blob, offset)
    if t == 9:
        values = struct.unpack_from(endian + '2h', blob, offset)
        return tuple(max(-1.0, v / 32767.0) for v in values)
    if t == 10:
        values = struct.unpack_from(endian + '4h', blob, offset)
        return tuple(max(-1.0, v / 32767.0) for v in values)
    if t == 11:
        values = struct.unpack_from(endian + '2H', blob, offset)
        return tuple(v / 65535.0 for v in values)
    if t == 12:
        values = struct.unpack_from(endian + '4H', blob, offset)
        return tuple(v / 65535.0 for v in values)
    if t == 13:
        raw = struct.unpack_from(endian + 'I', blob, offset)[0]
        return raw & 0x3FF, (raw >> 10) & 0x3FF, (raw >> 20) & 0x3FF
    if t == 14:
        raw = struct.unpack_from(endian + 'I', blob, offset)[0]
        return decode_dec3n(raw)
    if t == 15:
        return struct.unpack_from(endian + '2e', blob, offset)
    if t == 16:
        return struct.unpack_from(endian + '4e', blob, offset)
    return None


def parse_spore_arena(data, arena_offset=0):
    if arena_offset < 0:
        arena_offset = find_arena_offset(data)
    if arena_offset < 0 or data[arena_offset:arena_offset + 4] != RW4_MAGIC_PREFIX:
        raise RW4Error('RW4 arena signature not found')

    platform = data[arena_offset + 4:arena_offset + 8].rstrip(b'\0').decode('ascii', 'replace')
    if platform != 'w32':
        raise RW4Error('Spore (4.5.0.1) expects a w32 RW4 arena; found %s' % platform)

    # Spore's PC RW4 arenas are little-endian. Header fields are relative to arena start.
    base = arena_offset
    if base + 0x48 > len(data):
        raise RW4Error('Truncated Spore RW4 header')
    version_text = data[base + 16:base + 24].split(b'\0')[0].decode('ascii', 'replace')
    rw_type_code, section_count_a, section_count, _kind, _zero, p_infos, _manifest_size, _, _, _, p_buffers = \
        struct.unpack_from('<11I', data, base + 28)

    if section_count == 0 or section_count > 100000:
        raise RW4Error('Invalid Spore RW4 section count: %d' % section_count)

    info_abs = base + p_infos
    buffer_abs = base + p_buffers
    if info_abs < base or info_abs + section_count * 24 > len(data):
        raise RW4Error('Spore RW4 section table is outside the file')

    arena = SporeArena(platform, version_text, rw_type_code, section_count, info_abs, buffer_abs)
    for index in range(section_count):
        values = struct.unpack_from('<6I', data, info_abs + index * 24)
        section = SectionInfo(index, values[0], values[1], values[2], values[3], values[4], values[5])
        if section.type_code == TYPE_BASE_RESOURCE:
            section.p_data = buffer_abs + section.p_data
        else:
            section.p_data = base + section.p_data
        arena.sections.append(section)

    for section in arena.sections:
        try:
            if section.type_code == TYPE_BASE_RESOURCE:
                end = section.p_data + section.data_size
                if 0 <= section.p_data <= end <= len(data):
                    arena.objects[section.index] = data[section.p_data:end]
            elif section.type_code == TYPE_VERTEX_DESCRIPTION:
                arena.objects[section.index] = parse_vertex_description(data, section, '<')
            elif section.type_code == TYPE_VERTEX_BUFFER:
                arena.objects[section.index] = parse_vertex_buffer(data, section, '<')
            elif section.type_code == TYPE_INDEX_BUFFER:
                arena.objects[section.index] = parse_index_buffer(data, section, '<')
            elif section.type_code == TYPE_MESH:
                arena.objects[section.index] = parse_mesh(data, section, '<')
        except (struct.error, RW4Error):
            # Keep unknown/malformed sections addressable by index without aborting every other mesh.
            arena.objects[section.index] = None

    mesh_number = 0
    for section in arena.sections:
        if section.type_code != TYPE_MESH:
            continue
        mesh = arena.objects.get(section.index)
        if not isinstance(mesh, Mesh) or not mesh.vertex_buffer_refs:
            continue
        parsed = build_spore_mesh(data, arena, mesh, section.index, mesh_number)
        if parsed is not None:
            arena.parsed_meshes.append(parsed)
            mesh_number += 1
    return arena


def build_spore_mesh(data, arena, mesh, mesh_index, mesh_number):
    vbuffer = arena.objects.get(mesh.vertex_buffer_refs[0])
    ibuffer = arena.objects.get(mesh.index_buffer_ref)
    if not isinstance(vbuffer, VertexBuffer) or not isinstance(ibuffer, IndexBuffer):
        return None
    description = arena.objects.get(vbuffer.description_ref)
    vertex_blob = arena.objects.get(vbuffer.data_ref)
    index_blob = arena.objects.get(ibuffer.data_ref)
    if not isinstance(description, VertexDescription) or not isinstance(vertex_blob, (bytes, bytearray)) or not isinstance(index_blob, (bytes, bytearray)):
        return None

    stride = vbuffer.vertex_size or description.vertex_size
    if stride <= 0:
        return None
    vertex_count = mesh.vertex_count or vbuffer.vertex_count
    first_vertex = mesh.first_vertex or vbuffer.base_vertex_index
    if first_vertex + vertex_count > vbuffer.vertex_count:
        first_vertex = 0
        vertex_count = vbuffer.vertex_count

    positions = []
    normals = []
    uvs = []
    colors = []
    for vertex_index in range(vertex_count):
        base = (first_vertex + vertex_index) * stride
        if base + stride > len(vertex_blob):
            break
        values = {}
        for element in description.elements:
            try:
                values[element.rw_decl] = decode_vertex_element(vertex_blob, base, element, '<')
            except (struct.error, ValueError):
                values[element.rw_decl] = None
        position = values.get(RWDECL_POSITION)
        if position is None or len(position) < 3:
            position = (0.0, 0.0, 0.0)
        positions.append(tuple(float(v) for v in position[:3]))
        normal = values.get(RWDECL_NORMAL)
        normals.append(tuple(float(v) for v in normal[:3]) if normal is not None and len(normal) >= 3 else None)
        uv = values.get(RWDECL_TEXCOORD0)
        uvs.append(tuple(float(v) for v in uv[:2]) if uv is not None and len(uv) >= 2 else None)
        color = values.get(RWDECL_COLOR0)
        if color is not None:
            colors.append(tuple(float(v) / 255.0 if float(v) > 1.0 else float(v) for v in color[:4]))
        else:
            colors.append(None)

    index_size = 2 if ibuffer.index_format == D3DFMT_INDEX16 else 4
    index_fmt = '<H' if index_size == 2 else '<I'
    available = len(index_blob) // index_size
    count = ibuffer.index_count if 0 < ibuffer.index_count <= available else available
    indices = [struct.unpack_from(index_fmt, index_blob, i * index_size)[0] for i in range(count)]

    first_index = mesh.first_index
    if first_index >= len(indices):
        first_index = 0
    useful = indices[first_index:]
    triangles = []
    primitive = mesh.primitive_type or ibuffer.primitive_type
    if primitive == D3DPT_TRIANGLELIST:
        requested = mesh.primitive_count * 3 if mesh.primitive_count else len(useful)
        useful = useful[:min(len(useful), requested)]
        for i in range(0, len(useful) - 2, 3):
            tri = (useful[i] - first_vertex, useful[i + 1] - first_vertex, useful[i + 2] - first_vertex)
            if min(tri) >= 0 and max(tri) < len(positions) and len(set(tri)) == 3:
                triangles.append(tri)
    elif primitive == D3DPT_TRIANGLESTRIP:
        requested = mesh.primitive_count + 2 if mesh.primitive_count else len(useful)
        useful = useful[:min(len(useful), requested)]
        for i in range(len(useful) - 2):
            a, b, c = useful[i:i + 3]
            if i & 1:
                a, b = b, a
            tri = (a - first_vertex, b - first_vertex, c - first_vertex)
            if min(tri) >= 0 and max(tri) < len(positions) and len(set(tri)) == 3:
                triangles.append(tri)
    else:
        return None

    if not positions or not triangles:
        return None
    name = 'RW4_Mesh_%03d' % mesh_number
    return ParsedMesh(name, positions, triangles, uvs, normals, colors, mesh_index)


def extract_ascii_strings(data, minimum=4):
    pattern = rb'[\x20-\x7E]{%d,}' % minimum
    for match in re.finditer(pattern, data):
        yield match.start(), match.group(0).decode('ascii', 'replace')


def extract_utf16le_strings(data, minimum=4):
    pattern = rb'(?:[\x20-\x7E]\x00){%d,}' % minimum
    for match in re.finditer(pattern, data):
        yield match.start(), match.group(0).decode('utf-16le', 'replace')


# Xbox 360 vertex declaration format identifiers used by Crackdown's xb2 arenas.
X360DECL_FLOAT1 = 0x002C83A4
X360DECL_FLOAT2 = 0x002C23A5
X360DECL_FLOAT3 = 0x002A23B9
X360DECL_FLOAT4 = 0x001A23A6
X360DECL_D3DCOLOR = 0x00182886
X360DECL_UBYTE4 = 0x001A2286
X360DECL_BYTE4 = 0x001A2386
X360DECL_UBYTE4N = 0x001A2086
X360DECL_BYTE4N = 0x001A2186
X360DECL_SHORT2 = 0x002C2359
X360DECL_SHORT4 = 0x001A235A
X360DECL_USHORT2 = 0x002C2259
X360DECL_USHORT4 = 0x001A225A
X360DECL_SHORT2N = 0x002C2159
X360DECL_SHORT4N = 0x001A215A
X360DECL_USHORT2N = 0x002C2059
X360DECL_USHORT4N = 0x001A205A
X360DECL_UDEC3 = 0x002A2287
X360DECL_DEC3 = 0x002A2387
X360DECL_UDEC3N = 0x002A2087
X360DECL_DEC3N = 0x002A2187
X360DECL_FLOAT16_2 = 0x002C235F
X360DECL_FLOAT16_4 = 0x001A2360

TYPE_ARENA_SECTION_MANIFEST = 0x10004
TYPE_ARENA_SECTION_TYPES = 0x10005
TYPE_ARENA_EXTERNAL_ARENAS = 0x10006
TYPE_ARENA_SUBREFERENCES = 0x10007
TYPE_RENDER_OBJECT = 0x2000C


@dataclass
class Xb2VertexElement:
    offset: int
    format_code: int
    semantic_code: int

    @property
    def semantic(self):
        return self.semantic_code & 0xFF


@dataclass
class Xb2VertexDescription:
    flags: int
    vertex_size: int
    elements: list = field(default_factory=list)


@dataclass
class Xb2VertexBuffer:
    section_index: int
    description_ref: int
    vertex_count: int
    vertex_size: int
    data_size_hint: int
    data_ref_hint: int
    raw_section_ref: int = -1


@dataclass
class Xb2IndexBuffer:
    section_index: int
    data_ref: int
    data_size: int
    index_count: int


def parse_xb2_vertex_description(data, section):
    if section.p_data + 12 > len(data):
        raise RW4Error('Truncated Crackdown vertex description')
    flags, count_word, size_word = struct.unpack_from('>3I', data, section.p_data)
    element_count = (count_word >> 16) & 0xFFFF
    vertex_size = (size_word >> 16) & 0xFFFF
    if element_count > 64 or vertex_size > 4096:
        raise RW4Error('Invalid Crackdown vertex description')
    elements = []
    cursor = section.p_data + 12
    end = min(len(data), section.p_data + section.data_size)
    for _ in range(element_count):
        if cursor + 12 > end:
            break
        offset_word, format_code, semantic_code = struct.unpack_from('>3I', data, cursor)
        elements.append(Xb2VertexElement(offset_word & 0xFFFF, format_code, semantic_code))
        cursor += 12
    return Xb2VertexDescription(flags, vertex_size, elements)


def parse_xb2_vertex_buffer(data, section):
    if section.p_data + 32 > len(data):
        raise RW4Error('Truncated Crackdown vertex buffer')
    values = struct.unpack_from('>8I', data, section.p_data)
    return Xb2VertexBuffer(
        section_index=section.index,
        description_ref=values[7],
        vertex_count=values[6],
        vertex_size=(values[5] >> 16) & 0xFFFF,
        data_size_hint=values[4],
        data_ref_hint=values[3],
    )


def parse_xb2_index_buffer(data, section):
    if section.p_data + 24 > len(data):
        raise RW4Error('Truncated Crackdown index buffer')
    values = struct.unpack_from('>6I', data, section.p_data)
    return Xb2IndexBuffer(section.index, values[3], values[4], values[5])


def decode_x360_signed_normalized(value, maximum):
    return max(-1.0, min(1.0, float(value) / float(maximum)))


def decode_x360_vertex_value(blob, offset, format_code):
    if offset < 0 or offset >= len(blob):
        return None
    try:
        if format_code == X360DECL_FLOAT1:
            return struct.unpack_from('>f', blob, offset)
        if format_code == X360DECL_FLOAT2:
            return struct.unpack_from('>2f', blob, offset)
        if format_code == X360DECL_FLOAT3:
            return struct.unpack_from('>3f', blob, offset)
        if format_code == X360DECL_FLOAT4:
            return struct.unpack_from('>4f', blob, offset)
        if format_code == X360DECL_D3DCOLOR:
            raw = struct.unpack_from('>I', blob, offset)[0]
            return ((raw >> 16) & 255, (raw >> 8) & 255, raw & 255, (raw >> 24) & 255)
        if format_code == X360DECL_UBYTE4:
            return struct.unpack_from('4B', blob, offset)
        if format_code == X360DECL_BYTE4:
            return struct.unpack_from('4b', blob, offset)
        if format_code == X360DECL_UBYTE4N:
            return tuple(v / 255.0 for v in struct.unpack_from('4B', blob, offset))
        if format_code == X360DECL_BYTE4N:
            return tuple(decode_x360_signed_normalized(v, 127.0) for v in struct.unpack_from('4b', blob, offset))
        if format_code == X360DECL_SHORT2:
            return struct.unpack_from('>2h', blob, offset)
        if format_code == X360DECL_SHORT4:
            return struct.unpack_from('>4h', blob, offset)
        if format_code == X360DECL_USHORT2:
            return struct.unpack_from('>2H', blob, offset)
        if format_code == X360DECL_USHORT4:
            return struct.unpack_from('>4H', blob, offset)
        if format_code == X360DECL_SHORT2N:
            return tuple(decode_x360_signed_normalized(v, 32767.0) for v in struct.unpack_from('>2h', blob, offset))
        if format_code == X360DECL_SHORT4N:
            return tuple(decode_x360_signed_normalized(v, 32767.0) for v in struct.unpack_from('>4h', blob, offset))
        if format_code == X360DECL_USHORT2N:
            return tuple(v / 65535.0 for v in struct.unpack_from('>2H', blob, offset))
        if format_code == X360DECL_USHORT4N:
            return tuple(v / 65535.0 for v in struct.unpack_from('>4H', blob, offset))
        if format_code in (X360DECL_UDEC3, X360DECL_UDEC3N, X360DECL_DEC3, X360DECL_DEC3N):
            raw = struct.unpack_from('>I', blob, offset)[0]
            x = raw & 0x3FF
            y = (raw >> 10) & 0x3FF
            z = (raw >> 20) & 0x3FF
            if format_code in (X360DECL_DEC3, X360DECL_DEC3N):
                def signed10(value):
                    return value - 0x400 if value & 0x200 else value
                x, y, z = signed10(x), signed10(y), signed10(z)
            if format_code == X360DECL_DEC3N:
                return (decode_x360_signed_normalized(x, 511.0), decode_x360_signed_normalized(y, 511.0), decode_x360_signed_normalized(z, 511.0))
            if format_code == X360DECL_UDEC3N:
                return (x / 1023.0, y / 1023.0, z / 1023.0)
            return (x, y, z)
        if format_code == X360DECL_FLOAT16_2:
            return struct.unpack_from('>2e', blob, offset)
        if format_code == X360DECL_FLOAT16_4:
            return struct.unpack_from('>4e', blob, offset)
    except (struct.error, OverflowError):
        return None
    return None


def crackdown_semantic_kind(element):
    # Crackdown's Xenon descriptors encode the RW declaration semantic in the low byte.
    semantic = element.semantic
    if semantic == 0x01:
        return 'POSITION'
    if semantic == 0x03:
        return 'NORMAL'
    if semantic == 0x05:
        return 'COLOR'
    if semantic == 0x06:
        return 'TEXCOORD0'
    if semantic == 0x07:
        return 'TEXCOORD1'
    return 'SEMANTIC_%02X' % semantic


def build_crackdown_triangles(indices, vertex_count):
    # Crackdown xb2 index buffers use restartable triangle strips.
    triangles = []
    strip = []
    parity = 0
    for index in indices:
        if index == 0xFFFF:
            strip.clear()
            parity = 0
            continue
        strip.append(index)
        if len(strip) < 3:
            continue
        if len(strip) > 3:
            strip.pop(0)
        a, b, c = strip
        if parity & 1:
            a, b = b, a
        parity += 1
        if a == b or b == c or a == c:
            continue
        if a >= vertex_count or b >= vertex_count or c >= vertex_count:
            continue
        triangles.append((a, b, c))
    return triangles


def find_crackdown_vertex_blob(arena, data, vbuffer, reserved_raw_sections):
    expected = vbuffer.vertex_count * vbuffer.vertex_size
    if expected <= 0:
        return None, -1
    raw_sections = [section for section in arena.sections if section.type_code == 0 and section.index not in reserved_raw_sections]

    # Most Crackdown VBs store an allocation size two bytes above the raw section size.
    target = max(0, vbuffer.data_size_hint - 2)
    exact = [section for section in raw_sections if section.data_size == target and section.data_size >= expected]
    candidates = exact or [section for section in raw_sections if section.data_size >= expected]
    if not candidates:
        return None, -1
    candidates.sort(key=lambda section: (abs(section.data_size - target), section.data_size - expected, section.index))
    section = candidates[0]
    end = section.p_data + section.data_size
    if section.p_data < 0 or end > len(data):
        return None, -1
    return data[section.p_data:end], section.index


def decode_crackdown_vertices(vertex_blob, vbuffer, description):
    stride = vbuffer.vertex_size or description.vertex_size
    if stride <= 0:
        return [], [], [], []
    count = min(vbuffer.vertex_count, len(vertex_blob) // stride)
    positions = []
    normals = []
    uvs = []
    colors = []
    for vertex_index in range(count):
        base = vertex_index * stride
        position = None
        normal = None
        uv = None
        color = None
        for element in description.elements:
            value = decode_x360_vertex_value(vertex_blob, base + element.offset, element.format_code)
            if value is None:
                continue
            kind = crackdown_semantic_kind(element)
            if kind == 'POSITION' and len(value) >= 3:
                source = tuple(float(v) for v in value[:3])
                position = (source[0], -source[2], source[1])
            elif kind == 'NORMAL' and len(value) >= 3:
                source = tuple(float(v) for v in value[:3])
                normal = (source[0], -source[2], source[1])
            elif kind == 'TEXCOORD0' and len(value) >= 2:
                uv = tuple(float(v) for v in value[:2])
            elif kind == 'COLOR' and len(value) >= 4:
                color = tuple(float(v) / 255.0 if float(v) > 1.0 else float(v) for v in value[:4])
        positions.append(position if position is not None else (0.0, 0.0, 0.0))
        normals.append(normal)
        uvs.append(uv)
        colors.append(color)
    return positions, normals, uvs, colors


def parse_crackdown_arena(data, arena_offset, resource_name=''):
    if arena_offset < 0 or arena_offset + 0x70 > len(data):
        raise RW4Error('Truncated Crackdown RW4 arena')
    if data[arena_offset:arena_offset + 4] != RW4_MAGIC_PREFIX:
        raise RW4Error('Crackdown RW4 arena signature not found')
    platform = data[arena_offset + 4:arena_offset + 8].rstrip(b'\0').decode('ascii', 'replace')
    if platform != 'xb2':
        raise RW4Error('Crackdown (4.1.0.1) expects an xb2 RW4 arena; found %s' % platform)
    if data[arena_offset + 0x0C] != 1:
        raise RW4Error('Crackdown xb2 arena is not marked big-endian')

    section_count = struct.unpack_from('>I', data, arena_offset + 0x20)[0]
    p_infos = struct.unpack_from('>I', data, arena_offset + 0x30)[0]
    if section_count <= 0 or section_count > 100000:
        raise RW4Error('Invalid Crackdown RW4 section count: %d' % section_count)
    info_abs = arena_offset + p_infos
    if info_abs < arena_offset or info_abs + section_count * 20 > len(data):
        raise RW4Error('Crackdown RW4 section table is outside the file')

    manifest_abs = arena_offset + 0x50
    manifest = struct.unpack_from('>6I', data, manifest_abs)
    if manifest[0] != TYPE_ARENA_SECTION_MANIFEST:
        raise RW4Error('Crackdown RW4 section manifest not found')
    types_abs = manifest_abs + manifest[3]
    if types_abs + 12 > len(data):
        raise RW4Error('Truncated Crackdown RW4 section type table')
    types_header = struct.unpack_from('>3I', data, types_abs)
    if types_header[0] != TYPE_ARENA_SECTION_TYPES:
        raise RW4Error('Crackdown RW4 section type table not found')
    type_count = types_header[1]
    if type_count <= 0 or type_count > 4096 or types_abs + 12 + type_count * 4 > len(data):
        raise RW4Error('Invalid Crackdown RW4 section type count')
    type_codes = [struct.unpack_from('>I', data, types_abs + 12 + index * 4)[0] for index in range(type_count)]

    arena = CrackdownArena(arena_offset, platform, p_infos, len(data) - arena_offset, section_count=section_count, resource_name=resource_name)
    for index in range(section_count):
        values = struct.unpack_from('>5I', data, info_abs + index * 20)
        type_code_index = values[4]
        type_code = type_codes[type_code_index] if type_code_index < len(type_codes) else 0xFFFFFFFF
        p_data = arena_offset + values[0]
        arena.sections.append(SectionInfo(index, p_data, values[1], values[2], values[3], type_code_index, type_code))

    index_buffers = {}
    vertex_buffers = {}
    descriptions = {}
    for section in arena.sections:
        try:
            if section.type_code == TYPE_VERTEX_DESCRIPTION:
                value = parse_xb2_vertex_description(data, section)
                descriptions[section.index] = value
                arena.objects[section.index] = value
            elif section.type_code == TYPE_VERTEX_BUFFER:
                value = parse_xb2_vertex_buffer(data, section)
                vertex_buffers[section.index] = value
                arena.objects[section.index] = value
            elif section.type_code == TYPE_INDEX_BUFFER:
                value = parse_xb2_index_buffer(data, section)
                index_buffers[section.index] = value
                arena.objects[section.index] = value
            elif section.type_code == 0:
                end = section.p_data + section.data_size
                if 0 <= section.p_data <= end <= len(data):
                    arena.objects[section.index] = data[section.p_data:end]
        except (struct.error, RW4Error):
            arena.objects[section.index] = None

    reserved_raw_sections = {buffer.data_ref for buffer in index_buffers.values() if 0 <= buffer.data_ref < section_count}
    decoded_vertex_buffers = {}
    for section_index, vbuffer in vertex_buffers.items():
        description = descriptions.get(vbuffer.description_ref)
        if description is None:
            continue
        blob, raw_ref = find_crackdown_vertex_blob(arena, data, vbuffer, reserved_raw_sections)
        if blob is None:
            continue
        vbuffer.raw_section_ref = raw_ref
        decoded_vertex_buffers[section_index] = (vbuffer, description, blob)

    # A descriptor section begins a draw cluster. Index buffers following it use the
    # vertex buffer that points back to that descriptor, even when the VB object itself
    # is serialized elsewhere in the arena. This relationship is stable in Crackdown xb2.
    descriptor_indices = sorted(descriptions)
    mesh_number = 0
    for ib_section_index in sorted(index_buffers):
        ibuffer = index_buffers[ib_section_index]
        descriptor_ref = -1
        for candidate in descriptor_indices:
            if candidate <= ib_section_index:
                descriptor_ref = candidate
            else:
                break
        if descriptor_ref < 0:
            continue
        matching = [(index, entry) for index, entry in decoded_vertex_buffers.items() if entry[0].description_ref == descriptor_ref]
        if not matching:
            continue
        matching.sort(key=lambda item: (abs(item[0] - ib_section_index), item[0]))
        vb_section_index, (vbuffer, description, vertex_blob) = matching[0]

        if ibuffer.data_ref < 0 or ibuffer.data_ref >= len(arena.sections):
            continue
        raw_section = arena.sections[ibuffer.data_ref]
        if raw_section.type_code != 0:
            continue
        available_count = min(ibuffer.data_size, raw_section.data_size) // 2
        index_count = min(ibuffer.index_count, available_count)
        if index_count < 3:
            continue
        index_start = raw_section.p_data
        if index_start < 0 or index_start + index_count * 2 > len(data):
            continue
        indices = [struct.unpack_from('>H', data, index_start + i * 2)[0] for i in range(index_count)]

        positions, normals, uvs, colors = decode_crackdown_vertices(vertex_blob, vbuffer, description)
        triangles = build_crackdown_triangles(indices, len(positions))
        if not positions or not triangles:
            continue
        prefix = os.path.splitext(os.path.basename(resource_name))[0] if resource_name else 'Crackdown_Arena_%03X' % arena_offset
        name = '%s_Mesh_%03d' % (prefix, mesh_number)
        parsed = ParsedMesh(name, positions, triangles, uvs, normals, colors, ib_section_index)
        arena.parsed_meshes.append(parsed)
        mesh_number += 1

    return arena


def nearest_crackdown_resource_name(resources, arena_offset):
    preferred = [resource for resource in resources if resource.offset < arena_offset and resource.kind == 'DFF']
    if not preferred:
        return ''
    return max(preferred, key=lambda resource: resource.offset).name


def parse_crackdown_container(data):
    result = CrackdownContainer()
    seen_resources = set()
    seen_classes = set()

    for offset, text in extract_ascii_strings(data, 4):
        if text.startswith('c') and len(text) <= 80 and re.fullmatch(r'c[A-Za-z0-9_]+', text):
            if text not in seen_classes:
                seen_classes.add(text)
                result.classes.append(text)
        lower = text.lower()
        kind = None
        if lower.endswith('.dff'):
            kind = 'DFF'
        elif lower.endswith('.rx2'):
            kind = 'RX2'
        elif lower.endswith('.info'):
            kind = 'INFO'
        elif '.resblock' in lower:
            kind = 'RESBLOCK'
        if kind and text not in seen_resources:
            seen_resources.add(text)
            result.resources.append(CrackdownResource(text, offset, kind))

    for offset, text in extract_utf16le_strings(data, 4):
        lower = text.lower()
        kind = None
        if lower.endswith('.dff'):
            kind = 'DFF'
        elif lower.endswith('.rx2'):
            kind = 'RX2'
        elif lower.endswith('.info'):
            kind = 'INFO'
        elif '.resblock' in lower:
            kind = 'RESBLOCK'
        if kind and text not in seen_resources:
            seen_resources.add(text)
            result.resources.append(CrackdownResource(text, offset, kind))

    result.resources.sort(key=lambda resource: resource.offset)
    cursor = 0
    while True:
        offset = data.find(RW4_MAGIC_PREFIX, cursor)
        if offset < 0:
            break
        platform = data[offset + 4:offset + 8].rstrip(b'\0').decode('ascii', 'replace') if offset + 8 <= len(data) else ''
        resource_name = nearest_crackdown_resource_name(result.resources, offset)
        if platform == 'xb2':
            try:
                arena = parse_crackdown_arena(data, offset, resource_name)
            except RW4Error:
                footer_offset = struct.unpack_from('>I', data, offset + 0x30)[0] if offset + 0x34 <= len(data) else -1
                arena = CrackdownArena(offset, platform, footer_offset, len(data) - offset, resource_name=resource_name)
        else:
            footer_offset = struct.unpack_from('<I', data, offset + 0x30)[0] if offset + 0x34 <= len(data) else -1
            arena = CrackdownArena(offset, platform, footer_offset, len(data) - offset, resource_name=resource_name)
        result.arenas.append(arena)
        cursor = offset + 4

    return result
