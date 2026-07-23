import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Biwenger Finance Dashboard", page_icon="⚽", layout="wide")

st.title("⚽ Biwenger Finance Dashboard")
st.markdown("Calculadora e información financiera de tu plantilla en tiempo real.")

# --- SIDEBAR: Credenciales ---
st.sidebar.header("🔑 Credenciales de Biwenger")
token = st.sidebar.text_input("Bearer Token", type="password", help="Tu token de autorización")
league_id = st.sidebar.text_input("League ID", help="ID numérico de tu liga")
user_id = st.sidebar.text_input("User ID", help="Tu ID numérico de usuario")

if not token or not league_id or not user_id:
    st.info("👈 Por favor, introduce tu Token, League ID y User ID en la barra lateral para cargar los datos.")
    st.stop()

headers = {
    "Authorization": f"Bearer {token.strip()}",
    "X-League": str(league_id).strip(),
    "X-User": str(user_id).strip(),
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

@st.cache_data(ttl=60)
def fetch_user_data():
    url = f"https://biwenger.as.com/api/v2/user?fields=*,account(balance),players(id,name,position,price,value,fitness,status)"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json().get("data", {})
    else:
        st.error(f"Error al conectar con la API de Biwenger (Código HTTP: {resp.status_code})")
        return None

data = fetch_user_data()

if data:
    account = data.get("account", {})
    balance = account.get("balance", 0)
    players = data.get("players", [])

    # Procesar plantilla
    if players:
        df_players = pd.DataFrame(players)
        # Valor de equipo
        team_value = df_players["price"].sum() if "price" in df_players.columns else df_players.get("value", pd.Series([0])).sum()
    else:
        df_players = pd.DataFrame()
        team_value = 0

    max_bid = balance + (team_value * 0.25) # Cálculo genérico de puja máxima (saldo + 25% valor plantilla)

    # --- METRICAS PRINCIPALES ---
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Saldo Actual", f"{balance:,.0f} €".replace(",", "."))
    col2.metric("📊 Valor de Plantilla", f"{team_value:,.0f} €".replace(",", "."))
    col3.metric("🔥 Puja Máxima Estimada", f"{max_bid:,.0f} €".replace(",", "."))

    st.markdown("---")

    # --- TABLA DE JUGADORES ---
    st.subheader("📋 Plantilla Actual")
    if not df_players.empty:
        cols_to_show = [col for col in ["name", "position", "price", "status"] if col in df_players.columns]
        df_display = df_players[cols_to_show].copy()
        if "price" in df_display.columns:
            df_display["price"] = df_display["price"].apply(lambda x: f"{x:,.0f} €".replace(",", "."))
        df_display.columns = [col.capitalize() for col in df_display.columns]
        st.dataframe(df_display, use_container_width=True)
    else:
        st.write("No se encontraron jugadores en la plantilla.")
