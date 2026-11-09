# Gertec Academy — ajustes funcionais v4.3.0

- Removidos da Biblioteca de conteúdo os campos de início e encerramento; a disponibilidade passa a ser definida na campanha.
- Padronizado o nome da área como “Campanhas de aprendizagem”.
- Campanhas passam a ter disponibilidade inicial e encerramento, com validação de intervalo. O campo “Data limite” foi retirado das telas de criação e edição.
- Grupos passam a ter perfil de acesso (Colaborador, Gestor ou RH). O perfil do grupo participa da autorização de módulos e rotas dos seus membros; administradores continuam sendo atribuídos somente diretamente ao usuário.
- Configurações gerais passam a salvar fuso horário, com opções brasileiras e UTC. O fuso configurado é utilizado na validação do período das campanhas.
- A seleção de idioma já altera os rótulos da navegação principal. A tradução de todos os textos internos de cada módulo ainda requer expansão do catálogo de traduções.

As alterações de banco são aditivas e preservam registros existentes. As colunas antigas de disponibilidade dos cursos e `due_date` das campanhas são mantidas por compatibilidade, mas deixam de ser usadas na interface.
