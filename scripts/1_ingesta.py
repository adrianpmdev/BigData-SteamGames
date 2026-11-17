"""
Descarga los juegos de Steam desde la API de Steam y SteamSpy y los guarda en
data/raw/<fecha>/. Si se interrumpe, al relanzarlo continúa donde lo dejó.

Llamadas y archivos generados
-----------------------------
    games       games.jsonl       Lista de juegos de la tienda (Steam, IStoreService/GetAppList).
    appdetails  appdetails.jsonl  Ficha de cada juego (Steam, store/api/appdetails).
    reviews     reviews.jsonl     Resumen de reseñas de cada juego (Steam, IUserReviewsService/GetAppReviews).
    steamspy    steamspy.jsonl    Propietarios y tags de cada juego (SteamSpy, appdetails).

games va primero: las otras tres hacen una llamada por cada juego de games.jsonl.

Argumentos
----------
    --api-key   Steam Web API key. Solo hace falta para games.
    --fecha     Nombre de la carpeta de la captura. Por defecto, la fecha de hoy.
    --fuentes   Llamadas a hacer: games, appdetails, reviews, steamspy. Por defecto, todas.
    --limite    Descarga solo los N primeros juegos (para pruebas).

Uso
---
    # Prueba
    python scripts/1_ingesta.py --api-key CLAVE --fecha prueba --limite 100

    # Captura completa: primero games; después las otras tres en paralelo,
    # en una terminal cada una y con la misma --fecha.
    python scripts/1_ingesta.py --api-key CLAVE --fecha AAAA-MM-DD --fuentes games
    python scripts/1_ingesta.py --fecha AAAA-MM-DD --fuentes appdetails
    python scripts/1_ingesta.py --fecha AAAA-MM-DD --fuentes reviews
    python scripts/1_ingesta.py --fecha AAAA-MM-DD --fuentes steamspy
"""
from __future__ import annotations

import argparse
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

DIR_RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

URL_LISTA_APPS = "https://api.steampowered.com/IStoreService/GetAppList/v1/"
USER_AGENT = "steam-games-ingesta/1.0"
TIMEOUT_S = 30
MAX_REINTENTOS = 5
ESPERA_ERROR_S = 60
LOG_CADA = 500

log = logging.getLogger("ingesta")


# --------------------------------------------------------------------------- #
# Fuentes: una petición por appid                                             #
# --------------------------------------------------------------------------- #

def params_appdetails(appid: int) -> dict[str, str]:
    # cc=us -> precios en USD; l=english -> géneros, categorías y fechas en inglés.
    return {"appids": str(appid), "cc": "us", "l": "english"}


def params_reviews(appid: int) -> dict[str, str]:
    # num_per_page=1 -> el resumen (query_summary) y una sola reseña; con 0 Steam devuelve 20.
    # purchase_type=1 -> todas las compras.
    consulta = {"appid": appid, "num_per_page": 1, "languages": ["all"],
                "review_type": 0, "purchase_type": 1}
    return {"input_json": json.dumps(consulta)}


def params_steamspy(appid: int) -> dict[str, str]:
    return {"request": "appdetails", "appid": str(appid)}


# nombre: (url, segundos entre peticiones, función que construye los parámetros)
FUENTES: dict[str, tuple[str, float, Callable[[int], dict[str, str]]]] = {
    "appdetails": ("https://store.steampowered.com/api/appdetails", 1.5, params_appdetails),
    "reviews": ("https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/", 1.0, params_reviews),
    "steamspy": ("https://steamspy.com/api.php", 1.0, params_steamspy),
}


# --------------------------------------------------------------------------- #
# HTTP                                                                        #
# --------------------------------------------------------------------------- #

def get_json(url: str, params: dict[str, str]) -> Any:
    """GET que devuelve JSON. Reintenta ante límites (403/429), errores 5xx y de red."""
    url_completa = f"{url}?{urllib.parse.urlencode(params)}"
    peticion = urllib.request.Request(url_completa, headers={"User-Agent": USER_AGENT})

    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            with urllib.request.urlopen(peticion, timeout=TIMEOUT_S) as respuesta:
                datos = json.load(respuesta)
            if datos is None:  # appdetails responde "null" cuando limita sin dar 429.
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


# --------------------------------------------------------------------------- #
# JSONL                                                                       #
# --------------------------------------------------------------------------- #

def leer_appids_guardados(ruta: Path) -> set[int]:
    """appid de las líneas ya guardadas. Ignora líneas incompletas por un corte."""
    if not ruta.exists():
        return set()
    appids = set()
    with ruta.open(encoding="utf-8") as archivo:
        for linea in archivo:
            try:
                appids.add(json.loads(linea)["appid"])
            except (ValueError, KeyError):
                continue
    return appids


def guardar_linea(ruta: Path, registro: dict[str, Any]) -> None:
    with ruta.open("a", encoding="utf-8") as archivo:
        archivo.write(json.dumps(registro, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# Descarga                                                                    #
# --------------------------------------------------------------------------- #

def descargar_lista_juegos(api_key: str, destino: Path) -> None:
    """Descarga la lista de juegos de la tienda en games.jsonl."""
    if destino.exists():
        log.info("games: %s ya existe, no se descarga de nuevo.", destino.name)
        return

    # Se escribe en un temporal y solo se renombra si la lista llega completa.
    temporal = destino.with_suffix(".tmp")
    total = 0
    ultimo_appid = 0
    with temporal.open("w", encoding="utf-8") as archivo:
        while True:
            params = {"key": api_key, "max_results": "50000", "last_appid": str(ultimo_appid)}
            pagina = get_json(URL_LISTA_APPS, params)["response"]
            for app in pagina.get("apps", []):
                archivo.write(json.dumps(app, ensure_ascii=False) + "\n")
                total += 1
            log.info("games: %d descargados.", total)
            if not pagina.get("have_more_results"):
                break
            ultimo_appid = pagina["last_appid"]

    temporal.replace(destino)
    log.info("games: terminado.")


def leer_lista_juegos(ruta: Path) -> list[int]:
    with ruta.open(encoding="utf-8") as archivo:
        return [json.loads(linea)["appid"] for linea in archivo]


def descargar_fuente(nombre: str, appids: list[int], dir_captura: Path) -> None:
    """Pide la fuente para cada appid pendiente y guarda la respuesta original."""
    url, intervalo_s, construir_params = FUENTES[nombre]
    destino = dir_captura / f"{nombre}.jsonl"

    ya_guardados = leer_appids_guardados(destino)
    pendientes = [appid for appid in appids if appid not in ya_guardados]
    log.info("%s: %d ya descargados, %d pendientes.", nombre, len(ya_guardados), len(pendientes))

    for numero, appid in enumerate(pendientes, start=1):
        try:
            respuesta = get_json(url, construir_params(appid))
        except (urllib.error.HTTPError, RuntimeError) as error:
            # No se guarda: se volverá a intentar al relanzar el script.
            log.error("%s: appid %d no descargado (%s).", nombre, appid, error)
        else:
            guardar_linea(destino, {"appid": appid,
                                    "fecha_peticion": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                    "respuesta": respuesta})
        if numero % LOG_CADA == 0:
            log.info("%s: %d/%d.", nombre, numero, len(pendientes))
        time.sleep(intervalo_s)

    log.info("%s: terminado.", nombre)


# --------------------------------------------------------------------------- #
# Punto de entrada                                                            #
# --------------------------------------------------------------------------- #

def parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingesta de juegos desde la API de Steam y SteamSpy.")
    opciones = ["games", *FUENTES]
    parser.add_argument("--api-key", help="Steam Web API key (solo para la fuente games).")
    parser.add_argument("--fecha", default=date.today().isoformat(),
                        help="Carpeta de la captura en data/raw/ (por defecto, hoy).")
    parser.add_argument("--fuentes", nargs="+", choices=opciones, default=opciones,
                        help="Llamadas a hacer (por defecto, todas, una detrás de otra).")
    parser.add_argument("--limite", type=int, help="Descargar solo los N primeros juegos (pruebas).")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    args = parsear_argumentos()

    dir_captura = DIR_RAW / args.fecha
    ruta_juegos = dir_captura / "games.jsonl"
    fuentes_por_juego = [nombre for nombre in args.fuentes if nombre in FUENTES]

    if "games" in args.fuentes and not args.api_key:
        raise SystemExit("Falta --api-key para descargar games.jsonl.")
    if fuentes_por_juego and "games" not in args.fuentes and not ruta_juegos.exists():
        raise SystemExit(f"No existe {ruta_juegos}. Lanza primero --fuentes games.")

    dir_captura.mkdir(parents=True, exist_ok=True)
    log.info("Captura en %s", dir_captura)

    try:
        if "games" in args.fuentes:
            descargar_lista_juegos(args.api_key, ruta_juegos)
        if not fuentes_por_juego:
            return

        appids = leer_lista_juegos(ruta_juegos)
        if args.limite:
            appids = appids[: args.limite]
        for nombre in fuentes_por_juego:
            descargar_fuente(nombre, appids, dir_captura)
    except KeyboardInterrupt:
        log.warning("Descarga interrumpida. Relanza el mismo comando para continuar.")
        raise SystemExit(130)


if __name__ == "__main__":
    main()
