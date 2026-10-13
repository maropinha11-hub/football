# Teste de condução DefenseJog_LoopF

O FBX enviado pelo usuário foi adaptado ao esqueleto de 13 ossos do jogador
Gameplay Football. Os comprimentos e as proporções do modelo nativo são
preservados. O arquivo contém locomoção Biped, sem bola ou marcadores de
contato com ela; nesta primeira comparação, os eventos de toque, a física,
a velocidade e os controles continuam na base aprovada `40bdfc5`.

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

A animação nova entra na condução reta normal, com transição de 160 ms.
Corridas, viradas, recepções, passes, chutes e movimento sem bola usam as
animações nativas. Próximo ao instante do toque nativo, a parte inferior
do corpo também retorna gradualmente à pose nativa para preservar a
posição do pé no contato. É um teste visual de locomoção; adicionar um
novo ciclo completo de condução com contatos próprios exige esses
marcadores e a sincronização da bola em uma próxima etapa.

O ciclo acompanha a velocidade real do jogador, sem alterar o relógio da
simulação. O deslocamento horizontal do FBX é removido: a posição continua
controlada pelo jogo. Rotações são convertidas por direção dos segmentos,
e o apoio visual usa os volumes dos calçados nativos. A pose visual é
aplicada após o cache nativo para não contaminar a física nem a próxima
animação. A primeira pessoa permanece com a cabeça local oculta.

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
`fbx-dribble-trial-validation.json`, `tests/training_fbx_trial_smoke.py` e
`tests/training_original_fps_smoke.py`. A execução com renderização e
controle virtual ocorre no Linux; o pacote Windows é compilado em x64 e
verificado quanto aos recursos, DLLs e integridade. A avaliação de sensação
com o controle físico e a GPU do usuário continua no Windows.
