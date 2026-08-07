import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Biwenger Financial Monitor Pro", page_icon="⚽", layout="wide")

st.title("⚽ Monitor Financiero Biwenger (Automático Real-Time)")

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

@st.cache_data(ttl=60)
def fetch_account_leagues(t):
    url = "https://biwenger.as.com/api/v2/account"
    h = {"Authorization": f"Bearer {t}", "X-App-Version": "2.0.0"}
    try:
        req = requests.get(url, headers=h, timeout=8)
        return req.json().get("data", {}).get("leagues", [])
    except: return []

leagues = fetch_account_leagues(clean_token)
if not leagues:
    st.sidebar.error("❌ Token inválido.")
    st.stop()

league_dict = {l.get("name"): (l.get("id"), l.get("user", {}).get("id")) for l in leagues}
selected_league = st.sidebar.selectbox("🏆 Liga", list(league_dict.keys()))
l_id, u_id = league_dict[selected_league]

st.sidebar.header("⚙️ Ajustes")
max_bid_pct = st.sidebar.slider("Crédito Valor Equipo (%)", 0, 100, 25)

if st.sidebar.button("🔄 Recargar Datos"):
    st.cache_data.clear()
    st.rerun()

# --- LÓGICA DE DATOS Y PARSER ROBUSTO ---
headers = {"Authorization": f"Bearer {clean_token}", "X-League": str(l_id), "X-User": str(u_id), "X-App-Version": "2.0.0"}

@st.cache_data(ttl=5)
def get_data():
    base = "https://biwenger.as.com/api/v2/league"
    try:
        users_resp = requests.get(base, headers=headers).json()
        users = users_resp.get("data", {}).get("users", [])
        
        transfers_resp = requests.get(f"{base}/transfers?limit=100", headers=headers).json()
        transfers = transfers_resp.get("data", [])
        
        board_resp = requests.get(f"{base}/board?limit=100", headers=headers).json()
        board = board_resp.get("data", [])
        
        return users, transfers, board
    except: return [], [], []

users_data, transfers, board = get_data()

user_adjustments = {u.get("id"): 0.0 for u in users_data}
user_names = {u.get("id"): u.get("name") for u in users_data}

detected_events_log = []

def extract_id(val):
    if isinstance(val, dict):
        return val.get("id")
    if isinstance(val, (int, str)) and str(val).isdigit():
        return int(val)
    return None

def process_transaction(s_raw, b_raw, amount, source_desc=""):
    try:
        amt = float(amount)
    except:
        amt = 0.0
    if amt <= 0:
        return
    
    s_id = extract_id(s_raw)
    b_id = extract_id(b_raw)
    
    if s_id in user_adjustments:
        user_adjustments[s_id] += amt
    if b_id in user_adjustments:
        user_adjustments[b_id] -= amt
        
    s_name = user_names.get(s_id, f"Usuario {s_id}" if s_id else "Máquina / Mercado")
    b_name = user_names.get(b_id, f"Usuario {b_id}" if b_id else "Máquina / Mercado")
    
    detected_events_log.append({
        "Fuente": source_desc,
        "Vendedor": s_name,
        "Comprador": b_name,
        "Importe (€)": amt
    })

# 1. Procesar endpoint de transferencias
for t in transfers:
    if not isinstance(t, dict): continue
    s = t.get("from")
    b = t.get("to")
    amt = t.get("amount") or t.get("price") or 0
    process_transaction(s, b, amt, "Transfers API")

# 2. Procesar endpoint del tablón (feed) de forma robusta
for e in board:
    if not isinstance(e, dict): continue
    e_user = e.get("user")
    content = e.get("content")
    
    items = []
    if isinstance(content, list):
        items = content
    elif isinstance(content, dict):
        items = [content]
        
    for item in items:
        if not isinstance(item, dict): continue
        s = item.get("from")
        b = item.get("to")
        amt = item.get("amount") or item.get("price") or item.get("value") or 0
        
        # Si es una venta a la máquina (vender a ordenador sin 'to'), el usuario emisor es el vendedor
        if not s and e_user and amt > 0:
            ev_type = str(e.get("type", "")).lower()
            if "transfer" in ev_type or "sale" in ev_type or "market" in ev_type or "player" in ev_type:
                s = e_user
                
        process_transaction(s, b, amt, "Tablón (Feed)")

# --- GENERAR TABLA FINAL ---
records = []
for u in users_data:
    u_id = u.get("id")
    name = str(u.get("name", "Desconocido")).lower()
    
    v_inicial = DAY_ONE_VALS.get(name, 21500000.0)
    ajuste_total = user_adjustments.get(u_id, 0.0)
    
    saldo_real = (INITIAL_TOTAL - v_inicial) + ajuste_total
    v_actual = float(u.get("teamValue", 0) or 0)
    puja_max = saldo_real + ((max_bid_pct / 100.0) * v_actual)
    
    records.append({
        "Usuario": u.get("name"),
        "💸 Saldo Real en Caja": saldo_real,
        "🔄 Ajuste Automático Tablón": ajuste_total,
        "🔥 Puja Máxima Real": puja_max
    })

df = pd.DataFrame(records).sort_values("💸 Saldo Real en Caja", ascending=False)
for col in ["💸 Saldo Real en Caja", "🔄 Ajuste Automático Tablón", "🔥 Puja Máxima Real"]:
    df[col] = df[col].apply(lambda x: f"{x:,.0f} €".replace(",", "."))

st.subheader("📊 Monitor Financiero en Directo")
st.dataframe(df, use_container_width=True, hide_index=True)

with st.expander("🔍 Ver transacciones y eventos detectados automáticamente"):
    if detected_events_log:
        df_log = pd.DataFrame(detected_events_log)
        df_log["Importe (€)"] = df_log["Importe (€)"].apply(lambda x: f"{x:,.0f} €".replace(",", "."))
        st.dataframe(df_log, use_container_width=True, hide_index=True)
    else:
        st.info("No se han detectado movimientos de transacciones todavía.")
