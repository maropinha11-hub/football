# Correção da câmera e das transições

Extraia o ZIP completo em uma pasta nova e abra `treino-fisico.bat`.
`partida-fisica.bat` usa as mesmas correções com dois times. R3/Tab alterna
a câmera para observar o corpo. O controle continua com o mesmo mapeamento.

Esta revisão corrige três problemas identificados na versão anterior:

- Rotações equivalentes com sinais diferentes podiam se anular na interpolação
  ou produzir uma volta longa ao cruzar a direção de trás. A interpolação usa
  agora o arco curto, inclusive nos buffers entre simulação e desenho.
- A câmera era afastada pelos próprios braços e por uma colisão de tronco
  que incluía o pescoço. Agora sua posição e direção vêm da cabeça já desenhada;
  os braços não empurram a câmera. A proteção contra entrar na camisa usa a
  superfície do tronco e uma distância que protege todos os cantos da lente,
  considerando o campo de visão e o formato da tela. O plano próximo é de 2 cm.
- Ler quadros avançados de um clipe percorria os quadros anteriores, com
  alocações temporárias em cada consulta. A leitura agora busca as chaves
  vizinhas diretamente. A busca de movimento também deixa de calcular os
  membros quando precisa apenas da direção futura do corpo.

A velocidade angular usada nas transições é calculada entre dois quadros do
mesmo clipe. A diferença entre clipes misturados deixa de ser interpretada
como uma aceleração do membro.

O encerramento agora espera as notificações de tarefas já marcadas como
prontas antes de liberar o agendador. Isso elimina uma condição de corrida
identificada durante a investigação de uma saída inesperada no teste Linux.
A ocorrência e as repetições posteriores ficam registradas no relatório;
a causa específica daquele encerramento não foi capturada pelo depurador.

O teste de primeira pessoa mede a posição da lente, o alinhamento com a
cabeça e a distância à camisa em condução, viradas, cruzamento, queda e
recuperação. O relatório em `docs/camera-validation.json` distingue a versão
anterior, as verificações novas e os testes de regressão. A compilação Windows
é verificada quanto a executável, bibliotecas e arquivos; os testes gráficos
automatizados são executados na versão Linux. Ainda é necessária a avaliação
visual no seu Windows com o controle real.

As animações e a lógica continuam sendo as da integração nativa atual. Esta
correção não acrescenta novos movimentos capturados nem reproduz o runtime
Unity ou a Euphoria.
