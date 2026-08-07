import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Biwenger Financial Monitor Pro", page_icon="⚽", layout="wide")

st.title("⚽ Monitor Financiero Biwenger (Conexión Standings)")

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

leagues = fetch_account_leagues(clean_token)
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

headers = {"Authorization": f"Bearer {clean_token}", "X-League": str(l_id), "X-User": str(u_id), "X-App-Version": "2.0.0"}

@st.cache_data(ttl=5)
def get_all_data(league_id):
    # Añadimos el endpoint /standings que es el que contiene el valor del equipo
    url_standings = f"https://biwenger.as.com/api/v2/league/{league_id}/standings"
    url_transfers = f"https://biwenger.as.com/api/v2/league/{league_id}/transfers?limit=50"
    url_board = f"https://biwenger.as.com/api/v2/league/{league_id}/board?limit=50"
    
    r_standings = requests.get(url_standings, headers=headers).json()
    r_transfers = requests.get(url_transfers, headers=headers).json()
    r_board = requests.get(url_board, headers=headers).json()
    return r_standings, r_transfers, r_board

standings_resp, transfers_resp, board_resp = get_all_data(l_id)

# Los datos están en "data" (es una lista de usuarios con sus stats)
users_data = standings_resp.get("data", [])
transfers = transfers_resp.get("data", [])
board = board_resp.get("data", [])

# Creamos el mapa de ajustes basado en el ID del usuario
user_adjustments = {u.get("id"): 0.0 for u in users_data}
user_names = {u.get("id"): u.get("name") for u in users_data}
detected_events_log = []

def add_money(user_id, amount, desc):
    if user_id in user_adjustments and amount > 0:
        user_adjustments[user_id] += amount
        detected_events_log.append({"Usuario": user_names.get(user_id, str(user_id)), "Importe (€)": amount, "Descripción": desc})

def sub_money(user_id, amount, desc):
    if user_id in user_adjustments and amount > 0:
        user_adjustments[user_id] -= amount
        detected_events_log.append({"Usuario": user_names.get(user_id, str(user_id)), "Importe (€)": -amount, "Descripción": desc})

# Procesar movimientos
for t in transfers:
    if not isinstance(t, dict): continue
    amt = float(t.get("amount", 0) or t.get("price", 0) or 0)
    s = t.get("from"); b = t.get("to")
    if isinstance(s, dict): s = s.get("id")
    if isinstance(b, dict): b = b.get("id")
    if s: add_money(int(s), amt, "Venta")
    if b: sub_money(int(b), amt, "Compra")

for item in board:
    if not isinstance(item, dict): continue
    content = item.get("content")
    elements = content if isinstance(content, list) else [content]
    for el in elements:
        if not isinstance(el, dict): continue
        amt = float(el.get("amount", 0) or el.get("price", 0) or el.get("value", 0) or 0)
        s_id = el.get("from").get("id") if isinstance(el.get("from"), dict) else el.get("from")
        b_id = el.get("to").get("id") if isinstance(el.get("to"), dict) else el.get("to")
        if s_id and not b_id and amt > 0: add_money(int(s_id), amt, "Venta Inmediata")
        elif s_id and b_id and amt > 0:
            add_money(int(s_id), amt, "Venta entre mánagers")
            sub_money(int(b_id), amt, "Compra entre mánagers")

# --- TABLA FINAL ---
records = []
for u in users_data:
    u_id = u.get("id")
    # Biwenger suele devolver el valor en 'teamValue' dentro de standings
    v_actual = float(u.get("teamValue", 0))
    name = str(u.get("name", "Desconocido")).lower()
    
    v_inicial = DAY_ONE_VALS.get(name, 21500000.0)
    ajuste = user_adjustments.get(u_id, 0.0)
    
    saldo_real = (INITIAL_TOTAL - v_inicial) + ajuste
    valor_total_caja = v_actual + saldo_real
    puja_max = saldo_real + ((max_bid_pct / 100.0) * v_actual)
    
    records.append({
        "Usuario": u.get("name"),
        "Valor del equipo": v_actual,
        "Dinero en caja": saldo_real,
        "Valor equipo + caja": valor_total_caja,
        "Puja máxima": puja_max
    })

df = pd.DataFrame(records).sort_values("Dinero en caja", ascending=False)

for col in ["Valor del equipo", "Dinero en caja", "Valor equipo + caja", "Puja máxima"]:
    df[col] = df[col].apply(lambda x: f"{x:,.0f} €".replace(",", "."))

st.subheader("📊 Monitor Financiero en Directo")
st.dataframe(df, use_container_width=True, hide_index=True)
