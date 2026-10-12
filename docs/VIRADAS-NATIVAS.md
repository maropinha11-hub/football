> Registro histórico, substituído pela [restauração do Football original em primeira pessoa](GAMEPLAY-NATIVA-FPS.md).

# Viradas com a bola na gameplay nativa

O vídeo recebido em 12/10/2026 mostra o jogador na câmera externa. A correção
anterior só suspendia o rebote das pernas em uma reversão específica na primeira
pessoa. Nas demais viradas, as cápsulas rígidas do treino ainda podiam empurrar
a bola antes do contato da animação e desviar a trajetória prevista pelo motor.

O jogo original evita rebotes acidentais no jogador com posse e imediatamente
após seus toques (`Match::CheckBallCollisions`). As pernas simplificadas do treino
agora respeitam essa proteção durante condução/domínio com bola baixa, em todas
as câmeras, inclusive viradas laterais e completas. A proteção após um toque
dura os mesmos 200 ms usados pela lógica original. Contatos de bolas livres e
altas continuam usando o tratamento do treino.

Foi retirada a substituição artificial da velocidade da puxada da tentativa
anterior. Os eventos e impulsos voltam à lógica nativa aprovada. A alteração
não adiciona animações e mantém os controles e a câmera em primeira pessoa.

Durante a validação, o usuário também pediu movimento um pouco mais lento e
mais espaço entre o pé e a bola sem corrida. A velocidade desejada normal
passou de 5,0 para 4,5 m/s (`training_walk_speed_scale=0.9`), conservando a
intensidade do analógico. A corrida com RB e o domínio próximo com RT mantêm
suas velocidades originais. A assistência de interceptação conserva sua
direção e respeita o novo limite de caminhada enquanto há input de movimento.
Esse limite acompanha a intensidade do analógico, para a assistência não
acelerar o jogador além do pedido quando ele está levemente inclinado.
O planejamento do toque também segue essa velocidade em condução alinhada:
uma animação de velocidade discreta não deve adiantar a bola como se o jogador
estivesse a 3,5 ou 5 m/s quando o analógico pede um passo mais lento.

O planejador nativo de condução recebe uma margem de 12 cm à frente
(`training_dribble_spacing_m=0.12`) em toques de condução baixa e alinhada,
sem corrida, sem RT e sem ação de passe/chute. Não se aplica durante reversões
nem no domínio de uma bola recebida. A bola percorre esse espaço pela física
normal a partir do evento da animação, sem reposicionamento entre toques.

O teste `tests/training_turns_smoke.py` injeta um controle Xbox virtual no SDL,
executa viradas opostas, laterais e círculos contínuos, nas câmeras externa e
em primeira pessoa. Ele verifica distância da bola, movimento e ausência de
rebotes adicionais. A mesma sequência é registrada antes e após a correção,
em [native-turns-validation.json](native-turns-validation.json). Os testes de
puxadas e das demais jogadas verificam a continuidade da gameplay. Esse
registro é anterior ao ajuste posterior de velocidade e distância da bola.
A verificação da versão final está em
[native-training-polish-validation.json](native-training-polish-validation.json).
O teste `training_pace_spacing_smoke.py` compara os mesmos comandos no jogo
final com os ajustes ativados e desativados, medindo velocidade e distância.

Para reproduzir a validação após compilar a versão nativa:

```bash
source scripts/native-env.sh
ctest --test-dir build --output-on-failure
python3 tests/training_turns_smoke.py --build build --output /tmp/football-turns-check
python3 tests/training_pullback_smoke.py --build build --output /tmp/football-pullback-check
python3 tests/training_pace_spacing_smoke.py --build build --output /tmp/football-pace-check
python3 tests/training_smoke.py --build build --output /tmp/football-gameplay-check
```

Use diretórios de saída novos. Os testes renderizados usam Xvfb e o SDL real.

Para atualizar, feche o jogo e extraia `football-windows-viradas-nativas.zip`
na pasta que já contém `gameplayfootball.exe`, `run-training.bat`, `media` e
as DLLs. Aceite substituir e abra `run-training.bat`.

A validação renderizada é feita no Linux. O executável Windows é compilado
para x64 e verificado quanto a integridade e dependências; a execução gráfica
no Windows com o controle físico depende do teste no computador do usuário.
