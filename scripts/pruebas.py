#!/usr/bin/env python3
"""Las pruebas de los scripts, sin red: python3 scripts/pruebas.py

No cubren todo a proposito. Cubren dos cosas: las funciones que deciden si una
ficha se rellena o se queda vacia, que es donde un fallo es silencioso, y los
casos concretos que ya mordieron una vez. Cada uno de esos lleva escrito de
donde salio, porque una prueba sin su historia es la primera que alguien borra
por parecer una tonteria.

Nada de aqui sale a la red. Lo que necesita una respuesta se la da a mano, que
ademas es la unica forma de probar el caso de la fuente caida.

Hace falta Pillow, como el resto de los scripts: portadas.py lo importa al
cargarse y de ahi cuelga media cadena de imports. Esta en requirements.txt.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

import datos
import importar
import mediateca as m
import nueva


class Cabeceras(unittest.TestCase):
    """Leer y escribir el YAML de una ficha sin romper lo que ya habia."""

    def test_lista_en_bloque_se_lee_como_lista(self):
        # Obsidian escribe asi los tags en cuanto los tocas desde su editor de
        # propiedades. Si se leyeran como vacios, un script creeria que la
        # ficha no tiene tags y los pisaria.
        campos = m.frontmatter("---\ntags:\n  - accion\n  - rpg\nnota: 9\n---\n")
        self.assertEqual(campos["tags"], ["accion", "rpg"])
        self.assertEqual(campos["nota"], "9")

    def test_lista_vacia_cuenta_como_campo_sin_poner(self):
        self.assertTrue(m.vacio("[]"))
        self.assertTrue(m.vacio([]))
        self.assertTrue(m.vacio(None))
        self.assertFalse(m.vacio("algo"))
        self.assertFalse(m.vacio(["accion"]))

    def test_una_lista_se_escribe_en_bloque(self):
        # escribir_ficha reventaba con los tags que trae la ficha de Steam
        # porque no sabia escribir una lista. Ahora hay una sola funcion que
        # escribe una linea de cabecera y la usan los dos sitios que escriben.
        self.assertEqual(m.linea_yaml("tags", ["accion", "rpg"]),
                         "tags:\n  - accion\n  - rpg")

    def test_un_valor_con_dos_puntos_se_entrecomilla(self):
        # Sin comillas, "Spider-Man: Brand New Day" parte el YAML en dos.
        self.assertEqual(m.yaml_valor("Spider-Man: Brand New Day"),
                         '"Spider-Man: Brand New Day"')

    def test_escribir_campos_no_deja_huerfana_la_lista_vieja(self):
        # Al cambiar una clave que tenia lista debajo, los elementos viejos se
        # quedarian colgando bajo la clave nueva si no se los lleva por delante.
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "f.md"
            md.write_text("---\ntipo: juego\ntags:\n  - viejo\n  - antiguo\n"
                          "nota: 9\n---\n\ncuerpo\n", encoding="utf-8")
            m.escribir_campos(md, {"tags": ["nuevo"]})
            texto = md.read_text(encoding="utf-8")
            self.assertNotIn("viejo", texto)
            self.assertNotIn("antiguo", texto)
            self.assertIn("- nuevo", texto)
            # Y lo que no se toca, no se mueve.
            self.assertIn("tipo: juego", texto)
            self.assertIn("nota: 9", texto)
            self.assertIn("cuerpo", texto)

    def test_escribir_campos_añade_una_clave_que_no_existia(self):
        # De esto vive la idea de que los scripts vayan completando la ficha:
        # datos.py y portadas.py añaden claves que la plantilla no trae.
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "f.md"
            md.write_text("---\ntipo: peli\n---\n\n", encoding="utf-8")
            m.escribir_campos(md, {"letterboxd": "harakiri"})
            self.assertIn("letterboxd: harakiri", md.read_text(encoding="utf-8"))

    def test_sin_cabecera_no_escribe_nada(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "f.md"
            md.write_text("una nota sin cabecera\n", encoding="utf-8")
            self.assertFalse(m.escribir_campos(md, {"nota": 9}))
            self.assertEqual(md.read_text(encoding="utf-8"),
                             "una nota sin cabecera\n")


class NombresYParecidos(unittest.TestCase):
    """Identificar una obra sin confundirla con otra que se llama parecido."""

    def test_el_titulo_de_verdad_se_guarda_cuando_no_cabe_en_el_fichero(self):
        # Un nombre de fichero no admite ":", asi que "Spider-Man: Brand New
        # Day" se quedaba sin los dos puntos y con eso ya no lo encontraba
        # ningun catalogo.
        self.assertEqual(m.nombre_de_fichero("Spider-Man: Brand New Day"),
                         "Spider-Man Brand New Day")
        with tempfile.TemporaryDirectory() as tmp:
            self._vault(tmp)
            m.escribir_ficha("pelis", "Spider-Man: Brand New Day", {"tipo": "peli"})
            ficha = Path(tmp) / "pelis" / "Spider-Man Brand New Day.md"
            self.assertIn('title: "Spider-Man: Brand New Day"',
                          ficha.read_text(encoding="utf-8"))

    def test_la_misma_obra_escrita_distinto_no_se_duplica(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._vault(tmp)
            self.assertIsNotNone(m.escribir_ficha("pelis", "Parásitos", {"tipo": "peli"}))
            self.assertIsNone(m.escribir_ficha("pelis", "Parasitos", {"tipo": "peli"}))

    def test_una_ficha_que_ya_existe_nunca_se_pisa(self):
        # De esto depende poder repetir un volcado para recoger solo lo nuevo.
        with tempfile.TemporaryDirectory() as tmp:
            self._vault(tmp)
            m.escribir_ficha("juegos", "Portal", {"tipo": "juego", "nota": 10})
            ficha = Path(tmp) / "juegos" / "Portal.md"
            antes = ficha.read_text(encoding="utf-8")
            self.assertIsNone(m.escribir_ficha("juegos", "Portal", {"tipo": "juego"}))
            self.assertEqual(ficha.read_text(encoding="utf-8"), antes)

    def test_lo_que_se_parece_se_avisa_pero_no_se_descarta(self):
        # "Portal" contiene a "Portal 2" y son dos juegos distintos: se avisa
        # y decide el humano.
        with tempfile.TemporaryDirectory() as tmp:
            self._vault(tmp)
            m.escribir_ficha("juegos", "Portal", {"tipo": "juego"})
            self.assertTrue(m.parecidos("juegos", ["Portal 2"]))
            self.assertFalse(m.parecidos("juegos", ["Hades"]))

    def test_una_ficha_nueva_entra_en_borrador_y_con_tags_vacios(self):
        # El invariante del README: a la web solo llega lo ascendido a mano.
        with tempfile.TemporaryDirectory() as tmp:
            self._vault(tmp)
            m.escribir_ficha("juegos", "Hades", {"tipo": "juego"})
            texto = (Path(tmp) / "juegos" / "Hades.md").read_text(encoding="utf-8")
            self.assertIn("draft: true", texto)
            self.assertIn("tags: []", texto)

    def test_encaja_admite_que_el_titulo_baile_pero_no_otra_pelicula(self):
        # El buscador de Wikipedia siempre devuelve algo, aunque no tenga nada
        # que ver: sin esta comprobacion una ficha se queda con el cartel de
        # otra pelicula.
        self.assertTrue(m.encaja("Kill Bill Vol. 1", "Kill Bill: Volumen 1"))
        self.assertFalse(m.encaja("Harakiri", "Zoolander"))
        self.assertFalse(m.encaja("", "lo que sea"))

    def _vault(self, tmp):
        m.VAULT = Path(tmp)
        self.addCleanup(setattr, m, "VAULT", m.RAIZ / "content")


class FuenteCaida(unittest.TestCase):
    """Una fuente caida no es "no hay resultados", y no se pueden confundir.

    pedir() devuelve None en los dos casos, y confundirlos manda a buscar el
    error donde no esta. Los buscadores devuelven None si no se ha podido
    preguntar y [] si de verdad no hay nada.
    """

    def test_sin_respuesta_devuelve_none(self):
        self._pedir(lambda *a, **k: None)
        self.assertIsNone(nueva.buscar_juego("lo que sea", 5))
        self.assertIsNone(nueva.buscar_album("lo que sea", 5))

    def test_respuesta_vacia_devuelve_lista_vacia(self):
        self._pedir(lambda *a, **k: [])
        self.assertEqual(nueva.buscar_juego("lo que sea", 5), [])
        self._pedir(lambda *a, **k: {"release-groups": []})
        self.assertEqual(nueva.buscar_album("lo que sea", 5), [])

    def test_un_juego_sin_appid_no_entra(self):
        # Sin appid la caratula no se puede bajar y la ficha se queda a medias.
        self._pedir(lambda *a, **k: [{"name": "Con id", "appid": 400},
                                     {"name": "Sin id"}])
        self.assertEqual([c["titulo"] for c in nueva.buscar_juego("x", 5)],
                         ["Con id"])

    def _pedir(self, falso):
        original = nueva.pedir
        nueva.pedir = falso
        self.addCleanup(setattr, nueva, "pedir", original)


class CancionesEnDiscos(unittest.TestCase):
    """Plegar las canciones guardadas en el disco que las lleva, y contarlas."""

    LIBRERIA = {"tracks": [
        {"artist": "Radiohead", "album": "In Rainbows", "track": "Nude"},
        {"artist": "Radiohead", "album": "In Rainbows", "track": "Reckoner"},
        {"artist": "Radiohead", "album": "In Rainbows", "track": "Videotape"},
        {"artist": "Portishead", "album": "Dummy", "track": "Roads"},
        {"artist": "Nick Drake", "album": "Pink Moon", "track": "Pink Moon"},
        {"artist": None, "album": None, "track": "una suelta sin disco"},
    ]}

    def test_cuenta_las_canciones_de_cada_disco(self):
        discos = importar.canciones_en_discos(self.LIBRERIA, {})
        self.assertEqual(discos["In Rainbows"]["favoritas"], 3)
        self.assertEqual(discos["Dummy"]["favoritas"], 1)
        self.assertEqual(discos["In Rainbows"]["autor"], "Radiohead")

    def test_una_cancion_sin_disco_no_inventa_un_disco(self):
        # Antes vacio que equivocado: sin nombre de album no hay nada que contar.
        discos = importar.canciones_en_discos(self.LIBRERIA, {})
        self.assertEqual(len(discos), 3)
        self.assertNotIn(None, discos)

    def test_admite_las_dos_formas_en_que_spotify_nombra_las_claves(self):
        discos = importar.canciones_en_discos(
            {"tracks": [{"albumName": "Dummy", "artistName": "Portishead"}]}, {})
        self.assertEqual(discos["Dummy"]["favoritas"], 1)
        self.assertEqual(discos["Dummy"]["autor"], "Portishead")

    def test_sin_la_clave_tracks_no_revienta(self):
        self.assertEqual(importar.canciones_en_discos({"albums": []}, {}), {})
        self.assertEqual(importar.canciones_en_discos({"tracks": None}, {}), {})

    def test_el_umbral_decide_que_disco_es_favorito(self):
        discos = importar.canciones_en_discos(self.LIBRERIA, {})
        args = SimpleNamespace(completo=False, min_horas=8, min_nota=8,
                               min_favoritas=3)
        dentro, fuera = importar.criba(discos, args)
        self.assertEqual(list(dentro), ["In Rainbows"])
        self.assertEqual(sorted(fuera), ["Dummy", "Pink Moon"])

    def test_con_completo_entran_todos(self):
        discos = importar.canciones_en_discos(self.LIBRERIA, {})
        args = SimpleNamespace(completo=True, min_horas=8, min_nota=8,
                               min_favoritas=3)
        dentro, fuera = importar.criba(discos, args)
        self.assertEqual(len(dentro), 3)
        self.assertEqual(fuera, {})


class Etiquetas(unittest.TestCase):
    def test_un_genero_se_vuelve_tag_sin_perder_los_acentos(self):
        # "accion" al lado de "aventura" canta: son etiquetas que se leen.
        self.assertEqual(datos.etiqueta("  Acción y Aventura "), "acción-y-aventura")
        self.assertEqual(datos.etiqueta(None), "")

    def test_sacar_se_queda_con_la_primera_clave_que_traiga_algo(self):
        self.assertEqual(importar.sacar({"albumName": "X"}, "album", "albumName"), "X")
        self.assertEqual(importar.sacar({"album": "", "albumName": "X"},
                                        "album", "albumName"), "X")
        self.assertIsNone(importar.sacar({}, "album", "albumName"))


class Coherencia(unittest.TestCase):
    """Que la vault y lo que los scripts esperan de ella no se separen."""

    def test_cada_seccion_escribe_el_tipo_que_su_base_filtra(self):
        # Si una .base filtra por un tipo que ningun script escribe, la seccion
        # sale vacia en la web sin que falle nada.
        bases = {"juegos": "Juegos", "pelis": "Peliculas",
                 "libros": "Libros", "musica": "Musica"}
        for carpeta, base in bases.items():
            ruta = m.RAIZ / "content" / f"{base}.base"
            if not ruta.exists():
                continue
            texto = ruta.read_text(encoding="utf-8")
            self.assertIn(f'note.tipo == "{m.SECCIONES[carpeta]}"', texto,
                          f"{base}.base no filtra por el tipo que escribe {carpeta}")

    def test_las_fichas_de_la_vault_llevan_un_tipo_conocido(self):
        for carpeta, tipo in m.SECCIONES.items():
            for ficha in (m.RAIZ / "content" / carpeta).glob("*.md"):
                if ficha.stem == "index":
                    continue
                campos = m.frontmatter(ficha.read_text(encoding="utf-8"))
                self.assertEqual(campos.get("tipo"), tipo,
                                 f"{ficha.name} no dice tipo: {tipo}")

    def test_ninguna_ficha_apunta_a_una_portada_que_no_existe(self):
        # Una portada que falta no rompe el build: deja un hueco en la galeria.
        for carpeta in m.SECCIONES:
            for ficha in (m.RAIZ / "content" / carpeta).glob("*.md"):
                portada = m.frontmatter(ficha.read_text(encoding="utf-8")).get("portada")
                if not portada or not portada.startswith("[["):
                    continue
                nombre = portada.strip("[]")
                self.assertTrue((m.PORTADAS / nombre).exists(),
                                f"{ficha.name} apunta a {nombre}, que no esta")


if __name__ == "__main__":
    unittest.main(verbosity=2)
