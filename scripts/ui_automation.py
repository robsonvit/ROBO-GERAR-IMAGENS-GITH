import os
import json
import time
import random
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

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

    # Ler prompts
    prompts_file = os.path.join(base_dir, 'data', 'prompts.txt')
    try:
        with open(prompts_file, 'r', encoding='utf-8') as f:
            prompts = [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        print(f"Erro: Arquivo de prompts não encontrado em {prompts_file}")
        return

    if not prompts:
        print("Nenhum prompt encontrado no arquivo.")
        return

    # Iniciar Playwright
    with sync_playwright() as p:
        print("Iniciando navegador headless...")
        browser = p.chromium.launch(headless=True)
        
        # User-Agent comum
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        # Restaurar sessão
        context.add_cookies(cookies)

        page = context.new_page()
        
        # Aplicar stealth
        stealth_sync(page)

        print("Navegando para Google Labs Flow...")
        page.goto('https://labs.google/fx/pt/tools/flow/', wait_until='domcontentloaded')
        
        # Atraso para processamento dos scripts
        time.sleep(random.uniform(3, 5))

        for idx, prompt in enumerate(prompts):
            print(f"\n--- Processando prompt {idx + 1}/{len(prompts)} ---")
            print(f"Texto: '{prompt}'")
            try:
                # Localizar caixa de texto
                input_locator = page.locator('textarea, input[type="text"]').first
                input_locator.wait_for(state='visible', timeout=10000)
                
                # Limpar conteúdo
                input_locator.fill('')
                
                # Digitação progressiva
                input_locator.type(prompt, delay=100)
                
                # Atraso pós digitação
                time.sleep(random.uniform(1.0, 2.0))
                
                # Submeter
                input_locator.press('Enter')
                print("Solicitação enviada. Aguardando geração...")
                
                # Aguardar imagem ser gerada
                # Como não temos o DOM exato, esperamos até 45s por uma alteração significativa ou por um locator genérico
                time.sleep(random.uniform(3.0, 5.0))
                
                image_locator = page.locator('img').last
                image_locator.wait_for(state='visible', timeout=45000)
                
                # Obter a URL da imagem
                img_src = image_locator.get_attribute('src')
                
                if img_src:
                    print(f"Imagem encontrada. Baixando...")
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
