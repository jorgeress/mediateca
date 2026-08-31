Plantilla única para cualquier tipo de ficha.

Campos:

- `tipo`: juego, peli, libro o album. Debe coincidir con la carpeta.
- `year`: año de salida.
- `autor`: estudio, dirección, autor o artista según el caso.
- `nota`: del 1 al 10, en número.
- `estado`: pendiente, en curso, terminado, abandonado.
- `favorito`: true o false. Alimenta la vista "Solo favoritos".
- `portada`: ruta a una imagen en `assets/portadas/`, o una URL.
- `tags`: géneros o etiquetas libres, en minúscula y sin espacios.

Esta carpeta no se publica: está en `ignorePatterns` de la configuración de Quartz.
