# Gertec Academy Enterprise — Fundação 4.0

Esta entrega inicia a modernização Enterprise sobre a aplicação existente, preservando o modelo de dados e os módulos já utilizados. **Não é uma declaração de prontidão para produção**: é a primeira etapa técnica, com persistência mais segura, auditoria inicial e tracking de aprendizagem para mídia direta compatível.

## O que entra nesta entrega

- **Persistência protegida:** em `APP_ENV=production`, a aplicação exige `DATABASE_URL` e recusa SQLite. Isso impede que o serviço use silenciosamente um banco local efêmero no container.
- **Segredo de sessão:** em produção, exige `SECRET_KEY` com pelo menos 32 caracteres.
- **Compatibilidade de banco:** criação aditiva das novas tabelas `learning_events` e `audit_logs` e da coluna `enrollments.watched_seconds`; não apaga tabelas ou registros existentes.
- **Eventos de aprendizagem:** grava play, pause, heartbeat, ended, seek e visibility_hidden vinculados à matrícula e ao usuário autenticado.
- **Tracking de vídeo:** para URL direta de mídia `.mp4` ou `.webm`, usa o player HTML5 e envia heartbeats ao backend. O progresso automático considera segundos assistidos e só conclui automaticamente quando há evento `ended` e pelo menos 90% da duração estimada foi acumulada.
- **Limite do SharePoint:** quando o conteúdo é um iframe de SharePoint/OneDrive, o navegador não pode ler eventos internos do player por isolamento cross-origin. Nessa modalidade o tracking automático não é alegado; continua disponível confirmação manual. Para rastreamento real de conteúdo corporativo, próxima etapa deve usar SCORM/xAPI ou integração de player autorizada.
- **Auditoria inicial:** registra edição de usuários e criação/edição de campanhas. Administradores consultam em `/admin/audit`.
- **Relatório:** CSV passa a incluir segundos assistidos.
- **Higiene de deploy:** `.dockerignore` e `.gitignore` excluem `__pycache__`, `.pyc`, bancos locais, `.env` e uploads locais do build/repositório.

## Antes de atualizar o Render

1. Faça backup do PostgreSQL existente. Não apague nem recrie o banco.
2. Confirme que `DATABASE_URL` aponta para o PostgreSQL persistente já utilizado pelo serviço.
3. Configure `APP_ENV=production`.
4. Configure `SECRET_KEY` com um segredo aleatório forte (mínimo 32 caracteres). **Não altere o valor atual sem planejar a invalidação das sessões existentes.**
5. Mantenha as variáveis Entra/Graph atuais. O SSO continua opcional.
6. Atualize os arquivos no repositório atual `treinamentos`, branch `main`. Não crie um novo serviço ou banco pelo Blueprint.
7. Após o deploy, confira `/health`, faça login e valide usuários, campanhas e matrículas existentes.

## Variáveis essenciais

- `DATABASE_URL`: PostgreSQL persistente (obrigatória em produção)
- `APP_ENV=production`
- `SECRET_KEY`: segredo forte para sessão
- `COOKIE_SECURE=true` em HTTPS
- `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET`, `ENTRA_REDIRECT_URI`: opcionais para SSO
- `ADMIN_EMAILS`, `HR_EMAILS`, `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`: conforme configuração existente

## Limitações e próxima etapa obrigatória

Esta é a fundação, não a plataforma Enterprise final. Ainda precisam ser entregues e testados: migrations versionadas (Alembic), proteção CSRF em todos os formulários, rate limiting e bloqueio de tentativas, fluxo seguro de recuperação de senha, armazenamento de fotos em Azure Blob, RBAC por grupo e escopo, trilha de auditoria para todas as operações, gestão de conteúdo/aulas, avaliações e tentativas, SCORM 1.2/2004 e xAPI, relatórios com filtros, moderação do fórum, notificações, testes automatizados e testes de carga/segurança.

O contador de segundos é evidência técnica do player HTML5 para URLs de mídia direta, mas não substitui um LMS SCORM/xAPI completo, nem comprova identidade presencial. A duração configurada no curso é usada como estimativa de referência. Para SharePoint incorporado não há acesso aos eventos internos sem uma integração Microsoft/player autorizada.

## Desenvolvimento local

```bash
pip install -r requirements.txt
# Para desenvolvimento local, sem APP_ENV=production, SQLite local é permitido.
uvicorn app:app --reload
```

Em produção, nunca use SQLite no filesystem efêmero do container.
