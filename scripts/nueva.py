#!/usr/bin/env python3
"""Añade una obra suelta: la busca, la eliges tu y deja la ficha entera.

  scripts/nueva.py juego "hollow knight"
  scripts/nueva.py peli "parasite"
  scripts/nueva.py album "in rainbows"
  scripts/nueva.py libro "el nombre del viento"

Es lo que hace el buscador de Letterboxd o el de Spotify cuando escribes:
enseñar candidatos con lo justo para distinguirlos, y guardarse el
identificador de lo que elijas en vez del nombre. Eso es lo que hace que la
portada y los datos salgan exactos y se puedan rehacer siempre igual.

Cada tipo pregunta a la fuente que mejor lo conoce, y ninguna pide clave:

  juego  Steam         guarda appid, y trae year, autor y tags
  peli   Wikidata      guarda letterboxd, y trae year y direccion
  album  MusicBrainz   guarda mbid, y trae year y artista
  libro  Open Library  guarda coverid, y trae year y autor

Lo que la fuente no sabe es lo tuyo, y va en las opciones:

  --nota 8            del 1 al 10
  --estado "en curso" pendiente, en curso, terminado, abandonado
  --favorito          la marca como favorita
  --elegir 2          sin preguntar: el resultado numero 2
  --borrador          entra con draft: true, o sea sin salir en la web
  --dry-run           dice que crearia, sin tocar nada
"""

import argparse
import re
import sys
import urllib.parse

from datos import datos_juego
from mediateca import (ESTADOS, PORTADAS, SECCIONES, VAULT, escribir_campos,
                       escribir_ficha, ficha_letterboxd, nombre_de_fichero,
                       parecidos, pedir, peliculas_wikidata, preguntar, slug)
from portadas import FUENTES as CARATULAS, guardar

# Tipo de ficha -> carpeta de la vault. SECCIONES va al reves.
CARPETAS = {tipo: carpeta for carpeta, tipo in SECCIONES.items()}


# --- buscadores --------------------------------------------------------------
# Los cuatro devuelven lo mismo: una lista de candidatos, cada uno con lo que va
# a la cabecera de la ficha y una linea con la que reconocerlo. Asi el resto del
# script no tiene que saber de que catalogo viene ninguno.
#
# Devolver None es otra cosa que devolver una lista vacia: quiere decir que no
# se ha podido preguntar. No es lo mismo "de eso no hay nada" que "hoy el
# catalogo esta caido", y decir lo primero cuando pasa lo segundo manda a
# buscar el fallo justo donde no esta.

NOMBRE_FUENTE = {"juego": "Steam", "peli": "Wikidata",
                 "album": "MusicBrainz", "libro": "Open Library"}

def candidato(titulo, year=None, autor=None, pista=None, **ids):
    return {"titulo": re.sub(r"\s+", " ", titulo or "").strip(),
            "year": year, "autor": autor, "pista": pista, "ids": ids}


def describir(c):
    # Los titulos de catalogo son a veces un parrafo entero ("El Nombre de la
    # Ballena Coleccion Los Especiales de a la Orilla del Viento"), y uno solo
    # descuadra la lista de resultados.
    titulo = c["titulo"] if len(c["titulo"]) <= 70 else c["titulo"][:69].rstrip() + "…"
    partes = [titulo]
    if c["autor"]:
        partes.append("— " + c["autor"])
    if c["year"]:
        partes.append(f"({c['year']})")
    if c["pista"]:
        partes.append("  " + c["pista"])
    return " ".join(partes)


def buscar_juego(consulta, cuantos):
    """El buscador de la tienda de Steam, el mismo que su caja de busqueda.

    Solo da el nombre y el appid: el año y el estudio estan en la ficha de la
    tienda, que son una peticion por juego. Pedirlas para toda la lista seria
    una espera larga antes de enseñar nada, y con los juegos el nombre suele
    bastar para elegir. En cuanto eliges se piden las del que sea, una sola.
    """
    res = pedir("https://steamcommunity.com/actions/SearchApps/"
                + urllib.parse.quote(consulta))
    if res is None:
        return None
    return [candidato(a["name"], pista=f"appid {a['appid']}", appid=a["appid"])
            for a in res[:cuantos] if a.get("appid")]


def buscar_peli(consulta, cuantos):
    """Wikidata, que es quien sabe cual de las homonimas es cual.

    Enseña el año porque es lo unico que las separa: hay tres peliculas
    llamadas "Parasite" y cuatro "Little Women". Del titulo no se puede
    deducir nada, y por eso se elige de una lista y no a ciegas.
    """
    candidatas = peliculas_wikidata(consulta)
    if candidatas is None:
        return None
    return [candidato(c["nombre"], year=c["year"], letterboxd=c["letterboxd"])
            for c in candidatas[:cuantos]]


def buscar_album(consulta, cuantos):
    """MusicBrainz, por grupo de lanzamiento y no por edicion concreta.

    Un disco tiene una edicion por pais, por formato y por reedicion, y todas
    se llaman igual. El grupo de lanzamiento es el disco como obra, que es lo
    que se apunta en una mediateca.
    """
    url = ("https://musicbrainz.org/ws/2/release-group?fmt=json&limit="
           f"{cuantos}&query=" + urllib.parse.quote(consulta))
    datos = pedir(url)
    if datos is None:
        return None
    salida = []
    for grupo in datos.get("release-groups", []):
        fecha = grupo.get("first-release-date") or ""
        artistas = [a["artist"]["name"] for a in grupo.get("artist-credit", [])
                    if isinstance(a, dict) and a.get("artist")]
        salida.append(candidato(grupo.get("title"), year=fecha[:4] or None,
                                autor=", ".join(artistas[:2]) or None,
                                pista=grupo.get("primary-type") or "",
                                mbid=grupo["id"]))
    return salida


CAMPOS_OL = "title,author_name,cover_i,first_publish_year"


def buscar_libro(consulta, cuantos):
    """Open Library, que es el catalogo del Internet Archive.

    Devuelve casi siempre la edicion inglesa aunque busques en español, asi
    que "el nombre del viento" sale como "The Name of the Wind". No es un
    fallo: es la ficha de la obra, y la portada que baja es la de esa edicion.
    """
    url = (f"https://openlibrary.org/search.json?limit={cuantos}&fields={CAMPOS_OL}"
           "&q=" + urllib.parse.quote(consulta))
    datos = pedir(url)
    if datos is None:
        return None
    salida = []
    for doc in datos.get("docs") or []:
        salida.append(candidato(doc.get("title"), year=doc.get("first_publish_year"),
                                autor=(doc.get("author_name") or [None])[0],
                                pista="" if doc.get("cover_i") else "(sin portada)",
                                coverid=doc.get("cover_i")))
    return salida


BUSCADORES = {"juego": buscar_juego, "peli": buscar_peli,
              "album": buscar_album, "libro": buscar_libro}
assert set(BUSCADORES) == set(NOMBRE_FUENTE)


# --- completar ---------------------------------------------------------------
# Lo que el buscador no da y si da la ficha de la obra, una vez elegida. Una
# peticion mas, y solo la del candidato que hayas dicho tu.

def completar(tipo, elegido):
    campos = {c: v for c, v in elegido["ids"].items() if v}
    if tipo == "juego":
        valores, detalle = datos_juego(elegido["titulo"], campos, None)
        return {**campos, **valores}, detalle
    if tipo == "peli":
        ficha = ficha_letterboxd(campos.get("letterboxd", ""))
        direccion = ficha.get("direccion") or []
        if direccion:
            return {**campos, "autor": ", ".join(direccion[:2])}, "Letterboxd"
        return campos, "su ficha de Letterboxd no dice quien dirige"
    return campos, None


# --- alta --------------------------------------------------------------------

def caratula(tipo, md, campos, titulo):
    """La portada de la ficha recien creada, con el id que se acaba de guardar."""
    img, fuente = CARATULAS[tipo](titulo, campos, md)
    if not img:
        return None
    nombre = f"{slug(titulo)}.webp"
    peso = guardar(img, PORTADAS / nombre)
    escribir_campos(md, {"portada": f"[[{nombre}]]"})
    return f"{nombre}, {peso // 1024} KB, {fuente}"


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("tipo", choices=list(BUSCADORES))
    p.add_argument("titulo", help="lo que escribirias en un buscador")
    p.add_argument("--nota", type=int, choices=range(1, 11), metavar="1-10")
    p.add_argument("--estado", choices=ESTADOS, default="pendiente")
    p.add_argument("--favorito", action="store_true")
    p.add_argument("--elegir", type=int, metavar="N",
                   help="sin preguntar: el resultado numero N")
    p.add_argument("--resultados", type=int, default=8, metavar="N")
    p.add_argument("--borrador", action="store_true",
                   help="entra con draft: true, o sea sin salir en la web")
    p.add_argument("--dry-run", action="store_true", help="no escribe ni baja nada")
    return alta(p.parse_args())


def alta(args):
    """El alta en si, ya con las opciones decididas.

    Aparte del parseo porque `importar.py libro` entra por aqui: es la misma
    alta de una obra suelta, con otro nombre y con el borrador por defecto.
    """
    carpeta = CARPETAS[args.tipo]
    candidatos = BUSCADORES[args.tipo](args.titulo, args.resultados)
    if candidatos is None:
        print(f"No he podido hablar con {NOMBRE_FUENTE[args.tipo]}. No es que no esté:\n"
              "es que ahora mismo no contesta. Inténtalo dentro de un rato.")
        return 1
    if not candidatos:
        print(f"No encuentro nada con «{args.titulo}».")
        if args.tipo == "libro":
            print("Prueba con el título en inglés: el catálogo va casi todo por ahí.")
        if args.tipo == "peli":
            print("Prueba con el título original: es el que suele estar en Wikidata.")
        return 1

    if args.elegir:
        if not 1 <= args.elegir <= len(candidatos):
            print(f"Solo hay {len(candidatos)} resultados.")
            return 1
        elegido = candidatos[args.elegir - 1]
        print(f"  {args.elegir}) {describir(elegido)}")
    elif not sys.stdin.isatty():
        for i, c in enumerate(candidatos, 1):
            print(f"  {i}) {describir(c)}")
        print("\nSin terminal para preguntar. Repite con --elegir N.")
        return 1
    else:
        elegido = preguntar(candidatos, describir)
        if elegido is None:
            print("No se ha creado nada.")
            return 0

    extra, detalle = completar(args.tipo, elegido)
    titulo = elegido["titulo"]
    campos = {"tipo": args.tipo, "year": elegido["year"], "autor": elegido["autor"],
              "nota": args.nota, "estado": args.estado, "favorito": args.favorito,
              "portada": None, "tags": None}
    # Lo que traiga la ficha de la obra manda sobre lo que trajo el buscador:
    # la del juego sabe el estudio y el año, y la lista solo sabia el nombre.
    campos.update({c: v for c, v in extra.items() if v})

    if args.dry_run:
        print(f"\nSe crearía content/{carpeta}/{nombre_de_fichero(titulo)}.md")
        for clave, valor in campos.items():
            if valor not in (None, "", False):
                print(f"  {clave}: {valor}")
        if detalle:
            print(f"  ({detalle})")
        return 0

    md = escribir_ficha(carpeta, titulo, campos, borrador=args.borrador)
    if not md:
        print(f"\n«{titulo}» ya estaba en content/{carpeta}/.")
        return 0
    print(f"\nCreada {md.relative_to(VAULT.parent)}")

    hecha = caratula(args.tipo, md, campos, titulo)
    print("  portada: " + (hecha or "no la he encontrado; se pone a mano"))
    for aviso in parecidos(carpeta, [titulo]):
        print("  Se parece a una que ya tenías: " + aviso)
    if args.borrador:
        print("Entra con draft: true, así que no sale en la web hasta que le quites\n"
              "la línea. En Obsidian se ve ya.")
    if args.nota is None:
        print("Sin nota: ponla en Obsidian cuando la tengas, que es lo que\n"
              "decide si entra en el Top.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
