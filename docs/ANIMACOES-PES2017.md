# Animações do PES 2017 recebidas

O `dt13_win.cpk` enviado contém o acervo corporal necessário para começar:
10 arquivos MTAR, `body_anim_skel.ask` e `body_skel.frig`. Foram extraídos e
lidos **2.956 clipes**, com **2.365 nomes** identificados pelo hash Fox e pelo
mesmo ID presente no mapa de nomes do PES 2021. Os outros 591 conservam hash
e ID, sem inventar nomes. O catálogo é apenas metadados:
[pes2017-motion-catalog.json](pes2017-motion-catalog.json).

O CPK tem 24.039.984 bytes e SHA256
`25d2dad1dd2d41b42c98e075daf3fa6fde1c159c63af9f7f40014b383e3d9342`.
Dois leitores conferiram o índice; o leitor próprio validou os intervalos de
295 entradas antes de exportar qualquer recurso. Os 28 recursos de metadados
selecionados concordam byte a byte entre os leitores. Os dados originais e as
poses decodificadas ficam fora do repositório e do ZIP público.

## Diferenças encontradas no formato

As pernas usam unidades FRIG de tipo 3 com 80 bytes. Elas contêm canais de
alvo IK, seguidos dos canais FK da coxa e da canela. O leitor genérico associava
a primeira rotação ao primeiro osso, colocando a rotação de alvo na coxa.
A extensão em `read_pes_gani.py` respeita os índices explícitos e preserva os
alvos separadamente. Dois clipes de preparação de saída de bola usam esses
alvos: `kickoff_loop_kicker` e `kickoff_loop_waist`. A adaptação direta desses
dois clipes é bloqueada até haver uma reconstrução dos alvos.

Também foi corrigida uma leitura de tempo: a translação do clipe
`gkblockcover_crash_f03_3_0_y02` contém intervalos de 194 e 191 quadros.
Ler os bytes como inteiros com sinal descartava as últimas chaves. Com a
leitura sem sinal, ambas terminam corretamente no quadro 258. A correção é
coberta por um arquivo sintético independente.

Os nomes e IDs compartilhados não justificam copiar durações e marcadores de
2021: somente 1.697 dos 2.365 clipes nomeados têm a mesma contagem de quadros
naquele mapa. A escala angular `pi/2` e a cadência de 30 FPS continuam sendo
as hipóteses do leitor upstream, ainda sem comparação com o PES executando.
Valores finitos e uma pose plausível não comprovam equivalência à engine.

## Primeira adaptação no modelo do Football

O movimento `run_2_0` foi adaptado de 20 para 13 ossos, com base na anatomia,
nos vetores dos segmentos e no bind real do modelo. A conversão de eixos é
uma rotação própria `(X,Y,Z) -> (X,-Z,Y)`: não troca os lados do corpo.
A raiz horizontal fica fora do clipe nativo para evitar deslocamento duplo.
O protótipo atual resolve apoio em pé; poses de queda exigem outro contato
com o chão e são recusadas pelo conversor.

A amostragem gerou 91 poses a 100 Hz. Nos quadros 0, 45 e 90, o executável
renderizou a malha original, preservando os ossos e as distâncias rígidas,
sem valores inválidos e com as chuteiras acima do gramado. São três poses
verificadas, não uma validação de todas as transições ou de todo o acervo.

![Primeira pose adaptada no modelo nativo](images/pes2017-native-preview.png)

Essa primeira corrida é uma **prévia visual**, ativada explicitamente por configuração. Ela
não registra candidatos de gameplay, não decide recepções/chutes e não cria
contatos com a bola. Sem a opção de prévia, o treino usa a gameplay aprovada;
o teste de câmera e movimentos nativos passou novamente.

## Primeiro passe funcional — etapa anterior

A primeira versão acrescentou **um** movimento: `kick_short_0_0_inside_y0_000`
(hash `85b2713b`, ID 49074), um passe curto de chapa com o pé direito.
O atalho `treinar-animacoes-pes.bat` habilita o candidato; **Insert** compara
com o original. A condição de uso é jogador parado ou muito lento, bola baixa
e quase parada, direção frontal e força curta/média. O seletor conserva os
candidatos nativos quando o movimento não alcança a bola ou não se adequa à
situação. `treino-classico.bat` começa com o teste desligado.

A anotação de contato é nossa: quadro 26 a 100 Hz, retimado para 29 pelo
pipeline nativo. Não é um marcador recuperado do PES. O clipe usa a convenção
de altura relativa do Football; a prévia visual usa altura absoluta. O toque
passa pelo planejamento nativo e pela superfície real ponderada da chuteira,
sem ampliar a tolerância nem deslocar a perna instantaneamente até a bola.
A classificação genérica pela origem geométrica inicialmente escolhia a
chuteira apoiada; a anotação explícita corrige a seleção para o pé direito que
realiza a batida.

O ZIP daquela etapa contém somente essa adaptação e sua proveniência. Os arquivos originais
do jogo e a biblioteca decodificada completa continuam privados. A física,
força do passe e seleção de ações continuam sendo do Football. A hipótese de
30 FPS e a escala angular ainda precisam de comparação com o jogo original;
este teste não constitui recuperação da gameplay exata do PES.

![Passe adaptado no jogador nativo](images/pes2017-shortpass.png)

Os testes renderizados usam controle Xbox virtual em primeira e terceira
pessoa: contato único com o pé direito, comparação com o original, fallback
em corrida e passe lateral, bola fora de alcance e retomada do movimento.
As rotações do tronco/pernas permanecem finitas e contínuas na entrada e
saída. A simulação confirma contato na superfície; uma captura a 30 FPS pode
não mostrar o instante exato do impacto a 100 Hz. Resultados completos:
[pes2017-shortpass-validation.json](pes2017-shortpass-validation.json).
A compilação Windows foi conferida como pacote; sua execução gráfica não foi
realizada neste ambiente.

## Ampliação do banco

A etapa atual reúne 21 clipes de origem e conserva o passe aprovado. A
adaptação agora aplica também a rotação geral da animação, armazenada fora da
hierarquia dos ossos, e preserva o deslocamento de apoio das novas ações.
Há seleção por função, direção, velocidade e altura escalada para o jogador,
com candidatos nativos de reserva. A recepção de peito foi integrada à camada
superior existente, com previsão do instante de chegada e transição para a
ação seguinte. Detalhes e limites em
[BANCO-ANIMACOES-PES2017.md](BANCO-ANIMACOES-PES2017.md).

## Reproduzir com os arquivos locais

Depois da extração validada do CPK, decodificar um dos MTARs para uma pasta
nova, conservando o rig e os alvos:

```bash
python3 tools/animations/read_pes_gani.py body_anime_file7.mtar \
  --skeleton body_anim_skel.ask --rig body_skel.frig --output /tmp/pes17-decoded
```

Encontrar o JSON cujo campo `name` é `run_2_0`; os nomes de saída usam hash e
ordinal, para não sobrescrever arquivos. Converter apenas esse JSON:

```bash
blender -b --python tools/animations/retarget_fox_clip.py -- \
  /tmp/pes17-decoded/00131-72244c1c.json \
  /tmp/pes17-decoded/source-rig.json /tmp/run_2_0.anim
```

Em uma configuração de treino solo separada, acrescentar um caminho absoluto
para o clipe convertido e, opcionalmente, um quadro fixo:

```text
"training_pose_preview_file" "/tmp/run_2_0.anim"
"training_pose_preview_frame" "45"
```

Sem quadro fixo, a prévia toca uma vez e mantém a última pose; não se apresenta
esse movimento como um loop fechado. O teste gráfico usa:

```bash
python3 tests/training_pose_preview_smoke.py --build build \
  --clip /tmp/run_2_0.anim --output /tmp/pes17-review
```

O próximo trabalho é conferir movimentos prioritários contra a execução
original, verificar a cadência, anotar o contato correto e adaptar a preparação
e a saída de cada jogada ao seletor do Football. Os arquivos recebidos bastam
para continuar essa análise; a biblioteca completa ainda não está ligada à
partida. Resultados e limites estão em
[pes2017-animation-import-validation.json](pes2017-animation-import-validation.json).

Para reproduzir o candidato de passe, decodificar `body_anime_file6.mtar` e
usar o JSON de hash `85b2713b`, junto do seu `source-rig.json`:

```bash
blender -b --python tools/animations/retarget_fox_clip.py -- \
  /tmp/pes17-pass/00216-85b2713b.json /tmp/pes17-pass/source-rig.json \
  /tmp/short_pass.anim --short-pass --contact-frame 26 \
  --contact-point -0.01 -0.39 0.11

python3 tests/training_pes_shortpass_smoke.py --build build \
  --output /tmp/pes17-pass-external --camera 1
python3 tests/training_pes_shortpass_smoke.py --build build \
  --output /tmp/pes17-pass-firstperson --camera 2 --launch-via-cli
```

O teste lê o candidato em `data/media/training/pes17/short_pass.anim`, disponível
no diretório de dados do executável. Os arquivos originais de entrada não
fazem parte do repositório.
