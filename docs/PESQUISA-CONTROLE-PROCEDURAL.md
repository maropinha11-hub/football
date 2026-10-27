# Controle físico e aprendizagem para futebol

## Diagnóstico e implementação desta etapa

O controlador anterior transporta o corpo no referencial da trajetória nativa
e prende quadril e chuteiras durante o acompanhamento. Acrescentar inclinação,
IK ou variantes de poses não o transforma em locomoção física aprendida.
O experimento novo separa a referência, o motor e o corpo resultante:

| Componente | Implementado | Ainda necessário para o objetivo completo |
| --- | --- | --- |
| Referência procedural | Passada geométrica e postura no esqueleto nativo | Habilidades geradas para todas as jogadas |
| Corpo livre | 13 segmentos dinâmicos, 12 articulações, solas finitas, músculos limitados e proteção de queda | Recuperação e locomoção robustas em todas as condições |
| Motion matching | Busca experimental de quadros internos; retirada do corpo livre após reprovação de equilíbrio | Indexação e planejamento de ações com bola e disputas, sem perder seus contatos |
| Aprendizagem | Ambiente Bullet headless, ARS anterior e três campanhas PPO com estado articular | Política de corpo inteiro aprovada, com estado articular e tarefas completas de futebol |
| Comparação | F12 no treino solo e caminho anterior preservado | Implantação do controlador livre nos 22 jogadores após aprovação |

O novo motor não escreve transformações durante o acompanhamento, não usa
quadril cinemático e não sustenta a massa com uma força externa oculta.
Transformações só são configuradas na montagem/recolocação explícita. Os
motores são resolvidos com contatos e restrições pelo solver de impulsos.
Uma tentativa inicial com PD explícito/compensação aproximada apresentou
oscilação das chuteiras e quedas em repouso e foi substituída. O feedback de
tornozelo usa centro de massa extrapolado; o apoio continua dependendo do chão.

## Fontes consultadas

- [MimicKit](https://github.com/xbpeng/MimicKit): treinamento por imitação,
  DeepMimic, AMP e habilidades latentes. O README documenta referências,
  simuladores, avaliação separada e milhares de ambientes paralelos. Um
  checkpoint de outro humanoide não é diretamente compatível com nosso rig.
- [DeepMimic](https://github.com/xbpeng/DeepMimic) e seu
  [controlador implícito](https://github.com/xbpeng/DeepMimic/blob/master/DeepMimicCore/sim/ImpPDController.cpp):
  alvos articulares, dinâmica e treinamento de imitação. O próprio projeto
  recomenda MimicKit como sucessor. Não foi importada uma política pronta.
- [SkillMimic](https://github.com/wyhuai/SkillMimic): habilidades humanas com
  uma bola, usando demonstrações de interação corpo–objeto. É basquete,
  não futebol; sua contribuição aqui é incluir o objeto e seus contatos na
  aprendizagem, em vez de imitar somente o corpo. Não usamos seus checkpoints.
- [Motion-Matching de Daniel Holden](https://github.com/orangeduck/Motion-Matching):
  busca por pose/velocidade/trajetória e continuidade por inertialização.
  Motion matching escolhe uma referência; ele não resolve equilíbrio físico.
  O README distingue a licença MIT do código da licença mais restrita do
  banco de demonstração. Nenhum banco externo foi incorporado nesta revisão.
- [MuJoCo Playground, OP3](https://github.com/google-deepmind/mujoco_playground/blob/main/mujoco_playground/_src/locomotion/op3/joystick.py):
  observações, comandos de velocidade, impulsos de teste e penalidades de
  orientação, energia, variação de ação e deslizamento. É controle de um
  robô, não uma política de futebol humano que possamos simplesmente copiar.
- [LocoMuJoCo](https://github.com/robfiras/loco-mujoco): imitação e modelos
  biomecânicos, avaliação de trajetórias e randomização. A estrutura de
  benchmark é útil; conjuntos e modelos têm requisitos e licenças próprios.
- [SoccerKicks](https://github.com/nayariml/SoccerKicks) e a
  [análise visual já registrada](fluid-reception-research.json): pé de apoio,
  rotação do tronco, contramovimento dos braços e troca de apoio após o chute.
  A observação 2D de um chute não prova uma biblioteca 3D completa de futebol.
- [IHMC ICPController](https://github.com/ihmcrobotics/ihmc-open-robotics-software/blob/develop/ihmc-common-walking-control-modules/src/main/java/us/ihmc/commonWalkingControlModules/capturePoint/controller/ICPController.java):
  suporte viável e velocidade do centro de massa; referência anterior
  registrada em [fluid-reception-research.json](fluid-reception-research.json).

As tentativas de acessar o artigo de futebol da Science Robotics, páginas
externas e alguns PDFs retornaram 403; PHC retornou 404. Seus conteúdos não
foram tratados como artigos lidos. URLs, respostas e hashes dos materiais
efetivamente obtidos estão em [procedural-controller-research.json](procedural-controller-research.json).
Euphoria é uma tecnologia proprietária: o objetivo é um controlador físico
independente com comportamentos comparáveis, não uma cópia exata de seu código.

## Aprendizagem executada e resultado

O executável `fullbody_lab` usa o mesmo corpo e os mesmos motores do jogo,
sem renderização. A política candidata tem 12 observações globais e 36 saídas
residuais para as articulações. ARS compara retornos de rollouts físicos;
não são rótulos produzidos por um pêndulo nem ajuste a exemplos de PD.

Foram testadas quatro campanhas, com 120, 120, 150 e 200 épocas. A última
incluiu impactos no treinamento e seleção por retorno em múltiplas condições.
As sementes de teste são distintas das de treinamento. O critério exige
sustentação por mais de 95% da sequência, orientação e erros articulares
limitados em todos os testes de 0, 15 e 30 N.s. Nenhum candidato passou.
O último relatório e pesos rejeitados estão em
[fullbody-policy-candidate.json](../config/fullbody-policy-candidate.json).

Esse relatório descreve o motor experimental anterior ao feedback de apoio
mais recente. `fullbody_lab --legacy-v1` reproduz essa configuração. Os pesos
rejeitados não são carregados pelo jogo. A melhoria de apoio posterior é
controle procedural testado, não uma alegação de que o treinamento funcionou.

Para repetir a campanha registrada:

```bash
cmake --build build --target fullbody_lab -j3
python3 tools/animations/train_fullbody_policy.py --legacy-v1 \
  --executable build/fullbody_lab --output /tmp/fullbody-policy \
  --epochs 200 --directions 32
```

O arquivo de política só pode ser promovido se o conjunto separado passar.
O código gerado não substitui automaticamente uma política do jogo.

## Estrutura necessária para a gameplay aprendida completa

1. **Imitação no corpo nativo.** Exportar movimentos existentes com raiz,
   rotações, velocidades e eventos de contato; validar eixos, comprimento dos
   ossos e ausência de interpenetração inicial. Separar famílias de clips
   entre treino e teste, incluindo espelhamentos na mesma família.
2. **Observação articular completa.** Orientação/gravid​​ade, velocidades da
   raiz, rotações e velocidades das doze articulações, contatos dos pés,
   estado da bola relativo ao corpo, previsão de chegada, objetivo da ação
   e contatos com adversários. As 12 observações do ensaio atual não bastam.
3. **Política de baixo nível.** PPO por imitação/AMP, ações residuais limitadas
   sobre alvos articulares e torques limitados por articulação. O corpo só
   recebe gravidade, contatos e esforços internos. As animações são exemplos
   de estilo e execução, não trajetórias obrigatórias da raiz.
4. **Currículo.** Equilíbrio e recuperação de perturbações; caminhar, parar,
   andar de lado e de costas; correr, frear e virar; levantar em posições
   distintas; depois receber, conduzir, passar, chutar, cruzar e cabecear.
   A bola e o adversário precisam estar na simulação de treinamento das
   respectivas habilidades. Treinar só locomoção não ensina domínio de peito.
5. **Recompensas e contatos.** Imitação de pose/velocidade e extremidades,
   sucesso da jogada, apoio e equilíbrio; penalidades de esforço excessivo,
   mudança brusca de ação, pés deslizando e interpenetração. Não recompensar
   tocar a bola sem contato nem teleportar o membro para garantir acerto.
6. **Generalização.** Variar direção/velocidade/altura da bola, gramado,
   atrito, massa, impulsos e oponentes. Avaliar trajetórias e ações fora do
   treinamento, tempo real com 22 jogadores, recepção, quedas e retomadas.
7. **Seleção de alto nível.** Motion matching/plano de contato propõe uma
   referência viável e o controlador aprendido a executa. A escolha de
   referência e a simulação física permanecem componentes distintos.

Este é o trabalho que falta para chamar o sistema de gameplay totalmente
procedural com aprendizagem completa. Os modelos reduzidos existentes e uma
contagem de variantes de pose não substituem essa etapa.


## Correção de fase e resultados da nova etapa

O modo apoiado estava combinando uma passada gerada em um relógio independente
com a trajetória nativa. Isso alterava os apoios sem alterar a trajetória que os
transportava. Agora o modo 1 mantém o movimento nativo, suavizando somente
saltos de pose, sem deslocar os contatos das jogadas. A reavaliação no mesmo
instante reutiliza o deslocamento de continuidade e não avança o filtro.
A pose física e a pose reconstruída pela renderização também usam a mesma
referência original: calcular o aditivo sobre a referência já filtrada anulava
a suavização na imagem e deixava contato e corpo em posições diferentes.

No corpo livre, trocar diretamente de uma animação com pé levantado para
controle dinâmico não estabelecia apoio. A entrada usa postura inicial com
solas apoiadas, preparo de 0,85 s e entrada progressiva de 0,5 s. O limite
experimental de velocidade de referência é 0,55 m/s. Isso é uma correção de
inicialização, não uma aprovação da caminhada nem um atraso imposto ao modo
nativo. A busca de quadros internos foi desligada nesse corpo: escolher uma
pose próxima não prova que a troca de apoio é viável.

### Pesquisa adicional e controles reprovados

Foram obtidos e lidos os exemplos de [marcha horizontal do pymanoid](https://github.com/stephane-caron/pymanoid/blob/master/examples/horizontal_walking.py)
e seu [modelo centroidal](https://github.com/stephane-caron/pymanoid/blob/master/pymanoid/centroidal.py).
Eles separam apoio duplo, apoio simples, previsão de centro de massa e
trajetória do pé livre. Foram novamente consultados o controlador implícito
DeepMimic e o controle OP3 do MuJoCo Playground. URLs e hashes estão em
[procedural-balance-research.json](procedural-balance-research.json).
Os endereços tentados do artigo SIMBICON retornaram 403/404; não foram lidos.

Foram ensaiados planejamento geométrico de passos e controle inverso do corpo
flutuante com contatos e limites de esforço. Não produziram equilíbrio
confiável e foram retirados do código de execução do jogo. Os experimentos
reprovados estão em `tools/animations/experiments/`, sem entrar na compilação.
O modelo menor de massa, Jacobianos e termos de gravidade foi mantido como
instrumento de validação: comparado ao Bullet em 21 casos isolados de queda
livre/torque interno, apresentou erro máximo de aceleração abaixo de 0,05.
Esse teste não aprova o controlador de contato, a marcha ou a aparência humana.

### PPO de corpo inteiro realmente executado

O novo `fullbody_environment` simula os mesmos treze segmentos e motores do
Bullet. A raiz e as duas chuteiras continuam dinâmicas. Não existe transporte
cinemático nem força de sustentação externa. O processo recebe ações por
pipes locais e devolve observação, recompensa e término do episódio.

A observação tem 148 componentes: gravidade no corpo, velocidade da raiz,
velocidade angular, rotações e velocidades das doze articulações, referência
articular, comando, fase, altura, presença de contato nos pés e ações
anteriores. A rede ator tem duas camadas de 128 unidades e 20 canais residuais
em tronco, braços, pescoço e pernas. A rede crítica aprende o retorno.
O PPO usa clipping, GAE, episódios separados e sementes de teste distintas.
As ações são filtradas e executadas como alvos articulares limitados; não
movem o corpo por atribuição de coordenadas.

Foram concluídas campanhas de **999.424, 2.998.272 e 1.499.136 decisões**
a 50 Hz. Cada decisão contém dois controles a 100 Hz, cada um com dois
subpassos físicos. O primeiro ensaio manteve o feedback antigo do tornozelo;
os posteriores o retiraram do caminho de ação aprendida para evitar dois
controladores concorrentes. O terceiro também alinhou a sola da referência
com o chão. Nenhum desses candidatos foi carregado pelo jogo.

A avaliação separada mostrou que sobreviver em pé era uma solução local:
os dois últimos candidatos avançaram aproximadamente entre -4,1% e 2,9% da
distância pedida, em vez dos 70% exigidos, e quase nunca trocaram o apoio.
Por isso foram reprovados, mesmo sem cair nesses testes. Relatórios completos:
[fullbody-ppo-candidates.json](../config/fullbody-ppo-candidates.json).
Os checkpoints e os fontes de treinamento foram arquivados no pacote de
pesquisa `artifacts/football-physical-learning-research.zip`, fora do ZIP do jogo.

Treinamento opcional em Linux, com NumPy e PyTorch para CPU instalados:

```bash
cmake --build build --target fullbody_environment -j3
python3 tools/animations/train_fullbody_ppo.py \
  --executable build/fullbody_environment --output /tmp/football-ppo \
  --steps 3000000 --level .3 --auto-curriculum --reference-variant flat-soles
```

O treinamento usa referências geométricas e ainda não é imitação completa do
banco nativo nem aprendizagem de interação com bola/adversários. O próximo
currículo precisa incluir movimentos de referência e inicialização de fases
viáveis, penalidade de deslizamento e avaliação de transferência de peso,
seguindo a estrutura de imitação acima. Rodar mais épocas do mesmo ensaio sem
medir avanço não resolve essa lacuna. Corrida, frenagem, viradas, levantar e
habilidades de futebol continuam sem política de corpo inteiro aprovada.

No jogo entregue, o início em apoio e as transições nativas são correções de
controle procedural; **a gameplay 100% procedural e aprendida não está pronta**.


### Recepção após reiniciar uma tentativa

A regressão gráfica encontrou um problema independente da aprendizagem:
`GetLastTouchTeam()` tem um fallback histórico para a equipe 0, e o getter
não tipado do último jogador herdava esse fallback mesmo com o identificador
de último toque em -1. Assim, uma nova bola lançada no treino podia continuar
atribuída ao chutador anterior da equipe 0. A CPU não preparava a recepção
prioritária até ocorrer um choque passivo no joelho.

A consulta do jogador agora retorna vazio quando o toque não tem equipe
conhecida, mantendo o fallback tático da equipe. O ensaio sequencial foi
reforçado para exigir `last_actor=-1` na nova bola. No cenário que falhava,
a CPU passou a escolher o cabeceio na criação do passe e tocou com a cabeça,
sem a colisão passiva que precedia a resposta. Reposições e goleiros entram
na validação adicional por também consultarem esse estado.
