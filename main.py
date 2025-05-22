import logging
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
    ConversationHandler
)

# Включаем логирование (для отладки)
logging.basicConfig(level=logging.INFO)

# Ваши ключи
TELEGRAM_TOKEN = "7980244991:AAGrb7qMq9XIa3p0y6JnBo7i1tT2GFZgAm4"
TMDB_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIwNzU2Y2UzZmI5OGI4YWJjMWY3YWU5OGI4ZDA5YzkwOCIsIm5iZiI6MTc0NjAyMjU3NC44NTEsInN1YiI6IjY4MTIzMGFlZjlmZjM2MTlkOTAwMjRhZiIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.YPAf-IBNRPz-fN7mWDlOgiPDEcimYeYPZTXPU-HETII"

# Состояния вопросов
GENRE, MOOD, CREATOR, ERA, PLATFORM = range(5)

# Словарь пользователей: { user_id: {ответы} }
user_data = {}

# 📌 Вопросы и кнопки
questions = {
    GENRE: ("Какой жанр вас сегодня привлекает?", [
        "Комедия", "Триллер", "Фантастика", "Драма", "Романтика", "Ужасы", "Детектив"
    ]),
    MOOD: ("Какое настроение вы хотите поддержать или изменить?", [
        "Расслабиться", "Зарядиться энергией", "Погрузиться в размышления",
        "Посмеяться", "Испытать адреналин"
    ]),
    CREATOR: ("Есть ли любимые актёры, режиссёры или студии?", [
        "Кристофер Нолан", "Скарлетт Йоханссон", "Studio Ghibli", "Пропустить"
    ]),
    ERA: ("Хотите что-то новое или классику?", [
        "Новинки", "Классика", "Культовое кино 90-х или 2000-х"
    ]),
    PLATFORM: ("На какой платформе планируете смотреть?", [
        "Кинопоиск", "VK Video", "Ivi", "Okko", "YouTube", "Любая / есть подписка"
    ])
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data[update.effective_user.id] = {}
    context.user_data["step"] = GENRE
    await ask_question(update, context, GENRE)
    return GENRE

async def ask_question(update, context, step):
    text, options = questions[step]
    buttons = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in options]
    reply_markup = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id

    # Сохраняем ответ
    current_step = context.user_data.get("step", GENRE)
    user_data[user_id][current_step] = query.data

    next_step = current_step + 1
    context.user_data["step"] = next_step

    if next_step in questions:
        await ask_question(update, context, next_step)
        return next_step
    else:
        await query.edit_message_text("🔍 Подбираю фильмы по вашим предпочтениям...")
        await recommend_movies(update, context)
        return ConversationHandler.END

async def recommend_movies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    prefs = user_data.get(user_id, {})
    
    genre_map = {
        "Комедия": 35, "Триллер": 53, "Фантастика": 878, "Драма": 18,
        "Романтика": 10749, "Ужасы": 27, "Детектив": 9648
    }
    genre_id = genre_map.get(prefs.get(GENRE), 18)

    url = f"https://api.themoviedb.org/3/discover/movie"
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}"}
    params = {
        "language": "ru-RU",
        "sort_by": "popularity.desc",
        "with_genres": genre_id,
        "vote_count.gte": 100,
        "page": 1
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            data = await resp.json()

    results = data.get("results", [])[:5]
    for movie in results:
        title = movie.get("title")
        year = movie.get("release_date", "")[:4]
        overview = movie.get("overview", "Описание отсутствует")
        poster = movie.get("poster_path")
        poster_url = f"https://image.tmdb.org/t/p/w500{poster}" if poster else None

        text = f"{title} ({year})\n\n{overview}"
        buttons = [[
            InlineKeyboardButton("🔍 Подробнее", url=f"https://www.themoviedb.org/movie/{movie['id']}"),
            InlineKeyboardButton("🎬 Трейлер", url=f"https://www.youtube.com/results?search_query={title}+трейлер")
        ]]
        await context.bot.send_photo(
            chat_id=update.effective_user.id,
            photo=poster_url,
            caption=text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # Кнопка начать заново
    restart_btn = [[InlineKeyboardButton("🔁 Подобрать другой фильм", callback_data="restart")]]
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text="Хотите подобрать другой фильм?",
        reply_markup=InlineKeyboardMarkup(restart_btn)
    )

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)
    return GENRE

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GENRE: [CallbackQueryHandler(handle_answer)],
            MOOD: [CallbackQueryHandler(handle_answer)],
            CREATOR: [CallbackQueryHandler(handle_answer)],
            ERA: [CallbackQueryHandler(handle_answer)],
            PLATFORM: [CallbackQueryHandler(handle_answer)]
        },
        fallbacks=[CallbackQueryHandler(restart, pattern="^restart$")]
    )

    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()