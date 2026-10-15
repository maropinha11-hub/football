# Gameplay nativa com camada superior

A locomoção, a assistência, a escolha das ações e os impulsos continuam
baseados no Gameplay Football. O gesto adicional de peito é uma camada sobre
tronco, braços e cabeça; as pernas e a raiz permanecem na animação nativa.
Ele não bloqueia comandos até o fim nem desloca o jogador para um alvo fixo.

Na condução para frente, o gesto de toque é intercalado com a locomoção
original enquanto a bola rola. Os intervalos entre toques evitam repiques
nas diagonais. As animações são retimadas com seus eventos, mantendo o
relógio físico de 10 ms e as velocidades dos percursos.

A previsão e o contato usam a superfície do modelo. O domínio superior
exige o peito frontal; sair da trajetória permite perder a bola. As demais
recepções nativas continuam disponíveis. Não há reposicionamento instantâneo
de pernas para alcançar a bola. A câmera, os comandos Xbox, RB e RT reservado
continuam presentes.

Consulte [a integração](ANIMACAO-FBX-TESTE.md) e os
[resultados](upper-body-cadence-validation.json). Os relatórios anteriores
registram versões substituídas, inclusive o antigo bloqueio de recepção.

```bash
source scripts/native-env.sh
cmake --build build -j2
ctest --test-dir build --output-on-failure
FOOTBALL_TEST_GL_THREADS=1 python3 tests/training_upper_body_smoke.py --build build --output /tmp/football-upper-check --display :137
FOOTBALL_TEST_GL_THREADS=1 python3 tests/training_forward_cycle_smoke.py --build build --output /tmp/football-forward-check --display :135
FOOTBALL_TEST_GL_THREADS=1 python3 tests/training_running_actions_smoke.py --build build --output /tmp/football-running-check --display :138
FOOTBALL_TEST_GL_THREADS=1 python3 tests/training_native_controls_smoke.py --build build --output /tmp/football-controls-check --display :134
FOOTBALL_TEST_GL_THREADS=1 python3 tests/training_additive_animations_smoke.py --build build --output /tmp/football-additive-check --display :132
```

Execute em sequência e use pastas de saída novas. Os jogos renderizados são
verificados no Linux com controle Xbox virtual. O pacote Windows x64 tem
executável, DLLs, recursos, CRCs e hashes conferidos; o teste gráfico no
Windows 11 com o controle físico precisa ser feito nesse computador.

Extraia o pacote completo em uma pasta nova e abra `run-training.bat`.
