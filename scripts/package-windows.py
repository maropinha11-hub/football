#!/usr/bin/env python3
"""Package the tested MinGW Windows build with its runtime DLLs and data."""
from pathlib import Path
import argparse
import hashlib
import io
import os
import shutil
import subprocess
import tempfile
import zipfile


project = Path(__file__).resolve().parents[1]
build = project / "build-windows-mingw2"
artifacts = project / "artifacts"
artifacts.mkdir(exist_ok=True)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--restore-original-binary", action="store_true",
                    help="Reuse the exact approved Windows binary archived at 37a5543")
args = parser.parse_args()
approved_binary = None
if args.restore_original_binary:
    archived = subprocess.check_output([
        "git", "show", "37a5543:artifacts/football-windows-corrigir-orientacao.zip",
    ], cwd=project)
    with zipfile.ZipFile(io.BytesIO(archived)) as source:
        if source.testzip() is not None:
            raise SystemExit("Approved archive failed CRC verification")
        approved_binary = source.read("gameplayfootball.exe")
    if hashlib.sha256(approved_binary).hexdigest() != "ece4200cd1591edb60007ff71f4154cfaf7bcf232ec05ccfff001067f5418bfb":
        raise SystemExit("Approved executable differs from the original uploaded binary")
executable = build / "gameplayfootball.exe"
if approved_binary is None and not executable.exists():
    raise SystemExit(f"Windows executable not found: {executable}")

# The build machine keeps the toolchain outside the repository.  Allow an
# override so the same packager can be used from a Windows/MSYS2 checkout.
vcpkg_bin = Path(os.environ.get(
    "FOOTBALL_WINDOWS_VCPKG_BIN",
    "/workspace/.football-windows/vcpkg/installed/x64-mingw-dynamic/bin",
))
mingw_root = Path(os.environ.get(
    "FOOTBALL_WINDOWS_MINGW_ROOT",
    "/workspace/.football-native/root",
))
mingw_runtime = mingw_root / "usr" / "lib" / "gcc" / "x86_64-w64-mingw32" / "14-posix"
mingw_target = mingw_root / "usr" / "x86_64-w64-mingw32" / "lib"
stripper = os.environ.get("STRIP", "x86_64-w64-mingw32-strip")

with tempfile.TemporaryDirectory(prefix="football-windows-", dir=artifacts) as temporary:
    stage = Path(temporary) / "football-training-windows-x86_64"
    stage.mkdir()

    # Strip only the distributable copy.  The unstripped executable remains in
    # build-windows-mingw2 for crash analysis and future debugging.
    stripped = stage / "gameplayfootball.exe"
    if approved_binary is not None:
        stripped.write_bytes(approved_binary)
    else:
        subprocess.run([stripper, "--strip-debug", "-o", str(stripped), str(executable)], check=True)

    for entry in (project / "data").iterdir():
        if entry.name == "pes3":
            continue  # Source animation bank is installed from the user's local file.
        if entry.is_dir():
            shutil.copytree(entry, stage / entry.name)
        else:
            shutil.copy2(entry, stage / entry.name)
    shutil.copy2(project / "config" / "training.config", stage / "training.config")
    shutil.copy2(project / "config" / "situational-motion-catalog.json",
                 stage / "situational-motion-catalog.json")
    shutil.copy2(project / "config" / "procedural-strikes.json", stage / "procedural-strikes.json")
    for filename in ["LICENSE", "NOTICE"]:
        shutil.copy2(project / filename, stage / filename)
    shutil.copy2(project / "third_party/bullet/LICENSE.txt", stage / "BULLET-LICENSE.txt")
    shutil.copy2(project / "third_party/motion-matching/LICENSE.txt", stage / "MOTION-MATCHING-LICENSE.txt")
    shutil.copy2(project / "scripts/import-pes3.ps1", stage / "import-pes3.ps1")
    for filename in ("dividir-arquivos.ps1", "dividir-arquivos.bat"):
        shutil.copy2(project / "scripts" / filename, stage / filename)
    shutil.copy2(project / "docs/BASE-APROVADA.md",stage / "LEIA-BASE-APROVADA.txt")
    shutil.copy2(project / "config/approved-base.json",stage / "approved-base.json")
    for filename, command in [
        ("importar-pes3.bat", 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0import-pes3.ps1"'),
        ("estudar-pes3.bat", 'gameplayfootball.exe --config training.config --training --pes3-preview %*'),
    ]:
        (stage / filename).write_text(
            '@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\n' + command + '\r\npause\r\n',
            encoding="ascii", newline="",
        )

    # vcpkg's applocal deployment already identifies the direct DLLs.  Copying
    # every release DLL from the triplet also covers optional image/font/audio
    # codecs and Boost's transitive runtime libraries.
    if vcpkg_bin.is_dir():
        for dll in sorted(vcpkg_bin.glob("*.dll")):
            shutil.copy2(dll, stage / dll.name)
    else:
        raise SystemExit(f"vcpkg runtime directory not found: {vcpkg_bin}")

    for dll in ["libgcc_s_seh-1.dll", "libstdc++-6.dll"]:
        candidate = mingw_runtime / dll
        if not candidate.exists():
            raise SystemExit(f"MinGW runtime DLL not found: {candidate}")
        shutil.copy2(candidate, stage / dll)
    winpthread = mingw_target / "libwinpthread-1.dll"
    if winpthread.exists():
        shutil.copy2(winpthread, stage / winpthread.name)

    (stage / "run-training.bat").write_text(
        "@echo off\r\n"
        "setlocal\r\n"
        "cd /d \"%~dp0\"\r\n"
        "gameplayfootball.exe --config training.config --training %*\r\n"
        "if errorlevel 1 pause\r\n",
        encoding="ascii",
        newline="",
    )
    (stage / "jogar-partida.bat").write_text(
        '@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\n'
        'gameplayfootball.exe --config training.config --player-match %*\r\n'
        'if errorlevel 1 pause\r\n', encoding="ascii", newline="",
    )
    for filename, mode in [("treino-fisico.bat", "--training"),
                           ("partida-fisica.bat", "--player-match")]:
        (stage / filename).write_text(
            '@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\n'
            'gameplayfootball.exe --config training.config ' + mode + ' --physical-rig %*\r\n'
            'if errorlevel 1 pause\r\n', encoding="ascii", newline="",
        )
    (stage / "LEIA-FISICA.txt").write_text(
        "Teste de fisica corporal Bullet e busca de movimento — FPSoccer\n\n"
        "1. Extraia este ZIP completo em uma pasta nova.\n"
        "2. Abra treino-fisico.bat para o centro de treinamento experimental.\n"
        "3. R3/Tab: camera externa para observar o corpo.\n\n"
        "Correcao desta revisao: rotacoes pelo arco curto, camera presa a\n"
        "cabeca renderizada e leitura direta dos quadros. Leia LEIA-BASE-APROVADA.txt.\n\n"
        "F7: comparar fisica ligada/desligada.\n"
        "Base restaurada: fa0dfa6, correspondente ao executavel enviado.\n"
        "Sem os clipes de locomocao importados e sem busca por fase.\n"
        "Leia LEIA-BASE-APROVADA.txt.\n"
        "F1: comparar variacoes corporais de passes/chutes ligadas/desligadas.\n"
        "RT fica reservado no treino; os gestos de sola foram removidos.\n"
        "Na recepcao, mire com o analogico esquerdo e prepare A/X/Y/B antes\n"
        "do contato; apertos repetidos mantem o comando e a direcao escolhida.\n"
        "F3: mudar direcao do impacto (direita/frente/esquerda/tras).\n"
        "F8: impacto lateral medio (125 N.s), com tentativa de equilibrio.\n"
        "Shift+F8: impacto forte (190 N.s), para testar passos de recuperacao.\n"
        "Ctrl+F8: sobrecarga (350 N.s), pode superar o equilibrio e causar queda.\n"
        "F9: queda fisica; levantar usa as animacoes originais com apoio.\n"
        "F10: parceiro ao lado / pressionando / fora do treino.\n"
        "F11: alternar bola no parceiro / no jogador para testar LT.\n"
        "Segure LT/L2: com bola protege; sem bola tenta segurar a camisa.\n"
        "Solte para largar; distancia excessiva tambem solta.\n"
        "H: agarrar; N: proteger. L3 nao aciona mais a camisa.\n"
        "M: teste de disputa corporal, apenas em alcance de contato.\n"
        "R/View: reiniciar, inclusive durante uma queda.\n"
        "G: comparar gramado irregular/liso; a previsao usa a mesma superficie.\n"
        "Ctrl+F6 na partida fisica: ensaiar cara a cara, bola no angulo e recuo ao goleiro.\n"
        "Ctrl+Shift+F6: saida curta com linhas livres para observar a CPU.\n"
        "Mudancas bruscas em velocidade exigem equilibrio; conduzir devagar continua estavel.\n"
        "Na CPU, calcanhares sao restritos a emergencias leves, longe do proprio gol.\n"
        "Passe curto humano para tras: toque breve prefere calcanhar; carga maior gira o corpo.\n"
        "Shift/Ctrl+F4: passe rasteiro deslocado para cada lado.\n"
        "Shift+F5: bola forte no peito; Ctrl+F5: bola na barriga.\n"
        "Shift+Ctrl+F5: bolada forte alta para testar a reacao fisica.\n"
        "F4: passe rasteiro; F5: bola para o peito; F6: bola alta.\n"
        "Para passe de primeira/cabecada, peca A ou X antes de a bola chegar.\n"
        "A acao preparada permanece mesmo apertando novamente o botao.\n"
        "Xbox: controles anteriores; RB corre; direito olha.\n\n"
        "partida-fisica.bat: o mesmo experimento contra os times da CPU.\n"
        "Todos os 22 jogadores recebem a camada fisica, inclusive a CPU.\n"
        "Impactos selecionam passos de apoio e protecao de corpo inteiro.\n"
        "Passes, chutes e cruzamentos recebem preparacao e recuperacao de\n"
        "tronco e bracos conforme direcao, velocidade, bola e adversario.\n"
        "Teste um passe parado e outro para o lado durante a corrida com RB.\n"
        "A camada nova preserva os pes e o contato original com a bola.\n"
        "O catalogo inclui 11323 perfis procedurais sobre as animacoes existentes;\n"
        "as 65.718 combinacoes de metadados nao sao novas capturas nem uma\n"
        "validacao exaustiva. Consulte situational-motion-catalog.json.\n"
        "26 variantes geradas de passe/chute/cruzamento preservam raiz, pernas e eventos.\n"
        "Analogico leve permite caminhar; todo puxado e RB conservam a velocidade aprovada.\n"
        "Toque curto no A ficou mais fraco e a carga aumenta a forca gradualmente.\n"
        "Bolas paradas: jogadores se movimentam antes da cobranca, sem tocar antes do apito.\n"
        "Goleiros interceptam recuos com os pes e escolhem o lado do mergulho pela trajetoria.\n"
        "Audio: passos no gramado, respiracao, ambiente e impacto da bola.\n"
        "Apoio ativo: quadril cede sob carga e os joelhos compensam, mantendo as chuteiras apoiadas.\n"
        "F8 testa a recuperacao de apoio; F9 testa queda com esforco muscular e protecao.\n"
        "Na partida, LT/L2 ou H/N tambem tentam agarrar/proteger; M disputa.\n"
        "F2 na partida: aproxima um adversario para ensaio de contato.\n"
        "Ctrl+F2: aproxima pela frente para testar botes/carrinhos.\n"
        "Alt+F2: bola alta e adversario lado a lado para disputar de cabeca.\n"
        "F11 na partida: coloca a bola no adversario proximo para testar LT.\n"
        "Shift+F11: bola no jogador humano; B no teclado solicita tentativa CPU de agarrar.\n"
        "A sem bola: bote em pe. B no controle sem bola: carrinho.\n"
        "Contatos atrasados nas pernas podem desequilibrar, derrubar e causar falta.\n"
        "De costas e mais dificil receber bolas rapidas: vire para a chegada.\n"
        "CPU protege e pode segurar; excesso gera falta ou penalti na area.\n"
        "Voce cobra faltas, penaltis, escanteios, laterais e tiros de meta do seu time.\n"
        "A saida de jogo continua automatica pela CPU.\n"
        "F10 na partida: testar falta/penalti/escanteio/lateral/tiro de meta.\n"
        "Partida padrao: dois tempos de 45 minutos reais.\n"
        "RT/E pede passe: CPU considera passe no pe, adiantado ou por cima.\n"
        "F2/F11 sao montagens explicitas de teste; a IA volta a agir normalmente.\n"
        "run-training.bat e jogar-partida.bat abrem as versoes aprovadas.\n\n"
        "O equilibrio tenta recuperar apoio antes de uma queda comum.\n"
        "A locomocao continua guiada pelas animacoes existentes, com ajustes\n"
        "de equilibrio, bracos e alcance gradual. Nas quedas, articulacoes,\n"
        "gravidade, musculatura limitada e contatos com o chao controlam o corpo.\n"
        "Os musculos trocam torques internos, sem levantar o corpo no ar. A recuperacao\n"
        "combina as animacoes de levantar de frente/costas com apoio no chao.\n"
        "A camisa tem uma casca XPBD limitada nos vertices do tronco;\n"
        "nao e uma simulacao completa de tecido com rasgos ou agarramentos livres.\n"
        "Tronco e bracos acompanham animacoes por motores fisicos.\n"
        "A busca compara pose, velocidade e trajetoria de animacoes elegiveis.\n"
        "Camera: sensibilidade aumentada de 2.6 para 3.8.\n"
        "Os 270 contextos de teste sao variacoes de parametros,\n"
        "nao 270 capturas de movimento novas. Os limites completos da\n"
        "pesquisa e da simulacao constam em docs/EQUILIBRIO-E-CONTATO.md no GitHub.\n",
        encoding="utf-8",
    )
    (stage / "run-controller-test.bat").write_text(
        "@echo off\r\n"
        "setlocal\r\n"
        "cd /d \"%~dp0\"\r\n"
        "gameplayfootball.exe --test-controller %*\r\n"
        "pause\r\n",
        encoding="ascii",
        newline="",
    )
    (stage / "LEIA-ME.txt").write_text(
        "Centro de treinamento Gameplay Football — Windows 11 x64\n\n"
        "Extraia este ZIP para uma pasta nova. Para testar esta atualizacao,\n"
        "abra treino-fisico.bat; partida-fisica.bat testa os mesmos movimentos\n"
        "com os dois times. R3/Tab mostra o corpo; F1 compara as variacoes corporais.\n"
        "jogar-partida.bat: partida 11 x 11 com a base aprovada.\n"
        "run-training.bat: treino aprovado. RT/E sem bola: pedir passe. Conecte o\n"
        "controle Xbox Series S por USB ou Bluetooth antes de iniciar.\n"
        "treino-fisico.bat abre ragdoll e variacoes corporais; leia LEIA-FISICA.txt.\n"
        "Partida: IA nativa no nivel maximo, com formacao, marcacao, apoios e\n"
        "decisoes com bola autonomas tambem nos companheiros. Pedidos de passe\n"
        "avaliam risco e impedimento; se nao houver opcao, a CPU segue a jogada.\n\n"
        "Conducao nativa em todas as direcoes, preferindo o pe direito.\n"
        "A conducao frontal DefenseJog foi retirada da selecao.\n"
        "A selecao original conserva as viradas e a corrida com RB.\n"
        "A troca e automatica; L3/T nao alternam a animacao.\n"
        "Os impulsos exigem contato entre a bola e a regiao do corpo.\n"
        "RB usa a corrida nativa. No modo aprovado, RT continua reservado.\n"
        "Animacoes mais cadenciadas, com intervalos entre os toques.\n"
        "A simulacao continua em tempo real.\n"
        "R3 mostra o corpo na camera externa.\n\n"
        "LANCAMENTOS NO TECLADO, A PARTIR DA SUA POSICAO:\n"
        "F4: passe rasteiro. F5: bola para o peito. F6: cruzamento alto.\n"
        "F3/5 continua sendo treino de falta.\n"
        "Chest_Stand e Chest_Run sao dominios adicionais no seletor original.\n"
        "Os dominios anteriores continuam disponiveis. Solte o analogico e\n"
        "aperte F5 para Stand; avanco moderado e F5 para Run.\n"
        "Bracos fazem o dominio; apos a queda, voltam a locomocao suavemente.\n"
        "Antes do contato e na queda, ajuste apenas para frente ou tras.\n"
        "O dominio exige contato real na parte frontal do peito.\n\n"
        "Primeira pessoa: sem bola, direito vira e esquerdo move como FPS.\n"
        "Com bola, esquerdo conduz; direito olha com a cabeça e retorna lentamente.\n"
        "Frente segue a nova frente; direita vira para a nova direita.\n"
        "Baixo vira para trás; mantê-lo repete a virada após completar a anterior.\n"
        + ("Gameplay Football: seletor, aproximacao e toques nativos.\n"
           "RT reservado, sem alterar movimento, dominio ou corrida.\n"
           "Simulacao em tempo real, com passo fisico de 10 ms.\n" if approved_binary is None else "") +
        ("Base nativa da origem vi3itor (68159a2), com animacoes FBX integradas.\n" if approved_binary is None else
           "Gameplay nativa original aprovada (37a5543), sem a correcao da puxada.\n") +
        "Após passes/chutes o movimento fica livre; aproxime-se para dominar de novo.\n"
        "A passe; Y enfiada; B alto/carrinho; X chute (segure para carregar);\n"
        "RB correr; View reiniciar; Menu pausa;\n"
        "X: carga maxima em 0,52 s. LB+X: cobertura. A rotacao da bola\n"
        "depende do ponto real de contato; golpes fora do centro curvam.\n"
        "Ao receber um passe, frente/tras ajustam a interceptacao assistida.\n"
        "D-pad exercício; LB+D-pad baixo falta; R3 alterna as três câmeras.\n"
        "D-pad esquerda: bola aérea. Prepare A (passe) ou X (gol) para cabecear.\n"
        "LB+D-pad direita (tecla 6): passe recebido; prepare A/Y/X para jogar de primeira.\n"
        "Teclado: WASD, setas para olhar, J/I/L/K, Shift para correr,\n"
        "R, P, 1–6, Tab, Esc. run-controller-test.bat executa testes virtuais.\n"
        "log.txt registra Training::Timing; relação 1.0 = tempo real.\n\n"
        "O pacote contém o executável x64, SDL2, OpenAL, Boost, SQLite e os\n"
        "recursos necessários. O primeiro lançamento pode mostrar o SmartScreen\n"
        "porque o binário não é assinado; confirme a origem local do arquivo.\n\n"
        "Estudo de animacoes PES3 (opcional): execute importar-pes3.bat e selecione\n"
        "fpsoccer-pes-nucleo-v14.zip que voce ja possui. Execute estudar-pes3.bat.\n"
        "Um esqueleto de estudo de 19 ossos reproduz os clips ao lado do jogador.\n"
        "F7 abre/fecha; F8/F9 seguinte/anterior; F10 pausa/reinicia; F11 +1;\n"
        "C percorre os clips observados nos saves. Cada clip para no final.\n"
        "V aplica a pose ao corpo do jogador parado (teste de adaptacao).\n"
        "Analogico esquerdo, corrida, dominio, passe ou chute restauram a animacao\n"
        "nativa automaticamente. V tambem remove a pose; R3/Tab muda a camera.\n"
        "A camera externa aproxima o corpo durante V para conferir a animacao.\n"
        "Essa adaptacao nao escolhe as animacoes PES das jogadas nem seus contatos.\n"
        "O ritmo de estudo e 60 unidades de fase por segundo, ajustavel na config\n"
        "com pes3_preview_units_per_second. Nao e uma medicao da cadencia do PES.\n"
        "Nesse teste, comandos, jogadas, contatos e fisica continuam nativos.\n\n"
        "A base e o projeto Gameplay Football e o modo de treinamento mantido.\n"
        "A gameplay completa do PES ainda nao esta integrada. Os dados originais\n"
        "das animacoes sao importados do seu arquivo local e nao vem neste ZIP.\n",
        encoding="utf-8",
    )

    archive = artifacts / "football-training-windows-x86_64.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                output.write(path, path.relative_to(stage.parent))
    print(f"Created {archive} ({archive.stat().st_size // 1024 // 1024} MiB)")
    # The approved native installation already has its DLLs and game media.
    update = artifacts / ("football-windows-gameplay-original.zip" if approved_binary is not None else
                          "football-windows-teste-animacao-fbx.zip")
    with zipfile.ZipFile(update,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9)as output:
        output.write(stripped,"gameplayfootball.exe")
        output.write(stage/"run-training.bat","run-training.bat")
        for filename in ("treino-fisico.bat", "partida-fisica.bat", "LEIA-FISICA.txt",
                         "situational-motion-catalog.json","procedural-strikes.json","LEIA-BASE-APROVADA.txt","approved-base.json",
                         "dividir-arquivos.bat","dividir-arquivos.ps1"):
            output.write(stage/filename,filename)
        for filename in ("LICENSE","NOTICE","BULLET-LICENSE.txt","MOTION-MATCHING-LICENSE.txt"):
            output.write(stage/filename,filename)
        output.writestr("LEIA-ATUALIZACAO.txt",
            ("Windows x64 — conducao nativa com pe direito\r\n\r\n" if approved_binary is None else
             "Windows x64 — gameplay original com primeira pessoa\r\n\r\n") +
            "1. Feche o jogo.\r\n"
            "2. Extraia este ZIP DENTRO da pasta atual do jogo, onde ja ficam\r\n"
            "   gameplayfootball.exe, run-training.bat, as DLLs e a pasta media.\r\n"
            "3. Aceite substituir os arquivos.\r\n"
            "4. Para a revisao fisica, abra treino-fisico.bat ou partida-fisica.bat.\r\n"
            "   run-training.bat continua disponivel para o modo aprovado sem a camada fisica.\r\n\r\n"
            + ("Restaurada a base aprovada 37a5543.\r\n" if approved_binary is not None else
             "Conducao aprovada como padrao, sem toggle em L3/T.\r\n"
             "R3 alterna as cameras para ver o corpo completo.\r\n"
             "F4: passe recebido; F5: dominio de peito parado/avancando; F6: cruzamento.\r\n"
             "F5 sem direcao: Stand; F5 com avanco moderado: Run.\r\n"
             "Bracos fazem o dominio e voltam a corrida apos a bola cair; ajuste frente/tras.\r\n"
             "RB permite correr. RT continua reservado.\r\n") +
            "O ZIP inclui training.config e o novo clip em media/training.\r\n"
            "Nao precisa importar ou copiar a pasta pes3 para jogar.\r\n")
        output.write(stage / "training.config", "training.config")
        output.write(stage / "jogar-partida.bat", "jogar-partida.bat")
        if approved_binary is None:
            for path in sorted((stage / "media" / "animations" / "procedural_actions").glob("*.anim")):
                output.write(path,path.relative_to(stage))
            for name in ["turfstep0.wav","turfstep1.wav","breathing.wav","fieldair.wav"]:
                output.write(stage / "media" / "sounds" / name, "media/sounds/"+name)
            for path in sorted((stage / "media" / "training").glob("*.*")):
                output.write(path, path.relative_to(stage))
            for path in sorted((stage / "media" / "animations" / "mocap").glob("*.anim")):
                output.write(path,path.relative_to(stage))
    print(f"Created {update} ({update.stat().st_size // 1024 // 1024} MiB)")
