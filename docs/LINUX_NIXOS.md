# FreeCAD, Linux y NixOS

RS Maker está diseñado para Python dentro de **FreeCAD 1.x**. El complemento no
ejecuta servicios, no requiere cuenta ni modifica el sistema. En Linux instala
las fuentes en el directorio `Mod` mostrado por
`App.getUserAppDataDir()` dentro de FreeCAD.

La estructura esperada es:

```text
Mod/rs-maker/
├── Init.py
├── InitGui.py
├── freecad/RSMaker/
├── Resources/
└── package.xml
```

## VTracer opcional

VTracer añade trazado de curvas suave, pero es opcional. RS Maker siempre conserva
el trazador interno y ejecuta VTracer en un Python hijo con límite de tiempo,
memoria y CPU. Un fallo nativo del vectorizador no debe terminar FreeCAD.

Para activar la integración, instala `vtracer==0.6.15` en un Python accesible
desde la sesión gráfica y establece antes de iniciar FreeCAD:

```bash
export RS_MAKER_VTRACER_PYTHON=/ruta/al/venv/bin/python
freecad
```

En NixOS, crea o reutiliza un `venv` o entorno Nix reproducible; no hace falta
instalar VTracer dentro de un paquete global de Python. La ruta anterior debe
apuntar al mismo intérprete en el que `python -c "import vtracer"` funciona.
El botón **Comprobar VTracer** ejecuta esa comprobación sin bloquear la GUI.

Si OpenCV/OpenCL no está disponible, el procesamiento usa CPU. OpenCL nunca
fuerza una dependencia ni cubre las operaciones OpenCascade.

## Recuperación ante archivos complejos

Los archivos se validan antes de pasarlos a Qt/OpenCascade: 15 MB máximo,
25 megapíxeles máximo para PNG/JPG/WebP/BMP, y límites estructurales para SVG.
Se bloquean recursos externos, entidades XML y documentos SVG con complejidad
excesiva.

Si una combinación concreta de FreeCAD, controlador OpenCL o imagen necesita
diagnóstico, inicia FreeCAD con CPU y trazador interno:

```bash
RSM_NAMEFORGE_SAFE_MODE=1 freecad
```

Las marcas de etapa se guardan sin rutas ni contenido del usuario en:

```text
${XDG_CACHE_HOME:-$HOME/.cache}/rs-maker/nameforge-crash.log
```

## Desarrollo y comprobaciones

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m compileall -q Init.py InitGui.py freecad tests
.venv/bin/python -m unittest discover -s tests -v
```

CadQuery/OpenCascade prueba BRep, interferencias y estados idealizados sin
arrancar FreeCAD. Un BRep válido no sustituye la prueba en FreeCAD real,
la inspección del STL, el laminado, los cupones de tolerancia ni el montaje
físico.
