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

headers = {
    "Authorization": f"Bearer {token.strip()}",
    "X-League": str(league_id).strip(),
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

if user_id:
    headers["X-User"] = str(user_id).strip()

@st.cache_data(ttl=60)
def fetch_league_data():
    data = {}
    
    # 1. Consulta la liga global
    url_league = "https://biwenger.as.com/api/v2/league?fields=*,standings(*,user)"
    try:
        resp = requests.get(url_league, headers=headers)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
    except Exception:
        pass

    # 2. Consulta de respaldo específica para la clasificación / rivales
    url_standings = "https://biwenger.as.com/api/v2/league/standings"
    try:
        resp_st = requests.get(url_standings, headers=headers)
        if resp_st.status_code == 200:
            st_json = resp_st.json().get("data", {})
            if isinstance(st_json, list):
                data["standings"] = st_json
            elif isinstance(st_json, dict) and "standings" in st_json:
                data["standings"] = st_json["standings"]
            elif isinstance(st_json, dict) and "group" in st_json:
                data["standings"] = st_json["group"]
    except Exception:
        pass

    return data

league_data = fetch_league_data()

if not league_data:
    st.error("❌ No se pudieron obtener los datos de la liga. Revisa que el Token y League ID sean correctos.")
    st.stop()

league_name = league_data.get('name', 'Mi Liga')
st.subheader(f"🏆 Liga: {league_name}")

standings = league_data.get("standings", [])

def parse_entry(entry):
    if not isinstance(entry, dict):
        return {"ID User": None, "Usuario": "Desconocido", "Puntos": 0, "Valor Equipo (€)": 0, "Restante / Saldo (€)": 0}
    
    user_obj = entry.get("user") if isinstance(entry.get("user"), dict) else {}
    
    # Búsqueda flexible del nombre
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

    # ID del usuario
    uid = entry.get("id") or user_obj.get("id") or (entry.get("user") if isinstance(entry.get("user"), int) else None)

    # Puntos
    points = entry.get("points")
    if points is None:
        points = entry.get("score")
    if points is None:
        points = user_obj.get("points", 0)

    # Valor de la plantilla
    val = entry.get("teamValue")
    if val is None:
        val = entry.get("team_value")
    if val is None:
        val = user_obj.get("teamValue", 0)

    # Saldo
    bal = entry.get("balance")
    if bal is None:
        bal = user_obj.get("balance", 0)

    return {
        "ID User": uid,
        "Usuario": str(name),
        "Puntos": int(points or 0),
        "Valor Equipo (€)": float(val or 0),
        "Restante / Saldo (€)": float(bal or 0)
    }

if standings:
    rivals_list = [parse_entry(e) for e in standings]
    df_standings = pd.DataFrame(rivals_list)

    tab1, tab2 = st.tabs(["📊 Clasificación y Rivales", "👤 Mi Financiera"])

    with tab1:
        st.write("### 👥 Todos los participantes de la liga")
        
        df_display = df_standings.copy()
        df_display["Valor Equipo (€)"] = df_display["Valor Equipo (€)"].apply(lambda x: f"{x:,.0f} €".replace(",", "."))
        df_display["Restante / Saldo (€)"] = df_display["Restante / Saldo (€)"].apply(lambda x: f"{x:,.0f} €".replace(",", "."))

        st.dataframe(df_display[["Usuario", "Puntos", "Valor Equipo (€)", "Restante / Saldo (€)"]], use_container_width=True)

    with tab2:
        st.write("### 💰 Análisis Individual")
        
        user_names = df_standings["Usuario"].tolist()
        default_idx = 0
        if user_id:
            try:
                matching_row = df_standings[df_standings["ID User"] == int(user_id)]
                if not matching_row.empty:
                    default_idx = df_standings.index.get_loc(matching_row.index[0])
            except ValueError:
                pass

        selected_user = st.selectbox("Selecciona un mánager para ver sus métricas:", user_names, index=default_idx)
        
        user_row = df_standings[df_standings["Usuario"] == selected_user].iloc[0]
        
        val_team = user_row["Valor Equipo (€)"]
        bal_team = user_row["Restante / Saldo (€)"]
        max_bid = bal_team + (val_team * 0.25) if bal_team > 0 else val_team * 0.25

        col1, col2, col3 = st.columns(3)
        col1.metric("💰 Saldo Registrado", f"{bal_team:,.0f} €".replace(",", "."))
        col2.metric("📊 Valor de Plantilla", f"{val_team:,.0f} €".replace(",", "."))
        col3.metric("🔥 Puja Máx. Estimada", f"{max_bid:,.0f} €".replace(",", "."))

else:
    st.warning("No se encontraron datos de clasificación en esta liga.")
