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
| Motion matching | Busca em quadros internos da locomoção nativa, trajetória, apoio e continuidade | Indexação e planejamento de ações com bola e disputas, sem perder seus contatos |
| Aprendizagem | Ambiente headless com a mesma implementação Bullet e busca de política por recompensa | Política de corpo inteiro aprovada, com estado articular e tarefas completas de futebol |
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
