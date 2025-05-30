# DemonFF - Blender scripts for working with Renderware & R*/SA-MP/open.mp formats in Blender
# 2023 - 2025 SpicyBung

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
from ..data import map_data
from collections import namedtuple
from bpy_extras.io_utils import ImportHelper
from ..ops.importer_common import game_version

Vector = namedtuple("Vector", "x y z")


#######################################################
# Base for all IPL / IDE section reader / writer classes
class GenericSectionUtility: 

    def __init__(self, sectionName, dataStructures):
        self.sectionName = sectionName
        self.dataStructures = dataStructures

    #######################################################
    def read(self, fileStream):

        entries = []

        line = fileStream.readline().strip()
        while line != "end":

            # Split line and trim individual elements
            lineParams = [e.strip() for e in line.split(",")]

            # Get the correct data structure for this section entry
            dataStructure = self.getDataStructure(lineParams)

            # Validate data structure
            if(dataStructure is None):
                print(type(self).__name__+
                      " error: No appropriate data structure found")
                print("    Section name: " + self.sectionName)
                print("    Line parameters: " + str(lineParams))
            elif(len(dataStructure._fields) != len(lineParams)):
                print(
                    type(self).__name__+" error: Number of line parameters "
                    "doesn't match the number of structure fields."
                )
                print("    Section name: " + self.sectionName)
                print("    Data structure name: " + dataStructure.__name__)
                print("    Data structure: " + str(dataStructure._fields))
                print("    Line parameters: " + str(lineParams))
            else:
                # Add entry
                entry = dataStructure(*lineParams)
                if hasattr(entry, "id"):
                    entry = entry._replace(id=int(entry.id.strip().lstrip('#')))
                entries.append(entry)


            # Read next line
            line = fileStream.readline().strip()

        return entries

    #######################################################
    def getDataStructure(self, lineParams):
        struct_map = self.dataStructures

        if self.sectionName == "inst":
            field_count = len(lineParams)

            if field_count == 11:
                return struct_map.get("inst_binary")   # Binary 
            elif field_count == 13:
                return struct_map.get("inst")   # GTA III
            elif field_count == 14:
                return struct_map.get("inst")   # Vice City
            elif field_count == 12:
                return struct_map.get("inst")   # SA 
            else:
                print("INST error: Unknown number of line parameters")
                return None

        return struct_map.get(self.sectionName)
    #######################################################
    def write(self):
        pass

#######################################################
class OBJSSectionUtility(GenericSectionUtility):
    def getDataStructure(self, lineParams):
        global entry


        print(f"[DEBUG] OBJS line ({len(lineParams)} fields): {lineParams}")
        if len(lineParams) == 5:
            return self.dataStructures["objs_1"]
        else:
            print("[ERROR] Unrecognized OBJS line:", lineParams)
  

        if(len(lineParams) == 5):
            dataStructure = self.dataStructures["objs_1"]
        elif(len(lineParams) == 6):
            dataStructure = self.dataStructures["objs_2"]
        elif(len(lineParams) == 7):
            dataStructure = self.dataStructures["objs_3"]
        elif(len(lineParams) == 8):
            dataStructure = self.dataStructures["objs_4"]
        else:
            print(type(self).__name__ + " error: Unknown number of line parameters")
            dataStructure = None

        if len(lineParams) == 5:
            dataStructure = self.dataStructures["objs_1"]
            entry = dataStructure(*lineParams)
            entry = entry._replace(id=int(entry.id.strip().lstrip('#')))

            return type(entry)
        else:
            return dataStructure

    
        

#######################################################
class TOBJSectionUtility(GenericSectionUtility):
    def getDataStructure(self, lineParams):

        if(len(lineParams) == 7):
            dataStructure = self.dataStructures["tobj_1"]
        elif(len(lineParams) == 8):
            dataStructure = self.dataStructures["tobj_2"]
        elif(len(lineParams) == 9):
            dataStructure = self.dataStructures["tobj_3"]
        elif(len(lineParams) == 10):
            dataStructure = self.dataStructures["tobj_4"]
        else:
            print(type(self).__name__ + " error: Unknown number of line parameters")
            dataStructure = None
        
        return dataStructure

#######################################################
class CARSSectionUtility(GenericSectionUtility):
    def getDataStructure(self, lineParams):
        # TODO:
        print("'cars' not yet implemented")

# List of IPL/IDE sections which require a section utility that's different
# from the default one.
specialSections = {
    'objs': OBJSSectionUtility,
    'tobj': TOBJSectionUtility,
    'cars': CARSSectionUtility
}

# Utility for reading / writing to map data files (.IPL, .IDE)
#######################################################
class MapDataUtility:

    forced_ide_paths = None

    #######################################################
    def override_ide_paths(paths):
        MapDataUtility.forced_ide_paths = paths
    #######################################################

    # Returns a dictionary of sections found in the given file
    #######################################################
    def readFile(filepath, filename, dataStructures):

        if os.path.isabs(filename):
            fullpath = os.path.normpath(filename)
        else:
            fullpath = os.path.normpath(os.path.join(filepath, filename))
        print('\nMapDataUtility reading: ' + fullpath)

        sections = {}

        try:
            fileStream = open(fullpath, 'r', encoding='latin-1')

        except FileNotFoundError:

            # If file doesn't exist, look for binary file inside gta3.img file (credit to Allerek)
            fullpath = "%s%s" % (filepath, 'models/gta3.img')
            with open(fullpath, 'rb') as img_file:
                # Read the first 8 bytes for the header and unpack
                header = img_file.read(8)
                magic, num_entries = struct.unpack('4sI', header)

                # Read and process directory entries
                entry_size = 32
                entries = []
                for i in range(num_entries):
                    entry_data = img_file.read(entry_size)
                    offset, streaming_size, _, name = struct.unpack('IHH24s', entry_data)
                    
                    try:
                        name = name.split(b'\x00', 1)[0].decode('utf-8')
                    except UnicodeDecodeError:
                        name = name.split(b'\x00', 1)[0].decode('latin-1', errors='ignore')

                    entries.append((offset, streaming_size, name))

                # Look for ipl file in gta3.img
                for offset, streaming_size, name in entries:
                    if name == filename:

                        # Read and unpack the header
                        img_file.seek(offset * 2048)
                        header = img_file.read(32)
                        _, num_of_instances, _, _, _, _, _, instances_offset = struct.unpack('4siiiiiii', header)

                        # Read and process instance definitions
                        item_size = 40
                        read_base = offset * 2048 + instances_offset
                        insts = []
                        current_offset = read_base
                        for i in range(num_of_instances):
                            img_file.seek(current_offset)
                            instances = img_file.read(40)

                            # Read binary instance
                            x_pos, y_pos, z_pos, x_rot, y_rot, z_rot, w_rot, obj_id, interior, lod = struct.unpack('fffffffiii', instances)

                            # Create value list (with values as strings) and map to the data struct
                            vals = [obj_id, "", interior, x_pos, y_pos, z_pos, x_rot, y_rot, z_rot, w_rot, lod]
                            insts.append(dataStructures['inst'](*[str(v) for v in vals]))

                            # Prepare for reading of next instance inside of .ipl
                            current_offset = read_base + i * item_size

                        sections["inst"] = insts

        else:
            with fileStream:
                line = fileStream.readline().strip()

                while line:

                    # Presume we have a section start
                    sectionName = line
                    sectionUtility = None

                    if line in specialSections:
                        # Section requires some special reading / writing procedures
                        sectionUtility = specialSections[sectionName](
                            sectionName, dataStructures
                        )
                    elif line in dataStructures:
                        # Section is generic,
                        # can be read / written to with the default utility
                        sectionUtility = GenericSectionUtility(
                            sectionName, dataStructures
                        )

                    if sectionUtility is not None:
                        sections[sectionName] = sectionUtility.read(fileStream)
                        print("%s: %d entries" % (
                            sectionName, len(sections[sectionName]
                            )
                        ))

                    # Get next section
                    line = fileStream.readline().strip()

        return sections

    ########################################################################
    def getMapData(gameID, gameRoot, iplSection, isCustomIPL):

        data = map_data.data[gameID].copy()

        if MapDataUtility.forced_ide_paths:
            data['IDE_paths'] = MapDataUtility.forced_ide_paths
            MapDataUtility.forced_ide_paths = None
        elif isCustomIPL:
            # fallback scan if no override
            ide_paths = []
            for root_path, _, files in os.walk(os.path.join(gameRoot, "DATA/MAPS")):
                for file in files:
                    if file.lower().endswith(".ide"):
                        full_path = os.path.join(root_path, file)
                        ide_paths.append(os.path.relpath(full_path, gameRoot))
            data['IDE_paths'] = ide_paths


        elif MapDataUtility.forced_ide_paths:
            data['IDE_paths'] = MapDataUtility.forced_ide_paths
            MapDataUtility.forced_ide_paths = None


        else:
            # Prune IDEs unrelated to current IPL section (SA only). First, make IDE_paths a mutable list, then iterate
            # over a copy so we can remove elements during iteration. This is a naive pruning which keeps all ides with a
            # few generic keywords in their name and culls anything else with a prefix different from the given iplSection
            if gameID == game_version.SA:
                data['IDE_paths'] = list(data['IDE_paths'])
                for p in data['IDE_paths'].copy():
                    if p.startswith('DATA/MAPS/generic/') or p.startswith('DATA/MAPS/leveldes/') or 'xref' in p:
                        continue
                    ide_prefix = p.split('/')[-1].lower()
                    ipl_prefix = iplSection.split('/')[-1].lower()[:3]
                    if not ide_prefix.startswith(ipl_prefix):
                        data['IDE_paths'].remove(p)

        ide = {}

        for file in data['IDE_paths']:
            sections = MapDataUtility.readFile(
                gameRoot, file,
                data['structures']
            )
            ide = MapDataUtility.merge_dols(ide, sections)

        ipl = {}

        sections = MapDataUtility.readFile(
            gameRoot, iplSection,
            data['structures']
        )
        ipl = MapDataUtility.merge_dols(ipl, sections)

        # Extract relevant sections
        object_instances = []
        object_data = {}

        # Get all insts into a flat list (array)
        # Can't be an ID keyed dictionary, because there's many ipl
        # entries with the same ID - multiple pieces of
        # the same model (lamps, benches, trees etc.)
        if 'inst' in ipl:
            for entry in ipl['inst']:
                object_instances.append(entry)
                
        # Get all objs and tobjs into flat ID keyed dictionaries
        if 'objs' in ide:
            for entry in ide['objs']:
                if entry.id in object_data:
                    print('OBJS ERROR!! a duplicate ID!!')
                object_data[entry.id] = entry

        if 'tobj' in ide:
            for entry in ide['tobj']:
                if entry.id in object_data:
                    print('TOBJ ERROR!! a duplicate ID!!')
                object_data[entry.id] = entry

        return {
            'object_instances': object_instances,
            'object_data': object_data
            }
    #######################################################
    @staticmethod
    def getBinaryMapData(gameID, binaryIPLPath, idePaths):
        data = map_data.data[gameID].copy()

        object_instances = []
        with open(binaryIPLPath, "rb") as f:
            raw = f.read()

        for i in range(0x4C, len(raw), 40):
            chunk = raw[i:i + 40]
            if len(chunk) < 40:
                break

            pos = struct.unpack("<3f", chunk[0x00:0x0C])
            rot = struct.unpack("<4f", chunk[0x0C:0x1C])
            model_id = struct.unpack("<H", chunk[0x1C:0x1E])[0]
            interior_id = struct.unpack("<h", chunk[0x1E:0x20])[0]
            lod_model_id = struct.unpack("<I", chunk[0x24:0x28])[0]

            model_name = "dummy"    # not stored in binary - used later via IDE match

            inst = data['structures']['inst_binary'](
                model_id, model_name, interior_id,
                pos[0], pos[1], pos[2],
                rot[0], rot[1], rot[2], rot[3],
                lod_model_id
            )

            object_instances.append(inst)


        # --- Load IDE files ---
        object_data = {}
        for path in idePaths:
            sections = MapDataUtility.readFile(
                os.path.dirname(binaryIPLPath) + os.sep, os.path.basename(path),
                data['structures']
            )



            if 'objs' in sections:
                for entry in sections['objs']:
                    if entry.id in object_data:
                        print(f'OBJS ERROR!! Duplicate ID: {entry.id}')
                    object_data[entry.id] = entry

            if 'tobj' in sections:
                for entry in sections['tobj']:
                    if entry.id in object_data:
                        print(f'TOBJ ERROR!! Duplicate ID: {entry.id}')
                    object_data[entry.id] = entry

            print(f"➡ Loaded {len(object_instances)} instances from binary IPL")
            print(f"➡ Loaded {len(object_data)} objects from IDEs")

        # Patch modelName on each inst (if possible) ---
        for i, inst in enumerate(object_instances):
            model = object_data.get(inst.id)
            if model:
                patched = inst._replace(modelName=model.modelName)
                object_instances[i] = patched

        return {
            'object_instances': object_instances,
            'object_data': object_data
        }


    #######################################################
    def merge_dols(dol1, dol2):
        result = dict(dol1, **dol2)
        result.update((k, dol1[k] + dol2[k])
                        for k in set(dol1).intersection(dol2))
        return result
