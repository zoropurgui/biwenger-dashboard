import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Biwenger Financial Monitor Pro", page_icon="⚽", layout="wide")

st.title("⚽ Monitor Financiero Biwenger (Modo Diagnóstico)")

# --- SIDEBAR: Configuración ---
st.sidebar.header("🔑 Conexión")
token = st.sidebar.text_input("Bearer Token", type="password")

if not token:
    st.info("👈 Pega tu **Bearer Token** en la barra lateral.")
    st.stop()

clean_token = token.strip()
if clean_token.lower().startswith("bearer "):
    clean_token = clean_token[7:].strip()

# --- DATOS DE REFERENCIA (DÍA 1) ---
DAY_ONE_VALS = {
    "athletik81": 21600000.0, "ring014": 21580000.0, "tubu": 21570000.0, 
    "marroba": 21560000.0, "zhukkov": 21560000.0, "nitwolf": 21550000.0, 
    "yoqsetio xdxd": 21550000.0, "nistalikus": 21550000.0, "moltisanti": 21540000.0, 
    "gran gravessen": 21540000.0, "zoropurgui": 21530000.0, "_caesar_": 21510000.0, 
    "nitrorx": 21490000.0
}
INITIAL_TOTAL = 40000000.0

@st.cache_data(ttl=30)
def fetch_account_leagues(t):
    url = "https://biwenger.as.com/api/v2/account"
    h = {"Authorization": f"Bearer {t}", "X-App-Version": "2.0.0"}
    res = requests.get(url, headers=h, timeout=8)
    return res.json().get("data", {}).get("leagues", [])

try:
    leagues = fetch_account_leagues(clean_token)
except Exception as e:
    st.sidebar.error(f"Error de conexión: {e}")
    st.stop()

if not leagues:
    st.sidebar.error("❌ Token inválido o sin ligas.")
    st.stop()

league_dict = {l.get("name"): (l.get("id"), l.get("user", {}).get("id")) for l in leagues}
selected_league = st.sidebar.selectbox("🏆 Liga", list(league_dict.keys()))
l_id, u_id = league_dict[selected_league]

st.sidebar.header("⚙️ Ajustes")
max_bid_pct = st.sidebar.slider("Crédito Valor Equipo (%)", 0, 100, 25)

if st.sidebar.button("🔄 Recargar Datos"):
    st.cache_data.clear()
    st.rerun()

# --- PETICIONES A LA API (SIN BLOQUEAR ERRORES PARA VER QUÉ FALLA) ---
headers = {"Authorization": f"Bearer {clean_token}", "X-League": str(l_id), "X-User": str(u_id), "X-App-Version": "2.0.0"}
base = "https://biwenger.as.com/api/v2/league"

@st.cache_data(ttl=5)
def get_all_data():
    r_users = requests.get(base, headers=headers).json()
    r_transfers = requests.get(f"{base}/transfers?limit=50", headers=headers).json()
    r_board = requests.get(f"{base}/board?limit=50", headers=headers).json()
    return r_users, r_transfers, r_board

users_resp, transfers_resp, board_resp = get_all_data()

users_data = users_resp.get("data", {}).get("users", [])
transfers = transfers_resp.get("data", [])
board = board_resp.get("data", [])

user_adjustments = {u.get("id"): 0.0 for u in users_data}
user_names = {u.get("id"): u.get("name") for u in users_data}
detected_events_log = []

def add_money(user_id, amount, desc):
    if user_id in user_adjustments and amount > 0:
        user_adjustments[user_id] += amount
        detected_events_log.append({
            "Usuario": user_names.get(user_id, str(user_id)),
            "Importe (€)": amount,
            "Descripción": desc
        })

# Analizar transferencias formales
for t in transfers:
    if not isinstance(t, dict): continue
    # Estructura típica de transferencias
    amt = float(t.get("amount", 0) or t.get("price", 0) or 0)
    # Comprobar si hay vendedor
    seller = t.get("from")
    if isinstance(seller, dict): seller = seller.get("id")
    if seller:
        add_money(seller, amt, "Venta en transfers")

# Analizar el tablón (feed) de forma exhaustiva
for item in board:
    if not isinstance(item, dict): continue
    # Extraer datos del evento del tablón
    u_ev = item.get("user") # ID del usuario que genera el evento
    content = item.get("content")
    ev_type = str(item.get("type", ""))
    
    # Si el contenido es una lista o un diccionario
    elements = content if isinstance(content, list) else [content]
    
    for el in elements:
        if isinstance(el, dict):
            amt = float(el.get("amount", 0) or el.get("price", 0) or el.get("value", 0) or 0)
            # Buscar si hay un vendedor explícito
            from_obj = el.get("from")
            s_id = from_obj.get("id") if isinstance(from_obj, dict) else from_obj
            
            if not s_id and u_id: # Si no especifica 'from' pero pertenece al usuario del evento
                s_id = u_ev
                
            if s_id and amt > 0:
                add_money(int(s_id), amt, f"Movimiento en tablón (Tipo: {ev_type})")
        elif isinstance(content, (int, float)) and content > 0 and u_ev:
            add_money(int(u_ev), float(content), f"Evento numérico tablón ({ev_type})")

# --- TABLA FINAL ---
records = []
for u in users_data:
    u_id = u.get("id")
    name = str(u.get("name", "Desconocido")).lower()
    
    v_inicial = DAY_ONE_VALS.get(name, 21500000.0)
    ajuste = user_adjustments.get(u_id, 0.0)
    
    saldo_real = (INITIAL_TOTAL - v_inicial) + ajuste
    v_actual = float(u.get("teamValue", 0) or 0)
    puja_max = saldo_real + ((max_bid_pct / 100.0) * v_actual)
    
    records.append({
        "Usuario": u.get("name"),
        "💸 Saldo Real en Caja": saldo_real,
        "🔄 Ajuste Detectado": ajuste,
        "🔥 Puja Máxima Real": puja_max
    })

df = pd.DataFrame(records).sort_values("💸 Saldo Real en Caja", ascending=False)
for col in ["💸 Saldo Real en Caja", "🔄 Ajuste Detectado", "🔥 Puja Máxima Real"]:
    df[col] = df[col].apply(lambda x: f"{x:,.0f} €".replace(",", "."))

st.subheader("📊 Monitor Financiero en Directo")
st.dataframe(df, use_container_width=True, hide_index=True)

# --- PANEL DE DIAGNOSTICO ---
with st.expander("🛠️ Depuración: Ver qué devuelve exactamente la API del Tablón"):
    st.write("Si el script sigue sin ver la venta, expande esto para examinar los datos crudos que nos entrega Biwenger:")
    st.json(board[:5]) # Muestra los primeros 5 elementos del tablón tal cual llegan
