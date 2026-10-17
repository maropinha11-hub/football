> Registro histórico da versão `296bce6`. Os gestos com RT foram removidos.
> Veja a versão atual em [Mira e corpo](MIRA-E-CORPO.md).

# Sola, ações laterais e respostas aéreas

Extraia o ZIP completo em uma pasta nova e abra `treino-fisico.bat`.
`partida-fisica.bat` mantém a mesma camada experimental na partida.
R3/Tab muda a câmera; F1 compara os perfis corporais e F7 compara a física.

| Entrada | Gesto de teste |
| --- | --- |
| RT, parado perto da bola | Passagem do pé direito sobre a bola |
| RT + esquerdo para os lados | Arrasto lateral de sola |
| RT + esquerdo para trás/frente | Puxada/rolagem de sola nessa direção |
| Soltar e pressionar RT novamente | Repetir ou escolher outro gesto |
| RB | Corrida nativa; encerra a preparação da sola |
| F4 / F5 / F6 | Passe rasteiro / chegada ao peito / bola aérea |
| F8 / Shift+F8 / Ctrl+F8 | Impactos médio / forte / sobrecarga |

Os gestos de sola começam com a bola baixa e próxima, em repouso ou baixa
velocidade. O apoio esquerdo permanece plantado. A perna direita usa a
geometria do esqueleto e um alvo com velocidade e aceleração limitadas,
enquanto tronco e braços contrabalançam o gesto. A passagem do pé não
transmite um impulso à bola. O arrasto exige contato medido na malha da
chuteira; não reposiciona a bola para fabricar o toque. A liberação retorna
o pé ao apoio antes de retomar a seleção normal de animações.

O banco passa a **1.000 perfis procedurais** sobre as fontes existentes.
Além de esforço, pressão, giro e alcance, há três padrões: compacto,
abertura lateral e contrapeso para bolas aéreas. Eles mudam os eixos do
tronco e a abertura dos braços, com preparação e seguimento diferentes.
O padrão aéreo é usado conforme a altura prevista da bola. As animações
nativas continuam decidindo o gesto principal: passe, chute, voleio,
controle ou cabeceio. Contatos de cabeça preservam cabeça e tronco;
variam os braços. Domínios de peito, defesas e lançamentos do goleiro
conservam as suas cadeias de contato.

Os perfis são respostas contínuas sobre animações existentes, não mil
capturas novas. O catálogo inclui 2.604 pares candidatos de fonte e perfil
contando os espelhamentos nativos. Essa auditoria de metadados não é uma
validação gráfica exaustiva de todos os pares.

A preparação dos passes laterais recruta mais inclinação, rotação e braços.
Os alvos respeitam velocidade angular de 2,1 rad/s, inclinação frontal de
até 0,36 rad, lateral de até 0,20 rad e torção adicional de até 0,48 rad.
As restrições anatômicas dos braços continuam sendo aplicadas depois da
mistura gráfica. O controle de equilíbrio pode contribuir moderadamente
durante ações de pé; o cabeceio continua preservando o ponto de contato.

Na condução rasteira, um toque de pé aceito pode acrescentar um pequeno
impulso vertical dependente da variação de velocidade. O valor padrão é
`training_control_hop = 0.82`, equivalente a alguns centímetros de voo
livre. Gravidade e integração continuam em tempo real. A bola não recebe
esse impulso durante a passagem do pé, a rolagem de sola, passes ou chutes.

O equilíbrio, o motion matching e o ragdoll continuam baseados nas fontes
nativas, Bullet e motores articulares limitados. A simulação usa volumes
aproximados e interação entre jogadores por colisões e impulsos nativos.
O controlador é guiado por animações e apoios; esta etapa não incorpora
uma política muscular aprendida nem a engine proprietária da Rockstar.

Os testes gráficos são executados no jogo nativo Linux com Xbox virtual.
O pacote Windows é compilado para x64 e verificado com suas DLLs e recursos;
a execução com controle físico é observada no computador do jogador.

Nesta revisão passaram **355 verificações gráficas em 19 cenários**,
88 verificações dos solucionadores, 14 testes do catálogo, sete testes CTest
e 73 verificações dos pacotes. Os três padrões corporais foram observados na
gameplay real. A comparação com a condução anterior mediu picos de centro da
bola de 0,1262 m e 0,1403 m, mantendo o alcance abaixo de 0,59 m.

Nos gestos de sola testados, a bola percorreu aproximadamente 11–13 cm,
com apoio esquerdo plantado. A passagem do pé sobre a bola não gerou toque.
Os testes também exigem a saída de passes com RT ainda pressionado e a
interrupção do gesto por um passe após o retorno seguro do pé.

O [relatório desta revisão](sole-action-validation.json) registra hashes,
medições, testes e os ajustes após falhas intermediárias. As capturas são
da execução do jogo: [passagem do pé](images/sole-stepover.png) e
[aproximação da sola](images/sole-roll-right.png).

```sh
python3 tools/animations/build_situational_catalog.py --check
python3 tests/test_situational_catalog.py
python3 tests/run_physical_validation.py --build build --output /tmp/football-validation
```
