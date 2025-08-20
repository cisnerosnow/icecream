![Logo del proyecto](./logo.png)

# Icecream 🍦

**Icecream** es una herramienta ligera desarrollada en Python con una pequeña interfaz (Gradio) para facilitar la creación de proyectos Cordova directamente desde una GUI web local.

## 🚀 Características

- Interfaz en Gradio para elegir:
  - Archivo `.html` base.
  - Título de la app (puede incluir espacios).
  - Nombre de carpeta y paquete (tipo `com.miempresa.miapp`).
- Automatiza comandos Cordova:
  - `cordova create`
  - `cordova platform add android`
- Ideal para prototipos rápidos y generación de `.apk` o `.aab` listas para producción.

## 🧰 Requisitos

- Node.js y Cordova instalados globalmente:
  ```bash
  npm install -g cordova
  ```

- Python 3.10+ (Testeado especificamente con: Python 3.12.4)

- Crear un venv:
  ```bash
  python -m venv venv
  ```

- Activas el venv:
  ```bash
  .\venv\Scripts\Activate
  ```

- Asegurate de usar este comando:
  ```bash
  python -m pip install --upgrade pip setuptools wheel
  ```

- Instalar dependencias de Python:
  ```bash
  python -m pip install -r requirements.txt
  ```

## 📦 Estructura del proyecto

```bash
icecream/
├── app.py                  # Script principal con Gradio
├── requirements.txt
└── README.md
```

## 🛠️ Uso

1. Ejecuta la app con:

   ```bash
   python app.py
   ```

2. Abre el navegador y sigue la interfaz para:
   - Seleccionar tu archivo `.html`.
   - Especificar el nombre del app.
   - Generar automáticamente un proyecto Cordova listo.

3. El proyecto se crea dentro de `C:/dev/` con la estructura Cordova estándar.

## 📤 Salida esperada

- Un directorio creado como `C:/dev/NombreApp`
- Proyecto Cordova con Android configurado
- Archivo .aab compilado y listo
- Solo falta que tu lo firmes para que lo subas al playstore

## 📄 Licencia

MIT License
