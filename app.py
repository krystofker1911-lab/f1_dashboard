import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone
from streamlit_autorefresh import st_autorefresh

# --- 1. Nastavení aplikace ---
st.set_page_config(page_title="F1 Pro Pit Wall & Cockpit", layout="wide", initial_sidebar_state="collapsed")

# Živé obnovování každé 3 sekundy
st_autorefresh(interval=3000, key="f1_live_refresh")

# Vlastní CSS styly pro F1 Pit Wall
st.markdown("""
    <style>
        .stApp { background-color: #0E0E12; color: #FFFFFF; }
        .session-header {
            font-size: 24px; font-weight: bold; text-align: center;
            color: #E10600; margin-bottom: 5px; letter-spacing: 1px;
        }
        .track-status-box {
            padding: 10px; border-radius: 8px; text-align: center;
            font-size: 22px; font-weight: bold; margin-bottom: 12px;
            text-transform: uppercase; letter-spacing: 2px;
        }
        .status-green { background-color: #00D26A; color: #000; }
        .status-yellow { background-color: #FFCC00; color: #000; }
        .status-sc { background-color: #FF8800; color: #FFF; animation: blink 1s infinite; }
        .status-red { background-color: #FF1801; color: #FFF; animation: blink 0.6s infinite; }
        .status-vsc { background-color: #E67E22; color: #FFF; }
        .status-closed { background-color: #1E1E26; color: #FF4444; border: 2px solid #FF4444; }
        
        .countdown-box {
            background-color: #16161E; border: 1px solid #00E5FF;
            border-radius: 8px; padding: 10px; text-align: center;
            font-size: 18px; font-weight: bold; color: #00E5FF;
            margin-bottom: 15px; box-shadow: 0px 0px 10px rgba(0, 229, 255, 0.2);
        }
        .telemetry-card {
            background-color: #16161E; border-radius: 8px; padding: 15px;
            text-align: center; border: 1px solid #2A2A36; margin-bottom: 10px;
        }
        .telemetry-val { font-size: 32px; font-weight: bold; color: #00E5FF; }
        .drs-open { background-color: #00D26A; color: #000; padding: 6px; border-radius: 6px; font-weight: bold; }
        .drs-closed { background-color: #FF1801; color: #FFF; padding: 6px; border-radius: 6px; font-weight: bold; }
        
        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }
    </style>
""", unsafe_allow_html=True)

# Bezpečné stažení JSON dat z API
@st.cache_data(ttl=3)
def safe_get_json(url):
    try:
        res = requests.get(url, timeout=5)
        data = res.json()
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []

# --- 2. Inteligentní výběr relace s fallbackem ---
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

# Získání dat kol
laps_raw = []
session_key = "latest"
session_title = "🏎️ F1 PIT WALL DASHBOARD"

if active_session:
    session_key = str(active_session.get("session_key"))
    session_title = f"🔴 LIVE PIT WALL — {active_session.get('location', '')} ({active_session.get('session_name', '')})"
    laps_raw = safe_get_json(f"https://api.openf1.org/v1/laps?session_key={session_key}")

# Pokud neběží živá relace nebo v ní ještě nejsou kola, najdeme poslední relaci s platnými daty
if not laps_raw:
    if all_sessions:
        for s in reversed(all_sessions):
            sk = str(s.get("session_key"))
            test_laps = safe_get_json(f"https://api.openf1.org/v1/laps?session_key={sk}")
            if test_laps and len(test_laps) > 0:
                session_key = sk
                s_loc = s.get('location', 'F1 GP')
                s_name = s.get('session_name', 'Session')
                session_title = f"🏎️ F1 PIT WALL — {s_loc} ({s_name})"
                laps_raw = test_laps
                break

st.markdown(f'<div class="session-header">{session_title}</div>', unsafe_allow_html=True)

# --- 3. Načtení ostatních dat pro daný session_key ---
drivers_raw = safe_get_json(f"https://api.openf1.org/v1/drivers?session_key={session_key}")
status_raw = safe_get_json(f"https://api.openf1.org/v1/track_status?session_key={session_key}")
stints_raw = safe_get_json(f"https://api.openf1.org/v1/stints?session_key={session_key}")
pits_raw = safe_get_json(f"https://api.openf1.org/v1/pit?session_key={session_key}")
radios_raw = safe_get_json(f"https://api.openf1.org/v1/team_radio?session_key={session_key}")
location_raw = safe_get_json(f"https://api.openf1.org/v1/location?session_key={session_key}")

driver_map = {d.get('driver_number'): d.get('name_acronym', f"#{d.get('driver_number')}") for d in drivers_raw if isinstance(d, dict) and 'driver_number' in d}
team_map = {d.get('driver_number'): d.get('team_name', '-') for d in drivers_raw if isinstance(d, dict) and 'driver_number' in d}

# Stav trati / Odpočet
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

            time_str = f"{days}d {hours}h {minutes}m {seconds}s" if days > 0 else f"{hours}h {minutes}m {seconds}s"
            st.markdown(f'<div class="countdown-box">⏱️ Další relace: <b>{loc} — {s_name}</b> za <b>{time_str}</b></div>', unsafe_allow_html=True)
        except Exception:
            pass

# Stinty a Pit stopy
current_stints_map = {}
if stints_raw:
    df_stints = pd.DataFrame(stints_raw)
    if not df_stints.empty and 'driver_number' in df_stints.columns and 'stint' in df_stints.columns:
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

# --- 4. Záložky Aplikace ---
tab_timing, tab_cockpit, tab_map, tab_stints, tab_radio = st.tabs(["📊 Live Timing & Box", "🏎️ Kokpit Telemetrie", "🗺️ Mapa okruhu", "🛞 Stinty", "📻 Radio"])

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

with tab_timing:
    if not laps_raw:
        st.info("⌛ Čekám na data z trati...")
    else:
        df_laps = pd.DataFrame(laps_raw)
        if df_laps.empty or 'lap_number' not in df_laps.columns or 'driver_number' not in df_laps.columns:
            st.info("⌛ Čekám na dokončená kola...")
        else:
            df_valid = df_laps.dropna(subset=['lap_duration']) if 'lap_duration' in df_laps.columns else pd.DataFrame()

            best_s1 = df_valid['duration_sector_1'].min() if not df_valid.empty and 'duration_sector_1' in df_valid else None
            best_s2 = df_valid['duration_sector_2'].min() if not df_valid.empty and 'duration_sector_2' in df_valid else None
            best_s3 = df_valid['duration_sector_3'].min() if not df_valid.empty and 'duration_sector_3' in df_valid else None
            best_lap = df_valid['lap_duration'].min() if not df_valid.empty and 'lap_duration' in df_valid else None

            if not df_valid.empty:
                best_laps_per_driver = df_valid.sort_values('lap_duration').groupby('driver_number').first().reset_index()
                sorted_laps = best_laps_per_driver.sort_values('lap_duration').reset_index(drop=True)
            else:
                sorted_laps = df_laps.sort_values('lap_number').groupby('driver_number').last().reset_index()

            table_rows = []
            for idx, row in sorted_laps.iterrows():
                num = row.get('driver_number')
                s1 = row.get('duration_sector_1')
                s2 = row.get('duration_sector_2')
                s3 = row.get('duration_sector_3')
                lap_t = row.get('lap_duration')
                current_lap = int(row.get('lap_number')) if pd.notna(row.get('lap_number')) else 0
                is_pit_out = row.get('is_pit_out_lap', False)

                if is_pit_out:
                    track_status = "🟡 OUT LAP"
                elif num in pit_drivers and pd.isna(lap_t):
                    track_status = "🔧 IN PIT"
                else:
                    track_status = "🏎️ TRAŤ"

                stint_info = current_stints_map.get(num, {})
                tyre_str = stint_info.get("compound_str", "🔘 UNKNOWN")
                stint_nr = stint_info.get("stint_num", "S1")
                l_start = stint_info.get("lap_start", 1)
                tyre_age = max(1, current_lap - l_start + 1) if current_lap >= l_start else "-"

                table_rows.append({
                    "Pozice": f"P{idx + 1}",
                    "Jezdec": driver_map.get(num, f"#{num}"),
                    "Tým": team_map.get(num, "-"),
                    "Stav": track_status,
                    "Pneu": tyre_str,
                    "Stint": stint_nr,
                    "Stáří pneu": f"{tyre_age} kol" if isinstance(tyre_age, int) else "-",
                    "Kolo": current_lap if current_lap > 0 else "-",
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
                if row.get('_b_s1'): styles[8] = purple_style
                if row.get('_b_s2'): styles[9] = purple_style
                if row.get('_b_s3'): styles[10] = purple_style
                if row.get('_b_lap'): styles[11] = purple_style
                return styles

            display_cols = ["Pozice", "Jezdec", "Tým", "Stav", "Pneu", "Stint", "Stáří pneu", "Kolo", "Sektor 1", "Sektor 2", "Sektor 3", "Čas kola"]
            styled_table = df_final.style.apply(highlight_bests, axis=1)

            st.dataframe(styled_table, column_order=display_cols, use_container_width=True, height=680, hide_index=True)

with tab_cockpit:
    st.subheader("🏎️ Živá Telemetrie z Kokpitu Vozu")
    
    driver_options = {f"{acronym} ({team_map.get(num, '-')})": num for num, acronym in driver_map.items()}
    if driver_options:
        selected_label = st.selectbox("Vyber jezdce pro sledování kokpitu:", list(driver_options.keys()))
        selected_driver_num = driver_options[selected_label]
        
        car_data_raw = safe_get_json(f"https://api.openf1.org/v1/car_data?session_key={session_key}&driver_number={selected_driver_num}")
        
        if car_data_raw and len(car_data_raw) > 0:
            latest_telemetry = car_data_raw[-1]
            
            speed = latest_telemetry.get('speed', 0)
            rpm = latest_telemetry.get('rpm', 0)
            gear = latest_telemetry.get('n_gear', 0)
            throttle = latest_telemetry.get('throttle', 0)
            brake = latest_telemetry.get('brake', 0)
            drs_code = latest_telemetry.get('drs', 0)
            
            is_drs_open = drs_code >= 10 or drs_code in [8, 10, 12, 14]
            drs_html = '<div class="drs-open">🟢 DRS OTEVŘENO (OPEN)</div>' if is_drs_open else '<div class="drs-closed">🔴 DRS ZAVŘENO (CLOSED)</div>'
            
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
            st.info("⌛ Čekám na telemetrický signál z vozu...")
    else:
        st.info("⌛ Seznam jezdců není k dispozici.")

with tab_map:
    st.subheader("🗺️ Živá mapa okruhu a pozice vozů")
    if not location_raw:
        st.info("⌛ Čekám na GPS telemetrická data vozů z trati...")
    else:
        df_loc = pd.DataFrame(location_raw)
        if not df_loc.empty and 'x' in df_loc.columns and 'y' in df_loc.columns and 'driver_number' in df_loc.columns:
            latest_pos = df_loc.groupby('driver_number').last().reset_index()
            latest_pos['Jezdec'] = latest_pos['driver_number'].map(driver_map)
            
            st.scatter_chart(
                latest_pos,
                x='x',
                y='y',
                color='Jezdec',
                size=200,
                height=600,
                use_container_width=True
            )
        else:
            st.info("ℹ️ Telemetrická mapa trati je pro tuto relaci neaktivní.")

with tab_stints:
    st.subheader("🛞 Přehled všech Stintů a Strategií")
    if not stints_raw:
        st.info("ℹ️ Pro tuto relaci nejsou k dispozici žádná data o stintování.")
    else:
        df_all_stints = pd.DataFrame(stints_raw)
        if not df_all_stints.empty and 'driver_number' in df_all_stints.columns:
            stint_rows = []
            for _, r in df_all_stints.sort_values(['driver_number', 'stint']).iterrows():
                num = r.get('driver_number')
                comp = str(r.get('compound', 'UNKNOWN')).upper()
                tyre_icon = "🔴" if "SOFT" in comp else ("🟡" if "MEDIUM" in comp else ("⚪" if "HARD" in comp else ("🟢" if "INTER" in comp else ("🔵" if "WET" in comp else "🔘"))))
                
                l_start = int(r.get('lap_start', 1)) if pd.notna(r.get('lap_start')) else 1
                l_end = int(r.get('lap_end', 1)) if pd.notna(r.get('lap_end')) else l_start
                total_laps = max(1, l_end - l_start + 1)

                stint_rows.append({
                    "Jezdec": driver_map.get(num, f"#{num}"),
                    "Tým": team_map.get(num, "-"),
                    "Stint": f"Stint {r.get('stint', 1)}",
                    "Směs pneu": f"{tyre_icon} {comp}",
                    "Od kola": l_start,
                    "Do kola": l_end,
                    "Počet kol": total_laps
                })
            
            st.dataframe(pd.DataFrame(stint_rows), use_container_width=True, height=650, hide_index=True)

with tab_radio:
    st.subheader("📻 Kompletní Stream Týmových Rádií (Live Feed)")
    if not radios_raw:
        st.info("🎙️ Žádné audio nahrávky z rádií nejsou pro tuto relaci k dispozici.")
    else:
        df_radio = pd.DataFrame(radios_raw)
        if not df_radio.empty and 'date' in df_radio.columns:
            df_radio_sorted = df_radio.sort_values('date', ascending=False)
            
            st.caption(f"Celkem načteno **{len(df_radio_sorted)}** zpráv z traťového vysílání:")
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
                    else:
                        st.caption("Audio nedostupné")
                st.divider()
