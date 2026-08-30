import os
import json
import time
import random
import requests
import re
import base64
from nacl import encoding, public
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def encrypt_secret(public_key: str, secret_value: str) -> str:
    public_key_obj = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key_obj)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")

def update_github_secret(secret_name, secret_value):
    repo = os.environ.get('GITHUB_REPO')
    token = os.environ.get('GITHUB_TOKEN')
    
    if not repo or not token:
        print("GITHUB_REPO ou GITHUB_TOKEN ausentes. Pulando atualização de secret.")
        return False
        
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    url_key = f"https://api.github.com/repos/{repo}/actions/secrets/public-key"
    res_key = requests.get(url_key, headers=headers)
    if res_key.status_code != 200:
        print(f"Erro ao obter chave pública: {res_key.text}")
        return False
        
    key_info = res_key.json()
    key_id = key_info['key_id']
    key_value = key_info['key']
    
    encrypted_value = encrypt_secret(key_value, secret_value)
    
    url_secret = f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}"
    data = {
        "encrypted_value": encrypted_value,
        "key_id": key_id
    }
    res_secret = requests.put(url_secret, headers=headers, json=data)
    if res_secret.status_code in [201, 204]:
        print(f"✅ Secret {secret_name} atualizado com sucesso no GitHub!")
        return True
    else:
        print(f"❌ Erro ao atualizar secret: {res_secret.text}")
        return False

def send_to_telegram(filepath, caption):
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not bot_token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    try:
        with open(filepath, 'rb') as f:
            response = requests.post(url, files={'photo': f}, data={'chat_id': chat_id, 'caption': caption})
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
    except Exception:
        pass

def make_progress_bar(percent, elapsed, estimated_total=120):
    bar_length = 10
    filled_length = int(bar_length * percent // 100)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    tempo_rest = max(0, estimated_total - elapsed)
    return bar, tempo_rest

def main():
    auth_session_str = os.environ.get('AUTH_SESSION_JSON')
    if not auth_session_str:
        msg = (
            "❌ *Sessão não encontrada no GitHub!*\n\n"
            "O secret `AUTH_SESSION_JSON` está vazio.\n"
            "Por favor, rode o script `python extract_cookies.py` no seu PC para enviar os cookies iniciais."
        )
        print("Erro: AUTH_SESSION_JSON ausente.")
        send_status_message(msg)
        return

    try:
        raw_cookies = json.loads(auth_session_str)
        cookies = []
        for c in raw_cookies:
            c = dict(c)
            for k in ['hostOnly', 'session', 'storeId', 'id']:
                c.pop(k, None)
            if 'sameSite' in c and c['sameSite'] not in ['Strict', 'Lax', 'None']:
                del c['sameSite']
            cookies.append(c)
    except json.JSONDecodeError:
        print("Erro: JSON de sessão inválido.")
        return

    output_dir = os.path.join(BASE_DIR, 'output')
    os.makedirs(output_dir, exist_ok=True)

    single_prompt = os.environ.get('SINGLE_PROMPT')
    if single_prompt and single_prompt.strip():
        prompts = [p.strip() for p in single_prompt.split('\n') if p.strip()]
        print(f"🤖 Executando {len(prompts)} prompt(s) do Telegram")
    else:
        prompts_file = os.path.join(BASE_DIR, 'data', 'prompts.txt')
        try:
            with open(prompts_file, 'r', encoding='utf-8') as f:
                prompts = [line.strip() for line in f.readlines() if line.strip()]
        except FileNotFoundError:
            return

    if not prompts:
        return

    status_msg_id = send_status_message(f"⏳ *Iniciando geração de {len(prompts)} imagem(ns)...*")

    with sync_playwright() as p:
        # Usando contexto em memória (não-persistente), injetando cookies manualmente
        # pois o GitHub runner limpa o disco a cada execução
        context = p.chromium.launch_persistent_context(
            user_data_dir="/tmp/playwright_user_data",
            headless=False, # O Xvfb permite rodar "visível" de mentira
            accept_downloads=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled'],
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        
        # Injetar os cookies
        context.add_cookies(cookies)
        
        page = context.pages[0] if context.pages else context.new_page()
        
        print("Navegando para o Google Labs...")
        page.goto('https://labs.google/fx/pt/tools/flow/', wait_until='domcontentloaded', timeout=60000)
        time.sleep(4)
        
        current_url = page.url
        if 'accounts.google.com' in current_url or 'signin' in current_url.lower():
            print(f"⚠️ Sessão expirada/bloqueada! URL: {current_url}")
            send_status_message(
                "⚠️ *Sessão Bloqueada pelo Google!*\n\n"
                "O Google detectou a mudança de IP e invalidou os cookies.\n"
                "Rode o script `python extract_cookies.py` no seu PC para enviar novos cookies para o GitHub.\n"
                "*(Lembre-se: por rodar na nuvem, o Google sempre vai bloquear de tempos em tempos devido à mudança de IP do GitHub Actions)*."
            )
            context.close()
            return
        
        print(f"✅ Autenticado com sucesso! URL: {current_url}")
        
        sucessos = 0
        falhas = 0

        for idx, prompt in enumerate(prompts):
            start_time_prompt = time.time()
            
            def update_status(percent, status_text):
                elapsed = int(time.time() - start_time_prompt)
                bar, tempo_rest = make_progress_bar(percent, elapsed)
                msg = (
                    f"⏳ *Processando imagem {idx + 1} de {len(prompts)}*\n\n"
                    f"`[{bar}] {percent}%`\n"
                    f"💡 _{status_text}_\n\n"
                    f"⏱️ **Rodando há:** {elapsed}s\n"
                    f"⏳ **Falta aprox:** {tempo_rest}s"
                )
                edit_status_message(status_msg_id, msg)

            try:
                update_status(5, "Abrindo laboratório...")
                btn_clicado = False
                try:
                    btn_novo = page.locator("text=/Novo projeto/i").first
                    if btn_novo.is_visible(timeout=8000):
                        btn_novo.click()
                        time.sleep(random.uniform(3.0, 5.0))
                        btn_clicado = True
                except Exception:
                    pass
                
                if not btn_clicado:
                    page.goto('https://labs.google/fx/pt/tools/flow/', wait_until='domcontentloaded', timeout=60000)
                    time.sleep(5)
                    try:
                        btn_novo2 = page.locator("text=/Novo projeto/i").first
                        if btn_novo2.is_visible(timeout=5000):
                            btn_novo2.click()
                            time.sleep(3.0)
                    except Exception:
                        pass
                
                update_status(15, "Aguardando editor...")
                input_locator = page.locator('[data-slate-editor="true"][contenteditable="true"]').first
                input_locator.wait_for(state='visible', timeout=30000)
                
                old_count = page.locator('img[src*="getMediaUrlRedirect"], img[src^="blob:"]').count()
                
                update_status(25, "Digitando prompt...")
                input_locator.click()
                time.sleep(0.5)
                input_locator.press('Control+a')
                input_locator.press('Delete')
                time.sleep(0.3)
                input_locator.type(prompt, delay=80)
                time.sleep(1.5)
                
                input_locator.press('Enter')
                update_status(40, "Gerando imagem...")
                
                page.wait_for_function(f'''() => {{
                    const imgs = Array.from(document.querySelectorAll('img'));
                    const currentCount = imgs.filter(i => 
                        i.src.includes('getMediaUrlRedirect') || i.src.startsWith('blob:')
                    ).length;
                    return currentCount > {old_count};
                }}''', timeout=180000)
                time.sleep(3.0)
                
                update_status(65, "Finalizando geração...")
                
                img_box = None
                for _ in range(30):
                    img_box = page.evaluate('''() => {
                        const imgs = Array.from(document.querySelectorAll('img')).filter(i => 
                            i.src.includes('getMediaUrlRedirect') || i.src.startsWith('blob:')
                        );
                        if (!imgs.length) return null;
                        const rect = imgs[0].getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) return null;
                        return { x: rect.left, y: rect.top, width: rect.width, height: rect.height, cx: rect.left + rect.width / 2, cy: rect.top + rect.height / 2, right: rect.right };
                    }''')
                    if img_box and img_box['width'] > 50:
                        break
                    time.sleep(2)
                
                if not img_box:
                    raise Exception("Imagem não localizada.")
                
                center_x = img_box['cx']
                center_y = img_box['cy']
                
                update_status(75, "Baixando imagem...")
                dots_coords = None
                for _ in range(30):
                    page.mouse.move(center_x - 20, center_y - 20)
                    time.sleep(0.1)
                    page.mouse.move(center_x, center_y)
                    time.sleep(0.2)
                    
                    coords = page.evaluate('''(imgBox) => {
                        const allButtons = Array.from(document.querySelectorAll('button, [role="button"]'));
                        const candidatos = allButtons.filter(btn => {
                            const rect = btn.getBoundingClientRect();
                            if (rect.width === 0 || rect.height === 0) return false;
                            const btnCx = rect.left + rect.width / 2;
                            const btnCy = rect.top + rect.height / 2;
                            return btnCx >= (imgBox.right - 200) && btnCx <= (imgBox.right + 30) && btnCy >= (imgBox.y - 20) && btnCy <= (imgBox.y + 100);
                        });
                        if (!candidatos.length) return null;
                        candidatos.sort((a, b) => b.getBoundingClientRect().left - a.getBoundingClientRect().left);
                        const rect = candidatos[0].getBoundingClientRect();
                        return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
                    }''', img_box)
                    
                    if coords:
                        dots_coords = coords
                        break
                    time.sleep(2.0)
                
                if not dots_coords:
                    raise Exception("Botão de opções não apareceu.")
                
                page.mouse.click(dots_coords['x'], dots_coords['y'])
                time.sleep(1.5)
                
                baixar_item = page.locator('.mat-mdc-menu-item, [role="menuitem"], li, button').filter(has_text=re.compile(r"baixar|download", re.IGNORECASE)).locator("visible=true").last
                baixar_item.wait_for(state='visible', timeout=10000)
                baixar_item.hover()
                time.sleep(2.0)
                
                download_success = False
                for tentativa_dl in range(3):
                    try:
                        is_fallback = (tentativa_dl == 2)
                        qualidade = "1K" if is_fallback else "2K"
                        
                        try:
                            item = page.locator('.mat-mdc-menu-item, [role="menuitem"], li, button').filter(has_text=re.compile(qualidade, re.IGNORECASE)).locator("visible=true").last
                            item.wait_for(state='visible', timeout=5000)
                        except Exception:
                            continue
                            
                        with page.expect_download(timeout=90000) as download_info:
                            item.click(force=True)
                        
                        download = download_info.value
                        file_path = os.path.join(output_dir, f"img_{idx + 1}_{int(time.time())}.png")
                        download.save_as(file_path)
                        
                        send_to_telegram(file_path, f"🎨 *Prompt:* {prompt}\n⚠️ *(Baixado em {qualidade})*")
                        sucessos += 1
                        download_success = True
                        break
                    except Exception as e:
                        if tentativa_dl < 2:
                            page.keyboard.press('Escape')
                            time.sleep(1.0)
                            page.mouse.click(dots_coords['x'], dots_coords['y'])
                            time.sleep(1.5)
                            baixar_item.hover()
                            time.sleep(2.0)
                
                if not download_success:
                    raise Exception("Falha ao baixar imagem.")
                update_status(100, "✅ Imagem enviada!")
                
            except Exception as e:
                print(f"❌ Erro no prompt '{prompt}': {e}")
                try:
                    error_path = os.path.join(output_dir, f"error_{idx}.png")
                    page.screenshot(path=error_path)
                    send_to_telegram(error_path, f"🚨 *Erro!*\n{e}")
                except:
                    pass
                falhas += 1
            
            if idx < len(prompts) - 1:
                time.sleep(random.uniform(15, 25))

        # NOVIDADE: Atualizar cookies após o término!
        print("Atualizando cookies para manter a sessão viva...")
        try:
            current_cookies = context.cookies()
            if current_cookies:
                cookies_json = json.dumps(current_cookies)
                update_github_secret('AUTH_SESSION_JSON', cookies_json)
        except Exception as e:
            print(f"Erro ao salvar novos cookies: {e}")

        msg_fim = (
            f"✅ *Processo Concluído!*\n\n"
            f"📊 *Resumo:*\n"
            f"✔️ Sucessos: {sucessos}\n"
            f"❌ Falhas: {falhas}\n"
            f"📝 Total de prompts: {len(prompts)}\n"
            f"🔄 *Cookies atualizados no GitHub para evitar expiração!*"
        )
        edit_status_message(status_msg_id, msg_fim)
        context.close()

if __name__ == "__main__":
    main()
