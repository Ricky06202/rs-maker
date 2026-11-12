"""VTracer integration tests; no compiled Rust, FreeCAD, Qt or network required."""
import math
import struct
import unittest
from unittest.mock import patch
from freecad.RSMaker import vtracer_adapter as vt
from freecad.RSMaker import stencil_core as core


def rectangle(mask,w,x0,y0,x1,y1,value=1):
    for y in range(y0,y1):
        for x in range(x0,x1):
            mask[y*w+x]=value


class VTracerAdapterTests(unittest.TestCase):
    def test_gray_png_is_valid_and_encodes_mask_dimensions(self):
        m=bytearray([0,1,0,1,1,0])
        png=vt.mask_png(m,3,2)
        self.assertEqual(png[:8],b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II",png[16:24]),(3,2))
        with self.assertRaises(ValueError):
            vt.mask_png(bytearray([1]),3,2)

    def test_multiple_closed_subpaths_and_relative_commands(self):
        path="M 5 5 H 55 V 55 H 5 Z m 15 15 h 20 v 20 h -20 z"
        rings=vt.path_rings(path)
        self.assertEqual(len(rings),2)
        self.assertEqual(len(rings[0]),4)
        self.assertEqual(len(rings[1]),4)
        self.assertAlmostEqual(rings[1][0][0],20)
        with self.assertRaises(ValueError):
            vt.path_rings("M 0 0 L 10 0 L 10 10")  # open wire
        with self.assertRaises(ValueError):
            vt.path_rings("M 0 0 A 8 8 0 0 1 10 10 Z")

    def test_true_cubic_curves_have_subpixel_points(self):
        rings=vt.path_rings("M 8 8 C 16 0,32 0,40 8 S 52 32,40 40 Q 24 50,8 40 Z")
        self.assertEqual(len(rings),1)
        self.assertGreater(len(rings[0]),8)
        self.assertTrue(any(abs(x-round(x))>.001 for ring in rings
                            for x,y in ring))
        self.assertTrue(all(math.isfinite(v) for ring in rings
                            for point in ring for v in point))

    def test_topology_preserves_hole_and_material(self):
        w=h=80
        mask=bytearray(w*h)
        rectangle(mask,w,5,5,75,75)
        rectangle(mask,w,24,24,56,56,0)
        # Same black SVG path includes the inner negative-space counter.
        svg=('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80">
             <path fill="#000000" d="M 5 5 H 75 V 75 H 5 Z
                                     M 24 24 V 56 H 56 V 24 Z"/></svg>''')
        rings,n,total=vt.trace(mask,w,h,"high",runner=lambda png:svg)
        self.assertEqual(total,2)
        self.assertEqual(n,2)
        self.assertEqual(len(rings),2)
        self.assertEqual(sum(core.polygon_area(x)>0 for x in rings),1)
        self.assertEqual(sum(core.polygon_area(x)<0 for x in rings),1)

    def test_missing_small_counter_is_locally_preserved(self):
        w=h=80
        mask=bytearray(w*h)
        rectangle(mask,w,5,5,75,75)
        rectangle(mask,w,24,24,56,56,0)
        mask[65*w+64]=0
        svg='''<svg viewBox="0 0 80 80">
              <path d="M5 5H75V75H5Z M24 24V56H56V24Z"/></svg>'''
        paths,n,total=vt.trace(mask,w,h,"high",runner=lambda png:svg)
        self.assertEqual(total,3)
        self.assertEqual(n,2)
        self.assertEqual(len(paths),3)

    def test_svg_security_and_unsupported_geometry_trigger_fallback(self):
        w=h=30
        mask=bytearray([1])*(w*h)
        with self.assertRaises(ValueError):
            vt.svg_rings("<!DOCTYPE svg><svg/>",mask,w,h)
        with self.assertRaises(ValueError):
            vt.svg_rings('<svg viewBox="0 0 30 30"><path transform="scale(2)" d="M 1 1 L 4 1 L 4 4 Z"/></svg>',mask,w,h)

    def test_native_vectorizer_is_in_a_child_process(self):
        def crashed(*args,**kwargs):
            return type("Result",(),{"returncode":-11,"stderr":b"SIGSEGV","stdout":b""})()
        with patch.object(vt.subprocess,"run",side_effect=crashed),patch.object(vt,"_python_executable",create=True):
            with self.assertRaisesRegex(RuntimeError,"VTracer externo"):
                vt.run_external(b"png")


if __name__=="__main__":
    unittest.main()
