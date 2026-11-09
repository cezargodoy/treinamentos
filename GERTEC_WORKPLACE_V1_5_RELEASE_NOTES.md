# Gertec Workplace v1.5 — Administração central

## Implementado
- Modelo de notificações corporativas no banco compartilhado.
- Página `/workplace/admin`, exclusiva para administradores.
- Indicadores consolidados de usuários, grupos, cursos, processos e notificações.
- Atalhos para gestão de usuários, grupos e matriz de permissões já existentes.
- Publicação de comunicados globais com módulo de referência.
- Página `/workplace/notifications` para consulta individual.
- Ação de marcar notificação como lida.
- Registro de publicação no log de auditoria.
- Navegação central atualizada.

## Compatibilidade
- Não removeu nem renomeou tabelas existentes.
- A nova tabela `workplace_notifications` é criada pelo `Base.metadata.create_all(engine)` na inicialização.
- Academy, BPM e BPMN local foram preservados.

## Limitações desta etapa
- Notificações são comunicados internos consultáveis na central; não há push, e-mail ou integração Teams nesta entrega.
- A segmentação por módulo é informativa; comunicados são globais nesta primeira versão.
- A matriz atual de permissões e os papéis existentes foram preservados; a aplicação uniforme dessas permissões em todos os endpoints será uma etapa posterior de hardening.

## Deploy
1. Atualize o repositório GitHub conectado ao Render com todos os arquivos deste pacote.
2. Faça commit e push e aguarde o deploy.
3. Acesse `/workplace/admin` com perfil administrador.
4. Publique um comunicado de teste e confira `/workplace/notifications`.
5. Confirme que usuários sem perfil admin não acessam a administração central.
