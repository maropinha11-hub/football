#!/usr/bin/env python3
"""Package the tested native executable and its resources, excluding development files."""
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

project = Path(__file__).resolve().parents[1]
artifacts = project / "artifacts"
artifacts.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix="football-package-", dir=artifacts) as temporary:
    stage = Path(temporary) / "football-training-linux-x86_64"
    stage.mkdir()
    subprocess.run(["strip", "--strip-debug", "-o", str(stage / "gameplayfootball"), str(project / "build/gameplayfootball")], check=True)
    for entry in (project / "data").iterdir():
        if entry.is_dir():
            shutil.copytree(entry, stage / entry.name)
        else:
            shutil.copy2(entry, stage / entry.name)
    shutil.copy2(project / "config/training.config", stage / "training.config")
    for filename in ["LICENSE", "NOTICE"]:
        shutil.copy2(project / filename, stage / filename)
    launcher = stage / "run.sh"
    launcher.write_text('#!/usr/bin/env bash\nset -euo pipefail\ncd "$(dirname "$0")"\nexec ./gameplayfootball --config training.config --training "$@"\n')
    launcher.chmod(0o755)
    (stage / "LEIA-ME.txt").write_text(
        "Centro de treinamento Gameplay Football — Linux x86_64\n\n"
        "Binario compilado e validado em Debian 13. Requer um desktop OpenGL e\n"
        "as bibliotecas SDL2 >= 2.24, SDL2_image, SDL2_ttf, SDL2_gfx, OpenAL,\n"
        "Boost 1.83 (filesystem/system/thread) e SQLite3 disponiveis no sistema.\n"
        "Dependencias nao estao incluidas. Para outros sistemas, compile as fontes.\n\n"
        "Execute ./run.sh. Xbox: analogico move; A passe; Y enfiada; B alto/carrinho;\n"
        "X chute; RB correr; RT dominio; View reiniciar; Menu pausa; D-pad exercicio;\n"
        "R3 camera. Teclado: WASD, J/I/L/K, Shift/Espaco, R, P, 1-4, Tab, Esc.\n\n"
        "Usa recursos e motor originais da base aberta. Nao e uma decompilacao de PES.\n"
        "Controle fisico e desempenho no seu computador precisam de avaliacao local.\n"
    )
    subprocess.run([str(stage / "gameplayfootball"), "--help"], cwd=stage, check=True)
    archive = artifacts / "football-training-linux-x86_64.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(stage, arcname=stage.name)
    print(f"Created {archive} ({archive.stat().st_size // 1024 // 1024} MiB)")
