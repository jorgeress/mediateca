# Mediateca

Mi colección personal de juegos, películas, libros y discos, escrita en Obsidian
y publicada como web estática.

La idea era simple: llevaba años recomendando las mismas cosas por WhatsApp y
olvidándome de por qué me habían gustado. Quería un sitio donde apuntarlo una
vez, que se viera bien y que pudiera enlazar desde cualquier parte.

## Cómo funciona

Cada ficha es un fichero Markdown con unas pocas propiedades en la cabecera:

```yaml
---
tipo: juego                        # juego, peli, libro o album
year: 2019
autor: ZA/UM                       # estudio, dirección, autor o artista
nota: 10                           # del 1 al 10
estado: terminado                  # pendiente, en curso, terminado, abandonado
favorito: true
portada: "[[disco-elysium.webp]]"  # fichero de assets/portadas/
tags:
  - rpg
---
```

Las galerías no están escritas a mano. Son *Bases* de Obsidian (`.base`), que
filtran y ordenan por esas propiedades, así que se actualizan solas en cuanto
añado una ficha. Cada sección tiene tres vistas: galería, tabla y solo
favoritos.

Lo que se ve en la web es exactamente lo mismo que veo en Obsidian, sin plugins
de terceros ni un segundo formato que mantener.

## Por qué está partido en tres

Al abrir la carpeta se ven tres cosas que parecen lo mismo y no lo son. El
reparto es siempre igual: **una fuente, unas vistas y un resultado**.

**`content/` es la vault: la fuente.** Markdown plano y unos cuantos campos en
la cabecera. Es lo único que se escribe a mano y lo único que importa de
verdad: si mañana desaparecieran Obsidian y Quartz, la colección seguiría
entera y legible en cualquier editor de texto. Por eso la nota no guarda ni
maquetación ni orden ni el HTML de una tarjeta, solo los datos.

**Los `.base` son las vistas.** Un `.base` no contiene fichas: contiene la
*pregunta* («dame todo lo que tenga `tipo: juego`, ordenado por nota, en
tarjetas de 220 px»). Están sueltos y no dentro de las notas justamente para
que se puedan cambiar sin tocar ni una ficha: cambiar el criterio del *Top* de
un 9 a un 8 es editar un fichero, no doscientos. Y como es un formato nativo de
Obsidian, la misma vista se pinta igual en el editor y en la web; no hay una
galería para mí y otra para el visitante.

**`public/` es el resultado.** Lo escupe Quartz al construir y está en el
`.gitignore` a propósito: es material derivado, se regenera entero en cada
`build` y versionarlo solo serviría para llenar el historial de HTML y meter
conflictos absurdos en cada commit. Se borra sin miedo. En GitHub lo reconstruye
la Action en cada push y lo sube a Pages; la carpeta local es solo para verlo
antes de publicar.

La otra carpeta grande, `quartz/`, es el generador: no es contenido, es el
programa. Este repo es un *fork* de Quartz con la vault dentro, que es como se
usa Quartz normalmente.

### Por qué Quartz y no otra cosa

- Entiende los enlaces `[[wiki]]`, los *callouts* y los `![[embeds]]` de
  Obsidian tal cual. Con Hugo o Jekyll habría que reescribir cada nota o meter
  un preprocesador.
- Es de los pocos generadores que renderizan los `.base`. Esto es lo que evita
  mantener las galerías dos veces.
- Sale un sitio estático: se publica gratis en GitHub Pages, no hay servidor ni
  base de datos que se caiga, y se puede llevar a cualquier otro alojamiento
  copiando `public/`.
- Trae ya hechos el buscador, el modo oscuro, el grafo, los *backlinks* y las
  previsualizaciones al pasar el ratón.

No es la única forma de hacerlo, pero cualquier alternativa (Dataview + un
exportador, una base de datos, Notion) rompe alguna de esas cuatro cosas.

## Estructura

```
content/            la vault de Obsidian: lo único que se escribe a mano
  index.md          portada
  juegos/  pelis/  libros/  musica/
  *.base            las vistas de cada sección
  _plantillas/      plantilla de ficha (no se publica)
  assets/portadas/  imágenes
docs/
  importar.md       qué se puede sacar de cada fuente, y el flujo completo
scripts/
  importar.py       crea fichas desde Letterboxd, Steam, Spotify y Open Library
  mediateca.py      lo que comparten los tres scripts
  portadas.py       baja las carátulas y rellena el campo `portada`
  datos.py          rellena año, autor y tags desde Steam y Wikipedia
  vistazo.py        levanta el sitio con los borradores dentro
quartz/             el generador (fork de Quartz, no se toca)
quartz.config.yaml  configuración del sitio
public/             lo que genera el build; no se versiona
```

## Montarlo en otro ordenador

Hace falta [Node 22 o superior](https://nodejs.org), git y, para editar
cómodamente, [Obsidian](https://obsidian.md). Nada más: ni Docker, ni Ruby, ni
claves de API para arrancar.

```bash
git clone https://github.com/jorgeress/mediateca.git
cd mediateca
npm ci --ignore-scripts --include=optional
npm run install-plugins
npx quartz build --serve
```

Y ya está en <http://localhost:8080>, recargándose solo al guardar una nota.

Los dos detalles que no son evidentes:

- **`--ignore-scripts` no es opcional.** Sin él, `sharp` intenta compilarse
  desde el código fuente en vez de usar los binarios precompilados que ya vienen
  en las dependencias, y la instalación falla.
- **`install-plugins` va aparte de `npm ci`.** Los plugins de Quartz se leen de
  `quartz.config.yaml`, no del `package.json`, así que se instalan en un segundo
  paso. Si el sitio construye pero las galerías salen vacías, es que falta este
  comando.

Para editar las notas: en Obsidian, `Abrir carpeta como almacén` apuntando a
`content/` (a `content/`, no a la raíz del repo). La configuración de la vault
(plantillas y plugins nativos activos) viene versionada, así que las Bases
funcionan desde el primer arranque.

### Publicarlo bajo tu propia cuenta

1. Haz un *fork* del repo, o clónalo y súbelo al tuyo.
2. En `quartz.config.yaml`, cambia `baseUrl` por `tuusuario.github.io/mediateca`.
3. En `Settings → Pages` del repo, pon *Source* en **GitHub Actions**.
4. Empuja a `main`. El workflow de `.github/workflows/deploy.yaml` construye y
   despliega solo.

El workflow se salta el despliegue mientras el repositorio sea privado, porque
Pages no está disponible en repos privados con el plan gratuito. En cuanto lo
pases a público se activa solo, sin tocar nada.

## Añadir una ficha

Con la plantilla de `_plantillas/Ficha.md` (`Ctrl+P` → *Insertar plantilla*),
en la carpeta de su sección. En cuanto tenga `tipo` y `nota`, aparece sola en
la galería, en la tabla y, si llega al 9, en el *Top*. No hay que tocar ningún
índice.

## Traer lo que ya tienes en otros sitios

`scripts/importar.py` crea fichas a partir de Letterboxd, Steam y Spotify. No
pisa nunca una ficha que ya exista, así que se puede repetir cuando quieras
para recoger solo lo nuevo, y avisa cuando algo se parece a lo que ya tienes
(el *Witcher 3* de Steam se llama *The Witcher 3: Wild Hunt*, y esa la unes tú).

```bash
scripts/importar.py letterboxd-rss TU_USUARIO  # sin cuenta de pago
scripts/importar.py letterboxd ~/Descargas/letterboxd-export.zip  # con Pro
scripts/importar.py steam ~/Descargas/juegos.html  # tu página de juegos
scripts/importar.py listenbrainz TU_USUARIO     # discos más escuchados
scripts/importar.py spotify-export ~/Descargas/spotify.zip   # o desde el zip
scripts/importar.py libro "el nombre del viento"  # uno a uno, a mano
scripts/importar.py --dry-run letterboxd ...   # dice qué haría, sin escribir
```

**Todo entra en borrador**, con `draft: true` y el cuerpo en blanco (la nota sí
viene puesta en las películas, que es lo único que sabe Letterboxd). Quartz no
publica lo que lleva `draft`, así que la web sigue enseñando solo lo que hayas
ascendido a mano, mientras que en Obsidian se ven todas. Para ascender una
ficha se le quita la línea `draft` y se le pone nota y las dos frases del
porqué, que es lo único que estas fuentes no saben. Si prefieres que entren
publicadas directamente, `--sin-borrador`.

Por defecto va en **modo rápido**: solo entra lo que da alguna señal de haberte
importado, 8 horas jugadas en Steam y 4 estrellas en Letterboxd. Lo que se queda
fuera se cuenta por pantalla, no desaparece en silencio, y con `--completo`
entra todo. Los umbrales se mueven con `--min-horas` y `--min-nota`.

Cada fuente da lo suyo, y ninguna lo da todo:

| Fuente | Cómo | Qué trae |
| --- | --- | --- |
| Letterboxd | El RSS del perfil, o el export si tienes Pro | Título, año y **tu puntuación**, que pasa de estrellas a la escala de 1 a 10. La *watchlist* entra como `pendiente`. |
| Steam | Guardar `steamcommunity.com/my/games?tab=all` con `Ctrl+S`, o el export de datos | Título y horas jugadas, en el campo `horas`. |
| ListenBrainz | Tu nombre de usuario | Los discos más escuchados, con artista y el *mbid* de MusicBrainz. |
| Spotify | El zip del export | Lo mismo, desde tu historial. Con `--completo`, los álbumes guardados. |

Letterboxd es la única de las tres que sabe si algo te gustó. Steam sabe cuánto
jugaste, que no es lo mismo (por eso lo jugado entra como `en curso` y no como
`terminado`: eso no lo puede deducir nadie), y Spotify solo sabe que le diste a
guardar. De ahí que el volcado sea un punto de partida y no el resultado.

[ListenBrainz](https://listenbrainz.org) es el registro de escuchas de
MusicBrainz, la misma gente del Cover Art Archive de donde salen las carátulas,
y su API de estadísticas se lee sin registrar nada. Además devuelve el *mbid*
del disco, así que la carátula se baja exacta y no por parecido de nombre. Para
que tenga tus escuchas, se conecta Spotify en sus ajustes o se le sube el
historial ampliado cuando llegue.

Después de importar quedan dos pasos, los dos de una pasada y sin clave:
`scripts/portadas.py` le pone carátula a todo lo nuevo, y `scripts/datos.py`
rellena lo que la fuente no supo decir.

**Nada de esto pide pagar, ni registrar una aplicación, ni una clave de API.**
Fue una decisión, no una casualidad: el export CSV de Letterboxd está detrás de
su cuenta Pro y la API de Spotify pide Premium desde febrero de 2026, así que
las dos se cambiaron por vías abiertas. Lo que da y lo que no da cada fuente, y
qué herramientas de otros hacen ya parte de esto, está en
[`docs/importar.md`](docs/importar.md).

## Libros: uno a uno, buscando

Las otras tres secciones se vuelcan de golpe porque la lista ya es tuya y ya
está elegida: tu diario de Letterboxd, tu biblioteca de Steam, tus escuchas. Con
los libros no hay nada que volcar. No existe un sitio donde tengas apuntado lo
que has leído, y si existiera sería otra cuenta más.

Lo que sí hay es un catálogo público, así que la sección va por búsqueda, obra a
obra:

```bash
scripts/importar.py libro "el nombre del viento"
scripts/importar.py libro "dune" --nota 9 --estado terminado
scripts/importar.py libro "sapiens" --elegir 2     # sin preguntar
scripts/importar.py libro "watchmen" --resultados 10
```

Enseña los resultados y eliges tú:

```
  1) The Name of the Wind — Patrick Rothfuss (2007)
  2) The Wise Man's Fear — Patrick Rothfuss (2011)
  3) El Nombre de la Ballena Coleccion Los Especiales de a la Orilla del V… — …
  4) El origen de los nombres de los países del mundo — Edgardo D. Otero (2003)

¿Cuál? (1-5, Enter para el 1, 0 si ninguno):
```

**Elegir a mano es el punto, no un trámite.** Open Library devuelve la edición
inglesa aunque busques en español, y con los títulos cortos se cuela cualquier
cosa: mira el resultado 3. Quedarse con el primero a ciegas es exactamente lo
que hace que una ficha acabe con los datos de otro libro.

De la edición que elijas se guarda su `coverid`, igual que el `appid` en los
juegos y el `mbid` en los discos. Con él, `scripts/portadas.py` baja la portada
**de esa edición** y no una parecida de nombre.

La ficha entra en borrador como todo lo demás, y con `--nota` y `--estado` puedes
dejarla puesta de una vez si el libro ya lo has leído.

Es la misma API que usan los plugins de Obsidian que hacen esto, y tampoco pide
clave ni registro. Está aquí y no en un plugin para que las fichas salgan
directamente en el formato de la vault, sin un segundo esquema que mantener de
acuerdo con el primero.

Sirve igual para cómics y novela gráfica, que Open Library cataloga: *Watchmen*,
*Maus* y *Persépolis* salen con portada. Hoy entrarían como `tipo: libro`; una
sección propia sería añadir una entrada en `SECCIONES` y un `.base` que la
filtre.

## Portadas

Las carátulas se guardan **como fichero, dentro de la vault**, en
`content/assets/portadas/`, y la ficha las referencia con un enlace de Obsidian:

```yaml
portada: "[[disco-elysium.webp]]"
```

Enlazar a la imagen de un servidor ajeno es más cómodo el primer día y peor
todos los demás: las URLs se pudren, muchos CDN bloquean el *hotlinking*, la
galería depende de que ese servidor esté vivo y en Obsidian, sin conexión, no se
ve nada. Con el fichero dentro, la vault es autocontenida y funciona igual en el
portátil sin internet que en la web. Y el formato importa: **WebP a 400 px de
ancho** pesa entre 20 y 80 KB por carátula (las tarjetas miden 220 px, así que
400 cubre pantallas 2x y de ahí para arriba solo se malgasta ancho de banda).
Mil fichas siguen siendo unas pocas decenas de megas de repositorio.

El enlace va entre corchetes y no como ruta suelta a posta: así Obsidian lo
reconoce como enlace de verdad (y lo renombra solo si mueves la imagen), y
Quartz lo resuelve a la ruta correcta desde cualquier página. Una ruta en texto
plano se rompe en las subcarpetas.

Bajarlas es un comando:

```bash
scripts/portadas.py                 # rellena las fichas que no tienen portada
scripts/portadas.py --seccion pelis # solo esa carpeta
scripts/portadas.py --force         # rehace también las que ya la tienen
scripts/portadas.py --dry-run       # dice qué haría, sin tocar nada
```

Cada sección tira de la fuente que mejor la conoce, y **ninguna pide clave ni
registro**. Se clona el repositorio y funciona:

| Sección | Fuente |
| --- | --- |
| Juegos | Steam |
| Libros | Open Library (exacta, si la ficha trae `coverid`) |
| Música | MusicBrainz + Cover Art Archive |
| Películas | Wikipedia |

Las películas fueron el caso difícil. Para libros y discos existen catálogos
abiertos (Open Library es del Internet Archive, Cover Art Archive es de
MusicBrainz) y los juegos los sirve la propia tienda, pero para cine no hay
nada equivalente: las bases de datos de películas piden una clave detrás de un
formulario que quiere nombre, teléfono y dirección postal, y los servicios que
no la piden son CDN internos de aplicaciones de terceros, sin términos ni
garantía de seguir ahí mañana.

La salida es Wikipedia. El script busca la película en la Wikipedia en español,
salta al artículo en inglés por los enlaces de idioma (la española no admite
material con copyright, así que las carátulas solo viven en la inglesa) y se
queda con la imagen de la ficha lateral. La pega es la resolución: Wikipedia
obliga a que el material no libre esté en baja resolución, así que el póster
llega a unos 220 px de ancho. Es justo lo que mide la tarjeta, o sea que al
lado de los demás no se nota, solo se queda algo blando en pantallas de mucha
densidad. Y es el cartel internacional, no el de la edición española.

Si una ficha no se encuentra (la búsqueda va por el nombre del fichero), lo más
rápido es dejar la imagen a mano en `assets/portadas/` y escribir el enlace en
la cabecera. Con los libros pasa algo parecido: Open Library devuelve casi
siempre la portada de la edición inglesa aunque la ficha esté en español
(filtrar por idioma no cambia el resultado), así que si te importa la edición
concreta, esa se pone a mano. Y si una queda sin portada tampoco pasa nada: la tarjeta se pinta
con un degradado y la rejilla no se descuadra.

Las relaciones de aspecto de cada galería están puestas para lo que enseñan:
`0.67` (2:3, el formato de un póster o una portada de libro) en juegos,
películas y libros, y `1` en música y en el *Top*, que es un mosaico cuadrado.

## Verlo antes de ascender

Decidir qué asciendes mirando la web publicada no se puede, porque ahí todavía
no está: es justo lo que aún no has ascendido. Y mirar ficha por ficha en
Obsidian tampoco dice cómo va a quedar la galería entera, ni dónde cae el corte
del *Top*.

```bash
scripts/vistazo.py               # el sitio completo, borradores incluidos
scripts/vistazo.py --puerto 9000
scripts/vistazo.py --solo-build  # construye y no levanta nada
```

Sale en <http://localhost:8081>, con las fichas en borrador dentro y un aviso
en la portada para que no lo confundas con el sitio de verdad, que sigue en el
8080. Puedes tener los dos abiertos a la vez y compararlos.

No toca `quartz.config.yaml` ni la vault: copia el contenido **fuera del
repositorio**, le quita la línea `draft` a la copia y construye desde ahí. Ni
cortándolo a mitad puede acabar publicando un borrador. Que la copia salga
fuera no es capricho: el `glob` de Quartz se salta los directorios que empiezan
por punto, y además respeta el `.gitignore`, así que una copia dentro del repo
y anotada ahí no se encontraría a sí misma.

Es una foto fija, no recarga sola: si tocas una ficha, vuelve a lanzarlo.

## Lo que la fuente no sabe

Ninguna de las fuentes de importación lo da todo, y lo que le falta a cada una
no es casualidad. Tu página de juegos de Steam sabe cuántas horas les has
echado, pero no de qué año es el juego, ni quién lo hizo, ni de qué va. El
diario de Letterboxd sabe tu nota, pero no quién dirige. Así que lo importado
entra con `year`, `autor` y `tags` en blanco: sin año la galería no se ordena
por fecha, y sin tags la página de etiquetas y el grafo se quedan vacíos.

Eso lo cierra `scripts/datos.py`, que sabe dónde está cada cosa:

| Sección | Fuente | Qué rellena |
| --- | --- | --- |
| Juegos | Ficha de la tienda de Steam | `year`, `autor` (el estudio) y `tags` (los géneros, ya en español) |
| Películas | Ficha lateral de Wikipedia | `autor`, o sea la dirección |

```bash
scripts/datos.py                    # rellena solo lo que esté vacío
scripts/datos.py --force            # reescribe también lo que ya tenga valor
scripts/datos.py --dry-run          # dice qué pondría, sin tocar nada
scripts/datos.py content/juegos/Hollow\ Knight.md   # una ficha suelta
```

**La regla es no adivinar.** Los juegos van por el `appid` que el importador ya
dejó guardado, no por el título: buscar «PEAK» o «skate.» por nombre en Steam no
encuentra nada, y por `appid` sale siempre. Las películas van por el mismo
artículo de Wikipedia del que sale el cartel, con la misma comprobación de que
de verdad encaja. Antes que rellenar una ficha con los datos de otra obra, se
queda vacía y lo dice.

En la colección de este repo: 44 de 44 juegos, y 36 de 37 películas. La que
falta es un caso de manual — la ficha es de una película de 2025 y el artículo
que hay en Wikipedia es otra distinta, del mismo título y de 2016. Se negó a
mezclarlas, que es exactamente lo que tenía que hacer.

No pisa nada de lo que hayas escrito tú: solo toca los campos que estén
vacíos, salvo que le pases `--force`, y deja el resto de la cabecera igual, en
el mismo orden. Se puede repetir tantas veces como quieras; lo que ya está
resuelto se salta sin gastar una petición.

Para las otras tres secciones sigue siendo a mano. Con los juegos funciona
porque el `appid` identifica la obra sin lugar a dudas; para el director de una
película o el autor de un libro no hay un identificador equivalente en la ficha,
y adivinarlo por título es justo lo que hace que una ficha acabe con los datos
de otra.

## Cosas a medias

- El plugin que renderiza las Bases solo trae sus textos en inglés. El único que
  se veía era el contador de resultados, y está oculto por CSS. Si algún día
  aparece otro, habrá que traducirlo a mano.
- El export de Steam ha cambiado de formato varias veces, así que el importador
  rastrea el JSON entero buscando cosas con `appid` y nombre en vez de dar por
  buena una ruta concreta. Si algún día deja de encontrarlos, es ahí.

## Licencia y créditos

El generador es [Quartz](https://quartz.jzhao.xyz), de jackyzha0, bajo licencia
MIT. Se conserva su `LICENSE.txt`.

El contenido de `content/` es mío, Copyright (c) 2026 jorgeress.

Las carátulas son de sus respectivos autores y se usan en miniatura para
identificar cada obra. Vienen de [Open Library](https://openlibrary.org),
[Cover Art Archive](https://coverartarchive.org),
[Wikipedia](https://en.wikipedia.org) y Steam.
