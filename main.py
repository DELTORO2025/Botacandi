import os
import json
import re
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
# Variables de entorno
# =====================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

if not BOT_TOKEN:
    raise RuntimeError("❌ Falta BOT_TOKEN")
if not SHEET_ID:
    raise RuntimeError("❌ Falta SHEET_ID")
if not GOOGLE_CREDENTIALS:
    raise RuntimeError("❌ Falta GOOGLE_CREDENTIALS")

# =====================================================
# Google Sheets
# =====================================================
creds = json.loads(GOOGLE_CREDENTIALS)
gc = gspread.service_account_from_dict(creds)
sh = gc.open_by_key(SHEET_ID)
worksheet = sh.sheet1

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
def escape_html(texto):
    """Evita que caracteres especiales dañen el formato HTML"""
    return (
        str(texto or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

def norm_key(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())

def get_any(fila: dict, *candidatos: str, default=""):
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
    t = str(txt or "").strip().upper()
    return t.replace(" ", "").replace("-", "")

def es_placa(texto: str) -> bool:
    t = normalizar_placa(texto)
    if len(t) < 4 or len(t) > 10:
        return False
    return any(c.isalpha() for c in t) and any(c.isdigit() for c in t)

def extraer_numeros(texto: str) -> str:
    return "".join(c for c in (texto or "") if c.isdigit())

def interpretar_apto_candidatos(texto: str):
    dig = extraer_numeros(texto)
    if len(dig) < 3:
        return []
    torre = int(dig[:3])  # Permitimos hasta tres dígitos en la torre
    apto = int(dig[3:])
    if 1 <= torre <= 12:  # Verifica si la torre está en el rango esperado
        return [(torre, apto)]
    return []

# =====================================================
# /start
# =====================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Envíame un número de apartamento o una placa."
    )

# =====================================================
# BÚSQUEDA
# =====================================================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (update.message.text or "").strip()
    if not texto:
        return

    datos = worksheet.get_all_records()

    # ===============================
    # BUSCAR POR APARTAMENTO
    # ===============================
    candidatos = interpretar_apto_candidatos(texto)

    for fila in datos:
        try:
            torre_i = int(str(get_any(fila, "Torre", default="")).strip())
            apto_i = int(str(get_any(fila, "Apartamento", "Apto", default="")).strip())
        except:
            continue

        if any(torre_i == tb and apto_i == ab for (tb, ab) in candidatos):
            piso = escape_html(get_any(fila, "Piso", default=""))
            propietario = escape_html(get_any(fila, "Propietario", default="N/A"))
            saldo = escape_html(get_any(fila, "Saldo", default="N/A"))
            placa_carro = escape_html(get_any(fila, "Placa Carro", default="No registrado"))
            placa_moto = escape_html(get_any(fila, "Placa Moto", default="No registrada"))
            stikers = escape_html(get_any(fila, "Stikers", "Stickers", default="N/A"))

            estado_raw = normalizar(get_any(fila, "Estado", default=""))
            emoji, estado_txt = ESTADOS.get(estado_raw, ("⚪", "No especificado"))

            respuesta = (
                f"🏢 <b>Torre:</b> {torre_i}\n"
                f"🏠 <b>Apartamento:</b> {apto_i}\n"
                + (f"🛗 <b>Piso:</b> {piso}\n" if piso else "")
                + f"👤 <b>Propietario:</b> {propietario}\n"
                f"💰 <b>Saldo:</b> {saldo}\n"
                f"{emoji} <b>Estado:</b> {estado_txt}\n"
                f"🚗 <b>Placa carro:</b> {placa_carro}\n"
                f"🏍️ <b>Placa moto:</b> {placa_moto}\n"
                f"🏷️ <b>Stikers:</b> {stikers}"
            )

            await update.message.reply_text(respuesta, parse_mode="HTML")
            return

    await update.message.reply_text("❌ No encontrado.")

# =====================================================
# MAIN
# =====================================================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar))

    print("🤖 BOT ACTIVO")
    app.run_polling()

if __name__ == "__main__":
    main()
