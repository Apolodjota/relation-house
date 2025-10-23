"""
RelatioConstruct Backend
Servidor Flask que conecta el frontend con la API de Gemini
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from datetime import datetime
import requests

app = Flask(__name__)
CORS(app)  # Habilitar CORS para permitir peticiones desde el frontend

# ==========================================
# CONFIGURACIÓN
# ==========================================
DATA_FILE = 'data/entries.json'
GEMINI_API_KEY = os.environ.get('AIzaSyB0dTWRCRrwzfhFOERaYsUS4i3eK596GfI', 'TU_API_KEY_AQUI')
GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent'

# System Prompt para Gemini
SYSTEM_PROMPT = """
ERES "El Arquitecto", un agente de IA sabio, empático y metafórico. Tu rol es ser el constructor principal de la "casa" que representa la relación de pareja del usuario. El usuario solo te dará un aporte en texto libre.

TU OBJETIVO:
1. Identificar el pilar fundamental de la relación al que se refiere el usuario.
2. Interpretar el impacto de ese aporte (positivo, negativo, magnitud).
3. Traducir ese impacto en una acción de construcción o reparación para su casa metafórica.

CONTEXTO DE LA METÁFORA:
- La "Casa" = La relación de pareja.
- Los 5 Pilares:
  - "Cimientos" = Confianza.
  - "Paredes" / "Estructura" = Comunicación.
  - "Techo" / "Marco" = Compromiso.
  - "Interior" / "Decoración" = Intimidad.
  - "Puertas" / "Accesos" = Respeto.
- Aportes Positivos = Construyen, mejoran, añaden color, expanden la casa, cuidan el jardín.
- Aportes Negativos = Causan grietas, rompen ventanas, desvanecen el color, crean malas hierbas, dañan cimientos.

ENTRADA DEL USUARIO:
Recibirás un objeto JSON con una sola clave:
{
  "texto_entrada": "La descripción del usuario de un evento."
}

TAREA OBLIGATORIA:
Analiza la entrada y responde *únicamente* con un objeto JSON válido. No incluyas "```json" ni ningún texto explicativo fuera del JSON. La estructura debe ser:

{
  "pilar_detectado": "string",
  "magnitud_impacto": "string",
  "insight_arquitecto": "string",
  "accion_visual_sugerida": "string"
}

REGLAS PARA LAS CLAVES DE RESPUESTA:

1. "pilar_detectado":
   - Deduce y clasifica la entrada. Debes usar *exactamente* una de estas 5 cadenas:
   - "Comunicación"
   - "Confianza"
   - "Respeto"
   - "Intimidad"
   - "Compromiso"

2. "magnitud_impacto":
   - Clasifica el impacto. Usa solo uno de estos valores:
   - "positiva_grande" (Ej. compromiso, superar una crisis juntos)
   - "positiva_media" (Ej. gran cita, conversación importante)
   - "positiva_pequeña" (Ej. un buen gesto, apoyo diario)
   - "neutral" (Ej. una observación sin mucho peso)
   - "negativa_pequeña" (Ej. una discusión menor, un malentendido)
   - "negativa_media" (Ej. una mentira, romper la confianza)
   - "negativa_grande" (Ej. una traición, una pelea muy fuerte)

3. "insight_arquitecto":
   - Escribe un comentario (1-2 frases) en tu rol de "Arquitecto".
   - Debe ser empático y metafórico, conectando la entrada con la "casa".
   - (Ej. "Eso es un cimiento sólido.", "Eso ha causado una pequeña grieta en la ventana de la confianza.", "Están pintando las paredes con alegría.")

4. "accion_visual_sugerida":
   - Sugiere un código de acción *simple* para que el frontend lo interprete visualmente.
   - Usa códigos como:
     - Positivos: "construir_cimiento", "construir_pared", "construir_techo", "pintar_pared", "añadir_ventana", "plantar_flor", "añadir_luz", "expandir_casa"
     - Negativos: "añadir_grieta_pared", "romper_ventana", "despintar_pared", "crear_maleza", "apagar_luz", "dañar_cimiento"

EJEMPLOS:

---
ENTRADA EJEMPLO 1:
{
  "texto_entrada": "Le revisé el celular sin que se diera cuenta. No encontré nada pero me siento culpable."
}
RESPUESTA EJEMPLO 1:
{
  "pilar_detectado": "Confianza",
  "magnitud_impacto": "negativa_media",
  "insight_arquitecto": "Revisar sin permiso es un golpe a los cimientos. Aunque no encontraste nada, la acción misma ha creado una fisura en la estructura base de la confianza.",
  "accion_visual_sugerida": "dañar_cimiento"
}
---
ENTRADA EJEMPLO 2:
{
  "texto_entrada": "Hoy por fin decidimos mudarnos juntos y empezamos a ver apartamentos. ¡Qué emoción!"
}
RESPUESTA EJEMPLO 2:
{
  "pilar_detectado": "Compromiso",
  "magnitud_impacto": "positiva_grande",
  "insight_arquitecto": "¡Están construyendo un nuevo piso en su casa! Esta es una expansión mayor, un verdadero acto de compromiso que eleva toda la estructura.",
  "accion_visual_sugerida": "expandir_casa"
}
---
ENTRADA EJEMPLO 3:
{
  "texto_entrada": "Anoche solo vimos una película abrazados y fue perfecto. No necesitábamos más."
}
RESPUESTA EJEMPLO 3:
{
  "pilar_detectado": "Intimidad",
  "magnitud_impacto": "positiva_pequeña",
  "insight_arquitecto": "Esos momentos son la decoración de la casa. Están añadiendo calidez y luz al interior, haciendo que el espacio sea verdaderamente un hogar.",
  "accion_visual_sugerida": "añadir_luz"
}
---
"""

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
    Llama a la API de Gemini con el System Prompt y la entrada del usuario
    Retorna el JSON parseado con la respuesta del Arquitecto
    """
    
    # Construir el prompt completo
    user_message = f'{{"texto_entrada": "{texto_entrada}"}}'
    
    # Payload para Gemini
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": SYSTEM_PROMPT},
                    {"text": user_message}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 500,
            "topP": 0.9,
            "topK": 40
        }
    }
    
    # Hacer la petición
    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Extraer el texto de respuesta
        if 'candidates' in data and len(data['candidates']) > 0:
            text_response = data['candidates'][0]['content']['parts'][0]['text']
            
            # Limpiar el texto (remover markdown si existe)
            text_response = text_response.strip()
            if text_response.startswith('```json'):
                text_response = text_response[7:]
            if text_response.endswith('```'):
                text_response = text_response[:-3]
            text_response = text_response.strip()
            
            # Parsear como JSON
            architect_response = json.loads(text_response)
            return architect_response
        else:
            raise Exception("Respuesta vacía de Gemini")
            
    except requests.exceptions.RequestException as e:
        print(f"Error en petición a Gemini: {e}")
        return get_fallback_response(texto_entrada)
    except json.JSONDecodeError as e:
        print(f"Error parseando JSON de Gemini: {e}")
        return get_fallback_response(texto_entrada)
    except Exception as e:
        print(f"Error general: {e}")
        return get_fallback_response(texto_entrada)

def get_fallback_response(texto_entrada):
    """
    Respuesta de emergencia si Gemini falla
    Análisis básico por palabras clave
    """
    texto_lower = texto_entrada.lower()
    
    # Detección simple de pilar
    if any(word in texto_lower for word in ['hablar', 'conversar', 'dije', 'escuchar', 'expresar']):
        pilar = 'Comunicación'
        accion = 'construir_pared'
    elif any(word in texto_lower for word in ['confiar', 'mentir', 'secreto', 'honesto', 'celular']):
        pilar = 'Confianza'
        accion = 'construir_cimiento' if 'confiar' in texto_lower else 'dañar_cimiento'
    elif any(word in texto_lower for word in ['respetar', 'valorar', 'apreciar', 'admirar']):
        pilar = 'Respeto'
        accion = 'añadir_ventana'
    elif any(word in texto_lower for word in ['abrazo', 'beso', 'íntimo', 'cercano', 'romántico']):
        pilar = 'Intimidad'
        accion = 'añadir_luz'
    else:
        pilar = 'Compromiso'
        accion = 'construir_techo'
    
    # Detección simple de magnitud
    if any(word in texto_lower for word in ['pelea', 'discutir', 'enojado', 'mal', 'problema']):
        magnitud = 'negativa_pequeña'
        accion = 'añadir_grieta_pared'
    else:
        magnitud = 'positiva_media'
    
    return {
        "pilar_detectado": pilar,
        "magnitud_impacto": magnitud,
        "insight_arquitecto": "He registrado tu aporte. Cada experiencia, buena o mala, es parte de la construcción de tu relación.",
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
        "version": "2.0",
        "descripcion": "Backend para el diario de relación metafórico",
        "endpoints": {
            "POST /api/entry": "Registrar nueva entrada",
            "GET /api/entries": "Obtener todas las entradas"
        }
    })

@app.route('/api/entry', methods=['POST'])
def create_entry():
    """
    Endpoint para registrar una nueva entrada
    Espera: { "texto_entrada": "..." }
    Retorna: { "insight_arquitecto": "...", "accion_visual_sugerida": "...", ... }
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
        print(f"[LOG] Procesando entrada: {texto_entrada[:50]}...")
        architect_response = call_gemini_api(texto_entrada)
        print(f"[LOG] Respuesta del Arquitecto: {architect_response}")
        
        # Crear registro completo
        entry = {
            "timestamp": datetime.now().isoformat(),
            "texto_entrada": texto_entrada,
            "pilar_detectado": architect_response.get('pilar_detectado', 'Desconocido'),
            "magnitud_impacto": architect_response.get('magnitud_impacto', 'neutral'),
            "insight_arquitecto": architect_response.get('insight_arquitecto', 'Registro procesado.'),
            "accion_visual_sugerida": architect_response.get('accion_visual_sugerida', 'construir_pared')
        }
        
        # Guardar en la base de datos
        save_entry(entry)
        
        # Retornar respuesta al frontend
        return jsonify({
            "pilar_detectado": entry['pilar_detectado'],
            "magnitud_impacto": entry['magnitud_impacto'],
            "insight_arquitecto": entry['insight_arquitecto'],
            "accion_visual_sugerida": entry['accion_visual_sugerida']
        }), 200
        
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return jsonify({
            "error": "Error interno del servidor",
            "detalle": str(e)
        }), 500

@app.route('/api/entries', methods=['GET'])
def get_entries():
    """
    Endpoint para obtener todas las entradas guardadas
    Retorna: [{ "timestamp": "...", "texto_entrada": "...", ... }, ...]
    """
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
    """
    Endpoint para limpiar todas las entradas (útil para testing)
    """
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
    print("=" * 50)
    print("🏗️  RelatioConstruct Backend")
    print("=" * 50)
    print(f"API Key configurada: {'✓' if GEMINI_API_KEY != 'TU_API_KEY_AQUI' else '✗'}")
    print(f"Archivo de datos: {DATA_FILE}")
    print(f"Servidor corriendo en: http://localhost:5000")
    print("=" * 50)
    print("\nEndpoints disponibles:")
    print("  POST   /api/entry     - Registrar nueva entrada")
    print("  GET    /api/entries   - Obtener historial completo")
    print("  DELETE /api/entries   - Limpiar historial (testing)")
    print("\n⚠️  Recuerda configurar tu API Key de Gemini:")
    print("   export GEMINI_API_KEY='AIzaSyB0dTWRCRrwzfhFOERaYsUS4i3eK596GfI'")
    print("\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)