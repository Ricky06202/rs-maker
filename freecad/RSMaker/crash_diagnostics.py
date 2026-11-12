"""Crash-safe breadcrumbs for native FreeCAD/Qt/OpenCascade failures.

Unlike Python exceptions, SIGSEGV/SIGILL/OOM can terminate FreeCAD before
the error dialog or terminal output is flushed. Stage records are explicitly
fsynced, so the last completed stage survives a hard process crash.

Never record source image paths, font paths, text contents or credentials.
"""
import os
import time
from pathlib import Path

_LOG_NAME="nameforge-crash.log"
_MAX_SIZE=512*1024
_LAST_PATH=None


def log_path():
    root=os.environ.get("XDG_CACHE_HOME") or str(Path.home()/".cache")
    return Path(root)/"rs-maker"/_LOG_NAME


def checkpoint(stage, **metadata):
    """Write one durable, short stage record. Diagnostics must never crash CAD."""
    global _LAST_PATH
    try:
        dest=log_path()
        dest.parent.mkdir(parents=True,exist_ok=True)
        _LAST_PATH=dest
        info=" ".join(
            "%s=%s"%(str(k)[:32],str(v).replace("\n"," ")[:96])
            for k,v in sorted(metadata.items()))
        line="%s pid=%d %s %s\n"%(
            time.strftime("%Y-%m-%dT%H:%M:%S"),
            os.getpid(),str(stage).replace("\n"," ")[:80],info)
        flags=os.O_WRONLY|os.O_CREAT|os.O_APPEND
        fd=os.open(str(dest),flags,0o600)
        try:
            if os.fstat(fd).st_size>_MAX_SIZE:
                os.ftruncate(fd,0)
            os.write(fd,line.encode("utf-8","replace"))
            os.fsync(fd)
        finally:
            os.close(fd)
        return str(dest)
    except (OSError,ValueError,TypeError):
        return ""


def start_generation(cfg):
    return checkpoint("generate:start",
                      quality=getattr(cfg,"quality_mode","balanced"),
                      backend=getattr(cfg,"compute_backend","auto"),
                      lamp=bool(getattr(cfg,"lamp_mode",False)),
                      width_mm=getattr(cfg,"width",0),
                      height_mm=getattr(cfg,"height",0))


def stage_log_hint():
    return str(_LAST_PATH or log_path())
