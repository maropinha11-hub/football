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
- Jogo real renderizado: 78 verificações aprovadas, nenhuma ignorada.
  Usa os valores do pacote, reduzindo a resolução e começando com câmera
  externa para os primeiros exercícios.
- Recursos: 509 arquivos originais conferidos por hash, além do shader
  corrigido, conferido com `training-asset-overrides.json`.
- ZIP: CRC íntegro, executável e 26 DLLs PE32+ x64, dependências recursivas
  satisfeitas pelo pacote ou pelas APIs do Windows 11. Configuração e
  shader do arquivo conferidos com os fontes.
- Capturas de frente, visão para baixo e câmera externa inspecionadas.

Relatório: [validation-firstperson.json](validation-firstperson.json).
Execução: `1cb78dfb-404a-4f75-aa58-63e1ea5f2a01`. Cada tentativa registra um identificador novo e
seu resultado; este relatório corresponde à execução final aprovada.

SHA-256 do ZIP: `ee913811b5fd1c5a18a3943a2228bb7b59436712b154b23826b7f8505d4b3443`.

## Correções verificadas

O buffer permite preparar passe, enfiada e chute antes da chegada da bola.
A primeira ação registrada nos exercícios recebidos é o passe/chute pedido,
sem contato intermediário de domínio. Cabeceios de passe e finalização foram
registrados antes do quique, com primeiro contato da cabeça a 1,63 m. A
seleção também considera os gestos originais de cabeceio parado e com salto;
a potência do cabeceio respeita a animação original.

A curva durante a corrida com RB+RT conserva a assistência ao toque adiantado.
O teste mantém RT por 5,2 segundos em linha reta e depois exercita sua entrada
em uma corrida existente, uma curva de 2,5 segundos e a recuperação ao soltar
RT. Após a curva, a bola ficou a 0,58 m do jogador, sem reset. A janela de
recuperação começa somente em um contato real; passe, chute ou contato comum
a encerram. Soltar o analógico pede frenagem no próximo contato real do pé
para que o passo anterior não renove uma condução sem entrada.

A simulação do treino executa cinco fases ordenadas em um despacho por passo,
e tarefas já prontas dispensam esperas temporizadas do agendador. O passo
físico e a duração das animações continuam em 10 ms. Foram medidos 5.000 ms
simulados em 5.000 ms reais, e 2.500 ms em 2.500 ms durante curva com RB+RT.
O log registra a relação de tempo a cada cinco segundos reais. Essas são
medidas do runtime Linux; o desempenho no hardware Windows depende do teste
local do usuário.

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
| walking and dribbling | Player moved 6.65 m |
| walking retains ball | Ball distance max/end 0.60/0.57 m; controlled 15/15 frames |
| animation playback | Original animation frames advanced |
| release and deceleration | Stopped speed 0.000 m/s |
| sprinting | Walk 5.00, sprint 7.74 m/s |
| sprinting retains ball | Ball distance max/end 0.98/0.74 m; controlled 16/16 frames |
| short pass | Functions [1, 4]; ball speed 25.04 m/s |
| through pass | Functions [1, 5]; ball speed 25.49 m/s |
| high pass | Functions [1, 6]; ball speed 30.66 m/s |
| shot | Functions [1, 8]; ball speed 31.85 m/s |
| aerial physics | Peak height 3.94 m |
| super cancel free movement | Player moved away from incoming ball to x=-14.94 m |
| off-ball sliding | Functions [1, 13] |
| finishing exercise | Player starts at x=30.25 m |
| goal detection | Goal counter 0 -> 1 |
| automatic ball reset | Ball returned to x=30.65 m |
| charged shot elevation | Light (23.4934, 0.5426), charged (33.4431, 6.283) (speed, height); delivered charge {'light': 130, 'quick': 410, 'charged': 520, 'chip': 520} |
| quick shot elevation | Target 250 ms, delivered 410 ms; shot (31.6297, 4.1723) (speed, height) |
| LB chip trajectory | Chip (21.2769, 10.1825); charged (33.4431, 6.283) |
| free kick exercise | Player starts at [28.2396, -7.929, 0.0] |
| first person camera | Camera switches to first person |
| head free look with ball | Head yaw -0.97, player stays still |
| gradual head recenter | Head magnitude 1.11 -> 0.11 rad after input release |
| head look does not steer dribbling | Player delta [4.4654, 0.0]; head turns independently |
| straight dribbling | Forward/side displacement [7.898899999999999, 0.0] m |
| straight movement retains ball | Ball distance max/end 0.83/0.39 m; controlled 17/17 frames |
| held right keeps turning relative to new front | Successive right-turn angles -1.21/-1.31 rad |
| continuous relative turn retains ball | Ball distance max/end 0.67/0.67 m; controlled 14/14 frames |
| forward follows new front after turn | New front -2.84 rad; forward/side travel 5.87/0.36 m |
| new forward retains ball | Ball distance max/end 0.57/0.39 m; controlled 12/12 frames |
| RT preserves new forward direction | RT forward/side travel 5.28/-0.29 m; speed 4.13 m/s |
| RT after turn retains ball | Ball distance max/end 0.46/0.45 m; controlled 12/12 frames |
| idle RT does not turn player toward goal | Idle RT changed actual body heading -0.02 rad; no automatic goal-facing turn |
| down moves behind the current front | First 500 ms backwards travel -0.38 m; side -0.06 m |
| held down reverses relative to each new front | Body/camera turned 9.00 rad; 2 completed turns requested a new behind while down stayed held |
| repeated backward turns retain ball | Ball distance max/end 0.59/0.30 m; controlled 27/27 frames |
| up follows the front after backward turns | New forward/side travel 4.46/0.31 m |
| forward after backwards retains ball | Ball distance max/end 0.68/0.39 m; controlled 12/12 frames |
| simulation keeps real-time pace | 5000 ms simulation / 5000 ms monotonic clock; ratio 1.000 |
| reset cancels buffered shot | Functions [1]; no stale shot after reset |
| forward before turns retains ball | Ball distance max/end 0.83/0.37 m; controlled 12/12 frames |
| left turn retains ball | Ball distance max/end 0.90/0.57 m; controlled 12/12 frames |
| right reversal retains ball | Ball distance max/end 0.77/0.64 m; controlled 16/16 frames |
| backward turn retains ball | Ball distance max/end 0.53/0.34 m; controlled 12/12 frames |
| stopping after turns retains ball | Ball distance max/end 0.47/0.42 m; controlled 7/7 frames |
| stopping after turns releases movement | Stopped speed 0.000 m/s |
| restart after turns retains ball | Ball distance max/end 0.53/0.40 m; controlled 18/18 frames |
| turning uses original ball-control animations | Functions [1, 2] |
| close control diagonal retains ball | Ball distance max/end 0.45/0.40 m; controlled 22/22 frames |
| close control reversal retains ball | Ball distance max/end 0.54/0.29 m; controlled 16/16 frames |
| first person sprint retains ball | Ball distance max/end 0.99/0.70 m; controlled 25/25 frames |
| original knock-on and recovery | Long-touch distance max 2.17 m; recovered to 0.57 m after releasing RT |
| sprint knock-on turns retain control | Turning with RB+RT: distance max 2.10 m, controlled 25/25 frames |
| simulation pace during sprint knock-on turns | 2500 ms simulation / 2500 ms real; ratio 1.000 |
| knock-on turn recovers without reset | Recovered to 0.58 m after turning and releasing RT |
| pass releases possession | Ball distance 21.62 m |
| off ball idle does not chase | Idle displacement 0.000 m; speed 0.000 m/s |
| off ball movement is free after pass | Sideways displacement 3.74 m without super cancel |
| manual approach recovers passed ball | Recovered in 8.4 s; ball distance 0.39 m; functions [1, 2] |
| off ball FPS turning | Yaw changed -0.71 rad without ball |
| first person forward movement | Player moved 3.06 m |
| headed pass before bounce accepts early input | Action buffered with ball 5.29 m away |
| headed pass before bounce | First contact head / function 4 at z=1.6313 m; peak speed 19.43 m/s |
| headed shot before bounce accepts early input | Action buffered with ball 5.13 m away |
| headed shot before bounce | First contact head / function 8 at z=1.6313 m; peak speed 27.21 m/s |
| first-time short pass accepts early input | Action buffered with ball 5.62 m away |
| first-time short pass | First contact left_foot / function 4 at z=0.1100 m; peak speed 29.47 m/s |
| first-time through pass accepts early input | Action buffered with ball 5.66 m away |
| first-time through pass | First contact right_foot / function 5 at z=0.1100 m; peak speed 24.32 m/s |
| first-time shot accepts early input | Action buffered with ball 5.86 m away |
| first-time shot | First contact left_foot / function 8 at z=0.1100 m; peak speed 29.99 m/s |
| front stadium remains visible | Central distant roof covers 100.0% of inspection band |
| ball stays above turf | Minimum ball center 0.110 m |
| finite physics state | 1616 live samples are finite |
| rendered foot contact correction | 74 rendered foot corrections; median error 0.187 -> 0.093 m |
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
