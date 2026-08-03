import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Biwenger Dashboard", page_icon="⚽", layout="wide")

st.title("⚽ Liga Biwenger de Polola")

# --- SIDEBAR: Credenciales ---
st.sidebar.header("🔑 Credenciales")
token = st.sidebar.text_input("Bearer Token", type="password")
league_id = st.sidebar.text_input("League ID")
user_id = st.sidebar.text_input("User ID (Opcional)")

st.sidebar.header("⚙️ Configuración Financiera")
initial_budget = st.sidebar.number_input(
    "Presupuesto Total Inicial (€)", 
    value=40000000, 
    step=1000000,
    help="Reparto inicial del 31 de julio: 40M (Plantilla + Caja)"
)

if not token or not league_id:
    st.info("👈 Introduce tu **Bearer Token** y **League ID** en la barra lateral para acceder.")
    st.stop()

clean_token = token.strip().replace("Bearer ", "").replace("bearer ", "")
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

@st.cache_data(ttl=60)
def load_data():
    # Peticiones ultra sencillas para no saturar la API
    urls = [
        "https://biwenger.as.com/api/v2/league",
        "https://biwenger.as.com/api/v2/league/users",
        "https://biwenger.as.com/api/v2/league/standings"
    ]
    
    users = []
    last_status = None
    
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=8)
            last_status = r.status_code
            if r.status_code == 200:
                res = r.json().get("data", {})
                if isinstance(res, dict):
                    users = res.get("users", []) or res.get("standings", [])
                elif isinstance(res, list):
                    users = res
                if users:
                    break
        except Exception:
            pass

    parsed_users = []
    for u in users:
        if not isinstance(u, dict):
            continue
        uid = u.get("id") or (u.get("user", {}).get("id") if isinstance(u.get("user"), dict) else None)
        uname = u.get("name") or (u.get("user", {}).get("name") if isinstance(u.get("user"), dict) else f"Mánager {uid}")
        
        # Extraer el valor del equipo si viniera informado en la respuesta global
        tv = 0.0
        for k in ["teamValue", "value", "price"]:
            if k in u and isinstance(u[k], (int, float)):
                tv = float(u[k])
                break

        parsed_users.append({
            "ID": uid,
            "Usuario": str(uname),
            "Valor Equipo (€)": float(tv)
        })

    return pd.DataFrame(parsed_users), last_status

df_base, status_code = load_data()

if df_base.empty:
    st.error(f"❌ No se pudieron obtener los usuarios de la liga (Código de respuesta API: {status_code}).")
    st.warning("👉 Verifica que el **Bearer Token** no haya caducado y que el **League ID** sea correcto.")
    st.stop()

st.write("### 👥 Estado Financiero Calculado")
st.info("💡 **Ajuste Manual en Vivo:** Si la API de Biwenger no muestra el valor de la plantilla de algún rival, puedes modificar la celda **'Valor Equipo (€)'** directamente en la tabla. Los importes de **Dinero en Caja**, **Valor Total** y **Puja Máxima** se recalcularán al instante.")

# Tabla editable interactiva
df_edited = st.data_editor(
    df_base,
    column_config={
        "ID": None,
        "Usuario": st.column_config.TextColumn("Usuario", disabled=True),
        "Valor Equipo (€)": st.column_config.NumberColumn(
            "Valor Equipo (€)",
            min_value=0,
            step=500000,
            format="%d €"
        )
    },
    hide_index=True,
    use_container_width=True
)

# --- CÁLCULOS EN TIEMPO REAL ---
df_edited["Dinero en Caja (€)"] = initial_budget - df_edited["Valor Equipo (€)"]
df_edited["Valor Total (€)"] = df_edited["Dinero en Caja (€)"] + df_edited["Valor Equipo (€)"]
df_edited["Puja Máxima (€)"] = df_edited["Dinero en Caja (€)"] + (0.25 * df_edited["Valor Equipo (€)"])

# Reordenar columnas para presentación final
df_final = df_edited[["Usuario", "Valor Equipo (€)", "Dinero en Caja (€)", "Valor Total (€)", "Puja Máxima (€)"]]

# Formato visual limpio con separadores de miles
styler = df_final.style.format({
    "Valor Equipo (€)": lambda x: f"{x:,.0f} €".replace(",", "."),
    "Dinero en Caja (€)": lambda x: f"{x:,.0f} €".replace(",", "."),
    "Valor Total (€)": lambda x: f"{x:,.0f} €".replace(",", "."),
    "Puja Máxima (€)": lambda x: f"{x:,.0f} €".replace(",", ".")
})

st.write("#### 📊 Resultado Financiero y Límites de Baneo / Pujas")
st.dataframe(styler, use_container_width=True, hide_index=True)
