# Recepção, equilíbrio e circulação

Use `treino-fisico.bat` ou `partida-fisica.bat` do pacote completo. A câmera,
o analógico e a condução aprovada continuam sendo a base. Viradas bruscas em
corrida agora carregam o equilíbrio; passos de proteção e quedas dependem da
resposta do corpo articulado. Um marcador próximo, correndo e comprometido
na direção anterior, também pode perder o apoio. Andar e corrigir a direção
levemente não aciona esse desequilíbrio.

O pedido de domínio considera a chegada prevista da bola, altura, aproximação
e disputa da posse. Uma estatística de posse por proximidade não substitui
uma recepção concluída. A CPU prioriza receber uma bola rápida antes de passar.
Os contatos continuam exigindo a pele real do modelo; uma colisão de segurança
não se torna uma recepção automática inventada. Boladas fortes geram carga
física e uma reação de tronco e braços; contatos fracos têm resposta menor.

Na partida, **Ctrl+F6** alterna ensaios de goleiro: cara a cara sem cobertura,
chute no ângulo e recuo intencional. O goleiro fecha o ângulo em situações
descobertas e pode executar uma defesa de tentativa quando não alcança uma
bola que vai ao gol. Essa tentativa não concede contato nem defesa à distância.
Recuos intencionais de um companheiro continuam impedindo o uso das mãos.
**Ctrl+Shift+F6** prepara uma saída curta com linhas livres: a CPU escolhe e
executa o passe pela lógica normal. O ensaio só posiciona jogadores e bola.

A circulação prioriza opções seguras, combinações e a entrada de atacantes
na área quando há bola pelos lados. A condução da CPU longe da área, sem
pressão imediata, evita velocidade máxima constante. Calcanhares ficam
restritos a situações raras: baixa velocidade e força, pressão muito próxima,
longe do próprio gol e intervalo de pelo menos 30 segundos entre contatos.
Os demais passes de costas dão preferência à rotação do corpo.
Uma posse confirmada já pode escolher uma saída curta segura; a seleção não
espera um atraso que deixava passar a oportunidade antes do passe nativo.
A circulação prolongada continua exigindo posse estabilizada.

Perto do gol adversário, uma chegada aérea mantém as opções nativas de
finalizar ou passar de primeira. A assistência não transforma obrigatoriamente
essa oportunidade em domínio. Ao agarrar deliberadamente um adversário, a
assistência de recepção deixa de puxar o jogador para a bola. O analógico e a
tração física continuam ativos; a proteção com posse mantém sua lógica.

Avisos e alterações de placar agora chegam à rotina gráfica por snapshots,
junto com o relógio. O desenho dos textos usa uma só rotina, evitando operações
concorrentes sobre a fonte compartilhada durante reinícios e encerramento.

O catálogo agora tem **6.274 perfis**, em **32 famílias de curvas**, sobre
119 fontes nativas de ações. São 28.632 pares candidatos com espelhamentos.
Não são capturas novas: as pernas, os eventos de contato e as trajetórias
continuam pertencendo às animações e à física do jogo. As variações aumentam
o recrutamento de tronco e braços com limites de rotação e velocidade.

Resultados e limites desta revisão: [refinement-validation.json](refinement-validation.json).
Os testes gráficos usam Linux/X11 com controle Xbox virtual; o pacote Windows
é compilado e conferido separadamente. Não há teste de interface Windows ou
controle físico nesta máquina. Os ensaios finitos não garantem todos os lances
possíveis nem tornam a física uma simulação biomecânica completa.
