# DemonFF - Blender scripts for working with Renderware & R*/SA-MP/open.mp formats in Blender
# 2023 - 2026 spicybung

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
import struct

from dataclasses import dataclass
from io import BytesIO, BufferedReader, StringIO

from .data import map_data
from .img import img

#######################################################
@dataclass
class MapData:
    object_instances: list
    object_data: dict
    cull_instances: list
    grge_instances: list
    enex_instances: list
    effects_2dfx: dict

#######################################################
@dataclass
class TextIPLData:
    object_instances: list
    cull_instances: list
    grge_instances: list
    enex_instances: list

#######################################################
@dataclass
class TextIDEData:
    objs_instances: list
    tobj_instances: list
    anim_instances: list

# Base for all IPL / IDE section reader / writer classes
#######################################################
class SectionUtility:

    def __init__(self, section_name, data_structures = []):
        self.section_name = section_name
        self.data_structures_dict = {len(ds._fields): ds for ds in data_structures}

    #######################################################
    def read(self, file_stream):

        entries = []

        line = file_stream.readline().strip()
        while line.lower() != "end":

            if not line or line.startswith("#"):
                line = file_stream.readline().strip()
                continue

            # Split line and trim individual elements
            line_params = [e.strip() for e in line.split(",")]

            # Append file name for IDEs (needed for collision lookups)
            filename = os.path.basename(file_stream.name)
            if filename.lower().endswith('.ide'):
                line_params.append(filename)

            # Get the correct data structure for this section entry
            data_structure = self.get_data_structure(line_params)

            # Validate data structure
            if data_structure is None:
                print(type(self).__name__, "Error: No appropriate data structure found")
                print("    Section name:", self.section_name)
                print("    Line parameters:", str(line_params))

            elif len(data_structure._fields) != len(line_params):
                print(
                    type(self).__name__, "Error: Number of line parameters "
                    "doesn't match the number of structure fields."
                )
                print("    Section name:", self.section_name)
                print("    Data structure name:", data_structure.__name__)
                print("    Data structure:", str(data_structure._fields))
                print("    Line parameters:", str(line_params))

            else:
                # Add entry
                entries.append(data_structure(*line_params))

            # Read next line
            line = file_stream.readline().strip()

        return entries

    #######################################################
    def get_data_structure(self, line_params):
        return self.data_structures_dict.get(len(line_params))

    #######################################################
    def write(self, file_stream, lines):
        file_stream.write(f"{self.section_name}\n")
        for line in lines:
            file_stream.write(f"{line}\n")
        file_stream.write("end\n")

# Utility for reading / writing to map data files (.IPL, .IDE)
#######################################################
class MapDataUtility:

    forced_ide_paths = None
    OBJECT_DATA_ID_INDEX = "__demonff_id_index__"
    OBJECT_DATA_NAME_INDEX = "__demonff_name_index__"
    OBJECT_DATA_PAIR_INDEX = "__demonff_pair_index__"

    ########################################################################
    @staticmethod
    def normalize_map_lookup_name(value):
        name = str(value or "").strip().replace('\\', '/')
        name = os.path.basename(name)
        name = os.path.splitext(name)[0]
        return name.lower()

    ########################################################################
    @staticmethod
    def normalize_map_id(value):
        value_text = str(value if value is not None else "").strip()
        try:
            numeric_value = float(value_text)
            if numeric_value.is_integer():
                return str(int(numeric_value))
        except (TypeError, ValueError):
            pass
        return value_text

    ########################################################################
    @staticmethod
    def normalize_map_path(value):
        return str(value or "").strip().replace('\\', '/').lower()

    ########################################################################
    @staticmethod
    def discover_ide_paths(game_root):
        self = MapDataUtility
        discovered = []
        seen = set()

        map_roots = (
            os.path.join(game_root, "DATA", "MAPS"),
            os.path.join(game_root, "data", "maps"),
        )

        for map_root in map_roots:
            if not os.path.isdir(map_root):
                continue

            for root_path, _, filenames in os.walk(map_root):
                for filename in filenames:
                    if not filename.lower().endswith('.ide'):
                        continue

                    fullpath = os.path.join(root_path, filename)
                    relative_path = os.path.relpath(fullpath, game_root)
                    lookup_key = self.normalize_map_path(relative_path)
                    if lookup_key in seen:
                        continue

                    seen.add(lookup_key)
                    discovered.append(relative_path)

        default_ide = self.find_path_case_insensitive(game_root, os.path.join('DATA', 'DEFAULT.IDE'))
        if default_ide:
            relative_path = os.path.relpath(default_ide, game_root)
            lookup_key = self.normalize_map_path(relative_path)
            if lookup_key not in seen:
                discovered.insert(0, relative_path)

        return discovered

    ########################################################################
    @staticmethod
    def is_shared_ide_path(ide_path):
        normalized = MapDataUtility.normalize_map_path(ide_path)
        stem = os.path.splitext(os.path.basename(normalized))[0]
        return (
            '/generic/' in normalized
            or '/leveldes/' in normalized
            or 'xref' in normalized
            or stem in {'default', 'generic'}
        )

    ########################################################################
    @staticmethod
    def get_ide_path_affinity(ide_path, ipl_section):
        ide_normalized = MapDataUtility.normalize_map_path(ide_path)
        ipl_normalized = MapDataUtility.normalize_map_path(ipl_section)

        ide_stem = os.path.splitext(os.path.basename(ide_normalized))[0]
        ipl_stem = os.path.splitext(os.path.basename(ipl_normalized))[0]
        ide_parent = os.path.basename(os.path.dirname(ide_normalized))
        ipl_parent = os.path.basename(os.path.dirname(ipl_normalized))

        if ide_stem and ide_stem == ipl_stem and ide_parent == ipl_parent:
            return 100
        if ide_stem and ide_stem == ipl_stem:
            return 90
        if ide_parent and ide_parent == ipl_parent:
            return 80
        if ide_stem and ipl_stem and (ide_stem.startswith(ipl_stem) or ipl_stem.startswith(ide_stem)):
            return 40
        if ide_stem[:4] and ide_stem[:4] == ipl_stem[:4]:
            return 20
        return 0

    ########################################################################
    @staticmethod
    def collect_ide_object_entries(sections):
        entries = []
        for section_name in ('objs', 'tobj', 'anim'):
            entries.extend(sections.get(section_name, []))
        return entries

    ########################################################################
    @staticmethod
    def select_ide_paths_for_ipl(game_root, ide_paths, ipl_section, object_instances, data_structures, aliases):
        self = MapDataUtility

        unique_paths = []
        seen_paths = set()
        for ide_path in ide_paths:
            normalized_path = self.normalize_map_path(ide_path)
            if not normalized_path or normalized_path in seen_paths:
                continue
            seen_paths.add(normalized_path)
            unique_paths.append(ide_path)

        wanted_ids = set()
        wanted_names = set()
        wanted_pairs = set()
        for instance in object_instances:
            instance_id = self.normalize_map_id(getattr(instance, 'id', ''))
            model_name = self.normalize_map_lookup_name(getattr(instance, 'modelName', ''))
            if instance_id:
                wanted_ids.add(instance_id)
            if model_name:
                wanted_names.add(model_name)
            if instance_id and model_name:
                wanted_pairs.add((instance_id, model_name))

        candidate_info = []
        for ide_path in unique_paths:
            fullpath = self.get_full_path(game_root, ide_path)
            if not os.path.isfile(fullpath):
                continue

            sections = self.read_file(fullpath, data_structures, aliases)
            entries = self.collect_ide_object_entries(sections)
            entry_ids = set()
            entry_names = set()
            entry_pairs = set()

            for entry in entries:
                entry_id = self.normalize_map_id(getattr(entry, 'id', ''))
                model_name = self.normalize_map_lookup_name(getattr(entry, 'modelName', ''))
                if entry_id:
                    entry_ids.add(entry_id)
                if model_name:
                    entry_names.add(model_name)
                if entry_id and model_name:
                    entry_pairs.add((entry_id, model_name))

            candidate_info.append({
                'path': ide_path,
                'affinity': self.get_ide_path_affinity(ide_path, ipl_section),
                'shared': self.is_shared_ide_path(ide_path),
                'id_matches': len(entry_ids.intersection(wanted_ids)),
                'name_matches': len(entry_names.intersection(wanted_names)),
                'pair_matches': len(entry_pairs.intersection(wanted_pairs)),
                'entry_names': entry_names,
            })

        selected_paths = []
        selected_keys = set()

        def select(candidate):
            candidate_path = candidate['path']
            candidate_key = self.normalize_map_path(candidate_path)
            if candidate_key in selected_keys:
                return
            selected_keys.add(candidate_key)
            selected_paths.append(candidate_path)

        for candidate in candidate_info:
            if candidate['affinity'] >= 80:
                select(candidate)
                continue

            if wanted_names:
                if candidate['pair_matches'] > 0:
                    select(candidate)
                    continue
                if candidate['shared'] and candidate['name_matches'] > 0:
                    select(candidate)
                    continue
            elif candidate['id_matches'] > 0 and candidate['shared']:
                select(candidate)

        if wanted_names:
            resolved_names = set()
            for candidate in candidate_info:
                if self.normalize_map_path(candidate['path']) in selected_keys:
                    resolved_names.update(candidate['entry_names'].intersection(wanted_names))

            unresolved_names = wanted_names.difference(resolved_names)
            if unresolved_names:
                for candidate in candidate_info:
                    if candidate['entry_names'].intersection(unresolved_names):
                        select(candidate)

        if not selected_paths:
            local_candidates = [candidate for candidate in candidate_info if candidate['affinity'] > 0]
            for candidate in sorted(local_candidates, key=lambda item: item['affinity'], reverse=True):
                select(candidate)

        if not selected_paths:
            selected_paths = list(unique_paths)

        if selected_paths:
            print('MapDataUtility: selected IDEs for %s:' % os.path.basename(str(ipl_section)))
            for selected_path in selected_paths:
                print('   ', selected_path)

        return selected_paths

    ########################################################################
    @staticmethod
    def build_object_data(ide_sections):
        self = MapDataUtility
        object_data = {}
        id_index = {}
        name_index = {}
        pair_index = {}
        entry_keys = set()

        for entry in self.collect_ide_object_entries(ide_sections):
            entry_id = self.normalize_map_id(getattr(entry, 'id', ''))
            model_name = self.normalize_map_lookup_name(getattr(entry, 'modelName', ''))
            txd_name = self.normalize_map_lookup_name(getattr(entry, 'txdName', ''))
            filename = self.normalize_map_path(getattr(entry, 'filename', ''))
            entry_key = (type(entry).__name__, entry_id, model_name, txd_name, filename, tuple(entry))
            if entry_key in entry_keys:
                continue
            entry_keys.add(entry_key)

            if entry_id:
                id_index.setdefault(entry_id, []).append(entry)
            if model_name:
                name_index.setdefault(model_name, []).append(entry)
            if entry_id and model_name:
                pair_index.setdefault((entry_id, model_name), []).append(entry)

        object_data[self.OBJECT_DATA_ID_INDEX] = id_index
        object_data[self.OBJECT_DATA_NAME_INDEX] = name_index
        object_data[self.OBJECT_DATA_PAIR_INDEX] = pair_index

        for pair_key, entries in pair_index.items():
            if len(entries) == 1:
                object_data[pair_key] = entries[0]

        ambiguous_ids = []
        for entry_id, entries in id_index.items():
            if len(entries) != 1:
                ambiguous_ids.append(entry_id)
                continue

            object_data[entry_id] = entries[0]
            try:
                object_data[int(entry_id)] = entries[0]
            except (TypeError, ValueError):
                pass

        for model_name, entries in name_index.items():
            if len(entries) == 1:
                object_data[model_name] = entries[0]

        if ambiguous_ids:
            print(
                'MapDataUtility: ambiguous IDE IDs will only resolve by model name:',
                ', '.join(sorted(ambiguous_ids)[:16])
            )

        return object_data

    ########################################################################
    @staticmethod
    def resolve_object_data_entry(object_data, instance_id, model_name=''):
        self = MapDataUtility
        entry_id = self.normalize_map_id(instance_id)
        normalized_name = self.normalize_map_lookup_name(model_name)

        id_index = object_data.get(self.OBJECT_DATA_ID_INDEX, {})
        name_index = object_data.get(self.OBJECT_DATA_NAME_INDEX, {})
        pair_index = object_data.get(self.OBJECT_DATA_PAIR_INDEX, {})

        if normalized_name:
            if entry_id:
                pair_entries = pair_index.get((entry_id, normalized_name), [])
                if len(pair_entries) == 1:
                    return pair_entries[0]

                id_name_matches = [
                    entry
                    for entry in id_index.get(entry_id, [])
                    if self.normalize_map_lookup_name(getattr(entry, 'modelName', '')) == normalized_name
                ]
                if len(id_name_matches) == 1:
                    return id_name_matches[0]

            name_entries = name_index.get(normalized_name, [])
            if len(name_entries) == 1:
                return name_entries[0]

            legacy_pair = object_data.get((entry_id, normalized_name)) if entry_id else None
            if legacy_pair is not None:
                return legacy_pair

            legacy_name = object_data.get(normalized_name)
            if legacy_name is not None:
                return legacy_name

            return None

        id_entries = id_index.get(entry_id, [])
        if len(id_entries) == 1:
            return id_entries[0]

        if entry_id:
            legacy_entry = object_data.get(entry_id)
            if legacy_entry is not None:
                return legacy_entry

            try:
                legacy_entry = object_data.get(int(entry_id))
                if legacy_entry is not None:
                    return legacy_entry
            except (TypeError, ValueError):
                pass

        return None

    # Finds the path to a file case-insensitively
    #######################################################
    @staticmethod
    def find_path_case_insensitive(base_path, filename):
        current_path = os.path.join(base_path, filename)

        if os.path.isfile(current_path):
            return current_path

        current_path = base_path
        parts = os.path.normpath(filename).split(os.sep)

        for part in parts:
            try:
                entries = os.listdir(current_path)
            except FileNotFoundError:
                return None

            match = next((entry for entry in entries if entry.lower() == part.lower()), None)
            if match is None:
                return None
            current_path = os.path.join(current_path, match)

        return current_path

    # Check if file stream contains binary IPL data by reading its header
    #######################################################
    @staticmethod
    def is_binary_ipl_stream(file_stream):
        # Binary IPL files always start with the ASCII string "bnry"
        current_pos = file_stream.tell()
        try:
            header = file_stream.read(4)
            file_stream.seek(current_pos)
            return header == b'bnry'
        except (IOError, OSError):
            file_stream.seek(current_pos)
            return False

    # Get full path of file
    #######################################################
    @staticmethod
    def get_full_path(game_root, filename):
        # Check if file name is already an absolute path
        if os.path.isabs(filename):
            return filename

        fullpath = MapDataUtility.find_path_case_insensitive(game_root, filename)
        return fullpath or os.path.join(game_root, filename)

    # Merge Dictionaries of Lists
    #######################################################
    @staticmethod
    def merge_dols(dol1, dol2):
        result = dict(dol1, **dol2)
        result.update((k, dol1[k] + dol2[k])
                        for k in set(dol1).intersection(dol2))
        return result

    # Read binary IPL data from a file stream (credit to Allerek)
    #######################################################
    @staticmethod
    def read_binary_ipl_from_stream(file_stream, data_structures):
        sections = {}

        # Save the starting position (where the IPL file begins)
        start_pos = file_stream.tell()

        # Read and unpack the header
        header = file_stream.read(32)
        if len(header) < 32:
            print("Error: Invalid binary IPL file - header too short")
            return sections

        _, num_of_instances, _, _, _, _, _, instances_offset = struct.unpack('4siiiiiii', header)

        # Read and process instance definitions
        item_size = 40
        insts = []

        # Seek relative to the start of the IPL file
        file_stream.seek(start_pos + instances_offset)

        for i in range(num_of_instances):
            instances = file_stream.read(item_size)
            if len(instances) < item_size:
                print(f"Warning: Could not read instance {i}, reached end of file")
                break

            # Read binary instance
            x_pos, y_pos, z_pos, x_rot, y_rot, z_rot, w_rot, obj_id, interior, lod = struct.unpack('fffffffiii', instances)

            # Create value list (with values as strings) and map to the data struct
            vals = [obj_id, "", interior, x_pos, y_pos, z_pos, x_rot, y_rot, z_rot, w_rot, lod]
            insts.append(data_structures['inst'](*[str(v) for v in vals]))

        sections["inst"] = insts
        print("inst: %d entries" % len(insts))
        return sections

    # Read text-based IPL/IDE file from stream
    #######################################################
    @staticmethod
    def read_text_file_from_stream(file_stream, data_structures, aliases):
        sections = {}

        line = file_stream.readline().strip()

        while line:
            # Presume we have a section start
            section_name = line
            section_utility = None

            if section_name in aliases:
                available_data_structures = [data_structures[s] for s in aliases[line]]
                section_utility = SectionUtility(section_name, available_data_structures)

            elif section_name in data_structures:
                section_utility = SectionUtility(section_name, [data_structures[section_name]])

            if section_utility is not None:
                sections[section_name] = section_utility.read(file_stream)
                print("%s: %d entries" % (
                    section_name, len(sections[section_name])
                ))

            # Get next section
            line = file_stream.readline().strip()

        return sections

    # Returns a dictionary of sections found in the given file
    #######################################################
    @staticmethod
    def read_file(filepath, data_structures, aliases):
        self = MapDataUtility

        sections = {}
        try:
            with open(filepath, 'rb') as file_stream:
                if self.is_binary_ipl_stream(file_stream):
                    sections = self.read_binary_ipl_from_stream(file_stream, data_structures)
                else:
                    binary_data = file_stream.read()
                    text_data = binary_data.decode('latin-1')
                    text_stream = StringIO(text_data)
                    text_stream.name = filepath  # Set name attribute for IDE filename detection
                    sections = self.read_text_file_from_stream(text_stream, data_structures, aliases)

        except FileNotFoundError:
            print("File not found:", filepath)

        return sections

    ########################################################################
    @staticmethod
    def load_ide_data(game_root, ide_paths, data_structures, aliases):
        self = MapDataUtility

        ide = {}
        for file in ide_paths:
            fullpath = self.get_full_path(game_root, file)
            print('\nMapDataUtility reading:', fullpath)
            sections = self.read_file(fullpath, data_structures, aliases)
            ide = self.merge_dols(ide, sections)

        return ide

    ########################################################################
    @staticmethod
    def load_ipl_data(game_root, ipl_section, data_structures, aliases):
        self = MapDataUtility

        ipl = {}
        fullpath = self.get_full_path(game_root, ipl_section)
        print('\nMapDataUtility reading:', fullpath)

        if not os.path.isfile(fullpath):
             # If not found, look for it inside gta3.img
            imgpath = os.path.join(game_root, 'models/gta3.img')

            try:
                with img.open(imgpath) as img_file:
                    basename = os.path.basename(ipl_section)
                    entry_idx = img_file.find_entry_idx(basename)

                    if entry_idx > -1:
                        print("Read binary IPL from gta3.img:", basename)
                        _, data = img_file.read_entry(entry_idx)
                        file_stream = BufferedReader(BytesIO(data))
                        sections = MapDataUtility.read_binary_ipl_from_stream(file_stream, data_structures)
                        ipl = self.merge_dols(ipl, sections)
                        return ipl

            except FileNotFoundError:
                print("Warning: gta3.img not found at:", imgpath)

        sections = self.read_file(fullpath, data_structures, aliases)
        return self.merge_dols(ipl, sections)

    ########################################################################
    @staticmethod
    def detect_text_ipl_game(filename):
        """Detect the text IPL inst layout from the first valid inst row."""
        with open(filename, 'rb') as stream:
            if stream.read(4) == b'bnry':
                return map_data.game_version.SA

        with open(filename, 'r', encoding='latin-1', errors='replace') as stream:
            in_inst = False
            for raw_line in stream:
                line = raw_line.split('#', 1)[0].strip()
                if not line:
                    continue
                lower = line.lower()
                if lower == 'inst':
                    in_inst = True
                    continue
                if lower == 'end':
                    if in_inst:
                        break
                    continue
                if not in_inst:
                    continue

                field_count = len([part.strip() for part in line.split(',')])
                if field_count == 12:
                    return map_data.game_version.III
                if field_count == 13:
                    return map_data.game_version.VC
                if field_count == 11:
                    return map_data.game_version.SA
                raise ValueError(
                    'Unsupported IPL inst row with %d fields in %s' %
                    (field_count, filename)
                )

        raise ValueError('No valid inst rows found in IPL: %s' % filename)

    ########################################################################
    @staticmethod
    def load_map_data(game_id, game_root, ipl_section, is_custom_ipl):
        self = MapDataUtility
        data = map_data.data[game_id].copy()

        ipl_structures = data['structures']
        ipl_aliases = data['IPL_aliases']
        if is_custom_ipl:
            custom_path = self.get_full_path(game_root, ipl_section)
            detected_game = self.detect_text_ipl_game(custom_path)
            detected_data = map_data.data[detected_game]
            ipl_structures = detected_data['structures']
            ipl_aliases = detected_data['IPL_aliases']
            print('MapDataUtility: auto-detected IPL layout:', detected_game)

        ipl = self.load_ipl_data(
            game_root,
            ipl_section,
            ipl_structures,
            ipl_aliases
        )

        object_instances = list(ipl.get('inst', []))
        cull_instances = list(ipl.get('cull', []))
        grge_instances = list(ipl.get('grge', []))
        enex_instances = list(ipl.get('enex', []))

        forced_ide_paths = list(self.forced_ide_paths or [])
        if forced_ide_paths:
            ide_paths = forced_ide_paths
        elif is_custom_ipl:
            ide_paths = self.discover_ide_paths(game_root)
            ide_paths = self.select_ide_paths_for_ipl(
                game_root,
                ide_paths,
                ipl_section,
                object_instances,
                data['structures'],
                data['IDE_aliases']
            )
        elif game_id == map_data.game_version.VCS:
            ide_paths = self.select_ide_paths_for_ipl(
                game_root,
                list(data['IDE_paths']),
                ipl_section,
                object_instances,
                data['structures'],
                data['IDE_aliases']
            )
        else:
            ide_paths = list(data['IDE_paths'])

            if game_id == map_data.game_version.SA:
                selected_paths = []
                ipl_normalized = self.normalize_map_path(ipl_section)
                ipl_name = os.path.splitext(os.path.basename(ipl_normalized))[0]
                ipl_prefix = ipl_name[:3]

                for ide_path in ide_paths:
                    ide_normalized = self.normalize_map_path(ide_path)
                    ide_name = os.path.splitext(os.path.basename(ide_normalized))[0]
                    if self.is_shared_ide_path(ide_path) or ide_name[:3] == ipl_prefix:
                        selected_paths.append(ide_path)

                if selected_paths:
                    ide_paths = selected_paths

        ide = self.load_ide_data(
            game_root,
            ide_paths,
            data['structures'],
            data['IDE_aliases']
        )

        object_data = self.build_object_data(ide)
        effects_2dfx = {}
        for entry in ide.get('2dfx', []):
            entry_id = self.normalize_map_id(getattr(entry, 'id', ''))
            effects_2dfx.setdefault(entry_id, []).append(entry)

        return MapData(
            object_instances=object_instances,
            object_data=object_data,
            cull_instances=cull_instances,
            grge_instances=grge_instances,
            enex_instances=enex_instances,
            effects_2dfx=effects_2dfx
        )

    ########################################################################
    @staticmethod
    def write_text_ipl_to_stream(file_stream, game_id, ipl_data:TextIPLData):
        file_stream.write("# IPL generated with DemonFF\n")

        section_utility = SectionUtility("inst")
        section_utility.write(file_stream, ipl_data.object_instances)

        section_utility = SectionUtility("cull")
        section_utility.write(file_stream, ipl_data.cull_instances)

        if game_id == map_data.game_version.III:
            pass

        elif game_id == map_data.game_version.VC:
            section_utility = SectionUtility("pick")
            section_utility.write(file_stream, [])

            section_utility = SectionUtility("path")
            section_utility.write(file_stream, [])

        elif game_id == map_data.game_version.SA:
            section_utility = SectionUtility("path")
            section_utility.write(file_stream, [])

            section_utility = SectionUtility("grge")
            section_utility.write(file_stream, ipl_data.grge_instances)

            section_utility = SectionUtility("enex")
            section_utility.write(file_stream, ipl_data.enex_instances)

            section_utility = SectionUtility("pick")
            section_utility.write(file_stream, [])

            section_utility = SectionUtility("cars")
            section_utility.write(file_stream, [])

            section_utility = SectionUtility("jump")
            section_utility.write(file_stream, [])

            section_utility = SectionUtility("tcyc")
            section_utility.write(file_stream, [])

            section_utility = SectionUtility("auzo")
            section_utility.write(file_stream, [])

            section_utility = SectionUtility("mult")
            section_utility.write(file_stream, [])

    ########################################################################
    @staticmethod
    def write_text_ide_to_stream(file_stream, game_id, ide_data:TextIDEData):
        file_stream.write("# IDE generated with DemonFF\n")

        section_utility = SectionUtility("objs")
        section_utility.write(file_stream, ide_data.objs_instances)

        section_utility = SectionUtility("tobj")
        section_utility.write(file_stream, ide_data.tobj_instances)

        if game_id == map_data.game_version.III:
            pass

        elif game_id == map_data.game_version.VC:
            pass

        elif game_id == map_data.game_version.SA:
            section_utility = SectionUtility("anim")
            section_utility.write(file_stream, ide_data.anim_instances)

    ########################################################################
    @staticmethod
    def write_ipl_data(filename, game_id, ipl_data:TextIPLData):
        self = MapDataUtility

        with open(filename, 'w') as file_stream:
            self.write_text_ipl_to_stream(file_stream, game_id, ipl_data)

    ########################################################################
    @staticmethod
    def write_ide_data(filename, game_id, ide_data:TextIDEData):
        self = MapDataUtility

        with open(filename, 'w') as file_stream:
            self.write_text_ide_to_stream(file_stream, game_id, ide_data)

    ########################################################################
    @staticmethod
    def override_ide_paths(ide_paths):
        MapDataUtility.forced_ide_paths = list(ide_paths or [])

    ########################################################################
    @staticmethod
    def map_data_as_dict(map_data_object):
        return {
            'object_instances': map_data_object.object_instances,
            'object_data': map_data_object.object_data,
            'cull_instances': map_data_object.cull_instances,
            'grge_instances': map_data_object.grge_instances,
            'enex_instances': map_data_object.enex_instances,
            'effects_2dfx': map_data_object.effects_2dfx,
        }

    ########################################################################
    @staticmethod
    def getMapData(game_id, game_root, ipl_section, is_custom_ipl):
        map_data_object = MapDataUtility.load_map_data(
            game_id,
            game_root,
            ipl_section,
            is_custom_ipl
        )

        return MapDataUtility.map_data_as_dict(map_data_object)

    ########################################################################
    @staticmethod
    def getBinaryMapData(game_id, binary_ipl_path, ide_paths):
        data = map_data.data[game_id].copy()
        structures = data['structures']
        ide_aliases = data['IDE_aliases']

        object_instances = []

        with open(binary_ipl_path, 'rb') as file_stream:
            if MapDataUtility.is_binary_ipl_stream(file_stream):
                sections = MapDataUtility.read_binary_ipl_from_stream(
                    file_stream,
                    structures
                )
                object_instances.extend(sections.get('inst', []))
            else:
                file_stream.seek(0)
                raw = file_stream.read()

                for offset in range(0x4C, len(raw), 40):
                    chunk = raw[offset:offset + 40]
                    if len(chunk) < 40:
                        break

                    pos = struct.unpack('<3f', chunk[0x00:0x0C])
                    rot = struct.unpack('<4f', chunk[0x0C:0x1C])
                    model_id = struct.unpack('<H', chunk[0x1C:0x1E])[0]
                    interior_id = struct.unpack('<h', chunk[0x1E:0x20])[0]
                    lod_model_id = struct.unpack('<i', chunk[0x24:0x28])[0]

                    inst = structures['inst_binary'](
                        str(model_id),
                        '',
                        str(interior_id),
                        str(pos[0]), str(pos[1]), str(pos[2]),
                        str(rot[0]), str(rot[1]), str(rot[2]), str(rot[3]),
                        str(lod_model_id)
                    )

                    object_instances.append(inst)

        binary_dir = os.path.dirname(binary_ipl_path)
        ide_sections = {}
        for ide_path in ide_paths:
            if os.path.isabs(ide_path):
                fullpath = ide_path
            else:
                fullpath = MapDataUtility.find_path_case_insensitive(binary_dir, ide_path)
                if fullpath is None:
                    fullpath = os.path.join(binary_dir, ide_path)

            sections = MapDataUtility.read_file(
                fullpath,
                structures,
                ide_aliases
            )
            ide_sections = MapDataUtility.merge_dols(ide_sections, sections)

        object_data = MapDataUtility.build_object_data(ide_sections)

        for index, inst in enumerate(object_instances):
            model = MapDataUtility.resolve_object_data_entry(
                object_data,
                getattr(inst, 'id', ''),
                getattr(inst, 'modelName', '')
            )
            if model is not None and hasattr(inst, '_replace'):
                object_instances[index] = inst._replace(modelName=model.modelName)

        return {
            'object_instances': object_instances,
            'object_data': object_data,
            'cull_instances': [],
            'grge_instances': [],
            'enex_instances': [],
            'effects_2dfx': {},
        }

