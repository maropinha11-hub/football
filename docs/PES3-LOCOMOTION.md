# Locomoção PES 3: direção, decisões especiais e execução consecutiva

Esta continuação recupera código em estruturas próprias e verifica a ligação
entre direção, seleção e velocidade. **A importação para o treino continua
pendente.** O [pacote de locomoção](../artifacts/pes3-locomotion-research.zip)
contém código e vetores; o [coletor Windows](../artifacts/pes3-resource-collector-windows.zip)
recolhe os recursos de inicialização. O ZIP já foi recebido e conferido na
[etapa de recursos e referência](PES3-RECURSOS.md). O coletor não atualiza o jogo.

## Código e conferência

| Rotina própria | Código original | Conferência nova |
| --- | --- | --- |
| `locomotion_direction.hpp` | `0x018783B0..0x0187866C`, helpers reais de ângulo/distância/giro | 1.805 decisões |
| `locomotion_prediction.hpp` | `0x01854F20` e predicado `0x017D5990` | 646 predições + 141 predicados por perfil |
| `locomotion_special.hpp` | Dispatch `0x0187866C`, ramos 61/62/63 até `0x0187927C` | 210 decisões + 210 velocidades |
| `locomotion_variants.hpp` | Mesmo dispatch, ramos 28/35/48/864 | 319 decisões + 319 velocidades por perfil |
| `locomotion_chain.hpp` | Segmento consecutivo `0x018783B0..0x0187930C`, onze clips | 254 cenários por perfil |

Predição, variantes e sequência foram repetidas com FPU host binary32
`nearest` e `chop`, divisão/raiz `nearest`. Os ramos 61/62/63 e o seletor comum
usam a referência fixada anteriormente. Isso não prova aritmética completa do
PS2; a configuração EE/VU do PCSX2 do usuário permanece desconhecida.
O [registro de validação](pes3-movement-validation.json) conserva relatórios,
hashes, instruções e escopos. A nova execução comum mantém 92 decisões e
velocidades. O clip **35** agora é rejeitado pela API comum, porque tem um
ramo próprio comprovado no dispatch.

As tabelas em `locomotion_tables.hpp` vieram do ELF/overlay e coincidem com
a RAM: ângulos (257 entradas, `0x0129D890`), projeção (512, `0x018EB950`) e
direções internas (16, `0x018E56D0`). Não são um mapeamento de botões do Xbox.

A composição usa novas orientações, subestado, distância e diferença angular
da direção no seletor seguinte, e passa sua amplitude à velocidade. Entradas
incoerentes e caminhos não suportados são rejeitados sem alterar a saída.
O segmento original roda consecutivamente, sem injetar resultados C++ na
referência. Helpers originais continuam executando; valores numéricos de
perseguição/gate/reinício/limite são fornecidos explicitamente à API.
Os onze clips testados são 28/35/47/48/61/62/63/119/304/613/864.

São distintos os pedidos de troca simples com refresh, comparação de fase e
início codificado. O **714** do ramo 864 é argumento codificado, não frame
714. A velocidade de animação do ramo 28 é conferida antes da troca de fase,
que pode sobrescrevê-la. O ramo 47 calcula seu mínimo no segmento composto.
Wrapping, comparações estritas e ordem são preservados sem adivinhar gestos.

O replay offline recompila C++14 e passa em **6.920 comparações**, incluindo
perfis repetidos, velocidade composta e os 1.153 vetores de velocidade da
etapa anterior. Não são jogadas capturadas. Os **115 testes** das ferramentas
passam, incluindo domínio C++ com sanitizador de comportamento indefinido e
coleta/importação de AFS sintéticos. O coletor foi exercitado com PowerShell
7.4.6/Linux: espaços, ausência de nomes, corrupção, deduplicação, preservação
dos arquivos de entrada e ZIP/importação. A interface gráfica, batch Windows
11 e PowerShell 5.1 não foram executados nesta máquina.

## Busca de recursos no save antes da coleta

O save recebido é o atleta parado com bola, conforme informado pelo usuário.
Os cenários modificam cópias da memória; não retomam quadros do emulador.
O modelo da RAM já está animado ([investigação do rig](PES3-RIG.md)) e não
fornece, sozinho, uma inicialização calibrada para o esqueleto nativo.

Conferimos os carregadores `0x011801F0` e `0x011A2CD0`: solicitam os recursos
`0x00470000` e `0x00470001`. Seus ponteiros globais no save estão zerados.
Um candidato a cabeçalho de `body_lnk.bin`, em `0x00F4F000`, falha na
descompactação zlib; não foi exportado como arquivo válido. Nenhum fluxo
íntegro de `mon_lnk.bin` com o tamanho relatado foi encontrado.
O [registro da busca](pes3-cached-links.json) conserva os endereços e o erro.

Os [caminhos de recursos](pes3-resource-paths.json) foram recuperados dos 92
descritores do executável, em `0x0129D440`. O coletor segue índices/contagens,
dispensando nomes AFS e seleção manual de gestos. Tenta DATA E/F/G/I/S
disponíveis e registra divergências; não presume bytes iguais entre idiomas.
Nomes/tamanhos relatados precisam ser conferidos nos arquivos reais.

## Coletar no Windows 11

1. Baixe e extraia [pes3-resource-collector-windows.zip](../artifacts/pes3-resource-collector-windows.zip).
2. Abra `ColetarPES3.bat` e escolha `01_ISO_EXTRAIDA`, a pasta com `DATA_*.AFS`.
3. Envie o `PES3-recursos-....zip` criado ao lado do coletor. A leitura pode
   levar alguns minutos; a janela permanece aberta e mostra erros.

Não precisa instalar Python ou outro sistema. Também pode arrastar a pasta
sobre o `.bat`. A coleta lê os arquivos, cria uma saída nova e não envia nada
pela rede. Recolhe `body_lnk.bin`, `mon_lnk.bin`, `anime.bin`, `anime2.bin`,
`anime3.bin` e `game.mbc`, com origem/offsets/hashes. Deduplica recursos iguais.
O MBC relatado tem payload bruto de 1.750 bytes após o cabeçalho de 32;
esse caso é preservado sem interpretar campos desconhecidos como zlib.

Se nenhum DATA corresponder, envie `manifesto.json` da pasta indicada. Se
`SLES_519.12` estiver na pasta, seu hash precisa corresponder à revisão
recebida. O coletor verifica limites/contagens/cabeçalhos; o importador na
nuvem confere CRC ZIP, SHA256, fim/tamanho/checksum zlib e preserva o MBC bruto.
Hashes das DATA no manifesto são observações do coletor, sem conferência
independente dos arquivos DATA que ainda não recebemos.

## Reproduzir

No pacote de locomoção extraído, com Python 3 e g++:

```sh
python3 verify_movement_vectors.py . --output resultado-local.json
```

Uma execução nova das ferramentas `verify_direction.py`, `verify_prediction.py`,
`verify_special.py`, `verify_variants.py` e `verify_locomotion_chain.py` exige
`--state`, `--elf`, `--over`, `--core` (v0.14 extraído) e uma pasta nova em
`--output`. Predição, variantes e sequência aceitam `--fpu-rounding chop`.
O importador dos recursos funciona assim:

```sh
python3 tools/pes3/import_collected_resources.py PES3-recursos.zip --output /tmp/pes3-recursos-importados
```

Ainda faltam outros caminhos especiais, preparação/ações completas,
relógio/poses/contatos, colisões e física completa. Os recursos recebidos
agora coincidem com FPSANM14 e sua inicialização de referência foi recuperada
([conferência](PES3-RECURSOS.md)); escala/eixos/apoio para o motor nativo
ainda precisam ser calibrados. O runtime do treino aprovado permanece o mesmo;
IDs PES não foram convertidos diretamente para tipos de ações nativos.
