"""Lo que comparten los scripts de la mediateca: rutas, fichas y peticiones."""

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

UA = "mediateca/1.0 (https://github.com/jorgeress/mediateca)"

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
        if isinstance(valor, (list, tuple)):
            # En bloque y no entre corchetes, que es como los deja Obsidian.
            linea = clave + ":" + "".join(f"\n  - {yaml_valor(v)}" for v in valor)
        else:
            linea = f"{clave}: {yaml_valor(valor)}".rstrip()
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
