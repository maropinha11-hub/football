# Treino por animações e IK

Extraia o ZIP completo em **uma pasta nova** e abra **treino-classico.bat**.
Para a partida de teste, abra **jogar-partida.bat**. Não substitua arquivos de
outra versão nem copie pastas PES para esta instalação.

Para testar o **novo passe curto PES**, abra **treinar-animacoes-pes.bat**.
Com o jogador parado, mirando para a frente e a bola no chão, toque **A**.
**Insert** alterna o passe novo e o original; **R** reinicia a tentativa e
**R3/Tab** mostra o corpo por fora. O teste acrescenta um passe de chapa com
o pé direito. Corridas, passes laterais, bolas altas e as demais ações continuam
usando o banco nativo. A condução aprovada não foi substituída.

Esta versão usa a movimentação nativa aprovada e a câmera em primeira pessoa.
O corpo recebe adaptações de equilíbrio, tronco e braços, e alcance de pernas
por IK com comprimento dos ossos preservado. O contato da bola continua sendo
verificado na superfície do modelo. O corpo e a roupa não executam ragdoll.

- Analógico esquerdo: movimentação gradual; RB: corrida.
- Analógico direito: olhar; R3/Tab: câmera externa para observar os movimentos.
- A: passe; X: cruzamento; Y: profundidade; B: chute; LB+B: cobertura.
- LT/L2: proteção com a bola e disputa sem a bola.
- R/View: reiniciar a tentativa; 1 a 6: exercícios.
- F4: passe rasteiro; F5: chegada média; F6: bola alta.
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

O passe foi adaptado do acervo PES 2017 enviado pelo usuário. O instante de
contato foi anotado para o Football e só produz toque quando o pé alcança a
superfície real da bola. A física e a escolha das demais jogadas continuam
sendo do Football. Isto não reproduz a gameplay exata do PES; nenhum clipe
PES 2021 foi instalado. Consulte `ANIMACOES-PES2017.md` nos fontes.

A validação nativa com controle Xbox virtual está registrada em
`animation-gameplay-validation.json`. O pacote Windows também é conferido
quanto a executável, dependências e integridade. A execução gráfica no Windows
do usuário ainda precisa ser confirmada.
