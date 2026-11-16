# Preparación de los datos

## 1. Entender

### Decisiones

| Concepto | Nuestro proyecto |
|---|---|
| **Unidad de observación** | Una fila por juego de Steam. |
| **Clave candidata** | `app_id`: identifica un juego dentro de Steam. |
| **Esquema de salida** | Tabla `juegos` (detallada en la tabla siguiente). |
| **Alcance** | **Fuente:** Steam Games Dataset de FronkonGames en Kaggle, captura del 27/10/2026.<br>**Periodo:** juegos lanzados entre el 01/01/2020 y el 31/05/2025.<br>**Filtros:** fecha de lanzamiento dentro del periodo y solo las columnas necesarias para las cuatro preguntas del README.<br>**Población:** juegos publicados en la tienda Steam (mercado global). |
| **Trazabilidad** | Ruta del archivo RAW (`archivo_origen`) y posición del registro en el CSV original (`registro_origen`). |

### Tabla de salida: `juegos`

| Columna | Tipo | Obligatoria | Descripción |
|---|---|---|---|
| `app_id` | Entero | Sí | Identificador del juego en Steam. Clave candidata. |
| `nombre` | Texto | Sí | Nombre del juego. |
| `fecha_lanzamiento` | Fecha | Sí | Fecha de lanzamiento en Steam (entre 01/01/2020 y 31/05/2025). |
| `generos` | Lista de texto | No | Géneros oficiales del juego (Action, RPG, Indie…). Puede venir vacío; esos juegos no entran en la comparación por género. |
| `categorias` | Lista de texto | No | Características del juego (Single-player, Multi-player, Co-op, Online PvP…). Puede venir vacío. |
| `tags` | Lista de texto | No | Etiquetas de la comunidad (Roguelike, Survival, Pixel Graphics…). Detallan el nicho dentro de géneros muy amplios. Puede venir vacío. |
| `resenas_positivas` | Entero | Sí | Número de reseñas positivas. |
| `resenas_negativas` | Entero | Sí | Número de reseñas negativas. |
| `total_resenas` | Entero | Sí | Suma de reseñas positivas y negativas (columna derivada). |
| `pct_positivo` | Decimal | No | Porcentaje de reseñas positivas sobre el total (0–100). Vacío si el juego no tiene reseñas. |
| `propietarios_min` | Entero | Sí | Límite inferior del rango de `Estimated owners`. |
| `propietarios_max` | Entero | Sí | Límite superior del rango de `Estimated owners`. |
| `precio_usd` | Decimal | Sí | Precio en dólares estadounidenses. 0 si el juego es gratuito. |
| `es_gratis` | Booleano | Sí | Verdadero si `precio_usd` es 0 (columna derivada). |
| `descuento_pct` | Entero | Sí | Descuento aplicado en la fecha de la captura (0–100). Sirve para detectar precios rebajados. |
| `idiomas` | Lista de texto | No | Idiomas con interfaz o subtítulos. |
| `num_idiomas` | Entero | Sí | Número de idiomas de `idiomas` (columna derivada). |
| `idiomas_audio` | Lista de texto | No | Idiomas con doblaje completo. |
| `num_idiomas_audio` | Entero | Sí | Número de idiomas de `idiomas_audio` (columna derivada). |
| `archivo_origen` | Texto | Sí | Ruta relativa del RAW dentro del proyecto; incluye la captura (`data/raw/2026-10-27/games.csv`). |
| `registro_origen` | Entero | Sí | Posición del registro en el CSV original, sin contar la cabecera y empezando desde cero. Se cuenta por registro y no por línea, porque `About the game` contiene saltos de línea. |

### Transformaciones necesarias

| Transformación | Columna original | Resultado | Motivo |
|---|---|---|---|
| Corregir la cabecera | `DiscountDLC count` | `Discount` y `DLC count` | La cabecera tiene 39 nombres y las filas 40 valores; sin corregirla, las columnas se desplazan al leer el CSV. |
| Añadir procedencia | — | `archivo_origen`, `registro_origen` | Poder localizar cada registro limpio en el archivo RAW. Se añade antes de filtrar para conservar la posición original. |
| Seleccionar y renombrar columnas | `AppID`, `Name`, `Release date`, `Genres`, `Categories`, `Tags`, `Positive`, `Negative`, `Estimated owners`, `Price`, `Discount`, `Supported languages`, `Full audio languages` | Nombres en minúsculas y en español | Quedarse solo con lo necesario para las preguntas y unificar el estilo de nombres. |
| Convertir texto a fecha | `Release date` (`"Jul 29, 2016"`) | `fecha_lanzamiento` (Fecha) | Poder filtrar y agrupar por fecha. |
| Filtrar periodo | `fecha_lanzamiento` | Solo 01/01/2020–31/05/2025 | Periodo de análisis; las métricas dejaron de actualizarse a finales de mayo de 2025. |
| Separar campos multivalor | `Genres`, `Categories`, `Tags` (texto separado por comas) | `generos`, `categorias`, `tags` (listas) | Una celda puede tener varios valores. Se mantienen en la tabla `juegos` y se separarán en una fila por valor al agrupar. |
| Convertir listas de idiomas | `Supported languages`, `Full audio languages` (texto con formato `"['English', 'French']"`) | `idiomas`, `idiomas_audio` (listas) y `num_idiomas`, `num_idiomas_audio` (enteros) | El texto con corchetes no se puede contar ni filtrar directamente. |
| Unificar categorías | `generos`, `categorias`, `tags`, `idiomas` | Valores sin espacios sobrantes y con el mismo formato | Evitar que el mismo valor cuente como dos distintos. |
| Separar un rango en dos números | `Estimated owners` (`"20000 - 50000"`) | `propietarios_min`, `propietarios_max` (enteros) | El rango en texto no se puede comparar ni ordenar. |
| Calcular métricas de éxito | `Positive`, `Negative` | `total_resenas`, `pct_positivo` | Medir el éxito con el volumen y la calidad de las reseñas. |
| Convertir precio y descuento | `Price`, `Discount` | `precio_usd` (decimal), `descuento_pct` (entero), `es_gratis` (booleano) | Comparar tramos de precio y separar los juegos gratuitos de los de pago. |
| Tratar valores ausentes | `Genres`, `Categories`, `Tags` e idiomas vacíos; juegos con 0 reseñas | Valores nulos | Distinguir "sin dato" de un valor real y no calcular porcentajes sobre 0 reseñas. |
