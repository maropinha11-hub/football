# Condução nativa com animações adicionais

A condução continua usando o seletor e os vetores do Gameplay Football.
Na saída e com o analógico leve, usa as animações antigas. Com pressão forte
para frente, entra nas duas metades consecutivas de `DefenseJog_LoopF`,
registradas no próprio catálogo nativo. Não há sobreposição de pose antiga
na hora do toque nem um segundo controlador arrastando a bola.

Os marcadores são vinculados à pele do modelo e o deslocamento de aproximação
calculado pelo motor é conservado. O impulso só ocorre quando a esfera alcança
a região correspondente, com margem de 2,5 mm. Isso substitui a autorização
anterior por proximidade de até 40 cm. Os vetores de condução e domínio
continuam vindo de `humanoid_utils.cpp`; não é uma substituição da física
por alvos de posse exclusivos do ciclo FBX.

`Chest_Stand` e `Chest_Run` são domínios adicionais. A chegada ao peito
e o comando para frente distinguem as duas opções. Ambos completam o clip
antes da próxima jogada; comandos mantidos retomam o movimento ao final.
Quiques da própria condução não são tratados como passes externos.

A câmera, as direções do controle, o RT reservado e o passo físico de 10 ms
foram mantidos. Também permanecem a cadência aprovada, os exercícios de
passe/cruzamento, o quique configurável e os ajustes anteriores de carga,
cobertura e rotação dos chutes. Portanto, a restauração da condução não é
uma declaração de que todos os arquivos do programa são idênticos ao upstream.

A proteção de colisão com o corpo continua usando a superfície do modelo
para bolas aéreas que não são alcançadas por uma recepção. Não existe um
controlador extra arrastando a bola até o próximo pé ou prendendo o jogador
à posição capturada no início do domínio.

Os resultados desta versão ficam em
[chest-run-validation.json](chest-run-validation.json).
Os relatórios anteriores preservam o histórico das implementações substituídas.

```bash
source scripts/native-env.sh
cmake --build build -j2
ctest --test-dir build --output-on-failure
FOOTBALL_TEST_GL_THREADS=1 python3 tests/training_additive_animations_smoke.py --build build --output /tmp/football-additive-check --display :132
FOOTBALL_TEST_GL_THREADS=1 python3 tests/training_reception_variants_smoke.py --build build --output /tmp/football-receptions-check --display :137
FOOTBALL_TEST_GL_THREADS=1 python3 tests/training_forward_cycle_smoke.py --build build --output /tmp/football-forward-cycle --display :135
FOOTBALL_TEST_GL_THREADS=1 python3 tests/training_running_actions_smoke.py --build build --output /tmp/football-running-actions --display :138
FOOTBALL_TEST_GL_THREADS=1 python3 tests/training_native_controls_smoke.py --build build --output /tmp/football-native-controls --display :134
```

Use pastas de saída novas. As partidas renderizadas são verificadas no Linux
com controle Xbox virtual em SDL. O pacote Windows x64 tem o executável,
as DLLs, os recursos, os CRCs e os hashes conferidos; a execução gráfica em
Windows 11 com o controle físico precisa ser confirmada nesse computador.

Extraia o ZIP completo em uma pasta nova e abra `run-training.bat` na pasta
extraída. Não é necessário importar recursos PES nem copiar pastas antigas.
