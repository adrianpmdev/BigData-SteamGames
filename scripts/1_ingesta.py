"""
Descarga los juegos de Steam desde la API de Steam y SteamSpy y los guarda en
data/raw/<fecha>/. Solo guarda los juegos lanzados entre 2020 y 2025 (ambos
incluidos) y, de cada llamada, solo los campos que usa el análisis. Si se
interrumpe, al relanzarlo continúa donde lo dejó.

Funcionamiento
--------------
1. Descarga la lista de juegos de la tienda en games_list.jsonl (solo si no existe).
2. Recorre la lista juego a juego:
     appdetails -> si no es un juego lanzado en 2020-2025, se apunta en
                   games_discarded.jsonl y se pasa al siguiente.
     reviews    -> solo para los juegos que siguen.
     steamspy   -> solo para los juegos que siguen.
   Cada servidor tiene su propio ritmo de peticiones, así que las tres llamadas
   de un juego no se esperan entre sí.

Archivos generados
------------------
    games_list.jsonl         Lista de juegos de la tienda (Steam, IStoreService/GetAppList).
    games_details.jsonl      Ficha (Steam, store/api/appdetails): name, release_date, genres,
                             categories, is_free, price_initial (céntimos de euro), currency,
                             supported_languages.
    games_reviews.jsonl      Reseñas (Steam, IUserReviewsService/GetAppReviews): total_positive,
                             total_negative.
    games_owners_tags.jsonl  Propietarios y tags (SteamSpy, appdetails): owners, tags.
    games_discarded.jsonl    appid de los juegos que no son del periodo (para no volver a pedirlos).

Argumentos
----------
    --api-key   Steam Web API key. Solo hace falta si games_list.jsonl no existe.
    --fecha     Nombre de la carpeta de la captura. Por defecto, la fecha de hoy.
    --limite    Recorre solo los N primeros juegos de games_list.jsonl (para pruebas).

Uso
---
    # Prueba
    python scripts/1_ingesta.py --api-key CLAVE --fecha prueba --limite 100

    # Captura completa (para continuar tras un corte, el mismo comando)
    python scripts/1_ingesta.py --api-key CLAVE --fecha 2026-11-18
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


# =========================================================================== #
# VARIABLES Y CONSTANTES                                                      #
# =========================================================================== #

DIR_RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

URL_LISTA_APPS = "https://api.steampowered.com/IStoreService/GetAppList/v1/"
USER_AGENT = "steam-games-ingesta/1.0"
TIMEOUT_S = 30
MAX_REINTENTOS = 5
ESPERA_ERROR_S = 60
LOG_CADA = 50        # juegos entre cada línea de progreso
ANCHO_CABECERA = 70

ANIO_INICIO = 2020
ANIO_FIN = 2025

ARCHIVO_LISTA_JUEGOS = "games_list.jsonl"
ARCHIVO_DESCARTADOS = "games_discarded.jsonl"

# Llamadas que se hacen una vez por juego, en el orden en que se piden:
# appdetails decide si se piden las demás. intervalo_s = segundos mínimos entre
# peticiones a esa misma fuente; archivo = dónde se guardan sus campos.
FUENTES: dict[str, dict[str, Any]] = {
    # appdetails admite unas 200 peticiones cada 5 minutos: a 1 s da HTTP 429.
    "appdetails": {"url": "https://store.steampowered.com/api/appdetails",
                   "intervalo_s": 1.5, "archivo": "games_details.jsonl"},
    "reviews": {"url": "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/",
                "intervalo_s": 1.0, "archivo": "games_reviews.jsonl"},
    "steamspy": {"url": "https://steamspy.com/api.php",
                 "intervalo_s": 1.0, "archivo": "games_owners_tags.jsonl"},
}

# Momento (time.monotonic) de la última petición a cada fuente.
instante_ultima_peticion: dict[str, float] = {}

log = logging.getLogger("ingesta")


# =========================================================================== #
# FUNCIONES                                                                   #
# =========================================================================== #

# --------------------------------------------------------------------------- #
# Fuentes: parámetros de cada petición y campos que se guardan                #
# --------------------------------------------------------------------------- #

def construir_params(nombre: str, appid: int) -> dict[str, str]:
    """
    Construye los parámetros de la petición a una fuente para un juego.

    - appdetails: precios en euros (cc=es) y textos en inglés (l=english), para que
      géneros y categorías tengan siempre el mismo nombre.
    - reviews: una sola reseña (num_per_page=1), porque solo interesa el resumen
      (query_summary); con 0, Steam devuelve 20. purchase_type=1 incluye todas las compras.
    - steamspy: ficha del juego.

    Parámetros
    ----------
    nombre : clave de la fuente en FUENTES.
    appid  : identificador del juego en Steam.

    Devuelve
    --------
    Parámetros de la URL.

    Lanza
    -----
    ValueError : si la fuente no existe.
    """
    if nombre == "appdetails":
        return {"appids": str(appid), "cc": "es", "l": "english"}
    if nombre == "reviews":
        consulta = {"appid": appid, "num_per_page": 1, "languages": ["all"],
                    "review_type": 0, "purchase_type": 1}
        return {"input_json": json.dumps(consulta)}
    if nombre == "steamspy":
        return {"request": "appdetails", "appid": str(appid)}
    raise ValueError(f"fuente desconocida: {nombre}")


def extraer_campos_appdetails(appid: int, respuesta: Any) -> dict[str, Any] | None:
    """
    Se queda con los campos útiles de la ficha si el juego es del periodo de análisis.

    Descarta las fichas sin datos, lo que no es un juego, los juegos no lanzados
    ("Coming soon") y los lanzados fuera de ANIO_INICIO-ANIO_FIN. De la fecha
    ("19 Nov, 2020" o "Nov 19, 2020" según la región) solo se mira el año.

    Parámetros
    ----------
    appid     : identificador del juego en Steam.
    respuesta : JSON devuelto por appdetails.

    Devuelve
    --------
    Campos del juego, o None si se descarta.

    Lanza
    -----
    KeyError, TypeError : si la respuesta no tiene el formato esperado.
    """
    ficha = respuesta[str(appid)]
    if not ficha.get("success"):
        return None
    datos = ficha["data"]
    if datos.get("type") != "game":
        return None

    lanzamiento = datos.get("release_date") or {}
    anio = re.search(r"\b\d{4}\b", lanzamiento.get("date", ""))
    if lanzamiento.get("coming_soon") or not anio or not ANIO_INICIO <= int(anio.group()) <= ANIO_FIN:
        return None

    # initial = precio sin descuento, en céntimos. No viene si el juego es gratis
    # o no se vende en la región.
    precio = datos.get("price_overview") or {}
    return {
        "name": datos.get("name"),
        "release_date": lanzamiento["date"],
        "genres": [genero["description"] for genero in datos.get("genres", [])],
        "categories": [categoria["description"] for categoria in datos.get("categories", [])],
        "is_free": datos.get("is_free"),
        "price_initial": precio.get("initial"),
        "currency": precio.get("currency"),
        # Texto con HTML; los idiomas marcados con * tienen audio completo.
        "supported_languages": datos.get("supported_languages"),
    }


def extraer_campos_reviews(respuesta: Any) -> dict[str, Any]:
    """
    Se queda con el número de reseñas positivas y negativas.

    Parámetros
    ----------
    respuesta : JSON devuelto por GetAppReviews.

    Devuelve
    --------
    total_positive y total_negative.

    Lanza
    -----
    KeyError, TypeError : si la respuesta no tiene el formato esperado.
    """
    resumen = respuesta["response"]["query_summary"]
    return {"total_positive": resumen["total_positive"],
            "total_negative": resumen["total_negative"]}


def extraer_campos_steamspy(respuesta: Any) -> dict[str, Any]:
    """
    Se queda con el rango de propietarios y los nombres de los tags.

    SteamSpy envía los tags como {"Indie": 120, ...}, ordenados por votos, o como []
    si el juego no tiene; se guardan solo los nombres, en ese orden.

    Parámetros
    ----------
    respuesta : JSON devuelto por SteamSpy.

    Devuelve
    --------
    owners y tags.
    """
    return {"owners": respuesta.get("owners"),
            "tags": list(respuesta.get("tags") or [])}


def extraer_campos(nombre: str, appid: int, respuesta: Any) -> dict[str, Any] | None:
    """
    Se queda con los campos útiles de la respuesta de una fuente.

    Parámetros
    ----------
    nombre    : clave de la fuente en FUENTES.
    appid     : identificador del juego en Steam.
    respuesta : JSON devuelto por la fuente.

    Devuelve
    --------
    Campos del juego, o None si se descarta (solo appdetails descarta).

    Lanza
    -----
    KeyError, TypeError : si la respuesta no tiene el formato esperado.
    ValueError          : si la fuente no existe.
    """
    if nombre == "appdetails":
        return extraer_campos_appdetails(appid, respuesta)
    if nombre == "reviews":
        return extraer_campos_reviews(respuesta)
    if nombre == "steamspy":
        return extraer_campos_steamspy(respuesta)
    raise ValueError(f"fuente desconocida: {nombre}")


# --------------------------------------------------------------------------- #
# Peticiones HTTP: reintentos y ritmo de cada fuente                          #
# --------------------------------------------------------------------------- #

def pedir_json_con_reintentos(url: str, params: dict[str, str]) -> Any:
    """
    Hace un GET y devuelve el JSON de la respuesta.

    Ante límites de peticiones (HTTP 403/429), errores del servidor (5xx), errores de
    red o respuestas "null" (appdetails las da cuando limita sin 429), espera
    ESPERA_ERROR_S segundos y reintenta hasta MAX_REINTENTOS veces.

    Parámetros
    ----------
    url    : dirección del endpoint.
    params : parámetros de la URL.

    Devuelve
    --------
    JSON de la respuesta.

    Lanza
    -----
    urllib.error.HTTPError : ante un error 4xx que no es de límite (no se reintenta).
    RuntimeError           : si se agotan los reintentos.
    """
    url_completa = f"{url}?{urllib.parse.urlencode(params)}"
    peticion = urllib.request.Request(url_completa, headers={"User-Agent": USER_AGENT})

    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            with urllib.request.urlopen(peticion, timeout=TIMEOUT_S) as respuesta:
                datos = json.load(respuesta)
            if datos is None:
                raise ValueError("respuesta vacía")
            return datos
        except urllib.error.HTTPError as error:
            if error.code not in (403, 429) and error.code < 500:
                raise
            motivo = f"HTTP {error.code}"
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as error:
            motivo = f"{type(error).__name__}: {error}"

        log.warning("Intento %d/%d fallido (%s). Reintento en %d s.",
                    intento, MAX_REINTENTOS, motivo, ESPERA_ERROR_S)
        time.sleep(ESPERA_ERROR_S)

    raise RuntimeError(f"agotados {MAX_REINTENTOS} reintentos")


def consultar_fuente(nombre: str, appid: int) -> dict[str, Any] | None:
    """
    Pide una fuente para un juego, respetando su intervalo, y extrae los campos útiles.

    Cada fuente lleva su propio reloj (instante_ultima_peticion): solo se espera lo
    que falte desde la última petición a esa misma fuente.

    Parámetros
    ----------
    nombre : clave de la fuente en FUENTES.
    appid  : identificador del juego en Steam.

    Devuelve
    --------
    Campos del juego, o None si se descarta.

    Lanza
    -----
    urllib.error.HTTPError, RuntimeError : si la petición falla (ver pedir_json_con_reintentos).
    KeyError, TypeError                  : si la respuesta no tiene el formato esperado.
    """
    fuente = FUENTES[nombre]
    espera = instante_ultima_peticion.get(nombre, 0.0) + fuente["intervalo_s"] - time.monotonic()
    if espera > 0:
        time.sleep(espera)
    try:
        respuesta = pedir_json_con_reintentos(fuente["url"], construir_params(nombre, appid))
        return extraer_campos(nombre, appid, respuesta)
    finally:
        instante_ultima_peticion[nombre] = time.monotonic()


# --------------------------------------------------------------------------- #
# Archivos JSONL: lectura y escritura                                         #
# --------------------------------------------------------------------------- #

def leer_appids_jsonl(ruta: Path) -> list[int]:
    """
    Lee el appid de cada línea de un archivo JSONL, en orden.

    Ignora las líneas incompletas que pueda dejar un corte a mitad de escritura.

    Parámetros
    ----------
    ruta : archivo JSONL con un campo "appid" por línea.

    Devuelve
    --------
    Lista de appids; vacía si el archivo no existe.
    """
    if not ruta.exists():
        return []
    appids = []
    with ruta.open(encoding="utf-8") as archivo:
        for linea in archivo:
            try:
                appids.append(json.loads(linea)["appid"])
            except (ValueError, KeyError):
                continue
    return appids


def anadir_linea_jsonl(ruta: Path, registro: dict[str, Any]) -> None:
    """
    Añade un registro como una línea JSON al final del archivo.

    Parámetros
    ----------
    ruta     : archivo JSONL (se crea si no existe).
    registro : datos a escribir.
    """
    with ruta.open("a", encoding="utf-8") as archivo:
        archivo.write(json.dumps(registro, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# Consola: formato de números y mensajes de progreso                          #
# --------------------------------------------------------------------------- #

def formatear_numero(numero: int) -> str:
    """
    Formatea un entero con punto como separador de miles (201.333).

    Parámetros
    ----------
    numero : entero a formatear.

    Devuelve
    --------
    Número como texto.
    """
    return f"{numero:,}".replace(",", ".")


def formatear_decimal(numero: float) -> str:
    """
    Formatea un decimal con un dígito y coma como separador (1,5).

    Parámetros
    ----------
    numero : decimal a formatear.

    Devuelve
    --------
    Número como texto.
    """
    return f"{numero:.1f}".replace(".", ",")


def formatear_duracion(segundos: float) -> str:
    """
    Formatea una duración en horas y minutos (83 h 05 min).

    Parámetros
    ----------
    segundos : duración en segundos.

    Devuelve
    --------
    Duración como texto.
    """
    minutos = int(segundos // 60)
    return f"{minutos // 60} h {minutos % 60:02d} min"


def obtener_etiqueta_archivo(archivo: str) -> str:
    """
    Acorta el nombre de un archivo para los mensajes de progreso.

    Parámetros
    ----------
    archivo : nombre del archivo (p. ej. games_owners_tags.jsonl).

    Devuelve
    --------
    Nombre sin el prefijo games_ ni la extensión (p. ej. owners_tags).
    """
    return archivo.removeprefix("games_").removesuffix(".jsonl")


def mostrar_cabecera(titulo: str) -> None:
    """
    Escribe en el log el título de una sección entre dos líneas de =.

    Parámetros
    ----------
    titulo : texto de la cabecera.
    """
    log.info("=" * ANCHO_CABECERA)
    log.info(titulo)
    log.info("=" * ANCHO_CABECERA)


def mostrar_estado_archivos(hechos: dict[str, set[int]], descartados: set[int]) -> None:
    """
    Escribe en el log cuántos juegos tiene cada archivo de la captura.

    Parámetros
    ----------
    hechos      : appids guardados por cada fuente.
    descartados : appids descartados.
    """
    for nombre, fuente in FUENTES.items():
        log.info("  %-24s %10s juegos", fuente["archivo"], formatear_numero(len(hechos[nombre])))
    log.info("  %-24s %10s juegos", ARCHIVO_DESCARTADOS, formatear_numero(len(descartados)))


def mostrar_progreso(numero: int, total: int, inicio: float,
                     hechos: dict[str, set[int]], descartados: set[int]) -> None:
    """
    Escribe en el log una línea de progreso con el total de cada archivo, el ritmo
    y el tiempo estimado que falta.

    Parámetros
    ----------
    numero      : juegos recorridos en esta ejecución.
    total       : juegos pendientes al empezar esta ejecución.
    inicio      : momento (time.monotonic) en que empezó el recorrido.
    hechos      : appids guardados por cada fuente.
    descartados : appids descartados.
    """
    segundos_por_juego = (time.monotonic() - inicio) / numero
    contadores = " · ".join(
        f"{obtener_etiqueta_archivo(fuente['archivo'])} {formatear_numero(len(hechos[nombre]))}"
        for nombre, fuente in FUENTES.items()
    )
    log.info("[%s/%s · %s %%]  %s · %s %s  |  %s s/juego  |  quedan ~%s",
             formatear_numero(numero), formatear_numero(total), formatear_decimal(100 * numero / total),
             contadores, obtener_etiqueta_archivo(ARCHIVO_DESCARTADOS),
             formatear_numero(len(descartados)), formatear_decimal(segundos_por_juego),
             formatear_duracion(segundos_por_juego * (total - numero)))


# --------------------------------------------------------------------------- #
# Descarga: lista de juegos y datos de cada juego                             #
# --------------------------------------------------------------------------- #

def descargar_lista_juegos(api_key: str, destino: Path) -> None:
    """
    Descarga la lista completa de juegos de la tienda, página a página.

    Escribe en un archivo temporal y solo lo renombra a destino si la lista llega
    completa, para no dejar nunca la lista a medias.

    Parámetros
    ----------
    api_key : Steam Web API key.
    destino : ruta de ARCHIVO_LISTA_JUEGOS.
    """
    temporal = destino.with_suffix(".tmp")
    total = 0
    ultimo_appid = 0
    with temporal.open("w", encoding="utf-8") as archivo:
        while True:
            params = {"key": api_key, "max_results": "50000", "last_appid": str(ultimo_appid)}
            pagina = pedir_json_con_reintentos(URL_LISTA_APPS, params)["response"]
            for app in pagina.get("apps", []):
                archivo.write(json.dumps(app, ensure_ascii=False) + "\n")
                total += 1
            log.info("  %s juegos descargados", formatear_numero(total))
            if not pagina.get("have_more_results"):
                break
            ultimo_appid = pagina["last_appid"]

    temporal.replace(destino)


def descargar_datos_por_juego(appids: list[int], dir_captura: Path) -> None:
    """
    Pide appdetails, reviews y steamspy juego a juego y guarda cada respuesta útil.

    Se salta lo ya descargado en una ejecución anterior. Si appdetails descarta el
    juego, lo apunta en ARCHIVO_DESCARTADOS y no pide las demás fuentes. Si una
    petición falla, deja el juego incompleto para reintentarlo al relanzar.

    Parámetros
    ----------
    appids      : juegos a recorrer, en orden.
    dir_captura : carpeta de la captura (data/raw/<fecha>).
    """
    rutas = {nombre: dir_captura / fuente["archivo"] for nombre, fuente in FUENTES.items()}
    ruta_descartados = dir_captura / ARCHIVO_DESCARTADOS

    hechos = {nombre: set(leer_appids_jsonl(ruta)) for nombre, ruta in rutas.items()}
    descartados = set(leer_appids_jsonl(ruta_descartados))
    pendientes = [appid for appid in appids
                  if appid not in descartados and any(appid not in h for h in hechos.values())]

    mostrar_cabecera("DATOS POR JUEGO (details -> reviews -> owners_tags)")
    log.info("Ya descargado:")
    mostrar_estado_archivos(hechos, descartados)
    log.info("Pendientes: %s juegos. Progreso cada %d.", formatear_numero(len(pendientes)), LOG_CADA)

    try:
        recorrer_juegos_pendientes(pendientes, rutas, ruta_descartados, hechos, descartados)
    finally:
        mostrar_cabecera("RESUMEN")
        mostrar_estado_archivos(hechos, descartados)


def recorrer_juegos_pendientes(pendientes: list[int], rutas: dict[str, Path],
                               ruta_descartados: Path, hechos: dict[str, set[int]],
                               descartados: set[int]) -> None:
    """
    Pide las fuentes que falten de cada juego pendiente y guarda lo que llegue.

    Actualiza hechos y descartados a medida que escribe, y muestra el progreso
    cada LOG_CADA juegos.

    Parámetros
    ----------
    pendientes       : juegos a recorrer, en orden.
    rutas            : archivo de cada fuente.
    ruta_descartados : archivo de los juegos descartados.
    hechos           : appids guardados por cada fuente.
    descartados      : appids descartados.
    """
    inicio = time.monotonic()
    for numero, appid in enumerate(pendientes, start=1):
        for nombre in FUENTES:
            if appid in hechos[nombre]:
                continue
            try:
                campos = consultar_fuente(nombre, appid)
            except (urllib.error.HTTPError, RuntimeError, KeyError, TypeError) as error:
                log.error("%s: appid %d no descargado (%s: %s).", nombre, appid, type(error).__name__, error)
                break

            registro = {"appid": appid,
                        "fecha_peticion": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            if campos is None:
                anadir_linea_jsonl(ruta_descartados, registro)
                descartados.add(appid)
                break
            anadir_linea_jsonl(rutas[nombre], registro | campos)
            hechos[nombre].add(appid)

        if numero % LOG_CADA == 0 or numero == len(pendientes):
            mostrar_progreso(numero, len(pendientes), inicio, hechos, descartados)


# --------------------------------------------------------------------------- #
# Argumentos de la línea de comandos                                          #
# --------------------------------------------------------------------------- #

def parsear_argumentos() -> argparse.Namespace:
    """
    Lee los argumentos de la línea de comandos.

    Devuelve
    --------
    Argumentos: api_key, fecha y limite.
    """
    parser = argparse.ArgumentParser(description="Ingesta de juegos desde la API de Steam y SteamSpy.")
    parser.add_argument("--api-key", help=f"Steam Web API key (solo si {ARCHIVO_LISTA_JUEGOS} no existe).")
    parser.add_argument("--fecha", default=date.today().isoformat(),
                        help="Carpeta de la captura en data/raw/ (por defecto, hoy).")
    parser.add_argument("--limite", type=int,
                        help=f"Recorrer solo los N primeros juegos de {ARCHIVO_LISTA_JUEGOS} (pruebas).")
    return parser.parse_args()


# =========================================================================== #
# MAIN                                                                        #
# =========================================================================== #

def main() -> None:
    """Descarga la lista de juegos si falta y después los datos de cada juego."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s",
                        datefmt="%d/%m %H:%M:%S")
    args = parsear_argumentos()

    dir_captura = DIR_RAW / args.fecha
    ruta_juegos = dir_captura / ARCHIVO_LISTA_JUEGOS
    if not ruta_juegos.exists() and not args.api_key:
        raise SystemExit(f"No existe {ruta_juegos}: hace falta --api-key para descargarlo.")

    dir_captura.mkdir(parents=True, exist_ok=True)
    log.info("Captura en %s", dir_captura)

    try:
        mostrar_cabecera(f"LISTA DE JUEGOS ({ARCHIVO_LISTA_JUEGOS})")
        if ruta_juegos.exists():
            log.info("Ya existe, no se descarga de nuevo.")
        else:
            descargar_lista_juegos(args.api_key, ruta_juegos)

        appids = leer_appids_jsonl(ruta_juegos)
        log.info("%s juegos en la lista.", formatear_numero(len(appids)))
        if args.limite:
            appids = appids[: args.limite]
        descargar_datos_por_juego(appids, dir_captura)
    except KeyboardInterrupt:
        log.warning("Descarga interrumpida. Relanza el mismo comando para continuar.")
        raise SystemExit(130)


if __name__ == "__main__":
    main()
