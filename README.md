> **Nuevo módulo (en desarrollo):** RS Maker incluye el botón único **Crear…**, con un catálogo para elegir **Caja puzzle** o **NameForge (SVG + nombre)**. NameForge acepta **SVG, PNG, JPG y WebP**: en modo caja convierte la imagen a colores planos sobre superficie lisa; en modo lámpara crea **silueta y nombre calados (huecos reales)** con puentes automáticos para evitar partes sueltas. Un checkbox alterna entre **caja maciza** y **lámpara hueca** (frente + marco). Puedes editar el texto, el SVG, la fuente, el ancho, el alto y la profundidad. Los cuerpos STL deben importarse al laminador como partes alineadas de **un mismo objeto multicolor**; el complemento aún no exporta 3MF coloreado. Ya no existe el límite arbitrario de 350 regiones SVG. Consulta [la guía de NameForge](docs/NAMEFORGE.md). Integrado en GitHub, pendiente de validación con FreeCAD real y una impresión de prueba.\n\n# RS Maker v0.3 — Caja puzzle con colección Comida

**Estado:** prototipo CAD de ingeniería para adultos, **NO** juguete infantil validado o listo para vender. Todavía no se ha abierto en una interfaz real de FreeCAD ni ensamblado una impresión física. La versión 0.3 incorpora los generadores de figuras y escenarios originales sobre el núcleo mecánico experimental v0.2.

## Lo nuevo: Comida, Hamburguesita y Restaurante

1. **Colección Comida:** la base incorpora relieves de hamburguesa en sus cuatro caras, situados en la parte baja para no tapar los controles. Las caras conservan los cuatro retos de rueda + corredera. Los demás temas (Espacio y Playa) son planes futuros, no aparecen como opciones implementadas.
2. **Chibi Hamburguesita:** sólido imprimible independiente de una sola pieza; pan, relleno, pies integrados y ojos y boca *grabados* (sin ojos sueltos). Altura regulable entre 25 y 40 mm; expresiones Feliz/Sorprendida. Se coloca dentro de la caja como referencia visual y para comprobar que ocupa un espacio viable.
3. **Restaurante:** escena superior independiente con base, fachada, techo, letrero, toldo y dos pivotes cilíndricos. La tapa incluye dos huecos para esos pivotes. La escena no sustituye ni tapa el dial del quinto puzzle; no hay una unión adhesiva o de retención cautiva validada aún. No entregar a niños antes de asegurar la fijación.
4. **Edición:** el asistente permite seleccionar colección, figura, expresión, altura y escenario, además de las dificultades independientes de las cinco caras y las dimensiones de la caja.
5. **Compatibilidad:** se agregaron `Init.py` y `InitGui.py` en la raíz del complemento para que FreeCAD pueda cargar el Workbench; se corrigió la ruta de los iconos. Se pueden regenerar proyectos anteriores del esquema 2 a esquema 3, preservando sus cinco dificultades y medidas.

## Montaje (solo prototipo)

La figura queda **dentro** de la caja; la decoración grande queda **sobre** la tapa. Ambas son objetos CAD separados para permitir retirarlos y exportarlos individualmente. Los ojos y la boca están grabados para poder pintar los detalles sin pegar piezas muy pequeñas. Los dos pivotes del restaurante encajan teóricamente en huecos holgados de la tapa; todavía falta comprobar su montaje y diseñar una fijación permanente o cautiva.

La caja **conserva cinco retos**: cuatro ruedas laterales que bloquean correderas y una leva superior. El desbloqueo físico previsto exige liberar las cuatro correderas y luego girar la leva para levantar la tapa. No hay una simulación de movimiento completa ni familias alternativas de puzzle implementadas. Cambiar Fácil/Medio/Difícil cambia marcas y geometría del bloqueo, pero **no** establece una dificultad infantil calibrada.

## Instalación en FreeCAD 1.x

1. Cierra FreeCAD, guarda un respaldo de `RSMaker` anterior y extrae este ZIP.
2. Copia la carpeta interior `RSMaker` en el directorio de usuario `Mod`. En la consola de FreeCAD puedes consultar la base con `App.getUserAppDataDir()`; agrega `Mod`.
3. Comprueba la estructura: `.../Mod/RSMaker/InitGui.py`, `.../Mod/RSMaker/package.xml` y `.../Mod/RSMaker/freecad/RSMaker/collection.py`.
4. Reinicia FreeCAD y selecciona el banco **RS Maker** en el selector de bancos de trabajo.
5. Pulsa **Nueva caja**. La configuración inicial es `Comida / Hamburguesita / Restaurante`, aunque puedes desactivar cada componente creativo. Configura dimensiones y cinco dificultades y genera.
6. En el árbol selecciona el grupo `RS Maker | Cinco caras + tapa final` para usar **Editar** y **Exportar piezas STL**.

Si no aparecen los iconos o el banco de trabajo, guarda la salida de la consola de FreeCAD. **No hay garantía de compatibilidad gráfica** sin probarlo en FreeCAD real.

## Dimensiones reales de esta versión

**Atención:** el mecanismo experimental original necesita una caja de al menos **150 × 150 × 75 mm**. El ejemplo usa **170 × 160 × 95 mm**. Esto es bastante mayor que el objetivo comercial posterior de **80 × 80 × 55 mm**. No reduzcas el STL mecánico por escala: los huecos, ejes y tolerancias dejarían de ser funcionales. La miniaturización exige rediseñar los cinco puzzles y calibrarlos de nuevo. La miniatura interna se genera con altura nominal **30 mm**.

## Archivos de muestra

- `examples/RS-Maker-v0.3-Comida.step`: conjunto cerrado de referencia, con figuras y escenarios; exportado usando CadQuery/OpenCascade, **no** desde un FreeCAD real.
- `examples/Hamburguesita-v0.3.stl`: figura monolítica, pensada como prueba de escala y de acabado.
- `examples/Restaurante-v0.3.stl`: escena con pivotes, para probar fijación, resistencia y soportes.

Los STL son prototipos: se debe revisar orientación, soportes y grosor de detalle en el laminador.

**Nota sobre GitHub:** el repositorio guarda el código fuente y las pruebas; los modelos binarios STEP/STL de ejemplo se incluyen en el paquete ZIP descargable, pero no se versionan como código fuente. Consulte `examples/README.md`.

## Seguridad y derechos

- No entregar a menores ni vender como juguete hasta resolver retenedores de las ruedas laterales, eje y leva superior, unión de la escena, holguras, fractura de detalles, pellizcos, bordes y riesgos de piezas ingeribles, y cumplir las normas aplicables según mercado/edad.
- No se incluyen elementos de Pokémon, Bluey, Paw Patrol u otras franquicias. Comida, Hamburguesita y Restaurante son conceptos geométricos originales sin personajes registrados.
- Solo se han probado sólidos y algunos solapes estáticos en CAD, no la secuencia real de juego ni la duración de los mecanismos.

## Pruebas locales del código

```bash
python -m unittest discover -s tests -v
python -m compileall -q freecad tests Init.py InitGui.py
```

El test OCC requiere el paquete Python `cadquery`, empleado solo como kernel geométrico alternativo. No confundir estas pruebas con una validación en FreeCAD. Código del complemento bajo licencia MIT.

## Próximo objetivo

1. Ejecutar RS Maker en FreeCAD 1.x en el equipo real y corregir errores de arranque/GUI.
2. Imprimir una muestra **de restaurante + chibi**, y una pieza de test de pivotes, para verificar detalles y resistencia.
3. Diseñar retención física segura y, después, reducir mecanismos hasta alcanzar un formato coleccionable compacto.
4. Reemplazar las cuatro estaciones laterales iguales por familias de puzzle distintas usando el mismo contrato de cerrojo.
5. Implementar temas originales Espacio y Playa, accesorios para chibis, decoraciones importadas con permisos y una biblioteca editable.
