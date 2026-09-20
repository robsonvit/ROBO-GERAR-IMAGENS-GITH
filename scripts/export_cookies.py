import os
import json
import base64
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_DIR = os.path.join(BASE_DIR, "sessao_google")

def main():
    print("=" * 60)
    print("  🍪 EXPORTADOR DE COOKIES (SESSÃO DO GOOGLE LABS) 🍪")
    print("=" * 60)
    print(f"\nProcurando sessão local em: {SESSION_DIR}...")
    
    if not os.path.exists(SESSION_DIR):
        print("❌ Pasta de sessão local não encontrada. Por favor, rode o login_setup.py primeiro.")
        return

    with sync_playwright() as p:
        try:
            print("Abrindo navegador (invisível) para capturar os cookies...")
            context = p.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR,
                headless=True,
                args=['--no-sandbox', '--disable-blink-features=AutomationControlled'],
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # Obtém os cookies e estado de armazenamento local
            state = context.storage_state()
            context.close()
            
            # Converte para string JSON
            state_str = json.dumps(state)
            
            # Converte para Base64 para ser fácil de colar no GitHub Secrets
            state_b64 = base64.b64encode(state_str.encode('utf-8')).decode('utf-8')
            
            # Salva num arquivo local para facilitar a cópia
            output_file = os.path.join(BASE_DIR, "state_b64.txt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(state_b64)
                
            print("\n✅ Cookies capturados com sucesso!")
            print(f"✅ Um arquivo chamado 'state_b64.txt' foi criado na raiz do projeto com o código Base64.")
            print("\n--- O QUE FAZER AGORA? ---")
            print("1. Abra o arquivo state_b64.txt")
            print("2. Copie TODO o texto (sem quebras de linha)")
            print("3. Vá no seu repositório no GitHub -> Settings -> Secrets and variables -> Actions")
            print("4. Clique em 'New repository secret'")
            print("5. Name: GOOGLE_SESSION_STATE")
            print("6. Secret: <cole o texto aqui>")
            print("7. Clique em Add secret")
            
        except Exception as e:
            print(f"\n❌ Erro ao exportar cookies: {e}")

if __name__ == "__main__":
    main()
