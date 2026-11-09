# KiCad Eagle Exporter

Exporta placas y proyectos de **KiCad 10.0.x a Eagle XML** para usar un flujo de fresado con **Bantam Tools**, revisar diseños legacy y experimentar con la importación electrónica en **Autodesk Fusion**.

Incluye un **plugin para el editor de PCB**, un conversor por línea de comandos y un instalador para **Windows, Linux y macOS**. El motor nativo utiliza el Python de KiCad.

También incluye una **[versión web en JavaScript para GitHub Pages](web/README.md)**, independiente del runtime de KiCad. Carga PCB, esquemáticos o ZIP en el navegador y descarga EAGLE XML 7.7 (`.brd`, `.sch`, `.lbr`) y un informe. No sube los diseños a un servidor. Consulta su documentación para conocer los límites de la versión web y activar Pages con el workflow incluido.

Prueba local de la web: `node scripts/serve-web.mjs`. Paquete web independiente: `node scripts/build-web.mjs`.

**Estado: versión de desarrollo 0.3.0.** La conversión se probó en Windows con KiCad 10.0.7. Dos placas fueron importadas correctamente en Bantam Tools 1.2.3 durante el desarrollo. La edición de pistas y la sincronización completa en Eagle/Fusion siguen siendo experimentales. Linux y macOS necesitan pruebas nativas; disponer de instrucciones y pruebas de código multiplataforma no equivale a haber validado el plugin dentro de KiCad en esos sistemas.

**Licencia: GPL-3.0-only.** Consulta [LICENSE](LICENSE). Las dependencias conservan sus propias licencias. Esta carpeta está preparada para que su propietario la suba a su repositorio; no implica una publicación en GitHub ni aceptación en el gestor oficial de KiCad.

## Contenido

- [Qué exporta](#qué-exporta)
- [Instalación rápida](#instalación-rápida)
- [Usarlo dentro de KiCad](#usarlo-dentro-de-kicad)
- [Usarlo desde una terminal](#usarlo-desde-una-terminal)
- [Cómo llevar el resultado a Bantam](#cómo-llevar-el-resultado-a-bantam)
- [Cómo probarlo en Eagle y Fusion](#cómo-probarlo-en-eagle-y-fusion)
- [Informes y notas de conectividad](#informes-y-notas-de-conectividad)
- [Compatibilidad y límites](#compatibilidad-y-límites)
- [Desarrollo y pruebas](#desarrollo-y-pruebas)
- [Distribución y GitHub](#distribución-y-github)
- [Documentación técnica de referencia](#documentación-técnica-de-referencia)

## Qué exporta

### Solo placa

Entrada: un `.kicad_pcb` guardado. Salidas:

- `.brd`: placa Eagle XML, con pistas, cobre de pads, vías, perforaciones y contorno.
- `.report.json`: medidas, cantidades, alcance de la conversión y notas informativas.

Este modo está orientado a fabricar la placa. Por ahora cada pad se representa mediante un elemento independiente. Conserva la asignación de redes de los elementos admitidos, pero no conserva los componentes originales como unidades editables completas.

### Proyecto vinculado

Entradas: `.kicad_sch` y `.kicad_pcb` correspondientes. Salidas con el mismo nombre base:

- `.sch`: esquemático Eagle con símbolos y conexiones.
- `.brd`: placa con los pads agrupados en sus componentes originales.
- `.lbr`: biblioteca de símbolos, encapsulados y relaciones entre pines y pads.
- `.project-report.json`: consistencia eléctrica, nombres de redes, cantidades y notas.

La biblioteca también está incluida dentro del esquemático y la placa. No se requieren las bibliotecas KiCad originales para abrir los archivos exportados. El conversor lee los símbolos incluidos en el esquemático y los encapsulados presentes en la PCB; usa la netlist calculada por `kicad-cli` para comprobar las conexiones.

Esta primera versión admite proyectos de **una hoja**, sin buses ni imágenes. No ofrece conversión general de cualquier proyecto KiCad.

## Instalación rápida

### Requisitos

1. KiCad **10.0.x**, instalado con su soporte de scripting Python.
2. El módulo `pcbnew` accesible desde el Python usado por KiCad.
3. `kicad-cli` 10.0.x para exportar proyectos con esquemático.
4. Conexión a Internet para instalar Shapely y sus dependencias la primera vez.

El instalador utiliza `pip --target` dentro del plugin. No instala paquetes en el Python global del sistema ni requiere permisos de administrador para una instalación normal de usuario. Instala solamente ruedas binarias compatibles con el intérprete y la arquitectura actuales; si no existen, termina con un error legible en lugar de intentar compilar dependencias.

No reutilices la carpeta `_deps` de otra máquina, de otra arquitectura o de otro Python. Windows, Linux y macOS utilizan binarios diferentes; macOS Intel y Apple Silicon también son distintos.

### Windows

Descomprime el código y abre PowerShell en la carpeta del repositorio:

```powershell
python scripts/install.py
```

Si la detección automática falla, indica el Python de KiCad:

```powershell
python scripts/install.py --python "C:\Program Files\KiCad\10.0\bin\python.exe"
```

Puedes ejecutar directamente ese intérprete si no tienes otro comando `python` disponible:

```powershell
& 'C:\Program Files\KiCad\10.0\bin\python.exe' scripts/install.py
```

### Linux

Usa una instalación nativa de KiCad 10. En distribuciones que separan el soporte Python, instala también el paquete que proporciona `pcbnew` para el Python del sistema. Los nombres dependen de la distribución.

```sh
python3 scripts/install.py
```

Si tu Python predeterminado es de Conda, pyenv o un entorno virtual, especifica el del sistema que pueda importar `pcbnew`:

```sh
python3 scripts/install.py --python /usr/bin/python3
```

En Linux, puede ser necesario instalar `pip` mediante el gestor de paquetes de la distribución. No uses `sudo pip`. Este proyecto no valida todavía instalaciones Flatpak, Snap o entornos con aislamiento que impidan acceder al Python de KiCad.

### macOS

Instala KiCad 10 desde su distribución oficial, abre Terminal en la carpeta del repositorio y ejecuta:

```sh
python3 scripts/install.py
```

El instalador busca el Python dentro de las aplicaciones KiCad. Si la estructura de tu versión es distinta, proporciona su ruta mediante `--python`. Usa el intérprete incluido en tu instalación y su misma arquitectura; un Python de Homebrew o de Conda puede no importar `pcbnew`.

En un Mac Apple Silicon se necesitan dependencias ARM64 si KiCad se ejecuta de forma nativa. Si utilizas KiCad Intel mediante Rosetta, se necesitan las dependencias para ese entorno Intel. El instalador delega esa selección al Python elegido.

### Dónde se instala

| Sistema | Carpeta predeterminada del plugin |
|---|---|
| Windows | `%USERPROFILE%\Documents\KiCad\10.0\scripting\plugins\kicad_eagle_exporter` |
| Linux | `~/.local/share/kicad/10.0/scripting/plugins/kicad_eagle_exporter` |
| macOS | `~/Documents/KiCad/10.0/scripting/plugins/kicad_eagle_exporter` |

La instalación respeta `KICAD_DOCUMENTS_HOME` y, en Linux, `XDG_DATA_HOME`. Si utilizas documentos redirigidos a OneDrive, una ubicación personalizada o una instalación portable, comprueba la carpeta real de plugins desde el editor de PCB y pásala con `--plugin-dir`. El destino debe incluir la carpeta final `kicad_eagle_exporter`.

```sh
python3 scripts/install.py --plugin-dir "/ruta/personalizada/plugins/kicad_eagle_exporter"
```

Para revisar la detección antes de instalar:

```sh
python3 scripts/install.py --dry-run
```

Más opciones y solución de problemas: [docs/INSTALL.md](docs/INSTALL.md).

## Usarlo dentro de KiCad

1. Reinicia el editor de PCB después de instalar, o actualiza los plugins externos desde sus preferencias.
2. Abre una placa y guarda sus cambios.
3. Para exportar el proyecto, guarda también el esquemático. El plugin no puede comprobar si otra ventana de esquemático tiene cambios sin guardar.
4. En **Herramientas → Plugins externos**, elige **Exportar a Eagle / Bantam**. Puede aparecer también en la barra de herramientas.
5. Selecciona **Solo placa** o **Placa + esquemático + biblioteca**.
6. Selecciona el esquemático, si corresponde, y la ubicación del `.brd` de salida.
7. Al terminar, revisa el informe indicado por el diálogo.

El plugin exporta archivos guardados. Si la placa tiene cambios pendientes, pide guardarlos y termina esa operación. No guarda automáticamente el original. Si hay archivos de salida existentes, solicita confirmación antes de reemplazarlos.

La conversión se ejecuta en el hilo principal porque usa la API nativa de KiCad. Durante diseños grandes el editor puede quedar ocupado hasta que termine; esta versión prioriza usar la API en el contexto correcto.

## Usarlo desde una terminal

Después de instalar el plugin, el lanzador puede encontrar sus dependencias en la carpeta de instalación predeterminada:

```sh
python3 scripts/export.py board /ruta/placa.kicad_pcb /ruta/salida.brd
```

En Windows, utiliza `python` en lugar de `python3` si ese es el comando disponible. Las rutas con espacios deben ir entre comillas.

Proyecto completo:

```sh
python3 scripts/export.py project /ruta/proyecto.kicad_sch --pcb /ruta/proyecto.kicad_pcb --output /ruta/exportado/proyecto
```

Si omites `--pcb`, se busca una placa con el mismo nombre que el esquemático. `--output` indica un nombre base; el conversor añade las extensiones `.sch`, `.brd`, `.lbr` y `.project-report.json`.

Para seleccionar explícitamente el intérprete:

```sh
python3 scripts/export.py --python /ruta/python-de-kicad project proyecto.kicad_sch --output exportado/proyecto
```

Los archivos existentes se conservan salvo que añadas `--overwrite`. Una instalación en una carpeta personalizada puede requerir `KICAD_EAGLE_DEPS` apuntando a la carpeta `_deps` instalada. También puedes instalar dependencias para uso solo por terminal con el Python de KiCad y `pip --target plugin/kicad_eagle_exporter/_deps -r requirements.txt`.

Variables opcionales:

| Variable | Uso |
|---|---|
| `KICAD_EAGLE_PYTHON` | Ejecutable Python capaz de importar `pcbnew` 10.0.x |
| `KICAD_EAGLE_CLI` | Ejecutable `kicad-cli` 10.0.x |
| `KICAD_EAGLE_DEPS` | Dependencias instaladas para ese Python y arquitectura |

## Cómo llevar el resultado a Bantam

1. Abre el software de Bantam Tools.
2. Importa el `.brd` con **Open Files**.
3. Comprueba las dimensiones y selecciona Top o Bottom según tu diseño.
4. Revisa perforaciones, contorno, recortes y trayectorias.
5. En pads complejos, comprueba que el cobre superpuesto se vea continuo y que no aparezca un corte dentro del mismo pad.

El plugin no elige herramientas, profundidad, posición de material o fijación, y no produce G-code. Esos ajustes siguen perteneciendo al software de Bantam.

Un resultado correcto en una placa no garantiza que todos los elementos de otra placa sean interpretados igual. Para registrar compatibilidad, interesa probar diseños pequeños que aíslen pads rotados, arcos, vías y recortes.

## Cómo probarlo en Eagle y Fusion

En Eagle, coloca el `.sch` y el `.brd` con el mismo nombre base y abre ambos. En Fusion, sube ambos archivos juntos y conserva **Create Electronics Design** para asociarlos.

La biblioteca `.lbr` sirve para revisar y reutilizar la conversión. Los símbolos y encapsulados también están dentro de la pareja de archivos. No se crean bibliotecas gestionadas de Autodesk ni asociaciones con paquetes 3D.

Comprueba estos comportamientos por separado:

- Abrir los archivos sin errores de formato.
- Reconocer los mismos componentes y redes.
- Mantener la relación pin–pad.
- Mantener las conexiones al mover componentes o editar pistas.
- Recalcular correctamente el trazado o las conexiones pendientes.

Las pruebas de geometría y de netlist no sustituyen la última comprobación de edición. Durante el desarrollo se reportó un comportamiento de pistas que se separan al moverlas; este proyecto todavía no lo considera resuelto de forma general.

## Informes y notas de conectividad

Los informes incluyen dimensiones, cantidades de objetos, limitaciones y observaciones. El modo de proyecto agrega hashes de los archivos fuente y un mapa de nombres de redes.

Eagle no admite ciertos nombres que KiCad sí puede guardar. El conversor adapta espacios, punto y coma, dos puntos y mayúsculas, pero garantiza un mapa uno a uno para evitar unir redes diferentes por accidente.

Ejemplo: `BUTTON` y `BUTTON ` son redes distintas en KiCad. Pueden exportarse como `BUTTON` y `BUTTON_`; si ese segundo nombre ya existe, se asigna otro sufijo único. La misma transformación se aplica a placa y esquemático.

En `informational_notes` aparece una nota cuando dos nombres solo difieren por espacios. Incluye los componentes y pines afectados, las cantidades de pistas y si existe un pad aislado en una red de un solo pad. Esa situación puede no aparecer como conexión pendiente en KiCad porque no hay otro contacto de esa red al que exigir una pista.

La nota es informativa: no bloquea la exportación ni modifica el circuito. Corregir una etiqueta o unir redes es una decisión sobre el diseño que debe hacerse en KiCad.

El cobre al borde también se conserva como está y se informa. El plugin no intenta convertir avisos DRC intencionales en errores de exportación.

## Compatibilidad y límites

| Función | Estado |
|---|---|
| Windows, KiCad 10.0.7, motor de conversión | Probado localmente |
| Bantam Tools 1.2.3 | Dos pruebas manuales de usuario satisfactorias |
| Windows, botón dentro del editor | Requiere prueba interactiva de aceptación |
| Linux y macOS | Código y rutas preparados; prueba nativa pendiente |
| Esquemático de una hoja y PCB vinculados | Comprobados estructural y eléctricamente en el proyecto de desarrollo |
| Edición completa en Eagle/Fusion | Experimental |
| KiCad 9, 11 o posteriores | Fuera del alcance de esta versión |

Se admiten las capas externas F.Cu y B.Cu; pistas rectas y curvas; vías pasantes de diámetro uniforme; pads habituales circulares, rectangulares, ovales y con esquinas redondeadas; agujeros circulares; contornos cerrados y recortes interiores.

Un pad pasante con forma que Eagle no representa directamente se construye con un pad circular interior que lleva el taladro y dos superficies de cobre adicionales. Todos sus contactos se asignan a la misma red. Puede haber más contactos Eagle que pines físicos del componente; el `.lbr` conserva esa relación de uno a varios.

Eagle expresa la redondez de pads en porcentajes enteros. En una prueba se midió una diferencia máxima aproximada de 0,005 mm en el borde del cobre. Esa cifra describe esa prueba concreta, no un límite garantizado para todos los diseños.

El modo nativo rechaza elementos que no puede representar, incluyendo multicapa, taladros ranurados, vías ciegas o enterradas, zonas y ciertas formas especiales. Existe `--snapshot` en el motor de placa para experimentar con cobre aplanado en triángulos; no se expone como opción principal del plugin y no está validado de forma general en Bantam/Eagle.

No se exportan modelos 3D, máscara, pasta, reglas de diseño originales o gráficos KiBuzzard como componentes eléctricos. El esquemático puede necesitar ajustes visuales de texto. Se conservan los archivos originales.

### Por qué este plugin usa SWIG

La conversión ya desarrollada usa objetos `pcbnew`, poligonización y el lector de archivos de KiCad 10. Este paquete la integra mediante un Action Plugin clásico. Declara `runtime: swig`, requiere KiCad 10 y no pretende ser un plugin IPC.

La API SWIG está deprecada. La migración a IPC y la compatibilidad con KiCad 11 requieren trabajo adicional; cambiar el manifiesto no basta. Consulta [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Desarrollo y pruebas

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q plugin scripts
```

Las pruebas portables cubren nombres de redes, colisiones, parser, notas informativas y rutas por sistema. El flujo de GitHub Actions las ejecuta en Windows, Linux y macOS. No instala KiCad dentro de esos runners y no afirma haber probado el editor en ellos.

Las pruebas nativas utilizan una PCB sintética generada durante la ejecución, el lector Eagle de KiCad y comparación geométrica. Consulta [docs/TESTING.md](docs/TESTING.md). No se incluyen los proyectos de usuarios utilizados en el desarrollo dentro de este repositorio.

## Distribución y GitHub

```sh
python3 scripts/build.py
```

El comando genera en `dist/` un ZIP de código, un ZIP local para el gestor de plugins y hashes SHA-256. Los archivos excluyen dependencias compiladas, cachés, datos de usuario y resultados de prueba.

El ZIP PCM es un paquete de desarrollo instalable desde un archivo local, no una publicación aceptada por el repositorio oficial de KiCad. Sus dependencias deben prepararse para el Python local. Para una primera instalación sencilla, utiliza el ZIP de código y `scripts/install.py`.

Antes de publicar: confirmar el propietario y la visibilidad, actualizar los enlaces al repositorio elegido, ejecutar las pruebas y revisar el contenido que se subirá. El nombre propuesto y aprobado es `kicad-eagle-exporter`; la licencia es `GPL-3.0-only`. [docs/RELEASING.md](docs/RELEASING.md) describe los pasos de GitHub y la futura postulación al gestor oficial.

## Documentación técnica de referencia

- [Action Plugins y API pcbnew](https://dev-docs.kicad.org/en/apis-and-binding/pcbnew/index.html).
- [API IPC de KiCad y sus límites por versión](https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/for-addon-developers/).
- [Empaquetado de complementos para PCM](https://dev-docs.kicad.org/en/addons/).
- [Línea de comandos de KiCad 10](https://docs.kicad.org/10.0/en/cli/cli.html).
- [Reglas de nombres de Eagle/Fusion](https://help.autodesk.com/cloudhelp/ENU/Fusion-ECAD/files/ECD-CLI-N.htm).

KiCad, EAGLE, Fusion y Bantam Tools son nombres de sus respectivos propietarios. Este proyecto es una herramienta independiente.
