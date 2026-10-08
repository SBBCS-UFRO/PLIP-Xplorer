# Validación local — 8 de octubre de 2026

## Publicación 1.0.0 — PLIP-Xplorer (8 de octubre de 2026)

- Nuevo nombre, imagen aportada por el usuario y mención © 2026 del laboratorio UFRO.
- 137 textos por idioma: inglés, español, alemán, francés, chino simplificado,
  japonés y portugués de Brasil. Catálogos incluidos en el wheel y el ZIP.
- 15 pruebas unitarias: las 12 anteriores y cobertura de catálogos, marcadores
  de formato, rutas Unicode y recuperación del inglés para idiomas desconocidos.
- Prueba gráfica real de los siete idiomas: controles, cabeceras de tabla, filtros,
  opciones de estilo, estado traducido y persistencia de la preferencia.
- El cambio de idioma mantiene exactamente los resultados, filtros, cámara, modelos
  de etiquetas y un desplazamiento manual de etiqueta. JSON de estilos compatible
  en todos los idiomas; los valores internos conservan sus identificadores originales.
- Wheel compilado e instalado en ChimeraX 1.12/macOS. La actualización desde
  ChimeraX-PLIP-Explorer 0.2.1 conserva el Python configurado y abre una sesión previa.
- Comprobación de regresión de apariencia y exportación PNG/TIFF/JPEG, transparencia,
  dimensiones, colocación de etiquetas, restauración de visibilidad y sesiones .cxs.

Scripts: `test/languages_in_chimerax.py`, `test/rename_in_chimerax.py`,
`test/appearance_in_chimerax.py`. Informes locales: `validation/languages-check.json`,
`validation/rename-check.json`, `validation/appearance-check.json`. Capturas:
`validation/language-*.png`. Estos artefactos locales no se incluyen en el ZIP.

La comprobación valida funcionamiento y renderizado Unicode; las traducciones no
han pasado por una revisión independiente de hablantes nativos. Los registros del
motor, datos científicos y mensajes del sistema conservan su idioma original.

## Publicación 0.2.1 — PLIP-Explorer (8 de octubre de 2026)

- Wheel `ChimeraX-PLIP-Explorer` compilado e instalado en ChimeraX 1.12.
- Migración desde `ChimeraX-PLIP 0.2.0`: paquete anterior retirado, nuevo nombre
  registrado en Tools, preferencias conservadas y sesión previa restaurada.
- Verificado `ui tool show PLIP-Explorer` y la compatibilidad del comando `plip settings`.
- ZIP de fuentes + wheel generado con manifiesto SHA256; entradas y sumas verificadas.
- 12 pruebas del adaptador superadas tanto en el proyecto como en una copia extraída
  del ZIP. El script `setup_backend.py --help` funciona desde esa copia independiente.
- El motor PLIP se empaquetó desde el código extraído, sin acceder a índices externos,
  comprobando que la documentación y los archivos necesarios estaban incluidos.

La distribución excluye el entorno de análisis, los resultados, las cachés y las
rutas de usuario específicas. Conserva código fuente, licencia, créditos y ejemplos.

## Actualización 0.2.0 — personalización

Se comprobaron 12 pruebas unitarias del adaptador y la prueba real
`test/appearance_in_chimerax.py` en ChimeraX 1.12 con interfaz gráfica:

- Etiquetas de residuos y distancias; orden donante/aceptor correcto en puentes de agua.
- Filtros sin duplicación de etiquetas, grosor/color/líneas continuas y presets.
- Coordenadas e informe científico inalterados después de aplicar los estilos.
- Fuente/configuración y estilos JSON; rechazo de presets inválidos sin cambios parciales.
- Cambio y restauración del modo de ratón para mover etiquetas; conservación de cámara.
- PNG RGBA con alfa transparente, PNG opaco, TIFF y JPEG, todos de 1000 × 750 píxeles.
- Exportación de estilos oscuro, ilustración y representaciones de esferas/bolas.
- Aislamiento del resultado y restauración de los otros modelos ante un error del renderizador.
- Persistencia de los cinco modelos de etiquetas de la escena de prueba al guardar/abrir `.cxs`.

Artefactos: `validation/appearance-check.json`, `custom-white.png`,
`custom-transparent.png`, `custom-dark.png`, `custom-illustration.png`,
`custom-spheres.png`, `custom-publication.cxs` y `appearance-panel.png`.
Las comprobaciones de abajo corresponden a la base 0.1.0 conservada en esta versión.

Entorno comprobado: macOS, ChimeraX **1.12 (2026-06-12)**, PLIP **3.0.1** de este
repositorio, Python **3.11**, Open Babel **3.2.1**. Bundle: **ChimeraX-PLIP 0.1.0**.

## Resultados

- 9 pruebas del adaptador: XML de las ocho clases, coordenadas, XML inválido,
  CSV, cancelación, timeout, errores del motor, prevención de informes obsoletos
  y conservación de rutas de Python de entornos virtuales.
- 3 pruebas existentes de `plip/test/test_xml_parser.py`.
- Prueba de extremo a extremo con 1VSN: exportación del modelo, PLIP externo,
  13 interacciones/13 segmentos, comparación de extremos con XML, movimiento
  rígido, rechazo de coordenadas atómicas incorrectas y guardado/restauración `.cxs`.
- Prueba gráfica real: construcción del panel Qt, lista de ligandos, filtros,
  selección de residuos, enfoque, renderizado y análisis asíncrono desde el botón.
- Construcción e instalación real del wheel en ChimeraX 1.12.

## Casos adicionales calculados con PLIP y cargados en ChimeraX

| Estructura | Sitios | Interacciones | Segmentos dibujados |
|---|---:|---:|---:|
| 1EVE | 5 | 20 | 24 |
| 3EMS | 5 | 34 | 46 |
| 1RMD | 4 | 16 | 16 |

Se comprobaron las coordenadas de **cada extremo de cada segmento** contra el
XML generado. Estos casos cubren contactos hidrofóbicos, puentes de hidrógeno,
agua y sales, apilamiento π, π–catión y coordinación metálica. 1VSN cubre además
los enlaces de halógeno. Los puentes de agua producen dos segmentos por interacción.

Los conteos son de estas ejecuciones, no valores universales: la protonación puede
cambiar el resultado. No se realizó una comparación de imágenes píxel a píxel con
PyMOL ni una validación exhaustiva de todo PLIP. Se reutiliza su motor sin modificar
los criterios de detección; se valida el transporte y la representación de sus datos.

## Artefactos locales

- `validation/demo-1vsn.cxs`: escena de ejemplo del PLIP actual.
- `validation/binding-site.png`: render del sitio de unión.
- `validation/panel.png`: captura del panel.
- `validation/smoke-ok.txt`, `validation/gui-ok.txt`, `validation/corpus-ok.json`:
  marcadores de éxito y conteos de las pruebas de integración.
- `validation/plip-*/`: PDB exportado, informes y procedencia de cada análisis.

Los artefactos generados no se incluyen en el control de versiones. Los scripts
reproducibles están en `test/`; las pruebas del corpus requieren generar primero
los informes de las tres estructuras con PLIP (`-x --name report`).

## Pendiente antes de una publicación estable

- Validación de instalación y funcionamiento en Windows y Linux.
- Empaquetado autónomo del motor para eliminar el requisito previo de Conda.
- Exposición de modos avanzados y soporte más amplio de estructuras grandes.
- Persistencia del panel y tabla; actualmente se conserva la escena y se recarga XML.
- Validación de correspondencia de modelos para informes que contengan únicamente
  centros de grupos: la comprobación geométrica actual valida extremos atómicos,
  no centroides. En ese caso es imprescindible elegir el modelo correcto al cargar XML.

El wheel no ha sido publicado en el Toolshed público.
