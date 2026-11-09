# Gertec BPM — primeira entrega integrada

## Escopo implementado
- Novo módulo Gertec BPM acessível pelo menu lateral do Gertec Academy em `/bpm`.
- Visão inicial da cadeia de valor com filtros por categoria, busca e expansão dos grupos.
- Cadastro inicial idempotente de macroprocessos e processos com base na imagem de referência.
- Página de detalhe de cada processo, com hierarquia e indicação das próximas capacidades (BPMN, playbooks e indicadores).
- Inclusão de subprocessos por usuários com perfil administrativo/gestor/RH.
- Persistência em tabela própria `bpm_processes`, sem misturar dados com cursos/campanhas.
- Registro de auditoria ao incluir processos.

## Dados iniciais
A carga é executada na inicialização somente quando a tabela `bpm_processes` está vazia. São carregados os grupos da cadeia de valor, processos secundários, fornecedores, apoio estratégico e qualidade/compliance/segurança.

## Rotas
- `GET /bpm` — cadeia de valor
- `GET /bpm/process/{id}` — detalhe do processo
- `POST /bpm/process` — inclusão de processo/subprocesso (admin, RH ou gestor)

## Próximas etapas recomendadas
1. Editor BPMN 2.0 com BPMN.js e versionamento de modelos.
2. Motor de workflow com instâncias, tarefas, aprovações, prazos e trilha de auditoria.
3. Playbooks com checklists, anexos, evidências e critérios de conclusão.
4. Indicadores de SLA, lead time, gargalos e painéis por área.
5. Integração documental com SharePoint e controle de acesso granular por área.

## Observação de implantação
A atualização mantém o banco existente e cria a tabela nova via `Base.metadata.create_all`. Faça backup do banco e valide primeiro em homologação antes de publicar em produção.
