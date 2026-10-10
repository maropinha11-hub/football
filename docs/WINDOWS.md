# Windows 11

O artefato `artifacts/football-training-windows-x86_64.zip` é um pacote x64
portátil. Extraia-o para uma pasta local, conecte o controle Xbox Series S por
USB ou Bluetooth e execute `run-training.bat`. O lançador abre diretamente o
centro de treinamento com `config/training.config` e os recursos do jogo.

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
| LB + X | Cobertura |
| RB | Corrida |
| RT | Domínio |
| View | Reiniciar exercício |
| Menu | Pausar |
| D-pad | Trocar exercício |
| LB + D-pad baixo | Cobrança de falta |
| R3 | Câmera |

Primeira pessoa é o modo inicial. R3 alterna entre primeira pessoa, externa
e próxima. Com bola o direito não desvia a condução, e a cabeça retorna
gradualmente ao centro ao soltá-lo. O esquerdo acompanha a frente atual do
jogador: depois de virar, frente segue a nova frente e direita continua
virando para a nova direita. RT mantém esse referencial, com domínio mais
lento e próximo, sem virar automaticamente para o gol. Segurar X aumenta a força e a altura,
com carga máxima de 0,52 segundo; cerca de 0,25 segundo já produz elevação.
Os passes mantêm a carga de um segundo. As setas do teclado substituem o direito;
Q+K faz cobertura e 5/F3 inicia a cobrança de falta.

A condução usa a assistência e os passos originais para acompanhar a bola
durante curvas e inversões. Após um passe ou chute, o movimento fica livre;
aproxime-se novamente da bola para retomar o domínio. Ao atualizar, extraia
o novo ZIP em uma pasta nova e inicie por `run-training.bat`.

`training.config` permite ajustar `firstperson_fov`, `firstperson_look_speed`,
`firstperson_recenter_speed` e `input_analog_deadzone`.

O executável é compilado como PE32+ GUI para Windows x64 com MinGW e as DLLs
SDL2, OpenAL, Boost e SQLite ficam ao lado dele no ZIP. A renderização e o
controle físico precisam ser conferidos no computador Windows, pois o ambiente
de compilação não fornece uma sessão Windows nem um controle Xbox conectado.

Para recompilar a partir do código, use CMake/Ninja e um triplet MinGW x64
dinâmico do vcpkg (`sdl2`, `sdl2-image`, `sdl2-ttf`, `sdl2-gfx`, `openal-soft`,
`boost-filesystem`, `boost-system`, `boost-thread` e `sqlite3`), configure com
`CMAKE_SYSTEM_NAME=Windows` e execute `scripts/package-windows.py` depois do
build.
