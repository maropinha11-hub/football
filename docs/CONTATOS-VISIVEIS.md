> Registro histórico: esta versão foi retirada a pedido do usuário. A versão atual restaura a [gameplay original](GAMEPLAY-ORIGINAL.md).

# Condução e contatos da malha nativa

O treino inicia com a preferência pelo pé direito. L3/G conserva a opção de
alternar para a seleção normal. RT está reservado: não freia, não seleciona
domínio curto e não dispara um toque longo com RB. A intensidade do analógico
esquerdo controla o movimento; RB permite correr.

Os contatos de condução têm um intervalo e deixam a bola rolar à frente.
A puxada a partir da bola parada também aplica um impulso na direção pedida.
Quando a trajetória cruza a perna de apoio, a condução procura uma passagem
ao lado dela. Os passos de apoio ajustam a posição da perna para dar espaço
à bola, preservando os comprimentos dos ossos.
Nas curvas, o jogador se aproxima da bola que ainda rola na direção anterior
até o próximo contato. Depois de redirecioná-la, dá espaço para a puxada
passar à nova frente, em vez de correr por cima dela.

A colisão usa os triângulos e pesos da malha original, guardados durante o
carregamento. A simulação calcula a pose dos 13 ossos nativos e a correção
das pernas; o renderizador recebe essa mesma pose. A varredura considera o
movimento da bola e dos vértices durante cada passo de 10 ms. O raio físico
da bola é 0,11 m, compatível com a malha visual de 0,11003 m.

O domínio automático que aplicava força pela proximidade do jogador foi
retirado do treino. As jogadas nativas são aplicadas quando a superfície
do membro indicado chega à bola. Um contato aceito encerra a espera do
controle; a movimentação pode ser replanejada após o acompanhamento do pé.
O alvo do pé permanece no ponto do contato depois da jogada, enquanto a
bola segue sua trajetória. A perna de apoio bloqueia ou desvia um contato
incidental sem acrescentar a velocidade de corrida como outro chute.

As animações, passes, chutes, cabeçadas e recepções continuam sendo da base
Gameplay Football. O treino não ativa o banco ou o seletor PES.

Atualização: feche o jogo, extraia `football-windows-contatos-e-conducao.zip`
**dentro da pasta onde estão `run-training.bat`, `media` e as DLLs**, aceite
substituir e abra `run-training.bat`.

As verificações usam a execução renderizada no Linux, teclado e controle
Xbox virtual. O pacote Windows é compilado para x64 e verificado quanto
às dependências e à integridade. A execução com Windows 11 e o controle
físico depende do teste no computador do usuário.

Os resultados desta versão ficam em
[`native-visible-contact-validation.json`](native-visible-contact-validation.json).

Comandos de verificação, usando pastas novas de saída:

```sh
. scripts/native-env.sh
ctest --test-dir build --output-on-failure
python3 tests/training_dribble_contacts.py --build build --output /tmp/football-contacts
python3 tests/training_reversal_smoke.py --build build --output /tmp/football-reversals --analog-pad
python3 tests/training_smoke.py --build build --output /tmp/football-gameplay
```
