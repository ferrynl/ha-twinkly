# Wijzigingslogboek

## 0.1.30

- Voeg 50 ingebouwde livepatronen toe in vijf nieuwe categorieën.
- Gebruik dezelfde categorieën bij het maken van GIF’s.

## 0.1.29

- Herken ook GIPHY-afbeeldingslinks met een versietoken of met i.giphy.com.
- Probeer een extra kleine GIPHY-versie als de grotere versie niet past.

## 0.1.28

- Importeer gewone GIPHY-deellinks en directe GIPHY-afbeeldingslinks in de lokale GIF-bibliotheek.

## 0.1.27

- Verplaats de live-effectengalerij naar de mengtafel.
- Upload, maak, importeer en download GIF’s in een lokale bibliotheek.
- Speel GIF-kleuren rechtstreeks af op lampen of groepen.

## 0.1.26

- Voeg acht live patronen toe voor een lamp, groep of alle lampen zonder ze op de controllers op te slaan.

## 0.1.25

- Maak het tv-scherm compacter en voeg een live lichtmonitor met uitgangsniveau toe.
- Toon welke lampen op muziek staan en spring met één klik naar hun bediening.
- Voeg vijf snelkleuren toe voor alle lampen.

## 0.1.24

- Plaats Control Center in goud direct onder het Twinkly-logo en verwijder de losse kopteksten.

## 0.1.23

- Toon het volledige officiële Twinkly-logo in goud op een transparante achtergrond.
- Bewaar het SVG na de eerste download lokaal.

## 0.1.22

- Hernoem de app naar Twinkly Control Center.
- Voeg een lokaal, transparant Twinkly-beeldmerk toe aan het dashboard en het browsertabblad.

## 0.1.21

- Splits het mengpaneel in Bediening en Instellingen.
- Groepeer de lampbediening, scènepads en muziekbediening in een compactere responsieve indeling.
- Verplaats koppelingen, apparaatdetectie en groeps-, scène- en effectbeheer naar Instellingen.

## 0.1.20

- Gebruik dezelfde lokale hoesafbeelding als de Home Assistant-mediaspelerkaart.
- Geef bij automatische bronselectie voorrang aan een overeenkomende speler die een hoes meldt.

## 0.1.19

- Toon ook YouTube-miniaturen van de officiële afbeeldingsserver naast de lokale hoesafbeeldingen.
- Gebruik een beschikbare directe hoes als terugvaloptie als de lokale afbeelding faalt.
- Verwijder het automatisch laden van externe videobronnen.

## 0.1.18

- Kies de Home Assistant-mediaspeler rechtstreeks bij het tv-scherm.
- Bewaar de keuze centraal zonder herstart en bied automatische bronselectie aan.

## 0.1.17

- Maak van Nu speelt een tv-scherm met grotere hoesweergave.
- Gebruik de afbeelding van een overeenkomende Home Assistant-mediaspeler of een ingestelde speler.
- Toon videobediening als de speler een directe HTTPS MP4- of WebM-bron rapporteert.

## 0.1.16

- Toon de huidige Music Assistant-track in de mengtafel via LedFX Sendspin-metadata.
- Toon de albumhoes wanneer LedFX een lokale versie beschikbaar stelt.

## 0.1.15

- Voeg scènepads en eigen scènes per groep toe.
- Bewaar een centrale masterhelderheid voor muzieklicht.
- Toon muziekframes op de ledkaart en voeg stiltegedrag per groep toe.

## 0.1.14

- Bewaar de actieve muziekstijl centraal en toon die op alle browsers en na herstarts.
- Houd een nog niet toegepaste stijlkeuze apart van de actieve stijl.

## 0.1.13

- Vergroot de productfoto en verwijder de productlink en de toelichting onder de modelnaam.
- Bewaar opgehaalde productfoto’s lokaal tussen herstarts.

## 0.1.12

- Herken Twinkly Strings en Line op basis van de modelcode en toon bij ondersteunde reeksen een officiële referentiefoto.
- Lees bij bestaande apparaten de modelcode op de achtergrond uit.

## 0.1.11

- Verzend realtimeframes via één UDP-socket met een automatisch toegewezen bronpoort. Dit voorkomt een poortconflict wanneer meerdere Twinkly-lampen tegelijk op muziek reageren.

## 0.1.10

- Schermbrede, responsieve DJ-mengtafel met licht- en muziekbediening.
- Apparaatdiagnose met firmware, hardware, ledgegevens en wifi-informatie als de controller die meldt.

## 0.1.9

- Voeg Lichtloop, Muziekbanden, Blade Power+, Frequentiepuls en Muziekvuur toe.
- Bekijk de echte LedFX-frames als bewegende lichtbalk en neem een downloadbaar gifje op.

## 0.1.8

- Maak, bewerk en verwijder groepen en bedien de gekozen lampen tegelijk.
- Upload, vervang en verwijder eigen afbeeldingen bij lokale effecten.
- Groepen en afbeeldingen blijven bewaard in de appdata.

## 0.1.7

- Lees per controller de opgeslagen ledposities uit en toon die in een ledkaart.
- Draai 3D-kaarten en herken door de controller berekende layouts.
- Hergebruik ledposities twee minuten uit de cache.

## 0.1.6

- Speel het echte effect af op de lamp vanuit de effectkiezer.
- Bewaar herkenbare eigen namen per lamp en effect in je browser.
- Verwijder de illustratieve patronen die geen weergave van het echte effect waren.

## 0.1.5

- Kies een muziekstijl in het dashboard: Energiepuls, Kleurenspectrum, Bas en slag, Kleurgolf of Stroboscoop.
- Pas de stijl toe op alle lampen waarop Muziek is ingeschakeld.

## 0.1.4

- De knoppen Aan en Uit tonen per lamp de laatst gemeten status.
- De app schakelt de kleurmodus via de lokale Twinkly-API en toont meer details bij fouten.
- Lokale effecten hebben klikbare kaarten met illustratieve voorbeeldbeelden.

## 0.1.3

- Vernieuwd dashboard met Nederlands, Engels, Spaans en Duits.
- Aan probeert de laatst gebruikte lichtmodus te herstellen.
- Kleur gebruikt de lokale Twinkly-API.
- Opgeslagen films en ingebouwde effecten zijn per apparaat te laden.

## 0.1.2

- Koppel Music Assistant vanuit het Twinkly Kerst-dashboard.
- Configureer de Sendspin-bron en gedeelde DDP-uitgang in LedFX.

## 0.1.1

- Toon afgewezen opdrachten en netwerkfouten per apparaat.
- Ondersteun een instelbaar broadcastadres voor ontdekking.

## 0.1.0

- Eerste Home Assistant-app voor lokale bediening van RGB- en RGBW-Twinkly-verlichting.
- Zoek apparaten op het netwerk of voeg ze via IP toe.
- Bedien lampen afzonderlijk of tegelijk en stuur muziekeffecten van LedFX door.
