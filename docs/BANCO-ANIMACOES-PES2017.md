# Banco de ações PES 2017

Abra `treinar-animacoes-pes.bat`, depois de extrair o ZIP completo em uma
pasta nova. **Insert** compara com o banco original. **R3/Tab** alterna a
câmera; **R** reinicia a tentativa. Nenhuma pasta PES de outra versão precisa
ser copiada.
Para a partida com o mesmo banco, abra `partida-animacoes-pes.bat`.

O banco contém **1.833 clipes de origem** convertidos para o modelo do Football.
Eles geram **3.070 candidatos**: esse total inclui espelhos e a disponibilização
de recepções nos dois estados nativos de controle da bola. Essas cópias não
são contadas como novas capturas.

| Família | Clipes de origem | Aplicação |
| --- | ---: | --- |
| Passe | 142 | Chapa, bico, três dedos, diagonais e corrida |
| Chute | 72 | Batidas de diferentes alturas e ângulos, parado e correndo |
| Cruzamento/distribuição | 95 | Cruzamentos e lançamentos com os pés e as mãos |
| Cabeceio | 98 | Inclinações, saltos, alturas e direções diferentes |
| Recepção | 200 | Pé, canela, coxa, barriga, peito e cabeça |
| Condução e fintas | 422 | Passadas, solas, mudanças de direção e gestos de corpo |
| Locomoção | 300 | Esperas, caminhada, corrida e deslocamentos de campo/goleiro |
| Defesa de goleiro | 258 | Capturas, desvios e bloqueios |
| Cortes e carrinhos | 55 | Interceptações com os pés e corpo |
| Desequilíbrio | 149 | Reações, esquivas e quedas animadas |
| Recuperação | 42 | Transições de volta ao estado em pé |

O catálogo reproduzível está em
`data/media/training/pes17/catalog.json`; cada clipe tem sua proveniência ao
lado. As 21 receitas iniciais permanecem em `config/pes2017-action-recipes.json`.
As outras 1.812 adaptações são reproduzidas por
`tools/animations/build_pes_complete_bank.py`: o contexto é inferido dos nomes
e os marcadores de contato, da cinemática dos membros. O registro
`integration-audit.json` contabiliza os 2.956 arquivos recebidos.
Um clipe disponível no banco não precisa aparecer em toda tentativa: a
trajetória e a posição do corpo precisam permitir seu contato. A validação
registra quais fontes foram efetivamente usadas em cada cenário.

## Testar as ações

- **A**: passe; **Y**: profundidade; **B**: chute; **X**: cruzamento.
- Analógico esquerdo: movimento e direção; **RB**: corrida.
- **F4** envia um passe rasteiro; **Z+F4** envia pelo centro entre os pés.
- **7+F5** testa a canela/peito do pé; **8+F5**, a coxa; **F5**, o peito.
- **F6** envia uma bola alta; **Shift+F6**, uma bola para salto.
- **Home/End** ajustam a altura de F5/F6; **Delete** restaura a altura automática.
  As combinações numéricas de F5 mantêm suas alturas específicas.

Para tentar um passe ou chute de primeira, escolha a direção e aperte o botão
durante a chegada da bola. Um movimento que não alcance essa chegada conserva
as alternativas nativas. O modo PES também pode selecionar as novas conduções
e locomoções; as reservas nativas continuam disponíveis. `treino-classico.bat` e
`jogar-partida.bat` começam com o banco clássico.

## Adaptação e contato

A rotação geral do clipe Fox é separada dos canais dos ossos. O conversor
aplica essa rotação a toda a hierarquia antes de mudar os eixos para o modelo
nativo. Um caso sintético de giro de 90 graus verifica que o corpo gira uma
vez, preservando as rotações relativas dos membros.

As novas ações conservam o deslocamento horizontal de apoio. Nos movimentos
que começam parados, os primeiros e últimos 100 ms de velocidade da raiz são
ajustados para a entrada e a saída nativas; isso preserva a região do contato.
A torção inicial da pelve é tratada como preparação da batida. O passe já
aprovado conserva seus canais de pose, conferidos por um digest numérico.

Cada candidato possui seu próprio mapa de eventos. O construtor de cópia da
engine compartilha extensões; usá-lo diretamente fazia o espelho alterar o
tempo de contato do original. O carregador usa instâncias independentes.
O membro de contato é anotado explicitamente, para evitar confundir o pé de
apoio com aquele que realiza a batida.

A transição guarda a pose real anterior, mistura os segmentos com comprimento
fixo e usa o mesmo resultado nos contatos e na imagem. O apoio dos pés e os
limites dos braços continuam ativos. A passagem para uma ação nativa recebe
o mesmo tratamento; não depende de dois suavizadores divergentes.

O peito é uma camada de tronco e braços sobre a locomoção nativa. O início é
agendado pela previsão da bola, enquanto as pernas continuam disponíveis.
A próxima ação de corpo inteiro libera essa camada com uma transição de
pose. Passes/chutes explícitos e reações de contato podem interrompê-la.
Recepções novas não substituem a condução de uma bola rasteira já dominada.

Os marcadores são **anotações para o Football**, sem recuperar o tempo de
contato original do PES. A anotação só prepara a ação: o toque precisa passar
pelo teste real da superfície ponderada do modelo. A previsão usa a mesma
física e o mesmo gramado do jogo. O marcador não prende nem teletransporta a
bola para o pé.

## Seleção aprendida, viradas e fluidez

A seleção dos novos candidatos usa uma métrica de 50 dimensões treinada em
147.676 amostras do acervo adaptado. Ela compara posições e velocidades de
cinco pontos do corpo, trajetória futura, orientação e apoio dos pés.
O teste de continuidades de 20–80 ms, sob ruído de pose de 1 cm, obteve
96,7% de acertos em famílias separadas do treinamento. As condições reais de
bola, pressão adversária e limites do campo também participam da ordenação.
O modelo aprende custos de seleção; a física, o alcance e as regras continuam
sendo verificados pelo Football.

A busca geométrica recebe até 24 alternativas PES por comando, além das
reservas nativas. Cenas de espera e goleiro não entram pelo mecanismo de
reserva de locomoção. Goleiros usam os contextos de goleiro da partida; o
personagem do treino solo usa os contextos de jogador de linha. Capturas
longas de espera continuam respondendo a mudanças de comando quando a bola
está distante, mantendo a passada quando o comando permanece igual.

Na recepção superior, a separação entre peito e pelve tem limites de rotação.
Quando a pelve abandona o eixo de chegada, a camada é liberada em 120 ms.
A imagem usa o mesmo limite; o tronco deixa de compensar uma virada completa
girando para trás da cintura.

O formato FBAN2 guarda exatamente os valores float32 das chaves convertidas e
os metadados de contato. A organização preditiva dos bytes reduz o tamanho do
ZIP sem retirar quadros nem reduzir a precisão usada pela engine.
O leitor também aceita as animações em texto, inclusive linhas longas:
o limite antigo de 32 KB foi removido e metadados ausentes geram erro explícito.

## Validação e limites

Os testes das poses verificam todos os clipes: chaves temporais, quaternions,
comprimento dos ossos e apoio geométrico das chuteiras. Os testes renderizados
com controle Xbox virtual verificam seleção, contato, resposta ao comando,
transições, câmera e comparação com o banco clássico. Contatos PES e ações
nativas de reserva são registrados separadamente.

As métricas renderizadas registram os 13 segmentos. Seus intervalos de
continuidade distinguem os clipes completos da camada de tronco; as transições
para o banco nativo são incluídas. As pernas nativas durante a recepção
superior são conferidas quanto à independência da camada; as velocidades
angulares do banco nativo também ficam registradas como diagnóstico.

As poses do banco inteiro são conferidas quanto a chaves, normalização,
continuidade, comprimentos e apoio. Os relatórios da entrega registram as
verificações gráficas e as fontes que realmente produziram contato; a presença
de um clipe no catálogo não é contada como prova de contato em jogo.

A cobertura conjunta das duas câmeras exige as cinco famílias de ações e um
contato real de passe e chute PES em corrida. Uma tentativa individual pode usar a
reserva nativa quando a fase da passada não permite o clipe novo; isso fica
registrado, em vez de forçar um toque fora do alcance.

A validação gráfica é Linux/X11. A compilação Windows é conferida como pacote,
incluindo executável, dependências e integridade, sem execução gráfica do
Windows neste ambiente. Consulte `animation-gameplay-validation.json` e o
relatório `pes2017-action-bank-validation.json` para os cenários e fontes
efetivamente exercitados.

`pes2017-match-validation.json` registra os testes adicionais na partida:
recepções centrais e altas do jogador e da CPU, chegadas ao goleiro, reinícios
de bolas paradas e dois tempos com 22 jogadores. O teste autônomo verifica
também a relação entre o tempo simulado e o tempo real. Isso não equivale a
exercitar cada movimento do banco em todas as situações de uma partida.
A automação só fornece comando para cobrar as bolas paradas atribuídas ao
jogador humano; não pede passes nem resgata posses da CPU durante a partida.

A cadência de 30 FPS e a escala angular do leitor ainda precisam de comparação
com o PES executando. Não foi recuperado seu seletor original nem sua física.
Esta entrega integra movimentos a uma gameplay híbrida. Dos 2.956 arquivos,
591 permanecem sem nome/contexto identificado, 470 exigem contextos ou
sequências ainda não mapeados, 60 não passaram na conversão e dois dependem
de um solucionador auxiliar. Esses 1.123 arquivos ficam fora do banco ativo.
As animações nativas cobrem as reservas e os contextos ainda ausentes.
Cada transição possível e o contato de todos os 1.833 clipes não estão
comprovados. O corpo continua sem ragdoll.

Para reproduzir com os dados locais já decodificados:

```bash
python3 tools/animations/build_pes_complete_bank.py \
  --decoded /caminho/decoded-verified --output /tmp/pes17-bank
python3 tests/run_pes_release_suite.py --build build --output /tmp/pes17-release
python3 tests/run_pes_match_suite.py --build build --output /tmp/pes17-match
```

Os arquivos CPK, MTAR, ASK e FRIG originais e a biblioteca decodificada completa
continuam privados. O pacote inclui apenas as adaptações selecionadas e seus
metadados; os direitos dos movimentos de origem são preservados em `NOTICE`.
