# Football original em primeira pessoa, em tempo real

A solicitação atual substitui os ajustes anteriores de velocidade, distância
da bola e condução. O jogo retorna à física e aos toques originais do projeto
aberto, mantendo a câmera e as direções de comando em primeira pessoa.

`ball.cpp`, `ball.hpp` e `humanoid_utils.cpp` são idênticos aos arquivos da origem
`vi3itor/GameplayFootball`, revisão `68159a2f0f96eec8ebba26ab7820130f36b922a7`.
Isso restaura também o atrito linear de 1,6, que havia sido reduzido para 0,85,
e a restituição de 0,62. Não há substituição de impulsos de condução/puxada,
distância adicional à frente, preferência de pé nem chute com força/altura
calculadas pelo treino.

As regras originais de continuidade, seleção e interrupção dos passos também
foram restauradas. O treino usa a rotina original `Match::CheckBallCollisions`;
as cápsulas extras que podiam rebater a bola no próprio jogador foram retiradas.
A correção adicional das pernas no renderizador foi removida: a pose de
gameplay vem da animação nativa. O catálogo e os recursos originais permanecem.

RB permite correr. RT está reservado: os dispositivos de controle do treino
ignoram seu estado atual, anterior e seu valor analógico na função de domínio.
Ele não reduz velocidade, não adianta a bola com RB e não ativa super cancel.
Espaço, o equivalente no teclado, também fica reservado no treino. As direções
do analógico e a câmera mantêm os comandos aprovados: com bola, esquerdo conduz
em relação ao corpo e direito olha; sem bola, movimento acompanha a visão.

O modo solo conserva as proteções contra ausência de adversários, o movimento
livre após um passe, a preparação de ações antes da recepção e a disponibilidade
dos cabeceios nativos em exercícios aéreos. Não é uma reposição de todo o programa
por um executável antigo: permanecem SDL/XInput para Windows, exercícios, câmera
e as correções de temporização do ambiente atual.

O relógio continua monotônico, com passos físicos de 10 ms e correções do
agendamento que retiraram esperas desnecessárias. Não se acelera artificialmente
a simulação para compensar um relógio lento. O teste verifica a relação entre
tempo simulado e tempo real durante movimento.

Os resultados ficam em [native-original-fps-validation.json](native-original-fps-validation.json).
`tests/training_original_fps_smoke.py` usa controle Xbox virtual no SDL para
correr e soltar RB em diferentes momentos, repetir corrida/caminhada, parar,
verificar que RT não muda as velocidades e executar passes e chute nativos.
`tests/training_turns_smoke.py` verifica as viradas nas câmeras externa e em
primeira pessoa. A comparação dos arquivos originais faz parte da validação.

```bash
source scripts/native-env.sh
ctest --test-dir build --output-on-failure
python3 tests/training_original_fps_smoke.py --build build --output /tmp/football-original-fps-check
python3 tests/training_turns_smoke.py --build build --output /tmp/football-original-fps-turns
```

Use pastas de saída novas. A execução renderizada é testada no Linux; o pacote
Windows x64 tem a arquitetura, as DLLs, os CRCs e os hashes verificados. O teste
gráfico com Windows 11 e o controle físico precisa ser feito nesse computador.

O pacote completo pode ser extraído em uma pasta nova: abra `run-training.bat`
dentro da pasta extraída. Não é necessário importar recursos PES ou misturar
arquivos de outras versões.
