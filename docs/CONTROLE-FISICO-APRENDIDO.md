# Apoio procedural, controle físico aprendido e caminhada

Esta revisão mantém a locomoção aprovada e acrescenta um controlador muscular
neural pequeno ao Bullet. Ele atua no jogador e na CPU. Não é o Euphoria,
nem uma política de locomoção do corpo inteiro treinada por reforço.

## O que mudou no jogo

Esta correção liga a pose física completa à pose desenhada: inclinação e
deslocamento vertical do quadril acompanham a solução das pernas. Antes,
aplicar apenas as rotações dos membros escondia parte da resposta de apoio.
Os testes novos medem os tornozelos e a direção do tronco depois da mistura
final, em uma partida com 22 jogadores, além das métricas do simulador.

Sem bola, a passada lenta mantém uma fase contínua proporcional à distância
percorrida. Trocar um candidato nativo de movimento não reinicia mais a
passada. O IK orienta o avanço dos pés pela direção real do deslocamento,
inclusive de lado e para trás; a entrada e a saída da caminhada são graduais.
As ações e os contatos com bola continuam com o tempo do seletor nativo.

Um recebedor próximo pode assumir uma chegada alcançável quando a designação
de posse ainda aponta para um colega mais distante. Isso ajusta a aproximação,
sem conceder posse nem ampliar a pele de contato. Todo impacto corporal real
envia seu momento à física e gera uma resposta amortecida de tronco e braços,
inclusive durante outra ação. Repetir contatos não reinicia a resposta do zero.
A recepção também mantém o motor muscular ativo na CPU parada. Corpos caídos
continuam verificando a colisão da bola e recebem seu impulso articulado.

Até 74% do curso do analógico sem RB há uma faixa progressiva de caminhada,
até 1,55 m/s. Acima dela, a velocidade cresce suavemente até a velocidade
normal aprovada; RB continua sendo o comando de sprint. A passada lenta tem
apoio sobreposto e joelhos resolvidos no esqueleto original. O toque inicia a
passada de condução e deixa a bola rolar durante a recuperação. O contato é
recalculado na chuteira dessa pose, sem aumentar a tolerância da colisão.

A caminhada agora também reduz o balanço vertical do corpo, abre os cotovelos
e deixa os braços mais baixos, com contrarrotação suave do tronco. A CPU
seleciona o mesmo ciclo em aproximações lentas. Não há novas capturas externas.

Impactos moderados calculam uma passada de recuperação a partir do déficit de
apoio e da direção do impulso. Um pé levanta e avança; o outro tenta manter
seu apoio, com IK de duas articulações e comprimentos anatômicos preservados.
A trajetória é gerada sem escolher uma animação de tropeço. O pé mais baixo
permanece como apoio quando o outro já está em balanço. O apoio cede de forma
gradual quando a passada nativa avança além do alcance, sem prendê-lo a um
ponto que ficou para trás. Reposicionamentos de cobranças e do laboratório
limpam alvos e momento anteriores. Um braço
buscando uma pegada e corpos muito próximos impedem essa passada livre;
a resposta muscular continua ativa durante a disputa. Há limites de
velocidade, alcance e cruzamento das pernas, além de liberação gradual para
uma ação com a bola. Impactos fortes mantêm as reações protetoras nativas;
perda persistente de apoio ainda pode resultar em queda articulada. O controle
não garante equilíbrio contra qualquer força, nem é o sistema proprietário
Euphoria. Os alvos de apoio nunca são a posição da bola. Ao agarrar, a mão que fez o contato assume o acompanhamento, a partir de sua
pose atual. A continuidade da pegada passa a exigir essa mesma mão. Isso vale
para o jogador e para a CPU, sem trocar de braço nem reposicionar a mão
instantaneamente.

O fôlego humano lê o botão RB a cada passo de simulação. Velocidade pedida
pelo assistente de recepção não equivale mais a apertar RB. Sem RB, o jogador
recupera a reserva, inclusive durante a movimentação normal. A CPU gasta a
reserva quando decide fazer sprint e continua recuperando em apoio mais lento.

Todos os 21 atletas da CPU compartilham o mesmo banco imutável de respostas
protetoras do jogador. A simulação muscular fica ativa quando se movimentam
ou disputam a bola; o modo econômico fica restrito a atletas parados e longe
da disputa. As respostas graduais do tronco e dos braços foram ampliadas,
mantendo os limites anatômicos finais. O impulso de uma disputa corporal não
é mais aplicado também pela antiga camada de proximidade. Companheiros
próximos também têm contato corporal, com intensidade reduzida.

O equilíbrio continua tendo uma camada analítica: estima a distância de
recuperação com a perturbação de velocidade e a frequência de pêndulo
invertido `sqrt(g/altura)`, compara com o apoio e a passada disponível,
compromete um passo de recuperação e só entra em queda após perda de apoio
persistente. A rede controla a resposta muscular angular; não aprendeu
esse planejamento de passos. As duas camadas têm funções diferentes.

Nas recepções previstas, o recebedor designado da CPU orienta o corpo e ajusta
sua aproximação e frenagem antes da chegada. A seleção de domínio continua
nativa. A preparação do corpo também considera altura e tempo de chegada,
e o contato real recruta tronco e braços. Rebotes passivos têm restituição
menor; transições de pose não podem acrescentar uma velocidade muscular de
18 m/s à superfície do jogador.

Cabeceios têm preparação e acompanhamento de tronco/pescoço na referência
nativa, sem alterar a pose do instante exato do contato. A força considera
carga do comando, velocidade da bola e movimento real da superfície da cabeça,
com limites próprios de passe e finalização. A aproximação gradual da mão
do goleiro também foi ajustada para alcançar a trajetória com a pele real,
sem ampliar a tolerância de contato. Não herda a potência de passe
com o pé. Mais jogadores elegíveis podem disputar uma bola aérea, preservando
a prioridade de companheiros melhor posicionados e o contato real.

Uma bolada real nas costas não é mais classificada como domínio de cabeça.
A previsão não cria posse nem toque por proximidade: a pele precisa alcançar
a bola. Bolas fora do alcance ou fortes demais ainda podem escapar.

## Treinamento reproduzível

`tools/animations/train_muscle_policy.py` usa NumPy e busca de políticas pelo
método da entropia cruzada: 55 gerações, 80 candidatos, 12 elites e semente
20261023. A rede tem duas entradas, seis unidades tanh e 18 pesos, sem vieses.
As entradas são erro angular e velocidade angular relativa. A saída é uma
aceleração angular limitada a 140 rad/s².

As referências são curvas de tronco e ombros das animações nativas existentes.
Arquivos distintos alimentam treino, validação e avaliação final. Força,
amortecimento, erro inicial e impactos variam entre os ensaios. O relatório
`config/learned-muscle-policy.json` registra fontes, hashes, parâmetros,
histórico, métricas e pesos; o cabeçalho C++ é gerado com os mesmos pesos.
Não é necessário Python, GPU ou treinamento no computador de quem joga.

Para reproduzir em um ambiente de desenvolvimento com NumPy:

```sh
python3 tools/animations/train_muscle_policy.py
python3 -m unittest discover -s tests -p test_learned_muscle.py
cmake --build build
ctest --test-dir build --output-on-failure
```

Na avaliação reservada, o custo ponderado foi 0,06125, contra 0,13667 do motor
anterior. A variação de aceleração foi 38,69, contra 96,41, e o erro angular
RMS caiu de 0,0591 para 0,0302 rad. Um PD com velocidade relativa corrigida
teve erro menor (0,0168 rad), porém variação maior (166,24) e custo maior
(0,13879). A rede privilegia suavidade; não supera esse PD em precisão.

Essas métricas pertencem a uma dinâmica angular reduzida com perturbações,
não a um treinamento completo do personagem no Bullet. No jogo, os pesos
controlam os motores angulares de acompanhamento e a musculatura superior
durante quedas; inércia, limites de torque e articulações continuam físicos.
Os testes gráficos verificam execução real, limites e recuperação. Não
demonstram reprodução exata de movimentos humanos ou de outra engine.

Uma busca de 75 gerações, com impactos opostos e condições mais amplas,
foi avaliada na revisão anterior. Seu custo caiu ligeiramente, mas o erro e a variação
de aceleração pioraram em relação à rede aprovada. Os pesos foram rejeitados
para execução; o relatório está em `config/muscle-policy-rejected-candidate.json`.
O jogo mantém o modelo descrito acima. A nova plantação dos pés é analítica
com IK, combinada com esse servo neural; não foi aprendida por uma política
de corpo inteiro.

## Pesquisa e fontes primárias

- [DeepMimic: aprendizado de habilidades a partir de referências](https://github.com/xbpeng/DeepMimic): combina imitação com controle físico. O projeto original usa Bullet e TensorFlow; indica MimicKit como sucessor. Fundamenta separar a referência de pose da força muscular aplicada.
- [IsaacGymEnvs](https://github.com/isaac-sim/IsaacGymEnvs): exemplos de PPO, ambientes de treinamento físico paralelos e randomização de domínio. Fundamenta variar condições de treino e reservar trajetórias de avaliação.
- [AMP](https://xbpeng.github.io/projects/AMP/): referência para uma etapa futura de política corporal completa; a página não pôde ser obtida neste ambiente (HTTP 403), portanto não foi usada como código ou modelo.

Os READMEs dos dois repositórios e a licença MIT do DeepMimic foram obtidos
das fontes primárias em 23/10/2026. O coletor
`tools/research/fetch_active_control.py` registra sucesso, tamanho e hash, e
também registra as páginas inacessíveis. Nenhum modelo pré-treinado ou código
desses projetos foi incorporado. A rede desta revisão foi treinada aqui com
o banco nativo. As animações, seleção de jogadas e contato continuam usando
o sistema do Football com as correções anteriores.

## Como observar

Extraia o pacote completo em uma pasta nova. Abra `treino-fisico.bat` e use
R3/Tab para ver o corpo. Compare o analógico em cerca de um terço, metade e
dois terços do curso; observe a barra FOLEGO com e sem RB. F8/Shift+F8/Ctrl+F8
testam impactos crescentes. F2 aproxima um parceiro e M provoca uma disputa.
Em `partida-fisica.bat`, jogador e CPU usam a camada física. F7 compara essa
camada ligada/desligada. Segure **H** e aperte F4/F5/F6 para direcionar um
lançamento de teste a um companheiro controlado pela CPU. H+Ctrl+Shift+F4
afasta a bola para comparar a caminhada sem posse. Esses atalhos só montam
o cenário; os contatos, decisões e reações continuam sendo simulados.
A versão Windows é compilada e verificada aqui;
os testes gráficos automatizados rodam na versão Linux com controle virtual.
