from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import logging
from datetime import datetime, time
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Konfigurasi logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Token API dari variabel lingkungan
TOKEN = os.getenv('TOKEN')

# ID Channel Telegram (gunakan @username atau ID channel)
CHANNEL_ID = os.getenv('CHANNEL_ID')

# URL Channel Telegram
CHANNEL_URL = os.getenv('CHANNEL_URL')  

# ID Grup Chat untuk mengirim informasi
GROUP_CHAT_ID = os.getenv('GROUP_CHAT_ID')

# Daftar ID Admin untuk persetujuan pesan
ADMIN_IDS = ['1505906052', '1271072566', '6566884051']  # Tambahkan admin lain sesuai kebutuhan

# Maksimal jumlah pesan per hari
MAX_TEXT_MESSAGES = 3
MAX_PHOTOS_VIDEOS = 2

# Dictionary untuk menyimpan informasi pengguna dan pesan yang menunggu persetujuan
user_data = {}
pending_messages = {}

# Fungsi untuk reset data harian
def reset_daily_limits(context: CallbackContext):
    global user_data
    user_data = {}
    logging.info("Daily limits have been reset.")

# Fungsi untuk memeriksa keanggotaan pengguna
async def is_user_member(user_id: int, context: CallbackContext):
    try:
        chat_member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except:
        return False

# Fungsi start
async def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if await is_user_member(user_id, context):
        await context.bot.send_message(chat_id=update.message.chat_id, text='Selamat datang! Anda sudah bisa mengirim pesan, foto, atau video ke channel.')
    else:
        keyboard = [
            [InlineKeyboardButton("Join Channel", url=CHANNEL_URL)],
            [InlineKeyboardButton("Cek Lagi", callback_data='cek_lagi')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=update.message.chat_id, text='Anda belum bergabung dengan channel. Silakan bergabung terlebih dahulu.', reply_markup=reply_markup)

# Fungsi untuk menangani callback query dari tombol
async def button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if query.data == 'cek_lagi':
        if await is_user_member(user_id, context):
            await query.edit_message_text(text='Selamat datang! Anda sudah bisa mengirim pesan, foto, atau video ke channel.')
        else:
            keyboard = [
                [InlineKeyboardButton("Join Channel", url=CHANNEL_URL)],
                [InlineKeyboardButton("Cek Lagi", callback_data='cek_lagi')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text='Anda belum bergabung dengan channel. Silakan bergabung terlebih dahulu.', reply_markup=reply_markup)
    else:
        message_id = query.data.split('_')[1]
    if message_id in pending_messages:
        message_info = pending_messages[message_id]

        if query.data.startswith('approve'):
            if 'approved_by' in message_info:
                await query.edit_message_text(text=f"Pesan ini sudah disetujui oleh admin lain ({message_info['approved_by']}).")
            else:
                message_info['approved_by'] = query.from_user.username
                await approve_message(context, message_info)
                await query.edit_message_text(text='Pesan telah disetujui dan dikirim ke channel.')
                pending_messages.pop(message_id, None)
        
        elif query.data.startswith('reject'):
            if 'approved_by' in message_info:
                await query.edit_message_text(text=f"Pesan ini sudah disetujui oleh admin lain ({message_info['approved_by']}). Tidak bisa ditolak.")
            else:
                message_info['rejected_by'] = query.from_user.username
                await reject_message(context, message_info)  # Memanggil fungsi reject_message
                await notify_user_rejection(context, message_info)  # Memberitahu user bahwa pesan ditolak
                pending_messages.pop(message_id, None)
                await query.edit_message_text(text='Pesan telah ditolak.')

async def notify_user_rejection(context: CallbackContext, message_info):
    user_id = message_info['user_id']
    try:
        await context.bot.send_message(chat_id=user_id, text="Maaf, pesan Anda telah ditolak oleh admin dan tidak akan dipublikasikan.")
    except telegram.error.Forbidden:
        logging.warning(f"Tidak bisa mengirim pesan penolakan ke user {user_id}. Mungkin user telah memblokir bot.")

async def reject_message(context: CallbackContext, message_info):
    # Mengirim informasi ke grup log
    await send_info_to_group_reject(message_info, context)
    
async def send_info_to_group_reject(message_info, context: CallbackContext):
    user_id = message_info['user_id']
    rejected_by = message_info.get('rejected_by', 'Unknown')
    message_type = message_info['message_type']

    # Mendapatkan informasi pengguna dari chat member
    try:
        chat_member = await context.bot.get_chat_member(chat_id=user_id, user_id=user_id)
        user_name = chat_member.user.full_name
    except Exception as e:
        user_name = 'Unknown'
        logging.error(f"Failed to get user info: {e}")

    info_message = (
        f"Pesan telah ditolak:\n"
        f"Pengguna ID: {user_id}\n"
        f"Nama Pengguna: {user_name}\n"
        f"Ditolak oleh: {rejected_by}\n"
        f"Tipe Pesan: {message_type}"
    )
    
    # Kirim informasi ke grup log
    await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=info_message)

    # Log ke konsol
    logging.info(f"Log Information: {info_message}")

# Fungsi untuk mengirim informasi ke grup
async def send_info_to_group(message_info, context: CallbackContext):
    user_id = message_info['user_id']
    approved_by = message_info.get('approved_by', 'Unknown')
    message_type = message_info['message_type']

    # Mendapatkan informasi pengguna dari chat member
    try:
        chat_member = await context.bot.get_chat_member(chat_id=user_id, user_id=user_id)
        user_name = chat_member.user.full_name
    except Exception as e:
        user_name = 'Unknown'
        logging.error(f"Failed to get user info: {e}")

    info_message = (
        f"Pesan telah disetujui:\n"
        f"Pengguna ID: {user_id}\n"
        f"Nama Pengguna: {user_name}\n"
        f"Disetujui oleh: {approved_by}\n"
        f"Tipe Pesan: {message_type}"
    )
    
    # Kirim informasi ke grup log
    await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=info_message)

    # Log ke konsol
    logging.info(f"Log Information: {info_message}")

# Fungsi untuk mengecek dan memperbarui batas harian
def check_and_update_limits(user_id, message_type):
    today = datetime.now().date()
    if user_id not in user_data:
        user_data[user_id] = {'text': 0, 'photo_video': 0, 'last_update': today}
    
    user_info = user_data[user_id]
    if user_info['last_update'] != today:
        user_info['text'] = 0
        user_info['photo_video'] = 0
        user_info['last_update'] = today
    
    if message_type == 'text' and user_info['text'] < MAX_TEXT_MESSAGES:
        user_info['text'] += 1
        return True
    elif message_type == 'photo_video' and user_info['photo_video'] < MAX_PHOTOS_VIDEOS:
        user_info['photo_video'] += 1
        return True
    return False

# Fungsi untuk mendapatkan sisa batas harian
def get_remaining_limits(user_id):
    user_info = user_data.get(user_id, {'text': 0, 'photo_video': 0, 'last_update': datetime.now().date()})
    remaining_text = MAX_TEXT_MESSAGES - user_info['text']
    remaining_photo_video = MAX_PHOTOS_VIDEOS - user_info['photo_video']
    return remaining_text, remaining_photo_video

# Fungsi untuk mengirim pesan peninjauan ke admin
async def send_for_approval(update: Update, context: CallbackContext, message_type: str, message_content, caption=None):
    user_id = update.message.from_user.id
    message_id = update.message.message_id

    pending_messages[str(message_id)] = {
        'user_id': user_id,
        'message_type': message_type,
        'message_content': message_content,
        'caption': caption,  # Menyimpan caption jika ada
        'message_id': message_id
    }
    
    keyboard = [
        [InlineKeyboardButton("Approve", callback_data=f'approve_{message_id}'),
         InlineKeyboardButton("Reject", callback_data=f'reject_{message_id}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    for admin_id in ADMIN_IDS:
        try:
            if message_type == 'text':
                await context.bot.send_message(chat_id=admin_id, text=f"Pesan baru untuk persetujuan:\n\n{message_content}", reply_markup=reply_markup)
            elif message_type == 'photo':
                await context.bot.send_photo(chat_id=admin_id, photo=message_content, caption=caption if caption else "Foto baru untuk persetujuan:", reply_markup=reply_markup)
            elif message_type == 'video':
                await context.bot.send_video(chat_id=admin_id, video=message_content, caption=caption if caption else "Video baru untuk persetujuan:", reply_markup=reply_markup)
        except telegram.error.Forbidden:
            logging.warning(f"Bot tidak dapat mengirim pesan ke admin {admin_id} karena admin belum memulai percakapan dengan bot.")


# Fungsi untuk meneruskan pesan yang disetujui ke channel
async def approve_message(context: CallbackContext, message_info):
    message_type = message_info['message_type']
    message_content = message_info['message_content']
    caption = message_info.get('caption')  # Mengambil caption jika ada
    approved_by = message_info['approved_by']
    
    if message_type == 'text':
        await context.bot.send_message(chat_id=CHANNEL_ID, text=message_content)
    elif message_type == 'photo':
        await context.bot.send_photo(chat_id=CHANNEL_ID, photo=message_content, caption=caption)  # Mengirim foto dengan caption
    elif message_type == 'video':
        await context.bot.send_video(chat_id=CHANNEL_ID, video=message_content, caption=caption)  # Mengirim video dengan caption
    
    # Mengirim informasi ke grup log
    await send_info_to_group(message_info, context)


# Fungsi untuk meneruskan pesan ke admin untuk persetujuan
async def forward_message(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if await is_user_member(user_id, context):
        chat_type = update.message.chat.type
        if chat_type == 'private' and check_and_update_limits(user_id, 'text'):
            user_message = update.message.text
            await send_for_approval(update, context, 'text', user_message)
            
            # Cek sisa limit dan beri tahu pengguna
            remaining_text, remaining_photo_video = get_remaining_limits(user_id)
            await update.message.reply_text(f'Pesan Anda telah dikirim untuk persetujuan.\nSisa limit: \nPesan: {remaining_text}\nMedia: {remaining_photo_video}')
        else:
            await update.message.reply_text('Anda telah mencapai batas maksimum pesan teks untuk hari ini.')
    else:
        await update.message.reply_text('Anda harus bergabung dengan channel terlebih dahulu untuk menggunakan bot ini.', 
                                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel", url=CHANNEL_URL)], 
                                                                          [InlineKeyboardButton("Cek Lagi", callback_data='cek_lagi')]]))

# Fungsi untuk meneruskan foto ke admin untuk persetujuan
async def forward_photo(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if await is_user_member(user_id, context):
        chat_type = update.message.chat.type
        if chat_type == 'private' and check_and_update_limits(user_id, 'photo_video'):
            photo_file = update.message.photo[-1].file_id
            caption = update.message.caption  # Mengambil caption
            await send_for_approval(update, context, 'photo', photo_file, caption=caption)
            await update.message.reply_text('Foto Anda telah dikirim untuk persetujuan.')

            remaining_text, remaining_photo_video = get_remaining_limits(user_id)
            await update.message.reply_text(f'Anda masih bisa mengirim:\nPesan: {remaining_text}\nMedia: {remaining_photo_video}')
        else:
            await update.message.reply_text('Anda telah mencapai batas maksimum foto/video untuk hari ini.')
    else:
        await update.message.reply_text('Anda harus bergabung dengan channel terlebih dahulu untuk menggunakan bot ini.', 
                                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel", url=CHANNEL_URL)], 
                                                                          [InlineKeyboardButton("Cek Lagi", callback_data='cek_lagi')]]))

# Fungsi untuk meneruskan video ke admin untuk persetujuan
async def forward_video(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if await is_user_member(user_id, context):
        chat_type = update.message.chat.type
        if chat_type == 'private' and check_and_update_limits(user_id, 'photo_video'):
            video_file = update.message.video.file_id
            caption = update.message.caption  # Mengambil caption
            await send_for_approval(update, context, 'video', video_file, caption=caption)
            await update.message.reply_text('Video Anda telah dikirim untuk persetujuan.')

            remaining_text, remaining_photo_video = get_remaining_limits(user_id)
            await update.message.reply_text(f'Anda masih bisa mengirim:\nPesan: {remaining_text}\nMedia: {remaining_photo_video}')
        else:
            await update.message.reply_text('Anda telah mencapai batas maksimum foto/video untuk hari ini.')
    else:
        await update.message.reply_text('Anda harus bergabung dengan channel terlebih dahulu untuk menggunakan bot ini.', 
                                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel", url=CHANNEL_URL)], 
                                                                          [InlineKeyboardButton("Cek Lagi", callback_data='cek_lagi')]]))

# Fungsi utama
def main():
    # Buat aplikasi
    app = Application.builder().token(TOKEN).build()

    # Handler untuk /start
    app.add_handler(CommandHandler('start', start))
    
    # Handler untuk pesan teks
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_message))
    
    # Handler untuk foto
    app.add_handler(MessageHandler(filters.PHOTO, forward_photo))
    
    # Handler untuk video
    app.add_handler(MessageHandler(filters.VIDEO, forward_video))
    
    # Handler untuk tombol callback
    app.add_handler(CallbackQueryHandler(button))

    # Setup JobQueue untuk reset batas harian
    job_queue = app.job_queue
    job_queue.run_daily(reset_daily_limits, time=time(0, 0, 0))

    # Jalankan bot
    app.run_polling()

if __name__ == '__main__':
    main()
