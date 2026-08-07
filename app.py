import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Monitor Financiero Biwenger", page_icon="⚽", layout="wide"
)

st.title("⚽ Monitor Financiero Biwenger")

# --- SIDEBAR: Configuración ---
token = st.sidebar.text_input("Bearer Token", type="password")

if not token:
  st.info("👈 Pega tu **Bearer Token** en la barra lateral para empezar.")
  st.stop()

clean_token = token.strip().replace("Bearer ", "").strip()

INITIAL_TOTAL = 40000000.0

@st.cache_data(ttl=30)
def load_data(t):
  h = {"Authorization": f"Bearer {t}", "X-App-Version": "2.0.0"}
  try:
    acc = requests.get("https://biwenger.as.com/api/v2/account", headers=h, timeout=8).json()
    leagues = acc.get("data", {}).get("leagues", [])
    if not leagues: return None, None, {}, {}, {}
    l = leagues[0]
    l_id = l.get("id")
    u_id = l.get("user", {}).get("id")
    h_league = h.copy()
    h_league.update({"X-League": str(l_id), "X-User": str(u_id)})
    r_league = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}?include=all", headers=h_league).json()
    r_transfers = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}/transfers?limit=50", headers=h_league).json()
    r_board = requests.get(f"https://biwenger.as.com/api/v2/league/{l_id}/board?limit=50", headers=h_league).json()
    return l_id, u_id, r_league, r_transfers, r_board
  except Exception as e: return None, None, {"error": str(e)}, {}, {}

l_id, u_id, league_resp, transfers_resp, board_resp = load_data(clean_token)

if not l_id:
  st.error("❌ Error al conectar con la API de Biwenger. Comprueba tu token.")
  st.stop()

max_bid_pct = st.sidebar.slider("Crédito Valor Equipo (%)", 0, 100, 25)
if st.sidebar.button("🔄 Recargar Datos"):
  st.cache_data.clear()
  st.rerun()

# --- VALORES DE REFERENCIA / DÍA 1 ---
DAY_ONE_VALS = {
    "athletik81": 21600000.0, "ring014": 21580000.0, "tubu": 21570000.0,
    "marroba": 21560000.0, "zhukkov": 21560000.0, "nitwolf": 21550000.0,
    "yoqsetio xdxd": 21550000.0, "nistalikus": 21550000.0, "moltisanti": 21540000.0,
    "gran gravessen": 21540000.0, "zoropurgui": 21530000.0, "_caesar_": 21510000.0,
    "nitrorx": 21490000.0,
}

# --- EXTRACCIÓN DE DATOS ---
league_data = league_resp.get("data", {}) if isinstance(league_resp, dict) else {}
raw_list = []
for key_name in ["standings", "users", "members"]:
  val = league_data.get(key_name)
  if isinstance(val, list) and len(val) > 0: raw_list = val; break
  elif isinstance(val, dict) and len(val) > 0: raw_list = list(val.values()); break

user_names = {}
vm_data = {}
if raw_list:
  for item in raw_list:
    if not isinstance(item, dict): continue
    uid = item.get("id")
    uname = item.get("name") or item.get("username")
    if uid is None and isinstance(item.get("user"), dict):
      uid = item.get("user").get("id")
      uname = item.get("user").get("name") or item.get("user").get("username")
    if uid and uname:
      user_names[str(uid)] = uname
      # Extraer valor actual API (base para tu edición)
      t_val = 0
      for k in ["teamValue", "value", "marketValue", "price"]:
        if k in item and item[k]: t_val = float(item[k]); break
      vm_data[str(uid)] = t_val if t_val > 0 else 21500000.0

# --- PROCESAR AJUSTES ---
user_adjustments = {uid: 0.0 for uid in user_names.keys()}
def add_money(uid, amt): 
    if str(uid) in user_adjustments: user_adjustments[str(uid)] += amt
def sub_money(uid, amt): 
    if str(uid) in user_adjustments: user_adjustments[str(uid)] -= amt

transfers = transfers_resp.get("data", []) if isinstance(transfers_resp, dict) else []
for t in transfers:
    amt = float(t.get("amount", 0) or t.get("price", 0) or 0)
    s = t.get("from")
    b = t.get("to")
    if isinstance(s, dict): add_money(s.get("id"), amt)
    if isinstance(b, dict): sub_money(b.get("id"), amt)

board = board_resp.get("data", []) if isinstance(board_resp, dict) else []
for item in board:
    content = item.get("content")
    elements = content if isinstance(content, list) else [content]
    for el in elements:
        if not isinstance(el, dict): continue
        amt = float(el.get("amount") or el.get("price") or el.get("value") or 0)
        s_id = el.get("from", {}).get("id") if isinstance(el.get("from"), dict) else el.get("from")
        b_id = el.get("to", {}).get("id") if isinstance(el.get("to"), dict) else el.get("to")
        if s_id and not b_id: add_money(s_id, amt)
        elif s_id and b_id: add_money(s_id, amt); sub_money(b_id, amt)

# --- CONSTRUCCIÓN TABLA EDITABLE ---
records = []
for uid, name in user_names.items():
    records.append({
        "UID": uid, # Necesario para mapear luego
        "Usuario": name,
        "Valor equipo día 1": next((v for k, v in DAY_ONE_VALS.items() if k in name.lower()), 21500000.0),
        "Valor actual manual": vm_data.get(uid, 21500000.0),
    })

st.subheader("📊 Monitor Financiero")
st.write("✏️ *Edita la columna 'Valor actual manual' y el script recalculará el resto.*")

df_editor = st.data_editor(pd.DataFrame(records), hide_index=True)

# --- RE-CÁLCULO CON DATOS EDITADOS ---
final_records = []
for _, row in df_editor.iterrows():
    uid = row["UID"]
    v_actual = row["Valor actual manual"]
    v_inicial = row["Valor equipo día 1"]
    ajuste = user_adjustments.get(uid, 0.0)
    
    saldo_real = (INITIAL_TOTAL - v_inicial) + ajuste
    valor_total_caja = v_actual + saldo_real
    puja_max = saldo_real + ((max_bid_pct / 100.0) * v_actual)
    
    final_records.append({
        "Usuario": row["Usuario"],
        "Valor actual": v_actual,
        "Dinero en caja": saldo_real,
        "Valor equipo + caja": valor_total_caja,
        "Puja máxima": puja_max
    })

# Mostrar resultados finales
df_final = pd.DataFrame(final_records).sort_values("Valor equipo + caja", ascending=False)
for col in ["Valor actual", "Dinero en caja", "Valor equipo + caja", "Puja máxima"]:
    df_final[col] = df_final[col].apply(lambda x: f"{x:,.0f} €".replace(",", "."))

st.dataframe(df_final, use_container_width=True, hide_index=True)
