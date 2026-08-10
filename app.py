import json
import os
import pandas as pd
import pytesseract
import requests
import streamlit as st
from PIL import Image

st.set_page_config(
    page_title="Monitor Financiero Biwenger", page_icon="⚽", layout="wide"
)

st.title("⚽ Monitor Financiero Biwenger")

# --- HISTORIAL PERSISTENTE EN DISCO ---
HISTORY_FILE = "biwenger_history.json"


def load_history():
  if os.path.exists(HISTORY_FILE):
    try:
      with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    except Exception:
      return {}
  return {}


def save_history(history_data):
  try:
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
      json.dump(history_data, f, ensure_ascii=False, indent=2)
  except Exception as e:
    st.warning(f"No se pudo guardar el historial local: {e}")


# --- SIDEBAR: Configuración ---
token = st.sidebar.text_input("Bearer Token", type="password")
uploaded_file = st.sidebar.file_uploader(
    "📸 Sube captura de Biwenger", type=["png", "jpg", "jpeg"]
)

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
      return None, None, {}, {}, {}, {}

    l = leagues[0]
    l_id = l.get("id")
    u_id = l.get("user", {}).get("id")

    h_league = h.copy()
    h_league.update({"X-League": str(l_id), "X-User": str(u_id)})

    r_league = requests.get(
        f"https://biwenger.as.com/api/v2/league/{l_id}?include=all",
        headers=h_league,
    ).json()
    r_standings = requests.get(
        f"https://biwenger.as.com/api/v2/league/{l_id}/standings",
        headers=h_league,
    ).json()
    r_transfers = requests.get(
        f"https://biwenger.as.com/api/v2/league/{l_id}/transfers?limit=100",
        headers=h_league,
    ).json()
    r_board = requests.get(
        f"https://biwenger.as.com/api/v2/league/{l_id}/board?limit=100",
        headers=h_league,
    ).json()

    return l_id, u_id, r_league, r_transfers, r_board, r_standings
  except Exception as e:
    return None, None, {"error": str(e)}, {}, {}, {}


(
    l_id,
    u_id,
    league_resp,
    transfers_resp,
    board_resp,
    standings_resp,
) = load_data(clean_token)
if not l_id:
  st.error("❌ Error al conectar con la API de Biwenger. Comprueba tu token.")
  st.stop()

max_bid_pct = st.sidebar.slider("Crédito Valor Equipo (%)", 0, 100, 25)
if st.button("🔄 Recargar Datos"):
  st.cache_data.clear()
  st.rerun()

# --- VALORES DE REFERENCIA / DÍA 1 Y ORDEN DE USUARIOS ---
CUSTOM_USER_ORDER = [
    "athletik81",
    "ring014",
    "tubu",
    "marroba",
    "yoqsetio xdxd",
    "nitwolf",
    "nistalikus",
    "gran gravessen",
    "moltisanti",
    "zoropurgui",
    "_caesar_",
    "nitrorx",
]

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


def get_user_rank(name):
  n_lower = str(name).lower().strip()
  for idx, target_key in enumerate(CUSTOM_USER_ORDER):
    if target_key in n_lower:
      return idx
  return 999


# --- EXTRACCIÓN DE DATOS DE LA LIGA Y STANDINGS ---
raw_list = []

# Extraer primero de /standings (clasificación real)
s_data = (
    standings_resp.get("data", [])
    if isinstance(standings_resp, dict)
    else standings_resp
)
if isinstance(s_data, list):
  raw_list.extend(s_data)

# Extraer de /league
l_data = (
    league_resp.get("data", {}) if isinstance(league_resp, dict) else {}
)
for key_name in ["standings", "users", "members"]:
  val = l_data.get(key_name)
  if isinstance(val, list):
    raw_list.extend(val)
  elif isinstance(val, dict):
    raw_list.extend(list(val.values()))

user_names = {}
current_vm_data = {}

for item in raw_list:
  if not isinstance(item, dict):
    continue
  uid = item.get("id")
  uname = item.get("name") or item.get("username")
  if uid is None and isinstance(item.get("user"), dict):
    uid = item.get("user").get("id")
    uname = item.get("user").get("name") or item.get("user").get("username")

  if uname:
    uid_str = str(uid) if uid is not None else str(uname).lower().strip()
    uname_clean = str(uname).lower().strip()

    user_names[uid_str] = uname

    t_val = None
    for k in ["teamValue", "value", "marketValue", "price", "team_value"]:
      if k in item and item[k] is not None:
        try:
          val = float(item[k])
          if val > 100000:
            t_val = val
            break
        except:
          pass

    if t_val is not None:
      # Guardar tanto por ID como por nombre limpio para evitar descalces
      current_vm_data[uid_str] = t_val
      current_vm_data[uname_clean] = t_val

# --- PROCESAMIENTO OCR MEJORADO (TESSERACT POR FILAS) ---
if uploaded_file is not None:
  st.write("🔍 Leyendo captura por filas con Tesseract...")
  try:
    img = Image.open(uploaded_file).convert("L")
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    rows = {}
    for i in range(len(data["text"])):
      text = data["text"][i].strip()
      if not text:
        continue
      top = data["top"][i]
      matched_row = None
      for r_top in rows:
        if abs(r_top - top) < 15:
          matched_row = r_top
          break
      if matched_row is None:
        rows[top] = []
        matched_row = top
      rows[matched_row].append(text)

    known_users = {
        str(name).lower().strip(): uid for uid, name in user_names.items()
    }

    for r_top, words in rows.items():
      row_text = " ".join(words).lower()

      matched_uid = None
      matched_uname = None
      for u_name, uid in known_users.items():
        parts = u_name.split()
        if (
            any(p in row_text for p in parts if len(p) > 2)
            or u_name in row_text
        ):
          matched_uid = uid
          matched_uname = u_name
          break

      matched_val = None
      for w in words:
        clean_w = "".join(c for c in w if c.isdigit())
        if clean_w.isdigit() and len(clean_w) >= 6:
          val = float(clean_w)
          if 100000 <= val <= 1000000000:
            matched_val = val
            break

      if matched_val:
        if matched_uid:
          current_vm_data[matched_uid] = matched_val
        if matched_uname:
          current_vm_data[matched_uname] = matched_val

    st.success("✅ Valores actualizados correctamente desde la imagen.")
  except Exception as e:
    st.error(f"Error procesando la imagen: {e}")

if not user_names:
  for name, val in DAY_ONE_VALS.items():
    uid = name.replace(" ", "_")
    user_names[uid] = name.title()
    if uid not in current_vm_data:
      current_vm_data[uid] = val

# --- CARGAR HISTORIAL ACUMULADO ---
stored_history = load_history()
user_adjustments = {uid: 0.0 for uid in user_names.keys()}
detected_events_log = []


def parse_entity_id(ent):
  if isinstance(ent, dict):
    return str(ent.get("id")) if ent.get("id") is not None else None
  elif ent is not None:
    return str(ent)
  return None


def register_event(event_key, uid, amt, desc):
  """Registra un evento solo si no existía ya en la base de datos local."""
  if event_key not in stored_history:
    stored_history[event_key] = {
        "uid": str(uid),
        "amount": amt,
        "description": desc,
        "user_name": user_names.get(str(uid), str(uid)),
    }


# 1. Procesar /transfers
transfers = (
    transfers_resp.get("data", [])
    if isinstance(transfers_resp, dict)
    else []
)
if isinstance(transfers, list):
  for i, t in enumerate(transfers):
    if not isinstance(t, dict):
      continue
    t_id = str(
        t.get("id") or f"tr_{t.get('date', '')}_{i}_{t.get('amount', 0)}"
    )
    amt = float(
        t.get("amount", 0) or t.get("price", 0) or t.get("value", 0) or 0
    )
    s_id = parse_entity_id(t.get("from"))
    b_id = parse_entity_id(t.get("to"))

    if s_id and s_id in user_adjustments:
      register_event(f"tr_s_{t_id}", s_id, amt, "Venta de Jugador")
    if b_id and b_id in user_adjustments:
      register_event(f"tr_b_{t_id}", b_id, -amt, "Compra de Jugador")

# 2. Procesar /board
board = board_resp.get("data", []) if isinstance(board_resp, dict) else []
if isinstance(board, list):
  for i, item in enumerate(board):
    if not isinstance(item, dict):
      continue
    b_id_base = str(item.get("id") or f"bd_{item.get('date', '')}_{i}")
    type_event = item.get("type", "evento")
    content = item.get("content")
    elements = content if isinstance(content, list) else [content]

    for j, el in enumerate(elements):
      if not isinstance(el, dict):
        continue

      amt = float(
          el.get("amount", 0)
          or el.get("price", 0)
          or el.get("value", 0)
          or el.get("bonus", 0)
          or el.get("earned", 0)
          or 0
      )
      if amt <= 0:
        continue

      s_id = parse_entity_id(el.get("from"))
      b_id = parse_entity_id(el.get("to"))
      u_id_direct = (
          parse_entity_id(el.get("user"))
          or parse_entity_id(el.get("userID"))
          or parse_entity_id(el.get("id"))
      )

      if (
          s_id
          and b_id
          and s_id in user_adjustments
          and b_id in user_adjustments
      ):
        register_event(
            f"bd_s_{b_id_base}_{j}", s_id, amt, f"Venta mánager ({type_event})"
        )
        register_event(
            f"bd_b_{b_id_base}_{j}", b_id, -amt, f"Compra mánager ({type_event})"
        )
      elif s_id and s_id in user_adjustments and not b_id:
        register_event(
            f"bd_s_{b_id_base}_{j}", s_id, amt, f"Venta a Mercado ({type_event})"
        )
      elif b_id and b_id in user_adjustments and not s_id:
        register_event(
            f"bd_b_{b_id_base}_{j}", b_id, -amt, f"Compra a Mercado ({type_event})"
        )
      elif u_id_direct and u_id_direct in user_adjustments:
        register_event(
            f"bd_u_{b_id_base}_{j}",
            u_id_direct,
            amt,
            f"Prima / Abono ({type_event})",
        )

# Guardar eventos consolidados
save_history(stored_history)

# Calcular sumatorios de los eventos almacenados
for ev_id, ev_data in stored_history.items():
  uid = ev_data.get("uid")
  amt = ev_data.get("amount", 0.0)
  desc = ev_data.get("description", "")
  if uid in user_adjustments:
    user_adjustments[uid] += amt
    detected_events_log.append({
        "Usuario": user_names.get(uid, ev_data.get("user_name", uid)),
        "Importe (€)": amt,
        "Descripción": desc,
    })

# --- CORRECCIÓN MANUAL PERMANENTE (-280.000 € A YOQSETIO XDXD) ---
MANUAL_CORRECTIONS = {
    "yoqsetio xdxd": -280000.0,
}

for uid, name in user_names.items():
  name_lower = str(name).lower().strip()
  for target_key, correction_amt in MANUAL_CORRECTIONS.items():
    if target_key in name_lower:
      user_adjustments[uid] += correction_amt

# --- CONSTRUCCIÓN DE LA TABLA EDITABLE ---
records = []
for uid, name in user_names.items():
  v_inicial = get_day_one_val(name)
  name_clean = str(name).lower().strip()

  v_actual = (
      current_vm_data.get(uid)
      or current_vm_data.get(name_clean)
      or v_inicial
  )

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
  st.write(
      "✏️ *Actualiza o comprueba el 'Valor actual del equipo' reflejado por la"
      " captura.*"
  )

  df_records = pd.DataFrame(records)

  df_editor_input = df_records[["Usuario", "Valor actual del equipo"]].copy()

  edited_df = st.data_editor(
      df_editor_input,
      use_container_width=True,
      hide_index=True,
      disabled=["Usuario"],
  )

  df_final = df_records.copy()
  df_final["Valor actual del equipo"] = (
      edited_df["Valor actual del equipo"].values
  )

  df_final["Valor equipo + caja"] = (
      df_final["Valor actual del equipo"] + df_final["Dinero en caja (calculado)"]
  )
  df_final["Puja máxima"] = df_final["Dinero en caja (calculado)"] + (
      (max_bid_pct / 100.0) * df_final["Valor actual del equipo"]
  )

  # Ordenar segun el listado especificado en la imagen
  df_final["rank_custom"] = df_final["Usuario"].apply(get_user_rank)
  df_final = df_final.sort_values("rank_custom", ascending=True).drop(
      columns=["rank_custom"]
  )

  cols_num = [
      "Valor actual del equipo",
      "Valor de equipo día 1",
      "Dinero en caja (calculado)",
      "Balance (ajuste)",
      "Valor equipo + caja",
      "Puja máxima",
  ]

  def highlight_only_negatives(val):
    if isinstance(val, (int, float)) and val < 0:
      return "color: red; font-weight: bold;"
    return ""

  format_dict = {col: "{:,.0f} €" for col in cols_num}

  styled_df = (
      df_final[["Usuario"] + cols_num]
      .style.format(format_dict, thousands=".", precision=0)
      .map(highlight_only_negatives, subset=["Dinero en caja (calculado)"])
  )

  st.dataframe(
      styled_df,
      use_container_width=True,
      hide_index=True,
  )

  # --- GRÁFICO DE BARRAS DE VALOR DE EQUIPO + CAJA ---
  st.markdown("---")
  st.subheader("📈 Comparativa: Valor del Equipo + Caja")
  st.bar_chart(
      df_final,
      x="Usuario",
      y="Valor equipo + caja",
      use_container_width=True,
  )

else:
  st.warning("⚠️ No hay datos para mostrar en la tabla.")

st.markdown("---")
st.subheader("📜 Historial de Traspasos, Primas y Movimientos Detectados")
if detected_events_log:
  df_log = pd.DataFrame(detected_events_log)

  styled_log = df_log.style.format(
      {"Importe (€)": "{:,.0f} €"}, thousands=".", precision=0
  )

  st.dataframe(
      styled_log,
      use_container_width=True,
      hide_index=True,
  )
else:
  st.info("ℹ️ No se han detectado movimientos recientes.")
