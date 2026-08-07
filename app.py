import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Biwenger Financial Monitor Pro", page_icon="⚽", layout="wide")

st.title("⚽ Monitor Financiero Biwenger (Definitivo y Completo)")

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
    url_standings = f"https://biwenger.as.com/api/v2/league/{league_id}/standings"
    url_transfers = f"https://biwenger.as.com/api/v2/league/{league_id}/transfers?limit=50"
    url_board = f"https://biwenger.as.com/api/v2/league/{league_id}/board?limit=50"
    
    r_standings = requests.get(url_standings, headers=headers).json()
    r_transfers = requests.get(url_transfers, headers=headers).json()
    r_board = requests.get(url_board, headers=headers).json()
    return r_standings, r_transfers, r_board

standings_resp, transfers_resp, board_resp = get_all_data(l_id)

# Extracción robusta de usuarios / standings
raw_data = standings_resp.get("data", [])
if isinstance(raw_data, dict):
    users_data = raw_data.get("standings", []) or raw_data.get("users", [])
elif isinstance(raw_data, list):
    users_data = raw_data
else:
    users_data = []

transfers = transfers_resp.get("data", [])
board = board_resp.get("data", [])

# Mapeos de seguridad
user_adjustments = {u.get("id"): 0.0 for u in users_data if isinstance(u, dict)}
user_names = {u.get("id"): u.get("name") for u in users_data if isinstance(u, dict)}
detected_events_log = []

def add_money(user_id, amount, desc):
    if user_id in user_adjustments and amount > 0:
        user_adjustments[user_id] += amount
        detected_events_log.append({"Usuario": user_names.get(user_id, str(user_id)), "Importe (€)": amount, "Descripción": desc})

def sub_money(user_id, amount, desc):
    if user_id in user_adjustments and amount > 0:
        user_adjustments[user_id] -= amount
        detected_events_log.append({"Usuario": user_names.get(user_id, str(user_id)), "Importe (€)": -amount, "Descripción": desc})

# Procesar transferencias formales
for t in transfers:
    if not isinstance(t, dict): continue
    amt = float(t.get("amount", 0) or t.get("price", 0) or 0)
    s = t.get("from"); b = t.get("to")
    if isinstance(s, dict): s = s.get("id")
    if isinstance(b, dict): b = b.get("id")
    if s: add_money(int(s), amt, "Venta")
    if b: sub_money(int(b), amt, "Compra")

# Procesar Tablón
for item in board:
    if not isinstance(item, dict): continue
    content = item.get("content")
    elements = content if isinstance(content, list) else [content]
    for el in elements:
        if not isinstance(el, dict): continue
        amt = float(el.get("amount", 0) or el.get("price", 0) or el.get("value", 0) or 0)
        from_obj = el.get("from")
        to_obj = el.get("to")
        s_id = from_obj.get("id") if isinstance(from_obj, dict) else from_obj
        b_id = to_obj.get("id") if isinstance(to_obj, dict) else to_obj
        if s_id and not b_id and amt > 0:
            add_money(int(s_id), amt, "Venta Inmediata a Máquina")
        elif s_id and b_id and amt > 0:
            add_money(int(s_id), amt, "Venta entre mánagers")
            sub_money(int(b_id), amt, "Compra entre mánagers")

# --- TABLA FINAL ---
records = []
for u in users_data:
    if not isinstance(u, dict): continue
    u_id = u.get("id")
    name = str(u.get("name", "Desconocido")).lower()
    
    # Búsqueda segura del valor del equipo en varias propiedades posibles
    v_actual = float(u.get("teamValue") or u.get("value") or 0)
    
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

if records:
    df = pd.DataFrame(records).sort_values("Dinero en caja", ascending=False)
    
    for col in ["Valor del equipo", "Dinero en caja", "Valor equipo + caja", "Puja máxima"]:
        df[col] = df[col].apply(lambda x: f"{x:,.0f} €".replace(",", "."))

    st.subheader("📊 Monitor Financiero en Directo")
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.warning("No se han encontrado registros de usuarios en esta respuesta.")

# --- PANEL DE DIAGNÓSTICO Y TRANSACCIONES RESTAURADO ---
with st.expander("🔍 Ver transacciones y ventas a la máquina | 🛠️ Diagnóstico"):
    st.write("Estructura de datos obtenida (Standings de referencia):")
    st.json(users_data[0] if users_data else {})
    
    st.subheader("Historial de movimientos detectados")
    if detected_events_log:
        df_log = pd.DataFrame(detected_events_log)
        df_log["Importe (€)"] = df_log["Importe (€)"].apply(lambda x: f"{x:,.0f} €".replace(",", "."))
        st.dataframe(df_log, use_container_width=True, hide_index=True)
    else:
        st.info("No se han detectado movimientos de dinero todavía en los registros recientes.")
