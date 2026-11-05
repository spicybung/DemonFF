# DemonFF - IMG import, including the unlisted Stories LVZ companion route.
# Existing DFF, COL and texture importers handle the entries themselves.
import os
import re
import tempfile
from pathlib import Path
from struct import pack

import bpy
from bpy.props import StringProperty
from bpy.types import Operator, Panel
from bpy_extras.io_utils import ImportHelper

from ..gtaLib.img import img, findCompanion, trimDffPadding
from ..gtaLib.binary import writeAtomic
from .dff_importer import import_dff


def sanitize_filename(filename):
    name = re.split(r'[/\\]', str(filename))[-1]
    return re.sub(r'[^\w\-. ]', '_', name).strip(' .') or 'resource'


class ImgImporter:
    def __init__(self, img_path):
        self.img_path = os.fspath(img_path)
        self.entries = []
        self.warnings = []
        self.imported_count = 0

    def read_directory(self):
        with img.open(self.img_path) as archive:
            self.entries = [{'offset': entry.offset, 'streaming_size': entry.size, 'name': entry.name}
                            for entry in archive.directory_entries]
        return self.entries

    def import_dff(self, dff_data, dff_name, directory=None):
        if directory is None:
            with tempfile.TemporaryDirectory(prefix='demonff-img-') as directory:
                return self.import_dff(dff_data, dff_name, directory)
        output = Path(directory) / sanitize_filename(dff_name)
        output.write_bytes(trimDffPadding(dff_data))
        txd_files = [path for path in Path(directory).iterdir()
                     if path.suffix.casefold() == '.txd' and path.stem.casefold() == output.stem.casefold()]
        importer = import_dff({
            'file_name': str(output), 'load_txd': True,
            'txd_filename': str(txd_files[0]) if txd_files else '',
            'skip_mipmaps': True, 'txd_pack': True, 'image_ext': 'PNG',
            'connect_bones': False, 'use_mat_split': True, 'remove_doubles': False,
            'group_materials': True, 'import_normals': True, 'materials_naming': 'TEX',
        })
        collection = getattr(importer, 'current_collection', None)
        if collection is not None:
            collection['demonff_source_archive'] = self.img_path
            collection['demonff_source_entry'] = dff_name
        return importer

    def extract_dff_files(self):
        from .col_importer import import_col_mem
        with img.open(self.img_path) as archive, tempfile.TemporaryDirectory(prefix='demonff-img-') as directory:
            # Matching TXDs are available before any DFF is imported.
            for index, entry in enumerate(archive.directory_entries):
                if entry.name.lower().endswith('.txd'):
                    name, data = archive.read_entry(index)
                    (Path(directory) / sanitize_filename(name)).write_bytes(data)
            for index, entry in enumerate(archive.directory_entries):
                extension = Path(entry.name).suffix.lower()
                if extension not in {'.dff', '.col'}:
                    continue
                name, data = archive.read_entry(index)
                try:
                    if extension == '.dff':
                        self.import_dff(data, name, directory)
                    else:
                        import_col_mem(data, Path(name).stem)
                    self.imported_count += 1
                except (ValueError, OSError, RuntimeError) as error:
                    self.warnings.append('%s: %s' % (name, error))
        if not self.imported_count:
            raise ValueError('No DFF or COL entries could be imported' + (': ' + self.warnings[0] if self.warnings else ''))

    def create_dir_file(self):
        # Explicit utility only: importing never writes beside the source archive.
        data = b''.join(pack('<II24s', entry['offset'], entry['streaming_size'],
                             entry['name'].encode('latin-1')) for entry in self.entries)
        writeAtomic(Path(self.img_path).with_suffix('.dir'), data)

    def buildLvzResource(self, reader, resource_id, address, end, collection):
        material_list = reader.parse_mdl_material_list(address, max_end=end)
        groups, stop = reader.parse_mdl_geometry_after_list(material_list, max_end=end)
        reader.assign_materials_by_strip_bytes(material_list, groups)
        obj, ranges = reader.buildMeshFromMdlGroups(resource_id, groups)
        if obj is None:
            return None
        for old_collection in list(obj.users_collection):
            old_collection.objects.unlink(obj)
        collection.objects.link(obj)
        slots = {}
        for material_info in material_list.materials:
            texture_id = material_info.texture_id
            material = reader.material_by_res_index.get(texture_id)
            if material is None:
                material = bpy.data.materials.new('Resource %d' % texture_id)
                material['demonff_texture_resource'] = texture_id
                reader.material_by_res_index[texture_id] = material
            if texture_id not in slots:
                slots[texture_id] = len(obj.data.materials)
                obj.data.materials.append(material)
        for first, count, texture_id in ranges:
            if texture_id in slots:
                for polygon in obj.data.polygons[first:first + count]:
                    polygon.material_index = slots[texture_id]
        obj['demonff_source_archive'] = self.img_path
        obj['demonff_resource_id'] = resource_id
        return obj

    def importLvzPair(self, lvz_path, img_path):
        from ..gtaLib import lvz_img as lvz
        raw, compressed = lvz.safe_decompress(Path(lvz_path).read_bytes())
        reader = lvz.read_lvz(raw, Path(lvz_path).stem, True, False)
        header = reader.parse_master_header()
        if header.magic == bytes(4):
            raise ValueError('The LVZ file has an empty header')
        groups, count, cursor = reader.parse_slave_groups_and_rescount()
        rows = reader.walk_master_resource_table(header.res_table_addr, count)
        img_reader = lvz.read_img(Path(img_path).read_bytes(), raw)
        reader.use_swizzle = img_reader.detect_platform_from_lvz_groups() == 'PS2'
        collection = bpy.data.collections.new(Path(lvz_path).stem)
        bpy.context.scene.collection.children.link(collection)
        collection['demonff_lvz_source'] = str(lvz_path)
        collection['demonff_img_source'] = str(img_path)
        reader.decode_textures(rows)
        models = {}
        for row in rows:
            if row['kind'] != 'MDL':
                continue
            try:
                obj = self.buildLvzResource(reader, row['index'], row['res_addr'],
                                            row.get('res_end', len(raw)), collection)
                if obj is not None:
                    models[row['index']] = obj
            except (ValueError, RuntimeError, IndexError) as error:
                self.warnings.append('LVZ resource %d: %s' % (row['index'], error))
        details = img_reader.enumerate_sector_details(max_resource_id=count, dedupe_visible=True)
        sector_models = {}
        overlay_reader = img_reader._img_mdl_parser
        overlay_reader.stem = Path(lvz_path).stem + '_IMG_'
        overlay_reader.material_by_res_index = reader.material_by_res_index
        for row in img_reader.collect_sector_overlay_resources(max_resource_id=count):
            key = (row['sector_index'], row['res_id'])
            if key in sector_models:
                continue
            try:
                obj = self.buildLvzResource(overlay_reader, row['res_id'], row['raw_off'],
                                            row.get('resource_end', row['sector_end']), collection)
                if obj is not None:
                    sector_models[key] = obj
            except (ValueError, RuntimeError, IndexError) as error:
                self.warnings.append('IMG resource %d: %s' % (row['res_id'], error))
        used = set()
        for detail in details:
            resource_id, sector = int(detail[0]), int(detail[15])
            obj = sector_models.get((sector, resource_id), models.get(resource_id))
            if obj is None:
                self.warnings.append('Unresolved resource %d in sector %d' % (resource_id, sector))
                continue
            placed = obj if obj not in used else obj.copy()
            if placed != obj:
                collection.objects.link(placed)
            used.add(obj)
            placed.matrix_world = lvz.matrix_from_16_floats_row_major_values_with_origin(detail[12], detail[18])
            placed['demonff_img_sector'] = sector
            placed['demonff_img_pass'] = str(detail[14])
            self.imported_count += 1
        for obj in set(models.values()) | set(sector_models.values()):
            if details and obj not in used:
                obj.hide_set(True)
                obj.hide_render = True
        if not details:
            self.imported_count = len(models) + len(sector_models)
        if not self.imported_count:
            raise ValueError('No supported LVZ/IMG geometry could be imported')
        return self.imported_count

    def importArchiveData(self):
        self.warnings = []
        self.imported_count = 0
        source = Path(self.img_path)
        if source.suffix.lower() == '.lvz':
            companion = findCompanion(source, '.img')
            if companion is None:
                raise ValueError('The matching IMG file is missing beside ' + source.name)
            return self.importLvzPair(source, companion)
        with source.open('rb') as stream:
            magic = stream.read(4)
        companion = findCompanion(source, '.lvz')
        if companion is not None:
            return self.importLvzPair(companion, source)
        self.read_directory()
        self.extract_dff_files()
        return self.imported_count

    def import_img(self):
        groups = (bpy.data.objects, bpy.data.collections, bpy.data.meshes,
                  bpy.data.armatures, bpy.data.materials, bpy.data.images)
        snapshots = [set(group) for group in groups]
        try:
            return self.importArchiveData()
        except Exception:
            for group, snapshot in zip(groups, snapshots):
                for item in list(group):
                    if item not in snapshot:
                        if group == bpy.data.objects:
                            group.remove(item, do_unlink=True)
                        elif group == bpy.data.collections or item.users == 0:
                            group.remove(item)
            raise


class IMPORT_OT_img(Operator, ImportHelper):
    bl_idname = 'import_scene.img'
    bl_label = 'Import IMG(.img)'
    bl_description = 'Import models and collisions from an IMG archive'
    filename_ext = '.img'
    filter_glob: StringProperty(default='*.img', options={'HIDDEN'}, maxlen=255)

    def execute(self, context):
        if context.mode != 'OBJECT':
            self.report({'ERROR'}, 'Switch to Object Mode before importing an IMG')
            return {'CANCELLED'}
        importer = ImgImporter(bpy.path.abspath(self.filepath))
        try:
            count = importer.import_img()
        except (OSError, ValueError, RuntimeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        if importer.warnings:
            for warning in importer.warnings:
                print('DemonFF IMG:', warning)
            self.report({'WARNING'}, '%d entries or placements need attention; see the console' % len(importer.warnings))
        self.report({'INFO'}, 'Imported %d model/collision entries or placements' % count)
        return {'FINISHED'}


class IMPORT_PT_img_panel(Panel):
    bl_idname = 'IMPORT_PT_img_panel'
    bl_label = 'DemonFF - IMG Import'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'
    bl_category = 'DemonFF'

    def draw(self, context):
        self.layout.operator('import_scene.img', text='Import IMG(.img)')


def menu_func_import(self, context):
    self.layout.operator(IMPORT_OT_img.bl_idname, text='Import IMG(.img)')


def register():
    bpy.utils.register_class(IMPORT_OT_img)
    bpy.utils.register_class(IMPORT_PT_img_panel)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(IMPORT_PT_img_panel)
    bpy.utils.unregister_class(IMPORT_OT_img)
