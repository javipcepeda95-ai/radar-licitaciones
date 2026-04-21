import streamlit as st
import feedparser
import unicodedata
import pandas as pd
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Radar de Licitaciones", page_icon="🤖", layout="wide")

URL_FEED = "https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"
KEYWORDS = [
    "energia", "nuclear", "hidrogeno", "eficiencia", "energetica", "cae", 
    "biomasa", "biogas", "edar", "tratamiento", "agua", "automatizacion", 
    "industria 4.0", "scada", "certificado", "autoconsumo", "fotovoltaica", 
    "paneles", "plc"
]

def normalizar_texto(texto):
    if not texto: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto.lower()) if unicodedata.category(c) != 'Mn')

# --- INTERFAZ WEB ---
st.title("Radar de Licitaciones 🏢")
st.write("Pulsa el botón para conectar con la Plataforma del Estado y buscar nuevas oportunidades.")

# EL BOTÓN MÁGICO
if st.button("Buscar Nuevas Licitaciones Ahora", type="primary"):
    
    with st.spinner('Conectando con el Estado y leyendo expedientes...'):
        feed = feedparser.parse(URL_FEED)
        keywords_norm = [normalizar_texto(k) for k in KEYWORDS]
        
        ofertas_encontradas = []

        # Filtrar
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

    # --- MOSTRAR RESULTADOS ---
    st.success(f"¡Búsqueda completada a las {datetime.now().strftime('%H:%M:%S')}!")
    
    if ofertas_encontradas:
        st.metric(label="Ofertas Interesantes Encontradas", value=len(ofertas_encontradas))
        
        # Convertir a una tabla interactiva de datos
        df = pd.DataFrame(ofertas_encontradas)
        
        # Mostrar la tabla en la web (permite ordenar y hacer clic en enlaces)
        st.dataframe(
            df,
            column_config={
                "Enlace Oficial": st.column_config.LinkColumn("Enlace al PDF")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No se han encontrado licitaciones con esas palabras clave en este momento.")
