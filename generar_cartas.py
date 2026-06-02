import argparse
import calendar
import csv
import json
import re
import shutil
import socket
import subprocess
import tempfile
import unicodedata
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
HOST = "127.0.0.1"
PORT = 8765
PERIODOS = ["2024-3", "2025-1", "2025-3", "2026-1"]
MESES = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]
CSV_COLUMNS = [
    "tipo",
    "fecha_carta",
    "nombre",
    "tiene_cedula",
    "cedula",
    "titulo",
    "director_trabajo",
    "estudiantes",
    "sustentacion_tipo",
    "fecha_sustentacion",
    "periodo",
]
CSV_CONTENT_COLUMNS = [
    "tipo",
    "nombre",
    "titulo",
    "director_trabajo",
    "estudiantes",
]


def latex_escape(value):
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in value.strip())


def latex_path(path):
    return path.resolve().as_posix()


def parse_date(value, label):
    try:
        year, month, day = [int(part) for part in value.split("-")]
        return date(year, month, day)
    except ValueError:
        shown = value or "(vacia)"
        raise ValueError(f"{label} debe ser una fecha valida en formato AAAA-MM-DD. Valor recibido: {shown}.")


def format_fecha_carta(fecha):
    return f"{MESES[fecha.month - 1]} {fecha.day} de {fecha.year}"


def format_fecha_sustentacion(fecha):
    return f"el {fecha.day} de {MESES[fecha.month - 1].lower()} de {fecha.year}"


def join_estudiantes(names):
    escaped = [rf"\textbf{{{latex_escape(name)}}}" for name in names]
    if len(escaped) == 1:
        return escaped[0]
    if len(escaped) == 2:
        return f"{escaped[0]} y {escaped[1]}"
    return f"{', '.join(escaped[:-1])} y {escaped[-1]}"


def slugify(value):
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "carta"


def clipped_slug(value, max_length=55):
    slug = slugify(value)
    if len(slug) <= max_length:
        return slug
    return slug[:max_length].rstrip("_") or "proyecto"


def person_code(name):
    parts = [slugify(part) for part in name.split() if slugify(part)]
    if not parts:
        return "Persona"
    first_initial = parts[0][0].upper()
    surname = next((part for part in reversed(parts[1:]) if len(part) > 1), parts[0])
    return first_initial + surname[:5].capitalize()


def available_pdf_path(destination, filename):
    candidate = destination / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    counter = 2
    while True:
        candidate = destination / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def has_project_title(value):
    normalized = value.strip().lower()
    return bool(normalized) and normalized not in {"no hay", "no_hay", "n/a", "na"}


def validate_payload(payload):
    tipo = payload.get("tipo", "").strip().lower()
    if tipo not in {"director", "jurado"}:
        raise ValueError("Selecciona si la carta es de director o de jurado.")

    fecha_carta = parse_date(payload.get("fechaCarta", ""), "La fecha de la carta")
    nombre = payload.get("nombre", "").strip()
    if not nombre:
        raise ValueError("El nombre del director o jurado es obligatorio.")

    tiene_cedula = bool(payload.get("tieneCedula"))
    cedula = payload.get("cedula", "").strip()
    if tiene_cedula and not cedula:
        raise ValueError("Escribe la cedula o desmarca la opcion de cedula disponible.")

    titulo = payload.get("titulo", "").strip()

    director_trabajo = payload.get("directorTrabajo", "").strip()
    if tipo == "jurado" and not director_trabajo:
        raise ValueError("El nombre del director del trabajo es obligatorio para cartas de jurado.")

    estudiantes = [item.strip() for item in payload.get("estudiantes", []) if item.strip()]
    if not estudiantes:
        raise ValueError("Debe haber minimo un estudiante.")

    sustentacion_tipo = payload.get("sustentacionTipo", "").strip()
    fecha_sustentacion = None
    periodo = payload.get("periodo", "").strip()
    if sustentacion_tipo == "fecha":
        fecha_sustentacion = parse_date(payload.get("fechaSustentacion", ""), "La fecha de sustentacion")
    elif sustentacion_tipo == "periodo":
        if periodo not in PERIODOS:
            raise ValueError("Selecciona un periodo valido.")
    else:
        raise ValueError("Selecciona si la sustentacion tiene fecha exacta o periodo.")

    return {
        "tipo": tipo,
        "fecha_carta": fecha_carta,
        "nombre": nombre,
        "tiene_cedula": tiene_cedula,
        "cedula": cedula,
        "titulo": titulo,
        "director_trabajo": director_trabajo,
        "estudiantes": estudiantes,
        "sustentacion_tipo": sustentacion_tipo,
        "fecha_sustentacion": fecha_sustentacion,
        "periodo": periodo,
    }


def parse_bool(value):
    normalized = str(value).strip().lower()
    return normalized in {"si", "sí", "s", "true", "1", "yes", "y"}


def csv_cell(row, column):
    value = row.get(column) or ""
    return " ".join(str(value).replace("\r", "").replace("\t", " ").split())


def csv_row_has_letter_content(row):
    return any(csv_cell(row, column) for column in CSV_CONTENT_COLUMNS)


def csv_row_to_payload(row):
    estudiantes = [
        item.strip()
        for item in csv_cell(row, "estudiantes").split(";")
        if item.strip()
    ]
    return {
        "tipo": csv_cell(row, "tipo"),
        "fechaCarta": csv_cell(row, "fecha_carta"),
        "nombre": csv_cell(row, "nombre"),
        "tieneCedula": parse_bool(csv_cell(row, "tiene_cedula")),
        "cedula": csv_cell(row, "cedula"),
        "titulo": csv_cell(row, "titulo"),
        "directorTrabajo": csv_cell(row, "director_trabajo"),
        "estudiantes": estudiantes,
        "sustentacionTipo": csv_cell(row, "sustentacion_tipo"),
        "fechaSustentacion": csv_cell(row, "fecha_sustentacion"),
        "periodo": csv_cell(row, "periodo"),
    }


def build_tex(data):
    rol = data["tipo"]
    nombre = latex_escape(data["nombre"])
    cedula = latex_escape(data["cedula"])
    titulo = latex_escape(data["titulo"]) if has_project_title(data["titulo"]) else ""
    director_trabajo = latex_escape(data["director_trabajo"])
    estudiantes = join_estudiantes(data["estudiantes"])
    fecha_carta = format_fecha_carta(data["fecha_carta"])

    cedula_text = ""
    if data["tiene_cedula"]:
        cedula_text = rf", identificado con cédula \textbf{{{cedula}}},"

    if data["sustentacion_tipo"] == "fecha":
        sustentacion = f"El trabajo fue sustentado {format_fecha_sustentacion(data['fecha_sustentacion'])}."
    else:
        sustentacion = f"El trabajo fue sustentado en el periodo {latex_escape(data['periodo'])}."

    director_text = ""
    if data["tipo"] == "jurado":
        director_text = rf", bajo la dirección del profesor \textbf{{{director_trabajo}}}"

    if titulo:
        project_text = rf"del Trabajo de Grado \textit{{``{titulo}''}}, realizado por los estudiantes {estudiantes}{director_text}"
    else:
        project_text = rf"de Trabajo de Grado de los estudiantes {estudiantes}{director_text}"

    logo = latex_path(ASSETS_DIR / "logo_javeriana.png")
    firma = latex_path(ASSETS_DIR / "firma_mariela.png")

    return rf"""\documentclass[letterpaper,12pt]{{article}}

\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage[spanish]{{babel}}
\usepackage{{graphicx}}
\usepackage{{xcolor}}
\usepackage{{geometry}}
\usepackage{{fancyhdr}}
\usepackage{{ragged2e}}
\usepackage{{parskip}}
\usepackage{{mathptmx}}

\definecolor{{javerianaBlue}}{{RGB}}{{0,91,145}}

\geometry{{
letterpaper,
left=0.79in,
right=1.18in,
top=1.45in,
bottom=1.15in,
headheight=1.38in,
headsep=0.08in,
footskip=0.82in
}}

\pagestyle{{fancy}}
\fancyhf{{}}
\renewcommand{{\headrulewidth}}{{0pt}}
\renewcommand{{\footrulewidth}}{{0pt}}

\fancyhead[L]{{%
\vspace{{0.08in}}%
\includegraphics[width=4.25in]{{{logo}}}%
}}

\fancyfoot[L]{{%
\raisebox{{0pt}}[0pt][0pt]{{%
\begin{{minipage}}[c]{{0.06in}}
{{\color{{javerianaBlue}}\rule{{0.8pt}}{{0.48in}}}}
\end{{minipage}}%
\hspace{{0.08in}}%
\begin{{minipage}}[c]{{5.4in}}
{{\footnotesize
Dirección, piso. Edificio - \textit{{Bogotá D.C., Colombia}}\\[-1pt]
Teléfono: +57 (1) 320 8320 Ext. 0000}}
\end{{minipage}}%
}}%
}}

\begin{{document}}

\fontsize{{13}}{{16}}\selectfont

\vspace*{{0.5in}}

\noindent\textbf{{Bogotá, Colombia}}\\
\textbf{{{fecha_carta}}}

\vspace{{0.55in}}

\noindent A quien pueda interesar,

\vspace{{0.16in}}

\justifying
\noindent Por medio de la presente se deja constancia de que \textbf{{{nombre}}}{cedula_text} fue {rol} {project_text}. {sustentacion}

\vspace{{2.25in}}

\noindent Atentamente,

\vspace{{0.08in}}

\noindent\includegraphics[width=1.7in]{{{firma}}}

\vspace{{0.12in}}

{{\fontsize{{10}}{{12}}\selectfont
\noindent\textbf{{Dra.\ Mariela J. Curiel H.}}\\
Directora de la Maestría de Ingeniería de Sistemas y Computación\\
Pontificia Universidad Javeriana, Bogotá.
}}

\end{{document}}
"""


def downloads_dir():
    home = Path.home()
    for name in ("Downloads", "Descargas"):
        candidate = home / name
        if candidate.exists():
            return candidate
    fallback = home / "Downloads"
    fallback.mkdir(exist_ok=True)
    return fallback


def compile_pdf(tex_path, output_pdf):
    pdflatex = shutil.which("pdflatex")
    tectonic = shutil.which("tectonic")
    if pdflatex:
        command = ["pdflatex", "-interaction=nonstopmode", tex_path.name]
        engine = "PDFLaTeX"
    elif tectonic:
        command = ["tectonic", tex_path.name]
        engine = "Tectonic"
    else:
        raise RuntimeError("No encontre pdflatex ni tectonic en el PATH. Instala Tectonic o una distribucion LaTeX para generar el PDF.")

    try:
        subprocess.run(
            command,
            cwd=tex_path.parent,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip()
        raise RuntimeError(f"{engine} reporto un error al compilar la carta.\n{detail[-1200:]}")

    generated_pdf = tex_path.with_suffix(".pdf")
    if not generated_pdf.exists():
        raise RuntimeError("PDFLaTeX termino, pero no se encontro el PDF generado.")
    shutil.copy2(generated_pdf, output_pdf)


def save_letter(payload, output_dir=None):
    data = validate_payload(payload)
    destination = output_dir or downloads_dir()
    destination.mkdir(parents=True, exist_ok=True)
    project_slug = clipped_slug(data["titulo"] if has_project_title(data["titulo"]) else "sin_titulo")
    filename = f"carta_{data['tipo']}_{person_code(data['nombre'])}_{project_slug}.pdf"
    pdf_path = available_pdf_path(destination, filename)

    with tempfile.TemporaryDirectory(prefix="carta_pg_") as temp_dir:
        tex_path = Path(temp_dir) / f"{pdf_path.stem}.tex"
        tex_path.write_text(build_tex(data), encoding="utf-8")
        compile_pdf(tex_path, pdf_path)

    return {"ok": True, "pdf": str(pdf_path)}


def create_csv_template(path):
    rows = [
        {
            "tipo": "director",
            "fecha_carta": "2026-02-26",
            "nombre": "Nombre del director",
            "tiene_cedula": "si",
            "cedula": "123456789",
            "titulo": "Titulo del proyecto de grado",
            "director_trabajo": "",
            "estudiantes": "Estudiante Uno; Estudiante Dos",
            "sustentacion_tipo": "fecha",
            "fecha_sustentacion": "2026-05-20",
            "periodo": "",
        },
        {
            "tipo": "jurado",
            "fecha_carta": "2026-02-26",
            "nombre": "Nombre del jurado",
            "tiene_cedula": "no",
            "cedula": "",
            "titulo": "Titulo del proyecto de grado",
            "director_trabajo": "Nombre del director del trabajo",
            "estudiantes": "Estudiante Uno",
            "sustentacion_tipo": "periodo",
            "fecha_sustentacion": "",
            "periodo": "2026-1",
        },
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def iter_csv_payloads(csv_path):
    if not csv_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        missing = [column for column in CSV_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Al CSV le faltan columnas: {', '.join(missing)}")

        for index, row in enumerate(reader, start=2):
            if index in (2, 3):
                yield index, "omitida", "ejemplo", None
                continue
            if not csv_row_has_letter_content(row):
                yield index, "omitida", "vacia", None
                continue
            try:
                payload = csv_row_to_payload(row)
                data = validate_payload(payload)
                yield index, "valida", payload, data
            except Exception as exc:
                yield index, "error", str(exc), None


def validate_batch(csv_path):
    valid = []
    errors = []
    omitted = []
    rows_seen = 0

    for index, status, detail, data in iter_csv_payloads(csv_path):
        rows_seen += 1
        if status == "omitida":
            omitted.append(index)
            print(f"Fila {index}: omitida ({detail})")
        elif status == "valida":
            valid.append(index)
            print(f"Fila {index}: OK -> {data['tipo']} | {data['nombre']}")
        else:
            errors.append(f"Fila {index}: {detail}")
            print(f"Fila {index}: ERROR -> {detail}")

    print()
    print(f"Filas leidas del CSV: {rows_seen}")
    print(f"Filas validas: {len(valid)}")
    print(f"Filas omitidas: {len(omitted)}")
    print(f"Errores: {len(errors)}")
    if errors:
        print("\nRevisa estas filas:")
        for error in errors:
            print(f"- {error}")
    return 1 if errors else 0


def generate_batch(csv_path):
    generated = []
    errors = []
    omitted = []
    rows_seen = 0

    for index, status, detail, data in iter_csv_payloads(csv_path):
        rows_seen += 1
        if status == "omitida":
            omitted.append(index)
            print(f"Fila {index}: omitida ({detail})")
        elif status == "error":
            errors.append(f"Fila {index}: {detail}")
            print(f"Fila {index}: ERROR -> {detail}")
        else:
            try:
                folder = "Cartas Directores" if data["tipo"] == "director" else "Cartas Jurados"
                result = save_letter(detail, downloads_dir() / folder)
                generated.append(result["pdf"])
                print(f"Fila {index}: PDF generado -> {result['pdf']}")
            except Exception as exc:
                errors.append(f"Fila {index}: {exc}")
                print(f"Fila {index}: ERROR -> {exc}")

    print()
    print(f"Filas leidas del CSV: {rows_seen}")
    print(f"Cartas generadas: {len(generated)}")
    print(f"Filas omitidas: {len(omitted)}")
    print(f"Errores: {len(errors)}")
    if errors:
        print("\nRevisa estas filas:")
        for error in errors:
            print(f"- {error}")
    return 1 if errors else 0


def find_available_port(start_port=PORT):
    for port in range(start_port, start_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((HOST, port))
            except OSError:
                continue
            return port
    raise RuntimeError("No se encontro un puerto disponible para abrir la interfaz.")


HTML = r"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Generador de cartas</title>
  <style>
    :root {
      --blue: #005b91;
      --blue-dark: #004a78;
      --border: #d7e0e7;
      --text: #17202a;
      --muted: #52616b;
      --bg: #f5f8fb;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    header {
      background: white;
      border-bottom: 4px solid var(--blue);
    }
    .brand {
      max-width: 980px;
      margin: 0 auto;
      padding: 18px 22px;
      display: flex;
      align-items: center;
      gap: 18px;
    }
    .brand img { width: min(360px, 58vw); height: auto; }
    main {
      max-width: 980px;
      margin: 0 auto;
      padding: 24px 22px 40px;
    }
    form {
      background: white;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 22px;
      display: grid;
      gap: 18px;
    }
    fieldset {
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      margin: 0;
    }
    legend {
      color: var(--blue);
      font-weight: 700;
      padding: 0 6px;
    }
    label {
      display: block;
      font-weight: 700;
      margin-bottom: 6px;
    }
    .required::after {
      content: " *";
      color: var(--blue);
    }
    input, select {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 10px 12px;
      font: inherit;
      background: white;
    }
    input:focus, select:focus {
      outline: 2px solid rgba(0, 91, 145, 0.18);
      border-color: var(--blue);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }
    .inline {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 14px;
    }
    .choice {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      font-weight: 400;
      margin: 0;
    }
    .choice input {
      width: auto;
      margin: 0;
    }
    .student-row {
      display: grid;
      grid-template-columns: 1fr 42px;
      gap: 8px;
      margin-top: 8px;
    }
    button {
      border: 1px solid var(--blue);
      border-radius: 6px;
      padding: 10px 14px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      color: var(--blue);
      background: white;
    }
    button:hover { background: #edf6fb; }
    .primary {
      background: var(--blue);
      color: white;
      padding: 12px 18px;
    }
    .primary:hover { background: var(--blue-dark); }
    .icon {
      min-width: 42px;
      padding-inline: 0;
      font-size: 18px;
      line-height: 1;
    }
    .actions {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: center;
      flex-wrap: wrap;
    }
    .hint {
      color: var(--muted);
      font-size: 14px;
      margin: 6px 0 0;
    }
    .status {
      border-radius: 8px;
      padding: 12px 14px;
      display: none;
      white-space: pre-wrap;
    }
    .status.ok {
      display: block;
      border: 1px solid #8bc7a2;
      background: #eefaf2;
    }
    .status.error {
      display: block;
      border: 1px solid #e2a2a2;
      background: #fff0f0;
    }
    @media (max-width: 720px) {
      .grid { grid-template-columns: 1fr; }
      form { padding: 16px; }
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <img src="/assets/logo_javeriana.png" alt="Pontificia Universidad Javeriana">
    </div>
  </header>
  <main>
    <form id="form">
      <fieldset>
        <legend>Tipo de carta</legend>
        <div class="inline">
          <label class="choice"><input type="radio" name="tipo" value="director" checked> Director</label>
          <label class="choice"><input type="radio" name="tipo" value="jurado"> Jurado</label>
        </div>
      </fieldset>

      <div class="grid">
        <div>
          <label class="required" for="fechaCarta">Fecha de la carta</label>
          <input id="fechaCarta" name="fechaCarta" type="date" required>
          <p class="hint">Se escribira como: Febrero 26 de 2026.</p>
        </div>
        <div>
          <label class="required" for="nombre" id="nombreLabel">Nombre del director</label>
          <input id="nombre" name="nombre" required>
        </div>
      </div>

      <fieldset>
        <legend>Cedula</legend>
        <label class="choice"><input id="tieneCedula" type="checkbox" checked> Tengo la cedula disponible</label>
        <div style="margin-top: 10px;">
          <label for="cedula">Cedula</label>
          <input id="cedula" name="cedula">
        </div>
      </fieldset>

      <div>
        <label for="titulo">Titulo del proyecto</label>
        <input id="titulo" name="titulo">
        <p class="hint">Opcional. Si no hay titulo, puedes dejarlo vacio.</p>
      </div>

      <div id="directorTrabajoBox" hidden>
        <label class="required" for="directorTrabajo">Director del trabajo de grado</label>
        <input id="directorTrabajo" name="directorTrabajo">
      </div>

      <fieldset>
        <legend>Estudiantes</legend>
        <div id="students"></div>
        <button type="button" id="addStudent">+ Agregar estudiante</button>
        <p class="hint">Debe haber minimo un estudiante.</p>
      </fieldset>

      <fieldset>
        <legend>Sustentacion</legend>
        <div class="inline">
          <label class="choice"><input type="radio" name="sustentacionTipo" value="fecha" checked> Fecha exacta</label>
          <label class="choice"><input type="radio" name="sustentacionTipo" value="periodo"> Periodo</label>
        </div>
        <div class="grid" style="margin-top: 12px;">
          <div id="fechaSustBox">
            <label for="fechaSustentacion">Fecha de sustentacion</label>
            <input id="fechaSustentacion" type="date">
          </div>
          <div id="periodoBox" hidden>
            <label for="periodo">Periodo</label>
            <select id="periodo">
              <option>2024-3</option>
              <option>2025-1</option>
              <option>2025-3</option>
              <option>2026-1</option>
            </select>
          </div>
        </div>
      </fieldset>

      <div class="actions">
        <p class="hint">El PDF se guardara en la carpeta Descargas del computador.</p>
        <button class="primary" type="submit">Generar PDF</button>
      </div>
      <div id="status" class="status"></div>
    </form>
  </main>
  <script>
    const form = document.querySelector("#form");
    const students = document.querySelector("#students");
    const addStudent = document.querySelector("#addStudent");
    const tipoInputs = document.querySelectorAll("input[name='tipo']");
    const nombreLabel = document.querySelector("#nombreLabel");
    const tieneCedula = document.querySelector("#tieneCedula");
    const cedula = document.querySelector("#cedula");
    const directorTrabajoBox = document.querySelector("#directorTrabajoBox");
    const directorTrabajo = document.querySelector("#directorTrabajo");
    const sustentacionInputs = document.querySelectorAll("input[name='sustentacionTipo']");
    const fechaSustBox = document.querySelector("#fechaSustBox");
    const periodoBox = document.querySelector("#periodoBox");
    const fechaCarta = document.querySelector("#fechaCarta");
    const fechaSustentacion = document.querySelector("#fechaSustentacion");
    const statusBox = document.querySelector("#status");

    const today = new Date().toISOString().slice(0, 10);
    fechaCarta.value = today;
    fechaSustentacion.value = today;

    function setStatus(kind, message) {
      statusBox.className = `status ${kind}`;
      statusBox.textContent = message;
    }

    function addStudentRow(value = "") {
      const row = document.createElement("div");
      row.className = "student-row";
      const input = document.createElement("input");
      input.type = "text";
      input.placeholder = "Nombre del estudiante";
      input.required = true;
      input.value = value;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "icon";
      remove.textContent = "-";
      remove.title = "Quitar estudiante";
      remove.addEventListener("click", () => {
        if (students.querySelectorAll("input").length === 1) {
          setStatus("error", "Debe haber minimo un estudiante.");
          return;
        }
        row.remove();
      });
      row.append(input, remove);
      students.append(row);
    }

    function selectedRadio(name) {
      return document.querySelector(`input[name='${name}']:checked`).value;
    }

    function updateRole() {
      const isDirector = selectedRadio("tipo") === "director";
      nombreLabel.textContent = isDirector ? "Nombre del director" : "Nombre del jurado";
      directorTrabajoBox.hidden = isDirector;
      directorTrabajo.required = !isDirector;
      if (isDirector) directorTrabajo.value = "";
    }

    function updateCedula() {
      cedula.disabled = !tieneCedula.checked;
      if (!tieneCedula.checked) cedula.value = "";
    }

    function updateSustentacion() {
      const byDate = selectedRadio("sustentacionTipo") === "fecha";
      fechaSustBox.hidden = !byDate;
      periodoBox.hidden = byDate;
      fechaSustentacion.required = byDate;
    }

    tipoInputs.forEach(input => input.addEventListener("change", updateRole));
    sustentacionInputs.forEach(input => input.addEventListener("change", updateSustentacion));
    tieneCedula.addEventListener("change", updateCedula);
    addStudent.addEventListener("click", () => addStudentRow());

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const estudiantes = Array.from(students.querySelectorAll("input")).map(input => input.value.trim()).filter(Boolean);
      const payload = {
        tipo: selectedRadio("tipo"),
        fechaCarta: fechaCarta.value,
        nombre: document.querySelector("#nombre").value.trim(),
        tieneCedula: tieneCedula.checked,
        cedula: cedula.value.trim(),
        titulo: document.querySelector("#titulo").value.trim(),
        directorTrabajo: directorTrabajo.value.trim(),
        estudiantes,
        sustentacionTipo: selectedRadio("sustentacionTipo"),
        fechaSustentacion: fechaSustentacion.value,
        periodo: document.querySelector("#periodo").value,
      };

      try {
        const response = await fetch("/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) {
          setStatus("error", result.error || "No se pudo generar la carta.");
          return;
        }
        setStatus("ok", `PDF guardado en Descargas:\n${result.pdf}`);
      } catch (error) {
        setStatus("error", "No se pudo conectar con el script local.");
      }
    });

    addStudentRow();
    updateRole();
    updateCedula();
    updateSustentacion();
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def send_text(self, body, status=200, content_type="text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload, status=200):
        self.send_text(json.dumps(payload, ensure_ascii=False), status, "application/json; charset=utf-8")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self.send_text(HTML)
            return
        if path == "/assets/logo_javeriana.png":
            data = (ASSETS_DIR / "logo_javeriana.png").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_json({"ok": False, "error": "Ruta no encontrada."}, 404)

    def do_POST(self):
        if urlparse(self.path).path != "/generate":
            self.send_json({"ok": False, "error": "Ruta no encontrada."}, 404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            result = save_letter(payload)
            self.send_json(result)
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, 400)
        except Exception as exc:
            self.send_json({"ok": False, "error": f"Error inesperado: {exc}"}, 500)

    def log_message(self, format, *args):
        return


def run_server():
    port = find_available_port()
    url = f"http://{HOST}:{port}"
    server = ThreadingHTTPServer((HOST, port), Handler)
    print(f"Generador de cartas abierto en {url}")
    print("Presiona Ctrl+C para detenerlo.")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")


def main():
    parser = argparse.ArgumentParser(description="Generador de cartas de proyecto de grado.")
    parser.add_argument("--lote", type=Path, help="Genera PDFs desde un archivo CSV.")
    parser.add_argument("--validar", type=Path, help="Valida un CSV sin generar PDFs.")
    parser.add_argument("--crear-plantilla", type=Path, help="Crea una plantilla CSV editable en Excel.")
    args = parser.parse_args()

    if args.crear_plantilla:
        create_csv_template(args.crear_plantilla)
        print(f"Plantilla creada: {args.crear_plantilla}")
        return

    if args.lote:
        raise SystemExit(generate_batch(args.lote))

    if args.validar:
        raise SystemExit(validate_batch(args.validar))

    run_server()


if __name__ == "__main__":
    main()
