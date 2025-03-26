from flask import Flask, request
import threading
from rifa import bot, TOKEN
import os

app = Flask(__name__)

# Ruta principal para verificar que el servidor está funcionando
@app.route('/')
def home():
    return "Bot de Rifas funcionando correctamente! 🎉"

# Ruta para el webhook de Telegram
@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = bot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK"

def run_bot():
    """Función para ejecutar el bot en modo polling"""
    print("Iniciando bot en modo polling...")
    bot.infinity_polling(skip_pending=True)

if __name__ == '__main__':
    # Iniciar el bot en un hilo separado
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Iniciar el servidor web
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port) 