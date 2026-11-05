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

import os
import re
from dataclasses import dataclass
from pathlib import Path
from struct import unpack_from

SECTOR_SIZE = 2048


@dataclass
class DirectoryEntry:
    offset: int
    size: int
    name: str

    @classmethod
    def read_from_memory(cls, data, offset=0, version=1):
        if offset < 0 or offset + 32 > len(data):
            raise ValueError('Truncated IMG directory entry')
        if version == 2:
            sector, streaming_size, archive_size, name = unpack_from('<IHH24s', data, offset)
            size = streaming_size or archive_size
        else:
            sector, size, name = unpack_from('<II24s', data, offset)
        name = name.split(b'\0', 1)[0].decode('latin-1')
        return cls(sector, size, name)


def findCompanion(path, suffix):
    path = Path(path)
    wanted = path.with_suffix(suffix).name.casefold()
    matches = [entry for entry in path.parent.iterdir() if entry.is_file() and entry.name.casefold() == wanted]
    if not matches:
        stem = re.sub(r'\s*\(\d+(?:-\d+)?\)$', '', path.stem).casefold()
        matches = [entry for entry in path.parent.iterdir()
                   if entry.is_file() and entry.suffix.casefold() == suffix.casefold()
                   and re.sub(r'\s*\(\d+(?:-\d+)?\)$', '', entry.stem).casefold() == stem]
    if len(matches) > 1:
        raise ValueError('More than one matching companion for ' + path.name)
    return matches[0] if matches else None


def trimDffPadding(data):
    position = 0
    while position < len(data):
        if not data[position:].strip(b'\0'):
            return data[:position]
        if position + 12 > len(data):
            raise ValueError('Truncated DFF in IMG archive')
        kind, size, version = unpack_from('<III', data, position)
        end = position + 12 + size
        if end > len(data):
            raise ValueError('DFF chunk extends outside its IMG entry')
        position = end
    return data


class img:
    def load_dir_memory(self, data, version=1):
        if len(data) % 32:
            raise ValueError('IMG directory length is not a multiple of 32')
        self.directory_entries = [DirectoryEntry.read_from_memory(data, offset, version)
                                  for offset in range(0, len(data), 32)]
        self.entry_idx = 0

    def clear(self):
        self.directory_entries = []
        self.entry_idx = 0

    @classmethod
    def open(cls, filename):
        file = open(filename, 'rb')
        archive = cls(file)
        try:
            file.seek(0, os.SEEK_END)
            length = file.tell()
            file.seek(0)
            header = file.read(8)
            directory_end = 0
            if header[:4] == b'VER2':
                if len(header) != 8:
                    raise ValueError('Truncated IMG header')
                count = unpack_from('<I', header, 4)[0]
                if count > (length - 8) // 32:
                    raise ValueError('IMG directory count exceeds archive size')
                directory_end = 8 + count * 32
                archive.load_dir_memory(file.read(count * 32), version=2)
            else:
                directory = findCompanion(filename, '.dir')
                if directory is None:
                    raise ValueError('IMG v1 requires a matching DIR file')
                archive.load_dir_memory(directory.read_bytes(), version=1)
            for entry in archive.directory_entries:
                start = entry.offset * SECTOR_SIZE
                end = start + entry.size * SECTOR_SIZE
                if start < directory_end or end > length:
                    raise ValueError('IMG entry %r is outside its archive data' % entry.name)
            file.seek(0)
            return archive
        except Exception:
            archive.close()
            raise

    def close(self):
        file = getattr(self, '_file', None)
        if file is not None and not file.closed:
            file.close()

    def read_entry(self, entry_idx=None):
        index = self.entry_idx if entry_idx is None else entry_idx
        if not 0 <= index < len(self.directory_entries):
            return '', b''
        entry = self.directory_entries[index]
        self._file.seek(entry.offset * SECTOR_SIZE)
        data = self._file.read(entry.size * SECTOR_SIZE)
        if len(data) != entry.size * SECTOR_SIZE:
            raise ValueError('Truncated IMG entry ' + entry.name)
        return entry.name, data

    def find_entry_idx(self, name):
        wanted = name.casefold()
        return next((index for index, entry in enumerate(self.directory_entries)
                     if entry.name.casefold() == wanted), -1)

    def __init__(self, file):
        self._file = file
        self.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()
