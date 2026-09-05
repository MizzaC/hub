"""Resolve only allowlisted environment secrets; database values stay opaque."""

import os

from .base import ConnectorError

SECRET_ENVIRONMENTS = {
    "binance": {
        "api_key": "FUNDBOARD_BINANCE_API_KEY",
        "secret_key": "FUNDBOARD_BINANCE_SECRET_KEY",
    },
    "enable_banking": {
        "application_id": "FUNDBOARD_ENABLE_BANKING_APPLICATION_ID",
        "private_key_path": "FUNDBOARD_ENABLE_BANKING_PRIVATE_KEY_PATH",
    },
}


def default_secret_reference(provider):
    return f"env:{provider}" if provider in SECRET_ENVIRONMENTS else ""


def resolve_secrets(connection):
    expected_reference = default_secret_reference(connection.provider)
    if not expected_reference or connection.secret_reference != expected_reference:
        raise ConnectorError("secret_reference", "La référence de secrets est invalide.")
    values = {}
    missing = []
    for key, environment_name in SECRET_ENVIRONMENTS[connection.provider].items():
        value = os.getenv(environment_name, "").strip()
        if value:
            values[key] = value
        else:
            missing.append(environment_name)
    if missing:
        raise ConnectorError(
            "missing_secret",
            "La configuration secrète de cette connexion est incomplète.",
        )
    return values
