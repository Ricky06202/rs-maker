"""Background-only geometry preparation for RS Maker NameForge.

FreeCAD's Part and document APIs must be called on the GUI thread; this
QThread performs only raster, mask, bridge and polygon calculations.
"""
import threading
from .lamp_stencil import QtCore


class MaskWorker(QtCore.QThread):
    progressed = QtCore.Signal(int, str)

    def __init__(self, cfg, prepared, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.prepared = prepared
        self.result = None
        self.error = None
        self._cancel_requested = threading.Event()

    def cancel(self):
        self._cancel_requested.set()

    def _progress(self, value, message):
        if self._cancel_requested.is_set():
            raise RuntimeError("Generación cancelada.")
        from . import crash_diagnostics
        crash_diagnostics.checkpoint("worker:progress",percent=int(value))
        self.progressed.emit(int(value), str(message))

    def run(self):
        from . import lamp_stencil, crash_diagnostics
        crash_diagnostics.checkpoint("worker:start")
        try:
            self.result = lamp_stencil.build_masks(
                self.cfg, self.prepared, self._progress)
            if self._cancel_requested.is_set():
                self.result = None
                self.error = "Generación cancelada."
            else:
                crash_diagnostics.checkpoint("worker:completed")
        except Exception as exc:
            self.result = None
            self.error = str(exc)
            crash_diagnostics.checkpoint("worker:python-error",
                                         error=type(exc).__name__)
        finally:
            # Drop read-only QImage reference and other large scratch inputs.
            self.prepared = None
