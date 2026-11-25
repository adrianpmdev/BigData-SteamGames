"""
Transforma la captura RAW de data/raw/<fecha>/ en las tablas preparadas del diseño de
docs/2_preparacion.md y las guarda en data/processed/<fecha>/. Se detiene si a la captura
le falta alguna columna de las reglas o si alguna fecha no se puede convertir.

Reglas (en orden, un juego excluido cuenta solo en la primera regla que cumple)
------
1. Ninguna de sus cuatro fechas cae en 2020-2025              -> excluir (fuera_periodo).
2. Herramienta, servidor, artbook, banda sonora o demo         -> excluir (no_es_juego).
3. Precio anómalo (otra moneda, gratis con precio o de pago sin
   precio) con 10 reseñas o menos                              -> excluir (precio_anomalo).
4. De pago sin precio con género Free To Play                  -> excluir (precio_anomalo).
5. Gratis sin precio, o gratis con precio y Free To Play       -> precio 0.
6. De pago sin precio o precio en USD                          -> precio nulo.
7. Fechas: se convierten y se asigna la primera dentro del periodo.
8. Idiomas: una fila por idioma, con si tiene audio (*). Sin filas si declara 100 o más.
9. Géneros, categorías y etiquetas: una fila por valor en su tabla.
Todas las tablas se ordenan por la fecha del juego (y appid).

Archivos generados (data/processed/<fecha>/)
------------------
    juegos.parquet       Un juego por fila (clave appid), con captura_origen.
    generos.parquet      Un género de un juego por fila (clave appid + genero).
    categorias.parquet   Una categoría de un juego por fila (clave appid + categoria).
    etiquetas.parquet    Una etiqueta de un juego por fila (clave appid + etiqueta).
    idiomas.parquet      Un idioma de un juego por fila, con audio (clave appid + idioma).
    excluidos.parquet    Juegos excluidos, con motivo, detalle de la regla y captura_origen.
Después de guardarlas, se vuelven a leer y se comprueba que conservan contenido y tipos.

Argumentos
----------
    --fecha   Carpeta de la captura en data/raw/. Por defecto, 2026-11-18.

Uso
---
    python scripts/3_transformacion.py --fecha 2026-11-18
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


# =========================================================================== #
# VARIABLES Y CONSTANTES                                                      #
# =========================================================================== #

RAIZ = Path(__file__).resolve().parent.parent
DIR_RAW = RAIZ / "data" / "raw"
DIR_PROCESSED = RAIZ / "data" / "processed"
FECHA_CAPTURA_POR_DEFECTO = "2026-11-18"
ARCHIVO_FICHAS = "juegos_fichas.jsonl"

INICIO_PERIODO = pd.Timestamp("2020-01-01")
FIN_PERIODO = pd.Timestamp("2025-12-31")
# Formatos de fecha de la ficha de la tienda, según la región ("19 Nov, 2020" o "Nov 19, 2020").
FORMATOS_FECHA_TIENDA = ("%d %b, %Y", "%b %d, %Y")
COLUMNAS_FECHA_STEAM = ("fecha_lanzamiento_steam", "fecha_lanzamiento_original",
                        "fecha_salida_acceso_anticipado")
# Columnas de juegos_fichas.jsonl que usan las reglas.
COLUMNAS_NECESARIAS = ("appid", "nombre", "fecha_lanzamiento", *COLUMNAS_FECHA_STEAM, "generos",
                       "categorias", "etiquetas", "es_gratis", "precio_base_centimos", "moneda",
                       "idiomas", "resenas_positivas", "resenas_negativas")

# Fichas de tipo juego que no son juegos. "Editor", "Server" o "Launcher" no se usan:
# dan falsos positivos con juegos reales (Server is Down, Video Editor Tycoon...).
CATEGORIAS_SIN_MODO_DE_JUEGO = {"Family Sharing"}
PATRON_HERRAMIENTA = r"(?i)\b(?:dedicated server|mod tools?|sdk|artbook|art book|soundtrack)\b"
PATRON_DEMO = r"(?i)\bdemo\b"

GENERO_GRATIS = "Free To Play"
MONEDA = "EUR"
MAX_RESENAS_PRECIO_ANOMALO = 10   # con más reseñas, un precio anómalo se corrige en vez de excluir

# Idiomas: "English<strong>*</strong>, French<br><strong>*</strong>languages with full audio support".
SEPARADOR_NOTA_IDIOMAS = "<br>"
MARCA_AUDIO = "<strong>*</strong>"
# A partir de aquí el juego ha marcado (casi) todos los idiomas de Steam: no mide la traducción.
MIN_IDIOMAS_NO_FIABLE = 100

# Tabla de salida -> (columna de juegos_fichas, columna del valor).
TABLAS_LISTA = {"generos": ("generos", "genero"),
                "categorias": ("categorias", "categoria"),
                "etiquetas": ("etiquetas", "etiqueta")}
COLUMNAS_JUEGOS = ["appid", "nombre", "fecha_lanzamiento", "resenas_positivas", "resenas_negativas",
                   "precio_base_centimos", "captura_origen"]
# Tabla hija -> columna del valor (junto con appid forma su clave).
CLAVES_TABLAS_HIJAS = {"generos": "genero", "categorias": "categoria", "etiquetas": "etiqueta",
                       "idiomas": "idioma"}
FORMATO_FECHA_SALIDA = "%d/%m/%Y"   # solo para mostrar por pantalla
EXTENSION_TABLAS = ".parquet"
ANCHO_TITULO = 70


# =========================================================================== #
# FUNCIONES                                                                   #
# =========================================================================== #

# --------------------------------------------------------------------------- #
# Lectura y consola                                                           #
# --------------------------------------------------------------------------- #

def leer_jsonl(ruta: Path) -> pd.DataFrame:
    """
    Lee un archivo JSONL en un DataFrame, tolerando las líneas dañadas.

    Se quitan los bytes nulos y espacios de cada línea (una escritura interrumpida puede
    dejarlos). Las líneas vacías o que no son un objeto JSON se ignoran.

    Parámetros
    ----------
    ruta : archivo JSONL.

    Devuelve
    --------
    Un registro por línea válida.
    """
    registros = []
    with ruta.open(encoding="utf-8") as archivo:
        for linea in archivo:
            try:
                registro = json.loads(linea.strip("\x00 \t\r\n"))
            except ValueError:
                continue
            if isinstance(registro, dict):
                registros.append(registro)
    return pd.DataFrame.from_records(registros)


def mostrar_titulo(titulo: str) -> None:
    """
    Escribe el título de una sección entre dos líneas de =.

    Parámetros
    ----------
    titulo : texto del título.
    """
    print(f"\n{'=' * ANCHO_TITULO}\n{titulo}\n{'=' * ANCHO_TITULO}")


def formatear_numero(numero: int) -> str:
    """
    Formatea un entero con punto como separador de miles (201.397).

    Parámetros
    ----------
    numero : entero a formatear.

    Devuelve
    --------
    Número como texto.
    """
    return f"{numero:,}".replace(",", ".")


# --------------------------------------------------------------------------- #
# Reglas                                                                      #
# --------------------------------------------------------------------------- #

def asignar_fecha(fichas: pd.DataFrame) -> pd.Series:
    """
    Convierte las cuatro fechas del juego y asigna la primera que cae en el periodo.

    Parámetros
    ----------
    fichas : contenido de ARCHIVO_FICHAS.

    Devuelve
    --------
    Fecha asignada (NaT si ninguna cae en el periodo).

    Lanza
    -----
    ValueError si alguna fecha con texto no se puede convertir (formato desconocido):
    sin este control, esos juegos se excluirían como fuera_periodo sin serlo.
    """
    fecha_tienda = pd.Series(pd.NaT, index=fichas.index)
    for formato in FORMATOS_FECHA_TIENDA:
        fecha_tienda = fecha_tienda.fillna(pd.to_datetime(fichas["fecha_lanzamiento"], format=formato,
                                                          errors="coerce"))
    fechas = pd.concat([fecha_tienda] + [pd.to_datetime(fichas[columna], errors="coerce")
                                         for columna in COLUMNAS_FECHA_STEAM], axis=1)
    fechas.columns = ["fecha_lanzamiento", *COLUMNAS_FECHA_STEAM]
    con_texto = fichas[list(fechas.columns)].apply(lambda columna: columna.fillna("").astype(str).str.strip().ne(""))
    sin_convertir = (con_texto & fechas.isna()).sum()
    if sin_convertir.any():
        raise ValueError(f"Fechas que no se pueden convertir: {sin_convertir[sin_convertir > 0].to_dict()}.")
    return fechas.where(fechas.apply(lambda fecha: fecha.between(INICIO_PERIODO, FIN_PERIODO))).min(axis=1)


def decidir_exclusiones(fichas: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica las reglas de exclusión en orden y anota el motivo y la regla de cada juego.

    Parámetros
    ----------
    fichas : contenido de ARCHIVO_FICHAS, con fecha_asignada.

    Devuelve
    --------
    Columnas motivo y detalle (nulas si el juego no se excluye).
    """
    precio = fichas["precio_base_centimos"]
    pocas_resenas = (fichas["resenas_positivas"] + fichas["resenas_negativas"]) <= MAX_RESENAS_PRECIO_ANOMALO
    sin_genero = fichas["generos"].map(lambda generos: not generos)
    sin_modo_de_juego = fichas["categorias"].map(lambda categorias: set(categorias) <= CATEGORIAS_SIN_MODO_DE_JUEGO)
    de_pago_sin_precio = ~fichas["es_gratis"] & precio.isna()
    gratis_con_precio = fichas["es_gratis"] & precio.notna()
    en_otra_moneda = fichas["moneda"].notna() & fichas["moneda"].ne(MONEDA)

    reglas = [
        ("fuera_periodo", "ninguna de sus cuatro fechas cae en 2020-2025", fichas["fecha_asignada"].isna()),
        ("no_es_juego", "herramienta sin género ni modo de juego", sin_genero & sin_modo_de_juego),
        ("no_es_juego", "herramienta por el nombre", fichas["nombre"].str.contains(PATRON_HERRAMIENTA, na=False)),
        ("no_es_juego", "demo por el nombre", fichas["nombre"].str.contains(PATRON_DEMO, na=False)),
        ("precio_anomalo", f"precio en otra moneda y {MAX_RESENAS_PRECIO_ANOMALO} reseñas o menos",
         en_otra_moneda & pocas_resenas),
        ("precio_anomalo", f"gratis con precio y {MAX_RESENAS_PRECIO_ANOMALO} reseñas o menos",
         gratis_con_precio & pocas_resenas),
        ("precio_anomalo", f"de pago sin precio y {MAX_RESENAS_PRECIO_ANOMALO} reseñas o menos",
         de_pago_sin_precio & pocas_resenas),
        ("precio_anomalo", f"de pago sin precio con género {GENERO_GRATIS}",
         de_pago_sin_precio & fichas["generos"].map(lambda generos: GENERO_GRATIS in generos)),
    ]
    exclusiones = pd.DataFrame({"motivo": pd.NA, "detalle": pd.NA}, index=fichas.index, dtype="object")
    for motivo, detalle, cumple in reglas:
        libres = cumple & exclusiones["motivo"].isna()
        exclusiones.loc[libres, ["motivo", "detalle"]] = [motivo, detalle]
    return exclusiones


def corregir_precio(juegos: pd.DataFrame) -> pd.Series:
    """
    Corrige el precio de los juegos que se mantienen (reglas 5 y 6).

    Parámetros
    ----------
    juegos : juegos no excluidos, con las columnas de la ficha.

    Devuelve
    --------
    Precio en céntimos de euro, nulo si no hay un precio de compra válido.
    """
    precio = juegos["precio_base_centimos"].astype("Int64")
    gratis_free_to_play = juegos["es_gratis"] & juegos["generos"].map(lambda generos: GENERO_GRATIS in generos)
    precio[juegos["es_gratis"] & precio.isna() | gratis_free_to_play] = 0
    precio[juegos["moneda"].notna() & juegos["moneda"].ne(MONEDA)] = pd.NA
    return precio


def separar_idiomas(texto: object) -> list[tuple[str, bool]]:
    """
    Separa el texto de idiomas en una lista de idiomas, indicando cuáles tienen audio.

    Parámetros
    ----------
    texto : campo idiomas de la ficha (texto con HTML) o nulo.

    Devuelve
    --------
    (idioma, tiene audio) por idioma. Vacía si no hay dato o si el juego declara
    MIN_IDIOMAS_NO_FIABLE o más.
    """
    if not isinstance(texto, str):
        return []
    idiomas = [idioma.strip() for idioma in texto.split(SEPARADOR_NOTA_IDIOMAS)[0].split(",") if idioma.strip()]
    if len(idiomas) >= MIN_IDIOMAS_NO_FIABLE:
        return []
    return [(idioma.removesuffix(MARCA_AUDIO).strip(), idioma.endswith(MARCA_AUDIO)) for idioma in idiomas]


# --------------------------------------------------------------------------- #
# Tablas de salida                                                            #
# --------------------------------------------------------------------------- #

def construir_juegos(juegos: pd.DataFrame, captura_origen: str) -> pd.DataFrame:
    """
    Construye la tabla juegos con las columnas y tipos del diseño.

    Parámetros
    ----------
    juegos         : juegos no excluidos, con fecha_asignada.
    captura_origen : ruta relativa de la captura RAW.

    Devuelve
    --------
    Tabla juegos, ordenada por fecha y appid.
    """
    return juegos.assign(
        fecha_lanzamiento=juegos["fecha_asignada"].astype("datetime64[ms]"),
        precio_base_centimos=corregir_precio(juegos),
        captura_origen=captura_origen,
    )[COLUMNAS_JUEGOS].sort_values(["fecha_lanzamiento", "appid"])


def desplegar_lista(juegos: pd.DataFrame, columna: str, nombre_valor: str) -> pd.DataFrame:
    """
    Despliega una columna de listas en una fila por valor y juego.

    Parámetros
    ----------
    juegos       : juegos no excluidos.
    columna      : columna de listas de la ficha.
    nombre_valor : nombre de la columna del valor en la tabla de salida.

    Devuelve
    --------
    Tabla (appid, valor) sin vacíos ni repetidos. Las listas vacías no generan filas.
    """
    filas = juegos[["appid", columna]].explode(columna).rename(columns={columna: nombre_valor})
    filas[nombre_valor] = filas[nombre_valor].str.strip()
    filas = filas[filas[nombre_valor].fillna("").ne("")]
    return filas.drop_duplicates()


def desplegar_idiomas(juegos: pd.DataFrame) -> pd.DataFrame:
    """
    Separa el texto de idiomas en una fila por idioma y juego, con si tiene audio.

    Parámetros
    ----------
    juegos : juegos no excluidos.

    Devuelve
    --------
    Tabla (appid, idioma, audio) sin repetidos. Los juegos sin dato fiable no generan filas.
    """
    filas = juegos[["appid"]].assign(par=juegos["idiomas"].map(separar_idiomas)).explode("par").dropna()
    filas["idioma"], filas["audio"] = filas["par"].str[0], filas["par"].str[1].astype(bool)
    return filas[["appid", "idioma", "audio"]].drop_duplicates(["appid", "idioma"])


def ordenar_como_juegos(tabla: pd.DataFrame, juegos: pd.DataFrame, nombre_valor: str) -> pd.DataFrame:
    """
    Ordena una tabla hija en el mismo orden que juegos (fecha y appid) y por su valor.

    Parámetros
    ----------
    tabla        : tabla hija con appid.
    juegos       : tabla juegos ya ordenada.
    nombre_valor : columna del valor de la tabla hija.

    Devuelve
    --------
    Tabla ordenada.
    """
    posicion = pd.Series(range(len(juegos)), index=juegos["appid"])
    return tabla.assign(posicion=tabla["appid"].map(posicion)).sort_values(
        ["posicion", nombre_valor]).drop(columns="posicion")


def guardar_tablas(tablas: dict[str, pd.DataFrame], dir_salida: Path) -> None:
    """
    Guarda cada tabla en Parquet, la vuelve a leer y comprueba que no ha cambiado.

    Los textos se guardan con el tipo str de pandas para que la tabla leída sea idéntica
    a la guardada.

    Parámetros
    ----------
    tablas     : tablas de salida por nombre.
    dir_salida : carpeta de la captura en data/processed/.

    Lanza
    -----
    AssertionError si una tabla leída no coincide en contenido o tipos con la guardada.
    """
    dir_salida.mkdir(parents=True, exist_ok=True)
    for nombre, tabla in tablas.items():
        tabla = tabla.reset_index(drop=True)
        textos = tabla.select_dtypes(include=["object", "str"]).columns
        tabla[textos] = tabla[textos].astype("str")
        ruta = dir_salida / f"{nombre}{EXTENSION_TABLAS}"
        tabla.to_parquet(ruta, index=False)
        pd.testing.assert_frame_equal(pd.read_parquet(ruta), tabla, obj=nombre)


# --------------------------------------------------------------------------- #
# Revisión de resultados                                                      #
# --------------------------------------------------------------------------- #

def mostrar_antes_despues(fichas: pd.DataFrame, juegos: pd.DataFrame, idiomas: pd.DataFrame) -> None:
    """
    Muestra fecha, precio e idiomas antes y después de transformar en dos juegos de
    ejemplo: el primer juego gratis y el primero con 3 idiomas o más, alguno con audio.

    Parámetros
    ----------
    fichas  : registros originales de ARCHIVO_FICHAS.
    juegos  : tabla juegos preparada.
    idiomas : tabla idiomas preparada.
    """
    preparados = juegos.set_index("appid")
    originales = fichas.set_index("appid").loc[preparados.index]
    ejemplos = [originales.index[originales["es_gratis"]][0],
                originales.index[originales["idiomas"].fillna("").str.contains(MARCA_AUDIO, regex=False)
                                 & originales["idiomas"].fillna("").str.count(",").ge(2)][0]]
    for appid in ejemplos:
        original, preparado = originales.loc[appid], preparados.loc[appid]
        print(f"\n--- {appid} {original['nombre']}")
        print(f"  fecha:   {original['fecha_lanzamiento']!r:45} -> "
              f"{preparado['fecha_lanzamiento'].strftime(FORMATO_FECHA_SALIDA)}")
        precio_original = "(vacío)" if pd.isna(original["precio_base_centimos"]) else int(original["precio_base_centimos"])
        print(f"  precio:  {precio_original!s:45} -> {preparado['precio_base_centimos']}")
        suyos = idiomas[idiomas["appid"] == appid]
        print(f"  idiomas: {str(original['idiomas'])[:43]!r:45} -> {len(suyos)} idiomas "
              f"({int(suyos['audio'].sum())} con audio): {', '.join(suyos['idioma'])}")


# --------------------------------------------------------------------------- #
# Argumentos de la línea de comandos                                          #
# --------------------------------------------------------------------------- #

def parsear_argumentos() -> argparse.Namespace:
    """
    Lee los argumentos de la línea de comandos.

    Devuelve
    --------
    Argumentos: fecha.
    """
    parser = argparse.ArgumentParser(description="Transformación de la captura RAW de juegos de Steam.")
    parser.add_argument("--fecha", default=FECHA_CAPTURA_POR_DEFECTO,
                        help=f"Carpeta de la captura en data/raw/ (por defecto, {FECHA_CAPTURA_POR_DEFECTO}).")
    return parser.parse_args()


# =========================================================================== #
# MAIN                                                                        #
# =========================================================================== #

def main() -> None:
    """Aplica las reglas, construye las tablas y las guarda con un resumen."""
    args = parsear_argumentos()
    dir_captura = DIR_RAW / args.fecha
    if not (dir_captura / ARCHIVO_FICHAS).is_file():
        raise SystemExit(f"No existe {dir_captura / ARCHIVO_FICHAS}.")
    captura_origen = dir_captura.relative_to(RAIZ).as_posix()

    # Lectura de la captura RAW y comprobación de que trae las columnas que usan las reglas.
    fichas = leer_jsonl(dir_captura / ARCHIVO_FICHAS)
    faltan = [columna for columna in COLUMNAS_NECESARIAS if columna not in fichas.columns]
    if faltan:
        raise SystemExit(f"A {ARCHIVO_FICHAS} le faltan columnas: {', '.join(faltan)}.")

    # Reglas 1-4: fecha asignada y exclusiones con su motivo.
    fichas = fichas.assign(fecha_asignada=asignar_fecha(fichas))
    fichas = fichas.join(decidir_exclusiones(fichas))
    excluidos = fichas[fichas["motivo"].notna()]
    preparados = fichas[fichas["motivo"].isna()]

    # Reglas 5-9: tabla juegos (precio y fecha) y tablas hijas (listas e idiomas).
    juegos = construir_juegos(preparados, captura_origen)
    tablas = {"juegos": juegos}
    for nombre, (columna, nombre_valor) in TABLAS_LISTA.items():
        tablas[nombre] = desplegar_lista(preparados, columna, nombre_valor)
    tablas["idiomas"] = desplegar_idiomas(preparados)

    # Orden de las tablas hijas igual que juegos (por fecha).
    for nombre, nombre_valor in CLAVES_TABLAS_HIJAS.items():
        tablas[nombre] = ordenar_como_juegos(tablas[nombre], juegos, nombre_valor)

    # Tabla de excluidos con su motivo y procedencia.
    tablas["excluidos"] = excluidos.assign(captura_origen=captura_origen)[
        ["appid", "nombre", "motivo", "detalle", "captura_origen"]].sort_values("appid")

    # Guardado en Parquet y relectura para comprobar contenido y tipos.
    dir_salida = DIR_PROCESSED / args.fecha
    guardar_tablas(tablas, dir_salida)

    # Resumen: recuentos, nulos y filas por tabla.
    mostrar_titulo(f"RECUENTOS ({captura_origen} -> {dir_salida.relative_to(RAIZ).as_posix()})")
    print(f"  Registros originales  {formatear_numero(len(fichas)):>9}")
    print(f"  Preparados            {formatear_numero(len(preparados)):>9}")
    print(f"  Excluidos             {formatear_numero(len(excluidos)):>9}")
    for (motivo, detalle), cantidad in excluidos.groupby(["motivo", "detalle"]).size().items():
        print(f"    {motivo:15} {detalle:50} {formatear_numero(cantidad):>6}")
    sin_idiomas = int((~juegos["appid"].isin(tablas["idiomas"]["appid"])).sum())
    print(f"\n  Juegos sin precio: {formatear_numero(int(juegos['precio_base_centimos'].isna().sum()))}"
          f" | sin idiomas fiables: {formatear_numero(sin_idiomas)}")
    print("\n  Filas por tabla (unidad de observación):")
    for nombre, tabla in tablas.items():
        por_juego = (f"  ({len(tabla) / len(juegos):.1f} por juego)".replace(".", ",")
                     if nombre in CLAVES_TABLAS_HIJAS else "")
        print(f"    {nombre + EXTENSION_TABLAS:20} {formatear_numero(len(tabla)):>10}{por_juego}")

    # Revisión: valores de dos juegos antes y después de transformar.
    mostrar_titulo("ANTES Y DESPUÉS")
    mostrar_antes_despues(fichas, juegos, tablas["idiomas"])


if __name__ == "__main__":
    main()
