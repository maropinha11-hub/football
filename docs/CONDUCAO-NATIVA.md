# Correção da condução na base nativa

Esta versão parte de `37a5543fb30efb09e9b084733ee836478fff2b61`, cujo
executável distribuído corresponde exatamente ao enviado pelo usuário:
SHA-256 `ece4200cd1591edb60007ff71f4154cfaf7bcf232ec05ccfff001067f5418bfb`.
A integração híbrida de `9512740` foi revertida. O treino usa as animações,
a malha, os comandos e a física dessa base aprovada.

Na virada para trás, o cálculo inicial do toque já solicitava puxar a bola,
mas as misturas posteriores de recepção e erro do contato podiam devolver
o impulso à direção anterior. A correção final ocorre somente no evento
de contato de pé aceito pelo sistema nativo, depois dessas misturas. Mantém
o alcance original, a altura do impulso e a intensidade do analógico.
Pequenas oscilações do analógico perto da direção de trás conservam o alvo
da virada até o corpo e o contato com a bola permitirem outra virada.

**L3** (clicar o analógico esquerdo) ou **G** alterna a preferência pelo pé
dominante direito e a condução normal. A preferência começa ativada e
ordena os passos nativos compatíveis antes da verificação física de alcance;
o pé esquerdo continua disponível quando necessário. Passes, chutes,
cabeçadas e ações sem bola conservam sua seleção nativa. A correção da
virada funciona nos dois modos. A configuração opcional
`"training_dominant_control" "false"` inicia no modo normal.

Para atualizar no Windows: feche o jogo, extraia
`football-windows-corrigir-virada.zip` **dentro da pasta atual do jogo**,
aceite substituir os arquivos e abra `run-training.bat`. O ZIP contém
`gameplayfootball.exe`, `run-training.bat`, as licenças e as instruções.
Usa as DLLs e a pasta `media` da instalação existente. Também há um ZIP
completo para uma instalação nova. `--training` abre o treino nativo mesmo
com uma configuração antiga de estudo; o estudo só abre com sua opção
explícita `--pes3-preview`.

A validação está em [native-dribble-validation.json](native-dribble-validation.json).
Os testes executam o jogo renderizado no Linux com eventos SDL reais de
teclado e um controle Xbox virtual, incluindo L3, RT, corrida, oscilações do
analógico e viradas repetidas. O executável Windows foi compilado e suas
dependências verificadas; sua execução visual no Windows e o controle
físico ainda precisam da conferência no computador do usuário.
