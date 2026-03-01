# Home Assistant OpenF1-integration

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Stöd_projektet-F16061?logo=ko-fi&logoColor=white)](https://ko-fi.com/wizz666)

Realtids-F1-data för Home Assistant via det gratis [OpenF1 API](https://openf1.org).

**[🇬🇧 English instructions → README.md](README.md)**

---

## Funktioner

- **Live Race Control** — flaggnotiser (röd, gul, grön, safety car, VSC, chequered) med push-notiser
- **Förarövervakning** — följ upp till 3 förare: position, gap, interval, däck, däckålder
- **Konfigurerbara förare** — byt följda förare när som helst från dashboarden, utan att redigera kod
- **Komplett startfält** — live-positioner, gap och däck för alla 20 förare
- **Mästerskapsställning** — förar- och konstruktörspoäng, uppdateras varje timme
- **AI-kommentator** — en dramatisk mening live-kommentar vid viktiga race-händelser (kräver Groq-nyckel eller Google AI)
- **AI-sessionreferat** — automatiskt ~80-ords referat direkt när sessionen avslutas
- **CYD-display** — valfri ESP32-2432S028 pekskärm (3 sidor: race, standings, live grid)
- **Nästa session-nedräkning** — visar alltid hur lång tid till nästa FP/kval/lopp

## Krav

- Home Assistant 2024.1+
- [Pyscript-integration](https://github.com/custom-components/pyscript) (via HACS)
- Ingen API-nyckel behövs — OpenF1 är gratis och öppet

### Valfritt
- Groq API-nyckel (gratis tier på [console.groq.com](https://console.groq.com)) för AI-funktioner
- ESP32-2432S028 "Cheap Yellow Display" för fysisk display

## Installation

### 1. Installera Pyscript

Installera [pyscript](https://github.com/custom-components/pyscript) via HACS och lägg till i `configuration.yaml`:

```yaml
pyscript:
  allow_all_imports: true
  hass_is_global: true
```

### 2. Kopiera filer

Kopiera dessa filer till din Home Assistant-konfig:

| Fil | Destination |
|-----|------------|
| `openf1.py` | `config/pyscript/openf1.py` |
| `openf1_package.yaml` | `config/packages/openf1_package.yaml` |
| `f1_dashboard.yaml` | `config/dashboards/f1_dashboard.yaml` |

Aktivera packages i `configuration.yaml` om det inte redan är gjort:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

### 3. Registrera dashboarden

Lägg till i `configuration.yaml`:

```yaml
lovelace:
  dashboards:
    f1-live:
      mode: yaml
      title: "F1 Live"
      icon: mdi:racing-helmet
      show_in_sidebar: true
      filename: dashboards/f1_dashboard.yaml
```

### 4. Starta om Home Assistant

Efter omstart visas F1-dashboarden i sidofältet.

## Konfiguration

### Välj dina förare

Gå till **F1 Live → Inställningar** och ange förarnummer för slot 1–3. Sätt 0 för att inaktivera ett slot.

Vanliga nummer 2025/2026:
| Förare | Nummer |
|--------|--------|
| Verstappen | 1 |
| Norris | 4 |
| Hamilton | 44 |
| Leclerc | 16 |
| Sainz | 55 |
| Russell | 63 |
| Piastri | 81 |
| Alonso | 14 |

### AI-kommentator (valfritt)

1. Skaffa en gratis Groq API-nyckel på [console.groq.com](https://console.groq.com)
2. Använder du [Grocery Tracker](https://github.com/wizz666/homeassistant-grocery-tracker) delas nyckeln automatiskt
3. Annars: sätt `input_text.grocery_api_key_groq` till din nyckel
4. Aktivera **AI-kommentator** i AI-vyn på dashboarden

Fallback: om ingen Groq-nyckel finns används `ha_ai_task` (kräver Google AI- eller Anthropic-integration i HA).

## Sensorer

### Session

| Sensor | Beskrivning |
|--------|-------------|
| `sensor.f1_session_status` | inactive / Practice / Qualifying / Race / Sprint |
| `sensor.f1_next_session` | Nedräkning till nästa session (attrs: session_name, circuit, country, date_start) |
| `sensor.f1_flag` | Aktuell flagga: GREEN / YELLOW / RED / SAFETY CAR / VSC / CHEQUERED |
| `sensor.f1_lap` | Aktuellt varv |
| `sensor.f1_race_control_msg` | Senaste Race Control-meddelande |

### Följda förare (slot 1–3)

Ersätt `{n}` med 1, 2 eller 3:

| Sensor | Beskrivning |
|--------|-------------|
| `sensor.f1_d{n}_name` | Förarkortnamn (VER / HAM / etc.) |
| `sensor.f1_d{n}_position` | Aktuell position |
| `sensor.f1_d{n}_gap` | Gap till ledaren |
| `sensor.f1_d{n}_interval` | Gap till bilen framför |
| `sensor.f1_d{n}_compound` | Däck med emoji (🔴 SOFT) |
| `sensor.f1_d{n}_tyre_age` | Varv på aktuella däcken |

### Mästerskap

| Sensor | Beskrivning |
|--------|-------------|
| `sensor.f1_driver_standings` | Pipe-separerad ställning: `1.VER 125p\|2.NOR 113p\|...` |
| `sensor.f1_constructor_standings` | Pipe-separerad: `1.MCL 210p\|2.FER 190p\|...` |

### Fullständigt startfält / AI

| Sensor | Beskrivning |
|--------|-------------|
| `sensor.f1_live_grid` | Antal spårade förare; attr `grid` = lista med alla 20 förare |
| `sensor.f1_grid_display` | Kompakt pipe-sep-sträng för CYD-display |
| `sensor.f1_ai_commentary` | Senaste AI-kommentarmening |
| `sensor.f1_ai_recap` | Senaste AI-sessionreferat (~80 ord) |
| `sensor.f1_available_drivers` | Förare i aktuell session (attr: lista) |

## Notiser

Skickas alltid (ingen inställning behövs):
- 🔴 Röd flagga
- 🚗 Safety Car / VSC ute
- 🏁 Chequered flag (loppet klart)

Valfritt (toggle i dashboarden):
- 🟡 Gul / grön flagga
- 🔧 Pitstops för följda förare

## Valfritt: CYD-fysisk display

För ESP32-2432S028 ("Cheap Yellow Display"):

1. Kopiera `esphome/f1_display.yaml` till din ESPHome-konfig
2. Fyll i Wi-Fi-uppgifter och HA API-nyckel/lösenord
3. Flasha till enheten

Displayen visar 3 sidor (tryck för att byta):
- **Sida 0**: Live race — flaggfärgad header, 3 förarkort (pos/gap/däck), Race Control-meddelande
- **Sida 1**: Mästerskapsställning — förare och konstruktörer topp-10
- **Sida 2**: Fullständigt startfält topp-10 + AI-kommentar

Byter automatiskt till race-sidan när en session startar.

**→ Komplett installationsguide: [esphome/README.sv.md](esphome/README.sv.md)**

## Uppdateringsintervall

| Situation | Intervall |
|-----------|-----------|
| Aktiv session | Var 30:e sekund |
| Mellan sessioner | Var 5:e minut (session-check) |
| Mästerskapspoäng | Var timme |

## Felsökning

**Sensorer visar "–" efter omstart**
Normalt när ingen session är aktiv. Data hämtas automatiskt när en session startar.

**Förarnamn visar "#1" istället för "VER"**
Sessionsdata har ännu inte hämtats. Tryck på "Uppdatera nu" eller vänta på nästa poll-cykel.

**AI-kommentar fungerar inte**
Kontrollera att `input_boolean.f1_ai_commentary` är på och att en Groq-nyckel eller `ha_ai_task` AI är konfigurerad.

**CYD visar "N/A"**
ESPHome-textsensorerna hämtar data från HA var 30:e sekund. Vänta en minut efter HA-omstart.

## Datakälla

All data kommer från [openf1.org](https://openf1.org) — ett gratis, öppet F1-data-API.
Data finns tillgänglig för sessioner från och med 2023-säsongen.
Live-data är tillgänglig under sessioner och upp till 30 minuter efteråt.

## Stöd projektet

Gillar du det här projektet? En kopp kaffe uppskattas ☕

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/wizz666)

## Licens

MIT-licens — se [LICENSE](LICENSE)
