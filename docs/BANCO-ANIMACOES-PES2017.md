# Banco de ações PES 2017

Abra `treinar-animacoes-pes.bat`, depois de extrair o ZIP completo em uma
pasta nova. **Insert** compara com o banco original. **R3/Tab** alterna a
câmera; **R** reinicia a tentativa. Nenhuma pasta PES de outra versão precisa
ser copiada.

O banco contém **21 clipes de origem** convertidos para o modelo do Football.
Eles geram **37 candidatos**: esse total inclui espelhos e a disponibilização
de recepções nos dois estados nativos de controle da bola. Essas cópias não
são contadas como novas capturas.

| Família | Clipes de origem | Aplicação |
| --- | ---: | --- |
| Passe | 5 | Chapa frontal, diagonal, lateral, passe forte e passe em corrida |
| Chute | 4 | Peito do pé, chapa, diagonal e corrida |
| Cruzamento | 3 | Frontal, diagonal e corrida |
| Cabeceio | 3 | Inclinação para bola baixa, salto e bola mais alta |
| Recepção | 6 | Pé, peito do pé elevado, coxa, barriga, peito e cabeça |

O catálogo reproduzível está em
`data/media/training/pes17/catalog.json`; cada clipe tem sua proveniência ao
lado. As condições e anotações estão em `config/pes2017-action-recipes.json`.
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
as alternativas nativas. A condução, a caminhada, a corrida e as demais ações
aprovadas continuam com o Football. `treino-classico.bat` e
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

## Validação e limites

Os testes das poses verificam todos os clipes: chaves temporais, quaternions,
comprimento dos ossos e apoio geométrico das chuteiras. Os testes renderizados
com controle Xbox virtual verificam seleção, contato, resposta ao comando,
transições, câmera e comparação com o banco clássico. Contatos PES e ações
nativas de reserva são registrados separadamente.

As métricas renderizadas registram a coluna e as pernas. Seus intervalos de
continuidade distinguem os clipes completos da camada de tronco; as transições
para o banco nativo são incluídas. As pernas nativas durante a recepção
superior são conferidas quanto à independência da camada; as velocidades
angulares do banco nativo também ficam registradas como diagnóstico.

A bateria final passou em **179 verificações do banco nas duas câmeras** e
**102 verificações da gameplay nativa**, além de 14 suítes CTest e 250 testes
Python (244 aprovados e seis ignorados). Os 21 clipes tiveram suas poses
conferidas; **11 fontes distintas** produziram contatos PES reais nessa bateria,
cobrindo as cinco famílias e o chute em corrida. As demais fontes disponíveis
ainda não têm contato em jogo demonstrado por esses cenários.

A cobertura conjunta das duas câmeras exige as cinco famílias de ações e um
contato real do chute PES em corrida. Uma tentativa individual pode usar a
reserva nativa quando a fase da passada não permite o clipe novo; isso fica
registrado, em vez de forçar um toque fora do alcance.

A validação gráfica é Linux/X11. A compilação Windows é conferida como pacote,
incluindo executável, dependências e integridade, sem execução gráfica do
Windows neste ambiente. Consulte `animation-gameplay-validation.json` e o
relatório `pes2017-action-bank-validation.json` para os cenários e fontes
efetivamente exercitados.

A cadência de 30 FPS e a escala angular do leitor ainda precisam de comparação
com o PES executando. Não foi recuperado seu seletor original nem sua física.
Esta entrega integra movimentos a uma gameplay híbrida; não instala todo o
acervo de 2.956 clipes e não comprova toda combinação possível de transições.
Goleiros, defesas, carrinhos, quedas e várias jogadas menos comuns conservam as
animações nativas existentes. O corpo continua sem ragdoll.

Para reproduzir com os dados locais já decodificados:

```bash
python3 tools/animations/build_pes_action_bank.py \
  --decoded /caminho/decoded-verified --output /tmp/pes17-bank
python3 tests/run_pes_release_suite.py --build build --output /tmp/pes17-release
```

Os arquivos CPK, MTAR, ASK e FRIG originais e a biblioteca decodificada completa
continuam privados. O pacote inclui apenas as adaptações selecionadas e seus
metadados; os direitos dos movimentos de origem são preservados em `NOTICE`.
