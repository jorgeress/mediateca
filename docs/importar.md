# Traer tu colección desde Letterboxd, Steam y Spotify

Notas de lo que se puede y lo que no, comprobado en septiembre de 2026. Todo
son scripts de Python de la biblioteca estándar más Pillow. **No hay ninguna IA
en el camino**, ni hace falta tenerla: son exports, unas cuantas cuentas y
plantillas.

## Lo que ya existe, por si te vale mejor que esto

Antes de escribir nada miré lo que hay hecho:

- [obsidian-media-db-plugin](https://github.com/mProjectsCode/obsidian-media-db-plugin),
  el más completo. Consulta APIs de películas, series, anime, cómics, juegos
  (Steam incluido) y música, y crea la nota. Va por búsqueda manual, obra a
  obra, no por volcado de tu biblioteca.
- [obsidian-letterboxd-sync](https://github.com/osteotek/obsidian-letterboxd-sync),
  [letterboxd-import-for-obsidian](https://github.com/ATSenay/letterboxd-import-for-obsidian)
  y [letterboxd-mirror](https://github.com/diego-vicente/obsidian-letterboxd-mirror-plugin):
  los tres importan el CSV de Letterboxd a notas, con póster y plantilla propia.
  Solo cine.
- [letterboxd-viewer](https://github.com/KevDoy/letterboxd-viewer), una web
  estática que enseña tu export de Letterboxd. Solo cine, y no son notas tuyas:
  es un visor.

O sea: para cine solo, hay tres o cuatro cosas mejores que esto y sin escribir
una línea. Lo que no encontré es nada que junte juegos, cine y música en una
sola vault con fichas tuyas, que es de lo que va esto. Si algún día solo te
importa el cine, usa uno de esos.

Sobre **media-db** en concreto, que es el que más se parece a la parte de
búsqueda de libros de aquí: para libros consulta **la misma API que este repo,
Open Library, y tampoco pide clave**. No aporta una fuente que no esté ya. Lo
que aporta es el formulario, y a cambio trae su propio esquema de campos y su
propia convención de nombres para las portadas. Se puede doblar con sus
*mappings* y sus plantillas hasta que escupa `tipo/year/autor/nota/...`, pero
entonces hay dos sistemas que tienen que seguir de acuerdo, y el día que el
plugin cambie algo se rompe en silencio. Por eso la búsqueda está aquí dentro,
en `importar.py libro`, y no delegada a un plugin.

Para lo demás, sus APIs sí piden clave: OMDb y TMDB para cine, Comic Vine para
cómics, Boardgame Geek para juegos de mesa. Solo Steam, MusicBrainz, Wikipedia
y Open Library van sin registro, que son justo las cuatro que usa este repo.

## ¿Hace falta pagar?

**No.** Ninguna de las vías que usa esto pide pagar, ni registrar una
aplicación, ni pedir una clave de API. Comprobado en septiembre de 2026:

| Sección | Vía | Qué hace falta |
| --- | --- | --- |
| Películas | RSS del perfil de Letterboxd | tu nombre de usuario |
| Juegos | Tu página de juegos, guardada con Ctrl+S | la sesión abierta |
| Discos | API de estadísticas de ListenBrainz | tu nombre de usuario |
| Juegos | Export de datos de Steam | tu cuenta, y esperar unos días |
| Discos | Export de datos de Spotify | tu cuenta, y esperar |

Se descartaron por el camino dos vías que sí cuestan dinero, y conviene saber
por qué para no volver a proponerlas:

- **El export CSV de Letterboxd** está detrás de su cuenta Pro (35 $ al año).
  Importar es gratis para todo el mundo; exportar, no. El RSS del perfil da el
  mismo dato con menos historial. El lector de CSV sigue aquí porque leer un
  fichero no cuesta nada, pero la vía documentada es el RSS.
- **La API de Spotify** pide Premium desde el 11 de febrero de 2026: el dueño
  de la app tiene que tenerlo, solo se permite un Client ID por desarrollador y
  hay un tope de cinco usuarios autorizados por app. Ese tope, además, impide
  compartir una app con nadie. Estaba implementada y se ha quitado entera.

## Qué da cada fuente y qué no

| | Películas (Letterboxd) | Juegos (Steam) | Música (Spotify) |
| --- | --- | --- | --- |
| Título y año | sí | sí (el año lo pone `datos.py`) | sí |
| Autoría | **no** trae director | el estudio lo pone `datos.py` | sí, artista |
| **Tu nota** | **sí**, en estrellas | no | no |
| Señal de uso | fecha de visionado | horas jugadas | reproducciones |
| Estado | visto o *watchlist* | jugado o no | no |
| Portada | no | no | no |

La conclusión que manda sobre todo lo demás: **solo Letterboxd sabe si algo te
gustó**. Steam sabe cuánto jugaste y Spotify cuánto escuchaste, que no es lo
mismo. Por eso lo que sale de un volcado es un punto de partida, nunca el
resultado: la nota y las dos frases del porqué las pones tú.

Las carátulas no vienen de ninguna de las tres. Se bajan aparte, con
`scripts/portadas.py`, de fuentes sin clave. Y lo que Steam no cuenta de sus
propios juegos, el año y el estudio, lo rellena `scripts/datos.py` yendo a la
ficha de la tienda por el `appid`. Las dos vías son sin clave y sin registro.

### Películas

El export está en `Settings` → `Import & Export` → `Export your data`, y trae
`ratings.csv`, `watched.csv`, `diary.csv`, `reviews.csv` y `watchlist.csv`. El
que importa es `ratings.csv`: `Date,Name,Year,Letterboxd URI,Rating`, con la
puntuación de 0,5 a 5 estrellas, que aquí se dobla para la escala de 1 a 10.

Ese export **es de pago**: está detrás de Letterboxd Pro. Importar es gratis
para todo el mundo, exportar no.

La vía gratis es el RSS público del perfil, que da las últimas ~100 entradas del
diario con título, año, **tu nota** y la fecha. Menos historial, mismo dato:

```bash
scripts/importar.py letterboxd-rss TU_USUARIO
```

Lo que **no** se puede: sacar el director. No está en el export ni en el RSS.

### Juegos

Lo rápido es **tu propia página de juegos**, sin pedir nada ni esperar. Con la
sesión abierta, abre esto y guárdala con `Ctrl+S` (basta con *Solo HTML*):

    https://steamcommunity.com/my/games?tab=all

```bash
scripts/importar.py steam ~/Descargas/juegos.html
```

La lista completa viaja dentro del propio HTML, en un atributo
`data-profile-gameslist`, con el nombre y los minutos jugados de cada juego.

**Lo que no funciona: `&xml=1`.** Esa vista antigua devolvía un XML limpio, pero
hoy redirige al login *siempre*, tenga el perfil público o no: lo probé con ocho
perfiles distintos y los ocho dan 302 hacia `/login/`. Con la sesión abierta lo
que sale es un bucle de redirecciones y el navegador se planta. El importador
sigue entendiendo ese XML por si tienes uno viejo guardado, pero no lo busques.

También sirve el volcado por CSV o JSON de cualquier exportador de bibliotecas
de terceros, siempre que traiga `appid` y nombre.

La otra vía es el export de datos, en `Cuenta` → `Privacidad` → pedir una copia
de tus datos. Trae lo mismo más las compras y las reseñas, pero tarda días.
Nadie publica su estructura exacta y ha cambiado varias veces, así que el
importador no da por buena ninguna ruta: rastrea el JSON entero buscando cosas
con `appid` y nombre, y se queda con el mayor tiempo jugado que encuentre.

Las tres formas las entiende el mismo comando, que mira el contenido y no la
extensión.

De tu página se guarda además el `appid` de cada juego, y para los recientes la
ruta de su carátula. Buscar por nombre en Steam falla justo con los
*free-to-play* y los títulos raros (`skate.`, `PEAK`, `tModLoader`), y con el
`appid` la carátula sale siempre. Los juegos de 2024 en adelante ya no están en
la ruta clásica del CDN: la suya cuelga de un hash que solo aparece en tu propia
página, y por eso se guarda en la ficha.

La vía rápida alternativa sería la clave de la Web API de Steam
(`GetOwnedGames`), que es instantánea y da lo mismo. Está descartada por
decisión propia: aquí no se usan APIs con clave.

Lo que **no** se puede: saber si terminaste un juego. Por eso lo jugado entra
como `en curso` y nunca como `terminado`.

Lo que tampoco trae tu página de juegos es **el año ni el estudio**: solo el
nombre, el `appid` y los minutos. Eso lo cierra un segundo paso,
`scripts/datos.py`, que consulta la ficha pública de la tienda
(`store.steampowered.com/api/appdetails`, sin clave) por ese mismo `appid` y
escribe `year` y `autor`. Va despacio a propósito, que la tienda corta sobre
las 200 peticiones cada cinco minutos.

### Música

Spotify es la más enredada de las tres, porque tiene **dos exports distintos** y
ninguno de los dos es lo que uno espera:

- **Datos de la cuenta**: llega en unos días. Trae `YourLibrary.json` (lo que
  has guardado) y `StreamingHistory_music_*.json`, que es el historial reciente
  con `endTime`, `artistName`, `trackName` y `msPlayed`. Ojo: **no trae el
  nombre del álbum**, así que de aquí salen canciones y artistas más
  escuchados, pero no discos.
- **Historial ampliado**: el historial entero desde que abriste la cuenta, y
  este sí trae el álbum de cada reproducción. La pega es que tarda **hasta 30
  días** en llegar.

La vía rápida y gratis es **ListenBrainz**, que es el registro de escuchas de
MusicBrainz, la misma gente del Cover Art Archive de donde ya salen las
carátulas. Su API de estadísticas **se lee sin registrar nada ni pedir clave**:

```bash
scripts/importar.py listenbrainz TU_USUARIO
scripts/importar.py listenbrainz TU_USUARIO --periodo todo --top 60
```

Ventanas: `mes`, `trimestre`, `semestre`, `año` (la de por defecto) y `todo`.

Y trae algo que no da ninguna otra fuente: el **mbid** del disco, o sea su
identificador en MusicBrainz. Con él, `scripts/portadas.py` se baja la carátula
exacta de esa edición en vez de buscarla por parecido de nombre. Queda guardado
en la ficha, así que la portada se puede rehacer siempre igual.

Para que ListenBrainz tenga tus escuchas hay dos caminos, los dos gratis: conectar
Spotify en sus ajustes, que empieza a registrar desde ese momento, o subir el
historial ampliado en `listenbrainz.org/settings/import` cuando te llegue. Si
acabas de crear la cuenta y aún no hay nada, el script te lo dice.

Están implementadas las dos, porque no todo el mundo quiere crear una app:

```bash
scripts/importar.py spotify                      # API: lo más escuchado
scripts/importar.py spotify --periodo largo      # ventana de varios años
scripts/importar.py spotify --top 60             # cuántos discos
scripts/importar.py --completo spotify           # API: lo guardado, sin ranking

scripts/importar.py spotify-export ~/Descargas/spotify.zip              # el zip
scripts/importar.py --completo spotify-export ~/Descargas/spotify.zip   # guardados
```

Spotify no ordena discos, solo canciones, así que **los discos se agregan**: un
álbum con cinco canciones en tu top pesa más que uno con una suelta, y cuanto
más arriba esté la canción, más suma. Desde el export es más limpio, porque ahí
está el tiempo real escuchado de cada reproducción. En ese caso se descartan los
discos con menos de veinte minutos en total, que no son "lo más escuchado" de
nadie.

Si le pasas el export de la cuenta (el de días, sin álbum), el script te lo dice
en vez de fallar, y te queda `--completo` para meter lo guardado.

Lo que **no** se puede en ningún caso: sacar una nota tuya. Spotify no tiene
puntuaciones.

### Libros

No hay export que valga, y no es un fallo: no existe un sitio donde tengas
apuntado lo que has leído. Goodreads sería el equivalente, pero su API está
cerrada a nuevos desarrolladores desde 2020 y no ha vuelto. Así que la sección
no va por volcado sino **por búsqueda, obra a obra**, contra Open Library, que
es el catálogo del Internet Archive y la misma fuente de la que ya salían las
portadas de libro:

```bash
scripts/importar.py libro "el nombre del viento"
scripts/importar.py libro "dune" --nota 9 --estado terminado
scripts/importar.py libro "sapiens" --elegir 2   # sin preguntar
```

Enseña los resultados y eliges tú. **Eso no es un trámite que se pueda saltar**:
Open Library devuelve la edición inglesa aunque busques en español («el nombre
del viento» trae *The Name of the Wind*), y con los títulos cortos se cuela
cualquier cosa. Quedarse con el primero a ciegas es lo que hace que una ficha
acabe con los datos de otro libro. Por eso `--elegir N` existe pero no es lo
que pasa por defecto, y sin terminal para preguntar el script enseña la lista y
para en vez de inventarse una respuesta.

Se guarda el `coverid` de la edición elegida, así que la portada se baja exacta
y se puede rehacer siempre igual, igual que con el `appid` y el `mbid`.

Lo que **no** se puede: sacar una nota tuya, porque no hay cuenta de la que
sacarla. Se pone con `--nota` al crearla o a mano después.

**Cómics.** Open Library los cataloga y bastante bien: *Watchmen*, *Maus* y
*Persépolis* salen los tres con portada. Hoy entran como `tipo: libro`. Si algún
día quieres separarlos, es una entrada más en `SECCIONES` y un `.base`, no una
fuente nueva.

## Los dos modos

El importador arranca en **modo rápido**, que es el que tiene sentido la
primera vez: solo entra lo que da alguna señal de haberte importado.

| Fuente | Criterio del modo rápido | Se mueve con |
| --- | --- | --- |
| Steam | 8 horas jugadas o más | `--min-horas` |
| Letterboxd (export y RSS) | 4 estrellas o más | `--min-nota` |
| ListenBrainz y Spotify | los 40 discos más escuchados | `--top`, `--periodo` |

Los discos no pasan por umbral porque ya se seleccionan solos: coger el top 40
*es* la criba. En el export de Spotify, `--completo` no quita el umbral sino que
cambia de pregunta, de lo más escuchado a lo que tienes guardado.

Lo que se queda fuera se cuenta por pantalla, no desaparece en silencio. Con
`--completo` entra todo lo que traiga el export, sin umbrales.

```bash
scripts/importar.py steam ~/Descargas/steam.zip                 # rápido
scripts/importar.py --completo steam ~/Descargas/steam.zip      # todo
scripts/importar.py --min-horas 20 steam ~/Descargas/steam.zip  # más exigente
scripts/importar.py --dry-run ...                               # sin escribir
```

## El flujo

1. **Hoy, lo que tarda**: pide el historial ampliado de Spotify, que tarda
   hasta un mes. El de Steam solo hace falta si quieres compras y reseñas: para
   la biblioteca y las horas basta con guardar tu página de juegos.
2. **Hoy, lo que no tarda**: `letterboxd-rss TU_USUARIO`, o el export si eres
   Pro. Ya tienes las películas que te gustaron, con su nota puesta.
3. **`scripts/portadas.py`** y **`scripts/datos.py`**, uno detrás de otro:
   el primero le pone carátula a todo lo nuevo, el segundo rellena el año y el
   estudio de los juegos. Los dos se pueden repetir sin miedo, porque solo
   tocan lo que esté sin resolver.
4. **Asciende a mano** lo que merezca estar: quitar la línea `draft`, poner la
   nota y escribir las dos frases del porqué. Esto es el trabajo de verdad y no
   lo hace ninguna herramienta.
5. **Cuando lleguen los exports**, repite el paso 2 con Steam y Spotify. El
   importador no pisa nada de lo que ya haya, así que se puede repetir siempre.
   Si tienes cuenta en ListenBrainz con escuchas, los discos salen en el
   momento y no hace falta esperar a Spotify.
6. **Más adelante**, si quieres el archivo completo y no solo lo destacado,
   `--completo`. Los libros no entran por aquí: van uno a uno con
   `importar.py libro "título"`, cuando te acuerdes de uno.

## Personalizarlo

- Los umbrales, por bandera (`--min-horas`, `--min-nota`, `--completo`).
- El borrador, con `--sin-borrador` si prefieres que salga publicado ya.
- Los campos de la ficha se controlan desde `CAMPOS`, en `scripts/importar.py`;
  las fuentes de carátula desde `FUENTES`, en `scripts/portadas.py`, y las de
  relleno desde el `FUENTES` de `scripts/datos.py`, donde cada sección dice qué
  campos sabe completar. Añadir
  una sección nueva es añadir una entrada en `SECCIONES`, en
  `scripts/mediateca.py`, y un `.base` que la filtre.
