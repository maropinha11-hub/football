# Seleção de locomoção PES 3 e ligação com o Football

A continuação [PES3-LOCOMOTION.md](PES3-LOCOMOTION.md) acrescenta direção,
predição, ramos especiais e sua execução em sequência. Também corrige a
fronteira da API comum para rejeitar o clip 35, que possui um ramo próprio.
O pacote abaixo preserva a entrega anterior; a revisão atual está no pacote
de locomoção e nos relatórios da continuação.

Esta etapa reescreve a decisão comum de locomoção da ação 1/subestado 16 e
o ajuste de velocidade seguinte. O código recebe estruturas numéricas
próprias, sem ponteiros de jogadores ou RAM do PS2. **A gameplay completa e
a importação no treino ainda estão em desenvolvimento.**

O [pacote de código e evidência](../artifacts/pes3-selection-research.zip)
permite recompilar e repetir as comparações registradas sem arquivos PES.
Contém 19 arquivos, ocupa 129.792 bytes e tem SHA-256
`2cc1b0ce2234cdd89356e8114b0d23e5fb1479ff56968095c2f1f7ee457627c9`.
É uma entrega de pesquisa, sem novo executável Windows.

## Decisões recuperadas

[`locomotion_selection.hpp`](../tools/pes3/recovered/locomotion_selection.hpp)
preserva `0x018790E8..0x0187927C` e o ajuste do tempo do clip 47 que o precede.
Os nomes dos campos descrevem valores e posições recuperadas; não atribuem
um significado esportivo aos atributos.

| Caminho | Condição | Decisão |
| --- | --- | --- |
| Ramo da bola | Bit 0 de `state_flags`, jogador corresponde ao contexto e amplitude da bola menor que `5888 − 12 × attribute_124` | Clip 61, início 0, atualização de mistura 4 |
| Perseguição | Fora do ramo da bola; direcional zero ou gate ativo; candidato limitado à amplitude inicial abaixo do limiar de 70% com aritmética original | Clip 61, início 0, atualização de mistura 4 |
| Ramo comum | Fase zero e amplitude atual abaixo de 1.024, ou separação quantizada de direções maior ou igual a 80 | Clip 47, início 5, atualização de mistura 4 e subestado 55 |
| Virada no ramo comum | Separação quantizada maior ou igual a 80 | Zera a amplitude antes do ajuste de velocidade |
| Reinício do clip 47 | Predicado original de reinício ativo | Escreve o parâmetro de tempo 24 antes da decisão comum |

O ramo da bola é exclusivo e os limiares são estritos. O cálculo de 70%
multiplica por sete com retorno de 32 bits e depois divide por dez; uma
porcentagem em ponto flutuante muda casos de limite. As direções usam o menor
arco de um domínio circular de 16 bits, dividido por 256. Início 0/5, tempo
24 e janela 4 conservam os parâmetros originais; a conversão para quadros
ou milissegundos do Football permanece pendente.

Clips com caminhos próprios são recusados pela API, preservando a saída:
28, 48, 49, 51, 52, 54, 56, 61, 62, 63, 213, 214, 215, 216 e 864. Isso inclui
o caso de **já estar** no clip 61, embora o ramo comum possa pedir uma
transição **para** ele. Esses caminhos precisam de sua própria reescrita.
Máscaras fora de 0..15 e gates fora do domínio booleano são inválidos.

Predição, gate de perseguição e reinício ainda fornecem entradas explícitas
à decisão. Durante a conferência, seus helpers originais executaram
normalmente; os resultados não foram injetados no interpretador. Essa API
não reescreve os helpers nem identifica botões físicos a partir dos IDs PES.

## Ajuste de velocidade

[`locomotion_speed.hpp`](../tools/pes3/recovered/locomotion_speed.hpp) reescreve
`0x0187927C..0x0187930C`, incluindo a escala de atributo de `0x011610D0`, o
ajuste de `0x018A3A60` e o predicado de modo usado na frenagem. Extrai os bits
2..8 de `roster_ae`, calcula o divisor com `attribute_124` e aplica os
modificadores de perfil e frenagem. Os modos 4 e 16 são exceções ao modificador
de frenagem. As somas preservam o retorno de 32 bits antes da comparação.

Um alvo zero **pula** a atualização e conserva a amplitude atual; não é um
comando genérico de parar. São amplitudes internas por chamada, sem conversão
validada para metros por segundo. Modo e perfil são campos explícitos, sem
acesso a globais originais. A integração de posição e os ajustes de direção
após `0x0187930C` continuam fora desta API.

## Verificação

| Verificação | Casos | Resultado |
| --- | ---: | --- |
| Decisão contra instruções originais | 92 | Zero divergências nos 32 bytes de saída |
| Decisão seguida do ajuste de velocidade | 92 | Zero divergências na amplitude final |
| Ajuste de velocidade independente | 1.153 | Zero divergências no inteiro final |
| Suíte Python PES | 90 testes | Todos passaram, nenhum ignorado |
| ZIP extraído e recompilado | 92 + 92 + 1.153 comparações | Todos passaram; hashes conferidos |

Nos 92 cenários, 43 pediram o clip 47, 9 pediram o 61 e 40 conservaram o
clip. O clip 61 foi pedido em cinco casos do ramo da bola e quatro do ramo
de perseguição. Cinco cenários ativaram o gate de perseguição com direcional
diferente de zero; um alcançou o reinício do clip 47. A execução em sequência
registrou 31.577 instruções e 704 endereços distintos; a do ajuste independente,
102.786 instruções e 170 endereços.

Os relatórios estão em [seleção](pes3-selection-validation.json),
[velocidade](pes3-speed-validation.json) e
[evidência da entrega](pes3-locomotion-delivery.json). Os hashes dos binários,
save, interpretador e modelo numérico foram conferidos. Cada palavra
executada foi comparada com a imagem original, sem substituir chamadas por
respostas de teste.

O usuário confirmou que o save é de **jogador parado com bola**. Os cenários
modificam cópias dessa memória e entram nos trechos indicados com registradores
preparados. Não são novas jogadas capturadas nem retomam um quadro completo
no PCSX2. A comparação comprova as APIs nos cenários e modelo declarados;
não comprova toda a gameplay ou a aritmética do PS2.

## Mapa automático e contrato do Football

[`selection_bridge.py`](../tools/pes3/selection_bridge.py) cruza resultados,
regras e o índice de 1.105 clips. O [mapa gerado](pes3-selection-bridge.json)
associa os casos às condições que pediram cada clip. As três regras verificadas
abrangem **dois clips neste trecho**; os demais conservam seus contextos
estáticos, sem receber validação dinâmica. Nomes de gestos não são deduzidos
apenas dos IDs.

O mapa lê os 293 arquivos `.anim` do Football, com hashes, propriedades e
contatos escritos, e extrai os tipos nativos do código. Lista candidatos por
tipo e algumas propriedades de estado. `LongPass` consulta `shortpass`;
o enum `Header` não possui seleção direta por string. O treino atual pode
acrescentar contatos de cabeça da coleção de passes a certos chutes/passes altos.

Esse é o catálogo escrito no disco. Movimentos gerados, espelhamentos,
velocidade, direção, pé, ranking, alcance e contatos adicionais ainda exigem
avaliação de `AnimCollection`/`Humanoid` em execução. **O mapa não escolhe
a animação final do jogador nativo.**

Pedidos, ações e clips PES são domínios diferentes de `e_FunctionType`.
O contrato exige um comando nativo independente, conserva associações não
comprovadas vazias e registra a conversão pendente de unidades/tempo, os
19 ossos PES para os 13 nós nativos, apoios e contatos. Alcance e instante
de contato de `GetBestCheatableAnimID`/`FootballAnimationExtension` continuam
sendo requisitos da integração.

O avanço seguinte é recuperar caminhos especiais e helpers de predição/direção,
e validar conversões antes de habilitar um clip importado. O save parado permite
avançar no código; estados em movimento ampliarão a conferência durante o
processo. O executável Windows aprovado continua com seu comportamento anterior.

## Repetir

Com Python 3 e g++, no pacote extraído:

```bash
python verify_locomotion_vectors.py . --output resultado-local.json
```

O comando recompila e compara saídas registradas, sem ISO, save, RAM, emulador
ou executáveis PES. Para uma nova execução original, use o repositório,
os arquivos recebidos e o pacote v0.14 extraído:

```bash
python3 tools/pes3/verify_speed.py --state "$PES_STATE" --elf "$PES_ELF" --over "$PES_OVER" --core "$PES_CORE" --output /tmp/pes3-speed-novo
python3 tools/pes3/verify_selection.py --state "$PES_STATE" --elf "$PES_ELF" --over "$PES_OVER" --core "$PES_CORE" --output /tmp/pes3-selection-novo
python3 tools/pes3/selection_bridge.py --selection /tmp/pes3-selection-novo --actions docs/pes3-animation-actions.json --output /tmp/pes3-bridge-novo.json
python3 tools/pes3/build_selection_package.py --selection /tmp/pes3-selection-novo --speed /tmp/pes3-speed-novo --bridge /tmp/pes3-bridge-novo.json --output /tmp/pes3-selection-novo.zip
python3 -m unittest discover -s tests -p 'test_pes3*.py' -v
```

Escolha saídas novas. As ferramentas recusam fontes, relatórios, headers e
fixtures alterados depois da conferência. O ZIP contém estruturas e vetores
numéricos dessa etapa, sem os binários, save ou imagens de memória.
