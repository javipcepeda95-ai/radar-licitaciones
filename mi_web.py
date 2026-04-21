import streamlit as st
import feedparser
import unicodedata
import pandas as pd
from datetime import datetime, timedelta
import json
import os
import re
import io

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Radar Pro Anerpro", page_icon="🤖", layout="wide")

# --- TRUCO CSS "ARTILLERÍA PESADA" ---
st.markdown(
    """
    <style>
        /* 1. Eliminamos el espacio superior de Streamlit */
        [data-testid="stSidebarNav"] {display: none !important;}
        
        /* 2. Forzamos la barra lateral a ocupar toda la pantalla */
        section[data-testid="stSidebar"] .st-emotion-cache-6qob1r {
            padding-top: 0rem !important;
        }

        /* 3. El contenedor principal de la sidebar se convierte en un Flexbox */
        [data-testid="stSidebarUserContent"] > div:first-child {
            display: flex !important;
            flex-direction: column !important;
            /* Calculamos la altura restando los márgenes internos */
            min-height: calc(100vh - 40px) !important;
        }

        /* 4. Ajuste del Logo para que suba al límite */
        [data-testid="stSidebar"] img {
            margin-top: -45px !important;
            margin-bottom: 0px !important;
        }

        /* 5. EL TRUCO DEFINITIVO: 
           Targeteamos el último contenedor de bloque vertical y le damos margen auto arriba */
        [data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] > div:last-child {
            margin-top: auto !important;
            padding-bottom: 10px !important;
        }
        
        /* Estilo de botones para que sean uniformes */
        .stButton button {
            width: 100%;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 2. SISTEMA DE SEGURIDAD (Login) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    
    st.title("🔒 Acceso Corporativo")
    password_input = st.text_input("Contraseña:", type="password")
    if st.button("Entrar"):
        if password_input == st.secrets["PASSWORD_WEB"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else: st.error("⚠️ Contraseña incorrecta")
    return False

if check_password():
    # --- 3. CONFIGURACIÓN ---
    URL_FEED = "https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"
    ARCHIVO_HISTORIAL = "historial_licitaciones.json"
    DIAS_RETENCION = 5
    
    KEYWORDS = ["energia", "nuclear", "hidrogeno", "eficiencia", "energetica", "energética", "cae", "biomasa", "biogas", "edar", "tratamiento", "agua", "automatizacion", "industria 4.0", "scada", "certificado", "autoconsumo", "plc", "desalinizacion", "desaladora", "ciclo del agua", "telecontrol", "digitalizacion industrial", "gemelo digital", "auditoria energetica"]

    def normalizar_texto(texto):
        if not texto: return ""
        return ''.join(c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn')

    def formatear_moneda_es(valor_str):
        if not valor_str or "Ver en PDF" in str(valor_str): return valor_str
        try:
            limpio = "".join(c for c in str(valor_str) if c.isdigit() or c in ".,")
            if "." in limpio and "," in limpio:
                limpio = limpio.replace(".", "").replace(",", ".")
            elif "," in limpio:
                limpio = limpio.replace(",", ".")
            numero = float(limpio)
            return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"
        except: return valor_str

    def extraer_presupuesto(texto):
        if not texto: return "Ver en PDF"
        texto_l = re.sub(r'<[^>]*>', ' ', texto)
        patrones = [
            r"(?:Importe|Importe neto|Valor estimado|PVP):\s*([\d\.]+(?:,\d{1,2})?)",
            r"([\d\.]+(?:\d{3})?,\d{2})\s*(?:EUR|€|Euros)",
            r"([\d\.]+(?:\d{3})?)\s*(?:EUR|€|Euros)"
        ]
        for p in patrones:
            match = re.search(p, texto_l, re.I)
            if match: return formatear_moneda_es(match.group(1).strip())
        return "Ver en PDF"

    def cargar_y_limpiar_historial():
        if os.path.exists(ARCHIVO_HISTORIAL):
            with open(ARCHIVO_HISTORIAL, 'r', encoding='utf-8') as f:
                try: datos = json.load(f)
                except: return []
            f_limite = datetime.now() - timedelta(days=DIAS_RETENCION)
            datos_l = []
            for item in datos:
                try:
                    f_str = item.get("Detectado el") or item.get("Detectado")
                    f_item = datetime.strptime(str(f_str), "%Y-%m-%d %H:%M:%S") if "-" in str(f_str) else datetime.strptime(str(f_str), "%d/%m/%Y %H:%M")
                    if f_item >= f_limite:
                        if "Presupuesto" in item: item["Presupuesto"] = formatear_moneda_es(item["Presupuesto"])
                        datos_l.append(item)
                except: pass
            return datos_l
        return []

    def guardar_en_historial(nuevas_ofertas):
        historial_actual = cargar_y_limpiar_historial()
        enlaces_vistos = {o["Enlace Oficial"] for o in historial_actual}
        añadidas = 0
        for o in nuevas_ofertas:
            if o["Enlace Oficial"] not in enlaces_vistos:
                o["Detectado el"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                historial_actual.append(o)
                añadidas += 1
        if añadidas > 0:
            with open(ARCHIVO_HISTORIAL, 'w', encoding='utf-8') as f:
                json.dump(historial_actual, f, indent=4, ensure_ascii=False)
        return historial_actual, añadidas

    # --- 4. BARRA LATERAL ---
    with st.sidebar:
        # LOGO (Arriba del todo)
        if os.path.exists("logo.png"):
            st.image("logo.png", width=130)
        
        st.divider()
        
        # SECCIÓN MEDIA
        st.caption("⚙️ Mantenimiento")
        if st.button("Vaciar Memoria (Reset)"):
            if os.path.exists(ARCHIVO_HISTORIAL):
                os.remove(ARCHIVO_HISTORIAL)
                st.rerun()
        
        # BOTÓN CERRAR SESIÓN 
        # Al ser el último elemento del bloque sidebar, el CSS lo empujará al fondo
        if st.button("Cerrar Sesión"):
            st.session_state["password_correct"] = False
            st.rerun()

    # --- 5. CUERPO PRINCIPAL ---
    st.title("Radar de Licitaciones 🏢")
    tab1, tab2 = st.tabs(["🔍 Buscar Nuevas", "📁 Archivo e Informes"])
    columnas_ver = ["Publicado", "Organismo", "Título", "Presupuesto", "Palabras Detectadas", "Enlace Oficial"]

    with tab1:
        if st.button("Actualizar y Buscar Ahora", type="primary"):
            with st.spinner('Escaneando plataforma...'):
                feed = feedparser.parse(URL_FEED)
                encontradas = []
                for e in feed.entries:
                    res = e.summary if 'summary' in e else ""
                    txt = normalizar_texto(e.title + " " + res)
                    coin = sorted(list(set([k.upper() for k in KEYWORDS if normalizar_texto(k) in txt])))
                    if coin:
                        org = "No detectado"
                        m = re.search(r"(?:Órgano de Contratación|Organo de Contratacion):\s*(.*?)(?:;|\n|\||<|$)", res, re.I | re.S)
                        if m: org = m.group(1).strip()
                        elif e.get('author'): org = e.author
                        try: f_pub = datetime(*e.published_parsed[:3]).strftime("%d/%m/%Y")
                        except: f_pub = datetime.now().strftime("%d/%m/%Y")
                        encontradas.append({"Publicado": f_pub, "Organismo": org, "Título": e.title, "Presupuesto": extraer_presupuesto(res), "Palabras Detectadas": ", ".join(coin), "Enlace Oficial": e.link})

            historial, nuevas = guardar_en_historial(encontradas)
            if nuevas > 0:
                st.success(f"¡Detectadas {nuevas} nuevas!")
                df = pd.DataFrame(historial[-nuevas:])
                st.dataframe(df[columnas_ver], column_config={"Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace")}, hide_index=True, use_container_width=True)
            else: st.info("No hay novedades.")

    with tab2:
        historial = cargar_y_limpiar_historial()
        if historial:
            df_hist = pd.DataFrame(list(reversed(historial)))
            busq = st.text_input("Buscar en el historial:")
            if busq: df_hist = df_hist[df_hist.apply(lambda r: busq.lower() in r.astype(str).str.lower().str.cat(), axis=1)]
            st.dataframe(df_hist[columnas_ver], column_config={"Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace")}, hide_index=True, use_container_width=True)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_hist[columnas_ver].to_excel(writer, index=False, sheet_name='Licitaciones')
            st.download_button(label="📥 Descargar Excel", data=buffer.getvalue(), file_name="informe.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
