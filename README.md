# Bot de Rifas

Bot de Telegram para gestionar rifas pagadas y gratuitas con soporte para MongoDB.

## Requisitos

- Python 3.8 o superior
- MongoDB 4.4 o superior
- Las dependencias listadas en `requirements.txt`

## Instalación

1. Clonar el repositorio:
```bash
git clone <url-del-repositorio>
cd <directorio-del-repositorio>
```

2. Crear un entorno virtual e instalar dependencias:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Configurar las variables de entorno:
   - Crear un archivo `.env` en el directorio raíz
   - Agregar las siguientes variables:
```
MONGODB_URI=<tu-uri-de-mongodb>
TOKEN=<tu-token-de-telegram-bot>
ADMIN_CHAT_ID=<id-del-chat-admin>
CHAT_SOPORTE=<id-del-chat-soporte>
CHAT_HISTORIAL=<id-del-chat-historial>
```

## Configuración de MongoDB

1. Crear una base de datos llamada `rifa_db`
2. Las colecciones se crearán automáticamente al iniciar el bot:
   - `registro`
   - `rifas_pagadas`
   - `rifas_gratis`
   - `historial_rifas`
   - `historial_gratis`
   - `links`

## Uso

1. Iniciar el bot:
```bash
python ripe.py
```

2. Comandos disponibles:
   - `/start` - Iniciar el bot
   - `/rifa` - Comprar rifa
   - `/gratis` - Obtener rifa gratis
   - `/ganador` - Elegir ganador (solo admin)
   - `/ganadorz` - Gestionar lista de ganadores (solo admin)
   - `/uno` - Elegir ganador aleatorio (solo admin)
   - `/pi` - Elegir ganador gratis (solo admin)
   - `/qe` - Gestionar links de páginas web (solo admin)
   - `/lista` - Ver listas de rifas
   - `/descargar` - Descargar archivos
   - `/borrar_historial` - Borrar historial
   - `/cliente` - Iniciar soporte al cliente
   - `/gods` - Iniciar chat con cliente específico (solo admin)

## Características

- Gestión de rifas pagadas y gratuitas
- Sistema de códigos para rifas gratuitas
- Soporte al cliente integrado
- Backup automático diario
- Historial de rifas y ganadores
- Interfaz de administración completa

## Notas

- Los backups se realizan automáticamente todos los días a las 23:59
- Los archivos de backup se envían al canal de historial configurado
- Los datos se almacenan en MongoDB para mayor seguridad y escalabilidad 