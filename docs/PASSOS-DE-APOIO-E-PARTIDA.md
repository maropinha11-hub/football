# Passos de apoio e física na partida

Extraia o pacote completo em uma pasta nova, entre na pasta extraída e abra
`treino-fisico.bat` ou `partida-fisica.bat`. R3/Tab alterna a câmera para
observar o corpo. Os atalhos `run-training.bat` e `jogar-partida.bat` preservam
a versão aprovada sem a camada experimental.

| Comando | Teste |
| --- | --- |
| F8 / Shift+F8 | Impacto médio / forte, com reação de apoio |
| F3 | Alternar a direção do próximo impacto |
| Ctrl+F8 | Sobrecarga: tentativa de apoio, seguida de queda se necessário |
| F9 | Forçar uma queda para observar músculos e recuperação |
| F7 | Comparar a camada física ligada/desligada |
| F10, no treino | Parceiro ao lado, pressionando ou retirado |
| LT/L2 | Proteger com bola; tentar segurar o adversário sem bola |
| H / N / M | Tentar agarrar / proteger / disputar pelo teclado |
| F2, na partida | Aproximar um adversário para um ensaio de contato |
| F11, na partida | Colocar a bola no adversário próximo para ensaiar LT |
| R / View | Reiniciar |

F2 e F11 são montagens explícitas do laboratório. O adversário continua
tomando suas decisões normais; aproximá-lo não garante agarramento nem
concede a bola ao jogador. A mão precisa realmente alcançar a camisa, e o
contato se desfaz se o alcance for perdido. Fora desses comandos de teste,
as posições e decisões continuam sendo da partida original.

O antigo pedido de passo elevava artificialmente a velocidade até o limiar
de caminhada. Isso gerava a caminhada comum observada no F8. Agora o impacto
solicita um movimento nativo de desequilíbrio de corpo inteiro. A busca por
pose mantém a direção do impacto como prioridade, para não trocar um passo
lateral por uma proteção frontal apenas por semelhança com a pose parada.
Os movimentos incluem proteção frontal, lateral e traseira e desaceleração,
com versões de entrada parada, andando e correndo, incluindo espelhamentos.

O parceiro do treino toca esses movimentos sem consultar a IA de uma equipe
completa. Na partida, cada um dos 22 jogadores pode receber impulsos, reagir,
cair e levantar. Jogadores da CPU longe de uma disputa mantêm a animação
nativa sem integrar uma simulação Bullet de acompanhamento desnecessária.
O jogador fixo, a formação, o nível máximo e as decisões de bola são mantidos.

Durante a queda, motores PD limitados preservam flexão de cotovelos e joelhos
e direcionam os braços para amortecer o contato. Os torques nos dois lados
de cada articulação são opostos. A tentativa de endireitar o quadril só pode
trocar torque com pés que ainda apresentam contato real com o chão. Não há
força vertical para suspender o jogador. Quando o apoio é perdido, gravidade
e colisões continuam agindo; a recuperação conserva as animações originais
de levantar de frente e de costas.

As fontes de pesquisa permanecem em
[anatomy-physics-research.json](anatomy-physics-research.json): controladores
PD do DeepMimic, ponto de captura do IHMC e limites articulares do Jolt.
Esta revisão reaproveita 18 fontes nativas contando os espelhamentos; não
acrescenta centenas de milhares de capturas, nem um controlador muscular
aprendido. O banco anterior de 288 variações é procedural. A seleção pode
variar as reações adequadas às situações sem transformar essas variações em
novas capturas de partidas reais.

Cada jogador possui seu corpo articulado e chão local. A interação entre
jogadores combina as colisões nativas com impulsos e tração; não é uma única
simulação de todos os corpos rígidos da partida. Os volumes de colisão são
aproximados e a camisa continua sendo uma casca limitada sobre a malha.

Os testes gráficos usam o jogo nativo Linux e um Xbox virtual. O executável
Windows é compilado para x64 e o ZIP é conferido com suas DLLs e recursos.
A execução gráfica no Windows e o controle físico precisam ser observados
no computador do jogador. Passaram 184 verificações renderizadas em 14
cenários, 59 verificações dos solucionadores, os seis testes CTest e 68
verificações do pacote. O relatório
[stagger-match-validation.json](stagger-match-validation.json) identifica
os executáveis, o arquivo ZIP e as correções das falhas intermediárias.

Capturas do teste real:
[passo lateral](images/stagger-support-step.png),
[queda com musculatura ativa](images/stagger-muscular-fall.png) e
[partida física](images/stagger-physical-match.png).
