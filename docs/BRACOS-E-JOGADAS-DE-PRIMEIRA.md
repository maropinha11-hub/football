# Revisão dos braços, ações de primeira e contato

Registro da revisão anterior. A caminhada comum após impactos foi substituída
pelas reações descritas em [Passos de apoio e física na partida](PASSOS-DE-APOIO-E-PARTIDA.md).

Extraia o ZIP Windows completo em uma **pasta nova**, entre em
`football-training-windows-x86_64` e abra **treino-fisico.bat**.

| Teste | Comando |
| --- | --- |
| Receber passe rasteiro | F4 |
| Receber bola na altura do peito | F5 |
| Receber bola alta | F6 |
| Passe / cruzamento / chute | A / B / X no controle Xbox |
| Impacto médio, 125 N·s | F8 |
| Impacto forte, 190 N·s | Shift + F8 |
| Sobrecarga, 350 N·s | Ctrl + F8 |
| Queda deliberada | F9 |
| Ativar parceiro / pressão / retirar parceiro | F10 |
| Alternar a posse para testar LT | F11 |
| Proteção com bola / tentativa de segurar sem bola | LT/L2 |
| Agarrar / proteger pelo teclado | H / N |
| Alternar câmera | R3 / Tab |
| Reiniciar | R / View |

Para testar a cabeçada, lance com F6 e peça passe ou chute antes de a bola
chegar. O comando fica preparado mesmo se você apertar repetidamente.
A seleção mantém a verificação da trajetória e do contato real com a cabeça;
uma bola fora do alcance pode passar. F9 é um teste deliberado de queda.
Ctrl+F8 aplica um impulso comum mais forte, permitindo observar primeiro a
tentativa de equilíbrio e depois uma queda caso ela falhe.

## Correções

O buffer anterior deixava de emitir a ação durante uma nova pressão do mesmo
botão. Isso abria intervalos justamente quando a bola entrava no alcance da
cabeça. Um pedido confirmado agora permanece confirmado até a execução,
cancelamento ou expiração do buffer. Passe curto e longo também podem buscar
as cabeçadas nativas de espera, assim como chute e cruzamento.
A busca aérea preparada passa a executar em cada passo fixo de 10 ms: a
agenda de 20–80 ms usada normalmente podia pular toda a faixa de altura de
uma cabeçada. O jogador pode ajustar a aproximação do corpo em até 18 cm,
distribuídos pela preparação nativa a até 0,45 m/s; a tolerância de contato
com a malha permanece a mesma.

O acompanhamento físico dos braços em pé recebe uma contribuição menor e
limitada, conservando a firmeza da animação. Ombros usam limites separados de
inclinação e rotação axial; cotovelos têm flexão em um sentido e uma pequena
tolerância lateral. O alcance da mão obedece a esses limites. A separação
analítica considera antebraços, parte dos braços, tronco, cabeça e coxas.
Essa projeção é repetida **depois da mistura gráfica**, pois a interpolação
podia reintroduzir uma pose inválida entre duas amostras corretas da física.

A tração da camisa também reduz a velocidade pretendida de quem tenta
escapar. As forças recíprocas continuam limitadas a 260 N. A postura de
proteção oferece resistência adicional apoiada no chão e recebe uma parte
menor da correção de sobreposição corporal. Ela não concede invulnerabilidade
a impactos arbitrários. O teste do parceiro permanece no laboratório; as
disputas nativas da partida continuam disponíveis.

O passo corretivo antes não aparecia em certas situações porque sua
velocidade solicitada ficava abaixo do limite que seleciona uma animação de
passo. Com o analógico neutro, uma demanda suficiente agora solicita
brevemente o passo nativo mais lento e freia ao recuperar o apoio. A correção
não desloca diretamente os pés ou teleporta a raiz.
O pedido dura até 0,52 s livre, 0,44 s em proteção e 0,20 s com a camisa
presa, permitindo concluir a transição de uma animação parada.

## Pesquisa e banco de movimentos

Foram estudados os limites de inclinação/torção do Jolt, os controladores PD
do DeepMimic, o controle de ponto de captura do IHMC e as referências visuais
SoccerKicks já registradas no projeto. As fontes, resultados de acesso,
hashes e a aplicação de cada referência estão em
[anatomy-physics-research.json](anatomy-physics-research.json).

O banco atual contém **288 variações procedurais de 18 fontes nativas,
incluindo espelhamentos**. A revisão preserva esse banco e seus créditos.
Não foram obtidas novas sequências 3D de partidas nesta revisão. O estudo
visual de oito poses 2D é uma referência, sem profundidade suficiente para
reconstruir sozinho um chute 3D. Centenas de milhares de animações capturadas
exigem um acervo correspondente, licenças e revisão do retargeting; variar
parâmetros do ragdoll não produz esse acervo.

O equilíbrio continua sendo um controlador reduzido de perturbações com
passos pela locomoção nativa, tronco e braços assistidos e quedas Bullet.
Não é um controlador muscular aprendido. As colisões corporais usam volumes
aproximados e não uma garantia de separação de todos os triângulos da malha.

## Verificação

Os testes reproduzem toques repetidos de passe e cabeçada, medem os limites
na pose gráfica final, observam a desaceleração durante o agarramento e
verificam a recuperação após impactos graduais. O relatório
[anatomy-physics-validation.json](anatomy-physics-validation.json) identifica
o executável e o ZIP efetivamente verificados.

Passaram **160 verificações renderizadas em 12 cenários**, 58 verificações
dos solucionadores, os seis testes CTest e 115 verificações do pacote. O
[painel das medições](images/anatomy-physics-validation.png) mostra os três
passos de apoio e a redução de velocidade durante a tração. O relatório
preserva também as falhas intermediárias e a correção da preparação do teste
de fuga: o tempo é contado a partir do agarramento real.

Os testes gráficos executam em Linux com controle Xbox virtual. O pacote
Windows é compilado e verificado quanto a executável, DLLs e recursos; o
teste com o controle físico continua sendo feito no seu computador.
