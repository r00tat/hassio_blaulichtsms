# BlaulichtSMS Homeassistant Component

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

![Project Maintenance][maintenance-shield]

Diese Homeassistant Komponente ermöglicht es Alarme und Infos von [Blaulicht SMS](https://blaulichtsms.net/) abzurufen und diese Informationen anzuzeigen. Damit können bei einer Alarmierung Automatisierungen gestartet werden oÄ.

Für die Konfiguration muss ein [Einsatzmonitor](https://start.blaulichtsms.net/de/#/alarm-dashboard/list) konfiguriert werden und dessen Zugangsdaten in der Integration konfiguriert werden.

## Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?category=Integration&owner=r00tat&repository=hassio_blaulichtsms)

1. Füge das HACS Repository hinzu
   1. Falls der Open HACS Repository button nicht funktioniert, kann das Repository manuell hinzugefügt werden:
   2. HACS öffnen
   3. Integrationen öffnen
   4. 3 Punkte und dann "Benutzerdefinierte Repositories" öffnen
   5. `https://github.com/r00tat/hassio_blaulichtsms` als Repository und Kategorie `Integration` auswählen
2. Installiere die Blaulicht SMS Integration
3. Starte Homeassistant neu
4. Füge die Blaulicht SMS Integration mit dem konfigurierten Dashboard Zugangsdaten hinzu

## Development

Setup your environment and start a test container by running `./dev.sh`.

## License

This software is not affiliated with Blaulicht SMS and has been created and maintained by @r00tat.

The software is licensed under [Apache License 2.0](/LICENSE).

---

[hassio_blaulichtsms]: https://github.com/r00tat/hassio_blaulichtsms
[buymecoffee]: https://www.buymeacoffee.com/r00tat
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/r00tat/hassio_blaulichtsms.svg?style=for-the-badge
[commits]: https://github.com/r00tat/hassio_blaulichtsms/commits/main
[exampleimg]: example.png
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/r00tat/hassio_blaulichtsms.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40r00tat-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/r00tat/hassio_blaulichtsms.svg?style=for-the-badge
[releases]: https://github.com/r00tat/hassio_blaulichtsms/releases
