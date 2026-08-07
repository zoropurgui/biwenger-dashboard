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

# --- EXTRACCIÓN MEJORADA: PRIORIDAD EN STANDINGS ---
user_names = {}
vm_data = {}
api_balance_data = {}
extraction_debug_logs = []

league_data = league_resp.get("data", {}) if isinstance(league_resp, dict) else {}

# 1. BÚSQUEDA EN STANDINGS (Aquí está el valor real)
standings = league_data.get("standings", [])
if isinstance(standings, list):
    for item in standings:
        uid = str(item.get("id"))
        uname = item.get("name") or item.get("username")
        user_names[uid] = uname
        
        # Diagnóstico de claves
        debug_info = {
            "ID": uid,
            "Usuario": uname,
            "Claves": list(item.keys()),
            "teamValue_encontrado": None,
            "origen": "No encontrado"
        }
        
        # Búsqueda profunda de valor
        t_val = None
        # Probamos campo directo o dentro de 'team'
        team_obj = item.get("team") if isinstance(item.get("team"), dict) else {}
        
        # Combinamos el objeto actual y el objeto 'team' para buscar
        search_space = {**item, **team_obj}
        
        for key in ["teamValue", "value", "marketValue", "price"]:
            if key in search_space and search_space[key] is not None:
                try:
                    val = float(search_space[key])
                    if val > 0:
                        t_val = val
                        debug_info["teamValue_encontrado"] = t_val
                        debug_info["origen"] = f"Buscado en: {key}"
                        break
                except:
                    pass
        
        if t_val:
            vm_data[uid] = t_val
        
        extraction_debug_logs.append(debug_info)

# 2. BÚSQUEDA DE SALDO EN USERS (Como fallback)
users_list = league_data.get("users", [])
if isinstance(users_list, list):
    for u in users_list:
        uid = str(u.get("id"))
        for b_key in ["balance", "money", "cash"]:
            if b_key in u:
                api_balance_data[uid] = float(u[b_key])
                break

# --- RESTO DEL SCRIPT (Lógica Financiera igual) ---
DAY_ONE_VALS = {
    "athletik81": 21600000.0, "ring014": 21580000.0, "tubu": 21570000.0, 
    "marroba": 21560000.0, "zhukkov": 21560000.0, "nitwolf": 21550000.0, 
    "yoqsetio xdxd": 21550000.0, "nistalikus": 21550000.0, "moltisanti": 21540000.0, 
    "gran gravessen": 21540000.0, "zoropurgui": 21530000.0, "_caesar_": 21510000.0, 
    "nitrorx": 21490000.0
}

user_adjustments = {}
for uid, name in user_names.items():
    user_adjustments[uid] = 0.0
    if uid not in vm_data or vm_data[uid] == 0.0:
        vm_data[uid] = DAY_ONE_VALS.get(str(name).lower(), 21500000.0)

# --- PROCESAR TRANSFERENCIAS Y TABLÓN ---
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
    
    if uid in api_balance_data:
        saldo_real = api_balance_data[uid] + user_adjustments.get(uid, 0.0)
    else:
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

# --- DIAGNÓSTICO CORREGIDO: Ahora mira en STANDINGS ---
with st.expander("🔍 Diagnóstico: Extracción de Valores en STANDINGS (Ahora corregido)", expanded=True):
    st.markdown("Este panel analiza la lista **standings**. Si aquí ves valores, el monitor funcionará correctamente.")
    if extraction_debug_logs:
        st.dataframe(pd.DataFrame(extraction_debug_logs), use_container_width=True)
    else:
        st.write("No hay registros de depuración disponibles.")

with st.expander("🛠️ Panel de Diagnóstico (Ver Respuesta Bruta de la Liga)"):
    st.json(league_resp)
