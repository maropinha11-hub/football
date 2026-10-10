# Validação da gameplay em primeira pessoa

Verificação em 2026-10-10 UTC no ambiente Linux Debian 13 x86_64. O jogo
real foi renderizado por Mesa/OpenGL em Xvfb, com áudio OpenAL nulo.
O executável Windows foi compilado para x64 com MinGW GCC 14.2 e vcpkg.

## Resultados

- Compilação nativa e Windows: concluídas, status zero.
- CTest: 1 teste executado e aprovado; 58 verificações de controles SDL,
  movimento relativo à visão, olhar com bola, retorno da cabeça, carga de
  chute e varredura de colisão. Nenhum teste ignorado.
- Jogo renderizado: 32 verificações aprovadas, com eventos X11 e
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
execução `bc498b5c-dd19-4a02-b817-6fbc26929e8a`. Cada execução recebe um identificador novo
e registra seu resultado, inclusive quando falha.

SHA-256 do ZIP validado: `0d99b58dc8930fc4a4395c6acab79aa031859d2d6bc562ad6c039d97b3181a67`.

## Evidências da simulação

| Verificação | Evidência |
| --- | --- |
| rendered game startup | Native simulation emitted live frames |
| walking and dribbling | Player moved 4.74 m |
| animation playback | Original animation frames advanced |
| release and deceleration | Stopped speed 0.000 m/s |
| sprinting | Walk 5.00, sprint 7.88 m/s |
| short pass | Functions [1, 4]; ball speed 25.18 m/s |
| through pass | Functions [1, 5]; ball speed 25.49 m/s |
| high pass | Functions [1, 6]; ball speed 23.51 m/s |
| shot | Functions [1, 8]; ball speed 32.29 m/s |
| aerial physics | Peak height 3.94 m |
| super cancel free movement | Player moved away from incoming ball to x=-8.42 m |
| off-ball sliding | Functions [1, 13] |
| finishing exercise | Player starts at x=30.25 m |
| goal detection | Goal counter 0 -> 1 |
| automatic ball reset | Ball returned to x=30.65 m |
| charged shot elevation | Light (27.3104, 1.9741), charged (35.0, 6.282) (speed, height) |
| quick shot elevation | Quarter-second shot (29.7502, 2.8314) (speed, height) |
| LB chip trajectory | Chip (22.0, 10.181); charged (35.0, 6.282) |
| free kick exercise | Player starts at [28.2397, -7.929, 0.0] |
| first person camera | Camera switches to first person |
| head free look with ball | Head yaw -1.07, player stays still |
| gradual head recenter | Head magnitude 1.34 -> 0.13 rad after input release |
| head look does not steer dribbling | Player delta [4.1484, 0.0]; head turns independently |
| straight dribbling | Forward/side displacement [9.4484, 0.0] m |
| off ball FPS turning | Yaw changed -1.28 rad without ball |
| first person forward movement | Player moved 2.28 m |
| front stadium remains visible | Central distant stands cover 83.8% of inspection region |
| ball stays above turf | Minimum ball center 0.110 m |
| finite physics state | 704 live samples are finite |
| rendered foot contact correction | 40 rendered foot corrections; median error 0.205 -> 0.081 m |
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
A assistência de movimento do treino não altera a direção do analógico;
as ações de toque conservam sua seleção e suas restrições de alcance.

O chute atinge carga máxima em 520 ms. A curva de elevação responde antes,
com um toque médio de cerca de 250 ms. O teste aguarda a carga observada
pela simulação, pois eventos X11 podem chegar entre amostras de telemetria.
O teste de gol usa carga curta suficiente para chegar à baliza sem ultrapassar
sua altura; um toque mínimo pode perder velocidade antes de percorrer 22 m.

O jogador é destro, com qualidade de domínio 0,72 no pé esquerdo contra 1,0
no direito. Isso reduz alcance de assistência e precisão na absorção do impulso,
e favorece animações de domínio com o direito quando são compatíveis.
Não adiciona direção lateral aleatória à locomoção. A perna de contato recebe
uma correção com dois ossos, limitada a 25 cm no esqueleto base, durante uma
janela curta em torno do toque. O comprimento dos ossos é preservado.
A telemetria registra o erro da pose antes e depois do ajuste.

O shader antigo convertia profundidade acima de 0,999 em céu. Com o plano
próximo de 5,5 cm, isso apagava o estádio a partir de cerca de 45 m. Agora
somente profundidade 1,0 é céu. A seleção vertical de geometria acompanha
o FOV real da câmera, e a projeção usa o FOV do quadro atual.
Uma região central da arquibancada distante é verificada na imagem renderizada.

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
