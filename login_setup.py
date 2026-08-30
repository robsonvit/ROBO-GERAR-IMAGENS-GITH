"""
login_setup.py - Script de Login Inicial

Execute este script UMA VEZ para fazer login no Google Labs.
Depois disso, o bot vai rodar normalmente sem pedir login.

Como usar:
    python login_setup.py

Uma janela do Chrome vai abrir. Faça login com sua conta Google normalmente.
Após fazer login, volte aqui e pressione ENTER para salvar a sessão.
"""
import os
import time
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Volta uma pasta (de scripts/ para a raiz do projeto)
PROJECT_DIR = os.path.dirname(BASE_DIR) if os.path.basename(BASE_DIR) == 'scripts' else BASE_DIR
SESSION_DIR = os.path.join(PROJECT_DIR, "sessao_google")

def main():
    print("=" * 60)
    print("  🔐 SETUP DE LOGIN - GOOGLE LABS IMAGE FX")
    print("=" * 60)
    print(f"\n📁 Pasta de sessão: {SESSION_DIR}\n")
    print("Abrindo o Chrome... Faça login normalmente na janela que abrir.")
    print("Não feche a janela do Chrome manualmente!\n")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,  # VISÍVEL para você fazer login
            args=['--no-sandbox', '--disable-blink-features=AutomationControlled'],
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 800}
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto('https://labs.google/fx/pt/tools/flow/', timeout=60000)

        print("\n" + "=" * 60)
        print("  ⏳ Aguardando você fazer login...")
        print("  ✅ Quando estiver logado e ver o Google Labs, pressione")
        print("     ENTER aqui neste terminal para salvar a sessão.")
        print("=" * 60)
        
        input("\n  → Pressione ENTER após fazer login: ")

        # Verificar se login foi bem sucedido
        current_url = page.url
        if 'accounts.google.com' in current_url or 'signin' in current_url.lower():
            print("\n❌ Parece que você ainda não está logado. Tente novamente.")
        else:
            print(f"\n✅ Login detectado com sucesso! URL: {current_url}")
            print(f"✅ Sessão salva em: {SESSION_DIR}")
            print("\n🎉 Pronto! Agora você pode rodar o bot normalmente.")
            print("   Execute: python scripts/bot_listener.py")

        context.close()

if __name__ == "__main__":
    main()
