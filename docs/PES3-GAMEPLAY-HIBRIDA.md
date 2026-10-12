# Gameplay híbrida no treino

Esta versão usa as animações PES3 nas jogadas do Football. O usuário autorizou
a integração intermediária: ações, deslocamento, controles, física e contatos
continuam no motor nativo. A escolha de clips é um adaptador novo; não é o
seletor original do PES nem uma recuperação completa de sua gameplay.

## Jogar no Windows

Feche o jogo e extraia **todo o ZIP de atualização dentro da pasta que já usa**,
substituindo os arquivos. Execute **treinar-pes3.bat**. As animações que você
já importou permanecem na instalação. R3/Tab alterna as câmeras. Os comandos
do Xbox e os exercícios de passes, chutes e cabeçadas continuam iguais.

A assistência também foi corrigida para frear após o toque real de controle
quando o analógico é solto com a bola próxima. A velocidade restante da bola
não mantém o jogador andando sozinho; a aproximação antes do toque e a
recuperação de um toque longo distante continuam assistidas.

Uma instalação nova precisa dos recursos do pacote completo e da importação
local por `importar-pes3.bat`. O banco original não é distribuído nestes ZIPs.
`run-training.bat` abre o treino nativo; `estudar-pes3.bat` mantém a inspeção
manual por V/F7–F11. No Linux, execute `--training --pes3-live` no diretório
com os recursos e o banco local.

## Como a integração escolhe e executa movimentos

1. O Football escolhe sua animação considerando a ação solicitada, direção,
   velocidade, pé e situação da bola. Seus eventos físicos permanecem ativos.
2. Na primeira utilização, o adaptador mede 17 poses em cada um dos 1.105
   clips, no esqueleto nativo calibrado da malha. Compara nove poses da jogada
   nativa com as trajetórias candidatas, incluindo direção dos pés/cabeça,
   altura, excursão dos membros e pé responsável pelo contato.
   Compara também a reflexão anatômica no modelo nativo para atender ao outro
   pé. Essa reflexão é uma adaptação própria; mantém a qualidade do pé nativa.
3. A fase do clip acompanha a duração da animação nativa. Quando há contato,
   dois trechos de relógio encontram-se exatamente no instante escolhido pelo
   Football. O ponto de sincronização PES é calculado pelo adaptador; não é
   apresentado como um marcador original recuperado.
4. A camada visual combina 85% da pose selecionada com a pose nativa. Transições
   usam 120 ms do relógio nativo. Próximo do toque, restaura gradualmente a
   perna responsável ou a pose de cabeçada para preservar o alcance original.
   A correção de contato do pé continua ativa. O olhar nativo também permanece.
5. Candidatos incompatíveis mantêm a animação nativa. O resultado é armazenado
   por animação, pé e frame de contato. Renderização recebe uma pose imutável;
   não executa novamente o seletor nem altera a simulação da bola.

O alinhamento conserva comprimentos, orientação e pesos da malha aprovados
na versão anterior. Durante transições, o apoio é recalculado pelo volume dos
pés. Escala visual, limite de compatibilidade e mistura são políticas deste
adaptador, não constantes físicas extraídas do PES. Não se atribuem nomes de
ações a IDs do banco sem evidência.

## Validação

`tests/test_pes3_motion_match.py` verifica o relógio de contato, monotonicidade,
mistura de quaternions antipodais, comprimentos dos membros, apoio no chão,
entrada inválida e fallback. `PES3_TEST_BANK=/caminho/do/banco.fpsa` habilita
também a comparação com os recursos locais recebidos.

`tests/training_smoke.py --build build --output /tmp/resultado --pes3-bank
/caminho/do/banco.fpsa` executa os exercícios completos com eventos SDL reais
e verifica a aplicação automática na malha. A inspeção manual continua sendo
verificada por `tests/pes3_preview_smoke.py`.

O pacote Windows é compilado com MinGW e verificado quanto a arquivos, DLLs e
integridade. A execução gráfica automatizada ocorre no Linux com SDL/OpenGL;
o teste final no Windows com o controle físico depende do computador do usuário.

O [relatório desta versão](pes3-hybrid-validation.json) registra **169 testes
unitários, cinco grupos CTest, 91 verificações do treino e 42 do estudo**,
144 sincronizações de contato e a integridade dos dois ZIPs. As verificações
medem o adaptador híbrido e a gameplay nativa; não comprovam equivalência ao PES.
