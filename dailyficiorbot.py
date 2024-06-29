import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackContext

import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# Load environment variables from .env file
load_dotenv()

# Access the variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN')
INSTAGRAM_USER_ID = os.getenv('INSTAGRAM_USER_ID')
INSTAGRAM_ACCOUNT_TO_FOLLOW = os.getenv('INSTAGRAM_ACCOUNT_TO_FOLLOW')

# Initialize the bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Global variable to store chat_id
chat_id = None



# Setup Selenium WebDriver

chrome_options = Options()
chrome_options.binary_location = "/usr/bin/vivaldi"  # Update this path if necessary
chrome_options.add_argument("--headless")  # Run headless Chrome
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
service = Service('/usr/bin/chromedriver')  # Update this path to your chromedriver location if necessary

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global chat_id
    chat_id = update.message.chat_id
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Bot started!")

def get_latest_post():
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(f'https://www.instagram.com/{INSTAGRAM_ACCOUNT_TO_FOLLOW}/')
    time.sleep(5)  # Allow time for the page to load

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    driver.quit()
    
    scripts = soup.find_all('script', type="text/javascript")
    shared_data_script = None

    for script in scripts:
        if 'window._sharedData' in script.string:
            shared_data_script = script.string
            break
    
    if shared_data_script is None:
        return None
    
    shared_data = json.loads(shared_data_script.split(' = ', 1)[1].rstrip(';'))
    user_profile = shared_data['entry_data']['ProfilePage'][0]['graphql']['user']
    media = user_profile['edge_owner_to_timeline_media']['edges']
    
    if media:
        latest_post = media[0]['node']
        return {
            'media_url': latest_post['display_url'],
            'permalink': f"https://www.instagram.com/p/{latest_post['shortcode']}/",
            'caption': latest_post['edge_media_to_caption']['edges'][0]['node']['text'] if latest_post['edge_media_to_caption']['edges'] else '',
            'id': latest_post['id'],
        }
    return None

async def send_instagram_post(context: CallbackContext) -> None:
    latest_post = get_latest_post()
    if latest_post and chat_id:
        with open('last_post.txt', 'r+') as file:
            last_post_url = file.read()
            if last_post_url != latest_post['permalink']:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=latest_post['media_url'],
                    caption=f"{latest_post['caption']}\n\n{latest_post['permalink']}"
                )
                file.seek(0)
                file.write(latest_post['permalink'])
                file.truncate()

def main() -> None:
    if not os.path.exists('last_post.txt'):
        with open('last_post.txt', 'w') as f:
            f.write('')

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    start_handler = CommandHandler('start', start)
    fit_handler = CommandHandler('fit', send_instagram_post)
    application.add_handler(start_handler)
    application.add_handler(fit_handler)

    job_queue = application.job_queue
    job_queue.run_repeating(send_instagram_post, interval=20, first=0)

    application.run_polling()

if __name__ == '__main__':
    main()
