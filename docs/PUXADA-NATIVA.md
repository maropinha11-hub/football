> Registro da tentativa anterior, substituída pela [correção das viradas nativas](VIRADAS-NATIVAS.md).

# Puxada na gameplay nativa

Esta correção parte da base restaurada `37a5543`. Ela altera apenas dois pontos:

- O impulso da puxada é aplicado depois da mistura com a velocidade anterior
  da bola, no contato aceito da animação nativa. Segue a direção do analógico,
  com limite de 2,5 m/s e força proporcional à intensidade do movimento.
- Os colisores rígidos adicionais das pernas não aplicam um segundo rebote
  na virada controlada, com a bola baixa e próxima do jogador. A animação e
  o controle nativo continuam responsáveis por essa condução.
  Nos contatos incidentais com a bola baixa e controlada, a perna apenas
  bloqueia ou desliza a bola; a velocidade do corpo não vira outro chute.

A câmera, os controles, as animações, sua seleção e a renderização permanecem
como na base aprovada. Não há preferência nova de pé, intervalo novo de toque
ou substituição de poses. RT mantém a função original.

A atualização `football-windows-puxada-corrigida.zip` deve ser extraída na pasta
onde ficam `run-training.bat`, `media` e as DLLs. Aceite substituir e execute o BAT.
O ZIP inclui a configuração de primeira pessoa da base aprovada.

As verificações estão em [native-pullback-validation.json](native-pullback-validation.json).
O teste específico usa um controle Xbox virtual no SDL e verifica puxadas a
partir da bola parada, caminhada, corrida, corrida com RB mantido e domínio RT.
A execução renderizada é verificada no Linux; o pacote Windows é compilado
para x64 e tem sua integridade e dependências verificadas.
