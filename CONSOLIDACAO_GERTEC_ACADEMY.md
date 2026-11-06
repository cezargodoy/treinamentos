# Gertec Academy — pacote consolidado

Este pacote combina a versão com Dashboard Analítico com a correção pontual da sessão SQLAlchemy na rota `/learn/{cid}`.

## Preservado
- Dashboard administrativo analítico (KPIs, evolução de conclusões, status das matrículas, progresso por departamento e conteúdos mais acessados).
- Perfil editável e persistência de foto no PostgreSQL.
- Fórum e funcionalidades existentes.
- Biblioteca de conteúdo e avaliações (questões certo/errado, nota mínima, tentativas e publicação).
- Gamificação com link externo para Giga Quizzes.
- Campanhas, matrículas, tracking e relatórios existentes na versão-base do dashboard.

## Correção aplicada
A rota `/learn/{cid}` agora renderiza `learn.html` antes de fechar a sessão SQLAlchemy, mantendo os dados ORM necessários ao `base.html` disponíveis durante a renderização. O código mantém a consulta da avaliação, questões e indicador de vídeo direto que existiam na versão analítica.

## Validações executadas
- `app.py`: compilação Python (`py_compile`) aprovada.
- Templates Jinja: compilação/carregamento de todos os templates aprovada.
- Verificações estáticas: dashboard, avaliações, perfil, foto persistente, gamificação e correção da sessão encontrados.

## Antes de publicar
1. Faça backup do PostgreSQL no Render.
2. Extraia o ZIP e confira a pasta `treinamentos-main`.
3. Substitua o conteúdo do repositório local pelos arquivos desta pasta.
4. Faça commit e push para a branch configurada no Render.
5. Confirme o deploy e teste o dashboard administrativo e `/learn/1` e `/learn/2`.

Este pacote não executou teste integrado contra o PostgreSQL nem teste real no Render. Não exclua nem recrie o banco. Se o erro persistir, capture o novo traceback do Render.
