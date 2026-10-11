import os
import json
import base64
import subprocess
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_DIR = os.path.join(BASE_DIR, "sessao_google")

def update_github_secret(b64_content):
    try:
        cmd = ["gh", "secret", "set", "GOOGLE_SESSION_STATE", "-b", b64_content]
        res = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True, check=True)
        print("✅ Segredo 'GOOGLE_SESSION_STATE' atualizado no GitHub Actions via gh CLI!")
        return True
    except Exception as e:
        print(f"ℹ️ Não foi possível atualizar o GitHub automaticamente via gh CLI ({e}).")
        return False

def main():
    print("=" * 60)
    print("  🍪 EXPORTADOR DE COOKIES (SESSÃO DO GOOGLE FLOW) 🍪")
    print("=" * 60)
    print(f"\nProcurando sessão local em: {SESSION_DIR}...")
    
    if not os.path.exists(SESSION_DIR):
        print("❌ Pasta de sessão local não encontrada. Por favor, rode o login_setup.py primeiro.")
        return

    with sync_playwright() as p:
        try:
            print("Abrindo navegador (invisível) para capturar cookies do Google Flow...")
            context = p.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR,
                headless=True,
                args=['--no-sandbox', '--disable-blink-features=AutomationControlled'],
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            state = context.storage_state()
            context.close()
            
            # Salva o arquivo state.json local
            state_file = os.path.join(BASE_DIR, "state.json")
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
            print(f"✅ Arquivo 'state.json' salvo.")

            # Converte para Base64
            state_str = json.dumps(state)
            state_b64 = base64.b64encode(state_str.encode('utf-8')).decode('utf-8')
            
            output_file = os.path.join(BASE_DIR, "state_b64.txt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(state_b64)
                
            print(f"✅ Arquivo 'state_b64.txt' atualizado com código Base64.")

            # Sincroniza no GitHub Secrets
            print("🚀 Sincronizando com GitHub Secrets...")
            update_github_secret(state_b64)
            
        except Exception as e:
            print(f"\n❌ Erro ao exportar cookies: {e}")

if __name__ == "__main__":
    main()
