# Checklist de atualização segura — Gertec Academy

- [ ] Backup do PostgreSQL realizado e testado.
- [ ] `DATABASE_URL` aponta para o banco existente (não criar banco novo).
- [ ] `APP_ENV=production` configurado.
- [ ] `SECRET_KEY` existente preservada ou rotacionada de forma planejada.
- [ ] Repositório `cezargodoy/treinamentos`, branch `main`.
- [ ] Deploy concluído e commit esperado visível no Render.
- [ ] `/health` responde `{"status":"ok"}`.
- [ ] Login de administrador funciona.
- [ ] Usuários e campanhas anteriores continuam presentes.
- [ ] Uma matrícula de teste registra eventos e progresso em vídeo MP4/WEBM direto.
- [ ] A tela `/admin/audit` lista alterações administrativas.
- [ ] CSV inclui segundos assistidos.

Não aplicar Blueprint para criar um segundo serviço/banco. Atualizar o serviço existente conectado ao repositório atual.
