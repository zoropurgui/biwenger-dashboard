import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Biwenger Financial Monitor Pro", page_icon="⚽", layout="wide")

st.title("⚽ Monitor Financiero Biwenger (Conexión por Squads)")

# --- SIDEBAR ---
token = st.sidebar.text_input("Bearer Token", type="password")
if not token:
    st.info("👈 Pega tu Bearer Token.")
    st.stop()
clean_token = token.strip().replace("Bearer ", "")

# --- CONFIG ---
DAY_ONE_VALS = {
    "athletik81": 21600000.0, "ring014": 21580000.0, "tubu": 21570000.0, 
    "marroba": 21560000.0, "zhukkov": 21560000.0, "nitwolf": 21550000.0, 
    "yoqsetio xdxd": 21550000.0, "nistalikus": 21550000.0, "moltisanti": 21540000.0, 
    "gran gravessen": 21540000.0, "zoropurgui": 21530000.0, "_caesar_": 21510000.0, 
    "nitrorx": 21490000.0
}
INITIAL_TOTAL = 40000000.0

# --- FETCH DATA ---
@st.cache_data(ttl=60)
def get_league_data(token):
    h = {"Authorization": f"Bearer {token}", "X-App-Version": "2.0.0"}
    # 1. Obtener Ligas
    res = requests.get("https://biwenger.as.com/api/v2/account", headers=h).json()
    leagues = res.get("data", {}).get("leagues", [])
    if not leagues: return None, None, None, None
    
    l = leagues[0] # Usamos la primera liga
    l_id, u_id = l.get("id"), l.get("user", {}).get("id")
    h.update({"X-League": str(l_id), "X-User": str(u_id)})
    
    # 2. Obtener Squads (donde está el VM real)
    squads = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}/squads", headers=h).json()
    transfers = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}/transfers?limit=50", headers=h).json()
    board = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}/board?limit=50", headers=h).json()
    
    return l, squads.get("data", {}), transfers.get("data", []), board.get("data", [])

league_info, squads_data, transfers, board = get_league_data(clean_token)

if not league_info:
    st.error("Error al cargar datos.")
    st.stop()

# --- LÓGICA DE CÁLCULO ---
# Mapa: id -> nombre
users_map = {u.get("id"): u.get("name") for u in league_info.get("users", [])}
user_adjustments = {u_id: 0.0 for u_id in users_map}

# 1. Calcular VM sumando precio de jugadores en squads
vm_data = {}
for u_id_str, squad in squads_data.items():
    u_id = int(u_id_str)
    total_vm = 0
    for player in squad.get("players", []):
        total_vm += player.get("price", 0) # price suele ser el valor de mercado actual
    vm_data[u_id] = total_vm

# 2. Procesar transacciones (igual que antes)
def adjust(u_id, amount, is_add):
    if u_id in user_adjustments:
        user_adjustments[u_id] += amount if is_add else -amount

for t in transfers:
    amt = t.get("amount", 0)
    s = t.get("from")
    b = t.get("to")
    if isinstance(s, dict): adjust(s.get("id"), amt, True)
    if isinstance(b, dict): adjust(b.get("id"), amt, False)

# --- TABLA ---
records = []
for u_id, name in users_map.items():
    v_actual = vm_data.get(u_id, 0)
    v_inicial = DAY_ONE_VALS.get(name.lower(), 21500000.0)
    saldo_real = (INITIAL_TOTAL - v_inicial) + user_adjustments.get(u_id, 0)
    
    records.append({
        "Usuario": name,
        "Valor del equipo": v_actual,
        "Dinero en caja": saldo_real,
        "Valor equipo + caja": v_actual + saldo_real,
        "Puja máxima": saldo_real + (0.25 * v_actual) # Ajusta el % aquí
    })

df = pd.DataFrame(records).sort_values("Dinero en caja", ascending=False)
for col in ["Valor del equipo", "Dinero en caja", "Valor equipo + caja", "Puja máxima"]:
    df[col] = df[col].apply(lambda x: f"{x:,.0f} €".replace(",", "."))

st.dataframe(df, use_container_width=True, hide_index=True)

with st.expander("🛠️ Diagnóstico"):
    st.write("VM detectado para Caesar (ID 7740818):", vm_data.get(7740818, "No encontrado"))
    st.json(squads_data.get("7740818", {}) if "7740818" in squads_data else "No hay datos de equipo")
