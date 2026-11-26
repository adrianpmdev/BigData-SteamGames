"""
Valida las tablas preparadas de data/processed/<fecha>/ contra el diseño de
docs/2_preparacion.md y muestra cada control con su resultado.

Controles
---------
1. Columnas y tipos: cada tabla tiene las columnas y los tipos del diseño.
2. Obligatorios: las columnas obligatorias no tienen nulos.
3. Claves: la clave de cada tabla (con fecha_captura) no se repite.
4. Relaciones: todo appid + fecha_captura de las tablas hijas está en juegos y ningún
   excluido está en juegos.
5. Rangos: fechas dentro de 2020-2025, reseñas y precio no negativos.
6. Categorías: motivos de exclusión conocidos, valores de texto limpios (sin espacios
   sobrantes, vacíos ni restos de HTML) y nombres sin espacios sobrantes ni vacíos.
7. Procedencia: fecha_captura es la fecha de la carpeta en todas las tablas, archivo_origen
   apunta al archivo RAW usado, registro_origen no se repite y en esa línea del archivo
   está el mismo appid.
8. Balance: preparados + excluidos = registros de juegos_fichas.jsonl.

Argumentos
----------
    --fecha   Carpeta de la captura en data/raw/ y data/processed/, con formato AAAA-MM-DD.
              Por defecto, 2026-11-18.

Uso
---
    python scripts/4_validacion.py --fecha 2026-11-18

@author adrianpmdev
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
FORMATO_CARPETA_CAPTURA = "%Y-%m-%d"
ARCHIVO_FICHAS = "juegos_fichas.jsonl"
EXTENSION_TABLAS = ".parquet"

INICIO_PERIODO = pd.Timestamp("2020-01-01")
FIN_PERIODO = pd.Timestamp("2025-12-31")

# Diseño de la Tarea 3.1: tabla -> {columna: tipo de pandas}.
DISENO = {
    "juegos": {"appid": "int64", "fecha_captura": "datetime64[ms]", "nombre": "str",
               "fecha_lanzamiento": "datetime64[ms]", "resenas_positivas": "int64",
               "resenas_negativas": "int64", "precio_base_centimos": "Int64",
               "archivo_origen": "str", "registro_origen": "int64"},
    "generos": {"appid": "int64", "fecha_captura": "datetime64[ms]", "genero": "str"},
    "categorias": {"appid": "int64", "fecha_captura": "datetime64[ms]", "categoria": "str"},
    "etiquetas": {"appid": "int64", "fecha_captura": "datetime64[ms]", "etiqueta": "str"},
    "idiomas": {"appid": "int64", "fecha_captura": "datetime64[ms]", "idioma": "str", "audio": "bool"},
    "excluidos": {"appid": "int64", "fecha_captura": "datetime64[ms]", "nombre": "str", "motivo": "str",
                  "detalle": "str", "archivo_origen": "str", "registro_origen": "int64"},
}
TABLAS_CON_PROCEDENCIA = ("juegos", "excluidos")
COLUMNAS_OPCIONALES = {("juegos", "precio_base_centimos")}
CLAVE_JUEGO = ["appid", "fecha_captura"]
CLAVES = {"juegos": CLAVE_JUEGO, "generos": [*CLAVE_JUEGO, "genero"],
          "categorias": [*CLAVE_JUEGO, "categoria"], "etiquetas": [*CLAVE_JUEGO, "etiqueta"],
          "idiomas": [*CLAVE_JUEGO, "idioma"], "excluidos": CLAVE_JUEGO}
TABLAS_HIJAS = ("generos", "categorias", "etiquetas", "idiomas")
MOTIVOS_EXCLUSION = {"fuera_periodo", "no_es_juego", "precio_anomalo"}
PATRON_HTML = r"[<>*]"

ANCHO_TITULO = 70


# =========================================================================== #
# FUNCIONES                                                                   #
# =========================================================================== #

# --------------------------------------------------------------------------- #
# Lectura y consola                                                           #
# --------------------------------------------------------------------------- #

def leer_appids_por_linea(ruta: Path) -> pd.Series:
    """
    Lee el appid de cada registro válido de un JSONL con el mismo criterio que la
    transformación (se apartan las líneas vacías y las que no son un objeto JSON).

    Parámetros
    ----------
    ruta : archivo JSONL.

    Devuelve
    --------
    appid por línea del archivo (índice contado desde 0), solo de las líneas válidas.
    """
    appids = {}
    with ruta.open(encoding="utf-8") as archivo:
        for numero_linea, linea in enumerate(archivo):
            try:
                registro = json.loads(linea.strip("\x00 \t\r\n"))
            except ValueError:
                continue
            if isinstance(registro, dict):
                appids[numero_linea] = registro.get("appid")
    return pd.Series(appids, dtype="Int64")


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
# Controles                                                                   #
# --------------------------------------------------------------------------- #

def controlar_estructura(tablas: dict[str, pd.DataFrame]) -> list[tuple[str, str, int]]:
    """
    Controla columnas, tipos, obligatorios y claves de cada tabla (controles 1-3).

    Parámetros
    ----------
    tablas : tablas leídas de data/processed/<fecha>/.

    Devuelve
    --------
    (tabla, control, casos que lo incumplen) por control.
    """
    controles = []
    for nombre, columnas in DISENO.items():
        tabla = tablas[nombre]
        tipos = {columna: str(tipo) for columna, tipo in tabla.dtypes.items()}
        controles.append((nombre, "columnas y tipos del diseño",
                          sum(tipos.get(columna) != tipo for columna, tipo in columnas.items())
                          + len(set(tipos) - set(columnas))))
        obligatorias = [columna for columna in columnas if (nombre, columna) not in COLUMNAS_OPCIONALES]
        controles.append((nombre, "obligatorios sin nulos", int(tabla[obligatorias].isna().sum().sum())))
        controles.append((nombre, f"clave ({', '.join(CLAVES[nombre])}) sin repetir",
                          int(tabla.duplicated(CLAVES[nombre]).sum())))
    return controles


def esta_en_juegos(tabla: pd.DataFrame, juegos: pd.DataFrame) -> pd.Series:
    """
    Indica qué filas de una tabla tienen su appid + fecha_captura en juegos.

    Parámetros
    ----------
    tabla  : tabla con appid y fecha_captura.
    juegos : tabla juegos.

    Devuelve
    --------
    True en las filas cuyo juego está en juegos.
    """
    return pd.Series(pd.MultiIndex.from_frame(tabla[CLAVE_JUEGO]).isin(
        pd.MultiIndex.from_frame(juegos[CLAVE_JUEGO])), index=tabla.index)


def controlar_contenido(tablas: dict[str, pd.DataFrame], fecha_captura: pd.Timestamp, archivo_origen: str,
                        appids_raw: pd.Series) -> list[tuple[str, str, int]]:
    """
    Controla relaciones, rangos, categorías, procedencia y balance (controles 4-8).

    Parámetros
    ----------
    tablas         : tablas leídas de data/processed/<fecha>/.
    fecha_captura  : fecha de la carpeta de la captura.
    archivo_origen : ruta relativa del archivo RAW usado.
    appids_raw     : appid por línea de ARCHIVO_FICHAS.

    Devuelve
    --------
    (tabla, control, casos que lo incumplen) por control.
    """
    juegos, excluidos = tablas["juegos"], tablas["excluidos"]
    controles = [(nombre, "appid + fecha_captura existe en juegos",
                  int((~esta_en_juegos(tablas[nombre], juegos)).sum())) for nombre in TABLAS_HIJAS]
    controles += [
        ("excluidos", "ningún excluido está en juegos", int(esta_en_juegos(excluidos, juegos).sum())),
        ("juegos", "fecha entre 01/01/2020 y 31/12/2025",
         int((~juegos["fecha_lanzamiento"].between(INICIO_PERIODO, FIN_PERIODO)).sum())),
        ("juegos", "reseñas no negativas", int((juegos[["resenas_positivas", "resenas_negativas"]] < 0).any(axis=1).sum())),
        ("juegos", "precio no negativo", int((juegos["precio_base_centimos"] < 0).sum())),
        ("excluidos", "motivo conocido", int((~excluidos["motivo"].isin(MOTIVOS_EXCLUSION)).sum())),
    ]
    for nombre in TABLAS_HIJAS:
        valores = tablas[nombre][CLAVES[nombre][-1]]
        sucios = valores.ne(valores.str.strip()) | valores.eq("") | valores.str.contains(PATRON_HTML)
        controles.append((nombre, "valores limpios (sin espacios, vacíos ni HTML)", int(sucios.sum())))
    for nombre in TABLAS_CON_PROCEDENCIA:
        nombres = tablas[nombre]["nombre"]
        controles.append((nombre, "nombre sin espacios sobrantes ni vacío",
                          int((nombres.ne(nombres.str.strip()) | nombres.eq("")).sum())))
    controles += [(nombre, f"fecha_captura = {fecha_captura:%Y-%m-%d}",
                   int(tablas[nombre]["fecha_captura"].ne(fecha_captura).sum())) for nombre in DISENO]
    for nombre in TABLAS_CON_PROCEDENCIA:
        tabla = tablas[nombre]
        appid_en_linea = tabla["registro_origen"].map(appids_raw)
        controles += [(nombre, "archivo_origen es el archivo RAW usado", int(tabla["archivo_origen"].ne(archivo_origen).sum())),
                      (nombre, "registro_origen tiene el mismo appid en el RAW", int(appid_en_linea.ne(tabla["appid"]).fillna(True).sum()))]
    registros = pd.concat([tablas[nombre][["archivo_origen", "registro_origen"]] for nombre in TABLAS_CON_PROCEDENCIA])
    controles += [("juegos + excluidos", "registro_origen sin repetir", int(registros.duplicated().sum())),
                  ("juegos + excluidos", f"suman los {formatear_numero(len(appids_raw))} registros RAW",
                   abs(len(juegos) + len(excluidos) - len(appids_raw)))]
    return controles


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
    parser = argparse.ArgumentParser(description="Validación de las tablas preparadas de juegos de Steam.")
    parser.add_argument("--fecha", default=FECHA_CAPTURA_POR_DEFECTO,
                        help=f"Carpeta de la captura (por defecto, {FECHA_CAPTURA_POR_DEFECTO}).")
    return parser.parse_args()


# =========================================================================== #
# MAIN                                                                        #
# =========================================================================== #

def main() -> None:
    """Lee las tablas preparadas, aplica los controles y muestra su resultado."""
    args = parsear_argumentos()
    dir_tablas = DIR_PROCESSED / args.fecha
    dir_captura = DIR_RAW / args.fecha
    faltan = [nombre for nombre in DISENO if not (dir_tablas / f"{nombre}{EXTENSION_TABLAS}").is_file()]
    if faltan or not (dir_captura / ARCHIVO_FICHAS).is_file():
        raise SystemExit(f"Faltan archivos: {faltan or ARCHIVO_FICHAS}. Ejecuta antes 3_transformacion.py.")
    try:
        fecha_captura = pd.to_datetime(args.fecha, format=FORMATO_CARPETA_CAPTURA)
    except ValueError:
        raise SystemExit(f"La carpeta de la captura ({args.fecha}) no es una fecha AAAA-MM-DD.") from None

    # Lectura de las tablas preparadas y del recuento de la captura RAW.
    tablas = {nombre: pd.read_parquet(dir_tablas / f"{nombre}{EXTENSION_TABLAS}") for nombre in DISENO}
    appids_raw = leer_appids_por_linea(dir_captura / ARCHIVO_FICHAS)
    archivo_origen = (dir_captura / ARCHIVO_FICHAS).relative_to(RAIZ).as_posix()

    # Controles 1-8.
    controles = controlar_estructura(tablas) + controlar_contenido(tablas, fecha_captura, archivo_origen, appids_raw)

    # Resultado: un control por línea y resumen final.
    mostrar_titulo(f"CONTROLES ({dir_tablas.relative_to(RAIZ).as_posix()})")
    for tabla, control, incumplen in controles:
        estado = "OK   " if incumplen == 0 else "FALLO"
        print(f"  {estado} {tabla:20} {control:50} {formatear_numero(incumplen):>8}")
    fallos = sum(incumplen > 0 for _, _, incumplen in controles)
    print(f"\n  {len(controles) - fallos} de {len(controles)} controles correctos.")
    if fallos:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
