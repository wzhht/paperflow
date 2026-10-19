import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    """PaperFlow configuration error."""


@dataclass(frozen=True)
class Settings:
    elsevier_api_key: str | None = field(repr=False)
    springer_oa_api_key: str | None = field(repr=False)
    springer_meta_api_key: str | None = field(repr=False)
    http_timeout: float = 60.0
    mineru_backend: str = "api"
    mineru_api_token: str | None = field(default=None, repr=False)
    mineru_api_model: str = "vlm"
    mineru_api_timeout: float = 600.0
    crossref_mailto: str | None = None
    openalex_api_key: str | None = field(default=None, repr=False)
    ieee_api_key: str | None = field(default=None, repr=False)
    unpaywall_email: str | None = None
    elsevier_insttoken: str | None = field(default=None, repr=False)
    ieee_api_enabled: bool = True
    wiley_api_key: str | None = field(default=None, repr=False)


def load_settings() -> Settings:
    load_dotenv()

    return Settings(
        elsevier_api_key=os.getenv("ELSEVIER_API_KEY"),
        springer_oa_api_key=os.getenv("SPRINGER_OA_API_KEY"),
        springer_meta_api_key=os.getenv("SPRINGER_META_API_KEY"),
        http_timeout=60.0,
        mineru_backend=os.getenv("MINERU_BACKEND", "api"),
        mineru_api_token=(
            os.getenv("MINERU_API_TOKEN") or os.getenv("MINERU_API_KEY") or os.getenv("MINERU_API")
        ),
        mineru_api_model=os.getenv("MINERU_API_MODEL", "vlm"),
        mineru_api_timeout=float(os.getenv("MINERU_API_TIMEOUT", "600")),
        crossref_mailto=os.getenv("CROSSREF_MAILTO"),
        openalex_api_key=os.getenv("OPENALEX_API_KEY"),
        ieee_api_key=os.getenv("IEEE_API_KEY"),
        ieee_api_enabled=os.getenv("IEEE_API_ENABLED", "true").strip().lower() in {"1", "true", "yes"},
        wiley_api_key=(os.getenv("WILEY_API_KEY") or os.getenv("Wiley_API_KEY")
                       or os.getenv("WILEY_TDM_API_KEY")),
        unpaywall_email=os.getenv("UNPAYWALL_EMAIL"),
        elsevier_insttoken=os.getenv("ELSEVIER_INSTTOKEN") or os.getenv("ELSEVIER_INST_TOKEN"),
    )


def require_elsevier_api_key(
    settings: Settings,
) -> str:
    if not settings.elsevier_api_key:
        raise ConfigError("ELSEVIER_API_KEY is not configured.")

    return settings.elsevier_api_key


def require_springer_oa_api_key(
    settings: Settings,
) -> str:
    if not settings.springer_oa_api_key:
        raise ConfigError("SPRINGER_OA_API_KEY is not configured.")

    return settings.springer_oa_api_key


def require_springer_meta_api_key(
    settings: Settings,
) -> str:
    if not settings.springer_meta_api_key:
        raise ConfigError("SPRINGER_META_API_KEY is not configured.")

    return settings.springer_meta_api_key


def redact_error(text: str) -> str:
    """Never expose keys, bearer tokens or signed object-store URLs in diagnostics."""
    import re

    for name, value in os.environ.items():
        if (
            value
            and len(value) >= 8
            and (
                name.upper() == "MINERU_API"
                or any(part in name.upper() for part in ("KEY", "TOKEN", "SECRET"))
            )
        ):
            text = text.replace(value, "[REDACTED]")
    text = re.sub(r"https?://[^\s]+", "[URL REDACTED]", text)
    return re.sub(r"(?i)Bearer\s+[^\s]+", "Bearer [REDACTED]", text)
