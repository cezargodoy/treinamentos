# Gertec Workplace v1.6 — Gertec BCM

## Módulo incluído
- Novo módulo Gertec BCM no menu lateral e no dashboard Workplace.
- BIA: cadastro de atividades/processos, área, responsável, descrição, MTPD, RTO, RPO, impactos financeiro/operacional/reputacional, dependências e recursos mínimos.
- Criticidade inicial calculada por regra provisória baseada no MTPD.
- Importação de planos BCP e DRP em PDF, DOC/DOCX, XLS/XLSX e PPT/PPTX, até 30 MB.
- Armazenamento de arquivos e metadados no PostgreSQL.
- Visualização e download dos arquivos importados.
- Status documental: Rascunho, Em revisão, Aprovado e Obsoleto.
- Log de auditoria para criação BIA, importação e mudança de status.

## Deploy
1. Faça backup do banco e do repositório.
2. Atualize o projeto conectado ao Render com os arquivos deste ZIP.
3. Faça commit e push e aguarde o deploy.
4. Acesse `/bcm` e valide com perfis admin/gestor/RH.
5. Importe cópias de teste dos planos antes de incluir documentos oficiais.

## Limitações
- A importação preserva o arquivo original; não extrai automaticamente o conteúdo nem converte o plano em tarefas.
- Ainda não há workflow formal de aprovação, exercícios/testes, calendário, acionamento de crise, árvore de chamadas ou execução técnica de DR.
- Os documentos ficam no PostgreSQL como BYTEA. Para grande volume, recomenda-se SharePoint ou armazenamento de objetos corporativo.
- A regra de criticidade é provisória. A organização deve aprovar escalas de impacto e critérios BIA antes do uso oficial.
