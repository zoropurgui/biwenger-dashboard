Python
import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Biwenger Financial Monitor", page_icon="⚽", layout="wide")

st.title("⚽ Monitor Financiero Biwenger - Liga Real")

# --- SIDEBAR: Credenciales y Ajustes ---
st.sidebar.header("🔑 Credenciales de Biwenger")
token = st.sidebar.text_input("Bearer Token", type="password", help="Pega el token sin 'Bearer ' delante")
league_id = st.sidebar.text_input("League ID", help="ID de la nueva liga")
user_id = st.sidebar.text_input("User ID (Opcional)")

st.sidebar.header("⚙️ Reglas Financieras")
initial_budget = st.sidebar.number_input(
    "Presupuesto Total Inicial (€)", 
    value=40000000, 
    step=1000000,
    help="Presupuesto asignado el Día 1: 40M (Plantilla + Caja)"
)

max_bid_pct = st.sidebar.slider(
    "Crédito sobre Valor de Equipo (%)", 
    min_value=0.0, 
    max_value=100.0, 
    value=25.0, 
    step=1.0,
    help="Regla oficial de Biwenger: Caja + (25% del Valor de Plantilla)"
)

if not token or not league_id:
    st.info("👈 Introduce tu **Bearer Token** y el **League ID** de la nueva liga en la barra lateral.")
    st.stop()

clean_token = token.strip()
if clean_token.lower().startswith("bearer "):
    clean_token = clean_token[7:].strip()

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
def fetch_league_data():
    data = {}
    
    # 1. Obtener lista de mánagers
    try:
        r = requests.get("https://biwenger.as.com/api/v2/league", headers=headers, timeout=8)
        if r.status_code == 200:
            data["league"] = r.json().get("data", {})
    except Exception:
        pass

    # 2. Descargar el historial completo del tablón
    try:
        rb = requests.get("https://biwenger.as.com/api/v2/league/board?limit=1000", headers=headers, timeout=8)
        if rb.status_code == 200:
            data["board"] = rb.json().get("data", [])
    except Exception:
        pass

    return data

data = fetch_league_data()
league_info = data.get("league", {})
users_list = league_info.get("users", []) or league_info.get("standings", [])
board_events = data.get("board", [])

if not users_list:
    st.error("❌ No se pudieron obtener los datos de la nueva liga.")
    st.warning("👉 Verifica que el **Bearer Token** esté activo y que el **League ID** corresponda a la nueva liga.")
    st.stop()

st.subheader(f"🏆 Liga: {league_info.get('name', 'Novedades de la Liga')}")

# --- AUDITORÍA DE CONTABILIDAD DESDE EL DÍA 1 ---
user_stats = {}
for u in users_list:
    if isinstance(u, dict):
        uid = u.get("id") or (u.get("user", {}).get("id") if isinstance(u.get("user"), dict) else None)
        uname = u.get("name") or (u.get("user", {}).get("name") if isinstance(u.get("user"), dict) else f"Mánager {uid}")
        tv = float(u.get("teamValue") or u.get("value") or 0.0)
        if uid:
            user_stats[int(uid)] = {
                "name": str(uname),
                "spent": 0.0,
                "gained": 0.0,
                "squad_val": tv,
                "real_balance": u.get("balance")
            }

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

            # Fichajes, compras, ventas y repartos iniciales
            if any(t in ev_type for t in ["transfer", "market", "clause", "purchase", "sale", "assignment"]):
                if seller_id in user_stats:
                    user_stats[seller_id]["gained"] += amount
                if buyer_id in user_stats:
                    user_stats[buyer_id]["spent"] += amount

            # Primas y premios del Administrador
            elif any(t in ev_type for t in ["bonus", "reward", "prize", "admin"]):
                if buyer_id in user_stats:
                    user_stats[buyer_id]["gained"] += amount

# --- TABLA Y CÁLCULOS ---
records = []
for uid, info in user_stats.items():
    squad_val = info["squad_val"]
    
    if info["real_balance"] is not None:
        cash = float(info["real_balance"])
    else:
        cash = (initial_budget - info["spent"]) + info["gained"]

    total_val = squad_val + cash
    max_bid = cash + ((max_bid_pct / 100.0) * squad_val)

    records.append({
        "ID": uid,
        "Usuario": info["name"],
        "Valor Equipo (€)": squad_val,
        "Dinero en Caja (€)": cash,
        "Valor Total (€)": total_val,
        "Puja Máxima (€)": max_bid
    })

df_standings = pd.DataFrame(records)

st.write("### 👥 Auditoría Automática de Finanzas")

cols_order = [
    "Usuario",
    "Valor Equipo (€)",
    "Dinero en Caja (€)",
    "Valor Total (€)",
    "Puja Máxima (€)"
]

df_final = df_standings[cols_order].copy()

styler = df_final.style.format({
    "Valor Equipo (€)": lambda x: f"{x:,.0f} €".replace(",", "."),
    "Dinero en Caja (€)": lambda x: f"{x:,.0f} €".replace(",", "."),
    "Valor Total (€)": lambda x: f"{x:,.0f} €".replace(",", "."),
    "Puja Máxima (€)": lambda x: f"{x:,.0f} €".replace(",", ".")
})

st.dataframe(styler, use_container_width=True, hide_index=True)
