#!/usr/bin/env python3
"""Levanta el sitio con los borradores incluidos, para verlo antes de ascender.

En la web solo sale lo que has ascendido a mano: Quartz se salta todo lo que
lleve `draft: true`. Eso esta bien para publicar y fatal para decidir, porque
justo lo que quieres ver antes de ascender una tanda es como va a quedar la
galeria con ella dentro, y sobre todo donde cae el corte del Top.

No toca ni `quartz.config.yaml` ni la vault. Copia el contenido fuera del repo,
le quita la linea `draft` a la copia y construye desde ahi, en su propio
puerto. Aunque se corte a medias, lo que se publica no se entera: la copia es
un callejon sin salida y no esta ni dentro del repositorio.

Uso:
  scripts/vistazo.py               levanta el sitio completo en el 8081
  scripts/vistazo.py --puerto 9000 en otro puerto
  scripts/vistazo.py --solo-build  construye y no levanta el servidor
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from mediateca import RAIZ, VAULT

# Fuera del repo a proposito, y no en una carpeta oculta de la raiz: el glob de
# Quartz se salta los directorios que empiezan por punto y ademas respeta el
# .gitignore, asi que una copia dentro y anotada ahi no se encontraria sola.
VISTAZO = Path(tempfile.gettempdir()) / "mediateca-vistazo"

PUERTO = 8081  # el 8080 lo usa `npx quartz build --serve`, el sitio de verdad

# Ni el estado local de Obsidian ni la papelera pintan nada en una copia.
FUERA = shutil.ignore_patterns(".obsidian", ".trash", ".git")

DRAFT_RE = re.compile(r"^draft:[ \t]*(?:true|True)[ \t]*\n", re.M)

AVISO = """
> [!warning] Esto es el vistazo, no el sitio publicado
> Aquí se ven **todas** las fichas, incluidas las que siguen en borrador. La web
> de verdad solo enseña las que has ascendido. Para ascender una, quítale la
> línea `draft: true`.

"""


def copiar_sin_draft():
    if VISTAZO.exists():
        shutil.rmtree(VISTAZO)
    destino = VISTAZO / "content"
    shutil.copytree(VAULT, destino, ignore=FUERA)

    destapadas = 0
    for md in destino.rglob("*.md"):
        limpio, quitadas = DRAFT_RE.subn("", md.read_text(encoding="utf-8"))
        if quitadas:
            md.write_text(limpio, encoding="utf-8")
            destapadas += quitadas

    portada = destino / "index.md"
    if portada.exists():
        texto = portada.read_text(encoding="utf-8")
        # Debajo de la cabecera, que si no se rompe el frontmatter.
        cierre = texto.find("\n---\n", 4) if texto.startswith("---\n") else -1
        corte = cierre + len("\n---\n") if cierre != -1 else 0
        portada.write_text(texto[:corte] + AVISO + texto[corte:], encoding="utf-8")
    return destapadas


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--puerto", type=int, default=PUERTO,
                   help=f"puerto del servidor (por defecto {PUERTO})")
    p.add_argument("--solo-build", action="store_true",
                   help="construye la copia y no levanta ningún servidor")
    args = p.parse_args()

    destapadas = copiar_sin_draft()
    print(f"Copia en {VISTAZO} con {destapadas} fichas en borrador destapadas.\n",
          flush=True)

    orden = ["npx", "quartz", "build",
             "-d", str(VISTAZO / "content"), "-o", str(VISTAZO / "public")]
    if not args.solo_build:
        orden += ["--serve", "--port", str(args.puerto),
                  # El de por defecto lo ocupa el servidor del sitio de verdad,
                  # asi que se pueden tener los dos abiertos a la vez.
                  "--wsPort", str(args.puerto + 920)]
        print(f"El vistazo estará en http://localhost:{args.puerto}  (Ctrl+C para salir)")
        print("Es una foto fija: si tocas una ficha, vuelve a lanzarlo.\n", flush=True)

    try:
        return subprocess.call(orden, cwd=RAIZ)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
