"""
translations.py — All user-facing strings in English, Russian and Uzbek.

Usage:
    from translations import t, LANGS
    text = t(lang, "welcome", name="Ali")   # → formatted string
    text = t(lang, "dl_wait")               # → plain string
"""

LANGS = {
    "en": "🇬🇧 English",
    "ru": "🇷🇺 Русский",
    "uz": "🇺🇿 O'zbekcha",
}

_T: dict[str, dict[str, str]] = {

    # ── Language selection ─────────────────────────────────────────────────
    "choose_lang": {
        "en": "👋 Welcome! Please choose your language:",
        "ru": "👋 Добро пожаловать! Пожалуйста, выберите язык:",
        "uz": "👋 Xush kelibsiz! Tilni tanlang:",
    },
    "lang_set": {
        "en": "✅ Language set to English.",
        "ru": "✅ Язык установлен: Русский.",
        "uz": "✅ Til o'rnatildi: O'zbek.",
    },
    "lang_changed": {
        "en": "🌐 Language changed to English.",
        "ru": "🌐 Язык изменён на Русский.",
        "uz": "🌐 Til o'zgartirildi: O'zbek.",
    },

    # ── /start welcome ─────────────────────────────────────────────────────
    "welcome": {
        "en": (
            "👋 Hello, <b>{name}</b>!\n"
            "Welcome to <b>@topam1z_bot</b>\n\n"
            "What I can do:\n"
            "⬇️ Download videos — YouTube, Instagram, TikTok, Twitter & more\n"
            "🎵 Extract MP3 from any video\n"
            "🔍 Identify any song\n"
            "🎬 Edit videos — trim, compress, convert, merge, reverse & more\n\n"
            "📢 {channel}"
        ),
        "ru": (
            "👋 Привет, <b>{name}</b>!\n"
            "Добро пожаловать в <b>@topam1z_bot</b>\n\n"
            "Что умею:\n"
            "⬇️ Скачивать видео — YouTube, Instagram, TikTok, Twitter и другие\n"
            "🎵 Извлекать MP3 из любого видео\n"
            "🔍 Определять любую песню\n"
            "🎬 Редактировать — обрезать, сжать, конвертировать, склеить и другое\n\n"
            "📢 {channel}"
        ),
        "uz": (
            "👋 Salom, <b>{name}</b>!\n"
            "<b>@topam1z_bot</b>ga xush kelibsiz\n\n"
            "Nima qila olaman:\n"
            "⬇️ Video yuklab olish — YouTube, Instagram, TikTok, Twitter va boshqalar\n"
            "🎵 Har qanday videodan MP3 ajratish\n"
            "🔍 Istalgan qo'shiqni aniqlash\n"
            "🎬 Video tahrirlash — kesish, siqish, format, birlashtirish va boshqalar\n\n"
            "📢 {channel}"
        ),
    },

    # ── Menu button labels ─────────────────────────────────────────────────
    "btn_download":      {"en": "⬇️ Download",          "ru": "⬇️ Скачать",            "uz": "⬇️ Yuklab olish"},
    "btn_extract_audio": {"en": "🎵 Extract Audio",      "ru": "🎵 Извлечь аудио",      "uz": "🎵 Audio ajratish"},
    "btn_file_audio":    {"en": "🎬 File → Audio",       "ru": "🎬 Файл → Аудио",       "uz": "🎬 Fayl → Audio"},
    "btn_find_music":    {"en": "🔍 Find Music",         "ru": "🔍 Найти музыку",        "uz": "🔍 Musiqa topish"},
    "btn_profile":       {"en": "👤 My Profile",         "ru": "👤 Мой профиль",          "uz": "👤 Mening profilim"},
    "btn_batch":         {"en": "💾 Batch Download",     "ru": "💾 Пакетная загрузка",   "uz": "💾 Ko'p yuklab olish"},
    "btn_trim":          {"en": "✂️ Trim Video",          "ru": "✂️ Обрезать",            "uz": "✂️ Videoni kesish"},
    "btn_compress":      {"en": "🗜️ Compress Video",     "ru": "🗜️ Сжать видео",        "uz": "🗜️ Videoni siqish"},
    "btn_screenshot":    {"en": "📸 Screenshot",         "ru": "📸 Скриншот",            "uz": "📸 Skrinshot"},
    "btn_gif":           {"en": "🎞️ Video → GIF",        "ru": "🎞️ Видео → GIF",        "uz": "🎞️ Video → GIF"},
    "btn_convert":       {"en": "🔄 Convert Format",     "ru": "🔄 Конвертировать",      "uz": "🔄 Format o'zgartirish"},
    "btn_remove_audio":  {"en": "🔇 Remove Audio",       "ru": "🔇 Убрать звук",         "uz": "🔇 Ovozni o'chirish"},
    "btn_merge":         {"en": "🔀 Merge Audio+Video",  "ru": "🔀 Склеить аудио+видео", "uz": "🔀 Audio+Video birlashtirish"},
    "btn_media_info":    {"en": "📋 Media Info",         "ru": "📋 Инфо о медиа",        "uz": "📋 Media ma'lumoti"},
    "btn_speed":         {"en": "⚡ Change Speed",        "ru": "⚡ Изменить скорость",   "uz": "⚡ Tezlikni o'zgartirish"},
    "btn_reverse":       {"en": "🔁 Reverse Video",      "ru": "🔁 Реверс видео",        "uz": "🔁 Videoni teskari aylantirish"},
    "btn_post_info":     {"en": "ℹ️ Post Info",           "ru": "ℹ️ Инфо о посте",        "uz": "ℹ️ Post haqida ma'lumot"},
    "btn_stats":         {"en": "📊 Stats",               "ru": "📊 Статистика",          "uz": "📊 Statistika"},
    "btn_help":          {"en": "❓ Help",                "ru": "❓ Помощь",               "uz": "❓ Yordam"},
    "btn_movie":         {"en": "🎬 Movies",              "ru": "🎬 Фильмы",               "uz": "🎬 Kinolar"},
    "btn_language":      {"en": "🌐 Language",           "ru": "🌐 Язык",                "uz": "🌐 Til"},

    # ── Prompts ────────────────────────────────────────────────────────────
    "prompt_download": {
        "en": "📎 Paste a video URL:\n<i>YouTube · Instagram · TikTok · Twitter · Facebook</i>",
        "ru": "📎 Вставьте ссылку на видео:\n<i>YouTube · Instagram · TikTok · Twitter · Facebook</i>",
        "uz": "📎 Video havolasini yuboring:\n<i>YouTube · Instagram · TikTok · Twitter · Facebook</i>",
    },
    "prompt_extract_audio": {
        "en": "🔗 Paste a URL to extract audio from:",
        "ru": "🔗 Вставьте ссылку для извлечения аудио:",
        "uz": "🔗 Audio ajratish uchun havola yuboring:",
    },
    "prompt_file_audio": {
        "en": "📁 Send a video file — I'll extract the audio as MP3:",
        "ru": "📁 Отправьте видеофайл — я извлеку аудио в MP3:",
        "uz": "📁 Video fayl yuboring — men uni MP3 ga aylantirib beraman:",
    },
    "prompt_profile": {
        "en": "👤 Send an Instagram username (e.g. <code>@username</code>):",
        "ru": "👤 Введите имя пользователя Instagram (например, <code>@username</code>):",
        "uz": "👤 Instagram foydalanuvchi nomini yuboring (masalan, <code>@username</code>):",
    },
    "prompt_batch": {
        "en": "📋 Send multiple URLs, one per line (max 20):",
        "ru": "📋 Отправьте несколько ссылок, по одной на строке (макс. 20):",
        "uz": "📋 Bir nechta havola yuboring, har biri alohida qatorda (maks. 20 ta):",
    },
    "prompt_trim": {
        "en": "📁 Send the video to trim:",
        "ru": "📁 Отправьте видео для обрезки:",
        "uz": "📁 Kesish uchun video fayl yuboring:",
    },
    "prompt_trim_times": {
        "en": "✂️ Send <b>start and end time</b>:\n<code>0:30 - 1:45</code>  or  <code>30 105</code>",
        "ru": "✂️ Укажите <b>начало и конец</b>:\n<code>0:30 - 1:45</code>  или  <code>30 105</code>",
        "uz": "✂️ <b>Boshlanish va tugash vaqtini</b> yuboring:\n<code>0:30 - 1:45</code>  yoki  <code>30 105</code>",
    },
    "prompt_compress": {
        "en": "📁 Send the video to compress:",
        "ru": "📁 Отправьте видео для сжатия:",
        "uz": "📁 Siqish uchun video fayl yuboring:",
    },
    "prompt_screenshot": {
        "en": "📁 Send the video — I'll take a screenshot from it:",
        "ru": "📁 Отправьте видео — я сделаю скриншот:",
        "uz": "📁 Video fayl yuboring — men undan skrinshot olaman:",
    },
    "prompt_screenshot_ts": {
        "en": "📸 Send the <b>timestamp</b>:\n<code>1:23</code>  or  <code>83</code>",
        "ru": "📸 Укажите <b>временную метку</b>:\n<code>1:23</code>  или  <code>83</code>",
        "uz": "📸 <b>Vaqtni</b> yuboring:\n<code>1:23</code>  yoki  <code>83</code>",
    },
    "prompt_gif": {
        "en": "📁 Send the video to convert to GIF (max 15s):",
        "ru": "📁 Отправьте видео для создания GIF (макс. 15 сек.):",
        "uz": "📁 GIF yaratish uchun video fayl yuboring (maks. 15 soniya):",
    },
    "prompt_gif_times": {
        "en": "🎞️ Send <b>start and end time</b> (max 15s):\n<code>0:10 - 0:20</code>",
        "ru": "🎞️ Укажите <b>начало и конец</b> (макс. 15 сек.):\n<code>0:10 - 0:20</code>",
        "uz": "🎞️ <b>Boshlanish va tugash vaqtini</b> yuboring (maks. 15 soniya):\n<code>0:10 - 0:20</code>",
    },
    "prompt_convert": {
        "en": "📁 Send the video to convert:",
        "ru": "📁 Отправьте видео для конвертации:",
        "uz": "📁 Format o'zgartirish uchun video fayl yuboring:",
    },
    "prompt_remove_audio": {
        "en": "📁 Send the video to remove audio from:",
        "ru": "📁 Отправьте видео для отключения звука:",
        "uz": "📁 Ovozni o'chirish uchun video fayl yuboring:",
    },
    "prompt_merge_video": {
        "en": "📁 Send the <b>video</b> file first:",
        "ru": "📁 Сначала отправьте <b>видео</b>:",
        "uz": "📁 Avval <b>video</b> fayl yuboring:",
    },
    "prompt_merge_audio": {
        "en": "✅ Video received!\n\nNow send the <b>audio file</b> to merge with it.",
        "ru": "✅ Видео получено!\n\nТеперь отправьте <b>аудиофайл</b> для склейки.",
        "uz": "✅ Video qabul qilindi!\n\nEndi birlashtirish uchun <b>audio fayl</b> yuboring.",
    },
    "prompt_media_info": {
        "en": "📁 Send a video or audio file to analyse:",
        "ru": "📁 Отправьте видео или аудио для анализа:",
        "uz": "📁 Tahlil qilish uchun video yoki audio fayl yuboring:",
    },
    "prompt_speed": {
        "en": "📁 Send the video to change speed:",
        "ru": "📁 Отправьте видео для изменения скорости:",
        "uz": "📁 Tezlikni o'zgartirish uchun video fayl yuboring:",
    },
    "prompt_reverse": {
        "en": "📁 Send the video to reverse:",
        "ru": "📁 Отправьте видео для реверса:",
        "uz": "📁 Teskari aylantirish uchun video fayl yuboring:",
    },
    "prompt_post_info": {
        "en": "🔗 Paste a post URL:",
        "ru": "🔗 Вставьте ссылку на пост:",
        "uz": "🔗 Post havolasini yuboring:",
    },
    "prompt_music_how": {
        "en": "🔍 <b>Find Music</b>\n\nHow do you want to identify the song?",
        "ru": "🔍 <b>Найти музыку</b>\n\nКак вы хотите определить песню?",
        "uz": "🔍 <b>Musiqa topish</b>\n\nQo'shiqni qanday aniqlamoqchisiz?",
    },
    "prompt_music_link": {
        "en": "🔗 <b>Music by link</b>\n\nPaste a video URL:",
        "ru": "🔗 <b>Музыка по ссылке</b>\n\nВставьте ссылку на видео:",
        "uz": "🔗 <b>Havola orqali musiqa</b>\n\nVideo havolasini yuboring:",
    },
    "prompt_music_file": {
        "en": "🎤 <b>Music by audio</b>\n\nSend an audio or voice message:",
        "ru": "🎤 <b>Музыка по аудио</b>\n\nОтправьте аудио или голосовое сообщение:",
        "uz": "🎤 <b>Audio orqali musiqa</b>\n\nAudio yoki ovozli xabar yuboring:",
    },
    "prompt_music_text": {
        "en": "✏️ <b>Music by name</b>\n\nType a song title or artist:",
        "ru": "✏️ <b>Музыка по названию</b>\n\nВведите название или исполнителя:",
        "uz": "✏️ <b>Nom orqali musiqa</b>\n\nQo'shiq nomi yoki ijrochi yozing:",
    },
    "choose_quality": {
        "en": "📺 Choose video quality:",
        "ru": "📺 Выберите качество видео:",
        "uz": "📺 Video sifatini tanlang:",
    },
    "choose_compression": {
        "en": "🗜️ Choose compression level:",
        "ru": "🗜️ Выберите уровень сжатия:",
        "uz": "🗜️ Siqish darajasini tanlang:",
    },
    "choose_format": {
        "en": "🔄 Choose output format:",
        "ru": "🔄 Выберите формат для конвертации:",
        "uz": "🔄 Chiqish formatini tanlang:",
    },
    "choose_speed": {
        "en": "⚡ Choose playback speed:",
        "ru": "⚡ Выберите скорость воспроизведения:",
        "uz": "⚡ Ijro tezligini tanlang:",
    },

    # ── Status messages ────────────────────────────────────────────────────
    "dl_video_wait": {
        "en": "⏳ Downloading video ({quality}p)…",
        "ru": "⏳ Скачиваю видео ({quality}p)…",
        "uz": "⏳ Video yuklanmoqda ({quality}p)…",
    },
    "dl_audio_wait": {
        "en": "⏳ Downloading audio…",
        "ru": "⏳ Скачиваю аудио…",
        "uz": "⏳ Audio yuklanmoqda…",
    },
    "dl_info_wait": {
        "en": "ℹ️ Fetching info…",
        "ru": "ℹ️ Получаю информацию…",
        "uz": "ℹ️ Ma'lumot olinmoqda…",
    },
    "music_identifying": {
        "en": "🎵 Identifying music…",
        "ru": "🎵 Определяю музыку…",
        "uz": "🎵 Musiqa aniqlanmoqda…",
    },
    "music_sample_wait": {
        "en": "🎵 Downloading sample to identify…",
        "ru": "🎵 Скачиваю отрывок для определения…",
        "uz": "🎵 Aniqlash uchun namuna yuklanmoqda…",
    },
    "music_searching": {
        "en": "🔍 Searching for <b>{query}</b>…",
        "ru": "🔍 Ищу <b>{query}</b>…",
        "uz": "🔍 <b>{query}</b> qidirilmoqda…",
    },
    "extracting_audio": {
        "en": "🎵 Extracting audio…",
        "ru": "🎵 Извлекаю аудио…",
        "uz": "🎵 Audio ajratilmoqda…",
    },
    "trimming": {
        "en": "✂️ Trimming {start}s → {end}s…",
        "ru": "✂️ Обрезаю {start}s → {end}s…",
        "uz": "✂️ Kesilmoqda {start}s → {end}s…",
    },
    "compressing": {
        "en": "🗜️ Compressing to {height}p…",
        "ru": "🗜️ Сжимаю до {height}p…",
        "uz": "🗜️ {height}p ga siqilmoqda…",
    },
    "screenshot_wait": {
        "en": "📸 Taking screenshot at {ts}s…",
        "ru": "📸 Делаю скриншот на {ts}s…",
        "uz": "📸 {ts}s dagi skrinshot olinmoqda…",
    },
    "gif_wait": {
        "en": "🎞️ Creating GIF ({dur}s)…",
        "ru": "🎞️ Создаю GIF ({dur}s)…",
        "uz": "🎞️ GIF yaratilmoqda ({dur}s)…",
    },
    "converting": {
        "en": "🔄 Converting to {fmt}…",
        "ru": "🔄 Конвертирую в {fmt}…",
        "uz": "🔄 {fmt} formatiga o'zgartirilmoqda…",
    },
    "removing_audio": {
        "en": "🔇 Removing audio…",
        "ru": "🔇 Убираю звук…",
        "uz": "🔇 Ovoz o'chirilmoqda…",
    },
    "changing_speed": {
        "en": "⚡ Changing speed to {speed}x…",
        "ru": "⚡ Изменяю скорость до {speed}x…",
        "uz": "⚡ Tezlik {speed}x ga o'zgartirilmoqda…",
    },
    "reversing": {
        "en": "🔁 Reversing video…",
        "ru": "🔁 Реверсирую видео…",
        "uz": "🔁 Video teskari aylantirilmoqda…",
    },
    "merging": {
        "en": "🔀 Merging audio + video…",
        "ru": "🔀 Объединяю аудио + видео…",
        "uz": "🔀 Audio va video birlashtirilmoqda…",
    },
    "fetching_profile": {
        "en": "👤 Fetching @{username}…",
        "ru": "👤 Загружаю @{username}…",
        "uz": "👤 @{username} profili yuklanmoqda…",
    },
    "analysing": {
        "en": "📋 Analysing media…",
        "ru": "📋 Анализирую медиафайл…",
        "uz": "📋 Media tahlil qilinmoqda…",
    },
    "batch_starting": {
        "en": "⬇️ Starting <b>{count}</b> download(s)…\n<i>Each will be sent as it finishes.</i>",
        "ru": "⬇️ Запускаю <b>{count}</b> загрузку(и)…\n<i>Каждая будет отправлена по завершении.</i>",
        "uz": "⬇️ <b>{count}</b> ta yuklab olish boshlandi…\n<i>Har biri tayyor bo'lgach yuboriladi.</i>",
    },
    "queued": {
        "en": "⏳ Your request is queued — I'll process it shortly…",
        "ru": "⏳ Ваш запрос в очереди — обработаю в ближайшее время…",
        "uz": "⏳ So'rovingiz navbatda — tez orada qayta ishlanadi…",
    },

    # ── Errors ─────────────────────────────────────────────────────────────
    "err_download": {
        "en": "❌ <b>Download failed</b>\n<code>{error}</code>",
        "ru": "❌ <b>Ошибка загрузки</b>\n<code>{error}</code>",
        "uz": "❌ <b>Yuklab olish xatosi</b>\n<code>{error}</code>",
    },
    "err_too_large": {
        "en": "⚠️ File too large ({size}). Try a lower quality.",
        "ru": "⚠️ Файл слишком большой ({size}). Попробуйте меньшее качество.",
        "uz": "⚠️ Fayl juda katta ({size}). Pastroq sifatni sinab ko'ring.",
    },
    "err_too_large_upload": {
        "en": "⚠️ <b>File too large</b> ({size})\nBots can only handle files up to {max} MB.",
        "ru": "⚠️ <b>Файл слишком большой</b> ({size})\nБоты могут обрабатывать файлы до {max} МБ.",
        "uz": "⚠️ <b>Fayl juda katta</b> ({size})\nBotlar {max} MB gacha fayllarni qabul qiladi.",
    },
    "err_not_supported": {
        "en": "⚠️ Platform not supported.\nSupported: YouTube, Instagram, TikTok, Twitter/X, Facebook, Pinterest",
        "ru": "⚠️ Платформа не поддерживается.\nПоддерживаются: YouTube, Instagram, TikTok, Twitter/X, Facebook, Pinterest",
        "uz": "⚠️ Bu platforma qo'llab-quvvatlanmaydi.\nQo'llab-quvvatlanadi: YouTube, Instagram, TikTok, Twitter/X, Facebook, Pinterest",
    },
    "err_recognition": {
        "en": "❌ <b>Recognition failed</b>\n<code>{error}</code>",
        "ru": "❌ <b>Ошибка определения</b>\n<code>{error}</code>",
        "uz": "❌ <b>Aniqlash xatosi</b>\n<code>{error}</code>",
    },
    "err_profile_429": {
        "en": "⚠️ Instagram is rate-limiting us. Try again in 5–10 minutes.",
        "ru": "⚠️ Instagram ограничивает запросы. Попробуйте через 5–10 минут.",
        "uz": "⚠️ Instagram so'rovlarni vaqtincha chekladi. 5–10 daqiqadan so'ng qayta urinib ko'ring.",
    },
    "err_profile_404": {
        "en": "❌ Account <code>@{username}</code> not found or is private.",
        "ru": "❌ Аккаунт <code>@{username}</code> не найден или закрыт.",
        "uz": "❌ <code>@{username}</code> akkaunti topilmadi yoki yopiq.",
    },
    "err_profile": {
        "en": "❌ Could not fetch profile.\n<code>{error}</code>",
        "ru": "❌ Не удалось загрузить профиль.\n<code>{error}</code>",
        "uz": "❌ Profil yuklanmadi.\n<code>{error}</code>",
    },
    "err_invalid_ts": {
        "en": "⚠️ Invalid timestamp. Use: <code>1:23</code> or <code>83</code>",
        "ru": "⚠️ Неверная временная метка. Используйте: <code>1:23</code> или <code>83</code>",
        "uz": "⚠️ Vaqt noto'g'ri. Foydalaning: <code>1:23</code> yoki <code>83</code>",
    },
    "err_invalid_range": {
        "en": "⚠️ Invalid range. Use: <code>0:10 - 0:20</code>",
        "ru": "⚠️ Неверный диапазон. Используйте: <code>0:10 - 0:20</code>",
        "uz": "⚠️ Diapazon noto'g'ri. Foydalaning: <code>0:10 - 0:20</code>",
    },
    "err_gif_too_long": {
        "en": "⚠️ Max GIF duration is 15 seconds.",
        "ru": "⚠️ Максимальная длина GIF — 15 секунд.",
        "uz": "⚠️ GIF maksimal uzunligi — 15 soniya.",
    },
    "err_session": {
        "en": "⚠️ Session expired. Start again.",
        "ru": "⚠️ Сессия истекла. Начните заново.",
        "uz": "⚠️ Sessiya tugadi. Qaytadan boshlang.",
    },
    "err_no_results": {
        "en": "❓ No results found.",
        "ru": "❓ Результаты не найдены.",
        "uz": "❓ Hech narsa topilmadi.",
    },
    "err_no_url": {
        "en": "⚠️ No valid URLs found.",
        "ru": "⚠️ Действующих ссылок не найдено.",
        "uz": "⚠️ Haqiqiy havolalar topilmadi.",
    },
    "err_not_url": {
        "en": "⚠️ That doesn't look like a URL.",
        "ru": "⚠️ Это не похоже на ссылку.",
        "uz": "⚠️ Bu havola emas.",
    },
    "err_general": {
        "en": "❌ <b>Failed</b>\n<code>{error}</code>",
        "ru": "❌ <b>Ошибка</b>\n<code>{error}</code>",
        "uz": "❌ <b>Xato</b>\n<code>{error}</code>",
    },

    # ── Success / result messages ──────────────────────────────────────────
    "music_identified": {
        "en": "🎵 <b>Song identified!</b>",
        "ru": "🎵 <b>Песня определена!</b>",
        "uz": "🎵 <b>Qo'shiq aniqlandi!</b>",
    },
    "music_not_found": {
        "en": "❓ Could not identify the song. Try a different clip.",
        "ru": "❓ Не удалось определить песню. Попробуйте другой отрывок.",
        "uz": "❓ Qo'shiqni aniqlab bo'lmadi. Boshqa qismni sinab ko'ring.",
    },
    "music_results_title": {
        "en": "🎵 <b>Music Results</b>  (page {page}/{total})",
        "ru": "🎵 <b>Результаты</b>  (страница {page}/{total})",
        "uz": "🎵 <b>Natijalar</b>  ({page}/{total} sahifa)",
    },
    "batch_done": {
        "en": "✅ Batch done — <b>{ok}</b> delivered, <b>{fail}</b> failed.",
        "ru": "✅ Готово — <b>{ok}</b> доставлено, <b>{fail}</b> не удалось.",
        "uz": "✅ Tayyor — <b>{ok}</b> ta yuborildi, <b>{fail}</b> ta xato.",
    },
    "cancelled": {
        "en": "↩️ Cancelled.",
        "ru": "↩️ Отменено.",
        "uz": "↩️ Bekor qilindi.",
    },
    "url_detected": {
        "en": "{icon} <b>{platform}</b>\n\nChoose an action:",
        "ru": "{icon} <b>{platform}</b>\n\nВыберите действие:",
        "uz": "{icon} <b>{platform}</b>\n\nAmalni tanlang:",
    },
    "what_to_do": {
        "en": "What would you like to do?",
        "ru": "Что вы хотите сделать?",
        "uz": "Nima qilmoqchisiz?",
    },
    "video_received": {
        "en": "🎬 <b>{name}</b>  ·  {size}\n\nChoose an action:",
        "ru": "🎬 <b>{name}</b>  ·  {size}\n\nВыберите действие:",
        "uz": "🎬 <b>{name}</b>  ·  {size}\n\nAmalni tanlang:",
    },
    "audio_received": {
        "en": "🎵 Audio received. Identify the song?",
        "ru": "🎵 Аудио получено. Определить песню?",
        "uz": "🎵 Audio qabul qilindi. Qo'shiqni aniqlaymizmi?",
    },
    "fallback": {
        "en": "Send a video link, or choose an option from the menu below.",
        "ru": "Отправьте ссылку на видео или выберите действие из меню.",
        "uz": "Video havolasini yuboring yoki quyidagi menyudan tanlang.",
    },
    "done": {
        "en": "✅ Done.",
        "ru": "✅ Готово.",
        "uz": "✅ Bajarildi.",
    },

    # ── Admin auth ─────────────────────────────────────────────────────────
    "admin_pass_prompt": {
        "en": "🔐 <b>Admin Authentication Required</b>\n\nEnter your passcode:\n<i>Message will be deleted automatically.</i>",
        "ru": "🔐 <b>Требуется аутентификация администратора</b>\n\nВведите пароль:\n<i>Сообщение будет удалено автоматически.</i>",
        "uz": "🔐 <b>Admin autentifikatsiyasi talab qilinadi</b>\n\nParolni kiriting:\n<i>Xabar avtomatik o'chiriladi.</i>",
    },
    "admin_authenticated": {
        "en": "✅ <b>Authenticated!</b> Welcome to the admin panel.",
        "ru": "✅ <b>Аутентификация успешна!</b> Добро пожаловать в панель администратора.",
        "uz": "✅ <b>Tasdiqlandi!</b> Admin paneliga xush kelibsiz.",
    },
    "admin_wrong_pass": {
        "en": "❌ Wrong passcode. {left} attempt(s) left.",
        "ru": "❌ Неверный пароль. Осталось попыток: {left}.",
        "uz": "❌ Noto'g'ri parol. {left} ta urinish qoldi.",
    },
    "admin_locked": {
        "en": "🔒 Too many failed attempts. Try again in {sec}s.",
        "ru": "🔒 Слишком много неудачных попыток. Повторите через {sec}с.",
        "uz": "🔒 Juda ko'p noto'g'ri urinish. {sec} soniyadan so'ng qayta urinib ko'ring.",
    },
    "banned": {
        "en": "🚫 <b>You are banned.</b>",
        "ru": "🚫 <b>Вы заблокированы.</b>",
        "uz": "🚫 <b>Siz bloklangansiz.</b>",
    },
    "admins_only": {
        "en": "⛔ Admins only.",
        "ru": "⛔ Только для администраторов.",
        "uz": "⛔ Faqat adminlar uchun.",
    },

    # ── Help ───────────────────────────────────────────────────────────────
    "help": {
        "en": (
            "❓ <b>@topam1z_bot — Complete Guide</b>\n"
            "<i>via @topam1z_news</i>\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📥 <b>DOWNLOADING</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⬇️ <b>Download Video</b>\n"
            "  Paste a link → choose quality:\n"
            "  📱 360p  │  📺 720p  │  🖥 1080p  │  ✨ Best\n"
            "  Supports: YouTube, Instagram, TikTok, Twitter/X, Facebook, Pinterest\n\n"
            "🎵 <b>Extract Audio</b>\n"
            "  Paste a link → receive MP3 file\n\n"
            "💾 <b>Batch Download</b>\n"
            "  Send up to 20 links, one per line\n"
            "  Each file is sent as it finishes downloading\n\n"
            "📦 <b>File size</b>: files over 50 MB are auto-uploaded\n"
            "  to a temporary link (valid 24 hours)\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🎵 <b>MUSIC RECOGNITION</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔍 <b>Find Music</b> — 3 ways to identify a song:\n"
            "  🔗 By link     — paste a video URL\n"
            "  🎤 By audio    — send an audio/voice message\n"
            "  ✏️ By name     — type a song title or artist\n\n"
            "  Results: up to 10 per page with ◀️ ▶️ navigation\n"
            "  Tap a number button to download the MP3 directly\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🎬 <b>VIDEO TOOLS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "All tools work by sending a video file, then choosing an action:\n\n"
            "🎬 <b>File → Audio</b>  Extract MP3 from any video\n"
            "✂️ <b>Trim</b>          Cut a section: <code>0:30 - 1:45</code>\n"
            "🗜️ <b>Compress</b>      Reduce size: Light 720p / Medium 480p / Heavy 360p\n"
            "📸 <b>Screenshot</b>    Grab a frame at a specific timestamp\n"
            "🎞️ <b>GIF</b>           Convert a short clip (max 15s) to GIF\n"
            "🔄 <b>Convert</b>       Change format: MP4 / MKV / WEBM / MOV / AVI\n"
            "🔇 <b>Remove Audio</b>  Strip audio track from video\n"
            "🔀 <b>Merge</b>         Combine a video + separate audio file\n"
            "⚡ <b>Speed</b>         Change playback: 0.25x / 0.5x / 1.5x / 2x / 4x\n"
            "🔁 <b>Reverse</b>       Play video backwards (max 2 min / 100 MB)\n"
            "📋 <b>Media Info</b>    Show codec, resolution, FPS, bitrate, duration\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📡 <b>INLINE MODE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Use the bot in any chat without opening it:\n"
            "  Type <code>@topam1z_bot</code> + a video link\n"
            "  Two options appear: ⬇️ Video or 🎵 Audio\n"
            "  Select one — the result is delivered to that chat\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👤 <b>YOUR PROFILE & RANKS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Tap <b>My Profile</b> to see your rank and statistics.\n"
            "Rank is based on total actions (downloads + edits + recognitions):\n"
            "  🌱 Newcomer → ⭐ Beginner → 🥈 Regular\n"
            "  🥇 Active → 💎 Power User → 👑 Legend\n\n"
            "Higher rank = fewer ads between downloads.\n\n"

            "📢 Channel: {channel}"
        ),
        "ru": (
            "❓ <b>@topam1z_bot — Полное руководство</b>\n"
            "<i>via @topam1z_news</i>\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📥 <b>СКАЧИВАНИЕ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⬇️ <b>Скачать видео</b>\n"
            "  Вставьте ссылку → выберите качество:\n"
            "  📱 360p  │  📺 720p  │  🖥 1080p  │  ✨ Лучшее\n"
            "  Платформы: YouTube, Instagram, TikTok, Twitter/X, Facebook, Pinterest\n\n"
            "🎵 <b>Извлечь аудио</b>\n"
            "  Вставьте ссылку → получите MP3\n\n"
            "💾 <b>Пакетная загрузка</b>\n"
            "  До 20 ссылок, по одной на строке\n"
            "  Каждый файл отправляется по готовности\n\n"
            "📦 <b>Размер файла</b>: файлы более 50 МБ автоматически\n"
            "  загружаются на временный хост (ссылка 24 часа)\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🎵 <b>РАСПОЗНАВАНИЕ МУЗЫКИ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔍 <b>Найти музыку</b> — 3 способа:\n"
            "  🔗 По ссылке    — вставьте URL видео\n"
            "  🎤 По аудио     — отправьте аудио/голосовое\n"
            "  ✏️ По названию  — введите название или исполнителя\n\n"
            "  Результаты: до 10 на странице, навигация ◀️ ▶️\n"
            "  Нажмите на номер — скачать MP3 сразу\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🎬 <b>ИНСТРУМЕНТЫ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Отправьте видео → выберите действие:\n\n"
            "🎬 <b>Файл → Аудио</b>  Извлечь MP3 из видео\n"
            "✂️ <b>Обрезать</b>       Вырезать фрагмент: <code>0:30 - 1:45</code>\n"
            "🗜️ <b>Сжать</b>          Уменьшить размер: Лёгкое 720p / Среднее 480p / Сильное 360p\n"
            "📸 <b>Скриншот</b>       Кадр в заданный момент\n"
            "🎞️ <b>GIF</b>            Конвертировать клип (до 15 сек) в GIF\n"
            "🔄 <b>Конвертировать</b> Изменить формат: MP4 / MKV / WEBM / MOV / AVI\n"
            "🔇 <b>Убрать звук</b>    Удалить аудиодорожку\n"
            "🔀 <b>Объединить</b>     Совместить видео + отдельный аудиофайл\n"
            "⚡ <b>Скорость</b>        Изменить: 0.25x / 0.5x / 1.5x / 2x / 4x\n"
            "🔁 <b>Реверс</b>          Воспроизвести задом наперёд (макс. 2 мин / 100 МБ)\n"
            "📋 <b>Инфо о медиа</b>   Кодек, разрешение, FPS, битрейт, длительность\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📡 <b>ИНЛАЙН РЕЖИМ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Используйте бота в любом чате:\n"
            "  Введите <code>@topam1z_bot</code> + ссылку на видео\n"
            "  Появятся два варианта: ⬇️ Видео или 🎵 Аудио\n"
            "  Выберите — результат придёт в этот чат\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👤 <b>ПРОФИЛЬ И РАНГИ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Нажмите <b>Мой профиль</b> для просмотра ранга и статистики.\n"
            "Ранг зависит от общего числа действий (загрузки + обработка + распознавание):\n"
            "  🌱 Новичок → ⭐ Начинающий → 🥈 Обычный\n"
            "  🥇 Активный → 💎 Продвинутый → 👑 Легенда\n\n"
            "Чем выше ранг — тем реже показывается реклама.\n\n"

            "📢 Канал: {channel}"
        ),
        "uz": (
            "❓ <b>@topam1z_bot — To'liq qo'llanma</b>\n"
            "<i>@topam1z_news orqali</i>\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📥 <b>YUKLAB OLISH</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⬇️ <b>Video yuklab olish</b>\n"
            "  Havola yuboring → sifatni tanlang:\n"
            "  📱 360p  │  📺 720p  │  🖥 1080p  │  ✨ Eng yaxshi\n"
            "  Platformalar: YouTube, Instagram, TikTok, Twitter/X, Facebook, Pinterest\n\n"
            "🎵 <b>Audio ajratish</b>\n"
            "  Havola yuboring → MP3 fayl oling\n\n"
            "💾 <b>Ko'p yuklab olish</b>\n"
            "  20 tagacha havola, har biri alohida qatorda\n"
            "  Har bir fayl tayyor bo'lgach yuboriladi\n\n"
            "📦 <b>Fayl hajmi</b>: 50 MB dan katta fayllar avtomatik\n"
            "  vaqtinchalik serverga yuklanadi (havola 24 soat ishlaydi)\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🎵 <b>MUSIQA ANIQLASH</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔍 <b>Musiqa topish</b> — 3 usul:\n"
            "  🔗 Havola orqali   — video URL yuboring\n"
            "  🎤 Audio orqali    — audio yoki ovozli xabar yuboring\n"
            "  ✏️ Nom orqali      — qo'shiq nomi yoki ijrochi yozing\n\n"
            "  Natijalar: sahifada 10 ta, ◀️ ▶️ tugmalari bilan\n"
            "  Raqam tugmasini bosing — MP3 ni darhol yuklab oling\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🎬 <b>VIDEO VOSITALAR</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Video fayl yuboring → kerakli amalni tanlang:\n\n"
            "🎬 <b>Fayl → Audio</b>      Har qanday videodan MP3 ajratish\n"
            "✂️ <b>Kesish</b>             Qismni kesib olish: <code>0:30 - 1:45</code>\n"
            "🗜️ <b>Siqish</b>             Hajmini kamaytirish: Yengil 720p / O'rta 480p / Kuchli 360p\n"
            "📸 <b>Skrinshot</b>          Belgilangan vaqtdagi kadrni olish\n"
            "🎞️ <b>GIF</b>                Qisqa klipni (maks. 15 soniya) GIF ga o'zgartirish\n"
            "🔄 <b>Format o'zgartirish</b> MP4 / MKV / WEBM / MOV / AVI\n"
            "🔇 <b>Ovozni o'chirish</b>   Video dan audio trekni o'chirish\n"
            "🔀 <b>Birlashtirish</b>      Video + alohida audio faylni birlashtirish\n"
            "⚡ <b>Tezlik</b>              O'zgartirish: 0.25x / 0.5x / 1.5x / 2x / 4x\n"
            "🔁 <b>Teskari</b>            Videoni orqaga o'ynatish (maks. 2 daqiqa / 100 MB)\n"
            "📋 <b>Media ma'lumoti</b>    Kodek, o'lcham, FPS, bitreyt, davomiylik\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📡 <b>INLINE REJIM</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Botni istalgan chatda ishlatish:\n"
            "  <code>@topam1z_bot</code> + video havolasini yozing\n"
            "  Ikki tanlov chiqadi: ⬇️ Video yoki 🎵 Audio\n"
            "  Birini tanlang — natija o'sha chatga yuboriladi\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👤 <b>PROFIL VA DARAJALAR</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Darajangiz va statistikani ko'rish uchun <b>Mening profilim</b> tugmasini bosing.\n"
            "Daraja umumiy harakatlar soniga qarab belgilanadi:\n"
            "(yuklab olish + tahrirlash + musiqa aniqlash)\n\n"
            "  🌱 Yangi → ⭐ Boshlang'ich → 🥈 Faol\n"
            "  🥇 Juda faol → 💎 Kuchli → 👑 Afsona\n\n"
            "Daraja qanchalik yuqori bo'lsa — reklama shunchalik kam ko'rsatiladi.\n\n"

            "📢 Kanal: {channel}"
        ),
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    """
    Return the translated string for key in the given language.
    Falls back to English if the key/lang is missing.
    Supports keyword formatting: t('uz', 'welcome', name='Ali', brand='Bot')
    """
    lang  = lang if lang in LANGS else "en"
    entry = _T.get(key, {})
    text  = entry.get(lang) or entry.get("en") or f"[{key}]"
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass   # partial format is fine
    return text
