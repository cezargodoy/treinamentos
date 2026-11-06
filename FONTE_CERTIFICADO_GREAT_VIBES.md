# Fonte da assinatura visual do certificado

- Família tipográfica: **Great Vibes Regular**, de Robert E. Leuschke.
- Origem: Google Fonts (`ofl/greatvibes`).
- Licença: SIL Open Font License 1.1.
- O Dockerfile baixa o TTF oficial e o arquivo de licença durante o build da imagem.
- O ReportLab incorpora a fonte ao PDF gerado, para manter a aparência sem depender das fontes do computador do destinatário.
- A identificação “Edinalva Janjacomo” é tipográfica e ilustrativa; não é uma assinatura autógrafa nem comprova autorização pessoal.

Se o build do Render estiver sem acesso à origem da fonte, o build falhará e a aplicação manterá a última implantação funcional.
