# Base aprovada recuperada

Extraia o ZIP completo em uma pasta nova e abra **treino-fisico.bat**.
Use **partida-fisica.bat** para testar com os dois times. R3/Tab alterna a
câmera; F1 permite comparar as variações de corpo. Não copie pastas de outras
versões e não precisa importar o PES.

A base é o executável que você enviou: 7.486.959 bytes, SHA-256
`23230593d0f2735381a5522e21c71abc4977f76d32352bee814ebd096b4a30a3`.
Ele é byte a byte igual ao pacote do commit `fa0dfa6`.

O banco de animações, as velocidades, a cadência e a entrada original dos
clipes foram recuperados dessa versão. Os clipes de locomoção do pacote
Unity foram retirados; o carregador também ignora essa pasta caso sobrem
arquivos de uma instalação antiga. A troca usa a suavização nativa por um
intervalo um pouco maior, sem mudar a velocidade comandada pelo analógico.

Foram mantidas as correções de passe para trás, comandos de primeira,
disputas de cabeça, cobranças autorizadas após o apito, apoio do lateral,
botes/carrinhos, decisões dos goleiros e câmera presa à cabeça renderizada.
Passe curto para trás com toque breve prefere o calcanhar; carregando mais,
o jogador vira para passar. A bola continua exigindo contato real.
O ponto de contato do calcanhar mira a parte traseira da chuteira, evitando
que o passo de preparação desloque a bola antes do passe.
Quando a trajetória prevista ainda cruza a bola durante essa preparação,
o corpo faz um pequeno ajuste lateral planejado, de até 24 cm. O ajuste
começa e termina em zero e conserva o contato final; a colisão continua ativa
e a perna não é esticada independentemente para alcançar a bola.

A colisão de recepção considera a bola **e o corpo em movimento** durante
o passo de simulação, incluindo a velocidade da superfície atingida. A
condução já controlada no chão continua com a lógica aprovada para evitar
introduzir as antigas rebatidas entre as próprias pernas.

O catálogo contém **11.323 perfis procedurais**, em **80 famílias**, sobre as
animações nativas. As novas estratégias incluem apoio no voleio e meio
voleio, absorção/saída de cabeça e peito, apoio de coxa/canela, cortes,
passe virando e cruzamento em corrida. Quinze estilos de contato ajustam a
recrutação de tronco e braços conforme a jogada, mantendo as pernas, o
evento de contato e o deslocamento nativos. Não são 11.323 capturas novas.
As 80.118 combinações de metadados, incluindo espelhamentos nativos, são
candidatos compatíveis, não uma validação visual exaustiva.

O equilíbrio recebe uma resposta gradual adicional do tronco e dos braços
em cortes rápidos e impactos, sem substituir a passada. Quando o apoio é
superado, o ragdoll e as animações originais de levantar continuam atuando.

O apoio também recruta quadril e joelhos após a ação e sob perturbações:
uma compressão muscular amortecida cede sob o peso e recompõe a postura.
IK de duas articulações conserva a posição e a orientação das chuteiras,
sem substituir a direção, a passada ou a velocidade horizontal comandada.
A preparação do próximo toque reduz essa resposta; os domínios de peito
conservam sua composição específica. Nas quedas, os motores articulares
mantêm esforço muscular e os braços procuram apoio no chão.
É um protótipo próprio de comportamento físico ativo com Bullet, inspirado
nesse tipo de reação corporal; não incorpora a tecnologia Euphoria do GTA IV.

Há também **56 variantes geradas de ações nativas**, com contato de parte
interna/externa da chuteira, bico e peito do pé com pouco giro. Elas ajustam
tornozelo, tronco e ombros; preservam raiz, quadril, joelhos e tempo de contato.
O seletor mantém as ações originais como alternativas e só confirma o toque
quando a superfície da chuteira alcança a bola. As variantes não são capturas.

O analógico leve usa uma passada de caminhada entre os toques, com apoio
sobreposto dos pés e pouca elevação durante o balanço. Essa passada é gerada
no esqueleto nativo; os clipes que acertam a bola conservam seus contatos.
A velocidade com o analógico todo puxado e a corrida com RB continuam iguais
enquanto há fôlego. O toque breve no A ganhou força inicial (aproximadamente
5–7 m/s), com aumento gradual até cerca de 22 m/s conforme a carga.
O som artificial dos passos foi retirado; respiração, ambiente e impacto da bola
continuam ativos.

A barra **FOLEGO** aparece embaixo. RB gasta a reserva de sprint tanto do
jogador quanto dos 21 atletas da CPU. Quando ela acaba, a velocidade máxima
cai gradualmente; caminhar ou parar recupera mais rápido do que trotar.
Não é necessário esperar encher tudo para voltar a correr. Uma pequena faixa
de recuperação evita alternar corrida e trote a cada quadro ao segurar RB.
A CPU poupa fôlego em deslocamentos de apoio longe da disputa imediata.

Passes, cruzamentos, finalizações, voleios e cabeceios na física experimental
derivam a rotação do ponto real da superfície atingida e do impulso aplicado.
Contatos laterais opostos produzem curvas opostas; bater acima ou abaixo
muda o efeito vertical. A previsão e o voo usam a mesma integração existente.
Não é uma simulação aerodinâmica perfeita nem uma reprodução do Euphoria.
As conduções e mudanças de direção recrutam mais tronco e braços, com as
mesmas restrições anatômicas e sem alterar o instante do toque.

A CPU também pode disputar de cabeça perto do gol quando não há outra
finalização já preparada. Um contato corporal real durante a disputa aérea
carrega mais o equilíbrio; a perda de apoio decide se ocorre queda. Bolas
alcançáveis numa animação de agarrar podem ficar nas mãos do goleiro; boladas
mais fortes exigem espalmar. O desvio procura tirar a bola do centro do gol.

Nas bolas paradas, os jogadores fazem deslocamentos curtos para oferecer
opções antes da cobrança. O goleiro procura a trajetória dos recuos para
receber com os pés; a escolha do mergulho considera o lado da bola no
instante em que a animação pode alcançá-la, incluindo seu deslocamento durante
a preparação. Ctrl+F6 na partida alterna onze ensaios: cara a cara, ângulo,
três recuos próximos, duas finalizações laterais, duas centrais e dois recuos
mais rápidos e deslocados.

A volta da animação de levantar preserva o histórico de pose e de contato,
evitando uma amostra inválida do esqueleto na transição para ficar em pé.

F4: passe recebido; F5: bola no peito; F6: cruzamento alto. F8/Shift+F8/Ctrl+F8
testam impactos; F9 testa queda. F10 na partida prepara as bolas paradas.

O relatório técnico `docs/approved-base-validation.json`, no repositório,
registra os testes executados e suas limitações. Os testes gráficos usam
Linux com controle Xbox virtual; o pacote é compilado e verificado para
Windows, e a avaliação com o controle físico continua sendo feita no seu PC.

Nesta revisão, o apoio resolvido das pernas é preservado até a pose final;
a camada de tronco não pode mais sobrescrever os joelhos e os pés. Nos passos
laterais e para trás, um apoio curto no chão limita o deslizamento sem mover
a raiz ou prender o pé durante uma ação com bola. A aceleração também carrega
o controlador de equilíbrio, além dos impactos externos.

Recepções reais na pele podem amortecer a bola com coxa, canela, peito,
cabeça e chuteira. A resposta depende da velocidade e da orientação; bolas
fortes ou fora do alcance continuam podendo escapar. A previsão de recepção não cria
um toque por proximidade: o impulso de domínio exige contato na geometria.

A autorização do árbitro bloqueia a ação do cobrador, preservando as corridas
dos demais jogadores desde a preparação. O goleiro procura uma linha estável
para receber o recuo, sem avançar demais e passar da bola. As tentativas de
defesa consideram lado, altura e tempo de chegada; o mergulho especulativo
não deve cancelar uma interceptação com os pés já preparada.

A CPU recebeu uma opção de ultrapassagem pelo lateral no lado da bola,
respeitando a linha de impedimento. A circulação segura pode sair antes,
e há um pouco mais de abertura para chutar de longe com espaço.

O alcance final da defesa permite uma pequena correção gradual do ombro para
acompanhar a bola, com comprimento do braço e limites articulares preservados.
O planejamento e a execução usam a mesma curva de aproximação do corpo;
a tolerância de aceitação do contato não foi ampliada.
