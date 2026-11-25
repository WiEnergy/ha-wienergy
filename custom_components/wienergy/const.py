"""Constants for the WiEnergy integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "wienergy"
MANUFACTURER: Final = "EEG WiEnergy"

DEFAULT_BASE_URL: Final = "https://api.eeg-wienergy.at"
WEB_APP_URL: Final = "https://api.eeg-wienergy.at/ueberschuss.html?eg={community_id}"

CONF_COMMUNITY_ID: Final = "community_id"
CONF_PARTICIPANT_ID: Final = "participant_id"
CONF_MIN_CERTAINTY: Final = "min_certainty"

# Polling: the API recommends 5 minutes for forecast/windows and
# 60 seconds for signals. Files are regenerated roughly every 30 minutes,
# so 5 minutes for everything is plenty and stays far below all limits.
UPDATE_INTERVAL: Final = timedelta(minutes=5)
SIGNAL_HOURS: Final = 24

# Certainty levels, ordered from weakest to strongest.
CERTAINTY_ORDER: Final = ["none", "possible", "likely", "certain"]
DEFAULT_MIN_CERTAINTY: Final = "likely"

LEVELS: Final = ["surplus", "balanced", "deficit", "unavailable", "expired"]

# Fallback list (Einbindung der Prognose, v3.5) if the community list
# cannot be fetched during setup.
KNOWN_COMMUNITIES: Final = {
    "CC101028": "EEG Wienergy (BEG)",
    "RC104940": "Schwarzlackenau",
    "RC104942": "Floridsdorf",
    "RC104945": "Donaufeld",
    "RC106901": "Bruckhaufen",
    "RC107203": "Kagran",
    "RC107210": "Währing",
    "RC107211": "Heiligenstadt",
    "RC107212": "Stadlau",
    "RC107213": "Aspern",
    "RC107402": "Stammersdorf",
    "RC107432": "Fichtengasse",
    "RC107565": "Hernals",
}
