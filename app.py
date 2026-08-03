import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Biwenger Dashboard", page_icon="⚽", layout="wide")

st.title("⚽ Liga Biwenger de Polola")

# --- SIDEBAR ---
st.sidebar.header("🔑 Credenciales")
token = st.sidebar.text_input("Bearer Token", type="password")
league_id = st.sidebar.text_input("League ID")
user_id = st.sidebar.text_input("User ID (Opcional)")

st.sidebar.header("⚙️ Configuración Financiera")
initial_budget = st.sidebar.number_input(
    "Presupuesto Total Inicial (€)", 
    value=40000000, 
    step=1000000,
    help="Reparto inicial: 40M (Plantilla + Caja)"
)

if not token or not league_id:
    st.info("👈 Introduce tu **Bearer Token** y **League ID** en la barra lateral.")
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
    # 1. Obtener la lista de mánagers
    url_users = "https://biwenger.as.com/api/v2/league?fields=*,users(*,team,squad,teamValue),standings(*,user,team)"
    users = []
    try:
        r = requests.get(url_users, headers=headers, timeout=10)
        if r.status_code == 200:
            res = r.json().get("data", {})
            users = res.get("users", []) or res.get("standings", [])
    except Exception:
        pass

    parsed_users = []
    for u in users:
        if not isinstance(u, dict):
            continue
        uid = u.get("id") or (u.get("user", {}).get("id") if isinstance(u.get("user"), dict) else None)
        uname = u.get("name") or (u.get("user", {}).get("name") if isinstance(u.get("user"), dict) else f"User {uid}")
        
        # Intentar obtener el valor de equipo directo de la API
        tv = 0.0
        for k in ["teamValue", "value"]:
            if k in u and isinstance(u[k], (int, float)):
                tv = float(u[k])
                break
        
        # Si no está en la llamada principal, probar consulta individual por usuario
        if tv == 0 and uid:
            try:
                r_u = requests.get(f"https://biwenger.as.com/api/v2/user/{uid}?fields=teamValue,team,squad", headers=headers, timeout=3)
                if r_u.status_code == 200:
                    d_u = r_u.json().get("data", {})
                    tv = float(d_u.get("teamValue") or d_u.get("value") or 0.0)
            except Exception:
                pass

        parsed_users.append({
            "ID": uid,
            "Usuario": str(uname),
            "Valor Equipo (€)": float(tv)
        })

    return pd.DataFrame(parsed_users)

df_base = load_data()

if df_base.empty:
    st.error("❌ No se pudieron cargar los datos de la liga. Revisa tu Token y League ID.")
    st.stop()

st.write("### 👥 Estado Financiero Calculado")
st.info("💡 **Nota:** Si la API de Biwenger entrega $0\text{ €}$ en el valor del equipo de los rivales, puedes editar la columna **'Valor Equipo (€)'** directamente en la tabla y los cálculos de Caja y Puja Máxima se actualizarán automáticamente.")

# Permite editar unicamente la columna Valor Equipo (€)
df_edited = st.data_editor(
    df_base,
    column_config={
        "ID": None, # Ocultar columna ID
        "Usuario": st.column_config.TextColumn("Usuario", disabled=True),
        "Valor Equipo (€)": st.column_config.NumberColumn(
            "Valor Equipo (€)",
            min_value=0,
            step=100000,
            format="%d €"
        )
    },
    hide_index=True,
    use_container_width=True
)

# Recálculo dinámico en tiempo real
df_edited["Dinero en Caja (€)"] = initial_budget - df_edited["Valor Equipo (€)"]
df_edited["Valor Total (€)"] = df_edited["Dinero en Caja (€)"] + df_edited["Valor Equipo (€)"]
df_edited["Puja Máxima (€)"] = df_edited["Dinero en Caja (€)"] + (0.25 * df_edited["Valor Equipo (€)"])

# Reordenar columnas para la visualización final
df_final = df_edited[["Usuario", "Valor Equipo (€)", "Dinero en Caja (€)", "Valor Total (€)", "Puja Máxima (€)"]]

# Formatear valores numéricos
styler = df_final.style.format({
    "Valor Equipo (€)": lambda x: f"{x:,.0f} €".replace(",", "."),
    "Dinero en Caja (€)": lambda x: f"{x:,.0f} €".replace(",", "."),
    "Valor Total (€)": lambda x: f"{x:,.0f} €".replace(",", "."),
    "Puja Máxima (€)": lambda x: f"{x:,.0f} €".replace(",", ".")
})

st.write("#### 📊 Resultado Financiero y Pujas Máximas")
st.dataframe(styler, use_container_width=True, hide_index=True)
