import streamlit as st
import feedparser
import unicodedata
import pandas as pd
from datetime import datetime, timedelta
import json
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Radar de Licitaciones", page_icon="🤖", layout="wide")

URL_FEED = "https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"
ARCHIVO_HISTORIAL = "historial_licitaciones.json"
DIAS_RETENCION = 5

KEYWORDS = [
    "energia", "nuclear", "hidrogeno", "eficiencia", "energetica", "cae", 
    "biomasa", "biogas", "edar", "tratamiento", "agua", "automatizacion", 
    "industria 4.0", "scada", "certificado", "autoconsumo", "fotovoltaica", 
    "paneles", "plc"
]

def normalizar_texto(texto):
    if not texto: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn')

# --- LÓGICA DE MEMORIA (HISTORIAL) ---
def cargar_y_limpiar_historial():
    """Carga el historial y borra automáticamente lo que tenga más de 5 días."""
    if os.path.exists(ARCHIVO_HISTORIAL):
        with open(ARCHIVO_HISTORIAL, 'r', encoding='utf-8') as f:
            try:
                datos = json.load(f)
            except:
                return []
        
        datos_limpios = []
        fecha_limite = datetime.now() - timedelta(days=DIAS_RETENCION)
        
        for item in datos:
            try:
                fecha_item = datetime.strptime(item.get("Fecha Captura", ""), "%d/%m/%Y %H:%M")
                if fecha_item >= fecha_limite:
                    datos_limpios.append(item)
            except ValueError:
                pass
                
        with open(ARCHIVO_HISTORIAL, 'w', encoding='utf-8') as f:
            json.dump(datos_limpios, f, indent=4, ensure_ascii=False)
            
        return datos_limpios
    return []

def guardar_en_historial(nuevas_ofertas):
    """Añade ofertas nuevas al historial sin duplicar."""
    historial_actual = cargar_y_limpiar_historial()
    enlaces_vistos = {oferta["Enlace Oficial"] for oferta in historial_actual}
    
    añadidas = 0
    for oferta in nuevas_ofertas:
        if oferta["Enlace Oficial"] not in enlaces_vistos:
            oferta["Fecha Captura"] = datetime.now().strftime("%d/%m/%Y %H:%M")
            historial_actual.append(oferta)
            añadidas += 1
            
    if añadidas > 0:
        with open(ARCHIVO_HISTORIAL, 'w', encoding='utf-8') as f:
            json.dump(historial_actual, f, indent=4, ensure_ascii=False)
            
    return historial_actual, añadidas

# --- INTERFAZ WEB ---
st.title("Radar de Licitaciones 🏢")
st.write("Herramienta de filtrado inteligente para la Plataforma de Contratación del Estado.")

tab1, tab2 = st.tabs(["🔍 Buscar Nuevas", "📁 Archivo (5 días)"])

# --- PESTAÑA 1: BUSCADOR ---
with tab1:
    if st.button("Actualizar y Buscar", type="primary"):
        with st.spinner('Escaneando la plataforma...'):
            feed = feedparser.parse(URL_FEED)
            ofertas_encontradas = []

            for entrada in feed.entries:
                titulo = entrada.title
                resumen = entrada.summary if 'summary' in entrada else ""
                texto_analizar = normalizar_texto(titulo + " " + resumen)
                
                coincidencias = [kw.upper() for kw in KEYWORDS if normalizar_texto(kw) in texto_analizar]

                if coincidencias:
                    ofertas_encontradas.append({
                        "Título": titulo,
                        "Palabras Detectadas": ", ".join(coincidencias),
                        "Enlace Oficial": entrada.link
                    })

        historial_actualizado, cantidad_nuevas_reales = guardar_en_historial(ofertas_encontradas)

        st.success(f"Búsqueda finalizada a las {datetime.now().strftime('%H:%M:%S')}")
        
        if cantidad_nuevas_reales > 0:
            st.metric(label="Nuevas Licitaciones Detectadas", value=cantidad_nuevas_reales)
            # Mostrar solo las últimas encontradas
            df_nuevas = pd.DataFrame(historial_actualizado[-cantidad_nuevas_reales:])
            st.dataframe(df_nuevas, column_config={"Enlace Oficial": st.column_config.LinkColumn("Enlace al PDF")}, hide_index=True, use_container_width=True)
        else:
            st.info("No hay novedades. Todo lo publicado ya está en tu archivo.")

# --- PESTAÑA 2: ARCHIVO ---
with tab2:
    historial = cargar_y_limpiar_historial()
    if historial:
        st.write(f"Mostrando histórico de los últimos {DIAS_RETENCION} días:")
        df_historial = pd.DataFrame(list(reversed(historial)))
        st.dataframe(
            df_historial, 
            column_config={
                "Enlace Oficial": st.column_config.LinkColumn("Enlace al PDF"),
                "Fecha Captura": st.column_config.DatetimeColumn("Detectado el", format="DD/MM/YYYY HH:mm")
            }, 
            hide_index=True, 
            use_container_width=True
        )
    else:
        st.info("El archivo está vacío.")
