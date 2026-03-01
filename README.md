# Home Assistant OpenF1 Integration

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support_this_project-F16061?logo=ko-fi&logoColor=white)](https://ko-fi.com/wizz666)

Real-time F1 data for Home Assistant via the free [OpenF1 API](https://openf1.org).

**[🇸🇪 Svenska instruktioner → README.sv.md](README.sv.md)**

---

## Features

- **Live Race Control** — flag notifications (red, yellow, green, safety car, VSC, chequered) with push notifications
- **Driver Tracking** — track up to 3 drivers: position, gap to leader, interval, tyre compound, tyre age
- **Configurable Drivers** — change followed drivers anytime from the dashboard (no code editing needed)
- **Full 20-Driver Grid** — live positions, gaps and tyre compounds for the entire field
- **Championship Standings** — driver and constructor standings, updated every hour
- **AI Commentary** — one-sentence live commentary on significant race events (requires Groq API key or Google AI)
- **AI Session Recap** — auto-generated ~80-word race report after each session ends
- **CYD Display** — optional ESP32-2432S028 touchscreen display (3 pages: race, standings, live grid)
- **Next Session Countdown** — always shows time until the next practice/qualifying/race

## Requirements

- Home Assistant 2024.1+
- [Pyscript integration](https://github.com/custom-components/pyscript) (via HACS)
- No API key needed — OpenF1 is free and open

### Optional
- Groq API key (free tier at [console.groq.com](https://console.groq.com)) for AI commentary
- ESP32-2432S028 "Cheap Yellow Display" for the physical display

## Installation

### 1. Install Pyscript

Install [pyscript](https://github.com/custom-components/pyscript) via HACS, then add to `configuration.yaml`:

```yaml
pyscript:
  allow_all_imports: true
  hass_is_global: true
```

### 2. Copy files

Copy these files to your Home Assistant config directory:

| File | Destination |
|------|------------|
| `openf1.py` | `config/pyscript/openf1.py` |
| `openf1_package.yaml` | `config/packages/openf1_package.yaml` |
| `f1_dashboard.yaml` | `config/dashboards/f1_dashboard.yaml` |

Enable packages in `configuration.yaml` if not already done:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

### 3. Register the dashboard

Add to `configuration.yaml`:

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

### 4. Restart Home Assistant

After restart, the F1 dashboard appears in the sidebar.

## Configuration

### Choose your drivers

Go to **F1 Live → Inställningar** (Settings) and set the driver numbers for slots 1–3. Set to 0 to disable a slot.

Common 2025/2026 numbers:
| Driver | Number |
|--------|--------|
| Verstappen | 1 |
| Norris | 4 |
| Hamilton | 44 |
| Leclerc | 16 |
| Sainz | 55 |
| Russell | 63 |
| Piastri | 81 |
| Alonso | 14 |

### AI Commentary (optional)

1. Get a free Groq API key at [console.groq.com](https://console.groq.com)
2. If you use the [Grocery Tracker](https://github.com/wizz666/homeassistant-grocery-tracker) integration, the key is shared automatically
3. Otherwise, set `input_text.grocery_api_key_groq` to your key
4. Enable **AI-kommentator** in the AI view of the dashboard

Fallback: if no Groq key is set, AI uses `ha_ai_task` (requires Google AI or Anthropic integration in HA).

## Sensors

### Session

| Sensor | Description |
|--------|-------------|
| `sensor.f1_session_status` | inactive / Practice / Qualifying / Race / Sprint |
| `sensor.f1_next_session` | Countdown to next session (attrs: session_name, circuit, country, date_start) |
| `sensor.f1_flag` | Current flag: GREEN / YELLOW / RED / SAFETY CAR / VSC / CHEQUERED |
| `sensor.f1_lap` | Current lap number |
| `sensor.f1_race_control_msg` | Latest Race Control message |

### Followed drivers (slots 1–3)

Replace `{n}` with 1, 2 or 3:

| Sensor | Description |
|--------|-------------|
| `sensor.f1_d{n}_name` | Driver abbreviation (VER / HAM / etc.) |
| `sensor.f1_d{n}_position` | Current race position |
| `sensor.f1_d{n}_gap` | Gap to race leader |
| `sensor.f1_d{n}_interval` | Gap to the car ahead |
| `sensor.f1_d{n}_compound` | Tyre compound with emoji (🔴 SOFT) |
| `sensor.f1_d{n}_tyre_age` | Laps on current tyres |

### Championship

| Sensor | Description |
|--------|-------------|
| `sensor.f1_driver_standings` | Pipe-separated standings: `1.VER 125p\|2.NOR 113p\|...` |
| `sensor.f1_constructor_standings` | Pipe-separated: `1.MCL 210p\|2.FER 190p\|...` |

### Full grid / AI

| Sensor | Description |
|--------|-------------|
| `sensor.f1_live_grid` | Number of drivers tracked; attr `grid` = list of all 20 drivers |
| `sensor.f1_grid_display` | Compact pipe-sep string for CYD display |
| `sensor.f1_ai_commentary` | Latest AI live commentary sentence |
| `sensor.f1_ai_recap` | Latest AI session recap (~80 words) |
| `sensor.f1_available_drivers` | Drivers in current session (attr: list) |

## Notifications

Always sent (no setting needed):
- 🔴 Red flag
- 🚗 Safety Car / VSC deployed
- 🏁 Chequered flag (race finished)

Optional (toggle in dashboard):
- 🟡 Yellow / green flags
- 🔧 Pit stops for followed drivers

## Optional: CYD Physical Display

For the ESP32-2432S028 "Cheap Yellow Display":

1. Copy `esphome/f1_display.yaml` to your ESPHome config
2. Set your Wi-Fi credentials and HA API key/password
3. Flash to the device

The display shows 3 pages (touch to cycle):
- **Page 0**: Live race — flag colour header, 3 driver cards (pos/gap/tyre), Race Control message
- **Page 1**: Championship standings — driver and constructor top 10
- **Page 2**: Full grid top-10 + AI commentary

Auto-switches to race page when a session starts.

## Update interval

| Situation | Interval |
|-----------|----------|
| Active session | Every 30 seconds |
| Between sessions | Every 5 minutes (session check) |
| Championship standings | Every hour |

## Troubleshooting

**Sensors show "–" after restart**
Normal when no session is active. Data populates when a session starts.

**Driver names show "#1" instead of "VER"**
Session data hasn't been fetched yet. Tap "Uppdatera nu" (Update now) or wait for the next poll cycle.

**AI commentary not working**
Check that `input_boolean.f1_ai_commentary` is on and that a Groq key or `ha_ai_task` AI is configured.

**CYD shows "N/A"**
The ESPHome text sensors poll HA every 30s. Allow a minute after HA restart.

## Data source

All data is from [openf1.org](https://openf1.org) — a free, open F1 data API.
Data is available for sessions from the 2023 season onwards.
Live data is available during sessions and up to 30 minutes after they end.

## Support

If you find this useful, a coffee is always appreciated ☕

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/wizz666)

## License

MIT License — see [LICENSE](LICENSE)
