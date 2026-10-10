# Estudo do PES 3 para o centro de treinamento

Revisão de 10/10/2026. Base jogável aprovada pelo usuário:
`0cb7ead8dcf294755a0b0581f559cdeb241de0f3`.
Esta etapa acrescenta ferramentas de investigação e o contrato de integração;
nenhuma animação, regra física ou rotina do PES foi incorporada ao executável.

## Material recebido e alcance da conferência

Recebemos dois prints da ISO extraída e `analise-pes-sles51912.md`, com
172.981 bytes e SHA-256
`32f92a9d0bb9bea898f0e7a61677ff043f8e4d4969b228baf55365a5e9a6d7ea`.
O documento descreve outro projeto, um núcleo parcial v0.14; seus arquivos,
código-fonte, biblioteca, animações e estados PCSX2 não vieram no anexo.
Suas instruções de câmera, engine e cronograma pertencem àquele estudo;
o objetivo atual continua sendo nosso treinamento nativo em primeira pessoa.

| Informação | Origem | Situação nesta etapa |
| --- | --- | --- |
| `SLES_519.12`, `OVER.AFS`, `SYSTEM.CNF`, `CDLIST.DIR` | Prints | Nomes visíveis; bytes ainda não recebidos. |
| `DATA_F.AFS`, `DATA_G.AFS`, `DATA_S.AFS` | Prints | Presentes; não sabemos quais recursos cada arquivo desta cópia contém. |
| `SIZE_E.AFS` presente e `DATA_E.AFS` ausente da lista | Prints | Diferença a conferir com CNF, catálogo e executável; não prova corrupção. |
| 20 overlays, incluindo `game.ovl` | Relatório enviado | Relatado; aguardando `OVER.AFS` para reextrair e conferir hashes. |
| 1.105 blocos, 36.378 poses, 19 articulações | Relatório enviado | Relatado; aguardando o pacote v0.14 ou os recursos correspondentes. |
| 1.439.665 verificações do núcleo parcial | Relatório enviado | Não reexecutadas aqui; o próprio relatório limita o modelo de referência. |
| 0/132 poses finais inteiras idênticas | Relatório enviado | Divergência aberta; quantidade de testes de helpers não resolve a pose final. |
| 293 arquivos `.anim`, 195 contatos escritos, 14 canais por arquivo | Leitura deste checkout | Conferido pelo catálogo e pelos testes desta etapa. |

Os módulos IOP dos prints são componentes de execução do PS2, como áudio,
armazenamento, rede e controle. Seus nomes não localizam os clips dos atletas.
Os arquivos `.PSS` são candidatos a vídeo; não são a prioridade para animações.

## Arquivos necessários agora

O material mais útil é **`fpsoccer-pes-nucleo-v14.zip`**, citado no relatório.
Ele permitiria conferir a implementação, o formato do índice próprio, as
referências dos testes e `data/pes_animation_tracks.fpsa`. O relatório atribui
a esse último arquivo 6.310.088 bytes e SHA-256
`c40813d6b23f77834877ba4a5863ae54f8b829f6fc8f2c606d373c618d26bbe5`.
Não temos esse pacote nem deduzimos seu conteúdo a partir do texto.

Para conferir a cópia do disco, enviar em um ZIP pequeno:
**`SLES_519.12`, `OVER.AFS`, `SYSTEM.CNF` e `CDLIST.DIR`**.
Os dois arquivos maiores aparecem nos prints com aproximadamente 2,1 e
6,3 MiB. O leitor confere o ELF e o arquivo de módulos antes de usar qualquer
endereço do estudo. Um hash diferente exige nova correspondência; não é
prova isolada de que o disco esteja modificado ou inválido.

Se o pacote v0.14 não estiver disponível, os primeiros recursos de animação
a localizar são os seguintes. Os caminhos e IDs vêm do relatório de **DATA E**;
a correspondência com F/G/S ainda precisa ser verificada.

| Recurso relatado | Caminho relatado | Tamanho descompactado relatado |
| --- | --- | ---: |
| `0x00080000` / `anime.bin` | `020boot.afs/020boot_1.afs/020boot_1_pl.afs/020boot_1_pl_anime.afs` | 3.835.920 bytes |
| `0x00370000` / `anime2.bin` | `150pl.afs/150pl_anime.afs` | 1.302.320 bytes |
| `0x00370001` / `anime3.bin` | `150pl.afs/150pl_anime.afs` | 1.300.928 bytes |
| `0x00080001` / `game.mbc` | Mesmo contêiner de `anime.bin` | Payload relatado de 1.750 bytes; função desconhecida. |

Não precisamos receber a ISO inteira, a pasta IOP ou todos os AFS de centenas
de megabytes nesta primeira conferência.

## Ferramentas implementadas

[`inspect.py`](../tools/pes3/inspect.py) lê arquivos sem executar código PS2.
Inventaria AFS aninhados, índices e offsets absolutos, nomes quando há um
diretório compatível e cabeçalhos de módulos. Lê os segmentos ELF32 MIPS
little-endian e permite converter um endereço virtual apenas quando ele
pertence a um único segmento com bytes presentes no arquivo. Regiões apenas
reservadas em memória não viram instruções fictícias.

Com extração solicitada, seleciona somente os recursos de animação/ligação,
`game.mbc`, `game.ovl`, `training_free.ovl` e `training_common.ovl`. Preserva
os bytes armazenados e, para o wrapper `0x00010600` descrito no relatório,
confere os 32 bytes de cabeçalho, tamanhos, checksum zlib, fim do fluxo e
ausência de payload excedente. A saída descompactada tem limite configurável.
Os nomes de saída usam índices e nomes sanitizados; arquivos existentes não
são sobrescritos. Layouts sem nomes continuam inventariados por índice,
mas não permitem encontrar animações só pelo nome. Outros wrappers e a
decodificação dos ossos permanecem sem implementação.

Exemplos para quem tiver Python 3 no computador, dentro deste repositório:

```powershell
py -3 tools/pes3/inspect.py "C:\PES3_ESTUDO\01_ISO_EXTRAIDA\SLES_519.12" "C:\PES3_ESTUDO\01_ISO_EXTRAIDA\OVER.AFS" --output pes3-modulos.json --extract pes3-recursos
py -3 tools/pes3/inspect.py "C:\PES3_ESTUDO\01_ISO_EXTRAIDA\DATA_F.AFS" --output pes3-dados-f.json --extract pes3-recursos
```

No Linux, usar `python3` no lugar de `py -3`. Estes comandos são opcionais:
basta enviar os arquivos pequenos para fazermos a conferência na nuvem.
Para repetir uma extração, escolher uma pasta nova. Falhas retornam status
não zero e entram no relatório; extrações válidas de recursos anteriores
podem permanecer na pasta se uma entrada posterior falhar.

[`catalogue.py`](../tools/pes3/catalogue.py) cataloga a base aberta com hashes,
tipos de ação, propriedades, canais, chaves e eventos de bola escritos nos
arquivos. Valida quadros, números finitos, ordem das chaves e formato. O
endpoint de origem usa o passo **de 10 ms desta engine**, sem atribuir esse
tempo aos clips do PES.

```bash
python3 tools/pes3/catalogue.py --output /tmp/football-animation-catalogue.json
python3 -m unittest discover -s tests -p test_pes3_tools.py -v
```

São 20 testes com arquivos estruturais sintéticos e a base aberta real.
Cobrem AFS aninhados, limites/sobreposições, zlib inválido ou excessivo,
mapa ELF, extração sem alterar a entrada, nomes de saída e erros de catálogo.
Não são testes dos binários do PES, ainda não recebidos, nem da sua execução.

## Como o jogo já escolhe a animação

O ponto de integração é o C++ de
[`AnimCollection`](../src/onthepitch/player/humanoid/animcollection.cpp) e
[`Humanoid`](../src/onthepitch/player/humanoid/humanoid.cpp), preservando o
desempenho do treino. Python serve para preparar e conferir dados, não para
controlar o atleta a cada quadro.

`CrudeSelection` filtra ação, velocidade de entrada, direção do corpo,
direção da bola e estados especiais. `SelectAnim` mantém candidatos
compatíveis com o comando e ordena preferências. Nas ações com bola,
`GetBestCheatableAnimID` calcula o movimento e compara o gesto com a
trajetória prevista até achar um contato admissível. O treinamento já
reaproveita gestos de cabeceio de passe para finalizar pela altura da bola.

O catálogo de origem possui 283 arquivos carregados/espelhados e 10 templates;
o motor gera movimentos e contatos adicionais ao preparar a coleção. Por
isso 293 arquivos e 195 contatos escritos **não** são a contagem de clips
ou contatos disponíveis em runtime. O campo `touch_bodypart` é determinado
com a pose pelo motor, não inferido pelo nome do arquivo neste catálogo.

## Contrato do seletor ampliado

Cada clip importado deverá ter origem/hash, ID original, versão da conversão,
mapeamento de ossos, unidades/eixos comprovados, tempos das chaves, translação
da raiz, eventos de apoio/toque e limites de entrada/saída. Campos não
identificados ficam explícitos; não se inventa um evento a partir de um
registro auxiliar de oito bytes ou do nome `lnk`.

A seleção terá duas etapas:

1. **Admissibilidade física:** ação solicitada, fase/apoio da passada,
   posição e altura previstas da bola no contato, alcance da perna/cabeça,
   estados de posse e continuidade do toque em execução. Um candidato fora
   do alcance é rejeitado antes de qualquer pontuação.
2. **Preferência entre candidatos admissíveis:** continuidade da pose,
   diferença de velocidade/direção, tempo até o contato, custo da correção
   da raiz, pé de apoio e qualidade do pé dominante. Empates devem ser
   determinísticos; uma vantagem pequena não troca um clip a cada quadro.

A janela de contato compromete a ação até o toque ou um cancelamento
válido. Um cabeceio usa a cabeça; um passe de primeira não insere domínio;
um passe/chute libera a recuperação da condução; RB+RT mantém a recuperação
até um novo contato admissível. Essas condições já têm verificações no
treino e serão preservadas ao adicionar clips.

Não se substitui o teste físico por um ranking baseado apenas em distância.
Mistura visual e IK limitada refinam a pose; o impulso é publicado uma vez
no evento de contato, sem prender a bola ao jogador entre os toques.
Falha de importação ou falta de candidato conserva a coleção atual como
alternativa. Pesos e tolerâncias novas só serão definidos com clips
convertidos e trajetórias observadas, não pelo número de testes do relatório.

## Conversão e física: dependências concretas

O relatório descreve 19 articulações, mas os arquivos atuais têm 14 canais:
`player`, `body`, `middle`, `neck`, ombros/cotovelos e coxas/joelhos/tornozelos
de ambos os lados. O vetor de pais relatado não identifica sozinho os nomes
anatômicos, a pose de referência ou a orientação local de cada osso.
Antes de produzir um `.anim`, precisamos conferir essas bases e visualizar
pelo menos uma pose parada e uma sequência de passada/toque. Quaternions
compactados, tempos irregulares, mistura, espelhamento e translação da raiz
exigem tratamento separado; não basta renomear arquivos `.bin`.

Na física, o relatório distingue o atualizador real da previsão e registra
diferenças no arredondamento e no RNG. Também informa Y negativo para
elevação e divisores 256/213 cuja relação completa com o tempo não foi
estabelecida. Nosso motor usa Z positivo como altura, metros e passos de
10 ms. A escala visual de 256 unidades/m e os 60 Hz do outro treino são
escolhas daquele adaptador, não parâmetros do PES comprovados aqui.

Primeiro reproduzir os testes do núcleo recebido; depois medir unidades,
trajetórias, quique, atrito, spin e contato. Previsão deve concordar com o
atualizador no horizonte relevante conforme seu escopo, sem ser tratada
como se fosse a atualização real. Força/elevação dependem também do instante
e do gesto de contato; não se ajusta gravidade para compensar um clip errado.

Os endereços do relatório — seleção de entrada `0x01853D30`, dispatcher de
23 handlers `0x0184F5C0`, gate `0x017BB0A0` e composição/mistura de poses —
localizam investigação, não APIs do nosso executável Windows. A referência
de módulos e hashes precisa acompanhar cada endereço.

## Critério para liberar a primeira integração

Usar uma coleção opcional e começar com poucos clips identificados:
parado, início/parada de caminhada/corrida, curva, condução e toque simples.
Conferir na visualização externa e em primeira pessoa: apoios dos pés,
ausência de esticamento, continuidade da raiz/câmera e instante de contato.
O primeiro conjunto ampliado deve passar também pelos exercícios de
cabeceio, primeira, inversão, carga de chute e condução RB+RT da base atual.

Para comparar com PES, registrar sequências consecutivas com entradas
conhecidas, configuração, RNG e ordem de atualização. Três savestates
isolados e referências executadas em um modelo restrito não comprovam
transições do quadro inteiro. As divergências de poses do relatório devem
ser diagnosticadas antes de chamar a integração de reprodução fiel.

## Fontes consultadas

- Relatório do usuário v0.14, identificado por tamanho/hash acima. Os
  caminhos, hashes esperados, IDs e resultados PES neste documento são
  atribuídos a essa fonte; não houve acesso aos seus binários nesta etapa.
- Código do checkout aprovado de Gameplay Football, especialmente
  `animation.cpp`, `footballanimationextension.cpp`, `animcollection.cpp`
  e `humanoid.cpp`; catálogo regenerado com zero erros.
- [PCSX2: instruções R5900](https://github.com/PCSX2/pcsx2/blob/master/pcsx2/R5900OpcodeImpl.cpp),
  consultado em 10/10/2026: `MULT` e deslocamento aritmético `SRA` sustentam
  a necessidade de preservar bits/sinal no estudo. Snapshot de 41.783 bytes,
  SHA-256 `32f5ecad0f5bc4661ac37d1ca9b9ee5557954835c0d5474f4b53ff37a4b468cf`.
- [PCSX2: operações VU](https://github.com/PCSX2/pcsx2/blob/master/pcsx2/VUops.cpp),
  snapshot de 145.702 bytes, SHA-256
  `37d5098321e062956880637e90b6a975a8f28d88092a2f333f8f0d2e3750bd16`.
  Um cálculo binary32 do host não certifica todas as regras do PS2.
- [pyelftools: estruturas ELF](https://github.com/eliben/pyelftools/blob/main/elftools/elf/structs.py),
  snapshot de 25.460 bytes, SHA-256
  `1685f2e25692ea0c88f99df59d152318a27bbeebb93b0ceb54286f08651ba96a`.
  Conferida a organização dos cabeçalhos ELF32 e de seus segmentos; o leitor
  desta etapa foi escrito independentemente, sem dependências adicionais.
