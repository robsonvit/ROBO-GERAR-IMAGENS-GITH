"""
import_cookies.py - Importa cookies exportados via Cookie-Editor para o GitHub Secrets

Como usar:
1. No seu Chrome normal onde você já está logado no Google Flow (https://flow.google.com/):
   - Abra a extensão Cookie-Editor
   - Clique em 'Export' -> 'Export as JSON'
2. Salve o conteúdo em um arquivo chamado 'cookies.json' nesta pasta (ou execute este script).
3. O script enviará automaticamente para o GitHub Secrets (AUTH_SESSION_JSON)!
"""
import os
import json
import subprocess
import sys

# Garante suporte a UTF-8 no Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def main():
    print("=" * 65)
    print("  🍪 IMPORTADOR DE COOKIES — GOOGLE FLOW (ESTILO GROK) 🍪")
    print("=" * 65)

    cookies_file = os.path.join(BASE_DIR, "cookies.json")
    
    if os.path.exists(cookies_file):
        print(f"Lendo cookies de: {cookies_file}...")
        with open(cookies_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
    else:
        print("\nArquivo 'cookies.json' não encontrado na pasta.")
        print("Você pode colar o JSON do Cookie-Editor aqui embaixo agora:")
        print("(Cole o JSON e aperte ENTER):\n")
        content = input().strip()

    if not content:
        print("❌ Nenhum conteúdo fornecido.")
        return

    try:
        data = json.loads(content)
        if not isinstance(data, list):
            print("⚠️ Aviso: O formato esperado do Cookie-Editor é uma lista de cookies [ ... ].")
    except Exception as e:
        print(f"❌ Erro ao validar o JSON: {e}")
        return

    # Salva localmente em state.json
    state_file = os.path.join(BASE_DIR, "state.json")
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Arquivo local '{state_file}' salvo com sucesso!")

    # Atualiza segredo no GitHub
    compact_json = json.dumps(data)
    try:
        print("🚀 Enviando para o GitHub Secrets (AUTH_SESSION_JSON)...")
        cmd = ["gh", "secret", "set", "AUTH_SESSION_JSON"]
        subprocess.run(cmd, input=compact_json, cwd=BASE_DIR, check=True, capture_output=True, text=True)
        print("✅ Segredo 'AUTH_SESSION_JSON' atualizado com sucesso no GitHub Actions!")
        print("\n🎉 PRONTO! O robô no GitHub Actions já tem seus cookies do Flow!")
        print("   Agora ele entra direto na sua conta sem pedir nada, igualzinho ao Grok!")
    except Exception as e:
        print(f"Aviso ao enviar via gh CLI: {e}")
        print("Você também pode copiar o conteúdo e colar manualmente no GitHub Secrets com o nome AUTH_SESSION_JSON.")

if __name__ == "__main__":
    main()
