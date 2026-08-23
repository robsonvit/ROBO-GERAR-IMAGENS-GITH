import os
import json
import time
import random
import requests
from playwright.sync_api import sync_playwright

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

def make_progress_bar(percent, elapsed, estimated_total=120):
    bar_length = 10
    filled_length = int(bar_length * percent // 100)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    tempo_rest = max(0, estimated_total - elapsed)
    return bar, tempo_rest

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
            c = dict(c)  # copia para não mutar o original
            # Remover chaves que o Playwright não aceita
            for k in ['hostOnly', 'session', 'storeId', 'id']:
                c.pop(k, None)
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
        # Ler prompts do arquivo
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
        
        # launch_persistent_context é mais robusto para manter sessão do Google
        context = p.chromium.launch_persistent_context(
            user_data_dir="/tmp/playwright_user_data",
            headless=False,
            accept_downloads=True,
            args=['--no-sandbox', '--disable-dev-shm-usage'],
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        # Injetar cookies de autenticação do Google
        print("Injetando cookies de autenticação do Google...")
        context.add_cookies(cookies)
        
        # Navegar para o site e verificar autenticação
        print("Verificando autenticação...")
        page.goto('https://labs.google/fx/pt/tools/flow/', wait_until='domcontentloaded', timeout=60000)
        time.sleep(4)
        
        # Verificar se foi redirecionado para login
        current_url = page.url
        if 'accounts.google.com' in current_url or 'signin' in current_url.lower():
            print(f"⚠️ AVISO: Redirecionado para login! URL atual: {current_url}")
            print("Os cookies podem ter expirado. Tentando continuar mesmo assim...")
            send_status_message("⚠️ *Aviso:* Cookies de autenticação expirados! Renove o AUTH_SESSION_JSON.")
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

            print(f"\n{'='*60}")
            print(f"--- Processando prompt {idx + 1}/{len(prompts)} ---")
            print(f"Texto: '{prompt}'")
            print(f"{'='*60}")
            
            try:
                update_status(5, "Abrindo laboratório de imagens...")
                
                # ESTRATÉGIA: Usar botão 'Novo Projeto' para limpar a tela
                # SEM navegar com goto() a cada prompt — isso causa logout!
                print("Procurando botão '+ Novo projeto' para limpar a tela...")
                btn_clicado = False
                try:
                    btn_novo = page.locator("text=/Novo projeto/i").first
                    if btn_novo.is_visible(timeout=8000):
                        btn_novo.click()
                        print("✅ Botão '+ Novo projeto' clicado!")
                        time.sleep(random.uniform(3.0, 5.0))
                        btn_clicado = True
                except Exception:
                    pass
                
                # Se não encontrou o botão, tenta recarregar a página
                if not btn_clicado:
                    print("Botão não encontrado, recarregando página...")
                    page.goto('https://labs.google/fx/pt/tools/flow/', wait_until='domcontentloaded', timeout=60000)
                    time.sleep(random.uniform(4, 6))
                    # Verificar autenticação após reload
                    if 'accounts.google.com' in page.url or 'signin' in page.url.lower():
                        raise Exception(f"Redirecionado para login após reload! URL: {page.url}")
                    # Tentar botão de novo
                    try:
                        btn_novo2 = page.locator("text=/Novo projeto/i").first
                        if btn_novo2.is_visible(timeout=5000):
                            btn_novo2.click()
                            print("✅ Botão '+ Novo projeto' clicado após reload!")
                            time.sleep(random.uniform(3.0, 5.0))
                    except Exception:
                        print("Continuando sem clicar no botão...")
                
                # Salva screenshot para debug
                page.screenshot(path=os.path.join(output_dir, f"debug_0_inicial_{idx}.png"))
                
                update_status(15, "Aguardando campo de prompt...")
                
                # Localiza o editor do Google Labs
                print("Aguardando editor de prompt...")
                input_locator = page.locator('[data-slate-editor="true"][contenteditable="true"]').first
                input_locator.wait_for(state='visible', timeout=30000)
                
                # Contar imagens ANTES de digitar o prompt (para detectar quando nova imagem aparecer)
                old_count = page.locator('img[src*="getMediaUrlRedirect"], img[src^="blob:"]').count()
                print(f"Imagens existentes ANTES do prompt: {old_count}")
                
                update_status(25, "Digitando prompt...")
                
                # Clicar no editor e digitar o prompt
                input_locator.click()
                time.sleep(0.5)
                
                # Limpar o campo antes de digitar (caso tenha algo)
                input_locator.press('Control+a')
                input_locator.press('Delete')
                time.sleep(0.3)
                
                # Digitar o prompt letra a letra com delay natural
                input_locator.type(prompt, delay=80)
                time.sleep(random.uniform(1.0, 2.0))
                
                page.screenshot(path=os.path.join(output_dir, f"debug_1_antes_envio_{idx}.png"))
                
                # Enviar o prompt
                input_locator.press('Enter')
                print(f"✅ Prompt enviado! Aguardando geração da imagem... (imagens antes: {old_count})")
                
                update_status(40, "Google trabalhando (Gerando imagem)...")
                
                # Aguarda até que o número de imagens aumente (nova imagem gerada)
                # Timeout de 3 minutos para a IA gerar
                print("Aguardando nova imagem aparecer na tela...")
                page.wait_for_function(f'''() => {{
                    const imgs = Array.from(document.querySelectorAll('img'));
                    const currentCount = imgs.filter(i => 
                        i.src.includes('getMediaUrlRedirect') || i.src.startsWith('blob:')
                    ).length;
                    return currentCount > {old_count};
                }}''', timeout=180000)
                
                print("✅ Nova imagem detectada!")
                time.sleep(3.0)  # Aguarda renderização completa
                
                update_status(65, "Imagem gerada! Aguardando finalização...")
                
                page.screenshot(path=os.path.join(output_dir, f"debug_2_imagem_detectada_{idx}.png"))
                
                # ─── FASE DE HOVER E BOTÃO DE 3 PONTOS ─────────────────────────────────
                # Encontrar a primeira imagem gerada e fazer hover real sobre ela
                print("Localizando a imagem para fazer hover...")
                
                # Script JS para encontrar a primeira imagem e suas coordenadas
                img_box = None
                for tentativa_hover in range(30):  # Até 60s de tentativas
                    img_box = page.evaluate('''() => {
                        const imgs = Array.from(document.querySelectorAll('img')).filter(i => 
                            i.src.includes('getMediaUrlRedirect') || i.src.startsWith('blob:')
                        );
                        if (!imgs.length) return null;
                        const rect = imgs[0].getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) return null;
                        return {
                            x: rect.left,
                            y: rect.top,
                            width: rect.width,
                            height: rect.height,
                            cx: rect.left + rect.width / 2,
                            cy: rect.top + rect.height / 2,
                            right: rect.right
                        };
                    }''')
                    if img_box and img_box['width'] > 50:
                        break
                    time.sleep(2)
                
                if not img_box:
                    raise Exception("Não foi possível localizar a imagem gerada na tela.")
                
                print(f"Imagem localizada em: x={img_box['x']:.0f}, y={img_box['y']:.0f}, w={img_box['width']:.0f}, h={img_box['height']:.0f}")
                
                # Hover na imagem com movimentos naturais para acionar os botões flutuantes
                center_x = img_box['cx']
                center_y = img_box['cy']
                
                update_status(75, "Ativando menu de download...")
                
                dots_coords = None
                for tentativa_dots in range(45):  # Até 90s de tentativas
                    # Movimento de hover suave sobre a imagem
                    page.mouse.move(center_x - 20, center_y - 20)
                    time.sleep(0.1)
                    page.mouse.move(center_x, center_y)
                    time.sleep(0.2)
                    page.mouse.move(center_x + 10, center_y - 10)
                    time.sleep(0.2)
                    
                    # Verificar se o botão de 3 pontos apareceu
                    # O botão de 3 pontos fica no canto superior direito da imagem
                    coords = page.evaluate('''(imgBox) => {
                        // Procura qualquer botão que tenha aria-label com "mais" ou "opções" ou "menu"
                        // ou que esteja posicionado no canto da imagem
                        const allButtons = Array.from(document.querySelectorAll('button, [role="button"]'));
                        
                        // Filtrar botões visíveis que estão próximos do canto superior direito da imagem
                        const candidatos = allButtons.filter(btn => {
                            const rect = btn.getBoundingClientRect();
                            if (rect.width === 0 || rect.height === 0) return false;
                            
                            const btnCx = rect.left + rect.width / 2;
                            const btnCy = rect.top + rect.height / 2;
                            
                            // Botão deve estar próximo do canto superior direito da imagem
                            const dentroX = btnCx >= (imgBox.right - 200) && btnCx <= (imgBox.right + 30);
                            const dentroY = btnCy >= (imgBox.y - 20) && btnCy <= (imgBox.y + 100);
                            
                            return dentroX && dentroY;
                        });
                        
                        if (!candidatos.length) return null;
                        
                        // Pegar o botão mais à direita (provavelmente o de 3 pontos)
                        candidatos.sort((a, b) => b.getBoundingClientRect().left - a.getBoundingClientRect().left);
                        const btn = candidatos[0];
                        const rect = btn.getBoundingClientRect();
                        return {
                            x: rect.left + rect.width / 2,
                            y: rect.top + rect.height / 2
                        };
                    }''', img_box)
                    
                    if coords:
                        dots_coords = coords
                        print(f"✅ Botão de 3 pontos encontrado em tentativa {tentativa_dots + 1}!")
                        break
                    
                    if tentativa_dots % 5 == 4:
                        print(f"Tentativa {tentativa_dots + 1}/45 - Botão ainda não visível, continuando hover...")
                    
                    time.sleep(2.0)
                
                if not dots_coords:
                    page.screenshot(path=os.path.join(output_dir, f"debug_sem_botao_{idx}.png"))
                    raise Exception("Timeout 90s: Botão de opções (3 pontos) não apareceu após hover contínuo.")
                
                page.screenshot(path=os.path.join(output_dir, f"debug_3_hover_ok_{idx}.png"))
                
                # Clicar no botão de 3 pontos
                print("Clicando no botão de 3 pontos (opções)...")
                page.mouse.click(dots_coords['x'], dots_coords['y'])
                time.sleep(1.5)
                
                page.screenshot(path=os.path.join(output_dir, f"debug_4_menu_aberto_{idx}.png"))
                
                # ─── ENCONTRAR E CLICAR EM "BAIXAR" ─────────────────────────────────────
                print("Procurando item 'Baixar' no menu...")
                
                # ─── ENCONTRAR E CLICAR EM "BAIXAR" ─────────────────────────────────────
                print("Procurando item 'Baixar' no menu...")
                
                try:
                    import re
                    baixar_item = page.locator('.mat-mdc-menu-item, [role="menuitem"], li, button').filter(has_text=re.compile(r"baixar|download", re.IGNORECASE)).locator("visible=true").last
                    baixar_item.wait_for(state='visible', timeout=10000)
                    baixar_item.hover()
                    time.sleep(2.5)  # Aguarda submenu aparecer
                except Exception as e:
                    page.screenshot(path=os.path.join(output_dir, f"debug_sem_baixar_{idx}.png"))
                    raise Exception(f"Item de menu 'Baixar' não encontrado no menu de opções: {e}")
                
                page.screenshot(path=os.path.join(output_dir, f"debug_5_submenu_{idx}.png"))
                
                # ─── ENCONTRAR OPÇÃO "2K" ──────────────────────────────────────────
                print("Procurando opção '2K' no submenu...")
                try:
                    k2_item = page.locator('.mat-mdc-menu-item, [role="menuitem"], li, button').filter(has_text=re.compile(r"2K", re.IGNORECASE)).locator("visible=true").last
                    k2_item.wait_for(state='visible', timeout=10000)
                except Exception as e:
                    page.screenshot(path=os.path.join(output_dir, f"debug_sem_2k_{idx}.png"))
                    raise Exception(f"Opção '2K' não encontrada no submenu de qualidade: {e}")
                
                # ─── INTERCEPTAR DOWNLOAD (COM FALLBACK PARA 1K) ─────────────────────────
                download_success = False
                
                for tentativa_dl in range(3):
                    try:
                        # Nas duas primeiras tentativas usa 2K, na última faz fallback para 1K
                        is_fallback_1k = (tentativa_dl == 2)
                        qualidade_alvo = "1K" if is_fallback_1k else "2K"
                        
                        print(f"Tentativa {tentativa_dl + 1}/3 de download ({qualidade_alvo})...")
                        time.sleep(1.0)
                        
                        # Procurar o botão da qualidade específica
                        try:
                            qualidade_item = page.locator('.mat-mdc-menu-item, [role="menuitem"], li, button').filter(has_text=re.compile(qualidade_alvo, re.IGNORECASE)).locator("visible=true").last
                            qualidade_item.wait_for(state='visible', timeout=10000)
                        except Exception as e:
                            print(f"Aviso: Opção '{qualidade_alvo}' não encontrada. Erro: {e}")
                            continue # Tenta de novo no loop
                        
                        if is_fallback_1k:
                            update_status(90, "Falha no 2K. Baixando versão 1K (Tamanho Original)...")
                        
                        with page.expect_download(timeout=90000) as download_info:
                            # Clicar nativamente no container do menu
                            qualidade_item.click(force=True)
                        
                        download = download_info.value
                        prefixo = "geracao_1k" if is_fallback_1k else "geracao_2k"
                        filename = f"{prefixo}_{idx + 1}_{int(time.time())}.png"
                        file_path = os.path.join(output_dir, filename)
                        download.save_as(file_path)
                        
                        print(f"✅ Imagem {qualidade_alvo} salva com sucesso: {file_path}")
                        send_to_telegram(file_path, f"🎨 *Prompt:* {prompt}\n\n⚠️ *(Baixado em {qualidade_alvo})*")
                        sucessos += 1
                        download_success = True
                        break
                        
                    except Exception as dl_err:
                        print(f"❌ Falha na tentativa {tentativa_dl + 1}: {dl_err}")
                        
                        if tentativa_dl < 2:
                            print("Tentando reabrir o menu de opções...")
                            try:
                                page.keyboard.press('Escape')
                                time.sleep(0.5)
                                
                                page.mouse.move(center_x, center_y - 30)
                                time.sleep(0.3)
                                page.mouse.move(center_x, center_y)
                                time.sleep(1.0)
                                
                                page.mouse.click(dots_coords['x'], dots_coords['y'])
                                time.sleep(1.5)
                                
                                # Buscar novamente o Baixar
                                baixar_item = page.locator('.mat-mdc-menu-item, [role="menuitem"], li, button').filter(has_text=re.compile(r"baixar|download", re.IGNORECASE)).locator("visible=true").last
                                baixar_item.hover()
                                time.sleep(2.5)
                                
                            except Exception as reopen_err:
                                print(f"Erro ao reabrir menu: {reopen_err}")
                
                if not download_success:
                    page.screenshot(path=os.path.join(output_dir, f"debug_falha_download_{idx}.png"))
                    raise Exception(f"Falha ao interceptar download após 3 tentativas.")
                
                update_status(100, "✅ Imagem enviada com sucesso!")
                print(f"✅ Prompt {idx + 1} concluído com sucesso!")
                
            except Exception as e:
                print(f"❌ Erro no prompt '{prompt}': {e}")
                
                try:
                    error_path = os.path.join(output_dir, f"error_{idx}.png")
                    page.screenshot(path=error_path)
                    print(f"Screenshot de erro salvo: {error_path}")
                    send_to_telegram(error_path, f"🚨 *Erro no bot!*\n{e}\nVeja a tela:")
                except Exception as screen_err:
                    print(f"Erro ao salvar screenshot: {screen_err}")
                
                falhas += 1
            
            # Rate Limit entre gerações (exceto depois do último)
            if idx < len(prompts) - 1:
                delay = random.uniform(15, 25)
                print(f"\n⏸️ Rate Limit: Aguardando {delay:.1f}s antes da próxima geração...")
                time.sleep(delay)

        print(f"\n{'='*60}")
        print("✅ Processamento concluído!")
        print(f"📊 Sucessos: {sucessos} | Falhas: {falhas} | Total: {len(prompts)}")
        print(f"{'='*60}")
        
        msg_fim = (
            f"✅ *Processo Concluído!*\n\n"
            f"📊 *Resumo:*\n"
            f"✔️ Sucessos: {sucessos}\n"
            f"❌ Falhas: {falhas}\n"
            f"📝 Total de prompts: {len(prompts)}"
        )
        edit_status_message(status_msg_id, msg_fim)
        
        context.close()

if __name__ == "__main__":
    main()
