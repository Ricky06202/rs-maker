"""NameForge worker integration: optional VTracer never blocks normal CAD."""
import importlib
import sys
import types
import unittest
from unittest.mock import patch

from freecad.RSMaker import stencil_core as core
from freecad.RSMaker import vtracer_adapter


def rect(mask,w,x0,y0,x1,y1):
    for y in range(y0,y1):
        for x in range(x0,x1):
            mask[y*w+x]=1


class VTracerWorkerTests(unittest.TestCase):
    def setUp(self):
        self.w=78
        self.h=120
        aw,ah=68,62
        outer=bytearray(aw*ah)
        rect(outer,aw,28,3,45,57)
        self.prepared=dict(scale=1,w=self.w,h=self.h,margin=5,
                           top_of_band=88,art_w=aw,art_h=ah,
                           cached=(bytes(outer),bytes(outer)),
                           text_w=68,text_h=20,letters=bytearray(68*20))
        self.cfg=types.SimpleNamespace(bridge_width=1.6,
                                       quality_mode="balanced",
                                       compute_backend="cpu",
                                       vector_backend="vtracer")

    def _lamp(self):
        side=types.ModuleType("PySide2")
        side.QtCore=types.SimpleNamespace()
        side.QtGui=types.SimpleNamespace()
        side.QtSvg=types.SimpleNamespace()
        with patch.dict(sys.modules,{"PySide2":side}):
            return importlib.import_module("freecad.RSMaker.lamp_stencil")

    def test_worker_traces_three_parts_when_vtracer_is_available(self):
        lamp=self._lamp()
        names=[]
        def dummy_trace(mask,w,h,mode):
            names.append((w,h,mode))
            loops=core.cleaned_contours(mask,w,h,mode)
            return loops,len(loops),len(loops)
        with patch.object(vtracer_adapter,"trace",side_effect=dummy_trace):
            result=lamp.build_masks(self.cfg,self.prepared)
        self.assertEqual(len(names),3)
        self.assertEqual(result["vector_backend_requested"],"vtracer")
        self.assertTrue(all("VTracer" in result["trace_methods"][part]
                            for part in ("front","rear","cavity")))
        self.assertFalse(result["vector_fallbacks"])
        self.assertEqual(len(core.connected_components(
            result["rear_mask"],self.w,self.h)),1)

    def test_subprocess_failure_falls_back_to_existing_tracer(self):
        lamp=self._lamp()
        with patch.object(vtracer_adapter,"trace",
                          side_effect=RuntimeError("vtracer no está instalado")) as trace:
            result=lamp.build_masks(self.cfg,self.prepared)
        self.assertEqual(trace.call_count,1,
                         "No lanzar tres subprocesos después del primer fallo")
        self.assertEqual(set(result["trace_methods"]),{"front","rear","cavity"})
        self.assertIn("front",result["vector_fallbacks"])
        self.assertEqual(len(core.connected_components(
            result["rear_mask"],self.w,self.h)),1)

    def test_diagnostic_safe_mode_skips_external_native_vectorizer(self):
        import os
        lamp=self._lamp()
        with patch.dict(os.environ,{"RSM_NAMEFORGE_SAFE_MODE":"1"}),\
             patch.object(vtracer_adapter,"trace") as fake:
            result=lamp.build_masks(self.cfg,self.prepared)
        fake.assert_not_called()
        self.assertEqual(result["vector_backend_requested"],"builtin")


if __name__=="__main__":
    unittest.main()
