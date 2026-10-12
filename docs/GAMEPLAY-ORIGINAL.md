# Gameplay original restaurada

A versão atual retorna à base `37a5543fb30efb09e9b084733ee836478fff2b61`,
anterior à integração híbrida e aos ajustes posteriores de condução.
O código de gameplay, a configuração e os testes dessa base foram restaurados.
A câmera e os controles em primeira pessoa permanecem os que já funcionavam.

O pacote de restauração reutiliza o executável Windows arquivado nessa base.
Seu SHA-256 é idêntico ao executável originalmente enviado pelo usuário:
`ece4200cd1591edb60007ff71f4154cfaf7bcf232ec05ccfff001067f5418bfb`.
Ele conserva as animações nativas. Não foram adicionadas novas animações.

Feche o jogo, coloque `football-windows-gameplay-original.zip` na pasta onde
estão `run-training.bat` e `media`, escolha **Extrair aqui**, aceite substituir
os arquivos e execute `run-training.bat`. A configuração retorna à primeira
pessoa e às preferências da base aprovada; RT volta ao domínio original.

A recuperação do binário aprovado evita introduzir diferenças de recompilação.
Para reproduzir este pacote, execute:

```sh
. scripts/native-env.sh
python3 scripts/package-windows.py --restore-original-binary
```

A verificação compara o código restaurado e o executável com a base arquivada,
confere o BAT, os CRCs dos ZIPs, a arquitetura x64 e as dependências Windows.
Os testes de gameplay desta restauração não foram executados novamente.
Os resultados ficam em [native-original-restoration-validation.json](native-original-restoration-validation.json).
