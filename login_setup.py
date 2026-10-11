"""
login_setup.py - Setup e Renovação de Sessão Google Flow

Execute este script para fazer login na sua conta Google no Flow (https://flow.google.com/).
Após logar, ele salva a sessão localmente e já envia automaticamente para o
GitHub Secrets (GOOGLE_SESSION_STATE), permitindo que a geração na nuvem funcione
com o PC DESLIGADO!

Como usar:
    python login_setup.py
"""
import os
import sys
import json
import base64
import subprocess
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR) if os.path.basename(BASE_DIR) == 'scripts' else BASE_DIR
SESSION_DIR = os.path.join(PROJECT_DIR, "sessao_google")

def update_github_secret(b64_content):
    """Atualiza automaticamente o segredo no GitHub se o gh CLI estiver configurado."""
    try:
        cmd = ["gh", "secret", "set", "GOOGLE_SESSION_STATE", "-b", b64_content]
        res = subprocess.run(cmd, cwd=PROJECT_DIR, capture_output=True, text=True, check=True)
        print("✅ Segredo 'GOOGLE_SESSION_STATE' atualizado no GitHub Actions automaticamente via gh CLI!")
        return True
    except Exception as e:
        print(f"ℹ️ Não foi possível atualizar o GitHub automaticamente via gh CLI ({e}).")
        print("   Você pode copiar o conteúdo do arquivo 'state_b64.txt' e colar manualmente no GitHub Secrets.")
        return False

def main():
    print("=" * 65)
    print("  🔐 SETUP DE SESSÃO — GOOGLE FLOW (flow.google.com)")
    print("=" * 65)
    print(f"\n📁 Diretório de sessão persistente: {SESSION_DIR}\n")
    print("Abrindo o navegador para você entrar na sua conta Google...")
    print("Por favor, não feche o navegador manualmente.\n")

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

        print("=" * 65)
        print("  ⏳ Faça login com sua conta Google na janela que abriu.")
        print("  ✅ Quando você já estiver logado e vendo o Google Flow,")
        print("     pressione ENTER aqui no terminal para salvar!")
        print("=" * 65)
        
        input("\n  → Pressione ENTER após fazer login no Google Flow: ")

        current_url = page.url
        if 'accounts.google.com' in current_url or 'signin' in current_url.lower():
            print("\n❌ Parece que o login ainda não foi concluído. Tente novamente.")
            context.close()
            return

        print(f"\n✅ Login detectado com sucesso no Google Flow! URL: {current_url}")

        # Salva o storage state (cookies + localStorage)
        state = context.storage_state()
        context.close()

        state_path = os.path.join(PROJECT_DIR, "state.json")
        with open(state_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
        print(f"✅ Arquivo local '{state_path}' salvo com sucesso!")

        # Converte para base64
        state_str = json.dumps(state)
        state_b64 = base64.b64encode(state_str.encode('utf-8')).decode('utf-8')

        output_b64_file = os.path.join(PROJECT_DIR, "state_b64.txt")
        with open(output_b64_file, 'w', encoding='utf-8') as f:
            f.write(state_b64)
        print(f"✅ Arquivo '{output_b64_file}' atualizado com o código Base64!")

        # Envia para o GitHub Secrets automaticamente
        print("\n🚀 Sincronizando sessão com o GitHub Actions...")
        update_github_secret(state_b64)

        print("\n🎉 Tudo pronto! Agora as gerações pelo Telegram rodam no Google Flow")
        print("   diretamente na nuvem (GitHub Actions), SEM PRECISAR DO PC LIGADO!")

if __name__ == "__main__":
    main()
