-- ============================================================================ --
-- Esquema de la base de datos de juegos de Steam (2020-2025) en PostgreSQL.    --
--                                                                              --
-- Tablas creadas a partir de las tablas preparadas de data/processed/<fecha>/  --
-- (diseño en docs/2_preparacion.md).                                           --
--                                                                              --
-- ============================================================================ --

SET client_encoding = 'UTF8';
BEGIN;

CREATE SCHEMA IF NOT EXISTS catalogo_steam;

-- ---------------------------------------------------------------------------- --
-- Juegos                                                                       --
-- ---------------------------------------------------------------------------- --

CREATE TABLE IF NOT EXISTS catalogo_steam.juegos (
    appid                INTEGER NOT NULL,
    fecha_captura        DATE NOT NULL,
    nombre               TEXT NOT NULL,
    fecha_lanzamiento    DATE NOT NULL,
    resenas_positivas    INTEGER NOT NULL,
    resenas_negativas    INTEGER NOT NULL,
    precio_base_centimos INTEGER,
    archivo_origen       TEXT NOT NULL,
    registro_origen      INTEGER NOT NULL,

    CONSTRAINT juegos_pk PRIMARY KEY (appid, fecha_captura),
    CONSTRAINT juegos_registro_unico UNIQUE (archivo_origen, registro_origen),
    CONSTRAINT juegos_appid_positivo CHECK (appid > 0),
    CONSTRAINT juegos_fecha_captura_finita CHECK (isfinite(fecha_captura)),
    CONSTRAINT juegos_nombre_normalizado CHECK (nombre <> '' AND nombre = btrim(nombre)),
    CONSTRAINT fecha_en_periodo CHECK (fecha_lanzamiento BETWEEN DATE '2020-01-01' AND DATE '2025-12-31'),
    CONSTRAINT lanzado_antes_de_la_captura CHECK (fecha_lanzamiento <= fecha_captura),
    CONSTRAINT resenas_no_negativas CHECK (resenas_positivas >= 0 AND resenas_negativas >= 0),
    CONSTRAINT precio_no_negativo CHECK (precio_base_centimos IS NULL OR precio_base_centimos >= 0),
    CONSTRAINT juegos_archivo_de_la_captura CHECK (archivo_origen LIKE 'data/raw/' || to_char(fecha_captura, 'YYYY-MM-DD') || '/%'),
    CONSTRAINT juegos_registro_no_negativo CHECK (registro_origen >= 0)
);

CREATE TABLE IF NOT EXISTS catalogo_steam.excluidos (
    appid           INTEGER NOT NULL,
    fecha_captura   DATE NOT NULL,
    nombre          TEXT NOT NULL,
    motivo          TEXT NOT NULL,
    detalle         TEXT NOT NULL,
    archivo_origen  TEXT NOT NULL,
    registro_origen INTEGER NOT NULL,

    CONSTRAINT excluidos_pk PRIMARY KEY (appid, fecha_captura),
    CONSTRAINT excluidos_registro_unico UNIQUE (archivo_origen, registro_origen),
    CONSTRAINT excluidos_appid_positivo CHECK (appid > 0),
    CONSTRAINT excluidos_fecha_captura_finita CHECK (isfinite(fecha_captura)),
    CONSTRAINT excluidos_nombre_normalizado CHECK (nombre <> '' AND nombre = btrim(nombre)),
    CONSTRAINT motivo_conocido CHECK (motivo IN ('fuera_periodo', 'no_es_juego', 'precio_anomalo')),
    CONSTRAINT detalle_no_vacio CHECK (btrim(detalle) <> ''),
    CONSTRAINT excluidos_archivo_de_la_captura CHECK (archivo_origen LIKE 'data/raw/' || to_char(fecha_captura, 'YYYY-MM-DD') || '/%'),
    CONSTRAINT excluidos_registro_no_negativo CHECK (registro_origen >= 0)
);

-- ---------------------------------------------------------------------------- --
-- Tablas hijas: un valor de un juego en una captura por fila                   --
-- ---------------------------------------------------------------------------- --

CREATE TABLE IF NOT EXISTS catalogo_steam.generos (
    appid         INTEGER NOT NULL,
    fecha_captura DATE NOT NULL,
    genero        TEXT NOT NULL,

    CONSTRAINT generos_pk PRIMARY KEY (appid, fecha_captura, genero),
    CONSTRAINT generos_juego_fk FOREIGN KEY (appid, fecha_captura) REFERENCES catalogo_steam.juegos (appid, fecha_captura),
    CONSTRAINT genero_normalizado CHECK (genero <> '' AND genero = btrim(genero))
);

CREATE TABLE IF NOT EXISTS catalogo_steam.categorias (
    appid         INTEGER NOT NULL,
    fecha_captura DATE NOT NULL,
    categoria     TEXT NOT NULL,

    CONSTRAINT categorias_pk PRIMARY KEY (appid, fecha_captura, categoria),
    CONSTRAINT categorias_juego_fk FOREIGN KEY (appid, fecha_captura) REFERENCES catalogo_steam.juegos (appid, fecha_captura),
    CONSTRAINT categoria_normalizada CHECK (categoria <> '' AND categoria = btrim(categoria))
);

CREATE TABLE IF NOT EXISTS catalogo_steam.etiquetas (
    appid         INTEGER NOT NULL,
    fecha_captura DATE NOT NULL,
    etiqueta      TEXT NOT NULL,

    CONSTRAINT etiquetas_pk PRIMARY KEY (appid, fecha_captura, etiqueta),
    CONSTRAINT etiquetas_juego_fk FOREIGN KEY (appid, fecha_captura) REFERENCES catalogo_steam.juegos (appid, fecha_captura),
    CONSTRAINT etiqueta_normalizada CHECK (etiqueta <> '' AND etiqueta = btrim(etiqueta))
);

CREATE TABLE IF NOT EXISTS catalogo_steam.idiomas (
    appid         INTEGER NOT NULL,
    fecha_captura DATE NOT NULL,
    idioma        TEXT NOT NULL,
    audio         BOOLEAN NOT NULL,

    CONSTRAINT idiomas_pk PRIMARY KEY (appid, fecha_captura, idioma),
    CONSTRAINT idiomas_juego_fk FOREIGN KEY (appid, fecha_captura) REFERENCES catalogo_steam.juegos (appid, fecha_captura),
    CONSTRAINT idioma_normalizado CHECK (idioma <> '' AND idioma = btrim(idioma))
);

-- ---------------------------------------------------------------------------- --
-- Índices para agrupar por valor y por fecha dentro de una captura             --
-- ---------------------------------------------------------------------------- --

CREATE INDEX IF NOT EXISTS juegos_fecha_idx ON catalogo_steam.juegos (fecha_captura, fecha_lanzamiento);
CREATE INDEX IF NOT EXISTS generos_genero_idx ON catalogo_steam.generos (fecha_captura, genero);
CREATE INDEX IF NOT EXISTS categorias_categoria_idx ON catalogo_steam.categorias (fecha_captura, categoria);
CREATE INDEX IF NOT EXISTS etiquetas_etiqueta_idx ON catalogo_steam.etiquetas (fecha_captura, etiqueta);
CREATE INDEX IF NOT EXISTS idiomas_idioma_idx ON catalogo_steam.idiomas (fecha_captura, idioma);

-- ---------------------------------------------------------------------------- --
-- Descripción de tablas y columnas                                             --
-- ---------------------------------------------------------------------------- --

COMMENT ON TABLE catalogo_steam.juegos IS
    'Un juego de Steam en una captura, con alguna de sus fechas entre 2020 y 2025. Géneros, categorías, etiquetas e idiomas están en sus tablas hijas.';
COMMENT ON TABLE catalogo_steam.excluidos IS
    'Juego apartado en la preparación de una captura, con el motivo y la regla concreta. No está en juegos en esa captura.';
COMMENT ON TABLE catalogo_steam.generos IS
    'Género oficial de un juego en una captura. Un juego tiene varios géneros, sin repetir.';
COMMENT ON TABLE catalogo_steam.categorias IS
    'Característica de un juego en una captura (Single-player, Multi-player, Co-op...). Un juego tiene varias, sin repetir.';
COMMENT ON TABLE catalogo_steam.etiquetas IS
    'Etiqueta de la tienda votada por la comunidad, de un juego en una captura. Un juego tiene hasta 20, sin repetir.';
COMMENT ON TABLE catalogo_steam.idiomas IS
    'Idioma en el que están los textos de un juego en una captura, con si también está doblado a ese idioma. Sin filas si el juego declara 100 idiomas o más.';

COMMENT ON COLUMN catalogo_steam.juegos.appid IS
    'Identificador del juego en Steam.';
COMMENT ON COLUMN catalogo_steam.juegos.fecha_captura IS
    'Fecha de la carpeta de la captura (data/raw/<fecha>/). Distingue el mismo juego en capturas distintas.';
COMMENT ON COLUMN catalogo_steam.juegos.fecha_lanzamiento IS
    'Primera de sus cuatro fechas (tienda, Steam, original o salida del acceso anticipado) que cae entre 2020 y 2025.';
COMMENT ON COLUMN catalogo_steam.juegos.precio_base_centimos IS
    'Precio sin descuento en la tienda de España, en céntimos de euro. 0 si es gratis. NULL si no se puede comprar suelto.';
COMMENT ON COLUMN catalogo_steam.juegos.archivo_origen IS
    'Ruta relativa al proyecto del archivo RAW, con la carpeta de la captura (data/raw/2026-11-18/juegos_fichas.jsonl).';
COMMENT ON COLUMN catalogo_steam.juegos.registro_origen IS
    'Línea del juego en archivo_origen, contada desde 0.';
COMMENT ON COLUMN catalogo_steam.excluidos.motivo IS
    'Motivo de la exclusión: fuera_periodo, no_es_juego o precio_anomalo.';
COMMENT ON COLUMN catalogo_steam.excluidos.detalle IS
    'Regla concreta que excluyó el juego.';
COMMENT ON COLUMN catalogo_steam.excluidos.archivo_origen IS
    'Ruta relativa al proyecto del archivo RAW, con la carpeta de la captura.';
COMMENT ON COLUMN catalogo_steam.excluidos.registro_origen IS
    'Línea del juego en archivo_origen, contada desde 0.';
COMMENT ON COLUMN catalogo_steam.idiomas.audio IS
    'TRUE si el juego también está doblado a ese idioma.';

COMMIT;
