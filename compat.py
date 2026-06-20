# SPDX-License-Identifier: GPL-3.0-or-later
# BLeeds - Blender API compatibility helpers
# Supports Blender 2.90+ through current 4.x/5.x development builds where possible.

from typing import Any, List

import bpy

def getBlenderVersion() -> tuple:
    return tuple(getattr(bpy.app, "version", (0, 0, 0)))

def isBlenderAtLeast(major: int, minor: int = 0, patch: int = 0) -> bool:
    return getBlenderVersion() >= (major, minor, patch)

def setMeshAutoSmooth(mesh: Any, enabled: bool = True) -> None:
    if mesh is None:
        return
    if hasattr(mesh, "use_auto_smooth"):
        try:
            mesh.use_auto_smooth = bool(enabled)
        except Exception:
            pass

def getFileImportMenuType() -> Any:
    return getattr(bpy.types, "TOPBAR_MT_file_import", getattr(bpy.types, "INFO_MT_file_import", None))

def getFileExportMenuType() -> Any:
    return getattr(bpy.types, "TOPBAR_MT_file_export", getattr(bpy.types, "INFO_MT_file_export", None))

def appendMenu(menu_type: Any, draw_func: Any) -> None:
    if menu_type is None or draw_func is None:
        return
    try:
        menu_type.append(draw_func)
    except Exception:
        pass

def removeMenu(menu_type: Any, draw_func: Any) -> None:
    if menu_type is None or draw_func is None:
        return
    try:
        menu_type.remove(draw_func)
    except Exception:
        pass

def updateMesh(mesh: Any) -> None:
    if mesh is None:
        return
    try:
        mesh.update(calc_edges=False)
        return
    except TypeError:
        pass
    except Exception:
        return
    try:
        mesh.update()
    except Exception:
        pass

def getDomainSize(mesh: Any, domain: str) -> int:
    if mesh is None:
        return 0
    domain_key = str(domain or "POINT").upper().strip()
    try:
        if domain_key == "POINT":
            return len(mesh.vertices)
        if domain_key == "FACE":
            return len(mesh.polygons)
        if domain_key == "CORNER":
            return len(mesh.loops)
        if domain_key == "EDGE":
            return len(mesh.edges)
    except Exception:
        return 0
    return 0

def hasNativeMeshAttributes(mesh: Any) -> bool:
    return mesh is not None and hasattr(mesh, "attributes") and getattr(mesh, "attributes", None) is not None

def getNativeMeshAttribute(mesh: Any, name: str) -> Any:
    if not hasNativeMeshAttributes(mesh):
        return None
    try:
        return mesh.attributes.get(name)
    except Exception:
        return None

def removeNativeMeshAttribute(mesh: Any, attribute: Any) -> None:
    if not hasNativeMeshAttributes(mesh) or attribute is None:
        return
    try:
        mesh.attributes.remove(attribute)
    except Exception:
        pass

def newNativeMeshAttribute(mesh: Any, name: str, data_type: str, domain: str) -> Any:
    if not hasNativeMeshAttributes(mesh):
        return None
    try:
        return mesh.attributes.new(name=name, type=str(data_type or "INT").upper(), domain=str(domain or "POINT").upper())
    except Exception:
        return None

def getFallbackAttributeKey(name: str, suffix: str) -> str:
    safe = str(name).replace("\\", "_").replace("/", "_").replace('"', "_")
    return "bleeds_compat_attr_{}_{}".format(safe, suffix)

class CompatAttributeElement:
    def __init__(self, attribute: "CompatAttribute", index: int):
        self.attribute = attribute
        self.index = int(index)

    @property
    def value(self) -> Any:
        values = self.attribute.getValues()
        if 0 <= self.index < len(values):
            return values[self.index]
        return self.attribute.defaultValue()

    @value.setter
    def value(self, new_value: Any) -> None:
        values = self.attribute.getValues()
        target_len = max(len(values), self.index + 1)
        if len(values) < target_len:
            values.extend([self.attribute.defaultValue()] * (target_len - len(values)))
        if self.attribute.data_type == "FLOAT":
            try:
                values[self.index] = float(new_value)
            except Exception:
                values[self.index] = 0.0
        else:
            try:
                values[self.index] = int(new_value)
            except Exception:
                values[self.index] = 0
        self.attribute.setValues(values)

class CompatAttributeData:
    def __init__(self, attribute: "CompatAttribute"):
        self.attribute = attribute

    def __len__(self) -> int:
        return len(self.attribute.getValues())

    def __getitem__(self, index: int) -> CompatAttributeElement:
        return CompatAttributeElement(self.attribute, int(index))

class CompatAttribute:
    def __init__(self, mesh: Any, name: str, data_type: str = "INT", domain: str = "POINT"):
        self.mesh = mesh
        self.name = str(name)
        self.data_type = str(data_type or "INT").upper().strip()
        self.domain = str(domain or "POINT").upper().strip()
        self.data = CompatAttributeData(self)

    def defaultValue(self) -> Any:
        return 0.0 if self.data_type == "FLOAT" else 0

    def valueKey(self) -> str:
        return getFallbackAttributeKey(self.name, "values")

    def typeKey(self) -> str:
        return getFallbackAttributeKey(self.name, "type")

    def domainKey(self) -> str:
        return getFallbackAttributeKey(self.name, "domain")

    def getValues(self) -> List[Any]:
        if self.mesh is None:
            return []
        try:
            raw_values = self.mesh.get(self.valueKey(), [])
        except Exception:
            raw_values = []
        try:
            return list(raw_values)
        except Exception:
            return []

    def setValues(self, values: List[Any]) -> None:
        if self.mesh is None:
            return
        cleaned = []
        if self.data_type == "FLOAT":
            for value in values:
                try:
                    cleaned.append(float(value))
                except Exception:
                    cleaned.append(0.0)
        else:
            for value in values:
                try:
                    cleaned.append(int(value))
                except Exception:
                    cleaned.append(0)
        try:
            self.mesh[self.valueKey()] = cleaned
            self.mesh[self.typeKey()] = self.data_type
            self.mesh[self.domainKey()] = self.domain
        except Exception:
            pass

    def ensureLength(self, count: int) -> "CompatAttribute":
        values = self.getValues()
        count = max(0, int(count or 0))
        if len(values) < count:
            values.extend([self.defaultValue()] * (count - len(values)))
            self.setValues(values)
        elif len(values) > count and count > 0:
            values = values[:count]
            self.setValues(values)
        else:
            self.setValues(values)
        return self

def getFallbackMeshAttribute(mesh: Any, name: str) -> Any:
    if mesh is None:
        return None
    value_key = getFallbackAttributeKey(name, "values")
    try:
        if value_key not in mesh:
            return None
        data_type = str(mesh.get(getFallbackAttributeKey(name, "type"), "INT") or "INT")
        domain = str(mesh.get(getFallbackAttributeKey(name, "domain"), "POINT") or "POINT")
        return CompatAttribute(mesh, name, data_type, domain).ensureLength(getDomainSize(mesh, domain))
    except Exception:
        return None

def getMeshAttribute(mesh: Any, name: str) -> Any:
    attr = getNativeMeshAttribute(mesh, name)
    if attr is not None:
        return attr
    return getFallbackMeshAttribute(mesh, name)

def removeMeshAttribute(mesh: Any, attribute: Any) -> None:
    if attribute is None:
        return
    if isinstance(attribute, CompatAttribute):
        for suffix in ("values", "type", "domain"):
            key = getFallbackAttributeKey(attribute.name, suffix)
            try:
                if key in mesh:
                    del mesh[key]
            except Exception:
                pass
        return
    removeNativeMeshAttribute(mesh, attribute)

def ensureMeshAttribute(mesh: Any, name: str, data_type: str, domain: str = "POINT") -> Any:
    if mesh is None:
        return None
    data_type_key = str(data_type or "INT").upper().strip()
    domain_key = str(domain or "POINT").upper().strip()
    updateMesh(mesh)
    expected_count = getDomainSize(mesh, domain_key)

    if hasNativeMeshAttributes(mesh):
        attr = getNativeMeshAttribute(mesh, name)
        if attr is not None:
            existing_domain = str(getattr(attr, "domain", domain_key) or domain_key).upper().strip()
            existing_type = str(getattr(attr, "data_type", data_type_key) or data_type_key).upper().strip()
            if (existing_domain and existing_domain != domain_key) or (existing_type and existing_type != data_type_key):
                removeNativeMeshAttribute(mesh, attr)
                attr = None
        if attr is None:
            attr = newNativeMeshAttribute(mesh, name, data_type_key, domain_key)
        if attr is not None:
            return attr

    attr = CompatAttribute(mesh, name, data_type_key, domain_key)
    return attr.ensureLength(expected_count)

def getOrCreateCornerColorLayer(mesh: Any, name: str = "Col") -> Any:
    if mesh is None:
        return None
    if hasattr(mesh, "color_attributes"):
        try:
            existing = mesh.color_attributes.get(name)
            if existing is not None:
                return existing
        except Exception:
            pass
        try:
            return mesh.color_attributes.new(name=name, type="BYTE_COLOR", domain="CORNER")
        except Exception:
            pass
    if hasattr(mesh, "vertex_colors"):
        try:
            existing = mesh.vertex_colors.get(name)
            if existing is not None:
                return existing
        except Exception:
            pass
        try:
            return mesh.vertex_colors.new(name=name)
        except TypeError:
            try:
                return mesh.vertex_colors.new(name)
            except Exception:
                return None
        except Exception:
            return None
    return None

def linkObjectToCollection(collection: Any, obj: Any) -> None:
    if collection is None or obj is None:
        return
    try:
        collection.objects.link(obj)
    except Exception:
        try:
            bpy.context.collection.objects.link(obj)
        except Exception:
            pass

def setActiveObject(context: Any, obj: Any) -> None:
    if obj is None:
        return
    try:
        context.view_layer.objects.active = obj
        return
    except Exception:
        pass
    try:
        bpy.context.scene.objects.active = obj
    except Exception:
        pass

def safeSelectObject(obj: Any, selected: bool = True) -> None:
    if obj is None:
        return
    if hasattr(obj, "select_set"):
        try:
            obj.select_set(bool(selected))
            return
        except Exception:
            pass
    try:
        obj.select = bool(selected)
    except Exception:
        pass
