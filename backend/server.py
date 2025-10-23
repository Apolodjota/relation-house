"""
RelatioConstruct Backend
Servidor Flask que conecta el frontend con la API de Gemini
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from datetime import datetime
import requests  # Para fallback si es necesario

# Importar la biblioteca genai para la API de Google
try:
    from google import genai
    GENAI_AVAILABLE = True
    print("[INFO] Biblioteca genai importada correctamente")
except ImportError:
    GENAI_AVAILABLE = False
    print("[WARN] No se pudo importar la biblioteca genai. Por favor instala con: pip install google-generativeai")

app = Flask(__name__)
CORS(app)  # Habilitar CORS para permitir peticiones desde el frontend

# ==========================================
# CONFIGURACIÓN
# ==========================================
DATA_FILE = 'data/entries.json'
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'AIzaSyB0dTWRCRrwzfhFOERaYsUS4i3eK596GfI')

# Configurar el cliente de Gemini
genai_client = None
if GENAI_AVAILABLE:
    try:
        # Configurar la API key para el cliente
        genai.configure(api_key=GEMINI_API_KEY)
        # Crear el cliente
        genai_client = genai.Client()
        print("[INFO] Cliente genai inicializado exitosamente")
    except Exception as e:
        print(f"[ERROR] No se pudo inicializar el cliente genai: {str(e)}")

# Prompt compacto (se inyecta la entrada del usuario dentro de call_gemini_api)
SHORT_PROMPT = (
    "Eres 'El Arquitecto', un agente empático que analiza una interacción de pareja. "
    "Analiza el siguiente texto y responde SOLO con un JSON con estas claves: "
    "pilar_detectado, magnitud_impacto, es_constructivo, insight_arquitecto, consejo_profesional, accion_visual_sugerida. "
    "Para pilar_detectado usa EXACTAMENTE UNO de: Comunicación, Confianza, Respeto, Intimidad, Compromiso. "
    "Para magnitud_impacto usa: positiva_grande/positiva_media/positiva_pequeña/neutral/negativa_pequeña/negativa_media/negativa_grande. "
    "Para es_constructivo usa true si la interacción fortalece la relación, false si la debilita. "
    "Para insight_arquitecto escribe una frase metafórica relacionada con construcción. "
    "Para consejo_profesional da un consejo breve pero específico (3-5 frases) sobre la situación. "
    "Para accion_visual_sugerida, si es positivo usa: construir_cimiento, construir_pared, construir_techo, "
    "pintar_pared, añadir_ventana, plantar_flor, añadir_luz, expandir_casa. "
    "Si es negativo usa: dañar_cimiento, añadir_grieta_pared, romper_ventana, despintar_pared, crear_maleza, apagar_luz, retroceder_nivel."
)

# ==========================================
# FUNCIONES AUXILIARES
# ==========================================

def ensure_data_directory():
    """Crea el directorio de datos si no existe"""
    os.makedirs('data', exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w') as f:
            json.dump([], f)

def load_entries():
    """Carga todas las entradas del archivo JSON"""
    ensure_data_directory()
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_entry(entry):
    """Guarda una nueva entrada"""
    entries = load_entries()
    entries.append(entry)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

def call_gemini_api(texto_entrada):
    """
    Llama a la API de Gemini usando el cliente genai oficial
    """
    # Construir el prompt completo con la entrada del usuario
    prompt_completo = f"{SHORT_PROMPT}\n\nTexto a analizar: \"{texto_entrada}\"\n\nRESPONDE SOLO CON EL JSON SOLICITADO."
    
    # Intentar usar el cliente genai si está disponible
    if genai_client:
        try:
            print(f"[LOG] Llamando a Gemini API con cliente genai...")
            
            # Configurar los parámetros de generación
            generation_config = {
                "temperature": 0.2,
                "max_output_tokens": 800,
                "top_p": 0.95,
                "top_k": 40
            }
            
            # Llamar a la API con el cliente genai
            response = genai_client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=prompt_completo,
                generation_config=generation_config
            )
            
            # Extraer el texto de respuesta
            text_response = response.text
            print(f"[LOG] Respuesta recibida de Gemini API")
            
            # Limpiar el texto (remover markdown si existe)
            text_response = text_response.strip()
            if text_response.startswith('```json'):
                text_response = text_response[7:]
            elif text_response.startswith('```'):
                text_response = text_response[3:]
            if text_response.endswith('```'):
                text_response = text_response[:-3]
            text_response = text_response.strip()
            
            print(f"[LOG] Texto limpio: {text_response[:100]}...")
            
            # Parsear como JSON
            architect_response = json.loads(text_response)
            print(f"[LOG] JSON parseado correctamente")
            
            # Asegurar que es_constructivo sea booleano
            if "es_constructivo" in architect_response and isinstance(architect_response["es_constructivo"], str):
                architect_response["es_constructivo"] = architect_response["es_constructivo"].lower() == "true"
            
            return architect_response
        
        except Exception as e:
            print(f"[ERROR] Error con cliente genai: {str(e)}")
            print("[INFO] Intentando con fallback...")
            return get_fallback_response(texto_entrada)
    else:
        # Si no hay cliente genai disponible, usar el fallback
        print("[WARN] Cliente genai no disponible, usando fallback")
        return get_fallback_response(texto_entrada)

def get_fallback_response(texto_entrada):
    """
    Respuesta de emergencia si Gemini falla
    Análisis básico por palabras clave + consejo genérico
    """
    texto_lower = texto_entrada.lower()
    
    # Detección mejorada de pilares
    comunicacion_keywords = ['hablar', 'conversar', 'dije', 'escuchar', 'expresar', 'comunicar', 'comentar', 'decir']
    confianza_keywords = ['confiar', 'mentir', 'secreto', 'honesto', 'celular', 'revisar', 'celos', 'amiga', 'amigo']
    respeto_keywords = ['respetar', 'valorar', 'apreciar', 'insultar', 'gritar', 'espacio', 'entendió', 'entender']
    intimidad_keywords = ['abrazo', 'beso', 'íntimo', 'cercano', 'romántico', 'cariño', 'sexo', 'fotos']
    compromiso_keywords = ['futuro', 'planear', 'juntos', 'familia', 'proyecto', 'relación', 'compromiso', 'serio']
    
    # Contar coincidencias
    comunicacion_count = sum(1 for word in comunicacion_keywords if word in texto_lower)
    confianza_count = sum(1 for word in confianza_keywords if word in texto_lower)
    respeto_count = sum(1 for word in respeto_keywords if word in texto_lower)
    intimidad_count = sum(1 for word in intimidad_keywords if word in texto_lower)
    compromiso_count = sum(1 for word in compromiso_keywords if word in texto_lower)
    
    # Determinar pilar
    pilar_counts = {
        'Comunicación': comunicacion_count,
        'Confianza': confianza_count,
        'Respeto': respeto_count,
        'Intimidad': intimidad_count,
        'Compromiso': compromiso_count
    }
    
    pilar = max(pilar_counts, key=pilar_counts.get)
    
    # Detectar si es negativo
    palabras_negativas = ['pelea', 'discutir', 'enojado', 'mal', 'problema', 'mentir', 'insultar', 'celos']
    palabras_positivas = ['bien', 'amor', 'feliz', 'entendió', 'acuerdo', 'alegre', 'apoyó', 'juntos', 'compartir']
    
    negativos_count = sum(1 for word in palabras_negativas if word in texto_lower)
    positivos_count = sum(1 for word in palabras_positivas if word in texto_lower)
    
    es_constructivo = positivos_count >= negativos_count
    
    # Determinar acción visual
    acciones = {
        'Comunicación': 'construir_pared' if es_constructivo else 'añadir_grieta_pared',
        'Confianza': 'construir_cimiento' if es_constructivo else 'dañar_cimiento',
        'Respeto': 'añadir_ventana' if es_constructivo else 'romper_ventana',
        'Intimidad': 'añadir_luz' if es_constructivo else 'apagar_luz',
        'Compromiso': 'construir_techo' if es_constructivo else 'retroceder_nivel'
    }
    
    accion = acciones[pilar]
    magnitud = 'positiva_media' if es_constructivo else 'negativa_media'
    
    # Insights por pilar
    insights = {
        'Comunicación': "Las palabras que han intercambiado construyen paredes fuertes que dan estructura a su hogar.",
        'Confianza': "La confianza es el cimiento sobre el que se edifican las relaciones duraderas.",
        'Respeto': "El respeto mutuo abre ventanas para que circule aire fresco en la relación.",
        'Intimidad': "Han encendido una luz cálida que ilumina los rincones más personales de su relación.",
        'Compromiso': "Están construyendo un techo sólido que protegerá su relación en días de tormenta."
    }
    
    if not es_constructivo:
        insights = {
            'Comunicación': "Han aparecido grietas en las paredes de su comunicación que necesitan reparación.",
            'Confianza': "Los cimientos de confianza se han debilitado y requieren refuerzo inmediato.",
            'Respeto': "Se han roto ventanas importantes en su estructura de respeto mutuo.",
            'Intimidad': "La luz que iluminaba su conexión íntima se ha atenuado considerablemente.",
            'Compromiso': "El techo de su compromiso tiene goteras que deben ser reparadas."
        }
    
    consejos = {
        'Comunicación': "Hablar abiertamente sobre necesidades y expectativas fortalece su conexión. Practica la escucha activa, verificando que entiendes lo que tu pareja quiere transmitir. Recuerda que comunicar no es solo hablar, sino asegurarse de ser comprendido.",
        'Confianza': "La confianza se construye con consistencia en palabras y acciones. Sé transparente sobre tus sentimientos y preocupaciones. Si hay dudas, abórdalas directamente en vez de dejar que crezcan.",
        'Respeto': "El respeto significa valorar las diferencias y respetar límites personales. Aprende a discutir sin atacar el carácter de tu pareja. Las palabras hirientes dejan cicatrices duraderas.",
        'Intimidad': "La intimidad va más allá de lo físico; incluye vulnerabilidad emocional compartida. Dediquen tiempo a conexiones cotidianas significativas. A veces una mirada sincera vale más que grandes gestos.",
        'Compromiso': "El compromiso es una decisión diaria de priorizar la relación. Construyan rituales compartidos que fortalezcan su vínculo. Las pequeñas promesas cumplidas refuerzan la confianza en el futuro conjunto."
    }
    
    insight = insights[pilar]
    consejo = consejos[pilar]
    
    return {
        "pilar_detectado": pilar,
        "magnitud_impacto": magnitud,
        "es_constructivo": es_constructivo,
        "insight_arquitecto": insight,
        "consejo_profesional": consejo,
        "accion_visual_sugerida": accion
    }

# ==========================================
# RUTAS DE LA API
# ==========================================

@app.route('/', methods=['GET'])
def home():
    """Ruta raíz - información del API"""
    return jsonify({
        "nombre": "RelatioConstruct API",
        "version": "3.0",
        "descripcion": "Backend para el diario de relación metafórico con Gemini",
        "endpoints": {
            "POST /api/entry": "Registrar nueva entrada",
            "GET /api/entries": "Obtener todas las entradas",
            "DELETE /api/entries": "Limpiar historial"
        },
        "gemini_status": "✓ Configurado" if GEMINI_API_KEY else "✗ Sin configurar"
    })

@app.route('/api/entry', methods=['POST'])
def create_entry():
    """
    Endpoint para registrar una nueva entrada
    Espera: { "texto_entrada": "..." }
    Retorna: { "insight_arquitecto": "...", "consejo_profesional": "...", "accion_visual_sugerida": "...", ... }
    """
    try:
        data = request.get_json()
        
        if not data or 'texto_entrada' not in data:
            return jsonify({
                "error": "Falta el campo 'texto_entrada'"
            }), 400
        
        texto_entrada = data['texto_entrada'].strip()
        
        if not texto_entrada:
            return jsonify({
                "error": "El texto de entrada no puede estar vacío"
            }), 400
        
        # Llamar a Gemini
        print(f"\n[LOG] ====== NUEVA ENTRADA ======")
        print(f"[LOG] Texto: {texto_entrada[:100]}...")
        architect_response = call_gemini_api(texto_entrada)
        
        print(f"[LOG] Pilar detectado: {architect_response.get('pilar_detectado')}")
        print(f"[LOG] Es constructivo: {architect_response.get('es_constructivo')}")
        print(f"[LOG] Acción: {architect_response.get('accion_visual_sugerida')}")
        print(f"[LOG] ============================\n")
        
        # Crear registro completo
        entry = {
            "timestamp": datetime.now().isoformat(),
            "texto_entrada": texto_entrada,
            "pilar_detectado": architect_response.get('pilar_detectado', 'Desconocido'),
            "magnitud_impacto": architect_response.get('magnitud_impacto', 'neutral'),
            "es_constructivo": architect_response.get('es_constructivo', True),
            "insight_arquitecto": architect_response.get('insight_arquitecto', 'Registro procesado.'),
            "consejo_profesional": architect_response.get('consejo_profesional', 'Reflexiona sobre esta experiencia.'),
            "accion_visual_sugerida": architect_response.get('accion_visual_sugerida', 'construir_pared')
        }
        
        # Guardar en la base de datos
        save_entry(entry)
        
        # Retornar respuesta al frontend
        return jsonify(entry), 200
        
    except Exception as e:
        print(f"[ERROR] Error en create_entry: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": "Error interno del servidor",
            "detalle": str(e)
        }), 500

@app.route('/api/entries', methods=['GET'])
def get_entries():
    """Endpoint para obtener todas las entradas guardadas"""
    try:
        entries = load_entries()
        return jsonify(entries), 200
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return jsonify({
            "error": "Error al cargar entradas",
            "detalle": str(e)
        }), 500

@app.route('/api/entries', methods=['DELETE'])
def clear_entries():
    """Endpoint para limpiar todas las entradas"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)
        return jsonify({
            "mensaje": "Todas las entradas han sido eliminadas"
        }), 200
    except Exception as e:
        return jsonify({
            "error": "Error al limpiar entradas",
            "detalle": str(e)
        }), 500

# ==========================================
# PUNTO DE ENTRADA
# ==========================================

if __name__ == '__main__':
    ensure_data_directory()
    print("=" * 60)
    print("🏗️  RelatioConstruct Backend v3.0")
    print("=" * 60)
    print(f"✓ Gemini API configurada")
    print(f"✓ API Key: {GEMINI_API_KEY[:20]}...{GEMINI_API_KEY[-4:]}")
    print(f"✓ Archivo de datos: {DATA_FILE}")
    print(f"✓ Servidor corriendo en: http://localhost:5000")
    print("=" * 60)
    print("\nEndpoints disponibles:")
    print("  POST   /api/entry     - Registrar nueva entrada")
    print("  GET    /api/entries   - Obtener historial completo")
    print("  DELETE /api/entries   - Limpiar historial (testing)")
    print("\n🤖 El Arquitecto (Gemini) está listo para asesorar.\n")
    print("=" * 60)
    print()
    
    app.run(debug=True, host='0.0.0.0', port=5000)