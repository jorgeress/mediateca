#!/usr/bin/env python3
"""Crea fichas en la vault a partir de lo que ya tienes en otros sitios.

  letterboxd-rss USUARIO   peliculas: el diario publico del perfil
  letterboxd RUTA          peliculas: el export CSV, si tienes cuenta Pro
  steam RUTA               juegos: la pagina del perfil o el export
  listenbrainz USUARIO     discos: lo mas escuchado, sin clave ninguna
  spotify-export RUTA      discos: lo mismo desde el zip de Spotify

Ninguna de estas vias pide pagar ni registrar una aplicacion. Se antepone el
nombre del script: scripts/importar.py letterboxd-rss tu_usuario

Por defecto va en modo rapido: solo entra lo que da senal de haberte importado
(8 horas jugadas en Steam, 4 estrellas en Letterboxd). Con --completo entra
todo, y los umbrales se mueven con --min-horas y --min-nota.

Todo entra en borrador: `draft: true`, `nota` vacia y el cuerpo en blanco. La
excepcion son las peliculas, que si traen tu puntuacion porque Letterboxd es la
unica de las tres fuentes que sabe si algo te gusto. Quartz no publica lo que
lleva `draft`, asi que la web sigue enseñando solo lo que hayas ascendido a
mano; en Obsidian se ven todas. Con --sin-borrador entran publicadas.

Nunca se pisa una ficha que ya exista, asi que se puede repetir cuando quieras
para recoger solo lo nuevo. Despues conviene pasar scripts/portadas.py.
"""

import argparse
import csv
import html
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from mediateca import VAULT, nombre_de_fichero, normal, pedir, yaml_valor

CAMPOS = ["tipo", "year", "autor", "nota", "estado", "favorito", "portada", "tags"]

# Umbrales del modo rapido. Ninguna fuente sabe si algo te gusto salvo
# Letterboxd, asi que el resto se criba por la unica senal que dan: el uso.
MIN_HORAS = 8
MIN_NOTA = 8  # cuatro estrellas de Letterboxd
MIN_MS = 20 * 60 * 1000  # menos de veinte minutos no es "lo mas escuchado"


def plural(n, singular, plural_):
    return f"{n} {singular if n == 1 else plural_}"


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
    lineas = [f"{c}: {yaml_valor(campos.get(c))}".rstrip() for c in orden]
    if campos.get("tags") is None:
        lineas[orden.index("tags")] = "tags: []"
    if borrador:
        # Quartz se salta las notas con draft; Obsidian las sigue enseñando.
        lineas.append("draft: true")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("---\n" + "\n".join(lineas) + "\n---\n\n" + cuerpo,
                       encoding="utf-8")
    return destino


def ficheros(ruta, patron):
    """Saca los ficheros que encajen, venga la ruta como zip, carpeta o fichero."""
    ruta = Path(ruta).expanduser()
    if ruta.is_file() and ruta.suffix.lower() == ".zip":
        with zipfile.ZipFile(ruta) as z:
            for nombre in z.namelist():
                if re.search(patron, Path(nombre).name, re.I):
                    yield Path(nombre).name, z.read(nombre)
    elif ruta.is_dir():
        for p in sorted(ruta.rglob("*")):
            if p.is_file() and re.search(patron, p.name, re.I):
                yield p.name, p.read_bytes()
    elif ruta.is_file():
        yield ruta.name, ruta.read_bytes()


# --- Letterboxd --------------------------------------------------------------

def importar_letterboxd(args):
    """El export trae un csv por lista; interesan las notas, lo visto y la watchlist."""
    pelis = {}
    encontrados = []
    for nombre, datos in ficheros(args.ruta, r"\.csv$"):
        filas = list(csv.DictReader(io.StringIO(datos.decode("utf-8-sig"))))
        if not filas or "Name" not in filas[0]:
            continue
        encontrados.append(f"{nombre} ({len(filas)})")
        for fila in filas:
            titulo = (fila.get("Name") or "").strip()
            if not titulo:
                continue
            peli = pelis.setdefault(titulo, {"year": fila.get("Year"), "nota": None,
                                             "estado": "terminado"})
            if "watchlist" in nombre.lower():
                peli["estado"] = "pendiente"
            else:
                peli["estado"] = "terminado"
            if fila.get("Rating"):
                # Letterboxd puntua de 0,5 a 5 estrellas; aqui la escala es de 1 a 10.
                peli["nota"] = int(round(float(fila["Rating"]) * 2))

    if not encontrados:
        print("No he encontrado ningún csv de Letterboxd en esa ruta.")
        return 1
    print("Leído: " + ", ".join(encontrados))
    return volcar(pelis, "pelis", "peli", args)


def importar_letterboxd_rss(args):
    """El diario publico del perfil, que no pide cuenta de pago.

    Da menos historial que el export (las ultimas cien entradas mas o menos)
    pero exactamente el mismo dato: titulo, año y tu puntuacion.
    """
    usuario = args.usuario.strip().strip("/").split("/")[-1]
    crudo = pedir(f"https://letterboxd.com/{usuario}/rss/", binario=True)
    if not crudo:
        print(f"No he podido leer el diario de '{usuario}'. Comprueba el nombre y\n"
              "que el perfil no sea privado.")
        return 1

    espacio = {"letterboxd": "https://letterboxd.com"}
    pelis = {}
    for entrada in ElementTree.fromstring(crudo).iter("item"):
        titulo = entrada.findtext("letterboxd:filmTitle", namespaces=espacio)
        if not titulo:
            continue  # las listas y las reseñas sueltas no traen pelicula
        nota = entrada.findtext("letterboxd:memberRating", namespaces=espacio)
        año = entrada.findtext("letterboxd:filmYear", namespaces=espacio)
        pelis[titulo] = {
            "year": año,
            "estado": "terminado",
            "nota": int(round(float(nota) * 2)) if nota else None,
        }

    if not pelis:
        print("El diario no tiene entradas de películas.")
        return 1
    print(f"Diario de {usuario}: {len(pelis)} películas.")
    return volcar(pelis, "pelis", "peli", args)


# --- Steam -------------------------------------------------------------------

def buscar_juegos(dato, hallados):
    """Recorre el volcado buscando cosas con appid y nombre.

    El export de Steam ha cambiado de forma varias veces, asi que en vez de
    dar por buena una ruta concreta se rastrea el JSON entero.
    """
    if isinstance(dato, dict):
        appid = dato.get("appid") or dato.get("appId") or dato.get("app_id")
        nombre = dato.get("name") or dato.get("game_name") or dato.get("app_name")
        if appid and nombre:
            minutos = (dato.get("playtime_forever") or dato.get("playtime")
                       or dato.get("playtime_minutes") or 0)
            try:
                minutos = int(minutos)
            except (TypeError, ValueError):
                minutos = 0
            previo = hallados.get(str(nombre))
            if previo is None or minutos > previo["minutos"]:
                hallados[str(nombre)] = {"minutos": minutos, "appid": int(appid),
                                         "capsula": dato.get("capsule_filename")}
        for v in dato.values():
            buscar_juegos(v, hallados)
    elif isinstance(dato, list):
        for v in dato:
            buscar_juegos(v, hallados)


def juegos_de_xml(texto, hallados):
    """La pagina de juegos del perfil con ?xml=1, guardada desde el navegador."""
    for juego in ElementTree.fromstring(texto).iter("game"):
        nombre = juego.findtext("name")
        if not nombre:
            continue
        horas = (juego.findtext("hoursOnRecord") or "0").replace(",", "")
        try:
            minutos = int(float(horas) * 60)
        except ValueError:
            minutos = 0
        hallados[nombre] = {"minutos": minutos}


JUEGO_SUELTO = re.compile(r'\{[^{}]*?"appid":\s*\d+[^{}]*?\}')


def juegos_de_html(texto, hallados):
    """La pagina del perfil, guardada desde el navegador.

    La lista no esta en el HTML visible sino en un JSON dentro de un <script>,
    y viene escapada dos veces: una por ser una cadena JSON y otra por ir
    dentro del propio script. Como el numero de vueltas depende de como la
    guarde cada navegador, se desescapa poco a poco y se mira en cada vuelta,
    en vez de dar por buena una forma concreta.
    """
    for patron in (r'data-profile-gameslist="([^"]*)"', r"var rgGames = (\[.*?\]);"):
        m = re.search(patron, texto, re.S)
        if m:
            try:
                buscar_juegos(json.loads(html.unescape(m.group(1))), hallados)
                return
            except json.JSONDecodeError:
                pass

    variante = texto
    for _ in range(4):
        for trozo in JUEGO_SUELTO.findall(variante):
            try:
                buscar_juegos(json.loads(trozo), hallados)
            except json.JSONDecodeError:
                continue
        siguiente = variante.replace('\\"', '"').replace("\\/", "/")
        if siguiente == variante:
            return
        variante = siguiente


def importar_steam(args):
    hallados = {}
    leidos = []
    for nombre, datos in ficheros(args.ruta, r"\.(json|xml|html?)$"):
        texto = datos.decode("utf-8", "replace")
        antes = len(hallados)
        try:
            if texto.lstrip().startswith("<?xml") or "<gamesList" in texto[:2000]:
                juegos_de_xml(texto, hallados)
            elif texto.lstrip().startswith("<"):
                juegos_de_html(texto, hallados)
            else:
                buscar_juegos(json.loads(texto), hallados)
        except (json.JSONDecodeError, ElementTree.ParseError):
            continue
        if len(hallados) > antes:
            leidos.append(nombre)
    if not hallados:
        print("No he encontrado juegos en esa ruta. Lo que entiende:\n"
              "  - steamcommunity.com/my/games?tab=all guardada con Ctrl+S,\n"
              "    con la sesión abierta\n"
              "  - el zip del export de datos de Steam\n"
              "Si tienes una de las dos y aun así falla, enséñamela y lo ajusto.")
        return 1
    print(f"Leído: {', '.join(leidos[:6])}{' ...' if len(leidos) > 6 else ''}")

    juegos = {}
    for titulo, dato in hallados.items():
        horas = round(dato["minutos"] / 60)
        juegos[titulo] = {
            # Steam sabe cuanto has jugado, no si lo terminaste: nadie puede
            # deducir eso, asi que lo jugado entra como "en curso".
            "estado": "pendiente" if dato["minutos"] == 0 else "en curso",
            "horas": horas or None,
            "appid": dato.get("appid"),
            "capsula": dato.get("capsula"),
        }
    return volcar(juegos, "juegos", "juego", args)


# --- ListenBrainz ------------------------------------------------------------

# Las ventanas que admite su API de estadisticas.
RANGOS = {"mes": ("month", "del último mes"),
          "trimestre": ("quarter", "del último trimestre"),
          "semestre": ("half_yearly", "del último medio año"),
          "año": ("year", "del último año"),
          "todo": ("all_time", "de siempre")}


def importar_listenbrainz(args):
    """Los discos mas escuchados, de MusicBrainz y sin clave ninguna.

    ListenBrainz es el registro de escuchas de MusicBrainz, la misma gente del
    Cover Art Archive de donde salen las caratulas. Su API de estadisticas se
    lee sin registrarse y ademas devuelve el mbid del disco, asi que la portada
    se baja luego exacta en vez de por busqueda de texto.
    """
    usuario = args.usuario.strip().strip("/").split("/")[-1]
    rango, cuando = RANGOS[args.periodo]
    datos = pedir(f"https://api.listenbrainz.org/1/stats/user/{usuario}/releases"
                  f"?count={args.top}&range={rango}")
    if datos is None:
        print(f"No he podido leer las estadísticas de '{usuario}'. Comprueba el\n"
              "nombre de usuario en listenbrainz.org.")
        return 1

    lanzamientos = (datos.get("payload") or {}).get("releases") or []
    if not lanzamientos:
        print(f"'{usuario}' no tiene escuchas registradas en esa ventana.\n"
              "Si acabas de crear la cuenta, conecta Spotify o sube tu historial\n"
              "ampliado en listenbrainz.org/settings/import y vuelve luego.")
        return 1

    discos = {}
    for disco in lanzamientos:
        titulo = disco.get("release_name")
        if not titulo:
            continue
        discos[titulo] = {"autor": disco.get("artist_name"), "estado": "terminado",
                          "mbid": disco.get("caa_release_mbid") or disco.get("release_mbid")}
    print(f"{plural(len(discos), 'disco', 'discos')} entre lo más escuchado {cuando}.")
    return volcar(discos, "musica", "album", args, cribar=False)


# --- Spotify, por export -----------------------------------------------------

def sacar(fila, *claves):
    for clave in claves:
        if fila.get(clave):
            return fila[clave]
    return None


def importar_spotify_export(args):
    """Lee el zip de Spotify sin necesidad de crear ninguna app.

    Hay dos exports y no dan lo mismo. El de la cuenta trae YourLibrary.json
    (lo guardado) y un historial reciente que NO lleva el nombre del album,
    asi que de ese historial no salen discos. El historial ampliado, que tarda
    hasta un mes, si lleva el album de cada reproduccion, y ese es el que
    permite ordenar por lo mas escuchado de verdad.
    """
    guardados, escuchados, sin_album = {}, {}, 0
    leidos, historial_corto = [], False
    for nombre, datos in ficheros(args.ruta, r"\.json$"):
        try:
            contenido = json.loads(datos.decode("utf-8", "replace"))
        except json.JSONDecodeError:
            continue

        if isinstance(contenido, dict) and "albums" in contenido:
            for album in contenido["albums"] or []:
                titulo = sacar(album, "album", "album_name", "name")
                if titulo:
                    guardados[titulo] = {"autor": sacar(album, "artist", "artist_name"),
                                         "estado": "terminado"}
            leidos.append(nombre)
            continue

        if isinstance(contenido, list) and contenido and isinstance(contenido[0], dict):
            reproducciones = 0
            for fila in contenido:
                titulo = sacar(fila, "master_metadata_album_album_name", "albumName")
                ms = sacar(fila, "ms_played", "msPlayed") or 0
                if not titulo:
                    if sacar(fila, "master_metadata_track_name", "trackName"):
                        sin_album += 1
                        historial_corto = True
                    continue
                dato = escuchados.setdefault(titulo, {"ms": 0, "autor": None,
                                                      "estado": "terminado"})
                dato["ms"] += int(ms)
                dato["autor"] = dato["autor"] or sacar(
                    fila, "master_metadata_album_artist_name", "artistName")
                reproducciones += 1
            if reproducciones:
                leidos.append(nombre)

    if not leidos and not historial_corto:
        print("No he encontrado datos de Spotify en esa ruta.")
        return 1
    if leidos:
        print(f"Leído: {', '.join(leidos[:5])}{' ...' if len(leidos) > 5 else ''}")
    if sin_album:
        print(plural(sin_album, "reproducción viene", "reproducciones vienen")
              + " sin nombre de álbum. Eso es el historial\n"
              "corto del export de la cuenta, que no lo trae: para ordenar por lo más\n"
              "escuchado hace falta pedir el historial ampliado, que tarda hasta un mes.")

    if args.completo:
        if not guardados:
            print("No hay YourLibrary.json en esa ruta, que es donde va lo guardado.")
            return 1
        print(f"{len(guardados)} álbumes guardados.")
        return volcar(guardados, "musica", "album", args, cribar=False)

    if not escuchados:
        print("\nSin historial con álbum no puedo ordenar por lo más escuchado.\n"
              "Con --completo entran los álbumes guardados que traiga el export.")
        return 1
    oidos = {k: v for k, v in escuchados.items() if v["ms"] >= MIN_MS}
    mejores = sorted(oidos, key=lambda k: oidos[k]["ms"], reverse=True)[:args.top]
    discos = {t: {"autor": oidos[t]["autor"], "estado": "terminado"} for t in mejores}
    ms = sum(oidos[t]["ms"] for t in mejores)
    tiempo = (plural(round(ms / 3600000), "hora", "horas") if ms >= 3600000
              else plural(round(ms / 60000), "minuto", "minutos"))
    print(plural(len(discos), "disco entre lo más escuchado",
                 "discos entre lo más escuchado") + f" ({tiempo} en total).")
    return volcar(discos, "musica", "album", args, cribar=False)


# --- comun -------------------------------------------------------------------

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


def criba(elementos, args):
    """Aparta lo que no llega al umbral. Devuelve lo que entra y lo que no."""
    if args.completo:
        return elementos, {}
    dentro, fuera = {}, {}
    for titulo, dato in elementos.items():
        if dato.get("horas") is not None:
            pasa = dato["horas"] >= args.min_horas
        elif dato.get("nota") is not None:
            pasa = dato["nota"] >= args.min_nota
        else:
            # Sin horas ni nota no hay con que decidir: fuera del modo rapido.
            pasa = False
        (dentro if pasa else fuera)[titulo] = dato
    return dentro, fuera


def volcar(elementos, carpeta, tipo, args, cribar=True):
    elementos, apartados = criba(elementos, args) if cribar else (elementos, {})
    avisos = parecidos(carpeta, elementos)
    nuevas = repetidas = 0
    for titulo, dato in sorted(elementos.items()):
        campos = {"tipo": tipo, "year": dato.get("year"), "autor": dato.get("autor"),
                  "nota": dato.get("nota"), "estado": dato.get("estado", "pendiente"),
                  "favorito": False, "portada": None, "tags": None}
        if dato.get("horas"):
            campos["horas"] = dato["horas"]
        if dato.get("mbid"):
            # El identificador del disco en MusicBrainz: con el, la portada se
            # baja exacta y no por parecido de nombre.
            campos["mbid"] = dato["mbid"]
        if dato.get("appid"):
            # Lo mismo para los juegos: buscar por nombre falla con los
            # free-to-play, y con el appid la caratula sale siempre.
            campos["appid"] = dato["appid"]
        if dato.get("capsula") and "/" in str(dato["capsula"]):
            # Los juegos recientes no estan en la ruta clasica del CDN: su
            # caratula cuelga de un hash que solo aparece en tu propia pagina.
            campos["capsula"] = dato["capsula"]
        if args.dry_run:
            nuevas += 1
            continue
        if escribir_ficha(carpeta, titulo, campos, borrador=not args.sin_borrador):
            nuevas += 1
        else:
            repetidas += 1

    hecho = ("ficha se crearía", "fichas se crearían") if args.dry_run else (
        "ficha creada", "fichas creadas")
    print(f"\n{plural(nuevas, *hecho)} en content/{carpeta}/, "
          f"{plural(repetidas, 'ya estaba', 'ya estaban')}.")
    if apartados:
        umbral = (f"menos de {args.min_horas} horas" if carpeta == "juegos"
                  else f"nota por debajo de {args.min_nota}, o ninguna")
        print(plural(len(apartados), "ficha apartada", "fichas apartadas")
              + f" por el modo rápido ({umbral}). Con --completo entran todas.")
    if avisos:
        print("\nSe parecen a fichas que ya tenías. Si son la misma obra, únelas:")
        for aviso in avisos:
            print("  " + aviso)
    if nuevas and not args.dry_run:
        if not args.sin_borrador:
            print("Entran con draft: true, así que no salen en la web hasta que les\n"
                  "quites la línea. En Obsidian se ven todas.")
        print("Ahora: scripts/portadas.py")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="dice qué haría, sin escribir")
    p.add_argument("--completo", action="store_true",
                   help="sin umbrales: entra todo lo que traiga el export")
    p.add_argument("--min-horas", type=int, default=MIN_HORAS,
                   help=f"juegos: horas mínimas jugadas (por defecto {MIN_HORAS})")
    p.add_argument("--min-nota", type=int, default=MIN_NOTA,
                   help=f"películas: nota mínima (por defecto {MIN_NOTA}, o sea 4 estrellas)")
    p.add_argument("--sin-borrador", action="store_true",
                   help="las fichas entran publicadas, sin draft")
    subs = p.add_subparsers(dest="fuente", required=True)

    lb = subs.add_parser("letterboxd", help="export de Letterboxd")
    lb.add_argument("ruta", help="el .zip del export, la carpeta o un csv suelto")
    lb.set_defaults(func=importar_letterboxd)

    lr = subs.add_parser("letterboxd-rss", help="el diario público, sin cuenta Pro")
    lr.add_argument("usuario", help="tu nombre de usuario en Letterboxd")
    lr.set_defaults(func=importar_letterboxd_rss)

    st = subs.add_parser("steam", help="export de datos de Steam")
    st.add_argument("ruta", help="el .zip del export o la carpeta")
    st.set_defaults(func=importar_steam)

    lb = subs.add_parser("listenbrainz", help="lo más escuchado, sin clave ninguna")
    lb.add_argument("usuario", help="tu nombre de usuario en listenbrainz.org")
    lb.add_argument("--periodo", choices=list(RANGOS), default="año",
                    help="ventana (por defecto, año)")
    lb.add_argument("--top", type=int, default=40, help="cuántos discos (por defecto 40)")
    lb.set_defaults(func=importar_listenbrainz)

    se = subs.add_parser("spotify-export", help="lo mismo desde el zip, sin crear app")
    se.add_argument("ruta", help="el .zip del export de Spotify o la carpeta")
    se.add_argument("--top", type=int, default=40, help="cuántos discos (por defecto 40)")
    se.set_defaults(func=importar_spotify_export)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
