# Preparar la publicación de PLIP-Xplorer en GitHub

Esta entrega corresponde a **v1.0.0** y no presupone una dirección de repositorio.

## Contenido del repositorio

1. Descomprime `PLIP-Xplorer-1.0.0.zip`.
2. Crea un repositorio en tu cuenta con el nombre `PLIP-Xplorer`.
3. Sube **el contenido de la carpeta descomprimida**, para que `README.md` aparezca
   en la raíz y GitHub pueda mostrar el código. No subas solo el ZIP como único archivo.

La entrega incluye una carpeta `install/` con el wheel listo para instalar. No contiene
entornos Conda, cachés, resultados de análisis, configuraciones privadas ni rutas de
usuario específicas. El código del motor y sus ejemplos sí se incluyen para que el
script de instalación funcione desde una copia nueva del repositorio.

## Publicación descargable

1. En GitHub abre **Releases → Draft a new release**.
2. Crea la etiqueta `v1.0.0` y el título **PLIP-Xplorer 1.0.0**.
3. Adjunta:
   - `PLIP-Xplorer-1.0.0.zip` (fuentes, documentación y wheel).
   - `chimerax_plip_xplorer-1.0.0-py3-none-any.whl` (plugin independiente).

4. Describe la versión como experimental y probada en ChimeraX 1.12/macOS.
   Enlaza `INSTALLATION.md` en la descripción de la release.
5. Publica cuando hayas revisado los archivos y el texto de la release.

No confundas una release de GitHub con una publicación en el Toolshed de UCSF:
esta distribución usa un wheel local mediante `toolshed install`.

## Volver a generar la entrega

En ChimeraX:

```text
devel build "/ruta/PLIP-Xplorer/chimerax"
```

En una terminal, desde la raíz del proyecto:

```sh
python3 chimerax/package_release.py
```

El script comprueba que el wheel coincide con las fuentes, genera `release/`, copia
el wheel a `install/` y crea el ZIP junto a `SHA256SUMS.txt`. El ZIP incluye un
manifiesto SHA256 interno de todos sus archivos. Las carpetas de resultados y los
entornos locales se excluyen por una lista explícita de archivos y extensiones.
