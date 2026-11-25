"""
Diagnostica la captura RAW de data/raw/<fecha>/ con pandas antes de transformarla:
estructura, calidad, campos relevantes y cobertura temporal. Solo lee los archivos;
no modifica nada.

Comprobaciones
--------------
1. Estructura: filas, columnas, tipos y primeros registros de cada archivo.
2. Calidad: valores ausentes (null, lista vacía y texto vacío), filas repetidas,
   appid repetido y cuadre entre archivos (lista, periodo, fichas y descartados).
3. Campos relevantes de juegos_fichas.jsonl: géneros, categorías y etiquetas distintos
   (y variantes de un mismo valor), moneda, fichas que no son juegos, precio, reseñas
   y fechas.
4. Cobertura temporal: juegos por año y por mes con la fecha asignada (la primera de
   sus cuatro fechas que cae en el periodo), juegos fuera del periodo exacto y rango de
   fechas de petición.
5. Resumen: cifras de los posibles problemas para la tabla de docs/2_preparacion.md.

Argumentos
----------
    --fecha   Carpeta de la captura en data/raw/. Por defecto, 2026-11-18.

Uso
---
    python scripts/2_diagnostico.py --fecha 2026-11-18
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


# =========================================================================== #
# VARIABLES Y CONSTANTES                                                      #
# =========================================================================== #

DIR_RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
FECHA_CAPTURA_POR_DEFECTO = "2026-11-18"

ARCHIVO_LISTA_JUEGOS = "juegos_lista.jsonl"
ARCHIVO_PERIODO = "juegos_periodo.jsonl"
ARCHIVO_FICHAS = "juegos_fichas.jsonl"
ARCHIVO_DESCARTADOS = "juegos_descartados.jsonl"

CLAVE = "appid"
COLUMNAS_LISTA = ["generos", "categorias", "etiquetas"]

INICIO_PERIODO = pd.Timestamp("2020-01-01")
FIN_PERIODO = pd.Timestamp("2025-12-31")
# Formatos de fecha de la ficha de la tienda, según la región ("19 Nov, 2020" o "Nov 19, 2020").
FORMATOS_FECHA_TIENDA = ("%d %b, %Y", "%b %d, %Y")
# Años entre la fecha original y la de la tienda a partir de los que se considera un
# acceso anticipado largo o un relanzamiento.
ANIOS_ACCESO_ANTICIPADO_LARGO = 3

# Fichas de tipo juego que no son juegos (herramientas, servidores, demos...).
# Una herramienta sin género no tiene más categoría que Family Sharing (ni Single-player
# ni Multi-player). "Editor", "Server" o "Launcher" no se usan: dan falsos positivos
# con juegos reales (Server is Down, Video Editor Tycoon, Launcher Heroes...).
CATEGORIAS_SIN_MODO_DE_JUEGO = {"Family Sharing"}
PATRON_HERRAMIENTA = r"(?i)\b(?:dedicated server|mod tools?|sdk|artbook|art book|soundtrack)\b"
PATRON_DEMO = r"(?i)\bdemo\b"

FILAS_EJEMPLO = 2          # registros de ejemplo por archivo (más no caben en una terminal de 120)
MAS_FRECUENTES = 10
ANCHO_TITULO = 70
ANCHO_VALOR = 35           # caracteres máximos de un valor en las tablas de ejemplo


# =========================================================================== #
# FUNCIONES                                                                   #
# =========================================================================== #

# --------------------------------------------------------------------------- #
# Lectura                                                                     #
# --------------------------------------------------------------------------- #

def leer_jsonl(ruta: Path) -> tuple[pd.DataFrame, int]:
    """
    Lee un archivo JSONL en un DataFrame, tolerando las líneas dañadas.

    Antes de interpretar cada línea se quitan los bytes nulos y los espacios de los
    extremos (una escritura interrumpida puede dejar bytes nulos delante de un registro
    válido). Las líneas que quedan vacías se saltan y las que no son un objeto JSON se
    cuentan como no válidas. No se usa pd.read_json(lines=True) porque falla entero con
    una sola línea dañada.

    Parámetros
    ----------
    ruta : archivo JSONL.

    Devuelve
    --------
    (datos, número de líneas no válidas ignoradas).
    """
    registros = []
    ignoradas = 0
    with ruta.open(encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip("\x00 \t\r\n")
            if not linea:
                continue
            try:
                registro = json.loads(linea)
            except ValueError:
                ignoradas += 1
                continue
            if isinstance(registro, dict):
                registros.append(registro)
            else:
                ignoradas += 1
    return pd.DataFrame.from_records(registros), ignoradas


# --------------------------------------------------------------------------- #
# Consola                                                                     #
# --------------------------------------------------------------------------- #

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


def acortar_valor(valor: object) -> str:
    """
    Convierte un valor en texto de como mucho ANCHO_VALOR caracteres para las tablas.

    Parámetros
    ----------
    valor : valor de una celda (texto, número, lista o vacío).

    Devuelve
    --------
    Texto del valor; "(vacío)" si es nulo.
    """
    if not isinstance(valor, list) and pd.isna(valor):
        return "(vacío)"
    texto = str(valor)
    return texto if len(texto) <= ANCHO_VALOR else texto[:ANCHO_VALOR - 3] + "..."


def mostrar_frecuencias(frecuencias: pd.Series) -> None:
    """
    Escribe una tabla de dos columnas (valor y número de casos), alineada y con
    separador de miles.

    Parámetros
    ----------
    frecuencias : número de casos por valor.
    """
    etiquetas = [" / ".join(map(str, valor)) if isinstance(valor, tuple) else str(valor)
                 for valor in frecuencias.index]
    ancho = max(map(len, etiquetas), default=0)
    for etiqueta, cantidad in zip(etiquetas, frecuencias):
        print(f"  {etiqueta:{ancho}}  {formatear_numero(int(cantidad)):>8}")


def porcentaje(parte: int, total: int) -> str:
    """
    Formatea una proporción como porcentaje con un decimal y coma decimal.

    Parámetros
    ----------
    parte : casos que cumplen la condición.
    total : casos totales.

    Devuelve
    --------
    Porcentaje como texto (p. ej. "3,5 %"); "-" si total es 0.
    """
    return f"{100 * parte / total:.1f} %".replace(".", ",") if total else "-"


# --------------------------------------------------------------------------- #
# 1. Estructura                                                               #
# --------------------------------------------------------------------------- #

def examinar_estructura(nombre: str, datos: pd.DataFrame, ignoradas: int) -> None:
    """
    Muestra filas, columnas, tipos y primeros registros de un archivo.

    Parámetros
    ----------
    nombre    : nombre del archivo.
    datos     : contenido del archivo.
    ignoradas : líneas no válidas descartadas al leerlo.
    """
    print(f"\n--- {nombre}: {formatear_numero(len(datos))} filas x {datos.shape[1]} columnas "
          f"({ignoradas} líneas no válidas ignoradas)")
    # Una fila por columna (tipo y primeros registros) para que quepa en la consola.
    ejemplos = datos.head(FILAS_EJEMPLO).T.map(acortar_valor)
    ejemplos.columns = [f"registro {numero}" for numero in range(1, len(ejemplos.columns) + 1)]
    print(pd.concat([datos.dtypes.astype(str).rename("tipo"), ejemplos], axis=1).to_string())


# --------------------------------------------------------------------------- #
# 2. Calidad                                                                  #
# --------------------------------------------------------------------------- #

def contar_ausentes(datos: pd.DataFrame) -> pd.DataFrame:
    """
    Cuenta por columna los valores nulos, las listas vacías y los textos vacíos.

    isna() solo detecta los nulos; en la captura una ausencia también puede ser [] o "".

    Parámetros
    ----------
    datos : DataFrame a revisar.

    Devuelve
    --------
    Una fila por columna con las tres cuentas (solo columnas con alguna ausencia).
    """
    ausentes = pd.DataFrame({
        "nulos": datos.isna().sum(),
        "listas_vacias": datos.apply(lambda columna: columna.map(lambda v: isinstance(v, list) and not v).sum()),
        "textos_vacios": datos.apply(lambda columna: columna.map(lambda v: isinstance(v, str) and not v.strip()).sum()),
    })
    return ausentes[ausentes.sum(axis=1) > 0]


def contar_repetidos(datos: pd.DataFrame) -> tuple[int, int]:
    """
    Cuenta las filas repetidas y los appid repetidos.

    duplicated() no admite listas, así que se convierten a tuplas solo para comparar.

    Parámetros
    ----------
    datos : DataFrame con la columna CLAVE.

    Devuelve
    --------
    (filas repetidas, appid repetidos).
    """
    comparable = datos.apply(lambda columna: columna.map(lambda v: tuple(v) if isinstance(v, list) else v))
    return int(comparable.duplicated().sum()), int(datos[CLAVE].duplicated().sum())


def comprobar_cuadre(lista: pd.DataFrame, periodo: pd.DataFrame, fichas: pd.DataFrame,
                     descartados: pd.DataFrame) -> dict[str, int]:
    """
    Comprueba que los appid de los cuatro archivos encajan entre sí.

    lista = periodo + descartados en el filtro de periodo, y periodo = fichas +
    descartados en las fichas + pendientes de descargar.

    Parámetros
    ----------
    lista, periodo, fichas, descartados : contenido de cada archivo.

    Devuelve
    --------
    Cuentas del cuadre (lo que no encaja debería ser 0).
    """
    ids_lista, ids_periodo, ids_fichas = set(lista[CLAVE]), set(periodo[CLAVE]), set(fichas[CLAVE])
    ids_desc_periodo = set(descartados.loc[descartados["descartado_en"] == "periodo", CLAVE])
    ids_desc_fichas = set(descartados.loc[descartados["descartado_en"] == "fichas", CLAVE])
    return {
        "lista sin periodo ni descartados": len(ids_lista - ids_periodo - ids_desc_periodo),
        "en periodo y descartados en periodo": len(ids_periodo & ids_desc_periodo),
        "fichas fuera de periodo": len(ids_fichas - ids_periodo),
        "en fichas y descartados": len(ids_fichas & ids_desc_fichas),
        "pendientes de descargar": len(ids_periodo - ids_fichas - ids_desc_fichas),
    }


# --------------------------------------------------------------------------- #
# 3. Campos relevantes                                                        #
# --------------------------------------------------------------------------- #

def contar_valores_lista(columna: pd.Series) -> pd.Series:
    """
    Cuenta cuántos juegos tienen cada valor de una columna de listas.

    Parámetros
    ----------
    columna : columna con una lista de textos por juego.

    Devuelve
    --------
    Número de juegos por valor, de más a menos frecuente.
    """
    return columna.explode().dropna().value_counts()


def buscar_variantes(valores: pd.Index) -> list[list[str]]:
    """
    Busca valores que solo se diferencian en mayúsculas, espacios o guiones.

    Parámetros
    ----------
    valores : valores distintos de una columna.

    Devuelve
    --------
    Grupos de variantes de un mismo valor (vacía si no hay).
    """
    normalizados = pd.Series(valores, index=valores).str.lower().str.replace(r"[\s\-_]+", "", regex=True)
    grupos = normalizados.groupby(normalizados).groups
    return [sorted(grupo) for grupo in grupos.values() if len(grupo) > 1]


def convertir_fecha_tienda(textos: pd.Series) -> pd.Series:
    """
    Convierte las fechas de la tienda a fecha, probando los formatos de FORMATOS_FECHA_TIENDA.

    Parámetros
    ----------
    textos : fechas de lanzamiento tal como las muestra la tienda.

    Devuelve
    --------
    Fechas (NaT si ningún formato encaja).
    """
    fechas = pd.Series(pd.NaT, index=textos.index)
    for formato in FORMATOS_FECHA_TIENDA:
        fechas = fechas.fillna(pd.to_datetime(textos, format=formato, errors="coerce"))
    return fechas


def asignar_fecha(fechas: pd.DataFrame) -> pd.Series:
    """
    Asigna a cada juego la primera de sus fechas que cae dentro del periodo exacto.

    Se usan las cuatro fechas porque la ingesta acepta un juego si cualquiera de ellas
    cae en el periodo (p. ej. la tienda puede mostrar la fecha de la versión 1.0 y
    Steam la del lanzamiento en acceso anticipado).

    Parámetros
    ----------
    fechas : una columna por fecha del juego (tienda, Steam, original y salida del
             acceso anticipado).

    Devuelve
    --------
    Fecha asignada (NaT si ninguna cae en el periodo).
    """
    return fechas.where(fechas.apply(lambda fecha: fecha.between(INICIO_PERIODO, FIN_PERIODO))).min(axis=1)


def detectar_no_juegos(fichas: pd.DataFrame) -> pd.DataFrame:
    """
    Marca las fichas de tipo juego que no son juegos, con una columna por regla.

    Parámetros
    ----------
    fichas : contenido de ARCHIVO_FICHAS.

    Devuelve
    --------
    Una columna booleana por regla: herramienta sin género ni modo de juego,
    herramienta por el nombre y demo por el nombre.
    """
    sin_modo_de_juego = fichas["generos"].map(lambda generos: not generos) & \
        fichas["categorias"].map(lambda categorias: set(categorias) <= CATEGORIAS_SIN_MODO_DE_JUEGO)
    return pd.DataFrame({
        "herramienta sin género ni modo de juego": sin_modo_de_juego,
        "herramienta por el nombre": fichas["nombre"].str.contains(PATRON_HERRAMIENTA, regex=True),
        "demo por el nombre": fichas["nombre"].str.contains(PATRON_DEMO, regex=True),
    })


def revisar_campos(fichas: pd.DataFrame) -> dict[str, int]:
    """
    Muestra los valores distintos de los campos de categorías y cuenta valores fuera de rango.

    Parámetros
    ----------
    fichas : contenido de ARCHIVO_FICHAS, con fecha_tienda y fecha_original ya convertidas.

    Devuelve
    --------
    Cuentas de valores fuera de rango o incoherentes.
    """
    for columna in COLUMNAS_LISTA:
        frecuencias = contar_valores_lista(fichas[columna])
        print(f"\n--- {columna}: {len(frecuencias)} valores distintos. Más frecuentes:")
        mostrar_frecuencias(frecuencias.head(MAS_FRECUENTES))
        print(f"  Variantes de un mismo valor: {buscar_variantes(frecuencias.index) or 'ninguna'}")

    print("\n--- moneda:")
    mostrar_frecuencias(fichas["moneda"].fillna("(vacío)").value_counts())

    no_juegos = detectar_no_juegos(fichas)
    print("\n--- Fichas que no son juegos:")
    for regla, marcadas in no_juegos.items():
        ejemplos = ", ".join(fichas.loc[marcadas, "nombre"].head(FILAS_EJEMPLO))
        print(f"  {regla:40} {formatear_numero(int(marcadas.sum())):>8}  (p. ej. {ejemplos})")

    total_resenas = fichas["resenas_positivas"] + fichas["resenas_negativas"]
    es_gratis = fichas["es_gratis"].eq(True)
    precio = fichas["precio_base_centimos"]
    return {
        "reseñas negativas (< 0)": int((fichas[["resenas_positivas", "resenas_negativas"]] < 0).any(axis=1).sum()),
        "juegos con 0 reseñas": int((total_resenas == 0).sum()),
        "gratis con precio": int((es_gratis & precio.notna()).sum()),
        "de pago sin precio": int((~es_gratis & precio.isna()).sum()),
        "de pago con precio <= 0": int((~es_gratis & (precio <= 0)).sum()),
        "descuento fuera de 0-100": int((~fichas["descuento_pct"].dropna().between(0, 100)).sum()),
        "fecha de la tienda no convertible": int(fichas["fecha_tienda"].isna().sum()),
        "fecha original posterior a la de la tienda": int((fichas["fecha_original"] > fichas["fecha_tienda"]).sum()),
        "juegos sin géneros": int(fichas["generos"].map(lambda valores: not valores).sum()),
        "juegos sin etiquetas": int(fichas["etiquetas"].map(lambda valores: not valores).sum()),
        "fichas que no son juegos": int(no_juegos.any(axis=1).sum()),
    }


# --------------------------------------------------------------------------- #
# 4. Cobertura temporal                                                       #
# --------------------------------------------------------------------------- #

def revisar_cobertura(fichas: pd.DataFrame) -> dict[str, int]:
    """
    Muestra los juegos por año y por mes de 2020 con la fecha asignada y el rango de
    fechas de petición.

    Parámetros
    ----------
    fichas : contenido de ARCHIVO_FICHAS, con fecha_asignada, fecha_tienda y fecha_original.

    Devuelve
    --------
    Cuentas de juegos fuera del periodo exacto y de accesos anticipados largos.
    """
    asignada = fichas["fecha_asignada"]
    print("\n--- Juegos por año (fecha asignada):")
    mostrar_frecuencias(asignada.dropna().dt.year.value_counts().sort_index())
    print("\n--- Juegos por mes en 2020 (efecto COVID):")
    mostrar_frecuencias(asignada[asignada.dt.year == 2020].dt.strftime("%Y-%m").value_counts().sort_index())

    peticiones = pd.to_datetime(fichas["fecha_peticion"], utc=True)
    print(f"\n--- Fechas de petición: de {peticiones.min():%d/%m/%Y %H:%M} "
          f"a {peticiones.max():%d/%m/%Y %H:%M} (UTC)")

    diferencia_anios = (fichas["fecha_tienda"] - fichas["fecha_original"]).dt.days / 365.25
    return {
        "fuera del periodo exacto (margen de la ingesta)": int(asignada.isna().sum()),
        "fecha original anterior a 2020": int((fichas["fecha_original"] < INICIO_PERIODO).sum()),
        f"acceso anticipado de más de {ANIOS_ACCESO_ANTICIPADO_LARGO} años":
            int((diferencia_anios > ANIOS_ACCESO_ANTICIPADO_LARGO).sum()),
    }


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
    parser = argparse.ArgumentParser(description="Diagnóstico de la captura RAW de juegos de Steam.")
    parser.add_argument("--fecha", default=FECHA_CAPTURA_POR_DEFECTO,
                        help=f"Carpeta de la captura en data/raw/ (por defecto, {FECHA_CAPTURA_POR_DEFECTO}).")
    return parser.parse_args()


# =========================================================================== #
# MAIN                                                                        #
# =========================================================================== #

def main() -> None:
    """Carga la captura y muestra el diagnóstico de cada apartado y el resumen."""
    args = parsear_argumentos()
    dir_captura = DIR_RAW / args.fecha
    if not dir_captura.is_dir():
        raise SystemExit(f"No existe la captura {dir_captura}.")

    mostrar_titulo(f"1. ESTRUCTURA ({dir_captura})")
    archivos = {nombre: leer_jsonl(dir_captura / nombre)
                for nombre in (ARCHIVO_LISTA_JUEGOS, ARCHIVO_PERIODO, ARCHIVO_FICHAS, ARCHIVO_DESCARTADOS)}
    for nombre, (datos, ignoradas) in archivos.items():
        examinar_estructura(nombre, datos, ignoradas)
    lista, periodo, fichas, descartados = (datos for datos, _ in archivos.values())

    mostrar_titulo("2. CALIDAD")
    for nombre, (datos, _) in archivos.items():
        filas_repetidas, claves_repetidas = contar_repetidos(datos)
        print(f"\n--- {nombre}: {formatear_numero(filas_repetidas)} filas repetidas, "
              f"{formatear_numero(claves_repetidas)} {CLAVE} repetidos")
        ausentes = contar_ausentes(datos)
        print(ausentes.map(formatear_numero).to_string() if not ausentes.empty else "Sin valores ausentes.")
    print("\n--- Motivos de descarte:")
    mostrar_frecuencias(descartados.groupby(["descartado_en", "motivo"]).size())
    cuadre = comprobar_cuadre(lista, periodo, fichas, descartados)
    print("\n--- Cuadre entre archivos:")
    for comprobacion, cantidad in cuadre.items():
        print(f"  {comprobacion:45} {formatear_numero(cantidad):>8}")

    fichas = fichas.assign(fecha_tienda=convertir_fecha_tienda(fichas["fecha_lanzamiento"]),
                           fecha_original=pd.to_datetime(fichas["fecha_lanzamiento_original"], errors="coerce"))
    fichas = fichas.assign(fecha_asignada=asignar_fecha(pd.DataFrame({
        "tienda": fichas["fecha_tienda"],
        "steam": pd.to_datetime(fichas["fecha_lanzamiento_steam"], errors="coerce"),
        "original": fichas["fecha_original"],
        "salida_acceso_anticipado": pd.to_datetime(fichas["fecha_salida_acceso_anticipado"], errors="coerce"),
    })))

    mostrar_titulo(f"3. CAMPOS RELEVANTES ({ARCHIVO_FICHAS})")
    rangos = revisar_campos(fichas)

    mostrar_titulo("4. COBERTURA TEMPORAL")
    cobertura = revisar_cobertura(fichas)

    mostrar_titulo(f"5. RESUMEN ({formatear_numero(len(fichas))} juegos en {ARCHIVO_FICHAS})")
    for comprobacion, cantidad in (rangos | cobertura).items():
        print(f"  {comprobacion:50} {formatear_numero(cantidad):>8}  ({porcentaje(cantidad, len(fichas))})")


if __name__ == "__main__":
    main()
