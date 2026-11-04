# Gertec Academy — MVP corporativo

MVP de portal LMS com identidade visual Gertec. A aplicação é web: colaboradores e RH acessam pelo navegador, sem instalar Python localmente.

## O que já está implementado
- Login federado Microsoft Entra ID (OpenID Connect).
- Provisionamento automático do usuário no primeiro login.
- Papéis `admin`, `rh` e `colaborador`, definidos por listas de e-mails.
- Biblioteca de cursos com links para vídeos SharePoint/OneDrive.
- Campanhas que reutilizam cursos existentes e atribuem treinamentos aos colaboradores sincronizados.
- Área do colaborador com treinamentos atribuídos.
- Registro de conclusão e emissão de certificado com código único.
- Relatório gerencial com totais de matrículas, concluídos, pendentes e taxa de conclusão; exportação CSV completa com colaborador, e-mail, departamento, curso, progresso, status, datas e campanha.
- Sincronização de usuários via Microsoft Graph com paginação (até 10.000 usuários por execução).

## 1. Publicar no GitHub e Render
1. Envie todos os arquivos e pastas deste projeto para a raiz do repositório GitHub.
2. No Render, crie um Web Service conectado ao repositório, runtime Docker.
3. Use o plano Free apenas para piloto. O serviço pode hibernar após inatividade.
4. Configure as variáveis de ambiente descritas abaixo.
5. Use PostgreSQL gerenciado persistente (por exemplo, Supabase). Não use SQLite em produção.
6. Configure `COOKIE_SECURE=true` em produção HTTPS.

## 2. Configurar Microsoft Entra ID (SSO)
No Microsoft Entra admin center:
1. App registrations > New registration.
2. Nome: `Gertec Academy`.
3. Supported account types: Accounts in this organizational directory only (single tenant).
4. Em Authentication, adicione plataforma Web e Redirect URI: `https://SEU-DOMINIO/auth/callback`.
5. Crie um client secret em Certificates & secrets e copie o valor imediatamente.
6. Em API permissions, confirme `openid`, `profile`, `email` (delegated / OIDC); `User.Read` delegated para login.
7. Para sincronização de diretório via Microsoft Graph, configure também permissões **Application** `User.Read.All` e conceda admin consent. A sincronização usa client credentials; use credenciais dedicadas e política de rotação.
8. Restrinja o consentimento e valide com a equipe de identidade/segurança antes de liberar.

Variáveis de ambiente:
- `ENTRA_TENANT_ID`: Directory (tenant) ID.
- `ENTRA_CLIENT_ID`: Application (client) ID do app de login.
- `ENTRA_CLIENT_SECRET`: segredo do app de login.
- `ENTRA_REDIRECT_URI`: `https://SEU-DOMINIO/auth/callback`.
- `ADMIN_EMAILS`: e-mails de administradores separados por vírgula.
- `HR_EMAILS`: e-mails autorizados do RH separados por vírgula.
- `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`: credenciais de aplicativo com `User.Read.All` e admin consent. Podem usar o mesmo registro, se aprovado pela equipe de identidade.
- `DATABASE_URL`: conexão PostgreSQL.
- `SECRET_KEY`: segredo aleatório longo e exclusivo.
- `COOKIE_SECURE`: `true`.

Os usuários não listados em `ADMIN_EMAILS` ou `HR_EMAILS` entram como `colaborador`. O perfil é reavaliado no login. Proteja as listas de e-mails como configuração administrativa.

## 3. OneDrive / SharePoint
O MVP registra links corporativos para o vídeo, sem copiar os arquivos. No cadastro do curso, cole um link de compartilhamento ou link de incorporação compatível com iframe. O colaborador ainda precisa ter permissão no SharePoint/OneDrive para assistir.

Para produção, prefira:
- Biblioteca SharePoint dedicada para treinamento.
- Permissões de leitura para o público da campanha.
- Link de incorporação/visualização aprovado pelo tenant.
- Não habilitar links públicos anônimos sem aprovação.
- Se o link normal de compartilhamento não abrir em iframe, usar botão "Abrir vídeo" ou obter o embed link correto no SharePoint.

## 4. Como usar
1. Configure SSO e entre com a conta Microsoft.
2. Adicione o e-mail do responsável em `ADMIN_EMAILS` e os responsáveis de RH em `HR_EMAILS`.
3. Administrador abre `/admin/sync-users` para importar/atualizar usuários do diretório (permissão Graph necessária).
4. RH cria cursos em Biblioteca de cursos.
5. RH cria campanhas e seleciona cursos; os cursos são atribuídos aos usuários sincronizados com perfil colaborador.
6. Colaborador entra pelo SSO, acessa o curso e registra a conclusão.
7. RH exporta relatório CSV.

## Limitações deliberadas do MVP — não tratar como pronto para produção
- A sincronização Graph percorre páginas do diretório até o limite de 10.000 usuários por execução; grupos e filtros por unidade ainda precisam ser implementados.
- O MVP ainda não implementa upload de arquivos para SharePoint via Graph; o RH cadastra links existentes.
- O MVP não mede automaticamente a duração assistida do vídeo. A conclusão é declarada pelo colaborador, não prova presença ou visualização integral.
- Não há ainda avaliação com nota, regras condicionais de certificado, QR check-in de presença presencial, lembretes por e-mail, recuperação de acesso ou painel de auditoria detalhado.
- Adicionar proteção CSRF, rate limiting, logs de auditoria, testes de autorização, validação de URLs SharePoint, política de retenção e revisão LGPD antes de uso corporativo.
- Certificado nesta versão é um registro web imprimível via navegador; PDF assinado/QR de validação pública é evolução posterior.
- Validar integração, permissões Graph, política de cookies e regras de acesso com TI/Segurança da Gertec antes de disponibilizar a colaboradores.

## Identidade visual
A interface usa a paleta institucional baseada na marca Gertec: azul-marinho/azul para estrutura e séries principais, amarelo para destaques e estados pendentes, com cinzas neutros para fundos e grades.

## Segurança
Nunca comite client secrets, strings de conexão ou `SECRET_KEY` no GitHub. Configure-os somente em Render > Environment. Não use dados reais de colaboradores até concluir revisão de segurança e privacidade.

## Autenticação: login padrão e Microsoft Entra ID opcional

A tela `/login` oferece dois caminhos independentes:

- **Login padrão:** e-mail e senha cadastrados pelo administrador/RH. Senhas são armazenadas com PBKDF2-HMAC-SHA256 e salt individual.
- **Entrar com Microsoft (SSO):** aparece somente quando `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID` e `ENTRA_CLIENT_SECRET` estão configurados. Para iniciar sem integração, basta deixar essas variáveis vazias; o login padrão continua funcionando.

No primeiro acesso, se ainda não existir nenhum usuário, use `/setup` para criar a primeira conta administradora (senha mínima de 12 caracteres). Depois, entre em **Usuários** para cadastrar colaboradores, RH e outros administradores. O RH e o administrador podem criar contas locais.

Quando o SSO for habilitado futuramente, um colaborador local poderá usar o mesmo e-mail no botão Microsoft. O sistema vincula a identidade Entra ID à conta existente e preserva o perfil local atribuído. Configure a Redirect URI `https://SEU-DOMINIO/auth/callback` no App Registration.

**Atenção para produção:** habilite HTTPS e `COOKIE_SECURE=true`, configure `SECRET_KEY` forte, implemente política de recuperação/troca de senha, MFA conforme política corporativa, rate limiting, CSRF e auditoria antes de uso amplo. O cadastro inicial `/setup` fica automaticamente bloqueado depois que a primeira conta é criada.
