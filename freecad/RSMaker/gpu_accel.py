"""Optional AMD-friendly OpenCL acceleration for NameForge raster operations.

Uses OpenCV T-API (UMat), *not* NVIDIA CUDA. FreeCAD/Part, text bridge
algorithms and contour Booleans remain on CPU. Never forces an optional
dependency: missing OpenCV, missing OpenCL, and GPU errors fall back to the
existing pure-Python pipeline.
"""
from collections import Counter
from time import perf_counter


def _raw_rgba(image, np):
    """Extract QImage pixels across PySide2/PySide6 without retaining Qt data."""
    from .lamp_stencil import QtGui
    raster = image.convertToFormat(QtGui.QImage.Format_RGBA8888)
    length = raster.bytesPerLine() * raster.height()
    pointer = raster.constBits()
    if hasattr(pointer, "setsize"):
        pointer.setsize(length)
    raw = bytes(pointer)
    if len(raw) < length:
        raise ValueError("No se pudo leer la memoria QImage.")
    pixels = np.frombuffer(raw[:length], dtype=np.uint8)
    return pixels.reshape(raster.height(), raster.bytesPerLine())[
        :, :raster.width() * 4].reshape(raster.height(), raster.width(), 4)[:, :, :3].copy()


class ImageAccelerator:
    """OpenCL if available; CPU-only, feature-preserving fallback otherwise."""

    def __init__(self, preference="auto"):
        if preference not in ("auto", "opencl", "cpu"):
            raise ValueError("Procesador de imagen desconocido")
        self.requested = preference
        self.backend = "CPU (Python)"
        self.detail = ""
        self.cv2 = None
        self.np = None
        self.timings = {}
        self._gpu_failed = False
        if preference == "cpu":
            self.detail = "CPU elegida manualmente"
            return
        try:
            import cv2
            import numpy as np
            if not hasattr(cv2, "ocl") or not cv2.ocl.haveOpenCL():
                self.detail = "No hay dispositivo OpenCL disponible para OpenCV"
                return
            cv2.ocl.setUseOpenCL(True)
            if not cv2.ocl.useOpenCL():
                self.detail = "OpenCV no pudo activar OpenCL"
                return
            # Trigger a real GPU-aware kernel, not just a feature check.
            source = cv2.UMat(np.ones((64, 64), dtype=np.uint8))
            result = cv2.dilate(source, np.ones((3, 3), dtype=np.uint8))
            if result.get().shape != (64, 64):
                raise RuntimeError("Autoprueba OpenCL incompleta")
            self.cv2, self.np = cv2, np
            self.backend = "OpenCL (OpenCV UMat)"
            self.detail = ("OpenCL habilitado; OpenCV puede elegir una "
                           "implementación CPU para alguna operación.")
        except Exception as exc:
            self.detail = "OpenCL no disponible: %s" % exc

    @property
    def enabled(self):
        return self.cv2 is not None

    def _fallback(self, error):
        self._gpu_failed = True
        self.cv2 = self.np = None
        self.backend = "CPU (respaldo)"
        self.detail = "Fallo OpenCL; se usó CPU: %s" % error

    def image_mask(self, image, cpu_func, threshold=45):
        """Pixel segmentation using OpenCL inRange, or original QImage CPU."""
        if not self.enabled:
            return cpu_func(image, threshold)
        before = perf_counter()
        try:
            cv2, np = self.cv2, self.np
            rgb = _raw_rgba(image, np)
            h, w = rgb.shape[:2]
            corners = [tuple(int(x) for x in rgb[y, x]) for y, x in
                       ((0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1))]
            base = Counter(corners).most_common(1)[0][0]
            lower = tuple(max(0, c - threshold) for c in base)
            upper = tuple(min(255, c + threshold) for c in base)
            source = cv2.UMat(rgb)
            background = cv2.inRange(source, lower, upper)
            inverted = cv2.bitwise_not(background)
            mask = inverted.get()
            self.timings["threshold_gpu_pipeline_s"] = round(
                perf_counter() - before, 3)
            return bytearray((mask > 0).astype(np.uint8).tobytes())
        except Exception as exc:
            self._fallback(exc)
            return cpu_func(image, threshold)

    def morph(self, mask, w, h, radius, operation, cpu_func):
        """GPU erosion/dilation and OPEN/CLOSE with a square footprint.

        Each independent operation transfers its mask once to UMat and its
        result once back. Contour tracing / bridging still require CPU data.
        """
        if not self.enabled:
            return cpu_func(mask, w, h, radius, operation)
        if not radius:
            return bytearray(mask)
        start = perf_counter()
        try:
            cv2, np = self.cv2, self.np
            data = np.frombuffer(mask, dtype=np.uint8).reshape(h, w)
            src = cv2.UMat(data)
            size = 2 * int(radius) + 1
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (size, size))
            if operation == "dilate":
                out = cv2.dilate(src, kernel, borderType=cv2.BORDER_CONSTANT,
                                 borderValue=0)
            elif operation == "erode":
                out = cv2.erode(src, kernel, borderType=cv2.BORDER_CONSTANT,
                                borderValue=0)
            elif operation == "close":
                out = cv2.morphologyEx(src, cv2.MORPH_CLOSE, kernel,
                                       borderType=cv2.BORDER_CONSTANT,
                                       borderValue=0)
            elif operation == "open":
                out = cv2.morphologyEx(src, cv2.MORPH_OPEN, kernel,
                                       borderType=cv2.BORDER_CONSTANT,
                                       borderValue=0)
            else:
                raise ValueError("Operación morfológica inválida")
            result = bytearray(out.get().tobytes())
            if len(result) != w * h:
                raise ValueError("Tamaño de máscara OpenCL inesperado")
            self.timings["morph_gpu_pipeline_s"] = round(
                self.timings.get("morph_gpu_pipeline_s", 0.0) +
                perf_counter() - start, 3)
            return result
        except Exception as exc:
            self._fallback(exc)
            return cpu_func(mask, w, h, radius, operation)


def cpu_morph(mask, w, h, radius, operation):
    """Single semantic fallback; tests exercise it independently of FreeCAD."""
    from . import stencil_core as core
    if operation == "close":
        return core.close(mask, w, h, radius)
    if operation == "open":
        return core.open_mask(mask, w, h, radius)
    return core.morph(mask, w, h, radius, operation)
