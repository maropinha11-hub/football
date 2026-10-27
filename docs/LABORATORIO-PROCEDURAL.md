# Comparação de controladores

Extraia o pacote completo em uma pasta nova e abra **laboratorio-procedural.bat**.
Use **R3/Tab** para olhar o corpo por fora. **F12** alterna:

1. **Base nativa fluida + resposta procedural**: mantém a passada, a trajetória
   e os contatos da gameplay nativa na mesma fase. Suaviza descontinuidades
   de pose; ações com contato preservam seu quadro de execução. O apoio é
   híbrido, com dez segmentos dinâmicos e quadril/chuteiras guiados.
2. **Corpo físico livre**: os treze segmentos, inclusive quadril e chuteiras,
   têm massa e dinâmica. Motores limitados atuam nas doze articulações, junto
   com as restrições e os contatos reais do Bullet. Nenhum pé nem quadril é
   preso; não há força artificial para sustentar o corpo no ar.
3. **Base aprovada**: retorna ao controlador anterior.

A entrada no corpo livre agora começa de uma postura com apoio, mesmo se a
troca ocorrer no meio de uma animação. Há um breve preparo antes de aceitar
movimento. A bola é afastada para observar o equilíbrio.

Segure **U** para uma pressão contínua; **Shift+U** e **Ctrl+U** aumentam.
**F8** aplica 15 N.s; **Shift+F8**, 30 N.s; **Ctrl+F8**, 60 N.s.
**F3** muda a direção. **F9** testa uma perda grande de equilíbrio.
**R** recoloca o personagem em pé, explicitamente. O corpo livre ainda não
aprendeu a se levantar de todas as quedas. **F2/F4/F5/F6** mantêm os ensaios
de bola; suas ações ainda não constituem habilidades físicas aprendidas.

O apoio usa solas com área finita, reação do solo e correção articular pelo
centro de massa e sua velocidade. Quando perde sustentação, o controlador
troca a tentativa rígida de manter a postura por proteção muscular da queda.
As posições mostradas e os contatos com a bola usam a pose física resultante.
A busca experimental em quadros internos deixou de substituir a referência
do corpo livre, pois não demonstrou equilíbrio físico ao caminhar.

## Limites deste experimento

A caminhada física livre **continua sem aprovação** e ainda pode causar queda.
Não é uma gameplay completamente procedural pronta. A comparação está
disponível apenas no treino solo; **partida-fisica.bat** continua com o
controlador anterior para os 22 atores.

Foram executadas três campanhas PPO, somando 5.496.832 decisões no corpo
Bullet, com 148 observações e 20 canais de ação. Manter a postura não bastou:
o avanço na direção pedida e a troca real de apoio ficaram insuficientes.
Os candidatos **não foram instalados**. O executável usa controle articular e
feedback procedural, sem uma nova política neural de corpo inteiro aprovada.
Os modelos reduzidos antigos permanecem no controlador híbrido.

Para jogar com a base aprovada, use **treino-fisico.bat** ou
**partida-fisica.bat**. O corpo livre permanece um teste de pesquisa; ainda não
é Euphoria nem o objetivo completo de futebol aprendido e procedural.

Pesquisa, resultados e reprodução dos treinamentos:
[PESQUISA-CONTROLE-PROCEDURAL.md](PESQUISA-CONTROLE-PROCEDURAL.md).
