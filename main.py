async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (update.message.text or "").strip()
    if not texto:
        return

    datos = worksheet.get_all_records()

    # =====================================================
    # 1️⃣ BUSCAR POR PLACA
    # =====================================================
    placa_input = re.sub(r'[^A-Za-z0-9]', '', texto).upper()

    if any(c.isalpha() for c in placa_input) and any(c.isdigit() for c in placa_input):
        for fila in datos:
            placa_carro = re.sub(r'[^A-Za-z0-9]', '', 
                str(get_any(fila, "Placa Carro", default=""))
            ).upper()

            placa_moto = re.sub(r'[^A-Za-z0-9]', '', 
                str(get_any(fila, "Placa Moto", default=""))
            ).upper()

            if placa_input == placa_carro or placa_input == placa_moto:
                try:
                    torre_i = int(str(get_any(fila, "Torre", default="")).strip())
                    apto_i = int(str(get_any(fila, "Apartamento", "Apto", default="")).strip())
                except:
                    continue

                piso = escape_html(get_any(fila, "Piso", default=""))
                propietario = escape_html(get_any(fila, "Propietario", default="N/A"))
                saldo = escape_html(get_any(fila, "Saldo", default="N/A"))
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
                    f"🚗 <b>Placa carro:</b> {escape_html(get_any(fila, 'Placa Carro', default='No registrado'))}\n"
                    f"🏍️ <b>Placa moto:</b> {escape_html(get_any(fila, 'Placa Moto', default='No registrada'))}\n"
                    f"🏷️ <b>Stikers:</b> {stikers}"
                )

                await update.message.reply_text(respuesta, parse_mode="HTML")
                return

        await update.message.reply_text("❌ Placa no encontrada.")
        return

    # =====================================================
    # 2️⃣ BUSCAR POR APARTAMENTO
    # =====================================================
    resultado = interpretar_apto(texto, datos)

    if not resultado:
        await update.message.reply_text("❌ No encontrado.")
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
