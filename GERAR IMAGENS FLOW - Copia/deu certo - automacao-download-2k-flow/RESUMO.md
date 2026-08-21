# ✅ Deu Certo — Automação de Download 2K no Google Flow

**Data:** 06/07/2026
**Projeto:** GERAR IMAGENS FLOW

## O que funcionou

A interface do Google Flow possui proteção forte contra cliques simulados via JavaScript DOM (`event.isTrusted = false`), ignorando cliques na UI do React para abrir o menu de download. A solução que funcionou foi utilizar a API **`chrome.debugger`** no background (`service-worker.js`) para despachar eventos de mouse físicos (Input.dispatchMouseEvent).

Além disso, a lógica de busca dos botões (Dots, Baixar, 2K) foi refinada para:
1. Procurar o botão `⋮` (Mais opções) delimitando uma caixa espacial estrita de coordenadas exatamente no canto superior direito da imagem gerada.
2. Procurar os itens do menu (Baixar / 2K) fazendo o loop de forma reversa (de baixo para cima na árvore do DOM) usando `els.reverse()`, e limitando o `querySelectorAll` a elementos de lista e de menu (`li`, `[role="menuitem"]`), evitando assim o clique na nossa própria UI da extensão.

## Arquivos envolvidos

| Arquivo | Papel na solução |
|---------|-----------------|
| `manifest.json` | Adicionada permissão `"debugger"` para que o service-worker consiga assumir o mouse. |
| `background/service-worker.js` | Recebe a requisição do content, faz `chrome.debugger.attach()`, move o mouse milimetricamente (`Input.dispatchMouseEvent`) e rastreia na tela o botão `⋮`, o item `Baixar` e depois o submenu de `2K` para efetuar o clique físico final e `chrome.debugger.detach()`. |
| `content.js` | Quando identifica a nova imagem, despacha a mensagem `DEBUGGER_2K_DOWNLOAD` para o background script e aguarda a finalização (inclui também o atalho de debug Ctrl+Shift+Y). |

## Como replicar

1. Adicione `"debugger"` nas permissões do `manifest.json`.
2. O script que tem acesso ao DOM envia um ID (ou uma url de imagem para que o background calcule a posição inicial) via message.
3. No background, atache o debugger à aba atual.
4. Execute `chrome.debugger.sendCommand(target, "Runtime.evaluate")` para injetar funções utilitárias que varrem a tela em busca de posições (`getBoundingClientRect`).
5. Ao obter o `{cx, cy}` do elemento, mova o mouse para lá (`type: "mouseMoved"`) e envie um click composto por mousedown/mouseup (`type: "mousePressed"`, `type: "mouseReleased"`) e espere ~500ms para a animação da UI ocorrer antes do próximo clique.

## Observações

- **Extension context invalidated:** Lembre-se de sempre dar um `F5` na aba do Google Flow imediatamente após recarregar a extensão, pois caso contrário o `content.js` antigo tenta falar com o novo worker e falha.
- **Botões com textos iguais:** O Google Flow usa a palavra "Aumentada" tanto para 2K quanto para 4K, por isso usamos uma RegExp estrita apenas para a string '2k' ao caçar a opção final.
- Durante o fluxo, o Chrome exibirá um banner no topo avisando "O [Nome da Extensão] começou a depurar este navegador". É comportamento padrão de segurança e desaparece automaticamente após o `detach()`.
