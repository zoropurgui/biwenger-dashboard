import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Biwenger Financial Monitor Pro", page_icon="⚽", layout="wide")

st.title("⚽ Monitor Financiero Biwenger (Definitivo Blindado)")

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

# --- FETCH DATA SEGURO ---
@st.cache_data(ttl=30)
def load_all_biwenger_data(t):
    h = {"Authorization": f"Bearer {t}", "X-App-Version": "2.0.0"}
    acc = requests.get("https://biwenger.as.com/api/v2/account", headers=h).json()
    leagues = acc.get("data", {}).get("leagues", [])
    if not leagues:
        return None, None, None
    
    l = leagues[0]
    l_id, u_id = l.get("id"), l.get("user", {}).get("id")
    h.update({"X-League": str(l_id), "X-User": str(u_id)})
    
    league_resp = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}", headers=h).json()
    squads_resp = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}/squads", headers=h).json()
    transfers_resp = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}/transfers?limit=50", headers=h).json()
    
    return (
        league_resp.get("data", {}),
        squads_resp.get("data", {}),
        transfers_resp.get("data", [])
    )

league_data, squads_data, transfers = load_all_biwenger_data(clean_token)

if not league_data:
    st.error("❌ No se pudieron cargar los datos. Comprueba tu token.")
    st.stop()

users_list = league_data.get("users", [])
if not users_list:
    st.error("❌ No se encontraron usuarios en esta liga.")
    st.stop()

users_map = {u.get("id"): u.get("name", "Desconocido") for u in users_list if isinstance(u, dict)}
user_adjustments = {u_id: 0.0 for u_id in users_map}

# Calcular VM sumando el precio de los jugadores en squads
vm_data = {}
if isinstance(squads_data, dict):
    for u_id_str, squad in squads_data.items():
        try:
            u_id = int(u_id_str)
            total_vm = 0
            players = squad.get("players", []) if isinstance(squad, dict) else []
            for p in players:
                total_vm += float(p.get("price", 0) or 0)
            vm_data[u_id] = total_vm
        except Exception:
            pass
elif isinstance(squads_data, list):
    for item in squads_data:
        if isinstance(item, dict):
            u_id = item.get("id")
            total_vm = 0
            players = item.get("players", [])
            for p in players:
                total_vm += float(p.get("price", 0) or 0)
            if u_id:
                vm_data[int(u_id)] = total_vm

# Procesar transferencias
if isinstance(transfers, list):
    for t in transfers:
        if not isinstance(t, dict): continue
        amt = float(t.get("amount", 0) or t.get("price", 0) or 0)
        s = t.get("from"); b = t.get("to")
        if isinstance(s, dict): s = s.get("id")
        if isinstance(b, dict): b = b.get("id")
        if s and s in user_adjustments and amt > 0:
            user_adjustments[s] += amt
        if b and b in user_adjustments and amt > 0:
            user_adjustments[b] -= amt

# --- TABLA FINAL ---
records = []
for u_id, name in users_map.items():
    v_actual = vm_data.get(u_id, 0.0)
    v_inicial = DAY_ONE_VALS.get(str(name).lower(), 21500000.0)
    saldo_real = (INITIAL_TOTAL - v_inicial) + user_adjustments.get(u_id, 0.0)
    
    records.append({
        "Usuario": name,
        "Valor del equipo": v_actual,
        "Dinero en caja": saldo_real,
        "Valor equipo + caja": v_actual + saldo_real,
        "Puja máxima": saldo_real + (0.25 * v_actual)
    })

if records:
    df = pd.DataFrame(records).sort_values("Dinero en caja", ascending=False)
    for col in ["Valor del equipo", "Dinero en caja", "Valor equipo + caja", "Puja máxima"]:
        df[col] = df[col].apply(lambda x: f"{x:,.0f} €".replace(",", "."))
    st.subheader("📊 Monitor Financiero en Directo")
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.warning("⚠️ No hay registros para mostrar.")

with st.expander("🛠️ Diagnóstico"):
    st.write("Usuarios totales:", len(users_map))
    st.write("Mánagers con VM calculado:", len(vm_data))
    st.json(list(squads_data.items())[:1] if isinstance(squads_data, dict) else {})
