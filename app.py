import json
import os
import re
import pandas as pd
import plotly.express as px
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

# --- BOTÓN DE EMERGENCIA PARA RESETEAR ---
if st.sidebar.button("⚠️ RESETEAR HISTORIAL (Borrar JSON)"):
  if os.path.exists(HISTORY_FILE):
    os.remove(HISTORY_FILE)
    st.success("Historial borrado. Recargando...")
    st.rerun()
  else:
    st.warning("No se encontró el archivo de historial para borrar.")


def load_history():
  if os.path.exists(HISTORY_FILE):
    try:
      with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        # Limpieza automática de duplicados de fichajes que venían del muro en versiones anteriores
        cleaned = {}
        for k, v in data.items():
          desc = v.get("description", "")
          # Si el evento proviene del muro (bd_) y es una compra/venta, se descarta
          # porque /transfers (tr_) ya la contabiliza oficialmente.
          if k.startswith("bd_") and (
              "Venta" in desc or "Compra" in desc or "Mercado" in desc
          ):
            continue
          cleaned[k] = v
        return cleaned
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
    # Aumentado limit=500 para abarcar todo el historial de fichajes
    r_transfers = requests.get(
        f"https://biwenger.as.com/api/v2/league/{l_id}/transfers?limit=500",
        headers=h_league,
    ).json()
    r_board = requests.get(
        f"https://biwenger.as.com/api/v2/league/{l_id}/board?limit=500",
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

s_data = (
    standings_resp.get("data", [])
    if isinstance(standings_resp, dict)
    else standings_resp
)
if isinstance(s_data, list):
  raw_list.extend(s_data)

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


# --- CARGAR HISTORIAL ACUMULADO Y LIMPIAR DUPLICADOS ---
stored_history = load_history()

user_adjustments = {uid: 0.0 for uid in user_names.keys()}
detected_events_log = []


def parse_entity_id(ent):
  if isinstance(ent, dict):
    return str(ent.get("id")) if ent.get("id") is not None else None
  elif ent is not None:
    return str(ent)
  return None


def register_event(event_key, uid, amt, desc, overwrite=False):
  """Registra un evento o lo actualiza si overwrite es True."""
  if event_key not in stored_history or overwrite:
    stored_history[event_key] = {
        "uid": str(uid),
        "amount": amt,
        "description": desc,
        "user_name": user_names.get(str(uid), str(uid)),
    }


def extract_round_id(item, el):
  """Extrae el número o identificador de jornada/round si está disponible."""
  rnd = item.get("round") or el.get("round")
  if isinstance(rnd, dict):
    r_val = rnd.get("id") or rnd.get("name") or rnd.get("round")
    if r_val:
      str_val = str(r_val).strip()
      match = re.search(r"\d+", str_val)
      if match:
        return match.group(0)
      return str_val
  elif rnd is not None and str(rnd).strip():
    str_val = str(rnd).strip()
    match = re.search(r"\d+", str_val)
    if match:
      return match.group(0)
    return str_val

  title = str(
      item.get("title", "") or item.get("name", "") or item.get("text", "")
  ).lower()
  if "jornada" in title or "round" in title:
    match = re.search(r"(?:jornada|round)\s*(\d+)", title)
    if match:
      return match.group(1)
  return None


# 1. Procesar /transfers (Fuente oficial de compras y ventas)
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
        t.get("id") or f"tr_{t.get('date', '')}_{t.get('amount', 0)}"
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

# 2. Procesar /board (Muro de la liga: SOLO primas, abonos y bonificaciones)
TRANSFER_EVENT_TYPES = {"transfer", "transfers", "market", "clause"}

board = board_resp.get("data", []) if isinstance(board_resp, dict) else []
if isinstance(board, list):
  for i, item in enumerate(board):
    if not isinstance(item, dict):
      continue

    type_event = item.get("type", "evento")
    # TAREA CLAVE: Ignorar eventos de fichajes/mercado del muro para NO duplicar con /transfers
    if type_event in TRANSFER_EVENT_TYPES:
      continue

    has_real_id = bool(item.get("id"))
    b_id_base = str(item.get("id") or f"bd_{item.get('date', '')}_{type_event}")

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

      u_id_direct = (
          parse_entity_id(el.get("user"))
          or parse_entity_id(el.get("userID"))
          or parse_entity_id(el.get("id"))
          or parse_entity_id(el.get("to"))
      )

      rnd_id = extract_round_id(item, el)
      is_round_bonus = (
          type_event in ["round", "roundBonus", "bonus"] or rnd_id is not None
      )

      if u_id_direct and u_id_direct in user_adjustments:
        if is_round_bonus and rnd_id:
          # Clave fija vinculada al número de jornada y al mánager para actualizar primas aplazadas
          event_key = f"bd_round_{rnd_id}_{u_id_direct}"
          desc = f"Prima Jornada {rnd_id}"
          register_event(event_key, u_id_direct, amt, desc, overwrite=True)
        else:
          event_key = f"bd_u_{b_id_base}_{j}"
          desc = f"Prima / Abono ({type_event})"
          register_event(
              event_key, u_id_direct, amt, desc, overwrite=has_real_id
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

  # Calculamos la altura dinamica segun la cantidad de filas (aprox. 35px por fila + cabecera)
  table_height = (len(df_final) + 1) * 35 + 10

  st.dataframe(
      styled_df,
      use_container_width=True,
      hide_index=True,
      height=table_height,
  )

  # --- GRÁFICO DE BARRAS PERSONALIZADO (PLOTLY) ---
  st.markdown("---")
  st.subheader("📈 Comparativa: Valor del Equipo + Caja")

  fig = px.bar(
      df_final,
      x="Usuario",
      y="Valor equipo + caja",
      text="Valor equipo + caja",
      color_discrete_sequence=["#0d6efd"],
  )

  fig.update_traces(
      texttemplate="%{text:,.0f} €",
      textposition="outside",
      width=0.3,
  )

  fig.update_layout(
      xaxis_title="Usuario",
      yaxis_title="Valor equipo + caja",
      yaxis=dict(showgrid=True),
      height=500,
      margin=dict(l=20, r=20, t=30, b=20),
  )

  st.plotly_chart(fig, use_container_width=True)

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
