# Gertec Workplace v1.9 — GRC e BCM

## GRC
- Inventário de riscos corporativos, probabilidade x impacto (1–5), score inerente, estratégia de tratamento, score residual, responsável, prazo e status.
- Cadastro de requisitos/controles por framework (ISO 27001, ISO 9001, ISO 22301, LGPD, PCI DSS, OEA e políticas internas), aplicabilidade, implementação e URL de evidência (ex.: SharePoint).
- Registro de apontamentos de auditoria/não conformidades com severidade, responsável, plano de ação, prazo e acompanhamento de status.
- Auditoria de eventos de criação e atualização por meio do mecanismo de auditoria existente.

## BCM
- Mantém BIA e importação de planos BCP/DRP existentes.
- Adiciona inventário de recursos/dependências (sistemas, infraestrutura, fornecedores, pessoas-chave, instalações, dados e telecom), RTO/RPO e procedimento de recuperação.
- Adiciona registro de exercícios de continuidade, tipo, escopo, data, coordenador e ações esperadas.

## Implantação
- Migração aditiva via SQLAlchemy create_all; novas tabelas: grc_risks, grc_controls, grc_findings, bcm_resources, bcm_exercises.
- Não apaga tabelas existentes. Faça backup do PostgreSQL antes do deploy.
- Acesse /grc e /bcm após o deploy.

## Limites desta versão
- Os frameworks e requisitos precisam ser cadastrados e validados pela área responsável; não existe biblioteca normativa completa pré-carregada.
- O score de risco é uma matriz simples 5x5, que deve ser alinhada à metodologia corporativa aprovada.
- A URL de evidência permite referenciar SharePoint, mas não há integração Microsoft Graph nesta entrega.
- Importar BCP/DRP armazena o documento; não extrai nem interpreta automaticamente o conteúdo.
- Não há ainda fluxo formal de aprovação com segregação de funções, workflow de aceite de risco, plano de tratamento vinculado a controles, notificações automáticas, nem agendamento/execução de testes técnicos.
- O score de criticidade BIA existente permanece uma regra provisória baseada em MTPD; deve ser calibrado com as áreas de negócio.
