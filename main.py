import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp as youtube_dl
from tqdm import tqdm

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = "7313633829:AAH7DyaCDz2npGa1WznwLdNmAEFn8zXwaOY"
DOWNLOAD_FOLDER = './'

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()  # Clear user data on /start
    await update.message.reply_text(
        '👋 Hello! I am your music bot! Send me a YouTube link, and I will convert it to MP3 for you. '
        'You can also type /help to see what I can do. #Bot Created and Run by @mista_trix & @Vaboh'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        'ℹ️ Send a YouTube link, and I will download and convert it to MP3 for you.\n\n'
        'You can choose the audio quality after sending the link.\n\n'
        'Commands:\n'
        '🔸 /start - Start the bot and see the welcome message\n'
        '🔸 /help - Get help and see available commands'
    )

async def choose_quality(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [
            InlineKeyboardButton("🎧 High Quality (320 kbps)", callback_data='320'),
            InlineKeyboardButton("🎵 Medium Quality (192 kbps)", callback_data='192'),
        ],
        [
            InlineKeyboardButton("🔊 Low Quality (128 kbps)", callback_data='128')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        'Please choose the audio quality you want for the download:', 
        reply_markup=reply_markup
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    quality = query.data
    youtube_url = context.user_data['youtube_url']
    download_choice = context.user_data.get('download_choice', 'single')

    await query.edit_message_text(f'🎬 Downloading audio from {youtube_url} in {quality} kbps...')

    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': quality,
            }],
            'restrictfilenames': True,
            'noplaylist': (download_choice == 'single'),
            'progress_hooks': [lambda d: progress_hook(d, query)],  # Add progress hook
        }

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(youtube_url, download=True)

            video_title = info_dict.get('title', 'Unknown Title')
            mp3_file_path = ydl.prepare_filename(info_dict).rsplit('.', 1)[0] + '.mp3'

            # Send the video thumbnail to the user
            thumbnail_url = info_dict.get('thumbnail')
            if thumbnail_url:
                await query.message.reply_photo(photo=thumbnail_url)

            if os.path.getsize(mp3_file_path) <= 100 * 1024 * 1024:  # Check if file is <= 100MB
                await query.message.reply_text(f'✅ Conversion complete! Sending {video_title}.mp3 to you...')
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=open(mp3_file_path, 'rb'))
            else:
                await query.message.reply_text(f'⚠️ File size exceeds 100MB, which is the limit for Telegram. Consider downloading a smaller file.')
            
            os.remove(mp3_file_path)
    except Exception as e:
        logging.error(f"Error processing YouTube link: {e}")
        await query.message.reply_text(
            "❌ An error occurred while processing your request. "
            "Please ensure the link is correct and try again."
        )

async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()  # Clear previous user data at the beginning

    youtube_url = update.message.text
    context.user_data['youtube_url'] = youtube_url
    
    if 'youtube.com' in youtube_url or 'youtu.be' in youtube_url:
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,  # Extract without downloading
            }
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(youtube_url, download=False)
                
                if 'entries' in info_dict:  # 'entries' indicates it's a playlist
                    # Ask the user what they want to do
                    keyboard = [
                        [
                            InlineKeyboardButton("🎵 Download Single Video", callback_data='single'),
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text(
                        "This link contains a playlist. I can only handle single videos. Proceeding to download single video.", 
                        reply_markup=reply_markup
                    )
                else:
                    # Proceed to choose quality if it's not a playlist
                    await choose_quality(update, context)
        except Exception as e:
            logging.error(f"Error extracting info: {e}")
            await update.message.reply_text("⚠️ Could not process the provided link. Please try again.")
    else:
        await update.message.reply_text("⚠️ Please provide a valid YouTube link.")

async def handle_playlist_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    choice = query.data
    context.user_data['download_choice'] = choice

    if choice == 'single':
        await choose_quality(query, context)

def progress_hook(d, query):
    # Progress Hook with tqdm progress bar
    if d['status'] == 'downloading':
        pbar = tqdm(total=100, bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} {elapsed}")
        progress = d.get('downloaded_bytes', 0) / d.get('total_bytes', 1) * 100
        pbar.update(progress)
        pbar.close()
    
    if d['status'] == 'finished':
        logging.info(f"Done downloading video: {d['filename']}")

def main() -> None:
    application = ApplicationBuilder().token(TOKEN).build()

    # Register command and message handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_audio))
    application.add_handler(CallbackQueryHandler(handle_playlist_choice, pattern='^single$'))
    application.add_handler(CallbackQueryHandler(button))

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()
