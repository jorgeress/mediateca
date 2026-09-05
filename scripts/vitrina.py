"""Lo que comparten los scripts de Vitrina: rutas, fichas y peticiones."""

import difflib
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VAULT = RAIZ / "content"
PORTADAS = VAULT / "assets" / "portadas"

# Carpeta de la vault -> valor del campo `tipo` de la ficha.
SECCIONES = {"juegos": "juego", "pelis": "peli", "libros": "libro", "musica": "album"}

UA = "vitrina/1.0 (https://github.com/jorgeress/vitrina)"

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


# Un elemento de lista en bloque: "  - rpg".
ITEM_RE = re.compile(r"^[ \t]*-[ \t]+(.*)$")


def frontmatter(texto):
    """Lee la cabecera. No hace falta un YAML completo, pero si las listas.

    Las listas en bloque hay que entenderlas porque Obsidian escribe asi los
    tags en cuanto los tocas desde su editor de propiedades. Si aqui se leyeran
    como vacias, un script creeria que la ficha no tiene tags y los pisaria.
    """
    m = FRONT_RE.match(texto)
    if not m:
        return {}
    campos = {}
    ultima = None
    for linea in m.group(1).splitlines():
        item = ITEM_RE.match(linea)
        if item and ultima is not None:
            # Una clave con lista debajo: "tags:" y nada mas se lee como "".
            if not isinstance(campos.get(ultima), list):
                campos[ultima] = []
            campos[ultima].append(item.group(1).strip().strip('"').strip("'"))
            continue
        if linea.startswith((" ", "\t", "#")) or ":" not in linea:
            continue
        clave, _, valor = linea.partition(":")
        ultima = clave.strip()
        campos[ultima] = valor.strip().strip('"').strip("'")
    return campos


def vacio(valor):
    """Si un campo esta sin poner. `tags: []` cuenta como vacio; con algo, no."""
    if valor is None:
        return True
    if isinstance(valor, (list, tuple)):
        return not valor
    return valor.strip() in ("", "[]", "{}")


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


def linea_yaml(clave, valor):
    """Una linea de cabecera, con su lista debajo si el valor es una lista.

    En bloque y no entre corchetes, que es como escribe las listas Obsidian en
    cuanto tocas las propiedades de una nota desde su editor.
    """
    if isinstance(valor, (list, tuple)):
        return clave + ":" + "".join(f"\n  - {yaml_valor(v)}" for v in valor)
    return f"{clave}: {yaml_valor(valor)}".rstrip()


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
        linea = linea_yaml(clave, valor)
        # Se lleva por delante la lista que hubiera debajo de la clave, si no
        # los elementos viejos se quedarian huerfanos bajo la clave nueva.
        patron = rf"^{re.escape(clave)}:.*(?:\n[ \t]*-[ \t]+.*)*$"
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



# --- fichas nuevas -----------------------------------------------------------
# Lo que hace falta para crear una ficha desde cero, que necesitan tanto el
# importador, que las vuelca a cientos, como el alta de una obra suelta.

ESTADOS = ["pendiente", "en curso", "terminado", "abandonado"]

CAMPOS = ["tipo", "year", "autor", "nota", "estado", "favorito", "portada", "tags"]

def fichas_existentes(carpeta):
    return {p.stem: normal(p.stem) for p in (VAULT / carpeta).glob("*.md")
            if p.stem != "index"}


def escribir_ficha(carpeta, titulo, campos, cuerpo="", borrador=True):
    """Deja la ficha en su carpeta. Devuelve None si ya existia."""
    destino = VAULT / carpeta / f"{nombre_de_fichero(titulo)}.md"
    if destino.exists():
        return None
    # Misma obra escrita distinto ("Parásitos" y "Parasitos"): no se duplica.
    if normal(titulo) in fichas_existentes(carpeta).values():
        return None
    orden = CAMPOS + [c for c in campos if c not in CAMPOS]
    lineas = [linea_yaml(c, campos.get(c)) for c in orden]
    if nombre_de_fichero(titulo) != titulo:
        # Un nombre de fichero no admite ":" ni "?", asi que "Spider-Man: Brand
        # New Day" se queda sin los dos puntos y con eso ya no se encuentra en
        # ningun catalogo. El titulo de verdad se apunta aparte: es el que
        # buscan los scripts y el que Quartz pone de encabezado en la web.
        lineas.insert(0, f"title: {yaml_valor(titulo)}")
    if campos.get("tags") is None:
        lineas[orden.index("tags")] = "tags: []"
    if borrador:
        # Quartz se salta las notas con draft; Obsidian las sigue enseñando.
        lineas.append("draft: true")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("---\n" + "\n".join(lineas) + "\n---\n\n" + cuerpo,
                       encoding="utf-8")
    return destino


def parecidos(carpeta, titulos):
    """Titulos que se parecen a una ficha que ya hay, por si son la misma obra.

    No se descartan solos: "Portal" contiene a "Portal 2" y son dos juegos
    distintos. Se avisa y ya decides tu.
    """
    avisos = []
    for nombre, existente in fichas_existentes(carpeta).items():
        for titulo in titulos:
            nuevo = normal(titulo)
            if nuevo != existente and (nuevo in existente or existente in nuevo):
                avisos.append(f"{nombre}  <->  {titulo}")
    return avisos


def preguntar(candidatos, describir):
    """Elegir a mano es el punto, no un tramite.

    Un catalogo siempre devuelve algo, y con los titulos cortos cuela
    cualquier cosa: Open Library trae la edicion inglesa aunque busques en
    español, y en Steam "Portal" saca antes el 2 que el 1. Dar por bueno el
    primer resultado es justo lo que hace que una ficha acabe con los datos de
    otra obra.
    """
    for i, doc in enumerate(candidatos, 1):
        print(f"  {i}) {describir(doc)}")
    while True:
        try:
            resp = input(f"\n¿Cuál? (1-{len(candidatos)}, Enter para el 1, "
                         "0 si ninguno): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if resp == "":
            return candidatos[0]
        if resp == "0":
            return None
        if resp.isdigit() and 1 <= int(resp) <= len(candidatos):
            return candidatos[int(resp) - 1]
        print("  Eso no es una de las opciones.")


# --- Wikipedia ---------------------------------------------------------------
# Encontrar el articulo en ingles de una pelicula lo necesitan dos scripts: el
# de portadas, para sacar el cartel de la ficha lateral, y el de datos, para
# sacar la direccion. La parte dificil es la misma en los dos, asi que vive
# aqui y no en ninguno de ellos.

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


def articulo_html(articulo):
    """El HTML de la primera seccion, que es donde vive la ficha lateral."""
    datos = wiki("en", {"action": "parse", "prop": "text", "section": 0,
                        "redirects": 1, "page": articulo})
    return (datos or {}).get("parse", {}).get("text", {}).get("*", "")


# --- Letterboxd --------------------------------------------------------------
# El cartel de una pelicula solo esta bien en Letterboxd. Wikipedia obliga a que
# el material con copyright este en baja resolucion, asi que de alli sale a unos
# 220 px: justo lo que mide la tarjeta, y blando en cuanto la pantalla es 2x.
#
# La parte dificil no es bajarlo, es saber de que pelicula. La direccion de
# Letterboxd no se puede sacar del titulo: /film/parasite/ es la de Charles Band
# de 1982, y /film/little-women/ la de 1933. Por eso el id no se adivina nunca.
# Lo dice Wikidata, que guarda el identificador de Letterboxd (P6127) junto al
# año de estreno, y que tampoco pide clave.

JSONLD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def wikidata(params):
    """Una llamada a la API de Wikidata, sin apretar."""
    time.sleep(0.3)
    return pedir("https://www.wikidata.org/w/api.php?format=json&"
                 + urllib.parse.urlencode(params))


def año_de(claim):
    tiempo = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("time")
    m = re.match(r"\+(\d{4})", tiempo or "")
    return int(m.group(1)) if m else None


def peliculas_wikidata(titulo):
    """Las peliculas que se llaman asi, con su año y su id de Letterboxd."""
    ids = []
    fallos = 0
    for idioma in ("en", "es"):
        # Por los dos lados: el buscador mira etiquetas y alias del idioma que
        # se le pide, y una ficha puede estar con el titulo original o con el
        # traducido. "El Bola" solo aparece buscando en español.
        datos = wikidata({"action": "wbsearchentities", "search": titulo,
                          "language": idioma, "uselang": idioma,
                          "type": "item", "limit": 15})
        fallos += datos is None
        ids += [r["id"] for r in (datos or {}).get("search", [])]
    if fallos == 2:
        return None  # no es que no haya ninguna: es que no se ha podido preguntar
    ids = list(dict.fromkeys(ids))
    if not ids:
        return []

    datos = wikidata({"action": "wbgetentities", "ids": "|".join(ids[:50]),
                      "props": "claims|labels|aliases", "languages": "en|es"})
    if datos is None:
        return None
    datos = datos or {}
    salida = []
    for entidad in (datos.get("entities") or {}).values():
        claims = entidad.get("claims") or {}
        # Sin id de Letterboxd no hay cartel que bajar, y ademas es la mejor
        # señal de que la entidad es una pelicula: no lo lleva ni un libro ni
        # un disco ni el personaje que sale en ella.
        if "P6127" not in claims:
            continue
        nombres = [v["value"] for v in (entidad.get("labels") or {}).values()]
        nombres += [a["value"] for lista in (entidad.get("aliases") or {}).values()
                    for a in lista]
        if not encaja(titulo, *nombres):
            continue
        años = [a for a in (año_de(c) for c in claims.get("P577", [])) if a]
        salida.append({"letterboxd": claims["P6127"][0]["mainsnak"]["datavalue"]["value"],
                       "year": min(años) if años else None,
                       "nombre": nombres[0]})
    return salida


def letterboxd_id(titulo, year):
    """El id de la pelicula en Letterboxd, o None y el motivo de no darlo.

    Antes vacia que equivocada: si quedan dos candidatas y nada que las separe,
    no se elige ninguna. Con el cartel de otra pelicula la ficha miente; sin
    cartel solo esta a medias.
    """
    candidatas = peliculas_wikidata(titulo)
    if candidatas is None:
        return None, "no he podido consultar Wikidata"
    if not candidatas:
        return None, "Wikidata no la encuentra"

    if not year:
        if len(candidatas) == 1:
            return candidatas[0]["letterboxd"], f"Wikidata ({candidatas[0]['nombre']})"
        return None, f"{len(candidatas)} candidatas y la ficha no dice el año"

    year = int(year)
    # El año exacto manda. El margen de uno es solo para cuando no hay ninguna
    # exacta, porque el estreno en festival y el comercial caen en años
    # distintos; aplicado antes, "Little Women" de 2019 empata con la de 2018.
    justas = ([c for c in candidatas if c["year"] == year]
              or [c for c in candidatas if c["year"] and abs(c["year"] - year) <= 1])
    if len(justas) > 1:
        exactas = [c for c in justas if normal(c["nombre"]) == normal(titulo)]
        justas = exactas or justas
    if len(justas) == 1:
        return justas[0]["letterboxd"], f"Wikidata ({justas[0]['nombre']}, {justas[0]['year']})"
    if justas:
        return None, "varias del mismo año y ninguna encaja mejor"
    return None, ("ninguna es de " + str(year) + ": "
                  + ", ".join(f"{c['nombre']} ({c['year']})" for c in candidatas[:3]))


# Letterboxd enlaza en la misma pagina a TMDB, que es de donde saca su ficha.
TMDB_RE = re.compile(r"https://www\.themoviedb\.org/(?:movie|tv)/\d+")


def ficha_letterboxd(slug):
    """Lo que la pagina de la pelicula declara de si misma.

    Sale todo de la misma peticion, asi que pedir el cartel es tambien saber
    quien dirige, de que va y de que año es, sin volver a buscar en ningun
    sitio.

    Ojo con `sinopsis`: **ese texto no es de Letterboxd**, es de TMDB, a quien
    enlazan en la propia pagina. Por eso se devuelve tambien `tmdb`: quien la
    use tiene que citar a TMDB, no a ellos. Y viene en ingles siempre.
    """
    crudo = pedir(f"https://letterboxd.com/film/{slug}/", binario=True)
    html = (crudo or b"").decode("utf-8", "ignore")
    m = JSONLD_RE.search(html)
    if not m:
        return {}
    try:
        # La pagina envuelve el JSON en un comentario, que no es JSON valido.
        datos = json.loads(re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S).strip())
    except json.JSONDecodeError:
        return {}
    cartel = datos.get("image") or ""
    # El estreno esta en releasedEvent en unas fichas y en dateCreated en
    # otras: The Odyssey trae releasedEvent a null y la fecha solo en la
    # segunda, asi que hay que mirar las dos.
    estrenos = datos.get("releasedEvent") or []
    estreno = str((estrenos[0].get("startDate") if estrenos else None)
                  or datos.get("dateCreated") or "")
    tmdb = TMDB_RE.search(html)
    return {
        "titulo": datos.get("name"),
        # El tamaño va en la propia ruta y viene pedido a 600 de ancho. A 1000
        # llega nitido a la tarjeta de 220 px hasta en una pantalla de 3x, y
        # ocupa lo mismo despues de pasar por el WebP de portadas.py.
        "cartel": cartel.replace("-0-600-0-900-crop", "-0-1000-0-1500-crop") or None,
        "direccion": [p.get("name") for p in datos.get("director") or [] if p.get("name")],
        "sinopsis": datos.get("description") or None,
        "tmdb": tmdb.group(0) if tmdb else None,
        "year": int(estreno[:4]) if estreno[:4].isdigit() else None,
    }


def asegurar_letterboxd(md, campos):
    """El id de la ficha; si no lo tiene, se busca una vez y se apunta.

    Los juegos entran de Steam con su `appid` y los discos de ListenBrainz con
    su `mbid`, pero una pelicula escrita a mano no trae nada con que buscar.
    Se resuelve una sola vez: lo necesitan tanto portadas.py como datos.py, y
    dejarlo escrito ahorra dos peticiones a Wikidata en cada pasada.
    """
    if campos.get("letterboxd"):
        return campos["letterboxd"], "ya estaba en la ficha"
    slug, detalle = letterboxd_id(campos.get("title") or md.stem, campos.get("year"))
    if slug:
        escribir_campos(md, {"letterboxd": slug})
        campos["letterboxd"] = slug
    return slug, detalle
