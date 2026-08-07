import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Biwenger Financial Monitor", page_icon="⚽", layout="wide")

st.title("⚽ Monitor Financiero Biwenger")

# --- SIDEBAR: Auto-Login ---
st.sidebar.header("🔑 Conexión Automática")
token = st.sidebar.text_input("Bearer Token", type="password", help="Pega aquí tu token.")

if not token:
    st.info("👈 Pega tu **Bearer Token** en la barra lateral.")
    st.stop()

clean_token = token.strip()
if clean_token.lower().startswith("bearer "):
    clean_token = clean_token[7:].strip()

@st.cache_data(ttl=60)
def fetch_account_leagues(t):
    url = "https://biwenger.as.com/api/v2/account"
    h = {"Authorization": f"Bearer {t}", "X-App-Version": "2.0.0", "Accept": "application/json"}
    try:
        req = requests.get(url, headers=h, timeout=8)
        if req.status_code == 200:
            return req.json().get("data", {}).get("leagues", []), ""
        return [], f"Error HTTP {req.status_code}"
    except Exception as e:
        return [], str(e)

leagues_data, acc_err = fetch_account_leagues(clean_token)

if not leagues_data:
    st.sidebar.error("❌ Token inválido. Saca uno nuevo de la web.")
    st.stop()

# Selector de Liga Automático
league_dict = {l.get("name"): (l.get("id"), l.get("user", {}).get("id")) for l in leagues_data}
selected_league_name = st.sidebar.selectbox("🏆 Selecciona tu Liga", list(league_dict.keys()))
league_id, user_id = league_dict[selected_league_name]
st.sidebar.success("✅ Conectado y validado.")

st.sidebar.header("⚙️ Reglas Financieras")
initial_budget = st.sidebar.number_input("Presupuesto Inicial Total (€)", value=40000000, step=1000000)
max_bid_pct = st.sidebar.slider("Crédito Valor Equipo (%)", min_value=0.0, max_value=100.0, value=25.0)

if st.sidebar.button("🔄 Recargar Datos"):
    st.cache_data.clear()
    st.rerun()

headers = {
    "Authorization": f"Bearer {clean_token}",
    "X-League": str(league_id),
    "X-User": str(user_id),
    "Accept": "application/json",
    "X-App-Version": "2.0.0"
}

# --- RED DE SEGURIDAD: VALORES INICIALES ---
DAY_ONE_FALLBACK = {
    "athletik81": 21600000.0, "ring014": 21580000.0, "tubu": 21570000.0, 
    "marroba": 21560000.0, "zhukkov": 21560000.0, "nitwolf": 21550000.0, 
    "yoqsetio xdxd": 21550000.0, "nistalikus": 21550000.0, "moltisanti": 21540000.0, 
    "gran gravessen": 21540000.0, "zoropurgui": 21530000.0, "_caesar_": 21510000.0, 
    "nitrorx": 21490000.0
}

@st.cache_data(ttl=5)
def fetch_league_data(t_val, l_val, u_val):
    res = {"league": {}, "standings": [], "board": [], "transfers": []}
    try:
        r1 = requests.get("https://biwenger.as.com/api/v2/league", headers=headers, timeout=5)
        if r1.status_code == 200: res["league"] = r1.json().get("data", {})
        
        # Le añadimos parámetros extra para forzar que envíe el Valor de Equipo
        r2 = requests.get("https://biwenger.as.com/api/v2/league/standings?offset=0&limit=50", headers=headers, timeout=5)
        if r2.status_code == 200: 
            d = r2.json().get("data")
            res["standings"] = d if isinstance(d, list) else d.get("standings", [])

        r3 = requests.get("https://biwenger.as.com/api/v2/league/transfers?limit=100", headers=headers, timeout=5)
        if r3.status_code == 200: res["transfers"] = r3.json().get("data", [])

        r4 = requests.get("https://biwenger.as.com/api/v2/league/board?limit=100", headers=headers, timeout=5)
        if r4.status_code == 200: res["board"] = r4.json().get("data", [])
    except: pass
    return res

api_data = fetch_league_data(clean_token, league_id, user_id)
st.subheader(f"🏆 {selected_league_name}")

raw_users = api_data["league"].get("users", []) or []
if isinstance(api_data["standings"], list) and len(api_data["standings"]) > 0:
    raw_users.extend(api_data["standings"])

user_stats = {}
id_to_name = {}

# Procesar Usuarios
for u in raw_users:
    if not isinstance(u, dict): continue
    
    uid = u.get("id")
    u_dict = u.get("user") if isinstance(u.get("user"), dict) else {}
    uid = uid or u_dict.get("id")
    if not uid: continue
    uid = int(uid)
    
    uname = u.get("name") or u_dict.get("name") or f"Mánager {uid}"
    id_to_name[uid] = str(uname)
    
    # 1. Intentar sacar el valor de equipo de la API
    tv_api = 0.0
    for key in ["teamValue", "value", "team_value", "squadValue"]:
        val = u.get(key) if u.get(key) is not None else u_dict.get(key)
        if val is not None:
            try:
                if float(val) > 0: tv_api = float(val); break
            except: pass

    # 2. Cargar valor inicial de respaldo
    clean_name = str(uname).strip().lower()
    tv_inicial = DAY_ONE_FALLBACK.get(clean_name, 0.0)
    
    # Si la API falla o da 0, usamos el inicial. Si la API da un dato real (porque vendió), lo usamos.
    tv_final = tv_api if tv_api > 0 else tv_inicial

    icon_raw = u.get("icon") or u.get("avatar") or u_dict.get("icon") or u_dict.get("avatar")
    icon_url = icon_raw if icon_raw and str(icon_raw).startswith("http") else f"https://biwenger.as.com/assets/images/{icon_raw}" if icon_raw else "https://biwenger.as.com/assets/images/user.png"

    if uid not in user_stats:
        user_stats[uid] = {
            "name": str(uname), "icon": icon_url, 
            "spent": 0.0, "gained": 0.0, 
            "squad_val_actual": tv_final, 
            "squad_val_inicial": tv_inicial
        }
    else:
        if tv_final > 0: user_stats[uid]["squad_val_actual"] = tv_final
        if tv_inicial > 0: user_stats[uid]["squad_val_inicial"] = tv_inicial

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

# Leer Fichajes
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

# --- CÁLCULOS MÁGICOS ---
records = []
for uid, info in user_stats.items():
    squad_val_actual = info["squad_val_actual"]
    
    # 1. Calculamos cuánto dinero DEBERÍA tener en caja (Caja Inicial - Gastos + Ingresos Reales)
    caja_inicial = initial_budget - info["squad_val_inicial"]
    caja_visible = caja_inicial - info["spent"] + info["gained"]
    
    # 2. Truco del Limbo: Buscamos el dinero escondido de la máquina
    valor_total_visible = squad_val_actual + caja_visible
    
    # Si el valor visible es menor a 40M, la diferencia es la venta a la máquina que aún no han pagado
    dinero_limbo = 0.0
    if valor_total_visible < initial_budget:
        dinero_limbo = initial_budget - valor_total_visible
        
    # 3. La caja real que podrá usar esta noche es la Visible + el Limbo
    caja_real_total = caja_visible + dinero_limbo
    puja_maxima = caja_real_total + ((max_bid_pct / 100.0) * squad_val_actual)
        
    records.append({
        "Icono": info["icon"], 
        "Usuario": info["name"], 
        "Valor Equipo (€)": squad_val_actual,
        "Dinero Caja (Visible)": caja_visible,
        "💸 Pendiente Máquina": dinero_limbo,
        "💰 CAJA REAL TOTAL": caja_real_total,
        "🔥 Puja Máxima Real": puja_maxima
    })

df_base = pd.DataFrame(records)
if not df_base.empty:
    df_base = df_base.sort_values(by="💰 CAJA REAL TOTAL", ascending=False)

for col in ["Valor Equipo (€)", "Dinero Caja (Visible)", "💸 Pendiente Máquina", "💰 CAJA REAL TOTAL", "🔥 Puja Máxima Real"]:
    if col in df_base: df_base[col] = df_base[col].apply(lambda x: f"{x:,.0f} €".replace(",", "."))

st.dataframe(
    df_base, 
    column_config={"Icono": st.column_config.ImageColumn("Icono")},
    use_container_width=True, hide_index=True, height=(len(df_base)+1)*38+10 if not df_base.empty else 200
)

with st.expander("📜 Ver Fichajes y Ventas Detectados"):
    if detected_transfers:
        df_trans = pd.DataFrame(detected_transfers)
        df_trans["Importe (€)"] = df_trans["Importe (€)"].apply(lambda x: f"{x:,.0f} €".replace(",", "."))
        st.dataframe(df_trans, use_container_width=True, hide_index=True)
    else: st.info("Aún no se han detectado movimientos.")
