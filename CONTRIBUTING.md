# Testen en releases

Voeg voor elke nieuwe of gewijzigde functie een regressietest toe. Werk bestaande tests bij als het verwachte gedrag verandert. Voeg API- en dashboardtests toe in `twinkly/test_dashboard.py` of een nieuw `test_*.py`-bestand in dezelfde map. Zet tests voor releases en installatiemetadata in `scripts/test_*.py`.

- `docker build twinkly` voert de Python- en dashboardtests uit.
- `python -m unittest discover -s scripts -v` test de installatievarianten. Installeer vooraf `PyYAML==6.0.2`.
- GitHub Actions bouwt en start beide varianten op amd64 en arm64 en controleert de muziek-GIF’s en het dashboard.

Verhoog `version` in `twinkly/config.yaml` en voeg een bijbehorende sectie toe bovenaan `twinkly/CHANGELOG.md`. Open na het samenvoegen **Actions → Twinkly-tests en release → Run workflow** op `main`. Kies `beta` plus een uniek oplopend bètanummer voor die versie, of `stable`. De workflow publiceert de geteste commit pas na beide architectuurchecks. Maak releases via deze workflow. De centrale appwinkel haalt de releases op en gebruikt voor de bèta een aparte appmap.
