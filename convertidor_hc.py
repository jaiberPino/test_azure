import os
import google.generativeai as genai
from dotenv import load_dotenv
import json
import requests

#j='{"HC": "Paciente femenina acude a consulta refiriendo molestias relacionadas con gastritis, incluyendo reflujo, dolor de estómago y dolor generalizado desde hace 6 meses. El dolor lo describe con una intensidad de 8 en una escala de 1 a 10. Refiere antecedentes familiares de diabetes (madre fallecida). La paciente sospecha tener azúcar en la sangre debido a mareos después de consumir dulces, aunque no ha sido diagnosticada. Al examen, pesa 90 kg y mide 1.59 m.", "medicamentos": "Naproxeno", "alergia": "Penicilina", "DXS": [{"nombre": "Gastritis", "cie10": "K29"}, {"nombre": "Sospecha de Diabetes Mellitus", "cie10": "R81"}, {"nombre": "Reflujo gastroesofágico", "cie10": "K21"}]}'
# Cargar la API Key desde .env
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

prompt_base_urgencias = """
Eres un asistente médico experto en la generación de historias clínicas a partir de transcripciones de consultas. Tu tarea es analizar el texto de la conversación entre un paciente y un médico, ten en cuenta que hay errores de transcripción trata de corregirlos y luego extraer la información solicitada, basandose solo en lo analizado de la transcripción .
---
**Entrada:**
Recibirás una transcripción de un triage.
---

**Instrucciones:**
1. Analiza la conversación para identificar síntomas, antecedentes, hallazgos clínicos, etc.
2. Genera una historia clínica estructurada profesionalmente como se explica a continuación:
  - Motivo de consulta.
  - Enfermedad actual.
  - Estado de conciencia.
  - Signos vitales.
  - Intensidad del dolor.
  - Escala de Glasgow.
  - Diagnóstico principal.
  - Tipo de triage segun MEWS.
2. Devuelve el resultado como un objeto JSON basandose exactamente en las claves que se indican a continuación:
  * `"MOT_CONSULTA"`: Motivo de consulta del paciente.
  * `"ENF_ACTUAL"`: Descripción y análisis de la enfermedad actual.
  * `"ESTADO_CONCIENCIA"`: Es el estado de conciencia del paciente solo tengo esta opciones: Alerta, Somnoliento, Estuporoso, Coma.
  * `"SIGNOS_VIT"`: Signos vitales del paciente: Presión arterial (string separada por un espacio e.g '120 80'), presion arterial media, pulso, Frecuencia cardiaca, frecuencia respiratoria, sat O2, temperatura, talla (en cm), peso (kl).
  * `"INTENSIDAD"`: Intencidad del dolor de 1 a 10.
  * `"GLASGOW"`: Se divide en: a. Apertura ocular (posibles opciones: Espontánea, Al estimulo verbal. Al recibir un estimulo doloroso. No responde, No evaluable). b. Respuesta verbal (posibles opciones: Orientado, Confuso, Palabras inapropiadas, Sonidos incomprensibles, No responde, No evaluable). c. Respuesta motora (posibles opciones: Cumple órdenes, Localiza el dolor, Retira ante el estímulo doloroso, Respuesta en flexión, Respuesta en extensión, No responde, No evaluable). d. Escala de Glasgow total (suma de los puntos de las tres categorías anteriores, rango de 3 a 15).
  * `"DX_PRINCIPAL"`: Diagnóstico principal con código CIE-10 y descripción.
  * `"TIPO_TRIAGE"`: Obtener el total de puntos de Modified Early Warning Score (MEWS) for Clinical Deterioration, teniendo en cuenta los datos de signos vitales y estado de conciencia. El resultado debe ser un número entero que representa el total de puntos del MEWS.
3. **Ejemplo de salida esperada:**
{
  "MOT_CONSULTA": "Paciente consulta por quemadura en mano izquierda. ",
  "ENF_ACTUAL": "Paciente masculino  ingresa con quemaduras en mano .....",
  "ESTADO_CONCIENCIA": "Alerta",
  "SIGNOS_VIT": {"P_arterial": "120 80", "F_cardiaca": "80", "F_respiratoria": "16", "Sat_O2": "98", "Temperatura": "36.5", "Talla": "175", Peso: "70"},
  "INTENSIDAD": "5",
  "GLASGOW": "{
    "Apertura ocular": "Espontánea ",
    "Respuesta verbal": "Orientado ",
    "Respuesta motora": "Cumple órdenes ",
    "Total": "15"
  }",
  "DX_PRINCIPAL": {"T201": "Quemadura de primer grado en mano izquierda"},
  "TIPO_TRIAGE": "3"
}
**Transcripción real:**\n """

prompt_base = """
Eres un asistente médico experto en la generación de historias clínicas a partir de transcripciones de consultas. Tu tarea es analizar el texto de la conversación entre un paciente y un médico, ten en cuenta que hay errores de transcripción trata de corregirlos y luego extraer la información solicitada, basandose solo en lo analizado de la transcripción .
---
**Entrada:**
Recibirás una transcripción de una cita médica.
---

**Instrucciones:**
1. Analiza la conversación para identificar síntomas, antecedentes, hallazgos clínicos, etc.
2. Genera una historia clínica estructurada profesionalmente como se explica a continuación:
  - Motivo de consulta, 
  - Enfermedad actual.
  - Datos generales: Estado civil, ocupación, con quien vive, creencias, nivel de escolaridad, etc.
  - Antecedentes personales: Patológicos, Reconciliación medicamentosa, quirúrgicos, tóxicos, hábitos, etc.
  - Examen fisico general y por region: Aspecto general, Color de la piel, Estado de hidratación, Estado de conciencia, Estado del dolor, Condición al llegar, Orientado, Presión arterial, Pulso, Frec. respiratoria, Sat. Oxígeno, FIO2, Frec. cardíaca, Temperatura, Escala glasgow, Peso, Estatura, Ind.masa corp.
  - Examen físico por región.
  - Hallazgos clínicos: Las observaciones y datos objetivos que un profesional de la salud recopila durante un examen médico. Son la evidencia tangible que sustenta el diagnóstico y el plan de tratamiento.
  - Análisis y plan: Tu análisis de la situación y el plan de acción.
  - Paraclínicos realizados: Detalla los exámenes complementarios que se han realizado.
  - Diagnosticos: Debes identificar los diagnósticos con nombre y código CIE-10.
  - Medicamentos: Identifica los medicamentos que toma el paciente y a los que es alérgico.
2. Devuelve el resultado como un objeto JSON basandose exactamente en las claves que se indican a continuación:
  * `"MOT_CONSULTA"`: Motivo de consulta.
  * `"ENF_ACTUAL"`: Enfermedad actual.
  * `"DATOS_GENERALES"`: Datos generales.
  * `"ANTECEDENTES"`: Antecedentes personales.
  * `"EXAMEN_FISICO"`: Examen físico general y por regiones.
  * `"HALLAZGOS_CLINICOS"`: Hallazgos clínicos.
  * `"ANALISIS_Y_PLAN"`: Análisis de la situación y plan de acción.
  * `"PARACLINICOS_REALIZADOS"`: Paraclínicos realizados.
  * `"DXS"`: Lista de diagnósticos con `"cie10"` y `"descripcion"`.
  * `"MEDS"`: Lista de medicamentos que toma el paciente.
3. **Ejemplo de salida esperada:**
{
  "MOT_CONSULTA ": "Paciente consulta por dolor abdominal. ",
  "ENF_ACTUAL ": "Paciente masculino  con cuadro clínico de un mes .....",
  "DATOS_GENERALES ": {
    "Ocupacion ": "No referido. ",
    "Estado_civil ": "No referido",
    "Con_quien_vive ": "No referido"
  },
  "ANTECEDENTES ": {
    "Patologicos ": "Diabetes Mellitus ... ",
    "Reconciliacion_medicamentosa ": "Toma Forxiga... ",
    "Quirurgicos ": "Colecistectomía...... ",
    "Alergicos ": "Niega alergias.... ",
    "Toxicos ": "Tabaquismo: consume un cigarrillo diario. Alcohol: consumo ocasional, socialmente. ",
    "Familiares ": "Madre con antecedentes... ",
    "Habitos ": "Sedentarismo..."
  },
  "EXAMEN_FISICO ": {
    "General ": {
      "Aspecto_general ": "Buen estado general. ",
      "Estado_de_conciencia ": "Alerta y consciente. ",
      "Orientado ": "Orientado en tiempo, espacio y persona. ",
      "Estado_de_hidratacion ": "No referida. ",
      "Presion_arterial ": "130/80 mmHg ",
      "Frec_cardiaca ": "60 lpm ",
      "Frec_respiratoria ": "No referida ",
      "Sat_Oxigeno ": "99% ",
      "FIO2 ": "Ambiente (21%) ",
      "Temperatura ": "No referida ",
      "Peso ": "102 kg ",
      "Estatura ": "1.80 m ",
      "Ind_masa_corp ": "31.48 kg/m2 (Obesidad Grado I) "
    },
    "Por_region ": "Abdomen: No referida.  Extremidades: No referida.  Cardiovascular: No referida.  Respiratorio: No referido.  Neurológico: No referido... "
  },
  "HALLAZGOS_CLINICOS": "Paciente con antecedentes de Diabetes Mellitus tipo 2, obesidad y tabaquismo. Presenta dolor abdominal difuso, sin signos de irritación peritoneal. No se observan masas ni visceromegalias... ",
  "ANALISIS_Y_PLAN ": "Paciente con antecedentes de Diabetes Mellitus tipo 2, obesidad y tabaquismo... ....Reforzar recomendaciones sobre dieta y aumento de la actividad física para el manejo del peso y la diabetes. ",
  "PARACLINICOS_REALIZADOS ": "Ninguno referido durante la consulta. ",
  "DXS ": [
    {
      "cie10 ": "K297 ",
      "descripcion ": "Gastritis, no especificada (En estudio) "
    }, ....
    {
      "cie10 ": "R030 ",
      "descripcion ": "Lectura de presión sanguínea elevada, sin diagnóstico de hipertensión "
    }
  ],
  "MEDS ": [ "Forxiga", "Metformina", "Naproxeno"],
  "ALERGIAS ": "Ninguna conocida. "
}
**Transcripción real:**\n """

def get_chat_response(context: str) -> str:
    """
    Envía el contexto a Gemini y devuelve la historia clínica estructurada en JSON.
    """
    model = genai.GenerativeModel("gemini-2.5-pro")

    prompt = prompt_base + context

    try:
      response = model.generate_content(prompt)
      tokens = response.usage_metadata.total_token_count
      str_res = str(response.text)
      print("Resp_GEMINI: ",response)
      tokens = int(tokens * 0.005894)
      ini = str_res.find("{")
      fin = str_res.rfind("}")
      out=str_res[ini:fin+1]
      #json_string = ast.literal_eval(out)
      json_string = json.loads(out)
      json_string['tokens'] = tokens
      return json_string
    except Exception as e:
        print(f"Error al llamar a Gemini: {e}")
        return "Error al generar la historia clínica."

def get_chat_response_gpt(prompt):        
  headers = {
      "Content-Type": "application/json",
      "api-key": os.getenv("GPT_O4_MINI_KEY"),
  }
  payload = {
            "model": "o4-mini",
            "messages": [
            {
                "role": "user",
                "content": [
                {"type": "text", "text": prompt_base + prompt
                        }
                ]
            }
            ],
            "response_format": {"type": "json_object"},
        }
  # Send request
  response = requests.post(os.getenv("GPT_O4_MINI_ENDPOINT"), headers=headers, json=payload)

  # Handle the response as needed (e.g., print or process)
  response_json = response.json()
  print(response_json)
  # Accessing specific values
  choices = response_json['choices']
  str_res = choices[0]['message']['content']

  tokens = response_json['usage']['total_tokens']
  tokens = int(tokens * 0.00451)
  ini = str_res.find("{")
  fin = str_res.rfind("}")
  out=str_res[ini:fin+1]
  #json_string = ast.literal_eval(out)
  json_string = json.loads(out)
  json_string['tokens'] = tokens
  
  return json_string



# c="""Doctor: Carolina buenas tardes. Soy jaiber el médico que la va a atender el día de hoy. ¿Dígame qué es la trae por acá? 
#   Paciente: Hola doctor, buenas tardes. Es que últimamente he sentido mucha molestia porque tengo alborotada. La gastritis me da mucho reflujo, me da mucho el estómago y me da mucho dolor.
#   Doctor: ¿Hace cuánto viene con ese problema con eso?
#   Paciente: Hace 6 meses.
#   Doctor: 6 meses de 1 a 10 en cuanto cataloga ese dolor.
#   Paciente: 8.
#   Doctor: 8.
#   Doctor: ¿Toma algún medicamento?
#   Paciente: Si naproxeno.
#   Doctor: Listo.
#   Doctor: ¿Alérgica a algún medicamento?
#   Paciente: A la penicilina.
#   Doctor: ¿A la penicilina muy bien su familia, alguien sufre de alguna enfermedad?
#   Doctor: Si.
#   Paciente: Mamá la que falleció, tenía diabetes.
#   Paciente: Eh ya.
#   Doctor: Sufre de alguna enfermedad.
#   Paciente: No doctor.
#   Doctor: Bueno, es que pasa aquí yo la la reviso.
#   Doctor: Bueno pesas 90 kg cuánto mides?
#   Paciente: 159
#   Paciente: Doctor es que yo creo que tengo azucar en la sangre, cuando como dulce me mareo.
#   Doctor: ya te lo han diagnosticado?.                                                                                                           o.
#   Paciente: No, no me lo han diagnosticado.
#   Doctor: A bueno, entonces te voy a mandar un examen para revisar ese ese tema."""
# res = get_chat_response_gpt(c)
# print(res)