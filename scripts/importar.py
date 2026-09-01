#!/usr/bin/env python3
"""Crea fichas en la vault a partir de lo que ya tienes en otros sitios.

  scripts/importar.py letterboxd RUTA   export de Letterboxd (.zip, carpeta o csv)
  scripts/importar.py steam RUTA        export de datos de Steam (.zip o carpeta)
  scripts/importar.py spotify           albumes guardados, por OAuth

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


def codigo_de_autorizacion(client_id, verificador):
    """Abre el navegador y recoge el codigo que Spotify devuelve al volver."""
    reto = base64.urlsafe_b64encode(
        hashlib.sha256(verificador.encode()).digest()).decode().rstrip("=")
    estado = secrets.token_urlsafe(16)
    url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "client_id": client_id, "response_type": "code",
        "redirect_uri": REDIRECCION, "scope": "user-library-read",
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
    discos = {}
    url = "https://api.spotify.com/v1/me/albums?limit=50"
    while url:
        pagina = pedir(url, headers=cabecera)
        if not pagina:
            break
        for elemento in pagina.get("items", []):
            album = elemento.get("album", {})
            titulo = album.get("name")
            if not titulo:
                continue
            discos[titulo] = {
                "autor": ", ".join(a["name"] for a in album.get("artists", [])),
                "year": (album.get("release_date") or "")[:4] or None,
                "estado": "terminado",
            }
        url = pagina.get("next")
    print(f"Spotify ha devuelto {len(discos)} álbumes guardados.")
    return volcar(discos, "musica", "album", args)


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


def volcar(elementos, carpeta, tipo, args):
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

    verbo = "se crearían" if args.dry_run else "creadas"
    print(f"\n{nuevas} fichas {verbo} en content/{carpeta}/, "
          f"{repetidas} ya estaban.")
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
    p.add_argument("--sin-borrador", action="store_true",
                   help="las fichas entran publicadas, sin draft")
    subs = p.add_subparsers(dest="fuente", required=True)

    lb = subs.add_parser("letterboxd", help="export de Letterboxd")
    lb.add_argument("ruta", help="el .zip del export, la carpeta o un csv suelto")
    lb.set_defaults(func=importar_letterboxd)

    st = subs.add_parser("steam", help="export de datos de Steam")
    st.add_argument("ruta", help="el .zip del export o la carpeta")
    st.set_defaults(func=importar_steam)

    sp = subs.add_parser("spotify", help="álbumes guardados, por OAuth")
    sp.add_argument("--client-id", help=f"por defecto, {CLIENTE_SPOTIFY}")
    sp.set_defaults(func=importar_spotify)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
