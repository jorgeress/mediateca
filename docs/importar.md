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

## Qué da cada fuente y qué no

| | Películas (Letterboxd) | Juegos (Steam) | Música (Spotify) |
| --- | --- | --- | --- |
| Título y año | sí | sí (año no) | sí |
| Autoría | **no** trae director | no | sí, artista |
| **Tu nota** | **sí**, en estrellas | no | no |
| Señal de uso | fecha de visionado | horas jugadas | reproducciones |
| Estado | visto o *watchlist* | jugado o no | no |
| Portada | no | no | no |

La conclusión que manda sobre todo lo demás: **solo Letterboxd sabe si algo te
gustó**. Steam sabe cuánto jugaste y Spotify cuánto escuchaste, que no es lo
mismo. Por eso lo que sale de un volcado es un punto de partida, nunca el
resultado: la nota y las dos frases del porqué las pones tú.

Las carátulas no vienen de ninguna de las tres. Se bajan aparte, con
`scripts/portadas.py`, de fuentes sin clave.

### Películas

El export está en `Settings` → `Import & Export` → `Export your data`, y trae
`ratings.csv`, `watched.csv`, `diary.csv`, `reviews.csv` y `watchlist.csv`. El
que importa es `ratings.csv`: `Date,Name,Year,Letterboxd URI,Rating`, con la
puntuación de 0,5 a 5 estrellas, que aquí se dobla para la escala de 1 a 10.

Hay fuentes de terceros que dicen que exportar exige cuenta Pro. No he podido
confirmarlo (Letterboxd devuelve 403 a cualquier consulta automática), así que
míralo en tus ajustes, que se ve en diez segundos.

Si resulta que lo pide, queda una vía gratis: el RSS público de tu perfil,
`letterboxd.com/TU_USUARIO/rss/`. Lo he probado y devuelve las últimas ~100
entradas del diario con título, año, **tu nota** y la fecha. Es menos historial,
pero es exactamente el mismo dato.

Lo que **no** se puede: sacar el director. No está en el export ni en el RSS.

### Juegos

El export está en `Cuenta` → `Privacidad` → pedir una copia de tus datos, y
trae la biblioteca, las horas, las compras y las reseñas. Tarda días.

Nadie publica su estructura exacta y ha cambiado varias veces, así que el
importador no da por buena ninguna ruta: rastrea el JSON entero buscando cosas
con `appid` y nombre, y se queda con el mayor tiempo jugado que encuentre. Si
algún día deja de encontrar nada, te lo dice y se ajusta ahí.

La vía rápida alternativa sería la clave de la Web API de Steam
(`GetOwnedGames`), que es instantánea y da lo mismo. Está descartada por
decisión propia: aquí no se usan APIs con clave.

Lo que **no** se puede: saber si terminaste un juego. Por eso lo jugado entra
como `en curso` y nunca como `terminado`.

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

La tercera vía es la API (`me/top/artists` y `me/top/tracks`), que da los más
escuchados al momento en tres ventanas: cuatro semanas, seis meses y varios
años. Los discos salen agregando los álbumes de las canciones. Necesita crear
una app propia, que no pide datos personales y no lleva secreto: la
autorización va por PKCE y el permiso es de solo lectura.

Lo que **no** se puede en ningún caso: sacar una nota tuya. Spotify no tiene
puntuaciones.

### Libros

De momento a mano. No hay una fuente tuya equivalente, y es la lista más corta
de las cuatro.

## Los dos modos

El importador arranca en **modo rápido**, que es el que tiene sentido la
primera vez: solo entra lo que da alguna señal de haberte importado.

| Fuente | Criterio del modo rápido | Se mueve con |
| --- | --- | --- |
| Steam | 8 horas jugadas o más | `--min-horas` |
| Letterboxd | 4 estrellas o más | `--min-nota` |

Lo que se queda fuera se cuenta por pantalla, no desaparece en silencio. Con
`--completo` entra todo lo que traiga el export, sin umbrales.

```bash
scripts/importar.py steam ~/Descargas/steam.zip                 # rápido
scripts/importar.py --completo steam ~/Descargas/steam.zip      # todo
scripts/importar.py --min-horas 20 steam ~/Descargas/steam.zip  # más exigente
scripts/importar.py --dry-run ...                               # sin escribir
```

## El flujo

1. **Hoy, lo que tarda**: pide el export de Steam y el de Spotify. Uno tarda
   días y el otro hasta un mes, así que cuanto antes se pidan, mejor.
2. **Hoy, lo que no tarda**: exporta Letterboxd (o tira del RSS) e importa en
   modo rápido. Ya tienes las películas que te gustaron, con su nota puesta.
3. **`scripts/portadas.py`**, que le pone carátula a todo lo nuevo de una
   pasada.
4. **Asciende a mano** lo que merezca estar: quitar la línea `draft`, poner la
   nota y escribir las dos frases del porqué. Esto es el trabajo de verdad y no
   lo hace ninguna herramienta.
5. **Cuando lleguen los exports**, repite el paso 2 con Steam y Spotify. El
   importador no pisa nada de lo que ya haya, así que se puede repetir siempre.
6. **Más adelante**, si quieres el archivo completo y no solo lo destacado,
   `--completo`. Los libros, a mano.

## Personalizarlo

- Los umbrales, por bandera (`--min-horas`, `--min-nota`, `--completo`).
- El borrador, con `--sin-borrador` si prefieres que salga publicado ya.
- Los campos de la ficha se controlan desde `CAMPOS`, en `scripts/importar.py`,
  y las fuentes de carátula desde `FUENTES`, en `scripts/portadas.py`. Añadir
  una sección nueva es añadir una entrada en `SECCIONES`, en
  `scripts/mediateca.py`, y un `.base` que la filtre.
