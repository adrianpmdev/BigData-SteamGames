# Análisis de juegos de Steam (2020–2025)

**Objetivo:** si fuera un estudio de videojuegos, ¿qué **género** y qué **categoría** de juego debería desarrollar?

- [1. Documentación de recopilación del dataset](docs/1_recopilacion.md)
- [2. Documentación de preparación del dataset](docs/2_preparacion.md)
- [3. Documentación de modelado y análisis con SQL](docs/3_analisis.md)

## Ficha del dataset

| Apartado | Descripción |
| --- | --- |
| **Título y tema** | Juegos de Steam 2020–2025, dataset propio. Videojuegos: catálogo de la tienda Steam con datos de recepción y popularidad. |
| **Fuente** | Descarga propia con `scripts/1_ingesta.py` desde la **API de Steam** (`GetAppList`, `GetItems`, `GetTagList`, `appdetails`, `GetAppReviews`), publicada por Valve. Documentación: [Steam Web API](https://partner.steamgames.com/doc/webapi). `appdetails` es la API de la tienda y no tiene documentación oficial. Captura del 18/11/2026 al 24/11/2026. |
| **Registros y campos** | Cada registro es **un juego** de Steam, identificado por `appid`. Campos principales:<br>• `generos`: géneros oficiales (Action, RPG, Indie…), con varios valores por juego.<br>• `categorias`: características del juego (Single-player, Co-op, Online PvP…), con varios valores por juego.<br>• `resenas_positivas` / `resenas_negativas`: número de reseñas positivas y negativas de usuarios.<br>• `precio_base_centimos`: precio sin descuento, en céntimos de euro.<br>• `fecha_lanzamiento` y fechas de Steam: lanzamiento, original (p. ej. inicio del acceso anticipado) y salida del acceso anticipado.<br>• `etiquetas`: etiquetas de la tienda, votadas por la comunidad (Roguelike, Pixel Graphics…).<br>• `idiomas`: idiomas de los textos del juego y si también está doblado a cada uno. |
| **Formato y tamaño** | 4 archivos JSONL en `data/raw/2026-11-18/`, **unos 125 MB** en total:<br>• `juegos_lista`: 201.397 juegos de la tienda.<br>• `juegos_periodo`: 81.597 candidatos del periodo.<br>• `juegos_fichas`: **unos 81.000 juegos**, cada uno con su ficha, sus reseñas y sus etiquetas.<br>• `juegos_descartados`: juegos excluidos, con la fase y el motivo. |
| **Cobertura** | Juegos de Steam (mercado global) con **alguna de sus fechas (tienda, Steam, original o salida del acceso anticipado) entre el 01/01/2020 y el 31/12/2025**. Precios de la tienda de España. |
| **Condiciones de uso** | Datos de la API de Steam, sujetos a los [Steam Web API Terms of Use](https://steamcommunity.com/dev/apiterms).<br>**Compartir los archivos:** los datos son propiedad de Valve. Los términos permiten usarlos y mostrarlos en una aplicación propia, pero no autorizan expresamente a redistribuirlos como dataset. Aquí se comparten solo con fines educativos y sin relación con Valve. |
| **Preguntas** | 1. ¿Qué géneros y categorías tienen mejor relación entre éxito (reseñas, % positivo) y competencia (número de juegos)?<br>2. ¿Cómo ha evolucionado la oferta de cada género entre 2020 y 2025, incluido el efecto del boom de la COVID en 2020?<br>3. ¿Qué precio da mejores resultados en cada género?<br>4. ¿Influyen el multijugador, el cooperativo o los idiomas (cuántos y cuáles) en el éxito de un juego? |
| **Limitación inicial** | • Los juegos más recientes han tenido menos tiempo para acumular reseñas, así que no se pueden comparar en bruto con los más antiguos.<br>• No hay ventas reales: el éxito se mide con las reseñas, que solo pueden escribir quienes tienen el juego.<br>• El precio es el actual en la tienda de España, no el de lanzamiento. Los juegos que no se venden en España no tienen ficha.<br>• Un juego en acceso anticipado tiene varias fechas y en la preparación se decide a qué año se asigna.<br>• 2020 fue un año atípico por la COVID. |
| **Motivo de elección** | Me interesa el desarrollo de videojuegos. Los datos tienen categorías para comparar (géneros, categorías, etiquetas), cantidades numéricas (reseñas, precio) y fechas para estudiar la evolución, así que sirven para todas las fases del curso. Construí el dataset desde la API porque los datasets de Steam ya publicados en internet tenían información incompleta. |
