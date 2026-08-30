// Configurações (Preencha com seus dados)
var TELEGRAM_TOKEN = 'SEU_TELEGRAM_TOKEN_AQUI';
var GITHUB_TOKEN = 'SEU_GITHUB_TOKEN_AQUI';
var GITHUB_REPO = 'robsonvit/ROBO-GERAR-IMAGENS-GITH'; // Repositório atual
var WORKFLOW_FILE = 'run_generation.yml'; // Ajuste caso seu arquivo YML no GitHub tenha outro nome

function doPost(e) {
  try {
    var update = JSON.parse(e.postData.contents);
    
    // BARREIRA ANTI-CLONES (Usa a memória de cache do Google)
    var updateId = update.update_id.toString();
    var cache = CacheService.getScriptCache();
    
    // Se o Telegram enviou uma mensagem que já processamos hoje, retorna OK e ignora!
    if (cache.get(updateId)) {
      return ContentService.createTextOutput("OK");
    }
    
    // Se for mensagem inédita, salva o ID para não processar retries
    cache.put(updateId, "true", 3600); // Fica gravado por 1 hora
    
    // Verifica se é uma mensagem com texto
    if (update.message && update.message.text) {
      var text = update.message.text;
      var chatId = update.message.chat.id;
      
      // Verifica se o comando é /gerar
      if (text.startsWith('/gerar ')) {
        var prompt = text.replace('/gerar ', '').trim();
        
        if (prompt) {
          enviarParaGitHub(prompt, chatId);
        } else {
          enviarMensagemTelegram(chatId, "Por favor, envie o comando no formato: /gerar [seu prompt aqui]");
        }
      }
    }
  } catch (error) {
    // Trata erros silenciosamente para evitar que o Telegram fique retentando o webhook
    console.error(error);
  }
  
  // O Telegram exige uma resposta HTTP 200 OK
  return ContentService.createTextOutput("OK");
}

function enviarParaGitHub(prompt, chatId) {
  var githubUrl = 'https://api.github.com/repos/' + GITHUB_REPO + '/actions/workflows/' + WORKFLOW_FILE + '/dispatches';
  
  var payload = {
    "ref": "main", // Branch onde o workflow está configurado
    "inputs": {
      "prompt": prompt,
      "chat_id": chatId.toString() // Enviando o chatId para que o GitHub saiba para quem devolver a imagem
    }
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
    // Apenas envia pro GitHub e verifica a resposta silenciosamente
    var res = UrlFetchApp.fetch(githubUrl, options);
    if (res.getResponseCode() !== 204) {
       enviarMensagemTelegram(chatId, "⚠️ Ops, o Github recusou o comando! Código: " + res.getResponseCode() + "\nMotivo: " + res.getContentText());
    }
  } catch (error) {
    enviarMensagemTelegram(chatId, "❌ Erro grave no Google Script ao acionar Github: " + error.toString());
  }
}

function enviarMensagemTelegram(chatId, text) {
  var telegramUrl = 'https://api.telegram.org/bot' + TELEGRAM_TOKEN + '/sendMessage';
  
  var payload = {
    "chat_id": chatId,
    "text": text
  };
  
  var options = {
    "method": "post",
    "contentType": "application/json",
    "payload": JSON.stringify(payload)
  };
  
  UrlFetchApp.fetch(telegramUrl, options);
}
