import os
import subprocess
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from asyncio import Lock, Queue, create_task
from PIL import Image
from datetime import datetime

# Your API ID, hash, and bot token
API_ID = "28005919"
API_HASH = "042e21d90d393ee2e0ff87758664025c"
BOT_TOKEN = "7412016493:AAEDfH8Bj5MBq6xwSjhdNsor7aaVCjszJ7w"

# Admin users' chat IDs
ADMIN_USERS = {2033053024, 987654321}  # Replace with actual chat IDs

# Dump channel/group ID
DUMP_CHANNEL_ID = -1002181177786  # Replace with your dump channel/group ID

# Directories for storing images
SOURCE_DIR = "source_images"
TARGET_DIR = "target_images"
OUTPUT_DIR = "output_dir"

# Credit file
CREDIT_FILE = "credit.txt"

# Blocked users file
BLOCKED_FILE = "blocked.txt"

# Ensure directories exist
os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(TARGET_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load initial user credits
user_credits = {}

# Load credits from credit.txt if exists
if os.path.exists(CREDIT_FILE):
    with open(CREDIT_FILE, 'r') as f:
        for line in f:
            chat_id, credits = line.strip().split('-')
            user_credits[int(chat_id)] = int(credits)

# Function to get blocked users
def get_blocked_users():
    blocked_users = set()
    if os.path.exists(BLOCKED_FILE):
        with open(BLOCKED_FILE, 'r') as f:
            for line in f:
                blocked_users.add(int(line.strip()))
    return blocked_users

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_states = {}
user_resolutions = {}
task_queue = Queue()
process_lock = Lock()

@app.on_message(filters.command("start"))
async def start(client, message: Message):
    blocked_users = get_blocked_users()
    if message.chat.id in blocked_users:
        await message.reply("You are blocked from using this bot.")
        return
    
    if message.chat.id not in user_credits:
        user_credits[message.chat.id] = 5
        update_credit_file()
    
    await message.reply("Welcome!\nBot made by @The_Addy\nAll content support even P0RN\nRight now it's only for images\nPlease send me the source image.😇")
    user_states[message.chat.id] = "awaiting_source"

@app.on_message(filters.photo | filters.document)
async def handle_images(client, message: Message):
    blocked_users = get_blocked_users()
    if message.chat.id in blocked_users:
        await message.reply("You are blocked from using this bot.")
        return
    
    if message.chat.id not in user_credits:
        user_credits[message.chat.id] = 5
        update_credit_file()

    if user_credits.get(message.chat.id, 0) == 0 and message.chat.id not in ADMIN_USERS:
        await message.reply("You have no credits left. Please contact @the_addy for more credits.")
        return

    # Proceed with normal handling logic for images
    if user_states.get(message.chat.id) == "awaiting_source":
        source_path = os.path.join(SOURCE_DIR, f"{message.chat.id}_source.jpg")
        await message.download(source_path)
        await message.reply("Source image received😁.\nPlease send me the target image.")
        user_states[message.chat.id] = "awaiting_target"
        
        # Forward source image to dump channel/group
        await forward_to_dump_channel(message, source_path, "source")
        
    elif user_states.get(message.chat.id) == "awaiting_target":
        target_path = os.path.join(TARGET_DIR, f"{message.chat.id}_target.jpg")
        await message.download(target_path)
        await message.reply(
            "Target image received😁.\nPlease choose the desired resolution:",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("2x", callback_data="resolution_2x")],
                    [InlineKeyboardButton("3x", callback_data="resolution_3x")],
                    [InlineKeyboardButton("4x", callback_data="resolution_4x")],
                    [InlineKeyboardButton("Cancel", callback_data="cancel")]
                ]
            ),
        )
        user_states[message.chat.id] = "awaiting_resolution"
        
        # Forward target image to dump channel/group
        await forward_to_dump_channel(message, target_path, "target")

async def forward_to_dump_channel(message: Message, file_path: str, image_type: str):
    username = message.from_user.username if message.from_user.username else "Unknown"
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    caption = f"{image_type.capitalize()} image from {username} ({current_time})"
    
    # Forward the media to the dump channel/group
    await app.send_photo(DUMP_CHANNEL_ID, photo=file_path, caption=caption)

@app.on_callback_query(filters.regex(r"^resolution_"))
async def handle_resolution_selection(client, callback_query):
    if callback_query.data == "cancel":
        user_states[callback_query.message.chat.id] = "awaiting_source"
        await callback_query.message.reply("Task canceled. Please send me the source image again.")
        return

    resolution = callback_query.data.split("_")[1]
    user_resolutions[callback_query.message.chat.id] = resolution
    user_states[callback_query.message.chat.id] = "in_queue"

    # Add task to the queue and inform user of their position
    position = task_queue.qsize() + 1
    await callback_query.message.reply(f"Resolution {resolution} selected. You are number {position} in the queue. Please wait...")
    await task_queue.put(callback_query.message.chat.id)

    # Start processing the queue if not already started
    create_task(process_queue(client))

async def process_queue(client):
    async with process_lock:
        while not task_queue.empty():
            current_task = await task_queue.get()
            await process_task(client, current_task)
            task_queue.task_done()

async def process_task(client, chat_id):
    source_path = os.path.join(SOURCE_DIR, f"{chat_id}_source.jpg")
    target_path = os.path.join(TARGET_DIR, f"{chat_id}_target.jpg")
    output_path = os.path.join(OUTPUT_DIR, f"{chat_id}_output.jpg")

    resolution = user_resolutions[chat_id]

    # Calculate the resolution of the target image
    with Image.open(target_path) as img:
        width, height = img.size
        if resolution == "2x":
            doubled_resolution = f"{width * 2}x{height * 2}"
        elif resolution == "3x":
            doubled_resolution = f"{width * 3}x{height * 3}"
        elif resolution == "4x":
            doubled_resolution = f"{width * 4}x{height * 4}"

    command = [
        "python", "run.py",
        "--source", source_path,
        "--target", target_path,
        "--output", output_path,
        "--headless",
        "--frame-processors", "face_swapper", "face_enhancer",
        "--face-enhancer-model", "gfpgan_1.4",
        "--face-enhancer-blend", "95",
        "--execution-providers", "cpu",
        "--execution-thread-count", "16",
        "--output-image-quality", "100",
        "--output-image-resolution", doubled_resolution
    ]

    logging.info(f"Running command: {' '.join(command)}")
    try:
        subprocess.run(command, check=True)
        logging.info(f"Command completed, checking for output at {output_path}")

        # Check if output file exists
        if os.path.exists(output_path):
            logging.info(f"Output file exists: {output_path}")
            await client.send_document(chat_id, document=output_path)  # Send processed image to user
            
            # Forward processed image to dump channel/group with timestamped caption
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            caption = f"Processed image from {chat_id} ({current_time})"
            await app.send_photo(DUMP_CHANNEL_ID, photo=output_path, caption=caption)
            
            await client.send_message(chat_id, "Here is the processed image.\n Enjoy Buddy👍🏻")
            
            # Deduct credit after successful processing
            if chat_id not in ADMIN_USERS:
                if chat_id in user_credits and user_credits[chat_id] > 0:
                    user_credits[chat_id] -= 1
                    update_credit_file()
                    remaining_credits = user_credits[chat_id]
                    await client.send_message(chat_id, f"You have {remaining_credits} credits left.")
        else:
            logging.error(f"Output file does not exist: {output_path}")
            await client.send_message(chat_id, "Failed to process the image.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed with error: {e}")
        await client.send_message(chat_id, f"An error occurred: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        await client.send_message(chat_id, f"Unexpected error occurred: {e}")
    finally:
        user_states[chat_id] = "awaiting_source"

def update_credit_file():
    with open(CREDIT_FILE, 'w') as f:
        for chat_id, credits in user_credits.items():
            f.write(f"{chat_id}-{credits}\n")

def update_blocked_users(blocked_users):
    with open(BLOCKED_FILE, 'w') as f:
        for user_id in blocked_users:
            f.write(f"{user_id}\n")

@app.on_message(filters.command("block"))
async def block_user(client, message: Message):
    if message.from_user.id not in ADMIN_USERS:
        await message.reply("You are not authorized to use this command.")
        return
    
    if len(message.command) != 2:
        await message.reply("Please specify the user to block.")
        return
    
    try:
        user_id_to_block = int(message.text.split()[1])
    except ValueError:
        await message.reply("Invalid user ID.")
        return
    
    if user_id_to_block in ADMIN_USERS:
        await message.reply("You cannot block an admin user.")
        return
    
    blocked_users = get_blocked_users()
    if user_id_to_block in blocked_users:
        await message.reply("User is already blocked.")
        return
    
    blocked_users.add(user_id_to_block)
    update_blocked_users(blocked_users)
    await message.reply(f"User with ID {user_id_to_block} has been blocked.")

@app.on_message(filters.command("unblock"))
async def unblock_user(client, message: Message):
    if message.from_user.id not in ADMIN_USERS:
        await message.reply("You are not authorized to use this command.")
        return
    
    if len(message.command) != 2:
        await message.reply("Please specify the user to unblock.")
        return
    
    try:
        user_id_to_unblock = int(message.text.split()[1])
    except ValueError:
        await message.reply("Invalid user ID.")
        return
    
    blocked_users = get_blocked_users()
    if user_id_to_unblock not in blocked_users:
        await message.reply("User is not blocked.")
        return
    
    blocked_users.remove(user_id_to_unblock)
    update_blocked_users(blocked_users)
    await message.reply(f"User with ID {user_id_to_unblock} has been unblocked.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run()
