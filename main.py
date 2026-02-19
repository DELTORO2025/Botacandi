import os
import re
import json
import logging
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)
from html import escape as escape_html

# =====================================================
# CONFIGURACIÓN DESDE VARIABLES DE ENTORNO
# =====================================================

TOKEN = os.getenv("BOT_TOKEN")
SHEET_NAME = os.getenv("SHEET_NAME")
GOOGLE_CREDS = os.getenv("GOOGLE_CREDS")

if not TOKEN or not SHEET_NAME or not GOOGLE_CREDS:
    raise Exception("Faltan variables de entorno.")

# =====================================================
# LOGGING
# =====================================================

logging.basicConfig(level=logging.INFO)

# =====================================================
# GOOGLE SHEETS
# =====================================================

creds_dict = json.loads(GOOGLE_CREDS)

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)
worksheet = client.open(SHEET_NAME).sheet1

# =====================================================
# FUNCIONES AUXILIARES
# =====================================================

def get_any(row, *keys, default=""):
    for key in keys:
        if key in row and row[key]:
            return row[key]
    return default


def normalizar(texto):
    return str(texto).strip().lower()


ESTADOS = {
    "normal": ("🟢", "Normal"),
    "mora": ("🔴", "En mora"),
    "bloqueado": ("⛔", "Bloqueado"),
}

# =====================================================
# INTERPRETAR APARTAMENTO
# =====================================================

def interpretar_apto(texto, datos):
    limpio = re.sub(r"\D", "", texto)

    for fila in datos:
        try:
            torre = int(str(get_any(fila, "Torre")).strip())
            apto = int(str(get_any(fila, "Apartamento", "Apto")).strip())
        except:
            continue

        if limpio == str(apto):
            return torre, apto

        if limpio == f"{torre}{apto}":
            return torre, apto

    return None

# =====================================================
# RESPUESTA
# =====================================================

async def enviar_respuesta(update, fila):
    torre = get_any(fila, "Torre")
    apto = get_any(fila, "Apartamento", "Apto")
    propietario = escape_html(get_any(fila, "Propietario", default="N/A"))
    saldo = escape_html(get_any(fila, "Saldo", default="N/A"))
    placa_carro = escape_html(get_any(fila, "Placa Carro", default="No registrado"))
    placa_moto = escape_html(get_any(fila, "Placa Moto", default="No registrada"))
    stikers = escape_html(get_any(fila, "Stikers", "Stickers", default="N/A"))

    estado_raw = normalizar(get_any(fila, "Estado"))
    emoji, estado_txt = ESTADOS.get(estado_raw, ("⚪", "No especificado"))

    respuesta = (
        f"🏢 <b>Torre:</b> {torre}\n"
        f"🏠 <b>Apartamento:</b> {apto}\n"
        f"👤 <b>Propietario:</b> {propietario}\n"
        f"💰 <b>Saldo:</b> {saldo}\n"
        f"{emoji} <b>Estado:</b> {estado_txt}\n"
        f"🚗 <b>Placa carro:</b> {placa_carro}\n"
        f"🏍️ <b>Placa moto:</b> {placa_moto}\n"
        f"🏷️ <b>Stikers:</b> {stikers}"
    )

    await update.message.reply_text(respuesta, parse_mode="HTML")

# =====================================================
# BUSCADOR
# =====================================================

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (update.message.text or "").strip()

    datos = worksheet.get_all_records()

    placa_input = re.sub(r"[^A-Za-z0-9]", "", texto).upper()

    # Buscar placa
    if any(c.isalpha() for c in placa_input) and any(c.isdigit() for c in placa_input):
        for fila in datos:
            placa_carro = re.sub(r"[^A-Za-z0-9]", "", str(get_any(fila, "Placa Carro")).upper())
            placa_moto = re.sub(r"[^A-Za-z0-9]", "", str(get_any(fila, "Placa Moto")).upper())

            if placa_input == placa_carro or placa_input == placa_moto:
                return await enviar_respuesta(update, fila)

        return await update.message.reply_text("❌ Placa no encontrada.")

    # Buscar apartamento
    resultado = interpretar_apto(texto, datos)

    if not resultado:
        return await update.message.reply_text("❌ No encontrado.")

    torre_buscar, apto_buscar = resultado

    for fila in datos:
        if str(get_any(fila, "Torre")) == str(torre_buscar) and \
           str(get_any(fila, "Apartamento", "Apto")) == str(apto_buscar):
            return await enviar_respuesta(update, fila)

    await update.message.reply_text("❌ No encontrado.")

# =====================================================
# START
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot activo. Envía apartamento o placa.")

# =====================================================
# MAIN
# =====================================================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar))

    print("Bot corriendo...")
    app.run_polling()

if __name__ == "__main__":
    main()
