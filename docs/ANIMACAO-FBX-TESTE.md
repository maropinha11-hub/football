# Condução nativa e domínio de peito

Extraia o ZIP completo em uma pasta nova e abra `run-training.bat`.

A condução frontal importada DefenseJog não entra mais no catálogo de
candidatos. Todas as direções usam a seleção nativa que já aparecia nas
outras direções em terceira pessoa. O rastreamento identificou principalmente
`ballcontrol/walk/000.anim` e sua versão espelhada; o nome “diagonal” descreve
como o corpo aparece na câmera, não um deslocamento obrigatório de 45 graus.
A versão de pé direito tem preferência entre os candidatos válidos. O teste
de alcance continua podendo escolher outro pé quando necessário numa virada.
O analógico leve conserva a passada nativa lenta; RB conserva a corrida.

As transições passam pela suavização nativa, preservando a pose e os
comprimentos dos ossos, sem reposicionar uma perna instantaneamente até a bola.
Os intervalos mínimos de condução continuam em 420 ms, ou 300 ms com RB.
O relógio físico continua a 100 Hz. O fator de duração das animações é 1,12;
quadros e eventos são retimados juntos, conservando a velocidade do percurso.

## Domínio adicional

`Chest_Stand` e `Chest_Run` continuam disponíveis como camadas adicionais.
Durante o domínio a máscara inclui `middle`, `neck`, ombros e cotovelos. Após
a queda da bola, ombros e cotovelos voltam gradualmente à locomoção nativa.
Pelve, pernas e raiz preservam a locomoção nativa. A inclinação da fonte é composta com a
pelve atual. O deslocamento da raiz dos FBX não é aplicado.

Durante a chegada e a queda após o domínio, o movimento permitido é avançar
ou recuar no eixo fixo da recepção. A entrada lateral não vira o peito para
uma direção sem animação correspondente. Com o analógico solto, a assistência
não deve fazer o jogador caminhar contra a bola ainda alta. Após a queda,
a assistência nativa volta a acompanhar a bola no solo.

A previsão seleciona o gesto; ela não autoriza o impulso sozinha. O evento
exige contato da esfera com a pele na região frontal do peito, dentro da
margem numérica de 2,5 mm, vindo da frente. Cabeça e costas não autorizam esse
evento. Uma trajetória que não encontra o peito conserva as recepções nativas.
A proteção passiva usa a superfície ponderada do modelo e a trajetória
varrida da bola, incluindo o período depois do domínio.

| Tecla | Exercício |
| --- | --- |
| F4 | Passe rasteiro recebido |
| F5, analógico solto | Bola para domínio de peito parado |
| F5, avanço moderado | Domínio avançando |
| F6 | Cruzamento alto |
| R3 / Tab | Alternar câmera |
| R / View | Reiniciar |

RT continua reservado. Os arquivos DefenseJog permanecem arquivados para
rastreabilidade, sem serem carregados como candidatos de gameplay.

## Validação

`training_forward_cycle_smoke.py` verifica cinco direções em terceira pessoa,
pé direito, viradas, cadência e recuperação após RB. `training_upper_body_smoke.py`
verifica máscara de peito, retorno dos braços, preservação das pernas/raiz, ajuste
frente/trás, bloqueio lateral e contato real. Os testes de controles, ações
correndo e regressões completam a conferência. Consulte o relatório
[native-right-foot-reception-validation.json](native-right-foot-reception-validation.json).

Os testes renderizados rodam no Linux com controle Xbox virtual. O pacote
Windows x64 passa por compilação cruzada e verificação de código, DLLs,
recursos e integridade; o teste com Windows 11 e controle físico é local.
