import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Biwenger Financial Monitor", page_icon="⚽", layout="wide")

st.title("⚽ Monitor Financiero Biwenger")

# --- SIDEBAR: Credenciales y Ajustes ---
st.sidebar.header("🔑 Credenciales de Biwenger")
token = st.sidebar.text_input("Bearer Token", type="password", help="Pega el token sin 'Bearer ' delante")
league_id = st.sidebar.text_input("League ID", help="ID de la liga")
user_id = st.sidebar.text_input("User ID (Opcional)", help="ID de tu mánager (dejar en blanco si da error)")

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

if st.sidebar.button("🔄 Recargar datos (Limpiar Caché)"):
    st.cache_data.clear()
    st.rerun()

if not token or not league_id:
    st.info("👈 Introduce tu **Bearer Token** y el **League ID** en la barra lateral.")
    st.stop()

# Limpieza de valores
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

@st.cache_data(ttl=15)
def fetch_api_data(t_val, l_val, u_val):
    results = {"status": 0, "league": None, "board": [], "raw_err": ""}
    
    # 1. Petición a la Liga
    try:
        r = requests.get("https://biwenger.as.com/api/v2/league", headers=headers, timeout=8)
        results["status"] = r.status_code
        if r.status_code == 200:
            results["league"] = r.json().get("data", {})
        else:
            results["raw_err"] = r.text
            return results
    except Exception as e:
        results["raw_err"] = str(e)
        return results

    # 2. Petición al Tablón (Historial de fichajes/ventas)
    try:
        rb = requests.get("https://biwenger.as.com/api/v2/league/board?limit=1000", headers=headers, timeout=8)
        if rb.status_code == 200:
            results["board"] = rb.json().get("data", [])
    except Exception:
        pass

    return results

api_data = fetch_api_data(clean_token, clean_league_id, clean_user_id)
status_code = api_data["status"]
league_info = api_data["league"]
board_events = api_data["board"]

api_success = False
parsed_users = []

if status_code == 200 and isinstance(league_info, dict):
    users_list = league_info.get("users", []) or league_info.get("standings", [])
    if users_list:
        api_success = True

# --- GESTIÓN DE ERRORES DE API Y MODOS DE TRABAJO ---
if not api_success:
    st.error(f"⚠️ Error al conectar con Biwenger (Código HTTP: {status_code})")
    
    with st.expander("🔍 Ver detalle del error enviado por Biwenger"):
        st.code(api_data["raw_err"] if api_data["raw_err"] else "Sin respuesta del servidor.")
    
    st.warning(
        "👉 **Soluciones rápidas:**\n"
        "1. El **Bearer Token** ha caducado. Abre la web de Biwenger (F12 -> Red/Network) y copia uno nuevo.\n"
        "2. Si has puesto un **User ID**, prueba a **dejarlo completamente en blanco** en la barra lateral.\n"
        "3. Comprueba que el **League ID** (`310321`) pertenezca a la cuenta con la que iniciaste sesión."
    )
    
    st.write("---")
    st.subheader("🧪 Modo Manual de Respaldo")
    st.info("Puedes usar esta tabla para consultar o editar valores mientras actualizas las credenciales:")

    records = [
        {"Icono": "https://biwenger.as.com/assets/images/user.png", "Usuario": "Mánager 1", "Valor Equipo (€)": 15000000.0},
        {"Icono": "https://biwenger.as.com/assets/images/user.png", "Usuario": "Mánager 2", "Valor Equipo (€)": 18000000.0},
    ]
    df_base = pd.DataFrame(records)
else:
    st.subheader(f"🏆 Liga: {league_info.get('name', 'Novedades de la Liga')}")
    
    users_list = league_info.get("users", []) or league_info.get("standings", [])
    user_stats = {}
    
    for u in users_list:
        if isinstance(u, dict):
            uid = u.get("id") or (u.get("user", {}).get("id") if isinstance(u.get("user"), dict) else None)
            uname = u.get("name") or (u.get("user", {}).get("name") if isinstance(u.get("user"), dict) else f"Mánager {uid}")
            tv = float(u.get("teamValue") or u.get("value") or 0.0)
            
            icon_raw = u.get("icon") or u.get("avatar") or (u.get("user", {}).get("icon") if isinstance(u.get("user"), dict) else None)
            if icon_raw:
                icon_str = str(icon_raw)
                icon_url = icon_str if icon_str.startswith("http") else f"https://biwenger.as.com/assets/images/{icon_str}"
            else:
                icon_url = "https://biwenger.as.com/assets/images/user.png"

            if uid:
                user_stats[int(uid)] = {
                    "name": str(uname),
                    "icon": icon_url,
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

                if any(t in ev_type for t in ["transfer", "market", "clause", "purchase", "sale", "assignment"]):
                    if seller_id in user_stats:
                        user_stats[seller_id]["gained"] += amount
                    if buyer_id in user_stats:
                        user_stats[buyer_id]["spent"] += amount
                elif any(t in ev_type for t in ["bonus", "reward", "prize", "admin"]):
                    if buyer_id in user_stats:
                        user_stats[buyer_id]["gained"] += amount

    records = []
    for uid, info in user_stats.items():
        squad_val = info["squad_val"]
        if info["real_balance"] is not None:
            cash = float(info["real_balance"])
        else:
            cash = (initial_budget - info["spent"]) + info["gained"]

        records.append({
            "Icono": info["icon"],
            "Usuario": info["name"],
            "Valor Equipo (€)": squad_val,
            "Dinero en Caja (€)": cash,
            "Valor Total (€)": squad_val + cash,
            "Puja Máxima (€)": cash + ((max_bid_pct / 100.0) * squad_val)
        })
    
    df_base = pd.DataFrame(records)

# --- CÁLCULOS Y RENDERIZADO DE TABLA ---
if api_success:
    df_display = df_base.copy()
    for col in ["Valor Equipo (€)", "Dinero en Caja (€)", "Valor Total (€)", "Puja Máxima (€)"]:
        df_display[col] = df_display[col].apply(lambda x: f"{x:,.0f} €".replace(",", "."))

    st.write("### 👥 Auditoría Automática de Finanzas")
    st.dataframe(
        df_display,
        column_config={
            "Icono": st.column_config.ImageColumn("Icono", help="Avatar del mánager"),
            "Usuario": st.column_config.TextColumn("Usuario"),
            "Valor Equipo (€)": st.column_config.TextColumn("Valor Equipo (€)"),
            "Dinero en Caja (€)": st.column_config.TextColumn("Dinero en Caja (€)"),
            "Valor Total (€)": st.column_config.TextColumn("Valor Total (€)"),
            "Puja Máxima (€)": st.column_config.TextColumn("Puja Máxima (€)")
        },
        use_container_width=True,
        hide_index=True
    )
else:
    # Tabla editable para el modo manual
    df_edited = st.data_editor(
        df_base,
        column_config={
            "Icono": st.column_config.ImageColumn("Icono"),
            "Usuario": st.column_config.TextColumn("Usuario"),
            "Valor Equipo (€)": st.column_config.NumberColumn("Valor Equipo (€)", min_value=0, step=250000, format="%d €")
        },
        hide_index=True,
        use_container_width=True
    )
    df_edited["Dinero en Caja (€)"] = initial_budget - df_edited["Valor Equipo (€)"]
    df_edited["Valor Total (€)"] = df_edited["Dinero en Caja (€)"] + df_edited["Valor Equipo (€)"]
    df_edited["Puja Máxima (€)"] = df_edited["Dinero en Caja (€)"] + ((max_bid_pct / 100.0) * df_edited["Valor Equipo (€)"])
    
    for col in ["Valor Equipo (€)", "Dinero en Caja (€)", "Valor Total (€)", "Puja Máxima (€)"]:
        df_edited[col] = df_edited[col].apply(lambda x: f"{x:,.0f} €".replace(",", "."))

    st.write("#### 📊 Resultados Recalculados")
    st.dataframe(df_edited, use_container_width=True, hide_index=True)
