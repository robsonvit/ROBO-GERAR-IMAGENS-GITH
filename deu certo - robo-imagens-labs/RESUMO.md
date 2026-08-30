# Robô de Geração de Imagens (Google Labs Flow) - Correções e Sucesso

## O que estava falhando
- **Cookies Expirando no Loop**: O script navegava (`page.goto`) para a home page do Labs dentro do loop de prompts. Isso fazia o Google considerar uma nova navegação e perder a sessão.
- **Falso Positivo na Detecção**: Devido à navegação incorreta e o cache das imagens antigas, o robô achava que a imagem antiga era a nova.
- **Clique "Falso" no Download**: O clique em "2K" estava sendo feito via JavaScript (`element.click()`), o que era ignorado pela interface Angular/React do Google Labs e causava timeout.
- **Cookies Expirados**: O `AUTH_SESSION_JSON` original expirou no GitHub Secrets.

## Como foi resolvido
1. **Limpeza Inteligente da Tela**: Em vez de recarregar a página, o script agora clica no botão `+ Novo projeto` (mantendo a sessão viva) para limpar a tela para o próximo prompt.
2. **Hover Dinâmico e Busca Estável**: Melhoramos a busca pelo botão de 3 pontos para encontrar exatamente no canto superior direito do elemento da imagem que surge dinamicamente.
3. **Clique Físico (Mouse) em 2K**: Trocamos o clique JS pelo clique do mouse via Playwright (`page.mouse.click(x, y)`), garantindo que o sistema pegue o evento nativo corretamente.
4. **Atualização do Secret**: Novos cookies foram inseridos e testados via script local `extract_cookies.py`.

## Arquivos Salvos
- `ui_automation.py`: Contém a nova lógica do loop, clique nativo no botão de opções e download.
- `run_generation.yml`: Workflow configurado rodando background xvfb sem dar problemas de display.

## Status Final
O sistema agora roda totalmente independente e sem tela na nuvem. Pode enviar N prompts seguidos pelo Telegram e o script vai aguardar, gerar, baixar a versão alta resolução (2K) e enviar pro bot limpo!
