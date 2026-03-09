"""
OpenF1 – Home Assistant Pyscript v1.1
======================================
Real-time F1 data via openf1.org

Följer: Verstappen (#1), Hamilton (#44), Bottas (#77)

Sensorer – Session:
  sensor.f1_session_status        – inactive / Practice / Qualifying / Race / Sprint
  sensor.f1_next_session          – nedräkning + attrs: session_name, circuit, country, date_start
  sensor.f1_flag                  – GREEN / YELLOW / RED / SAFETY CAR / VSC / CHEQUERED
                                    attrs: display (emoji), message, history (lista)
  sensor.f1_lap                   – aktuellt varv (sträng, t.ex. "45")
  sensor.f1_race_control_msg      – senaste RC-meddelande (text)

Sensorer – Följda förare (ver / ham / bot):
  sensor.f1_{slug}_position       – position (t.ex. "1")
  sensor.f1_{slug}_gap            – lucka till ledaren (t.ex. "+8.423s")
  sensor.f1_{slug}_interval       – lucka till bilen framför
  sensor.f1_{slug}_compound       – däck med emoji (t.ex. "🔴 SOFT")
                                    attr: compound = råtext (SOFT/MED/HARD/INT/WET)
  sensor.f1_{slug}_tyre_age       – antal varv på däcken

Sensorer – Mästerskap (uppdateras var 1h + direkt efter lopp):
  sensor.f1_driver_standings      – pipe-separerad "1.VER 125p|2.HAM 98p|..."
                                    attr: summary = "VER 125 · HAM 98 · NOR 87"
  sensor.f1_constructor_standings – pipe-separerad "1.RBR 180p|2.MER 140p|..."
                                    attr: summary = "RBR 180 · MER 140 · MCL 92"

Notiser:
  Röd flagga, Safety Car, VSC, CHEQUERED — alltid
  Gul/grön flagga — om input_boolean.f1_notify_flags är på
  Pitstop (VER/HAM/BOT) — om input_boolean.f1_notify_pitstops är på

Tjänster:
  pyscript.openf1_refresh         – tvinga omedelbar uppdatering av alla sensorer
"""

import json

API_BASE = "https://api.openf1.org/v1"


# Hårdkodad fallback för vanliga förarnummer (visas innan första session hämtas)
_DRIVER_FALLBACK = {
    1: "VER", 2: "SAR", 3: "RIC", 4: "NOR", 5: "VET",
    10: "GAS", 11: "PER", 14: "ALO", 16: "LEC", 18: "STR",
    20: "MAG", 21: "DEV", 22: "TSU", 23: "ALB", 24: "ZHO",
    27: "HUL", 31: "OCO", 38: "BEA", 43: "COL", 44: "HAM",
    55: "SAI", 63: "RUS", 77: "BOT", 81: "PIA", 87: "BOR",
}

# Konfigurerbara följda förare – byggs från input_number.f1_followed_1/2/3
# Struktur: {driver_number: {"slot": 1|2|3, "name": "VER", "full_name": "Verstappen"}}
_FOLLOWED = {}

def _rebuild_followed():
    """Läser input_number.f1_followed_1/2/3 och uppdaterar _FOLLOWED + namn-sensorer."""
    _FOLLOWED.clear()
    for slot in (1, 2, 3):
        try:
            raw = state.get(f"input_number.f1_followed_{slot}") or "0"
            num = int(float(raw))
        except Exception:
            num = 0
        if num <= 0:
            # Slot tom – nollställ namn-sensor
            state.set(f"sensor.f1_d{slot}_name", "–", {
                "friendly_name": f"F1 – Förare {slot}",
                "icon": "mdi:racing-helmet",
                "driver_number": 0,
                "configured": False,
            })
            continue
        info = _driver_info.get(num, {})
        acronym = info.get("acronym") or _DRIVER_FALLBACK.get(num, f"#{num}")
        full    = info.get("full_name", acronym)
        _FOLLOWED[num] = {"slot": slot, "name": acronym, "full_name": full}
        state.set(f"sensor.f1_d{slot}_name", acronym, {
            "friendly_name": f"F1 – Förare {slot}",
            "icon": "mdi:racing-helmet",
            "driver_number": num,
            "full_name": full,
            "configured": True,
        })
    log.info(f"[OpenF1] Följda förare: {[(v['name'], k) for k,v in _FOLLOWED.items()]}")


COMPOUND_ICON = {
    "SOFT":         "🔴 SOFT",
    "MEDIUM":       "🟡 MED",
    "HARD":         "⚪ HARD",
    "INTERMEDIATE": "🟢 INT",
    "WET":          "🔵 WET",
}

TEAM_ABBR = {
    "Red Bull Racing":             "RBR",
    "Mercedes":                    "MER",
    "McLaren":                     "MCL",
    "Ferrari":                     "FER",
    "Williams":                    "WIL",
    "Aston Martin":                "AMR",
    "Alpine":                      "ALP",
    "Haas F1 Team":                "HAS",
    "Haas":                        "HAS",
    "Stake F1 Team Kick Sauber":   "SAU",
    "Sauber":                      "SAU",
    "Visa Cash App RB":            "RB",
    "RB F1 Team":                  "RB",
    "RB":                          "RB",
}

FLAG_ICON = {
    "GREEN":          "🟢",
    "YELLOW":         "🟡",
    "DOUBLE YELLOW":  "🟡🟡",
    "RED":            "🔴",
    "CHEQUERED":      "🏁",
    "BLUE":           "🔵",
    "BLACK AND WHITE": "⬛⬜",
    "BLACK":          "⬛",
    "WHITE":          "⬜",
    "SAFETY CAR":     "🚗 SC",
    "VIRTUAL SAFETY CAR": "🚗 VSC",
}

# ─── Modulnivå-state ─────────────────────────────────────────────────────────

_session_active = [False]
_session_key    = [None]
_session_name   = ["Ingen aktiv session"]
_session_type   = ["inactive"]

_last_rc_date   = [""]          # Senaste race_control-date vi processat
_rc_history     = []            # Senaste 10 händelser
_last_pit       = {}            # {driver_num: date_str}
_last_pos       = {}            # {driver_num: position}

_last_session_check   = [0.0]   # Unix timestamp
_last_standings_check = [0.0]   # Unix timestamp

# Full grid – alla 20 förare (uppdateras från befintliga poll-anrop, inga extra API-calls)
_all_positions  = {}    # {driver_num: position}
_all_gaps       = {}    # {driver_num: gap_str}
_all_compounds  = {}    # {driver_num: compound_raw}
_driver_info    = {}    # {driver_num: {"acronym": str, "team": str}}

# AI-motor
_ai_busy            = [False]   # Förhindrar parallella AI-anrop
_recap_pending      = [False]   # Sätts True när session slutar → triggar referat
_last_commentary_ts = [0.0]     # Cooldown för live-kommentar (120s)

SESSION_CHECK_SECS   = 300      # Kolla sessions var 5:e minut
POLL_INTERVAL_SECS   = 30       # Poll live data var 30s
STANDINGS_CHECK_SECS = 3600     # Uppdatera standings max 1 gång/timme

# ─── HTTP ─────────────────────────────────────────────────────────────────────

async def _get(endpoint, params=None):
    import aiohttp
    url = f"{API_BASE}/{endpoint}"
    if params:
        qs = "&".join([f"{k}={v}" for k, v in params.items()])
        url = f"{url}?{qs}"
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
                log.warning(f"[OpenF1] HTTP {resp.status}: {endpoint}")
    except Exception as e:
        log.warning(f"[OpenF1] API-fel ({endpoint}): {e}")
    return []

async def _get_jolpica(path):
    """Fallback: hämta standings från Jolpica/Ergast när openf1.org saknar data."""
    import aiohttp
    url = f"https://api.jolpi.ca/ergast/f1/{path}"
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
                log.warning(f"[OpenF1] Jolpica HTTP {resp.status}: {path}")
    except Exception as e:
        log.warning(f"[OpenF1] Jolpica-fel ({path}): {e}")
    return None

# ─── Tid-hjälpare ─────────────────────────────────────────────────────────────

def _now_utc():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)

def _parse_dt(s):
    from datetime import datetime, timezone
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

def _fmt_countdown(start_dt):
    from datetime import datetime, timezone
    if start_dt is None:
        return "?"
    now = _now_utc()
    if start_dt <= now:
        return "Nu"
    delta = start_dt - now
    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}min"
    return f"{minutes}min"

# ─── Sensoruppdatering per förare ─────────────────────────────────────────────

def _driver_sensor(slug, field, value, attrs):
    state.set(f"sensor.f1_{slug}_{field}", value, attrs)

def _init_driver_sensors():
    """Återställer alla d1/d2/d3-sensorer och uppdaterar namn från aktuell konfiguration."""
    _rebuild_followed()
    for slot in (1, 2, 3):
        matches = [(num, info) for num, info in _FOLLOWED.items() if info["slot"] == slot]
        drv_entry = matches[0] if matches else (0, None)
        full = drv_entry[1]["full_name"] if drv_entry[1] else f"Förare {slot}"
        _driver_sensor(f"d{slot}", "position", "–", {
            "friendly_name": f"F1 {full} – Position",
            "icon": "mdi:podium",
        })
        _driver_sensor(f"d{slot}", "gap", "–", {
            "friendly_name": f"F1 {full} – Gap to leader",
            "icon": "mdi:timer-outline",
        })
        _driver_sensor(f"d{slot}", "interval", "–", {
            "friendly_name": f"F1 {full} – Interval",
            "icon": "mdi:timer-outline",
        })
        _driver_sensor(f"d{slot}", "compound", "–", {
            "friendly_name": f"F1 {full} – Däck",
            "icon": "mdi:tire",
        })
        _driver_sensor(f"d{slot}", "tyre_age", "–", {
            "friendly_name": f"F1 {full} – Däckålder",
            "icon": "mdi:counter",
            "unit_of_measurement": "varv",
        })

# ─── Session discovery ────────────────────────────────────────────────────────

async def _check_sessions():
    """Hitta aktiv + nästa session. Kör var SESSION_CHECK_SECS sekunder."""
    from datetime import datetime, timezone, timedelta
    now = _now_utc()

    _last_session_check[0] = now.timestamp()

    year = now.year
    sessions = await _get("sessions", {"year": year})
    if not sessions:
        return

    active  = None
    upcoming = None

    for s in sessions:
        start = _parse_dt(s.get("date_start"))
        end   = _parse_dt(s.get("date_end"))
        if not start or not end:
            continue
        end_ext = end + timedelta(minutes=60)
        if start <= now <= end_ext:
            active = s
            break
        if start > now:
            if upcoming is None:
                upcoming = s
            elif start < _parse_dt(upcoming.get("date_start")):
                upcoming = s

    if active:
        new_key = active.get("session_key")
        if new_key != _session_key[0]:
            # Ny session startad – återställ allt
            _last_rc_date[0] = ""
            _rc_history.clear()
            _last_pit.clear()
            _last_pos.clear()
            _all_positions.clear()
            _all_gaps.clear()
            _all_compounds.clear()
            _driver_info.clear()
            log.info(f"[OpenF1] Ny session: key={new_key}")
            # Hämta förare-info för ny session
            await _fetch_driver_info(new_key)

        _session_active[0] = True
        _session_key[0]    = new_key
        stype = active.get("session_type", "Session")
        circuit = active.get("circuit_short_name", "")
        country = active.get("country_name", "")
        sname = f"{stype} – {circuit} GP"
        _session_type[0] = stype
        _session_name[0] = sname

        state.set("sensor.f1_session_status", stype, {
            "friendly_name": "F1 – Session",
            "icon": "mdi:racing-helmet",
            "session_key": new_key,
            "circuit": circuit,
            "country": country,
            "session_name": sname,
        })
        log.info(f"[OpenF1] Aktiv session: {sname} (key={new_key})")

    else:
        if _session_active[0]:
            log.info("[OpenF1] Session avslutad – triggar standings + AI-referat.")
            _last_standings_check[0] = 0.0  # Hämta uppdaterade standings direkt efter lopp
            _recap_pending[0] = True         # Triggar AI-sessionreferat i nästa poll-cykel
        _session_active[0] = False
        _session_key[0]    = None
        _session_type[0]   = "inactive"
        _session_name[0]   = "Ingen aktiv session"
        _init_driver_sensors()
        state.set("sensor.f1_session_status", "inactive", {
            "friendly_name": "F1 – Session",
            "icon": "mdi:racing-helmet",
            "session_name": "Ingen aktiv session",
        })
        state.set("sensor.f1_flag", "–", {
            "friendly_name": "F1 – Flagga",
            "icon": "mdi:flag",
            "message": "",
        })
        state.set("sensor.f1_lap", "–", {
            "friendly_name": "F1 – Varv",
            "icon": "mdi:counter",
        })

    # Uppdatera nästa-session-sensor (alltid, oavsett aktiv)
    if upcoming:
        start = _parse_dt(upcoming.get("date_start"))
        countdown = _fmt_countdown(start)
        stype = upcoming.get("session_type", "")
        circuit = upcoming.get("circuit_short_name", "")
        country = upcoming.get("country_name", "")
        gmt = upcoming.get("gmt_offset", "UTC")
        state.set("sensor.f1_next_session", countdown, {
            "friendly_name": "F1 – Nästa session",
            "icon": "mdi:clock-countdown",
            "session_name": f"{stype} – {circuit} GP",
            "circuit": circuit,
            "country": country,
            "session_type": stype,
            "date_start": upcoming.get("date_start", ""),
            "gmt_offset": gmt,
        })

# ─── Race Control ─────────────────────────────────────────────────────────────

def _should_notify_flag(flag, category, message):
    """Bestäm om denna race-control-händelse ska skicka notis."""
    if not flag and not category:
        return False
    flag_upper = (flag or "").upper()
    cat_upper  = (category or "").upper()

    # Alltid notifiera
    if flag_upper in ("RED",):
        return True
    if "SAFETY CAR" in cat_upper:
        return True
    if flag_upper == "CHEQUERED":
        return True
    if "VIRTUAL SAFETY CAR" in (message or "").upper():
        return True

    # Notifiera om flagg-notiser är påslagna
    notify_flags = state.get("input_boolean.f1_notify_flags")
    if notify_flags == "on":
        if flag_upper in ("YELLOW", "DOUBLE YELLOW", "GREEN"):
            return True

    return False

async def _poll_race_control():
    sk = _session_key[0]
    if not sk:
        return

    messages = await _get("race_control", {"session_key": sk})
    if not messages:
        return

    # Sortera på datum
    messages_sorted = sorted(messages, key=lambda m: m.get("date", ""))

    new_msgs = [m for m in messages_sorted if m.get("date", "") > _last_rc_date[0]]
    if not new_msgs:
        return

    current_flag = "–"
    current_flag_msg = ""
    current_lap = None

    for msg in new_msgs:
        flag     = msg.get("flag") or ""
        category = msg.get("category") or ""
        message  = msg.get("message") or ""
        lap      = msg.get("lap_number")
        date_str = msg.get("date", "")

        _last_rc_date[0] = date_str

        # Spåra varv
        if lap:
            current_lap = lap

        # Bestäm flagg-emoji och status
        flag_display = ""
        if "SAFETY CAR" in category and "VIRTUAL" not in category and "VIRTUAL" not in message.upper():
            if "DEPLOYED" in message.upper() or "SAFETY CAR" in flag.upper():
                flag_display = "🚗 SC"
                current_flag = "SAFETY CAR"
            elif "IN THIS LAP" in message.upper() or "ENDING" in message.upper():
                flag_display = "🟢 SC ending"
                current_flag = "GREEN"
        elif "VIRTUAL SAFETY CAR" in category.upper() or "VIRTUAL SAFETY CAR" in message.upper():
            if "DEPLOYED" in message.upper():
                flag_display = "🚗 VSC"
                current_flag = "VIRTUAL SAFETY CAR"
            elif "ENDING" in message.upper():
                flag_display = "🟢 VSC ending"
                current_flag = "GREEN"
        elif flag:
            flag_display = FLAG_ICON.get(flag.upper(), flag)
            current_flag = flag.upper()
        elif "SESSION STARTED" in message.upper():
            flag_display = "🟢 START"
            current_flag = "GREEN"
        elif "SESSION ENDED" in message.upper() or "FINALISED" in message.upper():
            flag_display = "🏁"
            current_flag = "CHEQUERED"

        current_flag_msg = message

        # Spara i historik
        entry = {
            "time": date_str[11:19] if len(date_str) >= 19 else date_str,
            "flag": flag_display,
            "message": message[:120],
            "lap": lap,
        }
        _rc_history.insert(0, entry)
        if len(_rc_history) > 10:
            _rc_history.pop()

        # Skicka notis?
        if _should_notify_flag(flag, category, message):
            lap_txt = f" (varv {lap})" if lap else ""
            title = f"🏎️ F1 {flag_display or flag or category}"
            msg_txt = f"{message}{lap_txt}" if message else f"{flag_display}{lap_txt}"
            notify.notify(title=title, message=msg_txt)
            persistent_notification.create(
                title=title,
                message=msg_txt,
                notification_id="f1_race_control",
            )
            # AI live-kommentar (asynkron, cooldown 120s, icke-blockerande)
            await _ai_race_commentary(flag or category, message, lap)

    # Uppdatera flaggsensor
    if current_flag:
        flag_disp = FLAG_ICON.get(current_flag, current_flag)
        state.set("sensor.f1_flag", current_flag, {
            "friendly_name": "F1 – Flagga",
            "icon": "mdi:flag",
            "display": flag_disp,
            "message": current_flag_msg,
            "history": list(_rc_history),
        })

    if current_lap:
        state.set("sensor.f1_lap", str(current_lap), {
            "friendly_name": "F1 – Varv",
            "icon": "mdi:counter",
        })

    if current_flag_msg:
        state.set("sensor.f1_race_control_msg", current_flag_msg[:80], {
            "friendly_name": "F1 – Senaste Race Control",
            "icon": "mdi:message-alert-outline",
        })

# ─── Positioner ───────────────────────────────────────────────────────────────

async def _poll_positions():
    sk = _session_key[0]
    if not sk:
        return

    data = await _get("position", {"session_key": sk})
    if not data:
        return

    # Ta senaste position per förare
    latest = {}
    for entry in data:
        drv = entry.get("driver_number")
        if drv is not None:
            latest[drv] = entry.get("position")

    # Spara alla positioner för full grid
    _all_positions.update({k: v for k, v in latest.items() if v is not None})

    for drv_num, info in _FOLLOWED.items():
        pos = latest.get(drv_num)
        if pos is None:
            continue
        slot = info["slot"]
        _driver_sensor(f"d{slot}", "position", str(pos), {
            "friendly_name": f"F1 {info['full_name']} – Position",
            "icon": "mdi:podium",
            "unit_of_measurement": "P",
        })

# ─── Luckor (intervals) ───────────────────────────────────────────────────────

async def _poll_intervals():
    sk = _session_key[0]
    if not sk:
        return

    data = await _get("intervals", {"session_key": sk})
    if not data:
        return

    # Ta senaste entry per förare
    latest = {}
    for entry in data:
        drv = entry.get("driver_number")
        if drv is not None:
            latest[drv] = entry

    # Spara alla gaps för full grid
    for drv_num, entry in latest.items():
        gap = entry.get("gap_to_leader")
        if gap == 0:
            _all_gaps[drv_num] = "Leader"
        elif isinstance(gap, (int, float)):
            _all_gaps[drv_num] = f"+{gap:.1f}s"
        else:
            _all_gaps[drv_num] = "–"

    for drv_num, info in _FOLLOWED.items():
        entry = latest.get(drv_num)
        if not entry:
            continue
        slot = info["slot"]

        gap = entry.get("gap_to_leader")
        ivl = entry.get("interval")

        gap_str = f"+{gap:.3f}s" if isinstance(gap, (int, float)) and gap > 0 else ("Leader" if gap == 0 else "–")
        ivl_str = f"+{ivl:.3f}s" if isinstance(ivl, (int, float)) and ivl > 0 else ("Leader" if ivl == 0 else "–")

        _driver_sensor(f"d{slot}", "gap", gap_str, {
            "friendly_name": f"F1 {info['full_name']} – Gap to leader",
            "icon": "mdi:timer-outline",
            "gap_seconds": gap,
        })
        _driver_sensor(f"d{slot}", "interval", ivl_str, {
            "friendly_name": f"F1 {info['full_name']} – Interval",
            "icon": "mdi:timer-outline",
            "interval_seconds": ivl,
        })

# ─── Däck (stints) ────────────────────────────────────────────────────────────

async def _poll_tyres():
    sk = _session_key[0]
    if not sk:
        return

    data = await _get("stints", {"session_key": sk})
    if not data:
        return

    # Gruppera per förare, ta senaste stint
    stints_by_driver = {}
    for s in data:
        drv = s.get("driver_number")
        if drv is not None:
            if drv not in stints_by_driver:
                stints_by_driver[drv] = []
            stints_by_driver[drv].append(s)

    # Spara alla compounds för full grid
    for drv, stints_list in stints_by_driver.items():
        if stints_list:
            _all_compounds[drv] = stints_list[-1].get("compound", "")

    # Hämta aktuellt varv från lapdata för att beräkna däckålder
    laps_data = await _get("laps", {"session_key": sk, "driver_number": 1})
    current_lap = 0
    if laps_data:
        lap_nums = [l.get("lap_number", 0) for l in laps_data if l.get("lap_number")]
        if lap_nums:
            current_lap = max(lap_nums)

    for drv_num, info in _FOLLOWED.items():
        stints = stints_by_driver.get(drv_num, [])
        if not stints:
            continue
        slot = info["slot"]

        # Aktuell stint = sista i listan
        current_stint = stints[-1]
        compound = current_stint.get("compound", "UNKNOWN")
        age_at_start = current_stint.get("tyre_age_at_start", 0) or 0
        lap_start = current_stint.get("lap_start", 1) or 1

        # Beräkna ålder
        laps_on_tyre = current_lap - lap_start + 1 if current_lap >= lap_start else 0
        total_age = age_at_start + laps_on_tyre

        compound_display = COMPOUND_ICON.get(compound, compound)

        _driver_sensor(f"d{slot}", "compound", compound_display, {
            "friendly_name": f"F1 {info['full_name']} – Däck",
            "icon": "mdi:tire",
            "compound": compound,
            "stint_number": current_stint.get("stint_number", 1),
        })
        _driver_sensor(f"d{slot}", "tyre_age", str(total_age) if total_age > 0 else "–", {
            "friendly_name": f"F1 {info['full_name']} – Däckålder",
            "icon": "mdi:counter",
            "unit_of_measurement": "varv",
            "age_at_start": age_at_start,
            "lap_start": lap_start,
        })

    # Bygg live grid (kombinerar pos + gaps + compounds för alla förare)
    _build_live_grid()

# ─── Pitstop-detektering ──────────────────────────────────────────────────────

async def _poll_pits():
    sk = _session_key[0]
    if not sk:
        return

    # Bara om pit-notiser är aktiva
    if state.get("input_boolean.f1_notify_pitstops") != "on":
        return

    data = await _get("pit", {"session_key": sk})
    if not data:
        return

    for entry in data:
        drv_num = entry.get("driver_number")
        if drv_num not in _FOLLOWED:
            continue
        date_str = entry.get("date", "")
        if not date_str or date_str <= _last_pit.get(drv_num, ""):
            continue

        _last_pit[drv_num] = date_str
        info = _FOLLOWED[drv_num]
        stop = entry.get("stop_duration") or entry.get("lane_duration") or 0
        lap = entry.get("lap_number", "?")

        # Hitta nytt däck från stints
        stints = await _get("stints", {"session_key": sk, "driver_number": drv_num})
        new_compound = ""
        if stints:
            latest_stint = stints[-1]
            new_compound = COMPOUND_ICON.get(latest_stint.get("compound", ""), "")

        title = f"🏎️ {info['name']} pittar!"
        msg = f"Varv {lap} · Stop: {stop:.1f}s{' → ' + new_compound if new_compound else ''}"
        notify.notify(title=title, message=msg)
        persistent_notification.create(
            title=title,
            message=msg,
            notification_id=f"f1_pit_{info['name']}",
        )
        log.info(f"[OpenF1] Pitstop: {info['name']} varv {lap}, {stop:.1f}s")

# ─── Uppdatera countdown (alltid, ingen session-krav) ─────────────────────────

def _update_countdown():
    """Räkna ned nästa session från cachat datum."""
    date_str = ""
    try:
        val = state.get("sensor.f1_next_session")
        if val and val not in ("–", "unknown"):
            # Hämta date_start från attribut
            date_str = state.get("sensor.f1_next_session.date_start") or ""
    except Exception:
        pass

    if not date_str:
        return

    start_dt = _parse_dt(date_str)
    if start_dt:
        countdown = _fmt_countdown(start_dt)
        try:
            current = state.get("sensor.f1_next_session")
            if current != countdown:
                attrs_keys = ["session_name", "circuit", "country", "session_type", "date_start", "gmt_offset"]
                attrs = {"friendly_name": "F1 – Nästa session", "icon": "mdi:clock-countdown", "date_start": date_str}
                state.set("sensor.f1_next_session", countdown, attrs)
        except Exception:
            pass

# ─── Full grid – alla 20 förare ──────────────────────────────────────────────

async def _fetch_driver_info(sk=None):
    """Hämtar förare-info (akronym, team) för sessionen. Anropas en gång per ny session."""
    session_key = sk or _session_key[0]
    if not session_key:
        return
    data = await _get("drivers", {"session_key": session_key})
    if data:
        _driver_info.clear()
        for d in data:
            num = d.get("driver_number")
            if num is not None:
                _driver_info[num] = {
                    "acronym":   (d.get("name_acronym") or str(num))[:3].upper(),
                    "team":      (d.get("team_name") or "")[:15],
                    "full_name": (d.get("last_name") or d.get("broadcast_name") or
                                  d.get("name_acronym") or str(num)),
                }
        log.info(f"[OpenF1] Förare-info: {len(_driver_info)} förare laddade")
        _rebuild_followed()   # Uppdatera _FOLLOWED med korrekta acronymer från API

        # Publicera lista på tillgängliga förare (nyttigt för konfiguration)
        drv_list = [
            {
                "number": num,
                "acronym": info["acronym"],
                "name": info.get("full_name", info["acronym"]),
                "team": info.get("team", ""),
            }
            for num, info in sorted(_driver_info.items())
        ]
        state.set("sensor.f1_available_drivers", str(len(drv_list)), {
            "friendly_name": "F1 – Tillgängliga förare",
            "icon": "mdi:account-group",
            "drivers": drv_list,
        })


_CMP_SHORT = {"SOFT": "S", "MEDIUM": "M", "HARD": "H", "INTERMEDIATE": "I", "WET": "W"}


def _build_live_grid():
    """Kombinerar _all_positions/_all_gaps/_all_compounds → sensor.f1_live_grid + sensor.f1_grid_display."""
    if not _all_positions:
        return
    grid = []
    for drv_num, pos in sorted(_all_positions.items(), key=lambda x: x[1]):
        info = _driver_info.get(drv_num, {"acronym": str(drv_num)[:3], "team": ""})
        cmp_raw = _all_compounds.get(drv_num, "")
        grid.append({
            "pos":      pos,
            "num":      drv_num,
            "acronym":  info["acronym"],
            "team":     info["team"],
            "gap":      _all_gaps.get(drv_num, "–"),
            "compound": cmp_raw,
        })

    state.set("sensor.f1_live_grid", str(len(grid)), {
        "friendly_name": "F1 – Live Grid",
        "icon": "mdi:format-list-numbered",
        "grid": grid,
    })

    # Kompakt pipe-separerad sträng för CYD (top 10): "P.ACR GAP C"
    display_parts = []
    for entry in grid[:10]:
        g = entry["gap"]
        g_short = (g[:7] if len(g) > 7 else g)
        c = _CMP_SHORT.get(entry["compound"], "?")
        display_parts.append(f"{entry['pos']}.{entry['acronym']} {g_short} {c}")

    state.set("sensor.f1_grid_display", "|".join(display_parts), {
        "friendly_name": "F1 – Grid Display",
        "icon": "mdi:format-list-numbered",
    })


# ─── AI-kommentator ────────────────────────────────────────────────────────────

def _ai_key_ok(k):
    """Returnerar True om k är en giltig API-nyckel (ej tom/placeholder)."""
    return bool(k) and k not in ("unknown", "none", "unavailable", "")


async def _call_groq(api_key, prompt, max_tokens):
    """Anropar Groq (llama-3.3-70b-versatile). Returnerar sträng eller None."""
    import aiohttp
    try:
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.85,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    return data["choices"][0]["message"]["content"].strip()
                log.warning(f"[OpenF1-AI] Groq HTTP {resp.status}")
    except Exception as e:
        log.warning(f"[OpenF1-AI] Groq-fel: {e}")
    return None


async def _call_anthropic(api_key, prompt, max_tokens):
    """Anropar Anthropic Claude (claude-haiku-4-5). Returnerar sträng eller None."""
    import aiohttp
    try:
        payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    return data["content"][0]["text"].strip()
                log.warning(f"[OpenF1-AI] Anthropic HTTP {resp.status}")
    except Exception as e:
        log.warning(f"[OpenF1-AI] Anthropic-fel: {e}")
    return None


async def _call_openai(api_key, prompt, max_tokens):
    """Anropar OpenAI (gpt-4o-mini). Returnerar sträng eller None."""
    import aiohttp
    try:
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.85,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    return data["choices"][0]["message"]["content"].strip()
                log.warning(f"[OpenF1-AI] OpenAI HTTP {resp.status}")
    except Exception as e:
        log.warning(f"[OpenF1-AI] OpenAI-fel: {e}")
    return None


async def _call_ha_ai_task(prompt):
    """Anropar ha_ai_task (Google AI / Anthropic etc. beroende på HA-konfiguration)."""
    try:
        result = await ai_task.generate_data(
            task_name="f1_commentary",
            instructions=prompt,
        )
        if isinstance(result, str):
            return result.strip() or None
        if isinstance(result, dict):
            return result.get("text") or result.get("result") or None
    except Exception as e:
        log.warning(f"[OpenF1-AI] ha_ai_task-fel: {e}")
    return None


def _resolve_key(provider):
    """
    Hämtar API-nyckel för provider.
    Prioritet: AI Hub → egen F1-nyckel → (Groq: Grocery Tracker-fallback)
    """
    hub_entities = {
        "groq":      "input_text.ai_hub_groq_key",
        "anthropic": "input_text.ai_hub_anthropic_key",
        "openai":    "input_text.ai_hub_openai_key",
    }
    # 1. AI Hub
    hub_key = (state.get(hub_entities.get(provider, "")) or "").strip()
    if _ai_key_ok(hub_key):
        return hub_key
    # 2. Egen F1-nyckel
    own_key = (state.get("input_text.f1_ai_api_key") or "").strip()
    if _ai_key_ok(own_key):
        return own_key
    # 3. Groq: bakåtkompatibel fallback från Grocery Tracker
    if provider == "groq":
        legacy = (state.get("input_text.grocery_api_key_groq") or "").strip()
        if _ai_key_ok(legacy):
            return legacy
    return ""


async def _ask_ai(prompt, max_tokens=200):
    """
    Routing-funktion: skickar prompt till rätt AI-leverantör.

    Leverantör väljs via input_select.f1_ai_provider (eller ai_hub_default_provider som fallback):
      auto       – Groq → Anthropic → OpenAI → ha_ai_task (första med nyckel)
      groq       – Groq
      ha_ai_task – HA:s inbyggda AI
      anthropic  – Anthropic Claude
      openai     – OpenAI GPT-4o-mini

    Nycklar hämtas i prioritetsordning: AI Hub → f1_ai_api_key → (legacy grocery key)
    """
    if _ai_busy[0]:
        return None
    _ai_busy[0] = True
    try:
        # Provider: f1_ai_provider → ai_hub_default_provider → auto
        provider = (state.get("input_select.f1_ai_provider") or "").strip().lower()
        if not provider or provider == "auto":
            hub_default = (state.get("input_select.ai_hub_default_provider") or "auto").strip().lower()
            provider = hub_default

        if provider == "groq":
            key = _resolve_key("groq")
            if not _ai_key_ok(key):
                log.warning("[OpenF1-AI] Groq valt men ingen nyckel – kontrollera AI Hub eller input_text.f1_ai_api_key")
                return None
            return await _call_groq(key, prompt, max_tokens)

        if provider == "anthropic":
            key = _resolve_key("anthropic")
            if not _ai_key_ok(key):
                log.warning("[OpenF1-AI] Anthropic valt men ingen nyckel")
                return None
            return await _call_anthropic(key, prompt, max_tokens)

        if provider == "openai":
            key = _resolve_key("openai")
            if not _ai_key_ok(key):
                log.warning("[OpenF1-AI] OpenAI valt men ingen nyckel")
                return None
            return await _call_openai(key, prompt, max_tokens)

        if provider == "ha_ai_task":
            return await _call_ha_ai_task(prompt)

        # auto: prova Groq → Anthropic → OpenAI → ha_ai_task
        for prov, call_fn in [
            ("groq",      _call_groq),
            ("anthropic", _call_anthropic),
            ("openai",    _call_openai),
        ]:
            key = _resolve_key(prov)
            if _ai_key_ok(key):
                result = await call_fn(key, prompt, max_tokens)
                if result:
                    return result
        return await _call_ha_ai_task(prompt)

    finally:
        _ai_busy[0] = False


async def _ai_race_commentary(flag, message, lap):
    """Genererar EN MENING live-kommentar vid signifikant race-händelse."""
    if state.get("input_boolean.f1_ai_commentary") != "on":
        return

    now_ts = _now_utc().timestamp()
    if now_ts - _last_commentary_ts[0] < 120:
        return   # Cooldown 2 min – undviker spam vid snabba händelseserier

    circuit = ""
    try:
        circuit = state.get("sensor.f1_session_status.circuit") or _session_name[0]
    except Exception:
        circuit = _session_name[0]

    # Dynamisk positionssträng för alla konfigurerade förare
    pos_parts = []
    for drv_num, info in _FOLLOWED.items():
        p = state.get(f"sensor.f1_d{info['slot']}_position") or "–"
        g = state.get(f"sensor.f1_d{info['slot']}_gap") or "–"
        pos_parts.append(f"{info['name']} P{p} ({g})")
    positions_txt = ", ".join(pos_parts) or "inga konfigurerade förare"
    lap_txt = f"varv {lap}" if lap else ""

    prompt = (
        f"Du är F1 TV-kommentator. Skriv EN MENING på svenska (max 120 tecken), "
        f"engagerande och dramatisk som på riktig TV.\n\n"
        f"Session: {_session_type[0]} – {circuit}{', ' + lap_txt if lap_txt else ''}\n"
        f"Händelse: {flag} – {message}\n"
        f"Positioner: {positions_txt}\n\n"
        f"Kommentar (EN mening, svenska, max 120 tecken):"
    )

    text = await _ask_ai(prompt, max_tokens=60)
    if not text:
        return

    _last_commentary_ts[0] = _now_utc().timestamp()
    text = text[:200].strip('"').strip()

    state.set("sensor.f1_ai_commentary", text, {
        "friendly_name": "F1 – AI-kommentator",
        "icon": "mdi:microphone",
        "event": f"{flag}: {message}",
        "lap": lap,
        "timestamp": _now_utc().isoformat(),
    })
    notify.notify(title="🎙️ F1", message=text)
    log.info(f"[OpenF1-AI] Kommentar: {text[:80]}")


async def _ai_session_recap():
    """Genererar AI-referat (~80 ord) direkt när en session avslutas."""
    if state.get("input_boolean.f1_ai_recap") != "on":
        return

    session_name = _session_name[0]

    history_lines = []
    for h in list(reversed(_rc_history)):
        lap_txt = f" (V{h['lap']})" if h.get("lap") else ""
        history_lines.append(f"- {h.get('flag', '')} {h.get('message', '')}{lap_txt}")
    history_txt = "\n".join(history_lines[:12]) or "Ingen tillgänglig historik."

    # Dynamisk slutpositionssträng
    final_parts = []
    for drv_num, info in _FOLLOWED.items():
        p = state.get(f"sensor.f1_d{info['slot']}_position") or "–"
        final_parts.append(f"{info['name']} P{p}")
    final_txt = ", ".join(final_parts) or "okänt resultat"

    prompt = (
        f"Du är F1-journalist. Skriv ett kort referat (70-100 ord) på svenska.\n\n"
        f"Session: {session_name}\n"
        f"Händelser (kronologisk):\n{history_txt}\n\n"
        f"Slutpositioner: {final_txt}\n\n"
        f"Fokusera på drama och nyckelhändelser. Avsluta med en mening om vad nästa "
        f"session kan innebära.\nReferat:"
    )

    text = await _ask_ai(prompt, max_tokens=200)
    if not text:
        return

    text = text[:600].strip()
    state.set("sensor.f1_ai_recap", text, {
        "friendly_name": "F1 – AI-sessionreferat",
        "icon": "mdi:newspaper",
        "session": session_name,
        "timestamp": _now_utc().isoformat(),
    })
    notify.notify(title=f"📰 F1: {session_name}", message=text[:300])
    log.info(f"[OpenF1-AI] Referat genererat: {session_name}")


# ─── Mästerskap (standings) ───────────────────────────────────────────────────

async def _fetch_standings():
    """Hämtar förare- och konstruktörsmästerskap. Kör max 1 gång/timme.
    Primär: openf1.org. Fallback: Jolpica/Ergast (har alltid aktuell data)."""
    year = _now_utc().year

    # ── Förarmästerskap ──────────────────────────────────────────────────────
    drv_data = await _get("drivers_championship", {"year": year})
    if drv_data:
        # openf1.org-format
        drv_sorted = sorted(drv_data, key=lambda d: d.get("position", 99))
        lines = []
        summary_parts = []
        for d in drv_sorted[:10]:
            pos  = d.get("position", "?")
            abbr = (d.get("name_acronym") or d.get("broadcast_name") or "UNK")[:3].upper()
            pts  = int(d.get("points") or 0)
            lines.append(f"{pos}.{abbr} {pts}p")
            if len(summary_parts) < 3:
                summary_parts.append(f"{abbr} {pts}")
        state.set("sensor.f1_driver_standings", "|".join(lines), {
            "friendly_name": "F1 – Förarmästerskap",
            "icon": "mdi:trophy",
            "summary": " · ".join(summary_parts),
            "year": year,
            "source": "openf1",
        })
        log.info(f"[OpenF1] Förare-standings (openf1): {' · '.join(summary_parts)}")
    else:
        # Fallback: Jolpica/Ergast
        log.info("[OpenF1] openf1.org saknar standings – försöker Jolpica")
        jdata = await _get_jolpica(f"{year}/driverStandings.json")
        try:
            slists = jdata["MRData"]["StandingsTable"]["StandingsLists"]
            drv_list = slists[0]["DriverStandings"] if slists else []
        except Exception:
            drv_list = []
        if drv_list:
            lines = []
            summary_parts = []
            for d in drv_list[:10]:
                pos  = d.get("position", "?")
                abbr = (d.get("Driver", {}).get("code") or "UNK")[:3].upper()
                pts  = int(float(d.get("points") or 0))
                lines.append(f"{pos}.{abbr} {pts}p")
                if len(summary_parts) < 3:
                    summary_parts.append(f"{abbr} {pts}")
            state.set("sensor.f1_driver_standings", "|".join(lines), {
                "friendly_name": "F1 – Förarmästerskap",
                "icon": "mdi:trophy",
                "summary": " · ".join(summary_parts),
                "year": year,
                "source": "jolpica",
            })
            log.info(f"[OpenF1] Förare-standings (jolpica): {' · '.join(summary_parts)}")
        else:
            state.set("sensor.f1_driver_standings", "–", {
                "friendly_name": "F1 – Förarmästerskap",
                "icon": "mdi:trophy",
                "summary": f"{year} säsongen ej startad",
                "year": year,
            })

    # ── Konstruktörsmästerskap ───────────────────────────────────────────────
    con_data = await _get("teams_championship", {"year": year})
    if con_data:
        # openf1.org-format
        con_sorted = sorted(con_data, key=lambda t: t.get("position", 99))
        lines = []
        summary_parts = []
        for t in con_sorted[:10]:
            pos  = t.get("position", "?")
            name = t.get("team_name", "?")
            abbr = TEAM_ABBR.get(name, name[:3].upper())
            pts  = int(t.get("points") or 0)
            lines.append(f"{pos}.{abbr} {pts}p")
            if len(summary_parts) < 3:
                summary_parts.append(f"{abbr} {pts}")
        state.set("sensor.f1_constructor_standings", "|".join(lines), {
            "friendly_name": "F1 – Konstruktörsmästerskap",
            "icon": "mdi:wrench-outline",
            "summary": " · ".join(summary_parts),
            "year": year,
            "source": "openf1",
        })
        log.info(f"[OpenF1] Konstruktörs-standings (openf1): {' · '.join(summary_parts)}")
    else:
        # Fallback: Jolpica/Ergast
        jdata = await _get_jolpica(f"{year}/constructorStandings.json")
        try:
            slists = jdata["MRData"]["StandingsTable"]["StandingsLists"]
            con_list = slists[0]["ConstructorStandings"] if slists else []
        except Exception:
            con_list = []
        if con_list:
            lines = []
            summary_parts = []
            for t in con_list[:10]:
                pos  = t.get("position", "?")
                name = t.get("Constructor", {}).get("name", "?")
                abbr = TEAM_ABBR.get(name, name[:3].upper())
                pts  = int(float(t.get("points") or 0))
                lines.append(f"{pos}.{abbr} {pts}p")
                if len(summary_parts) < 3:
                    summary_parts.append(f"{abbr} {pts}")
            state.set("sensor.f1_constructor_standings", "|".join(lines), {
                "friendly_name": "F1 – Konstruktörsmästerskap",
                "icon": "mdi:wrench-outline",
                "summary": " · ".join(summary_parts),
                "year": year,
                "source": "jolpica",
            })
            log.info(f"[OpenF1] Konstruktörs-standings (jolpica): {' · '.join(summary_parts)}")
        else:
            state.set("sensor.f1_constructor_standings", "–", {
                "friendly_name": "F1 – Konstruktörsmästerskap",
                "icon": "mdi:wrench-outline",
                "summary": f"{year} säsongen ej startad",
                "year": year,
            })

    _last_standings_check[0] = _now_utc().timestamp()

# ─── Följda förare – konfigurations-trigger ───────────────────────────────────

@state_trigger("input_number.f1_followed_1", "input_number.f1_followed_2", "input_number.f1_followed_3")
async def _on_followed_changed(**kwargs):
    """Kör när användaren ändrar vilka förare som följs."""
    log.info("[OpenF1] Följda förare ändrade – uppdaterar sensorer")
    _init_driver_sensors()
    if _session_active[0]:
        # Hämta data direkt för eventuellt ny förare
        await _poll_positions()
        await _poll_intervals()
        await _poll_tyres()

# ─── Manuell refresh-service ──────────────────────────────────────────────────

@service
async def openf1_refresh():
    """Tvinga omedelbar uppdatering av alla F1-sensorer."""
    log.info("[OpenF1] Manuell refresh...")
    _last_standings_check[0] = 0.0   # Tvinga standings-hämtning
    _all_positions.clear()
    _all_gaps.clear()
    _all_compounds.clear()
    await _check_sessions()
    if _session_key[0]:
        await _fetch_driver_info()
    if _session_active[0]:
        await _poll_race_control()
        await _poll_positions()
        await _poll_intervals()
        await _poll_tyres()
        await _poll_pits()
    await _fetch_standings()
    log.info("[OpenF1] Refresh klar.")

# ─── Huvud-poll-loop (var 30s) ────────────────────────────────────────────────

@time_trigger("period(now, 30s)")
async def _poll():
    import time
    now_ts = _now_utc().timestamp()

    # Kolla sessions var SESSION_CHECK_SECS sekunder
    if now_ts - _last_session_check[0] >= SESSION_CHECK_SECS:
        await _check_sessions()

    # Uppdatera standings var STANDINGS_CHECK_SECS sekunder (oavsett session)
    if now_ts - _last_standings_check[0] >= STANDINGS_CHECK_SECS:
        await _fetch_standings()

    # AI-sessionreferat om session just avslutats
    if _recap_pending[0] and not _ai_busy[0]:
        _recap_pending[0] = False
        await _ai_session_recap()

    # Uppdatera countdown alltid
    _update_countdown()

    # Live data bara under aktiv session
    if not _session_active[0]:
        return

    await _poll_race_control()
    await _poll_positions()
    await _poll_intervals()
    await _poll_tyres()
    await _poll_pits()

# ─── Startup ─────────────────────────────────────────────────────────────────

@time_trigger("startup")
async def _startup():
    # Initiera alla sensorer
    try:
        state.set("sensor.f1_session_status", "inactive", {
            "friendly_name": "F1 – Session",
            "icon": "mdi:racing-helmet",
            "session_name": "Startar...",
        })
        state.set("sensor.f1_flag", "–", {
            "friendly_name": "F1 – Flagga",
            "icon": "mdi:flag",
            "message": "",
            "history": [],
        })
        state.set("sensor.f1_lap", "–", {
            "friendly_name": "F1 – Varv",
            "icon": "mdi:counter",
        })
        state.set("sensor.f1_next_session", "Hämtar...", {
            "friendly_name": "F1 – Nästa session",
            "icon": "mdi:clock-countdown",
            "session_name": "",
            "date_start": "",
        })
        state.set("sensor.f1_race_control_msg", "–", {
            "friendly_name": "F1 – Senaste Race Control",
            "icon": "mdi:message-alert-outline",
        })
        state.set("sensor.f1_live_grid", "0", {
            "friendly_name": "F1 – Live Grid",
            "icon": "mdi:format-list-numbered",
            "grid": [],
        })
        state.set("sensor.f1_grid_display", "", {
            "friendly_name": "F1 – Grid Display",
            "icon": "mdi:format-list-numbered",
        })
        state.set("sensor.f1_ai_commentary", "–", {
            "friendly_name": "F1 – AI-kommentator",
            "icon": "mdi:microphone",
            "event": "",
            "timestamp": "",
        })
        state.set("sensor.f1_ai_recap", "–", {
            "friendly_name": "F1 – AI-sessionreferat",
            "icon": "mdi:newspaper",
            "session": "",
            "timestamp": "",
        })
        state.set("sensor.f1_driver_standings", "Hämtar...", {
            "friendly_name": "F1 – Förarmästerskap",
            "icon": "mdi:trophy",
            "summary": "",
        })
        state.set("sensor.f1_constructor_standings", "Hämtar...", {
            "friendly_name": "F1 – Konstruktörsmästerskap",
            "icon": "mdi:wrench-outline",
            "summary": "",
        })
        state.set("sensor.f1_available_drivers", "0", {
            "friendly_name": "F1 – Tillgängliga förare",
            "icon": "mdi:account-group",
            "drivers": [],
        })
        _init_driver_sensors()   # skapar d1/d2/d3-sensorer + namn-sensorer
    except Exception as e:
        log.error(f"[OpenF1] Sensor-init misslyckades: {e}")

    # Hämta session direkt
    try:
        await _check_sessions()
    except Exception as e:
        log.error(f"[OpenF1] Session-check vid startup misslyckades: {e}")

    # Hämta standings vid start
    try:
        await _fetch_standings()
    except Exception as e:
        log.error(f"[OpenF1] Standings-hämtning vid startup misslyckades: {e}")

    drivers_txt = " · ".join([f"{v['name']} #{k}" for k,v in _FOLLOWED.items()])
    log.info(f"[OpenF1] OpenF1 v1.3 startad. Följer: {drivers_txt or '(inga konfigurerade)'}")
