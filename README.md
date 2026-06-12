# JarvisAlarm 🤖

> Despertador inteligente para Windows con voz tipo Jarvis (Iron Man).
> Tu PC se enciende sola, te saluda con voz personalizada, te da el clima de tu ciudad, te avisa de feriados y abre tu video/música favorita de YouTube — todo automático.

![Status](https://img.shields.io/badge/status-active-success)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11-green)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-blue)

## ✨ Características

- 🌅 **Encendido automático** desde BIOS (Wake on RTC)
- 🎙️ **Voz clonable** (Fish Audio o Edge TTS gratis)
- 🌤️ **Clima en tiempo real** vía Open-Meteo (sin API key)
- 📅 **Detección de feriados** (Bolivia incluida, configurable)
- 🎬 **Auto-play YouTube** en navegador en kiosk mode
- 🔊 **Efectos de sonido** intro/outro cinematográficos
- 💬 **Mensajes aleatorios** — más de 50 variaciones de saludos
- 🌡️ **Recomendaciones contextuales** según clima (paraguas, abrigo, hidratación)
- 🇪🇸 **Totalmente en español** con soporte para acentos latinos

## 📋 Requisitos

- Windows 10 u 11
- Python 3.11 ([descargar](https://www.python.org/downloads/release/python-3119/))
- Acceso a BIOS (F2 o Supr al encender)
- Brave Browser (opcional, también funciona con Chrome/Edge)
- Conexión a internet

## 🚀 Instalación en 5 pasos

### Paso 1 — Configurar BIOS

1. Reinicia tu PC y presiona **F2** o **Supr** al arrancar.
2. Busca **Wake on RTC Alarm** / **Auto Power On** / **Resume by Alarm** (en sección Power Management o Advanced).
3. Actívalo y configura la hora deseada (ej: 04:55 si te despiertas a las 5:00).
4. Guarda con **F10** y sale.

### Paso 2 — Instalar Python y el proyecto

1. Instala [Python 3.11](https://www.python.org/downloads/release/python-3119/) marcando **"Add Python to PATH"**.
2. Clona o descarga este repositorio:
   ```bash
   git clone https://github.com/markotenory/jarvis-alarm.git
   ```
3. Mueve la carpeta a `C:\JarvisAlarm`.
4. Doble click en **`install.bat`** — esto crea un entorno virtual e instala dependencias.

### Paso 3 — Personalizar

1. Copia `config.example.json` y renómbralo a `config.json`.
2. Abre `config.json` con Bloc de notas y configura:
   - `user_name`: tu nombre
   - `city`, `latitude`, `longitude`, `timezone`: tu ubicación
   - `youtube_url`: el video/playlist que se abrirá al despertar
   - `tts_provider`: `"edge"` (gratis) o `"fish_audio"` (cloneada, $5/mes)
   - `messages`: edita los saludos a tu gusto

### Paso 4 — Programar la tarea de Windows

Click derecho sobre **`setup_task.ps1`** → **Ejecutar con PowerShell**.

Esto programa la tarea para ejecutarse todos los días a las 5:00 AM.

Para probarla sin esperar:
```cmd
schtasks /run /tn JarvisAlarm
```

### Paso 5 — Autologon (saltar PIN)

1. Presiona `Win + R`, escribe `netplwiz` y Enter.
2. Selecciona tu usuario.
3. Desmarca *"Los usuarios deben escribir su nombre y contraseña"*.
4. Escribe tu contraseña dos veces.

> **Windows 11**: si la opción está oculta, ejecuta como administrador:
> ```cmd
> reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\PasswordLess\Device" /v DevicePasswordLessBuildVersion /t REG_DWORD /d 0 /f
> ```

## ⚙️ Configuración avanzada

### Cambiar la voz

**Opción A — Edge TTS (gratis)**:
```json
"tts_provider": "edge",
"voice": "es-BO-MarceloNeural"
```

Otras voces disponibles: `es-MX-JorgeNeural`, `es-CO-GonzaloNeural`, `es-AR-TomasNeural`, etc.

**Opción B — Fish Audio (voz clonada, $5/mes)**:
1. Crea cuenta en [fish.audio](https://fish.audio).
2. Clona una voz subiendo un audio limpio de 1-3 minutos.
3. Obtén tu API key y model ID.
4. Configura:
   ```json
   "tts_provider": "fish_audio",
   "fish_audio_api_key": "tu_key",
   "fish_audio_model_id": "tu_model_id"
   ```

### Agregar feriados personalizados

En `config.json`, sección `custom_holidays`:
```json
"custom_holidays": [
  {"date": "12-25", "name": "Navidad"},
  {"date": "2026-09-24", "name": "Día de Santa Cruz"}
]
```

### Efectos de sonido

Pon tus MP3 en la carpeta `sounds/`:
- `sound_pre_intro`: alarma/timbre que suena PRIMERO
- `sound_intro`: efecto que suena ANTES de la voz (boot up Jarvis)
- `sound_outro`: chime de cierre al terminar

## 🛠️ Estructura del proyecto

```
JarvisAlarm/
├── jarvis_alarm.py         # Script principal
├── config.example.json     # Plantilla de configuración
├── requirements.txt        # Dependencias Python
├── install.bat             # Instalador automático
├── run_jarvis.bat          # Ejecutor silencioso
├── debug_jarvis.bat        # Ejecutor con consola visible
├── setup_task.ps1          # Programador de tarea Windows
├── sounds/                 # Efectos de sonido
└── README.md               # Esta documentación
```

## 🐛 Solución de problemas

| Problema | Solución |
|----------|----------|
| No suena nada | Verifica volumen del sistema y que `pygame` esté instalado |
| Error de clima | Verifica internet y coordenadas correctas en `config.json` |
| Tarea no se dispara | `schtasks /query /tn JarvisAlarm` para verificar |
| PIN sigue apareciendo | Revisar Paso 5 — algunos teléfonos requieren quitar Windows Hello PIN |
| Brave no abre | Verifica `brave_path` en config — usa `where brave` en CMD para encontrar ruta |

## 📺 Demo

[Ver video en YouTube](https://youtube.com/@tuusername)

## 🤝 Contribuir

Pull requests bienvenidos. Para cambios mayores, abre un issue primero.

## 📄 Licencia

MIT — ver [LICENSE](LICENSE).

## ⭐ Si te sirvió

Dale una ⭐ al repositorio y compártelo. Eso ayuda muchísimo a que más gente pueda despertarse como en una película.

---

Hecho con ❤️ por [Mark tenorio](https://github.com/markotenory)
