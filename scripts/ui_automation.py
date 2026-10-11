import os
import json
import time
import random
import requests
import re
import sys
from playwright.sync_api import sync_playwright

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
            response = requests.post(url, files={'photo': f}, data={'chat_id': chat_id, 'caption': caption, 'parse_mode': 'Markdown'})
            if response.status_code == 200:
                print("✅ Foto enviada com sucesso ao Telegram!")
            else:
                print(f"Aviso ao enviar ao Telegram: {response.text}")
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

                # 1. Verificar se já está dentro de um projeto (/project/) ou na home do Flow
                if '/project/' not in page.url:
                    print("Na página inicial do Flow. Abrindo/criando projeto...")
                    project_opened = False
                    
                    # Procura botão '+ Novo projeto' ou 'Start Creating'
                    try:
                        btn_novo = page.locator("text=/Novo projeto/i, text=/New project/i, text=/Start Creating/i").first
                        if btn_novo.is_visible(timeout=8000):
                            btn_novo.click()
                            time.sleep(4)
                            project_opened = True
                    except Exception as e:
                        print(f"Tentativa 1 de abrir projeto: {e}")

                    # Se não abriu, tenta clicar no primeiro card de projeto existente
                    if not project_opened and '/project/' not in page.url:
                        try:
                            card = page.locator('a[href*="/project/"]').first
                            if card.is_visible(timeout=5000):
                                card.click()
                                time.sleep(4)
                                project_opened = True
                        except Exception as e:
                            print(f"Tentativa 2 de abrir projeto: {e}")

                    try:
                        page.wait_for_url("**/project/**", timeout=25000)
                        print(f"✅ Projeto aberto: {page.url}")
                    except Exception:
                        print(f"Aviso: URL não mudou para /project/: {page.url}")

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

                update_status(15, "Localizando editor de prompt...")

                # 4. Localizar o campo de prompt
                editor_selectors = [
                    'div[contenteditable="true"].ProseMirror',
                    'div[role="textbox"][data-slate-editor="true"][contenteditable="true"]',
                    'div[contenteditable="true"][data-slate-editor="true"]',
                    'div[contenteditable="true"][aria-multiline="true"][role="textbox"]',
                    '[data-slate-editor="true"][contenteditable="true"]',
                    'div[role="textbox"][contenteditable="true"]',
                    'div[contenteditable="true"]'
                ]

                input_locator = None
                for sel in editor_selectors:
                    loc = page.locator(sel).last
                    try:
                        if loc.is_visible(timeout=3000):
                            input_locator = loc
                            break
                    except Exception:
                        continue

                if not input_locator:
                    raise Exception("Editor de prompt do Google Flow não encontrado.")

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
                input_locator.click()
                time.sleep(0.3)
                page.keyboard.press("Control+a")
                time.sleep(0.1)
                page.keyboard.press("Backspace")
                time.sleep(0.2)

                # Digita o prompt suavemente
                input_locator.press_sequentially(prompt, delay=35)
                time.sleep(1.2)

                update_status(35, "Enviando solicitação...")

                # 5. Localizar botão de envio (ícone de seta ou Create)
                submitted = False
                try:
                    submit_btn = page.locator(
                        'button:has(i:text-is("arrow_forward")), '
                        'button:has(mat-icon:text-is("arrow_forward")), '
                        'button:has(span:has-text("arrow_forward")), '
                        'button[aria-label="Create"], '
                        'button[aria-label*="Create" i], '
                        'button[aria-label*="Criar" i], '
                        'button[type="submit"]'
                    ).first

                    if submit_btn.is_visible(timeout=3000):
                        for _ in range(15):
                            disabled = submit_btn.get_attribute("disabled") is not None or submit_btn.get_attribute("aria-disabled") == "true"
                            if not disabled:
                                break
                            time.sleep(0.2)
                        submit_btn.click()
                        submitted = True
                        print("✅ Botão de envio clicado!")
                except Exception as e:
                    print(f"Tentativa no botão de envio: {e}")

                if not submitted:
                    input_locator.press('Enter')
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

                # 6. Aguardar nova imagem ser renderizada no grid
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

                    # Verificar novas imagens no DOM
                    found_src = page.evaluate('''(oldList) => {
                        const oldSet = new Set(oldList);
                        const imgs = Array.from(document.querySelectorAll('img')).filter(i => {
                            const r = i.getBoundingClientRect();
                            return r.width >= 80 && r.height >= 80 && i.src && i.src.startsWith('http');
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

                time.sleep(2.0)
                update_status(75, "Localizando imagem e preparando download 2K...")

                # 7. Obter coordenadas da imagem para o hover
                img_box = None
                for _ in range(20):
                    img_box = page.evaluate('''(targetSrc) => {
                        const img = Array.from(document.querySelectorAll('img')).find(i => i.src === targetSrc);
                        if (!img) return null;
                        const r = img.getBoundingClientRect();
                        if (r.width < 50 || r.height < 50) return null;
                        return {
                            left: r.left,
                            top: r.top,
                            right: r.right,
                            bottom: r.bottom,
                            width: r.width,
                            height: r.height,
                            cx: r.left + r.width / 2,
                            cy: r.top + r.height / 2
                        };
                    }''', new_img_src)
                    if img_box:
                        break
                    time.sleep(1.0)

                if not img_box:
                    raise Exception("Não foi possível obter coordenadas da imagem gerada.")

                # 8. Wiggle do mouse para revelar botão de 3 pontos (⋮) no canto superior direito
                dots_coords = None
                print("Balançando mouse sobre a imagem para revelar o botão ⋮...")
                for w_attempt in range(25):
                    # Movimenta suavemente pelo centro e canto superior direito
                    page.mouse.move(img_box['cx'] + (w_attempt % 2 * 20 - 10), img_box['cy'] + (w_attempt % 2 * 20 - 10))
                    time.sleep(0.2)
                    page.mouse.move(img_box['right'] - 30, img_box['top'] + 25)
                    time.sleep(0.3)

                    dots_coords = page.evaluate('''(b) => {
                        const btns = Array.from(document.querySelectorAll('button')).filter(btn => {
                            const s = window.getComputedStyle(btn);
                            if (s.display === 'none' || s.visibility === 'hidden') return false;
                            const r = btn.getBoundingClientRect();
                            if (r.width === 0 || r.height === 0) return false;
                            const cx = r.left + r.width / 2;
                            const cy = r.top + r.height / 2;
                            return cx >= b.right - 160 && cx <= b.right + 25 && cy >= b.top - 20 && cy <= b.top + 70;
                        });
                        if (!btns.length) return null;
                        btns.sort((a, b2) => b2.getBoundingClientRect().left - a.getBoundingClientRect().left);
                        const rc = btns[0].getBoundingClientRect();
                        return { x: rc.left + rc.width / 2, y: rc.top + rc.height / 2 };
                    }''', img_box)

                    if dots_coords:
                        print(f"✅ Botão ⋮ encontrado na tentativa {w_attempt + 1}!")
                        break
                    time.sleep(1.0)

                if not dots_coords:
                    raise Exception("Botão de 3 pontos (⋮) não apareceu sobre a imagem.")

                # Clica no botão ⋮
                page.mouse.click(dots_coords['x'], dots_coords['y'])
                time.sleep(1.5)

                # 9. Localizar opção "Baixar" no menu de contexto
                update_status(85, "Abrindo menu de download...")
                baixar_coords = None
                for _ in range(15):
                    baixar_coords = page.evaluate('''() => {
                        const items = Array.from(document.querySelectorAll('li, [role="menuitem"], [role="option"], .mat-mdc-menu-item')).filter(el => {
                            const t = (el.textContent || '').trim().toLowerCase();
                            return t.includes('baixar') || t.includes('download');
                        });
                        if (!items.length) return null;
                        const r = items[items.length - 1].getBoundingClientRect();
                        return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
                    }''')
                    if baixar_coords:
                        break
                    time.sleep(0.3)

                if not baixar_coords:
                    raise Exception("Opção 'Baixar' não encontrada no menu.")

                # Passa o mouse sobre "Baixar" para abrir o submenu de resolução (2K/1K)
                page.mouse.move(baixar_coords['x'], baixar_coords['y'])
                time.sleep(1.5)

                # 10. Localizar a opção "2K" no submenu
                btn2k_coords = None
                for _ in range(15):
                    btn2k_coords = page.evaluate('''() => {
                        const items = Array.from(document.querySelectorAll('li, [role="menuitem"], [role="option"], .mat-mdc-menu-item')).filter(el => {
                            const t = (el.textContent || '').trim().toLowerCase();
                            return t.includes('2k');
                        });
                        if (!items.length) return null;
                        const r = items[0].getBoundingClientRect();
                        return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
                    }''')
                    if btn2k_coords:
                        break
                    time.sleep(0.3)

                target_download = btn2k_coords if btn2k_coords else baixar_coords
                qualidade_str = "2K" if btn2k_coords else "1K"

                update_status(90, f"Baixando imagem em {qualidade_str}...")
                print(f"Iniciando download ({qualidade_str})...")

                # 11. Interceptar e salvar o download nativo do Playwright
                with page.expect_download(timeout=120000) as download_info:
                    page.mouse.click(target_download['x'], target_download['y'])
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
        context.close()
        if use_state:
            browser.close()

if __name__ == "__main__":
    main()
