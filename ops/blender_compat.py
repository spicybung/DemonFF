"""Shared Blender API differences, kept out of the format readers."""
import bpy


def actionChannelBag(action, owner=None, create=False):
    if owner is None:
        candidate = getattr(bpy.context, 'object', None)
        animation = getattr(candidate, 'animation_data', None)
        if animation is not None and animation.action == action:
            owner = candidate
    animation = getattr(owner, 'animation_data', None)
    slot = getattr(animation, 'action_slot', None) if animation is not None and animation.action == action else None
    slots = list(action.slots)
    if slot is None:
        if len(slots) == 1:
            slot = slots[0]
        elif len(slots) > 1:
            raise ValueError('Choose the object whose action slot should be used')
        elif create:
            slot = action.slots.new(id_type=getattr(owner, 'id_type', 'OBJECT'),
                                    name=getattr(owner, 'name', 'DemonFF'))
        else:
            return None
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in getattr(strip, 'channelbags', ()):
                if channelbag.slot_handle == slot.handle:
                    return channelbag
    if not create:
        return None
    layer = action.layers[0] if len(action.layers) else action.layers.new('DemonFF')
    strip = next((strip for strip in layer.strips if strip.type == 'KEYFRAME'), None)
    if strip is None:
        strip = layer.strips.new(type='KEYFRAME')
    bag = strip.channelbags.new(slot)
    if animation is not None and animation.action == action:
        animation.action_slot = slot
    return bag


class ActionCurveCollection:
    def __init__(self, action, owner=None, create=False):
        modern = hasattr(action, 'slots') and hasattr(action, 'layers') and (not getattr(action, 'is_action_legacy', False) or getattr(action, 'is_empty', False))
        legacy = getattr(action, 'fcurves', None) if not modern else None
        self.bag = None
        if legacy is not None:
            self.curves = legacy
        else:
            self.bag = actionChannelBag(action, owner, create)
            self.curves = self.bag.fcurves if self.bag is not None else ()

    def __iter__(self):
        return iter(self.curves)

    def __len__(self):
        return len(self.curves)

    def find(self, data_path, index=0):
        return self.curves.find(data_path, index=index) if hasattr(self.curves, 'find') else None

    def new(self, data_path, index=0, action_group=''):
        if not hasattr(self.curves, 'new'):
            raise ValueError('Create an action channelbag before adding animation curves')
        if self.bag is None:
            return self.curves.new(data_path, index=index, action_group=action_group)
        try:
            return self.curves.new(data_path, index=index, group_name=action_group)
        except TypeError:
            curve = self.curves.new(data_path, index=index)
            if action_group:
                group = self.bag.groups.get(action_group) or self.bag.groups.new(action_group)
                curve.group = group
            return curve

    def remove(self, curve):
        self.curves.remove(curve)


def actionCurves(action, owner=None, create=True):
    return ActionCurveCollection(action, owner, create)


def actionGroups(action, owner=None):
    modern = hasattr(action, 'slots') and hasattr(action, 'layers') and (not getattr(action, 'is_action_legacy', False) or getattr(action, 'is_empty', False))
    legacy = getattr(action, 'groups', None) if not modern else None
    if legacy is not None:
        return legacy
    return actionChannelBag(action, owner, True).groups


def assignAction(owner, action):
    animation = owner.animation_data_create()
    animation.action = action
    if action is not None and hasattr(action, 'slots') and (not getattr(action, 'is_action_legacy', False) or getattr(action, 'is_empty', False)):
        bag = actionChannelBag(action, owner, True)
        slot = next(slot for slot in action.slots if slot.handle == bag.slot_handle)
        animation.action_slot = slot
    return animation


def builtinShader(name):
    import gpu
    if bpy.app.version < (4, 0, 0):
        name = '3D_' + name
    return gpu.shader.from_builtin(name)


def drawOverlayBatch(batch, shader, matrix):
    import gpu
    if hasattr(gpu, 'state'):
        state = gpu.state
        previous_depth = state.depth_test_get()
        previous_mask = state.depth_mask_get()
        state.depth_test_set('LESS_EQUAL')
        state.depth_mask_set(False)
        gpu.matrix.push()
        try:
            gpu.matrix.multiply_matrix(matrix)
            batch.draw(shader)
        finally:
            gpu.matrix.pop()
            state.depth_mask_set(previous_mask)
            state.depth_test_set(previous_depth)
    else:
        import bgl
        enabled = bgl.glIsEnabled(bgl.GL_DEPTH_TEST)
        bgl.glEnable(bgl.GL_DEPTH_TEST)
        gpu.matrix.push()
        try:
            gpu.matrix.multiply_matrix(matrix)
            batch.draw(shader)
        finally:
            gpu.matrix.pop()
            if not enabled:
                bgl.glDisable(bgl.GL_DEPTH_TEST)
