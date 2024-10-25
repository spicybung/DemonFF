import bpy
import os
from ..gtaLib import txd

class TextureImporter:
    """
    The TextureImporter handles the loading and importing of TXD textures into Blender.
    """

    def __init__(self, skip_mipmaps=True):
        """
        Initializes the TextureImporter.

        :param skip_mipmaps: Boolean to determine whether to import mipmaps.
        """
        self.txd = None  # TXD file data
        self.images = {}  # Dictionary to store the imported textures
        self.file_name = ""  # Path to the TXD file
        self.skip_mipmaps = skip_mipmaps  # Option to skip mipmap import

    def _create_image(self, name, rgba_data, width, height):
        """
        Creates and returns a new Blender image using provided RGBA data.

        :param name: The image name to create.
        :param rgba_data: The RGBA pixel data.
        :param width: The width of the image.
        :param height: The height of the image.
        :return: Created image in Blender.
        """
        pixels = []
        # Convert RGBA data for Blender's bottom-to-top row format
        for h in range(height - 1, -1, -1):
            offset = h * width * 4
            pixels += [b / 255.0 for b in rgba_data[offset:offset + width * 4]]

        # Create a new image in Blender
        image = bpy.data.images.new(name, width, height)
        image.pixels = pixels
        return image

    def _get_unique_image_name(self, image_name):
        """
        Ensures that the image name is unique by adding a suffix if needed.

        :param image_name: The original image name.
        :return: A unique image name.
        """
        suffix = 1
        unique_name = image_name
        while bpy.data.images.get(unique_name):
            unique_name = f"{image_name}_{suffix}"
            suffix += 1
        return unique_name

    def _load_textures(self):
        """
        Loads textures from the TXD file into Blender as images.
        """
        txd_name = os.path.basename(self.file_name)

        # Handle native textures in TXD
        for texture in self.txd.native_textures:
            image_list = []
            mip_levels = texture.num_levels if not self.skip_mipmaps else 1

            for level in range(mip_levels):
                image_name = f"{txd_name}/{texture.name}/{level}"
                # Ensure unique image names if needed
                image_name = self._get_unique_image_name(image_name)

                # Retrieve existing image or create a new one
                image = bpy.data.images.get(image_name) or self._create_image(
                    image_name,
                    texture.to_rgba(level),
                    texture.get_width(level),
                    texture.get_height(level)
                )

                # Append the image to the list
                image_list.append(image)

            # Store the final image list for this texture
            self.images[texture.name] = image_list

        # Handle standard textures in TXD
        for texture, images in zip(self.txd.textures, self.txd.images):
            image_list = []
            mip_levels = len(images) if not self.skip_mipmaps else 1

            for level in range(mip_levels):
                img_data = images[level]
                image_name = f"{txd_name}/{texture.name}/{level}"
                # Ensure unique image names if needed
                image_name = self._get_unique_image_name(image_name)

                # Create the image if not found
                image = bpy.data.images.get(image_name) or self._create_image(
                    image_name, img_data.to_rgba(), img_data.width, img_data.height
                )

                # Append the image to the list
                image_list.append(image)

            # Store the final image list for this texture
            self.images[texture.name] = image_list

    def load_txd(self, file_name):
        """
        Loads the TXD file and imports its textures into Blender.

        :param file_name: Path to the TXD file to be loaded.
        """
        try:
            self.txd = txd.txd()  # Create a TXD object
            self.txd.load_file(file_name)  # Load the TXD data
            self.file_name = file_name  # Store file name
            self._load_textures()  # Load textures into Blender
            print(f"Successfully imported textures from TXD file: {file_name}")
        except Exception as error:
            print(f"Failed to load TXD file '{file_name}': {error}")

def import_texture(options):
    """
    A function to import TXD files into Blender based on given options.

    :param options: Dictionary with the following keys:
                    - 'file_name' (str): Path to the TXD file.
                    - 'skip_mipmaps' (bool): Skip mipmap levels if True.
    :return: An instance of TextureImporter.
    """
    # Initialize TextureImporter with the mipmap option
    importer = TextureImporter(skip_mipmaps=options.get('skip_mipmaps', True))
    
    # Load and import textures from the TXD file
    importer.load_txd(options['file_name'])
    
    return importer
