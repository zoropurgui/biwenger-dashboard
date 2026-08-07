import streamlit as st
import pandas as pd
import requests
import json

st.set_page_config(page_title="Biwenger Financial Monitor", page_icon="⚽", layout="wide")

st.title("⚽ Monitor Financiero Biwenger")

# --- SIDEBAR: Credenciales y Ajustes ---
st.sidebar.header("🔑 Credenciales de Biwenger")
token = st.sidebar.text_input("Bearer Token", type="password", help="Pega el token sin 'Bearer ' delante")
league_id = st.sidebar.text_input("League ID", help="ID de la liga")
user_id = st.sidebar.text_input("User ID (Obligatorio)", help="ID de tu mánager")

st.sidebar.header("⚙️ Reglas Financieras")
initial_budget = st.sidebar.number_input("Presupuesto Total Inicial (€)", value=40000000, step=1000000)
max_bid_pct = st.sidebar.slider("Crédito sobre Valor de Equipo (%)", min_value=0.0, max_value=100.0, value=25.0, step=1.0)

if st.sidebar.button("🔄 Recargar datos (Limpiar Caché)"):
    st.cache_data.clear()
    st.rerun()

if not token or not league_id or not user_id:
    st.info("👈 Introduce tu **Bearer Token**, **League ID** y **User ID** en la barra lateral para conectar.")
    st.stop()

clean_token = token.strip()
if clean_token.lower().startswith("bearer "):
    clean_token = clean_token[7:].strip()

headers = {
    "Authorization": f"Bearer {clean_token}",
    "X-League": str(league_id).strip(),
    "X-User": str(user_id).strip(),
    "Accept": "application/json, text/plain, */*",
    "X-App-Version": "2.0.0",
    "X-Lang": "es",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

DAY_ONE_FALLBACK = {
    "athletik81": 21600000.0, "ring014": 21580000.0, "tubu": 21570000.0, 
    "marroba": 21560000.0, "zhukkov": 21560000.0, "nitwolf": 21550000.0, 
    "yoqsetio xdxd": 21550000.0, "nistalikus": 21550000.0, "moltisanti": 21540000.0, 
    "gran gravessen": 21540000.0, "zoropurgui": 21530000.0, "_caesar_": 21510000.0, 
    "nitrorx": 21490000.0
}

@st.cache_data(ttl=5)
def fetch_api_data(t_val, l_val, u_val):
    results = {
        "status": 0, "league": None, "standings": [], "board": [], "transfers": [], 
        "raw_league": "", "raw_standings": "", "raw_board": "", "raw_transfers": ""
    }
    
    # 1. Liga
    try:
        r = requests.get("https://biwenger.as.com/api/v2/league", headers=headers, timeout=8)
        results["status"] = r.status_code
        results["raw_league"] = r.text
        if r.status_code == 200: results["league"] = r.json().get("data", {})
    except Exception as e: results["raw_league"] = f"Error: {str(e)}"

    # 2. Clasificación
    try:
        rs = requests.get("https://biwenger.as.com/api/v2/league/standings", headers=headers, timeout=8)
        results["raw_standings"] = rs.text
        if rs.status_code == 200:
            data = rs.json().get("data")
            # Corrección vital: si data es una lista directa, se asigna. Si es dict, se busca 'standings'
            if isinstance(data, list): results["standings"] = data
            elif isinstance(data, dict): results["standings"] = data.get("standings", [])
    except Exception as e: results["raw_standings"] = f"Error: {str(e)}"

    # 3. Tablón
    try:
        rb = requests.get("https://biwenger.as.com/api/v2/league/board?limit=100", headers=headers, timeout=8)
        results["raw_board"] = rb.text
        if rb.status_code == 200:
            data = rb.json().get("data")
            if isinstance(data, list): results["board"] = data
    except Exception as e: results["raw_board"] = f"Error: {str(e)}"

    # 4. Transferencias
    try:
        rt = requests.get("https://biwenger.as.com/api/v2/league/transfers?limit=100", headers=headers, timeout=8)
        results["raw_transfers"] = rt.text
        if rt.status_code == 200:
            data = rt.json().get("data")
            if isinstance(data, list): results["transfers"] = data
    except Exception as e: results["raw_transfers"] = f"Error: {str(e)}"

    return results

api_data = fetch_api_data(clean_token, str(league_id).strip(), str(user_id).strip())
league_info = api_data["league"]

if api_data["status"] != 200 or not isinstance(league_info, dict):
    st.error(f"⚠️ Error al conectar con Biwenger (Código: {api_data['status']})")
else:
    st.subheader(f"🏆 Liga: {league_info.get('name', 'Liga Biwenger')}")
    
    raw_users = league_info.get("users", []) or []
    if isinstance(api_data["standings"], list) and len(api_data["standings"]) > 0:
        raw_users.extend(api_data["standings"])

    user_stats = {}
    id_to_name = {}
    
    for u in raw_users:
        if not isinstance(u, dict): continue
        
        uid = u.get("id")
        u_dict = u.get("user") if isinstance(u.get("user"), dict) else {}
        uid = uid or u_dict.get("id")
        if not uid: continue
        uid = int(uid)
        
        uname = u.get("name") or u_dict.get("name") or f"Mánager {uid}"
        id_to_name[uid] = str(uname)
        
        tv = 0.0
        for key in ["teamValue", "value", "team_value", "squadValue"]:
            val = u.get(key) if u.get(key) is not None else u_dict.get(key)
            if val is not None:
                try:
                    if float(val) > 0:
                        tv = float(val)
                        break
                except: pass

        if tv == 0.0:
            clean_name = str(uname).strip().lower()
            tv = DAY_ONE_FALLBACK.get(clean_name, 0.0)
            uname_display = f"{uname} ⚠️"
        else:
            uname_display = str(uname)

        icon_raw = u.get("icon") or u.get("avatar") or u_dict.get("icon") or u_dict.get("avatar")
        icon_url = icon_raw if icon_raw and str(icon_raw).startswith("http") else f"https://biwenger.as.com/assets/images/{icon_raw}" if icon_raw else "https://biwenger.as.com/assets/images/user.png"
        
        real_bal = u.get("balance") or u_dict.get("balance")

        if uid not in user_stats:
            user_stats[uid] = {"name": uname_display, "icon": icon_url, "spent": 0.0, "gained": 0.0, "squad_val": tv, "real_balance": real_bal}
        else:
            if tv > 0 and "⚠️" in user_stats[uid]["name"]:
                user_stats[uid]["squad_val"] = tv
                user_stats[uid]["name"] = str(uname)
            if real_bal is not None: user_stats[uid]["real_balance"] = real_bal

    detected_transfers = []
    processed_keys = set()

    def process_event(seller_id, buyer_id, amount, source):
        if amount <= 0: return
        key = f"{seller_id}_{buyer_id}_{amount}"
        if key in processed_keys: return
        processed_keys.add(key)
        
        s_name = id_to_name.get(seller_id, "Mercado") if seller_id else "Mercado"
        b_name = id_to_name.get(buyer_id, "Mercado") if buyer_id else "Mercado"
        
        if seller_id in user_stats: user_stats[seller_id]["gained"] += amount
        if buyer_id in user_stats: user_stats[buyer_id]["spent"] += amount
        detected_transfers.append({"Origen": source, "Vendedor": s_name, "Comprador": b_name, "Importe (€)": amount})

    if isinstance(api_data["transfers"], list):
        for tr in api_data["transfers"]:
            if isinstance(tr, dict):
                s_id = tr.get("from", {}).get("id") if isinstance(tr.get("from"), dict) else tr.get("from")
                b_id = tr.get("to", {}).get("id") if isinstance(tr.get("to"), dict) else tr.get("to")
                try: process_event(int(s_id) if s_id else None, int(b_id) if b_id else None, float(tr.get("amount", 0)), "API Mercado")
                except: pass

    if isinstance(api_data["board"], list):
        for ev in api_data["board"]:
            if not isinstance(ev, dict): continue
            ev_type = str(ev.get("type", "")).lower()
            if not any(t in ev_type for t in ["transfer", "market", "purchase", "sale"]): continue
            
            content = ev.get("content", [])
            items = content if isinstance(content, list) else [content]
            for item in items:
                if isinstance(item, dict):
                    s_id = item.get("from", {}).get("id") if isinstance(item.get("from"), dict) else item.get("from")
                    b_id = item.get("to", {}).get("id") if isinstance(item.get("to"), dict) else item.get("to")
                    amt = item.get("amount") or item.get("price") or 0
                    try: process_event(int(s_id) if s_id else None, int(b_id) if b_id else None, float(amt), "Tablón")
                    except: pass

    records = []
    for uid, info in user_stats.items():
        squad_val = info["squad_val"]
        cash = float(info["real_balance"]) if info["real_balance"] is not None else (initial_budget - squad_val - info["spent"]) + info["gained"]
        records.append({
            "Icono": info["icon"], "Usuario": info["name"], "Valor Equipo (€)": squad_val,
            "Dinero en Caja (€)": cash, "Valor Total (€)": squad_val + cash, 
            "Puja Máxima (€)": cash + ((max_bid_pct / 100.0) * squad_val)
        })
    
    df_base = pd.DataFrame(records).sort_values(by="Valor Equipo (€)", ascending=False) if records else pd.DataFrame()
    for col in ["Valor Equipo (€)", "Dinero en Caja (€)", "Valor Total (€)", "Puja Máxima (€)"]:
        if col in df_base: df_base[col] = df_base[col].apply(lambda x: f"{x:,.0f} €".replace(",", "."))

    st.write("### 👥 Auditoría Automática de Finanzas")
    st.dataframe(
        df_base, 
        column_config={"Icono": st.column_config.ImageColumn("Icono")},
        use_container_width=True, hide_index=True, height=(len(df_base)+1)*38+10 if not df_base.empty else 200
    )

    with st.expander("📜 Ver Fichajes y Ventas Detectados por el Monitor"):
        if detected_transfers:
            df_trans = pd.DataFrame(detected_transfers)
            df_trans["Importe (€)"] = df_trans["Importe (€)"].apply(lambda x: f"{x:,.0f} €".replace(",", "."))
            st.dataframe(df_trans, use_container_width=True, hide_index=True)
        else: st.info("Aún no se han detectado movimientos.")

    # --- MODO DEPURACIÓN EN BRUTO ---
    with st.expander("🛠️ MODO DEPURACIÓN: Ver respuestas CRUDAS del servidor"):
        st.warning("Si estos cuadros dicen 'Token inválido', 'No autorizado', o muestran '[]', significa que tu Token de sesión ha caducado o no tiene permisos, y debes sacar uno nuevo de la web de Biwenger.")
        st.text_area("1. Clasificación RAW (¿Está enviando el Valor de Equipo?)", api_data["raw_standings"], height=150)
        st.text_area("2. Tablón RAW (¿Están aquí los eventos?)", api_data["raw_board"], height=150)
        st.text_area("3. Fichajes RAW (Endpoint directo)", api_data["raw_transfers"], height=150)
