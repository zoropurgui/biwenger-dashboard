import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Biwenger Financial Monitor Pro", page_icon="⚽", layout="wide")

st.title("⚽ Monitor Financiero Biwenger (Control Total)")

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

# --- PANEL DE AJUSTES MANUALES (Para saltarse el bloqueo de la máquina) ---
st.sidebar.subheader("🛠️ Ajuste Manual (Ventas a Máquina)")
st.sidebar.caption("Usa esto si Biwenger oculta una venta a la máquina hasta mañana.")
manual_marroba = st.sidebar.number_input("Ajuste Extra para Marroba (€)", value=75000.0, step=10000.0, format="%.0f")

if st.sidebar.button("🔄 Recargar Datos"):
    st.cache_data.clear()
    st.rerun()

# --- LÓGICA DE DATOS ---
headers = {"Authorization": f"Bearer {clean_token}", "X-League": str(l_id), "X-User": str(u_id), "X-App-Version": "2.0.0"}

@st.cache_data(ttl=5)
def get_data():
    base = "https://biwenger.as.com/api/v2/league"
    try:
        users = requests.get(base, headers=headers).json().get("data", {}).get("users", [])
        transfers = requests.get(f"{base}/transfers?limit=100", headers=headers).json().get("data", [])
        board = requests.get(f"{base}/board?limit=100", headers=headers).json().get("data", [])
        return users, transfers, board
    except: return [], [], []

users_data, transfers, board = get_data()

user_adjustments = {u.get("id"): 0.0 for u in users_data}

def process_transaction(s_id, b_id, amount):
    if not amount or amount <= 0: return
    if s_id in user_adjustments: user_adjustments[s_id] += amount
    if b_id in user_adjustments: user_adjustments[b_id] -= amount

for t in transfers:
    s = t.get("from", {}).get("id") if isinstance(t.get("from"), dict) else t.get("from")
    b = t.get("to", {}).get("id") if isinstance(t.get("to"), dict) else t.get("to")
    process_transaction(s, b, float(t.get("amount", 0)))

for e in board:
    if isinstance(e.get("content"), list):
        for item in e.get("content"):
            if isinstance(item, dict):
                s = item.get("from", {}).get("id") if isinstance(item.get("from"), dict) else item.get("from")
                b = item.get("to", {}).get("id") if isinstance(item.get("to"), dict) else item.get("to")
                amt = item.get("amount") or item.get("price") or 0
                process_transaction(s, b, float(amt))

# --- GENERAR TABLA FINAL ---
records = []
for u in users_data:
    u_id = u.get("id")
    name = str(u.get("name", "Desconocido")).lower()
    
    v_inicial = DAY_ONE_VALS.get(name, 21500000.0)
    
    # Sumamos el ajuste automático del tablón + el ajuste manual por si la máquina lo oculta
    extra_manual = manual_marroba if "marroba" in name else 0.0
    total_ajustes = user_adjustments.get(u_id, 0.0) + extra_manual
    
    saldo_real = (INITIAL_TOTAL - v_inicial) + total_ajustes
    
    v_actual = float(u.get("teamValue", 0) or 0)
    puja_max = saldo_real + ((max_bid_pct / 100.0) * v_actual)
    
    records.append({
        "Usuario": u.get("name"),
        "💸 Saldo Real en Caja": saldo_real,
        "🔄 Ajuste Ventas / Máquina": total_ajustes,
        "🔥 Puja Máxima Real": puja_max
    })

df = pd.DataFrame(records).sort_values("💸 Saldo Real en Caja", ascending=False)
for col in ["💸 Saldo Real en Caja", "🔄 Ajuste Ventas / Máquina", "🔥 Puja Máxima Real"]:
    df[col] = df[col].apply(lambda x: f"{x:,.0f} €".replace(",", "."))

st.dataframe(df, use_container_width=True, hide_index=True)

st.write("---")
st.caption("💡 Consejo: Si un usuario vende a la máquina y Biwenger lo oculta, introduce la cantidad exacta en la barra lateral ('Ajuste Extra para Marroba') para forzar el cálculo real de inmediato.")
