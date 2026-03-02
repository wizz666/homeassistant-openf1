# F1 Live Display — CYD (ESP32-2432S028)

A physical F1 race display for the **ESP32-2432S028** ("Cheap Yellow Display") that shows live race data from Home Assistant.

**[🇸🇪 Svenska instruktioner → README.sv.md](README.sv.md)**

---

## What it looks like

**Page 0 – Race Live**
```
┌─────────────────────────────────────────┐
│ F1  │  RACE              │         V 23 │  ← flag-coloured header
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
Header colour changes with flag state: 🔴 red flag, 🟡 yellow, 🟠 safety car, 🟢 green, ⬛ chequered.

**Page 1 – Championship Standings**
```
┌─────────────────────────────────────────┐
│ F1 2026                        4d 10h   │  ← red header
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

**Page 2 – Live Grid + AI**
```
┌─────────────────────────────────────────┐
│ LIVE GRID                      V 23     │  ← green (active) / grey (inactive)
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

**Touch**: Cycles through pages 0 → 1 → 2 → 0.
**Auto-switch**: Jumps to Race page when a session starts; returns to Standings when inactive.

---

## Hardware

The **ESP32-2432S028** is a popular, cheap (~$10–15) dev board with a built-in 2.8" ILI9341 320×240 colour display and XPT2046 resistive touchscreen. Often sold as "CYD" (Cheap Yellow Display).

**Where to buy**: AliExpress, Amazon, or local electronics stores.
Search for: `ESP32-2432S028` or `ESP32 CYD 2.8 TFT`

### GPIO pinout (already configured in the YAML)

| Function | GPIO |
|----------|------|
| SPI CLK | 14 |
| SPI MOSI | 13 |
| SPI MISO | 12 |
| Display CS | 15 |
| Display DC | 2 |
| Display Reset | 4 |
| Backlight (PWM) | 21 |
| Touch CS | 33 |
| Touch IRQ | 36 |

No wiring required — everything is on-board.

---

## Requirements

- **Home Assistant** with the OpenF1 pyscript integration installed and running
- **ESPHome** add-on installed in Home Assistant (via Add-on Store)
- USB cable for initial flashing (USB-C or micro-USB depending on board revision)
- Wi-Fi 2.4 GHz network

---

## Installation

### Step 1 — Install ESPHome

In Home Assistant, go to **Settings → Add-ons → Add-on Store** and install **ESPHome**.

### Step 2 — Add secrets

Open the ESPHome secrets file (`esphome/secrets.yaml` in your HA config) and add:

```yaml
wifi_ssid: "YourNetworkName"
wifi_password: "YourWiFiPassword"
api_encryption_key: "your32bytebase64key=="   # generate below
ota_password: "choose-a-password"
fallback_ap_password: "choose-a-fallback-password"
```

**Generate an API encryption key:**
In the ESPHome dashboard, click **Secrets** → the key will be auto-generated, or run:
```bash
python3 -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"
```

### Step 3 — Copy the YAML file

Copy `f1_display.yaml` to your Home Assistant ESPHome directory:
```
config/esphome/f1_display.yaml
```

Or paste the contents directly into the ESPHome dashboard editor.

### Step 4 — Flash the device

1. Connect the ESP32-2432S028 to your computer via USB
2. Open the ESPHome dashboard in Home Assistant
3. Find **f1-display** → click **Install** → choose **Plug into this computer**
4. Wait for compilation and flashing (~2–3 minutes)

> **Subsequent updates** can be done wirelessly via OTA — no USB needed.

### Step 5 — Add to Home Assistant

After flashing, the device appears in **Settings → Devices & Services** for adoption. Click **Configure** and approve the connection using your `api_encryption_key`.

---

## Configuration

No additional configuration is needed — the display reads directly from the sensors created by the OpenF1 pyscript integration.

### Changing displayed drivers

Drivers are configured in the **F1 Live → Inställningar** dashboard view (or via `input_number.f1_followed_1/2/3`). The display updates automatically within 30 seconds.

---

## Sensors used by the display

The ESPHome firmware subscribes to these Home Assistant sensors:

| Sensor | Page | Description |
|--------|------|-------------|
| `sensor.f1_session_status` | All | Session type; triggers auto page switch |
| `sensor.f1_flag` | 0 | Flag state → header background colour |
| `sensor.f1_lap` | 0 | Current lap number |
| `sensor.f1_next_session` | 0, 1, 2 | Countdown to next session |
| `sensor.f1_race_control_msg` | 0 | Latest Race Control message |
| `sensor.f1_d1_name` | 0 | Driver 1 abbreviation (e.g. VER) |
| `sensor.f1_d1_position` | 0 | Driver 1 race position |
| `sensor.f1_d1_gap` | 0 | Driver 1 gap to leader |
| `sensor.f1_d1_compound` | 0 | Driver 1 tyre compound |
| `sensor.f1_d1_tyre_age` | 0 | Driver 1 laps on current tyres |
| `sensor.f1_d2_*` | 0 | Same as above for driver slot 2 |
| `sensor.f1_d3_*` | 0 | Same as above for driver slot 3 |
| `sensor.f1_driver_standings` | 1 | Pipe-separated driver championship |
| `sensor.f1_constructor_standings` | 1 | Pipe-separated constructor championship |
| `sensor.f1_grid_display` | 2 | Pipe-separated full grid (top 10) |
| `sensor.f1_ai_commentary` | 2 | Latest AI commentary sentence |

---

## Troubleshooting

**Display shows "N/A" for all sensors**
The device has not yet synced with Home Assistant. Allow 30–60 seconds after both HA and the device have started. Check that the device is adopted in HA (Settings → Devices).

**"Waiting for race..." on page 2 even during a session**
The `sensor.f1_live_grid` is only populated when position + tyre data is available. This takes a few laps into the session.

**Device not appearing in ESPHome**
Make sure the device is on the same Wi-Fi network as Home Assistant. If it fails to connect, it creates a fallback hotspot named **F1Display Fallback** — connect to it using the `fallback_ap_password` you set in `secrets.yaml` to re-configure Wi-Fi.

**Touch not responding or triggering in wrong position**
The touch calibration values in the YAML (`x_min: 200`, `x_max: 3800`, `y_min: 240`, `y_max: 3860`) work for most boards. If touch is off, adjust these values. Some boards need `mirror_y: true` added under `transform`.

**Compilation error: "font not found"**
ESPHome downloads Roboto from Google Fonts during compilation. Make sure your HA instance has internet access.

**Display is very dim**
The backlight is configured to full brightness (`ALWAYS_ON`). If it's dim, check that GPIO21 is not shorted. You can adjust brightness by changing the light component to use a fixed level:
```yaml
light:
  - platform: monochromatic
    output: backlight_pwm
    id: backlight
    restore_mode: ALWAYS_ON
    default_transition_length: 0s
```

---

## Customisation

### Change font size

Edit the `size:` values under the `font:` section. Larger text = fewer characters per line.

### Change header colours

Edit the `flag_color()` lambda in the display section:
```cpp
auto flag_color = [&]() -> Color {
  std::string f = id(f1_flag).state;
  if (f == "RED") return Color(160, 0, 0);      // r, g, b (0–255)
  if (f == "YELLOW") return Color(150, 130, 0);
  // ...
};
```

### Disable a page

Change `% 3` to `% 2` in the touch handler to cycle through only 2 pages:
```cpp
id(current_page) = (id(current_page) + 1) % 2;  // 0 and 1 only
```

### Adjust update interval

The display redraws every second. To reduce CPU load, change `update_interval: 1s` to `update_interval: 2s` under the `display:` section.

---

## Support

If you find this useful, a coffee is always appreciated ☕

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/wizz666)
