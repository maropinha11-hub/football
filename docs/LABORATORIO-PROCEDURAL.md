# Comparação de controladores

Extraia o pacote completo em uma pasta nova e abra **laboratorio-procedural.bat**.
Use **R3/Tab** para olhar o corpo por fora. **F12** alterna:

1. **Referência procedural**: gera a passada e a postura pela geometria das
   pernas. A sustentação continua híbrida; ações de futebol preservam os
   movimentos nativos e seus eventos de contato.
2. **Corpo físico livre**: os treze segmentos, inclusive quadril e chuteiras,
   têm massa e dinâmica. Motores limitados atuam nas doze articulações, junto
   com as restrições e os contatos reais do Bullet. Nenhum pé nem quadril é
   preso; não há força artificial para sustentar o corpo no ar.
3. **Base aprovada**: retorna ao controlador anterior.

Ao entrar no corpo livre, a bola é afastada para observar o equilíbrio.
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

Ao pedir movimento no corpo livre, a referência pode vir de quadros internos
do banco nativo. A busca considera pose, velocidades medidas, trajetória
futura e fase de apoio, com continuidade entre referências. Essa busca é de
**locomoção**: passes e chutes continuam entrando pelos eventos nativos.

## Limites deste experimento

O modo físico livre é um laboratório separado, ainda sem uma política robusta
de caminhada, corrida, futebol e recuperação do chão. Pode perder equilíbrio
ao tentar se mover. A comparação está disponível apenas no treino solo;
**partida-fisica.bat** continua com o controlador anterior para os 22 atores.

No ensaio gráfico de caminhada desta etapa, avançou cerca de 0,70 m, mas
perdeu equilíbrio; permaneceu ereto em somente 22,5% das amostras desse trecho.
Passar nas verificações de montagem, comandos e contatos não aprova essa
caminhada. O corpo livre não deve substituir a versão jogável aprovada.

Foram executados treinamentos por recompensa no corpo Bullet. Os candidatos
não passaram pelo critério de generalização e **não foram instalados**.
O corpo livre entregue usa controle articular e feedback procedural, sem
uma política neural nova aprovada. Os modelos reduzidos antigos permanecem
no controlador híbrido. Este pacote não é Euphoria e não é a gameplay
completamente procedural e aprendida que é o objetivo do projeto.

Pesquisa e proposta para o controlador completo:
[PESQUISA-CONTROLE-PROCEDURAL.md](PESQUISA-CONTROLE-PROCEDURAL.md).
