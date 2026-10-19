# Continuidade dos movimentos e passes para trás

Extraia o ZIP completo em uma pasta nova. Abra **treino-fisico.bat**;
**partida-fisica.bat** usa o mesmo banco e as mesmas correções na partida.
RB corre; o analógico direito olha; R3/Tab troca a câmera. F12 compara a
camada de busca e continuidade. Os lançadores antigos continuam disponíveis.

## O que mudou

A conversão anterior acertava a direção dos segmentos, mas deixava a rotação
em torno do próprio osso indefinida. Isso torcia joelhos e cotovelos e podia
deformar o modelo. Os dez ciclos FBX agora resolvem também o plano de dobra
de cada membro. Perto da extensão completa, onde esse plano perde definição,
a conversão estabiliza a orientação. O apoio dos sapatos é recalculado após
a correção das emendas; o deslocamento horizontal de cada ciclo tem velocidade
constante, sem transformar a oscilação da pelve em aceleração do jogador.

A busca usa posições e velocidades da pose executada, incluindo a composição
física. Ela evita entradas no final de um clipe e conserva a fase quando
vence o ciclo que já estava tocando. A troca entre movimentos mistura duas
animações que avançam no tempo durante 140 ms, com entrada senoidal. Uma
transição interrompida parte da pose composta, sem voltar a uma pose antiga.
O deslocamento comandado e os eventos de contato continuam na simulação.

As antigas restrições de reavaliação dependiam da proximidade da bola e
pressupunham clipes curtos. Em um ciclo longo, elas podiam adiar uma parada
ou uma mudança de direção. A locomoção física agora responde também longe
da bola, considerando mudanças de direção do corpo além da velocidade.
Cabeçadas já solicitadas continuam sendo avaliadas a cada passo fixo de 10 ms.

**Passe curto para trás:** um toque breve, de até 160 ms de carga registrada,
prefere o calcanhar quando o jogador está devagar e a bola está ao alcance
no chão. Ao carregar mais, ele vira o corpo e usa um passe normal. A ordem
de virar também chega ao controle de bola, que antes podia manter a direção
antiga. A bola continua exigindo contato com o pé; a correção não amplia a
tolerância nem acrescenta um impulso invisível. Na cabeçada disputada, o
tronco pode alcançar gradualmente um pouco mais, com os pés apoiados.

Passes, chutes e cruzamentos conservam a preparação e o acompanhamento
procedural do tronco e dos braços. A mistura de locomoção não salta a
preparação de uma ação nem desloca seu instante de contato.

## Material e limites

Foram estudadas as regras do pacote MxM para continuidade de ciclos e mistura
de animações em avanço. A implementação é nativa em C++; não executa o
runtime Unity. Os dez ciclos convertidos vêm dos quatro FBX recebidos;
os 37 clipes de curvas humanoides Unity continuam catalogados para conversão.
Isso não representa uma implementação idêntica de MxM ou Euphoria.

O [relatório no repositório](continuity-validation.json) registra 36 cenários
com 603 verificações gráficas, dez suítes CTest e 83 verificações do pacote
Windows. Os testes gráficos usam Linux com controle Xbox virtual; a execução
gráfica Windows e o controle físico ainda precisam ser conferidos no PC.

Uma primeira abertura de partida no Linux encerrou antes das verificações.
Não se repetiu na nova execução nem em seis ciclos seguidos de abertura e
fechamento com o mesmo executável. A causa dessa ocorrência isolada não foi
estabelecida; ela está registrada no relatório.
