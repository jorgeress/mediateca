#!/usr/bin/env python3
"""Baja la portada de cada ficha y la deja en assets/portadas/ como WebP.

Cada seccion tira de la fuente que mejor la conoce:

  juegos  Steam (busqueda publica, sin clave)
  libros  Open Library (sin clave)
  musica  MusicBrainz + Cover Art Archive (sin clave)
  pelis   Wikipedia (sin clave)

Uso:
  scripts/portadas.py                 rellena las fichas sin portada
  scripts/portadas.py --force         rehace tambien las que ya la tienen
  scripts/portadas.py --seccion pelis solo esa carpeta
  scripts/portadas.py --dry-run       dice que bajaria, sin tocar nada
  scripts/portadas.py content/juegos/Hollow\\ Knight.md   una ficha suelta
"""

import argparse
import difflib
import re
import sys
import time
import urllib.parse
from io import BytesIO
from pathlib import Path

from PIL import Image

from mediateca import (FRONT_RE, PORTADAS, SECCIONES, VAULT, frontmatter, normal,
                       pedir, slug)

ANCHO = 400  # las tarjetas miden 220 px; 400 cubre pantallas 2x


def escribir_portada(md, nombre):
    texto = md.read_text(encoding="utf-8")
    m = FRONT_RE.match(texto)
    if not m:
        return False
    cabecera = m.group(1)
    linea = f'portada: "[[{nombre}]]"'
    if re.search(r"^portada:.*$", cabecera, re.M):
        nueva = re.sub(r"^portada:.*$", linea, cabecera, count=1, flags=re.M)
    else:
        nueva = cabecera + "\n" + linea
    md.write_text(texto.replace(cabecera, nueva, 1), encoding="utf-8")
    return True


def guardar(datos, destino, cuadrada=False):
    img = Image.open(BytesIO(datos))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    if img.width > ANCHO:
        # Ampliar una portada pequena solo la emborrona y la engorda.
        alto = round(img.height * ANCHO / img.width)
        img = img.resize((ANCHO, alto), Image.LANCZOS)
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, "WEBP", quality=82, method=6)
    del cuadrada
    return destino.stat().st_size


# --- fuentes -----------------------------------------------------------------

def caratula_steam(appid, capsula=None):
    if capsula and "/" in str(capsula):
        # Ruta con hash: la de los juegos recientes, que ya no estan en la vieja.
        img = pedir("https://shared.fastly.steamstatic.com/store_item_assets/steam"
                    f"/apps/{appid}/{capsula}", binario=True)
        if img and len(img) > 5000:
            return img
    for archivo in ("library_600x900_2x.jpg", "library_600x900.jpg", "header.jpg"):
        img = pedir(f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/{archivo}",
                    binario=True)
        if img and len(img) > 5000:
            return img
    return None


def portada_juego(titulo, campos):
    if campos.get("appid"):
        # Importado de tu propia biblioteca: el juego ya esta identificado.
        # Buscarlo por nombre falla con los free-to-play y con los titulos raros.
        img = caratula_steam(campos["appid"], campos.get("capsula"))
        if img:
            return img, "Steam (exacta, por appid)"
    url = "https://steamcommunity.com/actions/SearchApps/" + urllib.parse.quote(titulo)
    res = pedir(url) or []
    if not res:
        return None, None
    exacto = next((a for a in res if normal(a.get("name")) == normal(titulo)), res[0])
    img = caratula_steam(exacto["appid"])
    return (img, f"Steam ({exacto['name']})") if img else (None, None)


def portada_libro(titulo, campos):
    consulta = " ".join(filter(None, [titulo, campos.get("autor")]))
    url = ("https://openlibrary.org/search.json?limit=5"
           "&fields=title,author_name,cover_i,first_publish_year&q="
           + urllib.parse.quote(consulta))
    datos = pedir(url) or {}
    for doc in datos.get("docs", []):
        if not doc.get("cover_i"):
            continue
        img = pedir(f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-L.jpg",
                    binario=True)
        if img and len(img) > 5000:
            return img, f"Open Library ({doc.get('title')})"
    return None, None


def portada_album(titulo, campos):
    if campos.get("mbid"):
        # Viene de ListenBrainz: el disco ya esta identificado, no hay que buscarlo.
        img = pedir(f"https://coverartarchive.org/release/{campos['mbid']}/front-500",
                    binario=True)
        if img and len(img) > 5000:
            return img, "Cover Art Archive (exacta, por mbid)"
    consulta = f'releasegroup:"{titulo}"'
    if campos.get("autor"):
        consulta += f' AND artist:"{campos["autor"]}"'
    url = ("https://musicbrainz.org/ws/2/release-group?fmt=json&limit=5&query="
           + urllib.parse.quote(consulta))
    datos = pedir(url) or {}
    time.sleep(1.1)  # MusicBrainz pide como mucho una consulta por segundo
    for grupo in datos.get("release-groups", []):
        img = pedir(f"https://coverartarchive.org/release-group/{grupo['id']}/front-500",
                    binario=True)
        if img and len(img) > 5000:
            return img, f"Cover Art Archive ({grupo.get('title')})"
    return None, None


def wiki(host, params):
    """Una llamada a la API de MediaWiki, sin apretar: devuelve 429 enseguida."""
    time.sleep(0.6)
    return pedir(f"https://{host}.wikipedia.org/w/api.php?format=json&"
                 + urllib.parse.urlencode(params))


PARECIDO_MINIMO = 0.6


def encaja(titulo, *candidatos):
    """Si alguno de esos articulos va de esta pelicula.

    El buscador de Wikipedia siempre devuelve algo, aunque no tenga nada que
    ver, asi que sin esta comprobacion una ficha se queda con el cartel de otra
    pelicula. Se compara por parecido y no por igualdad porque los titulos
    bailan: "Kill Bill Vol. 1" contra "Kill Bill: Volumen 1".
    """
    buscado = normal(titulo)
    if not buscado:
        return False
    return any(difflib.SequenceMatcher(None, buscado, normal(c)).ratio() >= PARECIDO_MINIMO
               for c in candidatos)


# Una pelicula famosa suele tener articulo tambien para su banda sonora, su
# videojuego o la novela de la que sale, y todos se llaman casi igual.
OTRAS_OBRAS = ("soundtrack", "banda sonora", "album", "video game", "videojuego",
               "novel", "novela", "series", "serie", "song", "book", "musical",
               "manga", "anime", "comic", "comic book")


def articulos_ingleses(titulo, year):
    """Articulos en ingles que puedan ser esta pelicula, del mas parecido al menos.

    La Wikipedia en espanol no admite material con copyright, asi que las
    caratulas solo viven en la inglesa. Se busca por los dos lados: directo en
    la inglesa, que es donde caen las fichas con el titulo original, y en la
    española saltando por los enlaces de idioma, que es lo que resuelve las que
    tienen el titulo traducido.
    """
    candidatos = []

    directa = wiki("en", {"action": "query", "list": "search", "srlimit": 5,
                          "srsearch": f"{titulo} {year or ''} film".strip()})
    for resultado in (directa or {}).get("query", {}).get("search", []):
        if encaja(titulo, resultado["title"]):
            candidatos.append(resultado["title"])

    busqueda = wiki("es", {"action": "query", "list": "search", "srlimit": 5,
                           "srsearch": f"{titulo} {year or ''} pelicula".strip()})
    for resultado in (busqueda or {}).get("query", {}).get("search", []):
        enlaces = wiki("es", {"action": "query", "prop": "langlinks", "lllang": "en",
                              "redirects": 1, "titles": resultado["title"]})
        pagina = list((enlaces or {}).get("query", {}).get("pages", {}).values())
        for idioma in (pagina[0].get("langlinks") if pagina else None) or []:
            if encaja(titulo, resultado["title"], idioma["*"]):
                candidatos.append(idioma["*"])

    buscado = normal(titulo)
    limpios = [c for c in dict.fromkeys(candidatos)
               if not any(marca in c.lower() for marca in OTRAS_OBRAS
                          if marca not in titulo.lower())]

    def orden(candidato):
        """Primero el que se declara pelicula, y ademas del año que toca.

        Ordenar solo por parecido premia el titulo pelado, que suele ser la
        obra mas famosa y casi nunca la pelicula: "Little Women" a secas es la
        novela de 1868, y la pelicula es "Little Women (2019 film)".
        """
        bajo = candidato.lower()
        marca = re.search(r"\((\d{4})[^)]*\)", bajo)
        suyo = marca.group(1) if marca else None
        if year and suyo == str(year):
            grupo = 0  # se declara pelicula, y del año de la ficha
        elif year and suyo and suyo != str(year):
            grupo = 3  # otra version: el remake de 1997 no es la de 1957
        elif "film)" in bajo or "película" in bajo or "pelicula" in bajo:
            grupo = 1
        else:
            grupo = 2
        return grupo, -difflib.SequenceMatcher(None, buscado, normal(candidato)).ratio()

    return sorted(limpios, key=orden)


def imagen_infobox(articulo):
    datos = wiki("en", {"action": "parse", "prop": "text", "section": 0,
                        "redirects": 1, "page": articulo})
    html = (datos or {}).get("parse", {}).get("text", {}).get("*", "")
    m = re.search(r'class="[^"]*infobox-image[^"]*".*?<img[^>]+src="([^"]+)"', html, re.S)
    if not m:
        return None
    src = "https:" + m.group(1).split("?")[0].replace("&amp;", "&")
    # De la miniatura al fichero original, que ya es pequeno de por si.
    return re.sub(r"/thumb(/.*)/\d+px-[^/]+$", r"\1", src)


def portada_peli(titulo, campos):
    """El poster de la ficha lateral del articulo en ingles.

    Wikipedia obliga a que el material no libre este en baja resolucion, asi
    que sale a unos 220 px de ancho: justo lo que mide la tarjeta, nitido en
    una pantalla normal y algo blando en una de mucha densidad.
    """
    for articulo in articulos_ingleses(titulo, campos.get("year")):
        src = imagen_infobox(articulo)
        if not src:
            continue
        # Con paciencia y varios intentos: bajando muchas seguidas Wikimedia
        # corta, y si falla el primer candidato el segundo es OTRA pelicula.
        # Quedarse con el cartel equivocado es peor que quedarse sin cartel.
        time.sleep(0.6)
        img = pedir(src, binario=True, reintentos=5)
        if img and len(img) > 5000:
            return img, f"Wikipedia ({articulo})"
    return None, None


FUENTES = {"juego": portada_juego, "peli": portada_peli,
           "libro": portada_libro, "album": portada_album}


# --- recorrido ---------------------------------------------------------------

def fichas(args):
    if args.ficha:
        return [Path(f).resolve() for f in args.ficha]
    carpetas = [args.seccion] if args.seccion else SECCIONES
    salida = []
    for carpeta in carpetas:
        salida += sorted(p for p in (VAULT / carpeta).glob("*.md") if p.stem != "index")
    return salida


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("ficha", nargs="*", help="fichas sueltas; por defecto, todas")
    p.add_argument("--seccion", choices=list(SECCIONES), help="solo una carpeta")
    p.add_argument("--force", action="store_true", help="rehace las que ya tienen portada")
    p.add_argument("--dry-run", action="store_true", help="no baja ni escribe nada")
    args = p.parse_args()

    hechas = fallidas = saltadas = 0

    for md in fichas(args):
        campos = frontmatter(md.read_text(encoding="utf-8"))
        tipo = campos.get("tipo") or SECCIONES.get(md.parent.name)
        titulo = campos.get("title") or md.stem
        etiqueta = f"{md.parent.name}/{md.stem}"

        # Si apunta a una portada que ya no esta, se vuelve a bajar.
        apuntada = re.sub(r"^\[\[|\]\]$", "", campos.get("portada") or "")
        if apuntada and (PORTADAS / apuntada).exists() and not args.force:
            saltadas += 1
            continue
        if tipo not in FUENTES:
            print(f"  ?  {etiqueta}: tipo '{tipo}' desconocido")
            fallidas += 1
            continue
        if args.dry_run:
            print(f"  ·  {etiqueta}: buscaria en {FUENTES[tipo].__name__}")
            continue

        img, fuente = FUENTES[tipo](titulo, campos)
        if not img:
            print(f"  ✗  {etiqueta}: sin portada en la fuente")
            fallidas += 1
            continue

        nombre = f"{slug(titulo)}.webp"
        peso = guardar(img, PORTADAS / nombre)
        escribir_portada(md, nombre)
        print(f"  ✓  {etiqueta}: {nombre}, {peso // 1024} KB, {fuente}")
        hechas += 1

    print(f"\n{hechas} portadas nuevas, {fallidas} sin resolver, "
          f"{saltadas} ya la tenian.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
