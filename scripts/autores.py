#!/usr/bin/env python3
"""Conecta las fichas que comparten estudio, direccion o artista.

Obsidian agrupa por enlaces, no por campos: dos juegos con `autor: FromSoftware`
escrito igual no estan conectados de ninguna manera, ni en el grafo ni en los
backlinks. Con `autor: "[[autores/FromSoftware, Inc.|FromSoftware, Inc.]]"` si:
la pagina del estudio lista lo suyo, el grafo dibuja el haz y desde una ficha se
llega a las hermanas.

**Solo se enlaza a quien tenga dos obras o mas** (`--minimo`). Con una sola, el
enlace lleva a una pagina que no agrupa nada, y son 92 autores para 90 fichas:
el sitio doblaria de tamaño en paginas muertas. Al crecer la coleccion basta con
volver a pasarlo y el que llegue a dos se enlaza solo.

Las paginas de `content/autores/` las escribe esto entero en cada pasada, asi
que no se editan a mano. Lo que si es tuyo es el campo `autor` de cada ficha:
aqui solo se le pone o se le quita el enlace alrededor, nunca se cambia el
nombre.

Ojo: `datos.py` reescribe `autor` desde Steam y Letterboxd en texto plano. Si lo
pasas despues, vuelve a pasar esto para volver a enlazar.

Uso:
  scripts/autores.py             enlaza y reescribe las paginas de autor
  scripts/autores.py --minimo 1  enlaza a todos, tengan una obra o veinte
  scripts/autores.py --deshacer  quita los enlaces y deja el nombre pelado
  scripts/autores.py --dry-run   dice que haria, sin tocar nada
"""

import argparse
import re
import shutil
import sys
from collections import defaultdict

from vitrina import (SECCIONES, VAULT, escribir_campos, frontmatter,
                     nombre_de_fichero)

AUTORES = VAULT / "autores"

# Un `autor` ya enlazado: "[[autores/X|X]]". Se lee para poder volver a pasar
# el script sin acabar con enlaces dentro de enlaces.
ENLACE_RE = re.compile(r"\[\[autores/[^|\]]+\|([^\]]+)\]\]")

# Trozos que son el final de un nombre de empresa y no un autor aparte: sin
# esto, "FromSoftware, Inc." se parte en dos y "Inc." acaba siendo el estudio
# con mas juegos de la coleccion.
SUFIJOS = ("inc.", "inc", "ltd.", "ltd", "llc", "co.", "corp.", "gmbh",
           "s.a.", "s.l.", "b.v.", "pty", "ab", "oy")


def separar(valor):
    """El campo `autor` -> la lista de personas o estudios que nombra.

    La coma no basta como separador porque significa las dos cosas:
    "Mike Johnson, Tim Burton" son dos directores y "FromSoftware, Inc." es un
    solo estudio. Lo que decide es si el trozo de despues es un sufijo de
    empresa, en cuyo caso se vuelve a pegar al anterior.
    """
    valor = ENLACE_RE.sub(r"\1", valor or "").strip()
    if not valor:
        return []
    partes = []
    for trozo in [t.strip() for t in valor.split(",")]:
        if not trozo:
            continue
        if partes and trozo.lower().rstrip(".") in [s.rstrip(".") for s in SUFIJOS]:
            partes[-1] += ", " + trozo
        else:
            partes.append(trozo)
    return partes


def fichas():
    for carpeta, tipo in SECCIONES.items():
        for md in sorted((VAULT / carpeta).glob("*.md")):
            if md.stem == "index":
                continue
            campos = frontmatter(md.read_text(encoding="utf-8"))
            yield md, carpeta, tipo, campos


def obras_por_autor():
    mapa = defaultdict(list)
    for md, carpeta, _, campos in fichas():
        for autor in separar(campos.get("autor")):
            mapa[autor].append((carpeta, md.stem, campos.get("year") or ""))
    return mapa


def pagina(autor, obras):
    lineas = [f'---\ntitle: "{autor}"\ntipo: autor\n---\n',
              # Sin el punto si el nombre ya acaba en uno: "FromSoftware, Inc.."
              f"Lo que tengo de {autor}{'' if autor.endswith('.') else '.'}\n"]
    for carpeta, nombre, year in sorted(obras, key=lambda o: (o[0], o[1])):
        año = f" ({year})" if year else ""
        lineas.append(f"- [[{carpeta}/{nombre}|{nombre}]]{año}")
    lineas.append("\nEsta página la escribe `scripts/autores.py`.\n")
    return "\n".join(lineas)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--minimo", type=int, default=2,
                   help="obras que hacen falta para tener pagina (por defecto 2)")
    p.add_argument("--deshacer", action="store_true", help="quita todos los enlaces")
    p.add_argument("--dry-run", action="store_true", help="no escribe nada")
    args = p.parse_args()

    mapa = obras_por_autor()
    enlazables = ({} if args.deshacer
                  else {a: o for a, o in mapa.items() if len(o) >= args.minimo})

    # Las fichas: se les pone o se les quita el enlace, nunca se cambia el nombre.
    tocadas = 0
    for md, _, _, campos in fichas():
        partes = separar(campos.get("autor"))
        if not partes:
            continue
        nuevo = ", ".join(
            f"[[autores/{nombre_de_fichero(a)}|{a}]]" if a in enlazables else a
            for a in partes)
        if nuevo == (campos.get("autor") or ""):
            continue
        tocadas += 1
        if args.dry_run:
            print(f"  ·  {md.parent.name}/{md.stem}: {campos.get('autor')} -> {nuevo}")
        else:
            escribir_campos(md, {"autor": nuevo})

    if args.dry_run:
        print(f"\n  ·  {tocadas} fichas, {len(enlazables)} paginas de autor")
        return 0

    # Las paginas se reescriben enteras: son derivadas, no fuente.
    if AUTORES.exists():
        shutil.rmtree(AUTORES)
    if enlazables:
        AUTORES.mkdir(parents=True)
        for autor, obras in enlazables.items():
            destino = AUTORES / f"{nombre_de_fichero(autor)}.md"
            destino.write_text(pagina(autor, obras), encoding="utf-8")

    print(f"{tocadas} fichas actualizadas, {len(enlazables)} páginas de autor.")
    if not args.deshacer:
        sueltos = len(mapa) - len(enlazables)
        print(f"{sueltos} autores con menos de {args.minimo} obras se quedan "
              f"en texto, sin enlace.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
