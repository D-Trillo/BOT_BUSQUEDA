import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from search_module import search_all_databases
from drive_module import upload_to_drive

load_dotenv()

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Almacena resultados temporalmente por usuario
user_sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hola! Soy tu asistente de investigación.\n\n"
        "📝 Escríbeme así:\n"
        "`palabras clave | año inicio | año fin`\n\n"
        "Ejemplo:\n"
        "`machine learning, cancer | 2021 | 2024`",
        parse_mode="Markdown"
    )

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    try:
        parts = text.split("|")
        keywords = parts[0].strip()
        year_start = parts[1].strip() if len(parts) > 1 else "2020"
        year_end = parts[2].strip() if len(parts) > 2 else "2024"
    except:
        await update.message.reply_text("⚠️ Formato incorrecto. Usa: `palabras clave | año inicio | año fin`", parse_mode="Markdown")
        return

    await update.message.reply_text(f"🔍 Buscando *{keywords}* ({year_start}-{year_end})...\nEspera un momento ⏳", parse_mode="Markdown")

    results = search_all_databases(keywords, year_start, year_end)

    if not results:
        await update.message.reply_text("😔 No se encontraron resultados.")
        return

    user_sessions[user_id] = {"results": results, "index": 0, "saved": []}
    await send_next_result(update, context, user_id)

async def send_next_result(update_or_query, context, user_id):
    session = user_sessions.get(user_id)
    if not session:
        return

    index = session["index"]
    results = session["results"]

    if index >= len(results):
        saved = session["saved"]
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Has revisado todos los artículos.\n📥 Guardados: {len(saved)} artículos en Google Drive."
        )
        return

    article = results[index]
    title = article.get("title", "Sin título")
    authors = article.get("authors", "Desconocido")
    year = article.get("year", "?")
    abstract = article.get("abstract", "No disponible")[:300] + "..."
    source = article.get("source", "?")

    msg = (
        f"📄 *{title}*\n"
        f"👥 {authors}\n"
        f"📅 Año: {year} | 🗄️ Fuente: {source}\n\n"
        f"📝 _{abstract}_\n\n"
        f"📌 Artículo {index + 1} de {len(results)}"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Me interesa", callback_data=f"yes_{user_id}_{index}"),
            InlineKeyboardButton("❌ Descartar", callback_data=f"no_{user_id}_{index}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(chat_id=user_id, text=msg, parse_mode="Markdown", reply_markup=reply_markup)

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    parts = data.split("_")
    action = parts[0]
    user_id = int(parts[1])

    session = user_sessions.get(user_id)
    if not session:
        return

    index = session["index"]
    article = session["results"][index]

    if action == "yes":
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=user_id, text=f"⬇️ Descargando y subiendo a Drive: _{article['title']}_", parse_mode="Markdown")
        result = upload_to_drive(article)
        if result:
            session["saved"].append(article)
            await context.bot.send_message(chat_id=user_id, text="✅ Guardado en Drive correctamente.")
        else:
            await context.bot.send_message(chat_id=user_id, text="⚠️ No se pudo descargar el PDF, pero el artículo fue registrado.")
    else:
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=user_id, text="🗑️ Artículo descartado.")

    session["index"] += 1
    await send_next_result(update, context, user_id)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    app.add_handler(CallbackQueryHandler(handle_button))
    print("🤖 Bot iniciado. Esperando mensajes...")
    app.run_polling()

if __name__ == "__main__":
    main()