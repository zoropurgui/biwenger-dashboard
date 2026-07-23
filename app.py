import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Biwenger Dashboard", page_icon="⚽", layout="wide")

st.title("⚽ Biwenger League & Finance Dashboard")

# --- SIDEBAR: Credenciales ---
st.sidebar.header("🔑 Credenciales de Biwenger")
token = st.sidebar.text_input("Bearer Token", type="password", help="Tu token de autorización")
league_id = st.sidebar.text_input("League ID", help="ID numérico de tu liga")
user_id = st.sidebar.text_input("User ID (Opcional)", help="Tu ID de usuario para resaltar tu equipo")

if not token or not league_id:
    st.info("👈 Introduce tu **Bearer Token** y **League ID** en la barra lateral para cargar la liga.")
    st.stop()

clean_token = token.strip()
if clean_token.lower().startswith("bearer "):
    clean_token = clean_token[7:].strip()

clean_league_id = str(league_id).strip()
clean_user_id = str(user_id).strip() if user_id else ""

@st.cache_data(ttl=60)
def fetch_league_data(tok, l_id, u_id):
    headers = {
        "Authorization": f"Bearer {tok}",
        "X-League": l_id,
        "Accept": "application/json, text/plain, */*",
        "X-App-Version": "2.0.0",
        "X-Lang": "es",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    if u_id:
        headers["X-User"] = u_id

    data = {}
    errors = []
    
    # 1. Consulta la liga global
    url_league = "https://biwenger.as.com/api/v2/league?fields=*,standings(*,user)"
    try:
        resp = requests.get(url_league, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
        else:
            errors.append(f"Petición principal /league: HTTP {resp.status_code}")
    except Exception as e:
        errors.append(f"Error de red en /league: {str(e)}")

    # 2. Consulta de respaldo específica para standings
    url_standings = "https://biwenger.as.com/api/v2/league/standings"
    try:
        resp_st = requests.get(url_standings, headers=headers, timeout=10)
        if resp_st.status_code == 200:
            st_json = resp_st.json().get("data", {})
            if isinstance(st_json, list):
                data["standings"] = st_json
            elif isinstance(st_json, dict) and "standings" in st_json:
                data["standings"] = st_json["standings"]
            elif isinstance(st_json, dict) and "group" in st_json:
                data["standings"] = st_json["group"]
        else:
            errors.append(f"Petición de respaldo /standings: HTTP {resp_st.status_code}")
    except Exception as e:
        errors.append(f"Error de red en /standings: {str(e)}")

    return data, errors

league_data, error_logs = fetch_league_data(clean_token, clean_league_id, clean_user_id)

if not league_data or not league_data.get("standings"):
    st.error("❌ No se pudieron obtener los datos de la liga de Biwenger.")
    if error_logs:
        st.warning("🔍 **Informe de diagnóstico:**")
        for err in error_logs:
            st.write(f"- `{err}`")
    
    st.markdown("""
    **💡 Guía de resolución:**
    * **HTTP 401:** Tu Token ha caducado. Vuelve a abrir **biwenger.as.com**, pulsa **F12 ➔ Red (Network)** y copia un token nuevo de la cabecera `authorization`.
    * **HTTP 403:** Servidor/Cloudflare bloqueó puntualmente la petición. Espera 1 o 2 minutos y recarga la página.
    """)
    st.stop()

league_name = league_data.get('name', 'Mi Liga')
st.subheader(f"🏆 Liga: {league_name}")

standings = league_data.get("standings", [])

def parse_entry(entry):
    if not isinstance(entry, dict):
        return {"ID User": None, "Usuario": "Desconocido", "Puntos": 0, "Valor Equipo (€)": 0, "Dinero en Caja (€)": 0}
    
    user_obj = entry.get("user") if isinstance(entry.get("user"), dict) else {}
    
    name = (
        entry.get("name") or 
        entry.get("username") or 
        user_obj.get("name") or 
        user_obj.get("username")
    )
    if not name and isinstance(entry.get("user"), str):
        name = entry.get("user")
    if not name:
        name = f"Mánager {entry.get('id', '')}".strip()

    uid = entry.get("id") or user_obj.get("id") or (entry.get("user") if isinstance(entry.get("user"), int) else None)

    points = entry.get("points")
    if points is None:
        points = entry.get("score")
    if points is None:
        points = user_obj.get("points", 0)

    val = entry.get("teamValue")
    if val is None:
        val = entry.get("team_value")
    if val is None:
        val = user_obj.get("teamValue", 0)

    bal = entry.get("balance")
    if bal is None:
        bal = user_obj.get("balance", 0)

    return {
        "ID User": uid,
        "Usuario": str(name),
        "Puntos": int(points or 0),
        "Valor Equipo (€)": float(val or 0),
        "Dinero en Caja (€)": float(bal or 0)
    }

if standings:
    rivals_list = [parse_entry(e) for e in standings]
    df_standings = pd.DataFrame(rivals_list)

    df_standings["Posición"] = range(1, len(df_standings) + 1)
    df_standings["Valor Total (€)"] = df_standings["Valor Equipo (€)"] + df_standings["Dinero en Caja (€)"]
    df_standings["Puja Máxima (€)"] = df_standings["Dinero en Caja (€)"] + (0.25 * df_standings["Valor Equipo (€)"])

    tab1, tab2 = st.tabs(["📊 Clasificación y Rivales", "👤 Mi Financiera"])

    with tab1:
        st.write("### 👥 Clasificación y Estado Financiero de Rivales")

        cols_order = [
            "Posición",
            "Usuario",
            "Puntos",
            "Valor Equipo (€)",
            "Dinero en Caja (€)",
            "Valor Total (€)",
            "Puja Máxima (€)"
        ]
        
        df_table = df_standings[cols_order].copy()

        def color_negative_red(val):
            if isinstance(val, (int, float)) and val < 0:
                return 'color: #ff4b4b; font-weight: bold;'
            return ''

        if hasattr(df_table.style, "map"):
            styler = df_table.style.map(color_negative_red, subset=["Dinero en Caja (€)"])
        else:
            styler = df_table.style.applymap(color_negative_red, subset=["Dinero en Caja (€)"])

        styler = styler.format({
            "Valor Equipo (€)": lambda x: f"{x:,.0f} €".replace(",", "."),
            "Dinero en Caja (€)": lambda x: f"{x:,.0f} €".replace(",", "."),
            "Valor Total (€)": lambda x: f"{x:,.0f} €".replace(",", "."),
            "Puja Máxima (€)": lambda x: f"{x:,.0f} €".replace(",", ".")
        })

        st.dataframe(styler, use_container_width=True, hide_index=True)

    with tab2:
        st.write("### 💰 Análisis Individual")
        
        user_names = df_standings["Usuario"].tolist()
        default_idx = 0
        if clean_user_id:
            try:
                matching_row = df_standings[df_standings["ID User"] == int(clean_user_id)]
                if not matching_row.empty:
                    default_idx = df_standings.index.get_loc(matching_row.index[0])
            except ValueError:
                pass

        selected_user = st.selectbox("Selecciona un mánager para ver sus métricas:", user_names, index=default_idx)
        
        user_row = df_standings[df_standings["Usuario"] == selected_user].iloc[0]
        
        val_team = user_row["Valor Equipo (€)"]
        bal_team = user_row["Dinero en Caja (€)"]
        val_total = user_row["Valor Total (€)"]
        max_bid = user_row["Puja Máxima (€)"]

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("💰 Dinero en Caja", f"{bal_team:,.0f} €".replace(",", "."))
        col2.metric("📊 Valor de Plantilla", f"{val_team:,.0f} €".replace(",", "."))
        col3.metric("🏆 Valor Total", f"{val_total:,.0f} €".replace(",", "."))
        col4.metric("🔥 Puja Máx. Estimada", f"{max_bid:,.0f} €".replace(",", "."))

else:
    st.warning("No se encontraron datos de clasificación en esta liga.")
