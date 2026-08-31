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
tipo: juego          # juego, peli, libro o album
year: 2019
autor: ZA/UM         # estudio, dirección, autor o artista
nota: 10             # del 1 al 10
estado: terminado    # pendiente, en curso, terminado, abandonado
favorito: true
portada:             # ruta en assets/portadas/ o una URL
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

## Estructura

```
content/            la vault de Obsidian
  index.md          portada
  juegos/  pelis/  libros/  musica/
  *.base            las vistas de cada sección
  _plantillas/      plantilla de ficha (no se publica)
  assets/portadas/  imágenes
quartz.config.yaml  configuración del sitio
```

## Uso

Abrir la vault en Obsidian: `Abrir carpeta como almacén` apuntando a `content/`.

Levantar el sitio en local:

```bash
npm ci --ignore-scripts --include=optional
npm run install-plugins
npx quartz build --serve
```

El `--ignore-scripts` no es opcional: sin él, `sharp` intenta compilarse desde
el código fuente en vez de usar los binarios precompilados que ya vienen en las
dependencias, y la instalación falla.

Cada push a `main` republica el sitio en GitHub Pages.

## Cosas a medias

- Las portadas están vacías. Las carátulas y los pósters tienen copyright, así
  que hay que decidir entre enlazar a una fuente externa o no ponerlas. Mientras
  tanto, las tarjetas sin imagen se pintan con un degradado.
- El plugin que renderiza las Bases solo trae sus textos en inglés. El único que
  se veía era el contador de resultados, y está oculto por CSS. Si algún día
  aparece otro, habrá que traducirlo a mano.
- Las fichas que hay ahora son de ejemplo, para que el sitio no se viera vacío.

## Licencia

El generador es [Quartz](https://quartz.jzhao.xyz), de jackyzha0, bajo licencia
MIT. Se conserva su `LICENSE.txt`.

El contenido de `content/` es mío, Copyright (c) 2026 jorgeress.
