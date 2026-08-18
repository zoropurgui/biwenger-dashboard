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
        return {k: v for k, v in data.items() if not k.startswith("tr_")}
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
    r_standings = requests.get(
        f"https://biwenger.as.com/api/v2/league/{l_id}/standings",
        headers=h_league,
    ).json()
    r_board = requests.get(
        f"https://biwenger.as.com/api/v2/league/{l_id}/board?limit=500",
        headers=h_league,
    ).json()

    return l_id, u_id, r_league, r_board, r_standings
  except Exception as e:
    return None, None, {"error": str(e)}, {}, {}


(
    l_id,
    u_id,
    league_resp,
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

# --- ORDEN PERSONALIZADO Y VALORES DE REFERENCIA ---
CUSTOM_USER_ORDER = [
    "tubu",
    "ring014",
    "gran gravessen",
    "marroba",
    "moltisanti",
    "_caesar_",
    "nitrorx",
    "nitwolf",
    "athletik81",
    "nistalikus",
    "zoropurgui",
    "yoqsetio xdxd",
]

DAY_ONE_VALS = {
    "athletik81": 21600000.0,
    "ring014": 21580000.0,
    "tubu": 21570000.0,
    "marroba": 21560000.0,
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


# --- MAPEO UNIVERSAL DE USUARIOS ---
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
user_lookup = {}
current_vm_data = {}
direct_cash_data = {}

for item in raw_list:
  if not isinstance(item, dict):
    continue
  uid = item.get("id")
  uname = item.get("name") or item.get("username")
  if uid is None and isinstance(item.get("user"), dict):
    uid = item.get("user").get("id")
    uname = item.get("user").get("name") or item.get("user").get("username")

  if uid is not None or uname:
    canonical_uid = str(uid) if uid is not None else str(uname).lower().strip()
    display_name = str(uname) if uname else canonical_uid

    user_names[canonical_uid] = display_name

    if uid is not None:
      user_lookup[str(uid)] = canonical_uid
    if uname:
      user_lookup[str(uname).lower().strip()] = canonical_uid
      user_lookup[str(uname).strip()] = canonical_uid

    for cash_key in ["cash", "balance", "money", "dinero"]:
      if cash_key in item and item[cash_key] is not None:
        try:
          direct_cash_data[canonical_uid] = float(item[cash_key])
          break
        except:
          pass

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
      current_vm_data[canonical_uid] = t_val


def resolve_user(ent):
  if ent is None:
    return None
  if isinstance(ent, dict):
    eid = ent.get("id")
    if eid is not None and str(eid) in user_lookup:
      return user_lookup[str(eid)]
    ename = ent.get("name") or ent.get("username")
    if ename and str(ename).lower().strip() in user_lookup:
      return user_lookup[str(ename).lower().strip()]
    if isinstance(ent.get("user"), dict):
      return resolve_user(ent.get("user"))
    return None
  ent_str = str(ent).strip()
  if ent_str in user_lookup:
    return user_lookup[ent_str]
  if ent_str.lower() in user_lookup:
    return user_lookup[ent_str.lower()]
  return None


# --- OCR TESSERACT POR FILAS ---
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

    for r_top, words in rows.items():
      row_text = " ".join(words).lower()

      matched_uid = None
      for u_name_key, uid in user_lookup.items():
        if u_name_key in row_text and len(u_name_key) > 2:
          matched_uid = uid
          break

      matched_val = None
      for w in words:
        clean_w = "".join(c for c in w if c.isdigit())
        if clean_w.isdigit() and len(clean_w) >= 6:
          val = float(clean_w)
          if 100000 <= val <= 1000000000:
            matched_val = val
            break

      if matched_val and matched_uid:
        current_vm_data[matched_uid] = matched_val

    st.success("✅ Valores actualizados correctamente desde la imagen.")
  except Exception as e:
    st.error(f"Error procesando la imagen: {e}")

if not user_names:
  for name, val in DAY_ONE_VALS.items():
    uid = name.replace(" ", "_")
    user_names[uid] = name.title()
    user_lookup[name.lower()] = uid
    if uid not in current_vm_data:
      current_vm_data[uid] = val


# --- HISTORIAL DEL MURO ---
stored_history = load_history()
user_adjustments = {uid: 0.0 for uid in user_names.keys()}
detected_events_log = []


def register_event(event_key, uid, amt, desc, overwrite=False):
  if uid in user_adjustments:
    if event_key not in stored_history or overwrite:
      stored_history[event_key] = {
          "uid": str(uid),
          "amount": amt,
          "description": desc,
          "user_name": user_names.get(str(uid), str(uid)),
      }


def extract_round_id(item, el):
  rnd = item.get("round") or el.get("round")
  if isinstance(rnd, dict):
    r_val = rnd.get("id") or rnd.get("name") or rnd.get("round")
    if r_val:
      match = re.search(r"\d+", str(r_val))
      if match:
        return match.group(0)
  elif rnd is not None and str(rnd).strip():
    match = re.search(r"\d+", str(rnd))
    if match:
      return match.group(0)

  title = str(
      item.get("title", "") or item.get("name", "") or item.get("text", "")
  ).lower()
  if "jornada" in title or "round" in title:
    match = re.search(r"(?:jornada|round)\s*(\d+)", title)
    if match:
      return match.group(1)
  return None


board = board_resp.get("data", []) if isinstance(board_resp, dict) else []
if isinstance(board, list):
  for item in board:
    if not isinstance(item, dict):
      continue

    type_event = item.get("type", "evento")
    has_real_id = bool(item.get("id"))
    item_id = str(item.get("id") or f"bd_{item.get('date', '')}_{type_event}")

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

      s_id = resolve_user(el.get("from"))
      b_id = resolve_user(el.get("to"))
      u_id_direct = (
          resolve_user(el.get("user"))
          or resolve_user(el.get("userID"))
          or resolve_user(el.get("id"))
      )

      rnd_id = extract_round_id(item, el)
      is_round_bonus = (
          type_event in ["round", "roundBonus", "bonus"] or rnd_id is not None
      )

      if type_event in ["transfer", "transfers", "market", "clause"] or (
          s_id or b_id
      ):
        if s_id and b_id:
          register_event(
              f"bd_s_{item_id}_{j}",
              s_id,
              amt,
              "Venta a mánager",
              overwrite=has_real_id,
          )
          register_event(
              f"bd_b_{item_id}_{j}",
              b_id,
              -amt,
              "Compra de mánager",
              overwrite=has_real_id,
          )
        elif s_id and not b_id:
          register_event(
              f"bd_s_{item_id}_{j}",
              s_id,
              amt,
              "Venta a Mercado",
              overwrite=has_real_id,
          )
        elif b_id and not s_id:
          register_event(
              f"bd_b_{item_id}_{j}",
              b_id,
              -amt,
              "Compra de Mercado",
              overwrite=has_real_id,
          )
        elif u_id_direct:
          register_event(
              f"bd_u_{item_id}_{j}",
              u_id_direct,
              amt,
              f"Movimiento ({type_event})",
              overwrite=has_real_id,
          )

      elif is_round_bonus and rnd_id:
        u_target = u_id_direct or b_id or s_id
        if u_target:
          event_key = f"bd_round_{rnd_id}_{u_target}"
          desc = f"Prima Jornada {rnd_id}"
          register_event(event_key, u_target, amt, desc, overwrite=True)

      else:
        u_target = u_id_direct or b_id or s_id
        if u_target:
          event_key = f"bd_u_{item_id}_{j}"
          desc = f"Prima / Abono ({type_event})"
          register_event(
              event_key, u_target, amt, desc, overwrite=has_real_id
          )

save_history(stored_history)

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

# --- AJUSTES MANUALES EXCLUSIVOS PARA CASOS FUERA DEL LÍMITE DE API ---
HISTORICAL_OFFSETS = {
    "moltisanti": -3888000.0,
}

for uid, name in user_names.items():
  name_lower = str(name).lower().strip()
  for target_key, offset_amt in HISTORICAL_OFFSETS.items():
    if target_key in name_lower:
      user_adjustments[uid] += offset_amt

# --- CONSTRUCCIÓN DE LA TABLA PRINCIPAL ---
records = []
for uid, name in user_names.items():
  v_inicial = get_day_one_val(name)
  v_actual = current_vm_data.get(uid, v_inicial)

  if uid in direct_cash_data:
    saldo_real = direct_cash_data[uid]
  else:
    ajuste = user_adjustments.get(uid, 0.0)
    saldo_real = (INITIAL_TOTAL - v_inicial) + ajuste

  records.append({
      "UID": uid,
      "Usuario": name,
      "Valor actual del equipo": v_actual,
      "Valor de equipo día 1": v_inicial,
      "Dinero en caja (calculado)": saldo_real,
      "Balance (ajuste)": user_adjustments.get(uid, 0.0),
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

  table_height = (len(df_final) + 1) * 35 + 10

  st.dataframe(
      styled_df,
      use_container_width=True,
      hide_index=True,
      height=table_height,
  )

  # --- GRÁFICO DE BARRAS ---
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
