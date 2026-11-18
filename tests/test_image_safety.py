"""Input preflight tests that must run before Qt/native image decoders."""
import struct
import unittest
from unittest.mock import patch

from freecad.RSMaker import image_safety as safety


def png(width, height):
    return (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR"
            + struct.pack(">II", width, height) + b"\x08\x06\x00\x00\x00")


def jpeg(width, height):
    payload = b"\x08" + struct.pack(">HH", height, width) + b"\x03"
    return b"\xff\xd8\xff\xc0" + struct.pack(">H", len(payload) + 2) + payload + b"\xff\xd9"


def webp(chunk, payload):
    return (b"RIFF" + struct.pack("<I", len(payload) + 12)
            + b"WEBP" + chunk + struct.pack("<I", len(payload)) + payload)


class ImageSafetyTests(unittest.TestCase):
    def test_png_jpeg_and_webp_dimensions_are_checked_before_decode(self):
        for extension, data in (
                (".png", png(800, 600)),
                (".jpg", jpeg(800, 600)),
                (".webp", webp(b"VP8X", b"\x00\x1f\x03\x00\x57\x02\x00\x00\x00\x00")),
        ):
            with self.subTest(extension=extension):
                safety.validate_source_bytes(data, extension)
        with self.assertRaisesRegex(ValueError, "demasiados píxeles"):
            safety.validate_source_bytes(png(20000, 3000), ".png")
        with self.assertRaisesRegex(ValueError, "20000 px"):
            safety.validate_source_bytes(jpeg(40000, 1), ".jpeg")

    def test_webp_vp8_variants_have_bounded_dimensions(self):
        vp8 = b"\x00\x00\x00\x9d\x01\x2a" + struct.pack("<HH", 640, 480)
        vp8l_bits = (639) | (479 << 14)
        vp8l = b"\x2f" + vp8l_bits.to_bytes(4, "little")
        safety.validate_source_bytes(webp(b"VP8 ", vp8), ".webp")
        safety.validate_source_bytes(webp(b"VP8L", vp8l), ".webp")

    def test_svg_rejects_external_content_and_excessive_native_work(self):
        with self.assertRaisesRegex(ValueError, "DOCTYPE"):
            safety.validate_source_bytes(
                b'<!DOCTYPE svg [<!ENTITY x "x">]><svg/>', ".svg"
            )
        with self.assertRaisesRegex(ValueError, "recursos externos"):
            safety.validate_source_bytes(
                b'<svg xmlns="http://www.w3.org/2000/svg">'
                b'<image href="https://example.invalid/a.png"/></svg>', ".svg"
            )
        with self.assertRaisesRegex(ValueError, "recursos externos"):
            safety.validate_source_bytes(
                b'<svg><style>@import "https://example.invalid/a.css";'
                b'</style></svg>', ".svg"
            )
        with self.assertRaisesRegex(ValueError, "raíz"):
            safety.validate_source_bytes(b"<root/>", ".svg")
        with patch.object(safety, "MAX_SVG_PATH_DATA", 12):
            with self.assertRaisesRegex(ValueError, "demasiados datos"):
                safety.validate_source_bytes(
                    b'<svg><path d="M 0 0 L 1000 0 Z"/></svg>', ".svg"
                )

    def test_source_size_and_format_are_validated(self):
        with self.assertRaisesRegex(ValueError, "vacío"):
            safety.validate_source_bytes(b"", ".png")
        with self.assertRaisesRegex(ValueError, "máximo 15 MB"):
            safety.validate_source_bytes(b"x" * (safety.MAX_SOURCE_BYTES + 1), ".png")
        with self.assertRaisesRegex(ValueError, "no compatible"):
            safety.validate_source_bytes(b"data", ".gif")


if __name__ == "__main__":
    unittest.main()
