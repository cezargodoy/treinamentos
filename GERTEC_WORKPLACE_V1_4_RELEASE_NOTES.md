# Gertec Workplace v1.4 — Core integrado

## Decisão de produto
- Nome principal: Gertec Workplace.
- Identidade visual unificada.
- Gertec Academy e Gertec BPM como módulos ativos.
- GRC, People, Knowledge e Analytics apresentados como módulos planejados, sem links falsos nem funcionalidades simuladas.

## Alterações implementadas
- A rota `/` passa a apresentar o painel central Gertec Workplace.
- A rota `/academy` preserva o dashboard anterior do Gertec Academy para administradores e colaboradores.
- A navegação lateral passa a usar a identidade Gertec Workplace e reúne os acessos dos módulos.
- As rotas existentes do Academy e do BPM foram preservadas.
- Dashboard central utiliza contagens reais do banco: usuários ativos, cursos publicados, processos BPM ativos, macroprocessos e documentos BPM; para colaborador, mostra suas matrículas e status.
- Nenhuma tabela existente foi removida ou recriada.

## Deploy
1. Atualizar o repositório conectado ao Render com os arquivos deste pacote.
2. Fazer commit e push.
3. Executar novo deploy.
4. Acessar `/` para o Workplace e `/academy` para o painel do Academy.
5. Validar links, permissões e métricas com perfil administrador e colaborador.

## Escopo desta entrega
Esta é a primeira etapa de consolidação: shell central, dashboard e navegação unificada. Academy e BPM continuam usando seus módulos e tabelas existentes. GRC, People, Knowledge e Analytics aparecem como planejados; ainda não foram desenvolvidos. A arquitetura de serviços compartilhados e eventual separação de módulos será feita incrementalmente.
