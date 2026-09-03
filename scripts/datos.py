#!/usr/bin/env python3
"""Rellena los campos que el importador no podia saber.

Ninguna fuente lo da todo, y lo que le falta a cada una no es casualidad. Tu
pagina de juegos de Steam sabe cuanto has jugado pero no de que año es el juego,
quien lo hizo ni de que va; el diario de Letterboxd sabe tu nota pero no quien
dirige. Todo eso esta en otro sitio, publico y sin clave, y esto va a buscarlo.

La regla es la misma en las dos secciones: **no adivinar**. Los juegos se
resuelven por el `appid` que el importador ya guardo, que identifica la obra sin
lugar a dudas, y las peliculas por el mismo id de Letterboxd del que sale
el cartel, que Wikidata solo da cuando no hay duda de cual es. Antes que
rellenar una ficha con los datos de otra obra, se deja vacia.

Como todo lo demas de la mediateca, no pide clave ni registro.

  juegos  Steam, ficha de la tienda: year, autor y tags
  pelis   Letterboxd: autor, o sea la direccion

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

from mediateca import (SECCIONES, VAULT, articulo_html, articulos_ingleses,
                       asegurar_letterboxd, escribir_campos, ficha_letterboxd,
                       frontmatter, pedir, vacio)

# La tienda de Steam corta sobre las 200 peticiones cada cinco minutos. Con una
# biblioteca normal no se llega, pero se va sin prisa por si acaso.
ESPERA = 1.5

MAX_TAGS = 4  # los generos de Steam vienen del mas general al mas concreto


def etiqueta(texto):
    """Un genero tal cual viene -> un tag: en minuscula y sin espacios.

    Se dejan los acentos. Son etiquetas que se leen en la ficha y en la pagina
    de tags, y "accion" al lado de "aventura" canta.
    """
    return re.sub(r"\s+", "-", (texto or "").strip().lower())


# --- fuentes -----------------------------------------------------------------

def datos_juego(titulo, campos, md):
    del md
    del titulo  # aqui manda el appid, que identifica el juego sin dudas
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
    # Los generos vienen ya en español, porque la ficha se pide con l=spanish.
    generos = [etiqueta(g.get("description")) for g in datos.get("genres") or []]
    generos = [g for g in generos if g][:MAX_TAGS]
    if generos:
        valores["tags"] = generos
    return valores, f"Steam ({datos.get('name') or appid})"


# En la ficha lateral del articulo en ingles, la fila que dice quien dirige.
DIRECCION_RE = re.compile(r"<th[^>]*>\s*Directed by\s*</th>\s*<td[^>]*>(.*?)</td>",
                          re.S | re.I)


def datos_peli(titulo, campos, md):
    """La direccion, de la ficha de Letterboxd.

    Ni el export de Letterboxd ni su RSS traen el director, asi que las
    peliculas importadas se quedan sin `autor`. Sale de la misma pagina de la
    que ya sale el cartel y de la misma peticion, asi que llega gratis. Si la
    pelicula no se ha podido identificar queda Wikipedia, que lo trae en la
    ficha lateral pero hay que rascarlo del HTML.
    """
    slug_lb, detalle = asegurar_letterboxd(md, campos)
    if slug_lb:
        direccion = ficha_letterboxd(slug_lb).get("direccion")
        if direccion:
            return {"autor": ", ".join(direccion[:2])}, f"Letterboxd ({slug_lb})"

    for articulo in articulos_ingleses(titulo, campos.get("year")):
        m = DIRECCION_RE.search(articulo_html(articulo))
        if not m:
            continue
        # La celda trae enlaces, y con varios directores una lista o <br>. Y a
        # veces un <style> suelto: quitar solo las etiquetas deja el CSS de
        # dentro, que se colaba de director en las peliculas con dos.
        celda = re.sub(r"<(style|script)\b.*?</\1>", " ", m.group(1), flags=re.S | re.I)
        nombres = [re.sub(r"\[\d+\]", "", n).strip()
                   for n in re.sub(r"<[^>]+>", "\n", celda).split("\n")]
        nombres = [n for n in nombres if len(n) > 2 and not re.search(r"[{}:;]", n)][:2]
        if nombres:
            return {"autor": ", ".join(nombres)}, f"Wikipedia ({articulo})"
    return {}, (detalle if not slug_lb else "su ficha de Letterboxd no dice quien dirige")


# Que sabe rellenar cada seccion, y en que campos. Los libros no estan porque
# ya entran completos: `importar.py libro` los crea con año, autor y coverid
# de la edicion que hayas elegido tu. La musica tampoco, porque ListenBrainz da
# el artista de una y el genero de un disco no lo dice nadie sin discutirlo.
FUENTES = {"juego": (datos_juego, ("year", "autor", "tags")),
           "peli": (datos_peli, ("autor",))}


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
        titulo = campos.get("title") or md.stem
        nombre = f"{md.parent.name}/{md.stem}"
        if tipo not in FUENTES:
            print(f"  ?  {nombre}: no hay fuente para '{tipo}'; se rellena a mano")
            fallidas += 1
            continue

        fuente, esperados = FUENTES[tipo]
        faltan = (list(esperados) if args.force
                  else [c for c in esperados if vacio(campos.get(c))])
        if not faltan:
            saltadas += 1
            continue
        if args.dry_run:
            print(f"  ·  {nombre}: buscaría {', '.join(faltan)}")
            continue

        valores, detalle = fuente(titulo, campos, md)
        # Lo que ya estuviera puesto a mano no se pisa salvo con --force.
        valores = {c: v for c, v in valores.items() if c in faltan}
        if not valores:
            print(f"  ✗  {nombre}: {detalle}")
            fallidas += 1
            continue

        escribir_campos(md, valores)
        puesto = ", ".join(f"{c}: {', '.join(v) if isinstance(v, list) else v}"
                           for c, v in valores.items())
        print(f"  ✓  {nombre}: {puesto}  —  {detalle}")
        hechas += 1
        time.sleep(ESPERA)

    print(f"\n{hechas} fichas completadas, {fallidas} sin resolver, "
          f"{saltadas} ya estaban.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
