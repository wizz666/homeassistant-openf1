# F1 Live Display — CYD (ESP32-2432S028)

En fysisk F1-racedisplay för **ESP32-2432S028** ("Cheap Yellow Display") som visar live race-data från Home Assistant.

**[🇬🇧 English instructions → README.md](README.md)**

---

## Så här ser det ut

**Sida 0 – Race Live**
```
┌─────────────────────────────────────────┐
│ F1  │  RACE              │         V 23 │  ← flaggfärgad header
├─────────────────────────────────────────┤
│     VER     │     HAM     │     BOT     │
│     P 1     │     P 3     │     P 7     │
│    Leader   │   +3.247s   │  +18.521s   │
│  SOFT  8v   │  MED  15v   │  HARD  22v  │
├─────────────────────────────────────────┤
│  Race Control: INCIDENT AT TURN 8       │
├─────────────────────────────────────────┤
│ touch: byt vy                std/grid > │
└─────────────────────────────────────────┘
```
Headerfärgen ändras med flaggstatus: 🔴 röd flagga, 🟡 gul, 🟠 safety car, 🟢 grön, ⬛ chequered.

**Sida 1 – Mästerskapsställning**
```
┌─────────────────────────────────────────┐
│ F1 2026                        4d 10h   │  ← röd header
├─────────────────────────────────────────┤
│  FORARSTANDINGS  │   KONSTRUKTOR        │
│  1.VER 125p      │   1.RBR 180p         │
│  2.NOR 113p      │   2.MCL 165p         │
│  3.HAM  98p      │   3.FER 150p         │
│  4.LEC  87p      │   4.MER 120p         │
│  5.RUS  76p      │   5.WIL  45p         │
├─────────────────────────────────────────┤
│  4d 10h         touch: race/grid >      │
└─────────────────────────────────────────┘
```

**Sida 2 – Live Grid + AI**
```
┌─────────────────────────────────────────┐
│ LIVE GRID                      V 23     │  ← grön (aktiv) / grå (inaktiv)
├─────────────────────────────────────────┤
│  1.VER Leader S  │  6.LEC  +8.2s H     │
│  2.HAM  +2.1s M  │  7.NOR  +9.5s S     │
│  3.SAI  +3.4s H  │  8.ALO +12.1s M     │
│  4.RUS  +5.1s S  │  9.STR +14.3s H     │
│  5.PIA  +6.8s M  │ 10.TSU +16.0s M     │
├─────────────────────────────────────────┤
│  AI: VER leder suverant – Hamilton...   │
└─────────────────────────────────────────┘
```

**Touch**: Bläddrar sida 0 → 1 → 2 → 0.
**Auto-byte**: Hoppar till Race-sidan när en session startar; återgår till Standings när inactive.

---

## Hårdvara

**ESP32-2432S028** är ett populärt, billigt (~100–150 kr) dev-kort med inbyggd 2,8" ILI9341 320×240 färgdisplay och XPT2046 resistiv pekskärm. Säljs ofta som "CYD" (Cheap Yellow Display).

**Var man köper**: AliExpress, Amazon eller lokala elektronikbutiker.
Sök på: `ESP32-2432S028` eller `ESP32 CYD 2.8 TFT`

### GPIO-pinout (redan konfigurerat i YAML-filen)

| Funktion | GPIO |
|----------|------|
| SPI CLK | 14 |
| SPI MOSI | 13 |
| SPI MISO | 12 |
| Display CS | 15 |
| Display DC | 2 |
| Display Reset | 4 |
| Bakgrundsljus (PWM) | 21 |
| Touch CS | 33 |
| Touch IRQ | 36 |

Ingen inkoppling behövs — allt sitter på kortet.

---

## Krav

- **Home Assistant** med OpenF1 pyscript-integreringen installerad och igång
- **ESPHome**-tillägget installerat i Home Assistant (via Tilläggskatalogen)
- USB-kabel för den första flashningen (USB-C eller micro-USB beroende på kortrevision)
- Wi-Fi 2,4 GHz-nätverk

---

## Installation

### Steg 1 — Installera ESPHome

I Home Assistant, gå till **Inställningar → Tillägg → Tilläggskatalogen** och installera **ESPHome**.

### Steg 2 — Lägg till secrets

Öppna ESPhomes secrets-fil (`esphome/secrets.yaml` i din HA-konfig) och lägg till:

```yaml
wifi_ssid: "DittNätverksnamn"
wifi_password: "DittWiFiLösenord"
api_encryption_key: "din32bytebase64nyckel=="   # generera nedan
ota_password: "välj-ett-lösenord"
```

**Generera en API-krypteringsnyckel:**
I ESPHome-dashboarden, klicka **Secrets** → nyckeln genereras automatiskt, eller kör:
```bash
python3 -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"
```

### Steg 3 — Kopiera YAML-filen

Kopiera `f1_display.yaml` till din Home Assistants ESPHome-mapp:
```
config/esphome/f1_display.yaml
```

Eller klistra in innehållet direkt i ESPHome-dashboardens editor.

### Steg 4 — Flasha enheten

1. Anslut ESP32-2432S028 till din dator via USB
2. Öppna ESPHome-dashboarden i Home Assistant
3. Hitta **f1-display** → klicka **Install** → välj **Plug into this computer**
4. Vänta på kompilering och flashning (~2–3 minuter)

> **Senare uppdateringar** kan göras trådlöst via OTA — ingen USB behövs.

### Steg 5 — Lägg till i Home Assistant

Efter flashningen dyker enheten upp under **Inställningar → Enheter och tjänster** för godkännande. Klicka **Konfigurera** och godkänn anslutningen med din `api_encryption_key`.

---

## Konfiguration

Ingen ytterligare konfiguration behövs — displayen läser direkt från sensorerna som skapas av OpenF1 pyscript-integrationen.

### Byta visade förare

Förare konfigureras i **F1 Live → Inställningar**-vyn i dashboarden (eller via `input_number.f1_followed_1/2/3`). Displayen uppdateras automatiskt inom 30 sekunder.

---

## Sensorer som displayen använder

ESPHome-firmwaren prenumererar på dessa Home Assistant-sensorer:

| Sensor | Sida | Beskrivning |
|--------|------|-------------|
| `sensor.f1_session_status` | Alla | Sessionstyp; styr automatiskt sidbyte |
| `sensor.f1_flag` | 0 | Flaggstatus → headerns bakgrundsfärg |
| `sensor.f1_lap` | 0 | Aktuellt varvnummer |
| `sensor.f1_next_session` | 0, 1, 2 | Nedräkning till nästa session |
| `sensor.f1_race_control_msg` | 0 | Senaste Race Control-meddelande |
| `sensor.f1_d1_name` | 0 | Förare 1 förkortning (t.ex. VER) |
| `sensor.f1_d1_position` | 0 | Förare 1 racingposition |
| `sensor.f1_d1_gap` | 0 | Förare 1 gap till ledaren |
| `sensor.f1_d1_compound` | 0 | Förare 1 däcktyp |
| `sensor.f1_d1_tyre_age` | 0 | Förare 1 varv på nuvarande däck |
| `sensor.f1_d2_*` | 0 | Samma som ovan för förare slot 2 |
| `sensor.f1_d3_*` | 0 | Samma som ovan för förare slot 3 |
| `sensor.f1_driver_standings` | 1 | Pipe-separerad förarmästerskapsställning |
| `sensor.f1_constructor_standings` | 1 | Pipe-separerad konstruktörsmästerskapsställning |
| `sensor.f1_grid_display` | 2 | Pipe-separerat komplett startfält (topp 10) |
| `sensor.f1_ai_commentary` | 2 | Senaste AI-kommentarmening |

---

## Felsökning

**Displayen visar "N/A" för alla sensorer**
Enheten har ännu inte synkat med Home Assistant. Vänta 30–60 sekunder efter att både HA och enheten startat. Kontrollera att enheten är godkänd i HA (Inställningar → Enheter).

**"Väntar på race..." på sida 2 trots aktiv session**
`sensor.f1_live_grid` fylls bara när positions- och däckdata finns tillgänglig. Detta tar några varv in i sessionen.

**Enheten dyker inte upp i ESPHome**
Se till att enheten är på samma Wi-Fi-nätverk som Home Assistant. Om den inte kan ansluta skapar den en reservhotspot med namnet **F1Display Fallback** (lösenord: `f1display123`) — anslut till den för att konfigurera om Wi-Fi.

**Touch svarar inte eller triggar på fel position**
Kalibreringsvärdena i YAML:en (`x_min: 200`, `x_max: 3800`, `y_min: 240`, `y_max: 3860`) fungerar för de flesta kort. Om touchen är ur fas, justera dessa värden. Vissa kort behöver även `mirror_y: true` under `transform`.

**Kompileringsfel: "font not found"**
ESPHome laddar ner Roboto från Google Fonts vid kompilering. Se till att din HA-instans har internetåtkomst.

**Displayen är väldigt mörk**
Bakgrundsljuset är konfigurerat till full styrka (`ALWAYS_ON`). Om det ändå är mörkt, kontrollera att GPIO21 inte är kortsluten.

---

## Anpassning

### Ändra teckenstorlek

Redigera `size:`-värdena under `font:`-sektionen. Större text = färre tecken per rad.

### Ändra headerfärger

Redigera `flag_color()`-lambdan i display-sektionen:
```cpp
auto flag_color = [&]() -> Color {
  std::string f = id(f1_flag).state;
  if (f == "RED") return Color(160, 0, 0);      // r, g, b (0–255)
  if (f == "YELLOW") return Color(150, 130, 0);
  // ...
};
```

### Inaktivera en sida

Ändra `% 3` till `% 2` i touch-hanteraren för att bara bläddra igenom 2 sidor:
```cpp
id(current_page) = (id(current_page) + 1) % 2;  // Bara sida 0 och 1
```

### Justera uppdateringsintervall

Displayen ritas om varje sekund. För att minska CPU-belastningen, ändra `update_interval: 1s` till `update_interval: 2s` under `display:`-sektionen.

---

## Stöd projektet

Gillar du det här projektet? En kopp kaffe uppskattas ☕

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/wizz666)
