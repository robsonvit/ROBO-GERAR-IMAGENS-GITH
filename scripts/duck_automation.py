import os
import time
import base64
import requests
import telebot
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

if not TELEGRAM_BOT_TOKEN:
    print("ERRO: TELEGRAM_BOT_TOKEN não encontrado.")
    exit(1)

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
output_dir = os.path.join(BASE_DIR, 'output_duck')
os.makedirs(output_dir, exist_ok=True)

def gerar_imagem_duck(prompt: str) -> str:
    """Abre aba anônima, gera a imagem via Duck.ai e retorna o caminho do arquivo."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, # Alterado para rodar na nuvem
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='pt-BR'
        )
        page = context.new_page()
        
        try:
            print("Acessando duck.ai...")
            page.goto('https://duck.ai/', wait_until='networkidle', timeout=60000)
            time.sleep(3)
            
            print("Clicando em Nova Imagem...")
            try:
                import re
                btn_nova = page.get_by_text(re.compile(r"Nova Imagem|New Image", re.IGNORECASE)).first
                if btn_nova.is_visible(timeout=5000):
                    btn_nova.click()
                    time.sleep(2)
                else:
                    page.get_by_text(re.compile(r"Criar e editar imagens|Create and edit images", re.IGNORECASE)).first.click()
                    time.sleep(2)
            except Exception as e:
                print("Não achou botão Nova Imagem:", e)
                
            # Garante o prefixo "crie uma imagem"
            prompt_lower = prompt.lower()
            if not prompt_lower.startswith("crie") and not prompt_lower.startswith("gere") and not prompt_lower.startswith("faça"):
                prompt = f"crie a imagem de {prompt}"
                
            print(f"Enviando prompt calibrado: {prompt}")
            input_area = page.locator('textarea').first
            input_area.fill(prompt)
            time.sleep(1)
            input_area.press('Enter')
            time.sleep(3)
            
            # Verifica termos
            btn_continuar = page.locator('button', has_text=re.compile(r"Continuar|Continue|I Agree|Agree", re.IGNORECASE))
            if btn_continuar.count() > 0 and btn_continuar.first.is_visible():
                print("Aceitando termos de serviço (Continuar)...")
                btn_continuar.first.click()
                time.sleep(2)
                
            print("Aguardando geração da imagem (pode levar até 30s)...")
            
            # Aguarda o botão de download (Transferir imagem / Download image) ficar visível
            import re
            btn_download = page.get_by_role("button", name=re.compile(r"transferir imagem|download image", re.IGNORECASE)).last
            btn_download.wait_for(state='visible', timeout=60000)
            time.sleep(2)
            
            print("Imagem gerada! Clicando no botão de download...")
            file_path = os.path.join(output_dir, f"duck_img_{int(time.time())}.jpg")
            
            with page.expect_download(timeout=30000) as download_info:
                btn_download.click(force=True)
                
            download = download_info.value
            download.save_as(file_path)
                
            print(f"Imagem salva com sucesso via download nativo em {file_path}")
            return file_path
            
        except Exception as e:
            print(f"Erro no fluxo do Playwright: {e}")
            return None
        finally:
            browser.close()

@bot.message_handler(commands=['duck'])
def handle_duck(message):
    texto = message.text
    if len(texto) <= 6:
        bot.reply_to(message, "Por favor, envie o prompt. Ex: /duck um gato fofo")
        return
        
    prompt = texto[6:].strip()
    
    msg = bot.reply_to(message, "🦆 *Iniciando geração via Duck.ai (Aba anônima)...*\nAguarde uns segundos.", parse_mode='Markdown')
    
    img_path = gerar_imagem_duck(prompt)
    
    if img_path and os.path.exists(img_path):
        bot.edit_message_text(chat_id=msg.chat.id, message_id=msg.message_id, text="🦆 *Enviando imagem...*", parse_mode='Markdown')
        with open(img_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=f"🎨 *Prompt:* {prompt}\n🦆 *Gerado via Duck.ai (Anônimo)*", parse_mode='Markdown')
    else:
        bot.edit_message_text(chat_id=msg.chat.id, message_id=msg.message_id, text="❌ *Erro ao gerar imagem no Duck.ai.*", parse_mode='Markdown')

def enviar_para_telegram(img_path, prompt, msg_id=None):
    bot.send_photo(
        TELEGRAM_CHAT_ID, 
        open(img_path, 'rb'), 
        caption=f"🎨 *Prompt:* {prompt}\n🦆 *Gerado via Duck.ai (GitHub Actions)*", 
        parse_mode='Markdown'
    )
    if msg_id:
        try:
            bot.delete_message(TELEGRAM_CHAT_ID, msg_id)
        except:
            pass

import threading

def progress_updater(msg_id):
    import time
    bars = [
        "[■□□□□□□□□□] 10%",
        "[■■□□□□□□□□] 20%",
        "[■■■□□□□□□□] 30%",
        "[■■■■□□□□□□] 40%",
        "[■■■■■□□□□□] 50%",
        "[■■■■■■□□□□] 60%",
        "[■■■■■■■□□□] 70%",
        "[■■■■■■■■□□] 80%",
        "[■■■■■■■■■□] 90%",
        "[■■■■■■■■■■] 99%"
    ]
    global is_done
    idx = 0
    while not is_done and idx < len(bars):
        time.sleep(3)
        if is_done:
            break
        try:
            bot.edit_message_text(
                chat_id=TELEGRAM_CHAT_ID, 
                message_id=msg_id, 
                text=f"🦆 *PROMPT RECEBIDO E A IA ESTÁ TRABALHANDO*\n{bars[idx]}", 
                parse_mode='Markdown'
            )
        except Exception as e:
            pass
        idx += 1

is_done = False

if __name__ == "__main__":
    single_prompt = os.environ.get('SINGLE_PROMPT')
    msg_id = os.environ.get('MESSAGE_ID')
    
    if single_prompt and single_prompt.strip():
        print(f"[Bot] Rodando via SINGLE_PROMPT (Modo Action): {single_prompt}")
        
        # Notifica início se não tiver message_id da integração
        if not msg_id:
            msg = bot.send_message(TELEGRAM_CHAT_ID, f"🦆 *Iniciando geração via Duck.ai (Aba anônima)...*\nPrompt: {single_prompt}", parse_mode='Markdown')
            msg_id = msg.message_id
            
        t = threading.Thread(target=progress_updater, args=(msg_id,))
        t.start()
        
        img_path = gerar_imagem_duck(single_prompt)
        is_done = True
        
        if img_path and os.path.exists(img_path):
            enviar_para_telegram(img_path, single_prompt, msg_id)
        else:
            try:
                bot.edit_message_text(chat_id=TELEGRAM_CHAT_ID, message_id=msg_id, text="❌ *Erro ao gerar imagem no Duck.ai.*", parse_mode='Markdown')
            except:
                pass
    else:
        print("[Bot] Duck.ai Bot listener iniciado! Envie /duck <prompt> no Telegram.")
        bot.infinity_polling()

