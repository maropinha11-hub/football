# Poses PES3 na malha do jogador

Esta etapa liga as rotações recuperadas à malha que já aparece no treino.
O esqueleto PES tem 19 nós; o personagem nativo tem 13 ossos animados.
O adaptador usa as rotações globais, conserva as mudanças dos nós intermediários
e calcula as rotações locais na hierarquia nativa. Assim, omitir um nó não
faz a rotação do pai ser aplicada duas vezes ao filho.

**É um teste de adaptação de poses. A seleção automática completa de ações,
as transições PES e os contatos com a bola ainda não estão integrados.**
O movimento da raiz, as proporções, a pele, a física e os comandos continuam
nativos. Uma comparação matemática do adaptador não prova gameplay idêntica.

## Testar no Windows

1. Extraia a nova versão Windows em uma pasta nova.
2. Execute `importar-pes3.bat` e selecione seu `fpsoccer-pes-nucleo-v14.zip`.
3. Execute `estudar-pes3.bat` e, com o jogador parado, pressione **V**.
4. Use F8/F9 para trocar o clip, F10 para reproduzir/pausar, F11 para avançar
   uma unidade de fase ou C para percorrer os clips observados nos saves.
   Use R3 ou Tab para ver o corpo pelas outras câmeras.

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
como na etapa de reprodução. A referência nativa é a pose efetivamente
aplicada por `base.anim.util` durante a preparação da malha de cada personagem.

As mudanças de rotação global são transportadas pela rotação de exibição
`(X,Y,Z) → (X,Z,-Y)`. Não se transforma isso em metros nem em uma identificação
do pé preferido do PES. Os comprimentos e offsets dos ossos nativos continuam
os mesmos; não são os comprimentos e a malha originais do PES.

| Osso nativo | Nó PES usado |
| --- | ---: |
| body | 0 |
| middle | 8 |
| neck | 16 |
| left_shoulder / left_elbow | 12 / 14 |
| right_shoulder / right_elbow | 11 / 13 |
| left_thigh / left_knee / left_ankle | 3 / 5 / 7 |
| right_thigh / right_knee / right_ankle | 2 / 4 / 6 |

Na referência recebida, os ramos 3 e 12 ocupam o lado +X, correspondente ao
lado esquerdo do personagem nativo que olha para −Y. Isso confere o lado da
adaptação visual, sem atribuir nomes anatômicos aos campos desconhecidos do
executável nem presumir o significado dos atributos de habilidade.

O renderizador recebe as 19 rotações pelo snapshot de preparação/fetch.
Ele não acessa canais mutáveis da simulação. A adaptação valida os quaternions
e calcula toda a saída antes de aplicá-la. Entrada inválida conserva a saída
e o personagem usa sua animação nativa.

## Verificação

Os seis testes novos cobrem identidade na referência, hierarquia, mudança
de eixos, movimento de pai/filho sem aplicação dupla, sinal/norma de quaternion
e rejeição atômica de entradas inválidas. A verificação do banco faz **3.315
avaliações**, início/meio/fim dos 1.105 clips, e compara **43.095 rotações**
com composição independente de matrizes. O erro absoluto máximo observado
foi inferior a `5e-7`.

Essas comparações verificam o adaptador matemático, não os contatos físicos,
a equivalência entre as duas malhas ou a reconstrução exata de um save PES.
O registro desta entrega fica em `pes3-native-body-validation.json`.

```sh
python3 tests/test_pes3_native_pose.py -v
python3 tools/pes3/verify_native_pose.py --bundle /caminho/pes_animation_tracks.fpsa --output /tmp/pes3-corpo-validacao
python3 tests/pes3_preview_smoke.py --build build --bundle /caminho/pes_animation_tracks.fpsa --output /tmp/pes3-corpo-render
```

Para completar a gameplay, o próximo trabalho é integrar os corpos das ações
PES, decidir o clip e suas condições reais, estabelecer o relógio, misturar e
espelhar poses, converter movimentos e sincronizar o contato da bola. O teste
de corpo dá um caminho verificável para essa integração; não substitui essas
rotinas nem classifica gestos por números de clips.
