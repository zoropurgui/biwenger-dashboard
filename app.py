import streamlit as st
import pandas as pd
import requests

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
    help="Reparto inicial: 40M - Valor de Plantilla Inicial"
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
    
    # 1. Obtener lista de usuarios de la liga
    url_league = "https://biwenger.as.com/api/v2/league?fields=*,users(*,team),standings(*,user,team)"
    try:
        resp = requests.get(url_league, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
        else:
            errors.append(f"HTTP {resp.status_code} en /league")
    except Exception as e:
        errors.append(f"Error en /league: {str(e)}")

    users_list = data.get("users", []) or data.get("standings", [])
    
    # 2. Obtener datos individuales de mánagers (Valor de Plantilla)
    detailed_users = []
    for u in users_list:
        if not isinstance(u, dict):
            continue
        uid = u.get("id") or (u.get("user", {}).get("id") if isinstance(u.get("user"), dict) else None)
        u_info = dict(u)
        
        if uid:
            url_user = f"https://biwenger.as.com/api/v2/user/{uid}?fields=*,team"
            try:
                resp_u = requests.get(url_user, headers=headers, timeout=5)
                if resp_u.status_code == 200:
                    u_data = resp_u.json().get("data", {})
                    u_info["detailed_team"] = u_data.get("team", {})
                    if "balance" in u_data:
                        u_info["real_balance"] = u_data.get("balance")
            except Exception:
                pass
                
        detailed_users.append(u_info)
        
    data["detailed_users"] = detailed_users

    # 3. Descargar el Tablón de Noticias/Movimientos
    url_board = "https://biwenger.as.com/api/v2/league/board?limit=300"
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

# --- AUDITORÍA DE MOVIMIENTOS DEL TABLÓN ---
# Calculamos las ventas, compras y abonos de cada mánager a partir del tablón
user_moves = {u.get("id"): {"spent": 0, "gained": 0} for u in detailed_users if u.get("id")}

if isinstance(board_events, list):
    for event in board_events:
        if not isinstance(event, dict):
            continue
        
        ev_type = event.get("type")
        content = event.get("content", {})
        
        # 1. Compras/Ventas de jugadores
        if ev_type in ["transfer", "market", "clause"]:
            amount = event.get("amount") or content.get("amount") or event.get("price") or 0
            
            # Quién recibe el dinero (Vendedor)
            seller_id = event.get("from") or content.get("from")
            if isinstance(seller_id, dict):
                seller_id = seller_id.get("id")
            if seller_id in user_moves:
                user_moves[seller_id]["gained"] += amount

            # Quién paga el dinero (Comprador)
            buyer_id = event.get("to") or content.get("to")
            if isinstance(buyer_id, dict):
                buyer_id = buyer_id.get("id")
            if buyer_id in user_moves:
                user_moves[buyer_id]["spent"] += amount

        # 2. Premios y Abonos del Administrador
        elif ev_type in ["bonus", "admin_bonus"]:
            amount = event.get("amount") or content.get("amount") or 0
            target_user = event.get("user") or content.get("user")
            if isinstance(target_user, dict):
                target_user = target_user.get("id")
            if target_user in user_moves:
                user_moves[target_user]["gained"] += amount

def parse_entry(entry):
    uid = entry.get("id")
    if not uid and isinstance(entry.get("user"), dict):
        uid = entry["user"].get("id")

    user_obj = entry.get("user") if isinstance(entry.get("user"), dict) else {}
    team_obj = entry.get("detailed_team") or entry.get("team") or {}

    name = (
        entry.get("name") or 
        entry.get("username") or 
        user_obj.get("name") or 
        user_obj.get("username") or 
        f"Mánager {uid or ''}"
    )

    points = entry.get("points") if entry.get("points") is not None else user_obj.get("points", 0)

    # Valor de Plantilla Actual
    val = (
        team_obj.get("value") or 
        team_obj.get("teamValue") or 
        entry.get("teamValue") or 
        0
    )

    # Cálculo de Dinero en Caja:
    # Si tenemos el saldo real (nuestro propio usuario), lo usamos directo.
    # Si es un rival, calculamos: (Presupuesto Total - Valor Equipo Actual) + Net Movimientos del Tablón
    if "real_balance" in entry:
        bal = entry["real_balance"]
    else:
        moves = user_moves.get(uid, {"spent": 0, "gained": 0})
        net_board = moves["gained"] - moves["spent"]
        # Estimación: Caja Inicial (40M - Valor Plantilla) + Movimientos Tablón
        bal = (initial_budget - val) + net_board

    return {
        "ID User": uid,
        "Usuario": str(name),
        "Puntos": int(points or 0),
        "Valor Equipo (€)": float(val or 0),
        "Dinero en Caja (€)": float(bal or 0)
    }

rivals_list = [parse_entry(e) for e in detailed_users]
df_standings = pd.DataFrame(rivals_list)

df_standings["Posición"] = range(1, len(df_standings) + 1)
df_standings["Valor Total (€)"] = df_standings["Valor Equipo (€)"] + df_standings["Dinero en Caja (€)"]
df_standings["Puja Máxima (€)"] = df_standings["Dinero en Caja (€)"] + (0.25 * df_standings["Valor Equipo (€)"])

tab1, tab2 = st.tabs(["📊 Clasificación y VM de Rivales", "👤 Mi Equipo"])

with tab1:
    st.write("### 👥 Clasificación y Estado Financiero Estimado")

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

# --- INSPECTOR DE DATOS CRUDOS DEL TABLÓN ---
with st.expander("🛠️ Ver eventos sin procesar del Tablón (para diagnóstico)"):
    st.write("Últimos movimientos registrados en la liga:")
    st.json(board_events[:10] if board_events else [])
