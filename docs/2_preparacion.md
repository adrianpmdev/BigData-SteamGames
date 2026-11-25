# Preparación de los datos

## 1. Entender

### Decisiones

| Concepto | Nuestro proyecto |
|---|---|
| **Pregunta** | Si fuera un estudio de videojuegos, ¿qué género y qué categoría de juego debería desarrollar?<br>1. ¿Qué géneros y categorías tienen mejor relación entre éxito (reseñas, % positivo) y competencia (número de juegos)?<br>2. ¿Cómo ha evolucionado la oferta de cada género entre 2020 y 2025, incluido el efecto del boom de la COVID en 2020?<br>3. ¿Qué precio da mejores resultados en cada género?<br>4. ¿Influyen el multijugador, el cooperativo o el número de idiomas en el éxito de un juego? |
| **Unidad de observación** | `juegos`: una fila por juego de Steam.<br>`generos`, `categorias` y `etiquetas`: una fila por cada valor de un juego. |
| **Clave candidata** | `juegos`: `appid`, que identifica un juego dentro de Steam.<br>`generos`, `categorias` y `etiquetas`: `appid` + el valor (p. ej. `(appid, genero)`), que identifica cada valor una sola vez por juego. |
| **Esquema de salida** | Tabla `juegos` y tres tablas que la amplían, `generos`, `categorias` y `etiquetas`, unidas a ella por `appid` (detalladas en las tablas siguientes). |
| **Alcance** | **Fuente:** captura propia de la API de Steam del 18/11/2026 (`data/raw/2026-11-18/`).<br>**Periodo:** juegos con alguna de sus cuatro fechas (tienda, Steam, original y salida del acceso anticipado) entre el 01/01/2020 y el 31/12/2025. A cada juego se le asigna la primera de esas fechas que cae en el periodo.<br>**Filtros:** solo juegos (no DLC, demos, bandas sonoras ni herramientas), ya lanzados y con ficha en la tienda de España; solo las columnas necesarias para las cuatro preguntas del README.<br>**Población:** juegos publicados en la tienda Steam (mercado global). |
| **Trazabilidad** | Carpeta de la captura (`captura_origen`) y `appid`, que localiza la línea del juego en `juegos_fichas.jsonl`. `generos`, `categorias` y `etiquetas` llegan a esa línea por su `appid`. |

### Tabla de salida: `juegos`

| Columna | Tipo | Obligatoria | Descripción |
|---|---|---|---|
| `appid` | Entero | Sí | Identificador del juego en Steam. Clave candidata. |
| `nombre` | Texto | Sí | Nombre del juego. |
| `fecha_lanzamiento` | Fecha | Sí | Primera fecha del juego que cae entre 2020 y 2025: la de la tienda, la de Steam, la original (p. ej. inicio del acceso anticipado) o la de salida del acceso anticipado. De ella se sacan el año y el mes. |
| `resenas_positivas` | Entero | Sí | Número de reseñas positivas. |
| `resenas_negativas` | Entero | Sí | Número de reseñas negativas. |
| `precio_base_centimos` | Entero | No | Precio sin descuento en la tienda de España, en céntimos de euro. 0 si el juego es gratis. Nulo si el juego no se puede comprar suelto en la tienda (retirado, solo en ediciones o packs). |
| `num_idiomas` | Entero | No | Número de idiomas con interfaz o subtítulos. Nulo si la ficha no trae idiomas. |
| `num_idiomas_audio` | Entero | No | Número de idiomas con audio completo (doblaje). Nulo si la ficha no trae idiomas. |
| `captura_origen` | Texto | Sí | Ruta relativa de la carpeta de la captura dentro del proyecto (`data/raw/2026-11-18`). |

### Tablas de salida: `generos`, `categorias` y `etiquetas`

Un juego sin géneros, categorías o etiquetas no tiene filas en la tabla correspondiente, así que no entra en las comparaciones por ese campo.

| Tabla | Columna | Tipo | Obligatoria | Descripción |
|---|---|---|---|---|
| `generos` | `appid` | Entero | Sí | Juego al que pertenece el género. |
| `generos` | `genero` | Texto | Sí | Género oficial del juego (Action, RPG, Indie…). |
| `categorias` | `appid` | Entero | Sí | Juego al que pertenece la categoría. |
| `categorias` | `categoria` | Texto | Sí | Característica del juego (Single-player, Multi-player, Co-op, Online PvP…). |
| `etiquetas` | `appid` | Entero | Sí | Juego al que pertenece la etiqueta. |
| `etiquetas` | `etiqueta` | Texto | Sí | Etiqueta de la tienda, votada por la comunidad (Roguelike, Survival, Pixel Graphics…). Detalla el nicho dentro de géneros muy amplios. |

### Transformaciones necesarias

| Transformación | Columna original | Resultado | Motivo |
|---|---|---|---|
| Añadir procedencia | — | `captura_origen` | Poder localizar cada registro limpio en la captura RAW. |
| Seleccionar columnas | `nombre`, fechas, `generos`, `categorias`, `etiquetas`, `resenas_positivas`, `resenas_negativas`, `precio_base_centimos`, `es_gratis`, `moneda`, `idiomas` de `juegos_fichas` | Solo las columnas de las tablas de salida | Quedarse solo con lo necesario para las preguntas. |
| Convertir texto a fecha | `fecha_lanzamiento` (`"9 Sep, 2026"`), `fecha_lanzamiento_steam`, `fecha_lanzamiento_original`, `fecha_salida_acceso_anticipado` (`"2021-02-02"`) | Fechas | Poder comparar y agrupar por fecha. |
| Elegir fecha y filtrar periodo | `fecha_lanzamiento`, `fecha_lanzamiento_steam`, `fecha_lanzamiento_original`, `fecha_salida_acceso_anticipado` | `fecha_lanzamiento` (la primera que cae en 2020–2025); fuera los juegos sin ninguna fecha en el periodo | La captura deja un día de margen en cada extremo; aquí se aplica el periodo exacto con las mismas cuatro fechas que usa la ingesta. |
| Separar listas en tablas | `generos`, `categorias`, `etiquetas` (listas) | Tablas `generos`, `categorias` y `etiquetas`, con una fila por valor | Agrupar por género o categoría sin desagregar las listas en cada análisis; además, una lista no se guarda bien en CSV. |
| Contar idiomas | `idiomas` (texto con HTML: `English<strong>*</strong>, French`) | `num_idiomas`, `num_idiomas_audio` | La pregunta 4 solo necesita el número de idiomas; los marcados con `*` tienen audio completo. |
| Unificar valores | `generos`, `categorias`, `etiquetas`, `idiomas` | Valores sin espacios sobrantes y con el mismo formato | Evitar que el mismo valor cuente como dos distintos. |
| Completar el precio | `precio_base_centimos`, `es_gratis` | `precio_base_centimos` = 0 en juegos gratis | Los juegos gratis no traen precio; así los juegos gratis tienen un valor comparable y el precio 0 los identifica. |
| Tratar valores ausentes | Listas vacías (`generos`, `categorias`, `etiquetas`), `idiomas` nulo y juegos de pago sin precio | Sin filas en la tabla correspondiente; `num_idiomas`, `num_idiomas_audio` y `precio_base_centimos` nulos | Distinguir "sin dato" de un valor real (p. ej. no contar 0 idiomas). |

## 2. Diagnosticar

Código: `scripts/2_diagnostico.py` (solo lee la captura de `data/raw/2026-11-18/`; no modifica nada).

### Comprobaciones

| Comprobación | Resultado | Conclusión |
|---|---|---|
| Filas y columnas de cada archivo | `juegos_lista` 201.397 × 4 · `juegos_periodo` 81.597 × 6 · `juegos_fichas` 81.282 × 17 · `juegos_descartados` 120.115 × 4 | `juegos_fichas` es la base de la tabla `juegos`. |
| Tipos de datos | Fechas como texto en dos formatos (`"18 Mar, 2020"` en la tienda e ISO en Steam). `precio_base_centimos` es decimal por los nulos. Listas como `object`. `idiomas` es texto con HTML. | Hay que convertir las fechas y pasar el precio a entero. |
| Valores ausentes (nulos, listas vacías y textos vacíos) | Precio, descuento y moneda: 13.001 nulos. Fecha original: 75.136. `idiomas`: 109. Listas vacías: 70 en géneros, 52 en categorías y 15 en etiquetas. | Precio nulo → 0 en los juegos gratis. La fecha original solo existe en juegos con acceso anticipado. Las listas vacías no generan filas en `generos`, `categorias` y `etiquetas`. |
| Filas repetidas | 0 en los 4 archivos | Nada que eliminar. |
| `appid` repetido (clave candidata) | 0 en los 4 archivos | `appid` es una clave válida. |
| Cuadre entre archivos (lista, periodo, fichas y descartados) | 0 discrepancias: 201.397 = 81.597 en periodo + 119.800 descartados, y 81.597 = 81.282 fichas + 315 descartados | La captura está completa: no queda nada pendiente. |
| Géneros, categorías y etiquetas distintos y variantes de un mismo valor | 30 géneros, 63 categorías y 429 etiquetas, sin variantes. "Free To Play" (9.894) y "Early Access" (7.351) aparecen como géneros. | No hace falta unificar valores. Esos dos géneros no son temáticos. |
| Moneda | EUR 68.279 · vacía 13.001 · USD 2 | Hay 2 precios que no están en euros. |
| Fichas que no son juegos | 64 en total: 19 herramientas sin género ni modo de juego, 15 herramientas por el nombre (servidores dedicados, mod tools, SDK, artbooks, bandas sonoras) y 40 demos publicadas como juego (algunas cumplen dos reglas) | Steam las clasifica como juego, pero no lo son: se excluyen en la transformación. |
| Precio y `es_gratis` coherentes | 3 gratis con precio · 158 de pago sin precio · 0 de pago con precio ≤ 0 · 0 descuentos fuera de 0–100 | 161 juegos tienen el precio incoherente con `es_gratis`. |
| Reseñas fuera de rango y juegos con 0 reseñas | 0 negativas · 4.326 juegos (5,3 %) con 0 reseñas | Para esos juegos no se puede calcular el % positivo. |
| Fechas no convertibles y fecha original posterior a la de la tienda | 0 no convertibles · 19 con la fecha original posterior a la de la tienda · 792 con la fecha original anterior a 2020 · 677 en acceso anticipado más de 3 años | La regla de asignar la primera fecha dentro del periodo resuelve estos casos. |
| Cobertura temporal (juegos por año, por mes en 2020 y fechas de petición) | 9.051 (2020) · 10.321 · 11.282 · 12.954 · 17.384 · 20.220 (2025). En 2020, entre 627 (marzo) y 906 (octubre) al mes. Peticiones del 18 al 24/11/2026. | La oferta crece cada año (×2,2). En 2020 no se ve un pico claro en marzo y abril. |
| Juegos fuera del periodo exacto | 70 (0,1 %): ninguna de sus cuatro fechas cae en el periodo; entraron solo por el día de margen de la ingesta (31/12/2019 o 01/01/2026) | Se filtran en la limpieza. |

### Problemas y dudas detectados

| Problema | Cifra | Tipo |
|---|---|---|
| Precios en dólares (USD) en la tienda de España | 2 juegos | Error confirmado |
| Precio incoherente con `es_gratis`: juegos de pago sin precio o gratis con precio | 161 juegos (0,2 %) | Error confirmado |
| Fichas de tipo juego que no son juegos: herramientas, servidores dedicados y demos | 64 fichas (0,1 %) | Error confirmado |
| Juegos con 0 reseñas: sin ventas, demasiado recientes o fallo de la API. No tienen % positivo. | 4.326 juegos (5,3 %) | Necesita investigación |
