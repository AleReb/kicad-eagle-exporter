# Arquitectura y alcance

## Capas

- `action_plugin.py`: diálogo y registro en KiCad. No importa Shapely al cargar el plugin.
- `runtime.py`: búsqueda de Python, CLI y carpeta de instalación, con variables de entorno para instalaciones personalizadas.
- `kicad10_to_eagle.py`: motor de placa y notas informativas.
- `kicad10_project_to_eagle.py`: símbolos, agrupación de componentes, netlist de KiCad y consistencia de la pareja Eagle.
- `scripts/install.py`: preparación local de dependencias e instalación.
- `scripts/build.py`: empaquetado portable de código y ZIP PCM.

El diálogo usa los archivos guardados en disco. La PCB debe estar guardada; el usuario debe guardar el esquemático antes de exportar el proyecto. El plugin no sincroniza en vivo dos editores abiertos.

## Un archivo de código para cada sistema

El conversor no necesita tres ejecutables compilados. El mismo código Python funciona sobre el runtime de KiCad. Lo que depende del sistema es `pcbnew`, wxPython y las ruedas de Shapely/NumPy. Por eso no se distribuye la carpeta `_deps` dentro del código fuente ni del ZIP PCM genérico.

Esto reduce la matriz de mantenimiento, pero no sustituye pruebas nativas de macOS Intel, macOS ARM64 y distribuciones Linux. Los workflows actuales prueban lógica portable y empaquetado; no representan pruebas GUI o CAM.

## Integridad eléctrica

Los nombres Eagle se asignan con un mapa uno a uno. Colisiones por mayúsculas o sustitución de espacios generan sufijos únicos. La placa y el esquemático comparten el mapa.

Las notas sobre nombres parecidos no modifican conexiones. Un único pad en una red sin pistas puede estar intencionalmente aislado. Tampoco se consideran conexiones pendientes los pares de componentes que pertenecen a redes distintas aunque el diseñador haya querido conectarlos.

Se verifica la relación de pin de símbolo a pad de encapsulado y red. Esa relación puede ser de uno a varios por los pads compuestos. La coincidencia de geometría, netlist o XML no demuestra por sí sola que Eagle/Fusion permita editar y mover los segmentos de la forma esperada.

## KiCad 10 y futuro IPC

Esta versión depende de la API SWIG `pcbnew`, que está deprecada. Se limita expresamente a KiCad 10.0.x. KiCad recomienda IPC para desarrollos nuevos, pero la migración de este motor exige reemplazar la carga de archivos, el acceso a objetos y parte de la geometría.

Una posible siguiente etapa es un plugin IPC que coordine una conversión mediante archivos temporales o exportaciones CLI. Hay que validar cobertura API, manejo de cambios sin guardar y geometría en ese camino; no se obtiene compatibilidad con KiCad 11 simplemente cambiando `runtime` en los metadatos.

## Publicación pendiente

El namespace propuesto se basa en la cuenta GitHub autenticada durante la preparación. El nombre `kicad-eagle-exporter` y la licencia `GPL-3.0-only` fueron elegidos por el propietario. Antes de publicar deben ajustarse los recursos/URLs al repositorio de destino. El ZIP PCM de desarrollo no contiene una URL de descarga ni una declaración de aprobación oficial.
