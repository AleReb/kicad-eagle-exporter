# Instalación y solución de problemas

## Comprobar el intérprete

El mismo Python que ejecuta la conversión debe poder importar `pcbnew` y Shapely. Un Python distinto puede tener el mismo número de versión y seguir siendo incompatible.

```sh
/ruta/python-de-kicad -c "import pcbnew; print(pcbnew.Version())"
```

En PowerShell, antepone `&` a una ruta entre comillas. El resultado debe empezar por `10.0.`.

`scripts/install.py --dry-run` no instala archivos ni dependencias. Muestra el intérprete detectado y la carpeta de destino. Para instalaciones no estándar, utiliza `--python` y `--plugin-dir`.

## Dependencias

`requirements.txt` contiene Shapely 2.1 o posterior dentro de la versión mayor 2. Necesitamos `constrained_delaunay_triangles`; versiones anteriores no ofrecen esa operación. Pip instala también NumPy y las bibliotecas binarias correspondientes a la plataforma.

El instalador descarga esas dependencias en una carpeta temporal y comprueba que el Python seleccionado puede importarlas antes de copiarlas al plugin. Un fallo de descarga no reemplaza el código del plugin instalado.

No se utiliza un entorno virtual común para todos los sistemas ni se copian los archivos `.pyd`, `.so` o `.dylib` desde Windows a Linux/macOS. La distribución de código es la misma; la instalación de dependencias es local.

Si faltan ruedas binarias para tu Python/arquitectura, el instalador lo indicará. Esa combinación debe considerarse pendiente de soporte hasta que pueda instalarse y probarse. No se pide desactivar protecciones de macOS ni cambiar ajustes de seguridad del sistema.

## Carpeta correcta

Desde el editor de PCB, abre las preferencias de plugins de acción y usa su botón para abrir la carpeta de plugins. Esa carpeta es la referencia más fiable si cambiaste las rutas predeterminadas.

El instalador añade la carpeta `kicad_eagle_exporter` dentro de esa ubicación. Si usas `--plugin-dir`, incluye esa carpeta final en el argumento.

Los paquetes PCM se instalan en la ubicación gestionada por KiCad, que puede ser diferente de la carpeta manual de scripting. Evita tener una copia PCM y otra manual cargadas al mismo tiempo: aparecerían dos plugins o se podría cargar una versión distinta de la esperada.

## No aparece el botón

1. Reinicia el editor o actualiza la lista de plugins externos.
2. Comprueba que `__init__.py` esté directamente en `kicad_eagle_exporter` y que no haya una carpeta adicional de ZIP entre ambos.
3. Comprueba que estés usando KiCad 10, con scripting habilitado.
4. Revisa los errores de carga de plugins desde la consola de scripting.
5. Una vez listado, puede ser necesario activar su botón en la barra de herramientas.

Este es un plugin SWIG. Activar el servidor IPC no es un requisito para esta versión.

## Uso solo por terminal

Si no deseas instalar un botón, usa el Python de KiCad para instalar dependencias en la carpeta del código:

```sh
/ruta/python-de-kicad -m pip install --only-binary=:all: --target plugin/kicad_eagle_exporter/_deps -r requirements.txt
python3 scripts/export.py --python /ruta/python-de-kicad board placa.kicad_pcb salida.brd
```

Para el proyecto completo debe funcionar también `kicad-cli --version`. Si hay varias versiones, configura `KICAD_EAGLE_CLI` para elegir la 10.0.x.

## Instalación sin Internet

En una máquina con el mismo sistema operativo, arquitectura y Python de KiCad, descarga las ruedas:

```sh
/ruta/python-de-kicad -m pip download --only-binary=:all: -r requirements.txt -d wheelhouse
```

Tras copiar el código y `wheelhouse` al destino, instala sus dependencias sin red:

```sh
/ruta/python-de-kicad -m pip install --no-index --find-links wheelhouse --target plugin/kicad_eagle_exporter/_deps -r requirements.txt
python3 scripts/install.py --python /ruta/python-de-kicad --skip-dependencies
```

En ese último caso, copia `_deps` a la carpeta instalada, o utiliza `KICAD_EAGLE_DEPS` para apuntar a la carpeta preparada. La opción `--skip-dependencies` no copia ni instala dependencias automáticamente.

## Actualizar y desinstalar

Para actualizar una instalación manual, vuelve a ejecutar el instalador con la nueva versión y el mismo destino. Conserva archivos de usuario desconocidos; no hagas modificaciones personales dentro de los motores del plugin porque se reemplazan al actualizar.

Para desinstalar, cierra el editor y elimina únicamente la carpeta del plugin que se mostró durante la instalación. Las exportaciones guardadas en otras carpetas se conservan.
