# Preparación de los datos

1. [Entender (Tarea 3.1)](#1-entender-tarea-31)
2. [Diagnosticar (Tarea 3.2)](#2-diagnosticar-tarea-32)
3. [Transformar (Tarea 3.3)](#3-transformar-tarea-33)
4. [Validar y guardar (Tarea 3.4)](#4-validar-y-guardar-tarea-34)

<br><br>

## 1. Entender (Tarea 3.1)

Qué datos hacen falta para responder las preguntas y cómo serán las tablas preparadas.

### Decisiones

| Concepto | Nuestro proyecto |
|---|---|
| **Pregunta** | Si fuera un estudio de videojuegos, ¿qué género y qué categoría de juego debería desarrollar?<br>1. ¿Qué géneros y categorías tienen mejor relación entre éxito (reseñas, % positivo) y competencia (número de juegos)?<br>2. ¿Cómo ha evolucionado la oferta de cada género entre 2020 y 2025, incluido el efecto del boom de la COVID en 2020?<br>3. ¿Qué precio da mejores resultados en cada género?<br>4. ¿Influyen el multijugador, el cooperativo o los idiomas (cuántos y cuáles) en el éxito de un juego? |
| **Unidad de observación** | `juegos`: una fila por juego de Steam.<br>`generos`, `categorias`, `etiquetas` e `idiomas`: una fila por cada valor de un juego. |
| **Clave candidata** | `juegos`: `appid`, que identifica un juego dentro de Steam.<br>`generos`, `categorias`, `etiquetas` e `idiomas`: `appid` + el valor (p. ej. `(appid, genero)`), que identifica cada valor una sola vez por juego. |
| **Esquema de salida** | Tabla `juegos` y cuatro tablas que la amplían, `generos`, `categorias`, `etiquetas` e `idiomas`, unidas a ella por `appid` (detalladas en las tablas siguientes). |
| **Alcance** | **Fuente:** captura propia de la API de Steam del 18/11/2026 (`data/raw/2026-11-18/`).<br>**Periodo:** juegos con alguna de sus cuatro fechas (tienda, Steam, original y salida del acceso anticipado) entre el 01/01/2020 y el 31/12/2025. A cada juego se le asigna la primera de esas fechas que cae en el periodo.<br>**Filtros:** solo juegos (no DLC, demos, bandas sonoras ni herramientas), ya lanzados y con ficha en la tienda de España. Solo las columnas necesarias para las cuatro preguntas del README.<br>**Población:** juegos publicados en la tienda Steam (mercado global). |
| **Trazabilidad** | Carpeta de la captura (`captura_origen`) y `appid`, que localiza la línea del juego en `juegos_fichas.jsonl`. `generos`, `categorias`, `etiquetas` e `idiomas` llegan a esa línea por su `appid`. |

### Tabla de salida: `juegos`

| Columna | Tipo | Obligatoria | Descripción |
|---|---|---|---|
| `appid` | Entero | Sí | Identificador del juego en Steam. Clave candidata. |
| `nombre` | Texto | Sí | Nombre del juego. |
| `fecha_lanzamiento` | Fecha | Sí | Primera fecha del juego que cae entre 2020 y 2025: la de la tienda, la de Steam, la original (p. ej. inicio del acceso anticipado) o la de salida del acceso anticipado. De ella se sacan el año y el mes. |
| `resenas_positivas` | Entero | Sí | Número de reseñas positivas. |
| `resenas_negativas` | Entero | Sí | Número de reseñas negativas. |
| `precio_base_centimos` | Entero | No | Precio sin descuento en la tienda de España, en céntimos de euro. 0 si el juego es gratis. Nulo si el juego no se puede comprar suelto en la tienda (retirado, solo en ediciones o packs). |
| `captura_origen` | Texto | Sí | Ruta relativa de la carpeta de la captura dentro del proyecto (`data/raw/2026-11-18`). |

### Tablas de salida: `generos`, `categorias`, `etiquetas` e `idiomas`

Un juego sin géneros, categorías, etiquetas o idiomas no tiene filas en la tabla correspondiente, así que no entra en las comparaciones por ese campo.

| Tabla | Columna | Tipo | Obligatoria | Descripción |
|---|---|---|---|---|
| `generos` | `appid` | Entero | Sí | Juego al que pertenece el género. |
| `generos` | `genero` | Texto | Sí | Género oficial del juego (Action, RPG, Indie…). |
| `categorias` | `appid` | Entero | Sí | Juego al que pertenece la categoría. |
| `categorias` | `categoria` | Texto | Sí | Característica del juego (Single-player, Multi-player, Co-op, Online PvP…). |
| `etiquetas` | `appid` | Entero | Sí | Juego al que pertenece la etiqueta. |
| `etiquetas` | `etiqueta` | Texto | Sí | Etiqueta de la tienda, votada por la comunidad (Roguelike, Survival, Pixel Graphics…). Detalla el nicho dentro de géneros muy amplios. |
| `idiomas` | `appid` | Entero | Sí | Juego al que pertenece el idioma. |
| `idiomas` | `idioma` | Texto | Sí | Idioma con interfaz o subtítulos (English, Spanish - Spain…). |
| `idiomas` | `audio` | Booleano | Sí | Si el idioma tiene audio completo (doblaje). |

### Transformaciones necesarias

| Transformación | Columna original | Resultado | Motivo |
|---|---|---|---|
| Añadir procedencia | — | `captura_origen` | Poder localizar cada registro limpio en la captura RAW. |
| Seleccionar columnas | `nombre`, fechas, `generos`, `categorias`, `etiquetas`, `resenas_positivas`, `resenas_negativas`, `precio_base_centimos`, `es_gratis`, `moneda`, `idiomas` de `juegos_fichas` | Solo las columnas de las tablas de salida | Quedarse solo con lo necesario para las preguntas. |
| Convertir texto a fecha | `fecha_lanzamiento` (`"9 Sep, 2026"`), `fecha_lanzamiento_steam`, `fecha_lanzamiento_original`, `fecha_salida_acceso_anticipado` (`"2021-02-02"`) | Fechas | Poder comparar y agrupar por fecha. |
| Elegir fecha y filtrar periodo | `fecha_lanzamiento`, `fecha_lanzamiento_steam`, `fecha_lanzamiento_original`, `fecha_salida_acceso_anticipado` | `fecha_lanzamiento` (la primera que cae en 2020–2025). Se quitan los juegos sin ninguna fecha en el periodo | La captura deja un día de margen en cada extremo. Aquí se aplica el periodo exacto con las mismas cuatro fechas que usa la ingesta. |
| Separar listas en tablas | `generos`, `categorias`, `etiquetas` (listas) | Tablas `generos`, `categorias` y `etiquetas`, con una fila por valor | Agrupar por género o categoría sin desagregar las listas en cada análisis. Además, cada fila tiene una clave clara. |
| Separar idiomas | `idiomas` (texto con HTML: `English<strong>*</strong>, French`) | Tabla `idiomas`, con una fila por idioma y si tiene audio | La pregunta 4 necesita cuántos idiomas tiene cada juego y cuáles son los más frecuentes. Los marcados con `*` tienen audio completo. |
| Unificar valores | `generos`, `categorias`, `etiquetas`, `idiomas` | Valores sin espacios sobrantes y con el mismo formato | Evitar que el mismo valor cuente como dos distintos. |
| Completar el precio | `precio_base_centimos`, `es_gratis` | `precio_base_centimos` = 0 en juegos gratis | Los juegos gratis no traen precio. Con 0 tienen un valor comparable y se identifican fácilmente. |
| Tratar valores ausentes | Listas vacías (`generos`, `categorias`, `etiquetas`), `idiomas` nulo y juegos de pago sin precio | Sin filas en la tabla correspondiente y `precio_base_centimos` nulo | Distinguir "sin dato" de un valor real (p. ej. no poner precio 0 a un juego de pago). |

<br><br>

## 2. Diagnosticar (Tarea 3.2)

Revisión de la captura original para encontrar problemas antes de transformarla.

Código: `scripts/2_diagnostico.py`, sobre la captura de `data/raw/2026-11-18/`.

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
| Juegos fuera del periodo exacto | 70 (0,1 %). Ninguna de sus cuatro fechas cae en el periodo, solo entraron por el día de margen de la ingesta (31/12/2019 o 01/01/2026) | Se filtran en la limpieza. |

### Problemas y dudas detectados

| Problema | Cifra | Tipo |
|---|---|---|
| Precios en dólares (USD) en la tienda de España | 2 juegos | Error confirmado |
| Precio incoherente con `es_gratis`: juegos de pago sin precio o gratis con precio | 161 juegos (0,2 %) | Error confirmado |
| Fichas de tipo juego que no son juegos: herramientas, servidores dedicados y demos | 64 fichas (0,1 %) | Error confirmado |
| Juegos con 0 reseñas: sin ventas, demasiado recientes o fallo de la API. No tienen % positivo. | 4.326 juegos (5,3 %) | Necesita investigación |

<br><br>

## 3. Transformar (Tarea 3.3)

Reglas para pasar de la captura original a las tablas preparadas.

Código: `scripts/3_transformacion.py`. Lee la captura de `data/raw/2026-11-18/` y guarda las tablas en `data/processed/2026-11-18/`, ordenadas por fecha.

### Reglas

Se aplican en este orden. Si un juego cumple varias reglas de exclusión, cuenta solo en la primera.

| # | Condición | Acción | Motivo | Juegos |
|---|---|---|---|---|
| 1 | Ninguna de sus cuatro fechas cae entre el 01/01/2020 y el 31/12/2025 | Excluir (`fuera_periodo`) | Solo entraron por el día de margen de la ingesta. | 70 |
| 2 | Sin género y sin más categoría que Family Sharing, o con "Dedicated Server", "Mod Tools", "SDK", "Artbook", "Soundtrack" o "Demo" en el nombre | Excluir (`no_es_juego`) | Herramientas, servidores, artbooks, bandas sonoras y demos que Steam clasifica como juego. | 64 |
| 3 | Precio en otra moneda, gratis con precio o de pago sin precio, con 10 reseñas o menos | Excluir (`precio_anomalo`) | Precio no fiable en juegos sin peso en el análisis. | 61 |
| 4 | De pago sin precio y género Free To Play | Excluir (`precio_anomalo`) | Revisados en Steam: playtests o juegos que ya no existen. | 8 |
| 5 | Gratis sin precio, o gratis con precio y género Free To Play | Precio 0 | Los juegos gratis no traen precio, y los de Capcom traen el precio de un pack. | 12.795 |
| 6 | De pago sin precio con más de 10 reseñas | Precio nulo | No se pueden comprar sueltos (retirados o solo en ediciones): no hay un precio real. | 69 |
| 7 | Fechas en texto | Convertir a fecha y asignar la primera que cae en el periodo | Una sola fecha comparable por juego. | 81.079 |
| 8 | Texto de idiomas con HTML | Una fila por idioma en `idiomas`, con `audio` si lleva `*`. Sin filas si declara 100 idiomas o más | Los juegos que marcan (casi) todos los idiomas de Steam no reflejan su traducción real. | 1.751 sin filas |
| 9 | Listas de géneros, categorías y etiquetas | Una fila por valor en su tabla. Las listas vacías no generan filas | Agrupar por valor sin desplegar las listas en cada análisis. | 81.079 |

### Procedencia y excluidos

- Cada juego conserva su `appid` y `captura_origen` (`data/raw/2026-11-18`), que localizan su línea en `juegos_fichas.jsonl`. Las tablas hijas llegan a ella por `appid`.
- Los excluidos se guardan en la tabla `excluidos` con `appid`, `nombre`, `motivo`, `detalle` (la regla concreta) y `captura_origen`.

### Recuentos

| Registros | Juegos |
|---|---|
| Originales (`juegos_fichas.jsonl`) | 81.282 |
| Preparados (`juegos`) | 81.079 |
| Excluidos (`excluidos`) | 203: 70 `fuera_periodo`, 64 `no_es_juego` y 69 `precio_anomalo` |

Al desplegar las listas cambia la unidad de observación: en `juegos` cada fila es un juego y en las tablas hijas, un valor de un juego. Por eso tienen más filas que juegos, y un juego cuenta en tantos géneros como tenga.

| Tabla | Filas | Unidad de observación | Media por juego |
|---|---|---|---|
| `juegos` | 81.079 | un juego | — |
| `generos` | 236.231 | un género de un juego | 2,9 |
| `categorias` | 392.094 | una categoría de un juego | 4,8 |
| `etiquetas` | 1.344.486 | una etiqueta de un juego | 16,6 |
| `idiomas` | 333.369 | un idioma de un juego | 4,1 |

### Antes y después

| Juego | Campo | Antes (RAW) | Después |
|---|---|---|---|
| Kirchhoff's Revenge (801120) | Fecha | `"31 Dec, 2019"` (tienda) | 01/01/2020 (fecha de Steam, la primera dentro del periodo) |
| Kirchhoff's Revenge (801120) | Precio | vacío, `es_gratis` = true | 0 |
| Capcom Arcade Stadium (1515950) | Precio | 5999, `es_gratis` = true | 0 |
| Dictators:No Peace Countryballs (1139890) | Idiomas | `"English<strong>*</strong>, French<strong>*</strong>, …"` | 11 filas en `idiomas`, todas con `audio` = true |

### Ejemplo del resultado

Dictators:No Peace Countryballs (1139890) en `juegos`:

| appid | nombre | fecha_lanzamiento | resenas_positivas | resenas_negativas | precio_base_centimos | captura_origen |
|---|---|---|---|---|---|---|
| 1139890 | Dictators:No Peace Countryballs | 2020-01-01 | 5885 | 360 | 109 | data/raw/2026-11-18 |

Y en las tablas hijas: 4 filas en `generos` (Casual, Indie, Simulation, Strategy), 2 en `categorias` (Family Sharing, Single-player), 8 en `etiquetas` y 11 en `idiomas` (English, French, German…).

<br><br>

## 4. Validar y guardar (Tarea 3.4)

Comprobación de que las tablas preparadas cumplen el diseño, cuántos registros se pierden por el camino y cómo repetir todo el proceso.

Código: `scripts/4_validacion.py`. Lee las tablas de `data/processed/2026-11-18/` y muestra cada control con los casos que lo incumplen.

### Controles

Resultado: **34 de 34 controles correctos**. Para confirmar que los controles funcionan, se probaron con errores metidos a propósito (clave repetida, precio negativo, nombre vacío, HTML en un idioma, tipo cambiado…) y todos los detectaron.

| Control | Tablas | Qué comprueba | Resultado |
|---|---|---|---|
| Columnas y tipos | Todas | Las columnas y tipos de la 3.1: fecha como fecha, precio como entero con nulos, `audio` como booleano… | 0 errores |
| Obligatorios | Todas | Ningún nulo, salvo en `precio_base_centimos` | 0 nulos |
| Claves | Todas | `appid` en `juegos` y `excluidos`, `(appid, valor)` en las tablas hijas | 0 repetidas |
| Relaciones | Hijas y `excluidos` | Todo `appid` de las tablas hijas está en `juegos` y ningún excluido está en `juegos` | 0 errores |
| Rangos | `juegos` | Fecha entre el 01/01/2020 y el 31/12/2025, reseñas y precio no negativos | 0 fuera de rango |
| Categorías | Hijas y `excluidos` | Motivo de exclusión conocido. Valores sin espacios sobrantes, vacíos ni restos de HTML | 0 errores |
| Procedencia | `juegos` y `excluidos` | `captura_origen` es `data/raw/2026-11-18` | 0 errores |
| Balance | `juegos` + `excluidos` | Suman los 81.282 registros de la captura | Cuadra |
| Guardado | Todas | Al volver a leer cada Parquet, el contenido y los tipos son idénticos. Lo comprueba `3_transformacion.py` al guardar | Idénticas |

### Balance de registros

| Paso | Juegos |
|---|---|
| Entran (`juegos_fichas.jsonl`) | 81.282 |
| Se apartan (`excluidos`) | 203 (0,2 %) |
| Quedan preparados (`juegos`) | 81.079 |

Algunos juegos preparados no tienen todos los datos. Siguen contando en el resto del análisis, pero faltan en las preguntas que usan ese dato:

| Dato que falta | Juegos | Preguntas afectadas |
|---|---|---|
| Reseñas (0 reseñas, sin % positivo) | 4.292 | 1, 3 y 4 |
| Idiomas | 1.842 (1.751 declaran 100 o más y 91 no traen idiomas) | 4 |
| Precio | 69 | 3 |
| Categorías | 51 | 1 y 4 |
| Género | 50 | 1, 2 y 3 |

La unidad de observación cambia al preparar: entra un registro por juego y salen la tabla `juegos` (un juego por fila) y cuatro tablas con un valor de un juego por fila. El detalle está en los recuentos de la 3.3.

### Archivos generados

En `data/processed/2026-11-18/`, en formato Parquet (7,5 MB en total). Parquet guarda los tipos de cada columna, así que las tablas se leen igual que se guardaron.

| Archivo | Filas | Contenido |
|---|---|---|
| `juegos.parquet` | 81.079 | Un juego por fila |
| `generos.parquet` | 236.231 | Un género de un juego por fila |
| `categorias.parquet` | 392.094 | Una categoría de un juego por fila |
| `etiquetas.parquet` | 1.344.486 | Una etiqueta de un juego por fila |
| `idiomas.parquet` | 333.369 | Un idioma de un juego por fila, con si tiene audio |
| `excluidos.parquet` | 203 | Un juego apartado por fila, con su motivo |

### Ejecución

- **Captura original:** `data/raw/2026-11-18/juegos_fichas.jsonl` (81.282 registros).
- **Dependencias:** Python 3.15 con pandas 3.1 y pyarrow 26, instaladas desde `requirements.txt`. El entorno se crea con `python scripts/0_entorno.py` y se activa con `.venv\Scripts\Activate.ps1`.
- **Comandos**, desde la raíz del repositorio y con el entorno activado:

```
python scripts/2_diagnostico.py --fecha 2026-11-18
python scripts/3_transformacion.py --fecha 2026-11-18
python scripts/4_validacion.py --fecha 2026-11-18
```

La transformación sobrescribe las tablas de `data/processed/2026-11-18/` cada vez que se ejecuta. La captura de `data/raw/` solo se lee.

### Limitaciones para el análisis

- **No hay ventas:** el éxito se mide con las reseñas, que solo escriben quienes tienen el juego.
- **Los juegos recientes tienen menos reseñas:** la mediana baja de 25 en 2020 a 12 en 2025. Hay que comparar dentro de cada año o tenerlo en cuenta.
- **Las reseñas están muy concentradas:** el 1 % de los juegos acumula el 75 % de las reseñas. Las medianas representan mejor al juego típico que las medias.
- **Muchos juegos tienen pocas reseñas:** el 37 % tiene menos de 10, así que su % positivo es poco fiable.
- **"Free To Play" y "Early Access" aparecen como géneros** (9.846 y 7.307 juegos), aunque no son temáticos.
- **Call of Duty® agrupa varios juegos** y suma 812.352 reseñas, que pesan mucho en sus géneros.
- **El precio es el actual en la tienda de España**, no el de lanzamiento.
- **Los idiomas los declara el desarrollador:** no se puede comprobar que el juego esté traducido de verdad.
- **Acceso anticipado:** se usa la primera fecha dentro del periodo. Los juegos que llevan años en acceso anticipado (791 tienen la fecha original antes de 2020) acumulan más reseñas.
- **2020 fue un año atípico** por la COVID.
- **Las reglas de "no es un juego" usan el nombre:** una herramienta o demo sin esas palabras en el nombre puede seguir en los datos.
