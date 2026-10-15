# Domínio superior e condução com intervalos

Extraia o ZIP completo em uma pasta nova e abra `run-training.bat`.

| Situação | Comportamento |
| --- | --- |
| Saída parado / analógico leve | Condução nativa |
| Frente forte, bola próxima e alcançável | Gesto de toque DefenseJog_LoopF |
| Bola se afastando depois do toque | Locomoção nativa enquanto a bola rola |
| Virada ou RB | Seleção e recuperação nativas |
| Bola na trajetória do peito | Camada Chest_Stand ou Chest_Run sobre pernas livres |
| Jogador sai da trajetória | Sem domínio forçado; recepções nativas continuam disponíveis |

## Camada do peito

A camada altera `middle`, `neck`, ombros e cotovelos. Ela não altera a raiz,
a orientação da pelve nem os ossos das pernas. A rotação do tronco das fontes
é adaptada à referência da pelve atual. O deslocamento de raiz e as passadas
dos FBX não são aplicados nesse experimento.

A pose composta é usada tanto pelo renderizador quanto pelas colisões. A
previsão confere a parte frontal do peito; o evento real depende de a esfera
alcançar a pele nessa região, com margem numérica de 2,5 mm. A cabeça, as
costas e um alvo distante do corpo não autorizam o domínio. A camada não
prende o jogador ao ponto previsto de recepção. Um gesto que perde a bola
se desfaz suavemente; um gesto com contato pode continuar com as pernas andando.

`Chest_Stand` e `Chest_Run` continuam sendo fontes adicionais. Com o analógico
solto, a seleção pode usar Stand; com avanço moderado, pode usar Run. Movimento
mais forte pode alterar o encontro com a bola e exigir outra recepção.
As fontes FBX não têm trilha de bola: os marcadores de integração são ligados
à superfície do modelo durante o carregamento.

## Toque e rolagem

A animação de condução deixa de tocar continuamente quando não é necessária.
Depois do toque, ela completa o gesto e dá lugar à locomoção original. Outro
gesto só é escolhido quando a bola está à frente, próxima e alcançável; uma
bola se afastando continua rolando. Não há um segundo controlador arrastando
a bola nem uma correção rápida da perna no último instante.

Os eventos de condução têm intervalo mínimo de 420 ms, ou 300 ms durante RB.
A aproximação nativa confere a superfície da chuteira na altura prevista da
bola; chutes, passes e cabeçadas usam a mesma conferência da região pertinente.
O impulso continua exigindo contato físico real no instante de execução.

## Cadência e comandos

`training_animation_time_scale` vale 1,12. Os quadros e eventos são retimados
juntos; o percurso horizontal é ajustado para manter suas velocidades. O
comprimento dos ossos é preservado. A física e os comandos continuam a 100 Hz.
Os fontes Stand e Run de 151 e 91 amostras passam a 169 e 102 no catálogo.
O ciclo de condução termina cada metade retimada, sem cortar os quadros finais.

| Tecla | Exercício |
| --- | --- |
| F4 | Passe rasteiro recebido |
| F5, analógico solto | Bola para domínio de peito parado |
| F5, avanço moderado | Bola para experimentar o domínio avançando |
| F6 | Cruzamento alto |
| R3 / Tab | Alternar câmera |
| R / View | Reiniciar |

RB continua sendo corrida e RT fica reservado. L3/T não alternam a condução.

## Validação

`tests/training_upper_body_smoke.py` verifica domínio com pernas livres,
movimento antes da chegada, erro de trajetória, recepção com os pés e a
preservação da raiz e das pernas no modelo renderizado. O ponto de entrada
`training_reception_variants_smoke.py` executa essa especificação atual;
os antigos testes de bloqueio até o fim foram substituídos pelo novo requisito.

`tests/training_forward_cycle_smoke.py` verifica toques separados por locomoção
normal, avanço pelo campo, conclusão dos gestos, viradas diagonais, intervalo
entre impulsos, contato na malha e recuperação depois de RB. Os testes de
ações em corrida e controles conferem passes, chutes, cobertura e cabeçadas.

Resultados: [upper-body-cadence-validation.json](upper-body-cadence-validation.json).
Os testes renderizados usam Linux e controle Xbox virtual em SDL. O Windows
é compilado e tem executável, recursos, importações e integridade do ZIP
conferidos; a execução gráfica com o controle físico depende do computador.
