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
    for filename in ["LICENSE", "NOTICE"]:
        shutil.copy2(project / filename, stage / filename)
    shutil.copy2(project / "scripts/import-pes3.ps1", stage / "import-pes3.ps1")
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
        "Extraia este ZIP para uma pasta nova. jogar-partida.bat: partida 11 x 11.\n"
        "run-training.bat: treino aprovado. RT/E sem bola: pedir passe. Conecte o\n"
        "controle Xbox Series S por USB ou Bluetooth antes de iniciar.\n\n"
        "Conducao nativa em todas as direcoes, preferindo o pe direito.\n"
        "A conducao frontal DefenseJog foi retirada da selecao.\n"
        "A selecao original conserva as viradas e a corrida com RB.\n"
        "A troca e automatica; L3/T nao alternam a animacao.\n"
        "Os impulsos exigem contato entre a bola e a regiao do corpo.\n"
        "RB usa a corrida nativa. RT continua reservado.\n"
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
        for filename in ("LICENSE","NOTICE"):
            output.write(stage/filename,filename)
        output.writestr("LEIA-ATUALIZACAO.txt",
            ("Windows x64 — conducao nativa com pe direito\r\n\r\n" if approved_binary is None else
             "Windows x64 — gameplay original com primeira pessoa\r\n\r\n") +
            "1. Feche o jogo.\r\n"
            "2. Extraia este ZIP DENTRO da pasta atual do jogo, onde ja ficam\r\n"
            "   gameplayfootball.exe, run-training.bat, as DLLs e a pasta media.\r\n"
            "3. Aceite substituir os arquivos.\r\n"
            "4. Abra run-training.bat.\r\n\r\n"
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
            for path in sorted((stage / "media" / "training").glob("*.*")):
                output.write(path, path.relative_to(stage))
    print(f"Created {update} ({update.stat().st_size // 1024 // 1024} MiB)")
