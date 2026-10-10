# Validação da gameplay em primeira pessoa

Verificação em 2026-10-10 UTC no Linux Debian 13 x86_64. O jogo foi
renderizado com Mesa/OpenGL em Xvfb, áudio OpenAL nulo e llvmpipe com dois
threads. O pacote Windows x64 foi compilado com MinGW GCC 14.2 e vcpkg.

## Resultados

- Builds nativo e Windows concluídos com status zero. Ninja confirmou que
  o executável Windows está atualizado com os fontes finais.
- CTest: 1 teste executado e aprovado, com 78 verificações. Inclui
  controle SDL virtual Xbox, direção para trás, direção relativa à nova
  frente, olhar independente, carga de chute, colisões e prontidão antes
  da notificação de conclusão, também após reutilizar o comando.
- Jogo real renderizado: 65 verificações aprovadas, nenhuma ignorada.
  Usa os valores do pacote, reduzindo a resolução e começando com câmera
  externa para os primeiros exercícios.
- Recursos: 509 arquivos originais conferidos por hash, além do shader
  corrigido, conferido com `training-asset-overrides.json`.
- ZIP: CRC íntegro, executável e 26 DLLs PE32+ x64, dependências recursivas
  satisfeitas pelo pacote ou pelas APIs do Windows 11. Configuração e
  shader do arquivo conferidos com os fontes.
- Capturas de frente, visão para baixo e câmera externa inspecionadas.

Relatório: [validation-firstperson.json](validation-firstperson.json).
Execução: `7b4424de-39eb-4b0e-91d2-190d24513eff`. Cada tentativa registra um identificador novo e
seu resultado; este relatório corresponde à execução final aprovada.

SHA-256 do ZIP: `44f53f1588d9f12e00bf1b77a9229767c2dbcee000120f872d113dfeb4a33552`.

## Correções verificadas

Com bola, baixo pede a direção atrás do jogador imediatamente ao
controlador. O alvo fica estável durante o giro. Manter uma direção pede
novamente a nova direita/esquerda/trás quando o giro e o domínio terminam.
A telemetria distingue esses novos pedidos do simples balanço da câmera;
o teste de baixo mantido exige ao menos uma repetição efetiva do comando.
Frente fixa o rumo mostrado naquele instante, com olhar independente.
A referência acompanha o deslocamento real durante o giro, evitando usar
a antecipação do torso como nova frente.

As inversões freiam enquanto a bola ainda viaja no sentido contrário.
No contato aceito pela animação, o corte considera a entrada atual e
limita o impulso horizontal a 2,5 m/s quando o plano antigo aponta para
o sentido oposto. A bola continua livre: não se reposiciona para seguir
o jogador. O pé mais fraco mantém a diferença de controle. Após o contato,
a condução pode replanejar a movimentação restante sem repetir nem cancelar
o toque que já ocorreu, preservando as misturas de poses e a aceleração.
A assistência original ao domínio permanece; após passes o jogador fica
livre e precisa se aproximar para recuperar a bola.

A conclusão de uma tarefa agora publica a prontidão antes de notificar o
agendador. A ordem antiga podia perder a notificação e esperar 100 ms.
O mutex do comando é liberado antes da notificação, preservando a ordem dos
locks. O relógio usa o contador monotônico do SDL; o passo físico continua
10 ms. O pacote Windows inicializa o temporizador com precisão solicitada
de 1 ms e desativa a espera obrigatória de VSync, mantendo a apresentação
limitada pelo intervalo de 16 ms. O teste compara cinco segundos simulados
com o relógio real, sem mudar a velocidade da bola ou das animações.

## Evidências da execução

| Verificação | Evidência |
| --- | --- |
| rendered game startup | Native simulation emitted live frames |
| walking and dribbling | Player moved 7.14 m |
| walking retains ball | Ball distance max/end 0.61/0.56 m; controlled 15/15 frames |
| animation playback | Original animation frames advanced |
| release and deceleration | Stopped speed 0.000 m/s |
| sprinting | Walk 5.00, sprint 7.72 m/s |
| sprinting retains ball | Ball distance max/end 0.98/0.75 m; controlled 16/16 frames |
| short pass | Functions [1, 4]; ball speed 24.82 m/s |
| through pass | Functions [1, 5]; ball speed 24.82 m/s |
| high pass | Functions [1, 6]; ball speed 20.66 m/s |
| shot | Functions [1, 8]; ball speed 33.44 m/s |
| aerial physics | Peak height 3.93 m |
| super cancel free movement | Player moved away from incoming ball to x=-15.10 m |
| off-ball sliding | Functions [1, 13] |
| finishing exercise | Player starts at x=29.60 m |
| goal detection | Goal counter 0 -> 1 |
| automatic ball reset | Ball returned to x=30.24 m |
| charged shot elevation | Light (22.9325, 0.4749), charged (33.8514, 6.2843) (speed, height); delivered charge {'light': 120, 'quick': 410, 'charged': 520, 'chip': 520} |
| quick shot elevation | Target 250 ms, delivered 410 ms; shot (31.2757, 4.1715) (speed, height) |
| LB chip trajectory | Chip (22.0, 10.181); charged (33.8514, 6.2843) |
| free kick exercise | Player starts at [27.742, -7.9704, 0.0] |
| first person camera | Camera switches to first person |
| head free look with ball | Head yaw -0.94, player stays still |
| gradual head recenter | Head magnitude 1.16 -> 0.10 rad after input release |
| head look does not steer dribbling | Player delta [4.6111, -0.0615]; head turns independently |
| straight dribbling | Forward/side displacement [7.305400000000001, 0.0923] m |
| straight movement retains ball | Ball distance max/end 0.61/0.39 m; controlled 17/17 frames |
| held right keeps turning relative to new front | Successive right-turn angles -1.19/-1.35 rad |
| continuous relative turn retains ball | Ball distance max/end 0.73/0.73 m; controlled 14/14 frames |
| forward follows new front after turn | New front -2.78 rad; forward/side travel 5.89/0.44 m |
| new forward retains ball | Ball distance max/end 0.50/0.40 m; controlled 12/12 frames |
| RT preserves new forward direction | RT forward/side travel 5.19/-0.29 m; speed 4.32 m/s |
| RT after turn retains ball | Ball distance max/end 0.47/0.46 m; controlled 12/12 frames |
| idle RT does not turn player toward goal | Idle RT changed actual body heading 0.01 rad; no automatic goal-facing turn |
| down moves behind the current front | First 500 ms backwards travel -0.62 m; side -0.02 m |
| held down reverses relative to each new front | Body/camera turned 8.79 rad; 3 completed turns requested a new behind while down stayed held |
| repeated backward turns retain ball | Ball distance max/end 0.63/0.52 m; controlled 27/27 frames |
| up follows the front after backward turns | New forward/side travel 4.02/-0.53 m |
| forward after backwards retains ball | Ball distance max/end 0.78/0.39 m; controlled 12/12 frames |
| simulation keeps real-time pace | 5000 ms simulation / 5001 ms monotonic clock; ratio 1.000 |
| reset cancels buffered shot | Functions [1]; no stale shot after reset |
| forward before turns retains ball | Ball distance max/end 0.83/0.38 m; controlled 12/12 frames |
| left turn retains ball | Ball distance max/end 0.87/0.63 m; controlled 12/12 frames |
| right reversal retains ball | Ball distance max/end 0.75/0.72 m; controlled 16/16 frames |
| backward turn retains ball | Ball distance max/end 0.49/0.49 m; controlled 12/12 frames |
| stopping after turns retains ball | Ball distance max/end 0.36/0.36 m; controlled 7/7 frames |
| stopping after turns releases movement | Stopped speed 0.000 m/s |
| restart after turns retains ball | Ball distance max/end 0.54/0.37 m; controlled 18/18 frames |
| turning uses original ball-control animations | Functions [1, 2] |
| close control diagonal retains ball | Ball distance max/end 0.47/0.45 m; controlled 22/22 frames |
| close control reversal retains ball | Ball distance max/end 0.60/0.36 m; controlled 16/16 frames |
| first person sprint retains ball | Ball distance max/end 0.99/0.69 m; controlled 25/25 frames |
| original knock-on and recovery | Long-touch distance max 1.95 m; recovered to 0.66 m after releasing RT |
| pass releases possession | Ball distance 21.87 m |
| off ball idle does not chase | Idle displacement 0.000 m; speed 0.000 m/s |
| off ball movement is free after pass | Sideways displacement 4.09 m without super cancel |
| manual approach recovers passed ball | Recovered in 8.9 s; ball distance 0.41 m; functions [1, 2] |
| off ball FPS turning | Yaw changed -0.65 rad without ball |
| first person forward movement | Player moved 2.90 m |
| front stadium remains visible | Central distant roof covers 99.9% of inspection band |
| ball stays above turf | Minimum ball center 0.110 m |
| finite physics state | 1349 live samples are finite |
| rendered foot contact correction | 95 rendered foot corrections; median error 0.269 -> 0.143 m |
| external camera restoration | First person cycles back to external view |
| clean shutdown | Exit status 0 |

As medidas são amostras desta execução. A seleção de animações e os
atributos variam; elas não prometem os mesmos valores em toda situação.
A primeira verificação para trás exige deslocamento negativo perceptível
em 500 ms, permitindo a frenagem e o pivô da animação original.

## Limites da validação

O jogo e os controles virtuais foram executados no Linux da nuvem.
O Windows foi compilado e seu pacote verificado; não há sessão Windows,
GPU do usuário nem Xbox físico neste ambiente. A sensação do analógico,
o desempenho gráfico e a conexão USB/Bluetooth precisam ser conferidos
no computador Windows 11. Os menus antigos, partidas completas, adversários,
carreira e online não fazem parte desta validação do treino solo.
