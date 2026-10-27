# Análisis de juegos de Steam (2020–2025)

**Objetivo:** si fuera un estudio de videojuegos, ¿qué **género** y qué **categoría** de juego debería desarrollar?

## Ficha del dataset

| Apartado | Descripción |
| --- | --- |
| **Título y tema** | *Steam Games Dataset*. Videojuegos: catálogo de la tienda Steam con datos de recepción y popularidad. |
| **Fuente** | FronkonGames en Kaggle: <https://www.kaggle.com/datasets/fronkongames/steam-games-dataset>. Los datos se obtienen de la API de Steam y de SteamSpy. Consultado el 27/10/2026. |
| **Registros y campos** | Cada registro es **un juego** de Steam, identificado por `AppID`. Campos principales:<br>• `Genres`: géneros oficiales (Action, RPG, Indie…), con varios valores por juego.<br>• `Categories`: características del juego (Single-player, Co-op, Online PvP…), con varios valores por juego.<br>• `Positive` / `Negative`: número de reseñas positivas y negativas de usuarios.<br>• `Estimated owners`: rango estimado de propietarios (p. ej. `20000 - 50000`).<br>• `Price`: precio en USD.<br>• `Release date`: fecha de lanzamiento.<br>• `Tags`: etiquetas de la comunidad (Roguelike, Pixel Graphics…). |
| **Formato y tamaño** | Un archivo CSV (`games.csv`) de **400 MB** con **125.855 juegos × 40 columnas**. Trabajaré con **una parte**: los juegos lanzados entre el 01/01/2020 y el 31/05/2025, y solo las columnas útiles para la pregunta. |
| **Cobertura** | El dataset incluye juegos de Steam (mercado global) lanzados entre 1997 y 2026. El análisis se centrará en el periodo del **01/01/2020 al 31/05/2025**. |
| **Condiciones de uso** | Licencia MIT, según la ficha de Kaggle. |
| **Preguntas** | 1. ¿Qué géneros y categorías tienen mejor relación entre éxito (reseñas, % positivo, propietarios) y competencia (número de juegos)?<br>2. ¿Cómo ha evolucionado la oferta de cada género entre 2020 y 2025, incluido el efecto del boom de la COVID en 2020?<br>3. ¿Qué precio da mejores resultados en cada género?<br>4. ¿Influyen el multijugador, el cooperativo o el número de idiomas en el éxito de un juego? |
| **Limitación inicial** | • Las métricas de éxito dejaron de actualizarse a **finales de mayo de 2025**: los juegos posteriores aparecen con 0 reseñas. Por eso el periodo de análisis termina en esa fecha.<br>• Los juegos más recientes han tenido menos tiempo para acumular reseñas, así que no se pueden comparar en bruto con los más antiguos.<br>• No hay ventas reales: `Estimated owners` es un rango aproximado.<br>• 2020 fue un año atípico por la COVID. |
| **Motivo de elección** | Me interesa el desarrollo de videojuegos. El dataset tiene categorías para comparar (géneros, categorías, tags), cantidades numéricas (reseñas, precio, propietarios, horas de juego) y fechas para estudiar la evolución, así que sirve para todas las fases del curso. |
