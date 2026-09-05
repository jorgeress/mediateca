#!/usr/bin/env python3
"""Escribe el cuerpo de las fichas que salen en blanco.

Las 84 fichas sin una linea eran el cuello de botella del sitio: el buscador
las encuentra por el titulo, pero entrar en una era entrar a nada. Esto pone
de que va cada obra, sacado de la misma fuente que ya identifica la ficha.

  juegos  Steam, por `appid`     la descripcion corta de la tienda, en español
  pelis   Wikipedia ES, por el `letterboxd` que resuelve Wikidata
  musica  MusicBrainz, por `mbid`   la lista de canciones del disco
  libros  nada todavia, hace falta un `wikipedia` en la ficha; ver abajo

La regla es la de siempre: **no adivinar**. Cada obra se busca por el
identificador que ya tiene apuntado, nunca por parecido de nombre. Si no lo
tiene, o si la fuente no dice nada de ella, la ficha se queda en blanco y se
dice por que. Antes vacia que con el texto de otra obra.

Lo que no es tuyo va citado y enlazado, y no todo lo necesita:

  Steam       no da ninguna licencia, asi que el texto va como cita breve
              marcada, con enlace a su ficha de la tienda. La cita no es
              cortesia: es lo que la ampara.
  Wikipedia   es CC BY-SA 4.0, que si da permiso a cambio de nombrar autores,
              enlazar y decir la licencia. El enlace al articulo cubre lo
              primero, porque su historial es la lista de autores.
  MusicBrainz nada. Sus datos base -artistas, discos y listas de canciones-
              son CC0, o sea dominio publico. Y una lista de titulos son
              datos, no prosa.

Los libros se quedan fuera a proposito. Solo guardan `coverid`, que identifica
la portada y no la obra; cruzandolo se llega a la obra en Open Library, pero
alli 1 de 3 tiene descripcion y esta en frances, y Wikidata solo enlaza 1 de 3.
Llegar al articulo desde lo que hay hoy exige adivinar por titulo. Cuando una
ficha de libro tenga un campo `wikipedia` con el nombre del articulo, esto lo
rellena igual que una pelicula.

Uso:
  scripts/textos.py                    escribe solo las fichas en blanco
  scripts/textos.py --force            reescribe tambien las que ya tienen texto
  scripts/textos.py --seccion juegos   solo esa carpeta
  scripts/textos.py --dry-run          dice que pondria, sin pedir ni tocar nada
  scripts/textos.py content/juegos/Dispatch.md   una ficha suelta
"""

import argparse
import html
import re
import sys
import textwrap
import time
import urllib.parse
from pathlib import Path

from vitrina import (FRONT_RE, SECCIONES, VAULT, asegurar_letterboxd,
                     ficha_letterboxd, frontmatter, pedir)

ESPERA = 1.5  # la tienda de Steam corta sobre las 200 peticiones cada 5 minutos

ANCHO = 76  # el resto del repo escribe la prosa a esta anchura

LICENCIA_CC = "https://creativecommons.org/licenses/by-sa/4.0/deed.es"


def limpio(bruto):
    """El parrafo de una fuente -> texto plano de una sola linea.

    Steam mete <br>, <strong> y entidades en su descripcion corta, y Wikipedia
    devuelve el extracto ya en texto pero con espacios raros de las plantillas.
    """
    texto = re.sub(r"<[^>]+>", " ", bruto or "")
    return re.sub(r"\s+", " ", html.unescape(texto)).strip()


def cita(texto, credito):
    """Un callout de Obsidian con el texto y de donde sale.

    Se usa `[!quote]` y no un parrafo suelto porque la diferencia importa: asi
    se ve que la sinopsis es de la fuente y que lo que escriba el debajo es
    suyo. Quartz pinta los callouts igual que Obsidian, asi que se ve lo mismo
    en el editor y en la web.
    """
    lineas = textwrap.wrap(texto, ANCHO - 2) or [""]
    cuerpo = "\n".join(f"> {l}" for l in lineas)
    return f"> [!quote] De qué va\n{cuerpo}\n>\n> — {credito}"


# --- fuentes -----------------------------------------------------------------

def texto_juego(titulo, campos, md):
    del titulo, md  # aqui manda el appid, que identifica el juego sin dudas
    appid = campos.get("appid")
    if not appid:
        return None, "la ficha no tiene appid; se pone a mano"

    respuesta = pedir("https://store.steampowered.com/api/appdetails"
                      f"?appids={appid}&l=spanish&cc=es") or {}
    entrada = respuesta.get(str(appid)) or {}
    if not entrada.get("success"):
        return None, f"la tienda no tiene ficha del appid {appid}"

    datos = entrada.get("data") or {}
    sinopsis = limpio(datos.get("short_description"))
    if not sinopsis:
        return None, f"su ficha de Steam no trae descripcion ({appid})"

    tienda = f"https://store.steampowered.com/app/{appid}/"
    return cita(sinopsis, f"De su [ficha en Steam]({tienda})"), \
        f"Steam ({datos.get('name') or appid})"


def articulo_es(propiedad, valor):
    """El articulo de la Wikipedia en español de lo que tenga ese identificador.

    Se pregunta a Wikidata por el id exacto -el de Letterboxd para las pelis,
    el de Open Library para los libros- y no por el titulo. Wikidata solo
    contesta cuando ese id esta puesto en una ficha, asi que o sale la obra
    correcta o no sale ninguna, que es justo lo que se quiere.
    """
    consulta = ('SELECT ?art WHERE { ?item wdt:%s "%s". '
                '?art schema:about ?item; schema:isPartOf <https://es.wikipedia.org/> }'
                % (propiedad, valor))
    time.sleep(0.5)  # el endpoint publico de Wikidata pide no apretar
    datos = pedir("https://query.wikidata.org/sparql?format=json&query="
                  + urllib.parse.quote(consulta)) or {}
    for fila in datos.get("results", {}).get("bindings", []):
        url = fila.get("art", {}).get("value")
        if url:
            return urllib.parse.unquote(url.rsplit("/", 1)[-1]).replace("_", " ")
    return None


def resumen_wikipedia(articulo):
    """El primer parrafo del articulo, que es el que resume la obra."""
    ruta = urllib.parse.quote(articulo.replace(" ", "_"), safe="")
    time.sleep(0.4)
    datos = pedir(f"https://es.wikipedia.org/api/rest_v1/page/summary/{ruta}") or {}
    return limpio(datos.get("extract"))


def credito_wikipedia(articulo):
    enlace = "https://es.wikipedia.org/wiki/" + urllib.parse.quote(
        articulo.replace(" ", "_"), safe="")
    return (f"De [«{articulo}»]({enlace}) en Wikipedia, "
            f"bajo [CC BY-SA 4.0]({LICENCIA_CC})")


def texto_peli(titulo, campos, md):
    """La sinopsis, de la Wikipedia en español, por el id de Letterboxd.

    Se podria sacar de la propia pagina de Letterboxd, que la trae en su
    JSON-LD, pero ese texto no es suyo: es de TMDB, a quien enlazan en la
    misma pagina. Y viene en ingles. Wikipedia lo da en castellano y con una
    licencia que dice en claro que se puede hacer con el.
    """
    del titulo
    slug_lb, detalle = asegurar_letterboxd(md, campos)
    if not slug_lb:
        return None, detalle

    articulo = articulo_es("P6127", slug_lb)
    if articulo:
        sinopsis = resumen_wikipedia(articulo)
        if sinopsis:
            return cita(sinopsis, credito_wikipedia(articulo)), f"Wikipedia ({articulo})"

    # Sin articulo en español -pasa con lo recien estrenado- queda la ficha de
    # Letterboxd. Se cita a TMDB y no a ellos porque el texto es de TMDB, a
    # quien enlazan en su propia pagina; y se avisa de que viene en ingles.
    ficha = ficha_letterboxd(slug_lb)
    sinopsis, tmdb = ficha.get("sinopsis"), ficha.get("tmdb")
    if sinopsis and tmdb:
        return cita(limpio(sinopsis), f"De [su ficha en TMDB]({tmdb}), en inglés"), \
            f"TMDB via Letterboxd ({slug_lb})"
    if not articulo:
        return None, f"ni articulo en español ni sinopsis en Letterboxd ({slug_lb})"
    return None, f"el articulo «{articulo}» no trae resumen"


def texto_libro(titulo, campos, md):
    """Igual que una pelicula, pero solo si alguien ha dicho cual es el articulo.

    Ver la explicacion de arriba: desde el `coverid` no se llega sin adivinar.
    """
    del titulo, md
    articulo = campos.get("wikipedia")
    if not articulo:
        return None, "sin campo `wikipedia`; hay que decirle cual es el articulo"
    sinopsis = resumen_wikipedia(articulo)
    if not sinopsis:
        return None, f"el articulo «{articulo}» no trae resumen"
    return cita(sinopsis, credito_wikipedia(articulo)), f"Wikipedia ({articulo})"


MAX_EDICIONES = 6  # cada una es una peticion, y MusicBrainz pide ir despacio

CABECERA_MB = {"Accept": "application/json"}


def canciones_de_edicion(release_id):
    time.sleep(1.1)  # MusicBrainz pide como mucho una consulta por segundo
    datos = pedir(f"https://musicbrainz.org/ws/2/release/{release_id}"
                  "?inc=recordings&fmt=json", headers=CABECERA_MB) or {}
    titulos = [t.get("title") for m in datos.get("media") or []
               for t in m.get("tracks") or [] if t.get("title")]
    return titulos, datos.get("title")


def canciones_musicbrainz(mbid):
    """La lista de canciones del disco, en orden.

    El `mbid` puede ser de las dos cosas: el de ListenBrainz es de una edicion
    concreta y el que guarda nueva.py es del disco como obra. Se prueban las
    dos, igual que hace portadas.py para la caratula.

    Y de un disco hay muchas ediciones -de Three Cheers for Sweet Revenge hay
    19-, de las cuales unas cuantas estan a medias en la base: la primera de
    ese disco no tiene ni una cancion. Asi que se recorren hasta dar con una
    que traiga la lista, en vez de fiarse de la primera.
    """
    titulos, nombre = canciones_de_edicion(mbid)
    if titulos:
        return titulos, nombre or mbid

    grupo = pedir(f"https://musicbrainz.org/ws/2/release-group/{mbid}"
                  "?inc=releases&fmt=json", headers=CABECERA_MB) or {}
    for edicion in (grupo.get("releases") or [])[:MAX_EDICIONES]:
        titulos, nombre = canciones_de_edicion(edicion["id"])
        if titulos:
            return titulos, nombre or grupo.get("title") or mbid
    return [], None


def texto_album(titulo, campos, md):
    """La lista de canciones del disco, en orden."""
    del titulo, md
    mbid = campos.get("mbid")
    if not mbid:
        return None, "la ficha no tiene mbid; se pone a mano"

    titulos, nombre = canciones_musicbrainz(mbid)
    if not titulos:
        return None, f"MusicBrainz no da la lista de canciones ({mbid})"
    return cuerpo_disco(titulos), f"MusicBrainz ({nombre})"


def cuerpo_disco(titulos):
    """La lista numerada, aparte para poder probarla sin red ni ficheros.

    Solo la lista: no hay favoritas por cancion. Se probaron, con una estrella
    al final de la linea, y se quitaron a peticion suya porque marcarlas exigia
    editar el fichero y pasar un script, y eso no lo puede hacer nadie desde la
    web publicada, que es estatica. Los favoritos son de disco entero, con el
    campo `favorito`, que si se ve online para todo el mundo.
    """
    lineas = [f"{i}. {t}" for i, t in enumerate(titulos, 1)]
    return "## Canciones\n\n" + "\n".join(lineas)


FUENTES = {"juego": texto_juego, "peli": texto_peli,
           "album": texto_album, "libro": texto_libro}


# --- escritura ---------------------------------------------------------------

# Lo que escribe este script, y por tanto lo unico que puede pisar: el bloque
# de la cita, y la lista de canciones de un disco desde su encabezado al final.
GENERADO_RE = re.compile(
    r"^> \[!quote\][^\n]*\n(?:>[^\n]*\n?)*"   # la cita de la fuente
    r"|^## Canciones\n[\s\S]*\Z",             # la lista entera de un disco
    re.M)


def lo_suyo(cuerpo):
    """El cuerpo sin lo que genera el script: o sea, lo que ha escrito el.

    De esto depende que `--force` sea seguro. La sinopsis y la lista de
    canciones las puede volver a bajar el script cuando quiera; su parrafo, no.
    """
    return GENERADO_RE.sub("", cuerpo or "").strip()


def escribir_cuerpo(md, cuerpo):
    """Pone lo generado sin tocar lo que haya escrito el.

    **Lo suyo va arriba y lo generado debajo**, siempre, en las cuatro
    secciones. Asi hay un sitio fijo donde escribir que ningun script pisa, y
    quien entra en una ficha lee primero por que le gusto y luego la referencia.
    """
    texto = md.read_text(encoding="utf-8")
    m = FRONT_RE.match(texto)
    if not m:
        raise ValueError(f"{md} no tiene cabecera")
    suyo = lo_suyo(texto[m.end():])
    nuevo = (suyo + "\n\n" if suyo else "") + cuerpo.rstrip()
    md.write_text(m.group(0) + "\n" + nuevo + "\n", encoding="utf-8")


def fichas(args):
    if args.ficha:
        return [Path(f).resolve() for f in args.ficha]
    carpetas = [args.seccion] if args.seccion else list(SECCIONES)
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
                   help="reescribe el cuerpo de las fichas que ya tienen texto")
    p.add_argument("--dry-run", action="store_true", help="no consulta ni escribe nada")
    args = p.parse_args()

    hechas = fallidas = saltadas = 0

    for md in fichas(args):
        texto = md.read_text(encoding="utf-8")
        campos = frontmatter(texto)
        tipo = campos.get("tipo") or SECCIONES.get(md.parent.name)
        titulo = campos.get("title") or md.stem
        nombre = f"{md.parent.name}/{md.stem}"

        tiene_texto = bool(FRONT_RE.sub("", texto).strip())
        if tiene_texto and not args.force:
            saltadas += 1
            continue

        fuente = FUENTES.get(tipo)
        if not fuente:
            print(f"  ?  {nombre}: no hay fuente para '{tipo}'")
            fallidas += 1
            continue
        if args.dry_run:
            print(f"  ·  {nombre}: buscaría su texto")
            continue

        cuerpo, detalle = fuente(titulo, campos, md)
        if not cuerpo:
            print(f"  ✗  {nombre}: {detalle}")
            fallidas += 1
            continue

        escribir_cuerpo(md, cuerpo)
        print(f"  ✓  {nombre}  —  {detalle}")
        hechas += 1
        time.sleep(ESPERA)

    print(f"\n{hechas} fichas escritas, {fallidas} sin resolver, "
          f"{saltadas} ya tenian texto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
