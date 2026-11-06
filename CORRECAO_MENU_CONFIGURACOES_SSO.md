# Correção — acesso às Configurações Gerais / SSO

- Adicionado ao menu lateral, visível somente para administradores, o link **Configurações gerais** (`/admin/settings`).
- A tela existente permite configurar idioma, Tenant ID, Client ID e Client Secret do Microsoft Entra ID, além de SMTP.
- Corrigido o ciclo da sessão na rota da tela para renderizar o template antes de fechar a sessão SQLAlchemy.
- A sincronização de usuários permanece acessível pelo botão dentro da tela de configurações.

Observação: a tela e as rotas de configuração já existiam na versão anterior; o problema era a ausência do link no menu lateral. A conexão real com Entra ID depende de registrar o Redirect URI e conceder as permissões necessárias no tenant Microsoft.
