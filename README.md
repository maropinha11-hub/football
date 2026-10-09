# Centro de treinamento — Gameplay Football

Centro de treinamento nativo em C++/SDL2/OpenGL, derivado do
[Gameplay Football de vi3itor](https://github.com/vi3itor/GameplayFootball),
revisão `68159a2f0f96eec8ebba26ab7820130f36b922a7`.

Usa o jogador, o campo, o esqueleto, os 293 arquivos de animação e a física
da base original. O objetivo desta etapa é avaliar movimento e ações com
um jogador controlado. Primeira pessoa, carreira e partidas online ficam
para etapas posteriores.

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
`run-training.bat`. Para conferir a enumeração e os eventos do controle antes
do exercício, execute `run-controller-test.bat`. O pacote já leva o
executável, as DLLs SDL2/OpenAL/Boost/SQLite e os recursos do jogo; não é
necessário instalar essas bibliotecas separadamente. Consulte
[`docs/WINDOWS.md`](docs/WINDOWS.md) para o mapeamento e para recompilar.

## Controle Xbox Series S

Conecte por USB para o primeiro teste. O jogo usa o mapeamento padronizado
GameController da SDL2, com zona morta no analógico e limiar nos gatilhos.
É possível conectar e desconectar durante o treino; na ausência de controle,
o teclado assume o jogador. Os testes virtuais não substituem a avaliação do
controle físico, do Bluetooth ou da sensação dos comandos no seu PC.

| Ação | Xbox | Teclado |
| --- | --- | --- |
| Mover / conduzir | Analógico esquerdo | WASD |
| Correr | RB + analógico | Shift + WASD |
| Domínio próximo / frear | RT | Espaço |
| Passe curto | A | J |
| Passe em profundidade | Y | I |
| Passe alto / carrinho sem bola | B | L |
| Chute | X | K |
| Cancelar chute ou passe alto | A durante a preparação | J durante a preparação |
| Modificador especial original | LT | Ctrl esquerdo |
| Super cancel / toque à frente | RB + RT | Shift + Espaço |
| Recomeçar exercício | View | R |
| Trazer bola à posição atual | — | F2 |
| Pausar / retomar | Menu | P |
| Câmera externa / próxima | Clique do analógico direito | Tab |
| Livre / condução / finalização / bola aérea | D-pad cima / direita / baixo / esquerda | 1 / 2 / 3 / 4 |
| Sair | — | Esc ou F12 |

Segure e solte A/B/X/Y para graduar a força, como na lógica original. Sem
outro jogador, os passes seguem a direção e força informadas. Não há troca
de jogador, impedimentos ou interrupções do árbitro no treino. Após gol ou
bola muito além do campo, o exercício é reposto automaticamente.

O exercício de bola aérea permite testar domínio, cabeceios e voleios que
o seletor de animações original escolhe conforme a altura, a posição e o
momento da ação. Nem todo comando possui um gesto manual dedicado: o
próprio upstream deixa certos dribles especiais desativados.

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
python3 scripts/verify_upstream.py
```

Essa verificação compara os recursos originais e os módulos centrais de
física/animação com hashes registrados na importação. Ela comprova que
esses arquivos foram preservados; não comprova equivalência ao PES.

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
