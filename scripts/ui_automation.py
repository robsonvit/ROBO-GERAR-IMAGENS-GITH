import os
import json
import time
import random
import requests
import re
import sys
from playwright.sync_api import sync_playwright
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_DIR = os.path.join(BASE_DIR, "sessao_google")

def send_to_telegram(filepath, caption):
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not bot_token or not chat_id:
        print("Aviso: TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não definidos.")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    try:
        with open(filepath, 'rb') as f:
            response = requests.post(url, files={'photo': f}, data={'chat_id': chat_id, 'caption': caption, 'parse_mode': 'Markdown'}, timeout=60)
            if response.status_code == 200:
                print("✅ Foto enviada com sucesso ao Telegram!")
            else:
                # Fallback sem parse_mode se falhar formatação
                f.seek(0)
                r2 = requests.post(url, files={'photo': f}, data={'chat_id': chat_id, 'caption': caption}, timeout=60)
                if r2.status_code == 200:
                    print("✅ Foto enviada com sucesso ao Telegram (modo texto simples)!")
                else:
                    print(f"Aviso ao enviar ao Telegram: {r2.text}")
    except Exception as e:
        print(f"Erro ao enviar para o Telegram: {e}")

def send_status_message(text):
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not bot_token or not chat_id:
        return None
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        response = requests.post(url, data={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}, timeout=10)
        if response.status_code == 200:
            return response.json().get('result', {}).get('message_id')
        else:
            r2 = requests.post(url, data={'chat_id': chat_id, 'text': text}, timeout=10)
            if r2.status_code == 200:
                return r2.json().get('result', {}).get('message_id')
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
        r = requests.post(url, data={'chat_id': chat_id, 'message_id': message_id, 'text': text, 'parse_mode': 'Markdown'}, timeout=10)
        if r.status_code != 200:
            # Fallback sem parse_mode se markdown falhar
            requests.post(url, data={'chat_id': chat_id, 'message_id': message_id, 'text': text}, timeout=10)
    except Exception as e:
        print(f"Erro ao editar mensagem de status: {e}")

def update_github_secret_cookies(new_cookies):
    gh_token = os.environ.get('GH_PAT_TOKEN')
    repo = os.environ.get('GITHUB_REPO')
    if not gh_token or not repo:
        return
    try:
        import subprocess
        compact_json = json.dumps(new_cookies)
        cmd = ["gh", "secret", "set", "AUTH_SESSION_JSON", "--repo", repo]
        env = os.environ.copy()
        env["GH_TOKEN"] = gh_token
        res = subprocess.run(cmd, input=compact_json, text=True, env=env, check=True, capture_output=True)
        print("🔄 Cookies renovados e salvos com sucesso no GitHub Secrets!")
    except Exception as e:
        print(f"Aviso ao renovar segredo no GitHub: {e}")

def make_progress_bar(percent, elapsed, estimated_total=120):
    bar_length = 10
    filled_length = int(bar_length * percent // 100)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    tempo_rest = max(0, estimated_total - elapsed)
    return bar, tempo_rest

def main():
    state_file = os.path.join(BASE_DIR, "state.json")
    use_state = os.path.exists(state_file)

    if not os.path.exists(SESSION_DIR) and not use_state:
        msg = (
            "❌ *Sessão não encontrada!*\n\n"
            "Nem a pasta `sessao_google` nem o arquivo `state.json` existem.\n"
            "Configure a sessão do Google com o `login_setup.py`."
        )
        print("Erro: Sessão do Google ausente.")
        send_status_message(msg)
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
            prompts = ["Uma linda paisagem futurista com luzes neon"]

    if not prompts:
        print("Nenhum prompt fornecido.")
        return

    # Mensagem de status inicial (reaproveita MESSAGE_ID do webhook se disponível)
    incoming_msg_id = os.environ.get('MESSAGE_ID')
    status_msg_id = None
    if incoming_msg_id:
        try:
            status_msg_id = int(incoming_msg_id)
        except ValueError:
            pass

    if not status_msg_id:
        status_msg_id = send_status_message(f"⏳ *Iniciando geração no Google Flow ({len(prompts)} imagem(ns))...*")

    with sync_playwright() as p:
        # Detecta se está em Linux com Xvfb ou local
        is_linux = sys.platform.startswith('linux')
        has_display = bool(os.environ.get('DISPLAY'))
        is_headless = False if (is_linux and has_display) else (not os.path.exists(SESSION_DIR) and not has_display)

        browser_args = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled'
        ]

        if use_state:
            print("🚀 Iniciando na nuvem com state.json (Cookies)...")
            browser = p.chromium.launch(
                headless=is_headless,
                args=browser_args
            )
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
            except Exception as e:
                raw_data = None
                print(f"Erro ao ler state.json: {e}")

            if isinstance(raw_data, list):
                print(f"Detectado formato Cookie-Editor com {len(raw_data)} cookies.")
                context = browser.new_context(
                    accept_downloads=True,
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080}
                )
                cleaned_cookies = []
                for c in raw_data:
                    c_clean = dict(c)
                    for k in ['hostOnly', 'session', 'storeId', 'id']:
                        c_clean.pop(k, None)
                    if 'sameSite' in c_clean and c_clean['sameSite'] not in ['Strict', 'Lax', 'None']:
                        c_clean.pop('sameSite', None)
                    cleaned_cookies.append(c_clean)
                context.add_cookies(cleaned_cookies)
            else:
                context = browser.new_context(
                    storage_state=state_file,
                    accept_downloads=True,
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080}
                )
        else:
            print("💻 Iniciando localmente no PC com pasta de sessão...")
            context = p.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR,
                headless=False,
                accept_downloads=True,
                args=browser_args,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
        
        page = context.pages[0] if context.pages else context.new_page()

        print("Navegando para o Google Flow (https://flow.google.com/)...")
        page.goto('https://flow.google.com/', wait_until='domcontentloaded', timeout=60000)
        time.sleep(4)

        current_url = page.url
        if 'accounts.google.com' in current_url or 'signin' in current_url.lower():
            print(f"⚠️ Sessão expirada/bloqueada! URL: {current_url}")
            send_status_message(
                "⚠️ *Sessão Expirada ou Bloqueada!*\n\n"
                "Os cookies do Google Flow expiraram ou caíram no login.\n"
                "Execute `python login_setup.py` no PC para atualizar o GitHub Secrets."
            )
            context.close()
            return

        print(f"✅ Autenticado com sucesso! URL atual: {current_url}")

        sucessos = 0
        falhas = 0

        for idx, prompt in enumerate(prompts):
            start_time_prompt = time.time()

            def update_status(percent, status_text):
                elapsed = int(time.time() - start_time_prompt)
                bar, tempo_rest = make_progress_bar(percent, elapsed)
                msg = (
                    f"🎨 *Google Flow — Imagem {idx + 1} de {len(prompts)}*\n\n"
                    f"`[{bar}] {percent}%`\n"
                    f"💡 _{status_text}_\n\n"
                    f"⏱️ **Tempo decorrido:** {elapsed}s\n"
                    f"⏳ **Estimativa restante:** {tempo_rest}s"
                )
                edit_status_message(status_msg_id, msg)

            try:
                update_status(5, "Acessando estúdio do Flow...")

                # 1. Verificar se o editor já está visível ou se precisa abrir/criar projeto
                editor_locator = page.locator('div[contenteditable="true"].ProseMirror').first
                if not editor_locator.is_visible():
                    print("Editor não está visível. Abrindo/criando projeto...")
                    # Se estiver na página de apresentação (/about), clica em "Create with Google Flow"
                    create_btn = page.get_by_text(re.compile(r"Create with Google Flow|Criar com o Google Flow", re.I)).first
                    try:
                        if create_btn.is_visible(timeout=3000):
                            print("Clicando no botão 'Create with Google Flow' na página de boas-vindas...")
                            create_btn.click()
                            time.sleep(5)
                            if 'accounts.google.com' in page.url or 'signin' in page.url.lower():
                                send_status_message(
                                    "⚠️ *Sessão Expirada!*\n\n"
                                    "A sessão do Google Flow expirou e caiu no login.\n"
                                    "Por favor, atualize os cookies via Cookie-Editor ou rode `python import_cookies.py`."
                                )
                                context.close()
                                return
                    except Exception as e:
                        print(f"Aviso ao tentar botão de boas-vindas: {e}")

                    btn_novo = page.locator("button.new-project-button").or_(
                        page.get_by_role("button", name=re.compile(r"Novo projeto|New project", re.I))
                    ).first
                    card = page.locator('a.project-thumbnail-container, a[href*="/project/"]').first
                    if btn_novo.is_visible(timeout=6000):
                        print("Clicando em Novo Projeto (+)...")
                        btn_novo.click()
                        time.sleep(4)
                    elif card.is_visible(timeout=6000):
                        print("Abrindo primeiro projeto existente...")
                        card.click()
                        time.sleep(4)
                    else:
                        print("Aviso: Nem botão novo nem cards de projeto visíveis diretamente. Aguardando editor...")

                try:
                    editor_locator.wait_for(state='visible', timeout=25000)
                    print("✅ Editor ProseMirror visível com sucesso!")
                except Exception as e:
                    print(f"Aviso ao aguardar editor: {e}")

                # 2. Fechar eventuais popups / avisos
                for _ in range(3):
                    try:
                        btn_close = page.locator('button[aria-label="Close"], button[aria-label="Dismiss"], button:has-text("Dismiss"), button:has-text("Entendi")').first
                        if btn_close.is_visible(timeout=1500):
                            btn_close.click()
                            time.sleep(0.5)
                    except Exception:
                        break

                # 3. Desativar modo "Agente" se estiver ligado (garante modo de geração de imagem)
                try:
                    agent_btn = page.locator('button[aria-pressed="true"]').filter(has_text=re.compile(r"agent|agente", re.IGNORECASE)).first
                    if agent_btn.is_visible(timeout=2000):
                        print("Modo Agente ativado detectado. Desativando...")
                        agent_btn.click()
                        time.sleep(1.0)
                except Exception:
                    pass

                # Mapear imagens existentes antes do envio
                old_srcs = set(page.evaluate('''() => {
                    return Array.from(document.querySelectorAll('img'))
                        .filter(i => {
                            const r = i.getBoundingClientRect();
                            return r.width >= 50 && r.height >= 50 && i.src && i.src.startsWith('http');
                        })
                        .map(i => i.src);
                }'''))
                print(f"Imagens existentes antes do prompt: {len(old_srcs)}")

                update_status(25, "Digitando prompt...")
                editor_locator.click()
                time.sleep(0.3)
                page.keyboard.press("Control+a")
                time.sleep(0.1)
                page.keyboard.press("Backspace")
                time.sleep(0.2)

                # Digita o prompt suavemente
                editor_locator.press_sequentially(prompt, delay=35)
                time.sleep(1.0)

                update_status(35, "Enviando solicitação...")
                page.keyboard.press("Enter")
                print("✅ Prompt enviado via tecla Enter!")

                # Fechar eventual toast de validação
                time.sleep(1.0)
                try:
                    toast_dismiss = page.locator('button:has-text("Dismiss"), button[aria-label="Dismiss"]').first
                    if toast_dismiss.is_visible(timeout=1500):
                        toast_dismiss.click()
                except Exception:
                    pass

                update_status(45, "Aguardando geração da imagem no Flow...")

                # 4. Aguardar nova imagem ser renderizada no grid
                new_img_src = None
                start_wait = time.time()
                max_wait_seconds = 180

                while time.time() - start_wait < max_wait_seconds:
                    elapsed = int(time.time() - start_time_prompt)
                    pct = min(75, 45 + int((time.time() - start_wait) / max_wait_seconds * 30))
                    update_status(pct, f"Processando no Flow ({int(time.time() - start_wait)}s)...")

                    # Verificar se apareceu mensagem de erro
                    has_failed = page.evaluate('''() => {
                        const texts = Array.from(document.querySelectorAll('div, span, p'))
                            .map(el => (el.textContent || '').trim());
                        return texts.some(t => t.includes('Não foi possível gerar') || t.includes('Could not generate'));
                    }''')
                    if has_failed:
                        raise Exception("Google Flow indicou falha na geração.")

                    # Verificar novas imagens no DOM com URL http e tamanho >= 80
                    found_src = page.evaluate('''(oldList) => {
                        const oldSet = new Set(oldList);
                        const imgs = Array.from(document.querySelectorAll('img')).filter(i => {
                            const r = i.getBoundingClientRect();
                            return r.width >= 80 && r.height >= 80 && i.src && (i.src.includes('/asb/') || i.src.startsWith('http'));
                        });
                        for (const img of imgs) {
                            if (!oldSet.has(img.src)) {
                                return img.src;
                            }
                        }
                        return null;
                    }''', list(old_srcs))

                    if found_src:
                        new_img_src = found_src
                        print(f"✅ Imagem gerada encontrada: {new_img_src[:65]}...")
                        break

                    time.sleep(3.0)

                if not new_img_src:
                    raise Exception("Timeout 180s: A nova imagem não foi detectada no Flow.")

                time.sleep(3.0)
                update_status(75, "Localizando imagem e preparando download 2K...")

                # 5. Localizar elemento da imagem gerada e ativar a hotbar via hover
                target_img = page.locator(f'img[src="{new_img_src}"]').first
                if not target_img.is_visible():
                    target_img = page.locator('img[src*="/asb/"]').last

                print("Fazendo hover sobre a imagem gerada para ativar o menu...")
                target_img.hover()
                time.sleep(1.0)

                # 6. Localizar o botão de 3 pontos do card da imagem (tem atributo flowhotbarbutton e fica no card com y > 50)
                dots_btn = page.locator('button[flowhotbarbutton][aria-label*="opções" i], button[flowhotbarbutton]:has-text("more_vert")').first
                if not dots_btn.is_visible():
                    all_dots = page.locator('button:has-text("more_vert"), button[aria-label*="opções" i]')
                    for d_idx in range(all_dots.count()):
                        cand = all_dots.nth(d_idx)
                        b_box = cand.bounding_box()
                        if b_box and b_box['y'] > 50:
                            dots_btn = cand
                            break

                print("Clicando no botão ⋮ do card da imagem...")
                dots_btn.click(force=True)
                time.sleep(1.5)

                # 7. Localizar opção "Fazer o download" no menu de contexto
                update_status(85, "Abrindo menu de download...")
                baixar_menu = page.locator(
                    'button[role="menuitem"]:has-text("download"), '
                    'button[role="menuitem"]:has-text("Download"), '
                    'button[role="menuitem"]:has-text("Fazer o download"), '
                    '[role="menuitem"]:has-text("download")'
                ).first

                if not baixar_menu.is_visible(timeout=5000):
                    raise Exception("Item de menu 'Fazer o download' não encontrado.")

                print("Hover sobre 'Fazer o download' para abrir submenu de resolução...")
                baixar_menu.hover()
                time.sleep(1.5)

                # 8. Localizar a opção "2K" no submenu
                opt_2k = page.locator('button:has-text("2K"), [role="menuitem"]:has-text("2K")').first
                qualidade_str = "2K"
                target_download = opt_2k if opt_2k.is_visible(timeout=3000) else baixar_menu
                if not opt_2k.is_visible():
                    qualidade_str = "1K"
                    print("Aviso: Opção 2K não visível no submenu, baixando em 1K...")

                update_status(90, f"Baixando imagem em {qualidade_str}...")
                print(f"Iniciando download nativo ({qualidade_str})...")

                # 9. Interceptar e salvar o download nativo do Playwright
                with page.expect_download(timeout=120000) as download_info:
                    target_download.click()
                    time.sleep(1.0)

                download = download_info.value
                file_path = os.path.join(output_dir, f"flow_{idx + 1}_{int(time.time())}.png")
                download.save_as(file_path)
                print(f"✅ Arquivo salvo: {file_path}")

                send_to_telegram(file_path, f"🎨 *Prompt:* {prompt}\n✨ *Google Flow ({qualidade_str})*")
                update_status(100, f"✅ Imagem {qualidade_str} enviada!")
                sucessos += 1

            except Exception as e:
                print(f"❌ Erro no prompt '{prompt}': {e}")
                try:
                    error_path = os.path.join(output_dir, f"error_{idx}.png")
                    page.screenshot(path=error_path)
                    send_to_telegram(error_path, f"🚨 *Erro no Flow!*\n`{e}`")
                except Exception:
                    pass
                falhas += 1

            if idx < len(prompts) - 1:
                time.sleep(random.uniform(10, 15))

        msg_fim = (
            f"✅ *Processo Concluído no Google Flow!*\n\n"
            f"📊 *Resumo:*\n"
            f"✔️ Sucessos: {sucessos}\n"
            f"❌ Falhas: {falhas}\n"
            f"📝 Total de prompts: {len(prompts)}\n"
            f"☁️ *Executado 100% na nuvem sem o PC ligado!*"
        )
        edit_status_message(status_msg_id, msg_fim)
        if use_state and sucessos > 0:
            try:
                new_cookies = context.cookies()
                if new_cookies:
                    print(f"🔄 Salvando {len(new_cookies)} cookies renovados da sessão...")
                    update_github_secret_cookies(new_cookies)
            except Exception as e:
                print(f"Aviso ao renovar cookies: {e}")

        context.close()
        if use_state:
            browser.close()

        if sucessos == 0 and len(prompts) > 0:
            print("❌ Nenhuma imagem foi gerada com sucesso.")
            sys.exit(1)

if __name__ == "__main__":
    main()
