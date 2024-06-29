import os
import struct
import lzma

class img_importer:

    def __init__(self, img_file):
        self.img_file = img_file
        self.entries = []

    def read_dir(self, dir_file):
        with open(dir_file, 'rb') as f:
            while True:
                data = f.read(32)
                if not data:
                    break
                offset, size, name = struct.unpack('<II24s', data)
                name = name.decode('utf-8').rstrip('\0')
                self.entries.append((offset, size, name))

    def read_img(self):
        with open(self.img_file, 'rb') as f:
            for offset, size, name in self.entries:
                f.seek(offset * 2048)
                data = f.read(size * 2048)
                decompressed_data = self.decompress_data(data)
                with open(name, 'wb') as out_file:
                    out_file.write(decompressed_data)

    def decompress_data(self, data):
        try:
            decompressed_data = lzma.decompress(data)
            return decompressed_data
        except lzma.LZMAError:
            return data

    def import_img(self):
        dir_file = self.img_file.replace('.img', '.dir')
        if not os.path.exists(dir_file):
            raise FileNotFoundError(f"Directory file {dir_file} not found.")
        self.read_dir(dir_file)
        self.read_img()

# Usage
# importer = img_importer('path_to_img_file.img')
# importer.import_img()
