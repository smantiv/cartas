# Generar muchas cartas desde Excel

Usa `plantilla_cartas.csv` como base. Puedes abrirlo en Excel, Numbers o Google Sheets.

Cada fila genera una carta PDF.

El modo masivo omite automaticamente las dos primeras filas de ejemplo y tambien omite filas vacias, incluso si Excel dejo valores sueltos como `no` en alguna celda.

## Columnas

- `tipo`: escribe `director` o `jurado`.
- `fecha_carta`: obligatoria, formato `AAAA-MM-DD`, por ejemplo `2026-02-26`.
- `nombre`: nombre del director o jurado.
- `tiene_cedula`: escribe `si` o `no`.
- `cedula`: solo se usa si `tiene_cedula` es `si`.
- `titulo`: opcional. Si no hay titulo, escribe `NO HAY` o deja la celda vacia.
- `director_trabajo`: obligatorio solo cuando `tipo` es `jurado`.
- `estudiantes`: uno o varios nombres separados por punto y coma: `Ana Perez; Juan Gomez`.
- `sustentacion_tipo`: escribe `fecha` o `periodo`.
- `fecha_sustentacion`: formato `AAAA-MM-DD`, solo si `sustentacion_tipo` es `fecha`.
- `periodo`: solo si `sustentacion_tipo` es `periodo`. Valores permitidos: `2024-3`, `2025-1`, `2025-3`, `2026-1`.

## Comandos

Para revisar el CSV sin generar PDFs:

```bash
cd /Users/sofiamantilla/Documents/cartas
python3 generar_cartas.py --validar plantilla_cartas.csv
```

Para generar todos los PDFs:

```bash
cd /Users/sofiamantilla/Documents/cartas
python3 generar_cartas.py --lote plantilla_cartas.csv
```

Los PDFs se guardan en la carpeta Descargas del computador, separados asi:

- `Descargas/Cartas Directores`
- `Descargas/Cartas Jurados`

Para crear otra plantilla vacia con ejemplos:

```bash
python3 generar_cartas.py --crear-plantilla nueva_plantilla.csv
```

Importante: para generar PDFs necesitas tener `tectonic` o `pdflatex` instalado.
