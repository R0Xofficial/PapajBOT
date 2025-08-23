import os
import logging
import sqlite3
import asyncio
from datetime import datetime, time as dt_time
import pytz

# ZMIANA: Importujemy funkcję do wczytywania pliku .env
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ZMIANA: Wczytujemy zmienne środowiskowe z pliku .env na samym początku
load_dotenv()

# --- KONFIGURACJA ---
# Teraz os.getenv odczyta wartość z pliku .env, jeśli jest dostępna
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "DOMYSLNY_TOKEN_JEZELI_BRAK")
DB_FILE = "barka_bot.db"

# --- TEKST PIOSENKI "BARKA" ---
BARKA_LYRICS = [
    "Pan kiedyś stanął nad brzegiem,\nSzukał ludzi gotowych pójść za Nim,\nBy łowić serca słów Bożych prawdą.",
    "O Panie, to Ty na mnie spojrzałeś,\nTwoje usta dziś wyrzekły me imię.\nSwoją barkę pozostawiam na brzegu,\nRazem z Tobą nowy zacznę dziś łów.",
    "Jestem ubogim człowiekiem,\nMoim skarbem są ręce gotowe\nDo pracy z Tobą i czyste serce.",
    "Ty, potrzebujesz mych dłoni,\nMych serc, młodzieńczej odwagi,\nTylko Ty, rybaka, chciałeś mieć w domu swym,\nBy sobą dzielić się z nim."
]

# Konfiguracja logowania
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
POLAND_TZ = pytz.timezone('Europe/Warsaw')

# --- BAZA DANYCH ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS subscribers (chat_id INTEGER PRIMARY KEY)')
    conn.commit()
    conn.close()
    logger.info("Baza danych zainicjowana.")

def get_subscribers() -> set:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id FROM subscribers")
    subscribers = {row[0] for row in cursor.fetchall()}
    conn.close()
    return subscribers

def add_subscriber(chat_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO subscribers (chat_id) VALUES (?)", (chat_id,))
    conn.commit()
    conn.close()

def remove_subscriber(chat_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subscribers WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()

# --- FUNKCJE BOTA ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wysyła wiadomość powitalną."""
    welcome_message = (
        "Cześć! Jestem BarkaBot 🎵\n\n"
        "Codziennie o godzinie 21:37 będę wysyłać na ten czat tekst 'Barki'.\n\n"
        "➡️ Aby rozpocząć, użyj komendy /subskrybuj.\n"
        "ℹ️ Po listę wszystkich komend wpisz /pomoc."
    )
    await update.message.reply_text(welcome_message)

async def pomoc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wysyła listę dostępnych komend."""
    help_text = (
        "Oto lista dostępnych komend:\n\n"
        "✅ /subskrybuj - Aktywuje codzienną wysyłkę 'Barki' o 21:37.\n\n"
        "❌ /anuluj - Zatrzymuje subskrypcję dla tego czatu.\n\n"
        "📊 /status - Sprawdza status subskrypcji i czas następnej wysyłki.\n\n"
        "▶️ /terazspiewaj - Wysyła 'Barkę' natychmiast (do testów).\n\n"
        "❓ /pomoc - Wyświetla tę listę komend."
    )
    await update.message.reply_text(help_text)
    
async def subskrybuj(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dodaje czat do listy subskrybentów."""
    chat_id = update.effective_chat.id
    if chat_id not in get_subscribers():
        add_subscriber(chat_id)
        logger.info(f"Nowa subskrypcja z czatu {chat_id}.")
        await update.message.reply_text(
            "Subskrypcja aktywowana! 🎉 Widzimy się o 21:37.\n"
            "Jeśli zechcesz zrezygnować, wpisz /anuluj."
        )
    else:
        await update.message.reply_text(
            "Ten czat jest już na liście subskrybentów! Użyj /status, aby sprawdzić szczegóły."
        )

async def anuluj(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usuwa czat z listy subskrybentów."""
    chat_id = update.effective_chat.id
    if chat_id in get_subscribers():
        remove_subscriber(chat_id)
        logger.info(f"Czat {chat_id} zrezygnował z subskrypcji.")
        await update.message.reply_text("Subskrypcja dla tego czatu została anulowana.")
    else:
        await update.message.reply_text("Tego czatu nie ma na liście subskrybentów.")

async def send_barka(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Główna funkcja wysyłająca wiadomości."""
    job = context.job
    subscribers = get_subscribers()
    logger.info(f"Uruchomiono zadanie '{job.name}'. Znaleziono {len(subscribers)} subskrybentów.")
    if not subscribers:
        logger.warning("Brak subskrybentów do wysłania wiadomości.")
        return

    for chat_id in subscribers:
        try:
            logger.info(f"Wysyłanie do {chat_id}...")
            for part in BARKA_LYRICS:
                await context.bot.send_message(chat_id=chat_id, text=part)
                await asyncio.sleep(2)
            logger.info(f"Wysłano pomyślnie do {chat_id}.")
        except Exception as e:
            logger.error(f"Nie udało się wysłać wiadomości do {chat_id}: {e}")
            if "bot was blocked" in str(e) or "chat not found" in str(e) or "kicked" in str(e):
                remove_subscriber(chat_id)
                logger.info(f"Czat {chat_id} jest niedostępny. Usunięto z subskrypcji.")

async def teraz_spiewaj(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wysyła 'Barkę' na żądanie."""
    chat_id = update.effective_chat.id
    logger.info(f"Użytkownik {chat_id} uruchomił ręczne wysyłanie przez /terazspiewaj.")
    await update.message.reply_text("Już śpiewam! Rozpoczynam wysyłkę 'Barki'...")
    context.job_queue.run_once(send_barka, 1, name="manual_send")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sprawdza status bota."""
    sub_count = len(get_subscribers())
    jobs = context.job_queue.get_jobs_by_name("codzienna_barka")
    now_in_poland = datetime.now(POLAND_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')
    
    status_text = (
        f"Status bota:\n"
        f"🕰️ Aktualny czas (PL): {now_in_poland}\n"
        f"👥 Liczba subskrybentów: {sub_count}\n"
    )
    
    if jobs:
        next_run = jobs[0].next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        status_text += f"🎶 Następne śpiewanie: {next_run}"
    else:
        status_text += "🎶 Zaplanowane zadanie: Nie"
        
    await update.message.reply_text(status_text)

def main() -> None:
    # Delikatna zmiana w sprawdzaniu tokena, aby był bardziej uniwersalny
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "DOMYSLNY_TOKEN_JEZELI_BRAK":
        logger.error("Nie znaleziono tokena bota! Upewnij się, że plik .env istnieje i zawiera TELEGRAM_TOKEN.")
        return

    init_db()
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    job_queue = application.job_queue
    job_queue.run_daily(
        send_barka,
        time=dt_time(hour=21, minute=37, tzinfo=POLAND_TZ),
        name="codzienna_barka"
    )
    logger.info("Zaplanowano zadanie 'codzienna_barka'.")

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("pomoc", pomoc))
    application.add_handler(CommandHandler("subskrybuj", subskrybuj))
    application.add_handler(CommandHandler("anuluj", anuluj))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("terazspiewaj", teraz_spiewaj))
    
    logger.info("Bot został uruchomiony i nasłuchuje...")
    application.run_polling()

if __name__ == '__main__':
    main()
