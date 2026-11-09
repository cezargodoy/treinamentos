# Gertec BPM v1.2 — Documentação, trilhas e modelagem BPMN

## Novidades
- Repositório documental por processo/subprocesso, com upload de PDF, visualização inline e download.
- PDFs armazenados em tabela própria no PostgreSQL, com limite de 25 MB por arquivo.
- Associação de cursos publicados do Gertec Academy a uma trilha de aprendizagem do processo.
- Associação opcional de conteúdo externo via HTTPS.
- Editor visual BPMN 2.0 embarcado com bpmn-js Modeler: paleta de elementos, eventos, tarefas, gateways, raias e conexões.
- Importação e exportação de arquivos BPMN/XML.
- Persistência do diagrama BPMN por processo no PostgreSQL.
- Registro de auditoria para upload documental, vínculo de aprendizagem e salvamento do diagrama.

## Como utilizar
1. Atualize o código no repositório conectado ao Render e faça deploy.
2. Abra Gertec BPM e selecione um processo ou subprocesso.
3. Na aba Documentação, faça upload dos PDFs oficiais.
4. Na aba Trilha de aprendizagem, associe cursos publicados no Gertec Academy ou links HTTPS.
5. Na aba Modelagem visual, desenhe o processo e clique em Salvar diagrama.

## Notas técnicas
- As novas tabelas são criadas pelo `Base.metadata.create_all(engine)` na inicialização; não exige apagar ou recriar o banco.
- Arquivos PDF são persistidos como BYTEA no PostgreSQL. Avalie política de retenção e limites de armazenamento antes de uso em larga escala.
- O editor BPMN carrega bpmn-js 17.11.1 pelo CDN unpkg. O navegador dos usuários precisa acessar unpkg.com. Para ambientes sem acesso externo, hospede as bibliotecas localmente.
- Esta versão entrega documentação, associação de cursos e modelagem visual. Ainda não executa automaticamente workflows BPMN nem possui integração de matrícula/progresso do curso vinculada à conclusão do processo.
