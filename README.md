# WiEnergy für Home Assistant

Überschussprognose der Erneuerbare-Energie-Gemeinschaft **WiEnergy** als fertige Home-Assistant-Integration: Ampel, Bilanz, Überschussfenster und ein Ja/Nein-Sensor „Gemeinschaftsüberschuss“ für Automationen – ohne YAML und ohne Templates.

Die Integration schaltet selbst nichts. Sie liefert nur Signale; Wallbox, Wärmepumpe, Boiler oder Speicher steuert ihr mit euren eigenen Automationen. Die Prognose ist ohne Gewähr.

## Installation

**Über den Marketplace (Home Assistant 2026.11 oder neuer):** Einstellungen → Marketplace → nach „WiEnergy“ suchen → Herunterladen → Home Assistant neu starten.

Solange WiEnergy noch nicht im Katalog steht, über diesen Link hinzufügen:

[![Im Marketplace öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=WiEnergy&repository=ha-wienergy&category=integration)

**Manuell:** Ordner `custom_components/wienergy` in euer Home-Assistant-Verzeichnis `config/custom_components/` kopieren und neu starten.

## Einrichtung

Einstellungen → Geräte & Dienste → Integration hinzufügen → **WiEnergy**.

1. **API-Key leer lassen** → Gemeinschaft aus der Liste wählen (z. B. Bruckhaufen). Das öffentliche Signal braucht keine Anmeldung.
2. **Mit persönlichem API-Key** (ab Ausbaustufe 2) → zusätzlich euer individuelles Budget `recommendedMaxW` – die Zusatzleistung, die für euch aus Gemeinschaftsüberschuss gedeckt ist.

Mehrere Gemeinschaften lassen sich parallel einrichten.

## Entitäten

| Entität | Inhalt |
|---|---|
| Gemeinschaftsüberschuss (binär) | **an**, wenn die laufende Viertelstunde Überschuss mit ausreichender Sicherheit hat. Bei veralteten Daten **aus**. Für Automationen gedacht. |
| Ampel | `surplus` / `balanced` / `deficit` / `unavailable` / `expired` (veraltet, z. B. nachts) |
| Sicherheit | `certain` / `likely` / `possible` / `none` |
| Bilanz Gemeinschaft | Überschuss (+) bzw. Defizit (−) in W. Attribut `forecast`: Viertelstunden der nächsten 24 h für Diagramme |
| Empfohlene Zusatzleistung | `recommendedMaxW` in W (nur mit API-Key) |
| Erzeugung / Verbrauch / Deckungsgrad | Prognose der Gemeinschaft für die laufende Viertelstunde |
| Überschuss heute noch | erwarteter Überschuss bis Mitternacht in kWh – nützlich, um das Laden des Speichers aufzuschieben |
| Nächstes Fenster Beginn / Ende / Energie | laufendes oder nächstes Überschussfenster; Attribut `windows` mit allen Fenstern |
| Prognose erstellt / Signal gültig bis | Diagnose |

Die Integration hält sich an die Spielregeln aus „Einbindung der Prognose“: Abfrage alle 5 Minuten, Auswahl der Viertelstunde nach der Uhrzeit (nicht nach `current`), `expiresAt` und `unavailable` werden beachtet. Die Zustände wechseln minutengenau zur vollen Viertelstunde, auch ohne neuen Abruf.

### Optionen

Unter **Konfigurieren** wird festgelegt, ab welcher Sicherheit der Überschuss-Sensor einschaltet:

- **wahrscheinlich** (Standard) – für Wäsche, Geschirrspüler, Wallbox
- **sicher** – nur bei sehr sicherem Überschuss
- **möglich** – für Heizstab oder Boiler

## Beispiel: Boiler mit Gemeinschaftsstrom

```yaml
automation:
  - alias: "Boiler mit Gemeinschaftsstrom"
    triggers:
      - trigger: state
        entity_id: binary_sensor.bruckhaufen_gemeinschaftsuberschuss
        to: "on"
        for: "00:05:00"
    actions:
      - delay:
          minutes: "{{ range(1, 9) | random }}"   # nicht alle gleichzeitig
      - action: switch.turn_on
        target:
          entity_id: switch.boiler
  - alias: "Boiler aus ohne Überschuss"
    triggers:
      - trigger: state
        entity_id: binary_sensor.bruckhaufen_gemeinschaftsuberschuss
        to: "off"
        for: "00:10:00"
    actions:
      - action: switch.turn_off
        target:
          entity_id: switch.boiler
```

Die Entitäts-IDs hängen vom Namen der Gemeinschaft ab – unter Einstellungen → Entitäten nachsehen. Eigenen PV-Überschuss weiter vorrangig nutzen.

## English

Home Assistant integration for the surplus forecast of the WiEnergy renewable energy communities (Vienna, Austria). Provides a traffic-light sensor, community balance, surplus windows and a binary "community surplus" sensor for automations. Read-only; no API key needed for the public community signal.

## Hinweise

- Wetterdaten der Prognose: [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0)
- Fragen: info@eeg-wienergy.at · Fehler bitte als [Issue](https://github.com/WiEnergy/ha-wienergy/issues) melden
- Lizenz: MIT
