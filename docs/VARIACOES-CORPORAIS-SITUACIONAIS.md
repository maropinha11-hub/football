# Variações corporais durante as jogadas

Registro da revisão `11a818c`. A ampliação seguinte está em
[Sola, ações laterais e respostas aéreas](SOLA-E-VARIACOES.md).

Esta etapa acrescenta respostas de tronco e braços às animações existentes.
Um passe em corrida, com giro do corpo ou pressão próxima, pode recrutar mais
o tronco e abrir os braços para contrabalançar o movimento. A preparação e o
seguimento da ação recebem ajustes graduais; a animação nativa continua
definindo o gesto principal, o deslocamento e o momento do toque.

## Como comparar

Extraia o pacote Windows completo em uma **pasta nova**, entre na pasta
extraída e abra **treino-fisico.bat**. Para observar as mesmas respostas em
uma partida com jogadores da CPU, abra **partida-fisica.bat**.

| Comando | Função |
| --- | --- |
| F1 | Ligar/desligar somente as variações situacionais de tronco e braços |
| R3 / Tab | Alternar a câmera; use a externa para observar o corpo |
| A / B / X no Xbox | Passe / cruzamento / chute |
| RB | Correr |
| F4, no treino | Lançar um passe rasteiro em direção ao jogador |
| F5, no treino | Lançar uma bola para a região do peito |
| F6, no treino | Lançar uma bola alta |
| F7 | Ligar/desligar a camada física experimental inteira |
| F8 / Shift+F8 | Testar um impacto médio / forte |
| Ctrl+F8 | Testar uma sobrecarga, com tentativa de equilíbrio antes da queda |
| F3, no laboratório físico | Mudar a direção do próximo impacto |
| F9 | Iniciar uma queda deliberada de teste |
| R / View | Reiniciar |

Compare primeiro um passe simples parado e um passe em corrida para o lado.
Repita com F1 desligado e ligado, mantendo F7 ligado. Observe a preparação dos
braços, a participação do tronco e a volta à locomoção. F1 mantém o restante
do experimento físico; F7 desliga também os outros componentes dessa camada.

Para testar uma cabeçada, use F6 no treino e peça passe ou chute antes da
chegada da bola. A busca original continua podendo recusar uma bola fora do
alcance. F4, F5 e F6 lançam bolas de teste; a câmera muda por R3/Tab.

Os atalhos **run-training.bat** e **jogar-partida.bat** continuam abrindo a
versão aprovada com a física experimental desligada. A camada desta etapa
depende do experimento físico, inclusive quando F1 está marcado como ligado.

## O que o jogo considera

O contexto usa a velocidade do jogador, a força pedida, a direção da ação em
relação ao corpo, a posição prevista da bola no toque, o pé utilizado e a
proximidade do adversário. Nos passes com um companheiro definido, a pressão
do adversário mais próximo sobre a linha do passe também contribui para a
resposta corporal. Esse cálculo não altera o destinatário nem a decisão de
passe da inteligência artificial.

O perfil regula a intensidade da resposta do tronco, dos braços e do
seguimento. A direção e a dificuldade continuam sendo parâmetros contínuos.
Filtros com limites de velocidade e aceleração suavizam as mudanças; trocar
de perfil não troca instantaneamente a pose inteira.

As categorias registradas na telemetria são:

| Identificador | Ação |
| --- | --- |
| 0 | Sem variação situacional ativa |
| 1 | Passe |
| 2 | Chute |
| 3 | Cruzamento |
| 4 | Cabeceio |
| 5 | Controle de bola / corte |

A condução comum para frente conserva o gesto aprovado. As variações de
controle entram principalmente quando há um corte ou pressão relevante.
Domínios de peito e reações de desequilíbrio não recebem essa sobreposição,
pois já têm seus próprios movimentos. No cabeceio, os ajustes ficam nos
braços, preservando o gesto de cabeça e tronco responsável pelo contato.
Defesas e lançamentos com as mãos, contatos de outras partes do corpo e
estados especiais ou de retenção conservam a cadeia de contato original.

A camada situacional não desloca a raiz do jogador, não altera as rotações
das pernas nem reposiciona o pé de contato. A seleção e o solucionador de
contato nativos continuam responsáveis por escolher uma ação alcançável e
aceitar o toque na malha deformada. As restrições existentes de ombro e
cotovelo continuam sendo aplicadas após a mistura gráfica.

## Banco e origem dos movimentos

O catálogo contém **334 perfis procedurais** sobre um inventário de
**293 arquivos de animação originais**, dos quais **283** entram diretamente
no carregador nativo. Os outros dez são modelos de geração ou animações
omitidas pelo próprio carregador. Esses números não incluem as transições e
cópias que o jogo gera durante a execução.

A auditoria encontrou **627 pares candidatos de fonte e perfil**, ou
**1.254 contando os espelhamentos nativos existentes**. Ela considera o
marcador de contato, a parte do corpo, o alcance e a direção descritos pela
fonte, os limites de potência e os estados especiais. A classificação usa
a geometria auxiliar da fonte; o teste de contato na malha real continua
sendo necessário durante a jogada.

Esses 1.254 pares são combinações candidatas compatíveis com os metadados,
não 1.254 capturas novas nem 1.254 situações exaustivamente validadas. O
registro não multiplica indiscriminadamente todas as fontes por todos os
perfis. Regras conservadoras também limitam os perfis de controle e cabeceio.

O [manifesto do catálogo](../config/situational-motion-catalog.json) separa
fontes, perfis e candidatos. O gerador é reproduzível:

```sh
python3 tools/animations/build_situational_catalog.py --check
python3 tests/test_situational_catalog.py
```

Para inspecionar cada fonte, contato e conjunto de perfis candidatos:

```sh
python3 tools/animations/build_situational_catalog.py --inventory /tmp/situational-inventory.json
```

## Física e limites

O ragdoll Bullet, os passos nativos de apoio, os motores articulares
limitados e o equilíbrio já existentes continuam funcionando. A nova camada
enriquece ações guiadas pelas animações; não substitui esses componentes por
um novo controlador muscular. Os limites da interação entre jogadores e dos
volumes de colisão permanecem descritos em
[Passos de apoio e física na partida](PASSOS-DE-APOIO-E-PARTIDA.md).

Não foram acrescentadas novas sequências capturadas, novas reconstruções
3D por rotoscopia, centenas de milhares de animações gravadas ou uma política
física aprendida. A base permite ampliar respostas situacionais de forma
controlada; obter novas performances independentes ainda exige fontes de
movimento e revisão do retargeting. As referências e suas limitações estão
no [registro de pesquisa desta etapa](situational-motion-research.json).

Os testes de catálogo verificam origem, metadados, combinações válidas,
identificadores estáveis e consulta dos perfis compilada em C++14. Os testes
de movimento medem resposta corporal, continuidade e preservação da raiz e
dos pés. A aceitação final também depende dos testes gráficos de jogadas e
das verificações do pacote feitas para cada versão.

Os testes gráficos automatizados usam a versão nativa Linux com um controle
Xbox virtual. No Windows, a validação em nuvem cobre compilação para x64,
executável, DLLs e recursos do pacote; não equivale à execução gráfica em
Windows com o seu controle físico.

Nesta revisão passaram **314 verificações gráficas em 16 cenários**, incluindo
65 verificações novas em primeira pessoa e 65 em câmera externa. Também
passaram 87 verificações dos solucionadores, 14 testes do catálogo, os sete
testes CTest e 72 verificações dos pacotes. As contagens dessas suítes têm
escopos próprios e não representam capturas ou situações exaustivas.

O [relatório desta versão](situational-motion-validation.json) registra os
executáveis, o ZIP, as medições e as falhas intermediárias corrigidas nos
ensaios. No teste da partida, sete jogadores da CPU produziram 354 amostras
de resposta situacional durante passes e controles, sem deslocamento da raiz
ou dos pés por essa camada. O ensaio explícito de disputa também confirmou
uma reação nativa de corpo inteiro no jogador humano e no adversário.

Capturas da execução real em câmera externa:
[passe parado](images/situational-standing-forward-pass.png) e
[preparação de chute em corrida](images/situational-running-right-shot.png).
