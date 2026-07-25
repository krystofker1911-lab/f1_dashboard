import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone
from streamlit_autorefresh import st_autorefresh

# --- 1. Nastavení aplikace ---
st.set_page_config(page_title="F1 Pit Wall Timing", layout="wide", initial_sidebar_state="collapsed")

# Vlastní CSS styly pro F1 Pit Wall
st.markdown("""
    <style>
        .stApp { background-color: #0E0E12; color: #FFFFFF; }
        .session-header {
            font-size: 22px; font-weight: bold; text-align: center;
            color: #E10600; margin-bottom: 8px; letter-spacing: 1px;
        }
        .track-status-box {
            padding: 12px; border-radius: 10px; text-align: center;
            font-size: 24px; font-weight: bold; margin-bottom: 12px;
            text-transform: uppercase; letter-spacing: 2px;
        }
        .status-green { background-color: #00D26A; color: #000; }
        .status-yellow { background-color: #FFCC00; color: #000; }
        .status-sc { background-color: #FF8800; color: #FFF; animation: blink 1s infinite; }
        .status-red { background-color: #FF1801; color: #FFF; animation: blink 0.6s infinite; }
        .status-vsc { background-color: #E67E22; color: #FFF; }
        .status-closed { background-color: #1E1E26; color: #FF4444; border: 2px solid #FF4444; }
        
        .countdown-box {
            background-color: #16161E;
            border: 1px solid #00E5FF;
            border-radius: 8px;
            padding: 10px;
            text-align: center;
            font-size: 18px;
            font-weight: bold;
            color: #00E5FF;
            margin-bottom: 15px;
            box-shadow: 0px 0px 10px rgba(0, 229, 255, 0.2);
        }
        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }
    </style>
""", unsafe_allow_html=True)

# Bezpečné stažení JSON dat z API
def safe_get_json(url):
    try:
        res = requests.get(url, timeout=3)
        data = res.json()
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []

# --- 2. Kontrola kalendáře a relace ---
now_utc = datetime.now(timezone.utc)
year = now_utc.year
all_sessions = safe_get_json(f"https://api.openf1.org/v1/sessions?year={year}")

active_session = None
next_session = None

if all_sessions:
    for s in all_sessions:
        try:
            start_dt = pd.to_datetime(s.get('date_start'))
            end_dt = pd.to_datetime(s.get('date_end'))
            start_utc = start_dt.tz_localize('UTC') if start_dt.tzinfo is None else start_dt.tz_convert('UTC')
            end_utc = end_dt.tz_localize('UTC') if end_dt.tzinfo is None else end_dt.tz_convert('UTC')

            if start_utc <= now_utc <= end_utc:
                active_session = s
                break
            elif start_utc > now_utc:
                if next_session is None:
                    next_session = s
                else:
                    curr_next = pd.to_datetime(next_session.get('date_start'))
                    curr_next_utc = curr_next.tz_localize('UTC') if curr_next.tzinfo is None else curr_next.tz_convert('UTC')
                    if start_utc < curr_next_utc:
                        next_session = s
        except Exception:
            continue

# AUTO-REFRESH SPUŠTĚN POUZE POKUD JE RELACE AKTIVNÍ (LIVE)
if active_session:
    st_autorefresh(interval=3000, key="f1_live_refresh")

if active_session:
    session_key = active_session.get("session_key", "latest")
    session_title = f"🔴 LIVE TIMING — {active_session.get('location', '')} ({active_session.get('session_name', '')})"
else:
    session_key = "latest"
    session_title = "🏎️ FORMULA 1 — VÝSLEDKY POSLEDNÍ RELACE"

st.markdown(f'<div class="session-header">{session_title}</div>', unsafe_allow_html=True)

# --- 3. Načtení dat a stavu ---
drivers_raw = safe_get_json(f"https://api.openf1.org/v1/drivers?session_key={session_key}")
status_raw = safe_get_json(f"https://api.openf1.org/v1/track_status?session_key={session_key}")
laps_raw = safe_get_json(f"https://api.openf1.org/v1/laps?session_key={session_key}")

if active_session:
    status_code = 1
    if status_raw and len(status_raw) > 0:
        last_item = status_raw[-1]
        if isinstance(last_item, dict):
            status_code = last_item.get("status_code", 1)

    status_mapping = {
        1: ("🟢 TRAŤ ČISTÁ / GREEN FLAG", "status-green"),
        2: ("🟡 ŽLUTÁ VLAJKA / YELLOW FLAG", "status-yellow"),
        4: ("🚨 SAFETY CAR (SC) ON TRACK", "status-sc"),
        5: ("🚩 ČERVENÁ VLAJKA / RED FLAG", "status-red"),
        6: ("⚠️ VIRTUAL SAFETY CAR (VSC)", "status-vsc"),
        7: ("⚠️ VIRTUAL SAFETY CAR (VSC)", "status-vsc"),
    }
    status_text, status_class = status_mapping.get(int(status_code), ("🟢 TRAŤ OTEVŘENA", "status-green"))
    st.markdown(f'<div class="track-status-box {status_class}">{status_text}</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="track-status-box status-closed">🔴 TRAŤ JE UZAVŘENA / TRACK CLOSED</div>', unsafe_allow_html=True)

    if next_session:
        try:
            s_start = pd.to_datetime(next_session['date_start'])
            s_start_utc = s_start.tz_localize('UTC') if s_start.tzinfo is None else s_start.tz_convert('UTC')
            diff = s_start_utc - now_utc

            days = diff.days
            hours, remainder = divmod(diff.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            loc = next_session.get('location', 'F1 Grand Prix')
            s_name = next_session.get('session_name', 'Session')

            if days > 0:
                time_str = f"{days}d {hours}h {minutes}m {seconds}s"
            else:
                time_str = f"{hours}h {minutes}m {seconds}s"

            st.markdown(f'<div class="countdown-box">⏱️ Další relace: <b>{loc} — {s_name}</b> za <b>{time_str}</b></div>', unsafe_allow_html=True)
        except Exception:
            st.markdown('<div class="countdown-box">⏱️ Čekám na další relaci F1...</div>', unsafe_allow_html=True)

if not laps_raw:
    st.info("⌛ Čekám na data z trati...")
    st.stop()

# --- 4. Zpracování časů a tabulky ---
driver_map = {d.get('driver_number'): d.get('name_acronym', f"#{d.get('driver_number')}") for d in drivers_raw if isinstance(d, dict) and 'driver_number' in d}
team_map = {d.get('driver_number'): d.get('team_name', '-') for d in drivers_raw if isinstance(d, dict) and 'driver_number' in d}

df_laps = pd.DataFrame(laps_raw)

if df_laps.empty or 'lap_number' not in df_laps.columns or 'driver_number' not in df_laps.columns:
    st.info("⌛ Čekám na dokončená kola...")
    st.stop()

df_valid = df_laps.dropna(subset=['lap_duration']) if 'lap_duration' in df_laps.columns else pd.DataFrame()

best_s1 = df_valid['duration_sector_1'].min() if not df_valid.empty and 'duration_sector_1' in df_valid else None
best_s2 = df_valid['duration_sector_2'].min() if not df_valid.empty and 'duration_sector_2' in df_valid else None
best_s3 = df_valid['duration_sector_3'].min() if not df_valid.empty and 'duration_sector_3' in df_valid else None
best_lap = df_valid['lap_duration'].min() if not df_valid.empty and 'lap_duration' in df_valid else None

latest_laps = df_laps.sort_values('lap_number').groupby('driver_number').last().reset_index()

def fmt_time(seconds):
    if pd.isna(seconds) or seconds is None:
        return "-"
    try:
        sec_val = float(seconds)
        m = int(sec_val // 60)
        s = sec_val % 60
        return f"{m}:{s:06.3f}" if m > 0 else f"{s:.3f}"
    except Exception:
        return "-"

table_rows = []
for _, row in latest_laps.iterrows():
    num = row.get('driver_number')
    s1 = row.get('duration_sector_1')
    s2 = row.get('duration_sector_2')
    s3 = row.get('duration_sector_3')
    lap_t = row.get('lap_duration')

    table_rows.append({
        "Jezdec": driver_map.get(num, f"#{num}"),
        "Tým": team_map.get(num, "-"),
        "Kolo": int(row.get('lap_number')) if pd.notna(row.get('lap_number')) else "-",
        "Sektor 1": fmt_time(s1),
        "Sektor 2": fmt_time(s2),
        "Sektor 3": fmt_time(s3),
        "Čas kola": fmt_time(lap_t),
        "_b_s1": abs(s1 - best_s1) < 0.001 if (pd.notna(s1) and best_s1 and isinstance(s1, (int, float))) else False,
        "_b_s2": abs(s2 - best_s2) < 0.001 if (pd.notna(s2) and best_s2 and isinstance(s2, (int, float))) else False,
        "_b_s3": abs(s3 - best_s3) < 0.001 if (pd.notna(s3) and best_s3 and isinstance(s3, (int, float))) else False,
        "_b_lap": abs(lap_t - best_lap) < 0.001 if (pd.notna(lap_t) and best_lap and isinstance(lap_t, (int, float))) else False,
    })

df_final = pd.DataFrame(table_rows)

def highlight_bests(row):
    styles = [''] * len(row)
    purple_style = 'background-color: #8A2BE2; color: #FFFFFF; font-weight: bold;'
    if row.get('_b_s1'): styles[3] = purple_style
    if row.get('_b_s2'): styles[4] = purple_style
    if row.get('_b_s3'): styles[5] = purple_style
    if row.get('_b_lap'): styles[6] = purple_style
    return styles

display_cols = ["Jezdec", "Tým", "Kolo", "Sektor 1", "Sektor 2", "Sektor 3", "Čas kola"]
styled_table = df_final.style.apply(highlight_bests, axis=1)

st.dataframe(styled_table, column_order=display_cols, use_container_width=True, height=700, hide_index=True)
