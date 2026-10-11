# ✅ Deu Certo — Bot Telegram com Google Flow 2K e Barra de Progresso em Tempo Real

**Data:** 10/10/2026 23:35  
**Projeto:** ROBO-GERAR-IMAGENS-GITH  

## O que funcionou

A automação completa de geração de imagens no **Google Flow** em resolução **2K** via **Telegram**, rodando 100% na nuvem através do **GitHub Actions** e **Google Apps Script**, sem necessidade do computador local estar ligado ou com internet:
1. **Comando de Proteção:** Exige o comando `/flow <prompt>` ou `/gerar <prompt>` para evitar disparos acidentais ao enviar texto aleatório.
2. **Feedback Progressivo em Tempo Real:** O Apps Script responde imediatamente criando uma mensagem com a barra de progresso inicial (`[░░░░░░░░░░] 0%`) e repassa o `message_id` para o GitHub Actions. O Playwright edita progressivamente a mesma mensagem conforme as etapas são executadas (`5%` -> `25%` -> `35%` -> `60%` -> `85%` -> `90%` -> `100%`).
3. **Download 2K Nativo:** Faz o hover no card da imagem gerada, clica no botão de opções ⋮ (específico do card, evitando clicar no menu do cabeçalho do projeto), passa o mouse em "Fazer o download", clica em "2K" e intercepta o download oficial do arquivo em altíssima resolução.
4. **Entrega no Telegram:** Envia o arquivo de imagem diretamente para o chat do usuário no Telegram e finaliza o status como 100% concluído.

## Arquivos envolvidos

| Arquivo | Papel na solução |
|---------|-----------------|
| `codigo_google_script.js` | Webhook do Telegram hospedado no Google Apps Script. Filtra os comandos `/flow` / `/gerar`, envia a mensagem com barra de progresso inicial (`0%`) e despacha o evento via API do GitHub Actions com `prompt`, `chat_id` e `message_id`. |
| `ui_automation.py` | Script Playwright que executa na máquina virtual Linux do GitHub Actions. Injeta os cookies da conta Google, navega no Google Flow, digita o prompt no editor ProseMirror, aguarda a geração, faz o download em 2K e edita o status no Telegram a cada etapa. |
| `run_generation.yml` | Workflow do GitHub Actions (`workflow_dispatch`). Configura o ambiente Ubuntu, instala dependências e navegadores Playwright, lê os segredos (`AUTH_SESSION_JSON`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) e executa a automação. |

## Como replicar

1. **Configurar o Google Apps Script:**
   - Inserir o `TELEGRAM_TOKEN`, o `GITHUB_TOKEN` com escopos `repo` e `workflow`, e o repositório `GITHUB_REPO`.
   - Fazer deploy como Web App (Executar como: "Eu", Quem tem acesso: "Qualquer pessoa").
   - Configurar o Webhook do Telegram apontando para o URL gerado pelo deploy:
     `https://api.telegram.org/bot<TOKEN>/setWebhook?url=<URL_EXEC>`
2. **Configurar os Secrets no GitHub:**
   - `AUTH_SESSION_JSON`: JSON com os cookies exportados da conta Google logada no Flow (`flow.google.com`).
   - `TELEGRAM_BOT_TOKEN`: Token do bot criado no @BotFather.
   - `TELEGRAM_CHAT_ID`: ID do chat de destino para notificações padrão.
3. **Enviar comandos no Telegram:**
   - Enviar `/flow Um carro esportivo voando em uma cidade cyberpunk luzes neon 4k`
   - O bot responde imediatamente com `0%` e vai atualizando até entregar a foto em 2K.

## Observações

- **Menu ⋮ no Google Flow:** O seletor utilizado é `button[flowhotbarbutton][aria-label*="opções" i]`, o que evita qualquer clique incorreto no menu ⋮ geral do projeto no topo da página.
- **Persistência de Sessão:** Os cookies da sessão Google precisam estar válidos. Se a sessão expirar, basta exportar novamente os cookies atualizados no formato JSON e atualizar o secret `AUTH_SESSION_JSON`.
