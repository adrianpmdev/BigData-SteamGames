"""
Lee las tablas preparadas de data/processed/<fecha>/, comprueba que tienen las columnas del
modelo de sql/esquema.sql y que no están vacías, y las exporta a CSV en el orden del modelo.

Controles
---------
1. Cada tabla tiene todas las columnas del modelo SQL.
2. Ninguna tabla está vacía.
Al final muestra las filas por tabla, la suma de reseñas positivas y los juegos sin precio.

Archivos generados (data/processed/<fecha>/csv/)
------------------
    juegos.csv, generos.csv, categorias.csv, etiquetas.csv, idiomas.csv, excluidos.csv
    Fechas en AAAA-MM-DD y precio vacío cuando es nulo.

Argumentos
----------
    --fecha   Carpeta de la captura en data/processed/. Por defecto, 2026-11-18.

Uso
---
    python scripts/5_preparar_carga.py --fecha 2026-11-18

@author adrianpmdev
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


# =========================================================================== #
# VARIABLES Y CONSTANTES                                                      #
# =========================================================================== #

RAIZ = Path(__file__).resolve().parent.parent
DIR_PROCESSED = RAIZ / "data" / "processed"
FECHA_CAPTURA_POR_DEFECTO = "2026-11-18"
CARPETA_CSV = "csv"
EXTENSION_TABLAS = ".parquet"
EXTENSION_CSV = ".csv"
FORMATO_FECHA_CSV = "%Y-%m-%d"

# Columnas de cada tabla en el orden de sql/esquema.sql.
MODELO = {
    "juegos": ["appid", "fecha_captura", "nombre", "fecha_lanzamiento", "resenas_positivas", "resenas_negativas", "precio_base_centimos", "archivo_origen", "registro_origen"],
    "generos": ["appid", "fecha_captura", "genero"],
    "categorias": ["appid", "fecha_captura", "categoria"],
    "etiquetas": ["appid", "fecha_captura", "etiqueta"],
    "idiomas": ["appid", "fecha_captura", "idioma", "audio"],
    "excluidos": ["appid", "fecha_captura", "nombre", "motivo", "detalle", "archivo_origen", "registro_origen"],
}

ANCHO_TITULO = 70


# =========================================================================== #
# FUNCIONES                                                                   #
# =========================================================================== #

# --------------------------------------------------------------------------- #
# Consola                                                                     #
# --------------------------------------------------------------------------- #

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
# Preparación de la carga                                                     #
# --------------------------------------------------------------------------- #

def leer_tabla(dir_tablas: Path, nombre: str) -> pd.DataFrame:
    """
    Lee una tabla preparada y comprueba que tiene las columnas del modelo y datos.

    Parámetros
    ----------
    dir_tablas : carpeta de la captura en data/processed/.
    nombre     : nombre de la tabla.

    Devuelve
    --------
    Tabla con solo las columnas del modelo, en su orden.

    Lanza
    -----
    SystemExit si falta el archivo, faltan columnas o la tabla está vacía.
    """
    ruta = dir_tablas / f"{nombre}{EXTENSION_TABLAS}"
    if not ruta.is_file():
        raise SystemExit(f"No existe {ruta}. Ejecuta antes 3_transformacion.py.")

    tabla = pd.read_parquet(ruta)
    faltan = [columna for columna in MODELO[nombre] if columna not in tabla.columns]
    if faltan:
        raise SystemExit(f"A {ruta.name} le faltan columnas del modelo: {', '.join(faltan)}. Vuelve a ejecutar 3_transformacion.py.")

    if tabla.empty:
        raise SystemExit(f"{ruta.name} no tiene filas para cargar.")

    return tabla[MODELO[nombre]]


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
    parser = argparse.ArgumentParser(description="Exporta las tablas preparadas a CSV para cargarlas en PostgreSQL.")
    parser.add_argument("--fecha", default=FECHA_CAPTURA_POR_DEFECTO, help=f"Carpeta de la captura en data/processed/ (por defecto, {FECHA_CAPTURA_POR_DEFECTO}).")

    return parser.parse_args()


# =========================================================================== #
# MAIN                                                                        #
# =========================================================================== #

def main() -> None:
    """Lee las tablas preparadas, las exporta a CSV y muestra los valores de control."""
    args = parsear_argumentos()
    dir_tablas = DIR_PROCESSED / args.fecha
    dir_csv = dir_tablas / CARPETA_CSV

    # Lectura de las tablas y comprobación de columnas y filas.
    tablas = {nombre: leer_tabla(dir_tablas, nombre) for nombre in MODELO}

    # Exportación a CSV con las columnas en el orden del modelo.
    dir_csv.mkdir(parents=True, exist_ok=True)
    for nombre, tabla in tablas.items():
        tabla.to_csv(dir_csv / f"{nombre}{EXTENSION_CSV}", index=False, date_format=FORMATO_FECHA_CSV, encoding="utf-8")

    # Valores de control: filas por tabla, suma de reseñas positivas y juegos sin precio.
    print(f"{'=' * ANCHO_TITULO}\nCSV DE CARGA ({dir_csv.relative_to(RAIZ).as_posix()})\n{'=' * ANCHO_TITULO}")
    for nombre, tabla in tablas.items():
        print(f"  {nombre + EXTENSION_CSV:20} {formatear_numero(len(tabla)):>10} filas")

    juegos = tablas["juegos"]
    print(f"\n  Suma de reseñas positivas: {formatear_numero(int(juegos['resenas_positivas'].sum()))}")
    print(f"  Juegos sin precio:         {formatear_numero(int(juegos['precio_base_centimos'].isna().sum()))}")


if __name__ == "__main__":
    main()
