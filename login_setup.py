"""
login_setup.py - Setup e Renovação de Sessão Google Flow

Abre o navegador, ajuda a abrir a tela de login do Google Flow, valida
que a conta está REALMENTE logada (verificando cookies de autenticação do Google)
e sincroniza automaticamente com o GitHub Secrets para rodar na nuvem sem o PC ligado!
"""
import os
import sys
import json
import base64
import time
import subprocess
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR) if os.path.basename(BASE_DIR) == 'scripts' else BASE_DIR
SESSION_DIR = os.path.join(PROJECT_DIR, "sessao_google")

GOOGLE_AUTH_COOKIES = {'SID', 'SSID', 'HSID', '__Secure-1PSID', '__Secure-3PSID', 'SAPISID'}

def is_logged_in(context, page):
    """Verifica se a página está no Flow logado e possui cookies de autenticação do Google."""
    url = page.url.lower()
    # Se ainda estiver na página de marketing /about ou no accounts.google.com
    if '/about' in url or 'accounts.google.com' in url or 'signin' in url:
        return False, "Você ainda está na página de login ou apresentação (/about)."
    
    state = context.storage_state()
    cookies = state.get('cookies', [])
    cookie_names = {c.get('name') for c in cookies}
    
    has_auth_cookie = bool(cookie_names.intersection(GOOGLE_AUTH_COOKIES))
    if not has_auth_cookie:
        return False, "Nenhum cookie de sessão do Google detectado (SID/SSID ausentes)."
    
    return True, "Sessão autenticada válida!"

def update_github_secret(b64_content, state_dict=None):
    """Atualiza automaticamente os segredos no GitHub se o gh CLI estiver configurado."""
    try:
        cmd1 = ["gh", "secret", "set", "GOOGLE_SESSION_STATE", "-b", b64_content]
        subprocess.run(cmd1, cwd=PROJECT_DIR, capture_output=True, text=True, check=True)
        if state_dict:
            cmd2 = ["gh", "secret", "set", "AUTH_SESSION_JSON"]
            subprocess.run(cmd2, input=json.dumps(state_dict), cwd=PROJECT_DIR, capture_output=True, text=True, check=True)
        print("✅ Segredos 'AUTH_SESSION_JSON' e 'GOOGLE_SESSION_STATE' atualizados no GitHub Actions!")
        return True
    except Exception as e:
        print(f"ℹ️ Não foi possível atualizar o GitHub via gh CLI ({e}).")
        return False

def main():
    print("=" * 65)
    print("  🔐 SETUP DE SESSÃO — GOOGLE FLOW (flow.google.com)")
    print("=" * 65)
    print(f"\n📁 Diretório de sessão persistente: {SESSION_DIR}\n")
    print("Abrindo o navegador...")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled'
            ],
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 800}
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto('https://flow.google.com/', timeout=60000)
        time.sleep(3)

        # Se caiu na página /about, clica em "Start Creating" ou "Fazer login" para abrir a tela de login
        if '/about' in page.url.lower():
            print("Detectada página de boas-vindas (/about). Clicando para iniciar login...")
            try:
                btn_start = page.locator("text=/Start Creating/i, text=/Comece a criar/i, text=/Fazer login/i, text=/Sign in/i").first
                if btn_start.is_visible(timeout=5000):
                    btn_start.click()
                    time.sleep(2)
            except Exception as e:
                print(f"Clique automático: {e}")

        print("\n" + "=" * 65)
        print("  👉 FAÇA LOGIN NA JANELA DO CHROME QUE ABRIU:")
        print("  1. Entre com seu e-mail e senha da conta Google.")
        print("  2. Aguarde até a tela do Google Flow carregar (mostrando seus projetos).")
        print("  3. Quando estiver na tela de criação do Flow, volte aqui e tecle ENTER!")
        print("=" * 65)

        while True:
            input("\n  → Pressione ENTER após CONCLUIR o login no Google Flow: ")
            
            logged, reason = is_logged_in(context, page)
            if logged:
                print(f"\n✅ SUCESSO! Login do Google confirmado!")
                print(f"🌐 URL atual: {page.url}")
                break
            else:
                print(f"\n⚠️ {reason}")
                print(f"🌐 URL atual: {page.url}")
                print("➡️ Por favor, complete o login na janela do navegador aberta antes de confirmar.")

        # Salva o storage state (cookies + localStorage)
        state = context.storage_state()
        context.close()

        state_path = os.path.join(PROJECT_DIR, "state.json")
        with open(state_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
        print(f"✅ Arquivo local '{state_path}' salvo!")

        # Converte para base64
        state_str = json.dumps(state)
        state_b64 = base64.b64encode(state_str.encode('utf-8')).decode('utf-8')

        output_b64_file = os.path.join(PROJECT_DIR, "state_b64.txt")
        with open(output_b64_file, 'w', encoding='utf-8') as f:
            f.write(state_b64)
        print(f"✅ Arquivo '{output_b64_file}' atualizado com o código Base64!")

        # Sincroniza com GitHub Secrets
        print("\n🚀 Sincronizando sessão com o GitHub Actions...")
        update_github_secret(state_b64, state)

        print("\n🎉 SESSÃO ATIVA CONFIGURADA COM SUCESSO!")
        print("   Agora o GitHub Actions tem as credenciais da sua conta Google Flow.")
        print("   Pode enviar prompts pelo Telegram com o PC DESLIGADO!")

if __name__ == "__main__":
    main()
