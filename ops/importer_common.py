import bpy
from collections import namedtuple

game_version = namedtuple("game_version", "III VC SA LCS VCS IV")
game_version.III = 'III'
game_version.VC = 'VC'
game_version.SA = 'SA'
game_version.LCS = 'LCS'
game_version.VCS = 'VCS'
game_version.IV = 'IV'

#######################################################            
def set_object_mode(obj, mode):
        
    # Blender 2.79 compatibility
    if (2, 80, 0) > bpy.app.version:
        bpy.context.scene.objects.active = obj
    else:
        bpy.context.view_layer.objects.active = obj
        
    bpy.ops.object.mode_set(mode=mode, toggle=False)

#######################################################
def link_object(obj, collection):
    collection.objects.link(obj)
    if (2, 80, 0) > bpy.app.version:
        bpy.context.scene.objects.link(obj)
        
#######################################################        
def create_collection(name, link=True):
    if (2, 80, 0) > bpy.app.version:
        return bpy.data.groups.new(name)
    else:
        collection = bpy.data.collections.new(name)
        if link:
            bpy.context.scene.collection.children.link(collection)
            
        return collection        
        
#######################################################
def hide_object(object, hide=True):
    if (2, 80, 0) > bpy.app.version:
        object.hide = hide
    else:
        object.hide_set(hide)


#######################################################
class material_helper:

    """ Material Helper for Blender 2.7x and Blender 2.8 compatibility"""

    #######################################################
    def set_base_color(self, color):

        if self.principled:
            self.principled.base_color = [i / 255 for i in color[:3]]

            # Set Alpha
            node = self.principled.node_principled_bsdf.inputs["Base Color"]
            node.default_value[3] = color[3] / 255
            
        else:
            self.material.diffuse_color = [i / 255 for i in color[:3]]
            self.material.alpha = color[3] / 255

    #######################################################
    def set_texture(self, image, label="", filters=0, uv_addressing=0):

        if self.principled:
            self.principled.base_color_texture.node_image.label = label
            self.principled.base_color_texture.image  = image


            # Connect Alpha output to Principled BSDF
            image_node      = self.principled.base_color_texture.node_image
            principled_node = self.principled.node_principled_bsdf
            node_tree       = self.principled.material.node_tree

            node_tree.links.new(image_node.outputs["Alpha"],
                                principled_node.inputs["Alpha"])

        else:
            slot               = self.material.texture_slots.add()
            slot.texture       = bpy.data.textures.new(
                name           = label,
                type           = "IMAGE"
            )
            slot.texture.image = image

        self.material.dff.tex_filters = str(filters)
        self.material.dff.tex_u_addr  = str((uv_addressing >> 4) & 0xF)
        self.material.dff.tex_v_addr  = str(uv_addressing & 0xF)

    #######################################################
    def set_surface_properties(self, props):

        if self.principled:
            self.principled.specular       = props.specular
            self.principled.roughness      = props.diffuse
            self.material.dff.ambient = props.ambient
            
        else:
            self.material.diffuse_intensity  = props.diffuse
            self.material.specular_intensity = props.specular
            self.material.ambient            = props.ambient

    #######################################################
    def set_normal_map(self, image, label, intensity):

        if self.principled:
            self.principled.node_normalmap_get()
            
            self.principled.normalmap_texture.image = image
            self.principled.node_normalmap.label    = label
            self.principled.normalmap_strength      = intensity

        else:
            slot = self.material.texture_slots.add()
            slot.texture = bpy.data.textures.new(
                name = label,
                type = "IMAGE"
            )
            
            slot.texture.image = image
            slot.texture.use_normal_map = True
            slot.use_map_color_diffuse  = False
            slot.use_map_normal         = True
            slot.normal_factor          = intensity
        pass

    #######################################################
    def set_environment_map(self, plugin):

        if plugin.env_map:
            self.material.dff.env_map_tex      = plugin.env_map.name

        self.material.dff.export_env_map       = True
        self.material.dff.env_map_coef         = plugin.coefficient
        self.material.dff.env_map_fb_alpha     = plugin.use_fb_alpha        

    #######################################################
    def set_specular_material(self, plugin):
        
        self.material.dff.export_specular = True
        self.material.dff.specular_level = plugin.level
        self.material.dff.specular_texture = plugin.texture.decode('ascii')

    #######################################################
    def set_reflection_material(self, plugin):

        self.material.dff.export_reflection = True

        self.material.dff.reflection_scale_x = plugin.s_x
        self.material.dff.reflection_scale_y = plugin.s_y

        self.material.dff.reflection_offset_y = plugin.o_y
        self.material.dff.reflection_offset_x = plugin.o_x

        self.material.dff.reflection_intensity = plugin.intensity
        
    #######################################################
    def set_uv_animation(self, uv_anim):

        if self.principled:
            mapping = self.principled.base_color_texture.node_mapping_get()
            mapping.vector_type = 'POINT'

            fps = bpy.context.scene.render.fps

            action = bpy.data.actions.new(uv_anim.name)
            anim_data = self.material.node_tree.animation_data_create()
            anim_data.action = action

            fcurves = [
                None,
                action.fcurves.new(data_path='nodes["Mapping"].inputs[3].default_value', index=0),
                action.fcurves.new(data_path='nodes["Mapping"].inputs[3].default_value', index=1),
                None,
                action.fcurves.new(data_path='nodes["Mapping"].inputs[1].default_value', index=0),
                action.fcurves.new(data_path='nodes["Mapping"].inputs[1].default_value', index=1),
            ]

            for frame_idx, frame in enumerate(uv_anim.frames):
                for fc_idx, fc in enumerate(fcurves):
                    if not fc:
                        continue

                    should_add_kp = True

                    # Try to add constant interpolation
                    if frame_idx > 0 and frame.time == uv_anim.frames[frame_idx-1].time:

                        # We can overwrite the very first one keyframe
                        if len(fc.keyframe_points) < 2:
                            should_add_kp = False

                        else:
                            prev_kp, kp = fc.keyframe_points[-2:]

                            # We can overwrite the previous keyframe with constant interpolation
                            if prev_kp.interpolation == 'CONSTANT':
                                should_add_kp = False

                            # The values ​​of the previous keyframes are equal,
                            # so we can use constant interpolation and overwrite the last one
                            elif prev_kp.co[1] == kp.co[1]:
                                should_add_kp = False
                                prev_kp.interpolation = 'CONSTANT'

                    if should_add_kp:
                        fc.keyframe_points.add(1)

                    kp = fc.keyframe_points[-1]
                    val = frame.uv[fc_idx]

                    # Y coords are flipped in Blender
                    if fc_idx == 5:
                        val = 1 - val

                    # Could also use round here perhaps. I don't know what's better
                    kp.co = frame.time * fps, val
                    kp.interpolation = 'LINEAR'

        self.material.dff.animation_name   = uv_anim.name
        self.material.dff.export_animation = True

    #######################################################
    def set_user_data(self, user_data):
        self.material['dff_user_data'] = user_data.to_mem()[12:]
        
    #######################################################
    def __init__(self, material):
        self.material   = material
        self.principled = None

        # Init Principled Wrapper for Blender 2.8
        if bpy.app.version >= (2, 80, 0):
            from bpy_extras.node_shader_utils import PrincipledBSDFWrapper
            
            self.principled = PrincipledBSDFWrapper(self.material,
                                                    is_readonly=False)

#######################################################
class object_helper:

    #######################################################
    def __init__(self, name):

        """
        An object helper for importing different types of objects
        """
        
        self.name = name
        self.mesh = None
        self.object = None

    #######################################################
    def get_object(self):
        pass
    
    pass