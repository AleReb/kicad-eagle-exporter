# KiCad → EAGLE · Web

Aplicación estática escrita completamente en JavaScript. Funciona en GitHub Pages y procesa los diseños en el navegador, sin enviarlos a un servidor. No requiere Python, KiCad, Node ni dependencias instaladas para el usuario final. No usa CDN, analítica ni fuentes externas.

## Publicar en GitHub Pages

**Desde el repositorio completo:**

1. Sube los cambios de este repositorio, incluida la carpeta `web/` y `.github/workflows/pages.yml`.
2. En GitHub abre **Settings → Pages → Build and deployment → Source → GitHub Actions**.
3. Ejecuta **Actions → Deploy JavaScript converter to GitHub Pages → Run workflow**, o sube cambios a `main` o `master`.
4. El workflow prueba el conversor y publica exclusivamente el contenido de `web/`. La URL aparecerá en el despliegue de `github-pages`.

**Como sitio independiente:**

1. Ejecuta `node scripts/build-web.mjs` desde el repositorio completo.
2. Descomprime `dist/kicad-eagle-web-github-pages.zip`.
3. Sube **el contenido** descomprimido a la raíz de una rama de un repositorio GitHub.
4. En **Settings → Pages**, selecciona **Deploy from a branch**, la rama elegida y **/(root)**.

Todos los recursos usan rutas relativas, por lo que funcionan también en `https://usuario.github.io/nombre-repositorio/`. No hace falta configurar un dominio, secretos o backend. Activar Pages y subir el código son pasos de publicación; la copia local no significa que ya exista un sitio publicado.

Referencia oficial: [configurar la publicación de GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).

## Usar

1. Escoge **Solo PCB** o **Proyecto vinculado**.
2. Carga `.kicad_pcb` y, para proyecto, el `.kicad_sch` correspondiente. También puedes cargar un ZIP normal sin contraseña con ambos archivos. Si hay varias PCB o esquemáticos, selecciónalos en las listas.
3. Pulsa **Convertir a EAGLE**, revisa las notas y descarga cada archivo o el ZIP completo.
4. Para proyecto, conserva `.brd` y `.sch` juntos y con el mismo nombre. La `.lbr` se entrega también por separado y está embebida en ambos archivos.
5. Comprueba la consistencia del par esquema/placa en EAGLE, revisa geometría, reglas, taladros y conectividad antes de editar o fabricar.

El `.kicad_pro` se acepta como acompañante, pero no contiene PCB ni esquema y no se utiliza para reconstruir el circuito. Los originales no se modifican. Los datos permanecen en memoria hasta cerrar o recargar la pestaña; la web no ofrece almacenamiento persistente.

**EAGLE legacy significa aquí EAGLE XML 7.7**, con extensiones `.brd`, `.sch` y `.lbr`. No genera el formato binario de EAGLE 5 o anterior, un proyecto de Fusion, ni un archivo `.epf` de preferencias. Una pareja `.brd` + `.sch` vinculada constituye la salida de proyecto electrónico.

## Compatibilidad de esta versión experimental

- Archivos modernos S-expression de KiCad. Se probaron proyectos guardados con KiCad 10.0.7. Admite redes por nombre de KiCad 10 y el esquema anterior de códigos numéricos; otras versiones necesitan validación adicional.
- PCB con dos capas de cobre, F.Cu y B.Cu; pistas rectas y curvas; vías pasantes uniformes; pads circulares, rectangulares, ovales y redondeados; taladros circulares y contornos con líneas, arcos, círculos y rectángulos.
- Pads agrupados por componente. Los pads pasantes compuestos usan varios contactos eléctricos asociados al mismo pin.
- Proyecto de una hoja, símbolos embebidos, unidades, reflejos, cables, uniones, etiquetas y marcadores de alimentación.
- Los nombres de red se adaptan a EAGLE de forma uno a uno para conservar redes distintas, incluidas diferencias por espacios o mayúsculas.

Se rechazan zonas de cobre, capas internas, vías ciegas o microvías, ranuras, taladros desplazados, pads personalizados o con padstacks especiales, eliminación de anillos sin uso, gráficos de cobre, jerarquías, buses, imágenes y primitivas de esquema no admitidas. No se ofrece el modo snapshot experimental del plugin Python.

La máscara, pasta, modelos 3D, reglas originales, áreas de exclusión y algunos gráficos/textos auxiliares no se exportan. El informe muestra las capas gráficas omitidas. Los símbolos y textos pueden necesitar ajustes visuales.

La comprobación eléctrica reconstruye el grafo del esquemático y lo compara con las redes de los pads de la PCB. Detecta uniones de redes distintas, grupos separados unidos en la PCB, pines sin pads y pads conectados sin pines. No sustituye una netlist de `kicad-cli`, ERC o DRC. El cierre de Edge.Cuts se comprueba por extremos; no se validan todas las auto-intersecciones o islas.

Límites: 64 MB por archivo KiCad, 80 MB por ZIP comprimido, 96 MB de contenido seleccionado, 2.000 entradas ZIP, 90 segundos por conversión y un máximo de 15 millones de comparaciones punto/cable. ZIP64 y ZIP cifrado no se admiten. La descompresión requiere un navegador con `DecompressionStream('deflate-raw')`; si no está disponible, carga archivos sueltos.

## Desarrollo local

Desde la raíz del repositorio, con Node 22 o posterior:

```sh
node scripts/serve-web.mjs
```

Abre `http://127.0.0.1:8765`. No abras `index.html` con doble clic: los módulos y el Web Worker requieren HTTP/HTTPS. El servidor de desarrollo solo escucha en tu equipo. `PORT` permite cambiar el puerto.

Pruebas y paquete distribuible, sin `npm install`:

```sh
node --test web/tests/*.test.mjs
node scripts/build-web.mjs
```

La web incluye un proyecto de ejemplo sintético, sin datos de usuarios. Los diseños locales usados para validación no se incluyen en el sitio ni en el ZIP distribuible.

Validación adicional opcional con KiCad Python y Shapely, desde la raíz del repositorio:

```sh
python tests/integration_web_roundtrip.py entrada.kicad_pcb salida.brd
```

Esta prueba reimporta EAGLE con KiCad, compara el cobre de ambas caras (tolerancia de 0,015 mm), las referencias y la asignación de redes. En los dos proyectos locales de desarrollo, las distancias máximas medidas fueron aproximadamente 0,0041 y 0,0049 mm. También se validaron los nueve archivos XML (PCB, esquema y biblioteca del ejemplo y de los dos proyectos) contra el DTD de la instalación local de EAGLE 9.6.2. Estas medidas describen esos proyectos concretos; no garantizan exactitud para todos los diseños ni validan por sí solas la edición en EAGLE. La revisión visual interactiva quedó pendiente porque la herramienta de control de Chrome se detuvo al no poder verificar la URL de la ventana.

## Archivos

- `converter.js`: parser KiCad, geometría, grafo eléctrico y generador XML.
- `worker.js`: conversión fuera del hilo de la interfaz.
- `zip.js`: lectura ZIP almacenado/Deflate y descarga ZIP, con CRC y límites.
- `app.js`: carga, vista orientativa, controles y descargas.
- `index.html`, `styles.css`: interfaz responsive y accesible.
- `examples/`: proyecto de demostración.

## Licencia

GPL-3.0-only, como el proyecto original. Véase `LICENSE`. KiCad y EAGLE son marcas de sus respectivos titulares; esta herramienta es independiente.
