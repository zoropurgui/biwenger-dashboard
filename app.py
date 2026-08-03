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

st.sidebar.header("⚙️ Configuración de Liga")
initial_budget = st.sidebar.number_input(
    "Presupuesto Total Inicial (€)", 
    value=40000000, 
    step=1000000, 
    help="Reparto inicial del 31 de julio: 40M (Plantilla + Caja)"
)

if not token or not league_id:
    st.info("👈 Introduce tu **Bearer Token** y **League ID** en la barra lateral para cargar la liga.")
    st.stop()

clean_token = token.strip()
if clean_token.lower().startswith("bearer "):
    clean_token = clean_token[7:].strip()

clean_league_id = str(league_id).strip()
clean_user_id = str(user_id).strip() if user_id else ""

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
    
    # 1. Obtener la liga global
    url_league = "https://biwenger.as.com/api/v2/league?fields=*,users(*,team),standings(*,user,team)"
    try:
        resp = requests.get(url_league, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
        else:
            # Reintento simple si falla el selector complejo
            resp_s = requests.get("https://biwenger.as.com/api/v2/league", headers=headers, timeout=10)
            if resp_s.status_code == 200:
                data = resp_s.json().get("data", {})
            else:
                errors.append(f"HTTP {resp.status_code} en /league")
    except Exception as e:
        errors.append(f"Error en /league: {str(e)}")

    users_list = data.get("users", []) or data.get("standings", [])
    
    # 2. Consultar perfil de cada mánager solicitando explícitamente el objeto 'team'
    detailed_users = []
    for u in users_list:
        if not isinstance(u, dict):
            continue
        uid = u.get("id") or (u.get("user", {}).get("id") if isinstance(u.get("user"), dict) else None)
        u_info = dict(u)
        
        # Conservar el saldo si venía en la respuesta global (p. ej. tu usuario)
        if "balance" in u and u["balance"] is not None:
            u_info["real_balance"] = u["balance"]

        if uid:
            # Solicitamos los campos extendidos con ?fields=*,team
            url_user = f"https://biwenger.as.com/api/v2/user/{uid}?fields=*,team"
            try:
                time.sleep(0.15)  # Evita saturar peticiones
                resp_u = requests.get(url_user, headers=headers, timeout=5)
                if resp_u.status_code == 200:
                    u_data = resp_u.json().get("data", {})
                    u_info["detailed_user_data"] = u_data
                    if "balance" in u_data and u_data["balance"] is not None:
                        u_info["real_balance"] = u_data.get("balance")
                else:
                    errors.append(f"HTTP {resp_u.status_code} al consultar mánager ID {uid}")
            except Exception as e:
                errors.append(f"Error red mánager ID {uid}: {str(e)}")
                
        detailed_users.append(u_info)
        
    data["detailed_users"] = detailed_users

    # 3. Descargar el Tablón de Noticias para calcular movimientos
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

if error_logs:
    with st.expander("⚠️ Avisos de red o respuestas de la API"):
        for err in error_logs:
            st.write(f"- `{err}`")

# --- AUDITORÍA DE MOVIMIENTOS Y FICHAJES ---
user_moves = {}
for u in detailed_users:
    uid = u.get("id") or (u.get("user", {}).get("id") if isinstance(u.get("user"), dict) else None)
    if uid:
        try:
            user_moves[int(uid)] = {"spent": 0, "gained": 0}
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

def get_team_value(entry):
    u_data = entry.get("detailed_user_data", {})
    
    # 1. Búsqueda de clave directa en u_data o entry
    for key in ["teamValue", "team_value", "value"]:
        val = u_data.get(key) or entry.get(key)
        if isinstance(val, (int, float)) and val > 0:
            return float(val)

    # 2. Análisis del objeto o lista 'team'
    team_obj = u_data.get("team") or entry.get("team")
    
    if isinstance(team_obj, dict):
        for key in ["value", "teamValue", "price"]:
            val = team_obj.get(key)
            if isinstance(val, (int, float)) and val > 0:
                return float(val)
        if "players" in team_obj and isinstance(team_obj["players"], list):
            team_obj = team_obj["players"]

    if isinstance(team_obj, list):
        total_val = 0.0
        for p in team_obj:
            if isinstance(p, dict):
                p_val = p.get("price") or p.get("value") or p.get("marketValue") or p.get("priceMarket") or 0
                try:
                    total_val += float(p_val)
                except (ValueError, TypeError):
                    pass
        if total_val > 0:
            return total_val

    return 0.0

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

    # --- VALOR DE PLANTILLA ---
    val = get_team_value(entry)

    # --- DINERO EN CAJA ---
    if "real_balance" in entry and entry["real_balance"] is not None:
        bal = float(entry["real_balance"])
    elif "balance" in u_data and u_data["balance"] is not None:
        bal = float(u_data["balance"])
    else:
        moves = user_moves.get(uid, {"spent": 0, "gained": 0})
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
df_standings["Puja Máxima (€)"] = df_standings["Dinero en Caja (€)"] + (0.25 * df_standings["Valor Equipo (€)"])

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
    col4.metric("🔥 Puja Máx. Estimada", f"{max_bid:,.0f} €".replace(",", "."))

# --- INSPECTOR DE DATOS CRUDOS ---
with st.expander("🛠️ Ver datos sin procesar de la API (para diagnóstico)"):
    st.write("Estructura devuelta por Biwenger para el primer mánager consultado:")
    if detailed_users:
        st.json(detailed_users[0].get("detailed_user_data", {}))
