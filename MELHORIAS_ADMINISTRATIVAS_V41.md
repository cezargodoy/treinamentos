# Gertec Academy — melhorias administrativas v4.1

## Incluído nesta atualização
- Barra de rolagem vertical independente no menu lateral.
- Configurações gerais com preferência de idioma, parâmetros do Microsoft Entra ID e SMTP.
- Segredos do Entra ID e SMTP criptografados em repouso usando Fernet derivado de SECRET_KEY.
- Login SSO lê a configuração armazenada; sincronização Microsoft Graph usa Tenant ID, Client ID e Client Secret configurados na tela.
- Sincronização de usuários faz correspondência por Object ID e, quando necessário, por e-mail para atualizar contas locais existentes.
- Central de comunicações para envio individualizado de e-mails aos matriculados em uma campanha ou membros de um grupo.
- Assunto, mensagem, prazo, variáveis {{nome}}, {{campanha}} e {{prazo}}, histórico de envios e teste SMTP.
- Fonte decorativa incorporada para a identificação nominal de RH no certificado. É tipografia ilustrativa, não assinatura autógrafa.

## Configuração Entra ID
1. Registre uma aplicação no Microsoft Entra ID.
2. Configure a plataforma Web e o Redirect URI `https://SEU-DOMINIO/auth/callback`.
3. Para login, habilite OpenID Connect e permissões delegadas `openid`, `profile`, `email` e `User.Read`.
4. Para sincronização Graph por credenciais de aplicação, conceda `User.Read.All` (Application) e consentimento de administrador.
5. Cadastre Tenant ID, Client ID e Client Secret em Configurações gerais.
6. Use o botão de sincronização. Os usuários importados aparecerão em Usuários; associe-os aos grupos em Grupos.

## Configuração SMTP
- Servidor SMTP, porta (padrão 587), usuário, senha/app password e remetente.
- O envio utiliza STARTTLS. Confirme com a equipe de Mensageria se o relay corporativo permite autenticação SMTP.
- Faça um teste para um endereço controlado antes de enviar campanhas em massa.

## Observações operacionais
- As tabelas `app_settings` e `email_logs` são criadas por `create_all`; nenhuma tabela existente é apagada.
- Os segredos são criptografados com uma chave derivada de `SECRET_KEY`. **Não altere SECRET_KEY sem antes planejar a rotação/migração das configurações criptografadas**, pois isso impede descriptografar segredos salvos.
- O seletor grava a preferência de idioma e atualiza o atributo `lang` do documento. A tradução integral de todos os textos para inglês/espanhol ainda requer arquivos de tradução adicionais; a interface funcional continua em português nesta versão.
- A sincronização importa usuários do diretório; a associação a grupos internos é administrada na tela Grupos. Não há mapeamento automático de grupos do Entra ID nesta entrega.
- Testes executados nesta preparação: compilação sintática Python e parsing de todos os templates Jinja. Não foi possível executar autenticação real no Entra ID, envio SMTP ou teste integrado com o PostgreSQL do Render sem credenciais e serviços do ambiente.
