import streamlit as st
import requests
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# --- Nastavení aplikace ---
st.set_page_config(page_title="F1 Live Timing", layout="wide")

# Obnovování každé 3 sekundy
st_autorefresh(interval=3000, key="f1_timing_refresh")

# Čistý tmavý CSS styl
st.markdown("""
    <style>
        .stApp { background-color: #0E0E12; color: #FFFFFF; }
        .title { 
            font-size: 28px; font-weight: bold; text-align: center; 
            color: #E10600; margin-bottom: 20px; letter-spacing: 1px; 
        }
    </style>
""", unsafe_allow_html=True)

# Bezpečné stažení JSON dat z OpenF1 API
@st.cache_data(ttl=2)
def safe_get_json(url):
    try:
        res = requests.get(url, headers={'User-Agent': 'F1LiveTiming/1.0'}, timeout=4)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list):
                return data
        return []
    except Exception:
        return []

# --- Načtení živé nebo nejnovější dostupné relace ---
sessions_raw = safe_get_json("https://api.openf1.org/v1/sessions")
session_name = "F1 LIVE TIMING"

drivers_raw = safe_get_json("https://api.openf1.org/v1/drivers?session_key=latest")
laps_raw = safe_get_json("https://api.openf1.org/v1/laps?session_key=latest")

# Fallback: Pokud 'latest' nemá data, najdeme v historii nejnovější relaci, která data má
if (not drivers_raw or not laps_raw) and sessions_raw:
    for s in reversed(sessions_raw):
        sk = str(s.get("session_key"))
        d_test = safe_get_json(f"https://api.openf1.org/v1/drivers?session_key={sk}")
        l_test = safe_get_json(f"https://api.openf1.org/v1/laps?session_key={sk}")
        if d_test and l_test:
            drivers_raw = d_test
            laps_raw = l_test
            session_name = f"{s.get('location', 'F1 GP')} — {s.get('session_name', 'Session')}"
            break

st.markdown(f'<div class="title">⏱️ {session_name}</div>', unsafe_allow_html=True)

# Pomocná funkce pro formátování sekund na m:ss.ms
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

# --- Vykreslení tabulky časů ---
if not drivers_raw:
    st.info("⌛ Čekám na data z trati...")
else:
    driver_map = {d.get('driver_number'): d.get('name_acronym', f"#{d.get('driver_number')}") for d in drivers_raw if isinstance(d, dict) and 'driver_number' in d}
    team_map = {d.get('driver_number'): d.get('team_name', '-') for d in drivers_raw if isinstance(d, dict) and 'driver_number' in d}

    df_laps = pd.DataFrame(laps_raw) if laps_raw else pd.DataFrame()

    # Nejlepší absolutní časy pro fialové zvýraznění
    best_s1 = df_laps['duration_sector_1'].min() if not df_laps.empty and 'duration_sector_1' in df_laps else None
    best_s2 = df_laps['duration_sector_2'].min() if not df_laps.empty and 'duration_sector_2' in df_laps else None
    best_s3 = df_laps['duration_sector_3'].min() if not df_laps.empty and 'duration_sector_3' in df_laps else None
    best_lap = df_laps['lap_duration'].min() if not df_laps.empty and 'lap_duration' in df_laps else None

    rows = []
    for d_num, d_acronym in driver_map.items():
        driver_laps = df_laps[df_laps['driver_number'] == d_num] if not df_laps.empty and 'driver_number' in df_laps else pd.DataFrame()

        s1, s2, s3, lap_t = None, None, None, None
        current_lap = 0

        if not driver_laps.empty:
            last_lap = driver_laps.sort_values('lap_number').iloc[-1]
            s1 = last_lap.get('duration_sector_1')
            s2 = last_lap.get('duration_sector_2')
            s3 = last_lap.get('duration_sector_3')
            lap_t = last_lap.get('lap_duration')
            current_lap = int(last_lap.get('lap_number')) if pd.notna(last_lap.get('lap_number')) else 0

        rows.append({
            "Jezdec": d_acronym,
            "Tým": team_map.get(d_num, "-"),
            "Kolo": current_lap if current_lap > 0 else "-",
            "Sektor 1": fmt_time(s1),
            "Sektor 2": fmt_time(s2),
            "Sektor 3": fmt_time(s3),
            "Čas kola": fmt_time(lap_t),
            "lap_t_val": lap_t if pd.notna(lap_t) else 9999,
            "_b_s1": abs(s1 - best_s1) < 0.001 if (pd.notna(s1) and best_s1 and isinstance(s1, (int, float))) else False,
            "_b_s2": abs(s2 - best_s2) < 0.001 if (pd.notna(s2) and best_s2 and isinstance(s2, (int, float))) else False,
            "_b_s3": abs(s3 - best_s3) < 0.001 if (pd.notna(s3) and best_s3 and isinstance(s3, (int, float))) else False,
            "_b_lap": abs(lap_t - best_lap) < 0.001 if (pd.notna(lap_t) and best_lap and isinstance(lap_t, (int, float))) else False,
        })

    df_final = pd.DataFrame(rows)
    if not df_final.empty:
        # Seřazení podle času
        df_final = df_final.sort_values('lap_t_val').reset_index(drop=True)
        df_final.insert(0, 'Pozice', [f"P{i+1}" for i in range(len(df_final))])

        # Fialové zvýraznění nejlepších časů
        def highlight_bests(row):
            styles = [''] * len(row)
            purple = 'background-color: #8A2BE2; color: #FFFFFF; font-weight: bold;'
            if row.get('_b_s1'): styles[5] = purple
            if row.get('_b_s2'): styles[6] = purple
            if row.get('_b_s3'): styles[7] = purple
            if row.get('_b_lap'): styles[8] = purple
            return styles

        display_cols = ["Pozice", "Jezdec", "Tým", "Kolo", "Sektor 1", "Sektor 2", "Sektor 3", "Čas kola"]
        styled = df_final.style.apply(highlight_bests, axis=1)

        st.dataframe(styled, column_order=display_cols, use_container_width=True, height=750, hide_index=True)
