import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- 1. Nastavení aplikace ---
st.set_page_config(page_title="F1 Pro Pit Wall", layout="wide", initial_sidebar_state="expanded")

# Obnovování každých 5 sekund
st_autorefresh(interval=5000, key="f1_refresh")

st.markdown("""
    <style>
        .stApp { background-color: #0E0E12; color: #FFFFFF; }
        .session-header {
            font-size: 24px; font-weight: bold; text-align: center;
            color: #E10600; margin-bottom: 10px; letter-spacing: 1px;
        }
        .track-status-box {
            padding: 10px; border-radius: 8px; text-align: center;
            font-size: 20px; font-weight: bold; margin-bottom: 15px;
            text-transform: uppercase; letter-spacing: 1px;
        }
        .status-green { background-color: #00D26A; color: #000; }
        .status-yellow { background-color: #FFCC00; color: #000; border: 2px solid #FFD700; }
        .status-sc { background-color: #FF8800; color: #FFF; }
        .status-red { background-color: #FF1801; color: #FFF; }
        .status-vsc { background-color: #E67E22; color: #FFF; }
        
        .telemetry-card {
            background-color: #16161E; border-radius: 8px; padding: 15px;
            text-align: center; border: 1px solid #2A2A36; margin-bottom: 10px;
        }
        .telemetry-val { font-size: 32px; font-weight: bold; color: #00E5FF; }
        .drs-open { background-color: #00D26A; color: #000; padding: 6px; border-radius: 6px; font-weight: bold; }
        .drs-closed { background-color: #FF1801; color: #FFF; padding: 6px; border-radius: 6px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# Stahování seznamu relací s dlouhou pamětí (300 s), aby se menu načetlo okamžitě
@st.cache_data(ttl=300)
def fetch_sessions_list():
    current_yr = datetime.now().year
    for yr in [current_yr, current_yr - 1, 2024]:
        url = f"https://api.openf1.org/v1/sessions?year={yr}"
        try:
            res = requests.get(url, headers={'User-Agent': 'F1PitWall/1.0'}, timeout=5)
            if res.status_code == 200 and isinstance(res.json(), list) and len(res.json()) > 0:
                return res.json()
        except Exception:
            pass
    return []

# Stahování živých dat (krátká paměť 3 s)
@st.cache_data(ttl=3)
def fetch_openf1(endpoint, params=None):
    url = f"https://api.openf1.org/v1/{endpoint}"
    try:
        res = requests.get(url, params=params, headers={'User-Agent': 'F1PitWall/1.0'}, timeout=4)
        if res.status_code == 200 and isinstance(res.json(), list):
            return res.json()
        return []
    except Exception:
        return []

# Formátování času
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

# --- 2. Zobrazení postranního menu ---
st.sidebar.title("🏎️ F1 Pit Wall")

sessions_raw = fetch_sessions_list()
session_options = {}

if sessions_raw:
    for s in reversed(sessions_raw):
        sk = str(s.get("session_key"))
        loc = s.get('location', 'F1 GP')
        s_name = s.get('session_name', 'Session')
        yr = s.get('year', '')
        label = f"{loc} — {s_name} ({yr})"
        session_options[label] = sk

# POJISTKA: Menu už nikdy nezůstane prázdné
if not session_options:
    session_options["🔴 Živý přenos (latest)"] = "latest"

selected_label = st.sidebar.selectbox("Vyber relaci ze seznamu:", list(session_options.keys()), index=0)
session_key = session_options[selected_label]

st.markdown(f'<div class="session-header">🔴 {selected_label}</div>', unsafe_allow_html=True)

# --- 3. Načtení dat trati ---
drivers_raw = fetch_openf1("drivers", {"session_key": session_key})
laps_raw = fetch_openf1("laps", {"session_key": session_key})

# Fallback: Pokud vybraná relace nemá jezdce, načteme poslední relaci s daty
if not drivers_raw and sessions_raw:
    for s in reversed(sessions_raw):
        sk = str(s.get("session_key"))
        test_d = fetch_openf1("drivers", {"session_key": sk})
        if test_d:
            session_key = sk
            drivers_raw = test_d
            laps_raw = fetch_openf1("laps", {"session_key": sk})
            break

status_raw = fetch_openf1("track_status", {"session_key": session_key})
stints_raw = fetch_openf1("stints", {"session_key": session_key})
pits_raw = fetch_openf1("pit", {"session_key": session_key})

driver_map = {d.get('driver_number'): d.get('name_acronym', f"#{d.get('driver_number')}") for d in drivers_raw if isinstance(d, dict) and 'driver_number' in d}
team_map = {d.get('driver_number'): d.get('team_name', '-') for d in drivers_raw if isinstance(d, dict) and 'driver_number' in d}

# Stav trati
status_code = 1
if status_raw and len(status_raw) > 0:
    last_status = status_raw[-1]
    if isinstance(last_status, dict):
        status_code = last_status.get("status_code", 1)

status_mapping = {
    1: ("🟢 TRAŤ ČISTÁ / GREEN FLAG", "status-green"),
    2: ("⚠️ ŽLUTÁ VLAJKA / YELLOW FLAG", "status-yellow"),
    3: ("⚠️ DVOJITÁ ŽLUTÁ VLAJKA / DOUBLE YELLOW", "status-yellow"),
    4: ("🚨 SAFETY CAR (SC)", "status-sc"),
    5: ("🚩 ČERVENÁ VLAJKA / RED FLAG", "status-red"),
    6: ("⚠️ VIRTUAL SAFETY CAR (VSC)", "status-vsc"),
    7: ("⚠️ VIRTUAL SAFETY CAR (VSC)", "status-vsc"),
}
status_text, status_css = status_mapping.get(int(status_code), ("🟢 TRAŤ OTEVŘENA", "status-green"))
st.markdown(f'<div class="track-status-box {status_css}">{status_text}</div>', unsafe_allow_html=True)

# Stinty a Pit stopy
current_stints_map = {}
if stints_raw:
    df_stints = pd.DataFrame(stints_raw)
    if not df_stints.empty and 'driver_number' in df_stints.columns:
        latest_stints = df_stints.sort_values('stint').groupby('driver_number').last().reset_index()
        for _, st_row in latest_stints.iterrows():
            d_num = st_row['driver_number']
            comp = str(st_row.get('compound', 'UNKNOWN')).upper()
            tyre_icon = "🔴" if "SOFT" in comp else ("🟡" if "MEDIUM" in comp else ("⚪" if "HARD" in comp else ("🟢" if "INTER" in comp else ("🔵" if "WET" in comp else "🔘"))))
            current_stints_map[d_num] = {
                "compound_str": f"{tyre_icon} {comp}",
                "stint_num": f"S{st_row.get('stint', 1)}",
                "lap_start": st_row.get('lap_start', 1)
            }

pit_drivers = set()
if pits_raw:
    df_pits = pd.DataFrame(pits_raw)
    if not df_pits.empty and 'driver_number' in df_pits.columns:
        latest_pits = df_pits.groupby('driver_number').last().reset_index()
        for _, p_row in latest_pits.iterrows():
            pit_drivers.add(p_row['driver_number'])

# --- 4. Záložky ---
tab_timing, tab_cockpit, tab_map, tab_stints, tab_radio = st.tabs(["📊 Live Timing", "🏎️ Kokpit Telemetrie", "🗺️ Mapa okruhu", "🛞 Stinty & Pneu", "📻 Radio"])

with tab_timing:
    if not driver_map:
        st.info("⌛ Čekám na načtení jezdců...")
    else:
        df_laps = pd.DataFrame(laps_raw) if laps_raw else pd.DataFrame()

        best_s1 = df_laps['duration_sector_1'].min() if not df_laps.empty and 'duration_sector_1' in df_laps else None
        best_s2 = df_laps['duration_sector_2'].min() if not df_laps.empty and 'duration_sector_2' in df_laps else None
        best_s3 = df_laps['duration_sector_3'].min() if not df_laps.empty and 'duration_sector_3' in df_laps else None
        best_lap = df_laps['lap_duration'].min() if not df_laps.empty and 'lap_duration' in df_laps else None

        rows = []
        for d_num, d_acronym in driver_map.items():
            driver_laps = df_laps[df_laps['driver_number'] == d_num] if not df_laps.empty and 'driver_number' in df_laps else pd.DataFrame()

            total_laps = 0
            s1, s2, s3, lap_t = None, None, None, None
            lap_t_val = 9999
            is_pit_out = False

            if not driver_laps.empty:
                if 'lap_number' in driver_laps.columns:
                    valid_nums = driver_laps['lap_number'].dropna()
                    if not valid_nums.empty:
                        total_laps = int(valid_nums.max())

                last_row = driver_laps.sort_values('lap_number').iloc[-1]
                is_pit_out = last_row.get('is_pit_out_lap', False)

                if 'lap_duration' in driver_laps.columns:
                    valid_laps = driver_laps.dropna(subset=['lap_duration'])
                    if not valid_laps.empty:
                        best_driver_lap = valid_laps.sort_values('lap_duration').iloc[0]
                        s1 = best_driver_lap.get('duration_sector_1')
                        s2 = best_driver_lap.get('duration_sector_2')
                        s3 = best_driver_lap.get('duration_sector_3')
                        lap_t = best_driver_lap.get('lap_duration')
                        lap_t_val = lap_t if pd.notna(lap_t) else 9999

            if is_pit_out:
                track_status = "🟡 OUT LAP"
            elif d_num in pit_drivers and pd.isna(lap_t):
                track_status = "🔧 IN PIT"
            else:
                track_status = "🏎️ TRAŤ"

            stint_info = current_stints_map.get(d_num, {})
            tyre_str = stint_info.get("compound_str", "🔘 UNKNOWN")
            stint_nr = stint_info.get("stint_num", "S1")
            l_start = stint_info.get("lap_start", 1)
            tyre_age = max(1, total_laps - l_start + 1) if total_laps >= l_start and total_laps > 0 else "-"

            rows.append({
                "num": d_num,
                "Jezdec": d_acronym,
                "Tým": team_map.get(d_num, "-"),
                "Stav": track_status,
                "Pneu": tyre_str,
                "Stint": stint_nr,
                "Stáří pneu": f"{tyre_age} kol" if isinstance(tyre_age, int) else "-",
                "Kolo": total_laps if total_laps > 0 else "-",
                "Sektor 1": fmt_time(s1),
                "Sektor 2": fmt_time(s2),
                "Sektor 3": fmt_time(s3),
                "Čas kola": fmt_time(lap_t),
                "lap_t_val": lap_t_val,
                "_b_s1": abs(s1 - best_s1) < 0.001 if (pd.notna(s1) and best_s1 and isinstance(s1, (int, float))) else False,
                "_b_s2": abs(s2 - best_s2) < 0.001 if (pd.notna(s2) and best_s2 and isinstance(s2, (int, float))) else False,
                "_b_s3": abs(s3 - best_s3) < 0.001 if (pd.notna(s3) and best_s3 and isinstance(s3, (int, float))) else False,
                "_b_lap": abs(lap_t - best_lap) < 0.001 if (pd.notna(lap_t) and best_lap and isinstance(lap_t, (int, float))) else False,
            })

        df_final = pd.DataFrame(rows)
        if not df_final.empty:
            df_final = df_final.sort_values('lap_t_val').reset_index(drop=True)
            df_final['Pozice'] = [f"P{i+1}" for i in range(len(df_final))]

            def highlight_bests(row):
                styles = [''] * len(row)
                purple_style = 'background-color: #8A2BE2; color: #FFFFFF; font-weight: bold;'
                if row.get('_b_s1'): styles[9] = purple_style
                if row.get('_b_s2'): styles[10] = purple_style
                if row.get('_b_s3'): styles[11] = purple_style
                if row.get('_b_lap'): styles[12] = purple_style
                return styles

            display_cols = ["Pozice", "Jezdec", "Tým", "Stav", "Pneu", "Stint", "Stáří pneu", "Kolo", "Sektor 1", "Sektor 2", "Sektor 3", "Čas kola"]
            styled_table = df_final.style.apply(highlight_bests, axis=1)

            st.dataframe(styled_table, column_order=display_cols, use_container_width=True, height=680, hide_index=True)

with tab_cockpit:
    st.subheader("🏎️ Živá Telemetrie z Kokpitu Vozu")
    driver_options = {f"{acronym} ({team_map.get(num, '-')})": num for num, acronym in driver_map.items()}
    if driver_options:
        selected_label_cockpit = st.selectbox("Vyber jezdce pro sledování kokpitu:", list(driver_options.keys()))
        selected_driver_num = driver_options[selected_label_cockpit]
        
        car_data_raw = fetch_openf1("car_data", {"session_key": session_key, "driver_number": selected_driver_num})
        
        if car_data_raw and len(car_data_raw) > 0:
            latest = car_data_raw[-1]
            speed = latest.get('speed', 0)
            rpm = latest.get('rpm', 0)
            gear = latest.get('n_gear', 0)
            throttle = latest.get('throttle', 0)
            brake = latest.get('brake', 0)
            drs_code = latest.get('drs', 0)
            
            is_drs_open = drs_code >= 10 or drs_code in [8, 10, 12, 14]
            drs_html = '<div class="drs-open">🟢 DRS OTEVŘENO</div>' if is_drs_open else '<div class="drs-closed">🔴 DRS ZAVŘENO</div>'
            
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f'<div class="telemetry-card"><div style="color:#8E8E93;">RYCHLOST</div><div class="telemetry-val">{speed} <span style="font-size:16px;">km/h</span></div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="telemetry-card"><div style="color:#8E8E93;">STAV DRS</div><div style="margin-top:10px;">{drs_html}</div></div>', unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div class="telemetry-card"><div style="color:#8E8E93;">STUPEŇ / GEAR</div><div class="telemetry-val">{gear if gear > 0 else "N"}</div></div>', unsafe_allow_html=True)
            with c4:
                st.markdown(f'<div class="telemetry-card"><div style="color:#8E8E93;">OTÁČKY (RPM)</div><div class="telemetry-val">{rpm}</div></div>', unsafe_allow_html=True)
            
            st.divider()
            st.write("**📱 Pedály (Plyn / Brzda):**")
            col_th, col_br = st.columns(2)
            with col_th:
                st.write(f"🟢 Plyn: **{throttle}%**")
                st.progress(min(100, max(0, int(throttle))))
            with col_br:
                st.write(f"🔴 Brzda: **{brake}%**")
                st.progress(min(100, max(0, int(brake))))
        else:
            st.info("⌛ Telemetrická data pro vybraného jezdce nejsou k dispozici.")

with tab_map:
    st.subheader("🗺️ Mapa okruhu a pozice vozů")
    location_raw = fetch_openf1("location", {"session_key": session_key})
    if not location_raw:
        st.info("⌛ GPS data z trati nejsou k dispozici.")
    else:
        df_loc = pd.DataFrame(location_raw)
        if not df_loc.empty and 'x' in df_loc.columns and 'y' in df_loc.columns and 'driver_number' in df_loc.columns:
            latest_pos = df_loc.groupby('driver_number').last().reset_index()
            latest_pos['Jezdec'] = latest_pos['driver_number'].map(driver_map)
            st.scatter_chart(latest_pos, x='x', y='y', color='Jezdec', size=200, height=600, use_container_width=True)

with tab_stints:
    st.subheader("🛞 Přehled Stintů a Strategií")
    if not stints_raw:
        st.info("ℹ️ Data o stintování nejsou k dispozici.")
    else:
        df_all_stints = pd.DataFrame(stints_raw)
        if not df_all_stints.empty and 'driver_number' in df_all_stints.columns:
            stint_rows = []
            for _, r in df_all_stints.iterrows():
                num = r.get('driver_number')
                comp = str(r.get('compound', 'UNKNOWN')).upper()
                tyre_icon = "🔴" if "SOFT" in comp else ("🟡" if "MEDIUM" in comp else ("⚪" if "HARD" in comp else ("🟢" if "INTER" in comp else ("🔵" if "WET" in comp else "🔘"))))
                l_start = int(r.get('lap_start', 1)) if pd.notna(r.get('lap_start')) else 1
                l_end = int(r.get('lap_end', 1)) if pd.notna(r.get('lap_end')) else l_start

                stint_rows.append({
                    "Jezdec": driver_map.get(num, f"#{num}"),
                    "Tým": team_map.get(num, "-"),
                    "Stint": f"Stint {r.get('stint', 1)}",
                    "Směs pneu": f"{tyre_icon} {comp}",
                    "Od kola": l_start,
                    "Do kola": l_end,
                    "Počet kol": max(1, l_end - l_start + 1)
                })
            st.dataframe(pd.DataFrame(stint_rows), use_container_width=True, height=650, hide_index=True)

with tab_radio:
    st.subheader("📻 Stream Týmových Rádií")
    radios_raw = fetch_openf1("team_radio", {"session_key": session_key})
    if not radios_raw:
        st.info("🎙️ Žádné audio nahrávky nejsou k dispozici.")
    else:
        df_radio = pd.DataFrame(radios_raw)
        if not df_radio.empty and 'date' in df_radio.columns:
            df_radio_sorted = df_radio.sort_values('date', ascending=False)
            for _, r in df_radio_sorted.iterrows():
                num = r.get('driver_number')
                d_acronym = driver_map.get(num, f"#{num}")
                t_name = team_map.get(num, "Tým")
                audio_url = r.get('recording_url')
                raw_date = str(r.get('date', ''))
                formatted_time = raw_date[:19].replace('T', ' ') if 'T' in raw_date else raw_date
                
                col_l, col_r = st.columns([1, 3])
                with col_l:
                    st.markdown(f"### 🎧 {d_acronym}")
                    st.caption(f"**{t_name}** | {formatted_time}")
                with col_r:
                    if audio_url:
                        st.audio(audio_url)
                st.divider()
