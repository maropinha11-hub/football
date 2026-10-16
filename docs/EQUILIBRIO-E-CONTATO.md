# Equilíbrio e contato: revisão do laboratório

Revisão posterior: [braços, ações de primeira e impactos graduais](BRACOS-E-JOGADAS-DE-PRIMEIRA.md).
Os números abaixo documentam esta revisão anterior.

Extraia o ZIP Windows completo em uma **pasta nova** e execute
**treino-fisico.bat**. R3/Tab alterna a câmera. O treino aprovado permanece em
`run-training.bat`.

| Comando | Ação |
| --- | --- |
| LT/L2 com a bola | Proteger o corpo e buscar apoio com o braço |
| LT/L2 sem a bola | Alcançar e tentar segurar a camisa do parceiro |
| Soltar LT/L2 | Largar; é necessário soltar para tentar novamente após uma fuga |
| H / N | Atalhos de teclado para agarramento / proteção |
| F10 | Parceiro ao lado → pressão → parceiro fora |
| F11 | Alternar bola no parceiro / no jogador para testar os dois usos de LT |
| F8 | Empurrão recuperável |
| F9 | Iniciar deliberadamente uma queda, para testar ragdoll e levantar |
| F7 | Comparar a camada física ligada/desligada |
| M | Disputa corporal próxima |
| R/View | Reiniciar o exercício |

Quando a posse volta ao jogador, LT retorna à proteção mesmo se continuar
apertado. L3 deixou de acionar o agarramento. RB continua sendo corrida. F4/F5/F6
continuam lançando bolas de treino. Os novos vínculos de camisa são um
experimento com o parceiro do laboratório; a partida conserva as disputas
nativas.

## Recuperar o apoio antes de cair

O limite que derrubava imediatamente o jogador a partir de um impulso fixo
foi removido dos contatos normais. Um controlador reduzido calcula o ponto
de captura da **perturbação externa**, separadamente da velocidade de corrida
já planejada pela animação. Compara esse ponto com a base de apoio dos pés e
uma margem de passo. Reações de tronco/braços e um comando de passo corretivo
entram antes da queda. Um desequilíbrio que continue além dessa margem pode
vencer a recuperação e então liberar o corpo articulado.

Os parâmetros de jogo incluem massa de referência de 84 kg, limite de passo
corretivo de 1,15 m/s e uma janela de falha de aproximadamente 0,28 s.
Proteção preparada aumenta a margem; uma camisa presa limita a liberdade do
passo. Esses valores são ajustes do protótipo, **não medidas de um atleta**.
O acompanhamento cinemático também foi dividido corretamente nos dois
meios passos do Bullet: a raiz não informa mais velocidade dobrada no primeiro
e zero no segundo. Um teste específico mede o erro articular em translação
a 7 m/s.
F9 continua sendo uma queda deliberada e não mede a dificuldade de derrubar
um jogador em uma disputa normal.

A locomoção usa raiz e pernas animadas, com correção do comando nativo.
Tronco e braços recebem acompanhamento físico e aditivos. Uma jogada aérea enfileirada com o jogador parado mantém a espera no eixo
da recepção, para que uma marcha provisória não afaste o corpo da janela
da cabeçada. Os testes incluem comando imediato e após 100 e 180 ms.
As quedas usam os
13 corpos articulados do Bullet; levantar continua usando as animações
nativas completas, com alinhamento da superfície ao chão. Isso ainda não é
um controlador muscular treinado que resolva equilíbrio em qualquer situação.

## Busca de reações e referência real

O banco de reações reutiliza os clipes nativos de desequilíbrio recuperável,
incluindo suas versões espelhadas. Cada entrada gera 16 variações:
quatro intensidades, duas cadências e duas pequenas inclinações laterais.
A busca compara direção e lado do impacto, velocidade efetiva da cadência
e pose de entrada. A sequência
selecionada entra gradualmente como aditivo de tronco e braços, sem deslocar
os pés até uma bola nem substituir a validação de contato da gameplay.

Foram carregadas **288 referências a partir de 18 fontes, incluindo as
espelhadas**. São variações procedurais de fontes existentes, e não centenas
de novas performances filmadas. A quantidade realmente carregada é registrada em
`PHYSICAL_BALANCE_BANK`, junto da quantidade de fontes, e na validação desta
versão.

Foram digitizadas visualmente oito poses 2D da demonstração CC0 SoccerKicks:
aproximação, apoio, preparação, abertura dos braços, seguimento do chute e
recomposição. O [painel anotado](images/balance-kick-reference.jpg) e as
[coordenadas com proveniência](research/soccerkicks-keyposes.json) permitem
revisar o estudo. A perspectiva impede tratar esses ângulos projetados como
ângulos articulares 3D. A tolerância de marcação é explicitamente aproximada.

O modelo aberto MediaPipe/OpenCV foi investigado para captura automática,
mas ambos os servidores consultados responderam HTTP 403 ao download dos
pesos. Portanto a inferência e a reconstrução automática 3D **não foram
executadas**. As referências, licenças, hashes, acessos e limitações estão em
[balance-physics-research.json](balance-physics-research.json). A obtenção e
revisão de mais sequências 3D continua necessária para um banco amplo de
jogadas reconstruídas de partidas reais.

## Braço, agarramento, roupa e câmera

A mão escolhe um braço ao iniciar o alcance, em vez de alternar de ombro a
cada quadro. O cotovelo dobra pelo seu eixo de flexão, em uma faixa de
aproximadamente 9 a 138 graus; velocidade e aceleração das articulações são
limitadas. Alvos atrás do tronco são restringidos. A separação final entre
antebraço e tronco continua após a mistura de poses. A mão precisa realmente
alcançar a superfície antes de iniciar um vínculo.

O vínculo conserva um ponto de camisa, aplica forças recíprocas limitadas a
260 N e permite ao parceiro dar passos para se desvencilhar. Distância,
alcance, queda, soltura ou fuga encerram o vínculo. Tração persistente pode
superar o apoio disponível; não existe um temporizador que decrete uma queda
só por segurar o botão. O parceiro é um ator de teste programado, sem uma
política aprendida de luta corporal ou dedos articulados.

A roupa é a mesma casca XPBD de baixa resolução do modelo existente. Seus
vértices agora acompanham o deslocamento da superfície em subpassos, e a
velocidade do tecido é calculada **em relação ao corpo**. A inércia é filtrada,
a resposta é amortecida e a superfície impede deslocamento para dentro.
Isso elimina a causa identificada de correções repetidas durante corrida;
não adiciona resolução, dobras detalhadas ou auto colisão geral ao tecido.

O olho acompanha o deslocamento local da cabeça no esqueleto interpolado.
O filtro adicional que atrasava a posição do olho foi retirado. Uma esfera
de câmera é afastada dos volumes de tronco/braço e verificada contra a
superfície deformada do tronco. A cabeça própria continua oculta. Os volumes
aproximados melhoram a visão interna, mas não garantem ausência de qualquer
interseção entre triângulos em toda pose possível.

A execução gráfica é validada em Linux com controle Xbox virtual. A versão
Windows é compilada e verificada quanto a executável, DLLs, recursos e ZIP;
um teste gráfico no seu Windows e com seu controle físico continua sendo
necessário.

## Validação desta versão

Passaram 142 verificações renderizadas em dez cenários com o mesmo
executável, 51 verificações dos solucionadores, seis testes CTest e 113
verificações do pacote. O [relatório com hashes e falhas corrigidas](balance-physics-validation.json)
e o [gráfico das medições](images/balance-physics-validation.png) registram os resultados.

Para repetir: ative `scripts/native-env.sh`, execute
`ctest --test-dir build --output-on-failure` e
`python3 tests/run_physical_validation.py --build build --output /tmp/football-balance-retest`.
A pasta de saída deve ser nova; os testes gráficos precisam de X11 virtual.
