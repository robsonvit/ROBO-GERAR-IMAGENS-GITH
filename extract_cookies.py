import os
import json
import subprocess
from playwright.sync_api import sync_playwright

def extract():
    user_data_dir = os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data')
    
    with sync_playwright() as p:
        try:
            print("Tentando acessar o perfil do Chrome...")
            browser = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=True,
                channel="chrome",
            )
            
            page = browser.pages[0] if browser.pages else browser.new_page()
            print("Acessando Google Labs...")
            page.goto('https://labs.google/fx/pt/tools/flow/', timeout=60000)
            
            print("Extraindo cookies da sessão...")
            cookies = browser.cookies()
            
            google_cookies = [c for c in cookies if 'google' in c['domain']]
            
            if not google_cookies:
                print("Nenhum cookie do Google encontrado. Talvez não esteja logado.")
            else:
                json_str = json.dumps(google_cookies)
                print("Configurando secret AUTH_SESSION_JSON no GitHub...")
                proc = subprocess.Popen(['gh', 'secret', 'set', 'AUTH_SESSION_JSON'], stdin=subprocess.PIPE, text=True)
                proc.communicate(input=json_str)
                if proc.returncode == 0:
                    print("Sucesso ao configurar AUTH_SESSION_JSON!")
                else:
                    print("Falha ao configurar secret.")
                    
            browser.close()
        except Exception as e:
            print(f"Erro ao extrair pelo Playwright: {e}")

if __name__ == "__main__":
    extract()
