# Laboratório de contato corporal

Esta página registra a primeira revisão. Para os controles e o comportamento
atuais, consulte [Equilíbrio e contato](EQUILIBRIO-E-CONTATO.md).

Extraia o pacote Windows completo em uma **pasta nova** e abra
**treino-fisico.bat**. Use **R3/Tab** para observar o corpo por fora.
O treino normal continua em `run-training.bat`.

| Comando | Teste |
| --- | --- |
| F7 | Comparar camada física ligada/desligada |
| F8 | Empurrão recuperável, com reação de tronco e braços |
| F9 | Queda articulada e recuperação no chão |
| F10 | Parceiro ao lado → parceiro se aproximando → parceiro fora |
| Segurar H ou L3 | Alcançar e segurar a camisa do parceiro próximo |
| Soltar H/L3 | Largar a camisa |
| Segurar N ou LT | Apoiar o braço na região da camisa e proteger o corpo |
| M | Disputa corporal de teste, somente em alcance de contato |
| R/View | Reiniciar o exercício e limpar forças, quedas e agarramento |
| F4/F5/F6 | Passe rasteiro, bola para o peito e bola alta |

RB continua sendo corrida; analógico direito continua controlando a cabeça.
Os comandos de contato com o parceiro pertencem ao treino experimental.
Na partida, os adversários continuam usando a IA e as disputas nativas.

## Recuperação e equilíbrio

A recuperação anterior misturava a pose caída com uma pose em pé durante dois
segundos. Agora a orientação do corpo escolhe uma das animações nativas
`000_stand_up_from_front.anim` e `000_stand_up_from_back.anim`. A sequência é
alinhada ao corpo caído, entra gradualmente, reproduz a faixa completa e só
devolve o controle ao terminar. A altura é corrigida pela superfície da malha
deformada, para que a subida conserve apoio no chão. Isso é uma recuperação
animada com ajuste de apoio, não um controlador muscular aprendido.

Impactos pequenos provocam uma reação amortecida; os braços ajudam a
contrabalançar o tronco. A proteção aumenta a tolerância a um impacto antes
da queda. Durante a queda, há uma resposta limitada dos ombros para buscar
apoio, além da gravidade, das articulações e das colisões do Bullet. O corpo
continua firme durante a locomoção: a raiz e as pernas seguem a animação
nativa, enquanto tronco e braços recebem os ajustes físicos.

Um chute ou cruzamento em corrida, com mudança grande de direção, perturba o
equilíbrio **depois de um contato aceito com a bola**. Isso não acrescenta um
chute à distância nem sorteia quedas. Um contato corporal forte pode derrubar
o jogador. A preferência de passe para trás solicita a virada do corpo antes
de liberar o passe; há um limite de espera para não prender o comando.

## Mãos, roupa e contato

O alvo da mão é um ponto da superfície ponderada da camisa, voltado ao outro
jogador. O alcance usa os comprimentos reais dos dois segmentos do braço,
entra gradualmente e não estica os ossos. A restrição de puxão só começa
quando a extremidade do antebraço está a menos de 10 cm dessa superfície.
Essa distância inclui a aproximação da mão, que não tem dedos articulados
separadamente neste modelo. Distância excessiva, queda, reinício ou soltura
do botão liberam o vínculo.

A força do vínculo tem limite de 150 N, gera reações iguais e opostas e é
integrada em passos de 10 ms. O contato horizontal entre os dois jogadores
usa cápsulas, separação limitada e impulsos recíprocos. O comando M serve
para testar desequilíbrio corporal; não atribui posse nem move a bola por
decreto. Roubo de bola e carrinho na partida continuam sendo os nativos.

A camisa usa uma **casca XPBD sobre os vértices existentes do tronco**:
costuras coincidentes são unidas, as bordas permanecem presas, as arestas
resistem a deformação e as normais acompanham a superfície. O puxão de jogo
também deforma essa casca. O deslocamento é limitado a 4,5 cm normalmente e
12 cm durante um puxão. A superfície animada impede deslocamento para dentro
do corpo. O modelo atual tem poucos vértices nessa região: não há aqui tecido
de alta resolução, rasgos, dobra detalhada de manga ou auto colisão geral de
tecido. A resposta visual do material usa parâmetros de jogo, sem calibração
experimental do tecido.

O antebraço deixou de ignorar colisões com o tronco no Bullet. Uma projeção
adicional afasta a pose final dos braços de um volume elíptico do tronco,
depois da mistura de animação e física. Isso melhora os cruzamentos relatados,
mas cápsulas e volumes de proteção não constituem uma garantia de ausência
de interseções entre todos os triângulos, roupas, jogadores e cenário.

## Referências e alcance da pesquisa

- [Bullet 3.25](https://github.com/bulletphysics/bullet3/tree/2c204c49e56ed15ec5fcfa71d199ab6d6570b3f5): corpos rígidos, inércia, contatos e restrições articulares; núcleo incorporado sob licença zlib.
- [XPBD, Macklin, Müller e Chentanez, 2016](https://github.com/matthias-research/pages/blob/master/publications/XPBD.pdf): complacência de restrições independente da quantidade de iterações.
- [Cloth, Ten Minute Physics](https://github.com/matthias-research/pages/blob/master/tenMinutePhysics/14-cloth.html): estudo da organização de arestas, vínculos e passos de tecido. A implementação C++ deste protótipo foi escrita para o modelo existente.
- As animações de queda, proteção e levantar já presentes no Football são a referência de poses. As duas sequências reais curtas de chute e as demais fontes examinadas anteriormente estão registradas em [physical-rig-v2-research.json](physical-rig-v2-research.json).

As variações são adaptações procedurais das animações existentes conforme
impacto, alcance e proximidade. Não foram reconstruídas centenas de novas
animações por rotoscopia de partidas, nem validada uma reprodução exata da
biomecânica de um jogador real. Os testes numéricos e visuais do laboratório
servem para avaliar este protótipo e preservar a condução aprovada.

A compilação Windows é verificada quanto a executável, DLLs, recursos e
integridade do pacote. A execução gráfica automatizada ocorre em Linux com
controle Xbox virtual; não substitui o teste no Windows com seu controle.

Esta entrega passou em 126 verificações renderizadas, 39 verificações dos
solucionadores, seis testes CTest e 113 verificações de pacote. Os resultados,
hashes dos executáveis e falhas investigadas estão em
[contact-physics-validation.json](contact-physics-validation.json), com um
[gráfico da execução](images/contact-physics-validation.png).

Para reproduzir no ambiente de desenvolvimento, ative `scripts/native-env.sh`,
execute `ctest --test-dir build --output-on-failure` e
`python3 tests/run_physical_validation.py --build build --output /tmp/football-contact-retest`.
O último comando precisa de uma tela X11 virtual e deve receber uma pasta de
saída nova para preservar os registros de cada execução.
