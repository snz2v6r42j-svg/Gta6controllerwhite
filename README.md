# GTA 6 DualSense White — Telegram-voorraadtracker

Automatische controles voor de officiële witte GTA VI DualSense-controller bij PlayStation Direct, MediaMarkt, Saturn, Amazon.de, Müller en Euronics in Duitsland.

## Activeren

1. Maak een bot via [@BotFather](https://t.me/BotFather) en stuur zelf `/start` naar die bot.
2. Vind je persoonlijke chat-ID via de [Telegram Bot API](https://core.telegram.org/bots/api#getupdates): open `https://api.telegram.org/bot<JOUW_TOKEN>/getUpdates` privé en lees `message.chat.id`. Deel die URL of de bot-token nooit.
3. Zet bij deze repository onder **Settings → Secrets and variables → Actions** twee repository secrets:
   - `TELEGRAM_BOT_TOKEN` — bot-token uit BotFather
   - `TELEGRAM_CHAT_ID` — numerieke chat-ID
4. Ga naar **Actions → GTA 6 White DualSense voorraadcheck → Run workflow** en zet **test_message** op `true`. Controleer of je Telegram-testbericht aankomt.
5. Start nogmaals met `test_message` uit om de winkelpagina's te controleren. De geplande checks lopen daarna ongeveer elke 10 minuten, met mogelijke vertraging door GitHub.

De bot waarschuwt bij een **mogelijke** voorraadindicatie, niet bij een gegarandeerde bestelling. Dynamische sites en botbeveiliging kunnen scans verhinderen; die krijgen de status `unknown`. Kijk altijd zelf naar prijs, verzendbaarheid en betaalpagina. De bot koopt nooit zelf iets.

## Privacy en kosten
- GitHub Actions is op publieke repositories gratis met de gebruikelijke GitHub-hosted runners; planwijzigingen of gebruikslimieten kunnen van toepassing zijn.
- Bewaar je Telegram-token uitsluitend als repository secret, nooit in de code, Issues of chats.
- Je kunt de checks stoppen via **Actions → Disable workflow**.
- Gebruik geen captcha-omzeiling. Respecteer winkellimieten.

Officiële Sony-adviesprijs: €84,99 (voorraad en winkelprijzen kunnen afwijken).

## Tests
Run: `python -m unittest discover -s tests -v`

De code is een startversie. Productpagina's en voorraadindicatoren moeten worden gecontroleerd via een eerste echte GitHub Actions-run.
