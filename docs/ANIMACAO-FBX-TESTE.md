# Condução antiga e ciclo novo no treino

Extraia o pacote completo em uma pasta nova e execute `run-training.bat`.
A câmera e os comandos Xbox em primeira pessoa continuam disponíveis.

| Situação | Animação |
| --- | --- |
| Saída parado | Condução original |
| Analógico leve | Condução original em cadência mais lenta |
| Analógico forte para frente, após a saída | Ciclo DefenseJog_LoopF |
| Virada, corrida com RB ou ação com a bola | Animação apropriada do seletor nativo |

O ciclo novo foi registrado como animações nativas complementares, para
os dois lados da passada e as velocidades de locomoção suportadas pelo motor.
A segunda metade continua a primeira, em vez de sobrepor uma pose velha
a cada toque. A mistura normal do motor faz a entrada e a saída.
As rotações dos ossos e seus comprimentos permanecem os da adaptação aprovada;
não há um pé sendo esticado rapidamente até a bola.

A entrada tem 400 ms de estabilização depois de atingir a faixa de movimento.
O analógico usa limites diferentes para entrar e permanecer no ciclo, evitando
alternâncias por pequenas variações de pressão. Os limites internos de força
são 0,84 para entrar e 0,72 para permanecer. A escolha considera movimento,
recepção e ações; não existe um botão de alternância em L3.

O balanço lateral do quadril é parte da pose. Ele não classifica uma passada
para frente como uma virada, nem impede a seleção da outra metade do ciclo.
Um quique da bola tocada pelo próprio jogador também não inicia uma recepção
externa ou uma troca indevida de animação.

## Contatos na bola

Os eventos foram ligados à superfície do modelo, incluindo as chuteiras,
na pose correspondente de cada animação. O cálculo nativo de aproximação
conserva o deslocamento necessário para chegar a essa superfície. Um impulso
exige encontro entre a esfera e a região do corpo, com tolerância numérica
máxima de 2,5 mm. A antiga margem de 40 cm não autoriza toques no ar.

Uma passada que não encontra a bola não aplica força. O ciclo novo completa
a passada e segue; as outras ações podem ser escolhidas novamente sem
segurar o jogador. Os vetores nativos de condução, domínio, passe e chute
continuam calculando o resultado de contatos válidos. A bola não é arrastada
até um alvo do loop, e a animação não possui um controle paralelo de posse.

## Recepção e exercícios

`Chest_Stand` continua como candidato adicional aos domínios de peito originais.
A seleção verifica a altura da chegada para não escolher um domínio com a
cabeça quando a bola vai encontrar o peito. Após o contato, mover ou solicitar
uma ação permite sair da recuperação pela transição do motor.

| Tecla | Exercício |
| --- | --- |
| F4 | Passe rasteiro recebido |
| F5 | Bola para domínio no peito |
| F6 | Cruzamento alto |
| R3 / Tab | Alternar câmera |
| R / View | Reiniciar |

RB continua sendo corrida; RT fica reservado. O relógio físico permanece em
10 ms. As cópias lentas da animação antiga mudam sua cadência, sem colocar a
partida em câmera lenta.

## Reprodução e validação

`scripts/register_dribble_cycle.py` gera as variantes do ciclo a partir de
`data/media/training/DefenseJog_LoopF.anim`. Os arquivos gerados acompanham
tanto o ZIP completo quanto a atualização. O carregamento registra também
cópias retimadas da condução antiga para o analógico leve.

`tests/training_forward_cycle_smoke.py` verifica saída parado, analógico leve,
entrada na nova condução, continuidade das duas metades, estabilidade com
variação do analógico e encontro entre bola e chuteira. Ele também compara
contatos físicos com amostras da malha realmente renderizada.
Os testes de recepção e ações verificam as transições do restante da gameplay.
A resposta ao comando é medida após a confirmação da entrada pelo SDL;
o teclado dos testes usa XTEST em uma sessão X11 isolada.
Resultados desta versão: [forward-cycle-validation.json](forward-cycle-validation.json).

Os testes renderizados usam Linux e controle Xbox virtual em SDL. A compilação,
as DLLs e a integridade do pacote Windows são verificadas separadamente;
a execução no Windows 11 com o controle físico precisa ser conferida nesse PC.
