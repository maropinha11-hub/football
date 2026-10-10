# Validação da gameplay em primeira pessoa

Verificação em 2026-10-10 UTC no ambiente Linux Debian 13 x86_64. O jogo
real foi renderizado por Mesa/OpenGL em Xvfb, com áudio OpenAL nulo.
O executável Windows foi compilado para x64 com MinGW GCC 14.2 e vcpkg.

## Resultados

- Compilação nativa e Windows: concluídas, status zero.
- CTest: 1 teste executado e aprovado; 46 verificações de controles SDL,
  movimento relativo à visão, olhar com bola, retorno da cabeça, carga de
  chute e varredura de colisão. Nenhum teste ignorado.
- Jogo renderizado: 28 verificações aprovadas, com eventos X11 e
  telemetria real da simulação. Usa a configuração que vai no pacote,
  com resolução reduzida e câmera externa inicial para os exercícios prévios.
- Recursos originais: 510 arquivos de `data` conferidos contra hashes da
  importação por `scripts/verify_upstream.py --assets-only`.
- Pacote Windows: ZIP íntegro, PE32+ GUI x64, 26 DLLs de runtime; imports
  recursivos satisfeitos pelas DLLs do pacote ou APIs do Windows 11,
  incluindo XInput, AVRT e o contrato `api-ms-win-core-synch-l1-2-0`.
- Configuração do ZIP conferida: primeira pessoa inicial, direção contínua,
  sensibilidade e retorno da cabeça conforme `config/training.config`.

O relatório é [validation-firstperson.json](validation-firstperson.json),
execução `1922c162-63bb-4d45-974b-11dd729d0c2c`. Cada execução recebe um identificador novo
e registra seu resultado, inclusive quando falha.

SHA-256 do ZIP validado: `d1493a6a8ea95b49dd4917c5a09bcfc5671a95847fe90cd653ac8090ae58cc85`.

## Evidências da simulação

| Verificação | Evidência |
| --- | --- |
| rendered game startup | Native simulation emitted live frames |
| walking and dribbling | Player moved 6.54 m |
| animation playback | Original animation frames advanced |
| release and deceleration | Stopped speed 0.000 m/s |
| sprinting | Walk 5.00, sprint 7.83 m/s |
| short pass | Functions [1, 4]; ball speed 25.00 m/s |
| through pass | Functions [1, 5]; ball speed 24.93 m/s |
| high pass | Functions [1, 6]; ball speed 22.95 m/s |
| shot | Functions [1, 8]; ball speed 25.21 m/s |
| aerial physics | Peak height 3.94 m |
| super cancel free movement | Player moved away from incoming ball to x=-8.42 m |
| off-ball sliding | Functions [1, 13] |
| finishing exercise | Player starts at x=29.75 m |
| goal detection | Goal counter 0 -> 1 |
| automatic ball reset | Ball returned to x=29.79 m |
| charged shot elevation | Light (19.4274, 0.1814), charged (30.5488, 3.5669) (speed, height) |
| LB chip trajectory | Chip (20.5631, 8.7103); charged (30.5488, 3.5669) |
| free kick exercise | Player starts at [28.1211, -7.8597, 0.0] |
| first person camera | Camera switches to first person |
| head free look with ball | Head yaw -1.03, player stays still |
| gradual head recenter | Head magnitude 1.24 -> 0.11 rad after input release |
| head look does not steer dribbling | Player delta [6.4858, -0.8712000000000001]; head turns independently |
| off ball FPS turning | Yaw changed -0.55 rad without ball |
| first person forward movement | Player moved 2.70 m |
| ball stays above turf | Minimum ball center 0.110 m |
| finite physics state | 611 live samples are finite |
| external camera restoration | First person cycles back to external view |
| clean shutdown | Exit status 0 |

As medidas são amostras desta execução. A base seleciona animações e usa
atributos e componentes aleatórios; esses números não são garantidos para
todos os jogadores e situações. A captura de frente, a visão para baixo e
o retorno à câmera externa também foram inspecionados durante a integração.

Capturas: [primeira pessoa](../artifacts/firstperson-forward.png),
[olhando para baixo](../artifacts/training.png) e
[câmera externa](../artifacts/training-external.png).

## Correções e critérios de teste

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
Essas condições são observadas pela telemetria, mantendo as verificações
de direção, movimento e retorno gradual.

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
