# Gertec Academy v4.4.3 — controle de reprodução de vídeo

## Implementado para arquivos de vídeo diretos (MP4, WebM e OGG)
- Progresso calculado automaticamente pelos segundos de mídia efetivamente reproduzidos.
- Registro periódico de progresso no servidor.
- Bloqueio de avanço manual por barra de busca/seek no player HTML5.
- Retrocesso e pausa permitidos.
- Controle de velocidade em 1x, 1,25x, 1,5x e 2x.
- Conclusão automática no evento `ended`, desde que o tempo de mídia registrado alcance 90% da duração reportada pelo player.
- Campos de progresso manual e botão de conclusão manual ocultos para vídeos diretos; as rotas também rejeitam essas ações.

## Limitação importante: SharePoint / Microsoft Stream incorporado
O iframe do SharePoint é conteúdo de outra origem. Por política de segurança do navegador, o Gertec Academy não consegue ler o tempo atual, controlar a barra de busca ou impor a velocidade dentro desse player sem uma API oficial de controle/telemetria exposta pelo provedor. Para esses vídeos, o player continua externo e a conclusão permanece manual. Não afirmar controle antiavanço ou tracking automático para iframe SharePoint.

## Segurança e integridade
O bloqueio de seek é uma proteção de interface no player HTML5, não um mecanismo antifraude inviolável. Um usuário tecnicamente avançado pode manipular eventos do navegador. Para evidência de conformidade forte, recomenda-se player/streaming gerenciado com telemetria assinada no servidor.
