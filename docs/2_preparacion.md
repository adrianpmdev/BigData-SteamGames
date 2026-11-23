# Preparación de los datos

## 1. Entender

### Decisiones

| Concepto | Nuestro proyecto |
|---|---|
| **Unidad de observación** | Una fila por juego de Steam. |
| **Clave candidata** | `appid`: identifica un juego dentro de Steam y no se repite en ningún archivo de la captura. |
| **Esquema de salida** | Tabla `juegos` (detallada en la tabla siguiente). |
| **Alcance** | **Fuente:** captura propia de la API de Steam del 18/11/2026 (`data/raw/2026-11-18/`).<br>**Periodo:** juegos cuya fecha original o fecha de lanzamiento cae entre el 01/01/2020 y el 31/12/2025. A cada juego se le asigna la primera de esas fechas que cae en el periodo.<br>**Filtros:** solo juegos (no DLC, demos ni bandas sonoras), ya lanzados y con ficha en la tienda de España; solo las columnas necesarias para las cuatro preguntas del README.<br>**Población:** juegos publicados en la tienda Steam (mercado global). |
| **Trazabilidad** | Carpeta de la captura (`captura_origen`) y `appid`, que localiza la línea del juego en `juegos_fichas.jsonl`. |

### Tabla de salida: `juegos`

| Columna | Tipo | Obligatoria | Descripción |
|---|---|---|---|
| `appid` | Entero | Sí | Identificador del juego en Steam. Clave candidata. |
| `nombre` | Texto | Sí | Nombre del juego. |
| `fecha_lanzamiento` | Fecha | Sí | Primera fecha del juego que cae entre 2020 y 2025: la original (p. ej. inicio del acceso anticipado) o la de la tienda. De ella se sacan el año y el mes. |
| `generos` | Lista de texto | No | Géneros oficiales del juego (Action, RPG, Indie…). Puede venir vacío; esos juegos no entran en la comparación por género. |
| `categorias` | Lista de texto | No | Características del juego (Single-player, Multi-player, Co-op, Online PvP…). Puede venir vacío. |
| `etiquetas` | Lista de texto | No | Etiquetas de la tienda, votadas por la comunidad (Roguelike, Survival, Pixel Graphics…). Detallan el nicho dentro de géneros muy amplios. Puede venir vacío. |
| `resenas_positivas` | Entero | Sí | Número de reseñas positivas. |
| `resenas_negativas` | Entero | Sí | Número de reseñas negativas. |
| `precio_base_centimos` | Entero | Sí | Precio sin descuento en la tienda de España, en céntimos de euro. 0 si el juego es gratis. |
| `idiomas` | Lista de texto | No | Idiomas con interfaz o subtítulos. |
| `idiomas_audio` | Lista de texto | No | Idiomas con audio completo (doblaje). |
| `captura_origen` | Texto | Sí | Ruta relativa de la carpeta de la captura dentro del proyecto (`data/raw/2026-11-18`). |

### Transformaciones necesarias

| Transformación | Columna original | Resultado | Motivo |
|---|---|---|---|
| Añadir procedencia | — | `captura_origen` | Poder localizar cada registro limpio en la captura RAW. |
| Seleccionar columnas | `nombre`, fechas, `generos`, `categorias`, `etiquetas`, `resenas_positivas`, `resenas_negativas`, `precio_base_centimos`, `es_gratis`, `idiomas` de `juegos_fichas` | Solo las columnas de la tabla `juegos` | Quedarse solo con lo necesario para las preguntas. |
| Convertir texto a fecha | `fecha_lanzamiento` (`"9 Sep, 2026"`), `fecha_lanzamiento_original` (`"2021-02-02"`) | Fechas | Poder comparar y agrupar por fecha. |
| Elegir fecha y filtrar periodo | `fecha_lanzamiento`, `fecha_lanzamiento_original` | `fecha_lanzamiento` (la primera que cae en 2020–2025); fuera los juegos sin ninguna fecha en el periodo | La captura deja un día de margen en cada extremo y acepta cualquier fecha de Steam; aquí se aplica el periodo exacto con la fecha de la tienda. |
| Separar idiomas | `idiomas` (texto con HTML: `English<strong>*</strong>, French`) | `idiomas`, `idiomas_audio` (listas) | El texto con HTML no se puede contar ni filtrar; los idiomas con `*` tienen audio completo. |
| Unificar valores | `generos`, `categorias`, `etiquetas`, `idiomas` | Valores sin espacios sobrantes y con el mismo formato | Evitar que el mismo valor cuente como dos distintos. |
| Completar el precio | `precio_base_centimos`, `es_gratis` | `precio_base_centimos` = 0 en juegos gratis | Los juegos gratis no traen precio; así todos los juegos tienen un valor comparable y el precio 0 identifica a los gratuitos. |
| Tratar valores ausentes | Listas vacías (`generos`, `categorias`, `etiquetas`, `idiomas`) | Valores nulos | Distinguir "sin dato" de un valor real. |
