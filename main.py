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
    "RESTRICCIÓN": ("🔴", "Restricción"),
}

# =====================================================
# Utilidades
# =====================================================
def escape_html(texto):
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

def extraer_numeros(texto: str):
    return re.findall(r'\d+', texto)

# =====================================================
# NUEVA INTERPRETACIÓN CORRECTA
# =====================================================
def interpretar_apto(texto: str):
    """
    Acepta formatos:
    11 1278
    11-1278
    11,1278
    11/1278
    """

    numeros = extraer_numeros(texto)

    if len(numeros) >= 2:
        try:
            torre = int(numeros[0])
            apto = int(numeros[1])
            return torre, apto
        except:
            return None

    return None

# =====================================================
# /start
# =====================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Envíame Torre y Apartamento.\nEjemplo:\n11 1278"
    )

# =====================================================
# BÚSQUEDA
# =====================================================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (update.message.text or "").strip()
    if not texto:
        return

    datos = worksheet.get_all_records()

    resultado = interpretar_apto(texto)

    if not resultado:
        await update.message.reply_text(
            "❌ Formato inválido.\nUsa: 11 1278"
        )
        return

    torre_buscar, apto_buscar = resultado

    for fila in datos:
        try:
            torre_i = int(str(get_any(fila, "Torre", default="")).strip())
            apto_i = int(str(get_any(fila, "Apartamento", "Apto", default="")).strip())
        except:
            continue

        if torre_i == torre_buscar and apto_i == apto_buscar:
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
