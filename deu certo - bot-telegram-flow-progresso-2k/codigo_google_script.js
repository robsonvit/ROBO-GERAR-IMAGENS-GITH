// Configurações (Preencha com seus dados)
var TELEGRAM_TOKEN = 'SEU_TELEGRAM_TOKEN_AQUI'; // Insira o token do seu bot do Telegram
var GITHUB_TOKEN = 'SEU_GITHUB_TOKEN_AQUI'; // Insira seu token do GitHub
var GITHUB_REPO = 'robsonvit/ROBO-GERAR-IMAGENS-GITH'; // Repositório atual
var WORKFLOW_GERAR = 'run_generation.yml'; // Google Flow 2K

function doGet(e) {
  return ContentService.createTextOutput("Webhook Google Flow OK e Ativo 24h!");
}

function doPost(e) {
  try {
    var update = JSON.parse(e.postData.contents);

    // BARREIRA ANTI-CLONES
    var updateId = update.update_id.toString();
    var cache = CacheService.getScriptCache();
    if (cache.get(updateId)) {
      return ContentService.createTextOutput("OK");
    }
    cache.put(updateId, "true", 3600);

    if (update.message && update.message.text) {
      var text = (update.message.text || "").trim();
      var chatId = update.message.chat.id;

      if (text.startsWith('/start')) {
        var msg = "👋 *Olá! Sou seu Bot Gerador de Imagens no Google Flow (PRO).*\n\n" +
                  "Ele roda 100% na nuvem sem precisar do seu PC ligado!\n\n" +
                  "📌 *Para gerar uma imagem, use sempre o comando:*\n" +
                  "• `/flow seu prompt aqui`\n" +
                  "• ou `/gerar seu prompt aqui`\n\n" +
                  "_Exemplo:_ `/flow Um leao dourado com armadura futurista luzes neon 4k`\n\n" +
                  "✨ As imagens são geradas na sua conta Google Flow e baixadas em **2K**!";
        enviarMensagemTelegram(chatId, msg);
        return ContentService.createTextOutput("OK");
      }

      var prompt = "";
      var isComando = false;

      if (text.startsWith('/flow ') || text === '/flow') {
        isComando = true;
        prompt = text.replace('/flow', '').trim();
      } else if (text.startsWith('/gerar ') || text === '/gerar') {
        isComando = true;
        prompt = text.replace('/gerar', '').trim();
      }

      if (!isComando) {
        // Mensagem enviada sem comando — avisa para evitar disparos acidentais
        var aviso = "⚠️ *Comando não reconhecido!*\n\n" +
                    "Para gerar uma imagem e evitar disparos acidentais, use o comando:\n" +
                    "👉 `/flow seu prompt aqui`\n" +
                    "ou `/gerar seu prompt aqui`\n\n" +
                    "_Exemplo:_ `/flow Uma linda praia paradisiaca por do sol 4k`";
        enviarMensagemTelegram(chatId, aviso);
        return ContentService.createTextOutput("OK");
      }

      if (!prompt) {
        enviarMensagemTelegram(chatId, "⚠️ Por favor, digite o prompt após o comando.\n_Exemplo:_ `/flow Um guerreiro samurai neon 4k`");
        return ContentService.createTextOutput("OK");
      }

      // Envia feedback inicial e captura o message_id para edição em tempo real pelo GitHub Actions
      var feedbackInicial = "🎨 *Prompt recebido!*\n" +
                            "📝 _\"" + prompt + "\"_\n\n" +
                            "`[░░░░░░░░░░] 0%`\n" +
                            "⏳ _Acionando Google Flow na nuvem..._";
      var msgId = enviarMensagemTelegram(chatId, feedbackInicial);
      enviarParaGitHub(prompt, chatId, WORKFLOW_GERAR, msgId);
    }
  } catch (error) {
    console.error(error);
  }
  return HtmlService.createHtmlOutput("OK");
}

function enviarParaGitHub(prompt, chatId, workflow_file, messageId) {
  var githubUrl = 'https://api.github.com/repos/' + GITHUB_REPO + '/actions/workflows/' + workflow_file + '/dispatches';

  var inputs = {
      "prompt": prompt,
      "chat_id": chatId.toString()
  };
  
  if (messageId) {
      inputs["message_id"] = messageId.toString();
  }

  var payload = {
    "ref": "main",
    "inputs": inputs
  };

  var options = {
    "method": "post",
    "headers": {
      "Authorization": "token " + GITHUB_TOKEN,
      "Accept": "application/vnd.github.v3+json"
    },
    "payload": JSON.stringify(payload),
    "muteHttpExceptions": true
  };

  try {
    UrlFetchApp.fetch(githubUrl, options);
  } catch (error) {
    enviarMensagemTelegram(chatId, "❌ Erro grave ao acionar GitHub Actions: " + error.toString());
  }
}

function enviarMensagemTelegram(chatId, text) {
  var telegramUrl = 'https://api.telegram.org/bot' + TELEGRAM_TOKEN + '/sendMessage';
  
  var payload = {
    "chat_id": chatId,
    "text": text,
    "parse_mode": "Markdown"
  };
  
  var options = {
    "method": "post",
    "contentType": "application/json",
    "payload": JSON.stringify(payload),
    "muteHttpExceptions": true
  };
  
  try {
    var response = UrlFetchApp.fetch(telegramUrl, options);
    var json = JSON.parse(response.getContentText());
    if (json.ok) {
      return json.result.message_id;
    } else {
      // Fallback sem parse_mode caso markdown falhe
      delete payload.parse_mode;
      options.payload = JSON.stringify(payload);
      var r2 = UrlFetchApp.fetch(telegramUrl, options);
      var j2 = JSON.parse(r2.getContentText());
      if (j2.ok) return j2.result.message_id;
    }
  } catch(e) {
    console.error("Erro no Telegram: " + e.toString());
  }
  return null;
}
