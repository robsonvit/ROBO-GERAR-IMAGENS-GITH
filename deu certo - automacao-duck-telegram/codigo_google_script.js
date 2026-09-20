// Configurações (Preencha com seus dados)
var TELEGRAM_TOKEN = '8884730667:AAFksICsljBm17MkrANpCrBnGhuPbIQ2-Xc';
var GITHUB_TOKEN = 'SEU_GITHUB_TOKEN_AQUI';
var GITHUB_REPO = 'robsonvit/ROBO-GERAR-IMAGENS-GITH'; // Repositório atual
var WORKFLOW_GERAR = 'run_generation.yml';
var WORKFLOW_DUCK = 'run_duck_generation.yml';

function doGet(e) {
  return ContentService.createTextOutput("Webhook OK e Ativo!");
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
      var text = update.message.text || "";
      var chatId = update.message.chat.id;

      if (text.startsWith('/gerar ')) {
        var prompt = text.replace('/gerar ', '').trim();
        if (prompt) {
          enviarMensagemTelegram(chatId, "🚀 *Comando recebido!*\nAcordando o servidor Labs...\n_(Aguarde 1-2 minutos)_");
          enviarParaGitHub(prompt, chatId, WORKFLOW_GERAR);
        }
      } 
      else if (text.startsWith('/duck ')) {
        var prompt = text.replace('/duck ', '').trim();
        if (prompt) {
          var msgId = enviarMensagemTelegram(chatId, "🦆 *PROMPT RECEBIDO E A IA ESTÁ TRABALHANDO*\n[□□□□□□□□□□] 0%");
          enviarParaGitHub(prompt, chatId, WORKFLOW_DUCK, msgId);
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
    enviarMensagemTelegram(chatId, "❌ Erro grave: " + error.toString());
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
