# Pesquisa e decisões técnicas

## Fontes consultadas diretamente

1. [vi3itor/GameplayFootball](https://github.com/vi3itor/GameplayFootball),
   `68159a2f0f96eec8ebba26ab7820130f36b922a7`: código, Blunted2 integrado,
   modelos, texturas, banco e animações; README e licença Apache-2.0.
2. [BazkieBumpercar/GameplayFootball](https://github.com/BazkieBumpercar/GameplayFootball),
   `2387eae9ccef1ad1f2144e1acce01893d273aeb6`: versão original, README e
   licença de domínio público/Unlicense. O autor relata problemas de
   arquitetura, multithreading e falta de testes do motor.
3. Headers e bibliotecas SDL2 2.32.4, Boost 1.83 e CMake 3.31.6 do Debian 13,
   obtidos com repositório APT assinado: interfaces GameController,
   IDs de instância, eventos de hotplug e dispositivos virtuais.

O tópico Reddit informado e a API GitHub retornaram bloqueio de proxy
HTTP 403 neste ambiente. Seu conteúdo não foi utilizado como evidência.
As leituras Git HTTPS dos dois repositórios funcionaram. Não foi solicitado
token adicional, nem contornada a política de rede.

## Por que manter o motor

Um personagem genérico com física nova não reproduziria as animações e
o comportamento desta base. O fork atualizado reúne o motor e os recursos
que faltam no repositório descontinuado e migra partes para SDL2. Por isso,
o treinamento reutiliza a implementação nativa, não recria uma bola e um
boneco em uma engine diferente.

Os recursos em `data`, incluindo modelos e animações, são preservados byte
a byte, assim como `animcollection.cpp`. Nesta etapa, `ball.cpp` recebe
correções de contato com o chão e de previsão, `humanoidbase.cpp` adapta a
apresentação do corpo para primeira pessoa e corrige a orientação no reset,
e `humanoid_utils.cpp` diferencia chute carregado de cobertura no treino.
`humanoid.cpp` mantém uma proteção para ausência de oponente e permite
reavaliar a locomoção durante a animação de movimento no treino, inclusive
com posse ou longe da bola. O seletor preserva blend e limites de aceleração;
o intervalo mínimo entre essas revisões passa de 220 para 80 ms. O controle
humano e a simulação de partida são adaptados ao treino solo. Isso reutiliza
o seletor e as animações da base,
mas não significa que toda a experiência do treino seja idêntica à partida
11 contra 11: não existem adversários, assistência a companheiros, fadiga
acumulada ou arbitragem nesse contexto.

## Como a jogabilidade funciona

- A simulação original avança em intervalos de 10 ms, separados da
  renderização. O treinamento conserva esse passo de 100 Hz.
- `HumanController` transforma entrada, direção, força e contexto de posse
  em uma fila de comandos de movimento, domínio, passe, chute ou carrinho.
- `Humanoid` seleciona animações por velocidade, orientação, posição da bola
  e tempo de contato. O motor utiliza blend, correções de trajetória e
  ajustes de contato para sincronizar jogador e bola.
- O toque acontece no quadro de contato da animação. A bola mantém sua
  própria simulação, com gravidade `-9.81`, arrasto, atrito, quique, rotação,
  colisões com traves e rede e previsão de trajetória.
- Os 293 arquivos `.anim` incluem famílias de movimento, domínio, recepção,
  passe, passe alto, chute, defesa, carrinho, queda e movimentos especiais.
  Espelhamento e geração interna produzem outras opções em tempo de execução.
- Algumas famílias pertencem a goleiros, árbitros ou comemorações; sua
  presença no pacote não significa que todas se apliquem ao jogador solo.

## Falhas identificadas e tratadas

| Problema | Diagnóstico | Correção |
| --- | --- | --- |
| Reconexão do controle pode acessar memória fora do array | `event.jaxis.which` é um ID de instância SDL, não um índice contínuo; IDs continuam crescendo | Resolver IDs em slots estáveis e verificar limites antes de acessar arrays |
| Gatilhos Xbox tratados como um eixo combinado antigo | O código usa índices crus de joystick, dependentes de dispositivo e sistema | Usar GameController da SDL2, LT e RT independentes e limiar de ativação |
| Analógico ignora a maior parte do curso | A zona morta original exige 75%; o teste virtual confirma que um comando de 73% é descartado | Zona morta radial configurável, padrão 15%, e velocidade proporcional ao curso útil |
| Estado preso ao perder foco ou remover controle | A entrega de eventos depende de foco e estados não são limpos | Entregar eventos de ciclo de vida e limpar estados |
| Atalhos breves podem ser perdidos | Pressionar e soltar entre duas leituras deixa apenas o estado final solto | Guardar e consumir bordas de tecla para os atalhos de treino, ignorando repetição automática |
| Jogo presume dois times cheios e árbitros | Desreferências de oponente e seleção tática não fazem sentido com um único jogador | Time de treino com um atacante, oponente vazio, guardas e fluxo solo sem arbitragem |
| Treino perde referências ao repor a bola | Reset original escolhe o primeiro jogador do elenco, que não é ativo no treino | Manter o jogador ativo como referência de posse |
| Build rootless não encontra headers e bibliotecas de desenvolvimento | Debian usa headers multiarch e alguns symlinks apontam a bibliotecas já instaladas | Prefixo APT local verificado, includes multiarch e vínculos aos runtimes existentes |
| Recursos dependem do diretório corrente | Caminhos são relativos a `media` e `databases` | Preparar diretório de execução e fornecer script que inicia nele |
| Direção do corpo incoerente após reiniciar | Reset restaurava a direção global sempre para -Y, mesmo quando o jogador era colocado de frente para +X | Restaurar direção e ângulo do corpo a partir da orientação do exercício |
| Bola penetra no chão por um tick | O impacto era verificado antes de avançar a posição | Resolver a penetração também após a integração de cada passo |
| Bola atravessa o jogador no treino solo | A colisão original depende de toque recente de um adversário | Varredura contínua contra cápsulas de pernas, tronco e cabeça |
| Chute carregado permanece baixo | Elevação original segue contexto de animação e atributos | Carga determina velocidade e elevação; LB seleciona cobertura separada |

Outras falhas encontradas na execução e os resultados reais dos testes são
registrados em `docs/VALIDATION.md`. Uma falha futura requer diagnóstico e
teste específico; não há evidência suficiente para afirmar ausência de
todos os defeitos na base inteira.

## Limites e próximas decisões

Os links não incluem a implementação do PES nem indicam uma versão e
configuração de referência. Reproduzir exatamente PES exigiria dados
comparáveis de entrada, movimento, animações e contatos de uma referência
específica. Esta entrega preserva e testa Gameplay Football.

O treino solo permite testar locomoção, aceleração/frenagem, condução,
passes, chutes, carrinhos e situações aéreas. Duelo, desarme contra um
adversário, goleiro e passe com recebedor precisam de exercícios adicionais
com outros jogadores. Primeira pessoa foi integrada com movimento relativo à
visão sem bola, direção de condução independente do olhar com bola e retorno
gradual da cabeça. O treino de falta é parado, sem barreira ou goleiro.
Carreira e online continuam para etapas posteriores.

A validação virtual verifica o caminho de entrada. A avaliação de latência,
rumble, Bluetooth, sensação do movimento e desempenho na GPU do usuário
continua exigindo teste com o Xbox Series S no computador de destino.
