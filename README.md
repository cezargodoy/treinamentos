# Gertec Academy — versão ampliada

Plataforma corporativa de aprendizagem em FastAPI, SQLAlchemy e PostgreSQL, com interface em português e identidade visual Gertec (azul institucional e amarelo).

## Novos recursos desta versão

- **Grupos de usuários:** RH/administrador cria grupos, inclui ou remove participantes e direciona campanhas para grupos selecionados. Se nenhum grupo for escolhido na campanha, ela é distribuída a todos os colaboradores ativos.
- **Perfis e permissões por módulo:** administrador, RH, gestor e colaborador. O administrador pode habilitar/desabilitar módulos por perfil em `/admin/permissions`; as verificações são aplicadas no backend. Administradores mantêm acesso total.
- **Perfil e diretório:** usuário altera a própria foto (JPG, PNG ou WebP, até 3 MB) e localiza colegas por nome/departamento.
- **Fórum:** criação de tópicos e respostas entre usuários autenticados.
- **Disponibilidade dos cursos:** data/hora de início e encerramento, interpretadas no fuso `America/Sao_Paulo`. Cursos fora da janela não podem ser acessados.
- **Progresso individual:** o primeiro acesso marca o curso como iniciado; o colaborador pode atualizar manualmente o percentual e registrar conclusão. O dashboard mostra o progresso médio e por curso.
- **Relatório CSV:** exporta somente matrículas iniciadas, com nome, e-mail, departamento, grupos, treinamento, percentual, status, data de início, última atividade, conclusão, atribuição e campanha.

## Rotas principais

- `/login` — login padrão e botão SSO opcional.
- `/setup` — criação do primeiro administrador, somente quando o banco ainda não possui usuários.
- `/admin/users` — cadastro de usuários.
- `/admin/groups` — gestão de grupos e participantes.
- `/admin/permissions` — permissões por perfil (administrador).
- `/directory` — diretório de colaboradores.
- `/forum` — fórum corporativo.
- `/profile` — foto e perfil do usuário.
- `/courses` — biblioteca e cadastro de cursos (RH/administrador).
- `/campaigns` — campanhas por curso e grupo.
- `/reports` e `/reports.csv` — indicadores e exportação.

## Variáveis de ambiente

Mantenha as variáveis já utilizadas no deploy: `DATABASE_URL`, `SECRET_KEY`, `COOKIE_SECURE`, `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET`, `ENTRA_REDIRECT_URI`, `ADMIN_EMAILS`, `HR_EMAILS`, `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID` e `GRAPH_CLIENT_SECRET`. O SSO continua opcional: sem as variáveis `ENTRA_*`, o login padrão funciona.

## Deploy

1. Faça backup do banco PostgreSQL antes de atualizar.
2. Substitua os arquivos do repositório pelo conteúdo deste pacote e faça commit.
3. O Render deve iniciar novo deploy. As migrações aditivas criam as novas colunas e tabelas; ainda assim, faça backup antes.
4. Confirme `DATABASE_URL` apontando para PostgreSQL persistente e `SECRET_KEY` forte. Não use SQLite em produção no Render.
5. Crie/valide a conta administradora e configure permissões e grupos.

## Limitações importantes antes de produção

- O percentual de progresso é atualizado pelo colaborador e a abertura do curso marca o início. **Não há telemetria automática do vídeo**, portanto não é prova técnica de que o vídeo foi assistido integralmente. Para isso, integrar player compatível com xAPI/SCORM ou mecanismo de tracking aprovado.
- As fotos são salvas em `static/uploads`. Em Render sem disco persistente, uploads locais podem ser perdidos em novo deploy/restart. Para produção, conectar Azure Blob Storage ou SharePoint/OneDrive via Microsoft Graph.
- O fórum nesta versão tem tópicos e respostas, mas ainda não tem moderação avançada, denúncias, anexos, mensagens privadas ou notificações.
- Permissões são por perfil e módulo; grupos atualmente segmentam o direcionamento de campanhas, não substituem RBAC por grupo.
- Antes de produção corporativa, implementar proteção CSRF, rate limiting, trilha de auditoria, política de retenção, revisão LGPD, antivírus para uploads, política de senha/reset e testes de carga/segurança.
- O SSO Microsoft continua opcional e separado do login local. A sincronização Graph requer consentimento administrativo e permissões de aplicação configuradas no Entra ID.

## Atualizações desta versão
- Administração exclusiva para editar contas: `/admin/users/{id}/edit` permite alterar nome, e-mail, departamento, perfil, status ativo/inativo e senha. RH pode cadastrar e consultar, mas não alterar configurações existentes.
- Administrador pode alternar entre visão administrativa e visão de aluno pelo botão no dashboard. Na visão de aluno, a plataforma cria matrículas pessoais para os cursos publicados para permitir testar o fluxo de aprendizagem; isso gera registros reais de matrícula e deve ser considerado nos relatórios.
- Campanhas podem ser direcionadas simultaneamente a múltiplos perfis de acesso. A seleção de grupos também pode ser combinada com os perfis.
- Apenas administrador pode criar ou editar configurações de campanhas. Cada campanha exibe uma barra com a média do progresso das matrículas vinculadas.
- A edição de campanhas altera metadados e associações de cursos/perfis; matrículas históricas existentes não são removidas automaticamente para preservar evidências de aprendizagem.
