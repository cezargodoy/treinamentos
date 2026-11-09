# Gertec BPM v1.3 — BPMN hospedado internamente

## Alteração
O editor bpmn-js continua com a mesma experiência e versão 17.11.1, mas os arquivos JavaScript e CSS agora são incluídos na imagem Docker da aplicação e servidos pelo próprio Gertec Academy em `/static/vendor/bpmn-js/`.

## O que muda
- Removida a dependência do navegador em `unpkg.com`.
- Os estilos e o JavaScript do editor passam a usar caminhos locais `/static/vendor/bpmn-js/...`.
- A imagem Docker baixa o pacote oficial `bpmn-js@17.11.1` durante a etapa de build, copia `dist/` para a imagem final e não precisa acessar o CDN quando o usuário abre o modelador.
- Os diagramas continuam armazenados no PostgreSQL Gertec.
- Não há envio de diagramas ao bpmn.io nem serviço SaaS de modelagem.

## Deploy
1. Atualize o repositório GitHub conectado ao Render com todos os arquivos deste pacote.
2. Faça commit e push.
3. Execute um deploy que reconstrua a imagem Docker (não use somente restart).
4. Abra um subprocesso e confira no navegador, em Network, que os arquivos `bpmn-modeler.production.min.js` e os CSS são carregados do domínio do próprio Gertec Academy.

## Nota operacional
A etapa Docker de build precisa acessar o npm registry para obter a versão fixada do pacote. Depois de construída, a aplicação serve os assets localmente e não depende de `unpkg.com` em tempo de execução. O Dockerfile anterior já buscava fontes de assinatura no GitHub durante o build; essa característica foi mantida.

## Segurança e licença
A versão do pacote está fixada em 17.11.1. Atualizações devem ser controladas e testadas. Preserve os avisos de licença e copyright exigidos pelo projeto bpmn.io/BPMN.js. A hospedagem local reduz dependência externa no navegador, mas não substitui CSP, controle de acesso, validação de arquivos BPMN, revisão de dependências e testes de segurança.
