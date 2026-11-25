"""
Valida las tablas preparadas de data/processed/<fecha>/ contra el diseño de
docs/2_preparacion.md y muestra cada control con su resultado.

Controles
---------
1. Columnas y tipos: cada tabla tiene las columnas y los tipos del diseño.
2. Obligatorios: las columnas obligatorias no tienen nulos.
3. Claves: la clave de cada tabla no se repite.
4. Relaciones: todo appid de las tablas hijas está en juegos y ningún excluido está en juegos.
5. Rangos: fechas dentro de 2020-2025, reseñas y precio no negativos.
6. Categorías: motivos de exclusión conocidos y valores de texto limpios (sin espacios
   sobrantes, vacíos ni restos de HTML).
7. Procedencia: captura_origen apunta a la captura usada.
8. Balance: preparados + excluidos = registros de juegos_fichas.jsonl.

Argumentos
----------
    --fecha   Carpeta de la captura en data/raw/ y data/processed/. Por defecto, 2026-11-18.

Uso
---
    python scripts/4_validacion.py --fecha 2026-11-18
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
EXTENSION_TABLAS = ".parquet"

INICIO_PERIODO = pd.Timestamp("2020-01-01")
FIN_PERIODO = pd.Timestamp("2025-12-31")

# Diseño de la Tarea 3.1: tabla -> {columna: tipo de pandas}.
DISENO = {
    "juegos": {"appid": "int64", "nombre": "str", "fecha_lanzamiento": "datetime64[ms]",
               "resenas_positivas": "int64", "resenas_negativas": "int64",
               "precio_base_centimos": "Int64", "captura_origen": "str"},
    "generos": {"appid": "int64", "genero": "str"},
    "categorias": {"appid": "int64", "categoria": "str"},
    "etiquetas": {"appid": "int64", "etiqueta": "str"},
    "idiomas": {"appid": "int64", "idioma": "str", "audio": "bool"},
    "excluidos": {"appid": "int64", "nombre": "str", "motivo": "str", "detalle": "str",
                  "captura_origen": "str"},
}
COLUMNAS_OPCIONALES = {("juegos", "precio_base_centimos")}
CLAVES = {"juegos": ["appid"], "generos": ["appid", "genero"], "categorias": ["appid", "categoria"],
          "etiquetas": ["appid", "etiqueta"], "idiomas": ["appid", "idioma"], "excluidos": ["appid"]}
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

def contar_registros_jsonl(ruta: Path) -> int:
    """
    Cuenta los registros válidos de un JSONL con el mismo criterio que la transformación
    (se ignoran bytes nulos, líneas vacías y líneas que no son un objeto JSON).

    Parámetros
    ----------
    ruta : archivo JSONL.

    Devuelve
    --------
    Número de registros válidos.
    """
    total = 0
    with ruta.open(encoding="utf-8") as archivo:
        for linea in archivo:
            try:
                total += isinstance(json.loads(linea.strip("\x00 \t\r\n")), dict)
            except ValueError:
                continue
    return total


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


def controlar_contenido(tablas: dict[str, pd.DataFrame], captura_origen: str,
                        registros_raw: int) -> list[tuple[str, str, int]]:
    """
    Controla relaciones, rangos, categorías, procedencia y balance (controles 4-8).

    Parámetros
    ----------
    tablas         : tablas leídas de data/processed/<fecha>/.
    captura_origen : ruta relativa de la captura RAW usada.
    registros_raw  : registros válidos de ARCHIVO_FICHAS.

    Devuelve
    --------
    (tabla, control, casos que lo incumplen) por control.
    """
    juegos, excluidos = tablas["juegos"], tablas["excluidos"]
    controles = [(nombre, "appid existe en juegos", int((~tablas[nombre]["appid"].isin(juegos["appid"])).sum()))
                 for nombre in TABLAS_HIJAS]
    controles += [
        ("excluidos", "ningún excluido está en juegos", int(excluidos["appid"].isin(juegos["appid"]).sum())),
        ("juegos", "fecha entre 01/01/2020 y 31/12/2025",
         int((~juegos["fecha_lanzamiento"].between(INICIO_PERIODO, FIN_PERIODO)).sum())),
        ("juegos", "reseñas no negativas", int((juegos[["resenas_positivas", "resenas_negativas"]] < 0).any(axis=1).sum())),
        ("juegos", "precio no negativo", int((juegos["precio_base_centimos"] < 0).sum())),
        ("excluidos", "motivo conocido", int((~excluidos["motivo"].isin(MOTIVOS_EXCLUSION)).sum())),
    ]
    for nombre in TABLAS_HIJAS:
        valores = tablas[nombre][CLAVES[nombre][1]]
        sucios = valores.ne(valores.str.strip()) | valores.eq("") | valores.str.contains(PATRON_HTML)
        controles.append((nombre, "valores limpios (sin espacios, vacíos ni HTML)", int(sucios.sum())))
    controles += [(nombre, f"captura_origen = {captura_origen}", int(tablas[nombre]["captura_origen"].ne(captura_origen).sum()))
                  for nombre in ("juegos", "excluidos")]
    controles.append(("juegos + excluidos", f"suman los {formatear_numero(registros_raw)} registros RAW",
                      abs(len(juegos) + len(excluidos) - registros_raw)))
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

    # Lectura de las tablas preparadas y del recuento de la captura RAW.
    tablas = {nombre: pd.read_parquet(dir_tablas / f"{nombre}{EXTENSION_TABLAS}") for nombre in DISENO}
    registros_raw = contar_registros_jsonl(dir_captura / ARCHIVO_FICHAS)
    captura_origen = dir_captura.relative_to(RAIZ).as_posix()

    # Controles 1-8.
    controles = controlar_estructura(tablas) + controlar_contenido(tablas, captura_origen, registros_raw)

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
