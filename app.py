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
    # Obtiene datos globales de la liga y clasificación con rivales
    url = "https://biwenger.as.com/api/v2/league?fields=*,standings(*,user)"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json().get("data", {})
    return None

league_data = fetch_league_data()

if not league_data:
    st.error("❌ No se pudieron obtener los datos de la liga. Revisa que el Token y League ID sean correctos.")
    st.stop()

# Información de la liga
st.subheader(f"🏆 Liga: {league_data.get('name', 'Mi Liga')}")

standings = league_data.get("standings", [])

if standings:
    # Procesar tabla de rivales / clasificación
    rivals_list = []
    for entry in standings:
        u = entry.get("user", {})
        rivals_list.append({
            "ID User": u.get("id"),
            "Usuario": u.get("name", "Desconocido"),
            "Puntos": entry.get("points", 0),
            "Valor Equipo (€)": entry.get("teamValue", 0),
            "Restante / Saldo (€)": entry.get("balance", 0)
        })

    df_standings = pd.DataFrame(rivals_list)

    # --- PESTAÑAS DE NAVEGACIÓN ---
    tab1, tab2 = st.tabs(["📊 Clasificación y Rivales", "👤 Mi Financiera"])

    with tab1:
        st.write("### 👥 Todos los participantes de la liga")
        
        # Formatear números para lectura clara
        df_display = df_standings.copy()
        df_display["Valor Equipo (€)"] = df_display["Valor Equipo (€)"].apply(lambda x: f"{x:,.0f} €".replace(",", "."))
        if "Restante / Saldo (€)" in df_display.columns:
            df_display["Restante / Saldo (€)"] = df_display["Restante / Saldo (€)"].apply(lambda x: f"{x:,.0f} €".replace(",", "."))

        st.dataframe(df_display[["Usuario", "Puntos", "Valor Equipo (€)", "Restante / Saldo (€)"]], use_container_width=True)

    with tab2:
        st.write("### 💰 Análisis Individual")
        
        # Seleccionar usuario a analizar
        user_names = df_standings["Usuario"].tolist()
        
        # Buscar el índice del usuario actual si introdujo su ID
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
