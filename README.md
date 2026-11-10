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
