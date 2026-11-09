# Gertec Academy v4.4.4 — thumbnails opcionais

- Campo opcional de imagem de capa no cadastro de conteúdo.
- Formatos aceitos: JPEG, PNG e WebP; limite de 5 MB.
- Validação de assinatura do arquivo e MIME informado.
- Armazenamento no PostgreSQL, sem depender de disco efêmero do Render.
- Endpoint autenticado respeita acesso administrativo/RH ou matrícula do aluno.
- A imagem aparece na biblioteca, seleção de conteúdos das campanhas, edição de campanhas, painel do aluno e cabeçalho da pré-visualização.
- Dimensão visual preservada em 105 × 80 px; `object-fit: cover` mantém proporção e recorta o excedente sem distorção.
- Sem imagem, permanece o bloco azul e o ícone/identificador atual.
- Migração aditiva cria `thumbnail_data` e `thumbnail_mime` em bancos existentes; não remove dados.
