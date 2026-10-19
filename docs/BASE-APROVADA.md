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

A colisão de recepção considera a bola **e o corpo em movimento** durante
o passo de simulação, incluindo a velocidade da superfície atingida. A
condução já controlada no chão continua com a lógica aprovada para evitar
introduzir as antigas rebatidas entre as próprias pernas.

O catálogo contém **7.723 perfis procedurais**, em **48 famílias**, sobre as
animações nativas. As novas estratégias incluem apoio no voleio e meio
voleio, absorção/saída de cabeça e peito, apoio de coxa/canela, cortes,
passe virando e cruzamento em corrida. Doze estilos de contato ajustam a
recrutação de tronco e braços conforme a jogada, mantendo as pernas, o
evento de contato e o deslocamento nativos. Não são 7.723 capturas novas.
As 36.888 combinações de metadados, incluindo espelhamentos nativos, são
candidatos compatíveis, não uma validação visual exaustiva.

O equilíbrio recebe uma resposta gradual adicional do tronco e dos braços
em cortes rápidos e impactos, sem substituir a passada. Quando o apoio é
superado, o ragdoll e as animações originais de levantar continuam atuando.

F4: passe recebido; F5: bola no peito; F6: cruzamento alto. F8/Shift+F8/Ctrl+F8
testam impactos; F9 testa queda. F10 na partida prepara as bolas paradas.

O relatório técnico `docs/approved-base-validation.json`, no repositório,
registra os testes executados e suas limitações. Os testes gráficos usam
Linux com controle Xbox virtual; o pacote é compilado e verificado para
Windows, e a avaliação com o controle físico continua sendo feita no seu PC.
