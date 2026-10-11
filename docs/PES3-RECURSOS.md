# Recursos PES 3 recebidos: referência e desenho do esqueleto

O ZIP coletado em 11/10/2026 resolveu a ausência dos arquivos originais de
modelo e animação. Esta etapa reescreve a inicialização dos 19 ossos e a
passagem das poses compostas às matrizes de desenho. **A integração das
animações PES ao treino Windows ainda está pendente.** O código desta etapa
está em `tools/pes3/recovered`, sem alterações no runtime aprovado.

O [pacote de verificação](../artifacts/pes3-model-resources-research.zip) tem
274.305 bytes, 23 arquivos e SHA-256
`86db3535f8a56cd6b5b2638bd0c2ad8bfccbe89e9c926d328add60ce3b1bb89e`.
Contém C++14 próprio e vetores numéricos; não é uma atualização jogável.
O [registro resumido](pes3-resource-validation.json) registra execuções,
entradas, hashes e limites. Os diretórios originais dispensam classificação
manual para recuperar índices/blocos; interpretar as ações ainda depende
das rotinas que realmente escolhem e atualizam esses índices.

## Recursos conferidos

O ZIP recebido tem 7.403.106 bytes e SHA-256
`8258add78a08875fe5f2b40079d0d24a6156749d4f79a421a7c05fab993163c5`.
Contém seis recursos e um manifesto, com 18 registros provenientes de
DATA_F/G/S. Os bytes de cada recurso são iguais nas três versões recebidas;
as DATA completas não foram enviadas, portanto seus hashes declarados não
foram conferidos independentemente.

| Recurso | Resultado |
| --- | --- |
| `anime.bin`, `anime2.bin`, `anime3.bin` | 875 + 124 + 106 clips; 36.378 poses |
| `body_lnk.bin` | 13 contêineres zlib, 65 modelos; 26 com 19 ossos e 39 com 17 |
| `mon_lnk.bin` | 280 contêineres zlib com tamanhos/fim/checksum conferidos |
| `game.mbc` | Cabeçalho e payload bruto de 1.750 bytes preservados |

O importador aceita os caminhos com `\` gravados pelo .NET no Windows,
normalizando-os antes de conferir limites, duplicatas e caminhos.
Não extrai usando nomes não validados. Os testes incluem aliases,
travessia de diretórios, corrupção e inconsistência de tamanho/checksum.

`collected_assets.py` lê os diretórios sem consultar o catálogo anterior.
Os 1.105 blocos regeneram exatamente o FPSANM14 já conferido:
6.310.088 bytes, SHA-256
`c40813d6b23f77834877ba4a5863ae54f8b829f6fc8f2c606d373c618d26bbe5`.
Os 999 clips carregados no save coincidem integralmente, assim como seus
999 perfis de movimento e 999 registros auxiliares de oito bytes.
Os 106 restantes não estão carregados nesse save; isso é registrado como
ausência. Os registros auxiliares conservam seus bytes e não foram
renomeados como eventos de contato.

A duração no cabeçalho é um float: `0x0113A4C0` converte a saída de
`0x01114EE0` para inteiro. Todas as durações recebidas são floats inteiros
e coincidem com a tabela carregada.

## Inicialização própria e origem dos campos salvos

`model_bind.hpp` recupera o caminho alcançado de `0x0113A1C0`, incluindo
`0x01116190`, `0x01115B80` e `0x01113A10`. Recebe matrizes originais, índices
de pais/pares e um perfil aritmético explícito. Conserva a inversa rígida
por transposição e a ordem das operações; não normaliza quaternions por
hipótese e não usa uma pose animada como referência.

As 26 entradas com 19 ossos representam três conjuntos distintos de
matrizes. Todas passaram nos dois perfis: **52 comparações, 51.584 palavras,
441.084 instruções originais**. Cada instrução foi conferida contra o
ELF/overlay fixado, e todas as 992 palavras de cada saída foram comparadas.
O armazenamento de nós é explicitamente zerado antes da chamada. O port
não inclui a inicialização dos modelos de 17 ossos.

`bind_arithmetic.hpp` seleciona `nearest` ou `chop` sem modificar o modo
global de arredondamento. Divisão e raiz permanecem `nearest`. São modelos
de operações binary32 finitas, não uma implementação completa das flags,
acumuladores, temporização ou aritmética física do PS2.

No perfil `chop`, um único conjunto de matrizes reproduz os **3.168
componentes** das translações A não raiz dos 44 buffers salvos. A raiz é
animada e foi excluída. As correções de espelhamento salvas coincidem com
`nearest`, não com `chop`. Nenhum desses resultados torna a pose completa
equivalente em bits. As diferenças de composição descritas em
[PES3-RIG.md](PES3-RIG.md) continuam abertas.

## Pose composta → desenho

`render_pose.hpp` reescreve `0x01139E30`: copia as matrizes compostas ou
multiplica cada coluna pelo respectivo coeficiente de aparência, e força
o W final a 1. Não substitui coeficientes individuais por escala única.
Também reescreve `0x0113C870`: `(-0,2*x, +0,2*y, +0,2*z)` para a posição
desenhada, conservando os espaços originais sem afirmar unidade em metros.

São 264 comparações de matrizes e 22 de posição por perfil. Os destinos
0/17/19 e as fontes dos 44 buffers exercitam ambos os ramos.
Separadamente, seguimos os ponteiros que o renderer efetivamente selecionou
no save: 14 destinos com 19 matrizes e oito com 17. No perfil `chop`, todas
essas matrizes de desenho e as 22 posições coincidem com os campos salvos.
No perfil `nearest`, nenhuma saída completa de matrizes coincide, e só uma
posição completa coincide.

Esse resultado usa as matrizes já compostas do save como entrada. Não prova
que o caminho completo clip → pose avaliada → mistura → desenho foi
reconstruído, nem que o Football nativo já utiliza os clips PES.

## Repetir

No pacote extraído, com Python 3 e `g++`:

```sh
python3 verify_resource_vectors.py . --output resultado-local.json
```

Essa execução recompila C++14 e passou nos **624 casos, 212.228 palavras**
registrados. São regressões contra resultados de chamadas originais em
modelos declarados, não quadros novos retomados no PCSX2. Os arquivos,
relatórios e vetores têm hashes conferidos antes de serem usados.
Os 133 testes das ferramentas passaram, incluindo importação PowerShell,
limites/corrupção, perfis independentes, sanitizador C++ e repetição do ZIP.

Para repetir com os anexos e diretórios de saída novos:

```sh
python3 tools/pes3/collected_assets.py "$PES_RESOURCES" --output /tmp/pes3-assets-novo
python3 tools/pes3/verify_model_bind.py --archive "$PES_RESOURCES" --state "$PES_STATE" --elf "$PES_ELF" --over "$PES_OVER" --core "$PES_CORE" --profile nearest --output /tmp/pes3-bind-nearest-novo
python3 tools/pes3/verify_model_bind.py --archive "$PES_RESOURCES" --state "$PES_STATE" --elf "$PES_ELF" --over "$PES_OVER" --core "$PES_CORE" --profile chop --output /tmp/pes3-bind-chop-novo
python3 tools/pes3/verify_collected_provenance.py --archive "$PES_RESOURCES" --state "$PES_STATE" --bind /tmp/pes3-bind-nearest-novo --bind /tmp/pes3-bind-chop-novo --output /tmp/pes3-proveniencia-nova.json
python3 tools/pes3/verify_render_pose.py --state "$PES_STATE" --elf "$PES_ELF" --over "$PES_OVER" --core "$PES_CORE" --profile chop --output /tmp/pes3-render-novo
```

## Integração e validação seguintes

A referência original está recuperada. Ainda faltam adaptação dos eixos e
articulações nativas, unidades/tempo, caminhos de seleção pendentes,
transições e contatos/colisões completos. A escala de aparência foi
identificada no desenho; sua inicialização completa e conversão para o
motor nativo ainda precisam ser conferidas.

O único save disponível é o repouso com a bola. Para comparar movimento e
instante de contato, precisamos de sequências de estados de corrida,
passe, chute e cabeçada, incluindo antes, contato e depois. Não é necessário
rotular clips manualmente: os ponteiros/campos permitem identificá-los.
Uma sequência observada valida esses caminhos; não substitui as demais
rotinas pendentes nem comprova gameplay completa sozinha.
