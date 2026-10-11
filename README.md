# Centro de treinamento — Gameplay Football

Centro de treinamento nativo em C++/SDL2/OpenGL, derivado do
[Gameplay Football de vi3itor](https://github.com/vi3itor/GameplayFootball),
revisão `68159a2f0f96eec8ebba26ab7820130f36b922a7`.

Usa o jogador, o campo, o esqueleto, os 293 arquivos de animação e a física
da base original, com controles em primeira pessoa e ajustes de chutes e
colisões no treino. Carreira e partidas online ficam para etapas posteriores.

Em primeira pessoa, sem bola, o direito vira a visão e o esquerdo move e
desloca lateralmente em relação a ela. Com bola, o esquerdo conduz e o
direito olha ao redor sem alterar a direção do movimento. Após virar, empurre
o esquerdo para frente para seguir a nova frente; mantê-lo à direita continua
a curva para a nova direita. Baixo pede uma virada para trás; mantê-lo
repete a virada quando o corpo completa a anterior. RT mantém essa direção e ajusta o domínio,
sem virar automaticamente para o gol. A cabeça retorna
ao centro após uma breve pausa; a câmera acompanha o corpo interpolado e
oculta a cabeça e o cabelo do jogador local para evitar obstrução.

Não é uma decompilação completa do PES. Os links iniciais contêm Gameplay Football;
não contêm o motor nem as animações do PES. Fidelidade à base aberta e
equivalência ao PES são verificações diferentes. Consulte
[a pesquisa técnica](docs/RESEARCH.md) para a origem e os limites da implementação.

O [estudo PES3 dentro do treino](docs/PES3-ANIMACOES-NO-TREINO.md) reproduz os
1.105 clips recebidos em um esqueleto de 19 ossos ao lado do jogador. Na versão
Windows, use `importar-pes3.bat` com seu `fpsoccer-pes-nucleo-v14.zip`, depois
`estudar-pes3.bat`. Há pausa, avanço de fase e troca de clip. A ligação definitiva
à malha, a seleção completa de ações e os contatos PES ainda precisam ser integrados;
`run-training.bat` mantém a gameplay nativa aprovada.

O [teste de poses na malha nativa](docs/PES3-CORPO-NATIVO.md), ativado com V
no estudo, alinha os membros usando a pose reta da malha e as direções dos
segmentos PES, conserva os comprimentos e corrige o apoio visual dos pés.
Retomar os comandos restaura as animações nativas. A câmera externa aproxima
o corpo durante a inspeção. A seleção automática das jogadas PES e seus
contatos continuam pendentes.

A [atualização Windows de orientação](artifacts/football-windows-corrigir-orientacao.zip)
permite substituir apenas `gameplayfootball.exe` na instalação existente.
Ela corrige a frente da animação, os pares esquerdo/direito e a flexão dos
membros. A pasta `pes3`, as DLLs e os recursos já instalados continuam em uso.

O estudo do PES 3 e a conferência dos arquivos recebidos estão em
[docs/PES3.md](docs/PES3.md). O [laboratório offline de animações](artifacts/pes3-animation-lab.zip)
permite explorar 1.105 clips e exportar candidatos para o catálogo: extraia
o ZIP e abra `abrir-laboratorio.html` com Edge ou Chrome. É uma ferramenta de
pesquisa; a substituição das animações do jogador e da física continua pendente.

O [processo de recuperação do código PES 3](docs/PES3-ACTIONS.md) acrescenta
um mapa automático de referências para 506 clips e reescritas verificadas
de três roteamentos. No [laboratório com filtros de ação](artifacts/pes3-action-research.zip),
extraia o ZIP e abra `abrir-laboratorio.html` para consultar e exportar o mapa
sem classificação manual. Os corpos completos das ações e as condições
físicas ainda precisam de recuperação e validação.

A [etapa com o save state PES 3](docs/PES3-SAVESTATE.md) recompila em C++ os
caminhos alcançados e confere 276 chamadas com a memória do treino. No
[laboratório com reexecução](artifacts/pes3-savestate-research.zip), expanda
“Seleção reexecutada no treino” para consultar os cenários e clips registrados.
Esta entrega ainda não integra as animações PES ao executável jogável.

A [montagem de poses PES 3](docs/PES3-POSES.md) acrescenta 305 cenários,
1.113 comparações de chamadas e helpers semânticos C++ de quaternion,
matriz, rotação e mistura, com 5.434 comparações em bits. No
[laboratório de poses](artifacts/pes3-pose-research.zip), expanda “Poses do
treino PES” para consultar campos capturados e saídas reexecutadas. A
divergência contra as poses finais do emulador, a calibração dos ossos e
os contatos continuam pendentes antes da importação para o jogo Windows.

A [reescrita do esqueleto PES 3](docs/PES3-RIG.md) acrescenta oito operações
com estruturas próprias, 1.428 comparações aprovadas no modelo declarado e
conferência dos 6.688 componentes de rotação com as chaves compactadas.
O [pacote numérico](artifacts/pes3-rig-research.zip) permite recompilar e repetir
os testes sem arquivos do PES. A investigação corrige a etapa usada para
comparar poses; diferenças em bits e a integração no treino seguem abertas.

A [reescrita da seleção de locomoção PES 3](docs/PES3-SELECTION.md) acrescenta
92 decisões conferidas com ajuste de velocidade em sequência, 1.153 cenários
independentes de velocidade e um mapa automático de condições. O
[pacote de código](artifacts/pes3-selection-research.zip) repete as comparações
sem arquivos PES. O contrato preserva os comandos e requisitos do seletor
nativo; a seleção completa e a importação das animações continuam pendentes.

A [conferência dos recursos originais recebidos](docs/PES3-RECURSOS.md)
valida os 1.105 clips e recupera a inicialização de referência dos 19 ossos.
A ponte de desenho reescrita reproduz as matrizes e posições dos 22 jogadores
salvos a partir das poses já compostas. São 624 comparações C++14 registradas;
a avaliação completa das poses, os contatos e a integração Windows seguem pendentes.

A [análise dos dez novos saves de treino](docs/PES3-TREINO-ESTADOS.md)
confere 35 chamadas recompiladas e reescreve a regra temporal dos marcadores
e o ponto de referência variável do clip 741. São 4.526 comparações desses
dois módulos próprios, com índice automático dos marcadores observados.
A adaptação das poses e a integração ao treino Windows continuam pendentes.

## Executar no Linux

Em Debian/Ubuntu, instale as dependências normais do sistema:

```bash
sudo apt-get update
sudo apt-get install build-essential cmake python3 libgl-dev libsdl2-dev \
  libsdl2-image-dev libsdl2-ttf-dev libsdl2-gfx-dev libopenal-dev \
  libboost-system-dev libboost-thread-dev libboost-filesystem-dev libsqlite3-dev
./scripts/build.sh
./scripts/run-training.sh
```

É necessário um ambiente gráfico com OpenGL. No ambiente de nuvem Debian 13,
`./scripts/setup-cloud.sh` prepara as dependências sem acesso de administrador.
Essa instalação local mantém a verificação de assinaturas e hashes do APT.

O script de execução prepara os recursos no diretório `build` e inicia o
treino diretamente. A configuração editável fica em `build/training.config`;
recompilar não sobrescreve essa configuração nem os bancos locais.

## Executar no Windows 11

O pacote portátil x64 está em
`artifacts/football-training-windows-x86_64.zip`. Extraia-o para uma pasta,
conecte o controle Xbox Series S por USB ou Bluetooth e execute
`run-training.bat`. `run-controller-test.bat` executa verificações automáticas
com um controle virtual e da matemática de câmera/contatos; o controle físico
é verificado durante o treino. Desconecte controles físicos antes de executar
o teste virtual, para que eles não ocupem seus slots. O pacote já leva o
executável, as DLLs SDL2/OpenAL/Boost/SQLite e os recursos do jogo; não é
necessário instalar essas bibliotecas separadamente. Consulte
[`docs/WINDOWS.md`](docs/WINDOWS.md) para o mapeamento e para recompilar.

## Controle Xbox Series S

Conecte por USB para o primeiro teste. No Windows, controles Xbox usam
XInput, com GameController da SDL2 como alternativa, zona morta radial no
analógico e limiar nos gatilhos.
É possível conectar e desconectar durante o treino; na ausência de controle,
o teclado assume o jogador. Os testes virtuais não substituem a avaliação do
controle físico, do Bluetooth ou da sensação dos comandos no seu PC.

| Ação | Xbox | Teclado |
| --- | --- | --- |
| Mover / conduzir | Analógico esquerdo | WASD |
| Virar sem bola / olhar com bola | Analógico direito | Setas |
| Correr | RB + analógico | Shift + WASD |
| Domínio próximo / frear | RT | Espaço |
| Passe curto | A | J |
| Passe em profundidade | Y | I |
| Passe alto / carrinho sem bola | B | L |
| Chute | X | K |
| Cobertura | LB + X | Q + K |
| Cancelar chute ou passe alto | A durante a preparação | J durante a preparação |
| Modificador especial original | LT | Ctrl esquerdo |
| Super cancel / toque à frente | RB + RT | Shift + Espaço |
| Recomeçar exercício | View | R |
| Trazer bola à posição atual | — | F2 |
| Pausar / retomar | Menu | P |
| Alternar primeira pessoa / externa / próxima | Clique do analógico direito | Tab |
| Livre / condução / finalização / bola aérea | D-pad cima / direita / baixo / esquerda | 1 / 2 / 3 / 4 |
| Cobrança de falta parada | LB + D-pad baixo | 5 ou F3 |
| Receber passe rasteiro / jogar de primeira | LB + D-pad direita | 6 |
| Sair | — | Esc ou F12 |

Segure e solte A/B/X/Y para graduar a força. X também aumenta a elevação
com a carga; LB+X produz uma cobertura mais lenta e arqueada. A carga máxima
do chute é de 0,52 segundo; cerca de 0,25 segundo já levanta a bola, e um
toque rápido mantém a trajetória baixa. Os passes mantêm a carga de um segundo. Sem
outro jogador, os passes seguem a direção e força informadas. Não há troca
de jogador, impedimentos ou interrupções do árbitro no treino. Após gol ou
bola muito além do campo, o exercício é reposto automaticamente.

O analógico esquerdo corrige pequenos desvios perto das direções retas,
preservando diagonais e velocidade proporcional. A condução mantém a assistência
de movimento, a sequência de passos e o alcance das animações originais para
acompanhar a bola nas curvas, inversões e retomadas. Quando a bola sai do
domínio após um passe ou chute, o movimento volta a ser livre.
O jogador destro conserva ligeiramente mais impulso em contatos com o pé
esquerdo, sem reduzir o alcance dos toques. O contato recebe um ajuste suave
da perna no instante do toque, com limite de alcance e sem esticar os ossos.
Reiniciar o exercício também limpa os comandos de chute e passe pendentes.
RB + RT adianta a bola no instante de um toque original e mantém a assistência
para alcançá-la, inclusive ao virar e ao soltar RT. Passes e chutes liberam
essa recuperação. A bola conserva sua trajetória física entre os contatos.

No exercício de bola aérea, a trajetória permite cabecear antes do primeiro
quique. Prepare A para passar ou X para finalizar antes da chegada da bola;
a animação é escolhida pela altura, posição e momento do contato. Cabeceios
parados e com salto também aproveitam os gestos originais de passe. O exercício
6 fornece um passe rasteiro para preparar A/Y/X e jogar de primeira, sem
dominar antes. Esses comandos podem ser preparados até dois segundos antes
do contato. Nem todo comando possui um gesto manual dedicado: o
próprio upstream deixa certos dribles especiais desativados.

O treino agrupa as fases da simulação em uma tarefa por passo, reduzindo
trocas entre threads, e o agendador dispensa esperas temporizadas quando já
há trabalho pronto. A física e as animações mantêm o passo original de 10 ms.
O `log.txt` registra periodicamente a relação entre tempo simulado e real;
`1.0` corresponde à velocidade normal.

O treino usa varredura contínua da esfera da bola contra cápsulas de pernas,
tronco e cabeça, com restituição e perda de energia tangencial. São volumes
aproximados ao corpo, não colisão por triângulo de cada peça de roupa. A
cobrança de falta é um exercício parado, sem barreira ou adversários. A
sensação dos comandos e enquadramento precisam ser avaliados no PC Windows.

## Verificação

```bash
./scripts/build.sh
./scripts/test.sh
```

Os testes de entrada usam dispositivos virtuais SDL reais e verificam
mapeamento, gatilhos, zona morta, perda de foco, limites de arrays e
reconexão. O teste funcional abre o jogo em Xvfb com renderização Mesa,
envia comandos X11 e observa o estado real da simulação. Instale `xvfb`,
`xauth`, `xdotool` e `ffmpeg` para executá-lo fora da nuvem. O relatório,
o log e a captura da execução ficam em `artifacts/`.

```bash
python3 scripts/verify_upstream.py --assets-only
```

Essa verificação compara os recursos originais com hashes registrados na
importação. Modelos, campo, texturas e animações são preservados. A única
alteração em `data/` é o shader de pós-processamento, para impedir que o estádio
distante seja tratado como céu em primeira pessoa. Seu hash e motivo estão em
`docs/training-asset-overrides.json` e também são verificados. O código
de física e de apresentação foi adaptado nesta etapa; executar sem
`--assets-only` também compara esses módulos e informa as mudanças esperadas
em `ball.cpp`, `humanoidbase.cpp` e `humanoid_utils.cpp`.

## Desenvolvimento

Use o checkout existente: cada tarefa na nuvem já é isolada; não é necessário
criar worktrees. `FOOTBALL_BUILD_JOBS` ajusta o paralelismo de compilação
(padrão: 4). `FOOTBALL_BUILD_DIR` seleciona outro diretório de build.

Os processos gráficos precisam ser reiniciados em novas tarefas. Execute os
scripts a partir deste repositório. Para inspecionar a simulação:

```bash
./scripts/run-training.sh --telemetry
```

Na nuvem, sem monitor físico, `./scripts/start-headless.sh` inicia Xvfb e
o treino com Mesa. Aguarde linhas `TRAINING_FRAME` que mostrem o tempo
avançando para confirmar a simulação. O script limpa somente os processos
que iniciou ao encerrar. Não há suporte a controle físico ou prévia web
nessa execução; para jogar, execute a versão nativa no seu computador.

Para abrir os menus e as partidas da base original, execute a partir de `build`:

```bash
./gameplayfootball --config football.config --match
```

A validação desta etapa se concentra no treinamento. Modos antigos de
liga/partida precisam de validação própria. O executável Windows foi
cross-compilado como PE32+ x64 e empacotado com suas dependências; a primeira
execução com renderização e controle físico deve ser conferida no seu
Windows 11.

## Licenças

Preservados `LICENSE`, avisos nos arquivos, `NOTICE` e a licença OFL das
fontes. [UPSTREAM.md](docs/UPSTREAM.md) contém as instruções do fork antes
das alterações. O executável de treinamento usa os recursos dessa base.
O laboratório separado usa os dados numéricos PES 3 enviados pelo usuário;
a origem e os limites de validação estão em [docs/PES3.md](docs/PES3.md).
