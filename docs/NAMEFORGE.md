# RS Maker · NameForge (prototipo inicial)

NameForge es un módulo del mismo banco de trabajo **RS Maker**, no otro Workbench.

## Uso

1. Instala el repositorio en `Mod/RSMaker` y reinicia FreeCAD 1.x.
2. Abre el banco **RS Maker** → **Crear…**.
3. Selecciona **NameForge · Figura SVG + nombre**.
4. Escoge un SVG vectorial con áreas cerradas, una fuente local TTF/OTF y escribe el nombre.
5. Define **ancho**, **alto** y **profundidad total** (mm), más relieve de figura y nombre.
6. Marca o desmarca **Lámpara (hueca, 2 piezas)**: un solo check cambia el tipo de pieza.
7. Pulsa **Crear**; selecciona el grupo para **Editar creación** o **Exportar STL**.

## Dos modos, un check

- **Check desmarcado — Caja maciza:** bloque sólido de ancho × alto × profundidad. Cara inferior plana en `Z=0`, SVG y nombre en relieve hacia arriba. **Un STL**.
- **Check marcado — Lámpara hueca:** se generan **dos piezas separadas**, para evitar el puente largo que produciría imprimir una caja cerrada hueca: (1) un **frente plano de 2 mm** con SVG/nombre en relieve, y (2) un **marco perimetral de 3 mm** de ancho. La profundidad total incluye frente + marco; cavidad trasera abierta para LEDs, con pequeña salida inferior para cable. **Dos STL**, `nameforge_frente.stl` y `nameforge_marco.stl`.

Ambos STL de NameForge se exportan individualmente con su cara inferior en **Z=0** y se imprimen planos en la cama. El marco es abierto por delante y por detrás; coloca las luces dentro del marco, usa **filamento translúcido para el frente** y une ambas piezas por la superficie perimetral con adhesivo apto para el material. La unión por adhesivo es provisional: el complemento no genera todavía clips, difusor desmontable, soportes de LED, conectores ni electrónica.

La lámpara requiere como mínimo **9 mm de profundidad total**. El marco deja `profundidad - 2 mm` de espacio interior y la abertura interior mide `ancho - 6 mm` × `alto - 6 mm`. La pieza frontal es un panel completo sin orificios, pero debe imprimirse en material que deje pasar la luz; las letras/relieves, aunque se iluminen, no son todavía piezas multicolor separadas.

**Precauciones:** verifica las dimensiones reales del LED, alimentación eléctrica de baja tensión, disipación de calor, adhesión de piezas, cables y montaje antes de vender una lámpara; no se han realizado ensayos físicos. No utilices iluminación que pueda recalentar el PLA/PETG.

El dibujo ocupa la zona superior y el nombre queda centrado abajo. Se ajustan automáticamente para no salirse de la caja. Las propiedades del grupo y la interfaz **Editar** guardan los parámetros. El contenido SVG también queda embebido en el archivo FreeCAD para regenerar la misma figura aunque se mueva el archivo fuente. **La tipografía requiere conservar su archivo TTF/OTF.**

## Recomendaciones SVG

- Exporta desde Inkscape o equivalente como SVG simple: formas rellenas, rutas cerradas, sin imágenes raster, entidades externas ni texto SVG sin convertir a rutas.
- Los trazos simples deben convertirse a contornos. Si una ruta se auto-interseca, corrígela antes de importar.
- Tamaño máximo de SVG: 2 MB; máximo 350 regiones para limitar el costo de las booleanas.
- Los colores de relleno del SVG **no se traducen todavía a un 3MF multicolor**. El generador actual produce un único sólido/único STL, apropiado para impresión monocromática o pintado posterior. Para multicolor habrá que conservar los cuerpos por región en una siguiente versión.
- El relieve usa alturas planas distintas para imagen y nombre; no es un modelado escultórico automático.

## Nota sobre pruebas

Se ha integrado el código en el repositorio, **pero aún no se ha probado ejecutándolo en una instalación real de FreeCAD**. Primero prueba un SVG sencillo (un círculo o estrella cerrada) y una fuente TTF. Si falla con gráficos complejos, comparte el mensaje de la consola; el importador SVG de FreeCAD y las operaciones booleanas pueden variar según versión.

## Compatibilidad con las cajas puzzle

El botón único **Crear…** permite escoger entre **Caja puzzle sorpresa** (módulo anterior, experimental) y **NameForge**. Los botones **Editar** y **Exportar STL** detectan el tipo de proyecto seleccionado. `RSMaker_New` sigue registrado para compatibilidad con macros antiguas.
