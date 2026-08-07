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
    acc = requests.get(
        "https://biwenger.as.com/api/v2/account", headers=h, timeout=8
    ).json()
    leagues = acc.get("data", {}).get("leagues", [])
    if not leagues:
      return None, None, {}, {}, {}

    l = leagues[0]
    l_id = l.get("id")
    u_id = l.get("user", {}).get("id")

    h_league = h.copy()
    h_league.update({"X-League": str(l_id), "X-User": str(u_id)})

    r_league = requests.get(
        f"https://biwenger.as.com/api/v2/league/{l_id}?include=all",
        headers=h_league,
    ).json()
    r_transfers = requests.get(
        f"https://biwenger.as.com/api/v2/league/{l_id}/transfers?limit=50",
        headers=h_league,
    ).json()
    r_board = requests.get(
        f"https://biwenger.as.com/api/v2/league/{l_id}/board?limit=50",
        headers=h_league,
    ).json()

    return l_id, u_id, r_league, r_transfers, r_board
  except Exception as e:
    return None, None, {"error": str(e)}, {}, {}


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
    "nitrorx": 21490000.0,
}


def get_day_one_val(name):
  n_lower = str(name).lower().strip()
  for d_key, d_v in DAY_ONE_VALS.items():
    if d_key in n_lower:
      return d_v
  return 21500000.0


# --- EXTRACCIÓN DE DATOS ---
league_data = league_resp.get("data", {}) if isinstance(league_resp, dict) else {}
raw_list = []
for key_name in ["standings", "users", "members"]:
  val = league_data.get(key_name)
  if isinstance(val, list) and len(val) > 0:
    raw_list = val
    break
  elif isinstance(val, dict) and len(val) > 0:
    raw_list = list(val.values())
    break

user_names = {}
current_vm_data = {}

if raw_list:
  for item in raw_list:
    if not isinstance(item, dict): continue
    uid = item.get("id")
    uname = item.get("name") or item.get("username")
    if uid is None and isinstance(item.get("user"), dict):
      uid = item.get("user").get("id")
      uname = item.get("user").get("name") or item.get("user").get("username")
    if uid is None and uname is not None: uid = str(uname).lower().strip()
    elif uid is not None: uid = str(uid)
    if uid and uname:
      user_names[uid] = uname
      # Extraemos valor inicial de API
      t_val = None
      for k in ["teamValue", "value", "marketValue", "price", "team_value"]:
        if k in item and item[k] is not None:
            try: t_val = float(item[k]); break
            except: pass
      if t_val: current_vm_data[uid] = t_val

# --- PROCESAR AJUSTES (Transferencias) ---
user_adjustments = {uid: 0.0 for uid in user_names.keys()}
transfers = transfers_resp.get("data", []) if isinstance(transfers_resp, dict) else []
for t in transfers:
    amt = float(t.get("amount", 0) or t.get("price", 0) or 0)
    s = t.get("from")
    b = t.get("to")
    if isinstance(s, dict): s = s.get("id")
    if isinstance(b, dict): b = b.get("id")
    if s and str(s) in user_adjustments: user_adjustments[str(s)] += amt
    if b and str(b) in user_adjustments: user_adjustments[str(b)] -= amt

# --- CONSTRUCCIÓN DE LA TABLA ---
records = []
for uid, name in user_names.items():
  v_inicial = get_day_one_val(name)
  v_actual = current_vm_data.get(uid, v_inicial)
  records.append({
      "Usuario": name,
      "Valor de equipo día 1": v_inicial,
      "Valor actual del equipo": v_actual,
      "Balance": user_adjustments.get(uid, 0.0),
  })

if records:
  df = pd.DataFrame(records)
  
  st.subheader("📊 Monitor Financiero en Directo")
  st.write("✏️ *Puedes editar los valores en la columna 'Valor actual del equipo'.*")
  
  # --- AQUÍ ESTÁ EL CAMBIO ---
  # st.dataframe se convierte en st.data_editor
  edited_df = st.data_editor(df, use_container_width=True, hide_index=True)
  
  # Recalculamos con los valores editados (edited_df)
  df_final = edited_df.copy()
  
  # Calcular columnas calculadas basándose en el editor
  df_final["Dinero en caja"] = (INITIAL_TOTAL - df_final["Valor de equipo día 1"]) + df_final["Balance"]
  df_final["Valor equipo + caja"] = df_final["Valor actual del equipo"] + df_final["Dinero en caja"]
  df_final["Puja máxima"] = df_final["Dinero en caja"] + ((max_bid_pct / 100.0) * df_final["Valor actual del equipo"])
  
  df_final = df_final.sort_values("Valor equipo + caja", ascending=False)
  
  # Formateo visual
  for col in ["Valor de equipo día 1", "Valor actual del equipo", "Balance", "Dinero en caja", "Valor equipo + caja", "Puja máxima"]:
    df_final[col] = df_final[col].apply(lambda x: f"{x:,.0f} €".replace(",", "."))
    
  st.dataframe(df_final, use_container_width=True, hide_index=True)

else:
  st.warning("⚠️ No hay datos para mostrar.")
