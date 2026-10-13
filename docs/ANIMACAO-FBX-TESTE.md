# Animações FBX no treino

A condução aprovada `DefenseJog_LoopF` é o padrão. L3 e T não alternam mais
animações. Extraia o ZIP completo em uma pasta nova e abra `run-training.bat`.
Os recursos das duas animações já acompanham o pacote.

| Tecla | Exercício na posição atual do jogador |
| --- | --- |
| F4 | Receber passe rasteiro |
| F5 | Receber bola na altura do peito |
| F6 | Receber cruzamento alto |
| R3 / Tab | Alternar câmera; a terceira opção mostra o corpo de perto |
| R / View | Reiniciar |

Para testar o peito, solte os analógicos e pressione F5. O novo domínio é
escolhido quando o jogador está parado, não solicita passe/chute e uma bola
chega de frente à região do peito. Preparar A permite jogar de primeira;
bolas rasteiras e bolas de cabeçada continuam usando as ações nativas.
F3 e a tecla 5 continuam sendo o exercício de falta.

## Condução e postura

O ciclo de condução toca completo, independentemente das trocas do seletor
nativo. Os pés encostam nos triângulos das chuteiras; o preditor da bola
calcula seu percurso até o próximo passo. As pequenas correções de alcance
preservam os comprimentos das pernas e a orientação do calçado. Entre
contatos, a perna cede à esfera sem aplicar forças adicionais à bola. Esse
ajuste fica limitado a 8 cm.

O tronco recebe 0,13 radiano adicional de inclinação. A cabeça acompanha
a direção da câmera, com limites de rotação do pescoço e interpolação no
mesmo relógio do corpo. A sensibilidade passa de 2,1 para 2,6 rad/s.
A velocidade normal sem RB é 3,6 m/s com o analógico inteiro. A corrida
usa 90% da velocidade de entrada original. A fase acompanha a velocidade real,
sem alterar o relógio de 10 ms. RB continua sendo corrida e RT fica reservado.
A entrada/saída da condução usa 240 ms; transições nativas usam 120 ms.
O próximo alvo de condução fica no pé direito. A esquerda continua fazendo
os passos e pode adquirir uma bola fora desse corredor; viradas mantêm
animações da outra perna como alternativa quando a direita não alcança.
O alcance e a volta dos pés são graduais, em incrementos de até 3 mm por
ajuste; uma sobreposição física exige separação imediata.
O ajuste usa a normal da superfície atingida, inclusive quando a bola passa
atrás da chuteira. O pé começa a preparar o alcance antes do marcador, sem
desfazer essa preparação a cada quadro. Não há novo impulso no mesmo ciclo.

Após soltar RB, a assistência permanece por até 1,6 s e termina num contato
real de recuperação. A velocidade extra de interceptação fica disponível
enquanto a bola ainda está se afastando. Uma condução nativa pode preparar a
entrada do ciclo novo com um toque físico; não reposiciona a bola à distância.
As previsões usam a direção e a velocidade que o ciclo vai assumir e a
velocidade final da animação de movimento durante transições.

Os parâmetros `training_walk_speed_scale`, `training_sprint_speed_scale` e
`training_prefer_right_foot` ficam no arquivo de configuração.

## Domínio Chest_Stand

O FBX fornecido tem 46 poses a 30 FPS, de frame 1 a 46: duração de 1,5 s.
Foi convertido para 151 amostras a 100 FPS, mantendo o último quadro, sem
fechar um loop. O deslocamento horizontal da recuperação foi preservado
com `--root-motion` e aplicado à posição real do jogador após o contato.
As rotações e o apoio são adaptados às proporções do modelo nativo.

O frame 11 da fonte é um **marcador de integração** para a apresentação do
peito. O FBX não contém trajetória da bola nem evento de contato. O marcador
ajuda a antecipar a pose; a mudança de velocidade da bola só acontece quando
sua esfera encontra a camisa na região do peito. O encontro é refinado
entre os passos de 10 ms e conserva o tempo restante do passo após o choque.
A bola perde velocidade, cai diante do jogador e permanece livre.

A ação entra em 180 ms e toca uma única vez. A apresentação inicial mantém
seu tempo; os passos de recuperação usam 85% da velocidade da fonte.
Enquanto espera o contato, frente/trás permitem ajuste de até 18 cm. Após
o contato, mover ou solicitar uma jogada retira a pose em até 180 ms.
A assistência original de interceptação é mantida para passes que chegam;
não transforma bolas afastando-se do jogador em recepções automáticas.

## Contatos das jogadas nativas

O motor usava marcadores de animação com tolerância de até 40 cm, além de
colisores auxiliares. No treino, esses marcadores continuam ajudando a
escolher as jogadas, mas o impulso exige contato com a malha real da parte
correspondente: chuteira, cabeça ou tronco. A distância positiva permitida
é de até 2 mm. Uma interpenetração é separada na superfície, conservando
movimento angular e histórico, antes do impulso nativo.

A perna pode ajustar o alcance com cinemática de duas articulações, sem
mudar seus comprimentos. Um deslocamento visual de apoio de até 2,5 cm
resolve a extensão máxima em passes parados. A posição do corpo e as
rotações corrigidas são armazenadas no mesmo relógio da bola a 100 Hz.
Não se move uma bola distante para um ponto de animação.

A pose de contato tem prioridade sobre a condução que está saindo. Após
interpolar os quadros, ambas as chuteiras são conferidas contra a esfera
desenhada. Se houver sobreposição, a perna cede localmente, até 18 cm, sem
alterar os comprimentos, a orientação do calçado ou a trajetória da bola.
Isso evita atravessamentos entre amostras e impulsos duplicados na virada.
Uma janela curta em torno do marcador permite o impulso no encontro físico,
uma única vez por jogada. Isso evita perder um passe porque o encontro ocorreu
alguns milissegundos antes ou depois do marcador. Cruzar com B durante a
corrida mantém o contexto de passe enquanto a bola está sob controle.

Bolas altas recebidas também usam a superfície do corpo para contatos
acidentais. Uma bola que atinge a cabeça não é registrada como domínio de
peito; a colisão usa a parte realmente atingida.

## Chutes e efeitos

X chega à carga máxima em 520 ms. A carga altera a velocidade e a elevação;
LB+X preserva o modificador mesmo ao soltar os dois botões e faz cobertura.
A tolerância do marcador antigo não reduz a força depois de confirmado um
contato real. Cabeçadas e voleios mantêm suas ações nativas.

A rotação é calculada pelo braço de alavanca entre o ponto na chuteira e
o centro da bola, cruzado com o impulso. Contatos laterais produzem curva;
contatos acima ou abaixo do centro produzem efeito vertical. Golpes fortes
com pouca rotação podem apresentar uma pequena oscilação aerodinâmica.
Esse último efeito é um modelo limitado e determinístico, também usado pelo
preditor, e não uma reprodução medida da aerodinâmica de uma bola específica.

## Quique e futuros gramados

No treino, `training_ground_bounce` passa de 0,62 para 0,70. Esse parâmetro
separa a restituição do gramado dos contatos com o jogador. Gravidade,
arrasto, atrito e rotação continuam no preditor da base. O teste de queda
com o jogador fora do caminho compara os dois valores.

## Converter novas fontes

Blender 4.3+ é necessário apenas para desenvolver/importar animações.
Quem joga no Windows não precisa instalar Blender.

```bash
blender -b --threads 2 --python-exit-code 1 \
  --python tools/animations/import_fbx.py -- \
  assets/animation-sources/Chest_Stand.fbx \
  data/media/training/Chest_Stand.anim --non-loop --contact-frame 11 --root-motion
```

Para conduções em loop, omita `--non-loop` e `--contact-frame`. O conversor
valida segmentos, lateralidade e continuidade. As proporções e superfícies
vêm de `tools/animations/native_rig_reference.json`. Os JSONs ao lado dos
clips registram origem, hashes, duração, FPS e limites da adaptação.
O contato e as condições de seleção de cada nova ação ainda precisam ser
calibrados: não são informações que um FBX sem bola fornece automaticamente.

As verificações desta entrega estão em `animation-receptions-validation.json`
e nos testes `training_chest_smoke.py`, `training_ball_bounce_smoke.py`,
`training_fbx_trial_smoke.py`, `training_fbx_handoff_smoke.py` e
`training_original_fps_smoke.py`. `training_contact_transition_smoke.py`
verifica também os pés desenhados durante as transições curtas.
A execução renderizada usa Linux e controle
SDL Xbox virtual. O Windows é compilado em x64 e verificado quanto a recursos,
DLLs e integridade; controle físico e GPU do usuário são testados no Windows.
