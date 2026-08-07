import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Monitor Financiero Biwenger", page_icon="⚽", layout="wide")

st.title("⚽ Monitor Financiero Biwenger")

# --- SIDEBAR: Configuración ---
token = st.sidebar.text_input("Bearer Token", type="password")

if not token:
    st.info("👈 Pega tu **Bearer Token** en la barra lateral para empezar.")
    st.stop()

clean_token = token.strip().replace("Bearer ", "").strip()

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
def load_data(t):
    h = {"Authorization": f"Bearer {t}", "X-App-Version": "2.0.0"}
    try:
        acc = requests.get("https://biwenger.as.com/api/v2/account", headers=h, timeout=8).json()
        leagues = acc.get("data", {}).get("leagues", [])
        if not leagues: return None, None, {}, {}, {}, {}
        
        l = leagues[0]
        l_id = l.get("id")
        u_id = l.get("user", {}).get("id")
        
        h_league = h.copy()
        h_league.update({"X-League": str(l_id), "X-User": str(u_id)})
        
        r_league = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}", headers=h_league).json()
        r_squads = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}/squads", headers=h_league).json()
        r_transfers = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}/transfers?limit=50", headers=h_league).json()
        r_board = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}/board?limit=50", headers=h_league).json()
        
        return l_id, u_id, r_league, r_squads, r_transfers, r_board
    except Exception as e:
        return None, None, {"error": str(e)}, {}, {}, {}

l_id, u_id, league_resp, squads_resp, transfers_resp, board_resp = load_data(clean_token)

if not l_id:
    st.error("❌ Error al conectar con la API de Biwenger. Comprueba tu token.")
    st.stop()

max_bid_pct = st.sidebar.slider("Crédito Valor Equipo (%)", 0, 100, 25)
if st.sidebar.button("🔄 Recargar Datos"):
    st.cache_data.clear()
    st.rerun()

league_data = league_resp.get("data", {}) if isinstance(league_resp, dict) else {}
users_list = league_data.get("users", [])

user_adjustments = {}
user_names = {}
for u in users_list:
    if isinstance(u, dict):
        uid = u.get("id")
        uname = u.get("name", "Desconocido")
        if uid:
            user_adjustments[uid] = 0.0
            user_names[uid] = uname

# Extracción robusta del Valor de Mercado (VM) desde squads
vm_data = {}
squads_data = squads_resp.get("data", {})

if isinstance(squads_data, dict):
    for uid_str, squad in squads_data.items():
        try:
            uid = int(uid_str)
            total_vm = float(squad.get("value", 0) or squad.get("teamValue", 0) or 0)
            if total_vm == 0 and isinstance(squad.get("players"), list):
                total_vm = sum(float(p.get("price", 0) or p.get("marketValue", 0) or 0) for p in squad["players"])
            vm_data[uid] = total_vm
        except Exception:
            pass
elif isinstance(squads_data, list):
    for item in squads_data:
        if isinstance(item, dict):
            uid = item.get("user") or item.get("id")
            total_vm = float(item.get("value", 0) or item.get("teamValue", 0) or 0)
            if total_vm == 0 and isinstance(item.get("players"), list):
                total_vm = sum(float(p.get("price", 0) or p.get("marketValue", 0) or 0) for p in item["players"])
            if uid:
                vm_data[int(uid)] = total_vm

# Procesar transferencias y tablón
detected_events_log = []

def add_money(uid, amt, desc):
    if uid in user_adjustments and amt > 0:
        user_adjustments[uid] += amt
        detected_events_log.append({"Usuario": user_names.get(uid, str(uid)), "Importe (€)": amt, "Descripción": desc})

def sub_money(uid, amt, desc):
    if uid in user_adjustments and amt > 0:
        user_adjustments[uid] -= amt
        detected_events_log.append({"Usuario": user_names.get(uid, str(uid)), "Importe (€)": -amt, "Descripción": desc})

transfers = transfers_resp.get("data", []) if isinstance(transfers_resp, dict) else []
if isinstance(transfers, list):
    for t in transfers:
        if not isinstance(t, dict): continue
        amt = float(t.get("amount", 0) or t.get("price", 0) or 0)
        s = t.get("from"); b = t.get("to")
        if isinstance(s, dict): s = s.get("id")
        if isinstance(b, dict): b = b.get("id")
        if s: add_money(int(s), amt, "Venta de Jugador")
        if b: sub_money(int(b), amt, "Compra de Jugador")

board = board_resp.get("data", []) if isinstance(board_resp, dict) else []
if isinstance(board, list):
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

# Construcción de la tabla financiera
records = []
for uid, name in user_names.items():
    v_actual = vm_data.get(uid, 0.0)
    v_inicial = DAY_ONE_VALS.get(str(name).lower(), 21500000.0)
    ajuste = user_adjustments.get(uid, 0.0)
    
    saldo_real = (INITIAL_TOTAL - v_inicial) + ajuste
    valor_total_caja = v_actual + saldo_real
    puja_max = saldo_real + ((max_bid_pct / 100.0) * v_actual)
    
    records.append({
        "Usuario": name,
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
    st.warning("⚠️ No hay datos para mostrar en la tabla.")

st.markdown("---")
st.subheader("📜 Historial de Traspasos y Movimientos Detectados")
if detected_events_log:
    df_log = pd.DataFrame(detected_events_log)
    df_log["Importe (€)"] = df_log["Importe (€)"].apply(lambda x: f"{x:,.0f} €".replace(",", "."))
    st.dataframe(df_log, use_container_width=True, hide_index=True)
else:
    st.info("ℹ️ No se han detectado movimientos recientes.")

with st.expander("🛠️ Panel de Diagnóstico (Ver estructura de Squads)"):
    st.json(squads_resp)
