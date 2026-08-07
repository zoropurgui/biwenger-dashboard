import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Biwenger Financial Monitor Pro", page_icon="⚽", layout="wide")

st.title("⚽ Monitor Financiero Biwenger (Valor de Equipo Corregido)")

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
max_bid_pct = st.sidebar.slider("Porcentaje Valor Equipo para Puja (%)", 0, 100, 25)

if st.sidebar.button("🔄 Recargar Datos"):
    st.cache_data.clear()
    st.rerun()

headers = {"Authorization": f"Bearer {clean_token}", "X-League": str(l_id), "X-User": str(u_id), "X-App-Version": "2.0.0"}

@st.cache_data(ttl=5)
def get_all_data(league_id):
    url_league = f"https://biwenger.as.com/api/v2/league/{league_id}"
    url_transfers = f"https://biwenger.as.com/api/v2/league/{league_id}/transfers?limit=50"
    url_board = f"https://biwenger.as.com/api/v2/league/{league_id}/board?limit=50"
    
    r_users = requests.get(url_league, headers=headers).json()
    r_transfers = requests.get(url_transfers, headers=headers).json()
    r_board = requests.get(url_board, headers=headers).json()
    return r_users, r_transfers, r_board

users_resp, transfers_resp, board_resp = get_all_data(l_id)
users_data = users_resp.get("data", {}).get("users", [])
transfers = transfers_resp.get("data", [])
board = board_resp.get("data", [])

# ... (Lógica de transacciones igual que antes) ...
user_adjustments = {u.get("id"): 0.0 for u in users_data}
user_names = {u.get("id"): u.get("name") for u in users_data}

def add_money(user_id, amount):
    if user_id in user_adjustments and amount > 0: user_adjustments[user_id] += amount

def sub_money(user_id, amount):
    if user_id in user_adjustments and amount > 0: user_adjustments[user_id] -= amount

for t in transfers:
    amt = float(t.get("amount", 0) or t.get("price", 0) or 0)
    s = t.get("from")
    b = t.get("to")
    if isinstance(s, dict): s = s.get("id")
    if isinstance(b, dict): b = b.get("id")
    if s: add_money(int(s), amt)
    if b: sub_money(int(b), amt)

for item in board:
    content = item.get("content")
    elements = content if isinstance(content, list) else [content]
    for el in elements:
        if not isinstance(el, dict): continue
        amt = float(el.get("amount", 0) or el.get("price", 0) or el.get("value", 0) or 0)
        s = el.get("from")
        b = el.get("to")
        s_id = s.get("id") if isinstance(s, dict) else s
        b_id = b.get("id") if isinstance(b, dict) else b
        if s_id and not b_id and amt > 0: add_money(int(s_id), amt)
        elif s_id and b_id and amt > 0:
            add_money(int(s_id), amt)
            sub_money(int(b_id), amt)

# --- TABLA FINAL ---
records = []
for u in users_data:
    u_id = u.get("id")
    
    # AQUI ESTA EL CAMBIO: Probamos varios campos comunes de la API
    valor_equipo = float(u.get("teamValue") or u.get("value") or u.get("totalValue") or 0)
    
    # Ajuste por saldo inicial (basado en lo que teníamos)
    dinero_caja = float(u.get("balance", 0)) + user_adjustments.get(u_id, 0.0)
    
    valor_total = dinero_caja + valor_equipo
    puja_max = dinero_caja + ((max_bid_pct / 100.0) * valor_equipo)
    
    records.append({
        "Usuario": u.get("name"),
        "Valor del equipo": valor_equipo,
        "Dinero en caja": dinero_caja,
        "Valor total": valor_total,
        "Puja máxima": puja_max
    })

df = pd.DataFrame(records).sort_values("Dinero en caja", ascending=False)
for col in ["Valor del equipo", "Dinero en caja", "Valor total", "Puja máxima"]:
    df[col] = df[col].apply(lambda x: f"{x:,.0f} €".replace(",", "."))

st.dataframe(df, use_container_width=True, hide_index=True)

# --- DIAGNOSTICO DE CAMPOS ---
with st.expander("🛠️ Diagnóstico: Si Valor de Equipo sigue a 0, expande esto"):
    if users_data:
        st.write("Datos brutos del primer usuario (busca qué campo tiene el valor de la plantilla):")
        st.json(users_data[0])
