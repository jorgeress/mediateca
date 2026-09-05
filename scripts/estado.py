#!/usr/bin/env python3
"""Cómo va Vitrina: qué hay, qué falta y qué se publica.

Las galerias enseñan lo que hay. Esto enseña lo que **no** hay, que es lo que
hace falta para saber por donde seguir: cuantas fichas siguen en borrador, a
cuales les falta la nota o el texto, y cuantas verian de verdad los visitantes.

No consulta nada por red ni escribe nada: solo lee la vault. Se puede lanzar
tantas veces como quieras.

Uso:
  scripts/estado.py                  el resumen
  scripts/estado.py --seccion pelis  solo esa carpeta
  scripts/estado.py --detalle        ademas, que ficha le falta cada cosa
"""

import argparse
import re
import sys
from collections import Counter, defaultdict

from vitrina import (FRONT_RE, PORTADAS, SECCIONES, VAULT, frontmatter, vacio)

# Los que hacen falta para que una ficha este completa de verdad.
CAMPOS = ("year", "autor", "nota", "portada", "tags")

# En assets/portadas/ vive tambien el .gitkeep, que no es una caratula huerfana.
IMAGENES = {".webp", ".jpg", ".jpeg", ".png", ".gif", ".avif"}

def leer(carpeta):
    """Cada ficha de la carpeta: sus campos, si es borrador y si tiene texto."""
    for md in sorted((VAULT / carpeta).glob("*.md")):
        if md.stem == "index":
            continue
        texto = md.read_text(encoding="utf-8")
        m = FRONT_RE.match(texto)
        if not m:
            continue
        yield md, frontmatter(texto), texto[m.end():].strip()


def barra(hechas, total, ancho=24):
    if not total:
        return " " * ancho
    llenas = round(ancho * hechas / total)
    return "█" * llenas + "·" * (ancho - llenas)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seccion", choices=list(SECCIONES), help="solo una carpeta")
    p.add_argument("--detalle", action="store_true",
                   help="lista las fichas a las que les falta algo")
    args = p.parse_args()

    carpetas = [args.seccion] if args.seccion else list(SECCIONES)
    total = Counter()
    borrador = Counter()
    con_texto = Counter()
    faltan = defaultdict(list)
    notas = Counter()
    favoritos = Counter()
    portadas_usadas = set()
    rotas = []

    for carpeta in carpetas:
        for md, campos, cuerpo in leer(carpeta):
            total[carpeta] += 1
            if campos.get("draft") == "true":
                borrador[carpeta] += 1
            if cuerpo:
                con_texto[carpeta] += 1
            else:
                faltan["texto"].append(f"{carpeta}/{md.stem}")
            for campo in CAMPOS:
                if vacio(campos.get(campo)):
                    faltan[campo].append(f"{carpeta}/{md.stem}")
            if campos.get("nota"):
                notas[int(campos["nota"])] += 1
            if campos.get("favorito") == "true":
                favoritos[carpeta] += 1
            apuntada = re.sub(r"^\[\[|\]\]$", "", campos.get("portada") or "")
            if apuntada:
                portadas_usadas.add(apuntada)
                if not (PORTADAS / apuntada).exists():
                    rotas.append(f"{carpeta}/{md.stem} -> {apuntada}")

    hay = sum(total.values())
    if not hay:
        print("No hay ninguna ficha todavía.")
        return 0
    publicadas = hay - sum(borrador.values())

    print("FICHAS")
    print(f"  {'':10} {'total':>6} {'borrador':>9} {'publicadas':>11} {'con texto':>10}")
    for carpeta in carpetas:
        print(f"  {carpeta:10} {total[carpeta]:>6} {borrador[carpeta]:>9} "
              f"{total[carpeta] - borrador[carpeta]:>11} {con_texto[carpeta]:>10}")
    print(f"  {'':10} {'—' * 6:>6} {'—' * 9:>9} {'—' * 11:>11} {'—' * 10:>10}")
    print(f"  {'total':10} {hay:>6} {sum(borrador.values()):>9} "
          f"{publicadas:>11} {sum(con_texto.values()):>10}")

    print(f"\nEN LA WEB  {barra(publicadas, hay)}  {publicadas} de {hay}")
    if not publicadas:
        print("  Ninguna. Quartz se salta lo que lleva `draft: true`; en Obsidian se")
        print("  ven todas. Para ascender una, quítale esa línea.")

    print("\nSIN RELLENAR")
    for campo in CAMPOS + ("texto",):
        cuantas = len(faltan[campo])
        if cuantas:
            print(f"  {campo:10} {cuantas:>4}   {barra(hay - cuantas, hay)}")
            if args.detalle:
                for ficha in faltan[campo]:
                    print(f"             · {ficha}")
    if not any(faltan.values()):
        print("  Nada. Están todas completas.")

    if notas:
        print("\nNOTAS      " + "  ".join(f"{n}:{c}" for n, c in
                                          sorted(notas.items(), reverse=True)))

    # Favoritos.base junta las cuatro secciones y cada .base tiene ademas su
    # vista "Solo favoritos". Si aqui sale 0, esas paginas salen vacias.
    print(f"\nFAVORITOS  {barra(sum(favoritos.values()), hay)}  "
          f"{sum(favoritos.values())} de {hay}")
    for carpeta in carpetas:
        print(f"  {carpeta:10} {favoritos[carpeta]:>4}")
    if not sum(favoritos.values()):
        print("  Ninguna. Favoritos.base y las vistas «Solo favoritos» salen vacías")
        print("  hasta que alguna ficha lleve `favorito: true`.")

    # Solo con la vault entera tiene sentido: con --seccion sobran las de las otras.
    if not args.seccion:
        sueltas = sorted(p.name for p in PORTADAS.glob("*")
                         if p.is_file() and p.suffix.lower() in IMAGENES
                         and p.name not in portadas_usadas)
        if sueltas or rotas:
            print("\nPORTADAS")
            if rotas:
                print(f"  {len(rotas)} ficha(s) apuntan a una imagen que no está:")
                for r in rotas:
                    print(f"    ✗ {r}")
            if sueltas:
                print(f"  {len(sueltas)} imagen(es) que ya no usa ninguna ficha:")
                for s in sueltas if args.detalle else sueltas[:5]:
                    print(f"    · {s}")
                if not args.detalle and len(sueltas) > 5:
                    print(f"    … y {len(sueltas) - 5} más (--detalle las lista)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
