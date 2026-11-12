"""GPU preferences and graceful CPU fallback (requires no FreeCAD/OpenCV)."""
import unittest
from unittest.mock import patch
from freecad.RSMaker.gpu_accel import ImageAccelerator, cpu_morph
from freecad.RSMaker import stencil_core as core


class DummyImage:
    def __init__(self,w,h):
        self._w,self._h=w,h

    def width(self):
        return self._w

    def height(self):
        return self._h


class OpenCLFallbackTests(unittest.TestCase):
    def test_cpu_setting_does_not_import_opencv(self):
        # Explicit CPU option must run without attempting any GPU imports.
        accelerator=ImageAccelerator("cpu")
        self.assertFalse(accelerator.enabled)
        self.assertEqual(accelerator.backend,"CPU (Python)")
        image=DummyImage(9,9)
        mask=accelerator.image_mask(image,lambda image,t:bytearray([1]*81))
        self.assertEqual(sum(mask),81)

    def test_cpu_morph_semantics_preserved(self):
        w=h=30
        mask=bytearray(w*h)
        for y in range(5,20):
            for x in range(4,17):
                mask[y*w+x]=1
        for op in ("dilate","erode","open","close"):
            got=cpu_morph(mask,w,h,2,op)
            target=(core.close(mask,w,h,2) if op=="close" else
                    core.open_mask(mask,w,h,2) if op=="open" else
                    core.morph(mask,w,h,2,op))
            self.assertEqual(got,target)

    def test_missing_opencl_falls_back_without_crash(self):
        accelerator=ImageAccelerator("cpu")
        accelerator._fallback("Controlador AMD no disponible")
        self.assertFalse(accelerator.enabled)
        self.assertIn("CPU", accelerator.backend)
        self.assertIn("AMD", accelerator.detail)
        image=DummyImage(2,2)
        got=accelerator.image_mask(image,lambda image,t:bytearray((0,1,1,0)))
        self.assertEqual(list(got),[0,1,1,0])

    def test_invalid_backend(self):
        with self.assertRaises(ValueError):
            ImageAccelerator("cuda")

    def test_opencl_masks_match_cpu_if_available(self):
        accelerator=ImageAccelerator("opencl")
        if not accelerator.enabled:
            self.skipTest("OpenCV/OpenCL no disponible en este runner")
        w=h=48
        mask=bytearray(w*h)
        for y in range(8,36):
            for x in range(9,39):
                mask[y*w+x]=1
        for operation in ("dilate","erode","open","close"):
            gpu=accelerator.morph(mask,w,h,2,operation,cpu_morph)
            cpu=cpu_morph(mask,w,h,2,operation)
            self.assertEqual(gpu,cpu,
                             "OpenCL cambió la geometría de la máscara")


if __name__ == "__main__":
    unittest.main()
