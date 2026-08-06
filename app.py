import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Biwenger Financial Monitor", page_icon="⚽", layout="wide")

st.title("⚽ Monitor Financiero Biwenger")

# --- SIDEBAR: Credenciales y Configuración ---
st.sidebar.header("🔑 Credenciales de Biwenger")
token = st.sidebar.text_input("Bearer Token", type="password", help="Pega el token sin 'Bearer ' delante")
league_id = st.sidebar.text_input("League ID", help="ID de la liga")
user_id = st.sidebar.text_input("User ID (Opcional)")

st.sidebar.header("⚙️ Configuración Financiera")
initial_budget = st.sidebar.number_input(
    "Presupuesto Total Inicial (€)", 
    value=40000000, 
    step=1000000,
    help="Presupuesto por mánager (Plantilla + Caja)"
)

max_bid_pct = st.sidebar.slider(
    "Crédito sobre Valor de Equipo (%)", 
    min_value=0.0, 
    max_value=100.0, 
    value=25.0, 
    step=1.0,
    help="Regla de Biwenger: Caja + (25% del Valor de Plantilla)"
)

if not token or not league_id:
    st.info("👈 Introduce tu **Bearer Token** y **League ID** en la barra lateral.")
    st.stop()

# Limpieza de credenciales
clean_token = token.strip()
if clean_token.lower().startswith("bearer "):
    clean_token = clean_token[7:].strip()

clean_league_id = str(league_id).strip()
clean_user_id = str(user_id).strip() if user_id else ""

headers = {
    "Authorization": f"Bearer {clean_token}",
    "X-League": clean_league_id,
    "Accept": "application/json, text/plain, */*",
    "X-App-Version": "2.0.0",
    "X-Lang": "es",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}
if clean_user_id:
    headers["X-User"] = clean_user_id

@st.cache_data(ttl=15)
def fetch_api_data():
    url = "https://biwenger.as.com/api/v2/league"
    try:
        r = requests.get(url, headers=headers, timeout=8)
        return r.status_code, r.json() if r.headers.get('content-type', '').startswith('application/json') else r.text
    except Exception as e:
        return 0, str(e)

status_code, api_response = fetch_api_data()

parsed_users = []
league_name = "Mi Liga"
api_success = False

if status_code == 200 and isinstance(api_response, dict):
    api_data = api_response.get("data", {})
    league_name = api_data.get("name", "Mi Liga")
    users = api_data.get("users", []) or api_data.get("standings", [])
    
    for u in users:
        if isinstance(u, dict):
            uid = u.get("id") or (u.get("user", {}).get("id") if isinstance(u.get("user"), dict) else None)
            uname = u.get("name") or (u.get("user", {}).get("name") if isinstance(u.get("user"), dict) else f"Mánager {uid}")
            tv = float(u.get("teamValue") or u.get("value") or 0.0)
            parsed_users.append({"ID": uid, "Usuario": str(uname), "Valor Equipo (€)": tv})
            
    if parsed_users:
        api_success = True

# --- TRATAMIENTO DE ERRORES Y MODO DEMO / MANUAL ---
if not api_success:
    st.error(f"⚠️ Error de conexión con Biwenger (Código HTTP: {status_code})")
    
    with st.expander("🔍 Ver respuesta exacta del servidor de Biwenger"):
        st.write(api_response)
        
    st.warning("👉 **Causas habituales:** El Bearer Token ha caducado o el League ID no coincide con la cuenta del Token.")
    
    st.write("---")
    st.subheader("🧪 Modo de Prueba / Ajuste Manual (Para testear)")
    
    demo_users = [
        {"ID": 1, "Usuario": "Chavowen", "Valor Equipo (€)": 15000000.0},
        {"ID": 2, "Usuario": "Chusco83", "Valor Equipo (€)": 18500000.0},
        {"ID": 3, "Usuario": "Ínter del Ciprés", "Valor Equipo (€)": 12000000.0},
        {"ID": 4, "Usuario": "Mallorca Fantasy", "Valor Equipo (€)": 20000000.0},
        {"ID": 5, "Usuario": "Mogambo", "Valor Equipo (€)": 14000000.0},
        {"ID": 6, "Usuario": "Nairobi F.C.", "Valor Equipo (€)": 16000000.0},
        {"ID": 7, "Usuario": "Onuba FC", "Valor Equipo (€)": 11000000.0},
        {"ID": 8, "Usuario": "Rayo76", "Valor Equipo (€)": 17500000.0},
        {"ID": 9, "Usuario": "Wasabi", "Valor Equipo (€)": 13000000.0},
        {"ID": 10, "Usuario": "zoropurgui", "Valor Equipo (€)": 19810500.0}
    ]
    df_base = pd.DataFrame(demo_users)
else:
    st.subheader(f"🏆 Liga: {league_name}")
    df_base = pd.DataFrame(parsed_users)

# --- TABLA INTERACTIVA EDITABLE ---
st.info("✏️ **Instrucciones:** Modifica cualquier importe en **'Valor Equipo (€)'** para recalcular **Caja** y **Puja Máxima** al instante.")

df_edited = st.data_editor(
    df_base,
    column_config={
        "ID": None,
        "Usuario": st.column_config.TextColumn("Usuario", disabled=True),
        "Valor Equipo (€)": st.column_config.NumberColumn(
            "Valor Equipo (€)",
            min_value=0,
            step=250000,
            format="%d €"
        )
    },
    hide_index=True,
    use_container_width=True
)

# --- CÁLCULOS DINÁMICOS EN TIEMPO REAL ---
df_edited["Dinero en Caja (€)"] = initial_budget - df_edited["Valor Equipo (€)"]
df_edited["Valor Total (€)"] = df_edited["Dinero en Caja (€)"] + df_edited["Valor Equipo (€)"]
df_edited["Puja Máxima (€)"] = df_edited["Dinero en Caja (€)"] + ((max_bid_pct / 100.0) * df_edited["Valor Equipo (€)"])

df_final = df_edited[["Usuario", "Valor Equipo (€)", "Dinero en Caja (€)", "Valor Total (€)", "Puja Máxima (€)"]]

styler = df_final.style.format({
    "Valor Equipo (€)": lambda x: f"{x:,.0f} €".replace(",", "."),
    "Dinero en Caja (€)": lambda x: f"{x:,.0f} €".replace(",", "."),
    "Valor Total (€)": lambda x: f"{x:,.0f} €".replace(",", "."),
    "Puja Máxima (€)": lambda x: f"{x:,.0f} €".replace(",", ".")
})

st.write("#### 📊 Estado Financiero y Límite de Pujas")
st.dataframe(styler, use_container_width=True, hide_index=True)
