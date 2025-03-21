import os
import json
import qrcode
import uuid
from telebot import TeleBot, types
from datetime import datetime
import random
import platform
import subprocess
import threading
import time

# Token del bot
TOKEN = '6824080362:AAH9YKYT0xTLPnc0Z597YjVLXNCo4nvgl-8'
ADMIN_CHAT_ID = 5498545183

# Constantes
CHAT_SOPORTE = -1002670436670  # Chat donde están los operadores
CHAT_HISTORIAL = -1002659327715  # Chat donde se guarda el historial
TIEMPO_INACTIVIDAD = 240  # 1 minuto en segundos

# Inicializar el bot
bot = TeleBot(TOKEN)

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
    archivos = [REGISTRO_FILE, COMPRAS_FILE, GANADORES_FILE, GRATIS_FILE, CODIGOS_FILE, LINKS_FILE]
    for archivo in archivos:
        if not os.path.exists(archivo):
            with open(archivo, 'w') as f:
                json.dump({}, f)

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
    rifas = cargar_json(COMPRAS_FILE)
    historial_rifas = cargar_json(HISTORIAL_RIFA_FILE)
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    
    if rifas:
        historial_rifas[fecha_actual] = rifas
        guardar_json(HISTORIAL_RIFA_FILE, historial_rifas)
        guardar_json(COMPRAS_FILE, [])
    
    # Mover datos de rifas gratis
    gratis = cargar_json(GRATIS_FILE)
    historial_gratis = cargar_json(HISTORIAL_GRATIS_FILE)
    
    if gratis:
        historial_gratis[fecha_actual] = gratis
        guardar_json(HISTORIAL_GRATIS_FILE, historial_gratis)
        guardar_json(GRATIS_FILE, [])

def notificar_ganador(ganador, tipo_rifa):
    """Notifica al ganador y a los demás participantes"""
    if tipo_rifa == 'pagada':
        participantes = cargar_json(COMPRAS_FILE)
        mensaje_ganador = (
            f"🎉 ¡Felicitaciones {ganador['nombre']}! 🎉\n\n"
            f"Has sido seleccionado como el ganador de la rifa de esta semana.\n"
            f"Compraste {ganador['cantidad']} boleto(s).\n\n"
            "Nos pondremos en contacto contigo pronto para coordinar la entrega de tu premio. 🏆"
        )
    else:
        participantes = cargar_json(GRATIS_FILE)
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
    registro = cargar_json(REGISTRO_FILE)
    
    # Verificar si el usuario ya está registrado
    usuario_existente = next((u for u in registro if u['chat_id'] == chat_id), None)
    
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
        registro = cargar_json(REGISTRO_FILE)
        usuario = next((u for u in registro if u['nombre'] == message.text), None)
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
        registro = cargar_json(REGISTRO_FILE)
        registro.append({
            'nombre': nombre,
            'celular': celular,
            'chat_id': chat_id,
            'fecha_registro': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        guardar_json(REGISTRO_FILE, registro)
        
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
            
            # Guardar compra
            compras = cargar_json(COMPRAS_FILE)
            compras.append({
                'nombre': datos_temp['nombre'],
                'celular': datos_temp['celular'],
                'chat_id': datos_temp['chat_id'],
                'cantidad': cantidad,
                'numeros_unicos': numeros_unicos,
                'fecha_compra': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            guardar_json(COMPRAS_FILE, compras)
            
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
    gratis = cargar_json(GRATIS_FILE)
    hoy = datetime.now().strftime('%Y-%m-%d')
    participacion_hoy = any(g['chat_id'] == chat_id and g['fecha_registro'].startswith(hoy) for g in gratis)
    
    if participacion_hoy:
        bot.send_message(chat_id, 
            "❌ Ya has participado hoy en la rifa gratis.\n\n"
            "Por favor, vuelve mañana para participar nuevamente.\n"
            "¡Gracias por tu interés! 🎉")
        return
    
    # Obtener links disponibles
    links = cargar_json(LINKS_FILE)
    if not links:
        bot.send_message(chat_id, 
            "❌ Lo sentimos, no hay páginas disponibles en este momento.\n"
            "Por favor, intenta más tarde.")
        return
    
    # Enviar mensaje con los links disponibles
    mensaje = "🎉 Para obtener una rifa gratis, visita una de nuestras páginas web:\n\n"
    for i, link in enumerate(links, 1):
        mensaje += f"{i}. {link}\n"
    mensaje += "\nCopia el código que aparece en la página y envíalo aquí."
    
    bot.send_message(chat_id, mensaje)
    bot.register_next_step_handler(message, verificar_codigo_gratis)

def verificar_codigo_gratis(message):
    try:
        chat_id = message.chat.id
        codigo = message.text.strip()
        
        # Cargar códigos.json
        try:
            with open('codigos.json', 'r') as f:
                datos = json.load(f)
        except Exception as e:
            bot.reply_to(message, "❌ Error al cargar los códigos. Por favor, intenta más tarde.")
            return
        
        # Verificar si el código está en la lista de códigos disponibles
        if codigo in datos['codigos']:
            # Código válido, proceder con el registro
            bot.send_message(chat_id, "✅ Código válido! Por favor, ingrese su nombre completo:")
            bot.register_next_step_handler(message, pedir_nombre_gratis, codigo)
            return
            
        # Verificar si es el código activo
        if codigo == datos['codigo_activo']:
            # Código válido, proceder con el registro
            bot.send_message(chat_id, "✅ Código válido! Por favor, ingrese su nombre completo:")
            bot.register_next_step_handler(message, pedir_nombre_gratis, codigo)
            return
            
        # Verificar si ya fue usado
        for usado in datos['usados']:
            if usado['codigo'] == codigo:
                bot.send_message(chat_id, "❌ Este código ya ha sido utilizado. Por favor, intente con otro código.")
                bot.register_next_step_handler(message, verificar_codigo_gratis)
                return
        
        # Si llegamos aquí, el código no es válido
        bot.send_message(chat_id, "❌ Código no válido. Por favor, intente nuevamente.")
        bot.register_next_step_handler(message, verificar_codigo_gratis)
        
    except Exception as e:
        print(f"Error al verificar código: {e}")
        bot.send_message(chat_id, "❌ Error al verificar el código. Por favor, intente nuevamente.")
        bot.register_next_step_handler(message, verificar_codigo_gratis)

def pedir_nombre_gratis(message, codigo):
    if not message or not message.text:
        return
    nombre = message.text.strip()
    if len(nombre.split()) >= 2:
        bot.send_message(message.chat.id, "Por favor, ingrese su número de celular:")
        bot.register_next_step_handler(message, pedir_celular_gratis, nombre, codigo)
    else:
        bot.send_message(message.chat.id, "Por favor, ingrese su nombre completo (nombre y apellido):")
        bot.register_next_step_handler(message, pedir_nombre_gratis, codigo)

def pedir_celular_gratis(message, nombre, codigo):
    if not message or not message.text:
        return
    celular = message.text.strip()
    if celular.isdigit():
        # Generar número único
        numero_unico = generar_numero_unico()
        
        # Guardar en registro de rifas gratis
        gratis = cargar_json(GRATIS_FILE)
        gratis.append({
            'nombre': nombre,
            'celular': celular,
            'chat_id': message.chat.id,
            'numero_unico': numero_unico,
            'codigo': codigo,
            'fecha_registro': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        guardar_json(GRATIS_FILE, gratis)
        
        # Generar y enviar QR
        qr_data = f"Número Único: {numero_unico}\nNombre: {nombre}\nCelular: {celular}"
        qr_filename = f"qr_gratis_{message.chat.id}.png"
        generar_qr(qr_data, qr_filename)
        
        with open(qr_filename, 'rb') as qr_file:
            bot.send_photo(message.chat.id, qr_file)
        
        os.remove(qr_filename)
        
        # Mensaje de confirmación
        bot.send_message(message.chat.id,
            f"¡Felicidades, {nombre}! 🎉\n\n"
            "Has obtenido una rifa gratis.\n"
            "Tu número único está en el código QR adjunto.\n\n"
            "¡Buena suerte! 🍀")
    else:
        bot.send_message(message.chat.id, "Por favor, ingrese un número de celular válido:")
        bot.register_next_step_handler(message, pedir_celular_gratis, nombre, codigo)

# Comando /ganador (solo admin)
@bot.message_handler(commands=['ganador'])
def ganador(message):
    if message.chat.id == ADMIN_CHAT_ID:
        compras = cargar_json(COMPRAS_FILE)
        if compras:
            # Elegir ganador aleatorio
            ganador = random.choice(compras)
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
        ganadores = cargar_json(GANADORES_FILE)
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
        gratis = cargar_json(GRATIS_FILE)
        if gratis:
            ganador = random.choice(gratis)
            bot.send_message(ADMIN_CHAT_ID,
                f"¡Ganador de rifa gratis seleccionado!\n\n"
                f"Nombre: {ganador['nombre']}\n"
                f"Celular: {ganador['celular']}\n"
                f"Número único: {ganador['numero_unico']}")
            
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
        links = cargar_json(LINKS_FILE)
        if links:
            lista = "\n".join([f"{i+1}. {link}" for i, link in enumerate(links)])
            bot.send_message(message.chat.id, f"Seleccione el número del link a eliminar:\n\n{lista}")
            bot.register_next_step_handler(message, eliminar_link)
        else:
            bot.send_message(message.chat.id, "No hay links registrados.")
    elif message.text == "Ver Links":
        links = cargar_json(LINKS_FILE)
        if links:
            lista = "\n".join([f"{i+1}. {link}" for i, link in enumerate(links)])
            bot.send_message(message.chat.id, f"Lista de links:\n\n{lista}")
        else:
            bot.send_message(message.chat.id, "No hay links registrados.")

def agregar_link(message):
    if not message or not message.text:
        return
    link = message.text.strip()
    if link.startswith('http://') or link.startswith('https://'):
        links = cargar_json(LINKS_FILE)
        if link not in links:
            links.append(link)
            guardar_json(LINKS_FILE, links)
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
        links = cargar_json(LINKS_FILE)
        if 0 <= indice < len(links):
            link_eliminado = links.pop(indice)
            guardar_json(LINKS_FILE, links)
            bot.send_message(message.chat.id, f"✅ Link '{link_eliminado}' eliminado exitosamente.")
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
        historial = cargar_json(HISTORIAL_RIFA_FILE)
        mostrar_lista_formateada(message, historial, "pagada", markup)
    elif message.text == "Participantes Pagados":
        participantes = cargar_json(COMPRAS_FILE)
        mostrar_lista_formateada(message, participantes, "pagada", markup)
    else:
        bot.send_message(message.chat.id, "Opción no válida. Usa /lista para empezar de nuevo.", reply_markup=markup)

def mostrar_lista_gratis(message):
    if not message or not message.text:
        return

    markup = types.ReplyKeyboardRemove()
    if message.text == "Ganadores Gratis":
        historial = cargar_json(HISTORIAL_GRATIS_FILE)
        mostrar_lista_formateada(message, historial, "gratis", markup)
    elif message.text == "Participantes Gratis":
        participantes = cargar_json(GRATIS_FILE)
        mostrar_lista_formateada(message, participantes, "gratis", markup)
    else:
        bot.send_message(message.chat.id, "Opción no válida. Usa /lista para empezar de nuevo.", reply_markup=markup)

def mostrar_lista_formateada(message, datos, tipo, markup):
    if not datos:
        bot.send_message(message.chat.id, "No hay datos para mostrar.", reply_markup=markup)
        return

    texto = ""
    if isinstance(datos, dict):  # Para historial
        for fecha, participantes in datos.items():
            texto += f"📅 Fecha: {fecha}\n"
            for i, participante in enumerate(participantes, 1):
                texto += f"{i}. {participante['nombre']} - {participante.get('cantidad', 1)} boleto(s)\n"
                texto += f"ID: {participante['chat_id']}\n\n"
    else:  # Para datos actuales
        for i, participante in enumerate(datos, 1):
            texto += f"{i}. {participante['nombre']} - {participante.get('cantidad', 1)} boleto(s)\n"
            texto += f"ID: {participante['chat_id']}\n\n"

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
    if message.text == "Descargar Rifas":
        with open(COMPRAS_FILE, 'rb') as file:
            bot.send_document(message.chat.id, file)
    elif message.text == "Descargar Gratis":
        with open(GRATIS_FILE, 'rb') as file:
            bot.send_document(message.chat.id, file)
    elif message.text == "Descargar Historial":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Historial Rifas", "Historial Gratis")
        bot.send_message(message.chat.id, "¿Qué historial deseas descargar?", reply_markup=markup)
        bot.register_next_step_handler(message, descargar_historial)

def descargar_historial(message):
    if message.text == "Historial Rifas":
        with open(HISTORIAL_RIFA_FILE, 'rb') as file:
            bot.send_document(message.chat.id, file)
    elif message.text == "Historial Gratis":
        with open(HISTORIAL_GRATIS_FILE, 'rb') as file:
            bot.send_document(message.chat.id, file)

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
    if message.text == "Borrar Historial Rifas":
        guardar_json(HISTORIAL_RIFA_FILE, {})
        bot.send_message(message.chat.id, "✅ Historial de rifas borrado exitosamente.", reply_markup=markup)
    
    elif message.text == "Borrar Historial Gratis":
        guardar_json(HISTORIAL_GRATIS_FILE, {})
        bot.send_message(message.chat.id, "✅ Historial de rifas gratis borrado exitosamente.", reply_markup=markup)
    
    elif message.text == "Borrar Compradores Actuales":
        # Crear respaldo antes de borrar
        compras = cargar_json(COMPRAS_FILE)
        fecha = datetime.now().strftime('%Y-%m-%d')
        historial = cargar_json(HISTORIAL_RIFA_FILE)
        historial[fecha] = compras
        guardar_json(HISTORIAL_RIFA_FILE, historial)
        
        # Borrar compradores actuales
        guardar_json(COMPRAS_FILE, [])
        bot.send_message(message.chat.id, 
            "✅ Compradores actuales borrados exitosamente.\n"
            "📋 Se ha creado un respaldo en el historial.", 
            reply_markup=markup)
    
    elif message.text == "Borrar Participantes Gratis":
        # Crear respaldo antes de borrar
        gratis = cargar_json(GRATIS_FILE)
        fecha = datetime.now().strftime('%Y-%m-%d')
        historial = cargar_json(HISTORIAL_GRATIS_FILE)
        historial[fecha] = gratis
        guardar_json(HISTORIAL_GRATIS_FILE, historial)
        
        # Borrar participantes gratis actuales
        guardar_json(GRATIS_FILE, [])
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
            guardar_json(HISTORIAL_RIFA_FILE, datos)
            bot.send_message(message.chat.id, 
                "✅ Datos guardados exitosamente en el historial de rifas.", 
                reply_markup=markup)
        
        elif tipo_subida_actual == "Subir Historial Gratis":
            guardar_json(HISTORIAL_GRATIS_FILE, datos)
            bot.send_message(message.chat.id, 
                "✅ Datos guardados exitosamente en el historial de rifas gratis.", 
                reply_markup=markup)
        
        elif tipo_subida_actual == "Subir Lista Compradores":
            guardar_json(COMPRAS_FILE, datos)
            bot.send_message(message.chat.id, 
                "✅ Lista de compradores actualizada exitosamente.", 
                reply_markup=markup)
        
        elif tipo_subida_actual == "Subir Lista Gratis":
            guardar_json(GRATIS_FILE, datos)
            bot.send_message(message.chat.id, 
                "✅ Lista de participantes gratis actualizada exitosamente.", 
                reply_markup=markup)

        tipo_subida_actual = None

    except json.JSONDecodeError:
        markup = types.ReplyKeyboardRemove()
        bot.send_message(message.chat.id, "❌ El archivo no es un JSON válido.", reply_markup=markup)
    except Exception as e:
        markup = types.ReplyKeyboardRemove()
        bot.send_message(message.chat.id, f"❌ Error al procesar el archivo: {str(e)}", reply_markup=markup)

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

# Iniciar el bot
if __name__ == '__main__':
    try:
        print('🤖 Bot iniciado exitosamente...')
        # Usar skip_pending=True para ignorar mensajes antiguos al iniciar
        bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print(f'❌ Error al iniciar el bot: {e}')
    finally:
        print('👋 Bot detenido') 