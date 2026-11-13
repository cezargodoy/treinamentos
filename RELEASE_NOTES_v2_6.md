# Gertec Workplace v2.6 – Correção Jurídico e navegação

## Alterações
- Removido o link Fórum da barra lateral do Gertec Workplace. O Fórum permanece disponível no módulo Academy.
- Corrigida a migração do módulo Jurídico para bancos PostgreSQL que já possuíam `legal_tickets` sem a coluna `code`.
- A migração é aditiva: adiciona colunas ausentes, preenche códigos históricos no formato `LEG-000001` e cria índice único. Não apaga nem recria chamados.

## Publicação
Faça backup do PostgreSQL antes do deploy. A migração é executada na inicialização da aplicação.
A validação local de sintaxe e templates não substitui o teste no Render com o banco real.
