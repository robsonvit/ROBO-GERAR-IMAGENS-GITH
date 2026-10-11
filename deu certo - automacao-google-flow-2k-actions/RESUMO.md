# ✅ Deu Certo — Automação Google Flow 2K no GitHub Actions

**Data:** 2026-10-10 22:40 (BRT)  
**Projeto:** ROBO GERAR IMAGENS GITH (robsonvit/ROBO-GERAR-IMAGENS-GITH)

## O que funcionou

A migração completa da geração de imagens para o **Google Flow** (`https://flow.google.com/`) rodando 100% na nuvem via **GitHub Actions**, sem precisar do computador local ligado.
1. **Autenticação via Cookies (Cookie-Editor):** O JSON completo exportado do navegador Chrome foi configurado no segredo `AUTH_SESSION_JSON` do GitHub Secrets. O Playwright sanitiza e injeta os cookies diretamente no contexto em ambiente Linux headless (`xvfb-run`), autenticando na conta PRO do usuário.
2. **Navegação Resiliente no Flow Studio:** Se a página abrir na apresentação (`/about`), clica automaticamente em `Create with Google Flow`. Em seguida, abre/cria o projeto com `button.new-project-button` ou card existente, revelando o editor Slate/ProseMirror (`div[contenteditable="true"].ProseMirror`).
3. **Submissão Universal via Tecla Enter:** O prompt é digitado suavemente com `press_sequentially()` e enviado instantaneamente com `page.keyboard.press("Enter")`.
4. **Detecção e Interceptação de Download 2K:**
   - Detecta o surgimento do novo card de imagem gerado pelo Flow (`img[src*="/asb/"]` ou `flow-content.google`).
   - Faz hover sobre a imagem para despertar a hotbar.
   - Clica no botão de 3 pontos do card usando o seletor exclusivo `button[flowhotbarbutton][aria-label*="opções" i], button[flowhotbarbutton]:has-text("more_vert")` com `force=True` (evitando clicar acidentalmente no menu de título do projeto no topo).
   - Passa o mouse sobre `"Fazer o download"` para desdobrar o submenu.
   - Clica na opção `"2K"` dentro de um bloco nativo `page.expect_download(timeout=120000)`.
   - Salva a imagem em alta definição em `output/` e envia diretamente para o Telegram do usuário.
5. **Integração Telegram 24h:** O webhook no Google Apps Script (`codigo_google_script.js`) recebe prompts diretamente pelo Telegram e despacha o workflow `run_generation.yml` via API do GitHub Actions, atualizando barra de progresso em tempo real.

## Arquivos envolvidos

| Arquivo | Papel na solução |
|---|---|
| `scripts/ui_automation.py` | Script principal em Playwright Python com injeção de cookies, digitação no ProseMirror, hover de hotbar, clique forçado no menu e interceptação nativa do download 2K. |
| `.github/workflows/run_generation.yml` | Workflow do GitHub Actions com ambiente Ubuntu + Xvfb, injeção segura do secret `AUTH_SESSION_JSON` em `state.json` e upload dos artefatos em caso de sucesso/debug. |
| `codigo_google_script.js` | Webhook do Telegram no Google Apps Script que dispara o workflow `run_generation.yml` no GitHub Actions a cada mensagem recebida. |

## Como replicar

1. No navegador logado na conta Google com acesso ao Flow, exporte todos os cookies com a extensão **Cookie-Editor** em formato JSON.
2. Configure o segredo no GitHub Actions com o comando:
   ```bash
   gh secret set AUTH_SESSION_JSON < cookies.json
   ```
3. Garanta que o workflow utilize `xvfb-run` para rodar o Chromium com display virtual:
   ```bash
   xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" python scripts/ui_automation.py
   ```
4. Para acionar manualmente via CLI:
   ```bash
   gh workflow run run_generation.yml -f prompt="Seu prompt aqui"
   ```

## Observações

- **Seletor de 3 Pontos:** Nunca use seletores genéricos como `button:has-text("more_vert").first`, pois o menu do projeto no topo da página fica em `y=18` e possui o mesmo ícone. Sempre use o seletor `button[flowhotbarbutton]` ou filtre por `y > 50`.
- **Download 2K:** O upscaling 2K do Google Flow pode levar de 30 a 90 segundos dependendo da fila dos servidores. O `timeout=120000` (2 minutos) no `expect_download` garante margem de segurança total.
