# Seleção de animações com a memória do treino PES 3

O save state recebido permitiu avançar dos roteamentos isolados para caminhos
executáveis de seleção e atualização. Registramos os argumentos de transição
e recompilamos estaticamente os caminhos alcançados em C++, comparando seus
resultados com um interpretador das instruções originais. **A gameplay completa
e a integração das animações ao nosso treino continuam pendentes.**

## Abrir os resultados

Baixe [pes3-savestate-research.zip](../artifacts/pes3-savestate-research.zip),
extraia e abra `abrir-laboratorio.html` com Edge ou Chrome. Expanda “Seleção
reexecutada no treino”, escolha um cenário e percorra suas transições. Os
clips registrados são apresentados automaticamente; não é necessário
classificá-los visualmente para consultar essas associações.

“Memória capturada” significa que os bytes iniciais do cenário vieram do
save state sem alterações. **Os argumentos das chamadas são definidos pelo
teste**, inclusive os pedidos de ação. “Memória alterada para teste” identifica
modificações explícitas de comando, ação ou subestado. Nenhuma das duas opções
significa uma gravação de quadros consecutivos executados no PS2.

“Exportar reexecução” conserva o cenário, as alterações, os IDs e os endereços
das transições. A prévia desenha o clip individual com a hierarquia diagnóstica
já existente; ainda não mostra a mistura, o contato com a bola ou a pose final
do jogo. Quando não há chamada de transição, consulta o campo de clip ao
retornar. Esse campo também não comprova a execução visual de uma animação.

## Conferência do estado recebido

O arquivo `SLES-51912 (3D653E04).01.p2s` tem 15.758.906 bytes e SHA-256
`b24f8ae70f608efc6c78a3a5ff249ee86ccd8c3043ebc752fca5a573ad2a87cb`.
O identificador informa **PCSX2 v2.8.2**, formato `0x9A590000`. Os 16 membros
passaram nas verificações de tamanho e CRC. O estado usa ZIP com Zstandard,
método 93, para as regiões de memória.

| Conferência | Resultado |
| --- | --- |
| EE RAM | 33.554.432 bytes; SHA-256 `dff465421161cc88efe4c9ac853bff7c03026aaead7ce32471ae98d9481bafbd` |
| Scratchpad | 16.384 bytes; SHA-256 `fa68124dc045f593ac308e4d6227c93414db989691ceab91ca0f09dfa61f568c` |
| Código carregado | 386.812 palavras únicas comparadas com a análise dos binários; nenhuma divergência |
| Animações carregadas | IDs 0–998: 999 blocos iguais em bytes ao FPSANM14 recebido |
| Animações restantes | IDs 999–1104: 106 ponteiros nulos neste estado |
| Atleta controlado | ID 10; registro `0x014C3560`, ação 0, subestado 2, clip 304, instante 40 |
| Contexto / configuração / bola | Ponteiros recuperados das variáveis globais registradas no relatório |
| Metadados EE | PC `0x01126210`, GP `0x012ADEF0`, SP `0x01FFFCA0`; usados como metadados, sem retomar esse PC |

O layout dos registradores foi conferido no
[SaveState.cpp do PCSX2 v2.8.2](https://github.com/PCSX2/pcsx2/blob/v2.8.2/pcsx2/SaveState.cpp)
e no [R5900.h da mesma versão](https://github.com/PCSX2/pcsx2/blob/v2.8.2/pcsx2/R5900.h).
O leitor não deduz o layout interno de outra versão. O
[relatório](pes3-savestate-validation.json) conserva hashes, inventário,
atores, fontes, testes e escopos.

## Caminhos recuperados e comparação C++

As rotinas examinadas incluem seleção de entrada `0x01853D30`, pedidos
`0x0184F5C0`, atualização de ação `0x01880490`, ação 1 `0x01876B50` e a
rotina coletiva `0x01881220`. Esta última prepara dados, preserva campos da
bola, percorre os registros dos atletas ativos e chama as rotinas posteriores
na ordem original. Sua chamada isolada ainda não constitui o quadro completo
do PES.

| Medida | Resultado desta execução |
| --- | ---: |
| Cenários concluídos | 234 de 234 |
| Memória inicial sem alterações / alterada para teste | 91 / 143 |
| Chamadas originais / comparações nativas | 276 / 276 |
| Instruções originais interpretadas | 2.142.295 |
| Palavras de instrução recompiladas | 51.609 |
| Chamadas de transição registradas | 86, envolvendo 20 clips |
| Testes Python | 47 aprovados |
| Verificações do laboratório no navegador | 43 aprovadas; zero erros JS ou requisições |

Os cenários exercitam os 62 códigos de ação com subestado inicial zero,
os 13 subestados recuperados da ação 1, os 23 pedidos, máscaras de entrada
e chamadas com os registros dos 22 atletas. Não percorrem todos os ramos
dessas ações. Há também uma sequência de três chamadas coletivas: ela avança
o relógio do atleta controlado de 40 para 41, depois 0 e 1. É uma sequência
do modelo com memória contínua, sem representar três quadros observados no
emulador. O gate `0x017BB0A0` foi alcançado cinco vezes nestes testes.

Em cada retorno comparam-se **todos os bytes da EE RAM e do scratchpad**, os
32 registradores gerais baixos, os 32 registradores FPU, a quantidade e a
sequência de instruções. Todas as comparações passaram. A referência executa
os helpers originais normalmente; não substitui retornos por resultados
nativos ou por sucesso fixo.

A aritmética de ponto flutuante usa o modelo selecionado do pacote v0.14,
com arredondamento host binary32 e operações VU delimitadas. Essa comparação
valida a tradução em relação ao interpretador/modelo utilizado, **não a
equivalência de todo o FPU/VU, flags, temporização ou hardware do PS2**.
Os registradores iniciais são normalizados para chamadas explícitas; não são
uma retomada dos registradores salvos durante a renderização.

## Referências dinâmicas agora observadas

O [índice de reexecução](pes3-replay-evidence.json) registra as transições,
sem exigir marcações. Três chamadas cujo argumento era desconhecido ou vinha
de um campo foram alcançadas:

| Chamada | Argumento na análise estática | Valor nos caminhos testados |
| --- | --- | --- |
| `0x01167374` | Desconhecido | Clip 119 |
| `0x0119F904` | `arg0+0x2DC:u16` | Clips atuais registrados, incluindo 47, 119, 263 e 304 |
| `0x0163FD18` | Desconhecido | Clip 869 |

Esses valores são observações concretas nos cenários identificados, não
substituições universais dos argumentos. As 84 chamadas pendentes da análise
estática permanecem registradas como tais; os 506 clips com referências
estáticas continuam sendo a mesma contagem. Uma execução local confirma um
caminho, não todos os contextos possíveis daquele ID.

## Ferramentas e reprodução

[`savestate.py`](../tools/pes3/savestate.py) lê o ZIP sem executar código do
emulador. Limita arquivos, tamanhos e descompressão, verifica cabeçalhos,
nomes, sobreposições e CRC; preserva a entrada. A extração opcional escreve
somente em uma pasta nova. Suporta métodos ZIP 0, 8 e 93.

[`replay.py`](../tools/pes3/replay.py) valida os bytes carregados, os clips,
monta os cenários, registra caminhos e confere os retornos nativos.
[`lift.py`](../tools/pes3/lift.py) traduz os endereços alcançados para operações
C++ explícitas. [`lift_runtime.hpp`](../tools/pes3/lift_runtime.hpp) oferece
registradores, acesso delimitado à memória, delay slots e aritmética.
Instruções alteradas, caminhos ausentes e operações fora do domínio falham;
não viram uma aproximação silenciosa.

Essa implementação é **recompilação estática parcial**, com a representação
de registradores e memória do PS2. Não é recuperação dos nomes ou do código
C++ original, nem uma interface semântica pronta para o esqueleto do nosso
motor. O ZIP inclui `native/lifted_program.cpp`, a API e o suporte para
inspeção e compilação. A API recebe cópias de 32 MiB de EE RAM e 16 KiB de
scratchpad; seus endereços são endereços da memória representada.

Com Python 3, `zstandard`, g++, Node e o pacote v0.14 extraído em `PES_CORE`,
defina `PES_STATE`, `PES_ELF` e `PES_OVER` para os arquivos recebidos:

```bash
python3 tools/pes3/savestate.py "$PES_STATE" --output /tmp/pes3-state-novo.json
python3 tools/pes3/replay.py --state "$PES_STATE" --elf "$PES_ELF" --over "$PES_OVER" --analysis /tmp/pes3-actions-final/actions.json --core "$PES_CORE" --reference "$PES_CORE/reference" --output /tmp/pes3-replay-novo
python3 tools/pes3/build_lab.py --core "$PES_CORE" --actions /tmp/pes3-actions-final --validation /tmp/pes3-actions-final-validation.json --replay /tmp/pes3-replay-novo --output /tmp/pes3-state-lab-novo.zip
python3 -m unittest discover -s tests -p 'test_pes3*.py' -v
python3 tests/pes3_lab_smoke.py /tmp/pes3-state-lab-novo.zip --output /tmp/pes3-state-browser-novo.json
```

Os arquivos de análise/validação anteriores podem ser regenerados conforme
[PES3-ACTIONS.md](PES3-ACTIONS.md). Escolha saídas novas. g++ compila com
`-fno-fast-math -ffp-contract=off`. Playwright/Chromium são usados somente no
teste; o HTML offline não requer essas dependências no Windows.

O teste carrega os mesmos bytes HTML com `set_content` no Chromium da nuvem;
a política local bloqueia `file://`. A abertura por arquivo no Windows/Edge
continua sendo uma conferência distinta.

Pacote: 12.672.608 bytes, SHA-256
`dd0debf03657efd0b23eab86442c1a803742679f0ad4ae48a7bb2cc3f9f43fc1`.
`replay-validation.json.gz` contém o relatório completo. Seu JSON descompactado
tem SHA-256 `2e31a188a8f84df6dd2fd7a1baa7c17dfd382415078d9c5a1f493b0715841907`.

## O que falta para o centro de treinamento

Ainda é necessário recuperar caminhos não exercitados, conferir o quadro
completo e a aritmética contra sequências do emulador, resolver a pose final,
caches, mistura e espelhamento. A divergência anterior de poses finais
permanece aberta. Em seguida, unidades/eixos e os 19 ossos precisam ser
adaptados ao jogador do treino e os contatos com a bola validados antes da
habilitação no seletor nativo. A física completa também exige essa validação.

O pacote de treinamento Windows mantém SHA-256
`ee913811b5fd1c5a18a3943a2228bb7b59436712b154b23826b7f8505d4b3443`.
Esta entrega publica a recuperação, os caminhos C++ e sua conferência; ainda
não acrescenta os clips PES ao executável jogável.
