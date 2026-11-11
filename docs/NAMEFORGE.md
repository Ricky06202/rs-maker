# RS Maker · NameForge — frente plano multicolor

NameForge está dentro del banco de trabajo **RS Maker** (Crear → Figura SVG + nombre).

El SVG puede contener **más de 350 regiones**. No hay un límite arbitrario por cantidad de regiones: la viabilidad depende de la complejidad de las rutas y de la capacidad de FreeCAD/OpenCascade. Los dibujos especialmente densos seguirán necesitando optimización si la generación se vuelve demasiado lenta.

## Uso

1. Selecciona en FreeCAD el banco RS Maker → Crear → NameForge.
2. Importa un SVG vectorial con contornos rellenos y colores planos, escoge una tipografía TTF/OTF e introduce el nombre.
3. Ajusta ancho, alto, profundidad (mm), tamaño de fuente y margen.
4. Modo caja: base **maciza**. Modo lámpara: frente plano de 2 mm y marco hueco con salida de cable.
5. Crear genera una base y **un sólido independiente por cada color encontrado** (más el marco si es lámpara). Edítalo desde el grupo RS Maker.
6. Exporta los STL. En el laminador, importa todas las piezas como **partes de un mismo objeto multicolor**, manteniendo las coordenadas originales, y asigna un filamento a cada color. No importes como objetos separados que el laminador recentre individualmente.

## Geometría de fabricación

- Las regiones del SVG y las letras son **incrustaciones**, no relieves. Su cara superior termina exactamente al mismo nivel que la base: ninguna supera Z = profundidad.
- El generador recorta las regiones solapadas conforme al orden de dibujo del SVG; las áreas que quedan cubiertas no deben atravesar otras piezas de color.
- El fondo se vacía **solo en los volúmenes locales de las incrustaciones**, que quedan ocupados por los cuerpos de otros colores. La caja maciza no tiene una cavidad interior.
- La incrustación es de hasta 0.6 mm, conservando al menos 1.4 mm bajo el color en el frente de lámpara de 2 mm.
- Los colores son los que pueda interpretar `importSVG` de FreeCAD. Gradientes, filtros SVG, imágenes raster, máscaras y SVG que no contenga superficies cerradas pueden requerir conversión previa a rutas y rellenos planos.
- En lámpara, el frente multicolor es independiente del marco abierto. Esta versión no genera difusor, tapa trasera ni fijaciones para LEDs. Prueba temperaturas y conexiones eléctricas antes de utilizarla.

**Importante:** STL no guarda la asignación de filamentos. Se necesitan los STL alineados como partes de una sola pieza y asignar los colores en el laminador; guarda después el proyecto del laminador como 3MF. El complemento aún **no exporta 3MF coloreado directamente**.

## Compatibilidad y pruebas

Se conserva la edición de proyectos NameForge anteriores mediante el esquema 3. Los campos `ArtworkRelief` y `TextRelief` históricos continúan almacenados para abrir modelos anteriores, pero se ignoran al generar: el frente siempre es liso. La tipografía local debe continuar disponible en la ruta original; el SVG queda embebido en el documento FreeCAD.

La nueva generación necesita validación en FreeCAD 1.x con SVG reales (simples y de más de 350 regiones) y una impresión de prueba multicolor. La comprobación estática y las pruebas de CI no demuestran encaje físico, correcto mapeo de todos los SVG ni compatibilidad con todas las versiones de FreeCAD.
