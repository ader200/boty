import os
import json
import qrcode
import uuid
from telebot import TeleBot, types
from datetime import datetime, timedelta
import random
import platform
import subprocess
import threading
import time
from flask import Flask, render_template_string
from pymongo import MongoClient
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Crear una aplicación Flask
app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Bot de Rifas</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 40px;
                    text-align: center;
                }
                h1 {
                    color: #333;
                }
            </style>
        </head>
        <body>
            <h1>Bot de Rifas</h1>
            <p>El servidor está funcionando correctamente.</p>
        </body>
        </html>
    """)

# Función para ejecutar el servidor web en un hilo separado
def run_web_server():
    port = int(os.environ.get('PORT', 3000))  # Render asigna el puerto mediante la variable PORT
    app.run(host='0.0.0.0', port=port)

# Iniciar el servidor web en un hilo separado si no estamos usando gunicorn
if 'gunicorn' not in os.environ.get('SERVER_SOFTWARE', ''):
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()

# Token del bot
TOKEN = '6824080362:AAH9YKYT0xTLPnc0Z597YjVLXNCo4nvgl-8'
ADMIN_CHAT_ID = 5498545183

# Constantes
CHAT_SOPORTE = -1002670436670  # Chat donde están los operadores
CHAT_HISTORIAL = -1002659327715  # Chat donde se guarda el historial
TIEMPO_INACTIVIDAD = 240  # 1 minuto en segundos

# Constantes para códigos
DIAS_ESPERA = 20
ARCHIVO_CODIGOS = 'codigos.json'

# Clase para manejar la base de datos MongoDB
class Database:
    def __init__(self):
        self.client = None
        self.db = None
        self.connect()
    
    def connect(self):
        """Establece la conexión con MongoDB"""
        try:
            # Obtener las credenciales del archivo .env
            mongodb_uri = os.getenv('MONGODB_URI')
            if not mongodb_uri:
                print("❌ Error: No se encontró MONGODB_URI en las variables de entorno")
                return False
            
            print("🔄 Intentando conectar a MongoDB...")
            
            # Intentar conectar a MongoDB con timeout
            self.client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
            
            # Verificar la conexión
            self.client.admin.command('ping')
            
            # Seleccionar la base de datos
            self.db = self.client.get_database()
            
            # Crear colecciones si no existen
            collections = ['registro', 'rifas_pagadas', 'rifas_gratis', 
                         'historial_rifas', 'historial_gratis', 'links']
            
            db_collections = self.db.list_collection_names()
            for collection in collections:
                if collection not in db_collections:
                    self.db.create_collection(collection)
            
            print("✅ Conexión exitosa a MongoDB")
            return True
            
        except Exception as e:
            print(f"❌ Error al conectar con MongoDB: {str(e)}")
            if hasattr(e, 'details'):
                print(f"Detalles del error: {e.details}")
            self.client = None
            self.db = None
            return False
    
    def reconnect_if_needed(self):
        """Intenta reconectar si la conexión se perdió"""
        try:
            if self.client is None or self.db is None:
                return self.connect()
            # Verificar la conexión con un ping
            self.client.admin.command('ping')
            return True
        except Exception as e:
            print(f"🔄 Reconectando a MongoDB debido a: {str(e)}")
            return self.connect()
    
    def registro_find_one(self, query):
        """Busca un registro con manejo de errores"""
        if not self.reconnect_if_needed():
            return None
        try:
            return self.db.registro.find_one(query)
        except Exception as e:
            print(f"Error al buscar en registro: {e}")
            return None
    
    def registro_insert_one(self, document):
        """Inserta un registro con manejo de errores"""
        if not self.reconnect_if_needed():
            return None
        try:
            return self.db.registro.insert_one(document)
        except Exception as e:
            print(f"Error al insertar en registro: {e}")
            return None
    
    def rifas_gratis_find_one(self, query):
        """Busca en rifas_gratis con manejo de errores"""
        if not self.reconnect_if_needed():
            return None
        try:
            return self.db.rifas_gratis.find_one(query)
        except Exception as e:
            print(f"Error al buscar en rifas_gratis: {e}")
            return None
    
    def links_find(self):
        """Obtiene todos los links con manejo de errores"""
        if not self.reconnect_if_needed():
            return []
        try:
            return list(self.db.links.find())
        except Exception as e:
            print(f"Error al obtener links: {e}")
            return []
    
    def rifas_gratis_insert_one(self, document):
        """Inserta un documento en rifas_gratis"""
        if not self.reconnect_if_needed():
            return None
        try:
            return self.db.rifas_gratis.insert_one(document)
        except Exception as e:
            print(f"Error al insertar en rifas_gratis: {e}")
            return None
    
    def rifas_pagadas_insert_one(self, document):
        """Inserta un documento en rifas_pagadas"""
        if not self.reconnect_if_needed():
            return None
        try:
            return self.db.rifas_pagadas.insert_one(document)
        except Exception as e:
            print(f"Error al insertar en rifas_pagadas: {e}")
            return None
    
    def rifas_pagadas_find(self):
        """Obtiene todas las rifas pagadas"""
        if not self.reconnect_if_needed():
            return []
        try:
            return list(self.db.rifas_pagadas.find())
        except Exception as e:
            print(f"Error al obtener rifas pagadas: {e}")
            return []
    
    def rifas_gratis_find(self):
        """Obtiene todas las rifas gratis"""
        if not self.reconnect_if_needed():
            return []
        try:
            return list(self.db.rifas_gratis.find())
        except Exception as e:
            print(f"Error al obtener rifas gratis: {e}")
            return []
    
    def historial_rifas_insert_one(self, document):
        """Inserta un documento en historial_rifas"""
        if not self.reconnect_if_needed():
            return None
        try:
            return self.db.historial_rifas.insert_one(document)
        except Exception as e:
            print(f"Error al insertar en historial_rifas: {e}")
            return None
    
    def historial_gratis_insert_one(self, document):
        """Inserta un documento en historial_gratis"""
        if not self.reconnect_if_needed():
            return None
        try:
            return self.db.historial_gratis.insert_one(document)
        except Exception as e:
            print(f"Error al insertar en historial_gratis: {e}")
            return None
    
    def rifas_pagadas_delete_many(self, filter={}):
        """Elimina documentos de rifas_pagadas"""
        if not self.reconnect_if_needed():
            return None
        try:
            return self.db.rifas_pagadas.delete_many(filter)
        except Exception as e:
            print(f"Error al eliminar de rifas_pagadas: {e}")
            return None
    
    def rifas_gratis_delete_many(self, filter={}):
        """Elimina documentos de rifas_gratis"""
        if not self.reconnect_if_needed():
            return None
        try:
            return self.db.rifas_gratis.delete_many(filter)
        except Exception as e:
            print(f"Error al eliminar de rifas_gratis: {e}")
            return None
    
    def links_insert_one(self, document):
        """Inserta un link en la colección de links"""
        if not self.reconnect_if_needed():
            return None
        try:
            return self.db.links.insert_one(document)
        except Exception as e:
            print(f"Error al insertar link: {e}")
            return None
    
    def links_delete_one(self, filter):
        """Elimina un link de la colección"""
        if not self.reconnect_if_needed():
            return None
        try:
            return self.db.links.delete_one(filter)
        except Exception as e:
            print(f"Error al eliminar link: {e}")
            return None
    
    def historial_rifas_find(self):
        """Obtiene todo el historial de rifas pagadas"""
        if not self.reconnect_if_needed():
            return []
        try:
            return list(self.db.historial_rifas.find())
        except Exception as e:
            print(f"Error al obtener historial de rifas: {e}")
            return []

    def historial_gratis_find(self):
        """Obtiene todo el historial de rifas gratis"""
        if not self.reconnect_if_needed():
            return []
        try:
            return list(self.db.historial_gratis.find())
        except Exception as e:
            print(f"Error al obtener historial de rifas gratis: {e}")
            return []

    def historial_gratis_delete_many(self, filter={}):
        """Elimina documentos del historial de rifas gratis"""
        if not self.reconnect_if_needed():
            return None
        try:
            return self.db.historial_gratis.delete_many(filter)
        except Exception as e:
            print(f"Error al eliminar del historial de rifas gratis: {e}")
            return None

    def historial_rifas_delete_many(self, filter={}):
        """Elimina documentos del historial de rifas pagadas"""
        if not self.reconnect_if_needed():
            return None
        try:
            return self.db.historial_rifas.delete_many(filter)
        except Exception as e:
            print(f"Error al eliminar del historial de rifas pagadas: {e}")
            return None

# Inicializar el bot
bot = TeleBot(TOKEN)

# Inicializar la base de datos
db = Database()

# Variables globales
comprobantes_pendientes = {}
conversaciones_activas = {}
temporizadores = {}
operadores_ocupados = {}  # Para rastrear qué operador está hablando con qué cliente

# Archivos JSON
REGISTRO_FILE = 'registro.json'
COMPRAS_FILE = 'compras.json'
GANADORES_FILE = 'ganadores.json'
GRATIS_FILE = 'gratis.json'
CODIGOS_FILE = 'codigos.json'
LINKS_FILE = 'links.json'

# Nuevos archivos JSON para historial
HISTORIAL_RIFA_FILE = 'historial_rifa.json'
HISTORIAL_GRATIS_FILE = 'historial_gratis.json'
CONVERSACIONES_DIR = 'conversaciones'

# Asegurarse de que los archivos JSON existan
def inicializar_json():
    archivos = [REGISTRO_FILE, COMPRAS_FILE, GANADORES_FILE, GRATIS_FILE, LINKS_FILE]
    for archivo in archivos:
        if not os.path.exists(archivo):
            with open(archivo, 'w') as f:
                json.dump({}, f)
    
    # Inicializar archivo de códigos con estructura específica
    if not os.path.exists(ARCHIVO_CODIGOS):
        datos_codigos = {
            'codigos': [],
            'estadisticas': {
                'codigos_disponibles': 0,
                'codigos_en_uso': 0,
                'codigos_usados': 0,
                'ultima_actualizacion': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        }
        with open(ARCHIVO_CODIGOS, 'w') as f:
            json.dump(datos_codigos, f, indent=4)

# Generar número único
def generar_numero_unico():
    return str(uuid.uuid4())

# Generar QR
def generar_qr(data, filename):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(filename)

# Cargar datos JSON
def cargar_json(archivo):
    try:
        with open(archivo, 'r') as f:
            return json.load(f)
    except:
        return {}

# Guardar datos JSON
def guardar_json(archivo, datos):
    with open(archivo, 'w') as f:
        json.dump(datos, f, indent=4)

def verificar_viernes():
    """Verifica si es viernes a las 10 PM"""
    now = datetime.now()
    return now.weekday() == 4 and now.hour == 22

def mover_datos_a_historial():
    """Mueve los datos actuales a los archivos de historial"""
    # Mover datos de rifas pagadas
    rifas = db.rifas_pagadas_find()
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    
    if rifas:
        db.historial_rifas_insert_one({
            'fecha': fecha_actual,
            'rifas': rifas
        })
        db.rifas_pagadas_delete_many()
    
    # Mover datos de rifas gratis
    gratis = db.rifas_gratis_find()
    
    if gratis:
        db.historial_gratis_insert_one({
            'fecha': fecha_actual,
            'rifas': gratis
        })
        db.rifas_gratis_delete_many()

def notificar_ganador(ganador, tipo_rifa):
    """Notifica al ganador y a los demás participantes"""
    if tipo_rifa == 'pagada':
        participantes = db.rifas_pagadas_find()
        mensaje_ganador = (
            f"🎉 ¡Felicitaciones {ganador['nombre']}! 🎉\n\n"
            f"Has sido seleccionado como el ganador de la rifa de esta semana.\n"
            f"Compraste {ganador['cantidad']} boleto(s).\n\n"
            "Nos pondremos en contacto contigo pronto para coordinar la entrega de tu premio. 🏆"
        )
    else:
        participantes = db.rifas_gratis_find()
        mensaje_ganador = (
            f"🎉 ¡Felicitaciones {ganador['nombre']}! 🎉\n\n"
            f"Has sido seleccionado como el ganador de la rifa gratuita de esta semana.\n\n"
            "Nos pondremos en contacto contigo pronto para coordinar la entrega de tu premio. 🏆"
        )

    # Notificar al ganador
    bot.send_message(ganador['chat_id'], mensaje_ganador)

    # Notificar a los demás participantes
    mensaje_otros = (
        f"🎯 ¡Tenemos un ganador!\n\n"
        f"Felicitaciones a {ganador['nombre']}, quien ganó con {ganador.get('cantidad', 1)} boleto(s).\n\n"
        "No te desanimes, ¡la próxima semana podrías ser tú!\n"
        "Tenemos grandes sorpresas preparadas para los próximos sorteos. 🎁\n\n"
        "Usa /rifa o /gratis para participar en el próximo sorteo. 🍀"
    )

    for participante in participantes:
        if participante['chat_id'] != ganador['chat_id']:
            try:
                bot.send_message(participante['chat_id'], mensaje_otros)
            except:
                continue

# Comando /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "¡Bienvenido al Bot de Rifas! 🎉\n\n"
                         "Comandos disponibles:\n"
                         "/rifa - Comprar rifa\n"
                         "/gratis - Obtener rifa gratis\n"
                         "/ganador - Elegir ganador (solo admin)\n"
                         "/ganadorz - Gestionar lista de ganadores (solo admin)\n"
                         "/uno - Elegir ganador aleatorio (solo admin)\n"
                         "/pi - Elegir ganador gratis (solo admin)\n"
                         "/qe - Gestionar links de páginas web (solo admin)\n"
                         "/lista - Ver listas de rifas\n"
                         "/descargar - Descargar archivos\n"
                         "/borrar_historial - Borrar historial\n"
                         "/cliente - Iniciar soporte al cliente\n"
                         "/gods - Iniciar chat con cliente específico (solo admin)")

# Comando /rifa
@bot.message_handler(commands=['rifa'])
def rifa(message):
    chat_id = message.chat.id
    
    # Verificar si el usuario ya está registrado
    usuario_existente = db.registro_find_one({'chat_id': chat_id})
    
    if usuario_existente:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(usuario_existente['nombre'], "Otro")
        bot.send_message(chat_id, "¿Desea usar su nombre registrado o registrar uno nuevo?", reply_markup=markup)
        bot.register_next_step_handler(message, procesar_opcion_rifa)
    else:
        bot.send_message(chat_id, "Por favor, ingrese su nombre completo:")
        bot.register_next_step_handler(message, pedir_nombre_rifa)

def procesar_opcion_rifa(message):
    if message.text == "Otro":
        bot.send_message(message.chat.id, "Por favor, ingrese su nombre completo:")
        bot.register_next_step_handler(message, pedir_nombre_rifa)
    else:
        usuario = db.registro_find_one({'nombre': message.text})
        if usuario:
            # Auto-rellenar celular y continuar con el proceso
            chat_id = message.chat.id
            
            # Enviar instrucciones de pago
            bot.send_message(chat_id, 
                f"Perfecto, {usuario['nombre']}.\n\n"
                "Por favor, proceda a depositar el monto correspondiente al número de boletos que desea adquirir:\n\n"
                "**Banco Pichincha**\n"
                "Cuenta de ahorro transaccional\n"
                "Número: 2209547823\n\n"
                "Ahora, envíame una foto del comprobante de pago.\n\n"
                "¡Gracias por su preferencia y apoyo!")
            
            bot.register_next_step_handler(message, procesar_comprobante_rifa, usuario['nombre'], usuario['celular'])
        else:
            bot.send_message(message.chat.id, "Usuario no encontrado. Por favor, ingrese su nombre completo:")
            bot.register_next_step_handler(message, pedir_nombre_rifa)

def pedir_nombre_rifa(message):
    if not message or not message.text:
        bot.send_message(message.chat.id, "Por favor, ingrese su nombre completo (nombre y apellido).")
        bot.register_next_step_handler(message, pedir_nombre_rifa)
        return
    
    nombre = message.text.strip()
    if len(nombre.split()) < 2:
        bot.send_message(message.chat.id, 
            "❌ Error: El nombre debe contener al menos nombre y apellido.\n\n"
            "Por favor, ingrese su nombre completo.\n"
            "Ejemplo: Juan Pérez")
        bot.register_next_step_handler(message, pedir_nombre_rifa)
    else:
        bot.send_message(message.chat.id, "Por favor, ingrese su número de celular:")
        bot.register_next_step_handler(message, pedir_celular_rifa, nombre)

def pedir_celular_rifa(message, nombre):
    if not message or not message.text:
        bot.send_message(message.chat.id, "Por favor, ingrese su número de celular.")
        bot.register_next_step_handler(message, pedir_celular_rifa, nombre)
        return
    
    celular = message.text.strip()
    if not celular.isdigit():
        bot.send_message(message.chat.id, 
            "❌ Error: El número de celular debe contener solo dígitos.\n\n"
            "Por favor, ingrese su número de celular correctamente.\n"
            "Ejemplo: 0991234567")
        bot.register_next_step_handler(message, pedir_celular_rifa, nombre)
    elif len(celular) < 10:
        bot.send_message(message.chat.id, 
            "❌ Error: El número de celular debe tener al menos 10 dígitos.\n\n"
            "Por favor, ingrese su número de celular completo.\n"
            "Ejemplo: 0991234567")
        bot.register_next_step_handler(message, pedir_celular_rifa, nombre)
    else:
        chat_id = message.chat.id
        
        # Guardar en registro
        db.registro_insert_one({
            'nombre': nombre,
            'celular': celular,
            'chat_id': chat_id,
            'fecha_registro': datetime.now()
        })
        
        # Enviar instrucciones de pago
        bot.send_message(chat_id, 
            f"✅ Perfecto, {nombre}.\n\n"
            "Por favor, proceda a depositar el monto correspondiente al número de boletos que desea adquirir:\n\n"
            "🏦 **Banco Pichincha**\n"
            "Cuenta de ahorro transaccional\n"
            "Número: 2209547823\n\n"
            "📸 Ahora, envíame una foto del comprobante de pago.\n\n"
            "¡Gracias por su preferencia y apoyo!")
        
        bot.register_next_step_handler(message, procesar_comprobante_rifa, nombre, celular)

def procesar_comprobante_rifa(message, nombre, celular):
    if not message:
        bot.send_message(message.chat.id, "Por favor, envíe una foto del comprobante de pago.")
        bot.register_next_step_handler(message, procesar_comprobante_rifa, nombre, celular)
        return
    
    if not message.photo:
        bot.send_message(message.chat.id, 
            "❌ Error: No se detectó una imagen.\n\n"
            "Por favor, envíe una foto clara del comprobante de pago.\n"
            "Asegúrese de que la imagen sea legible y muestre claramente el monto y la fecha.")
        bot.register_next_step_handler(message, procesar_comprobante_rifa, nombre, celular)
    else:
        # Generar un ID único para este comprobante
        comprobante_id = str(uuid.uuid4())
        
        # Enviar al admin para verificación con botones inline
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ Sí", callback_data=f"verificar_si_{message.chat.id}_{comprobante_id}"),
            types.InlineKeyboardButton("❌ No", callback_data=f"verificar_no_{message.chat.id}_{comprobante_id}")
        )
        
        # Guardar datos temporales
        datos_temp = {
            'nombre': nombre,
            'celular': celular,
            'chat_id': message.chat.id,
            'file_id': message.photo[-1].file_id,
            'comprobante_id': comprobante_id
        }
        
        # Enviar foto con botones al admin
        bot.send_photo(
            ADMIN_CHAT_ID,
            message.photo[-1].file_id,
            caption=f"📝 Verificar comprobante de:\nNombre: {nombre}\nCelular: {celular}\nID: {comprobante_id}",
            reply_markup=markup
        )
        
        # Guardar datos temporales en el diccionario global
        global comprobantes_pendientes
        comprobantes_pendientes[comprobante_id] = datos_temp
        
        # Mensaje al usuario
        bot.send_message(message.chat.id, 
            "✅ Tu comprobante ha sido enviado al administrador para verificación.\n\n"
            "📋 Proceso de verificación:\n"
            "1. El administrador revisará tu comprobante\n"
            "2. Si es válido, te pedirá la cantidad de boletos\n"
            "3. Recibirás tu código QR con los números\n\n"
            "⏳ Por favor, espera la respuesta del administrador.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('verificar_'))
def manejar_verificacion(call):
    if call.from_user.id == ADMIN_CHAT_ID:
        _, decision, chat_id, comprobante_id = call.data.split('_')
        chat_id = int(chat_id)
        
        global comprobantes_pendientes
        if comprobante_id in comprobantes_pendientes:
            datos_temp = comprobantes_pendientes[comprobante_id]
            
            if decision == 'si':
                bot.send_message(ADMIN_CHAT_ID, "¿Cuántos boletos está comprando?")
                bot.register_next_step_handler(call.message, procesar_cantidad_boletos, datos_temp)
            else:
                bot.send_message(datos_temp['chat_id'], 
                    "Lo sentimos, su comprobante no fue verificado como auténtico. "
                    "Por favor, intente nuevamente con un comprobante válido.")
            
            # Eliminar solo este comprobante específico
            del comprobantes_pendientes[comprobante_id]
            
            # Actualizar mensaje original
            bot.edit_message_reply_markup(
                chat_id=ADMIN_CHAT_ID,
                message_id=call.message.message_id,
                reply_markup=None
            )
            
            # Mostrar mensaje de cuántos comprobantes quedan pendientes
            pendientes = len(comprobantes_pendientes)
            if pendientes > 0:
                bot.send_message(ADMIN_CHAT_ID, f"Quedan {pendientes} comprobantes pendientes de verificar.")
    else:
        bot.answer_callback_query(call.id, "No tienes permisos para verificar comprobantes.")

def procesar_cantidad_boletos(message, datos_temp):
    if not message or not message.text:
        bot.send_message(ADMIN_CHAT_ID, "Por favor, ingrese la cantidad de boletos.")
        bot.register_next_step_handler(message, procesar_cantidad_boletos, datos_temp)
        return
    
    try:
        cantidad = int(message.text)
        if cantidad <= 0:
            bot.send_message(ADMIN_CHAT_ID, 
                "❌ Error: La cantidad debe ser mayor a 0.\n\n"
                "Por favor, ingrese una cantidad válida de boletos.\n"
                "Ejemplo: 1, 2, 3, etc.")
            bot.register_next_step_handler(message, procesar_cantidad_boletos, datos_temp)
        elif cantidad > 100:
            bot.send_message(ADMIN_CHAT_ID, 
                "❌ Error: La cantidad máxima es 100 boletos.\n\n"
                "Por favor, ingrese una cantidad válida de boletos.\n"
                "Ejemplo: 1, 2, 3, etc.")
            bot.register_next_step_handler(message, procesar_cantidad_boletos, datos_temp)
        else:
            # Generar números únicos
            numeros_unicos = [generar_numero_unico() for _ in range(cantidad)]
            
            # Guardar compra en MongoDB
            db.rifas_pagadas_insert_one({
                'nombre': datos_temp['nombre'],
                'celular': datos_temp['celular'],
                'chat_id': datos_temp['chat_id'],
                'cantidad': cantidad,
                'numeros_unicos': numeros_unicos,
                'fecha_compra': datetime.now()
            })
            
            # Generar y enviar QR
            qr_data = f"Números Únicos:\n{', '.join(numeros_unicos)}\nNombre: {datos_temp['nombre']}\nCelular: {datos_temp['celular']}"
            qr_filename = f"qr_{datos_temp['chat_id']}.png"
            generar_qr(qr_data, qr_filename)
            
            with open(qr_filename, 'rb') as qr_file:
                bot.send_photo(datos_temp['chat_id'], qr_file)
            
            os.remove(qr_filename)
            
            # Mensaje de confirmación
            bot.send_message(datos_temp['chat_id'],
                f"🎉 ¡Gracias por tu compra, {datos_temp['nombre']}!\n\n"
                f"📋 Detalles de tu compra:\n"
                f"- Cantidad de boletos: {cantidad}\n"
                f"- Números únicos: {', '.join(numeros_unicos)}\n\n"
                "🎯 Tus números únicos están en el código QR adjunto.\n"
                "🍀 ¡Participa nuevamente para aumentar tus chances de ganar!")
    except ValueError:
        bot.send_message(ADMIN_CHAT_ID, 
            "❌ Error: Debe ingresar un número válido.\n\n"
            "Por favor, ingrese la cantidad de boletos usando solo números.\n"
            "Ejemplo: 1, 2, 3, etc.")
        bot.register_next_step_handler(message, procesar_cantidad_boletos, datos_temp)

# Comando /gratis
@bot.message_handler(commands=['gratis'])
def gratis(message):
    chat_id = message.chat.id
    
    # Verificar si el usuario ya participó hoy
    if chat_id != ADMIN_CHAT_ID:  # Skip esta verificación para admin
        hoy = datetime.now().strftime('%Y-%m-%d')
        participacion_hoy = db.rifas_gratis_find_one({
            'chat_id': chat_id,
            'fecha_registro': {'$gte': datetime.strptime(hoy, '%Y-%m-%d')}
        })
        
        if participacion_hoy:
            bot.send_message(chat_id, 
                "❌ Ya has participado hoy en la rifa gratis.\n\n"
                "Por favor, vuelve mañana para participar nuevamente.\n"
                "¡Gracias por tu interés! 🎉")
            return
    
    # Obtener links disponibles
    links = db.links_find()
    
    # Mostrar lista de páginas disponibles
    mensaje = "📋 Páginas disponibles con códigos:\n\n"
    if links:
        for i, link in enumerate(links, 1):
            mensaje += f"{i}. {link['url']}\n"
        
        mensaje += "\n✨ Visita cualquiera de estas páginas para obtener el código."
        bot.send_message(chat_id, mensaje)
        
        # Solo pedir el código si hay páginas disponibles
        bot.send_message(chat_id, "Por favor, ingrese el código:")
        bot.register_next_step_handler(message, verificar_codigo_gratis)
    else:
        mensaje += "❌ No hay páginas registradas en este momento.\n\n"
        mensaje += "Por favor, contacta al administrador o intenta más tarde."
        bot.send_message(chat_id, mensaje)

def verificar_codigo_gratis(message):
    if not message or not message.text:
        bot.send_message(message.chat.id, "Por favor, ingrese el código.")
        bot.register_next_step_handler(message, verificar_codigo_gratis)
        return
    
    codigo = message.text.strip()
    
    if verificar_codigo(codigo):
        bot.send_message(message.chat.id, "Código válido. Por favor, ingrese su nombre completo:")
        bot.register_next_step_handler(message, pedir_nombre_gratis, codigo)
    else:
        bot.send_message(message.chat.id, 
            "❌ Error: Código inválido o ya utilizado.\n\n"
            "Por favor, sigue estos pasos:\n"
            "1. Visita una de las páginas disponibles\n"
            "2. Obtén el código\n"
            "3. Ingresa el código aquí\n"
            "4. Completa el registro\n\n"
            "Inténtalo de nuevo.")
        bot.register_next_step_handler(message, verificar_codigo_gratis)

def pedir_nombre_gratis(message, codigo):
    if not message or not message.text:
        bot.send_message(message.chat.id, "Por favor, ingrese su nombre completo.")
        bot.register_next_step_handler(message, pedir_nombre_gratis, codigo)
        return
    
    nombre = message.text.strip()
    chat_id = message.chat.id
    fecha = datetime.now()
    
    # Guardar en la base de datos
    db.rifas_gratis_insert_one({
        'chat_id': chat_id,
        'nombre': nombre,
        'codigo': codigo,
        'fecha_registro': fecha
    })
    
    # Enviar confirmación
    bot.send_message(chat_id,
        f"🎉 ¡Gracias por participar, {nombre}!\n\n"
        "✅ Tu registro ha sido confirmado.\n"
        "🍀 ¡Buena suerte en el sorteo!")

# Comando /ganador (solo admin)
@bot.message_handler(commands=['ganador'])
def ganador(message):
    if message.chat.id == ADMIN_CHAT_ID:
        rifas = db.rifas_pagadas_find()
        if rifas:
            # Elegir ganador aleatorio
            ganador = random.choice(rifas)
            notificar_ganador(ganador, 'pagada')
            
            # Si es viernes a las 10 PM, mover datos al historial
            if verificar_viernes():
                mover_datos_a_historial()
        else:
            bot.send_message(ADMIN_CHAT_ID, "No hay compradores registrados.")
    else:
        bot.send_message(message.chat.id, "No tiene permisos para usar este comando.")

@bot.message_handler(commands=['gods'])
def comando_gods(message):
    try:
        # Verificar que sea el administrador correcto
        if message.from_user.id != ADMIN_CHAT_ID:
            bot.reply_to(message, "❌ No tienes permisos para usar este comando")
            return
        
        # Solicitar ID del cliente
        msg = bot.send_message(
            message.from_user.id,
            "📝 Por favor, envía el ID del cliente para iniciar el chat"
        )
        bot.register_next_step_handler(msg, iniciar_chat_gods)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

def iniciar_chat_gods(message):
    try:
        # Convertir el ID a número
        cliente_id = int(message.text)
        operador_id = message.from_user.id
        
        # Verificar si el cliente ya está en una conversación
        if cliente_id in conversaciones_activas:
            bot.reply_to(message, "❌ Este cliente ya está en una conversación")
            return
        
        # Iniciar la conversación
        conversaciones_activas[cliente_id] = {
            'inicio': datetime.now(),
            'mensajes': [],
            'operador_id': operador_id,
            'atendido': True
        }
        
        operadores_ocupados[operador_id] = cliente_id
        
        # Notificar al operador
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            "❌ Cerrar Chat",
            callback_data=f"cerrar_soporte_{cliente_id}"
        ))
        
        bot.send_message(
            operador_id,
            f"✅ Chat iniciado con cliente {cliente_id}\n"
            "📝 Puedes empezar a escribir mensajes",
            reply_markup=markup
        )
        
        # Notificar al cliente
        try:
            bot.send_message(
                cliente_id,
                "👨‍💼 Un agente de soporte ha iniciado una conversación\n"
                "✍️ Puedes escribir tus mensajes\n"
                "❌ Para salir usa /cerrar"
            )
        except Exception as e:
            bot.reply_to(
                message,
                f"⚠️ No se pudo notificar al cliente: {str(e)}\n"
                "El chat sigue activo."
            )
            
    except ValueError:
        bot.reply_to(
            message,
            "❌ Error: El ID debe ser un número\n"
            "Por favor, intenta nuevamente con /gods"
        )
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error inesperado: {str(e)}\n"
            "Por favor, intenta nuevamente con /gods"
        )

# Comando /ganadorz (solo admin)
@bot.message_handler(commands=['ganadorz'])
def ganadorz(message):
    if message.chat.id == ADMIN_CHAT_ID:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Agregar", "Eliminar", "Ver lista")
        bot.send_message(message.chat.id, "¿Qué desea hacer?", reply_markup=markup)
        bot.register_next_step_handler(message, procesar_opcion_ganadorz)
    else:
        bot.send_message(message.chat.id, "No tiene permisos para usar este comando.")

def procesar_opcion_ganadorz(message):
    if not message or not message.text:
        return
    if message.text == "Agregar":
        bot.send_message(message.chat.id, "Ingrese el nombre del ganador:")
        bot.register_next_step_handler(message, agregar_ganador)
    elif message.text == "Eliminar":
        ganadores = cargar_json(GANADORES_FILE)
        if ganadores:
            lista = "\n".join([f"{i+1}. {g['nombre']}" for i, g in enumerate(ganadores)])
            bot.send_message(message.chat.id, f"Seleccione el número del ganador a eliminar:\n\n{lista}")
            bot.register_next_step_handler(message, eliminar_ganador)
        else:
            bot.send_message(message.chat.id, "No hay ganadores registrados.")
    elif message.text == "Ver lista":
        ganadores = cargar_json(GANADORES_FILE)
        if ganadores:
            lista = "\n".join([f"{i+1}. {g['nombre']} - {g['celular']}" for i, g in enumerate(ganadores)])
            bot.send_message(message.chat.id, f"Lista de ganadores:\n\n{lista}")
        else:
            bot.send_message(message.chat.id, "No hay ganadores registrados.")

def agregar_ganador(message):
    if not message or not message.text:
        return
    nombre = message.text.strip()
    bot.send_message(message.chat.id, "Ingrese el número de celular del ganador:")
    bot.register_next_step_handler(message, guardar_ganador, nombre)

def guardar_ganador(message, nombre):
    if not message or not message.text:
        return
    celular = message.text.strip()
    if celular.isdigit():
        ganadores = cargar_json(GANADORES_FILE)
        ganadores.append({
            'nombre': nombre,
            'celular': celular,
            'fecha_registro': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        guardar_json(GANADORES_FILE, ganadores)
        bot.send_message(message.chat.id, "Ganador agregado exitosamente.")
    else:
        bot.send_message(message.chat.id, "Por favor, ingrese un número de celular válido:")

def eliminar_ganador(message):
    if not message or not message.text:
        return
    try:
        indice = int(message.text) - 1
        ganadores = cargar_json(GANADORES_FILE)
        if 0 <= indice < len(ganadores):
            ganador_eliminado = ganadores.pop(indice)
            guardar_json(GANADORES_FILE, ganadores)
            bot.send_message(message.chat.id, f"Ganador '{ganador_eliminado['nombre']}' eliminado exitosamente.")
        else:
            bot.send_message(message.chat.id, "Número de ganador no válido.")
    except ValueError:
        bot.send_message(message.chat.id, "Por favor, ingrese un número válido.")

# Comando /uno (solo admin)
@bot.message_handler(commands=['uno'])
def uno(message):
    if message.chat.id == ADMIN_CHAT_ID:
        ganadores = db.historial_rifas_find()
        if ganadores:
            ganador = random.choice(ganadores)
            bot.send_message(ADMIN_CHAT_ID,
                f"¡Ganador seleccionado!\n\n"
                f"Nombre: {ganador['nombre']}\n"
                f"Celular: {ganador['celular']}")
        else:
            bot.send_message(ADMIN_CHAT_ID, "No hay ganadores registrados.")
    else:
        bot.send_message(message.chat.id, "No tiene permisos para usar este comando.")

# Comando /pi (solo admin)
@bot.message_handler(commands=['pi'])
def pi(message):
    if message.chat.id == ADMIN_CHAT_ID:
        gratis = db.rifas_gratis_find()
        if gratis:
            ganador = random.choice(gratis)
            bot.send_message(ADMIN_CHAT_ID,
                f"¡Ganador de rifa gratis seleccionado!\n\n"
                f"Nombre: {ganador['nombre']}\n"
                f"Celular: {ganador.get('celular', 'No registrado')}\n"
                f"Código: {ganador['codigo']}")
            
            # Notificar al ganador
            bot.send_message(ganador['chat_id'],
                f"¡Felicidades, {ganador['nombre']}! 🎉\n\n"
                "Has sido seleccionado como ganador de la rifa gratis.\n"
                "Nos pondremos en contacto contigo pronto.")
        else:
            bot.send_message(ADMIN_CHAT_ID, "No hay participantes en rifas gratis registrados.")
    else:
        bot.send_message(message.chat.id, "No tiene permisos para usar este comando.")

# Comando /qe (solo admin)
@bot.message_handler(commands=['qe'])
def qe(message):
    if message.chat.id == ADMIN_CHAT_ID:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Agregar Link", "Eliminar Link", "Ver Links")
        bot.send_message(message.chat.id, "¿Qué desea hacer con los links?", reply_markup=markup)
        bot.register_next_step_handler(message, procesar_opcion_qe)
    else:
        bot.send_message(message.chat.id, "No tiene permisos para usar este comando.")

def procesar_opcion_qe(message):
    if not message or not message.text:
        return
    if message.text == "Agregar Link":
        bot.send_message(message.chat.id, "Por favor, envíe el link completo (ejemplo: https://ejemplo.com):")
        bot.register_next_step_handler(message, agregar_link)
    elif message.text == "Eliminar Link":
        links = db.links_find()
        if links:
            lista = "\n".join([f"{i+1}. {link['url']}" for i, link in enumerate(links)])
            bot.send_message(message.chat.id, f"Seleccione el número del link a eliminar:\n\n{lista}")
            bot.register_next_step_handler(message, eliminar_link)
        else:
            bot.send_message(message.chat.id, "No hay links registrados.")
    elif message.text == "Ver Links":
        links = db.links_find()
        if links:
            lista = "\n".join([f"{i+1}. {link['url']}" for i, link in enumerate(links)])
            bot.send_message(message.chat.id, f"Lista de links:\n\n{lista}")
        else:
            bot.send_message(message.chat.id, "No hay links registrados.")

def agregar_link(message):
    if not message or not message.text:
        return
    link = message.text.strip()
    if link.startswith('http://') or link.startswith('https://'):
        # Verificar si el link ya existe
        links = db.links_find()
        if not any(l['url'] == link for l in links):
            db.links_insert_one({'url': link})
            bot.send_message(message.chat.id, "✅ Link agregado exitosamente.")
        else:
            bot.send_message(message.chat.id, "❌ Este link ya está registrado.")
    else:
        bot.send_message(message.chat.id, "❌ Por favor, envíe un link válido que comience con http:// o https://")

def eliminar_link(message):
    if not message or not message.text:
        return
    try:
        indice = int(message.text) - 1
        links = db.links_find()
        links_list = list(links)
        if 0 <= indice < len(links_list):
            link_eliminado = links_list[indice]
            db.links_delete_one({'url': link_eliminado['url']})
            bot.send_message(message.chat.id, f"✅ Link '{link_eliminado['url']}' eliminado exitosamente.")
        else:
            bot.send_message(message.chat.id, "❌ Número de link no válido.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Por favor, ingrese un número válido.")

@bot.message_handler(commands=['lista'])
def lista(message):
    if message.chat.id != ADMIN_CHAT_ID:
        bot.reply_to(message, "No tienes permisos para usar este comando.")
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Rifas Pagadas", "Rifas Gratis")
    bot.send_message(message.chat.id, "¿Qué lista deseas ver?", reply_markup=markup)
    bot.register_next_step_handler(message, procesar_tipo_lista)

def procesar_tipo_lista(message):
    if not message or not message.text:
        return

    if message.text == "Rifas Pagadas":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Ganadores Pagados", "Participantes Pagados")
        bot.send_message(message.chat.id, "¿Qué deseas ver?", reply_markup=markup)
        bot.register_next_step_handler(message, mostrar_lista_pagados)
    elif message.text == "Rifas Gratis":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Ganadores Gratis", "Participantes Gratis")
        bot.send_message(message.chat.id, "¿Qué deseas ver?", reply_markup=markup)
        bot.register_next_step_handler(message, mostrar_lista_gratis)
    else:
        markup = types.ReplyKeyboardRemove()
        bot.send_message(message.chat.id, "Opción no válida. Usa /lista para empezar de nuevo.", reply_markup=markup)

def mostrar_lista_pagados(message):
    if not message or not message.text:
        return

    markup = types.ReplyKeyboardRemove()
    if message.text == "Ganadores Pagados":
        historial = db.historial_rifas_find()
        mostrar_lista_formateada(message, historial, "pagada", markup)
    elif message.text == "Participantes Pagados":
        participantes = db.rifas_pagadas_find()
        mostrar_lista_formateada(message, participantes, "pagada", markup)
    else:
        bot.send_message(message.chat.id, "Opción no válida. Usa /lista para empezar de nuevo.", reply_markup=markup)

def mostrar_lista_gratis(message):
    if not message or not message.text:
        return

    markup = types.ReplyKeyboardRemove()
    if message.text == "Ganadores Gratis":
        historial = db.historial_gratis_find()
        mostrar_lista_formateada(message, historial, "gratis", markup)
    elif message.text == "Participantes Gratis":
        participantes = db.rifas_gratis_find()
        mostrar_lista_formateada(message, participantes, "gratis", markup)
    else:
        bot.send_message(message.chat.id, "Opción no válida. Usa /lista para empezar de nuevo.", reply_markup=markup)

def mostrar_lista_formateada(message, datos, tipo, markup):
    if not datos:
        bot.send_message(message.chat.id, "No hay datos para mostrar.", reply_markup=markup)
        return

    texto = ""
    if tipo == "pagada":
        for participante in datos:
            texto += f"👤 {participante['nombre']} - {participante.get('cantidad', 1)} boleto(s)\n"
            texto += f"📱 Celular: {participante.get('celular', 'No registrado')}\n"
            texto += f"🆔 ID: {participante['chat_id']}\n\n"
    else:  # tipo == "gratis"
        for participante in datos:
            texto += f"👤 {participante['nombre']}\n"
            texto += f"📱 Celular: {participante.get('celular', 'No registrado')}\n"
            texto += f"🆔 ID: {participante['chat_id']}\n"
            texto += f"🎫 Código: {participante.get('codigo', 'No registrado')}\n\n"

    # Dividir el mensaje si es muy largo
    if len(texto) > 4000:
        partes = [texto[i:i+4000] for i in range(0, len(texto), 4000)]
        for i, parte in enumerate(partes):
            if i == len(partes) - 1:
                bot.send_message(message.chat.id, parte, reply_markup=markup)
            else:
                bot.send_message(message.chat.id, parte)
    else:
        bot.send_message(message.chat.id, texto, reply_markup=markup)

@bot.message_handler(commands=['descargar'])
def descargar(message):
    if message.chat.id != ADMIN_CHAT_ID:
        bot.reply_to(message, "No tienes permisos para usar este comando.")
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Descargar Rifas", "Descargar Gratis", "Descargar Historial")
    bot.send_message(message.chat.id, "¿Qué archivo deseas descargar?", reply_markup=markup)
    bot.register_next_step_handler(message, procesar_descarga)

def procesar_descarga(message):
    if not message or not message.text:
        return

    try:
        if message.text == "Descargar Rifas":
            datos = {
                'rifas_pagadas': db.rifas_pagadas_find()
            }
            filename = 'rifas_pagadas.json'
        elif message.text == "Descargar Gratis":
            datos = {
                'rifas_gratis': db.rifas_gratis_find()
            }
            filename = 'rifas_gratis.json'
        elif message.text == "Descargar Historial":
            datos = {
                'historial_rifas': db.historial_rifas_find(),
                'historial_gratis': db.historial_gratis_find()
            }
            filename = 'historial.json'
        else:
            bot.send_message(message.chat.id, "❌ Opción no válida")
            return

        # Guardar datos en archivo temporal
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=4, default=str)

        # Enviar archivo
        with open(filename, 'rb') as f:
            bot.send_document(message.chat.id, f)

        # Eliminar archivo temporal
        os.remove(filename)

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error al procesar la descarga: {e}")

@bot.message_handler(commands=['borrar_historial'])
def borrar_historial(message):
    if message.chat.id != ADMIN_CHAT_ID:
        bot.reply_to(message, "No tienes permisos para usar este comando.")
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        "Borrar Historial Rifas", 
        "Borrar Historial Gratis",
        "Borrar Compradores Actuales",
        "Borrar Participantes Gratis",
        "Subir Nuevo Historial"
    )
    bot.send_message(message.chat.id, "¿Qué deseas hacer?", reply_markup=markup)
    bot.register_next_step_handler(message, procesar_borrado_historial)

def procesar_borrado_historial(message):
    if not message or not message.text:
        return

    markup = types.ReplyKeyboardRemove()
    try:
        if message.text == "Borrar Historial Rifas":
            # Crear backup antes de borrar
            historial = db.historial_rifas_find()
            if historial:
                fecha = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'backup_historial_rifas_{fecha}.json'
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(historial, f, indent=4, default=str)
                with open(filename, 'rb') as f:
                    bot.send_document(
                        CHAT_HISTORIAL,
                        f,
                        caption=f"📦 Backup historial rifas antes de borrar {fecha}"
                    )
                os.remove(filename)
            
            # Borrar historial
            db.historial_rifas_delete_many()
            bot.send_message(message.chat.id, "✅ Historial de rifas borrado exitosamente.", reply_markup=markup)
        
        elif message.text == "Borrar Historial Gratis":
            # Crear backup antes de borrar
            historial = db.historial_gratis_find()
            if historial:
                fecha = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'backup_historial_gratis_{fecha}.json'
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(historial, f, indent=4, default=str)
                with open(filename, 'rb') as f:
                    bot.send_document(
                        CHAT_HISTORIAL,
                        f,
                        caption=f"📦 Backup historial gratis antes de borrar {fecha}"
                    )
                os.remove(filename)
            
            # Borrar historial
            db.historial_gratis_delete_many()
            bot.send_message(message.chat.id, "✅ Historial de rifas gratis borrado exitosamente.", reply_markup=markup)
        
        elif message.text == "Borrar Compradores Actuales":
            # Crear backup antes de borrar
            rifas = db.rifas_pagadas_find()
            if rifas:
                fecha = datetime.now().strftime('%Y-%m-%d')
                db.historial_rifas_insert_one({
                    'fecha': fecha,
                    'rifas': rifas
                })
            
            # Borrar compradores actuales
            db.rifas_pagadas_delete_many()
            bot.send_message(message.chat.id, 
                "✅ Compradores actuales borrados exitosamente.\n"
                "📋 Se ha creado un respaldo en el historial.", 
                reply_markup=markup)
        
        elif message.text == "Borrar Participantes Gratis":
            # Crear backup antes de borrar
            gratis = db.rifas_gratis_find()
            if gratis:
                fecha = datetime.now().strftime('%Y-%m-%d')
                db.historial_gratis_insert_one({
                    'fecha': fecha,
                    'rifas': gratis
                })
            
            # Borrar participantes gratis actuales
            db.rifas_gratis_delete_many()
            bot.send_message(message.chat.id, 
                "✅ Participantes gratis borrados exitosamente.\n"
                "📋 Se ha creado un respaldo en el historial.", 
                reply_markup=markup)
        
        elif message.text == "Subir Nuevo Historial":
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(
                "Subir Historial Rifas",
                "Subir Historial Gratis",
                "Subir Lista Compradores",
                "Subir Lista Gratis"
            )
            bot.send_message(message.chat.id, 
                "📤 ¿Qué tipo de archivo deseas subir?\n\n"
                "- Historial Rifas: Para subir historial de rifas pagadas\n"
                "- Historial Gratis: Para subir historial de rifas gratis\n"
                "- Lista Compradores: Para subir lista actual de compradores\n"
                "- Lista Gratis: Para subir lista actual de participantes gratis", 
                reply_markup=markup)
            bot.register_next_step_handler(message, seleccionar_tipo_subida)
        
        else:
            bot.send_message(message.chat.id, "❌ Opción no válida. Usa /borrar_historial para empezar de nuevo.", reply_markup=markup)
    
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error al procesar el borrado: {e}", reply_markup=markup)

def seleccionar_tipo_subida(message):
    if not message or not message.text:
        return

    global tipo_subida_actual
    markup = types.ReplyKeyboardRemove()

    if message.text in ["Subir Historial Rifas", "Subir Historial Gratis", "Subir Lista Compradores", "Subir Lista Gratis"]:
        tipo_subida_actual = message.text
        bot.send_message(message.chat.id, 
            "📤 Por favor, envía el archivo JSON que deseas cargar.", 
            reply_markup=markup)
        bot.register_next_step_handler(message, cargar_nuevo_historial)
    else:
        bot.send_message(message.chat.id, 
            "❌ Opción no válida. Usa /borrar_historial para empezar de nuevo.", 
            reply_markup=markup)

def cargar_nuevo_historial(message):
    try:
        if not message.document:
            markup = types.ReplyKeyboardRemove()
            bot.send_message(message.chat.id, "❌ Por favor, envía un archivo JSON válido.", reply_markup=markup)
            return

        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        datos = json.loads(downloaded_file.decode('utf-8'))

        global tipo_subida_actual
        markup = types.ReplyKeyboardRemove()

        if tipo_subida_actual == "Subir Historial Rifas":
            for rifa in datos:
                db.historial_rifas_insert_one(rifa)
            bot.send_message(message.chat.id, 
                "✅ Datos guardados exitosamente en el historial de rifas.", 
                reply_markup=markup)
        
        elif tipo_subida_actual == "Subir Historial Gratis":
            for rifa in datos:
                db.historial_gratis_insert_one(rifa)
            bot.send_message(message.chat.id, 
                "✅ Datos guardados exitosamente en el historial de rifas gratis.", 
                reply_markup=markup)
        
        elif tipo_subida_actual == "Subir Lista Compradores":
            for rifa in datos:
                db.rifas_pagadas_insert_one(rifa)
            bot.send_message(message.chat.id, 
                "✅ Lista de compradores actualizada exitosamente.", 
                reply_markup=markup)
        
        elif tipo_subida_actual == "Subir Lista Gratis":
            for rifa in datos:
                db.rifas_gratis_insert_one(rifa)
            bot.send_message(message.chat.id, 
                "✅ Lista de participantes gratis actualizada exitosamente.", 
                reply_markup=markup)

        tipo_subida_actual = None

    except json.JSONDecodeError:
        markup = types.ReplyKeyboardRemove()
        bot.send_message(message.chat.id, "❌ El archivo no es un JSON válido.", reply_markup=markup)
    except Exception as e:
        markup = types.ReplyKeyboardRemove()
        bot.send_message(message.chat.id, f"❌ Error al procesar el archivo: {e}", reply_markup=markup)

# Variable global para el tipo de subida actual
tipo_subida_actual = None

@bot.message_handler(commands=['cliente'])
def iniciar_soporte(message):
    chat_id = message.chat.id
    
    # Crear directorio para conversaciones si no existe
    if not os.path.exists(CONVERSACIONES_DIR):
        os.makedirs(CONVERSACIONES_DIR)

    # Verificar si ya tiene una conversación activa
    if chat_id in conversaciones_activas:
        return

    # Iniciar nueva conversación
    conversaciones_activas[chat_id] = {
        'inicio': datetime.now(),
        'mensajes': [],
        'atendido': False
    }

    # Notificar al usuario
    bot.send_message(chat_id, 
        "🎯 Chat de soporte iniciado\n"
        "✍️ Puedes escribir tus mensajes\n"
        "❌ Para salir usa /cerrar")

    # Notificar al canal de soporte
    markup_soporte = types.InlineKeyboardMarkup()
    markup_soporte.add(types.InlineKeyboardButton("💬 Atender Cliente", callback_data=f"atender_{chat_id}"))
    
    bot.send_message(CHAT_SOPORTE, 
        f"🆕 Nuevo cliente esperando atención\n"
        f"👤 Cliente: {message.from_user.first_name}\n"
        f"🆔 ID: {chat_id}",
        reply_markup=markup_soporte)

@bot.message_handler(commands=['cerrar'])
def cerrar_chat_comando(message):
    chat_id = message.chat.id
    if chat_id in conversaciones_activas:
        cerrar_conversacion(chat_id, "cliente")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    try:
        if call.data.startswith("atender_"):
            # Operador quiere atender al cliente
            chat_id = int(call.data.split("_")[1])
            operador_id = call.from_user.id
            
            if operador_id in operadores_ocupados:
                bot.answer_callback_query(call.id, "❌ Ya estás atendiendo a otro cliente")
                return
                
            if chat_id in conversaciones_activas:
                operadores_ocupados[operador_id] = chat_id
                conversaciones_activas[chat_id]['operador_id'] = operador_id
                conversaciones_activas[chat_id]['atendido'] = True
                
                # Actualizar mensaje del operador
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("❌ Cerrar Chat", callback_data=f"cerrar_soporte_{chat_id}"))
                
                bot.edit_message_reply_markup(
                    chat_id=CHAT_SOPORTE,
                    message_id=call.message.message_id,
                    reply_markup=markup
                )
                
                bot.answer_callback_query(call.id, "✅ Chat iniciado con el cliente")
                
                # Notificar al cliente
                bot.send_message(chat_id, "👨‍💼 Un agente se ha unido al chat")

        elif call.data.startswith("cerrar_soporte_"):
            # Operador quiere cerrar el chat
            chat_id = int(call.data.split("_")[2])
            if chat_id in conversaciones_activas:
                cerrar_conversacion(chat_id, "operador")
                bot.answer_callback_query(call.id, "✅ Chat cerrado")

    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Error al procesar la acción")
        print(f"Error en callback: {e}")

def procesar_mensaje_cliente(message):
    chat_id = message.chat.id
    if chat_id not in conversaciones_activas:
        return

    # Guardar mensaje
    conversaciones_activas[chat_id]['mensajes'].append({
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'from_id': chat_id,
        'nombre': message.from_user.first_name,
        'content': message.text if message.text else '[imagen]',
        'type': 'text' if message.text else 'image'
    })

    # Enviar al soporte
    if message.text:
        bot.send_message(CHAT_SOPORTE, 
            f"👤 Cliente {message.from_user.first_name}:\n{message.text}")
    elif message.photo:
        bot.send_photo(CHAT_SOPORTE, 
            message.photo[-1].file_id,
            caption=f"📸 Imagen de {message.from_user.first_name}")

def cerrar_conversacion(chat_id, tipo):
    if chat_id not in conversaciones_activas:
        return

    # Generar y enviar el archivo de la conversación
    guardar_conversacion(chat_id)

    # Notificar a ambas partes
    if tipo == "operador":
        mensaje = "✅ El operador ha cerrado el chat"
    elif tipo == "cliente":
        mensaje = "✅ Has cerrado el chat"
    else:
        mensaje = "✅ Chat finalizado"
    
    try:
        bot.send_message(chat_id, mensaje)
        bot.send_message(CHAT_SOPORTE, f"Chat con cliente {chat_id} finalizado")
    except:
        pass

    # Limpiar datos
    if chat_id in conversaciones_activas:
        operador_id = conversaciones_activas[chat_id].get('operador_id')
        if operador_id and operador_id in operadores_ocupados:
            del operadores_ocupados[operador_id]
        del conversaciones_activas[chat_id]

def guardar_conversacion(chat_id):
    if chat_id not in conversaciones_activas:
        return

    conversacion = conversaciones_activas[chat_id]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{CONVERSACIONES_DIR}/chat_{chat_id}_{timestamp}.txt"

    # Crear contenido formateado
    contenido = [
        "╔═══════════════════════════════╗",
        "║         CHAT DE SOPORTE       ║",
        "╚═══════════════════════════════╝",
        f"Cliente ID: {chat_id}",
        f"Inicio: {conversacion['inicio'].strftime('%Y-%m-%d %H:%M:%S')}",
        f"Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "═" * 40,
        ""
    ]

    # Agregar mensajes
    for msg in conversacion['mensajes']:
        tiempo = msg['timestamp']
        remitente = "👤 Cliente" if msg['from_id'] == chat_id else "👨‍💼 Soporte"
        contenido.extend([
            "┌" + "─" * 38,
            f"│ {remitente} - {tiempo}",
            f"│ {msg['content']}",
            "└" + "─" * 38,
            ""
        ])

    # Guardar archivo
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(contenido))

    # Enviar al canal de historial
    with open(filename, 'rb') as f:
        bot.send_document(CHAT_HISTORIAL, f,
            caption=f"📋 Historial del chat con cliente {chat_id}")

# Manejador para mensajes normales
@bot.message_handler(content_types=['text', 'photo'])
def manejar_mensajes(message):
    # Si es un mensaje del operador
    if message.chat.id == CHAT_SOPORTE:
        # Buscar si el operador está atendiendo a algún cliente
        operador_id = message.from_user.id
        if operador_id in operadores_ocupados:
            chat_id = operadores_ocupados[operador_id]
            if chat_id in conversaciones_activas:
                # Guardar mensaje
                conversaciones_activas[chat_id]['mensajes'].append({
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'from_id': CHAT_SOPORTE,
                    'content': message.text if message.text else '[imagen]',
                    'type': 'text' if message.text else 'image'
                })
                
                # Enviar al cliente
                if message.text and not message.text.startswith('/'):
                    bot.send_message(chat_id, f"👨‍💼 Soporte: {message.text}")
                elif message.photo:
                    bot.send_photo(chat_id, message.photo[-1].file_id, caption="👨‍💼 Imagen del soporte")
    
    # Si es un mensaje del cliente
    elif message.chat.id in conversaciones_activas:
        procesar_mensaje_cliente(message)

# Inicializar archivos JSON
inicializar_json()

def backup_diario():
    """Realiza un backup diario de la base de datos"""
    while True:
        try:
            # Esperar hasta las 23:59
            ahora = datetime.now()
            siguiente_backup = ahora.replace(hour=23, minute=59, second=0, microsecond=0)
            if ahora >= siguiente_backup:
                siguiente_backup += timedelta(days=1)
            
            time.sleep((siguiente_backup - ahora).total_seconds())
            
            # Realizar backup
            fecha = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup = {
                'fecha': fecha,
                'rifas_pagadas': db.rifas_pagadas_find(),
                'rifas_gratis': db.rifas_gratis_find(),
                'historial_rifas': db.historial_rifas_find(),
                'historial_gratis': db.historial_gratis_find(),
                'links': db.links_find()
            }
            
            # Guardar backup en archivo JSON
            filename = f'backup_{fecha}.json'
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(backup, f, indent=4, default=str)
            
            # Enviar backup al canal de historial
            with open(filename, 'rb') as f:
                bot.send_document(
                    CHAT_HISTORIAL,
                    f,
                    caption=f"📦 Backup automático {fecha}"
                )
            
            # Eliminar archivo temporal
            os.remove(filename)
            
            print(f"✅ Backup realizado exitosamente: {fecha}")
            
        except Exception as e:
            print(f"❌ Error en backup: {e}")
            time.sleep(300)  # Esperar 5 minutos antes de reintentar

def cargar_codigos():
    """Carga los códigos desde el archivo JSON"""
    try:
        with open(ARCHIVO_CODIGOS, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Error al cargar códigos: {e}")
        return None

def guardar_codigos(datos):
    """Guarda los códigos en el archivo JSON"""
    try:
        with open(ARCHIVO_CODIGOS, 'w') as f:
            json.dump(datos, f, indent=4)
        return True
    except Exception as e:
        print(f"Error al guardar códigos: {e}")
        return False

def actualizar_estados_codigos():
    """Actualiza el estado de los códigos según las fechas"""
    try:
        datos = cargar_codigos()
        if not datos:
            return False
        
        ahora = datetime.now()
        cambios = False
        
        # Si es después de la 1 AM, desactivar códigos en uso
        if ahora.hour >= 1:
            for codigo in datos['codigos']:
                if codigo['estado'] == 'en_uso':
                    fecha_desactivacion = datetime.strptime(codigo['fecha_desactivacion'], '%Y-%m-%d %H:%M:%S')
                    if fecha_desactivacion <= ahora:
                        codigo['estado'] = 'usado'
                        codigo['fecha_disponible'] = (ahora + timedelta(days=DIAS_ESPERA)).strftime('%Y-%m-%d %H:%M:%S')
                        cambios = True
        
        # Activar códigos que ya cumplieron su tiempo de espera
        for codigo in datos['codigos']:
            if codigo['estado'] == 'usado':
                fecha_disponible = datetime.strptime(codigo['fecha_disponible'], '%Y-%m-%d %H:%M:%S')
                if fecha_disponible <= ahora:
                    codigo['estado'] = 'disponible'
                    codigo['fecha_activacion'] = None
                    codigo['fecha_desactivacion'] = None
                    codigo['fecha_disponible'] = None
                    cambios = True
        
        if cambios:
            # Actualizar estadísticas
            datos['estadisticas']['codigos_disponibles'] = sum(1 for c in datos['codigos'] if c['estado'] == 'disponible')
            datos['estadisticas']['codigos_en_uso'] = sum(1 for c in datos['codigos'] if c['estado'] == 'en_uso')
            datos['estadisticas']['codigos_usados'] = sum(1 for c in datos['codigos'] if c['estado'] == 'usado')
            datos['estadisticas']['ultima_actualizacion'] = ahora.strftime('%Y-%m-%d %H:%M:%S')
            
            return guardar_codigos(datos)
        
        return True
    except Exception as e:
        print(f"Error al actualizar estados: {e}")
        return False

def verificar_codigo(codigo):
    """Verifica si un código es válido y está disponible"""
    try:
        datos = cargar_codigos()
        if not datos:
            return False
        
        for c in datos['codigos']:
            if c['codigo'] == codigo and c['estado'] in ['disponible', 'en_uso']:
                # Si el código está disponible, marcarlo como en uso
                if c['estado'] == 'disponible':
                    ahora = datetime.now()
                    c['estado'] = 'en_uso'
                    c['fecha_activacion'] = ahora.strftime('%Y-%m-%d %H:%M:%S')
                    c['fecha_desactivacion'] = (ahora.replace(hour=1, minute=0, second=0, microsecond=0) + 
                                              timedelta(days=1 if ahora.hour >= 1 else 0)).strftime('%Y-%m-%d %H:%M:%S')
                    c['usos'] += 1
                    
                    # Actualizar estadísticas
                    datos['estadisticas']['codigos_disponibles'] -= 1
                    datos['estadisticas']['codigos_en_uso'] += 1
                    datos['estadisticas']['ultima_actualizacion'] = ahora.strftime('%Y-%m-%d %H:%M:%S')
                    
                    guardar_codigos(datos)
                return True
        return False
    except Exception as e:
        print(f"Error al verificar código: {e}")
        return False

# Iniciar el hilo de backup
backup_thread = threading.Thread(target=backup_diario, daemon=True)
backup_thread.start()

if __name__ == '__main__':
    print('Iniciando bot...')
    bot.polling()