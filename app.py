import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Biwenger Financial Monitor Pro", page_icon="⚽", layout="wide")

st.title("⚽ Monitor Financiero Biwenger (Definitivo)")

# --- SIDEBAR: Configuración ---
st.sidebar.header("🔑 Conexión")
token = st.sidebar.text_input("Bearer Token", type="password")

if not token:
    st.info("👈 Pega tu **Bearer Token** en la barra lateral para empezar.")
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
def fetch_all_biwenger_data(t):
    h = {"Authorization": f"Bearer {t}", "X-App-Version": "2.0.0"}
    try:
        acc = requests.get("https://biwenger.as.com/api/v2/account", headers=h, timeout=8).json()
        leagues = acc.get("data", {}).get("leagues", [])
        if not leagues: return None, None, {}, {}, {}, {}, {}
        
        l = leagues[0]
        l_id, u_id = l.get("id"), l.get("user", {}).get("id")
        h.update({"X-League": str(l_id), "X-User": str(u_id)})
        
        r_league = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}", headers=h).json()
        r_standings = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}/standings", headers=h).json()
        r_squads = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}/squads", headers=h).json()
        r_transfers = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}/transfers?limit=50", headers=h).json()
        r_board = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}/board?limit=50", headers=h).json()
        
        return l_id, u_id, r_league, r_standings, r_squads, r_transfers, r_board
    except Exception:
        return None, None, {}, {}, {}, {}, {}

l_id, u_id, league_resp, standings_resp, squads_resp, transfers_resp, board_resp = fetch_all_biwenger_data(clean_token)

if not l_id:
    st.error("❌ Error de conexión o token inválido.")
    st.stop()

st.sidebar.header("⚙️ Ajustes")
max_bid_pct = st.sidebar.slider("Crédito Valor Equipo (%)", 0, 100, 25)

if st.sidebar.button("🔄 Recargar Datos"):
    st.cache_data.clear()
    st.rerun()

# Extraer usuarios combinando la liga y los standings
league_data = league_resp.get("data", {}) if isinstance(league_resp, dict) else {}
users_list = league_data.get("users", [])
standings_data = standings_resp.get("data", []) if isinstance(standings_resp, dict) else []

if not users_list and isinstance(standings_data, list):
    users_list = standings_data

if not users_list:
    users_list = [{"id": i, "name": name.title()} for i, name in enumerate(DAY_ONE_VALS.keys())]

user_adjustments = {}
user_names = {}
for u in users_list:
    if isinstance(u, dict):
        u_id = u.get("id")
        u_name = u.get("name", "Desconocido")
        if u_id:
            user_adjustments[u_id] = 0.0
            user_names[u_id] = u_name

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

# Procesar Tablón de anuncios
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

# Extracción ultra robusta del VM buscando en standings, squads o propiedades internas
vm_data = {}

# 1. Buscar en standings (que es de donde sale la vista web)
if isinstance(standings_data, list):
    for item in standings_data:
        if isinstance(item, dict):
            u_id = item.get("id")
            # Buscar teamValue en múltiples rutas posibles dentro del objeto de standings
            tv = (
                item.get("teamValue") or 
                item.get("value") or 
                (item.get("stat") or {}).get("teamValue") or
                (item.get("account") or {}).get("teamValue") or
                0.0
            )
            if u_id and tv > 0:
                vm_data[int(u_id)] = float(tv)

# 2. Si falta alguno, buscar en squads sumando jugadores
squads_data = squads_resp.get("data", {}) if isinstance(squads_resp, dict) else {}
if isinstance(squads_data, dict):
    for u_id_str, squad in squads_data.items():
        try:
            u_id = int(u_id_str)
            if u_id not in vm_data or vm_data[u_id] == 0:
                total_vm = 0
                players = squad.get("players", []) if isinstance(squad, dict) else []
                for p in players:
                    total_vm += float(p.get("price", 0) or p.get("marketValue", 0) or 0)
                if total_vm > 0:
                    vm_data[u_id] = total_vm
        except Exception:
            pass

# --- CONSTRUCCIÓN DE LA TABLA FINANCIERA ---
records = []
for u in users_list:
    if not isinstance(u, dict): continue
    u_id = u.get("id")
    name = str(u.get("name", "Desconocido"))
    name_lower = name.lower()
    
    v_actual = vm_data.get(u_id, 0.0)
    v_inicial = DAY_ONE_VALS.get(name_lower, 21500000.0)
    ajuste = user_adjustments.get(u_id, 0.0)
    
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

# --- HISTORIAL DE TRASPASOS Y MOVIMIENTOS ---
st.markdown("---")
st.subheader("📜 Historial de Traspasos y Movimientos Detectados")
if detected_events_log:
    df_log = pd.DataFrame(detected_events_log)
    df_log["Importe (€)"] = df_log["Importe (€)"].apply(lambda x: f"{x:,.0f} €".replace(",", "."))
    st.dataframe(df_log, use_container_width=True, hide_index=True)
else:
    st.info("ℹ️ No se han detectado movimientos recientes en transferencias o tablón.")

# --- PANEL DE DIAGNÓSTICO TÉCNICO ---
with st.expander("🛠️ Panel de Diagnóstico Técnico (Ver respuestas brutas de la API)"):
    st.write("**Standings Response (Datos de la tabla web):**")
    st.json(standings_resp)
