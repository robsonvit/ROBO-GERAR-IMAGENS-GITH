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
            headless=False, # Pode mudar para True no futuro
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        try:
            print("Acessando duck.ai...")
            page.goto('https://duck.ai/', wait_until='networkidle', timeout=60000)
            time.sleep(3)
            
            print("Clicando em Nova Imagem...")
            try:
                btn_nova = page.get_by_text("Nova Imagem").first
                if btn_nova.is_visible(timeout=5000):
                    btn_nova.click()
                    time.sleep(2)
                else:
                    page.get_by_text("Criar e editar imagens").first.click()
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
            btn_continuar = page.locator('button', has_text="Continuar")
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

def enviar_para_telegram(img_path, prompt):
    bot.send_photo(
        TELEGRAM_CHAT_ID, 
        open(img_path, 'rb'), 
        caption=f"🎨 *Prompt:* {prompt}\n🦆 *Gerado via Duck.ai (GitHub Actions)*", 
        parse_mode='Markdown'
    )

if __name__ == "__main__":
    single_prompt = os.environ.get('SINGLE_PROMPT')
    if single_prompt and single_prompt.strip():
        print(f"[Bot] Rodando via SINGLE_PROMPT (Modo Action): {single_prompt}")
        # Notifica início
        msg = bot.send_message(TELEGRAM_CHAT_ID, f"🦆 *Iniciando geração via Duck.ai (Aba anônima)...*\nPrompt: {single_prompt}", parse_mode='Markdown')
        
        img_path = gerar_imagem_duck(single_prompt)
        if img_path and os.path.exists(img_path):
            enviar_para_telegram(img_path, single_prompt)
            bot.edit_message_text(chat_id=msg.chat.id, message_id=msg.message_id, text="✅ *Geração e envio concluídos!*", parse_mode='Markdown')
        else:
            bot.edit_message_text(chat_id=msg.chat.id, message_id=msg.message_id, text="❌ *Erro ao gerar imagem no Duck.ai.*", parse_mode='Markdown')
    else:
        print("[Bot] Duck.ai Bot listener iniciado! Envie /duck <prompt> no Telegram.")
        bot.infinity_polling()

