import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Biwenger Financial Monitor", page_icon="⚽", layout="wide")

st.title("⚽ Monitor Financiero Biwenger")

# --- SIDEBAR: Credenciales y Ajustes ---
st.sidebar.header("🔑 Credenciales de Biwenger")
token = st.sidebar.text_input("Bearer Token", type="password", help="Pega el token sin 'Bearer ' delante")
league_id = st.sidebar.text_input("League ID", help="ID de la liga")
user_id = st.sidebar.text_input("User ID (Obligatorio)", help="ID de tu mánager")

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

if not token or not league_id or not user_id:
    st.info("👈 Introduce tu **Bearer Token**, **League ID** y **User ID** en la barra lateral para conectar.")
    st.stop()

# Limpieza de valores
clean_token = token.strip()
if clean_token.lower().startswith("bearer "):
    clean_token = clean_token[7:].strip()

clean_league_id = str(league_id).strip()
clean_user_id = str(user_id).strip()

headers = {
    "Authorization": f"Bearer {clean_token}",
    "X-League": clean_league_id,
    "X-User": clean_user_id,
    "Accept": "application/json, text/plain, */*",
    "X-App-Version": "2.0.0",
    "X-Lang": "es",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# --- RESPALDO CON DATOS REALES DEL DÍA 1 ---
DAY_ONE_FALLBACK = {
    "athletik81": 21600000.0,
    "ring014": 21580000.0,
    "tubu": 21570000.0,
    "marroba": 21560000.0,
    "zhukkov": 21560000.0,
    "nitwolf": 21550000.0,
    "yoqsetio xdxd": 21550000.0,
    "nistalikus": 21550000.0,
    "moltisanti": 21540000.0,
    "gran gravessen": 21540000.0,
    "zoropurgui": 21530000.0,
    "_caesar_": 21510000.0,
    "nitrorx": 21490000.0
}

@st.cache_data(ttl=10)
def fetch_api_data(t_val, l_val, u_val):
    results = {"status": 0, "league": None, "standings": [], "board": [], "raw_err": ""}
    
    # 1. Petición a la liga
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

    # 2. Petición a la clasificación con límite extendido
    try:
        rs = requests.get("https://biwenger.as.com/api/v2/league/standings?offset=0&limit=100", headers=headers, timeout=8)
        if rs.status_code == 200:
            results["standings"] = rs.json().get("data", {}).get("standings", [])
    except Exception:
        pass

    # 3. Descarga del tablón
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
standings_data = api_data["standings"]
board_events = api_data["board"]

api_success = status_code == 200 and isinstance(league_info, dict)

if not api_success:
    st.error(f"⚠️ Error al conectar con Biwenger (Código HTTP: {status_code})")
    with st.expander("🔍 Ver detalle del error enviado por Biwenger"):
        st.code(api_data["raw_err"] if api_data["raw_err"] else "Sin respuesta del servidor.")
    st.warning("👉 Verifica que el **User ID** pertenezca a la cuenta del **Bearer Token** y a la liga.")
else:
    st.subheader(f"🏆 Liga: {league_info.get('name', 'FC Biwenger Primera División')}")
    
    raw_users = league_info.get("users", []) or []
    if isinstance(league_info.get("standings"), list):
        raw_users.extend(league_info["standings"])
    if isinstance(standings_data, list):
        raw_users.extend(standings_data)

    user_stats = {}
    
    for u in raw_users:
        if not isinstance(u, dict):
            continue
        
        uid = u.get("id")
        u_dict = u.get("user") if isinstance(u.get("user"), dict) else {}
        if not uid:
            uid = u_dict.get("id")
        if not uid:
            continue
            
        uid = int(uid)
        uname = u.get("name") or u_dict.get("name") or f"Mánager {uid}"
        
        # Intentar obtener valor desde la API
        tv = 0.0
        for key in ["teamValue", "value", "team_value", "squadValue"]:
            if u.get(key) is not None:
                try:
                    tv = float(u[key])
                    if tv > 0:
                        break
                except (ValueError, TypeError):
                    pass
            if u_dict.get(key) is not None:
                try:
                    tv = float(u_dict[key])
                    if tv > 0:
                        break
                except (ValueError, TypeError):
                    pass

        # Aplicar datos reales de la captura si la API devuelve 0
        if tv == 0.0:
            clean_name = str(uname).strip().lower()
            tv = DAY_ONE_FALLBACK.get(clean_name, 0.0)

        # Avatar
        icon_raw = u.get("icon") or u.get("avatar") or u_dict.get("icon") or u_dict.get("avatar")
        if icon_raw:
            icon_str = str(icon_raw)
            icon_url = icon_str if icon_str.startswith("http") else f"https://biwenger.as.com/assets/images/{icon_str}"
        else:
            icon_url = "https://biwenger.as.com/assets/images/user.png"

        real_bal = u.get("balance") or u_dict.get("balance")

        if uid not in user_stats:
            user_stats[uid] = {
                "name": str(uname),
                "icon": icon_url,
                "spent": 0.0,
                "gained": 0.0,
                "squad_val": tv,
                "real_balance": real_bal
            }
        else:
            if tv > 0:
                user_stats[uid]["squad_val"] = tv
            if real_bal is not None:
                user_stats[uid]["real_balance"] = real_bal
            if icon_url != "https://biwenger.as.com/assets/images/user.png":
                user_stats[uid]["icon"] = icon_url

    # Procesamiento del Tablón
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
        
        # Dinero en Caja = 40M - Valor de Plantilla Inicial - Gastos + Ingresos
        if info["real_balance"] is not None:
            cash = float(info["real_balance"])
        else:
            cash = (initial_budget - squad_val - info["spent"]) + info["gained"]

        total_val = squad_val + cash
        max_bid = cash + ((max_bid_pct / 100.0) * squad_val)

        records.append({
            "Icono": info["icon"],
            "Usuario": info["name"],
            "Valor Equipo (€)": squad_val,
            "Dinero en Caja (€)": cash,
            "Valor Total (€)": total_val,
            "Puja Máxima (€)": max_bid
        })
    
    df_base = pd.DataFrame(records)
    
    if not df_base.empty and "Valor Equipo (€)" in df_base.columns:
        df_base = df_base.sort_values(by="Valor Equipo (€)", ascending=False)

    # Formato numérico
    for col in ["Valor Equipo (€)", "Dinero en Caja (€)", "Valor Total (€)", "Puja Máxima (€)"]:
        df_base[col] = df_base[col].apply(lambda x: f"{x:,.0f} €".replace(",", "."))

    st.write("### 👥 Auditoría Automática de Finanzas")
    st.dataframe(
        df_base,
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
