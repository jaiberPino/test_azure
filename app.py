import os
import time
import uuid
import json
import threading
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import wave
import sounddevice as sd
from convertidor_hc import get_chat_response, get_chat_response_gpt
#import azure.cognitiveservices.speech as speechsdk
import requests
import time
from dotenv import load_dotenv
from sap_conection import escribir_evolucion

desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
proces = os.path.join(desktop_dir, "process_ia")
if not os.path.exists(proces):
    os.makedirs(proces)
    
load_dotenv()
base_url = "https://api.assemblyai.com"

headers = {
    "authorization": os.getenv("ASSEMBLY_KEY")
}
# --- Parámetros de grabación ---
FS = 16000  # Frecuencia de muestreo en Hz
CHANNELS = 1  # Número de canales (1 para mono)
FILENAME = "grabacion.wav"

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'

# --- CONFIGURACIÓN DE CREDENCIALES ---
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "TU_CLAVE_DE_AZURE_SPEECH")
AZURE_REGION = os.getenv("AZURE_REGION", "eastus")

# --- VARIABLES DEL USUARIO (simulación) ---
USERS = {
    "admin": "5533*",
    "medico": "secreta456"
}
SAMPLE_RATE = 16000
EXPECTED_CHANNELS =  2

# --- Gestión de Grabación en el Servidor ---
# Diccionario para almacenar los hilos de grabación y sus datos
RECORDING_PROCESSES = {}
recording_lock = threading.Lock()

class Recorder(threading.Thread):
    """Clase para manejar la grabación en un hilo separado."""
    def __init__(self, recording_id):
        super().__init__()
        self._stop_event = threading.Event()
        self.recording_id = recording_id
        self.frames = []
        self.stream = None

    def run(self):
        """Inicia la grabación en el hilo."""
        print(f"Iniciando grabación para el ID: {self.recording_id}")
        try:
            # Usamos un bloque `with` para asegurar que el stream se cierre correctamente
            with sd.InputStream(samplerate=FS, channels=CHANNELS, dtype='int16', callback=self._callback) as stream:
                self.stream = stream
                print("Grabadora activa. Esperando la señal de detención...")
                # Espera hasta que el evento de detención sea activado
                self._stop_event.wait()
        except Exception as e:
            print(f"Error en el hilo de grabación: {e}")
        finally:
            print("Hilo de grabación finalizado.")

    def _callback(self, indata, frames, time, status):
        """Callback que se ejecuta con cada bloque de audio."""
        if status:
            print(status, flush=True)
        # Añade los datos de audio a la lista
        self.frames.append(indata.copy())

    def stop(self):
        """Detiene la grabación de forma segura."""
        print("Recibida la señal para detener la grabación.")
        self._stop_event.set()

    def get_data(self):
        """Devuelve los datos de audio grabados."""
        # Concatena todos los bloques de audio grabados
        if not self.frames:
            return None
        # `sd.rec` devuelve un array de numpy, lo concatenamos
        import numpy as np
        return np.concatenate(self.frames)

# --- Funciones de procesamiento (ajustadas para el nuevo flujo) ---
def guardar_audio(filename, data, fs):
    """
    Guarda los datos de audio de numpy en un archivo WAV.
    """
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(fs)
        wf.writeframes(data.tobytes())
    print(f"Audio guardado en '{filename}'")

def transcribir_con_diarizacion_assemblyai(file_path):
    file_path = r"C:\Users\jypa\Documents\codes_visual\transcriptionApp\grabacion_98eb91d6-fdc1-41dd-a5bd-2d6513a39d45.wav"
    with open(file_path, "rb") as f:
        response = requests.post(base_url + "/v2/upload",
                            headers=headers,
                            data=f)

    audio_url = response.json()["upload_url"]

    data = {
        "audio_url": audio_url,
        "speech_model": "universal",
        "language_code": "es",  # Español
        "speaker_labels": True
    }

    url = base_url + "/v2/transcript"
    response = requests.post(url, json=data, headers=headers)

    transcript_id = response.json()['id']
    polling_endpoint = base_url + "/v2/transcript/" + transcript_id
    transcript_text = ''
    while True:
        transcription_result = requests.get(polling_endpoint, headers=headers).json()
        #transcript_text = transcription_result['text']

        if transcription_result['status'] == 'completed':
            for utt in transcription_result.get('utterances', []):
                if utt['speaker'] == "A":
                    speek = "Doctor"
                elif utt['speaker'] == "B":
                    speek= "Paciente"
                else:
                    speek= "Familiar"
                transcript_text = transcript_text + f"{speek}: {utt['text']} \n"
            print(transcript_text)
            return transcript_text

        elif transcription_result['status'] == 'error':
            raise RuntimeError(f"Transcription failed: {transcription_result['error']}")

        else:
            time.sleep(3)
   
#Rutas de la app
@app.route("/login", methods=["GET", "POST"])
def login():
    """Maneja el inicio de sesión del usuario."""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username in USERS and USERS[username] == password:
            session["username"] = username
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Usuario o contraseña incorrectos")
    return render_template("login.html")

@app.route("/logout")
def logout():
    """Cierra la sesión del usuario."""
    session.pop("username", None)
    return redirect(url_for("login"))

@app.route("/")
def index():
    """Renderiza la página principal de la aplicación."""
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", username=session["username"])

@app.route("/start_recording", methods=["POST"])
def start_recording():
    """Inicia una nueva grabación en un hilo separado."""
    with recording_lock:
        recording_id = str(uuid.uuid4())
        recorder = Recorder(recording_id)
        RECORDING_PROCESSES[recording_id] = recorder
        recorder.start()
        print(f"Grabación iniciada con ID: {recording_id}")
    return jsonify({"status": "Grabación iniciada", "recording_id": recording_id})

@app.route("/stop_recording/<string:recording_id>", methods=["POST"])
def stop_recording(recording_id):
    """Detiene una grabación y procesa el audio."""
    print(f"Recibida solicitud para detener grabación con ID: {recording_id}")
    with recording_lock:
        if recording_id not in RECORDING_PROCESSES:
            return jsonify({"error": "ID de grabación no válido"}), 404
        recorder = RECORDING_PROCESSES[recording_id]
        recorder.stop()
        del RECORDING_PROCESSES[recording_id]
    
    try:
        # Espera a que el hilo de grabación finalice
        recorder.join()
        audio_data = recorder.get_data()
        if audio_data is None or len(audio_data) == 0:
            return jsonify({"error": "No se grabó audio"}), 500

        # Guarda el archivo de audio
        # Creamos un nombre de archivo único para cada grabación
        filename = f"grabacion_{recording_id}.wav"
        guardar_audio(filename, audio_data, FS)

        # Transcribe y analiza el audio
        transcripcion = transcribir_con_diarizacion_assemblyai(filename)
        if transcripcion:
            print("Transcripción obtenida. Enviando a Gemini para análisis...")
            jsonOut = get_chat_response(transcripcion)
            #jsonOut = get_chat_response_gpt(transcripcion)

            print("Análisis de Gemini completado.")
            return jsonify(jsonOut)
        else:
            return jsonify({"error": "No se pudo transcribir el audio"}), 500
    except Exception as e:
        print(f"Error al procesar el audio: {e}")
        return jsonify({"error": f"Error interno del servidor: {e}"}), 500
    finally:
        pass
        # Limpia el archivo de audio
        # if 'filename' in locals() and os.path.exists(filename):
        #     os.remove(filename)

@app.route("/save_corrected_json", methods=["POST"])
def save_corrected_json():
    """
    Recibe el JSON con las correcciones hechas por el usuario desde la interfaz.
    """
    # request.get_json() extrae los datos JSON del cuerpo de la petición
    json_corrected = request.get_json()

    if not json_corrected:
        return jsonify({"status": "error", "message": "No se recibieron datos JSON"}), 400
    # 1. Obtener los campos del formulario (Episodio, Especialidad, etc.)
    episodio = json_corrected.get("episodio")
    especialidad = json_corrected.get("especialidad")
    campo3 = json_corrected.get("campo3")
    campo4 = json_corrected.get("campo4")

    print("Episodio:", episodio)
    print("Especialidad:", especialidad)
    print("Campo 3:", campo3)
    print("Campo 4:", campo4)

    # --- AQUÍ ES DONDE TIENES TU JSON CORREGIDO ---
    # Ahora puedes hacer lo que necesites con la variable 'json_corrected':
    # 1. Imprimirlo en la consola para verificar que llegó correctamente.
    print("--- JSON Corregido Recibido ---")
    # Usamos import json y json.dumps para imprimirlo de forma legible (pretty-print)
    import json
    print(json.dumps(json_corrected, indent=2, ensure_ascii=False))
    
    # Crea un nombre de archivo único para la tarea

    nombre_archivo_tarea = proces + f"\{episodio}.json"
    print(f"Nombre del archivo de tarea: {nombre_archivo_tarea}")
    # Guarda el JSON en la carpeta de tareas pendientes
    try:
        with open(nombre_archivo_tarea, 'w', encoding='utf-8') as f:
            json.dump(json_corrected, f, ensure_ascii=False, indent=4)
        print(f"Tarea para episodio {episodio} guardada en la cola.")
    except Exception as e:
        print(f"Error al guardar la tarea: {e}")
        return jsonify({"status": "error", "message": "No se pudo crear la tarea"}), 500

    #escribir_evolucion(episodio, json_corrected)
    # Devolvemos una respuesta al frontend para confirmar que se recibió.
    return jsonify({"status": "success", "message": "JSON corregido recibido y procesado"}), 200

if __name__ == "__main__":
    app.run(debug=True, port=5011)
