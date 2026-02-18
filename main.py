import os
import json
import re
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import gspread

# =====================================================
# Cargar variables de entorno
# =====================================================
# Solo es necesario cargar dotenv si usas un archivo .env, en este caso no lo usamos.
# load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Obtiene el token de Telegram desde las variables de entorno de Railway
SHEET_ID = os.getenv("SHEET_ID")  # Obtiene el ID de la hoja de Google Sheets
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")  # Obtiene las credenciales de Google (JSON)

# Verificación de que las variables están presentes
print("[ENV] BOT_TOKEN:", bool(BOT_TOKEN))
print("[ENV] SHEET_ID:", SHEET_ID)
print("[ENV] GOOGLE_CREDENTIALS:", bool(GOOGLE_CREDENTIALS))

# Si falta alguna variable, lanza un error
if not BOT_TOKEN:
    raise RuntimeError("❌ Falta BOT_TOKEN en Railway")
if not SHEET_ID:
    raise RuntimeError("❌ Falta SHEET_ID en Railway")
if not GOOGLE_CREDENTIALS:
    raise RuntimeError("❌ Falta GOOGLE_CREDENTIALS en Railway")

# =====================================================
# Conexión Google Sheets
# =====================================================
creds = json.loads(GOOGLE_CREDENTIALS)  # Convierte el string de GOOGLE_CREDENTIALS en un objeto JSON
gc = gspread.service_account_from_dict(creds)  # Autenticación con las credenciales de Google
sh = gc.open_by_key(SHEET_ID)  # Abre la hoja de cálculo utilizando el SHEET_ID
worksheet = sh.sheet1  # Accede a la primera hoja

# =====================================================
# Estados
# =====================================================
ESTADOS = {
    "N": ("🟢", "Normal"),
    "A": ("🟡", "Acuerdo"),
    "R": ("🔴", "Restricción"),
    "RESTRICCION": ("🔴", "Restricción"),
    "RESTRICIÓN": ("🔴", "Restricción"),
}

# =====================================================
# Utilidades
# =====================================================
def norm_key(s: str) -> str:
    """Normaliza nombres de columnas para tolerar espacios/mayúsculas."""
    return re.sub(r"\s+", " ", str(s or "").strip().lower())

def get_any(fila: dict, *candidatos: str, default=""):
    """
    Obtiene un campo de una fila aunque el encabezado tenga espacios o mayúsculas distintas.
    candidatos: lista de nombres posibles ("Placa Carro", "Placa carro ", etc)
    """
    if not isinstance(fila, dict):
        return default
    mapa = {norm_key(k): k for k in fila.keys()}
    for c in candidatos:
        ck = norm_key(c)
        if ck in mapa:
            return fila.get(mapa[ck], default)
    return default

def normalizar(txt):
    return str(txt or "").strip().upper()

def normalizar_placa(txt):
    # Quita espacios, guiones y pone MAYÚSCULAS
    t = str(txt or "").strip().upper()
    t = t.replace(" ", "").replace("-", "")
    return t

def es_placa(texto: str) -> bool:
    """
    Placa: mezcla letras y números, tamaño razonable.
    Acepta: RPH360, XTH15Y, HTX-213, etc.
    """
    t = normalizar_placa(texto)
    if len(t) < 4:
        return False
    if len(t) > 10:
        return False
    tiene_letra = any(c.isalpha() for c in t)
    tiene_numero = any(c.isdigit() for c in t)
    return tiene_letra and tiene_numero

def extraer_numeros(texto: str) -> str:
    return "".join(c for c in (texto or "") if c.isdigit())

def interpretar_apto_candidatos(texto: str):
    """
    Devuelve una lista de posibles (torre, apto) a probar en Sheets.
    Acepta formatos tipo:
      - 101270 -> (10,1270)
      - 11006  -> (11,006)
      - 11202  -> (11,202)
      - 110-06 -> (11,006)
      - torre 10 apto 1270
      - 10-1270
      - 1101, 2202, etc.
    """
    t = str(texto or "").strip().lower()

    # 1) Explicit format "torre X apto Y"
    m = re.search(r"\b(torre|tor|t)\s*[:\-]?\s*(\d{1,2})\b", t)
    n = re.search(r"\b(apto|apartamento|apt|a)\s*[:\-]?\s*(\d{1,5})\b", t)
    if m and n:
        torre = int(m.group(2))
        apto = int(n.group(2))
        if 1 <= torre <= 12 and apto >= 0:
            return [(torre, apto)]

    # 2) Numerals only: consider pure digits
    dig = extraer_numeros(texto)
    if len(dig) < 3:
        return []

    candidatos = []

    # 2A) Ambiguous 5 digits case (11006 should match torre 11 apto 6)
    if len(dig) == 5:
        torre_a = int(dig[:2])  # First two digits as the tower
        apto_a = int(dig[2:])   # Remaining as apartment
        if 1 <= torre_a <= 12:
            candidatos.append((torre_a, apto_a))

    # 2B) Handle more than 5 digits or any other cases
    elif len(dig) > 5:
        torre = int(dig[:2])  # First two digits as the tower
        apto = int(dig[2:])   # Remaining as apartment
        if 1 <= torre <= 12:
            candidatos.append((torre, apto))

    # Returning possible interpretations without duplicates
    out = []
    seen = set()
    for c in candidatos:
        if c not in seen:
            out.append(c)
            seen.add(c)
    return out

def parsear_lista_placas(celda: str):
    """
    Si en la celda guardan varias placas separadas por coma, slash o salto,
    las detectamos todas.
    """
    raw = str(celda or "")
    partes = re.split(r"[,\n;/]+", raw)
    out = []
    for p in partes:
        p = normalizar_placa(p)
        if p:
            out.append(p)
    return out

# =====================================================
# /start
# =====================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Envíame un apartamento o una placa.\n\n"
        "📌 Apartamentos (cualquier forma):\n"
        "• 101270  (Torre 10 Apto 1270)\n"
        "• 111260  (Torre 11 Apto 1260)\n"
        "• 12-1270\n"
        "• 2202    (Torre 2 Apto 202)\n"
        "• 1101    (Torre 1 Apto 101)\n"
        "• Torre 10 Apto 1270\n\n"
        "🚗 Placas:\n"
        "• RPH360\n"
        "• xth15y\n"
        "• HTX-213"
    )

# =====================================================
# Búsqueda principal
# =====================================================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (update.message.text or "").strip()
    if not texto:
        return

    datos = worksheet.get_all_records()

    # Detectar si existe columna Piso en la hoja
    tiene_piso = False
    if datos:
        for k in datos[0].keys():
            if norm_key(k) == "piso":
                tiene_piso = True
                break

    # Búsqueda por PLACA
    if es_placa(texto):
        placa_b = normalizar_placa(texto)
        encontrados = []

        for fila in datos:
            placa_carro_raw = get_any(
                fila,
                "Placa Carro", "Placa carro", "Placa carro ", "PlacaCarro",
                default=""
            )
            placa_moto_raw = get_any(
                fila,
                "Placa Moto", "Placa moto", "Placa moto ", "PlacaMoto",
                default=""
            )

            placas_fila = set(parsear_lista_placas(placa_carro_raw) + parsear_lista_placas(placa_moto_raw))

            if placa_b in placas_fila:
                torre_f = get_any(fila, "Torre", default="")
                apto_f  = get_any(fila, "Apartamento", "Apto", default="")
                piso_f  = get_any(fila, "Piso", default="")

                try:
                    torre_i = int(str(torre_f).strip())
                except:
                    torre_i = None
                try:
                    apto_i = int(str(apto_f).strip())
                except:
                    apto_i = None

                estado_raw = normalizar(get_any(fila, "Estado", default=""))
                emoji, estado_txt = ESTADOS.get(estado_raw, ("⚪", "No especificado"))

                propietario = get_any(fila, "Propietario", default="N/A")
                saldo = get_any(fila, "Saldo", default="N/A")
                stikers = get_any(fila, "Stikers", "Stickers", default="N/A")

                encontrados.append({
                    "torre": torre_i if torre_i is not None else torre_f,
                    "piso": piso_f,
                    "apto": apto_i if apto_i is not None else apto_f,
                    "propietario": propietario,
                    "saldo": saldo,
                    "emoji": emoji,
                    "estado_txt": estado_txt,
                    "placa_carro": placa_carro_raw or "No registrado",
                    "placa_moto": placa_moto_raw or "No registrada",
                    "stikers": stikers,
                })

        if not encontrados:
            await update.message.reply_text(
                f"❌ No encontré la placa *{placa_b}* en la base.",
                parse_mode="Markdown"
            )
            return

        if len(encontrados) == 1:
            e = encontrados[0]
            respuesta = (
                f"🔎 *Placa buscada:* {placa_b}\n\n"
                f"🏢 *Torre:* {e['torre']}\n"
                + (f"🛗 *Piso:* {e['piso']}\n" if str(e['piso']).strip() else "")
                + f"🏠 *Apartamento:* {e['apto']}\n"
                f"🧍 *Propietario:* {e['propietario']}\n"
                f"💰 *Saldo:* {e['saldo']}\n"
                f"{e['emoji']} *Estado:* {e['estado_txt']}\n"
                f"🚗 *Placa carro:* {e['placa_carro']}\n"
                f"🏍️ *Placa moto:* {e['placa_moto']}\n"
                f"🏷 *Stikers:* {e['stikers']}"
            )
            await update.message.reply_text(respuesta, parse_mode="Markdown")
            return

        msg = [f"🔎 *Placa buscada:* {placa_b}\n\nEncontré *{len(encontrados)}* registros:"]
        for e in encontrados:
            linea = f"\n— 🏢T{e['torre']} 🏠A{e['apto']} | 🧍{e['propietario']} | {e['emoji']}{e['estado_txt']}"
            if str(e["piso"]).strip():
                linea = f"\n— 🏢T{e['torre']} 🛗P{e['piso']} 🏠A{e['apto']} | 🧍{e['propietario']} | {e['emoji']}{e['estado_txt']}"
            msg.append(linea)
        await update.message.reply_text("".join(msg), parse_mode="Markdown")
        return

    # Búsqueda por APARTAMENTO
    candidatos = interpretar_apto_candidatos(texto)

    if not candidatos:
        await update.message.reply_text(
            "❌ No pude leer lo que enviaste.\n\n"
            "✅ Ejemplos de apartamento:\n"
            "• 101270 (Torre 10 Apto 1270)\n"
            "• 12-1270\n"
            "• 2202 (Torre 2 Apto 202)\n"
            "• 1101 (Torre 1 Apto 101)\n"
            "• Torre 10 Apto 1270\n\n"
            "✅ Ejemplos de placa:\n"
            "• RPH360\n"
            "• XTH15Y\n"
            "• HTX-213"
        )
        return

    for fila in datos:
        torre_f = get_any(fila, "Torre", default="")
        apto_f = get_any(fila, "Apartamento", "Apto", default="")
        piso_f = get_any(fila, "Piso", default="")

        try:
            torre_i = int(str(torre_f).strip())
            apto_i = int(str(apto_f).strip())
        except:
            continue

        # Probamos todos los candidatos posibles
        if any(torre_i == tb and apto_i == ab for (tb, ab) in candidatos):
            estado_raw = normalizar(get_any(fila, "Estado", default=""))
            emoji, estado_txt = ESTADOS.get(estado_raw, ("⚪", "No especificado"))

            propietario = get_any(fila, "Propietario", default="N/A")
            saldo = get_any(fila, "Saldo", default="N/A")
            placa_carro = get_any(
                fila,
                "Placa Carro", "Placa carro", "Placa carro ", "PlacaCarro",
                default="No registrado"
            )
            placa_moto = get_any(
                fila,
                "Placa Moto", "Placa moto", "Placa moto ", "PlacaMoto",
                default="No registrada"
            )
            stikers = get_any(fila, "Stikers", "Stickers", default="N/A")

            respuesta = (
                f"🏢 *Torre:* {torre_i}\n"
                + (f"🛗 *Piso:* {piso_f}\n" if str(piso_f).strip() else "")
                + f"🏠 *Apartamento:* {apto_i}\n"
                f"🧍 *Propietario:* {propietario}\n"
                f"💰 *Saldo:* {saldo}\n"
                f"{emoji} *Estado:* {estado_txt}\n"
                f"🚗 *Placa carro:* {placa_carro}\n"
                f"🏍️ *Placa moto:* {placa_moto}\n"
                f"🏷 *Stikers:* {stikers}"
            )

            await update.message.reply_text(respuesta, parse_mode="Markdown")
            return

    await update.message.reply_text("❌ Apartamento no encontrado")

# =====================================================
# Main
# =====================================================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar))

    print("🤖 BOT ACTIVO 24/7 EN RAILWAY")
    app.run_polling()

if __name__ == "__main__":
    main()
