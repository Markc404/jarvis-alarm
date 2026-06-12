"""
Jarvis Alarm - Despertador con voz tipo Jarvis (Iron Man)
Reproduce saludo, informe del clima y un video de YouTube en Brave.

Uso: python jarvis_alarm.py
"""

import asyncio
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import edge_tts
import pygame
import requests

# -----------------------------
# Configuracion
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
AUDIO_PATH = BASE_DIR / "jarvis_output.mp3"
LOG_PATH = BASE_DIR / "jarvis.log"
CACHE_DIR = BASE_DIR / "audio_cache"
CACHE_DIR.mkdir(exist_ok=True)


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# -----------------------------
# Clima (Open-Meteo, sin API key)
# -----------------------------
WEATHER_CODES = {
    0: "cielo despejado", 1: "mayormente despejado", 2: "parcialmente nublado",
    3: "nublado", 45: "neblina", 48: "neblina con escarcha",
    51: "llovizna ligera", 53: "llovizna moderada", 55: "llovizna densa",
    61: "lluvia ligera", 63: "lluvia moderada", 65: "lluvia fuerte",
    71: "nevada ligera", 73: "nevada moderada", 75: "nevada fuerte",
    80: "chubascos", 81: "chubascos moderados", 82: "chubascos intensos",
    95: "tormenta eléctrica", 96: "tormenta con granizo ligero", 99: "tormenta con granizo fuerte",
}

DIAS_SEMANA = {
    "Monday": "lunes", "Tuesday": "martes", "Wednesday": "miércoles",
    "Thursday": "jueves", "Friday": "viernes", "Saturday": "sábado",
    "Sunday": "domingo",
}
MESES = {
    "January": "enero", "February": "febrero", "March": "marzo",
    "April": "abril", "May": "mayo", "June": "junio",
    "July": "julio", "August": "agosto", "September": "septiembre",
    "October": "octubre", "November": "noviembre", "December": "diciembre",
}


WEATHER_CACHE_FILE = BASE_DIR / "weather_last.json"
HOLIDAYS_CACHE_FILE = BASE_DIR / "holidays_cache.json"


def get_weather(cfg: dict):
    """Fetch con 3 reintentos + cache en disco como fallback."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": cfg["latitude"],
        "longitude": cfg["longitude"],
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,apparent_temperature",
        "hourly": "precipitation_probability,temperature_2m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_probability_mean,uv_index_max",
        "timezone": cfg.get("timezone", "auto"),
        "forecast_days": 1,
        "forecast_hours": 12,
    }
    last_error = None
    for attempt in range(1, 4):
        try:
            log(f"[CLIMA] Intento {attempt}/3 a Open-Meteo...")
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
            # Guardar cache exitoso
            try:
                with open(WEATHER_CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f)
            except Exception:
                pass
            return data
        except Exception as e:
            last_error = e
            log(f"[CLIMA] Fallo intento {attempt}: {e}")
            if attempt < 3:
                time.sleep(2 * attempt)  # backoff: 2s, 4s

    # Si todos los intentos fallaron, usar cache anterior
    log(f"[CLIMA] Todos los intentos fallaron. Ultimo error: {last_error}")
    try:
        if WEATHER_CACHE_FILE.exists():
            with open(WEATHER_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            log("[CLIMA] Usando cache previo de clima (puede estar desactualizado)")
            return cached
    except Exception as e:
        log(f"[CLIMA] No se pudo leer cache: {e}")
    return None


def get_holidays(cfg: dict) -> list:
    """Obtiene feriados oficiales de Bolivia desde Nager.Date + custom del config."""
    country = cfg.get("holidays_country", "BO")
    year = datetime.now().year
    cache_key = f"{country}_{year}"

    # Intentar leer cache primero
    try:
        if HOLIDAYS_CACHE_FILE.exists():
            with open(HOLIDAYS_CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
            if cache.get("key") == cache_key:
                holidays = list(cache.get("data", []))
                # Agregar feriados custom del config
                holidays.extend(cfg.get("custom_holidays", []))
                return holidays
    except Exception:
        pass

    # Fetch a Nager.Date API
    holidays = []
    try:
        url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country}"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        for h in r.json():
            holidays.append({
                "date": h["date"],
                "name": h.get("localName") or h.get("name"),
            })
        # Guardar cache
        try:
            with open(HOLIDAYS_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({"key": cache_key, "data": holidays}, f, ensure_ascii=False)
        except Exception:
            pass
        log(f"[FERIADOS] {len(holidays)} feriados {country} {year} cargados")
    except Exception as e:
        log(f"[FERIADOS] Error obteniendo feriados: {e}")

    # Agregar feriados custom (siempre, incluso si la API falló)
    holidays.extend(cfg.get("custom_holidays", []))
    return holidays


def check_today_holiday(holidays: list) -> dict | None:
    """Verifica si hoy es feriado. Retorna {date, name} o None."""
    today = datetime.now().strftime("%Y-%m-%d")
    today_mmdd = datetime.now().strftime("%m-%d")
    for h in holidays:
        if h.get("date") == today or h.get("date") == today_mmdd:
            return h
    return None


def build_speech(cfg: dict, weather) -> str:
    """
    Construye el speech usando plantillas del config con placeholders:
      {user}, {time}, {date}, {city}, {temp}, {tmax}, {tmin},
      {humidity}, {wind}, {condition}, {rain_prob}
    """
    user = cfg.get("user_name", "señor")
    msgs = cfg.get("messages", {})
    now = datetime.now()
    hour = now.hour

    def pick(key, default):
        """Si el mensaje es una lista, elige uno al azar. Si es string, lo usa tal cual."""
        val = msgs.get(key, default)
        if isinstance(val, list):
            return random.choice(val) if val else default
        return val

    if hour < 12:
        greeting_template = pick("greeting_morning", "Buenos días, {user}.")
    elif hour < 19:
        greeting_template = pick("greeting_afternoon", "Buenas tardes, {user}.")
    else:
        greeting_template = pick("greeting_evening", "Buenas noches, {user}.")

    time_str = now.strftime("%H:%M")
    dia = DIAS_SEMANA.get(now.strftime("%A"), now.strftime("%A"))
    mes = MESES.get(now.strftime("%B"), now.strftime("%B"))
    date_str = f"{dia} {now.day} de {mes}"

    common = {
        "user": user,
        "time": time_str,
        "date": date_str,
        "city": cfg.get("city", ""),
    }

    parts = [greeting_template.format(**common)]
    parts.append(pick("time_date", "Son las {time} horas, {date}.").format(**common))
    parts.append(pick("welcome_rested", "Espero que haya descansado bien.").format(**common))

    if weather:
        try:
            current = weather["current"]
            daily = weather["daily"]
            data = dict(common)
            data["temp"] = round(current["temperature_2m"])
            data["humidity"] = round(current["relative_humidity_2m"])
            data["wind"] = round(current["wind_speed_10m"])
            data["condition"] = WEATHER_CODES.get(current["weather_code"], "condiciones variables")
            data["tmax"] = round(daily["temperature_2m_max"][0])
            data["tmin"] = round(daily["temperature_2m_min"][0])
            # Sensacion termica (apparent_temperature)
            try:
                data["apparent_temp"] = round(current.get("apparent_temperature", current["temperature_2m"]))
            except Exception:
                data["apparent_temp"] = data["temp"]
            # Indice UV maximo del dia
            try:
                uv = daily.get("uv_index_max", [None])[0]
                data["uv_index"] = round(uv) if uv is not None else 0
            except Exception:
                data["uv_index"] = 0
            # Calcular probabilidad real de lluvia: promedio de proximas 6 horas
            # (mucho mas alineado con lo que muestran weather.com / clima.com)
            try:
                hourly_probs = weather.get("hourly", {}).get("precipitation_probability", [])
                next_hours = [p for p in hourly_probs[:6] if p is not None]
                if next_hours:
                    rain_prob = int(sum(next_hours) / len(next_hours))
                else:
                    rain_prob = int(daily.get("precipitation_probability_mean", [0])[0] or 0)
            except Exception:
                rain_prob = int(daily.get("precipitation_probability_max", [0])[0] or 0)
            data["rain_prob"] = rain_prob
            log(f"[CLIMA] Probabilidad lluvia proximas 6h: {rain_prob}%")

            # Detectar feriados (hoy y mañana)
            try:
                from datetime import timedelta
                holidays_list = get_holidays(cfg)
                today_h = check_today_holiday(holidays_list)
                tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                tomorrow_mmdd = (datetime.now() + timedelta(days=1)).strftime("%m-%d")
                tomorrow_h = None
                for h in holidays_list:
                    if h.get("date") == tomorrow_str or h.get("date") == tomorrow_mmdd:
                        tomorrow_h = h
                        break

                if today_h:
                    data["holiday_name"] = today_h.get("name", "feriado")
                    log(f"[FERIADO HOY] {data['holiday_name']}")
                    parts.insert(2, pick("holiday_notice", "Hoy es {holiday_name}, feriado nacional. Disfrute su día libre, {user}.").format(**data))

                if tomorrow_h:
                    data["holiday_tomorrow"] = tomorrow_h.get("name", "feriado")
                    log(f"[FERIADO MAÑANA] {data['holiday_tomorrow']}")
                    parts.insert(2 if not today_h else 3,
                                 pick("holiday_tomorrow_notice", "Aviso: mañana será {holiday_tomorrow}, día feriado. Planifique en consecuencia, {user}.").format(**data))
            except Exception as e:
                log(f"[FERIADOS] Error en deteccion: {e}")

            parts.append(pick("weather_intro", "Permítame informarle del clima en {city}.").format(**data))
            parts.append(pick("weather_current", "Actualmente {temp} grados, con {condition}, humedad del {humidity} por ciento, y vientos de {wind} kilómetros por hora.").format(**data))
            parts.append(pick("weather_extras", "Sensación térmica de {apparent_temp} grados. Índice UV máximo del día: {uv_index}.").format(**data))
            parts.append(pick("weather_forecast", "El pronóstico de hoy: máxima de {tmax} y mínima de {tmin} grados, con un {rain_prob} por ciento de probabilidad de lluvia.").format(**data))

            # Recomendacion contextual segun clima real (prioridad arriba > abajo)
            cond_lower = data["condition"].lower()
            rec_key = None
            if data["rain_prob"] >= 70:
                rec_key = "warning_heavy_rain"
            elif data["rain_prob"] >= 50:
                rec_key = "warning_rain"
            elif data["temp"] >= 32:
                rec_key = "warning_extreme_heat"
            elif data["temp"] >= 28 and ("despejado" in cond_lower or "mayormente" in cond_lower):
                rec_key = "warning_sunny_hot"
            elif data["temp"] >= 28:
                rec_key = "warning_hot"
            elif data["temp"] <= 10:
                rec_key = "warning_very_cold"
            elif data["temp"] <= 15:
                rec_key = "warning_cold"
            elif data["wind"] >= 35:
                rec_key = "warning_windy"
            elif "neblina" in cond_lower or "fog" in cond_lower:
                rec_key = "warning_foggy"
            elif "despejado" in cond_lower:
                rec_key = "recommendation_clear"
            elif "nublado" in cond_lower:
                rec_key = "recommendation_cloudy"

            if rec_key:
                template = pick(rec_key, "")
                if template:
                    parts.append(template.format(**data))
        except Exception as e:
            log(f"Error building weather speech: {e}")
            parts.append(pick("weather_error", "Los datos del clima no están disponibles, {user}.").format(**common))
    else:
        parts.append(pick("weather_unavailable", "No pude obtener el reporte del clima, {user}.").format(**common))

    parts.append(pick("outro", "Ahora reproduciré su selección matinal. Tenga un día productivo.").format(**common))
    return " ".join(parts)


# -----------------------------
# Voz - cache key
# -----------------------------
def _cache_key(text: str, provider: str, voice_id: str, model: str) -> str:
    raw = f"{provider}|{voice_id}|{model}|{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


# -----------------------------
# Voz - Chatterbox (local, open source)
# -----------------------------
_chatterbox_model = None


def synthesize_chatterbox(text: str, cfg: dict, out_path: Path) -> Path:
    global _chatterbox_model

    reference_audio = cfg.get("chatterbox_reference_audio", "").strip()
    language = cfg.get("chatterbox_language", "es")
    device = cfg.get("chatterbox_device", "cpu")

    if not reference_audio:
        raise ValueError("Falta chatterbox_reference_audio en config.json")
    ref_path = Path(reference_audio)
    if not ref_path.is_absolute():
        ref_path = BASE_DIR / ref_path
    if not ref_path.exists():
        raise ValueError(f"No existe audio de referencia: {ref_path}")

    log("[CHATTERBOX] Importando librerias...")
    try:
        import torchaudio
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    except ImportError as e:
        raise RuntimeError(f"Chatterbox no instalado. Ejecuta install_chatterbox.bat. {e}")

    if _chatterbox_model is None:
        log("[CHATTERBOX] Cargando modelo multilingue (primera vez ~30 seg)...")
        _chatterbox_model = ChatterboxMultilingualTTS.from_pretrained(device=device)
        log("[CHATTERBOX] Modelo cargado.")

    log(f"[CHATTERBOX] Sintetizando {len(text)} chars en idioma '{language}'...")
    wav = _chatterbox_model.generate(
        text,
        language_id=language,
        audio_prompt_path=str(ref_path),
    )

    wav_path = out_path.with_suffix(".wav")
    torchaudio.save(str(wav_path), wav, _chatterbox_model.sr)
    log(f"[CHATTERBOX] Audio guardado: {wav_path.name}")
    return wav_path


# -----------------------------
# Voz - XTTS v2 (Coqui, local)
# -----------------------------
_xtts_model = None


def synthesize_xtts(text: str, cfg: dict, out_path: Path) -> Path:
    global _xtts_model

    reference_audio = cfg.get("xtts_reference_audio", "").strip()
    language = cfg.get("xtts_language", "es")
    device = cfg.get("xtts_device", "cpu")

    if not reference_audio:
        raise ValueError("Falta xtts_reference_audio en config.json")
    ref_path = Path(reference_audio)
    if not ref_path.is_absolute():
        ref_path = BASE_DIR / ref_path
    if not ref_path.exists():
        raise ValueError(f"No existe audio de referencia: {ref_path}")

    # Aceptar TOS de Coqui automaticamente
    os.environ["COQUI_TOS_AGREED"] = "1"

    log("[XTTS] Importando librerias...")
    try:
        from TTS.api import TTS
    except ImportError as e:
        raise RuntimeError(f"XTTS no instalado. Ejecuta install_xtts.bat. {e}")

    if _xtts_model is None:
        log("[XTTS] Cargando modelo xtts_v2 (primera vez baja ~2 GB)...")
        _xtts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
        log("[XTTS] Modelo cargado.")

    log(f"[XTTS] Sintetizando {len(text)} chars en idioma '{language}'...")
    wav_path = out_path.with_suffix(".wav")
    _xtts_model.tts_to_file(
        text=text,
        speaker_wav=str(ref_path),
        language=language,
        file_path=str(wav_path),
    )
    log(f"[XTTS] Audio guardado: {wav_path.name}")
    return wav_path


# -----------------------------
# Voz - ElevenLabs API
# -----------------------------
def synthesize_elevenlabs(text: str, cfg: dict, out_path: Path) -> None:
    api_key = cfg.get("elevenlabs_api_key", "").strip()
    voice_id = cfg.get("elevenlabs_voice_id", "").strip()
    model = cfg.get("elevenlabs_model", "eleven_flash_v2_5")

    if not api_key or not voice_id:
        raise ValueError("ElevenLabs no configurado")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": model,
        "voice_settings": {
            "stability": float(cfg.get("elevenlabs_stability", 0.5)),
            "similarity_boost": float(cfg.get("elevenlabs_similarity", 0.75)),
            "style": float(cfg.get("elevenlabs_style", 0.0)),
            "use_speaker_boost": True,
        },
    }
    r = requests.post(url, json=payload, headers=headers, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs HTTP {r.status_code}: {r.text[:200]}")
    out_path.write_bytes(r.content)


# -----------------------------
# Voz - Fish Audio API
# -----------------------------
def synthesize_fish_audio(text: str, cfg: dict, out_path: Path) -> None:
    """Genera audio con Fish Audio API en una sola llamada."""
    api_key = cfg.get("fish_audio_api_key", "").strip()
    model_id = cfg.get("fish_audio_model_id", "").strip()
    model = cfg.get("fish_audio_model", "s1")
    speed = float(cfg.get("fish_audio_speed", 0.85))
    volume = float(cfg.get("fish_audio_volume", 0))

    if not api_key or not model_id:
        raise ValueError("Fish Audio no configurado")

    url = "https://api.fish.audio/v1/tts"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "model": model,
    }
    payload = {
        "text": text,
        "reference_id": model_id,
        "format": "mp3",
        "mp3_bitrate": 128,
        "normalize": True,
        "latency": "normal",
        "chunk_length": 200,
        "prosody": {"speed": speed, "volume": volume},
    }
    r = requests.post(url, json=payload, headers=headers, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"Fish Audio HTTP {r.status_code}: {r.text[:300]}")
    out_path.write_bytes(r.content)


# -----------------------------
# Voz - Edge TTS (fallback gratis)
# -----------------------------
async def synthesize_edge(text: str, cfg: dict, out_path: Path) -> None:
    communicate = edge_tts.Communicate(
        text=text,
        voice=cfg.get("voice", "es-BO-MarceloNeural"),
        rate=cfg.get("voice_rate", "+0%"),
        volume=cfg.get("voice_volume", "+0%"),
    )
    await communicate.save(str(out_path))


# -----------------------------
# Voz - Dispatcher con cache
# -----------------------------
async def synthesize(text: str, cfg: dict, out_path: Path) -> Path:
    provider = cfg.get("tts_provider", "edge").lower()
    if provider == "elevenlabs":
        voice_id = cfg.get("elevenlabs_voice_id", "")
        model = cfg.get("elevenlabs_model", "eleven_flash_v2_5")
        ext = ".mp3"
    elif provider == "fish_audio":
        voice_id = cfg.get("fish_audio_model_id", "")
        model = cfg.get("fish_audio_model", "s1")
        ext = ".mp3"
    elif provider == "chatterbox":
        voice_id = cfg.get("chatterbox_reference_audio", "")
        model = cfg.get("chatterbox_language", "es")
        ext = ".wav"
    elif provider == "xtts":
        voice_id = cfg.get("xtts_reference_audio", "")
        model = cfg.get("xtts_language", "es")
        ext = ".wav"
    else:
        voice_id = cfg.get("voice", "")
        model = ""
        ext = ".mp3"

    actual_out = out_path.with_suffix(ext)
    key = _cache_key(text, provider, voice_id, model)
    cache_file = CACHE_DIR / f"{key}{ext}"

    if cache_file.exists() and cache_file.stat().st_size > 0:
        log(f"[CACHE HIT] Reutilizando {cache_file.name}")
        if actual_out.exists():
            try:
                actual_out.unlink()
            except Exception:
                pass
        shutil.copy(cache_file, actual_out)
        return actual_out

    log(f"[CACHE MISS] Generando con provider={provider}")
    if actual_out.exists():
        try:
            actual_out.unlink()
        except Exception:
            pass

    if provider == "elevenlabs":
        try:
            synthesize_elevenlabs(text, cfg, actual_out)
            log(f"[ELEVENLABS] Generado: {len(text)} chars")
        except Exception as e:
            log(f"[ELEVENLABS ERROR] {e}. Fallback a Edge TTS.")
            actual_out = out_path.with_suffix(".mp3")
            await synthesize_edge(text, cfg, actual_out)
    elif provider == "fish_audio":
        try:
            synthesize_fish_audio(text, cfg, actual_out)
            log(f"[FISH AUDIO] Generado: {len(text)} chars")
        except Exception as e:
            log(f"[FISH AUDIO ERROR] {e}. Fallback a Edge TTS.")
            actual_out = out_path.with_suffix(".mp3")
            await synthesize_edge(text, cfg, actual_out)
    elif provider == "chatterbox":
        try:
            actual_out = synthesize_chatterbox(text, cfg, out_path)
        except Exception as e:
            log(f"[CHATTERBOX ERROR] {e}. Fallback a Edge TTS.")
            actual_out = out_path.with_suffix(".mp3")
            await synthesize_edge(text, cfg, actual_out)
    elif provider == "xtts":
        try:
            actual_out = synthesize_xtts(text, cfg, out_path)
        except Exception as e:
            log(f"[XTTS ERROR] {e}. Fallback a Edge TTS.")
            actual_out = out_path.with_suffix(".mp3")
            await synthesize_edge(text, cfg, actual_out)
    else:
        await synthesize_edge(text, cfg, actual_out)

    if actual_out.exists() and actual_out.stat().st_size > 0:
        cache_real = CACHE_DIR / f"{key}{actual_out.suffix}"
        shutil.copy(actual_out, cache_real)
        log(f"[CACHE] Guardado: {cache_real.name}")
    return actual_out


def play_audio(path: Path) -> None:
    pygame.mixer.init()
    pygame.mixer.music.set_volume(1.0)
    pygame.mixer.music.load(str(path))
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.2)
    pygame.mixer.music.unload()
    pygame.mixer.quit()


def launch_video(cfg: dict) -> None:
    url = cfg["youtube_url"]
    brave = cfg["brave_path"]
    if not os.path.exists(brave):
        brave = cfg.get("brave_path_fallback", "")
    if not brave or not os.path.exists(brave):
        log("Brave not found, opening default browser")
        os.startfile(url)
        return

    subprocess.Popen(
        [brave, "--kiosk", "--autoplay-policy=no-user-gesture-required", url],
        close_fds=True,
    )
    log("Launched Brave in kiosk mode")


def main() -> int:
    log("=== Jarvis Alarm starting ===")
    try:
        cfg = load_config()
    except Exception as e:
        log(f"Failed to load config: {e}")
        return 1

    time.sleep(5)

    log("Fetching weather...")
    weather = get_weather(cfg)

    speech = build_speech(cfg, weather)
    log(f"Speech: {speech}")

    log("Synthesizing voice...")
    try:
        audio_path = asyncio.run(synthesize(speech, cfg, AUDIO_PATH))
    except Exception as e:
        log(f"TTS failed: {e}")
        return 2

    # Detectar si el speech termina con countdown (3,2,1 o 5,4,3,2,1)
    is_countdown = bool(re.search(r'\b(?:5[\s,]*4[\s,]*)?3[\s,]*2[\s,]*1\b|\b(?:cinco[\s.,]*cuatro[\s.,]*)?tres[\s.,]*dos[\s.,]*uno\b', speech, re.IGNORECASE))
    if is_countdown:
        log("[FX] Countdown detectado en outro -> se omite chime, YouTube inmediato")

    # Efectos de sonido + voz
    log(f"Playing audio: {audio_path.name}")
    try:
        # Pre-intro: sonido extra que suena ANTES del intro normal (ej. alarma iPhone)
        pre_intro = cfg.get("sound_pre_intro", "")
        if pre_intro:
            pre_intro_path = BASE_DIR / pre_intro
            if pre_intro_path.exists():
                log(f"[FX] Reproduciendo pre-intro: {pre_intro_path.name}")
                play_audio(pre_intro_path)

        # Intro: boot-up de Jarvis (si existe)
        intro = cfg.get("sound_intro", "")
        if intro:
            intro_path = BASE_DIR / intro
            if intro_path.exists():
                log(f"[FX] Reproduciendo intro: {intro_path.name}")
                play_audio(intro_path)

        # Voz principal
        play_audio(audio_path)

        # Outro: SOLO si NO hay countdown
        if not is_countdown:
            outro = cfg.get("sound_outro", "")
            if outro:
                outro_path = BASE_DIR / outro
                if outro_path.exists():
                    log(f"[FX] Reproduciendo outro: {outro_path.name}")
                    play_audio(outro_path)
    except Exception as e:
        log(f"Playback failed: {e}")

    log("Launching YouTube video...")
    try:
        launch_video(cfg)
    except Exception as e:
        log(f"Video launch failed: {e}")

    log("=== Jarvis Alarm finished ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
