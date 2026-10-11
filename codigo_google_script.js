// Configurações (Preencha com seus dados)
var TELEGRAM_TOKEN = '8884730667:AAFksICsljBm17MkrANpCrBnGhuPbIQ2-Xc';
var GITHUB_TOKEN = 'SEU_GITHUB_TOKEN_AQUI'; // Insira seu token do GitHub (escopo: repo + workflow)
var GITHUB_REPO = 'robsonvit/ROBO-GERAR-IMAGENS-GITH'; // Repositório atual
var WORKFLOW_GERAR = 'run_generation.yml'; // Google Flow 2K
var WORKFLOW_DUCK = 'run_duck_generation.yml'; // DuckDuckGo fallback

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
        var msg = "👋 *Olá! Sou seu Bot Gerador de Imagens no Google Flow.*\n\n" +
                  "Ele roda 100% na nuvem sem precisar do PC ligado!\n\n" +
                  "📌 *Como usar:*\n" +
                  "• `/flow seu prompt aqui` (ou apenas digite o prompt)\n" +
                  "• `/gerar seu prompt aqui`\n" +
                  "• `/duck seu prompt aqui` (alternativa Duck.ai)\n\n" +
                  "✨ As imagens são geradas no Google Flow em alta resolução (2K)!";
        enviarMensagemTelegram(chatId, msg);
        return ContentService.createTextOutput("OK");
      }

      if (text.startsWith('/duck ')) {
        var promptDuck = text.replace('/duck ', '').trim();
        if (promptDuck) {
          var msgId = enviarMensagemTelegram(chatId, "🦆 *Comando DuckDuckGo recebido!*\n`[░░░░░░░░░░] 0%`");
          enviarParaGitHub(promptDuck, chatId, WORKFLOW_DUCK, msgId);
        }
      } 
      else {
        // Trata /flow, /gerar ou prompt direto digitado pelo usuário
        var prompt = text;
        if (prompt.startsWith('/flow ')) {
          prompt = prompt.replace('/flow ', '').trim();
        } else if (prompt.startsWith('/gerar ')) {
          prompt = prompt.replace('/gerar ', '').trim();
        }

        if (prompt) {
          var msgId = enviarMensagemTelegram(chatId, "🎨 *Prompt recebido!*\nAcordando o Google Flow na nuvem...\n`[░░░░░░░░░░] 0%`");
          enviarParaGitHub(prompt, chatId, WORKFLOW_GERAR, msgId);
        }
      }
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
    }
  } catch(e) {
    console.error("Erro no Telegram: " + e.toString());
  }
  return null;
}
