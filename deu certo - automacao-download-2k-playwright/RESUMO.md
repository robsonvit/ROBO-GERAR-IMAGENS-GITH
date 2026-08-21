# ✅ Deu Certo — Automação Download 2K Playwright (Google Labs Flow)

**Data:** 2026-08-21
**Projeto:** ROBO GERAR IMAGENS GITH

## O que funcionou

A interceptação e download de imagens geradas em 2K no Google Labs Flow usando Playwright no GitHub Actions. A solução final combinou três pilares fundamentais:
1. **Headful Mode + Xvfb:** Downloads nativos do Chrome (iniciados pela própria página via blob/fetch) muitas vezes falham no modo `headless=True` padrão do Playwright. Usar o `xvfb-run` no Ubuntu GitHub Actions com `headless=False` cria uma tela virtual que engana o Chrome e permite que o mecanismo nativo de downloads funcione 100%.
2. **Conflito de Depuradores:** Não podemos usar uma extensão Chrome que injeta eventos de mouse via `chrome.debugger` junto com o Playwright, pois ambos usam o protocolo de depuração (CDP). O Chrome bloqueia o segundo depurador. A solução foi remover a extensão e usar os cliques nativos do próprio Playwright.
3. **Loop Ativo de Wiggle (Polling de UI):** Imagens recém geradas no Google Labs aparecem primeiro como placeholders borrados. Se posicionarmos o mouse sobre elas e esperarmos, o evento de "hover" não é acionado quando a imagem real renderiza, e os botões de opções (3 pontos) nunca aparecem. A solução foi fazer um loop ativo que balança o mouse (`wiggle`) constantemente sobre a área da imagem até que o botão de 3 pontos finalmente apareça no DOM, garantindo sincronia perfeita com a finalização do upscaling.

## Arquivos envolvidos

| Arquivo | Papel na solução |
|---------|-----------------|
| `ui_automation.py` | Script principal do Playwright. Contém a configuração `headless=False`, a lógica de Wiggle ativo sobre o bounding box para capturar a renderização da imagem, os cliques encadeados (3 pontos -> Baixar -> 2K) e o `expect_download(timeout=150000)`. |
| `run_generation_workflow.yml` | Workflow do GitHub Actions. Instala o pacote `xvfb` no Ubuntu e aciona o script Python envelopado pelo comando `xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" python scripts/ui_automation.py`. |

## Como replicar

1. Sempre que for rodar automações que exigem downloads nativos não triviais ou detecção anti-bot, utilize o modo headful (`headless=False`) do Playwright associado ao `xvfb` em ambientes Linux/CI.
2. Em interfaces dinâmicas complexas (como React/Angular no Google Labs) onde elementos dependem de "hover" real sobre imagens carregadas assincronamente (lazy load/geração), nunca use waits estáticos sobre coordenadas fixas passadas. Use loops ativos (polling) que movimentam o mouse constantemente até que o elemento alvo brote no DOM.
3. Jamais tente carregar extensões baseadas em `chrome.debugger` dentro de um browser controlado pelo Playwright.

## Observações

- **Timeouts:** O upscaling 2K do Google pode demorar dependendo da carga do servidor deles. O `expect_download` foi ajustado para 150 segundos (2.5 minutos) por segurança.
- **Artefatos ZIP:** No GitHub Actions, o download 2K é pego pelo Playwright e salvo na pasta `output/`, e em seguida upado via `actions/upload-artifact@v4`.
