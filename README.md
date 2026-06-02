# Generador de Cartas de Proyecto de Grado 🎓

Autora: **Sofia Carolina Mantilla**  
Fecha: **junio 1, 2026**

Este proyecto genera cartas PDF para directores y jurados de proyectos de grado. Se puede usar de dos formas:

- 🧾 **Generación por lote** desde un archivo CSV.
- 🖥️ **Interfaz web local** para generar una carta manualmente.

---

## ¿Qué necesitas instalar? ✅

### 1. Python

En macOS normalmente ya tienes Python instalado. Verifica con:

```bash
python3 --version
```

### 2. Tectonic o LaTeX

Para convertir las cartas a PDF necesitas un compilador LaTeX. La opción más sencilla es **Tectonic**:

```bash
brew install tectonic
```

Verifica que quedó instalado:

```bash
tectonic --version
```

También funciona si tienes `pdflatex` instalado.

---

## Archivos importantes 📁

```text
generar_cartas.py        Script principal
plantilla_cartas.csv     Archivo para generar cartas por lote
assets/                  Logos, firma e imágenes usadas en las cartas
INSTRUCCIONES_LOTE.md    Instrucciones rápidas del modo lote
```

Los PDFs se guardan en tu carpeta de Descargas:

```text
Downloads/Cartas Directores
Downloads/Cartas Jurados
```

---

## Cómo validar el CSV sin generar PDFs 🔍

Antes de generar cartas, es recomendable validar el CSV:

```bash
cd /Users/sofiamantilla/Documents/cartas
python3 generar_cartas.py --validar plantilla_cartas.csv
```

Esto revisa:

- fechas inválidas;
- campos obligatorios vacíos;
- tipos de carta incorrectos;
- filas vacías;
- filas de ejemplo.

Si todo está bien, verás algo como:

```text
Filas validas: 51
Errores: 0
```

---

## Cómo generar PDFs por lote 🧾

Cuando el CSV ya esté validado:

```bash
cd /Users/sofiamantilla/Documents/cartas
python3 generar_cartas.py --lote plantilla_cartas.csv
```

El script:

- omite las primeras 2 filas de ejemplo;
- omite filas vacías;
- genera cartas de directores en `Downloads/Cartas Directores`;
- genera cartas de jurados en `Downloads/Cartas Jurados`.

Los archivos se nombran de forma legible, por ejemplo:

```text
carta_jurado_SManti_nombre_del_proyecto.pdf
```

Si ya existe un archivo con el mismo nombre, agrega `_2`, `_3`, etc.

---

## Cómo usar la interfaz web local 🖥️

También puedes abrir una interfaz para crear una carta manual:

```bash
cd /Users/sofiamantilla/Documents/cartas
python3 generar_cartas.py
```

El navegador se abrirá automáticamente. Si no se abre, mira la URL que aparece en la terminal, normalmente algo como:

```text
http://127.0.0.1:8765
```

Desde ahí puedes llenar los datos de una carta y generar el PDF.

Para detener la interfaz, vuelve a la terminal y presiona:

```text
Ctrl + C
```

---

## Cómo llenar `plantilla_cartas.csv` 📝

El CSV debe tener estas columnas exactas:

```text
tipo,fecha_carta,nombre,tiene_cedula,cedula,titulo,director_trabajo,estudiantes,sustentacion_tipo,fecha_sustentacion,periodo
```

### Columnas

- `tipo`: `director` o `jurado`.
- `fecha_carta`: fecha de la carta en formato `AAAA-MM-DD`.
- `nombre`: nombre del director o jurado.
- `tiene_cedula`: `si` o `no`.
- `cedula`: solo se llena si `tiene_cedula` es `si`.
- `titulo`: título del proyecto. Si no hay título, escribe `NO HAY`.
- `director_trabajo`: obligatorio para cartas de jurado; vacío para director.
- `estudiantes`: nombres separados por punto y coma si hay varios.
- `sustentacion_tipo`: `fecha` o `periodo`.
- `fecha_sustentacion`: obligatoria si `sustentacion_tipo` es `fecha`.
- `periodo`: se usa si `sustentacion_tipo` es `periodo`.

Ejemplo con varios estudiantes:

```text
Ana Pérez; Juan Gómez; María López
```

---

## Crear una plantilla nueva 🧩

Si quieres crear otro CSV base:

```bash
cd /Users/sofiamantilla/Documents/cartas
python3 generar_cartas.py --crear-plantilla nueva_plantilla.csv
```

---

## Errores comunes 🛠️

### `No encontre pdflatex ni tectonic`

Instala Tectonic:

```bash
brew install tectonic
```

### `La fecha de la carta debe ser una fecha valida`

Usa formato:

```text
AAAA-MM-DD
```

Ejemplo correcto:

```text
2026-06-01
```

Ejemplo incorrecto:

```text
2026-02-30
```

### El script no ve filas nuevas del CSV

Guarda el archivo antes de correr el script. Si editas en Excel o Numbers, exporta nuevamente como CSV y reemplaza `plantilla_cartas.csv`.

### El PDF no aparece

Revisa las carpetas:

```text
~/Downloads/Cartas Directores
~/Downloads/Cartas Jurados
```

---

## Flujo recomendado 🌟

1. Edita `plantilla_cartas.csv`.
2. Guarda el archivo.
3. Valida:

```bash
python3 generar_cartas.py --validar plantilla_cartas.csv
```

4. Si no hay errores, genera:

```bash
python3 generar_cartas.py --lote plantilla_cartas.csv
```

5. Revisa los PDFs en Descargas.

