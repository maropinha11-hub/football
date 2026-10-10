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
        if entry.is_dir():
            shutil.copytree(entry, stage / entry.name)
        else:
            shutil.copy2(entry, stage / entry.name)
    shutil.copy2(project / "config" / "training.config", stage / "training.config")
    for filename in ["LICENSE", "NOTICE"]:
        shutil.copy2(project / filename, stage / filename)

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
        "Extraia este ZIP para uma pasta e execute run-training.bat. Conecte o\n"
        "controle Xbox Series S por USB ou Bluetooth antes de iniciar.\n\n"
        "Primeira pessoa: sem bola, direito vira e esquerdo move como FPS.\n"
        "Com bola, esquerdo conduz; direito olha com a cabeça e retorna lentamente.\n"
        "A passe; Y enfiada; B alto/carrinho; X chute (carga = força/altura);\n"
        "LB+X cobertura; RB correr; RT domínio; View reiniciar; Menu pausa;\n"
        "D-pad exercício; LB+D-pad baixo falta; R3 alterna as três câmeras.\n"
        "Teclado: WASD, setas para olhar, J/I/L/K, Q+K cobertura, Shift/Espaço,\n"
        "R, P, 1–5, Tab, Esc. run-controller-test.bat executa testes virtuais.\n\n"
        "O pacote contém o executável x64, SDL2, OpenAL, Boost, SQLite e os\n"
        "recursos necessários. O primeiro lançamento pode mostrar o SmartScreen\n"
        "porque o binário não é assinado; confirme a origem local do arquivo.\n\n"
        "A base é o projeto Gameplay Football e o modo de treinamento mantido.\n"
        "Não é uma decompilação de PES nem inclui conteúdo proprietário.\n",
        encoding="utf-8",
    )

    archive = artifacts / "football-training-windows-x86_64.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                output.write(path, path.relative_to(stage.parent))
    print(f"Created {archive} ({archive.stat().st_size // 1024 // 1024} MiB)")
