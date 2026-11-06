# Ajustes do certificado Gertec Academy

## Alterações desta versão
- Assinatura gráfica ilustrativa ampliada para a Diretoria de Recursos Humanos (não representa assinatura de pessoa física).
- Logotipo oficial Gertec atualizado no canto superior direito, ampliado.
- Identificação Gertec Academy no canto superior esquerdo.
- Faixa/curva azul superior esquerda ampliada.
- Campo de carga horária com largura ampliada e fonte ajustável para caber no retângulo.
- Carga horária aceita formatos `1h`, `1h30min`, `90min`, `2h15min` e `1.5h`.
- Campanhas armazenam o rótulo original da carga horária; a migração adiciona `duration_text` sem remover dados.
- Certificado exibe a duração formatada, sem plural incorreto como `1 HORAS`.

## Publicação
Faça backup do PostgreSQL antes do deploy. A migração adiciona apenas a coluna `duration_text` à tabela `campaigns`.
