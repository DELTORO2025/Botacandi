import re
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
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
# 🔐 CONFIGURACIÓN
# =====================================================

TOKEN = "PON_AQUI_TU_TOKEN"
SHEET_NAME = "PON_AQUI_EL_NOMBRE_DE_TU_HOJA"
CREDENTIALS_FILE = "credenciales.json"

# =====================================================
# LOGGING
# =====================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# =====================================================
# GOOGLE SHEETS
# =====================================================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

creds = ServiceAccountCredentials.from_json_keyfile_name(
    CREDENTIALS_FILE, scope
)

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

    if not limpio:
        return None

    for fila in datos:
        try:
            torre = int(str(get_any(fila, "Torre")).strip())
            apto = int(str(get_any(fila, "Apartamento", "Apto")).strip())
        except:
            continue

        combinado = f"{torre}{apto}"

        if limpio == str(apto):
            return torre, apto

        if limpio == combinado:
            return torre, apto

    return None

# =====================================================
# COMANDO START
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "👋 Bienvenido.\n\n"
        "Puedes buscar por:\n"
        "• Número de apartamento (1104, 11006, 11 1006)\n"
        "• Placa (RPH360, HTX-213)\n"
    )
    await update.message.reply_text(mensaje)

# =====================================================
# FUNCIÓN PRINCIPAL
# =====================================================

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):

    texto = (update.message.text or "").strip()

    if not texto:
        return

    try:
        datos = worksheet.get_all_records()
    except Exception as e:
        await update.message.reply_text("❌ Error leyendo la base de datos.")
        return

    # =====================================================
    # 1️⃣ BUSCAR POR PLACA
    # =====================================================

    placa_input = re.sub(r"[^A-Za-z0-9]", "", texto).upper()

    if any(c.isalpha() for c in placa_input) and any(c.isdigit() for c in placa_input):

        for fila in datos:

            placa_carro = re.sub(
                r"[^A-Za-z0-9]", "",
                str(get_any(fila, "Placa Carro", default="")).upper()
            )

            placa_moto = re.sub(
                r"[^A-Za-z0-9]", "",
                str(get_any(fila, "Placa Moto", default="")).upper()
            )

            if placa_input == placa_carro or placa_input == placa_moto:

                return await enviar_respuesta(update, fila)

        return await update.message.reply_text("❌ Placa no encontrada.")

    # =====================================================
    # 2️⃣ BUSCAR POR APARTAMENTO
    # =====================================================

    resultado = interpretar_apto(texto, datos)

    if not resultado:
        return await update.message.reply_text("❌ No encontrado.")

    torre_buscar, apto_buscar = resultado

    for fila in datos:
        try:
            torre = int(str(get_any(fila, "Torre")).strip())
            apto = int(str(get_any(fila, "Apartamento", "Apto")).strip())
        except:
            continue

        if torre == torre_buscar and apto == apto_buscar:
            return await enviar_respuesta(update, fila)

    await update.message.reply_text("❌ No encontrado.")

# =====================================================
# FORMATEAR RESPUESTA
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
# INICIAR BOT
# =====================================================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar))

    print("✅ Bot iniciado correctamente...")
    app.run_polling()

if __name__ == "__main__":
    main()
