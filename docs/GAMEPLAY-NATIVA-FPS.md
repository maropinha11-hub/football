# Gameplay nativa com camada superior

A condução usa a seleção nativa em todas as direções e câmeras, priorizando
o pé direito entre candidatos válidos. A condução frontal DefenseJog foi
retirada da seleção. Os gestos adicionais de peito usam tronco, cabeça e
braços; após a queda, os braços voltam suavemente à locomoção. Pernas e raiz
mantêm a locomoção nativa. A recepção permite
ajustes para frente e para trás, sem domínio virando para os lados.

A previsão e o contato usam a superfície do modelo. O domínio exige contato
frontal no peito; as demais recepções nativas continuam disponíveis. Não há
reposicionamento instantâneo de pernas para alcançar a bola. Câmera, comandos
Xbox, RB e RT reservado permanecem.

Consulte [a integração](ANIMACAO-FBX-TESTE.md) e os
[resultados](native-right-foot-reception-validation.json). Os relatórios
anteriores registram versões substituídas.

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
