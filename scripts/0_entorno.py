"""
Crea el entorno virtual del proyecto (.venv en la raíz) e instala las librerías de
requirements.txt. Si .venv ya existe, solo instala o actualiza las librerías.

Uso
---
    python scripts/0_entorno.py

Después, activa el entorno:
    Windows:      .venv\\Scripts\\activate
"""
from __future__ import annotations

import subprocess
import venv
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_VENV = RAIZ / ".venv"
PYTHON_VENV = DIR_VENV / "Scripts" / "python.exe"
REQUIREMENTS = RAIZ / "requirements.txt"


def crear_venv() -> None:
    if DIR_VENV.exists():
        print(f"El entorno ya existe: {DIR_VENV}")
        return
    print(f"Creando el entorno en {DIR_VENV}...")
    venv.create(DIR_VENV, with_pip=True)


def instalar_librerias() -> None:
    python = str(PYTHON_VENV)
    print("Actualizando pip...")
    subprocess.run([python, "-m", "pip", "install", "--upgrade", "pip"], check=True)
    print(f"Instalando {REQUIREMENTS.name}...")
    subprocess.run([python, "-m", "pip", "install", "-r", str(REQUIREMENTS)], check=True)


def main() -> None:
    crear_venv()
    instalar_librerias()
    print("\nEntorno listo. Actívalo con: .venv\\Scripts\\activate")


if __name__ == "__main__":
    main()
