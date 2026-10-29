# Estudo da referência PES 2017

As duas partes `PES2017.7z.001/.002` foram recebidas e recompostas. Cabeçalhos
e CRCs do 7z foram verificados; o executável tem 110.179.840 bytes e SHA256
`6598860f6cce192e7a7017bad451aa62fc01d9c3c76806eeebafc0691fe22a26`.
É PE32/x86, com 25 módulos de imports estáticos, conferidos também por GNU
objdump. O recurso de versão declara 1.0.0.0; caminhos de compilação contendo
`Patch10100` não comprovam, sozinhos, a versão funcional do patch.
A instalação do PC Windows não está montada no ambiente na nuvem.
O prompt recebido termina na frase incompleta “comportamentos complex”.

**Animações recebidas:** o usuário enviou separadamente `Data/dt13_win.cpk`.
O índice de 295 entradas foi validado, os dez MTARs corporais e o rig foram
extraídos, e 2.956 clipes foram decodificados. Uma prévia de `run_2_0` foi
renderizada no modelo nativo. Veja [o relatório e os limites atuais](../../docs/ANIMACOES-PES2017.md).
As descrições de coleta abaixo ficam como histórico; o CPK já recebido não
precisa ser reenviado. A biblioteca ainda não foi ligada às ações da partida.

Foram identificadas 193 referências a caminhos de constantes/animações e
recuperados 65 nomes de campos da bola, seus destinos numa estrutura de
436 bytes e suas origens no leitor de dados serializados. Isso **não recupera
os valores ativos nem as equações da física**. O construtor inspecionado
inicializa dados em zero; não se pode usar esses zeros como constantes reais.
Veja [o relatório](../../docs/pes2017-analysis-validation.json) e
[o esquema](../../docs/pes2017-ball-schema.json). O executável não foi rodado,
e nenhum componente proprietário é incluído nas ferramentas.

O executável já foi recebido integralmente; não é necessário reenviá-lo.
Para outras transferências grandes, use 7-Zip, **Adicionar ao arquivo → Dividir em
volumes: 24M**, e envie todas as partes `.7z.001`, `.7z.002` etc. O divisor
`scripts/dividir-arquivos.bat`, incluído no pacote anterior, também funciona
com executáveis e arquivos 7z: selecione “Todos os arquivos” na janela e envie
as partes e o manifesto. Não junte as partes por texto nem renomeie apenas uma
delas para `.exe`.

## Inspeção estática

`windows/ColetarPES2017.bat` abre um seletor de arquivo no Windows. O coletor
produz um ZIP pequeno com SHA256 do executável, cabeçalhos PE e inventário
das pastas raiz, `Data` e `download`. Não copia os arquivos de jogo, não os
executa nem altera a instalação. Esse caminho permite obter a identidade da
versão e a estrutura local antes de transferir o binário inteiro.
O inventário gerado pelo usuário no Windows foi recebido: 115 arquivos,
84 CPKs, nenhum erro, SHA256 do executável e metadados das 14 seções iguais
ao arquivo analisado. Veja [a validação da instalação](../../docs/pes2017-installation-validation.json).

## Coleta seletiva de recursos

A instalação contém pacotes com nomes DMPES e arquivos Sider. A presença
desses arquivos não identifica, por si só, a configuração ativa nem uma
referência original sem modificações. Não se deve assumir que um pacote
`Gameplay.cpk` está ativo ou contém os parâmetros desejados apenas pelo nome.

O novo `windows/ColetarRecursosPES2017.bat` lê índices dos CPKs em `Data` e
`download`. Seleciona `.bin/.json` de `common/match/constant` e `.bin` das
pastas `common/anime/playerID/bin`, `AnimeTable/bin` e `Mbinfo/bin`. Registra
origem, intervalos, hashes e variantes dos mesmos caminhos em arquivos
diferentes. Também guarda os pequenos `sider.ini`, `gameplay.ini` e
`download/DpFileList.bin`, necessários para investigar carregamento e
sobreposições. Nas raízes avulsas configuradas dentro da instalação, só
examina essas mesmas categorias; não executa módulos ou Lua.

O leitor C# foi escrito para este projeto. Usa fatos do formato CPK/UTF
consultados em CriPakTools e vgmstream, com URLs e hashes em
[pes2017-cpk-research.json](../../docs/pes2017-cpk-research.json).
Lê números e offsets com as ordens de bytes corretas; suporta tabelas UTF
normais e a máscara de tabela do formato CRI. Não modifica proteção do jogo.
Valida limites, tipos, nomes e intervalos do índice antes de exportar um
arquivo. Containers só com ITOC/sem TOC nominal ou estruturas não suportadas
são registrados como erros; não se adivinham nomes ou offsets.

A saída preserva bytes armazenados, incluindo CRILAYLA ou outros wrappers.
Nenhuma descompressão ou equivalência de parâmetros é alegada nessa etapa.
Os recursos são identificados pelo hash completo de seu conteúdo; o hash do
CPK inteiro só é calculado para arquivos selecionados de até 512 MiB. Para
os maiores, a procedência é explicitamente parcial: tamanho e hashes das
tabelas, além dos hashes integrais de cada recurso. Não confundir isso com
hash integral do CPK ou confirmação de uso em execução.

O limite é 24 MiB por recurso e 128 MiB de bytes selecionados no total. Um
recurso maior é registrado como não coletado. Se o ZIP exceder 30 MiB, a
ferramenta divide automaticamente em partes de 24 MiB e gera seus hashes.
O usuário envia o ZIP ou todas as partes e o manifesto correspondente.

O núcleo C# foi compilado e executado em Mono/Linux com containers sintéticos
independentes: tabelas normais/mascaradas, constantes, campos zero, UTF legado,
TOC antes/depois dos dados, aliases, compressão preservada, truncamento,
limites, caminhos inválidos e índices sobrepostos. O novo invólucro PowerShell
e a seleção de pasta ainda não foram executados em Windows. O inventário
anterior foi executado pelo usuário; não se trata de uma execução local do
novo coletor. Nenhum CPK real completo foi recebido ainda.

```bash
# Com Mono/mcs.exe disponíveis (ou PES2017_TEST_MONO/PES2017_TEST_MCS):
python3 -m unittest discover -s tests -p test_pes2017_collector.py -v
```

Depois de receber os recursos, verificar seus hashes, identificar os wrappers
e os objetos serializados, decodificar parâmetros sem presumir unidades e
comprovar quais variantes são usadas. A calibração da gameplay continua
dependendo de entradas e trajetórias medidas no PES.

## Ferramentas de análise

Após a transferência integral, a ferramenta Python faz análise limitada e
verificada de cabeçalhos, seções e imports estáticos:

```bash
python3 tools/pes2017/inspect_executable.py /caminho/PES2017.exe --output /tmp/pes2017-pe.json
```

Não carrega o executável. Um import é uma dependência declarada, não prova de
onde está a gameplay. RVA não é endereço virtual absoluto nem offset de
arquivo; o leitor faz a conversão pelas seções. Não há bypass de proteção,
injeção, extração de conteúdo de CPK ou distribuição de componentes originais.
Desmontagem/decompilação de funções e observação do jogo em execução ficam
limitadas ao que foi documentado; a observação em execução e os arquivos de
parâmetros ainda dependem de evidências locais.

O extrator do esquema aceita apenas a revisão recebida, recusando outros
hashes antes de reutilizar seus endereços. Ele acompanha a procedência do
retorno de funções: algumas escritas de inteiros/bytes ocorrem depois que
a próxima chave já foi colocada na pilha, sem pertencer à próxima chave.

```bash
python3 tools/pes2017/recover_ball_schema.py /caminho/PES2017.exe \
  --objdump objdump --output /tmp/esquema-bola.json
```

`decode_ball_blob.py` pode decodificar o objeto binário quando o recurso e
seu offset correto forem identificados. O offset precisa ser explícito;
ponteiros de arrays são relativos ao objeto e suas leituras são limitadas
ao arquivo. Testes com dados sintéticos verificam o decodificador, sem
contar como valores do PES. Não há busca automática de um bloco que
“pareça realista”, nem instalação desses dados no Football.

## Comparação reproduzível

`calibration.py` exporta a telemetria existente do Football e compara dois
registros. Não altera parâmetros do jogo. Cada registro declara versão e hash
do executável, cenário, condições, procedência, unidades e comandos observados.
As posições devem estar em metros, os tempos em segundos e os eixos em
`x_forward_y_left_z_up`. A origem horizontal e o rumo inicial são definidos
antes do ensaio; a altura continua referida ao gramado.

O exportador exige início/fim explícitos, recusa cruzar um reinício e não
deduz botões de controle ausentes no log. No log atual, o gamepad registra
movimento e chute; passe/RB precisam de instrumentação adicional para uma
comparação dessas ações. Os bits de teclado existentes permitem registrar
esses botões em ensaios de teclado. A resolução atual é 100 ms, insuficiente
para afirmar equivalência de latência, contato ou poses a cada quadro.

Exemplo de arquivo de cenário **a preencher com condições efetivamente medidas**:

```json
{
  "scenario": "low_speed_carry",
  "conditions": {
    "case_id": "identificador-comum-do-ensaio",
    "player_profile": "registrar-altura-atributos-pe-dominante",
    "pitch_and_ball": "registrar-condicoes",
    "control_assistance": "registrar-opcoes"
  },
  "required_inputs": ["move"]
}
```

```bash
python3 tools/pes2017/calibration.py export-native \
  --log /caminho/game.log --executable build/gameplayfootball \
  --case /tmp/caso.json --start-ms 1200 --end-ms 3200 \
  --heading-rad 0 --output /tmp/football-trace.json

python3 tools/pes2017/calibration.py compare \
  --reference /tmp/pes2017-trace.json --candidate /tmp/football-trace.json \
  --tolerances /tmp/criterios.json --output /tmp/comparacao.json
```

O registro PES deve vir de medição instrumentada ou vídeo com escala de campo
e tempo calibrados; a procedência declarada continua sujeita a verificação.
Não existe ainda um coletor de posições em memória do PES: nenhum endereço
foi descoberto ou presumido. O coletor de inventário não mede gameplay.

`criterios.json` exige quatro limites positivos, explicitamente escolhidos
como critérios de engenharia: `player_position_rmse_m`,
`ball_position_rmse_m`, `player_speed_rmse_mps`, `maximum_input_error`.
Eles não são valores físicos extraídos do PES. Registros com unidades,
condições, comandos necessários ou durações incompatíveis são recusados.
As métricas não ajustam automaticamente escala, rotação ou velocidade do
tempo para disfarçar diferenças. A comparação usa a cadência mais grossa
disponível, sem inventar resolução. O relatório mostra também distância,
velocidade amostrada, separação jogador/bola e altura da bola.

Dados sintéticos ou comparação do Football consigo mesmo recebem resultado
`self_or_synthetic_test_only`, nunca aprovação de equivalência ao PES.
Até receber medições originais, **não há resultado PES × Football**.

Ensaios necessários: aceleração reta, frenagem, reversão, condução lenta,
condução máxima, curva com bola, rolamento livre, quique, passe parado e
varredura de carga de chute. Repetir cada caso com as mesmas entradas e
condições, reservando repetições para validação depois da calibração.

O projeto permanece C++/SDL2/OpenGL; controles estão em `src/hid`, seleção e
movimento em `src/onthepitch/player`, bola em `src/onthepitch/ball.cpp`, treino
e telemetria em `src/onthepitch/training.cpp`, e física experimental em
`src/onthepitch/player/humanoid`. Essas ferramentas preservam os executáveis,
as animações e a gameplay da versão aprovada. Não são uma nova gameplay PES.
