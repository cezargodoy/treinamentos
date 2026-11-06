# Certificados Gertec Academy

- A campanha possui carga horária em horas (`duration_hours`).
- O certificado da campanha é emitido quando todas as matrículas do colaborador naquela campanha estão concluídas.
- O PDF é gerado em A4 horizontal, com paleta azul-marinho, azul institucional e dourado.
- O logotipo oficial fornecido está em `static/gertec-logo-oficial.png`.
- O QR Code aponta para `/certificates/validate/{codigo}` e a rota valida o código no banco.
- A área de assinatura identifica somente a Diretoria de Recursos Humanos, sem assinatura gráfica fictícia.

Antes de produção, valide com RH o texto institucional, a carga horária, os critérios de conclusão e o responsável formal pela emissão. Faça backup do PostgreSQL antes do deploy.
