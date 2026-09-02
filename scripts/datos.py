#!/usr/bin/env python3
"""Rellena los campos que el importador no podia saber.

Ninguna fuente lo da todo. Tu pagina de juegos de Steam sabe cuanto has jugado,
pero no dice ni de que año es el juego ni quien lo hizo, asi que lo importado
entra con `year` y `autor` en blanco. Aqui se completan yendo a la ficha de la
tienda por el `appid` que el importador ya dejo guardado en cada nota, que es
mas fiable que buscar por titulo: los free-to-play y los nombres raros
(`skate.`, `PEAK`) no se encuentran por nombre y por appid salen siempre.

Como todo lo demas de la mediateca, no pide clave ni registro.

  juegos  Steam, ficha de la tienda: year y autor

Uso:
  scripts/datos.py                    rellena los campos vacios
  scripts/datos.py --force            reescribe tambien los que ya tienen valor
  scripts/datos.py --seccion juegos   solo esa carpeta
  scripts/datos.py --dry-run          dice que pondria, sin tocar nada
  scripts/datos.py content/juegos/Hollow\\ Knight.md   una ficha suelta
"""

import argparse
import re
import sys
import time
from pathlib import Path

from mediateca import (SECCIONES, VAULT, escribir_campos, frontmatter, pedir)

# La tienda de Steam corta sobre las 200 peticiones cada cinco minutos. Con una
# biblioteca normal no se llega, pero se va sin prisa por si acaso.
ESPERA = 1.5


# --- fuentes -----------------------------------------------------------------

def datos_juego(campos):
    appid = campos.get("appid")
    if not appid:
        return {}, "la ficha no tiene appid; se pone a mano"

    respuesta = pedir("https://store.steampowered.com/api/appdetails"
                      f"?appids={appid}&l=spanish&cc=es") or {}
    entrada = respuesta.get(str(appid)) or {}
    if not entrada.get("success"):
        # Pasa con lo retirado de la tienda y con lo que ya no es una app suya.
        return {}, f"la tienda no tiene ficha del appid {appid}"
    datos = entrada.get("data") or {}

    valores = {}
    # La fecha viene en el idioma pedido y con formatos distintos segun el
    # juego ("22 OCT 2025", "Oct 2025", "Por anunciar"): del año para arriba no
    # hay nada que ordenar en la galeria, asi que solo se saca el año.
    año = re.search(r"\b(1\d{3}|20\d{2})\b", (datos.get("release_date") or {}).get("date") or "")
    if año:
        valores["year"] = int(año.group(1))
    # El estudio antes que la distribuidora: en la ficha `autor` es quien lo
    # hizo, igual que la direccion en una pelicula y no la productora.
    estudios = datos.get("developers") or datos.get("publishers") or []
    if estudios:
        valores["autor"] = ", ".join(estudios[:2])
    return valores, f"Steam ({datos.get('name') or appid})"


# Que sabe rellenar cada seccion, y en que campos. Las demas van a mano: para
# el director de una pelicula o el autor de un libro no hay una fuente que
# identifique la obra sin lugar a dudas como hace el appid con los juegos.
FUENTES = {"juego": (datos_juego, ("year", "autor"))}


# --- recorrido ---------------------------------------------------------------

def fichas(args):
    if args.ficha:
        return [Path(f).resolve() for f in args.ficha]
    # Sin --seccion se recorre solo lo que tiene fuente, para no listar como
    # fallo cada pelicula y cada libro, que se rellenan a mano de todos modos.
    carpetas = [args.seccion] if args.seccion else [
        c for c, tipo in SECCIONES.items() if tipo in FUENTES]
    salida = []
    for carpeta in carpetas:
        salida += sorted(p for p in (VAULT / carpeta).glob("*.md") if p.stem != "index")
    return salida


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("ficha", nargs="*", help="fichas sueltas; por defecto, todas")
    p.add_argument("--seccion", choices=list(SECCIONES), help="solo una carpeta")
    p.add_argument("--force", action="store_true",
                   help="reescribe los campos que ya tienen valor")
    p.add_argument("--dry-run", action="store_true", help="no consulta ni escribe nada")
    args = p.parse_args()

    hechas = fallidas = saltadas = 0

    for md in fichas(args):
        campos = frontmatter(md.read_text(encoding="utf-8"))
        tipo = campos.get("tipo") or SECCIONES.get(md.parent.name)
        etiqueta = f"{md.parent.name}/{md.stem}"
        if tipo not in FUENTES:
            print(f"  ?  {etiqueta}: no hay fuente para '{tipo}'; se rellena a mano")
            fallidas += 1
            continue

        fuente, esperados = FUENTES[tipo]
        faltan = esperados if args.force else [c for c in esperados if not campos.get(c)]
        if not faltan:
            saltadas += 1
            continue
        if args.dry_run:
            print(f"  ·  {etiqueta}: buscaría {', '.join(faltan)}")
            continue

        valores, detalle = fuente(campos)
        # Lo que ya estuviera puesto a mano no se pisa salvo con --force.
        valores = {c: v for c, v in valores.items() if c in faltan}
        if not valores:
            print(f"  ✗  {etiqueta}: {detalle}")
            fallidas += 1
            continue

        escribir_campos(md, valores)
        puesto = ", ".join(f"{c}: {v}" for c, v in valores.items())
        print(f"  ✓  {etiqueta}: {puesto}  —  {detalle}")
        hechas += 1
        time.sleep(ESPERA)

    print(f"\n{hechas} fichas completadas, {fallidas} sin resolver, "
          f"{saltadas} ya estaban.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
