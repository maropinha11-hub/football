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
Na entrada, a fase usa a cadência prevista até a mistura terminar. A
velocidade residual de uma virada nativa não pode adiantar o toque antes
que a pose nova esteja completa. A escolha da primeira pose confere a
ponta da chuteira avançando, da mesma forma que a aquisição real da bola.
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
O alvo do domínio mantém a posição e orientação escolhidas na previsão,
mesmo quando o movimento nativo de fundo troca de animação. A cabeça
autorizada pelo clip é preservada antes do contato, para não interpor o
queixo entre a bola e o peito. O choque varre todo o percurso do passo.
Antes do contato, qualquer movimento sai do domínio parado e solicita
novamente uma recepção nativa, mantendo a assistência de interceptação.
O impulso de amortecimento no peito é calculado com a previsão real de
quique e atrito, para terminar à frente dos passos finais, sem novos toques
no ar. Há 120 ms de acomodação depois do contato e 120 ms no término,
seguidos de uma saída de pose em 180 ms. O movimento pode sair após o contato quando a bola já está descendo
ao alcance dos pés, antes dos passos finais. Sem novo comando, a animação
completa é preservada. Lados continuam chegando ao seletor de recepção;
a locomoção de espera permite antecipar ou recuar na direção do passe.
A assistência original de interceptação é mantida para passes que chegam;
não transforma bolas afastando-se do jogador em recepções automáticas.

## Contatos das jogadas nativas

O motor usava marcadores de animação com tolerância de até 40 cm, além de
colisores auxiliares. No treino, esses marcadores continuam ajudando a
escolher as jogadas, mas o impulso exige contato com a malha real da parte
correspondente: chuteira, cabeça ou tronco. A distância positiva permitida
é de até 2 mm. Uma interpenetração é separada na superfície, conservando
movimento angular e histórico, antes do impulso nativo.

O seletor conserva a ordem nativa de candidatos, mas confere a malha na
trajetória prevista antes de iniciar a jogada. A aproximação usa o movimento
do jogador inteiro; os ângulos gravados da perna não são esticados para
buscar uma bola distante. As trocas de movimento conservam a interpolação
do motor nativo e a condução aprovada.

A previsão também descarta uma aproximação que passe pelo outro pé. Um
contato de pé em corrida, passe ou chute planeja uma saída que deixe espaço
para a continuação da passada; o impulso ocorre uma vez, no contato real. O ajuste
visual residual de separação está limitado a 8 cm, conservando os comprimentos
e a orientação do calçado, e não busca a bola. A pose de contato tem prioridade
sobre a condução ou o domínio que está saindo. Bola, altura e rotação do corpo
usam o mesmo instante do passo de 10 ms.

Uma cabeçada pode usar um contato anterior ao marcador quando a cabeça já
encontra realmente a bola. Marcadores continuam selecionando a animação;
o impulso exige a parte correta do corpo e não usa a tolerância antiga de
40 cm para produzir um toque no vazio.

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

As verificações das correções de condução e recepção estão em
`natural-contact-validation.json` e `training_control_reception_smoke.py`.
A integração anterior está documentada em `animation-receptions-validation.json`
e nos testes `training_chest_smoke.py`, `training_ball_bounce_smoke.py`,
`training_fbx_trial_smoke.py`, `training_fbx_handoff_smoke.py` e
`training_original_fps_smoke.py`. `training_contact_transition_smoke.py`
verifica também os pés desenhados durante as transições curtas.
A execução renderizada usa Linux e controle
SDL Xbox virtual. O Windows é compilado em x64 e verificado quanto a recursos,
DLLs e integridade; controle físico e GPU do usuário são testados no Windows.

## Analógico parcial e corrida

A preferência pelo pé direito pertence à condução frontal FBX aprovada.
Corridas e viradas mantêm a ordem original dos candidatos nativos, sem
forçar uma perna inadequada. A preparação da passada FBX só se aplica à condução frontal acima de
3 m/s e depois da aceleração ou desaceleração. A velocidade manual
também fica restrita à condução sem RB acima de 3 m/s, preservando
a assistência original com o analógico parcial e na corrida. Domínios nativos de condução usam uma janela curta em torno do
marcador original, para reconhecer o pé que já encostou na esfera;
passes/chutes também exigem contato físico. Os multiplicadores de velocidade continuam
em 0,72 (normal) e 0,90 (RB), com simulação em tempo real.

Os testes específicos desta correção são `training_natural_actions_smoke.py`
e `training_reception_commit_smoke.py`, com contato de cada ação em corrida,
viradas durante a carga, recepções repetidas e mudança de comando após o peito.

## Retomar a condução e interromper o domínio

Ao sair parado, a entrada da condução mantém a raiz parada durante a mistura
até o primeiro contato físico da chuteira. A fase e o pequeno ajuste do pé
são preparados gradualmente para esse contato; o toque considera a aceleração
nativa até a próxima passada. Nas demais entradas, a preparação usa a posição
prevista da bola e do jogador ao final da mistura. Uma entrada que não alcança
a bola devolve a assistência nativa ao terminar sua janela de contato.

A interrupção de `Chest_Stand` preserva uma transição de 180 ms também quando
o seletor prepara outra animação de contato. O personagem acompanha o primeiro
quique até o toque seguinte, evitando caminhar sobre a bola enquanto ela sobe.
O RB mantém o movimento e a seleção de animações nativos, e sua soltura conserva
a assistência quando a bola ainda está mais rápida. O impulso do contato real
considera a continuação da passada para manter a chuteira fora da bola;
a preparação de um chute admite uma correção limitada maior que a corrida.
O alvo seguinte da condução corresponde à distância restante da fase, com
o tempo calculado pela curva nativa de aceleração ou desaceleração. Reduzir
o analógico durante um toque não encurta indevidamente essa distância.

`training_stationary_handoff_smoke.py` verifica pausas, apertar/soltar RB,
interrupções após o peito, contato real e continuidade das rotações desenhadas.
Os resultados desta versão estão em `stationary-handoff-validation.json`.
