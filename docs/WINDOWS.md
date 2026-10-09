# Windows 11

O artefato `artifacts/football-training-windows-x86_64.zip` é um pacote x64
portátil. Extraia-o para uma pasta local, conecte o controle Xbox Series S por
USB ou Bluetooth e execute `run-training.bat`. O lançador abre diretamente o
centro de treinamento com `config/training.config` e os recursos do jogo.

Para verificar a enumeração do controle antes de jogar, execute
`run-controller-test.bat`. A janela lista os dispositivos SDL detectados e os
eventos de botões/eixos recebidos. O mapeamento usado no treino é:

| Controle | Ação |
| --- | --- |
| Analógico esquerdo | Movimento |
| A | Passe |
| Y | Passe em profundidade |
| B | Bola alta / carrinho |
| X | Chute |
| RB | Corrida |
| RT | Domínio |
| View | Reiniciar exercício |
| Menu | Pausar |
| D-pad | Trocar exercício |
| R3 | Câmera |

O executável é compilado como PE32+ GUI para Windows x64 com MinGW e as DLLs
SDL2, OpenAL, Boost e SQLite ficam ao lado dele no ZIP. A renderização e o
controle físico precisam ser conferidos no computador Windows, pois o ambiente
de compilação não fornece uma sessão Windows nem um controle Xbox conectado.

Para recompilar a partir do código, use CMake/Ninja e um triplet MinGW x64
dinâmico do vcpkg (`sdl2`, `sdl2-image`, `sdl2-ttf`, `sdl2-gfx`, `openal-soft`,
`boost-filesystem`, `boost-system`, `boost-thread` e `sqlite3`), configure com
`CMAKE_SYSTEM_NAME=Windows` e execute `scripts/package-windows.py` depois do
build.
