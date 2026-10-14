# Animações adicionais no treino

Extraia o pacote completo em uma pasta nova e execute `run-training.bat`.
A câmera em primeira pessoa, o controle Xbox, a cadência aprovada e o RT
reservado continuam disponíveis.

| Tecla | Exercício |
| --- | --- |
| F4 | Receber passe rasteiro |
| F5 | Receber bola na altura do peito |
| F6 | Receber cruzamento alto |
| R3 / Tab | Alternar câmera para conferir o corpo |
| R / View | Reiniciar |

## Condução original com apresentação nova

O Football volta a escolher as animações, calcular a aproximação, aplicar
os toques e manter a posse. `DefenseJog_LoopF` acompanha visualmente a
condução para frente sem RB. Sua fase avança com a distância percorrida e
continua durante as trocas internas do seletor. Nos contatos, os pés usam
a pose da jogada nativa; a mistura entra e sai em 240 ms.

A animação visual não altera a velocidade da bola, não bloqueia comandos,
não segura o jogador esperando um pé e não precisa adquirir uma posse
separada. Viradas, saída parado, corrida, passe e chute usam o mesmo
caminho com a apresentação nova ligada ou desligada. A opção interna
`training_fbx_dribble` serve para comparar esses dois casos nos testes;
L3 não alterna mais a condução durante o jogo.

## Domínio adicional

`Chest_Stand` entra como candidato de domínio no seletor original, ao lado
das animações de peito existentes. O carregamento preserva suas 151 amostras,
a posição relativa do corpo e o deslocamento da recuperação. O evento de
contato usa a extensão de futebol do motor, com previsão e aproximação
calculadas pelo seletor nativo. Os domínios antigos continuam disponíveis
para outras alturas, velocidades e direções.

Mover ou solicitar uma ação depois do contato pode interromper a recuperação
do clip novo usando a transição normal do motor. Não há um segundo sistema
prendendo a posição do jogador ou esperando a bola cair. Uma colisão real
com o corpo continua sendo tratada quando a recepção não alcança a bola.

## Validação

Os testes novos verificam respostas ao controle, retenção da bola, ações e
interrupções com a apresentação ligada e desligada. Os relatórios das
versões anteriores documentam implementações substituídas: expectativas
como `TRAINING_FBX_TOUCH` e posse exclusiva do loop não descrevem esta versão.
A compilação Windows é verificada separadamente; testes de partida neste
ambiente usam a versão Linux e um controle Xbox virtual em SDL.
