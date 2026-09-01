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
scripts/
  portadas.py       baja las carátulas y rellena el campo `portada`
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

Cada sección tira de la fuente que mejor la conoce, y todas menos una funcionan
sin registrarse:

| Sección | Fuente | Clave |
| --- | --- | --- |
| Juegos | Steam | no |
| Libros | Open Library | no |
| Música | MusicBrainz + Cover Art Archive | no |
| Películas | TMDB | sí, gratuita |

Para las películas hace falta una clave de TMDB, que se saca en un minuto en
[themoviedb.org/settings/api](https://www.themoviedb.org/settings/api):

```bash
mkdir -p ~/.config/mediateca && echo TU_CLAVE > ~/.config/mediateca/tmdb
```

El script la busca ahí o en la variable `TMDB_API_KEY`. Nunca se guarda en el
repositorio.

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

## Cosas a medias

- Los pósters de las tres películas siguen vacíos, a la espera de la clave de
  TMDB. En cuanto esté, `scripts/portadas.py --seccion pelis` los rellena.
- El plugin que renderiza las Bases solo trae sus textos en inglés. El único que
  se veía era el contador de resultados, y está oculto por CSS. Si algún día
  aparece otro, habrá que traducirlo a mano.
- Las fichas que hay ahora son de ejemplo, para que el sitio no se viera vacío.

## Licencia y créditos

El generador es [Quartz](https://quartz.jzhao.xyz), de jackyzha0, bajo licencia
MIT. Se conserva su `LICENSE.txt`.

El contenido de `content/` es mío, Copyright (c) 2026 jorgeress.

Las carátulas son de sus respectivos autores y se usan en miniatura para
identificar cada obra. Vienen de [TMDB](https://www.themoviedb.org),
[Open Library](https://openlibrary.org),
[Cover Art Archive](https://coverartarchive.org) y Steam. Este proyecto usa la
API de TMDB pero no está avalado ni certificado por TMDB.
