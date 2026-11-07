# Twinkly Control Center voor Home Assistant

Lokale Home Assistant OS-app voor RGB- en RGBW-Twinkly-verlichting met een webpaneel en muziekeffecten. Versie 0.1.28 is een proefversie. Beschikbare modi verschillen per model en firmware. Het is verstandig om op één RGB- en één RGBW-controller te beginnen en vervolgens de rest toe te voegen.

## Installeren

1. Open in Home Assistant **Instellingen → Apps → Appwinkel → ⋮ → Repositories**.
2. Voeg `https://github.com/ferrynl/ha-twinkly` toe. Zoek **Twinkly Control Center**, installeer de app en start hem.
3. Open de webinterface en kies **Zoeken op netwerk**. Broadcast werkt binnen hetzelfde subnet. Gebruik **IP toevoegen** bij gemiste apparaten en reserveer de adressen in DHCP.
4. Test aan/uit, kleur en dimmen per apparaat. **Aan** herstelt de laatst gebruikte modus als die bekend is. Anders probeert de app een warme vaste kleur en daarna alternatieve apparaatmodi. Gebruik **Kleur** voor een vaste RGB-kleur. Kies **Effecten laden** op een apparaatkaart om de opgeslagen Twinkly-films en ingebouwde effecten van dat apparaat te zien. Gebruik **Afspelen op lamp** om het echte effect te zien. Je kunt per lamp herkenbare namen bewaren in je browser. Cloud- en galerie-effecten zijn beschikbaar zodra de officiële app ze als lokaal effect naar de controller heeft geschreven.

## Music Assistant en LedFx

Draait LedFX met Sendspin op dezelfde Home Assistant-host? Klik in Twinkly Control Center op **Music Assistant koppelen**. De app zoekt de Sendspin-server, kiest die als actieve audiobron in LedFX en maakt zo nodig één DDP-uitgang met een starteffect aan. Voeg daarna **LedFx Twinkly** toe aan de afspeelgroep in Music Assistant. Onder **Muziekstijl** kies je een LedFX-effect voor de gedeelde uitgang. Kies **Stijl toepassen** om het effect te wisselen. De stappen hieronder zijn ook handmatig uitvoerbaar.

1. Installeer LedFx met Sendspin-ondersteuning die past bij je Music Assistant-versie. Zie de [Sendspin-handleiding van LedFx](https://docs.ledfx.app/en/latest/settings/sendspin.html).
2. Voeg in LedFx onder **Settings → Features** een Sendspin-server toe. Selecteer die onder **Settings → Audio**. Zet de LedFx-speler aan in Music Assistant en voeg hem toe aan een afspeelgroep met een compatibele speaker.
3. Maak in LedFx één **DDP**-apparaat met **120 pixels**, **RGB**, poort **18490** en als doel **127.0.0.1** als LedFx en Twinkly Control Center dezelfde host-netwerkruimte gebruiken. Stel een audio-effect in op dat DDP-apparaat.
4. Draait LedFx op een andere host, stel dan als DDP-doel het LAN-IP van Home Assistant in. Zet in de configuratie van Twinkly Control Center `ddp_source` op het IPv4-bronadres van LedFx zoals Home Assistant het ontvangt, en herstart de app.
5. Start muziek in Music Assistant en kies **Muziek** bij één lamp of bij **Alle lampen**. De status bovenaan toont of er DDP-frames binnenkomen. **Stop muziek** probeert de voorgaande modus te herstellen. Bij wegvallende frames gebeurt dit ook. Bij stilte kan LedFx zwarte frames blijven sturen.

DDP is UDP zonder authenticatie. Laat de poort binnen het lokale netwerk en gebruik een vertrouwde LedFx-bron. De webinterface loopt via Home Assistant Ingress. Gebruik bij voorkeur één app tegelijk om de modus van een lamp te wijzigen.

## Netwerk en caching

- Apparaatnaam, ledprofiel, pixelcount en IP-adres blijven in `/data/devices.json` bewaard. Een statusupdate van het webpaneel leest alleen de cache.
- Eén DDP-frame voedt alle lampen. Elke lamp houdt zijn eigen lokale sessie en een vooraf berekende pixelmapping. Alleen het nieuwste frame wordt bewaard.
- Standaard maximaal 20 frames per seconde per lamp, instelbaar van 5 tot 25. Een lokaal UDP-pakket gaat naar elke lamp of per fragment bij grotere apparaten. De realtime modus wordt ongeveer elke twee seconden gecontroleerd.
- Tot acht gelijktijdige apparaatoperaties. Bij een netwerkfout wacht de lamp vijf seconden voordat ze weer frames probeert te verwerken. De overige lampen houden hun eigen uitzendlus.
- Gedeelde animatie over maximaal 40 geregistreerde controllers, met 20 als beoogde opstelling. Praktische framerate hangt af van wifi, firmware en de lengte van de strings.

De app verdeelt hetzelfde effect over de ledvolgorde per controller. Via **Ledkaart laden** bekijk je de door de controller opgeslagen 2D- of 3D-ledposities. Een 3D-kaart kan worden gedraaid. De kaart is alleen-lezen. Twinkly-groepsbeheer en de Twinkly Music-dongle vallen buiten deze proefversie.

## Als zoeken of bedienen niet werkt

Stel indien nodig `discovery_broadcast` in op het broadcastadres van je eigen LAN en herstart de app. Gebruik vanuit de Home Assistant Terminal `curl -v --max-time 5 http://TWINKLY_IP/xled/v1/gestalt` en vervang TWINKLY_IP door het adres van de lamp. Als toevoegen lukt maar bedienen faalt, toont de webinterface de fout per apparaat.

## Groepen en effectafbeeldingen

Maak onder **Groepen** een groep met een naam en de gewenste lampen. Bedien aan/uit, kleur, helderheid en muziek voor die selectie, of pas de leden later aan.

Kies bij een effect **Afbeelding uploaden** en selecteer een JPG, PNG of WebP van maximaal 10 MB. De browser verkleint de afbeelding naar een stilstaand JPEG-voorbeeld. Groepen en voorbeelden blijven in de appdata staan en zijn zichtbaar op andere apparaten die dezelfde Home Assistant-installatie gebruiken.

## Muziekvoorbeeld

Kies een muziekstijl en klik **Stijl toepassen**. **Livevoorbeeld** toont de RGB-uitvoer van LedFX als lichtbalk. Met **Gifje opnemen** neem je drie seconden van de ontvangen frames op. Het voorbeeld verschijnt in het dashboard en kan worden gedownload. Beide functies hebben actieve LedFX-frames nodig en kunnen ook worden gebruikt voordat je Muziek op een Twinkly-lamp inschakelt.

## Apparaatinfo

Klik op **Apparaatinfo laden** bij een lamp. De app leest model, firmware, ledgegevens, netwerkstatus en RSSI uit voor zover de controller die rapporteert. De diagnose wordt één minuut gecachet. Ontbrekende wifi-velden krijgen geen geschatte waarde.

Modelkaarten gebruiken de productcode uit de Twinkly-API. Voor bekende Strings RGB+W- en Line-codes toont de kaart een officiële foto van de productreeks, bij het eerste gebruik opgehaald vanaf Twinkly en daarna uit de lokale appdata geladen. Een reeksfoto kan een andere uitvoering tonen. Onbekende codes krijgen alleen hun modelcode.

De actieve muziekstijl wordt na een geslaagde LedFX-koppeling of stijlwijziging centraal bewaard. Andere browsers tonen deze stijl automatisch. Na een update vanaf een oudere versie verschijnt de status zodra je een stijl toepast of Music Assistant opnieuw koppelt.

## Scènes, masterfader en stilte

De scènepads bevatten Kerst rustig, Trance en Alles uit. Sla ook eigen scènes op met de gekozen groep, muziekstijl en masterstand. De master regelt de helderheid van alle muziekframes. Klik op Toepassen om een gewijzigde stand op te slaan. Een geopende ledkaart toont muziekframes op de gemeten ledposities.

Kies in de groepsinstellingen wat er gebeurt bij wegvallende of enkele seconden volledig zwarte LedFX-frames: vorige modus, warm wit of uitfaden. Bij overlappende groepen wint de eerste ingestelde afwijkende regel. Als LedFX tijdens stilte gekleurde frames blijft sturen, kan de app de stilte niet herkennen.

Het **Nu speelt**-scherm toont titel, artiest en album uit de Sendspin-metadata die LedFX ontvangt. De hoes verschijnt wanneer LedFX een lokale hoes heeft opgeslagen. De weergave werkt met LedFX op dezelfde host en vereist dat Music Assistant trackgegevens naar de gekoppelde speler stuurt.

Het tv-scherm kan ook de afbeelding uit Home Assistant tonen. De app zoekt een actieve speler met dezelfde titel als LedFX. Stel bij **Configuratie** desgewenst `media_player` in op de exacte entiteit, bijvoorbeeld `media_player.woonkamer`. Het scherm toont lokale hoezen en ondersteunde YouTube-miniaturen.

Gebruik **Tv-bron** bij het scherm om rechtstreeks een Home Assistant-mediaspeler te kiezen. **Automatisch** blijft de optie om de track op basis van LedFX te koppelen. De keuze wordt centraal bewaard. De instelling `media_player` dient als beginwaarde zolang je nog geen keuze in het mengpaneel hebt opgeslagen.

Het mengpaneel heeft twee pagina’s. **Bediening** bevat licht, muziek, tv, scènepads, groepsbediening en apparaten. **Instellingen** bevat taal, Music Assistant, tv-bron, apparaatdetectie en beheer van groepen, scènes en effectafbeeldingen.

Het Twinkly-beeldmerk is lokaal opgenomen als transparant SVG, gebaseerd op [Simple Icons](https://github.com/simple-icons/simple-icons/blob/develop/icons/twinkly.svg). Het merk is van Twinkly.

De kop gebruikt het volledige [officiële Twinkly-logo](https://twinkly.com/cdn/shop/files/Twinkly_Logo_White.svg) met een gouden kleurverloop. De add-on haalt het SVG bij de eerste weergave op en bewaart het in de lokale appdata. Het bestaande kleine beeldmerk blijft het icoon van het browsertabblad.

De **Live effectengalerij** streamt acht eigen patronen naar één lamp, een groep of alle lampen. Ze gebruiken geen opslagplaats op de controller. Kies **Stop live-effect** om de vorige lampmodus te herstellen.

De mengtafel bevat een GIF-bibliotheek. Upload een GIF, maak een GIF uit een live patroon of importeer een rechtstreekse HTTPS-URL als die site browserdownloads via CORS toestaat. De bibliotheek bewaart maximaal 30 GIF’s van elk maximaal 512 KiB en 120 frames. De app vertaalt de GIF-kleuren naar één rij voor de leds. Je kunt het origineel weer downloaden.

Bij **Importeer URL** kun je ook een gewone GIPHY-deellink plakken. De add-on haalt een geschikte GIF-versie op bij GIPHY en slaat die lokaal op.
