import streamlit as st
import pandas as pd
import requests
import time

st.set_page_config(page_title="Biwenger Dashboard", page_icon="⚽", layout="wide")

st.title("⚽ Liga Biwenger de Polola")

# --- SIDEBAR: Credenciales y Ajustes ---
st.sidebar.header("🔑 Credenciales de Biwenger")
token = st.sidebar.text_input("Bearer Token", type="password", help="Tu token de autorización")
league_id = st.sidebar.text_input("League ID", help="ID numérico de tu liga")
user_id = st.sidebar.text_input("User ID (Opcional)", help="Tu ID de usuario para resaltar tu equipo")

st.sidebar.header("⚙️ Configuración Financiera")
initial_budget = st.sidebar.number_input(
    "Presupuesto Total Inicial (€)", 
    value=40000000, 
    step=1000000, 
    help="Reparto inicial del 31 de julio: 40M (Plantilla + Caja)"
)

max_bid_pct = st.sidebar.slider(
    "Crédito sobre VM para Puja Máx. (%)", 
    min_value=0.0, 
    max_value=100.0, 
    value=25.0, 
    step=1.0,
    help="Regla oficial de Biwenger: 25% del Valor de Plantilla (0.25)"
)

if not token or not league_id:
    st.info("👈 Introduce tu **Bearer Token** y **League ID** en la barra lateral para cargar la liga.")
    st.stop()

clean_token = token.strip()
if clean_token.lower().startswith("bearer "):
    clean_token = clean_token[7:].strip()

clean_league_id = str(league_id).strip()
clean_user_id = str(user_id).strip() if user_id else ""

# --- FUNCIÓN AUXILIAR: Extracción recursiva del Valor de Plantilla ---
def extract_team_value(obj):
    if isinstance(obj, (int, float)):
        return float(obj)
    if isinstance(obj, dict):
        for k in ["teamValue", "team_value", "value", "price"]:
            if k in obj and isinstance(obj[k], (int, float)) and obj[k] > 0:
                return float(obj[k])
        if "team" in obj and obj["team"]:
            val = extract_team_value(obj["team"])
            if val > 0:
                return val
        if "players" in obj and isinstance(obj["players"], list):
            return sum(extract_team_value(p) for p in obj["players"])
    if isinstance(obj, list):
        return sum(extract_team_value(item) for item in obj)
    return 0.0

@st.cache_data(ttl=60)
def fetch_league_data(tok, l_id, u_id):
    headers = {
        "Authorization": f"Bearer {tok}",
        "X-League": l_id,
        "Accept": "application/json, text/plain, */*",
        "X-App-Version": "2.0.0",
        "X-Lang": "es",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    if u_id:
        headers["X-User"] = u_id

    data = {}
    errors = []

    # 1. Intentar endpoints globales de liga
    league_urls = [
        f"https://biwenger.as.com/api/v2/league?fields=*,users(*,team),standings(*,user,team)",
        f"https://biwenger.as.com/api/v2/league/users?fields=*,team",
        f"https://biwenger.as.com/api/v2/league/standings?fields=*,team"
    ]
    
    users_list = []
    for url in league_urls:
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                res_json = resp.json().get("data", {})
                if isinstance(res_json, dict):
                    data.update(res_json)
                    found_users = res_json.get("users", []) or res_json.get("standings", [])
                    if found_users:
                        users_list = found_users
                        break
                elif isinstance(res_json, list):
                    users_list = res_json
                    break
        except Exception as e:
            errors.append(f"Error en {url}: {str(e)}")

    # 2. Consultar perfiles individuales con fallbacks
    detailed_users = []
    for u in users_list:
        if not isinstance(u, dict):
            continue
        
        uid = u.get("id") or (u.get("user", {}).get("id") if isinstance(u.get("user"), dict) else None)
        u_info = dict(u)

        if "balance" in u and u["balance"] is not None:
            u_info["real_balance"] = u["balance"]

        if uid:
            user_endpoints = [
                f"https://biwenger.as.com/api/v2/user/{uid}?fields=id,name,team,teamValue,balance",
                f"https://biwenger.as.com/api/v2/user/{uid}/team",
                f"https://biwenger.as.com/api/v2/user/{uid}?fields=team"
            ]
            
            for u_url in user_endpoints:
                try:
                    time.sleep(0.1)
                    resp_u = requests.get(u_url, headers=headers, timeout=5)
                    if resp_u.status_code == 200:
                        u_data = resp_u.json().get("data", {})
                        if u_data:
                            u_info["detailed_user_data"] = u_data
                            if isinstance(u_data, dict) and "balance" in u_data and u_data["balance"] is not None:
                                u_info["real_balance"] = u_data.get("balance")
                            
                            # Si ya encontramos un valor de equipo > 0, no probamos más endpoints
                            if extract_team_value(u_data) > 0:
                                break
                except Exception:
                    pass

        detailed_users.append(u_info)

    data["detailed_users"] = detailed_users

    # 3. Descargar el Tablón de Noticias/Movimientos
    url_board = "https://biwenger.as.com/api/v2/league/board?limit=500"
    try:
        resp_b = requests.get(url_board, headers=headers, timeout=10)
        if resp_b.status_code == 200:
            data["board"] = resp_b.json().get("data", [])
        else:
            errors.append(f"HTTP {resp_b.status_code} en /board")
    except Exception as e:
        errors.append(f"Error en /board: {str(e)}")

    return data, errors

league_data, error_logs = fetch_league_data(clean_token, clean_league_id, clean_user_id)
detailed_users = league_data.get("detailed_users", [])
board_events = league_data.get("board", [])

if not detailed_users:
    st.error("❌ No se pudieron obtener los datos de los mánagers.")
    if error_logs:
        st.warning("🔍 **Informe de diagnóstico:**")
        for err in error_logs:
            st.write(f"- `{err}`")
    st.stop()

league_name = league_data.get('name', 'Mi Liga')
st.subheader(f"🏆 Liga: {league_name}")

# --- AUDITORÍA DE MOVIMIENTOS EN EL TABLÓN ---
user_moves = {}
for u in detailed_users:
    uid = u.get("id") or (u.get("user", {}).get("id") if isinstance(u.get("user"), dict) else None)
    if uid:
        try:
            user_moves[int(uid)] = {"spent": 0.0, "gained": 0.0}
        except ValueError:
            pass

if isinstance(board_events, list):
    for event in board_events:
        if not isinstance(event, dict):
            continue
        
        ev_type = event.get("type")
        content = event.get("content")
        items = content if isinstance(content, list) else ([content] if isinstance(content, dict) else [event])
            
        for item in items:
            if not isinstance(item, dict):
                continue
                
            raw_amount = item.get("amount") or item.get("price") or 0
            try:
                amount = float(raw_amount)
            except (ValueError, TypeError):
                amount = 0.0

            seller = item.get("from")
            seller_id = seller.get("id") if isinstance(seller, dict) else seller
            try:
                seller_id = int(seller_id) if seller_id is not None else None
            except ValueError:
                seller_id = None

            buyer = item.get("to") or item.get("user")
            buyer_id = buyer.get("id") if isinstance(buyer, dict) else buyer
            try:
                buyer_id = int(buyer_id) if buyer_id is not None else None
            except ValueError:
                buyer_id = None

            if ev_type in ["transfer", "market", "clause", "purchase", "sale"]:
                if seller_id in user_moves:
                    user_moves[seller_id]["gained"] += amount
                if buyer_id in user_moves:
                    user_moves[buyer_id]["spent"] += amount
                        
            elif ev_type in ["bonus", "admin_bonus", "adminBonus", "reward", "prize"]:
                if buyer_id in user_moves:
                    user_moves[buyer_id]["gained"] += amount

def parse_entry(entry):
    uid = entry.get("id")
    if not uid and isinstance(entry.get("user"), dict):
        uid = entry["user"].get("id")
    try:
        uid = int(uid) if uid is not None else None
    except ValueError:
        pass

    u_data = entry.get("detailed_user_data", {})
    user_obj = u_data if u_data else (entry.get("user") if isinstance(entry.get("user"), dict) else {})

    name = (
        u_data.get("name") or 
        entry.get("name") or 
        user_obj.get("name") or 
        f"Mánager {uid or ''}"
    )

    points = entry.get("points") if entry.get("points") is not None else user_obj.get("points", 0)

    # 1. Extraer Valor de Plantilla
    val = extract_team_value(entry)

    # 2. Extraer Dinero en Caja
    if "real_balance" in entry and entry["real_balance"] is not None:
        bal = float(entry["real_balance"])
    elif "balance" in u_data and u_data["balance"] is not None:
        bal = float(u_data["balance"])
    else:
        moves = user_moves.get(uid, {"spent": 0.0, "gained": 0.0})
        net_board_cash = moves["gained"] - moves["spent"]
        bal = (initial_budget - val) + net_board_cash

    return {
        "ID User": uid,
        "Usuario": str(name),
        "Puntos": int(points or 0),
        "Valor Equipo (€)": float(val),
        "Dinero en Caja (€)": float(bal)
    }

rivals_list = [parse_entry(e) for e in detailed_users]
df_standings = pd.DataFrame(rivals_list)

df_standings["Posición"] = range(1, len(df_standings) + 1)
df_standings["Valor Total (€)"] = df_standings["Valor Equipo (€)"] + df_standings["Dinero en Caja (€)"]

# Puja Máxima: Dinero en caja + (% sobre Valor de Equipo)
df_standings["Puja Máxima (€)"] = df_standings["Dinero en Caja (€)"] + ((max_bid_pct / 100.0) * df_standings["Valor Equipo (€)"])

tab1, tab2 = st.tabs(["📊 Clasificación y VM de Rivales", "👤 Mi Equipo"])

with tab1:
    st.write("### 👥 Clasificación y Estado Financiero Calculado")

    cols_order = [
        "Posición",
        "Usuario",
        "Puntos",
        "Valor Equipo (€)",
        "Dinero en Caja (€)",
        "Valor Total (€)",
        "Puja Máxima (€)"
    ]
    
    df_table = df_standings[cols_order].copy()

    def color_negative_red(val):
        if isinstance(val, (int, float)) and val < 0:
            return 'color: #ff4b4b; font-weight: bold;'
        return ''

    if hasattr(df_table.style, "map"):
        styler = df_table.style.map(color_negative_red, subset=["Dinero en Caja (€)"])
    else:
        styler = df_table.style.applymap(color_negative_red, subset=["Dinero en Caja (€)"])

    styler = styler.format({
        "Valor Equipo (€)": lambda x: f"{x:,.0f} €".replace(",", "."),
        "Dinero en Caja (€)": lambda x: f"{x:,.0f} €".replace(",", "."),
        "Valor Total (€)": lambda x: f"{x:,.0f} €".replace(",", "."),
        "Puja Máxima (€)": lambda x: f"{x:,.0f} €".replace(",", ".")
    })

    st.dataframe(styler, use_container_width=True, hide_index=True)

with tab2:
    st.write("### 💰 Análisis Individual")
    
    user_names = df_standings["Usuario"].tolist()
    default_idx = 0
    if clean_user_id:
        try:
            matching_row = df_standings[df_standings["ID User"] == int(clean_user_id)]
            if not matching_row.empty:
                default_idx = df_standings.index.get_loc(matching_row.index[0])
        except ValueError:
            pass

    selected_user = st.selectbox("Selecciona un mánager para ver sus métricas:", user_names, index=default_idx)
    
    user_row = df_standings[df_standings["Usuario"] == selected_user].iloc[0]
    
    val_team = user_row["Valor Equipo (€)"]
    bal_team = user_row["Dinero en Caja (€)"]
    val_total = user_row["Valor Total (€)"]
    max_bid = user_row["Puja Máxima (€)"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Dinero en Caja", f"{bal_team:,.0f} €".replace(",", "."))
    col2.metric("📊 Valor de Plantilla", f"{val_team:,.0f} €".replace(",", "."))
    col3.metric("🏆 Valor Total", f"{val_total:,.0f} €".replace(",", "."))
    col4.metric(f"🔥 Puja Máx. ({max_bid_pct:.0f}%)", f"{max_bid:,.0f} €".replace(",", "."))

# --- INSPECTOR DE DATOS CRUDOS DE LA API ---
with st.expander("🛠️ Ver datos sin procesar de la API (para diagnóstico)"):
    st.write("Estructura devuelta por Biwenger para el primer mánager consultado:")
    if detailed_users:
        st.json(detailed_users[0])
