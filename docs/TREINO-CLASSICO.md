# Treino por animações e IK

Extraia o ZIP completo em **uma pasta nova** e abra **treino-classico.bat**.
Para a partida de teste, abra **jogar-partida.bat**. Não substitua arquivos de
outra versão nem copie pastas PES para esta instalação.

Para testar o **banco de animações PES**, abra **treinar-animacoes-pes.bat**.
Para usá-lo na partida com CPU, abra **partida-animacoes-pes.bat**.
**Insert** alterna o banco novo e o original; **R** reinicia a tentativa e
**R3/Tab** mostra o corpo por fora. Há 1.833 clipes adaptados para passes, chutes,
cruzamentos, cabeceios, recepções, conduções, defesas e recuperações, além dos movimentos nativos que continuam
disponíveis. O seletor usa a trajetória e o alcance real para decidir a jogada.
O treino clássico mantém o banco nativo; a opção PES também usa as novas
conduções e locomoções quando o contexto permite.

O treino clássico usa a movimentação nativa aprovada e a câmera em primeira pessoa.
O corpo recebe adaptações de equilíbrio, tronco e braços, e alcance de pernas
por IK com comprimento dos ossos preservado. O contato da bola continua sendo
verificado na superfície do modelo. O corpo e a roupa não executam ragdoll.

- Analógico esquerdo: movimentação gradual; RB: corrida.
- Analógico direito: olhar; R3/Tab: câmera externa para observar os movimentos.
- A: passe; X: cruzamento; Y: profundidade; B: chute; LB+B: cobertura.
- LT/L2: proteção com a bola e disputa sem a bola.
- R/View: reiniciar a tentativa; 1 a 6: exercícios.
- F4: passe rasteiro; F5: chegada média; F6: bola alta.
- Home/End: aumentar/diminuir a altura de F5/F6; Delete: voltar à altura automática.
- Z+F4: passe central entre os pés; 7/8/9 + F5: canela/coxa/descendente.
- Shift+F6: bola para salto. Na partida, H acrescenta o teste no companheiro CPU.
- F8: reação a impacto; F9: reação animada forte. F12 não ativa corpo livre.

O gramado usa a mesma superfície irregular na simulação e na previsão da bola.
O quique padrão foi ajustado para 0,74; a resposta ao solo dissipa energia.
Não se promete que toda bola seja alcançável: o jogador precisa ter tempo e
alcance reais para o contato. O passe central agora recebe a mesma busca
antecipada de contato usada nas bolas altas, inclusive para a CPU.
Se a canela/coxa tocar primeiro durante uma recepção preparada, esse contato
real pode concluir o domínio. A bola é amortecida nessa ação e o jogador
continua a jogada, em vez de ficar esperando um toque posterior do pé.

Os movimentos foram adaptados do acervo PES 2017 enviado pelo usuário. Uma
métrica treinada compara pose, velocidades, trajetória e apoio; o seletor
também considera a bola prevista e a pressão adversária. Os instantes de
contato foram anotados ou estimados para o Football: o marcador não aplica
força sozinho, pois o corpo precisa alcançar a bola na simulação. O domínio
de peito usa a camada de tronco e braços sobre as pernas nativas. A entrada e
a saída das ações PES compartilham a pose entre simulação e imagem. Ao virar
durante a recepção, o tronco tem sua torção limitada e libera a camada superior
suavemente, mantendo a liberdade das pernas.

A física e o seletor continuam sendo do Football. Isto é uma integração
híbrida. Há 1.123 arquivos sem contexto identificado, sem sequência mapeada
ou ainda reprovados na adaptação; eles ficam fora do banco ativo de 1.833.
Nenhum clipe PES 2021 foi instalado. `treino-classico.bat` e
`jogar-partida.bat` continuam começando com o banco original. Os atalhos
`treinar-animacoes-pes.bat` e `partida-animacoes-pes.bat` habilitam o novo banco.
A validação inclui treino nas duas câmeras, recepções da CPU, goleiros,
reinícios de bolas paradas e uma partida autônoma.

A validação nativa com controle Xbox virtual está registrada em
`animation-gameplay-validation.json`. O pacote Windows também é conferido
quanto a executável, dependências e integridade. A execução gráfica no Windows
do usuário ainda precisa ser confirmada.
