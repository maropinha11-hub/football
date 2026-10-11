# Animações PES3 no campo de treinamento

O executável agora tem um modo de estudo que reproduz os movimentos do banco
PES3 recebido, dentro do campo, em um esqueleto de estudo com **19 ossos** ao lado
do jogador. Esse esqueleto conserva a hierarquia original; não passa pela
redução para os 13 ossos da malha nativa.

A continuação [PES3-CORPO-NATIVO.md](PES3-CORPO-NATIVO.md) acrescenta um teste
de aplicação das rotações à malha do jogador, ativado com V. É uma adaptação
visual; ainda não seleciona automaticamente as animações das jogadas.

**A gameplay completa do PES ainda não substitui a gameplay nativa.** O jogador
controlável, as colisões, os passes, os chutes, as cabeçadas e a câmera continuam
usando o treino aprovado. O esqueleto de estudo não participa da física.

## Windows 11

1. Extraia a nova versão de `football-training-windows-x86_64.zip` em uma pasta nova.
2. Execute `importar-pes3.bat`. Na janela, selecione o arquivo
   `fpsoccer-pes-nucleo-v14.zip` que você já enviou. Também aceita seu
   `pes_animation_tracks.fpsa` extraído.
3. Execute `estudar-pes3.bat`. O controle Xbox continua funcionando no jogador
   normal; o esqueleto de estudo mostra as animações do PES.

Para jogar o treino normal, execute `run-training.bat`.
Não é preciso reinstalar o Windows nem instalar Python ou um compilador.
O pacote não contém o banco original: o importador confere seu SHA-256 e instala
somente os dados numéricos do arquivo local, sem executar código do ZIP.

| Tecla | Função no estudo |
| --- | --- |
| F7 | Mostrar/ocultar o esqueleto PES3 |
| V | Aplicar/remover a pose de estudo na malha do jogador parado |
| F8 / F9 | Clip seguinte/anterior, mantendo o estado de pausa |
| F10 | Pausar/continuar; reiniciar se chegou ao final |
| F11 | Pausar e avançar uma unidade de fase |
| C | Percorrer os IDs de clips observados nos dez saves |
| Tab / R3 | Alternar as câmeras existentes do treino |

Cada clip para no final. Não é presumido que todos sejam ciclos de corrida.
O ritmo inicial é **60 unidades de fase por segundo**, uma velocidade de
reprodução para estudo. A cadência original do PES ainda não foi confirmada.
Para mudar o ritmo, adicione, por exemplo,
`"pes3_preview_units_per_second" "50"` ao `training.config`.

## O que foi integrado

`src/pes3` contém o carregador do FPSANM14 e o decodificador/interpolador
semântico do núcleo v0.14 fornecido. As cinco fontes incorporadas desse núcleo
mantêm seus bytes, registrados em `pes3-native-animation-validation.json`.
As operações de hierarquia reutilizam `tools/pes3/recovered/pose_rig.hpp` e
`pose_ops.hpp`, previamente comparadas com as rotinas originais.

O caminho executado pelo jogo é:

`FPSANM14 → chave irregular → 19 poses locais → hierarquia original → matrizes/pontos → geometria de estudo`.

O carregador valida assinatura, diretório, duração, intervalos, sentinelas e
translações. A carga para execução exige os 1.105 clips, tamanho e CRC do banco
recebido. O importador confere também o SHA-256
`c40813d6b23f77834877ba4a5863ae54f8b829f6fc8f2c606d373c618d26bbe5`.
Dados inválidos não substituem um banco instalado.

O renderizador recebe snapshots com os 19 pontos. Não lê as poses mutáveis
da tarefa de simulação. A transformação de exibição `(-X,-Z,-Y)` e o ajuste de
altura para visualização ficam separados dos dados originais e da física.
Eles **não certificam os eixos, lados ou metros necessários ao retarget**.

## Verificação

- **90 comparações novas** do caminho completo de um clip inicializado,
  contra chamadas originais `0x01113CC0`, `0x01115130` e `0x01115EA0`.
- Comparação de **1.376 palavras por caso**, incluindo canais, pose local,
  flags, hierarquia, quaternions, pontos e matrizes. **941.379 instruções**
  originais executadas no modelo de referência; **923 palavras distintas**
  conferidas com o ELF/overlay recebido.
- **3.315 avaliações** cobrem início, meio e fim dos 1.105 clips, sem saída
  inválida. Esse conjunto verifica o domínio de execução; não é uma nova
  comparação integral com o console.
- **6.697 casos selados** de decodificação/interpolação e canais capturados do
  núcleo v0.14 passaram novamente, usando as fontes de produção.
- Testes do carregador, entradas inválidas, preservação de saída e relógio;
  teste renderizado por eventos SDL; regressão do treino existente.

As comparações novas usam canais explicitamente inicializados, sem mistura ou
espelhamento, e o modelo de arredondamento nearest. Não são frames retomados
no PCSX2 nem uma prova da aritmética exata do PS2. A divergência anteriormente
identificada entre reconstrução completa e poses salvas continua aberta.

## Reproduzir a verificação

Com o ambiente nativo preparado:

```sh
bash scripts/build.sh
bash scripts/test.sh
python3 tests/pes3_preview_smoke.py --build build --bundle /caminho/pes_animation_tracks.fpsa --output /tmp/pes3-preview-validacao
python3 tools/pes3/verify_runtime_pose.py --bundle /caminho/pes_animation_tracks.fpsa --state /caminho/treino.p2s --elf /caminho/SLES_519.12 --over /caminho/OVER.AFS --core /caminho/fpsoccer-pes-nucleo-v14 --output /tmp/pes3-poses-validacao
```

No Linux, `--pes3-preview` abre o estudo. O arquivo fica por padrão em
`pes3/pes_animation_tracks.fpsa`, relativo à pasta de execução, ou no caminho
definido por `pes3_animation_file` na configuração.

## O que falta para substituir a gameplay

A reprodução de um clip inicializado está integrada. Ainda faltam a ligação
validada com a malha, as poses misturadas/espelhadas no contexto real, a escolha
completa de ações/animações, o relógio original e os contatos sincronizados
com a bola. Os marcadores já recuperados continuam tratados como verificações
temporais, sem serem todos classificados como toques de pé ou cabeça.

Esta versão oferece uma reprodução testável no motor do jogo. Ela não deve
ser apresentada como a decompilação completa ou a gameplay idêntica ao PES.
