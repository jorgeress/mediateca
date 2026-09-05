#!/usr/bin/env python3
"""Junta las canciones favoritas de todos los discos en una pagina.

Una vista `.base` consulta **fichas**, no viñetas dentro de una ficha, asi que
"mis canciones favoritas" no puede ser una pestaña de `Musica.base` como lo son
"Galeria" o "Favoritos": las canciones no son fichas, son lineas dentro del
disco que las lleva. Esto las recoge y escribe la pagina.

La fuente sigue siendo la ficha del disco, que es donde se marcan: una estrella
al final de la linea de la cancion, en la lista que dejo `textos.py`. Para
añadir o quitar una favorita se toca el disco, nunca esta pagina, que se
reescribe entera en cada pasada.

De paso pone al dia el campo `favoritas` de cada disco, que es la cuenta de sus
estrellas, para que no se separe de lo que dice el cuerpo.

Uso:
  scripts/canciones.py            reescribe la pagina y pone al dia las cuentas
  scripts/canciones.py --dry-run  dice que pondria, sin tocar nada
"""

import argparse
import sys
from pathlib import Path

from textos import favoritas_escritas
from vitrina import FRONT_RE, VAULT, escribir_campos, frontmatter

PAGINA = VAULT / "Canciones favoritas.md"

CABECERA = """---
title: Canciones favoritas
---

Las canciones que he marcado con una estrella dentro de cada disco. Los discos
enteros que son favoritos están en [[Favoritos]] y en la pestaña «Favoritos» de
[[musica/index|Música]]; esto son las canciones sueltas.

Esta página la escribe `scripts/canciones.py` a partir de las fichas de los
discos: para añadir una, se le pone la ★ a la canción en su disco.
"""


def discos_con_favoritas():
    """Cada disco con sus canciones estrelladas, por orden de disco."""
    salida = []
    for md in sorted((VAULT / "musica").glob("*.md")):
        if md.stem == "index":
            continue
        texto = md.read_text(encoding="utf-8")
        campos = frontmatter(texto)
        suyas = favoritas_escritas(FRONT_RE.sub("", texto))
        if suyas:
            salida.append((md, campos, suyas))
    return salida


def tabla(discos):
    filas = ["| Canción | Disco | Artista |", "| --- | --- | --- |"]
    for md, campos, suyas in discos:
        for cancion in suyas:
            # El disco va como enlace para que Obsidian y Quartz lo conecten:
            # desde la cancion se llega a la ficha, y en el grafo se ve el haz.
            filas.append(f"| {cancion} | [[musica/{md.stem}\\|{md.stem}]] "
                         f"| {campos.get('autor') or ''} |")
    return "\n".join(filas)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="no escribe nada")
    args = p.parse_args()

    discos = discos_con_favoritas()
    total = sum(len(s) for _, _, s in discos)
    if not discos:
        print("Ningun disco tiene canciones marcadas con ★.")
        return 0

    for md, campos, suyas in discos:
        if str(campos.get("favoritas") or "") != str(len(suyas)):
            if args.dry_run:
                print(f"  ·  {md.stem}: favoritas {campos.get('favoritas')} -> {len(suyas)}")
            else:
                escribir_campos(md, {"favoritas": len(suyas)})
                print(f"  ✓  {md.stem}: favoritas al dia ({len(suyas)})")

    cuerpo = CABECERA + "\n" + tabla(discos) + "\n"
    if args.dry_run:
        print(f"\n  ·  escribiria {PAGINA.name} con {total} canciones "
              f"de {len(discos)} discos")
        return 0

    PAGINA.write_text(cuerpo, encoding="utf-8")
    print(f"\n{PAGINA.name}: {total} canciones de {len(discos)} discos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
