# Reescrita do esqueleto PES 3 e diferenças numéricas

Esta etapa entrega oito operações C++ com estruturas numéricas próprias:
composição, conversão entre representações, espelhamento e mistura de poses.
As **1.428 comparações passaram em bits contra as rotinas originais no modelo
declarado**. A investigação também localizou a origem compactada dos 6.688
componentes de rotação do save recebido e separou a pose composta de campos
locais desatualizados. **As animações PES ainda não estão integradas ao
treinamento Windows; a equivalência completa continua aberta.**

O [pacote reproduzível](../artifacts/pes3-rig-research.zip) contém código,
vetores numéricos e relatórios. Tem 750.114 bytes, 19 arquivos e SHA-256
`9264ecf9e7392380aad444e081ff325f30ca8877b6bad55b3a43e0dc63a52ea9`.
O [registro resumido](pes3-rig-validation.json) relaciona entradas, execuções,
hashes e limites de cada resultado. O laboratório visual anterior continua
disponível em [PES3-POSES.md](PES3-POSES.md).

## Operações recuperadas

[`pose_rig.hpp`](../tools/pes3/recovered/pose_rig.hpp) recebe 19 ossos, índices
de pais/pares de espelhamento, vetores, matrizes, caches e flags. Não recebe
ponteiros PS2 nem cópias da RAM. O wrapper trabalha numa cópia e só confirma
as saídas se toda a operação terminar com dados válidos.

| Operação | Rotina de origem | Comparações |
| --- | --- | ---: |
| `compose_matrices` | `0x01116060` | 44 |
| `ensure_composed` | `0x011157E0` | 88 |
| `ensure_local` | `0x01115940` | 88 |
| `mirror_raw` | `0x01115C60` | 44 |
| `apply_mirror` | `0x01115C20` | 88 |
| `mirror_gate` | `0x011156B0` | 352 |
| `materialize` | `0x01115EA0` | 220 |
| `mix` | `0x01115520` | 504 |

[`rig.py`](../tools/pes3/rig.py) executou primeiro as rotinas originais em
cópias do save, conferindo cada instrução alcançada contra ELF/overlay.
Depois comparou todas as palavras das três estruturas numéricas C++ de
cada caso, incluindo fontes alteradas, flags, caches e campos preservados.
Foram 2.378.096 instruções executadas e 940 palavras diferentes conferidas.
Os 550 casos com memória capturada e 878 com alterações explícitas são
identificados separadamente; todos usam argumentos e chamadas definidos
pelo teste, sem retomar o PC salvo do emulador.

A bateria cobre os 44 esqueletos, quatro ramos de conversão matriz→quaternion,
sete pesos de mistura e destinos independentes ou iguais a cada uma das
fontes. Os 21 casos de mistura de todas as translações exercitam descritores
de classe modificados; 483 casos misturam somente a raiz. A tabela de classes
é lida dos bytes originais, e seu helper continua executando. O fallback que
exigiria nova decodificação do clip é rejeitado pela API numérica.

A composição por matriz e a composição por quaternion conservam suas
operações diferentes. A conversão para local usa o conjugado do quaternion
do pai, sem dividir pela norma. Não normalizamos essa operação por conta
própria. Em `ensure_composed`, um ramo marca bits `2/4` sem escrever a matriz;
as flags isoladas não foram convertidas numa garantia genérica de matriz válida.

## Origem e arredondamento dos canais

[`channel_provenance.py`](../tools/pes3/channel_provenance.py) conferiu os
999 clips carregados contra o contêiner FPSANM14 recebido. Para cada buffer,
usou o clip apontado pela instância e percorreu suas chaves compactadas.
Não inferiu inteiros a partir dos floats salvos para provar a origem.

As 88 séries completas A/B, com 19 quaternions cada, têm correspondência
única com chaves reais de seus clips. Todos os **6.688 componentes** coincidem
com o produto do inteiro signed-16 pelo fator `0x38000100`, arredondado em
direção a zero. Com arredondamento ao mais próximo, 4.384 coincidem e 2.304
diferem. Isso comprova essas séries nesse estado; não comprova todos os
quadros, a atualização do relógio ou a aritmética PS2 completa.

O usuário informou que provavelmente manteve o padrão do PCSX2, sem certeza.
O [PCSX2 2.8.2](https://github.com/PCSX2/pcsx2/blob/v2.8.2/pcsx2/Pcsx2Config.cpp#L31)
define truncamento nas operações comuns EE/VU e arredondamento ao mais
próximo na divisão FPU. No
[recompilador x86](https://github.com/PCSX2/pcsx2/blob/v2.8.2/pcsx2/x86/iFPU.cpp#L1739),
`SQRT.S` também seleciona arredondamento ao mais próximo. Essas configurações
da versão são evidência externa; não são uma leitura das configurações efetivas
do computador que gerou o save. A implementação do emulador não foi copiada.

[`arithmetic.py`](../tools/pes3/arithmetic.py) mantém cinco perfis separados
em módulos privados. A referência pública anterior permanece intacta.
Operações finitas usam binary32 com arredondamento selecionado e tratamento
VU de subnormais; flags, temporização, acumuladores e unidades de divisão
PS2 completos continuam fora do modelo.
[`verify_arithmetic_profiles.py`](../tools/pes3/verify_arithmetic_profiles.py)
executou trinta verificações de instruções sintéticas para divisão, raiz,
multiplicação, conversão e independência
dos perfis. Elas são distintas das execuções originais do jogo.

## Comparar a mesma etapa da pose

Há duas sequências diferentes na investigação:

1. Avaliar → espelhar → converter para local → recompor por matriz.
2. Avaliar → materializar, deixando a rotina original escolher e conservar
   a representação composta após o espelhamento.

A primeira sequência força uma recomposição que pode modificar os pontos:
os quaternions quantizados não são perfeitamente unitários, e o conjugado
usado na conversão local não é uma inversa com divisão pela norma.
A segunda evita essa transformação adicional. Em 3 dos 44 buffers capturados,
o bit que marca o local está ausente; comparar esses campos como uma pose
local atual não valida o quadro desenhado. Os relatórios registram essas flags
e distinguem campos compostos recalculados daqueles que permaneceram intactos.

No perfil compatível com os modos padrão mencionados, mantendo o cache,
a diferença máxima dos pontos compostos passa de **0,3656158447265625** na
recomposição forçada para **0,0004119873046875** na materialização.
São unidades do modelo, sem conversão comprovada para metros.
**Nenhuma das 44 poses compostas inteiras ficou igual em bits.** Não foi
aplicada tolerância para transformar esse resultado em aprovação.

| Perfil FPU / VU / divisão / raiz | Componentes de pontos iguais, de 3.344 | Maior diferença de ponto |
| --- | ---: | ---: |
| Próximo / próximo / próximo / próximo | 1.085 | 0,0010223388671875 |
| Próximo / truncado / próximo / próximo | 1.617 | 0,000457763671875 |
| Truncado / próximo / truncado / truncado | 1.313 | 0,000579833984375 |
| Truncado / truncado / truncado / truncado | 1.432 | 0,000640869140625 |
| Truncado / truncado / próximo / próximo | 2.174 | 0,0004119873046875 |

Essa tabela usa `materialized_cached`. Cada perfil executou 572 chamadas
originais e 3.557.401 instruções, em 220 comparações de fase/buffer.
Os relatórios completos mantêm os resultados de todas as fases e perfis,
inclusive os piores. O perfil final não foi escolhido como equivalência por
ter mais componentes iguais.

## Repetir a verificação

Extraia o pacote. Com Python 3 e `g++` disponíveis, execute:

```bash
python3 verify_rig_vectors.py . --output resultado-local.json
```

[`verify_rig_vectors.py`](../tools/pes3/verify_rig_vectors.py) confere os hashes,
recompila o C++ e repete as 1.428 comparações contra os vetores registrados.
Esse processo foi executado com os arquivos extraídos do ZIP entregue.
Dispensa ISO, ELF, RAM e save; não substitui uma nova execução original.
Os 74 testes Python/C++ do repositório também passaram, sem pulos.

Para reexecutar as rotinas originais com os anexos e núcleo parcial recebidos,
use caminhos próprios e diretórios/arquivos de saída novos:

```bash
python3 tools/pes3/rig.py --state "$PES_STATE" --elf "$PES_ELF" --over "$PES_OVER" --core "$PES_CORE" --output /tmp/pes3-rig-novo
python3 tools/pes3/channel_provenance.py --state "$PES_STATE" --core "$PES_CORE" --output /tmp/pes3-canais-novo.json
python3 tools/pes3/verify_arithmetic_profiles.py --core "$PES_CORE" --output /tmp/pes3-perfis-novo.json
python3 tools/pes3/pose_differences.py --state "$PES_STATE" --elf "$PES_ELF" --over "$PES_OVER" --core "$PES_CORE" --fpu-rounding chop --vu-rounding chop --division-rounding nearest --sqrt-rounding nearest --output /tmp/pes3-diferencas-novo.json
```

## Integração no treinamento

A etapa numérica pode ser usada por uma engine sem executar endereços PS2.
A adaptação aos 13 nós esqueléticos nativos ainda exige confirmar lados,
eixos, pose de referência e escala, além do instante de contato com a bola.
O modelo compartilhado encontrado na RAM contém uma pose já avaliada;
tratá-lo como T-pose de referência produziria uma calibração sem comprovação.
O [plano de adaptação](pes3-retarget-plan.json) conserva essas pendências
e `runtime_enabled: false`.

Para validar seleção e contatos ao longo do movimento, a evidência seguinte
precisa incluir uma sequência de quadros PES do mesmo gesto, com estados
antes, no contato e depois. O usuário confirmou que o save completo disponível
mostra o jogador parado com a bola. Ele é nossa referência de repouso com a
bola; não registra a sequência de um chute. Estados adicionais permitiriam
verificar relógio, caches, apoio,
mistura e liberação da bola contra o movimento capturado. A referência do
esqueleto ainda precisa ser recuperada do recurso de modelo ou de sua
inicialização original; uma sequência em movimento não substitui essa referência.

O executável e os recursos do treinamento aprovado permanecem com os mesmos
bytes; seu ZIP Windows tem SHA-256
`ee913811b5fd1c5a18a3943a2228bb7b59436712b154b23826b7f8505d4b3443`.
Este pacote entrega pesquisa verificável, sem uma nova versão jogável.
