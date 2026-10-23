# Controle físico aprendido e caminhada

Esta revisão mantém a locomoção aprovada e acrescenta um controlador muscular
neural pequeno ao Bullet. Ele atua no jogador e na CPU. Não é o Euphoria,
nem uma política de locomoção do corpo inteiro treinada por reforço.

## O que mudou no jogo

Até 74% do curso do analógico sem RB há uma faixa progressiva de caminhada,
até 1,55 m/s. Acima dela, a velocidade cresce suavemente até a velocidade
normal aprovada; RB continua sendo o comando de sprint. A passada lenta tem
apoio sobreposto e joelhos resolvidos no esqueleto original. O toque inicia a
passada de condução e deixa a bola rolar durante a recuperação. O contato é
recalculado na chuteira dessa pose, sem aumentar a tolerância da colisão.

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

Nas recepções previstas, a CPU orienta o corpo para a bola antes da chegada.
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
camada ligada/desligada. A versão Windows é compilada e verificada aqui;
os testes gráficos automatizados rodam na versão Linux com controle virtual.
