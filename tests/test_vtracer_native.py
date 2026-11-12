"""Optional real VTracer smoke test (run in CI with vtracer installed)."""
import importlib.util
import unittest
from freecad.RSMaker import vtracer_adapter as adapter
from freecad.RSMaker import stencil_core as core


@unittest.skipUnless(importlib.util.find_spec("vtracer"),"VTracer Python binding not installed")
class NativeVTracerSmokeTests(unittest.TestCase):
    def test_real_binary_trace_round_trips_contours_without_losing_holes(self):
        w=h=96
        mask=bytearray(w*h)
        for y in range(6,90):
            for x in range(6,90):
                mask[y*w+x]=1
        for y in range(32,64):
            for x in range(32,64):
                mask[y*w+x]=0
        original=core.cleaned_contours(mask,w,h,"balanced")
        paths,used,total=adapter.trace(mask,w,h,"balanced")
        self.assertEqual(total,len(original))
        self.assertEqual(len(paths),len(original))
        self.assertGreater(used,0)
        self.assertTrue(any(core.polygon_area(p)>0 for p in paths))
        self.assertTrue(any(core.polygon_area(p)<0 for p in paths))


if __name__=="__main__":
    unittest.main()
