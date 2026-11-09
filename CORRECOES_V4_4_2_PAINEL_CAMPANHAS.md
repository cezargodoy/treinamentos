# Gertec Academy v4.4.2 — correções do painel e campanhas

## Correções
- Corrigido o acesso à lista de conteúdos da campanha no painel do aluno (`track['items']`), evitando a colisão com o método nativo `dict.items` do Python/Jinja2.
- A edição de campanha agora permite selecionar grupos além dos perfis.
- Criada a associação persistente entre campanhas e grupos (`campaign_groups`).
- Ao salvar uma campanha, novos usuários elegíveis recebem as matrículas ainda inexistentes.
- Matrículas já existentes são preservadas para não apagar o progresso do aluno.
- Exclusão individual e exclusão em massa também removem as associações de grupos da campanha.
- A exclusão de campanhas continua removendo matrículas e eventos associados, preservando certificados históricos.

## Banco de dados
A tabela `campaign_groups` é criada pelo `Base.metadata.create_all(engine)` na inicialização. Nenhuma tabela existente é removida e nenhuma limpeza geral do PostgreSQL é executada.

## Validação
Verificações estáticas: compilação Python e carregamento dos templates Jinja2. A integração com o PostgreSQL de produção e o fluxo completo no Render precisam ser confirmados após o deploy.
