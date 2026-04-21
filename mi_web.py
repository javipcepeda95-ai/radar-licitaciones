import streamlit as st
import feedparser
import unicodedata
import pandas as pd
from datetime import datetime, timedelta
import json
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Radar de Licitaciones", page_icon="🤖", layout="wide")

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True
    st.title("🔒 Acceso Restringido")
    password_input = st.text_input("Introduce la contraseña para acceder:", type="password")
    if st.button("Entrar"):
        if password_input == st.secrets["PASSWORD_WEB"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("⚠️ Contraseña incorrecta")
    return False

if check_password():
    URL_FEED = "https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"
    ARCHIVO_HISTORIAL = "historial_licitaciones.json"
    DIAS_RETENCION = 5
    
    KEYWORDS = [
        "energia", "nuclear", "hidrogeno", "eficiencia", "energetica", "energética", "cae", 
        "biomasa", "biogas", "edar", "tratamiento", "agua", "automatizacion", 
        "industria 4.0", "scada", "certificado", "autoconsumo", "plc", 
        "desalinizacion", "desaladora", "ciclo del agua", "telecontrol", 
        "digitalizacion industrial", "gemelo digital", "auditoria energetica"
    ]

    def normalizar_texto(texto):
        if not texto: return ""
        return ''.join(c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn')

    def cargar_y_limpiar_historial():
        if os.path.exists(ARCHIVO_HISTORIAL):
            with open(ARCHIVO_HISTORIAL, 'r', encoding='utf-8') as f:
                try: datos = json.load(f)
                except: return []
            fecha_limite = datetime.now() - timedelta(days=DIAS_RETENCION)
            datos_limpios = []
            for item in datos:
                try:
                    fecha_str = item.get("Detectado el") or item.get("Detectado")
                    if "-" in str(fecha_str):
                        fecha_item = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S")
                    else:
                        fecha_item = datetime.strptime(fecha_str, "%d/%m/%Y %H:%M")
                    if fecha_item >= fecha_limite:
                        datos_limpios.append(item)
                except: pass
            return datos_limpios
        return []

    def guardar_en_historial(nuevas_ofertas):
        historial_actual = cargar_y_limpiar_historial()
        enlaces_vistos = {oferta["Enlace Oficial"] for oferta in historial_actual}
        añadidas = 0
        for oferta in nuevas_ofertas:
            if oferta["Enlace Oficial"] not in enlaces_vistos:
                oferta["Detectado el"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                historial_actual.append(oferta)
                añadidas += 1
        with open(ARCHIVO_HISTORIAL, 'w', encoding='utf-8') as f:
            json.dump(historial_actual, f, indent=4, ensure_ascii=False)
        return historial_actual, añadidas

    # --- INTERFAZ ---
    with st.sidebar:
        st.header("Opciones")
        if st.button("Cerrar Sesión"):
            st.session_state["password_correct"] = False
            st.rerun()
        st.divider()
        if st.button("Vaciar Memoria (Reset)"):
            if os.path.exists(ARCHIVO_HISTORIAL):
                os.remove(ARCHIVO_HISTORIAL)
                st.rerun()

    st.title("Radar de Licitaciones 🏢")
    tab1, tab2 = st.tabs(["🔍 Buscar Nuevas", "📁 Archivo (5 días)"])

    with tab1:
        if st.button("Actualizar y Buscar", type="primary"):
            with st.spinner('Escaneando plataforma...'):
                feed = feedparser.parse(URL_FEED)
                ofertas_encontradas = []
                for entrada in feed.entries:
                    texto_completo = normalizar_texto(entrada.title + " " + (entrada.summary if 'summary' in entrada else ""))
                    coincidencias = [kw.upper() for kw in KEYWORDS if normalizar_texto(kw) in texto_completo]
                    
                    if coincidencias:
                        # LOGICA MEJORADA PARA EL ORGANISMO
                        organismo = "Desconocido"
                        if 'author_detail' in entrada and 'name' in entrada.author_detail:
                            organismo = entrada.author_detail.name
                        elif 'author' in entrada:
                            organismo = entrada.author
                        
                        try: fecha_pub = datetime(*entrada.published_parsed[:3]).strftime("%d/%m/%Y")
                        except: fecha_pub = datetime.now().strftime("%d/%m/%Y")

                        ofertas_encontradas.append({
                            "Publicado": fecha_pub, 
                            "Organismo": organismo,
                            "Título": entrada.title, 
                            "Palabras Detectadas": ", ".join(list(set(coincidencias))), 
                            "Enlace Oficial": entrada.link
                        })

            historial, nuevas = guardar_en_historial(ofertas_encontradas)
            if nuevas > 0:
                st.success(f"¡Detectadas {nuevas} nuevas!")
                df_nuevas = pd.DataFrame(historial[-nuevas:])
                columnas = ["Publicado", "Organismo", "Título", "Palabras Detectadas", "Enlace Oficial"]
                st.dataframe(df_nuevas[columnas], column_config={"Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace")}, hide_index=True, use_container_width=True)
            else:
                st.info("No hay novedades.")

    with tab2:
        historial = cargar_y_limpiar_historial()
        if historial:
            df_historial = pd.DataFrame(list(reversed(historial)))
            columnas_ver = ["Publicado", "Organismo", "Título", "Palabras Detectadas", "Enlace Oficial"]
            # Asegurar columnas
            for c in columnas_ver: 
                if c not in df_historial.columns: df_historial[c] = "N/A"
            st.dataframe(df_historial[columnas_ver], column_config={"Enlace Oficial": st.column_config.LinkColumn("PDF", display_text="Ver Enlace")}, hide_index=True, use_container_width=True)
        else:
            st.info("Archivo vacío.")
