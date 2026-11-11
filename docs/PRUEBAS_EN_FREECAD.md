# Plan de validación de RS Maker 0.2 en FreeCAD y físicamente

**Estado:** pruebas pendientes. La prueba OpenCascade de la geometría cerrada no demuestra articulación libre ni seguridad.

## 1. Cargar el banco de trabajo

- Abrir FreeCAD 1.x y comprobar que aparece `RS Maker` en el selector de bancos.
- Pulsar «Nueva caja» y comprobar los cinco controles de dificultad; ninguno debe desaparecer si se cambia el nivel.
- Crear una caja con valores predeterminados. Deben aparecer **14 partes**: base, tapa, cuatro cerrojos, cuatro ruedas, dial de la tapa, leva, retenedor y motivo de huella.
- Seleccionar el grupo en el árbol, pulsar Editar, cambiar solo «Derecha» a Difícil. Regenerar y verificar que las otras cuatro dificultades no cambian.
- Guardar FCStd, cerrar FreeCAD, volver a abrirlo y probar que el grupo sigue siendo editable.

## 2. Revisión dimensional y de interferencias

- Verificar cuatro orejas en el interior de la tapa, cuatro cerrojos alineados y un orificio de giro de tapa.
- Comprobar que cada cerrojo entra en su oreja sin intersección; que al retroceder **20 mm** la abandona por completo.
- Comprobar la rueda de cada lateral durante su giro, no solo en las posiciones finales: el brazo debe apartarse del pomo sin atravesar la base ni los otros controles.
- Girar la leva superior desde la posición bajo el estante hasta la de liberación. Verificar que no golpea otra pieza durante el arco.
- Comprobar que ninguna pieza flotante (ruedas, leva/retén) se sale sin herramienta o destrabado intencional: esto requerirá un rediseño del sistema de retención antes de uso infantil.
- Repetir con dimensiones mínimas 150×150 mm y holguras mínima y máxima; confirmar que las operaciones de FreeCAD no producen errores de TopoShape.

## 3. Impresión y montaje (no realizados)

- Imprimir solo pruebas dimensionales de un cerrojo, guía y rueda; comprobar la holgura nominal real.
- Añadir soportes de retención seguros y validar resistencia al esfuerzo de apertura; no usar adhesivo como único cierre sin prueba.
- Montar las cinco estaciones, comprobar el recorrido completo y 30 ciclos de abrir/cerrar sin roturas o atascos.
- Repetir pruebas de fricción y esfuerzo con distintas orientaciones de impresión y materiales.
- Revisar edad objetivo, tamaño y resistencia de piezas pequeñas, pellizcos, bordes y legislación aplicable a juguetes antes de uso comercial.

## 4. Mejoras obligatorias antes de una primera venta

- Una biblioteca de al menos cuatro mecanismos laterales auténticamente diferentes, con adaptador al pestillo común.
- Un selector de dificultad con cambios de reglas o pasos jugables, verificado con pruebas de usuario; no solo símbolos impresos.
- Un método de retención cautivo de todos los diales y partes móviles.
- Importador de diseños con licencias claras y separación entre artes y mecanismo.
- Ensayos físicos y documentación del producto apta para fabricante/impresor.

## Incremento v0.3 — colección original de comida

1. Confirmar que FreeCAD encuentra `Mod/RSMaker/InitGui.py` y que los iconos aparecen.
2. Crear una caja con `Comida`, `Hamburguesita`, `Restaurante`, expresión `Feliz`, altura 30 mm y medidas por defecto de 170×160×95 mm.
3. Comprobar en el árbol que aparecen `Chibi Hamburguesita` y `Escenario Restaurante`; al ocultarlos, las cinco piezas/estaciones mecánicas siguen intactas.
4. Ocultar `Tapa` y verificar que el chibi es un cuerpo independiente alojado dentro. Mostrarla y comprobar que el chibi no invade el interior de la tapa.
5. Comprobar que los pivotes del restaurante quedan alineados con los huecos de la tapa y que su base no interfiere con el dial superior. Repetir con figura Sorprendida de 25 y 40 mm.
6. Exportar los dos STL por separado y abrirlos en el laminador: inspeccionar detalle de ojos, boca, ventanillas del restaurante, soportes y continuidad de malla.
7. Regenerar un proyecto v0.2 existente con v0.3 y verificar que se conservan medidas y dificultades, y que el nuevo grupo "Arte original" aparece sin perder piezas anteriores.
8. No asumir que el método de retención de pivotes y ejes es suficiente ni imprimir juguetes para niños sin evaluación de seguridad.
