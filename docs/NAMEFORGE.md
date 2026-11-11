# RS Maker · NameForge (prototipo inicial)

NameForge es un módulo del mismo banco de trabajo **RS Maker**, no otro Workbench.

## Uso

1. Instala el repositorio en `Mod/RSMaker` y reinicia FreeCAD 1.x.
2. Abre el banco **RS Maker** → **Crear…**.
3. Selecciona **NameForge · Figura SVG + nombre**.
4. Escoge un SVG vectorial con áreas cerradas, una fuente local TTF/OTF y escribe el nombre.
5. Define **ancho**, **alto** y **profundidad maciza** (todas medidas en mm), más relieve de figura y nombre.
6. Pulsa **Crear sólido**; selecciona el grupo creado para **Editar creación** o **Exportar STL**.

**Imprimibilidad:** la caja es un bloque completamente macizo `ancho × alto × profundidad`, con base inferior íntegramente plana sobre `Z=0`; tanto SVG como texto se elevan en la dirección `+Z`. Se fusionan al cuerpo en un único sólido y se exportan como un solo STL. No se generan cavidades, electrónica, tapa ni apoyos por debajo del plano de impresión. Es un prototipo CAD: inspecciona el sólido en FreeCAD y comprueba soporte, detalles y laminado antes de producir.

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
