# DemonFF - Blender scripts to edit basic GTA formats to work in conjunction with SAMP/open.mp
# 2023 - 2025 SpicyBung

# This is a fork of DragonFF by Parik - maintained by Psycrow, and various others!
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

import bpy
import struct
from dataclasses import dataclass
from mathutils import Matrix, Vector, Quaternion
from os import SEEK_CUR

#######################################################
bl_info = {
    "name": "GTA IFP Import/Export",
    "blender": (3, 0, 0),
    "category": "Import-Export",
}
#######################################################
POSEDATA_PREFIX = 'pose.bones["%s"].'

def invalid_active_object(self, context):
    self.layout.label(text='You need to select the armature to import animation')

def set_keyframe(curves, frame, values):
    for i, c in enumerate(curves):
        c.keyframe_points.add(1)
        c.keyframe_points[-1].co = frame, values[i]
        c.keyframe_points[-1].interpolation = 'LINEAR'

def find_bone_by_id(arm_obj, bone_id):
    for bone in arm_obj.data.bones:
        if bone.get('bone_id') == bone_id:
            return bone

def create_action(arm_obj, anim, fps, global_matrix):
    act = bpy.data.actions.new(anim.name)
    missing_bones = set()

    for b in anim.bones:
        bone = find_bone_by_id(arm_obj, b.bone_id) if b.bone_id != 0 else None
        if not bone:
            bone = arm_obj.data.bones.get(b.name)

        if bone:
            g = act.groups.new(name=b.name)
            bone_name = bone.name
            pose_bone = arm_obj.pose.bones[bone_name]
            pose_bone.rotation_mode = 'QUATERNION'
            pose_bone.location = (0, 0, 0)
            pose_bone.rotation_quaternion = (1, 0, 0, 0)
            pose_bone.scale = (1, 1, 1)
            loc_mat = bone.matrix_local.copy()
            if bone.parent:
                loc_mat = bone.parent.matrix_local.inverted_safe() @ loc_mat
            else:
                loc_mat = global_matrix @ loc_mat
        else:
            g = act.groups.new(name='%s %d' % (b.name, b.bone_id))
            bone_name = b.name
            loc_mat = Matrix.Identity(4)
            missing_bones.add(bone_name)

        cr = [act.fcurves.new(data_path=(POSEDATA_PREFIX % bone_name) + 'rotation_quaternion', index=i) for i in range(4)]
        for c in cr:
            c.group = g

        if b.keyframe_type[2] == 'T':
            cl = [act.fcurves.new(data_path=(POSEDATA_PREFIX % bone_name) + 'location', index=i) for i in range(3)]
            for c in cl:
                c.group = g

        if b.keyframe_type[3] == 'S':
            cs = [act.fcurves.new(data_path=(POSEDATA_PREFIX % bone_name) + 'scale', index=i) for i in range(3)]
            for c in cs:
                c.group = g

        loc_pos = loc_mat.to_translation()
        loc_rot = loc_mat.to_quaternion()
        loc_scl = loc_mat.to_scale()

        prev_rot = None

        for kf in b.keyframes:
            time = kf.time * fps

            if b.keyframe_type[2] == 'T':
                set_keyframe(cl, time, kf.pos - loc_pos)
            if b.keyframe_type[3] == 'S':
                set_keyframe(cs, time, Vector((1, 1, 1)) + kf.scl - loc_scl)

            rot = loc_rot.rotation_difference(kf.rot)

            if prev_rot:
                alt_rot = rot.copy()
                alt_rot.negate()
                if rot.rotation_difference(prev_rot).angle > alt_rot.rotation_difference(prev_rot).angle:
                    rot = alt_rot
            prev_rot = rot

            set_keyframe(cr, time, rot)

    return act, missing_bones

def load_ifp(filepath):
    with open(filepath, 'rb') as fd:
        version = read_str(fd, 4)

        anim_cls = ANIM_CLASSES.get(version)
        if not anim_cls:
            raise ValueError('Unsupported IFP file format')

        data = anim_cls.read(fd)
        return Ifp(version, data)

def apply_ifp_to_armature(context, ifp, fps, global_matrix):
    arm_obj = context.view_layer.objects.active
    if not arm_obj or type(arm_obj.data) != bpy.types.Armature:
        context.window_manager.popup_menu(invalid_active_object, title='Error', icon='ERROR')
        return {'CANCELLED'}

    animation_data = arm_obj.animation_data
    if not animation_data:
        animation_data = arm_obj.animation_data_create()

    if ifp.version == 'ANP3':
        fps = 1.0

    missing_bones = set()
    for anim in ifp.data.animations:
        act, mb = create_action(arm_obj, anim, fps, global_matrix)
        act.name = anim.name
        animation_data.action = act
        missing_bones = missing_bones.union(mb)

    if missing_bones:
        bpy.ops.message.missing_bones('INVOKE_DEFAULT', message='\n'.join(missing_bones))

    return {'FINISHED'}

#######################################################
class IMPORT_OT_ifp(bpy.types.Operator):
    bl_idname = "import_scene.ifp"
    bl_label = "Import IFP"
    filename_ext = ".ifp"
    filter_glob: bpy.props.StringProperty(
        default="*.ifp",
        options={'HIDDEN'},
    )
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    is_sa: bpy.props.BoolProperty(name="San Andreas", default=True)

    def execute(self, context):
        try:
            ifp = load_ifp(self.filepath)
            result = apply_ifp_to_armature(context, ifp, 30, Matrix.Identity(4))
            return result
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

def menu_func_import(self, context):
    self.layout.operator(IMPORT_OT_ifp.bl_idname, text="DemonFF IFP(.ifp)")

def register():
    bpy.utils.register_class(IMPORT_OT_ifp)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(IMPORT_OT_ifp)

if __name__ == "__main__":
    register()

#######################################################
# Additional IFP reading and writing logic
@dataclass
class Keyframe:
    time: float
    pos: Vector
    rot: Quaternion
    scl: Vector
#######################################################
@dataclass
class Bone:
    name: str
    keyframe_type: str
    use_bone_id: bool
    bone_id: int
    sibling_x: int
    sibling_y: int
    keyframes: []
#######################################################
@dataclass
class Animation:
    name: str
    bones: []
#######################################################
@dataclass
class IfpData:
    name: str
    animations: []
#######################################################
class Anp3Bone(Bone):
    def get_keyframes_size(self):
        s = 16 if self.keyframe_type[2] == 'T' else 10
        return len(self.keyframes) * s

    def get_size(self):
        return 36 + self.get_keyframes_size()

    @classmethod
    def read(cls, fd):
        name = read_str(fd, 24)
        keyframe_type, keyframes_num, bone_id = read_uint32(fd, 3)
        keyframe_type = 'KRT0' if keyframe_type == 4 else 'KR00'

        keyframes = []
        for _ in range(keyframes_num):
            qx, qy, qz, qw, time = read_int16(fd, 5)
            px, py, pz = read_int16(fd, 3) if keyframe_type[2] == 'T' else (0, 0, 0)
            kf = Keyframe(
                time,
                Vector((px / 1024.0, py / 1024.0, pz / 1024.0)),
                Quaternion((qw / 4096.0, qx / 4096.0, qy / 4096.0, qz / 4096.0)),
                Vector((1, 1, 1))
            )
            keyframes.append(kf)

        return cls(name, keyframe_type, True, bone_id, 0, 0, keyframes)
#######################################################
class Anp3Animation(Animation):
    @staticmethod
    def get_bone_class():
        return Anp3Bone

    def get_size(self):
        return 36 + sum(b.get_size() for b in self.bones)

    @classmethod
    def read(cls, fd):
        name = read_str(fd, 24)
        bones_num, keyframes_size, unk = read_uint32(fd, 3)
        bones = [Anp3Bone.read(fd) for _ in range(bones_num)]
        return cls(name, bones)
#######################################################
class Anp3(IfpData):
    @staticmethod
    def get_animation_class():
        return Anp3Animation

    @classmethod
    def read(cls, fd):
        size = read_uint32(fd)
        name = read_str(fd, 24)
        animations_num = read_uint32(fd)
        animations = [cls.get_animation_class().read(fd) for _ in range(animations_num)]
        return cls(name, animations)
#######################################################
class AnpkBone(Bone):
    def get_keyframes_size(self):
        s = 20
        if self.keyframe_type[2] == 'T':
            s += 12
        if self.keyframe_type[3] == 'S':
            s += 12
        return len(self.keyframes) * s

    def get_size(self):
        if self.use_bone_id:
            anim_len = 44
        else:
            anim_len = 48
        return self.get_keyframes_size() + anim_len + 24

    @classmethod
    def read(cls, fd):
        fd.seek(4, SEEK_CUR)  # CPAN
        bone_len = read_uint32(fd)
        fd.seek(4, SEEK_CUR)  # ANIM
        anim_len = read_uint32(fd)
        name = read_str(fd, 28)
        keyframes_num = read_uint32(fd)
        fd.seek(8, SEEK_CUR)  # unk

        if anim_len == 44:
            bone_id = read_uint32(fd)
            sibling_x, sibling_y = 0, 0
            use_bone_id = True
        else:
            bone_id = 0
            sibling_x, sibling_y = read_int32(fd, 2)
            use_bone_id = False

        if keyframes_num:
            keyframe_type = read_str(fd, 4)
            keyframes_len = read_uint32(fd)

            keyframes = []
            for _ in range(keyframes_num):
                qx, qy, qz, qw = read_float32(fd, 4)
                px, py, pz = read_float32(fd, 3) if keyframe_type[2] == 'T' else (0, 0, 0)
                sx, sy, sz = read_float32(fd, 3) if keyframe_type[3] == 'S' else (1, 1, 1)
                time = read_float32(fd)

                rot = Quaternion((qw, qx, qy, qz))
                rot.conjugate()

                kf = Keyframe(
                    time,
                    Vector((px, py, pz)),
                    rot,
                    Vector((sx, sy, sz)),
                )
                keyframes.append(kf)
        else:
            keyframe_type = 'K000'
            keyframes = []

        return cls(name, keyframe_type, use_bone_id, bone_id, sibling_x, sibling_y, keyframes)
    
#######################################################
class AnpkAnimation(Animation):
    @staticmethod
    def get_bone_class():
        return AnpkBone

    def get_size(self):
        name_len = len(self.name) + 1
        name_align_len = (4 - name_len % 4) % 4
        return 32 + name_len + name_align_len + sum(b.get_size() for b in self.bones)

    @classmethod
    def read(cls, fd):
        fd.seek(4, SEEK_CUR)  # NAME
        name_len = read_uint32(fd)
        name = read_str(fd, name_len)
        fd.seek((4 - name_len % 4) % 4, SEEK_CUR)
        fd.seek(4, SEEK_CUR)  # DGAN
        animation_size = read_uint32(fd)
        fd.seek(4, SEEK_CUR)  # INFO
        unk_size, bones_num = read_uint32(fd, 2)
        fd.seek(unk_size - 4, SEEK_CUR)
        bones = [AnpkBone.read(fd) for _ in range(bones_num)]
        return cls(name, bones)
    
#######################################################
class Anpk(IfpData):
    @staticmethod
    def get_animation_class():
        return AnpkAnimation

    @classmethod
    def read(cls, fd):
        size = read_uint32(fd)
        fd.seek(4, SEEK_CUR)  # INFO
        info_len, animations_num = read_uint32(fd, 2)
        name = read_str(fd, info_len - 4)
        fd.seek((4 - info_len % 4) % 4, SEEK_CUR)

        animations = [cls.get_animation_class().read(fd) for _ in range(animations_num)]
        return cls(name, animations)

ANIM_CLASSES = {
    'ANP3': Anp3,
    'ANPK': Anpk,
}

#######################################################
@dataclass
class Ifp:
    version: str
    data: object

    @classmethod
    def read(cls, fd):
        version = read_str(fd, 4)

        anim_cls = ANIM_CLASSES.get(version)
        if not anim_cls:
            raise Exception('Unknown IFP version')

        data = anim_cls.read(fd)
        return cls(version, data)

    def write(self, fd):
        write_str(fd, self.version, 4)
        self.data.write(fd)
        fd.write(b'\x00' * (2048 - (fd.tell() % 2048)))

    @classmethod
    def load(cls, filepath):
        with open(filepath, 'rb') as fd:
            return cls.read(fd)

    def save(self, filepath):
        with open(filepath, 'wb') as fd:
            return self.write(fd)

# Helper functions for reading and writing data
def read_int16(fd, num=1, en='<'):
    res = struct.unpack('%s%dh' % (en, num), fd.read(2 * num))
    return res if num > 1 else res[0]

def read_int32(fd, num=1, en='<'):
    res = struct.unpack('%s%di' % (en, num), fd.read(4 * num))
    return res if num > 1 else res[0]

def read_uint32(fd, num=1, en='<'):
    res = struct.unpack('%s%dI' % (en, num), fd.read(4 * num))
    return res if num > 1 else res[0]

def read_float32(fd, num=1, en='<'):
    res = struct.unpack('%s%df' % (en, num), fd.read(4 * num))
    return res if num > 1 else res[0]

def read_str(fd, max_len):
    n, res = 0, ''
    while n < max_len:
        b = fd.read(1)
        n += 1
        if b == b'\x00':
            break
        res += b.decode()

    fd.seek(max_len - n, SEEK_CUR)
    return res

def write_val(fd, vals, t, en='<'):
    data = vals if hasattr(vals, '__len__') else (vals, )
    data = struct.pack('%s%d%s' % (en, len(data), t), *data)
    fd.write(data)

def write_uint16(fd, vals, en='<'):
    write_val(fd, vals, 'h', en)

def write_int32(fd, vals, en='<'):
    write_val(fd, vals, 'i', en)

def write_uint32(fd, vals, en='<'):
    write_val(fd, vals, 'I', en)

def write_float32(fd, vals, en='<'):
    write_val(fd, vals, 'f', en)

def write_str(fd, val, max_len):
    fd.write(val.encode())
    fd.write(b'\x00' * (max_len - len(val)))

def export_anp3(ifp_data, fd):
    # Header
    fd.write(b'ANP3')
    offset_placeholder = fd.tell()
    fd.write(struct.pack('<I', 0))  # Offset placeholder

    internal_name = ifp_data.name.encode().ljust(24, b'\x00')
    fd.write(internal_name)
    fd.write(struct.pack('<I', len(ifp_data.animations)))

    for anim in ifp_data.animations:
        anim_name = anim.name.encode().ljust(24, b'\x00')
        fd.write(anim_name)
        fd.write(struct.pack('<I', len(anim.bones)))

        frame_data_size_pos = fd.tell()
        fd.write(struct.pack('<I', 0))  # Placeholder frame size
        fd.write(struct.pack('<I', 1))  # Unknown (always 1)

        frame_start = fd.tell()

        for bone in anim.bones:
            bone_name = bone.name.encode().ljust(24, b'\x00')
            frame_type = 4 if bone.use_bone_id else 3
            fd.write(bone_name)
            fd.write(struct.pack('<III', frame_type, len(bone.keyframes), bone.bone_id))

            for frame in bone.keyframes:
                quat = (frame.rot.x, frame.rot.y, frame.rot.z, frame.rot.w)
                time = int(frame.time * 1024)

                fd.write(struct.pack('<hhhhH',
                    int(quat[0]*4096), int(quat[1]*4096), int(quat[2]*4096), int(quat[3]*4096),
                    time
                ))

                if frame_type == 4:
                    fd.write(struct.pack('<hhh',
                        int(frame.pos.x*1024), int(frame.pos.y*1024), int(frame.pos.z*1024)
                    ))

        # Fixing frame_data size
        frame_end = fd.tell()
        frame_data_size = frame_end - frame_start
        current_pos = fd.tell()
        fd.seek(frame_data_size_pos)
        fd.write(struct.pack('<I', frame_data_size))
        fd.seek(current_pos)

    # EOF offset
    eof_offset = fd.tell()
    fd.seek(offset_placeholder)
    fd.write(struct.pack('<I', eof_offset))

def collect_animation_data(context):
    arm_obj = context.object
    action = arm_obj.animation_data.action
    animations = []

    anim = Animation(name=action.name, bones=[])

    for pose_bone in arm_obj.pose.bones:
        bone = Bone(
            name=pose_bone.name,
            keyframe_type='KRT0',
            use_bone_id=False,
            bone_id=0,
            sibling_x=0,
            sibling_y=0,
            keyframes=[]
        )

        frames = sorted({kp.co[0] for fc in action.fcurves for kp in fc.keyframe_points})
        for frame_num in frames:
            context.scene.frame_set(int(frame_num))
            quat = pose_bone.rotation_quaternion
            loc = pose_bone.location
            scale = pose_bone.scale
            time = frame_num / context.scene.render.fps

            kf = Keyframe(time=time, pos=loc.copy(), rot=quat.copy(), scl=scale.copy())
            bone.keyframes.append(kf)

        anim.bones.append(bone)

    animations.append(anim)
    return IfpData(name="BlenderIFP", animations=animations)

#######################################################
class EXPORT_OT_ifp(bpy.types.Operator):
    bl_idname = "export_scene.ifp"
    bl_label = "Export IFP (.ifp)"
    filename_ext = ".ifp"
    filter_glob: bpy.props.StringProperty(default="*.ifp", options={'HIDDEN'})
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        try:
            ifp_data = collect_animation_data(context)
            with open(self.filepath, 'wb') as fd:
                export_anp3(ifp_data, fd)
            self.report({'INFO'}, f"IFP file exported: {self.filepath}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

def export_menu_func(self, context):
    self.layout.operator(EXPORT_OT_ifp.bl_idname, text="DemonFF Export IFP (.ifp)")


