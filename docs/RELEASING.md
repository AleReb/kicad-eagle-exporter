# Preparar GitHub y una versión distribuible

## Antes del primer push

Confirmar propietario, nombre y visibilidad. La cuenta autenticada en el entorno de preparación es `AleReb`; eso no decide automáticamente dónde ni con qué visibilidad publicar.

La licencia elegida por el propietario es **GPL-3.0-only**, incluida en `LICENSE` y declarada en `metadata.json`. Conserva los avisos de autoría y las licencias de las dependencias. El nombre elegido es **kicad-eagle-exporter**.

Revisar que no se incluyan placas, esquemáticos o bibliotecas de usuarios sin autorización. Este repositorio contiene solo código y la generación de una prueba sintética. Las carpetas `_deps`, `test-output`, cachés y ZIP se excluyen de Git.

## Crear el repositorio

Desde su carpeta, con GitHub CLI autenticado:

```sh
git init -b main
git add .
git commit -m "Prepare KiCad 10 Eagle exporter plugin"
gh repo create OWNER/REPOSITORY --private --source . --remote origin --push
```

Sustituir OWNER/REPOSITORY por el nombre confirmado. Usar `--public` únicamente si se decidió que fuera público. Si el repositorio remoto ya existe:

```sh
git remote add origin https://github.com/OWNER/REPOSITORY.git
git push -u origin main
```

No ejecutar ambos procedimientos sobre un repositorio ya conectado sin comprobar primero `git remote -v`.

## Generar paquetes

```sh
python3 -m unittest discover -s tests -v
python3 scripts/build.py
```

`dist/` contiene:

- `kicad-eagle-exporter-0.3.0-source.zip`: código, instalador, pruebas y documentación.
- `kicad-eagle-exporter-0.3.0-pcm.zip`: plugin y `metadata.json` con estructura PCM.
- `SHA256SUMS.txt`: hashes de los dos paquetes.

La versión está marcada como `development`. Una distribución de código no contiene ruedas para cada sistema. Cada usuario instala dependencias para el Python de su KiCad mediante `scripts/install.py`. El ZIP PCM local necesita preparación equivalente de dependencias; no debe presentarse todavía como instalación sin pasos adicionales.

## Release de GitHub

Después de publicar el repositorio y completar las pruebas apropiadas, crear una etiqueta y una release preliminar. Adjuntar los ZIP y `SHA256SUMS.txt`. Indicar en la descripción qué sistemas se probaron realmente y qué pruebas de Eagle/Fusion siguen pendientes.

No crear etiquetas `stable` ni afirmar compatibilidad nativa con Linux/macOS solo porque las pruebas portables de Actions estén verdes.

## Gestor oficial de KiCad

Publicar en GitHub y aparecer en el gestor oficial son pasos distintos. Para solicitar la inclusión oficial hacen falta licencia compatible, metadatos en inglés, namespace correcto, versión/estado precisos, URL pública de descarga y su SHA-256, además de un lugar para reportar problemas.

Los campos de descarga se añaden a los metadatos enviados al repositorio de paquetes; no se incrusta el hash del ZIP dentro de su propio `metadata.json`. Consulta la [documentación oficial de complementos](https://dev-docs.kicad.org/en/addons/).

Antes de esa solicitud hay que resolver una instalación fiable de dependencias para el entorno de cada KiCad. El borrador actual prepara el código y una vía manual, y no afirma aprobación por KiCad.
