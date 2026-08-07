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

# --- EXTRACCIÓN DIRECTA Y LIMPIA DE LA API (STANDINGS Y USERS) ---
league_data = league_resp.get("data", {}) if isinstance(league_resp, dict) else {}
standings = league_data.get("standings", [])
users_list = league_data.get("users", [])

financial_data = {}
extraction_debug_logs = []

# 1. Leer desde standings (fuente principal de clasificación y valor de equipo)
if isinstance(standings, list):
    for s in standings:
        if not isinstance(s, dict): continue
        uid = s.get("id")
        if uid is None and isinstance(s.get("user"), dict):
            uid = s.get("user").get("id")
            
        if uid is not None:
            uid_str = str(uid)
            uname = s.get("name") or s.get("username")
            if not uname and isinstance(s.get("user"), dict):
                uname = s.get("user").get("name") or s.get("user").get("username")
            
            team_val = float(s.get("teamValue", 0) or 0)
            balance_val = float(s.get("balance", 0) or s.get("money", 0) or 0)
            
            financial_data[uid_str] = {
                "name": uname or f"Mánager {uid_str}",
                "teamValue": team_val,
                "balance": balance_val
            }

# 2. Combinar/Actualizar con users (fuente de balance oficial)
if isinstance(users_list, list):
    for u in users_list:
        if not isinstance(u, dict): continue
        uid = u.get("id")
        if uid is not None:
            uid_str = str(uid)
            uname = u.get("name") or u.get("username")
            balance_val = u.get("balance")
            team_val = u.get("teamValue") or u.get("value")
            
            if uid_str not in financial_data:
                financial_data[uid_str] = {
                    "name": uname or f"Mánager {uid_str}",
                    "teamValue": float(team_val) if team_val is not None else 0.0,
                    "balance": float(balance_val) if balance_val is not None else 0.0
                }
            else:
                if balance_val is not None:
                    financial_data[uid_str]["balance"] = float(balance_val)
                if team_val is not None and float(team_val) > 0:
                    financial_data[uid_str]["teamValue"] = float(team_val)
                if uname:
                    financial_data[uid_str]["name"] = uname

for uid_str, data in financial_data.items():
    extraction_debug_logs.append({
        "ID": uid_str,
        "Usuario": data["name"],
        "Valor del Equipo": data["teamValue"],
        "Dinero en Caja": data["balance"]
    })

# --- PROCESAR HISTORIAL DE TRASPASOS Y TABLÓN PARA EL LOG ---
detected_events_log = []

transfers = transfers_resp.get("data", []) if isinstance(transfers_resp, dict) else []
if isinstance(transfers, list):
    for t in transfers:
        if not isinstance(t, dict): continue
        amt = float(t.get("amount", 0) or t.get("price", 0) or 0)
        s = t.get("from"); b = t.get("to")
        if isinstance(s, dict): s = s.get("name") or s.get("id")
        if isinstance(b, dict): b = b.get("name") or b.get("id")
        if s is not None:
            detected_events_log.append({"Movimiento": "Venta de Jugador", "Detalle": f"Venta por {amt:,.0f} €"})
        if b is not None:
            detected_events_log.append({"Movimiento": "Compra de Jugador", "Detalle": f"Compra por {amt:,.0f} €"})

board = board_resp.get("data", []) if isinstance(board_resp, dict) else []
if isinstance(board, list):
    for item in board:
        if not isinstance(item, dict): continue
        content = item.get("content")
        elements = content if isinstance(content, list) else [content]
        for el in elements:
            if not isinstance(el, dict): continue
            amt = float(el.get("amount", 0) or el.get("price", 0) or el.get("value", 0) or 0)
            if amt > 0:
                detected_events_log.append({"Movimiento": "Movimiento en Tablón", "Detalle": f"Operación de {amt:,.0f} €"})

# --- CONSTRUCCIÓN DE LA TABLA FINANCIERA ---
records = []
for uid, data in financial_data.items():
    v_actual = data["teamValue"]
    saldo_real = data["balance"]
    
    valor_total_caja = v_actual + saldo_real
    puja_max = saldo_real + ((max_bid_pct / 100.0) * v_actual)
    
    records.append({
        "Usuario": data["name"],
        "Valor del equipo": v_actual,
        "Dinero en caja": saldo_real,
        "Valor equipo + caja": valor_total_caja,
        "Puja máxima": puja_max
    })

if records:
    df = pd.DataFrame(records).sort_values("Valor equipo + caja", ascending=False)
    for col in ["Valor del equipo", "Dinero en caja", "Valor equipo + caja", "Puja máxima"]:
        df[col] = df[col].apply(lambda x: f"{x:,.0f} €".replace(",", "."))
    
    st.subheader("📊 Monitor Financiero en Directo")
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.warning("⚠️ No hay datos para mostrar en la tabla. Comprueba la conexión con la liga.")

st.markdown("---")
st.subheader("📜 Historial de Traspasos y Movimientos Detectados")
if detected_events_log:
    df_log = pd.DataFrame(detected_events_log)
    st.dataframe(df_log, use_container_width=True, hide_index=True)
else:
    st.info("ℹ️ No se han detectado movimientos recientes.")

# --- DIAGNÓSTICO ---
with st.expander("🔍 Diagnóstico de Extracción Directa", expanded=False):
    st.markdown("Comprueba aquí que los valores extraídos coinciden con los de tu aplicación de Biwenger.")
    if extraction_debug_logs:
        df_debug = pd.DataFrame(extraction_debug_logs)
        for col in ["Valor del Equipo", "Dinero en Caja"]:
            df_debug[col] = df_debug[col].apply(lambda x: f"{x:,.0f} €".replace(",", "."))
        st.dataframe(df_debug, use_container_width=True, hide_index=True)
    else:
        st.write("No hay registros de depuración disponibles.")

with st.expander("🛠️ Panel de Diagnóstico (Ver Respuesta Bruta de la Liga)"):
    st.json(league_resp)
