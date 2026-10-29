# Referências PES e integração de animações

Auditoria de 29/10/2026. A gameplay entregue continua sendo a do Football,
com animações nativas e IK. Nenhuma gameplay exata do PES foi integrada e
nenhum clipe PES 2021 foi instalado no executável.

## pes2017-recomp

Foi inspecionado o commit
[`8dd109b`](https://github.com/dzakyraf/pes2017-recomp/tree/8dd109b38f875774275e259550d066cefd618da0).
O projeto traduz instruções PowerPC da edição europeia de Xbox 360 para C++
e fornece o runtime de sistema, gráficos e áudio. O fluxo documentado compila
para Android ARM64; o CMake também contém caminhos para um programa host.

O código traduzido do jogo é produzido localmente na pasta `ppc/`, excluída
do Git. É necessário o `default.xex` e os arquivos de dados dessa edição.
O `PES2017.exe` x86 de Windows já recebido é um executável de outra arquitetura
e não é a entrada desse recompilador.

Foram lidos o processo de build, a configuração de limites de funções,
`runtime/title.h`, os hooks de inicialização e apresentação, o mapeador de
símbolos e a documentação de portabilidade. Os hooks publicados são ajustes
de runtime; não expõem uma API independente de recepção, chute, física da bola
ou seleção de animação. Os diagnósticos de jogador em `title.h` ainda têm
endereços zero. O sidecar `config/pes_symbols.txt` não está no checkout.

Há também heranças do projeto-base: `tools/find_in_title.py` procura a entrada
`mp` e `title.VERSION`, ausentes do `tools/title.py` deste commit. Esse utilitário
não pode ser tratado como um decodificador pronto da gameplay PES.

O repositório é útil para estudar tradução de instruções, dependências do
runtime e validação numérica. Não foi executado aqui e não houve incorporação
do seu código GPL ao Football. As alegações de partida funcionando no Android
são do upstream, não testes deste ambiente.

Para a edição Windows, o estudo anterior identificou 65 campos de parâmetros
da bola no executável. Ainda faltam os valores ativos, as unidades confirmadas,
as rotinas e os dados de animação, além de trajetórias de referência para comparar
a execução. Não foi criado um segundo launcher que apenas renomeie a gameplay
atual como se fosse o PES original.

## pes-gani / PES 2021

Escopo confirmado pelo usuário: aproveitar **somente as animações do PES 2021**,
identificadas pelos nomes. A física, os controles e a lógica de escolha de jogadas
continuam sendo os do Football. A auditoria da recompilação de 2017 acima fica
como referência; não é um requisito para importar esses clipes de 2021.

Foi inspecionado o commit
[`4f6dbf0`](https://github.com/jhnzbdev/pes-gani/tree/4f6dbf00f66df761ce2f6ac9b2d80af48e172788).
O leitor MIT e o mapa de nomes foram preservados em `third_party/pes-gani`,
com licença e hashes dos arquivos em `UPSTREAM.json`.

Esse leitor recupera clipes GANI em contêineres MTAR, rotações, translação da
raiz e tempos de chave. O upstream relata PES 2021 como verificado; PES 2019/2020
são compatibilidades esperadas, e PES 2017 não foi validado. Aqui passaram os
dois vetores conhecidos de StrCode32 e a verificação dos hashes dos **4.105
nomes** publicados. Isso não equivale a decodificar 4.105 animações reais aqui.

Pontos relevantes para evitar as deformações de integrações anteriores:

- O rig original descrito tem 20 ossos e nosso modelo utiliza 13.
- A associação de canais depende do `.frig`, inclusive das cadeias IK dos braços.
- O leitor usa escala de 0,01 para translações e π/2 para meios ângulos.
  Não se deve transportar para 2021 a hipótese angular de outro leitor de 2017.
- A raiz precisa permanecer separada da trajetória que o Football já aplica.
- Nosso importador preserva chaves esparsas. O `--dense` do upstream usa
  interpolação linear normalizada, que não prova interpolação idêntica à engine.
- Nomes, hashes e índices `info` ajudam a classificar o acervo; não recuperam
  sozinhos as regras que escolhem cada jogada nem as equações da física.

Os arquivos necessários vêm do `dt13_all.cpk` da cópia do usuário:

```text
common/anime/FoxAnim/Body/body_anime_file0.mtar ... body_anime_file9.mtar
common/anime/FoxAnim/Body/CharacterAssets/body_anim_skel.ask
common/anime/FoxAnim/Body/CharacterAssets/body_skel.frig
```

A preparação do leitor não altera o jogo. Para inventariar um MTAR extraído:

```bash
python3 tools/animations/read_pes_gani.py body_anime_file0.mtar
```

Para decodificar as chaves e o rig original, em uma pasta de saída nova:

```bash
python3 tools/animations/read_pes_gani.py body_anime_file0.mtar \
  --skeleton body_anim_skel.ask --rig body_skel.frig --output /tmp/pes2021-clips
```

O wrapper valida limites de tabelas, hierarquia, mapeamento de canais,
quaternions, valores finitos e tempos. Os testes utilizam arquivos sintéticos
independentes, sem movimentos proprietários. O próximo passo depende de clipes
reais: validar o rig e seus eixos, adaptar um único movimento ao modelo nativo
e conferir o contato na imagem antes de instalar outros. Esse processo não
substitui a recuperação e comparação da física e do seletor original.

Proveniência e limites: [pes-reference-research.json](pes-reference-research.json).
