# RS Maker · NameForge — imagen o SVG, caja multicolor y lámpara calada

En FreeCAD: **RS Maker → Crear… → NameForge**. Elige una imagen PNG/JPG/WebP/BMP o SVG, una tipografía TTF/OTF, escribe el nombre y configura las dimensiones de la pieza.

## Lámpara: silueta y nombre hueco (checkbox activado)

1. La ilustración se convierte en una **silueta exterior** con detalles interiores abiertos para dejar pasar la luz. No se extruyen las miles de regiones del SVG original.
2. El **nombre se corta completamente** a través del frente de 2 mm. No es un relieve ni una pieza añadida.
3. Los centros de letras como **A, O, B, R, D, P** se unen a la superficie mediante **puentes de material**. Ancho configurable **1.0–3.5 mm**; valor inicial: 1.6 mm.
4. El **marco perimetral de 3 mm de ancho** sigue la silueta y delimita la cavidad de iluminación. La **tapa trasera de 2 mm está fusionada al marco** y forman **una sola carcasa imprimible**, con orificio para el cable. La lámpara genera **dos piezas**: un frente calado de 2 mm y una carcasa trasera cerrada. La profundidad total incluye ambos frentes; el espacio para LED queda dentro de la carcasa. El frontal aún necesita fijación al perímetro después de instalar la iluminación.
5. La ilustración se rasteriza a una resolución controlada; los contornos se **suavizan ligeramente** conservando las puntas importantes. Se abre el patrón en la silueta y se conserva un borde estructural. Un verificador de conectividad descarta islas diminutas y conecta las restantes mediante puentes. Si el suavizado produce una cara inválida, el generador reintenta con contornos menos suavizados.
6. Imprime **el frente calado y la carcasa posterior** por separado, apoyados con sus caras planas en la cama. La tapa trasera **no aparece como objeto suelto**: ya es parte de la carcasa. Revisa el montaje del frente, los puentes, el paso para cable, el material translúcido si corresponde, la alimentación y la disipación del LED antes de utilizarlo.

**Importante:** una imagen con fondo complejo, transparencia irregular o trazos muy finos puede requerir ajustes en origen. La conversión automática simplifica detalles para mejorar la fabricabilidad. La capa del nombre es un recorte en el plástico, no una impresión multicolor.

## Caja maciza (checkbox desactivado)

La base permanece completamente llena. Las áreas de color del SVG o imagen se convierten en un **SVG simplificado con paleta de 2–16 colores planos**; los cuerpos se incrustan en el fondo con la cara visible coplanar, **sin relieve**. La cuantización puede perder gradientes y detalles.

Para imprimir en varios colores, importa todos los STL como partes alineadas de **un mismo objeto** en el laminador y asigna filamentos. Los STL carecen de información de filamento; guarda después un proyecto 3MF. El complemento todavía no exporta 3MF multicolor directamente.

## Tamaño recomendado y escalado proporcional

El botón **Sugerir dimensiones según el detalle** analiza la imagen o SVG y propone un ancho y alto en milímetros a partir de la densidad de bordes y proporciones de su silueta. Es una **heurística orientativa para impresión con boquilla de 0.4 mm**, no una garantía del resultado: comprueba la vista previa del laminador y el tamaño mínimo de los rasgos antes de imprimir.

**Ancho y alto siempre permanecen vinculados.** Modificar cualquiera de los dos recalcula el otro con la misma relación de aspecto; el botón de sugerencia establece una nueva proporción antes de activar el bloqueo. Se respetan los límites del modelo (ancho 30–430 mm, alto 40–430 mm). **La profundidad permanece independiente**, porque determina el espacio físico para iluminación.

## Edición y origen de imágenes

Se almacenan el SVG o imagen fuente en los parámetros del documento FreeCAD (contenido embebido en base64). Así puede volver a editarse el mismo proyecto aunque el original haya cambiado de lugar. Se conservan ancho, alto, profundidad, tipografía, nombre, modo, número de colores y ancho de puentes.

## Procesamiento acelerado en GPU AMD (opcional)

Para el modo **Lámpara**, NameForge puede usar OpenCL de OpenCV a través de `cv2.UMat` para clasificar píxeles y realizar dilatación, erosión, apertura y cierre sobre máscaras. **No necesita CUDA ni NVIDIA.** El resto del trabajo —conectividad de islas, puentes, contornos CAD, extrusiones y uniones booleanas de OpenCascade— continúa ejecutándose en CPU. El cálculo de máscaras y contornos se ejecuta en un **QThread**, pero la creación de sólidos FreeCAD sigue en el hilo principal porque sus APIs no son seguras para operaciones concurrentes.

El diálogo ofrece tres opciones:

- **Automático:** intenta OpenCL si la instalación de FreeCAD ve OpenCV y un dispositivo OpenCL disponible; si no, vuelve a CPU.
- **Preferir GPU · OpenCL:** solicita la misma aceleración y vuelve automáticamente a CPU ante errores, sin interrumpir la generación.
- **Solo CPU:** evita importar OpenCV y funciona sin dependencias adicionales.

El OpenCV que utiliza NameForge debe ser importable desde **el Python integrado en FreeCAD**; instalarlo en otro entorno Python no basta. En Linux, puede verificarse la disponibilidad desde la consola Python de FreeCAD con:

```python
import cv2
print("OpenCL disponible:", cv2.ocl.haveOpenCL())
cv2.ocl.setUseOpenCL(True)
print("OpenCL habilitado:", cv2.ocl.useOpenCL())
```

Si OpenCV no está instalado, o el controlador AMD no expone OpenCL, NameForge conserva su ruta CPU sin cambios. En entornos Qt de FreeCAD, **se recomienda una instalación de OpenCV sin componentes Qt adicionales** (por ejemplo, paquete `opencv-python-headless` compatible con el Python del sistema) para evitar conflictos de plugins, sin modificar el Python de FreeCAD a ciegas.

Al finalizar se imprime en la **consola de FreeCAD** el procesador usado y los tiempos de preparación, silueta, máscaras y contornos. Prueba el mismo dibujo primero con «Solo CPU» y luego con «Automático» y compara los tiempos. OpenCV puede usar una implementación CPU incluso cuando OpenCL está habilitado; `UMat` <b>no garantiza</b> que cada operación use la GPU ni que sea más rápida. La transferencia GPU↔CPU también cuesta tiempo.

**Pendiente de validación real:** aún no se ha verificado esta ruta con un equipo AMD del usuario, sus controladores ni OpenCascade instalado en FreeCAD. Las pruebas CI cubren compatibilidad y respaldo CPU; no ejecutan GPU AMD.

## Compatibilidad y pruebas

- El esquema NameForge pasa a versión 6 y conserva los proyectos anteriores (esquemas 1–5).
- Se utiliza QtSvg/QImage y FreeCAD/Part incluidos con FreeCAD 1.x: no se exigen OpenCV, NumPy ni programas externos.
- Hay pruebas Python de máscaras, huecos y puentes, además de las pruebas anteriores del proyecto.
- **Todavía no se ha probado el circuito completo en la interfaz real de FreeCAD ni con una impresión física.** No debe asumirse que todas las siluetas tendrán suficiente resistencia ni que el cableado LED está certificado.

## Actualización — carcasa con fondo unido

En modo lámpara el generador devuelve **exactamente dos cuerpos FreeCAD**, frontal calado (`nameforge_frente`) y carcasa cerrada (`nameforge_marco`). La segunda contiene marco + tapa trasera fusionados mediante una operación booleana de sólidos. La comprobación exige que el resultado sea válido y tenga **un único sólido**: un mero compuesto de dos cuerpos no es suficiente. El grupo `nameforge_tapa_trasera` de proyectos antiguos se elimina al regenerar el mismo proyecto, conservando el objeto `nameforge_marco` para mantener la compatibilidad de edición.

El frente sigue separado para poder colocar los LED. El orificio trasero de cable continúa en el fondo y no se exporta una tapa separada. **Validación pendiente:** generar en FreeCAD real y comprobar el contacto de ambas superficies y tolerancias de montaje antes de imprimir.


## Contornos con curvas CAD (actualización de acabado)

En modo **Balanceado** y **Alta calidad**, los contornos de la ilustración, las perforaciones del nombre y la carcasa se suavizan en el trabajador de NameForge y se dividen en tramos delimitados por las **esquinas verdaderas**. Durante la construcción del modelo, FreeCAD convierte los tramos suaves en **curvas B-spline reales de OpenCascade** mediante `Part.BSplineCurve.interpolate(...)`; no se limita a unir todos los píxeles con segmentos rectos ni depende del SVG intermedio. Las puntas largas y deliberadas (cabello, esquinas de la placa) se mantienen sin redondear. Los ajustes rápidos conservan los polígonos ligeros.

Si la B-spline invade una perforación o FreeCAD la rechaza, el generador **reintenta automáticamente** con polígonos ya suavizados y después con los contornos conservadores originales. La validación comprueba wires cerrados y caras válidas antes de extruir; el frente conserva sus puentes y la carcasa posterior permanece un único sólido con el marco unido.

Las curvas se calculan parcialmente en el QThread: la preparación y división de tramos se hace fuera de la GUI; **la creación de curvas FreeCAD y las booleanas CAD siguen en el hilo principal**, por seguridad. Un diseño extremadamente complejo puede hacer lenta esa fase. Las pruebas Python no sustituyen la validación visual de FreeCAD ni una impresión física.
