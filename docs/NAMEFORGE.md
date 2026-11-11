# RS Maker · NameForge — imagen o SVG, caja multicolor y lámpara calada

En FreeCAD: **RS Maker → Crear… → NameForge**. Elige una imagen PNG/JPG/WebP/BMP o SVG, una tipografía TTF/OTF, escribe el nombre y configura las dimensiones de la pieza.

## Lámpara: silueta y nombre hueco (checkbox activado)

1. La ilustración se convierte en una **silueta exterior** con detalles interiores abiertos para dejar pasar la luz. No se extruyen las miles de regiones del SVG original.
2. El **nombre se corta completamente** a través del frente de 2 mm. No es un relieve ni una pieza añadida.
3. Los centros de letras como **A, O, B, R, D, P** se unen a la superficie mediante **puentes de material**. Ancho configurable **1.0–3.5 mm**; valor inicial: 1.6 mm.
4. El **marco perimetral de 3 mm** sigue la silueta y delimita la cavidad de iluminación. El conjunto ahora tiene **tres piezas**: frente calado de 2 mm, marco y **tapa trasera lisa de 2 mm** con un orificio para el cable. La profundidad total incluye ambas tapas. El marco ocupa la profundidad restante. La tapa necesita una fijación adecuada (adhesivo o mecanismo a diseñar); todavía no incorpora clips ni tornillos.
5. La ilustración se rasteriza a una resolución controlada; los contornos se **suavizan ligeramente** conservando las puntas importantes. Se abre el patrón en la silueta y se conserva un borde estructural. Un verificador de conectividad descarta islas diminutas y conecta las restantes mediante puentes. Si el suavizado produce una cara inválida, el generador reintenta con contornos menos suavizados.
6. Imprime frente, marco y tapa por separado, con sus caras planas apoyadas en la cama. Revisa el montaje de la tapa, puentes, voladizos, paso para cable, material translúcido si corresponde, alimentación y disipación del LED antes de utilizarlo.

**Importante:** una imagen con fondo complejo, transparencia irregular o trazos muy finos puede requerir ajustes en origen. La conversión automática simplifica detalles para mejorar la fabricabilidad. La capa del nombre es un recorte en el plástico, no una impresión multicolor.

## Caja maciza (checkbox desactivado)

La base permanece completamente llena. Las áreas de color del SVG o imagen se convierten en un **SVG simplificado con paleta de 2–16 colores planos**; los cuerpos se incrustan en el fondo con la cara visible coplanar, **sin relieve**. La cuantización puede perder gradientes y detalles.

Para imprimir en varios colores, importa todos los STL como partes alineadas de **un mismo objeto** en el laminador y asigna filamentos. Los STL carecen de información de filamento; guarda después un proyecto 3MF. El complemento todavía no exporta 3MF multicolor directamente.

## Tamaño recomendado y escalado proporcional

El botón **Sugerir dimensiones según el detalle** analiza la imagen o SVG y propone un ancho y alto en milímetros a partir de la densidad de bordes y proporciones de su silueta. Es una **heurística orientativa para impresión con boquilla de 0.4 mm**, no una garantía del resultado: comprueba la vista previa del laminador y el tamaño mínimo de los rasgos antes de imprimir.

**Ancho y alto siempre permanecen vinculados.** Modificar cualquiera de los dos recalcula el otro con la misma relación de aspecto; el botón de sugerencia establece una nueva proporción antes de activar el bloqueo. Se respetan los límites del modelo (ancho 30–430 mm, alto 40–430 mm). **La profundidad permanece independiente**, porque determina el espacio físico para iluminación.

## Edición y origen de imágenes

Se almacenan el SVG o imagen fuente en los parámetros del documento FreeCAD (contenido embebido en base64). Así puede volver a editarse el mismo proyecto aunque el original haya cambiado de lugar. Se conservan ancho, alto, profundidad, tipografía, nombre, modo, número de colores y ancho de puentes.

## Compatibilidad y pruebas

- El esquema NameForge pasa a versión 4 y conserva los proyectos anteriores (esquemas 1, 2 y 3).
- Se utiliza QtSvg/QImage y FreeCAD/Part incluidos con FreeCAD 1.x: no se exigen OpenCV, NumPy ni programas externos.
- Hay pruebas Python de máscaras, huecos y puentes, además de las pruebas anteriores del proyecto.
- **Todavía no se ha probado el circuito completo en la interfaz real de FreeCAD ni con una impresión física.** No debe asumirse que todas las siluetas tendrán suficiente resistencia ni que el cableado LED está certificado.
