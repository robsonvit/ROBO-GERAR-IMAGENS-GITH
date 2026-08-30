import os
import requests
import telebot
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env local, se existir
load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO') # formato: dono/repo, ex: robsonvit/ROBO-GERAR-IMAGENS-GITH
GITHUB_WORKFLOW = os.environ.get('GITHUB_WORKFLOW', 'run_generation.yml')

if not TELEGRAM_BOT_TOKEN:
    print("ERRO: TELEGRAM_BOT_TOKEN não encontrado.")
    exit(1)

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

@bot.message_handler(commands=['gerar'])
def handle_gerar(message):
    texto = message.text
    # Remove o comando /gerar do texto
    if len(texto) <= 7:
        bot.reply_to(message, "Por favor, envie os prompts junto com o comando.\nExemplo:\n/gerar\nprompt 1\nprompt 2")
        return
        
    prompts = texto[6:].strip() # Pega tudo depois de "/gerar "
    
    # Envia mensagem inicial
    msg = bot.reply_to(message, "🚀 *Iniciando automação...*\nEnfileirando job no GitHub Actions...", parse_mode='Markdown')
    
    if not GITHUB_TOKEN or not GITHUB_REPO:
        bot.edit_message_text(
            chat_id=msg.chat.id,
            message_id=msg.message_id,
            text="❌ Erro: GITHUB_TOKEN ou GITHUB_REPO não estão configurados no bot."
        )
        return

    # Chama a API do GitHub para rodar o Workflow
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW}/dispatches"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {
        "ref": "main", # branch principal
        "inputs": {
            "prompt": prompts
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 204:
            bot.edit_message_text(
                chat_id=msg.chat.id,
                message_id=msg.message_id,
                text="✅ *Sucesso!* Job disparado no GitHub Actions.\nEm breve a automação começará a gerar e enviar suas imagens aqui.",
                parse_mode='Markdown'
            )
        else:
            bot.edit_message_text(
                chat_id=msg.chat.id,
                message_id=msg.message_id,
                text=f"❌ *Erro ao disparar no GitHub:*\nStatus Code: {response.status_code}\nResponse: {response.text}",
                parse_mode='Markdown'
            )
    except Exception as e:
        bot.edit_message_text(
            chat_id=msg.chat.id,
            message_id=msg.message_id,
            text=f"❌ *Erro na requisição para o GitHub:*\n{str(e)}",
            parse_mode='Markdown'
        )

print("Bot listener iniciado! Pressione Ctrl+C para parar.")
bot.infinity_polling()
