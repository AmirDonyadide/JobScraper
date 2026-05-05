"""
Helpers for loading user-editable scraper configuration files.

Keep the scraper workflow in linkedin_job_scraper.py, and keep the words and
search filter values that non-developers may edit in keywords.txt and
filters.json.
"""

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
KEYWORDS_FILE = BASE_DIR / "keywords.txt"
FILTERS_FILE = BASE_DIR / "filters.json"


class ConfigFileError(RuntimeError):
    """Raised when a required user-editable config file is missing or invalid."""


def load_keywords(path: Path = KEYWORDS_FILE) -> list[str]:
    if not path.exists():
        raise ConfigFileError(
            f"Missing {path.name}. Add one keyword per line in that file."
        )

    keywords = []
    for line in path.read_text(encoding="utf-8").splitlines():
        keyword = line.strip()
        if keyword and not keyword.startswith("#"):
            keywords.append(keyword)

    if not keywords:
        raise ConfigFileError(f"{path.name} does not contain any keywords.")

    return keywords


def load_filter_config(path: Path = FILTERS_FILE) -> dict[str, Any]:
    if not path.exists():
        raise ConfigFileError(
            f"Missing {path.name}. Add search and final filter settings there."
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigFileError(f"{path.name} is not valid JSON: {e}") from e

    if not isinstance(data, dict):
        raise ConfigFileError(f"{path.name} must contain a JSON object.")

    return data


def config_section(config: dict[str, Any], section: str) -> dict[str, Any]:
    value = config.get(section, {})
    return value if isinstance(value, dict) else {}


def config_str(
    config: dict[str, Any], section: str, name: str, default: str = ""
) -> str:
    value = config_section(config, section).get(name, default)
    if value is None:
        return default
    return str(value).strip()


def config_int(
    config: dict[str, Any], section: str, name: str, default: int
) -> int:
    value = config_section(config, section).get(name, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        print(
            f"⚠ Invalid integer for {section}.{name}={value!r}, using {default}."
        )
        return default


def config_list(
    config: dict[str, Any], section: str, name: str, default: list[str]
) -> list[str]:
    value = config_section(config, section).get(name, default)

    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, list):
        items = value
    else:
        print(f"⚠ Invalid list for {section}.{name}, using defaults.")
        items = default

    return [
        str(item).strip()
        for item in items
        if item is not None and str(item).strip()
    ]
