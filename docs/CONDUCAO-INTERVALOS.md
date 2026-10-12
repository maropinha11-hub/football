# Contatos e intervalos da condução nativa

A condução com preferência pelo pé direito usa um intervalo entre os
contatos planejados. O sistema escolhe uma animação cujo contato possa
ocorrer depois desse intervalo; a bola continua rolando e o jogador mantém
a locomoção nativa entre os toques. RT permite um domínio mais curto.
Uma mudança de direção permite antecipar a puxada depois de completar
o contato anterior, e o início de uma virada usa um intervalo menor para
evitar deixar a bola para trás. Passes, chutes e recepções de primeira
conservam seus contatos nativos e podem interromper a condução.
O limite de velocidade entre os toques vale apenas no domínio próximo;
quando a bola é adiantada, a assistência nativa continua permitindo alcançá-la.

L3/G continua alternando o modo dominante e o normal. O normal conserva
o ritmo da seleção nativa; os dois modos recebem a correção das colisões.
O ritmo do modo dominante não altera o relógio da simulação.

Os colisores das pernas usam os canais da animação atual, as medidas da
malha e os offsets da hierarquia nativa. São calculados na simulação, sem
ler os ossos interpolados pelo renderizador. A varredura considera os dois
extremos em movimento. Durante o domínio, a perna de apoio bloqueia ou
desvia a bola e não lhe transfere a velocidade de corrida como outro chute.
O contato planejado da perna que executa a jogada fica sob responsabilidade
do evento nativo de animação, evitando uma colisão incidental na preparação.
O fim do contato conserva os cinco quadros de acompanhamento do pé usados
pela correção de pose, antes de permitir outra seleção de condução.
A puxada escolhe um caminho ao lado da perna de apoio quando a trajetória
direta a atravessaria. A posição da bola continua sendo resolvida pela física.

As medidas e animações usadas pertencem ao modelo do Gameplay Football.
Nenhuma animação ou seleção de jogada do PES é ativada no treino nativo.

Atualização Windows: extraia `football-windows-virada-e-intervalos.zip`
dentro da pasta que já contém `run-training.bat`, `media` e as DLLs,
aceite substituir e abra `run-training.bat`.

[Validação dos contatos](native-dribble-contact-validation.json) inclui
medições antes/depois, sequências de viradas e intervalos entre os contatos
reais. O pacote foi compilado para Windows; os testes renderizados são feitos
no Linux com um controle Xbox virtual. A execução com o controle físico no
Windows depende da conferência no computador do usuário.

Verificação reproduzível, depois de compilar a versão nativa:

```sh
. scripts/native-env.sh
ctest --test-dir build --output-on-failure
python3 tests/training_smoke.py --build build --output /tmp/football-gameplay-check
python3 tests/training_reversal_smoke.py --build build --output /tmp/football-reversal-check --analog-pad
python3 tests/training_dribble_contacts.py --build build --output /tmp/football-contact-check
```

Os testes usam pastas de saída novas. A sequência de contatos mantém RB
pressionado durante as viradas de corrida e, após RB+RT, solta RT mantendo
a corrida para alcançar a bola adiantada. A distância máxima permitida nessa
jogada é a mesma do exercício nativo de adiantar a bola; a recuperação exige
retorno à distância de condução. A virada a partir do repouso verifica primeiro
a puxada e o giro com o pé plantado, depois o deslocamento para trás.
