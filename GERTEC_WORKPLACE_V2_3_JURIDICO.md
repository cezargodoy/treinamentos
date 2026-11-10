# Gertec Workplace v2.3 — Módulo Jurídico

## Funcionalidades
- Novo módulo Gertec Jurídico na navegação do Workplace, respeitando a configuração global de módulos.
- Abertura de solicitações por qualquer usuário autenticado: contratos, NDA, aditivos, distratos, procurações, pareceres, notificações e consultas.
- Registro de solicitante, área, parceiro/cliente, tipo de relacionamento, prioridade, responsável, descrição e anexo.
- SLA manual por solicitação, em horas (1 a 8760), contado a partir da criação.
- Indicadores: volume total, solicitações em andamento, concluídas no SLA, vencidas/fora do SLA, tempo médio de atendimento e volume de contratos/NDA.
- Sinalização de SLA: verde (dentro do prazo), amarelo (até 8 horas para vencer), vermelho (estourado ou concluído fora do prazo) e roxo (concluído no prazo).
- Atualização de status, responsável e SLA por usuários com perfil admin, RH, gestor ou membro de grupo com perfil Jurídico.
- Perfil Jurídico disponível na configuração de grupos e na matriz de permissões por módulo.
- Solicitantes comuns visualizam apenas suas próprias solicitações; perfis Jurídico, RH, gestor e admin visualizam a fila completa.
- Anexos de até 20 MB armazenados no banco de dados.
- Registro de abertura e atualização na trilha de auditoria existente.

## Persistência e implantação
- Nova tabela `legal_tickets`, criada de forma aditiva por `Base.metadata.create_all`.
- Não remove, recria ou altera dados das tabelas existentes.
- A disponibilidade global do módulo pode ser controlada em Configurações > Disponibilidade global dos módulos.
- Fazer backup do PostgreSQL antes do deploy, publicar os arquivos e validar a criação de solicitação, anexos, atualização de status e cálculo de SLA.

## Validações executadas
- `python -m py_compile app.py`: aprovado.
- Templates Jinja `base.html`, `legal.html`, `settings.html`, `groups.html` e `workplace_access.html`: carregados e compilados.
- O teste de inicialização completa do FastAPI não foi executado neste ambiente: a dependência `authlib` não está instalada aqui. Validar no ambiente Render após deploy.

## Observações
- O SLA desta primeira entrega é contado em horas corridas, não em horas úteis/calendário de expediente.
- Os anexos são armazenados no PostgreSQL; integração de documentos com SharePoint e notificações automáticas por e-mail/Teams podem ser evoluídas posteriormente.
