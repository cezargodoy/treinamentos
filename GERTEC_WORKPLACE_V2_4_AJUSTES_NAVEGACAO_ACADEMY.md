# Gertec Workplace v2.4 — Ajustes de navegação e jornada Academy

- Removido o atalho Gamificação do menu Workplace e do menu Academy.
- Gestão de Acessos e Configurações Gerais agrupadas sob Administração central.
- Auditoria removida da navegação principal e adicionada dentro de Configurações gerais.
- Rótulos de navegação simplificados para BPM, BCM e Jurídico.
- A ação Entrar como aluno agora redireciona para /academy.
- Painel inicial e logotipo Academy permanecem apontando para /academy, que resolve o painel conforme o modo administrador/aluno.
- Conteúdos de cada trilha exibidos em grade responsiva de três colunas (duas em tablet e uma em celular).
- Botão Editar configurações recebe estilo amarelo e fica ao lado de Excluir campanha.
- Conclusão de um conteúdo de campanha retorna à jornada Academy enquanto houver itens pendentes; certificados são acessados quando todos os conteúdos da campanha estiverem concluídos.
- O mesmo redirecionamento é aplicado à conclusão manual, avaliação aprovada e tracking de vídeo direto.

Validações locais: AST Python e parse de todos os templates Jinja concluídos. Não foi executado deploy nem teste de integração com PostgreSQL/Render.
