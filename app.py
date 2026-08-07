import pandas as pd
import requests
import streamlit as st
import easyocr
import numpy as np
from PIL import Image

st.set_page_config(
    page_title="Monitor Financiero Biwenger", page_icon="⚽", layout="wide"
)

st.title("⚽ Monitor Financiero Biwenger")

# --- SIDEBAR: Configuración ---
token = st.sidebar.text_input("Bearer Token", type="password")
uploaded_file = st.sidebar.file_uploader("📸 Sube captura de Biwenger", type=["png", "jpg", "jpeg"])

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
if st.button("🔄 Recargar Datos"):
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

# --- EXTRACCIÓN DE DATOS DE LA LIGA ---
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
api_balance_data = {}
extraction_debug_logs = []

if raw_list:
  for item in raw_list:
    if not isinstance(item, dict):
      continue
    uid = item.get("id")
    uname = item.get("name") or item.get("username")
    if uid is None and isinstance(item.get("user"), dict):
      uid = item.get("user").get("id")
      uname = item.get("user").get("name") or item.get("user").get("username")
    if uid is None and uname is not None:
      uid = str(uname).lower().strip()
    elif uid is not None:
      uid = str(uid)
    if uid and uname:
      user_names[uid] = uname
      t_val = None
      for k in ["teamValue", "value", "marketValue", "price", "team_value"]:
        if k in item and item[k] is not None:
          try:
            val = float(item[k])
            if val > 0: t_val = val; break
          except: pass
      if t_val is None:
        for sub_key in ["team", "account", "user", "data"]:
          sub_obj = item.get(sub_key)
          if isinstance(sub_obj, dict):
            for k in ["teamValue", "value", "marketValue", "price", "team_value"]:
              if k in sub_obj and sub_obj[k] is not None:
                try:
                  val = float(sub_obj[k])
                  if val > 0: t_val = val; break
                except: pass
            if t_val is not None: break
      if t_val is not None: current_vm_data[uid] = t_val
      extraction_debug_logs.append({"ID": uid, "Usuario": uname})

# --- PROCESAMIENTO OCR MEJORADO ---
if uploaded_file is not None:
    st.write("🔍 Procesando imagen por filas...")
    try:
        reader = easyocr.Reader(['es'])
        img = Image.open(uploaded_file)
        img_np = np.array(img)
        result = reader.readtext(img_np)
        
        known_users = {str(name).lower().strip(): uid for uid, name in user_names.items()}
        
        lines = []
        for bbox, text, prob in result:
            y_center = (bbox[0][1] + bbox[2][1]) / 2
            lines.append((y_center, text))
            
        lines.sort(key=lambda x: x[0])
        
        rows = []
        tolerance = 15
        for y, text in lines:
            placed = False
            for row in rows:
                if abs(row['y'] - y) < tolerance:
                    row['texts'].append(text)
                    placed = True
                    break
            if not placed:
                rows.append({'y': y, 'texts': [text]})
                
        for row in rows:
            row_text_full = " ".join(row['texts']).lower()
            
            matched_uid = None
            for u_name_lower, uid in known_users.items():
                parts = u_name_lower.split()
                if any(p in row_text_full for p in parts if len(p) > 2):
                    matched_uid = uid
                    break
                    
            matched_val = None
            for t in row['texts']:
                clean_t = t.replace('.', '').replace(',', '').replace('€', '').replace('M', '').strip()
                if clean_t.isdigit():
                    val = float(clean_t)
                    if 100000 <= val <= 1000000000:
                        matched_val = val
                        break
                        
            if matched_uid and matched_val:
                current_vm_data[matched_uid] = matched_val
                
        st.success("✅ Valores de equipo actualizados correctamente desde la imagen.")
    except Exception as e:
        st.error(f"Error procesando imagen: {e}")

if not user_names:
  for name, val in DAY_ONE_VALS.items():
    uid = name.replace(" ", "_")
    user_names[uid] = name.title()
    if uid not in current_vm_data: current_vm_data[uid] = val

user_adjustments = {uid: 0.0 for uid in user_names.keys()}

# --- PROCESAR TRANSFERENCIAS Y TABLÓN ---
detected_events_log = []
def add_money(uid, amt, desc):
  uid_str = str(uid)
  if uid_str in user_adjustments and amt > 0:
    user_adjustments[uid_str] += amt
    detected_events_log.append({"Usuario": user_names.get(uid_str, uid_str), "Importe (€)": amt, "Descripción": desc})

def sub_money(uid, amt, desc):
  uid_str = str(uid)
  if uid_str in user_adjustments and amt > 0:
    user_adjustments[uid_str] -= amt
    detected_events_log.append({"Usuario": user_names.get(uid_str, uid_str), "Importe (€)": -amt, "Descripción": desc})

transfers = transfers_resp.get("data", []) if isinstance(transfers_resp, dict) else []
if isinstance(transfers, list):
  for t in transfers:
    if not isinstance(t, dict): continue
    amt = float(t.get("amount", 0) or t.get("price", 0) or 0)
    s = t.get("from"); b = t.get("to")
    if isinstance(s, dict): s = s.get("id")
    if isinstance(b, dict): b = b.get("id")
    if s is not None: add_money(str(s), amt, "Venta de Jugador")
    if b is not None: sub_money(str(b), amt, "Compra de Jugador")

board = board_resp.get("data", []) if isinstance(board_resp, dict) else []
if isinstance(board, list):
  for item in board:
    if not isinstance(item, dict): continue
    content = item.get("content")
    elements = content if isinstance(content, list) else [content]
    for el in elements:
      if not isinstance(el, dict): continue
      amt = float(el.get("amount", 0) or el.get("price", 0) or el.get("value", 0) or 0)
      from_obj = el.get("from"); to_obj = el.get("to")
      s_id = from_obj.get("id") if isinstance(from_obj, dict) else from_obj
      b_id = to_obj.get("id") if isinstance(to_obj, dict) else to_obj
      if s_id is not None and b_id is None and amt > 0: add_money(str(s_id), amt, "Venta Inmediata a Máquina")
      elif s_id is not None and b_id is not None and amt > 0:
        add_money(str(s_id), amt, "Venta entre mánagers")
        sub_money(str(b_id), amt, "Compra entre mánagers")

# --- CONSTRUCCIÓN DE LA TABLA EDITABLE ---
records = []
for uid, name in user_names.items():
  v_inicial = get_day_one_val(name)
  v_actual = current_vm_data.get(uid, v_inicial)
  ajuste = user_adjustments.get(uid, 0.0)
  
  saldo_real = (INITIAL_TOTAL - v_inicial) + ajuste
  
  records.append({
      "UID": uid,
      "Usuario": name,
      "Valor actual del equipo": v_actual,
      "Valor de equipo día 1": v_inicial,
      "Dinero en caja (calculado)": saldo_real,
      "Balance (ajuste)": ajuste,
  })

if records:
  st.subheader("📊 Monitor Financiero en Directo")
  st.write("✏️ *Actualiza el 'Valor actual del equipo' de cada mánager o sube captura.*")
  
  df_records = pd.DataFrame(records)
  
  df_editor_input = df_records[["Usuario", "Valor actual del equipo"]].copy()
  
  edited_df = st.data_editor(
      df_editor_input, 
      use_container_width=True, 
      hide_index=True,
      disabled=["Usuario"]
  )
  
  df_final = df_records.copy()
  df_final["Valor actual del equipo"] = edited_df["Valor actual del equipo"].values
  
  df_final["Valor equipo + caja"] = df_final["Valor actual del equipo"] + df_final["Dinero en caja (calculado)"]
  df_final["Puja máxima"] = df_final["Dinero en caja (calculado)"] + ((max_bid_pct / 100.0) * df_final["Valor actual del equipo"])
  
  df_final = df_final.sort_values("Valor equipo + caja", ascending=False)
  
  cols_to_format = ["Valor actual del equipo", "Valor de equipo día 1", "Dinero en caja (calculado)", "Balance (ajuste)", "Valor equipo + caja", "Puja máxima"]
  
  display_df = df_final.copy()
  for col in cols_to_format:
    display_df[col] = display_df[col].apply(lambda x: f"{x:,.0f} €".replace(",", "."))
    
  st.dataframe(display_df, use_container_width=True, hide_index=True)

else:
  st.warning("⚠️ No hay datos para mostrar en la tabla.")

st.markdown("---")
st.subheader("📜 Historial de Traspasos y Movimientos Detectados")
if detected_events_log:
  df_log = pd.DataFrame(detected_events_log)
  df_log["Importe (€)"] = df_log["Importe (€)"].apply(lambda x: f"{x:,.0f} €".replace(",", "."))
  st.dataframe(df_log, use_container_width=True, hide_index=True)
else:
  st.info("ℹ️ No se han detectado movimientos recientes.")
