#!/usr/bin/env python3
"""Crea fichas en la vault a partir de lo que ya tienes en otros sitios.

  scripts/importar.py letterboxd RUTA   export de Letterboxd (.zip, carpeta o csv)
  scripts/importar.py steam RUTA        export de datos de Steam (.zip o carpeta)
  scripts/importar.py spotify           lo mas escuchado, por OAuth
  scripts/importar.py spotify-export RUTA   lo mismo desde el zip, sin app

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
import base64
import csv
import hashlib
import http.server
import io
import json
import re
import secrets
import sys
import urllib.parse
import webbrowser
import zipfile
from pathlib import Path

from mediateca import VAULT, nombre_de_fichero, normal, pedir

CAMPOS = ["tipo", "year", "autor", "nota", "estado", "favorito", "portada", "tags"]

# Umbrales del modo rapido. Ninguna fuente sabe si algo te gusto salvo
# Letterboxd, asi que el resto se criba por la unica senal que dan: el uso.
MIN_HORAS = 8
MIN_NOTA = 8  # cuatro estrellas de Letterboxd
MIN_MS = 20 * 60 * 1000  # menos de veinte minutos no es "lo mas escuchado"


def plural(n, singular, plural_):
    return f"{n} {singular if n == 1 else plural_}"


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
        return '"' + v.replace('"', r"\"") + '"'
    return v


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
                hallados[str(nombre)] = {"minutos": minutos}
        for v in dato.values():
            buscar_juegos(v, hallados)
    elif isinstance(dato, list):
        for v in dato:
            buscar_juegos(v, hallados)


def importar_steam(args):
    hallados = {}
    leidos = []
    for nombre, datos in ficheros(args.ruta, r"\.json$"):
        try:
            buscar_juegos(json.loads(datos.decode("utf-8", "replace")), hallados)
        except json.JSONDecodeError:
            continue
        leidos.append(nombre)
    if not hallados:
        print("No he encontrado juegos en esa ruta. Enséñame qué ficheros trae el\n"
              "export y ajusto el rastreo: su formato cambia cada dos por tres.")
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
        }
    return volcar(juegos, "juegos", "juego", args)


# --- Spotify -----------------------------------------------------------------

CLIENTE_SPOTIFY = Path.home() / ".config" / "mediateca" / "spotify-client-id"
REDIRECCION = "http://127.0.0.1:8888/callback"
PERMISOS = "user-top-read user-library-read"

# Las tres ventanas que ofrece Spotify para lo mas escuchado.
VENTANAS = {"corto": ("short_term", "últimas cuatro semanas"),
            "medio": ("medium_term", "últimos seis meses"),
            "largo": ("long_term", "de varios años")}


def codigo_de_autorizacion(client_id, verificador):
    """Abre el navegador y recoge el codigo que Spotify devuelve al volver."""
    reto = base64.urlsafe_b64encode(
        hashlib.sha256(verificador.encode()).digest()).decode().rstrip("=")
    estado = secrets.token_urlsafe(16)
    url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "client_id": client_id, "response_type": "code",
        "redirect_uri": REDIRECCION, "scope": PERMISOS,
        "code_challenge_method": "S256", "code_challenge": reto, "state": estado})

    recogido = {}

    class Recoge(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            recogido.update(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h1>Listo</h1><p>Ya puedes cerrar esta pestaña.</p>"
                             .encode("utf-8"))

        def log_message(self, *_):
            pass

    print("Abriendo el navegador para que autorices la lectura de tu biblioteca.")
    print(f"Si no se abre solo: {url}\n")
    webbrowser.open(url)
    with http.server.HTTPServer(("127.0.0.1", 8888), Recoge) as servidor:
        servidor.handle_request()

    if recogido.get("state", [None])[0] != estado:
        print("El estado devuelto no coincide con el enviado. Abortado.")
        return None
    return recogido.get("code", [None])[0]


def importar_spotify(args):
    client_id = args.client_id or (CLIENTE_SPOTIFY.read_text().strip()
                                   if CLIENTE_SPOTIFY.exists() else None)
    if not client_id:
        print("Falta el client id de tu app de Spotify:\n"
              "  1. https://developer.spotify.com/dashboard, Create app.\n"
              f"  2. Redirect URI: {REDIRECCION}\n"
              "  3. mkdir -p ~/.config/mediateca && "
              f"echo TU_CLIENT_ID > {CLIENTE_SPOTIFY}\n"
              "No hace falta el client secret: se usa PKCE.")
        return 1

    verificador = secrets.token_urlsafe(64)
    codigo = codigo_de_autorizacion(client_id, verificador)
    if not codigo:
        print("No he recibido el código de autorización.")
        return 1

    token = pedir("https://accounts.spotify.com/api/token",
                  headers={"Content-Type": "application/x-www-form-urlencoded"},
                  datos=urllib.parse.urlencode({
                      "grant_type": "authorization_code", "code": codigo,
                      "redirect_uri": REDIRECCION, "client_id": client_id,
                      "code_verifier": verificador}).encode())
    if not token or "access_token" not in token:
        print("Spotify no ha dado el token. Revisa que el Redirect URI de la app\n"
              f"sea exactamente {REDIRECCION}")
        return 1

    cabecera = {"Authorization": "Bearer " + token["access_token"]}
    if args.completo:
        discos = albumes_guardados(cabecera)
        print(f"Spotify ha devuelto {len(discos)} álbumes guardados.")
    else:
        discos = albumes_mas_escuchados(cabecera, args.periodo, args.top)
        print(f"{len(discos)} discos entre lo más escuchado ({VENTANAS[args.periodo][1]}).")
    return volcar(discos, "musica", "album", args, cribar=False)


def ficha_de_album(album):
    return {"autor": ", ".join(a["name"] for a in album.get("artists", [])),
            "year": (album.get("release_date") or "")[:4] or None,
            "estado": "terminado"}


def albumes_guardados(cabecera):
    discos = {}
    url = "https://api.spotify.com/v1/me/albums?limit=50"
    while url:
        pagina = pedir(url, headers=cabecera)
        if not pagina:
            break
        for elemento in pagina.get("items", []):
            album = elemento.get("album", {})
            if album.get("name"):
                discos[album["name"]] = ficha_de_album(album)
        url = pagina.get("next")
    return discos


def albumes_mas_escuchados(cabecera, periodo, cuantos):
    """Spotify da las canciones mas escuchadas, no los discos: se agregan.

    Un disco con cinco canciones en tu top pesa mas que uno con una suelta,
    que es justo el orden que interesa.
    """
    ventana = VENTANAS[periodo][0]
    peso, fichas = {}, {}
    for desplazamiento in (0, 50):
        pagina = pedir("https://api.spotify.com/v1/me/top/tracks"
                       f"?limit=50&offset={desplazamiento}&time_range={ventana}",
                       headers=cabecera)
        for puesto, cancion in enumerate((pagina or {}).get("items", [])):
            album = cancion.get("album", {})
            titulo = album.get("name")
            if not titulo:
                continue
            # Cuanto mas arriba esta la cancion, mas suma su disco.
            peso[titulo] = peso.get(titulo, 0) + (100 - desplazamiento - puesto)
            fichas.setdefault(titulo, ficha_de_album(album))
    mejores = sorted(peso, key=peso.get, reverse=True)[:cuantos]
    return {titulo: fichas[titulo] for titulo in mejores}


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

    st = subs.add_parser("steam", help="export de datos de Steam")
    st.add_argument("ruta", help="el .zip del export o la carpeta")
    st.set_defaults(func=importar_steam)

    sp = subs.add_parser("spotify", help="por OAuth: lo más escuchado, o lo guardado")
    sp.add_argument("--client-id", help=f"por defecto, {CLIENTE_SPOTIFY}")
    sp.add_argument("--periodo", choices=list(VENTANAS), default="medio",
                    help="ventana de lo más escuchado (por defecto, medio)")
    sp.add_argument("--top", type=int, default=40, help="cuántos discos (por defecto 40)")
    sp.set_defaults(func=importar_spotify)

    se = subs.add_parser("spotify-export", help="lo mismo desde el zip, sin crear app")
    se.add_argument("ruta", help="el .zip del export de Spotify o la carpeta")
    se.add_argument("--top", type=int, default=40, help="cuántos discos (por defecto 40)")
    se.set_defaults(func=importar_spotify_export)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
