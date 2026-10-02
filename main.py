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

# =====================================================
# INTERPRETAR APARTAMENTO INTELIGENTE
# =====================================================
def interpretar_apto(texto: str, datos):
    numeros = re.findall(r'\d+', texto)

    if not numeros:
        return None

    # Si vienen dos números separados → directo
    if len(numeros) >= 2:
        return int(numeros[0]), int(numeros[1])

    # Si viene uno solo → probar combinaciones reales
    dig = numeros[0]
    posibles = []

    if len(dig) >= 4:
        posibles.append((int(dig[0]), int(dig[1:])))

    if len(dig) >= 5:
        posibles.append((int(dig[:2]), int(dig[2:])))

    # Verificar cuál existe realmente en el Sheet (Versión blindada)
    for torre_test, apto_test in posibles:
        for fila in datos:
            try:
                torre_val = str(get_any(fila, "Torre", default=""))
                apto_val = str(get_any(fila, "Apartamento", "Apto", default=""))
                
                torre_nums = re.findall(r'\d+', torre_val)
                apto_nums = re.findall(r'\d+', apto_val)
                
                if not torre_nums or not apto_nums:
                    continue
                    
                torre_i = int(torre_nums[0])
                apto_i = int(apto_nums[0])
            except:
                continue

            if torre_i == torre_test and apto_i == apto_test:
                return torre_test, apto_test

    return None

# =====================================================
# /start
# =====================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Envíame el número del apartamento o la placa.\n\n"
        "Ejemplos:\n"
        "1104\n"
        "11006\n"
        "Torre 1 Apto 1006\n"
        "ABC123\n"
        "XYZ 12D"
    )

# =====================================================
# BÚSQUEDA
# =====================================================
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # CORRECCIÓN 1: Convertimos todo a mayúsculas desde el principio
    texto = (update.message.text or "").strip().upper()
    if not texto:
        return

    datos = worksheet.get_all_records()

    # CORRECCIÓN 2: Expresión regular que detecta carros (XXX123) y motos (XXX12A)
    # y permite que pongan espacios o guiones en el medio.
    placa_regex = r'[A-Z]{3}[ -]*\d{2}[0-9A-Z]'
    placas_encontradas = re.findall(placa_regex, texto)

    if placas_encontradas:
        # Limpiamos la placa que escribió el usuario (le quitamos espacios/guiones)
        placa_buscar = re.sub(r'[^A-Z0-9]', '', placas_encontradas[0])
        
        for fila in datos:
            # Traemos ambas placas del excel
            placa_carro_raw = str(get_any(fila, "Placa Carro", default=""))
            placa_moto_raw = str(get_any(fila, "Placa Moto", default=""))
            
            # Limpiamos las placas del Excel por si tienen espacios accidentales
            placa_carro_limpia = re.sub(r'[^A-Z0-9]', '', placa_carro_raw.upper())
            placa_moto_limpia = re.sub(r'[^A-Z0-9]', '', placa_moto_raw.upper())

            # CORRECCIÓN 3: Comparamos contra la placa de carro O la placa de moto
            if placa_buscar == placa_carro_limpia or placa_buscar == placa_moto_limpia:
                
                # Rescatamos los valores reales para mostrarlos tal cual en el mensaje
                placa_carro_mostrar = escape_html(placa_carro_raw) or "No registrado"
                placa_moto_mostrar = escape_html(placa_moto_raw) or "No registrada"
                
                piso = escape_html(get_any(fila, "Piso", default=""))
                propietario = escape_html(get_any(fila, "Propietario", default="N/A"))
                saldo = escape_html(get_any(fila, "Saldo", default="N/A"))
                stikers = escape_html(get_any(fila, "Stikers", "Stickers", default="N/A"))

                estado_raw = normalizar(get_any(fila, "Estado", default=""))
                emoji, estado_txt = ESTADOS.get(estado_raw, ("⚪", "No especificado"))

                respuesta = (
                    f"🏢 <b>Torre:</b> {get_any(fila, 'Torre', default='No especificado')}\n"
                    f"🏠 <b>Apartamento:</b> {get_any(fila, 'Apartamento', default='No especificado')}\n"
                    + (f"🛗 <b>Piso:</b> {piso}\n" if piso else "")
                    + f"👤 <b>Propietario:</b> {propietario}\n"
                    f"💰 <b>Saldo:</b> {saldo}\n"
                    f"{emoji} <b>Estado:</b> {estado_txt}\n"
                    f"🚗 <b>Placa carro:</b> {placa_carro_mostrar}\n"
                    f"🏍️ <b>Placa moto:</b> {placa_moto_mostrar}\n"
                    f"🏷️️ <b>Stikers:</b> {stikers}"
                )

                await update.message.reply_text(respuesta, parse_mode="HTML")
                return

        # Si entra por placa pero no la encuentra en la base de datos
        await update.message.reply_text(f"❌ La placa {placa_buscar} no se encontró en la base de datos.")
        return

    # =====================================================
    # Si no se encuentra placa, buscar por apartamento
    # =====================================================
    resultado = interpretar_apto(texto, datos)

    if not resultado:
        await update.message.reply_text("❌ No encontrado o formato no reconocido.")
        return

    torre_buscar, apto_buscar = resultado

    for fila in datos:
        try:
            torre_val = str(get_any(fila, "Torre", default=""))
            apto_val = str(get_any(fila, "Apartamento", "Apto", default=""))
            
            torre_nums = re.findall(r'\d+', torre_val)
            apto_nums = re.findall(r'\d+', apto_val)
            
            if not torre_nums or not apto_nums:
                continue
                
            torre_i = int(torre_nums[0])
            apto_i = int(apto_nums[0])
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
