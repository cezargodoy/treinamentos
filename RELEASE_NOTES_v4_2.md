# Gertec Academy v4.2 — exclusões controladas e dashboard PDF

## Fórum
- Autor pode excluir a própria discussão e as respostas associadas.
- Administrador pode excluir qualquer discussão.
- Autor pode excluir a própria resposta; administrador pode excluir qualquer resposta.
- Ações registradas em `audit_logs`.

## Campanhas
- Exclusão disponível apenas para administrador.
- Antes de remover a campanha, os vínculos de matrícula e certificado são preservados com `campaign_id = NULL`.
- Vínculos de campanha com cursos e perfis são removidos; ação registrada na auditoria.

## Biblioteca de conteúdo
- Exclusão disponível apenas para administrador.
- Exclusão é bloqueada quando há matrículas, campanhas ou certificados vinculados, para proteger histórico e integridade referencial.
- Avaliações sem vínculos de aprendizagem são removidas junto com questões e tentativas.

## Relatórios
- Filtros por período, campanha, departamento e grupo.
- Indicadores de matrículas, conclusões, pendências, taxa de conclusão e horas assistidas registradas.
- Visões de evolução mensal, desempenho por departamento e conteúdos mais atribuídos.
- Exportação do dashboard em PDF A4 paisagem, com página de indicadores e página de detalhamento.
- Exportação CSV existente preservada.

## Compatibilidade e dados
- Não há remoção ou recriação de tabelas.
- Não há migração de schema nesta versão.
- Exclusões são protegidas por autorização no backend; esconder botões na interface não é usado como controle de segurança.
