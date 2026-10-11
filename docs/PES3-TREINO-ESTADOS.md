# Dez saves de treino: decisões e marcadores das animações

Os dez arquivos recebidos em 11/10/2026 são válidos, distintos e compatíveis
com a revisão SLES_519.12 estudada. Eles permitiram conferir gestos e
locomoção em movimento, além do save parado anterior. Nesta etapa foram
reescritas a regra temporal dos marcadores e a escolha variável do ponto
de referência da bola no clip 741. **As animações PES ainda não estão
integradas ao executável Windows.**

O [relatório](pes3-training-states-validation.json) contém os hashes dos
dez arquivos, atores, clips, condições observadas e resultados.
O [pacote reproduzível](../artifacts/pes3-training-states-research.zip)
tem 422.287 bytes, 20 arquivos e SHA-256
`200fb5f31b8d27188690368c476f3105160f67733a75eb120f71b229227add85`.
Contém código e provas numéricas; não atualiza o jogo. Não é necessário
instalar Windows novamente nem substituir o treino aprovado.

## O que os arquivos comprovam

Cada ZIP teve tamanhos, descompressão e CRC conferidos. Em cada RAM foram
comparadas 386.812 palavras de instrução do ELF/overlay analisado e os
999 blocos de animação carregados, integralmente, com o contêiner validado.
Os 106 clips do terceiro banco não estão carregados nestes estados.

As chaves compactadas também explicam todos os canais A/B de rotação:
**880 conjuntos, 66.880 componentes**, usando o produto binary32 `chop`
declarado. Esse resultado identifica a origem dos canais. A interpolação,
mistura e pose final não ficam automaticamente comprovadas por ele.

| Slot | Ator selecionado | Ação / subestado | Clip | Fase capturada |
| --- | ---: | --- | ---: | ---: |
| 01 | 9 | 1 / 16 | 47 | 48,3489 |
| 02 | 5 | 11 / 32 | 313 | 22 |
| 03 | 5 | 0 / 2 | 304 | 22 |
| 04 | 10 | 27 / 32 | 219 | 23 |
| 05 | 10 | 0 / 2 | 304 | 3 |
| 06 | 10 | 4 / 34 | 269 | 40 |
| 07 | 11 | 1 / 16 | 47 | 46,4844 |
| 08 | 10 | 27 / 2 | 206 | 13,6000 |
| 09 | 8 | 14 / 21 | 797 | 25 |
| 10 | 8 | 4 / 17 | 275 | 25 |

Os números preservam o domínio original, sem nomes de gestos atribuídos por
suposição. Os nomes dos slots não estabelecem uma sequência de frames.
Alguns saves mostram a seleção automática de outro atleta enquanto o
anterior termina o gesto. O analisador inclui esses atletas: no slot 02,
por exemplo, também investiga o ator 9, ação 5, clip 236. No slot 04,
acompanha o ator 5, ação 8, clip 224; no 08, o ator 11, ação 9, clip 264.
Assim, selecionar Cafu não faz a análise atribuir a ele o gesto anterior.

## Chamadas originais e C++ recompilado

[`study_states.py`](../tools/pes3/study_states.py) executa atualizações dos
atores relevantes e os dois modos do seletor do atleta controlado.
São **35 chamadas sem edição de entrada, todas concluídas**, com 114.461
instruções executadas no modelo declarado. Nenhum helper original foi
substituído por um resultado pronto.

Os 19.149 endereços de instrução alcançados foram recompilados em C++17.
As 35 comparações conferem toda a RAM EE, scratchpad, registradores baixos
GPR/FPU e sequência de instruções. Não se retomou a CPU do PCSX2; são
chamadas explícitas com registradores normalizados, não frames completos.
Os perfis FPU/VU desta comparação são `nearest`.

Foram observadas chamadas de troca/mistura de animação, mudança de fase,
dez verificações temporais e uma liberação de bola com seu núcleo.
A liberação foi alcançada **no slot 01, ator 9 em locomoção**, não numa
cabeçada presumida: chamada em `0x01879D9C`, rumo 32768, amplitude 9037 e
argumento vertical 2. Alcançar essa chamada não prova os contatos de todos
os passes/chutes nem a física completa.

O índice automático incluído no ZIP associa os marcadores observados aos
clips e condições originais, sem pedir classificação manual:

| Clip | Ação observada | Marcadores observados |
| --- | ---: | --- |
| 224 | 8 | 16 |
| 236 | 5 | 10, 11 |
| 264 | 9 | 18, 20 |
| 269 | 4 | 16 |
| 275 | 4 | 16, 17 |
| 797 | 14 | 10, 26 |

Um marcador pode comandar uma transição ou uma verificação de contato.
O índice conserva essa distinção: não transforma todo marcador em toque
na bola, nem converte IDs PES em valores do enum nativo.

## Regra temporal reescrita

[`animation_events.hpp`](../tools/pes3/recovered/animation_events.hpp)
reescreve integralmente `0x0116AFE0..0x0116B078`:

```text
Se (blend_window != 0 ou cycle_fix != 0) e blend_tick == 0: bloquear.
delta = phase - conversão_signed32(marker), com arredondamento declarado.
Elegível quando -step/2 < delta <= step/2.
```

A borda inferior é aberta e a superior fechada. Com passo 1 e marcador
24, fase 23,5 não é elegível, enquanto 24,5 é. O port conserva a
conversão assinada, os flags, a divisão `nearest` e os perfis `nearest`
e `chop` das operações selecionadas, sem mudar o arredondamento global.

[`verify_animation_events.py`](../tools/pes3/verify_animation_events.py)
fez **4.280 comparações temporais**: 1.320 com campos capturados de todos
os 22 atletas e 2.960 com limites explicitamente modificados em cópias.
Os casos modificados incluem passos fracionários, zero/negativo, flags
de mistura/ciclo e conversões de marcadores assinados grandes. São probes
aritméticos, não frames observados do jogo.

## Ponto variável do clip 741

O pacote v0.14 marcava esse clip como não suportado pelo leitor inteiro
restrito, pois `0x016D2090` carrega um float de `context+0x41C`.
A investigação confirmou que o resultado depende desse campo. Portanto,
preencher a lacuna com um único track estático perderia comportamento.

[`ball_anchor_741.hpp`](../tools/pes3/recovered/ball_anchor_741.hpp)
reescreve a seleção de `0x016D2088..0x016D2110` e conserva os cinco pontos
signed-16 de `0x018E0350`. Calcula `trunc(-209 - context_y)` e escolhe
segundo os limites 37, 13, -16 e -51. O índice de referência permanece 7;
não foi renomeado como um osso anatômico sem conferência adicional.

São **246 comparações** contra chamadas completas do sampler original
`0x016CF420`, em dois perfis e três índices de amostra por entrada.
Os campos capturados dos dez saves e as fronteiras sintéticas são
registrados separadamente. As cinco alternativas foram alcançadas.
O sampler original confirmou coordenadas e índice de referência; o campo
`choice` do port foi conferido com o endereço da linha original selecionada.
O núcleo v0.14 recebido permanece intacto; este é um módulo próprio separado.

As duas reescritas totalizam 372.012 instruções originais verificadas.
Os espaços de coordenadas e as unidades originais são preservados.
Não foram inventadas conversões para metros nem nomes de pé/cabeça.

## Repetir as verificações

Com Python 3, g++, os arquivos recebidos e o núcleo v0.14 extraído:

```bash
python3 tools/pes3/study_states.py --state "SAVE01.p2s" --state "SAVE02.p2s" --elf "$PES_ELF" --over "$PES_OVER" --analysis "$PES_ANALYSIS/actions.json" --core "$PES_CORE" --output /tmp/pes3-estados-novo
python3 tools/pes3/verify_animation_events.py --state "SAVE01.p2s" --state "SAVE02.p2s" --elf "$PES_ELF" --over "$PES_OVER" --core "$PES_CORE" --output /tmp/pes3-eventos-novo
python3 tools/pes3/build_event_index.py --study /tmp/pes3-estados-novo --events /tmp/pes3-eventos-novo --output /tmp/pes3-indice-novo.json
```

Repita `--state` para cada um dos dez arquivos, na mesma ordem em ambos
os comandos. Escolha saídas novas. Os arquivos enviados são somente lidos.

Após extrair o ZIP publicado, `python verify_event_vectors.py .` recompila
os módulos próprios em C++14 e repete as 4.526 comparações com saídas
originais gravadas, sem saves, ISO, PCSX2 ou núcleo v0.14. Essa prova offline
também foi executada nesta entrega; ela não é uma nova execução do PES.

A suíte `test_pes3_*.py` passou em **142 testes**, incluindo fronteiras
temporais, flags, arredondamento, escolhas variáveis, saída atômica em
entradas inválidas e preservação do atleta anterior após troca de seleção.

## O que ainda impede a integração completa

Faltam a seleção/efeitos de contato nos demais contextos, a concordância
da avaliação e mistura das poses com os campos capturados, a calibração
de eixos/unidades/ossos e a adaptação desses resultados ao motor nativo.
Depois dessas ligações, será necessário compilar e testar o treino Windows,
incluindo condução, passes, chutes e cabeçadas em primeira pessoa.

Esta etapa não altera `src`, animações nativas ou o pacote Windows aprovado.
As verificações das chamadas e módulos acima passaram; equivalência da
gameplay completa, importação no treino e teste com controle físico ainda
não foram realizados. Nenhum dos relatórios marca o runtime como integrado.
