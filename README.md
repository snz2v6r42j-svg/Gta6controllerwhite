# GTA 6 DualSense White — Telegram-voorraadtracker

Automatische controles voor de officiële witte GTA VI DualSense-controller bij PlayStation Direct, MediaMarkt, Saturn, Amazon.de, Müller, Euronics, OkaySoft, Galaxus en Cyberport in Duitsland.

## Activeren

1. Maak een bot via [@BotFather](https://t.me/BotFather) en stuur zelf `/start` naar die bot.
2. Vind je persoonlijke chat-ID via de [Telegram Bot API](https://core.telegram.org/bots/api#getupdates): open `https://api.telegram.org/bot<JOUW_TOKEN>/getUpdates` privé en lees `message.chat.id`. Deel die URL of de bot-token nooit.
3. Zet bij deze repository onder **Settings → Secrets and variables → Actions** twee repository secrets:
   - `TELEGRAM_BOT_TOKEN` — bot-token uit BotFather
   - `TELEGRAM_CHAT_ID` — numerieke chat-ID
4. Ga naar **Actions → GTA 6 White DualSense voorraadcheck → Run workflow** en zet **test_message** op `true`. Controleer of je Telegram-testbericht aankomt.
5. Start nogmaals met `test_message` uit om de winkelpagina's te controleren. De geplande checks lopen daarna ongeveer elke 10 minuten, met mogelijke vertraging door GitHub.

De bot waarschuwt bij een **mogelijke** voorraadindicatie, niet bij een gegarandeerde bestelling. Dynamische sites en botbeveiliging kunnen scans verhinderen; die krijgen de status `unknown`. Kijk altijd zelf naar prijs, verzendbaarheid en betaalpagina. De bot koopt nooit zelf iets.

## Betrouwbaarheid en wat de status betekent

- **possible**: De productpagina én (voor OkaySoft) de categorie tonen voldoende signalen voor een mogelijk bestelbare controller. De koopbaarheid moet je nog zelf controleren.
- **out**: Een expliciete uitverkochtmelding op een voor dit product relevante pagina.
- **unknown**: De winkel blokkeert de automatische controle, de pagina laadt dynamisch of bevat onvoldoende productinformatie. *Dit is geen bewijs van uitverkocht.*
- Bij OkaySoft wordt het productscherm **altijd** met de bijbehorende categoriepagina vergeleken. Een verzenddatum of een verouderde voorbestelknop veroorzaakt **geen** voorraadmelding meer.
- In de **GitHub Actions**-uitvoering staat een overzicht van de status per winkel. Veel Duitse webshops blokkeren aanvragen vanuit GitHub met HTTP 403; dit omzeilen we niet met CAPTCHA-bypasses. Daardoor is de monitoring niet gegarandeerd volledig.

De eerste echte diagnose liet zien dat OkaySoft uitleesbaar was, maar op 'out' stond. De overige winkels waren vaak 'unknown'. Voeg bij voorkeur ook de eigen meldingen van winkels of een gespecialiseerde voorraadmeldingsdienst toe als tweede kanaal.

## Privacy en kosten
- GitHub Actions is op publieke repositories gratis met de gebruikelijke GitHub-hosted runners; planwijzigingen of gebruikslimieten kunnen van toepassing zijn.
- Bewaar je Telegram-token uitsluitend als repository secret, nooit in de code, Issues of chats.
- Je kunt de checks stoppen via **Actions → Disable workflow**.
- Gebruik geen captcha-omzeiling. Respecteer winkellimieten.

Officiële Sony-adviesprijs: €84,99 (voorraad en winkelprijzen kunnen afwijken).

## Tests
Run: `python -m unittest discover -s tests -v`

De code is een startversie. Productpagina's en voorraadindicatoren moeten worden gecontroleerd via een eerste echte GitHub Actions-run.


## Amazon.de televisieprijsfouten — categoriebreed

Deze tweede functie gebruikt **geen specifieke productlinks of ASINs**. Hij volgt recente prijswijzigingen bij televisies op Amazon.de, en stuurt een Telegram-melding wanneer alle criteria gelden:

- De vorige prijs én het 90-daagse gemiddelde zijn ieder minstens **€500**.
- De nieuwe Amazon-prijs is minstens **80% lager** dan beide bedragen (voorbeeld: €600 → €100).
- De prijsverandering is maximaal **24 uur oud**, en de Keepa-update maximaal **12 uur oud**.
- Het is een complete televisie, geen afstandsbediening, muurbeugel of accessoire.
- Alleen de **Amazon-zelf-verkochte prijs** is geselecteerd; gebruikte en marketplace-prijzen tellen niet mee.
- Een ASIN wordt niet steeds opnieuw gemeld, behalve wanneer de prijs nog minstens 5% verder daalt.

**Opzet:** `tv_price_errors.py`, `tv_price_errors_config.json`, `tv_price_state.json` en `.github/workflows/tv-price-errors.yml`. De workflow is ingepland om elke tien minuten te controleren (onderhevig aan GitHub-vertraging).

**Op dit moment niet live geactiveerd:** hiervoor is een **betaalde Keepa API-sleutel** nodig. Maak een Keepa API-abonnement aan via https://keepa.com/api en sla de sleutel op als repository secret `KEEPA_API_KEY` bij [GitHub Actions Secrets](https://github.com/snz2v6r42j-svg/Gta6controllerwhite/settings/secrets/actions). Bewaar de sleutel NOOIT in de repository of chat. Het bestand `tv_price_errors_config.json` bevat de instellingen; je hoeft geen productlijst bij te houden.

De scanner gebruikt Keepa **Browsing Deals** (5 API-tokens per paginaverzoek), met drie zoekopdrachten en maximaal twee pagina's per zoekopdracht. Maximaal ongeveer **30 API-tokens per controle** (als alle pagina's nodig zijn). Controleer of je Keepa-abonnement dat kan leveren. De scanner vindt de Keepa-prijswijzigingen die in recente resultaten staan, **niet gegarandeerd alle televisies op Amazon.de**. Een prijsfout kan voorbij zijn voordat Keepa hem registreert. De melding is nooit een garantie dat Amazon de prijs bij het afrekenen nog hanteert.

Bij ontbrekende `KEEPA_API_KEY` stuurt de geplande workflow **geen enkele** API-aanvraag of prijsfoutmelding, en legt hij in het GitHub Actions-overzicht uit waarom. De bestaande GTA VI-voorraadtracker blijft onafhankelijk werken.

De extra specifieke-productenmodule (`amazon_price_errors.py` met `amazon_watchlist.json`) is optioneel en heeft geen actieve workflow. Voor jouw voorkeur geldt de categoriebrede tv-scanner hierboven.
