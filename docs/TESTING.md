# Pruebas

## Portables

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q plugin scripts
```

Cubren nombres de redes y colisiones, parser de S-expressions, rutas por sistema y notas informativas. Se ejecutan sin KiCad y sin Shapely, por lo que pueden correr en los runners Windows, Linux y macOS de GitHub.

## Integración nativa

Ejecuta con el Python de KiCad 10, después de instalar dependencias:

```sh
/ruta/python-de-kicad tests/integration_roundtrip.py
```

Genera una placa sintética en `test-output/`, exporta a Eagle, reimporta mediante el lector de KiCad y compara geometría por capa. Comprueba un arco, un pad rotado, una vía, agujeros, recorte y conservación del original. Esa prueba no incluye un circuito privado ni presupone un diseño funcional.

## Aceptación del botón

1. Instalar en la carpeta real de plugins.
2. Reiniciar/actualizar plugins y comprobar el botón o menú.
3. Probar cancelar cada diálogo: no debe generar archivos.
4. Probar con una placa modificada: debe pedir guardar.
5. Exportar la placa sintética y comparar con la salida por terminal.
6. Exportar un proyecto de una hoja compatible y abrir `.sch` y `.brd` juntos en Eagle/Fusion.
7. Revisar las notas informativas, los archivos existentes y los errores por geometría no admitida.

Registrar sistema, arquitectura, KiCad, Python y versión del plugin. Afirmar que el botón funciona requiere completar esta prueba dentro de KiCad; importar la clase en un proceso Python solo verifica su carga.

## Validación Eagle, Fusion y Bantam

Para Eagle/Fusion, comprobar formato, correspondencia símbolo–encapsulado, conexiones pendientes y comportamiento al editar/mover pistas y componentes. Para Bantam, comprobar ambas caras, dimensiones, perforaciones, recortes y continuidad de los pads compuestos.

Los avisos de separación o cobre al borde pueden ser intencionales. Se documentan, sin reparar automáticamente el diseño. Las diferencias añadidas por el conversor deben distinguirse de los problemas presentes en el origen.

## Estado conocido

Windows con KiCad 10.0.7: motores de conversión comprobados durante desarrollo. Dos PCBs se importaron en Bantam Tools 1.2.3 con confirmación del usuario. El proyecto vinculado se comprobó mediante netlist y reimportación de PCB, pero todavía requiere aceptación de edición en Eagle/Fusion. Linux/macOS y el botón GUI requieren pruebas nativas.
