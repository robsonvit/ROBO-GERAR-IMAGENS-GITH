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
                
                print("Extraindo coordenadas da imagem para forçar menus de 2K...")
                box = image_locator.bounding_box()
                if not box:
                    raise Exception("Imagem não possui bounding box visível.")
                    
                # 1. Hover na imagem para revelar o botão de Opções
                page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                time.sleep(1.5)
                
                # 2. Encontrar e clicar no botão de 3 pontos
                dots_coords = page.evaluate('''() => {
                    const imgs = Array.from(document.querySelectorAll('img')).filter(i => i.src.includes('getMediaUrlRedirect') || i.src.startsWith('blob:'));
                    if (!imgs.length) return null;
                    const r = imgs[imgs.length - 1].getBoundingClientRect();
                    const btns = Array.from(document.querySelectorAll('button')).filter(btn => {
                        const rc = btn.getBoundingClientRect();
                        if (rc.width === 0) return false;
                        const cx = rc.left + rc.width/2;
                        const cy = rc.top + rc.height/2;
                        return cx >= r.right - 150 && cx <= r.right + 15 && cy >= r.top - 15 && cy <= r.top + 60;
                    });
                    if(!btns.length) return null;
                    btns.sort((a,b) => b.getBoundingClientRect().left - a.getBoundingClientRect().left);
                    const br = btns[0].getBoundingClientRect();
                    return { x: br.left + br.width/2, y: br.top + br.height/2 };
                }''')
                
                if not dots_coords:
                    raise Exception("Botão de opções (3 pontos) não encontrado na imagem.")
                    
                page.mouse.click(dots_coords['x'], dots_coords['y'])
                time.sleep(1.5)
                
                # 3. Encontrar menu "Baixar"
                baixar_coords = page.evaluate('''() => {
                    const items = Array.from(document.querySelectorAll('li, [role="menuitem"], [role="option"], .mat-mdc-menu-item')).filter(el => {
                        const t = (el.textContent||'').toLowerCase();
                        return t.includes('baixar') || t.includes('download');
                    });
                    if(!items.length) return null;
                    const br = items[0].getBoundingClientRect();
                    return { x: br.left + br.width/2, y: br.top + br.height/2 };
                }''')
                
                if not baixar_coords:
                    raise Exception("Item de menu 'Baixar' não encontrado.")
                    
                page.mouse.move(baixar_coords['x'], baixar_coords['y'])
                time.sleep(1.5)
                
                # 4. Encontrar botão "2K"
                k2_coords = page.evaluate('''() => {
                    const items = Array.from(document.querySelectorAll('li, [role="menuitem"], [role="option"], .mat-mdc-menu-item')).filter(el => {
                        return (el.textContent||'').toLowerCase().includes('2k');
                    });
                    if(!items.length) return null;
                    const br = items[0].getBoundingClientRect();
                    return { x: br.left + br.width/2, y: br.top + br.height/2 };
                }''')
                
                if not k2_coords:
                    raise Exception("Botão '2K' não encontrado no submenu.")
                    
                print("Iniciando interceptação oficial do download...")
                with page.expect_download(timeout=45000) as download_info:
                    page.mouse.click(k2_coords['x'], k2_coords['y'])
                    
                download = download_info.value
                filename = f"geracao_2k_{idx + 1}_{int(time.time())}.png"
                file_path = os.path.join(output_dir, filename)
                download.save_as(file_path)
                print(f"Sucesso: Imagem 2K salva em {file_path}")
                
                # Enviar para o Telegram via bot
                send_to_telegram(file_path, f"🎨 **Prompt:** {prompt}")
                    
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
