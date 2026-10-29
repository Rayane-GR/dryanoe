"""Runtime configuration, read from the environment set by docker compose."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    app_name: str = "MouHassaBa API"
    version: str = "0.1.0"
    description: str = (
        "REST API for MouHassaBa, an accounting application compliant with the "
        "Algerian SCF (Système Comptable Financier)."
    )
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://mouhassaba:mouhassaba_dev@localhost:5432/mouhassaba",
        )
    )
    # TAP (taxe sur l'activité professionnelle) rate applied to revenue by default.
    # Rates are set by Algerian finance law and must be confirmed with an accountant.
    default_tap_rate: float = field(
        default_factory=lambda: float(os.getenv("DEFAULT_TAP_RATE", "0.015"))
    )


settings = Settings()
