# ✅ Deu Certo — Automação DuckDuckGo com Telegram e Barra de Progresso

**Data:** 2026-09-20
**Projeto:** ROBO GERAR IMAGENS GITH

## O que funcionou

Criamos com sucesso uma automação completa onde o usuário envia `/duck [prompt]` no Telegram e o webhook do Google Apps Script intercepta a mensagem. O webhook responde instantaneamente no Telegram com uma barra de progresso em 0% e aciona um workflow no GitHub Actions via `workflow_dispatch`. 

O GitHub Actions roda o script Python com Playwright que abre o DuckDuckGo (aba anônima com `incognito=True` no contexto do browser), gera a imagem pelo modelo ChatGPT embutido, faz o download do Blob resultante em tempo real monitorando a rede do Playwright, edita a barra de progresso a cada 3 segundos via threading e por fim envia a imagem gerada para o Telegram. Além disso, resolvemos o erro do Google Apps Script com o Runtime V8 e OAuth (clasp deploy exigindo permissões manuais).

## Arquivos envolvidos

| Arquivo | Papel na solução |
|---------|-----------------|
| `codigo_google_script.js` | Webhook do Google que lida com os comandos `/gerar` e `/duck`. Envia a mensagem inicial da barra de progresso, extrai o `message_id` retornado pelo Telegram e despacha o workflow no GitHub enviando o `message_id` como input. |
| `appsscript.json` | Manifest do Google Apps Script. Exige `runtimeVersion: V8` e `access: ANYONE_ANONYMOUS` para que o Telegram possa disparar a URL do Webhook corretamente sem erro 404/Login. |
| `run_duck_generation.yml` | Workflow do GitHub Actions que foi refatorado para aceitar `message_id` via `inputs` e executá-lo no ambiente Python usando a variável de ambiente para que o script possa atualizar a barra de progresso. |
| `duck_automation.py` | Script Python com Playwright. Implementa uma Threading paralela que edita a mensagem do Telegram para simular a barra de progresso preenchendo. Ao mesmo tempo, controla o browser, aguarda o botão de "Download", intercepta o Blob do download pelo event listener do Playwright, envia a foto para o Telegram via bot e sinaliza a thread de progresso para encerrar. |

## Como replicar

1. Subir o `codigo_google_script.js` para o Google Apps Script usando `clasp push`.
2. Acessar a interface Web do Google Apps Script e executar a função `doGet` ou `doPost` uma vez manualmente para conceder a **Autorização OAuth**. Sem isso, a comunicação externa via `UrlFetchApp` falha silenciosamente.
3. Fazer o `clasp deploy` para gerar um novo Deployment ID.
4. Setar o webhook no Telegram chamando `https://api.telegram.org/bot[TOKEN]/setWebhook?url=[URL_EXEC_DO_APPS_SCRIPT]`.
5. Disparar a mensagem no Telegram e acompanhar os logs no GitHub Actions!

## Observações

- **Google Apps Script:** Sempre que gerar um novo Deploy, lembre-se de configurar a permissão de acesso para "ANYONE_ANONYMOUS", caso contrário o Telegram recebe erro `404 Not Found`. E lembre de clicar em "Permitir" a cada permissão adicionada.
- **GitHub Actions Runner Local:** Se o runner rodar em Windows e o `setup-python` tentar mexer no registro e falhar por permissões, use o Python local do runner instalando dependências com `.venv\Scripts\pip`.
- **Barra de Progresso:** A barra foi feita usando uma `threading.Thread` no Python. É essencial usar um `global is_done = True` após o encerramento do download para evitar que a Thread fique rodando infinitamente editando a mesma mensagem no Telegram e estourando o limite de Rate Limit da API do Telegram.
