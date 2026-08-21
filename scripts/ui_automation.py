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

def send_status_message(text):
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not bot_token or not chat_id:
        return None
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        response = requests.post(url, data={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'})
        if response.status_code == 200:
            return response.json().get('result', {}).get('message_id')
    except Exception as e:
        print(f"Erro ao enviar mensagem de status: {e}")
    return None

def edit_status_message(message_id, text):
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not bot_token or not chat_id or not message_id:
        return
    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    try:
        requests.post(url, data={'chat_id': chat_id, 'message_id': message_id, 'text': text, 'parse_mode': 'Markdown'})
    except Exception as e:
        print(f"Erro ao editar mensagem de status: {e}")

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
        prompts = [p.strip() for p in single_prompt.split('\n') if p.strip()]
        print(f"🤖 Modo Telegram: Executando {len(prompts)} prompt(s) enviado(s)")
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

    status_msg_id = send_status_message(f"⏳ *Iniciando geração de {len(prompts)} imagem(ns)...*")

    # Iniciar Playwright
    with sync_playwright() as p:
        print("Iniciando navegador headless...")
        
        context = p.chromium.launch_persistent_context(
            user_data_dir="/tmp/playwright_user_data",
            headless=False,
            accept_downloads=True,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        # Criar uma nova página no contexto persistente
        page = context.pages[0] if context.pages else context.new_page()
        
        # Carregar os cookies
        print("Injetando cookies de autenticação do Google...")
        context.add_cookies(cookies)
        sucessos = 0
        falhas = 0

        for idx, prompt in enumerate(prompts):
            print(f"\n--- Processando prompt {idx + 1}/{len(prompts)} ---")
            print(f"Texto: '{prompt}'")
            
            tempo_restante = (len(prompts) - idx) * 2 # estimativa de 2 min por imagem
            edit_status_message(status_msg_id, f"⏳ *Gerando imagem {idx + 1} de {len(prompts)}*\nTempo estimado restante: ~{tempo_restante} minuto(s)")
            
            # Navega para a home do Flow a cada prompt para garantir uma tela 100% limpa (Novo Projeto)
            page.goto('https://labs.google/fx/pt/tools/flow/', wait_until='domcontentloaded')
            time.sleep(random.uniform(3, 5))
            
            try:
                print("Procurando botão '+ Novo projeto'...")
                btn_novo = page.locator("text=/Novo projeto/i").first
                if btn_novo.is_visible(timeout=5000):
                    btn_novo.click()
                    print("✅ Botão '+ Novo projeto' clicado para iniciar tela limpa!")
                    time.sleep(random.uniform(3.0, 5.0))
            except Exception as e:
                print(f"Botão não precisou ser clicado ou não achou: {e}")
            
            try:
                # Localiza o editor raiz do Google Labs
                input_locator = page.locator('[data-slate-editor="true"][contenteditable="true"]').first
                input_locator.wait_for(state='visible', timeout=15000)
                input_locator.click()
                
                # Conta quantas imagens existem ANTES de enviar o prompt
                old_count = page.locator('img[src*="getMediaUrlRedirect"], img[src^="blob:"]').count()
                
                input_locator.type(prompt, delay=100)
                time.sleep(random.uniform(1.0, 2.0))
                input_locator.press('Enter')
                print(f"Solicitação enviada. Imagens antes: {old_count}. Aguardando geração da nova imagem...")
                
                # Espera até que o número de imagens na tela aumente
                page.wait_for_function(f'''() => {{
                    const imgs = Array.from(document.querySelectorAll('img'));
                    const currentCount = imgs.filter(i => i.src.includes('getMediaUrlRedirect') || i.src.startsWith('blob:')).length;
                    return currentCount > {old_count};
                }}''', timeout=120000)
                
                print("Nova imagem gerada detectada com sucesso!")
                time.sleep(2.0) # Pequeno fôlego para a imagem renderizar completamente
                
                image_locator = page.locator('img[src*="getMediaUrlRedirect"], img[src^="blob:"]').first
                image_locator.wait_for(state='visible', timeout=45000)
                
                # 1 e 2. Wiggle do mouse até a geração finalizar e o botão de 3 pontos aparecer
                print("Aguardando finalização da geração (balançando o mouse até o ícone de 3 pontos aparecer)...")
                dots_coords = None
                for attempt in range(60): # 60 * 2s = 120s
                    box = page.evaluate('''() => {
                        const imgs = Array.from(document.querySelectorAll('img')).filter(i => i.src.includes('getMediaUrlRedirect') || i.src.startsWith('blob:'));
                        if (!imgs.length) return null;
                        const r = imgs[0].getBoundingClientRect();
                        return {x: r.left, y: r.top, width: r.width, height: r.height, right: r.right};
                    }''')
                    
                    if box:
                        # Wiggle the mouse to ensure hover state is triggered even if the DOM re-rendered
                        page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2)
                        time.sleep(0.2)
                        page.mouse.move(box['x'] + box['width']/2 + 10, box['y'] + box['height']/2 + 10)
                        time.sleep(0.3)
                        
                        coords = page.evaluate('''() => {
                            const imgs = Array.from(document.querySelectorAll('img')).filter(i => i.src.includes('getMediaUrlRedirect') || i.src.startsWith('blob:'));
                            if (!imgs.length) return null;
                            const r = imgs[0].getBoundingClientRect();
                            const btns = Array.from(document.querySelectorAll('button')).filter(btn => {
                                const rc = btn.getBoundingClientRect();
                                if (rc.width === 0) return false;
                                const cx = rc.left + rc.width/2;
                                const cy = rc.top + rc.height/2;
                                return cx >= r.right - 150 && cx <= r.right + 15 && cy >= r.top - 15 && cy <= r.top + 60;
                            });
                            if(btns.length > 0) {
                                btns.sort((a,b) => b.getBoundingClientRect().left - a.getBoundingClientRect().left);
                                const br = btns[0].getBoundingClientRect();
                                return { x: br.left + br.width/2, y: br.top + br.height/2 };
                            }
                            return null;
                        }''')
                        
                        if coords:
                            dots_coords = coords
                            break
                            
                    time.sleep(1.5)
                    
                if not dots_coords:
                    raise Exception("Timeout 120s: Botão de opções (3 pontos) não apareceu. A imagem pode não ter terminado de gerar.")
                    
                page.screenshot(path=os.path.join(output_dir, f"debug_1_hover_success_{idx}.png"))
                    
                page.mouse.click(dots_coords['x'], dots_coords['y'])
                time.sleep(1.5)
                page.screenshot(path=os.path.join(output_dir, f"debug_2_dots_{idx}.png"))
                
                # 3. Encontrar menu "Baixar"
                baixar_coords = page.evaluate('''() => {
                    const items = Array.from(document.querySelectorAll('li, [role="menuitem"], [role="option"], .mat-mdc-menu-item')).filter(el => {
                        const t = (el.textContent||'').toLowerCase();
                        const br = el.getBoundingClientRect();
                        return (t.includes('baixar') || t.includes('download')) && br.width > 0 && br.height > 0;
                    });
                    if(!items.length) return null;
                    const br = items[items.length - 1].getBoundingClientRect(); // Pega o último renderizado (mais recente na tela)
                    return { x: br.left + br.width/2, y: br.top + br.height/2 };
                }''')
                
                if not baixar_coords:
                    raise Exception("Item de menu 'Baixar' não encontrado visível.")
                    
                page.mouse.move(baixar_coords['x'], baixar_coords['y'])
                time.sleep(2.0)
                page.screenshot(path=os.path.join(output_dir, f"debug_3_baixar_{idx}.png"))
                
                # 4. Encontrar botão "2K"
                k2_coords = page.evaluate('''() => {
                    const items = Array.from(document.querySelectorAll('li, [role="menuitem"], [role="option"], .mat-mdc-menu-item')).filter(el => {
                        const br = el.getBoundingClientRect();
                        return (el.textContent||'').toLowerCase().includes('2k') && br.width > 0 && br.height > 0;
                    });
                    if(!items.length) return null;
                    const br = items[items.length - 1].getBoundingClientRect();
                    return { x: br.left + br.width/2, y: br.top + br.height/2 };
                }''')
                
                if not k2_coords:
                    raise Exception("Botão '2K' não encontrado no submenu.")
                    
                print("Iniciando interceptação oficial do download...")
                try:
                    with page.expect_download(timeout=150000) as download_info:
                        # Clica nativamente pelo Playwright
                        page.mouse.click(k2_coords['x'], k2_coords['y'])
                        time.sleep(1.0)
                        page.screenshot(path=os.path.join(output_dir, f"debug_4_clicked_2k_{idx}.png"))
                        
                    download = download_info.value
                    filename = f"geracao_2k_{idx + 1}_{int(time.time())}.png"
                    file_path = os.path.join(output_dir, filename)
                    download.save_as(file_path)
                    print(f"Sucesso: Imagem 2K salva em {file_path}")
                    
                    # Enviar para o Telegram via bot
                    send_to_telegram(file_path, f"🎨 **Prompt:** {prompt}")
                    sucessos += 1
                except Exception as e:
                    page.screenshot(path=os.path.join(output_dir, f"debug_5_timeout_{idx}.png"))
                    raise Exception(f"Falha ao interceptar download 2K: {e}")
                    
            except Exception as e:
                print(f"Erro durante o processamento do prompt '{prompt}': {e}")
                
                # Salvar log/screenshot do erro
                error_path = os.path.join(output_dir, f"error_{idx}.png")
                page.screenshot(path=error_path)
                print(f"Screenshot de erro salvo em {error_path}")
                send_to_telegram(error_path, f"🚨 **Erro no bot!** {e}\nVeja a última tela:")
                falhas += 1
                
            # Rate Limit entre gerações
            if idx < len(prompts) - 1:
                delay = random.uniform(15, 20)
                print(f"Rate Limit: Aguardando {delay:.2f}s para a próxima geração...")
                time.sleep(delay)

        print("Finalizado o processamento de todos os prompts.")
        if 'status_msg_id' in locals():
            msg_fim = f"✅ *Processo Concluído!*\n\n📊 *Resumo:*\n✔️ Sucessos: {sucessos}\n❌ Falhas: {falhas}\nTotal de prompts recebidos: {len(prompts)}"
            edit_status_message(status_msg_id, msg_fim)
        context.close()

if __name__ == "__main__":
    main()
