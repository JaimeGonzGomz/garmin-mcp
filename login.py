"""Inicio de sesion unico en Garmin Connect. Guarda los tokens en ~/.garmin-mcp-tokens.

Ejecutalo tu mismo en una terminal (pide email, contrasena y codigo MFA si lo tienes).
La contrasena no se guarda: solo los tokens.
"""
import getpass
from pathlib import Path

from garminconnect import Garmin

TOKENS = Path.home() / ".garmin-mcp-tokens"


def main() -> None:
    email = input("Email de Garmin Connect: ").strip()
    password = getpass.getpass("Contrasena: ")
    client = Garmin(email, password, prompt_mfa=lambda: input("Codigo MFA: ").strip())
    client.login(str(TOKENS))
    print(f"Listo. Tokens guardados en {TOKENS}")


if __name__ == "__main__":
    main()
