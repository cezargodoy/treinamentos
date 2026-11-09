# Correção 2.0.1 — Internal Server Error nos módulos

## Causa corrigida
O template base consultava `request.url.path` para escolher o menu, mas diversas rotas renderizavam páginas sem injetar `request` no contexto Jinja. Isso podia gerar `UndefinedError` e HTTP 500.

## Correção
- A decisão do shell de navegação agora é feita no helper central `render()`, com base no nome do template.
- O template base não depende mais de `request` para renderizar.
- O menu original do Academy permanece selecionado para os templates de aprendizagem.
- Workplace, BPM, GRC e BCM mantêm o shell central correspondente.

## Validação
- Sintaxe Python validada.
- Todos os templates Jinja compilados.
- Ainda é necessário executar teste de integração no ambiente Render.
