"""Lo que comparten los scripts de la mediateca: rutas, fichas y peticiones."""

import json
import re
import time
import unicodedata
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VAULT = RAIZ / "content"
PORTADAS = VAULT / "assets" / "portadas"

# Carpeta de la vault -> valor del campo `tipo` de la ficha.
SECCIONES = {"juegos": "juego", "pelis": "peli", "libros": "libro", "musica": "album"}

UA = "mediateca/1.0 (https://github.com/jorgeress/mediateca)"

FRONT_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def pedir(url, headers=None, binario=False, datos=None, reintentos=3):
    cabeceras = {"User-Agent": UA, **(headers or {})}
    for intento in range(reintentos):
        try:
            req = urllib.request.Request(url, headers=cabeceras, data=datos)
            with urllib.request.urlopen(req, timeout=20) as r:
                cuerpo = r.read()
            return cuerpo if binario else json.loads(cuerpo)
        except Exception:
            if intento == reintentos - 1:
                return None
            time.sleep(1.5 * (intento + 1))
    return None


def frontmatter(texto):
    """Lee las claves planas de la cabecera. No hace falta un YAML completo."""
    m = FRONT_RE.match(texto)
    if not m:
        return {}
    campos = {}
    for linea in m.group(1).splitlines():
        if linea.startswith((" ", "-", "#")) or ":" not in linea:
            continue
        clave, _, valor = linea.partition(":")
        campos[clave.strip()] = valor.strip().strip('"').strip("'")
    return campos


def yaml_valor(v):
    if v is None or v == "":
        return ""
    if isinstance(v, str) and v.isdigit():
        return v
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if re.search(r'^[\s>|&*!%@`\[\]{}#-]|[:#]\s|["\']|^\d+$', v):
        return '"' + v.replace('"', r'\"') + '"'
    return v


def escribir_campos(md, valores):
    """Cambia o añade claves en la cabecera y deja el resto de la ficha igual.

    No se reescribe el YAML entero a proposito: asi se respetan el orden, los
    comentarios y lo que hayas puesto a mano, y un campo que no toca este
    diccionario no se mueve.
    """
    texto = md.read_text(encoding="utf-8")
    m = FRONT_RE.match(texto)
    if not m:
        return False
    cabecera = m.group(1)
    for clave, valor in valores.items():
        linea = f"{clave}: {yaml_valor(valor)}".rstrip()
        patron = rf"^{re.escape(clave)}:.*$"
        if re.search(patron, cabecera, re.M):
            cabecera = re.sub(patron, lambda _: linea, cabecera, count=1, flags=re.M)
        else:
            cabecera += "\n" + linea
    md.write_text(texto[:m.start(1)] + cabecera + texto[m.end(1):], encoding="utf-8")
    return True


def slug(nombre):
    base = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", base.lower())).strip("-")


def normal(s):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", s or "")
                  .encode("ascii", "ignore").decode().lower())


def nombre_de_fichero(titulo):
    """El titulo tal cual, sin lo que no admite un nombre de fichero."""
    limpio = re.sub(r'[/\\:*?"<>|]', " ", titulo)
    return re.sub(r"\s+", " ", limpio).strip(" .") or "sin titulo"
