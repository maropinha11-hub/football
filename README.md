# Centro de treinamento — Gameplay Football

Centro de treinamento nativo em C++/SDL2/OpenGL, derivado do
[Gameplay Football de vi3itor](https://github.com/vi3itor/GameplayFootball),
revisão `68159a2f0f96eec8ebba26ab7820130f36b922a7`.

Usa o jogador, o campo, o esqueleto, os 293 arquivos de animação e a física
da base original, com controles em primeira pessoa e ajustes de chutes e
colisões no treino. Carreira e partidas online ficam para etapas posteriores.

Em primeira pessoa, sem bola, o direito vira a visão e o esquerdo move e
desloca lateralmente em relação a ela. Com bola, o esquerdo conduz e o
direito olha ao redor sem alterar a direção do movimento. A cabeça retorna
ao centro após uma breve pausa; a câmera acompanha o corpo interpolado e
oculta a cabeça e o cabelo do jogador local para evitar obstrução.

Não é uma decompilação do PES. Os links fornecidos contêm Gameplay Football;
não contêm o motor nem as animações do PES. Fidelidade à base aberta e
equivalência ao PES são verificações diferentes. Consulte
[a pesquisa técnica](docs/RESEARCH.md) para a origem e os limites da implementação.

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

O exercício de bola aérea permite testar domínio, cabeceios e voleios que
o seletor de animações original escolhe conforme a altura, a posição e o
momento da ação. Nem todo comando possui um gesto manual dedicado: o
próprio upstream deixa certos dribles especiais desativados.

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
das alterações. Não foram utilizados arquivos extraídos de PES.
