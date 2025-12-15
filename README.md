## Definicion de Proyecto

Crear una herramienta para mejorar las ventas de Pika Snacks. Pika es una empresa que vende Snacks Saludables, sus principales productos son Arepas, Waffles, Muffins. Los principales clientes de Pika son personas naturales y hoteles. 

El principal medio de contacto de Pika es por WhatsApp, por esta de forma manual se hace la interaccion con sus clientes y se hacen las ventas. Se tiene ya cuentas de WhatsApp business y un catalogo de producto. 


## Objetivo Principal 

El objetivo principal es mejorar las ventas de Pika Snacks. 


## Metodologia 

LA idea es poder incluir herramientas de inteligencia artificial al modelo de ventas de Pika. En principio con dos herramientas. 

1. Un chatbot que pueda responder preguntas de los clientes y hacer ventas. Se usara un tercero como infraestructura para el chatbot pero se analizaran las conversaciones hasta hoy para poder entrenar el chatbot.
2. Un analisis de ventas que pueda predecir las ventas futuras y ayudar a la toma de decisiones. Para esto es necesario buscar en las conversaciones todos las interacciones que se volvieron una venta. 


## Desarrollo 

Se usara un framework de chatbot para el chatbot y un framework de analisis de datos para el analisis de ventas. 

Para el desarrollo se usaran las siguientes herramientas:

1. Python. 
2. OPenAI para analizar las conversaciones. 
3. Se debe usar Git para control de versiones. 
4. Se debe usar GitHub para subir el codigo. 



## Proceso 

1. Se van a exportar las conversaciones a un repositiorio de Google Drive. 
2. Se tomara cada archivo de conversacion y analizara para sacar los principales insights de la conversacion, tanto si hay o no hay venta. 
3. De las conversaciones que terminaron siendo una venta se sacara informacion relevante: Nombre o numero de telefomo de cliente, producto que compro, cantidad, direccion de envio, fecha de la compra. 
4. Se creara archivos csv con la informacion de las ventas, esto se subira a una base de datos en la nube. 
5. Con el analisis de AI se definiarn las preuntas y respusetas mas comunes para entrenar el chatbot. 

---

## Guía rápida (Opción A - sin Docker)

Levanta un backend mínimo en local. Ideal para empezar hoy y migrar luego a Docker/Postgres.

### Requisitos

- Python 3.11+
- pip actualizado (`pip install --upgrade pip`)

### Pasos

1) Crear entorno y dependencias mínimas

```
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install "fastapi" "uvicorn[standard]" "python-dotenv"
```

2) Crear estructura mínima

```
mkdir -p app
```

Crea el archivo `app/main.py` con este contenido:

```python
from fastapi import FastAPI

app = FastAPI(title="Pika Backend")

@app.get("/health")
def health():
    return {"status": "ok"}
```

3) Ejecutar el servidor

```
uvicorn app.main:app --reload --port 8000
```

- Verifica: http://localhost:8000/health y http://localhost:8000/docs

### Notas

- Puedes usar SQLite más adelante agregando una `DATABASE_URL` si lo necesitas.
- Cuando quieras escalar, agregaremos Docker y Postgres (Opción B).
