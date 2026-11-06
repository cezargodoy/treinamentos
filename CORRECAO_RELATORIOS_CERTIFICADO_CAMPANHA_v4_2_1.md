# Correção v4.2.1 — Relatórios e certificado por campanha

## Relatórios
- Corrigida colisão de contexto entre a lista de departamentos usada no filtro e os totais usados no gráfico.
- Os totais do gráfico agora são enviados como `department_stats`; a lista simples de departamentos permanece em `departments`.
- A exportação PDF usa `department_stats` para montar o quadro de conclusão por departamento.

## Certificados
- Para matrículas vinculadas a campanhas, a conclusão do conteúdo não emite mais um certificado individual com o título do curso.
- A emissão aguarda a conclusão de todos os conteúdos da campanha e emite o certificado vinculado à campanha.
- A listagem oculta certificados individuais antigos para cursos que estejam vinculados a campanhas, evitando exibir o nome do conteúdo no lugar do nome da campanha.
- O PDF e a página de validação já priorizam o título da campanha quando o certificado possui `campaign_id`.

## Banco de dados
Nenhuma alteração de schema ou migração é necessária.
