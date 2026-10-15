# Partida com um jogador fixo

Extraia o ZIP completo numa pasta nova e abra **jogar-partida.bat**.
`run-training.bat` continua abrindo o treino aprovado.

São onze jogadores contra onze. Você controla o mesmo jogador do treino;
os outros dez companheiros, os onze adversários e os goleiros usam a IA
original. A seleção não troca automaticamente quando a posse muda. A câmera
em primeira pessoa e os controles aprovados acompanham seu jogador.

| Comando | Ação |
| --- | --- |
| RT / E | Pedir passe quando estiver sem bola |
| A | Passe |
| X | Chute; segurar aumenta a carga |
| LB + X | Cobertura |
| B | Passe alto / cruzamento |
| RB | Corrida |
| Analógico direito | Olhar |
| R3 / Tab | Alternar câmera |
| Menu / P | Pausar |
| View / R | Reiniciar a partida e zerar o placar |
| Esc | Fechar |

O pedido dura até 4,5 segundos. Um companheiro com a posse tenta executar um
passe pela animação e pelo cálculo originais; procure uma linha livre.
O adversário pode interceptar. Segurar RT não dispara pedidos repetidos.
Com a bola, RT não altera a condução.

Há dois tempos de três minutos reais de bola em jogo, com relógio de 45 e
90 minutos. Gols, laterais, escanteios, tiros de meta, faltas e impedimentos
usam o fluxo original. A CPU cobra as reposições; seu jogador continua fixo.
O intervalo segue automaticamente para o segundo tempo, com troca de lados.
A partida termina após o segundo tempo, inclusive se houver empate, e mantém
o placar na tela. R/View começa outra partida.

## Integração

O modo `--player-match` mantém `training_mode` para os comandos e as animações
aprovadas, mas executa o ciclo de partida original: dois times, estratégias,
funções táticas, posse, árbitros, relógio e placar. `trainingPlayer` identifica
separadamente o ator fixo; `designatedPossessionPlayer` continua disponível à
IA para acompanhar a disputa pela bola. A atribuição do controle humano é
fixa, inclusive durante reposições e reconexão do controle.

O banco nativo e a cadência aprovada são compartilhados. A seleção de
condução prioriza candidatos alcançáveis de pé direito. A CPU conserva seus
cálculos originais de aproximação e domínio. A camada adicional do peito,
a cabeça seguindo a câmera e os contatos ajustados do protótipo continuam
no jogador controlado. A captura de contato não é repetida por outros atores
sobre os marcadores compartilhados do banco de animações.

RT é lido diretamente para o pedido, mantendo desativado o antigo modificador
de condução. A solicitação adiciona uma opção de passe ao controlador da CPU;
a bola só recebe o impulso no evento de toque normal da animação.

`player_match_half_seconds`, em `training.config`, define a duração de cada
tempo (180 por padrão). `simulation_seed` pode ser definido para reproduzir
uma investigação; sem essa propriedade, o jogo conserva a semente de relógio.
Os testes usam tempos curtos para atravessar os dois períodos e o apito final.

## Verificação

`tests/player_match_smoke.py` executa a partida renderizada com um Xbox virtual:
22 jogadores, controle fixo, movimentos da CPU nos dois times, pedido por
RT/E, execução de passe, câmeras, dois tempos, fim do relógio e reinício.
Os testes do treino continuam verificando a base aprovada. O relatório
[player-match-validation.json](player-match-validation.json) registra os resultados.

A execução gráfica é verificada no Linux. O Windows x64 é compilado e o pacote
é conferido quanto a código, DLLs, recursos e integridade. A execução com
Windows 11 e seu controle físico deve ser feita no seu computador.
