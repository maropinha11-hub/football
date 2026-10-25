# Equilíbrio sob pressão contínua

Extraia o pacote completo em uma pasta nova e abra **treino-fisico.bat**.
Use **R3/Tab** para observar o corpo por fora.

* Segure **U** para empurrar continuamente; solte para observar a recuperação.
* **Shift+U** aumenta a força; **Ctrl+U** testa sobrecarga, que pode causar queda.
* **F3** muda a direção; **F8** continua sendo um impacto isolado e **F9** uma queda deliberada.
* **Z+F4** envia um passe central para testar a recepção entre os pés.
* **Z+F2** coloca a bola parada perto dos pés para testar a saída com ela.
* **F10**, no treino, aproxima um parceiro; o modo **partida-fisica.bat** usa o mesmo controlador na CPU.

O controlador conserva deslocamento além de velocidade após um impacto. A
pressão precisa primeiro deslocar o corpo, com compensação de quadril, joelhos,
tronco e braços, em vez de desaparecer imediatamente por amortecimento.
A passada de recuperação evita avançar por dentro de um oponente próximo.

O transporte horizontal leva todos os segmentos no mesmo referencial do
jogador. Isso elimina o avanço artificial de meio passo de física que forçava
as articulações durante a corrida. A queda livre recupera a velocidade global
do jogador.

Os motores articulares acompanham a orientação e velocidade em relação ao
segmento pai e aplicam torques opostos nesse segmento. Coxas e canelas agora
participam da simulação ativa. A camada gráfica preserva o balanço original dos
braços sem impor uma pose física atrasada em toda a corrida. As chuteiras de
apoio conservam os alvos nativos e o comprimento dos ossos permanece fixo.

O alcance de um passe rasteiro é planejado antes de aceitar a animação.
Um ajuste limitado da perna aproxima o pé durante a preparação, sendo amostrado
pela colisão e pela renderização. O contato final continua sendo medido na pele;
o passe não é dominado simplesmente porque passou perto do jogador.

A previsão da CPU considera a altura do jogador e usa pontos de encontro
distintos para pés, peito e cabeça. Pequenos ajustes de uma bola alta mantêm o
jogador em espera até a preparação da recepção.

## Aprendizagem e referências

`tools/animations/train_balance_policy.py` treina uma rede 5→24→2 com NumPy,
distilando um planejador de ponto de captura com alcance limitado. Usa 16.000
estados de treino, 3.000 de validação e 5.000 de teste com sementes separadas.
As saídas propõem deslocamento do apoio e compensação do quadril. O controlador
limita as propostas segundo o suporte medido; a rede não decide contatos.
O erro de teste foi de 1,44 cm na proposta de apoio e 0,00962 rad no quadril.
O modelo reduzido e os resultados estão em `config/learned-balance-policy.json`.

Foram consultados os códigos públicos de [DeepMimic](https://github.com/xbpeng/DeepMimic),
[MimicKit](https://github.com/xbpeng/MimicKit),
[Motion-Matching](https://github.com/orangeduck/Motion-Matching) e
[Jolt Ragdoll](https://github.com/jrouwe/JoltPhysics/blob/master/Jolt/Physics/Ragdoll/Ragdoll.cpp).
Os URLs, hashes e resultados das consultas estão em `active-body-research.json`.

Esta revisão é um controlador híbrido: trajetória e apoio nativos durante a
locomoção, músculos articulares ativos e dinâmica livre na queda. Não é uma
política de futebol de corpo inteiro treinada por reforço nem uma reprodução
da engine Euphoria. A aprendizagem do equilíbrio não demonstra, por si só,
realismo de todos os movimentos. O treino renderizado e as disputas contra CPU
precisam verificar também os contatos, apoios e transições.
