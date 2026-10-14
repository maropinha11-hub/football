# Condução nativa com animações adicionais

A condução usa novamente as rotinas da versão `40bdfc5`, que restaurou o
Gameplay Football aberto com os comandos aprovados em primeira pessoa.
`GetBestCheatableAnimID`, `CalculateMovementSmuggle`, os vetores de domínio
e os vetores de condução permanecem iguais àquela base. O jogador não
espera uma posse paralela do loop FBX para começar a andar ou tocar a bola.

O seletor continua decidindo os passos, a aproximação, a trajetória e os
eventos de contato. `DefenseJog_LoopF` acompanha visualmente a condução sem
RB, com fase contínua e transições de pose. Não aplica impulsos adicionais
nem filtra os comandos de condução e recepção.

`Chest_Stand` foi acrescentado ao catálogo. Os domínios de peito antigos
permanecem. Para chegadas compatíveis ao peito e jogador parado, o candidato
novo tem preferência, passando pela mesma validação nativa de alcance e
aproximação. O exercício F5 entrega uma bola mais direta nessa região.
Após o contato de uma recepção, um comando pode sair da recuperação usando
o seletor e a mistura de poses do motor. A recepção usa a previsão atual
da bola; o atraso de reação não reaproveita a trajetória do exercício anterior.

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
[additive-native-validation.json](additive-native-validation.json).
Os relatórios anteriores preservam o histórico das implementações substituídas.

```bash
source scripts/native-env.sh
cmake --build build -j2
ctest --test-dir build --output-on-failure
FOOTBALL_TEST_GL_THREADS=1 python3 tests/training_additive_animations_smoke.py --build build --output /tmp/football-additive-check --display :132
FOOTBALL_TEST_GL_THREADS=1 python3 tests/training_additive_animations_smoke.py --build build --output /tmp/football-additive-reference --display :133 --native-only
```

Use pastas de saída novas. As partidas renderizadas são verificadas no Linux
com controle Xbox virtual em SDL. O pacote Windows x64 tem o executável,
as DLLs, os recursos, os CRCs e os hashes conferidos; a execução gráfica em
Windows 11 com o controle físico precisa ser confirmada nesse computador.

Extraia o ZIP completo em uma pasta nova e abra `run-training.bat` na pasta
extraída. Não é necessário importar recursos PES nem copiar pastas antigas.
