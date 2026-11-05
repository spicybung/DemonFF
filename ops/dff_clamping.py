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

from dataclasses import dataclass


DFF_VERTEX_LIMIT = 65535


@dataclass
class DffClampSelection:
    vertex_indices: list
    face_indices: list
    faces: list
    original_vertices: int
    original_faces: int

    @property
    def omitted_vertices(self):
        return self.original_vertices - len(self.vertex_indices)

    @property
    def omitted_faces(self):
        return self.original_faces - len(self.face_indices)

    def report(self, label):
        return (f'{label}: kept {len(self.vertex_indices)}/{self.original_vertices} vertex records '
                f'and {len(self.face_indices)}/{self.original_faces} faces; '
                f'omitted {self.omitted_vertices} vertices and {self.omitted_faces} faces')


def select_clamped_geometry(vertex_count, faces, vertex_limit=DFF_VERTEX_LIMIT):
    if vertex_count < 0 or vertex_limit < 0:
        raise ValueError('Vertex count and vertex limit must not be negative')
    faces = list(faces)
    selected_vertices = []
    selected_faces = []
    remapped_faces = []
    remap = {}
    oversized = vertex_count > vertex_limit
    if not oversized:
        selected_vertices = list(range(vertex_count))
    if not faces:
        selected_vertices = list(range(min(vertex_count, vertex_limit)))
    for face_index, face in enumerate(faces):
        indices = tuple(face)
        if len(indices) < 3 or len(set(indices)) < 3:
            continue
        if any(not isinstance(index, int) or not 0 <= index < vertex_count for index in indices):
            continue
        if oversized:
            needed = list(dict.fromkeys(index for index in indices if index not in remap))
            if len(selected_vertices) + len(needed) > vertex_limit:
                continue
            for index in needed:
                remap[index] = len(selected_vertices)
                selected_vertices.append(index)
            remapped_faces.append(tuple(remap[index] for index in indices))
        else:
            remapped_faces.append(indices)
        selected_faces.append(face_index)
    return DffClampSelection(selected_vertices, selected_faces, remapped_faces, vertex_count, len(faces))
