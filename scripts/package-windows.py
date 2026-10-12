#!/usr/bin/env python3
"""Package the tested MinGW Windows build with its runtime DLLs and data."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import zipfile


project = Path(__file__).resolve().parents[1]
build = project / "build-windows-mingw2"
artifacts = project / "artifacts"
artifacts.mkdir(exist_ok=True)

executable = build / "gameplayfootball.exe"
if not executable.exists():
    raise SystemExit(f"Windows executable not found: {executable}")

# The build machine keeps the toolchain outside the repository.  Allow an
# override so the same packager can be used from a Windows/MSYS2 checkout.
vcpkg_bin = Path(os.environ.get(
    "FOOTBALL_WINDOWS_VCPKG_BIN",
    "/tmp/vcpkg/installed/x64-mingw-dynamic/bin",
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
        "Extraia este ZIP para uma pasta nova e execute run-training.bat. Conecte o\n"
        "controle Xbox Series S por USB ou Bluetooth antes de iniciar.\n\n"
        "Primeira pessoa: sem bola, direito vira e esquerdo move como FPS.\n"
        "Com bola, esquerdo conduz; direito olha com a cabeça e retorna lentamente.\n"
        "Frente segue a nova frente; direita vira para a nova direita.\n"
        "Baixo vira para trás; mantê-lo repete a virada após completar a anterior.\n"
        "RT mantém a direção atual, sem virar sozinho para o gol.\n"
        "A condução mantém a assistência e os passos originais nas viradas.\n"
        "Viradas para tras mantem o impulso de puxar a bola no contato do pe.\n"
        "L3 (clicar o esquerdo) ou G alterna pe dominante/normal; inicia no direito.\n"
        "No dominante, o pe completa o gesto e a bola rola antes do proximo toque.\n"
        "Pernas de apoio bloqueiam/desviam a bola sem aplicar um segundo chute.\n"
        "RB+RT adianta a bola e mantém o acompanhamento, inclusive nas curvas.\n"
        "Após passes/chutes o movimento fica livre; aproxime-se para dominar de novo.\n"
        "A passe; Y enfiada; B alto/carrinho; X chute (carga = força/altura);\n"
        "X: carga máxima 0,52 s; cerca de 0,25 s já levanta a bola.\n"
        "LB+X cobertura; RB correr; RT domínio; View reiniciar; Menu pausa;\n"
        "D-pad exercício; LB+D-pad baixo falta; R3 alterna as três câmeras.\n"
        "D-pad esquerda: bola aérea. Prepare A (passe) ou X (gol) para cabecear.\n"
        "LB+D-pad direita (tecla 6): passe recebido; prepare A/Y/X para jogar de primeira.\n"
        "Teclado: WASD, setas para olhar, J/I/L/K, Q+K cobertura, Shift/Espaço,\n"
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
    update = artifacts / "football-windows-virada-e-intervalos.zip"
    with zipfile.ZipFile(update,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9)as output:
        output.write(stripped,"gameplayfootball.exe")
        output.write(stage/"run-training.bat","run-training.bat")
        for filename in ("LICENSE","NOTICE"):
            output.write(stage/filename,filename)
        output.writestr("LEIA-ATUALIZACAO.txt",
            "Atualizacao Windows x64 — viradas, perna de apoio e intervalos\r\n\r\n"
            "1. Feche o jogo.\r\n"
            "2. Extraia este ZIP DENTRO da pasta atual do jogo, onde ja ficam\r\n"
            "   gameplayfootball.exe, run-training.bat, as DLLs e a pasta media.\r\n"
            "3. Aceite substituir os arquivos.\r\n"
            "4. Abra run-training.bat.\r\n\r\n"
            "L3: clique o analogico esquerdo para alternar conducao com o pe\r\n"
            "dominante (direito) e normal. No teclado: G. Comeca no dominante.\r\n"
            "O esquerdo continua disponivel se for necessario para alcancar a bola.\r\n"
            "A correcao da virada para tras funciona nos DOIS modos.\r\n"
            "No dominante, ha um intervalo real entre as conduzidas; RT mantem\r\n"
            "o dominio mais curto. Viradas podem puxar antes para manter o controle.\r\n"
            "A puxada contorna a perna de apoio e o contato dela nao da um segundo chute.\r\n"
            "Esta versao utiliza a gameplay e as animacoes nativas da base enviada.\r\n"
            "Nao precisa importar ou copiar a pasta pes3 para jogar.\r\n")
    print(f"Created {update} ({update.stat().st_size // 1024 // 1024} MiB)")
