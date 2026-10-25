# Quedas protegidas e postura

Extraia o pacote completo em uma pasta nova. Use **partida-fisica.bat** para
os dois times ou **treino-fisico.bat** para observar o jogador. R3/Tab muda
entre as câmeras. A condução e os comandos aprovados continuam como base.

Segure U para empurrar gradualmente; Shift+U aumenta a pressão e Ctrl+U testa
sobrecarga. F8 aplica um impacto isolado, Shift+F8 um impacto mais forte e
Ctrl+F8 uma sobrecarga. F3 alterna a direção. F9 é uma queda deliberada: serve
para examinar a proteção, não para medir a resistência normal a um empurrão.

Na partida, **Ctrl+Shift+F9** aplica a queda de laboratório aos 22 jogadores.
Esse é um ensaio extremo, não uma jogada normal. **Ctrl+Shift+F4**, no treino,
afasta a bola para observar a caminhada sem posse; use o analógico levemente.

## Mudanças físicas

O mundo físico de cada atleta permanece carregado quando ele para. Os músculos
continuam sendo calculados para a CPU quieta. Iniciar a queda e retornar à
atividade reutiliza os corpos e as restrições existentes. A passagem para a
queda conserva a velocidade dos membros e não eleva o corpo para recriá-lo.
Reiniciar uma situação explicitamente ainda limpa os estados antigos.

A proteção usa tempo estimado até o chão, velocidade, inclinação e contatos
reais. Ombros e cotovelos procuram alvos de apoio no solo, com limites
anatômicos e velocidade angular limitada. A cabeça recolhe e as pernas
ajustam a flexão. Os músculos trocam torques internos e permanecem ativos:
não se aplica uma força artificial para sustentar o quadril no ar.

Enquanto há apoio real dos pés, o corpo pode aplicar correção postural com
reação oposta nos tornozelos. Ao atingir o solo com o tronco ou quadril, a
força diminui para absorver e acomodar o impacto. Manter os mesmos torques
altos depois dessa colisão provocava giros extras. Uma queda comum que
recupere apoio, altura e estabilidade pode encerrar sem uma animação de
levantar deitado; o teste deliberado F9 mantém sua sequência completa.

A caminhada livre e a condução lenta derivada usam altura do quadril calculada
pelo alcance das pernas, em vez de uma redução fixa de oito centímetros.
A relação entre ciclo, distância e duração do apoio também foi corrigida;
o evento de contato acompanha a mesma fase de avanço da chuteira.
Isso reduz a cadência excessiva sem desacelerar a simulação. A oscilação
vertical da condução lenta ficou limitada pela geometria da passada.
Isso permite estender a perna de apoio sem esticar os ossos. As referências
originais e o contato da chuteira continuam sendo avaliados na mesma pose.

## Desempenho e limites

O passo de simulação continua em 10 ms. A revisão elimina recriações de
corpos na pausa/movimento e na entrada/saída da queda. Uma lentidão detectada
em jogo deixa uma linha **Performance::SimulationHitch** no arquivo log.txt,
com ritmo de simulação, custo da lógica e espera pelo estado de renderização.
Esse registro ajuda a investigar problemas que dependam do PC ou da partida.

Este continua sendo um controlador híbrido. A movimentação e as ações de
futebol usam o banco nativo; no acompanhamento ativo, o quadril e os alvos das
chuteiras seguem a trajetória comandada e dez segmentos têm dinâmica. Durante
a queda, os treze segmentos são dinâmicos. A recuperação do chão ainda combina
as animações nativas de levantar com alinhamento de apoio.

O modelo muscular neural e o planejador reduzido de equilíbrio existentes
continuam em uso. Esta revisão não treinou uma política de corpo inteiro por
reforço e não criou novas capturas. Os alvos de proteção e de passada são
procedurais; isso não torna toda a gameplay procedural nem a transforma na
tecnologia proprietária Euphoria.

Referências de controle e limitações da pesquisa anterior:
[fluid-reception-research.json](fluid-reception-research.json) e
[active-body-research.json](active-body-research.json).
