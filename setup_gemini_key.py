"""
setup_gemini_key.py - Configura a API Oficial do Google Imagen 3 (Sem Cookies / Nunca Expira)

Como usar:
1. Acesse https://aistudio.google.com/app/apikey (com sua conta Google)
2. Clique em "Create API Key" (ou "Criar chave de API") e copie a chave gerada.
3. Execute este script: ele salvará a chave localmente no .env e no GitHub Secrets (GEMINI_API_KEY)!
"""
import os
import sys
import subprocess

# Garante suporte a UTF-8 no Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def main():
    print("=" * 65)
    print("  🔑 CONFIGURAÇÃO DA API OFICIAL DO GOOGLE IMAGEN 3 (GRATUITA)")
    print("=" * 65)
    print("\nCom a chave de API Oficial do Google:")
    print("  • NUNCA mais precisa de cookies nem Cookie-Editor.")
    print("  • NUNCA expira a sessão.")
    print("  • As imagens são geradas em menos de 10 segundos na nuvem!")
    print("\n👉 Pegue sua chave gratuita em: https://aistudio.google.com/app/apikey\n")

    key = input("Cole sua API Key do Google AI Studio aqui e tecle ENTER: ").strip()

    if not key:
        print("❌ Nenhuma chave informada.")
        return

    # 1. Salva no .env local
    env_file = os.path.join(BASE_DIR, ".env")
    env_lines = []
    found = False
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    env_lines.append(f'GEMINI_API_KEY="{key}"\n')
                    found = True
                else:
                    env_lines.append(line)
    if not found:
        env_lines.append(f'\nGEMINI_API_KEY="{key}"\n')

    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(env_lines)
    print("✅ Chave salva no seu arquivo local '.env'!")

    # 2. Salva no GitHub Secrets via gh CLI
    try:
        print("🚀 Enviando 'GEMINI_API_KEY' para o GitHub Secrets...")
        cmd = ["gh", "secret", "set", "GEMINI_API_KEY"]
        subprocess.run(cmd, input=key, cwd=BASE_DIR, check=True, capture_output=True, text=True)
        print("✅ Segredo 'GEMINI_API_KEY' configurado com sucesso no GitHub Actions!")
        print("\n🎉 PARABÉNS! Seu robô agora usa a API Oficial do Google Imagen 3!")
        print("   Seus comandos no Telegram agora vão gerar imagens em ~10 segundos e NUNCA mais vão expirar!")
    except Exception as e:
        print(f"\nℹ️ Não foi possível enviar automaticamente pelo gh CLI ({e}).")
        print("   Você pode adicionar manualmente no GitHub:")
        print("   1. Acesse seu repositório no GitHub -> Settings -> Secrets and variables -> Actions")
        print("   2. Clique em 'New repository secret'")
        print("   3. Nome: GEMINI_API_KEY")
        print("   4. Valor: cole sua chave e clique em 'Add secret'.")

if __name__ == "__main__":
    main()
