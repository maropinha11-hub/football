# Gramado, recepção e disputas

Esta revisão mantém a locomoção aprovada e a câmera em primeira pessoa.
`treino-fisico.bat` abre o laboratório; `partida-fisica.bat` usa os mesmos
contatos de pele, bola, equilíbrio e variações corporais nos 22 jogadores.
Os atalhos `run-training.bat` e `jogar-partida.bat` mantêm a camada corporal
experimental desligada.

- **G:** compara gramado irregular e liso. A superfície estática tem pequenas
  alturas, normais e resistência espacial; o mesmo cálculo participa da
  previsão e do movimento real da bola. Contatos dissipam energia.
- **F4:** passe recebido; **Shift/Ctrl+F4:** passe deslocado lateralmente.
  **Shift+F5:** bola forte no peito; **Ctrl+F5:** bola na barriga.
  A assistência mantém a interceptação nativa em vez de anulá-la com o
  analógico centralizado. De costas, receber uma bola rápida exige virar;
  bolas lentas e próximas ainda admitem um controle difícil.
- **Na partida, A sem bola:** bote em pé. **B sem bola:** carrinho. Acertar as pernas
  pode causar passo de recuperação ou queda; velocidade, direção, contato
  recente na bola e entrada por trás influenciam a reação e a arbitragem.
  Uma tentativa sem contato não derruba automaticamente ninguém.
- **LT/L2:** protege com a bola e tenta agarrar sem ela. CPU utiliza a mesma
  mão com alcance limitado e forças recíprocas; segurar excessivamente pode
  gerar falta e, dentro da área, pênalti.
- Na partida, **F2** aproxima um adversário; **Ctrl+F2** coloca-o à frente
  para testar botes e carrinhos; **F11** põe a bola nele;
  **Shift+F11** põe a bola no humano; **B no teclado** solicita uma tentativa
  de agarramento pela CPU próxima. São montagens explícitas do laboratório.
- **F10 na partida:** alterna ensaios de falta, pênalti, escanteio, lateral e
  tiro de meta. O humano cobra as reposições do seu time; a saída inicial
  continua automática pela CPU. Os botões normais realizam a cobrança.
- **RT/E sem bola na partida:** pede passe. A CPU avalia pé, lançamento
  adiantado e bola por cima conforme corrida, linha de passe e espaço.

A partida padrão tem dois tempos de 45 minutos reais. É possível reduzir
`player_match_half_seconds` em `training.config` para testes rápidos.
O nível máximo e a organização nativa são preservados, com escolhas adicionais
para saída segura, chutão sob pressão, cruzamento, chute de fora e devolução
em combinação. Passes de costas dão preferência à rotação do corpo quando
há tempo. O goleiro examina a trajetória tridimensional para identificar
bolas que realmente cruzam o gol e saídas possíveis em cruzamentos.

O catálogo contém **3.691 perfis**, incluindo o neutro, em 15 famílias de
curvas procedurais. Novas famílias incluem amortecimento, controle orientado,
cabeceio reativo, voleio, batida externa e força com o peito do pé. Os
14.718 pares candidatos com espelhamentos não são animações capturadas
novas nem prova de cobertura de todas as situações. As pernas e os eventos
de contato continuam sob responsabilidade das animações nativas; o ajuste
de tronco e braços não estica o pé até uma bola inalcançável.

Os testes executam o jogo Linux com renderização X11 e controle Xbox virtual.
O executável Windows é compilado e seu pacote portátil é verificado; esta
máquina não executa a interface do Windows nem um controle físico. O corpo
articulado, as cápsulas de membros e a roupa continuam aproximações físicas,
com mistura de animações e motores limitados. Esta revisão não promete
colisão perfeita em toda combinação possível nem uma reprodução do PES.

A validação e o teste de 40 alternâncias de física com reinícios estão em
[pitch-disputes-validation.json](pitch-disputes-validation.json). Todos os
cenários finais registrados usam o mesmo executável. Reinícios e publicação
de poses agora compartilham a sincronização usada pela leitura gráfica.

A comparação de velocidade do RT usa partidas independentes com a mesma
semente e gramado liso; o gramado irregular é testado separadamente. O ensaio
de agarramento usa a posse no parceiro e exige desaceleração mensurável,
força recíproca limitada e soltura por perda efetiva de alcance, escape ou queda.
O braço não pode continuar preso fora do seu alcance.

Capturas durante os testes: [passe lateral](pitch-running-pass.png) e
[chute lateral](pitch-running-shot.png).
