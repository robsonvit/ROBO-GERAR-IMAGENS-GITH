import os
import json
import time
import random
import requests
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

def send_to_telegram(filepath, caption):
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("Telegram Token ou Chat ID ausente. Pulando envio.")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    try:
        with open(filepath, 'rb') as f:
            files = {'photo': f}
            data = {'chat_id': chat_id, 'caption': caption}
            response = requests.post(url, files=files, data=data)
            if response.status_code == 200:
                print("✅ Imagem enviada com sucesso para o Telegram!")
            else:
                print(f"❌ Falha ao enviar imagem: {response.text}")
    except Exception as e:
        print(f"Erro ao enviar para o Telegram: {e}")

def main():
    # Carregar sessão de autenticação
    auth_session_str = os.environ.get('AUTH_SESSION_JSON')
    if not auth_session_str:
        print("Erro: A variável de ambiente AUTH_SESSION_JSON não está configurada.")
        return

    try:
        cookies = json.loads(auth_session_str)
    except json.JSONDecodeError:
        print("Erro: Falha ao interpretar o JSON da sessão AUTH_SESSION_JSON.")
        return

    # Preparar diretório de saída
    base_dir = os.path.dirname(os.path.dirname(__file__))
    output_dir = os.path.join(base_dir, 'output')
    os.makedirs(output_dir, exist_ok=True)

    single_prompt = os.environ.get('SINGLE_PROMPT')
    
    if single_prompt and single_prompt.strip():
        prompts = [single_prompt.strip()]
        print(f"🤖 Modo Telegram: Executando apenas o prompt enviado -> {prompts[0]}")
    else:
        # Ler prompts
        prompts_file = os.path.join(base_dir, 'data', 'prompts.txt')
        try:
            with open(prompts_file, 'r', encoding='utf-8') as f:
                prompts = [line.strip() for line in f.readlines() if line.strip()]
        except FileNotFoundError:
            print(f"Erro: Arquivo de prompts não encontrado em {prompts_file}")
            return

    if not prompts:
        print("Nenhum prompt encontrado.")
        return

    # Iniciar Playwright
    with sync_playwright() as p:
        print("Iniciando navegador headless...")
        browser = p.chromium.launch(headless=True)
        
        # User-Agent comum
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        context.add_cookies(cookies)
        page = context.new_page()
        stealth_sync(page)

        print("Navegando para Google Labs Flow...")
        page.goto('https://labs.google/fx/pt/tools/flow/', wait_until='domcontentloaded')
        time.sleep(random.uniform(3, 5))

        for idx, prompt in enumerate(prompts):
            print(f"\n--- Processando prompt {idx + 1}/{len(prompts)} ---")
            print(f"Texto: '{prompt}'")
            try:
                input_locator = page.locator('textarea, input[type="text"]').first
                input_locator.wait_for(state='visible', timeout=10000)
                input_locator.fill('')
                input_locator.type(prompt, delay=100)
                time.sleep(random.uniform(1.0, 2.0))
                input_locator.press('Enter')
                print("Solicitação enviada. Aguardando geração...")
                
                time.sleep(random.uniform(3.0, 5.0))
                
                image_locator = page.locator('img').last
                image_locator.wait_for(state='visible', timeout=45000)
                
                img_src = image_locator.get_attribute('src')
                
                if img_src:
                    if img_src.startswith('http'):
                        response = page.request.get(img_src)
                        img_data = response.body()
                    elif img_src.startswith('data:image'):
                        import base64
                        header, encoded = img_src.split(",", 1)
                        img_data = base64.b64decode(encoded)
                    else:
                        print("Formato de src de imagem não suportado para download direto.")
                        continue
                        
                    filename = f"geracao_{idx + 1}_{int(time.time())}.png"
                    filepath = os.path.join(output_dir, filename)
                    
                    with open(filepath, 'wb') as f:
                        f.write(img_data)
                    print(f"Sucesso: Imagem salva em {filepath}")
                    
                    # Enviar para o Telegram!
                    send_to_telegram(filepath, f"🎨 **Prompt:** {prompt}")
                else:
                    print("Falha: Não foi possível obter o src da imagem.")
                    
            except Exception as e:
                print(f"Erro durante o processamento do prompt '{prompt}': {e}")
                
            # Rate Limit entre gerações
            if idx < len(prompts) - 1:
                delay = random.uniform(15, 20)
                print(f"Rate Limit: Aguardando {delay:.2f}s para a próxima geração...")
                time.sleep(delay)

        print("\nFinalizado o processamento de todos os prompts.")
        browser.close()

if __name__ == "__main__":
    main()
