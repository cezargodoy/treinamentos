# Gertec Workplace v2.3 - Gertec Juridico

Modulo de service desk juridico com chamados para contratos, NDA e demais solicitacoes.

- Dashboard de volume, backlog, concluidos no/fora do SLA e tempo medio de conclusao.
- SLA manual por chamado em horas, com vencimento calculado a partir da abertura.
- Indicacao visual verde (dentro), amarelo (proximo do vencimento) e vermelho (estourado).
- Responsavel, area solicitante, solicitante, parceiro/cliente, prioridade, status e descricao.
- Anexo de documento por chamado (limite 20 MB), armazenado no banco.
- Atualizacao de status, responsavel, SLA e resolucao.
- Modulo integrado ao menu e ao catalogo de modulos globais/permissoes.

Observacoes: o SLA nesta versao considera horas corridas, nao calendario de dias uteis. O acesso herda autenticacao e permissao de modulo existentes. Validar deploy, banco e fluxos no Render antes de uso operacional.
