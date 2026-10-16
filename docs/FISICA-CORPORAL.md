# Teste de animação e física corporal

Extraia o pacote Windows completo numa pasta nova e abra **treino-fisico.bat**.
O centro de treinamento abre com a camada física ligada. **R3/Tab** mostra o
corpo de fora. **F7** compara ligado/desligado, **F8** aplica um impacto leve,
**F9** aplica um impacto forte e **R/View** reinicia, inclusive durante a queda.
Os comandos Xbox, F4/F5/F6, a câmera e a cabeça continuam disponíveis.
**partida-fisica.bat** permite experimentar a mesma camada com os times da CPU.
Os atalhos `run-training.bat` e `jogar-partida.bat` conservam os modos aprovados.

## O que foi implementado

A locomoção usa as animações nativas como referência. Uma camada procedural
adapta a postura à aceleração, à velocidade de giro, ao alcance da bola e à
proximidade/lado de um adversário. Ela acrescenta inclinação, contrarrotação
do tronco, compensação dos braços e proteção lateral. Os pés de apoio são
resolvidos com IK de duas articulações, preservando os comprimentos dos ossos.

Os pequenos alcances para pés, tronco e cabeça são planejados antes do evento
de contato. O deslocamento adicional aproxima-se do alvo com velocidade
limitada: 0,55 m/s e até 14 cm para pés, com limite menor de 4,5 cm no tronco.
A seleção original de animações e de jogadas continua atuando. A camada não
dispara um chute por a bola estar próxima: o impulso autorizado ainda exige
contato na malha ponderada do personagem.

Um impacto leve perturba o equilíbrio com resposta amortecida. Um impacto
forte libera a sustentação: o corpo passa a ter movimento da raiz, gravidade,
velocidades angulares nas articulações, limites de rotação e contatos de
cápsulas com o chão. Cortes sustentados em velocidade alta também podem
causar perda de equilíbrio. Após a queda, a recuperação assistida conduz
gradualmente o corpo até a postura nativa e devolve o controle.

A integração tem três estados: ativo, caindo e recuperando. Durante os dois
últimos, a condução e os chutes deixam de comandar a raiz. A bola permanece
livre e continua colidindo com a malha física; botões pressionados durante
a queda não deixam um chute antigo pendente para depois de levantar.

Na partida experimental, o contato nativo entre jogadores envia um impulso
à camada física do ator controlado. A CPU conserva a versão de gameplay
aprovada. Há um intervalo entre respostas ao mesmo contato para não tratar
um encostão contínuo como uma sequência de pancadas independentes.

## Variação das animações

O banco original tem **293 arquivos**: 75 de movimento, 45 de condução,
40 domínios, 37 passes rasteiros, 15 passes altos, 17 chutes, 28 defesas,
19 desequilíbrios/quedas, 7 disputas, 6 carrinhos e 4 especiais. Os domínios
adicionais do treino permanecem no banco separado.

A nova camada reutiliza essas referências com parâmetros contínuos. Um
mesmo clip pode resultar em posturas diferentes conforme o contexto, sem
criar cópias idênticas nem trocar a fase do pé que deveria tocar a bola.
O teste numérico cruza **270 contextos**: três velocidades, cinco curvas,
três alturas de alcance, três deslocamentos laterais e duas distâncias de
adversário, usando poses de condução, chute e domínio do banco nativo.
Esses contextos são testes de variação procedural; não são novos clips de
captura de movimento, nem prova de cobertura de todas as jogadas do futebol.

## Pesquisa consultada

O registro de acesso e os hashes estão em
[physical-rig-research-sources.json](physical-rig-research-sources.json).
Os artigos e vídeos externos foram usados para estudo, sem serem incluídos
no pacote do jogo.

| Fonte efetivamente acessada | Observação e aplicação |
| --- | --- |
| Macklin, Müller e Chentanez, [XPBD, 2016](https://matthias-research.github.io/pages/publications/XPBD.pdf), DOI [10.1145/2994258.2994272](https://doi.org/10.1145/2994258.2994272) | PDF integral consultado pelo espelho dos autores no GitHub. Fundamenta a projeção de contatos com complacência e multiplicadores acumulados por passo. |
| Peng et al., [DeepMimic, 2018](https://xbpeng.github.io/projects/DeepMimic/), DOI [10.1145/3197517.3201311](https://doi.org/10.1145/3197517.3201311) | Artigo integral, página dos autores e implementação de PD implícito consultados. Mostra a importância de referência de movimento, controle de articulações e objetivos de tarefa. Este experimento usa controle analítico; não foi treinada uma política de aprendizado por reforço. |
| [Modelo OpenSim Gait10dof18musc](https://github.com/opensim-org/opensim-models/tree/master/Models/Gait10dof18musc) | Consultadas massas, inércias, articulações e créditos do modelo. Ajuda a distinguir esqueleto de animação de modelo biomecânico. Os próprios créditos limitam o uso científico do modelo simplificado. Nenhum músculo, malha ou arquivo OpenSim foi importado. |
| [SoccerKicks](https://github.com/nayariml/SoccerKicks) | Descrição do conjunto de 38 vídeos e dos métodos de reconstrução 2D/3D consultada. A reconstrução monocular tem ambiguidades e não mede diretamente forças de contato. |
| [FilteredSoccerPose](https://github.com/Jacopogr/FilteredSoccerPose) | Projeto de análise de poses consultado e sequência `12_penalty` analisada: 121 quadros, cerca de 3,63 s, com vídeo original e sobreposição de poses. É uma referência visual de chute com bola parada, não uma validação biomecânica de todas as ações. |
| [AI4Animation](https://github.com/sebastianstarke/AI4Animation) | Documentação consultada sobre repertório, fases de movimento e síntese a partir de dados. Não foi incorporada uma rede neural desse projeto. |

Na sequência de chute observada, as fases relevantes são aproximação,
apoio ao lado da bola, preparação da perna que chuta, extensão no contato
e continuação do movimento com rotação do corpo. Os braços participam do
equilíbrio e a perna de apoio não acompanha a bola durante todo o ciclo.
Isso orientou a preservação da fase original do toque, os apoios e a redução
das correções durante uma ação rápida. A imagem monocular não permite
atribuir medidas exatas de torque, profundidade ou ângulos 3D a esse atleta.

As consultas diretas a PubMed/PMC, Crossref, FIFA Training Centre e arXiv
foram bloqueadas pela rede, inclusive após a tentativa com permissão ampliada.
Os PDFs dos autores, o código e o vídeo acima foram acessados por seus
espelhos públicos no GitHub. Não houve acesso a uma biblioteca completa de
vídeos de cabeçadas, divididas, giros e domínios; essas ações continuam usando
suas referências nativas e precisam de validação específica adicional.

Como referências bibliográficas para aprofundamento, ficaram identificados
Lees et al., *The biomechanics of kicking in soccer: a review*, DOI
[10.1080/02640414.2010.481305](https://doi.org/10.1080/02640414.2010.481305),
Hof et al., *The condition for dynamic stability*, DOI
[10.1016/j.jbiomech.2004.03.025](https://doi.org/10.1016/j.jbiomech.2004.03.025),
e de Leva, *Adjustments to Zatsiorsky–Seluyanov's segment inertia parameters*,
DOI [10.1016/0021-9290(95)00178-6](https://doi.org/10.1016/0021-9290(95)00178-6).
Os textos integrais desses três trabalhos não foram acessados nesta sessão.
As frações segmentares e os limites usados no protótipo são aproximações
de desenvolvimento, com divisões próprias para os 13 ossos do modelo.

## Cálculos e integração

- O jogo mantém seu passo de 10 ms; a camada usa dois subpassos de 5 ms.
- Os comprimentos dos segmentos são os do modelo nativo e são impostos por
  cinemática direta. A camada não estica os ossos para alcançar a bola.
- A inclinação usa uma fração limitada da razão entre aceleração horizontal
  e gravidade. O giro do tronco e dos braços acompanha a velocidade angular
  filtrada, com redução durante chutes e domínios.
- O alcance tem um envelope de antecipação de até 240 ms. Alvos fora do
  pequeno intervalo permitido continuam a cargo do seletor e da aproximação
  original; a camada não alcança bolas arbitrariamente distantes.
- Os contatos de chão usam a forma XPBD `Δλ = -(C + αλ)/(w + α)`, com a
  contribuição angular da raiz em `w` e complacência dividida por `dt²`.
  As cápsulas dos segmentos são aproximações da superfície para o chão.
- A recuperação usa PD com denominador implícito e limites de aceleração
  angular. As rotações retornam progressivamente à referência nativa.
- O indicador de apoio registra uma aproximação de centro de massa
  extrapolado `x + v/sqrt(g/h)`. Ele é diagnóstico; não constitui uma prova
  de equilíbrio de um humano real.
- A pose física é amostrada no relógio da simulação e aplicada na malha pelo
  mesmo histórico temporal utilizado nos contatos. A câmera acompanha a
  cabeça interpolada, com horizonte estável e altura mínima junto ao chão.
  Quando o motor amostra mais de uma fase de animação no mesmo passo, a pose
  é recalculada sem integrar novamente a dinâmica. Isso preserva o instante
  de contato em chutes rápidos e nas trocas de clip.

O núcleo está em `physical_rig.cpp`; `humanoid_physical.cpp` faz a ligação
com animação, bola, controles e renderização. A referência de simulação
nativa é atualizada também durante quedas prolongadas, evitando manter
um snapshot que sai da janela de histórico de 300 ms.

## Limites do experimento

A locomoção ativa continua conduzida por animações, com deformações
procedurais e IK. A dinâmica livre fica nas quedas; a recuperação é assistida.
Preparações e eventos de passe, chute e cabeçada preservam a postura nativa,
inclusive quando a ação está esperando a bola chegar. As correções de alcance
continuam pequenas e condicionadas ao contato real.
O contato com o solo resolve a raiz articulada com proxies e amortecimento,
sem um solucionador completo de inércias acopladas de cada corpo rígido.
O corpo a corpo continua usando a detecção e a separação nativas, acrescentando
uma resposta física ao jogador controlado. Não há contato articulado completo
nos 22 jogadores, resolução geral de colisão de cada membro consigo mesmo,
músculos personalizados, tecido mole ou validação médica de impactos.
A colisão passiva da bola com o corpo conserva o filtro nativo de bola aérea;
bolas rasteiras junto a um corpo caído ainda não têm cobertura articulada geral.

Essas aproximações permitem experimentar a variedade de posturas sem trocar
o motor inteiro. Os números de massa, inércia, amortecimento e limites
articulares ainda precisam de ajuste visual e de testes com mais movimentos
e biotipos. O retorno de uma queda ainda pode parecer assistido. A qualidade
de cada transição deve ser avaliada jogando antes de promover o experimento
ao treino padrão.

## Verificação

`physical_rig_tests` verifica estabilidade numérica, apoios, comprimento dos
ossos, alcance gradual, queda, recuperação, reset e 270 contextos de poses.
`tests/training_physical_rig_smoke.py` exercita o jogo renderizado com entrada
SDL de um Xbox virtual, incluindo o retorno ao controle depois de quedas.
O cenário `--match` exercita colisões reais com jogadores da CPU.
Na versão entregue, passaram 95 verificações renderizadas em seis cenários,
19 verificações do núcleo, cinco testes CTest e 107 conferências do pacote.
Os 270 contextos fazem parte do teste numérico, sem representar novos clips.
As imagens [de condução](images/physical-dribble.png),
[do impacto](images/physical-fall.png) e [após a recuperação](images/physical-recovered.png)
foram capturadas nessa execução.
Os resultados e as limitações observadas estão em
[physical-rig-validation.json](physical-rig-validation.json).

Os testes gráficos são executados no Linux. O pacote Windows x64 é compilado
e conferido quanto a executável, DLLs, recursos e integridade; a execução
com Windows 11 e controle físico precisa ser verificada no computador de jogo.
