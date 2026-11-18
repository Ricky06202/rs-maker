"""Bounded, dependency-free preflight for NameForge image inputs.

Qt and native decoders are deliberately not the first component allowed to
inspect an input. A small compressed file can still advertise an image large
enough to exhaust FreeCAD, while an SVG can contain enough native work to
destabilize QtSvg. These checks run before decoding and reject unsafe or
unreasonably complex inputs with an actionable Python exception.
"""
import io
import re
import struct
import xml.etree.ElementTree as ET


MAX_SOURCE_BYTES = 15_000_000
MAX_IMAGE_PIXELS = 25_000_000
MAX_IMAGE_SIDE = 20_000
MAX_SVG_ELEMENTS = 50_000
MAX_SVG_ATTRIBUTES = 2_000_000
MAX_SVG_PATH_DATA = 1_500_000
MAX_SVG_DEPTH = 128
_RASTER_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
_BLOCKED_SVG_TAGS = {
    "audio", "embed", "foreignobject", "iframe", "object", "script", "video",
}
_URL_STYLE = re.compile(r"url\s*\(\s*['\"]?\s*([^)'\"\s]+)", re.I)


def _local_name(name):
    return name.rsplit("}", 1)[-1].lower()


def _safe_reference(value):
    text = value.strip()
    if not text or text.startswith("#"):
        return True
    compact = text.lower().replace(" ", "")
    return (
        compact.startswith("data:image/png;base64,")
        or compact.startswith("data:image/jpeg;base64,")
        or compact.startswith("data:image/webp;base64,")
    )


def _validate_image_dimensions(width, height, source):
    if width <= 0 or height <= 0:
        raise ValueError("La %s anuncia dimensiones inválidas." % source)
    if width > MAX_IMAGE_SIDE or height > MAX_IMAGE_SIDE:
        raise ValueError(
            "La %s es demasiado grande: máximo %d px por lado."
            % (source, MAX_IMAGE_SIDE)
        )
    if width * height > MAX_IMAGE_PIXELS:
        raise ValueError(
            "La %s tiene demasiados píxeles (%d): máximo %d."
            % (source, width * height, MAX_IMAGE_PIXELS)
        )
    return width, height


def png_dimensions(data):
    if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("El PNG no tiene una cabecera válida.")
    if data[12:16] != b"IHDR":
        raise ValueError("El PNG no tiene un bloque IHDR inicial.")
    return struct.unpack(">II", data[16:24])


def jpeg_dimensions(data):
    if len(data) < 4 or not data.startswith(b"\xff\xd8"):
        raise ValueError("El JPEG no tiene una cabecera válida.")
    index = 2
    sof = {
        0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
        0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
    }
    while index + 1 < len(data):
        while index < len(data) and data[index] != 0xFF:
            index += 1
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in (0x01, 0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            break
        length = struct.unpack(">H", data[index:index + 2])[0]
        if length < 2 or index + length > len(data):
            break
        payload = index + 2
        if marker in sof:
            if length < 7:
                break
            height, width = struct.unpack(">HH", data[payload + 1:payload + 5])
            return width, height
        index += length
    raise ValueError("El JPEG no contiene dimensiones legibles.")


def webp_dimensions(data):
    if len(data) < 16 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("El WebP no tiene una cabecera válida.")
    chunk = data[12:16]
    size = struct.unpack("<I", data[16:20])[0]
    if len(data) < 20 + min(size, 30):
        raise ValueError("La cabecera WebP está incompleta.")
    payload = data[20:]
    if chunk == b"VP8X":
        if size < 10:
            raise ValueError("La cabecera WebP VP8X está incompleta.")
        width = 1 + int.from_bytes(payload[4:7], "little")
        height = 1 + int.from_bytes(payload[7:10], "little")
        return width, height
    if chunk == b"VP8 ":
        if size < 10 or payload[3:6] != b"\x9d\x01\x2a":
            raise ValueError("La cabecera WebP VP8 está incompleta.")
        width = struct.unpack("<H", payload[6:8])[0] & 0x3FFF
        height = struct.unpack("<H", payload[8:10])[0] & 0x3FFF
        return width, height
    if chunk == b"VP8L":
        if size < 5 or payload[0] != 0x2F:
            raise ValueError("La cabecera WebP VP8L está incompleta.")
        bits = int.from_bytes(payload[1:5], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    raise ValueError("El WebP usa un formato interno no reconocido.")


def bmp_dimensions(data):
    if len(data) < 26 or data[:2] != b"BM":
        raise ValueError("El BMP no tiene una cabecera válida.")
    dib = struct.unpack("<I", data[14:18])[0]
    if dib == 12 and len(data) >= 22:
        return tuple(struct.unpack("<HH", data[18:22]))
    if dib >= 40 and len(data) >= 26:
        width, height = struct.unpack("<ii", data[18:26])
        return width, abs(height)
    raise ValueError("El BMP usa una cabecera no reconocida.")


def validate_svg(data):
    lowered = data.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise ValueError("Exporta el SVG sin DOCTYPE ni entidades externas.")
    element_count = 0
    attribute_bytes = 0
    path_bytes = 0
    try:
        depth = 0
        root_seen = False
        for event, element in ET.iterparse(
                io.BytesIO(data), events=("start", "end")):
            if event == "start":
                depth += 1
                element_count += 1
                if not root_seen:
                    root_seen = True
                    if _local_name(element.tag) != "svg":
                        raise ValueError("El archivo no tiene un elemento SVG raíz.")
                if depth > MAX_SVG_DEPTH:
                    raise ValueError("El SVG tiene demasiados niveles anidados.")
                if element_count > MAX_SVG_ELEMENTS:
                    raise ValueError("El SVG contiene demasiados elementos.")
                tag = _local_name(element.tag)
                if tag in _BLOCKED_SVG_TAGS:
                    raise ValueError("El SVG contiene contenido ejecutable o externo.")
                for name, value in element.attrib.items():
                    attribute_bytes += len(name.encode("utf-8"))
                    attribute_bytes += len(value.encode("utf-8"))
                    if attribute_bytes > MAX_SVG_ATTRIBUTES:
                        raise ValueError("El SVG contiene atributos excesivos.")
                    attribute = _local_name(name)
                    if attribute in ("href", "src") and not _safe_reference(value):
                        raise ValueError(
                            "El SVG enlaza recursos externos; incrústalos primero."
                        )
                    if attribute == "style":
                        for match in _URL_STYLE.finditer(value):
                            if not _safe_reference(match.group(1)):
                                raise ValueError(
                                    "El SVG enlaza recursos externos; incrústalos primero."
                                )
                if tag == "path":
                    path_bytes += len(element.attrib.get("d", "").encode("utf-8"))
                    if path_bytes > MAX_SVG_PATH_DATA:
                        raise ValueError("El SVG contiene demasiados datos de ruta.")
            else:
                if _local_name(element.tag) == "style":
                    css = element.text or ""
                    if "@import" in css.lower():
                        raise ValueError(
                            "El SVG enlaza recursos externos; incrústalos primero."
                        )
                    for match in _URL_STYLE.finditer(css):
                        if not _safe_reference(match.group(1)):
                            raise ValueError(
                                "El SVG enlaza recursos externos; incrústalos primero."
                            )
                depth -= 1
                element.clear()
    except ET.ParseError as exc:
        raise ValueError("SVG inválido: %s." % exc) from exc
    return True


def validate_source_bytes(data, extension):
    if not isinstance(data, bytes):
        try:
            data = bytes(data)
        except (TypeError, ValueError) as exc:
            raise ValueError("No se pudo leer el contenido de la imagen.") from exc
    if not data:
        raise ValueError("El archivo de imagen está vacío.")
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError("Imagen demasiado grande (máximo 15 MB).")
    ext = extension.lower()
    if ext == ".svg":
        validate_svg(data)
        return
    if ext not in _RASTER_EXTENSIONS:
        raise ValueError("Formato de imagen no compatible.")
    if ext == ".png":
        dimensions = png_dimensions(data)
    elif ext in (".jpg", ".jpeg"):
        dimensions = jpeg_dimensions(data)
    elif ext == ".webp":
        dimensions = webp_dimensions(data)
    else:
        dimensions = bmp_dimensions(data)
    _validate_image_dimensions(*dimensions, "imagen")
