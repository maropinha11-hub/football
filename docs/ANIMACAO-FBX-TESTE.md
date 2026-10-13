# Teste de condução DefenseJog_LoopF

O FBX enviado pelo usuário foi adaptado ao esqueleto de 13 ossos do jogador
Gameplay Football. Os comprimentos e as proporções do modelo nativo são
preservados. O arquivo contém locomoção Biped, sem bola ou marcadores de
contato com ela. O teste agora acrescenta seus próprios contatos geométricos
para a condução reta. A física da bola, os controles e o modo original
continuam na base aprovada `40bdfc5`.

Este clip substitui o `DefenseJog_F` enviado anteriormente. O novo arquivo
tem um ciclo fechado de 0,7 segundo (quadros 1–22 a 30 fps), convertido em
71 amostras; a cadência acompanha o deslocamento real do jogador usando
a velocidade medida na animação, de aproximadamente 3,206 m/s.

## Jogar e comparar

1. Extraia `football-training-windows-x86_64.zip` em uma pasta nova.
2. Conecte o controle e execute `run-training.bat`.
3. Clique no analógico esquerdo (L3) para alternar original/nova. No teclado,
   use T. A mensagem na tela informa a opção; a original é o padrão.
4. Conduza reto com a bola, sem RB. R3 alterna as câmeras; a câmera externa
   próxima permite conferir braços, pernas e pés. Partindo da primeira pessoa,
   aperte R3 duas vezes para chegar à câmera próxima. Tab faz isso no teclado.

A animação nova entra na condução reta normal, com transição de 240 ms e
curva de aceleração/desaceleração suave. A cabeça recebe mais 0,08 radiano
(cerca de 4,6 graus) de inclinação para frente. As transições nativas de
movimento e jogadas usam 120 ms, mantendo seus eventos de contato.
O ciclo inteiro, incluindo as pernas e o tronco, segue do início ao fim em
loop. A fase avança no passo físico de 10 ms e é interpolada no mesmo tempo
histórico usado para desenhar a bola e o jogador. Não reinicia quando o
seletor nativo troca um passo e não retorna às pernas nativas a cada toque.

Com a opção FBX ligada, a velocidade normal solicitada ao caminhar/conduzir
é 6% menor (4,7 m/s com o analógico inteiro). A fase acompanha o deslocamento
real, reduzindo a cadência sem desacelerar o relógio do jogo. RB segue nativo.

O tronco recebe cerca de seis graus adicionais de inclinação para frente,
sem alterar o ciclo das pernas ou os comprimentos dos ossos.

Os pontos de contato são recuperados a partir do movimento dos calçados
adaptados ao modelo. Uma esfera tangente aos triângulos da chuteira visível
marca o local do próximo toque. O impulso é calculado com o preditor
original da bola, incluindo grama, arrasto e rotação, para que a bola alcance
esse local junto com o próximo passo. A bola segue a física entre contatos;
não é reposicionada nem presa ao pé. Um toque só é aceito com proximidade
geométrica de 0,5 mm da superfície. Pequenos ajustes de alcance do pé
encaixam a chuteira na bola no momento do toque. As duas articulações da
perna preservam os comprimentos originais e a rotação do calçado. O ciclo
inteiro permanece em execução, sem substituir suas pernas por outro passo.
Entre contatos, o pé cede levemente quando sua trajetória original cruzaria
a esfera, evitando atravessá-la. A bola mantém o impulso e o rolamento do
controlador aprovado; não recebe forças extras de colisores invisíveis nem
é reposicionada. Os ajustes da perna ficam limitados a 8 cm; o modo original
mantém os contatos e a física originais.

A posição do corpo, a fase e os ajustes dos pés usam amostras físicas de
10 ms e o mesmo instante de desenho da bola. Isso evita que o jogador
pareça atrasado em relação a um contato calculado corretamente.

Na entrada, a pose é alinhada à posição prevista da bola ao fim dos 240 ms.
A troca só começa com um pé baixo e avançando que consiga alcançar essa
posição; a bola rola livremente até esse contato.
Se um toque for perdido ou a entrada não alcançar a bola, o modo nativo retoma o
controle; uma bola distante não é puxada para o loop.

Desde essa entrada alcançável, os antigos impulsos de condução e a correção
de posição para interceptar a bola ficam suspensos. Isso evita duas lógicas
disputarem o mesmo movimento. RB, viradas, recepções, passes, chutes,
movimento sem bola e a opção original continuam com os eventos nativos.

O deslocamento horizontal do FBX é removido: os comandos nativos movem o
jogador. Rotações são convertidas por direção dos segmentos, e o apoio
visual usa os volumes dos calçados nativos. A pose é aplicada após o cache
nativo. A primeira pessoa permanece com a cabeça local oculta.

## Reproduzir a conversão

O arquivo original está em `assets/animation-sources/DefenseJog_LoopF.fbx`.
O conversor precisa de Blender 4.3 ou posterior; quem apenas joga o pacote
Windows não precisa instalar Blender.

```bash
blender -b --threads 2 --python-exit-code 1 \
  --python tools/animations/import_fbx.py -- \
  assets/animation-sources/DefenseJog_LoopF.fbx \
  data/media/training/DefenseJog_LoopF.anim
```

`tools/animations/native_rig_reference.json` registra os deslocamentos e
volumes do esqueleto nativo calibrado. O JSON ao lado do clip registra os
hashes, a duração, a velocidade original e os erros da conversão. O clip
preparado já acompanha os pacotes completo e de atualização; não é preciso
copiar recursos PES de versões anteriores.

Imagens capturadas na execução do teste: [original](images/fbx-dribble-original.png)
e [nova animação](images/fbx-dribble-new.png).

As verificações reproduzíveis desta entrega estão em
`fbx-dribble-trial-validation.json`, `tests/training_fbx_trial_smoke.py`,
`tests/training_fbx_handoff_smoke.py` e
`tests/training_original_fps_smoke.py`. A execução com renderização e
controle virtual ocorre no Linux; o pacote Windows é compilado em x64 e
verificado quanto aos recursos, DLLs e integridade. A avaliação de sensação
com o controle físico e a GPU do usuário continua no Windows.
