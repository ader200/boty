from http.server import BaseHTTPRequestHandler
import json
from rifa import bot, TOKEN

def webhook_handler(event, context):
    try:
        # Obtener el cuerpo de la solicitud
        body = json.loads(event['body'])
        
        # Procesar la actualización con el bot
        bot.process_new_updates([body])
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'OK'})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Leer el cuerpo de la solicitud
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            event = {'body': post_data.decode('utf-8')}
            
            # Procesar la solicitud
            response = webhook_handler(event, None)
            
            # Enviar respuesta
            self.send_response(response['statusCode'])
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(response['body'].encode('utf-8'))
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8')) 