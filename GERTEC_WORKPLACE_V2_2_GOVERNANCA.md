# Gertec Workplace v2.2 — Governança integrada

## Principais alterações
- Navegação do Gertec Academy sem atalhos administrativos de usuários, grupos, permissões e diretório.
- Logo do Gertec Academy retorna para `/academy`.
- Workplace centraliza a Gestão de Acessos com atalhos para usuários, grupos e diretório, além de matriz de autorização por perfil e módulo.
- Configurações gerais permitem habilitar/desabilitar globalmente Academy, BPM, BCM e GRC. A desativação remove o módulo da navegação e bloqueia suas rotas.
- GRC apresenta heatmap 5x5 por probabilidade e impacto, com pontos que navegam ao registro do risco.
- Apontamentos de auditoria podem ser associados a um controle/requisito normativo específico.
- BIA sincroniza automaticamente processos BPM do tipo Processo nas categorias Cadeia de Valor e Processos Secundários; subprocessos são excluídos. Inclui ranking de criticidade e RTO.

## Banco de dados
- Alterações são aditivas. Não há drop, truncate ou recriação do banco.
- Nova coluna opcional `grc_findings.control_id` é adicionada se ainda não existir.
- Configurações globais dos módulos utilizam `app_settings`.

## Validações locais
- `app.py` compilado com `py_compile`.
- Todos os templates Jinja foram carregados e os templates afetados renderizados com contexto de exemplo.
- Não foi possível executar teste de integração FastAPI/SQLAlchemy neste ambiente porque a dependência `authlib` não está instalada no runtime de validação.
- Deploy e validação de SSO/Entra, permissões reais e persistência no Render permanecem pendentes.
