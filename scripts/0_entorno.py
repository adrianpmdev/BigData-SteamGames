"""
Crea el entorno virtual del proyecto (.venv en la raíz) e instala las librerías de
requirements.txt DENTRO de ese entorno (nunca en el Python global). Solo para Windows.

Uso
---
    python scripts/0_entorno.py            # crea .venv si no existe e instala
    python scripts/0_entorno.py --recrear  # borra .venv y lo vuelve a crear

El entorno se crea con el mismo Python con el que ejecutas este script, sea cual sea
su versión. Si quieres otra versión, lánzalo con ella (p. ej. `py -3.13 scripts/0_entorno.py`).

Notas
-----
- Un script no puede "activar" el entorno en tu terminal (cada proceso tiene su
  propio entorno). Por eso aquí se usa directamente el Python del .venv para
  instalar, y al final tienes que activarlo tú.
- Primero se instala de forma normal. Si falla porque alguna librería no tiene rueda
  precompilada para tu versión de Python (p. ej. pyyaml en versiones muy nuevas) y
  pip intenta compilarla, se reintenta con --only-binary :all:, que elige versiones
  ya compiladas y no necesita Microsoft C++ Build Tools.

@author adrianpmdev
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import venv
from pathlib import Path


# =========================================================================== #
# VARIABLES Y CONSTANTES                                                      #
# =========================================================================== #

RAIZ = Path(__file__).resolve().parent.parent
DIR_VENV = RAIZ / ".venv"
REQUIREMENTS = RAIZ / "requirements.txt"

PYTHON_VENV = DIR_VENV / "Scripts" / "python.exe"
COMANDO_ACTIVAR = r".venv\Scripts\Activate.ps1   (cmd: .venv\Scripts\activate.bat)"

VERSION_ACTUAL = f"{sys.version_info.major}.{sys.version_info.minor}"


# =========================================================================== #
# FUNCIONES                                                                   #
# =========================================================================== #

def obtener_version_python_venv() -> str | None:
    """
    Consulta la versión del Python instalado en .venv.

    Devuelve
    --------
    Versión en formato 'X.Y', o None si .venv no existe o está roto.
    """
    try:
        salida = subprocess.run([str(PYTHON_VENV), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"], capture_output=True, text=True, check=True)

        return salida.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def preparar_venv(recrear: bool) -> None:
    """
    Crea .venv, o lo reutiliza si ya existe y es válido.

    Lo borra y lo vuelve a crear si se pide, si está roto o si usa una versión de
    Python distinta de la que ejecuta este script.

    Parámetros
    ----------
    recrear : si es True, borra .venv aunque sea válido.
    """
    version = obtener_version_python_venv()

    if DIR_VENV.exists():
        motivo = None
        if recrear:
            motivo = "se ha pedido --recrear"
        elif version is None:
            motivo = "el entorno está roto o incompleto"
        elif version != VERSION_ACTUAL:
            motivo = f"usa Python {version} y estás ejecutando Python {VERSION_ACTUAL}"

        if motivo is None:
            print(f"El entorno ya existe (Python {version}): {DIR_VENV}")

            return

        print(f"Borrando el entorno anterior ({motivo})...")
        shutil.rmtree(DIR_VENV)

    print(f"Creando el entorno con Python {VERSION_ACTUAL} en {DIR_VENV}...")
    venv.create(DIR_VENV, with_pip=True)


def instalar_requirements() -> None:
    """
    Actualiza pip e instala requirements.txt con el Python de .venv.

    Si la instalación normal falla (normalmente porque alguna librería no tiene rueda
    precompilada para esta versión de Python), reintenta solo con paquetes
    precompilados (--only-binary :all:).

    Lanza
    -----
    subprocess.CalledProcessError : si falla la actualización de pip o el reintento.
    """
    pip = [str(PYTHON_VENV), "-m", "pip", "install", "--disable-pip-version-check"]

    print("Actualizando pip...")
    subprocess.run([*pip, "--upgrade", "pip"], check=True)

    print(f"Instalando {REQUIREMENTS.name}...")
    resultado = subprocess.run([*pip, "--prefer-binary", "-r", str(REQUIREMENTS)])
    if resultado.returncode == 0:
        return

    print(f"\nLa instalación normal ha fallado (seguramente alguna librería no tiene rueda precompilada para Python {VERSION_ACTUAL}).\nReintentando solo con paquetes precompilados (--only-binary :all:)...\n")
    subprocess.run([*pip, "--only-binary", ":all:", "-r", str(REQUIREMENTS)], check=True)


def parsear_argumentos() -> argparse.Namespace:
    """
    Lee los argumentos de la línea de comandos.

    Devuelve
    --------
    Argumentos: recrear.
    """
    parser = argparse.ArgumentParser(description="Crea .venv e instala requirements.txt")
    parser.add_argument("--recrear", action="store_true", help="borra y recrea .venv")

    return parser.parse_args()


# =========================================================================== #
# MAIN                                                                        #
# =========================================================================== #

def main() -> None:
    """Prepara .venv, instala las librerías e indica cómo activar el entorno."""
    args = parsear_argumentos()
    preparar_venv(args.recrear)
    instalar_requirements()
    print(f"\nEntorno listo (Python {VERSION_ACTUAL}). Actívalo con:  {COMANDO_ACTIVAR}")


if __name__ == "__main__":
    main()
