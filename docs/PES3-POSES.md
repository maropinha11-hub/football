# Montagem de poses do treino PES 3

Esta etapa recupera caminhos de montagem de poses com o save state enviado,
incluindo caches, dois buffers por atleta, mistura, espelhamento e conversão
para pontos/matrizes compostos. Os caminhos alcançados foram traduzidos em
C++ e comparados com as instruções originais no modelo aritmético declarado.
Também há quatro helpers semânticos que trabalham com vetores e matrizes,
sem receber memória do PS2. **A importação para o jogador do treinamento
Windows continua pendente.**

## Consultar os resultados

Baixe [pes3-pose-research.zip](../artifacts/pes3-pose-research.zip), extraia e
abra `abrir-laboratorio.html` com Edge ou Chrome. Expanda **Poses do treino
PES**, escolha a origem, o atleta/cenário e o buffer.

“Pose capturada no PES” lê os campos numéricos do save original. “Pose
reexecutada em C++” mostra a saída das chamadas definidas pelo teste,
conferidas contra o modelo das instruções originais. A indicação de memória
alterada identifica ações, subestados ou flags modificados para exercitar
um caminho. Mesmo com memória inicial intacta, os argumentos e a sequência
de chamadas são definidos pelo teste; não se retoma o PC salvo do emulador.

As poses são estáticas. A prévia usa os pontos compostos registrados, com
uma inversão visual do eixo vertical e fixação horizontal opcional. Não
recalcula esses pontos com a hierarquia diagnóstica do clip. Mudar o ID de
animação volta à reprodução do clip isolado. Exportar pose conserva os bits
e a origem da seleção.

## O que o código revelou

O layout foi conferido nos 44 esqueletos do estado: dois buffers para cada
um dos 22 registros de atleta. Isso não significa que todos participam
ativamente do treino. Cada cadeia tem 19 nós, pais em ordem topológica e
pares de espelhamento recíprocos.

| Rotina original | Papel nos caminhos examinados |
| --- | --- |
| `0x01113CC0` | Decodifica canais de um clip. |
| `0x01115130` | Avalia a pose local, usando o cache de arco curto. |
| `0x01115710` | Calcula o cache, respeitando a flag de validade. |
| `0x01115520` | Mistura dois buffers de pose. |
| `0x011156B0` / `0x01115C20` | Verifica e aplica a representação espelhada. |
| `0x01115940` | Obtém a representação local a partir das representações disponíveis. |
| `0x01115EA0` / `0x01116060` | Converte representações e monta matrizes/pontos compostos. |
| `0x0113C8B0` | Monta a pose do atleta nos caminhos alcançados, com buffers, tabelas e helpers. |

No nó, `+0x40/+0x50` guardam translação/quaternion locais;
`+0x60/+0x70`, quaternion/ponto compostos; `+0x00`, matriz em colunas;
`+0x104`, próximo nó; `+0x108`, pai; `+0x10C`, par de espelhamento.
Os campos de cache e as flags não podem ser descartados para reproduzir a
mesma etapa de processamento.

A interpolação dentro de um clip e a mistura entre buffers usam rotinas
diferentes. A mistura examinada em `0x010D29B0` escolhe o sinal do quaternion
pelo produto escalar, interpola e normaliza: **NLERP de arco curto**. Os
produtos, somas, redução do produto escalar e zeros com sinal precisam manter
a ordem das operações originais no modelo. Não foi substituída por uma
SLERP genérica.

As chamadas de montagem deixam representações pendentes. Os cenários
finalizam os dois buffers com a conversão original antes de exportar pontos
compostos, pois uma transição pode trocar o buffer selecionado. A avaliação
local é comparada no seu próprio retorno: uma conversão posterior também
pode reescrever campos locais, incluindo a quarta componente da raiz.

## Evidência e alcance

O [relatório resumido](pes3-pose-validation.json) registra as contagens,
hashes, escopos, testes e pacote. `pose-validation.json.gz`, dentro do ZIP,
contém os retornos completos de cada chamada: hashes de toda a EE RAM e do
scratchpad, 32 registradores gerais baixos, 32 registradores FPU, quantidade
e sequência de instruções. O C++ e a referência são executados separadamente.
Os helpers originais continuam executando; nenhum retorno nativo é injetado
no interpretador.

| Verificação executada | Resultado |
| --- | --- |
| Cenários de montagem | 305/305 concluídos; nenhum bloqueado. |
| Chamadas originais × C++ no modelo declarado | 1.113/1.113 iguais nos retornos verificados. |
| Instruções originais examinadas nessa montagem | 5.741.559; 52.414 palavras traduzidas. |
| Avaliação local com cache recalculado × port v0.14 | 44/44 iguais em bits. |
| Quatro helpers semânticos × instruções originais | 5.434/5.434 comparações iguais em bits. |
| Regressão da seleção de animações | 234 cenários; 276/276 chamadas iguais no modelo. |
| Testes Python/C++ | 61 aprovados; nenhum falhou ou foi pulado. |
| Interface Chromium com o HTML empacotado | 54 verificações aprovadas; nenhum erro JavaScript ou pedido de rede. |
| Avaliação local recalculada × campos finais gravados | 0/44 poses inteiras iguais; divergência aberta. |

O pacote tem 17.669.713 bytes, 25 arquivos e CRCs conferidos. SHA-256:
`b97e21fa98b1f4f6c111b054164a209edc6b8aecaa7eda567cad44cf76d81a05`.
A [captura da interface](pes3-pose-lab.png) mostra os pontos compostos do
atleta 10, buffer 1, lidos do save.

Os cenários incluem os 22 atletas, os 44 buffers com cache mantido ou
recalculado, espelhamento/conversão, 62 códigos de ação com subestado zero,
13 subestados da ação 1, 23 pedidos, atualização coletiva e sete pesos de
mistura. Exercitam caminhos específicos desses estados; não todos os ramos.
Os valores de retorno da rotina de montagem não foram interpretados como
um código de sucesso de uma API recuperada: a conclusão é o retorno normal
da chamada dentro do modelo.

**A divergência contra a pose local gravada permanece aberta.** A avaliação
com cache recalculado coincide com o port local v0.14 nos 44 buffers novos,
mas não produz poses inteiras idênticas aos campos finais capturados.
O relatório conserva essas diferenças separadamente dos testes aprovados.
A comparação antiga de 0/132 pertence a outros estados, cujas memórias
completas não foram enviadas; não foi convertida em um resultado aprovado.
Caches e etapas posteriores foram identificados, mas isso não resolve todas
as diferenças numéricas ou de ordem do quadro.

A aritmética usa host IEEE binary32, produtos/somas separados e tratamento
selecionado de subnormais. VU/FPU, temporização, flags, dispositivos e
arredondamento específico do PS2 não estão integralmente emulados.
As operações adicionais foram conferidas nas tabelas de codificação do
[PCSX2 v2.8.2](https://github.com/PCSX2/pcsx2/blob/v2.8.2/pcsx2/R5900OpcodeTables.cpp).
A implementação do emulador não foi copiada. Igualdade com esse modelo
nunca é apresentada como igualdade de todo o hardware ou da gameplay.

## Reescrita sem memória do PS2

[`pose_ops.hpp`](../tools/pes3/recovered/pose_ops.hpp) contém funções C++
com entradas/saídas próprias:

| Helper | Rotina de origem |
| --- | --- |
| `multiply` | `0x010D3060`, composição de quaternions. |
| `matrix` | `0x010D2F00`, matriz em colunas com ordem original das operações. |
| `rotate` | `0x010D2FF0`, transformação no domínio selecionado. |
| `blend` | `0x010D29B0`, mistura NLERP com escolha do sinal e normalização. |

[`verify_pose_ops.py`](../tools/pes3/verify_pose_ops.py) executa primeiro os
helpers originais com operandos numéricos dos ossos capturados, realocados
numa cópia de RAM. Depois compara os resultados C++ em bits. São 5.434
comparações: 836 para cada um dos três primeiros helpers e 2.926 para mistura.
O ZIP inclui vetores e wrapper C para repetir a comparação. Os exemplos
sintéticos dos testes verificam também identidades, sinal oposto, quarta
componente, entradas inválidas e preservação da saída em falhas.

Essas funções são uma parte da futura ponte para a engine. Não constituem
um sistema completo de seleção, rig, espelhamento, contato ou física da bola.
`pose-native/` conserva separadamente a recompilação dos caminhos completos
alcançados, que ainda trabalha com registradores e endereços representados
na memória EE. Endereços PS2 nunca viram ponteiros executáveis no Windows.

## Adaptação ao nosso jogador

[`retarget.py`](../tools/pes3/retarget.py) confere o XML nativo e prepara
relações candidatas dos 19 nós PES com os 13 nós esqueléticos do nosso
jogador. O 14º canal de animação nativo é `player`, responsável pela
translação da engine. As cadeias ancestrais são conservadas para compor os
quadros intermediários; copiar quaternions por índice não é uma conversão
válida entre esses esqueletos.

[O plano de adaptação](pes3-retarget-plan.json), também incluído no ZIP,
registra os pares, cadeias, posições de referência e
hash do objeto nativo. Os nomes anatômicos são hipóteses de correspondência
pela topologia, não símbolos recuperados do PES. Lados, eixos, correções da
pose de referência, escala e sincronização dos contatos continuam pendentes.
As flags `runtime_enabled`, `axes_calibrated`, `scale_calibrated`,
`left_right_calibrated` e `ball_contacts_validated` permanecem falsas.

O pacote Windows jogável aprovado permanece com SHA-256
`ee913811b5fd1c5a18a3943a2228bb7b59436712b154b23826b7f8505d4b3443`.
Esta entrega não modifica a câmera, os controles Xbox ou a física nativa.
Também não inclui o save completo, RAM, malhas, ISO ou executável PES.

## Reprodução

Com as dependências já preparadas na nuvem, defina `PES_CORE`, `PES_STATE`,
`PES_ELF` e `PES_OVER` para os arquivos recebidos. Use novas pastas de saída:

```bash
python3 tools/pes3/pose.py --state "$PES_STATE" --elf "$PES_ELF" --over "$PES_OVER" --analysis /tmp/pes3-actions-final/actions.json --core "$PES_CORE" --output /tmp/pes3-poses-novo
python3 tools/pes3/retarget.py --evidence /tmp/pes3-poses-novo/pose-evidence.json --output /tmp/pes3-retarget-novo.json
python3 tools/pes3/build_lab.py --core "$PES_CORE" --actions /tmp/pes3-actions-final --validation /tmp/pes3-actions-final-validation.json --replay /tmp/pes3-replay-novo --pose /tmp/pes3-poses-novo --output /tmp/pes3-poses-lab-novo.zip
python3 -m unittest discover -s tests -p 'test_pes3*.py' -v
python3 tests/pes3_lab_smoke.py /tmp/pes3-poses-lab-novo.zip --output /tmp/pes3-poses-browser-novo.json
```

As etapas anteriores de análise e reexecução estão em
[PES3-ACTIONS.md](PES3-ACTIONS.md) e [PES3-SAVESTATE.md](PES3-SAVESTATE.md).
Python 3, `zstandard` e g++ são usados na pesquisa; Playwright/Chromium, no
teste de interface. O HTML offline usa apenas Edge/Chrome. O teste da nuvem
carrega os mesmos bytes com `set_content`; abrir por arquivo no Windows
continua sendo uma verificação distinta. Nenhuma configuração de ambiente
adicional foi necessária nesta etapa.
