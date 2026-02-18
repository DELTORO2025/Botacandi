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
# Variables de entorno (Railway)
# =====================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

if not BOT_TOKEN:
    raise RuntimeError("❌ Falta BOT_TOKEN en Railway")
if not SHEET_ID:
    raise RuntimeError("❌ Falta SHEET_ID en Railway")
if not GOOGLE_CREDENTIALS:
    raise RuntimeError("❌ Falta GOOGLE_CREDENTIALS en Railway")

# =====================================================
# Conexión Google Sheets
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
    t = str(texto or "").strip().lower()

    # formato "torre X apto Y"
    m = re.search(r"\b(torre|tor|t)\s*[:\-]?\s*(\d{1,2})\b", t)
    n = re.search(r"\b(apto|apartamento|apt|a)\s*[:\-]?\s*(\d{1,5})\b", t)
    if m and n:
        return [(int(m.group(2)), int(n.group(2)))]

    dig = extraer_numeros(texto)
    if len(dig) < 3:
        return []

    candidatos = []
    torre = int(dig[:2])
    apto = int(dig[2:])
    if 1 <= torre <= 12:
        candidatos.append((torre, apto))

    return candidatos

def parsear_lista_placas(celda: str):
    raw = str(celda or "")
    partes = re.split(r"[,\n;/]+", raw)
    return [normalizar_placa(p) for p in partes if p.strip()]

# =====================================================
# /start
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Envíame un apartamento o una placa.\n\n"
        "Ejemplos apartamento:\n"
        "101270\n"
        "12-1270\n"
        "2202\n"
        "1101\n"
        "Torre 10 Apto 1270\n\n"
        "Ejemplos placa:\n"
        "RPH360\n"
        "XTH15Y\n"
        "HTX-213"
    )

# =====================================================
# Búsqueda
# =====================================================

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (update.message.text or "").strip()
    if not texto:
        return

    datos = worksheet.get_all_records()

    # -------------------------
    # BUSCAR POR PLACA
    # -------------------------
    if es_placa(texto):
        placa_b = normalizar_placa(texto)

        for fila in datos:
            placas = set(
                parsear_lista_placas(get_any(fila, "Placa Carro", default="")) +
                parsear_lista_placas(get_any(fila, "Placa Moto", default=""))
            )

            if placa_b in placas:

                torre = get_any(fila, "Torre", default="")
                apto = get_any(fila, "Apartamento", "Apto", default="")
                piso = get_any(fila, "Piso", default="")
                propietario = get_any(fila, "Propietario", default="N/A")
                saldo = get_any(fila, "Saldo", default="N/A")
                placa_carro = get_any(fila, "Placa Carro", default="No registrado")
                placa_moto = get_any(fila, "Placa Moto", default="No registrada")
                stikers = get_any(fila, "Stikers", "Stickers", default="N/A")

                estado_raw = normalizar(get_any(fila, "Estado", default=""))
                emoji, estado_txt = ESTADOS.get(estado_raw, ("⚪", "No especificado"))

                respuesta = (
                    f"🔎 Placa buscada: {placa_b}\n\n"
                    f"🏢 Torre: {torre}\n"
                    + (f"🛗 Piso: {piso}\n" if str(piso).strip() else "")
                    + f"🏠 Apartamento: {apto}\n"
                    f"🧍 Propietario: {propietario}\n"
                    f"💰 Saldo: {saldo}\n"
                    f"{emoji} Estado: {estado_txt}\n"
                    f"🚗 Placa carro: {placa_carro}\n"
                    f"🏍️ Placa moto: {placa_moto}\n"
                    f"🏷 Stikers: {stikers}"
                )

                await update.message.reply_text(respuesta)
                return

        await update.message.reply_text(f"❌ No encontré la placa {placa_b}")
        return

    # -------------------------
    # BUSCAR POR APARTAMENTO
    # -------------------------
    candidatos = interpretar_apto_candidatos(texto)

    if not candidatos:
        await update.message.reply_text(
            "❌ No pude leer lo que enviaste.\n\n"
            "Ejemplos apartamento:\n"
            "101270\n"
            "12-1270\n"
            "2202\n"
            "1101\n"
            "Torre 10 Apto 1270\n\n"
            "Ejemplos placa:\n"
            "RPH360\n"
            "XTH15Y\n"
            "HTX-213"
        )
        return

    for fila in datos:
        try:
            torre_i = int(str(get_any(fila, "Torre", default="")).strip())
            apto_i = int(str(get_any(fila, "Apartamento", "Apto", default="")).strip())
        except:
            continue

        if any(torre_i == tb and apto_i == ab for (tb, ab) in candidatos):

            piso = get_any(fila, "Piso", default="")
            propietario = get_any(fila, "Propietario", default="N/A")
            saldo = get_any(fila, "Saldo", default="N/A")
            placa_carro = get_any(fila, "Placa Carro", default="No registrado")
            placa_moto = get_any(fila, "Placa Moto", default="No registrada")
            stikers = get_any(fila, "Stikers", "Stickers", default="N/A")

            estado_raw = normalizar(get_any(fila, "Estado", default=""))
            emoji, estado_txt = ESTADOS.get(estado_raw, ("⚪", "No especificado"))

            respuesta = (
                f"🏢 Torre: {torre_i}\n"
                + (f"🛗 Piso: {piso}\n" if str(piso).strip() else "")
                + f"🏠 Apartamento: {apto_i}\n"
                f"🧍 Propietario: {propietario}\n"
                f"💰 Saldo: {saldo}\n"
                f"{emoji} Estado: {estado_txt}\n"
                f"🚗 Placa carro: {placa_carro}\n"
                f"🏍️ Placa moto: {placa_moto}\n"
                f"🏷 Stikers: {stikers}"
            )

            await update.message.reply_text(respuesta)
            return

    await update.message.reply_text("❌ Apartamento no encontrado")

# =====================================================
# MAIN
# =====================================================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buscar))

    print("🤖 BOT ACTIVO EN RAILWAY")
    app.run_polling()

if __name__ == "__main__":
    main()
