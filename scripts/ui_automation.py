import os
import json
import time
import random
import requests
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

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
        raw_cookies = json.loads(auth_session_str)
        cookies = []
        for c in raw_cookies:
            # Remover chaves que o Playwright não aceita
            for k in ['hostOnly', 'session', 'storeId', 'id']:
                if k in c:
                    del c[k]
            # Consertar sameSite
            if 'sameSite' in c:
                if c['sameSite'] not in ['Strict', 'Lax', 'None']:
                    del c['sameSite']
            cookies.append(c)
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
        Stealth().apply_stealth_sync(page)

        print("Navegando para Google Labs Flow...")
        page.goto('https://labs.google/fx/pt/tools/flow/', wait_until='domcontentloaded')
        time.sleep(random.uniform(3, 5))
        
        try:
            print("Procurando botão '+ Novo projeto'...")
            # Pega qualquer botão que contenha 'Novo projeto'
            btn_novo = page.locator("text=/Novo projeto/i").first
            # Se não estiver visível nos primeiros 5s, ignora e segue (pode já estar na tela certa)
            if btn_novo.is_visible(timeout=5000):
                btn_novo.click()
                print("✅ Botão '+ Novo projeto' clicado!")
                time.sleep(random.uniform(3.0, 5.0))
        except Exception as e:
            print(f"Botão não precisou ser clicado ou não achou: {e}")

        for idx, prompt in enumerate(prompts):
            print(f"\n--- Processando prompt {idx + 1}/{len(prompts)} ---")
            print(f"Texto: '{prompt}'")
            try:
                # Google Labs costuma usar <div contenteditable> ou textareas muito complexos.
                # get_by_role('textbox') pega qualquer campo de texto visível e acessível!
                input_locator = page.get_by_role('textbox').last
                input_locator.wait_for(state='visible', timeout=15000)
                
                # Clique e limpeza universal
                input_locator.click()
                page.keyboard.press('Control+A')
                page.keyboard.press('Backspace')
                input_locator.type(prompt, delay=100)
                time.sleep(random.uniform(1.0, 2.0))
                input_locator.press('Enter')
                print("Solicitação enviada. Aguardando geração...")
                
                time.sleep(random.uniform(3.0, 5.0))
                
                # Aguarda especificamente a imagem gerada (filtrando avatares/ícones)
                # O Google Labs geralmente usa URLs com 'getMediaUrlRedirect' para as criações em 2k
                image_locator = page.locator('img[src*="getMediaUrlRedirect"], img[src^="blob:"]').last
                image_locator.wait_for(state='visible', timeout=45000)
                
                # Pega o .src absoluto (em vez do atributo raw)
                img_src = image_locator.evaluate("node => node.src")
                print(f"URL da imagem gerada: {img_src[:100]}...")
                
                if img_src:
                    if img_src.startswith('blob:'):
                        # Para blobs, temos que usar fetch via JavaScript do navegador
                        base64_data = page.evaluate('''async (url) => {
                            const res = await fetch(url);
                            const blob = await res.blob();
                            return new Promise((resolve, reject) => {
                                const reader = new FileReader();
                                reader.onloadend = () => resolve(reader.result);
                                reader.onerror = reject;
                                reader.readAsDataURL(blob);
                            });
                        }''', img_src)
                        import base64
                        header, encoded = base64_data.split(",", 1)
                        img_data = base64.b64decode(encoded)
                    elif img_src.startswith('http'):
                        # Playwright request funciona em http nativamente
                        # Se não passar os cookies no request.get pode dar erro 403, 
                        # mas o context gerencia os cookies automaticamente!
                        response = page.request.get(img_src)
                        img_data = response.body()
                    elif img_src.startswith('data:image'):
                        import base64
                        header, encoded = img_src.split(",", 1)
                        img_data = base64.b64decode(encoded)
                    else:
                        print(f"Formato de src de imagem não suportado: {img_src[:50]}")
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
                try:
                    error_img = os.path.join(output_dir, f"error_{idx}.png")
                    page.screenshot(path=error_img)
                    send_to_telegram(error_img, "🚨 Erro! O bot não achou a caixa de texto. Veja o que ele está vendo:")
                except Exception as ex:
                    print(f"Erro ao tirar screenshot: {ex}")
                
            # Rate Limit entre gerações
            if idx < len(prompts) - 1:
                delay = random.uniform(15, 20)
                print(f"Rate Limit: Aguardando {delay:.2f}s para a próxima geração...")
                time.sleep(delay)

        print("\nFinalizado o processamento de todos os prompts.")
        browser.close()

if __name__ == "__main__":
    main()
