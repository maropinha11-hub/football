# Windows 11

O artefato `artifacts/football-training-windows-x86_64.zip` é um pacote x64
portátil. Extraia-o para uma pasta local, conecte o controle Xbox Series S por
USB ou Bluetooth e execute `run-training.bat`. O lançador abre diretamente o
centro de treinamento com `config/training.config` e os recursos do jogo.

Para estudar as animações PES3 dentro do campo, execute `importar-pes3.bat`,
selecione seu `fpsoccer-pes-nucleo-v14.zip` e execute `estudar-pes3.bat`.
O modo mostra um esqueleto de 19 ossos ao lado do jogador, com pausa e avanço
de fase. A substituição da gameplay do PES ainda está pendente.
Os controles e os limites estão em [PES3-ANIMACOES-NO-TREINO.md](PES3-ANIMACOES-NO-TREINO.md).
Com o jogador parado, V aplica a pose PES à malha nativa para teste.
Movimentar, correr, dominar, passar ou chutar restaura automaticamente a animação
nativa. Consulte [PES3-CORPO-NATIVO.md](PES3-CORPO-NATIVO.md).

`run-controller-test.bat` executa testes automáticos com controle virtual,
câmera, carga de chute e colisões. Execute o teste com controles físicos
desconectados, para deixar os slots disponíveis ao dispositivo virtual.
O treino usa XInput para Xbox no Windows,
com SDL como alternativa. O mapeamento usado no treino é:

| Controle | Ação |
| --- | --- |
| Analógico esquerdo | Movimento |
| Analógico direito | Virar a visão sem bola; olhar com a cabeça com bola |
| A | Passe |
| Y | Passe em profundidade |
| B | Bola alta / carrinho |
| X | Chute |
| RB | Corrida |
| RT | Reservado, sem função no treino |
| View | Reiniciar exercício |
| Menu | Pausar |
| D-pad | Trocar exercício |
| LB + D-pad baixo | Cobrança de falta |
| LB + D-pad direita | Receber passe rasteiro para jogar de primeira |
| R3 | Câmera |

Primeira pessoa é o modo inicial. R3 alterna entre primeira pessoa, externa
e próxima. Com bola o direito não desvia a condução, e a cabeça retorna
gradualmente ao centro ao soltá-lo. O esquerdo acompanha a frente atual do
jogador: depois de virar, frente segue a nova frente e direita continua
virando para a nova direita. Baixo pede a direção atrás do corpo; se for
mantido, pede novamente a nova direção para trás após completar a virada.
RT está reservado. Segurar X carrega o chute com as regras originais do Football.
As setas do teclado substituem o direito; Shift permite correr e 5/F3 inicia
a cobrança de falta. Espaço, o equivalente de RT no teclado, também fica reservado.

A condução usa a assistência e os passos originais para acompanhar a bola
durante curvas e inversões. Após um passe ou chute, o movimento fica livre;
aproxime-se novamente da bola para retomar o domínio. Ao atualizar, extraia
o novo ZIP em uma pasta nova e inicie por `run-training.bat`.

Na bola aérea (D-pad esquerda), prepare A para cabecear um passe ou X para
cabecear uma finalização antes da chegada. O exercício de passe recebido
(LB + D-pad direita; tecla 6) permite preparar A/Y/X para jogar de primeira.
RB permite correr e, ao soltá-lo, o jogador volta à condução normal. A bola
segue a física original entre contatos. A restauração do núcleo e os testes
estão descritos em [GAMEPLAY-NATIVA-FPS.md](GAMEPLAY-NATIVA-FPS.md).

O treino reduz as trocas entre tarefas do motor, mantendo o passo de 10 ms.
Se ainda perceber lentidão, o `log.txt` contém linhas `Training::Timing`:
uma relação próxima de `1.0` indica tempo real. Esse registro também permite
distinguir atraso da simulação de baixa frequência de imagem no seu PC.

`training.config` permite ajustar `firstperson_fov`, `firstperson_look_speed`,
`firstperson_recenter_speed` e `input_analog_deadzone`. O pacote usa
`graphics_vsync=0`, com apresentação limitada pelo intervalo de 16 ms.
Se preferir sincronização com o monitor, use `graphics_vsync=1`.

O executável é compilado como PE32+ GUI para Windows x64 com MinGW e as DLLs
SDL2, OpenAL, Boost e SQLite ficam ao lado dele no ZIP. A renderização e o
controle físico precisam ser conferidos no computador Windows, pois o ambiente
de compilação não fornece uma sessão Windows nem um controle Xbox conectado.

Para recompilar a partir do código, use CMake/Ninja e um triplet MinGW x64
dinâmico do vcpkg (`sdl2`, `sdl2-image`, `sdl2-ttf`, `sdl2-gfx`, `openal-soft`,
`boost-filesystem`, `boost-system`, `boost-thread` e `sqlite3`), configure com
`CMAKE_SYSTEM_NAME=Windows` e execute `scripts/package-windows.py` depois do
build.

Neste ambiente, o SDK MinGW/vcpkg restaurado fica em
`/workspace/.football-windows/vcpkg`, com cache e fontes nessa mesma pasta
persistente. A configuração de `build-windows-mingw2` usa esse caminho.
Os cabeçalhos adicionais necessários são `boost-signals2`, `boost-random`
e `boost-circular-buffer`; SDL2_image inclui JPEG, WebP e TIFF.
Para recompilar e empacotar nesta máquina:

```bash
source scripts/native-env.sh
cmake --build build-windows-mingw2 -j2
python scripts/package-windows.py
```

Os servidores indisponíveis de dependências foram substituídos por espelhos
GitHub oficiais ou pelo arquivo fonte Debian. A amalgamação SQLite 3.53.4
foi gerada pelos scripts do próprio SQLite a partir da tag oficial;
os arquivos e as verificações SHA512 ficam no cache do SDK. Esses arquivos
são necessários para desenvolvimento, e não para executar o ZIP completo.
