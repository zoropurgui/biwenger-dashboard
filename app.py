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

st.sidebar.header("⚙️ Configuración Financiera")
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
def fetch_biwenger_data(tok, l_id, u_id):
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

    # 1. Obtener liga y lista de usuarios
    url_league = "https://biwenger.as.com/api/v2/league"
    try:
        resp = requests.get(url_league, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
        else:
            errors.append(f"HTTP {resp.status_code} en /league")
    except Exception as e:
        errors.append(f"Error en /league: {str(e)}")

    # 2. Descargar el Tablón de Noticias/Movimientos (hasta 1000 eventos)
    url_board = "https://biwenger.as.com/api/v2/league/board?limit=1000"
    try:
        resp_b = requests.get(url_board, headers=headers, timeout=10)
        if resp_b.status_code == 200:
            data["board"] = resp_b.json().get("data", [])
        else:
            errors.append(f"HTTP {resp_b.status_code} en /board")
    except Exception as e:
        errors.append(f"Error en /board: {str(e)}")

    return data, errors

data, error_logs = fetch_biwenger_data(clean_token, clean_league_id, clean_user_id)
users_list = data.get("users", []) or data.get("standings", [])
board_events = data.get("board", [])

if not users_list:
    st.error("❌ No se pudieron obtener los usuarios de la liga.")
    if error_logs:
        st.warning("🔍 **Informe de diagnóstico:**")
        for err in error_logs:
            st.write(f"- `{err}`")
    st.stop()

league_name = data.get('name', 'Mi Liga')
st.subheader(f"🏆 Liga: {league_name}")

# --- AUDITORÍA COMPLETA DESDE EL TABLÓN ---
user_finances = {}
for u in users_list:
    if isinstance(u, dict):
        uid = u.get("id") or (u.get("user", {}).get("id") if isinstance(u.get("user"), dict) else None)
        name = u.get("name") or (u.get("user", {}).get("name") if isinstance(u.get("user"), dict) else f"Mánager {uid}")
        if uid:
            try:
                uid_int = int(uid)
                user_finances[uid_int] = {
                    "name": str(name),
                    "spent": 0.0,
                    "gained": 0.0,
                    "squad": {}, # player_id -> price
                    "real_balance": u.get("balance")
                }
            except (ValueError, TypeError):
                pass

# Procesar eventos del tablón
if isinstance(board_events, list):
    for event in board_events:
        if not isinstance(event, dict):
            continue
        
        ev_type = str(event.get("type", "")).lower()
        content = event.get("content")
        items = content if isinstance(content, list) else ([content] if isinstance(content, dict) else [event])
            
        for item in items:
            if not isinstance(item, dict):
                continue
            
            raw_amount = item.get("amount") or item.get("price") or item.get("value") or event.get("amount") or 0
            try:
                amount = float(raw_amount)
            except (ValueError, TypeError):
                amount = 0.0

            seller = item.get("from") or event.get("from")
            seller_id = seller.get("id") if isinstance(seller, dict) else seller
            try:
                seller_id = int(seller_id) if seller_id is not None else None
            except (ValueError, TypeError):
                seller_id = None

            buyer = item.get("to") or item.get("user") or event.get("to") or event.get("user")
            buyer_id = buyer.get("id") if isinstance(buyer, dict) else buyer
            try:
                buyer_id = int(buyer_id) if buyer_id is not None else None
            except (ValueError, TypeError):
                buyer_id = None

            player_obj = item.get("player") or item.get("players")
            player_id = None
            if isinstance(player_obj, dict):
                player_id = player_obj.get("id")
                if amount == 0:
                    try:
                        amount = float(player_obj.get("price") or player_obj.get("value") or 0)
                    except (ValueError, TypeError):
                        pass
            elif isinstance(player_obj, (int, str)):
                player_id = player_obj

            # 1. Compras, Ventas, Fichajes y Reparto Inicial
            if any(t in ev_type for t in ["transfer", "market", "clause", "purchase", "sale", "assignment", "lineup"]):
                if seller_id in user_finances:
                    user_finances[seller_id]["gained"] += amount
                    if player_id and player_id in user_finances[seller_id]["squad"]:
                        del user_finances[seller_id]["squad"][player_id]
                        
                if buyer_id in user_finances:
                    user_finances[buyer_id]["spent"] += amount
                    if player_id:
                        user_finances[buyer_id]["squad"][player_id] = amount

            # 2. Premios y Abonos del Administrador
            elif any(t in ev_type for t in ["bonus", "reward", "prize", "admin"]):
                if buyer_id in user_finances:
                    user_finances[buyer_id]["gained"] += amount

# --- CONSTRUCCIÓN DE LA TABLA ---
records = []
for uid, info in user_finances.items():
    squad_val = sum(info["squad"].values())
    
    # Si no se desglosaron los IDs de jugadores pero hubo repartos/compras, usamos el total gastado
    if squad_val == 0 and info["spent"] > 0:
        squad_val = info["spent"]

    # Dinero en Caja:
    # Si Biwenger nos da el saldo oficial (tu usuario), lo usamos directo.
    # Para rivales: (40M Iniciales - Gastos) + Ventas y Premios
    if info["real_balance"] is not None:
        cash = float(info["real_balance"])
    else:
        cash = (initial_budget - info["spent"]) + info["gained"]

    total_val = squad_val + cash
    
    # Puja Máxima = Dinero en Caja + 25% del Valor del Equipo (0.25 * Valor Equipo)
    max_bid = cash + (0.25 * squad_val)

    records.append({
        "ID User": uid,
        "Usuario": info["name"],
        "Valor Equipo (€)": squad_val,
        "Dinero en Caja (€)": cash,
        "Valor Total (€)": total_val,
        "Puja Máxima (€)": max_bid
    })

df_standings = pd.DataFrame(records)
df_standings["Posición"] = range(1, len(df_standings) + 1)

tab1, tab2 = st.tabs(["📊 Clasificación y Estado Financiero", "👤 Mi Equipo"])

with tab1:
    st.write("### 👥 Estado Financiero Calculado desde el Tablón de la Liga")

    cols_order = [
        "Posición",
        "Usuario",
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
    selected_user = st.selectbox("Selecciona un mánager para ver sus métricas:", user_names)
    user_row = df_standings[df_standings["Usuario"] == selected_user].iloc[0]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Dinero en Caja", f"{user_row['Dinero en Caja (€)']:,.0f} €".replace(",", "."))
    col2.metric("📊 Valor de Plantilla", f"{user_row['Valor Equipo (€)']:,.0f} €".replace(",", "."))
    col3.metric("🏆 Valor Total", f"{user_row['Valor Total (€)']:,.0f} €".replace(",", "."))
    col4.metric("🔥 Puja Máx. (Caja + 25% VM)", f"{user_row['Puja Máxima (€)']:,.0f} €".replace(",", "."))

# --- DIAGNÓSTICO DEL TABLÓN ---
with st.expander("🛠️ Ver contabilidad extraída del Tablón por Mánager (para verificación)"):
    st.json(user_finances)
