# Poses PES3 na malha do jogador

Esta etapa liga as poses recuperadas à malha que já aparece no treino.
O esqueleto PES tem 19 nós; o personagem nativo tem 13 ossos animados.
O adaptador usa as rotações globais, conserva as mudanças dos nós intermediários
e calcula as rotações locais na hierarquia nativa. Assim, omitir um nó não
faz a rotação do pai ser aplicada duas vezes ao filho.

**É um teste de adaptação de poses. A seleção automática completa de ações,
as transições PES e os contatos com a bola ainda não estão integrados.**
As proporções, a pele, o deslocamento do jogador, a física e os comandos
continuam nativos. A altura visual da pelve é corrigida para apoiar os pés;
essa correção não desloca o jogador na simulação. Uma comparação matemática
do adaptador não prova gameplay idêntica.

## Testar no Windows

Se já tem o jogo e as animações instalados, use
`artifacts/football-windows-corrigir-orientacao.zip`: feche o jogo, copie
`gameplayfootball.exe` desse ZIP para a pasta que já usa e substitua o
executável antigo. Abra `estudar-pes3.bat`. Essa atualização usa os recursos
e a pasta `pes3` já instalados. A versão completa também está disponível.

1. Extraia a nova versão Windows em uma pasta nova.
2. Execute `importar-pes3.bat` e selecione seu `fpsoccer-pes-nucleo-v14.zip`.
3. Execute `estudar-pes3.bat` e, com o jogador parado, pressione **V**.
4. Use F8/F9 para trocar o clip, F10 para reproduzir/pausar, F11 para avançar
   uma unidade de fase ou C para percorrer os clips observados nos saves.
   Use R3 ou Tab para ver o corpo pelas outras câmeras. Na câmera externa,
   o estudo aproxima a visão para facilitar a inspeção dos membros.

V volta às animações nativas. Movimentar o analógico esquerdo, correr,
dominar, passar ou chutar também encerra automaticamente a aplicação da pose
de estudo. A restauração limpa o histórico visual da pose importada, para
não misturá-la com o passe, chute ou movimento seguinte. O gráfico de 19 nós
continua disponível ao lado do jogador até você fechá-lo com F7.

`run-training.bat` abre o treino normal. A aplicação de poses não é habilitada
por padrão e não altera a escolha das animações das jogadas.

## Correspondências e referência

O adaptador é código próprio de FPSoccer em `src/pes3/native_pose.hpp`.
Sua referência fonte é o clip 47 na fase zero, com os canais inicializados
como na etapa de reprodução. A referência nativa é a pose reta efetivamente
aplicada por `straight.anim.util`, após desfazer a pose de autoria da malha.
`base.anim.util` participa dessa preparação, mas contém membros dobrados e
não é a referência de calibração do adaptador corrigido.

O adaptador alinha cada braço, antebraço, coxa e canela à direção física entre
os respectivos nós PES. Também usa os extremos do tronco para os nós
intermediários que não existem no personagem nativo. As linhas dos quadris
e dos ombros orientam a torção do tronco. Isso corrige o problema anterior:
aplicar apenas diferenças de rotação entre duas poses diferentes mantinha
um erro de alinhamento em todos os clips.

Os limites dos pés são capturados da própria malha preparada. A pelve recebe
uma correção visual de altura para que os volumes dos pés permaneçam acima
do campo. A elevação da fonte é adaptada pela razão dos comprimentos das
pernas; isso é um ajuste de proporções visuais, não uma conversão comprovada
das unidades físicas do PES. O ajuste considera a altura efetiva no mundo, incluindo o deslocamento
vertical do nó nativo do jogador. A correção anterior é removida a cada
frame, para não acumular altura quando a reprodução está pausada. O giro
do corpo conserva a orientação atual do jogador no campo.

Durante V, o ajuste nativo de contato com a bola e a interpolação temporal
nativa deixam de alterar a pose importada. O corpo e o gráfico usam o mesmo
snapshot. Ao voltar aos comandos do treino, o histórico visual é limpo e
as animações e seus ajustes nativos são restaurados.

As mudanças de rotação global são transportadas pela rotação de exibição
`(X,Y,Z) → (-X,-Z,-Y)`. Não se transforma isso em metros nem em uma identificação
do pé preferido do PES. Os comprimentos e offsets dos ossos nativos continuam
os mesmos; não são os comprimentos e a malha originais do PES.

| Osso nativo | Nó PES usado |
| --- | ---: |
| body | 0 |
| middle | 8 |
| neck | 16 |
| left_shoulder / left_elbow | 11 / 13 |
| right_shoulder / right_elbow | 12 / 14 |
| left_thigh / left_knee / left_ankle | 2 / 4 / 6 |
| right_thigh / right_knee / right_ankle | 3 / 5 / 7 |

Na referência recebida, as dobras dos joelhos avançam para +Z da fonte;
a frente do personagem nativo é −Y. A conversão anterior `(X,Z,-Y)` invertia
essa relação, deixando joelhos e tronco dobrados para trás, embora os
comprimentos e a posição dos segmentos passassem nos testes matemáticos.

A conversão corrigida leva a frente +Z da fonte para −Y nativo e o alto −Y
da fonte para +Z nativo. É uma rotação própria, com determinante +1. Ela
também troca os lados visíveis de X, por isso as correspondências dos pares
foram corrigidas junto com a conversão. Os ramos 2 e 11 ocupam agora +X
nativo, o lado esquerdo ao olhar para −Y. Não se atribuem nomes recuperados
aos campos desconhecidos do executável nem se presumem habilidades.

O renderizador recebe as 19 rotações pelo snapshot de preparação/fetch.
Ele não acessa canais mutáveis da simulação. A adaptação valida os quaternions
e calcula toda a saída antes de aplicá-la. Entrada inválida conserva a saída
e o personagem usa sua animação nativa.

## Verificação

Os testes de geometria cobrem poses de referência diferentes, composição
de pais, extremos do tronco, giro, eixos opostos, elevação e rejeição atômica.
A verificação do banco usa o bind capturado pelo carregador real da malha e
faz **7.735 avaliações** dos 1.105 clips, incluindo fases intermediárias.
Confere **77.350 direções**, comprimentos, composição e apoio dos pés.

O teste renderizado reproduz os clips observados, examina os vértices reais
da pele, a conservação das distâncias dos vértices rígidos, o apoio dos pés,
a estabilidade da pausa e a restauração dos comandos nativos.
Também verifica o sentido das dobras dos joelhos, a inclinação do tronco e
a orientação da cabeça e das pontas dos pés na referência. A rotação de
pontos e a rotação de quaternions usam a mesma conversão de eixos.
Os resultados atuais estão em `pes3-native-orientation-validation.json`.
`pes3-native-retarget-validation.json` registra a versão anterior, cujos
testes de comprimentos e direções ainda não conferiam a frente anatômica.
`pes3-native-body-validation.json` é o registro histórico da primeira versão;
sua comparação de matrizes não detectava o desalinhamento físico relatado.

Essas verificações não provam contato com a bola, equivalência entre as duas
malhas nem reconstrução exata de um save PES. A seleção completa de ações,
as transições e os eventos ainda precisam ser integrados.

```sh
python3 tests/test_pes3_retarget.py -v
python3 tests/pes3_preview_smoke.py --build build --bundle /caminho/pes_animation_tracks.fpsa --output /tmp/pes3-corpo-render
python3 tools/pes3/verify_native_retarget.py --bundle /caminho/pes_animation_tracks.fpsa --engine-log /tmp/pes3-corpo-render/preview-smoke.log --output /tmp/pes3-corpo-validacao
```

Para completar a gameplay, o próximo trabalho é integrar os corpos das ações
PES, decidir o clip e suas condições reais, estabelecer o relógio, misturar e
espelhar poses, converter movimentos e sincronizar o contato da bola. O teste
de corpo dá um caminho verificável para essa integração; não substitui essas
rotinas nem classifica gestos por números de clips.
