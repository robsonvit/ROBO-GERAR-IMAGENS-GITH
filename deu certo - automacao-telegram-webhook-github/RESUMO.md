# ✅ Deu Certo — Automação Telegram Webhook ao GitHub (Com Barra de Progresso)

**Data:** 21/08/2026
**Projeto:** Robô Gerador de Imagens (Github Actions + Playwright)

## O que funcionou

A migração de um servidor local em loop (`bot_listener.py`) para um webhook serverless no **Google Apps Script** rodando 24h sem custo. O sistema inteiro precisou de fortes escudos para lidar com os constantes "retries" do Telegram quando ocorrem pequenos atrasos na API do GitHub. 
O segredo do sucesso foi a combinação de 3 coisas:
1. Um bloqueio anti-clones no Google usando `CacheService` que ignora IDs de mensagens repetidas do Telegram.
2. O uso do parâmetro `concurrency: cancel-in-progress: true` no Workflow do GitHub para esmagar rodadas sobrepostas.
3. A criação de uma barra de progresso ascii em tempo real editando a mesma mensagem no Telegram usando `editMessageText` diretamente pelo Playwright em Python.

## Arquivos envolvidos

| Arquivo | Papel na solução |
|---------|-----------------|
| `codigo_google_script.js` | É o webhook (doPost) que recebe o Telegram, bloqueia os clones e bate no Github via `dispatches`. |
| `run_generation.yml` | Arquivo do Github Actions (Workflow) responsável por criar a máquina na nuvem e cancelar clones pela concorrência. |
| `ui_automation.py` | Script Python do bot do Playwright. Alterado para criar mensagens dinâmicas (`[███░░░] 30%`) atualizando os estágios no Telegram. |

## Como replicar

1. Basta colar o código `.js` num Web App do Google Apps Script configurado com "Acesso: Qualquer Pessoa".
2. Linkar a URL do Web App ao Token do Telegram (usando o método `setWebhook` da API do Telegram).
3. Todo comando enviado no Telegram acionará o script do Google, que vai disparar um `workflow_dispatch` no Github Actions passando o Prompt e o Chat ID.
4. O GitHub sobe a máquina, roda o Python, atualiza o status dinâmico enviando HTTP POST pro bot, gera a imagem, e faz o download.

## Observações

- **Cuidado ao atualizar Web Apps no Google:** Se atualizar muitas vezes gerando "novas versões", as permissões bugam e mudam sozinhas para "Apenas eu", gerando o Erro 302 (Redirecionamento de Login) e quebrando o Telegram. Para arrumar, precisa criar uma *Nova Implantação* do zero.
- A API do Github `dispatches` é rápida, mas exige permissão de token (`GITHUB_TOKEN` com escopo `repo`).
- O Telegram tem Timeout em webhooks de cerca de 10-15s, daí a importância do script não esperar muito tempo de serviços lentos e de sempre usar bloqueios de ID.
