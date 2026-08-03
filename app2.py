import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Biwenger Financial Monitor", page_icon="⚽", layout="wide")

st.title("⚽ Monitor Financiero Biwenger - Nueva Liga")

# --- SIDEBAR: Credenciales y Ajustes ---
st.sidebar.header("🔑 Credenciales de Biwenger")
token = st.sidebar.text_input("Bearer Token", type="password", help="Tu token de autorización de Biwenger")
league_id = st.sidebar.text_input("League ID", help="ID numérico de la nueva liga")
user_id = st.sidebar.text_input("User ID (Opcional)", help="Tu ID de usuario")

st.sidebar.header("⚙️ Reglas de la Liga")
initial_budget = st.sidebar.number_input(
    "Presupuesto Total Inicial (€)", 
    value=40000000, 
    step=1000000, 
    help="Reparto inicial del primer día: 40M (Plantilla + Caja)"
)

max_bid_pct = st.sidebar.slider(
    "Crédito sobre Valor de Equipo (%)", 
    min_value=0.0, 
    max_value=100.0, 
    value=25.0, 
    step=1.0,
    help="Regla oficial de Biwenger: Puja Máx = Caja + (25% * Valor de Plantilla)"
)

if not token or not league_id:
    st.info("👈 Cuando empiece la nueva liga el viernes, introduce aquí tu **Bearer Token** y **League ID**.")
    st.stop()

clean_token = token.strip().replace("Bearer ", "").replace("bearer ", "")
clean_league_id = str(league_id).strip()
clean_user_id = str(user_id).strip() if user_id else ""

headers = {
    "Authorization": f"Bearer {clean_token}",
    "X-League": clean_league_id,
    "Accept": "application/json, text/plain, */*",
    "X-App-Version": "2.0.0",
    "X-Lang": "es",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}
if clean_user_id:
    headers["X-User"] = clean_user_id

@st.cache_data(ttl=30)
def fetch_league_and_board():
    data = {}
    errors = []

    # 1. Obtener la lista de participantes
    try:
        r = requests.get("https://biwenger.as.com/api/v2/league", headers=headers, timeout=10)
        if r.status_code == 200:
            data["league"] = r.json().get("data", {})
        else:
            errors.append(f"HTTP {r.status_code} en /league")
    except Exception as e:
        errors.append(f"Error en /league: {str(e)}")

    # 2. Descargar todos los eventos del Tablón (desde el primer día)
    try:
        rb = requests.get("https://biwenger.as.com/api/v2/league/board?limit=1000", headers=headers, timeout=10)
        if rb.status_code == 200:
            data["board"] = rb.json().get("data", [])
        else:
            errors.append(f"HTTP {rb.status_code} en /board")
    except Exception as e:
        errors.append(f"Error en /board: {str(e)}")

    return data, errors

data, errors = fetch_league_and_board()
league_info = data.get("league", {})
users_list = league_info.get("users", []) or league_info.get("standings", [])
board_events = data.get("board", [])

if not users_list:
    st.error("❌ No se pudieron obtener los datos de la liga.")
    if errors:
        st.warning("🔍 Detalle de errores:")
        for err in errors:
            st.write(f"- `{err}`")
    st.stop()

st.subheader(f"🏆 Liga: {league_info.get('name', 'Novedades de la Liga')}")

# --- AUDITORÍA DE EVENTOS DESDE EL DÍA 1 ---
user_stats = {}
for u in users_list:
    if isinstance(u, dict):
        uid = u.get("id") or (u.get("user", {}).get("id") if isinstance(u.get("user"), dict) else None)
        uname = u.get("name") or (u.get("user", {}).get("name") if isinstance(u.get("user"), dict) else f"Mánager {uid}")
        if uid:
            try:
                user_stats[int(uid)] = {
                    "name": str(uname),
                    "spent": 0.0,
                    "gained": 0.0,
                    "squad_val": 0.0,
                    "real_balance": u.get("balance")
                }
            except (ValueError, TypeError):
                pass

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
            
            # Obtención del importe del movimiento o valor del jugador
            raw_amount = item.get("amount") or item.get("price") or item.get("value") or event.get("amount") or 0
            try:
                amount = float(raw_amount)
            except (ValueError, TypeError):
                amount = 0.0

            # Vendedor / Remitente
            seller = item.get("from") or event.get("from")
            seller_id = seller.get("id") if isinstance(seller, dict) else seller
            try:
                seller_id = int(seller_id) if seller_id is not None else None
            except (ValueError, TypeError):
                seller_id = None

            # Comprador / Destinatario
            buyer = item.get("to") or item.get("user") or event.get("to") or event.get("user")
            buyer_id = buyer.get("id") if isinstance(buyer, dict) else buyer
            try:
                buyer_id = int(buyer_id) if buyer_id is not None else None
            except (ValueError, TypeError):
                buyer_id = None

            # Fichajes, compras, ventas, reparte inicial y cláusulas
            if any(t in ev_type for t in ["transfer", "market", "clause", "purchase", "sale", "assignment"]):
                if seller_id in user_stats:
                    user_stats[seller_id]["gained"] += amount
                    user_stats[seller_id]["squad_val"] = max(0.0, user_stats[seller_id]["squad_val"] - amount)
                        
                if buyer_id in user_stats:
                    user_stats[buyer_id]["spent"] += amount
                    user_stats[buyer_id]["squad_val"] += amount

            # Abonos y premios otorgados por el Administrador
            elif any(t in ev_type for t in ["bonus", "reward", "prize", "admin"]):
                if buyer_id in user_stats:
                    user_stats[buyer_id]["gained"] += amount

# --- CONSTRUCCIÓN DE LA TABLA FINANCIERA ---
records = []
for uid, info in user_stats.items():
    squad_val = info["squad_val"]
    
    # Cálculo del Dinero en Caja
    if info["real_balance"] is not None:
        cash = float(info["real_balance"])
    else:
        cash = (initial_budget - info["spent"]) + info["gained"]

    total_val = squad_val + cash
    max_bid = cash + ((max_bid_pct / 100.0) * squad_val)

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

st.write("### 👥 Auditoría de Finanzas y Pujas Máximas")

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

with st.expander("🛠️ Ver eventos procesados del Tablón (Diagnóstico)"):
    st.write(f"Se han analizado **{len(board_events)}** eventos del tablón de la liga.")
    st.json(user_stats)
