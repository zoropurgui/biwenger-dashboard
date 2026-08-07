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
        if not leagues: return None, None, {}, {}, {}
        
        l = leagues[0]
        l_id = l.get("id")
        u_id = l.get("user", {}).get("id")
        
        h_league = h.copy()
        h_league.update({"X-League": str(l_id), "X-User": str(u_id)})
        
        r_league = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}?include=all", headers=h_league).json()
        r_transfers = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}/transfers?limit=50", headers=h_league).json()
        r_board = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}/board?limit=50", headers=h_league).json()
        
        return l_id, u_id, r_league, r_transfers, r_board
    except Exception as e:
        return None, None, {"error": str(e)}, {}, {}

l_id, u_id, league_resp, transfers_resp, board_resp = load_data(clean_token)

if not l_id:
    st.error("❌ Error al conectar con la API de Biwenger. Comprueba tu token.")
    st.stop()

max_bid_pct = st.sidebar.slider("Crédito Valor Equipo (%)", 0, 100, 25)
if st.sidebar.button("🔄 Recargar Datos"):
    st.cache_data.clear()
    st.rerun()

# --- EXTRACCIÓN ROBUSTA Y MULTINIVEL DE VALORES DE EQUIPO ---
user_names = {}
vm_data = {}

league_data = league_resp.get("data", {}) if isinstance(league_resp, dict) else {}

# 1. Buscar en el array de usuarios ('users')
users_list = league_data.get("users", [])
if isinstance(users_list, list):
    for u in users_list:
        if isinstance(u, dict):
            uid = u.get("id")
            uname = u.get("name")
            team_val = u.get("teamValue") or u.get("value") or u.get("marketValue")
            if uid is not None and uname:
                uid_str = str(uid)
                user_names[uid_str] = uname
                if team_val is not None:
                    try:
                        v = float(team_val)
                        if v > 0:
                            vm_data[uid_str] = v
                    except:
                        pass

# 2. Buscar en la clasificación ('standings') por si estuviera ahí estructurado de otra forma
standings_list = league_data.get("standings", [])
if isinstance(standings_list, list):
    for s in standings_list:
        if isinstance(s, dict):
            uid = s.get("id") or s.get("user")
            if isinstance(uid, dict):
                uid = uid.get("id")
            uname = s.get("name") or s.get("username")
            team_val = s.get("teamValue") or s.get("value") or s.get("marketValue")
            if uid is not None:
                uid_str = str(uid)
                if uname and uid_str not in user_names:
                    user_names[uid_str] = uname
                if team_val is not None:
                    try:
                        v = float(team_val)
                        if v > 0:
                            vm_data[uid_str] = v
                    except:
                        pass

# 3. Búsqueda recursiva profunda como red de seguridad para cualquier nodo faltante
def deep_extract(node):
    if isinstance(node, dict):
        uid = node.get("id") or node.get("user") or node.get("userId")
        if isinstance(uid, dict):
            uid = uid.get("id")
        uname = node.get("name") or node.get("username") or node.get("slug")
        
        val = None
        for k in ["teamValue", "value", "marketValue", "team_value"]:
            if k in node and node[k] is not None:
                try:
                    v = float(node[k])
                    if v > 100000:
                        val = v
                        break
                except:
                    pass
        
        if uid is not None:
            uid_str = str(uid)
            if uname and (uid_str not in user_names or len(str(user_names[uid_str])) < len(str(uname))):
                user_names[uid_str] = uname
            if val is not None and (uid_str not in vm_data or vm_data[uid_str] == 0.0):
                vm_data[uid_str] = val
                
        for v_sub in node.values():
            deep_extract(v_sub)
    elif isinstance(node, list):
        for item in node:
            deep_extract(item)

deep_extract(league_resp)

# Inicializar ajustes de usuario y aplicar fallback solo si realmente no se encontró valor en la API
user_adjustments = {}
for uid, name in user_names.items():
    user_adjustments[uid] = 0.0
    if uid not in vm_data or vm_data[uid] == 0.0:
        vm_data[uid] = DAY_ONE_VALS.get(str(name).lower(), 21500000.0)

if not user_names:
    for idx, (name_key, def_val) in enumerate(DAY_ONE_VALS.items()):
        uid = str(1000 + idx)
        user_adjustments[uid] = 0.0
        user_names[uid] = name_key.title()
        vm_data[uid] = def_val

# --- PROCESAR TRANSFERENCIAS Y TABLÓN (LÓGICA INTACTA Y FUNCIONAL) ---
detected_events_log = []

def add_money(uid, amt, desc):
    uid_str = str(uid)
    if uid_str in user_adjustments and amt > 0:
        user_adjustments[uid_str] += amt
        detected_events_log.append({"Usuario": user_names.get(uid_str, uid_str), "Importe (€)": amt, "Descripción": desc})

def sub_money(uid, amt, desc):
    uid_str = str(uid)
    if uid_str in user_adjustments and amt > 0:
        user_adjustments[uid_str] -= amt
        detected_events_log.append({"Usuario": user_names.get(uid_str, uid_str), "Importe (€)": -amt, "Descripción": desc})

transfers = transfers_resp.get("data", []) if isinstance(transfers_resp, dict) else []
if isinstance(transfers, list):
    for t in transfers:
        if not isinstance(t, dict): continue
        amt = float(t.get("amount", 0) or t.get("price", 0) or 0)
        s = t.get("from"); b = t.get("to")
        if isinstance(s, dict): s = s.get("id")
        if isinstance(b, dict): b = b.get("id")
        if s is not None: add_money(s, amt, "Venta de Jugador")
        if b is not None: sub_money(b, amt, "Compra de Jugador")

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
            if s_id is not None and b_id is None and amt > 0:
                add_money(s_id, amt, "Venta Inmediata a Máquina")
            elif s_id is not None and b_id is not None and amt > 0:
                add_money(s_id, amt, "Venta entre mánagers")
                sub_money(b_id, amt, "Compra entre mánagers")

# --- CONSTRUCCIÓN DE LA TABLA FINANCIERA ---
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

with st.expander("🛠️ Panel de Diagnóstico (Ver Respuesta Bruta de la Liga)"):
    st.json(league_resp)
