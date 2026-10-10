# Validação da gameplay em primeira pessoa

Verificação em 2026-10-10 UTC no ambiente Linux Debian 13 x86_64. O jogo
real foi renderizado por Mesa/OpenGL em Xvfb, com áudio OpenAL nulo e
llvmpipe limitado a dois threads para respeitar a cota de CPU da nuvem.
O executável Windows foi compilado para x64 com MinGW GCC 14.2 e vcpkg.

## Resultados

- Compilação nativa e Windows: concluídas, status zero.
- CTest: 1 teste executado e aprovado; 58 verificações de controles SDL,
  movimento relativo à visão, olhar com bola, retorno da cabeça, carga de
  chute e varredura de colisão. Nenhum teste ignorado.
- Jogo renderizado: 52 verificações aprovadas, com eventos X11 e
  telemetria real da simulação. Usa a configuração que vai no pacote,
  com resolução reduzida e câmera externa inicial para os exercícios prévios.
- Recursos originais: 509 arquivos de `data` conferidos contra os hashes da
  importação. O shader de pós-processamento corrigido também foi conferido
  contra o hash registrado em `training-asset-overrides.json`.
- Pacote Windows: ZIP íntegro, PE32+ GUI x64, 26 DLLs de runtime; imports
  recursivos satisfeitos pelas DLLs do pacote ou APIs do Windows 11,
  incluindo XInput, AVRT e o contrato `api-ms-win-core-synch-l1-2-0`.
- Configuração do ZIP conferida: primeira pessoa inicial, direção contínua,
  sensibilidade e retorno da cabeça conforme `config/training.config`.

O relatório é [validation-firstperson.json](validation-firstperson.json),
execução `d68c12b0-b019-4bc8-a0c0-681c554ba5fa`. Cada execução recebe um identificador novo
e registra seu resultado, inclusive quando falha.

SHA-256 do ZIP validado: `9b418112a6edaf27890a8d067c4ce9211f45092e4a409916bc243a1be89a8abf`.

## Evidências da simulação

| Verificação | Evidência |
| --- | --- |
| rendered game startup | Native simulation emitted live frames |
| walking and dribbling | Player moved 7.04 m |
| walking retains ball | Ball distance max/end 0.60/0.56 m; controlled 15/15 frames |
| animation playback | Original animation frames advanced |
| release and deceleration | Stopped speed 0.000 m/s |
| sprinting | Walk 5.00, sprint 7.77 m/s |
| sprinting retains ball | Ball distance max/end 0.98/0.72 m; controlled 16/16 frames |
| short pass | Functions [1, 4]; ball speed 25.04 m/s |
| through pass | Functions [1, 5]; ball speed 25.49 m/s |
| high pass | Functions [1, 6]; ball speed 16.91 m/s |
| shot | Functions [1, 8]; ball speed 31.76 m/s |
| aerial physics | Peak height 3.93 m |
| super cancel free movement | Player moved away from incoming ball to x=-67.87 m |
| off-ball sliding | Functions [1, 13] |
| finishing exercise | Player starts at x=29.62 m |
| goal detection | Goal counter 1 -> 2 |
| automatic ball reset | Ball returned to x=29.79 m |
| charged shot elevation | Light (22.7987, 0.6215), charged (35.0, 6.282) (speed, height); delivered charge {'light': 140, 'quick': 270, 'charged': 520, 'chip': 520} |
| quick shot elevation | Target 250 ms, delivered 270 ms; shot (28.1214, 2.0107) (speed, height) |
| LB chip trajectory | Chip (21.5621, 10.189); charged (35.0, 6.282) |
| free kick exercise | Player starts at [27.6379, -7.935, 0.0] |
| first person camera | Camera switches to first person |
| head free look with ball | Head yaw -1.01, player stays still |
| gradual head recenter | Head magnitude 1.03 -> 0.08 rad after input release |
| head look does not steer dribbling | Player delta [6.4785, 0.1978]; head turns independently |
| straight dribbling | Forward/side displacement [8.748999999999999, -0.1691] m |
| straight movement retains ball | Ball distance max/end 0.57/0.47 m; controlled 18/18 frames |
| reset cancels buffered shot | Functions [1]; no stale shot after reset |
| forward before turns retains ball | Ball distance max/end 0.56/0.48 m; controlled 12/12 frames |
| left turn retains ball | Ball distance max/end 0.44/0.44 m; controlled 13/13 frames |
| right reversal retains ball | Ball distance max/end 0.65/0.44 m; controlled 18/18 frames |
| backward turn retains ball | Ball distance max/end 0.64/0.29 m; controlled 13/13 frames |
| stopping after turns retains ball | Ball distance max/end 0.59/0.39 m; controlled 7/7 frames |
| stopping after turns releases movement | Stopped speed 0.000 m/s |
| restart after turns retains ball | Ball distance max/end 0.60/0.44 m; controlled 21/21 frames |
| turning uses original ball-control animations | Functions [1, 2] |
| close control diagonal retains ball | Ball distance max/end 0.66/0.59 m; controlled 22/22 frames |
| close control reversal retains ball | Ball distance max/end 0.58/0.40 m; controlled 16/16 frames |
| first person sprint retains ball | Ball distance max/end 0.97/0.66 m; controlled 26/26 frames |
| original knock-on and recovery | Long-touch distance max 2.19 m; recovered to 0.68 m after releasing RT |
| pass releases possession | Ball distance 25.67 m |
| off ball idle does not chase | Idle displacement 0.000 m; speed 0.000 m/s |
| off ball movement is free after pass | Sideways displacement 3.69 m without super cancel |
| manual approach recovers passed ball | Recovered in 12.4 s; ball distance 0.49 m; functions [1, 2] |
| off ball FPS turning | Yaw changed -0.80 rad without ball |
| first person forward movement | Player moved 6.05 m |
| front stadium remains visible | Central distant roof covers 97.9% of inspection band |
| ball stays above turf | Minimum ball center 0.110 m |
| finite physics state | 1854 live samples are finite |
| rendered foot contact correction | 271 rendered foot corrections; median error 0.176 -> 0.063 m |
| external camera restoration | First person cycles back to external view |
| clean shutdown | Exit status 0 |

As medidas são amostras desta execução. A base seleciona animações e usa
atributos e componentes aleatórios; esses números não são garantidos para
todos os jogadores e situações. A captura de frente, a visão para baixo e
o retorno à câmera externa também foram inspecionados durante a integração.

## Correções e critérios de teste

O controle remove pequenas entradas laterais perto das direções retas,
preserva diagonais e intensidade do analógico, e mantém o referencial da
condução independente das pequenas rotações da animação em repouso.
A condução conserva `AI_GetBallControlMovement` entre eventos de toque,
com a seleção original de passos e de alcance. A substituição por movimento
puro do analógico fazia o jogador seguir sozinho quando uma inversão não
possuía uma animação de toque imediatamente compatível. O alcance reduzido
e a ordenação adicional pelo pé dominante foram retirados; a tolerância no
evento de toque voltou aos 40 cm originais. A combinação RB+RT mantém o
knock-on original durante o domínio; o super cancel continua disponível
quando não há posse, conforme a regra original.

A entrada no domínio admite velocidade relativa de até 10 m/s, com
limite de 12 m/s durante a condução. O limite anterior de entrada era
8 m/s, justamente a velocidade máxima de corrida, e podia atrasar a
recepção de uma bola parada até ela atingir os volumes do corpo.

Sem bola, o treino substitui a perseguição automática do jogador designado
pelo movimento informado. O teste verifica que ele fica parado sem entrada,
pode afastar-se após um passe sem super cancel, e recupera a bola por uma
aproximação manual, sem reset, F2 ou reposicionamento artificial.
Reiniciar o treino também reinicia o controlador humano, cancelando cargas
e ações pendentes do exercício anterior. Isso é verificado ao reiniciar
durante a carga de um chute e conferir que ele não dispara depois.

O chute atinge carga máxima em 520 ms. A curva de elevação responde antes,
com um toque médio de cerca de 250 ms. O teste aguarda a carga observada
pela simulação e registra o contador observado, limitado a 520 ms; eventos X11
podem chegar entre amostras de telemetria. A indicação de 250 ms é o alvo do
teste, e o relatório inclui a duração observada. O contador original ainda
pode avançar durante a preparação da animação, após saturar a força.
O teste de gol conduz o jogador até cerca de seis metros da linha e usa
carga máxima para conferir travessia, rede, contagem única e reset. Isso
separa a detecção de gol da entrega tardia de key-up pelo renderizador por
software: um chute mais carregado de 22 metros pode passar acima da trave.
As curvas de força e elevação continuam verificadas separadamente.

O jogador é destro, com qualidade de domínio 0,72 no pé esquerdo contra 1,0
no direito. A diferença conserva somente 2,8% do impulso recebido a mais no pé esquerdo,
sem aumentar a força, reduzir o alcance ou mudar a escolha dos passos.
Não adiciona direção lateral aleatória à locomoção. A perna de contato recebe
uma correção com dois ossos, limitada a 25 cm no esqueleto base, durante uma
janela curta em torno do toque. O comprimento dos ossos é preservado.
A telemetria registra o erro da pose antes e depois do ajuste.

O shader antigo convertia profundidade acima de 0,999 em céu. Com o plano
próximo de 5,5 cm, isso apagava o estádio a partir de cerca de 45 m. Agora
somente profundidade 1,0 é céu. A seleção vertical de geometria acompanha
o FOV real da câmera, e a projeção usa o FOV do quadro atual.
Uma faixa central do teto distante é verificada na imagem renderizada,
considerando a pequena variação vertical da câmera animada. A arquibancada
clara não é classificada como céu. O critério foi conferido nas capturas
anteriores: cobertura de 0% com o estádio cortado e 100% com o shader corrigido.

O reset restaurava a direção do corpo para -Y independentemente da direção
do exercício. Agora restaura o ângulo e a direção corretos. A cabeça local
é ocultada por submesh, preservando a gola, e a câmera usa o mesmo fator de
altura da pele para acompanhar o pescoço interpolado. O nome do próprio
jogador também deixa de obstruir a visão em primeira pessoa.

A locomoção do treino pode reavaliar animações de movimento durante a posse
e longe da bola. Mantém blend, limites de aceleração e quadros de contato
das ações; reduz a espera mínima entre revisões de movimento para 80 ms.
O analógico conserva a intensidade da entrada em vez de virar uma direção
sempre a velocidade máxima.

Os testes sem bola primeiro afastam o jogador da trajetória da bola aérea.
Sem esse preparo, a bola pode chegar durante a espera da renderização por
software, e B corretamente muda de carrinho para passe alto. O teste do
retorno da cabeça aguarda a confirmação de que a entrada de olhar foi
solta; enviar um evento X11 não garante que a aplicação já o consumiu.
Cada pressão e soltura é confirmada pela telemetria do teclado/HID antes
que comece a medida de duração. As direções exatas do movimento também
são confirmadas antes das inversões. O leitor consome o log incrementalmente,
e os testes de carga observam o histórico da ação para não perder um chute
que já terminou entre consultas. A janela do teste de gol inclui toda a
ação, desde antes de pressionar X até a contagem e o reset.
Essas condições preservam as verificações de direção, domínio, movimento
e retorno gradual mesmo na renderização por software.

## Reprodução da perda da bola

O mesmo roteiro em primeira pessoa foi executado antes e depois da correção:
correr reto, andar, virar à esquerda, inverter à direita, voltar, parar,
retomar e inverter em domínio próximo. Na inversão à direita, a versão
anterior terminou a 4,298 m da bola, chegando a 7,660 m na retomada seguinte.
A versão corrigida terminou essa inversão a 0,735 m e a retomada a 0,441 m,
com domínio mantido em todas as amostras do roteiro. Os resultados completos
estão em [validation-possession.json](validation-possession.json).

Os testes renderizados permanentes agora medem a distância real entre bola
e jogador e exigem manutenção do domínio nas curvas, inversões, corrida,
domínio próximo, paradas e retomadas. Verificar somente o deslocamento reto
do jogador não detectava esta regressão.

## Limites da validação

A versão anterior com XInput teve seu funcionamento confirmado pelo usuário
no Xbox Series S. Esta versão conserva esse caminho de entrada. Sua
renderização, latência, Bluetooth e sensação da primeira pessoa ainda
precisam ser avaliados no Windows 11 do usuário. Não há Windows nem Xbox
físico conectado na máquina de compilação.

As colisões de corpo usam cápsulas de pernas, tronco e cabeça; não são
colisões por triângulo de cada membro ou roupa. A falta é um exercício
parado sem barreira, adversários ou goleiro. Não foram validados todos os
clips individualmente, todas as situações aéreas, partidas antigas, ligas,
carreira ou online. Não houve comparação com o motor de uma versão de PES.
Os recursos de campo, modelo e animações originais são preservados; código
de bola, câmera, controle e locomoção foi adaptado conforme documentado.
