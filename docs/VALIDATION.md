# Validação do centro de treinamento

Validação realizada em 2026-10-09 na máquina de nuvem Linux x86_64,
Debian 13, GCC 14.2, CMake 3.31.6, SDL2 2.32.4 e Boost 1.83.
O jogo foi renderizado em Xvfb/OpenGL por software, com áudio OpenAL nulo
para a máquina sem dispositivo de áudio. Isso não mede desempenho na GPU
nem a latência de um Xbox físico no computador do usuário.

## Resultado da versão atual

- Compilação C++ nativa: concluída, status zero.
- Reexecução da instalação rootless: concluída, status zero. APT manteve
  assinatura de repositório e hashes de pacotes; não houve alteração de
  dependências do sistema nem desativação de verificações.
- `ctest --test-dir build --output-on-failure`: 1 teste executado, 1 aprovado,
  28 verificações de entrada SDL; nenhum teste ignorado.
- `./scripts/test.sh`: status zero; 16 verificações funcionais aprovadas
  com a aplicação gráfica em execução.
- `python3 scripts/verify_upstream.py`: 515 arquivos originais verificados,
  incluindo recursos em `data` e módulos centrais de física/animação.
- `scripts/start-headless.sh`: inicialização confirmada por quadros reais
  de simulação com tempo avançando e encerramento pelo comando Escape,
  status zero. O script também encerrou o Xvfb que iniciou.

O relatório funcional atual é `artifacts/validation.json`, execução
`12d44617-42b5-49d7-be1d-bdb2e96d70ba`. O runner grava um identificador
novo em cada execução e registra também falhas, para não deixar um
resultado aprovado antigo aparentar sucesso de um teste posterior.

## Evidências funcionais

| Verificação | Evidência observada |
| --- | --- |
| Inicialização gráfica | Simulação emitindo quadros reais e campo/jogador renderizados |
| Movimento/condução | Deslocamento do jogador de 6,33 m no comando de caminhada |
| Reprodução das animações | Quadros das animações originais avançando |
| Soltar movimento | Velocidade final de 0,000 m/s após desaceleração |
| Corrida | Pico de 7,66 m/s, contra 5,00 m/s no trecho de caminhada |
| Passe curto | Função original 4; bola a 25,05 m/s |
| Passe em profundidade | Função original 5; bola a 25,53 m/s |
| Passe alto | Função original 6; bola a 27,69 m/s |
| Chute | Função original 8; bola a 29,92 m/s |
| Bola aérea | Altura máxima observada de 3,94 m |
| Super cancel | Movimento livre afastou o jogador da trajetória de interceptação, até x=-5,48 m |
| Carrinho sem bola | Animação/função original 13 durante movimento sem posse |
| Exercício de finalização | Jogador colocado próximo de x=30 m |
| Gol | Contador passou de 0 para 1, sem contagem duplicada no lance |
| Reposição automática | Bola devolvida a x=30,65 m após o gol |
| Encerramento | Processo terminou com status zero |

As velocidades são amostras dessa execução da base, não valores
garantidos para todo jogador ou ação. A base usa atributos, contexto,
previsão e componentes aleatórios. Foram preservados seus algoritmos.

## Entrada Xbox

O teste criou um controle virtual Xbox pela API SDL e percorreu a mesma
entrada usada pelo `HIDGamepad`, com ID de instância não zero. Verificou
direção do analógico, zona morta, gatilhos liberados/pressionados, X como
chute, bordas e estado anterior, rejeição de índices inválidos, limpeza na
perda de foco, remoção e reconexão em slot estável. Também verificou que
um atalho pressionado e solto entre duas leituras não se perde nem executa
duas vezes.

O curso útil do analógico foi corrigido: a zona morta original de 75%
descartava o comando virtual de 73%; o padrão configurável de 15% o aceita.
As velocidades de movimento e os arquivos de animação não foram retocados
para fazer testes passarem.

## Correções verificadas durante a integração

Falhas iniciais do harness e condições incorretas de teste foram corrigidas:
inicialização dos managers no teste SDL, captura do lançamento da bola
aérea desde a seleção do exercício e teste de carrinho após movimento
livre com super cancel. O motor original pode escolher interceptação,
domínio ou passe alto quando a bola já está próxima; pressionar B em
qualquer momento não é um teste válido de carrinho sem posse.

No treino, o estado de bola dentro do gol permanece ativo até a reposição,
como o motor original exige para a física da rede. O cruzamento da linha
dura apenas um tick; usar esse evento como estado contínuo faria a rede
perder a informação e permitiria contagens repetidas.

## Limites de cobertura

Não foram validados controle físico, Bluetooth, vibração, Windows/macOS,
desempenho no PC do usuário, todos os clips individualmente, cabeceio e
voleio em cada contexto, duelo com adversário, goleiro, recebedor de passe,
partidas e ligas antigas. Os recursos dessas ações continuam na base, mas
a sua existência não equivale a uma execução aprovada de cada situação.

Primeira pessoa, carreira e online ficam para a etapa posterior solicitada.
Não houve comparação com uma versão específica de PES. Os repositórios
fornecidos não contêm seu motor ou suas animações.

Os arquivos e os binários foram preparados neste workspace. A configuração
salva contém `install_script` e `start_skill`; publicar o ambiente e testar
uma tarefa nova são etapas separadas. Não foi realizado push para GitHub.
