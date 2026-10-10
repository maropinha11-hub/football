#!/usr/bin/env python3
"""Build a self-contained, offline research viewer from the user's PES data."""
import argparse
import base64
import hashlib
import json
import struct
import zipfile
from pathlib import Path

from fpsa import EXPECTED_BUNDLE_SHA256, read_bundle


def build(core, output):
    tool = Path(__file__).resolve().parent
    catalogue = json.loads((core / "data/animation_pose_catalog.json").read_text())
    data, inventory = read_bundle(core / "data/pes_animation_tracks.fpsa", catalogue)
    if inventory["sha256"] != EXPECTED_BUNDLE_SHA256:
        raise ValueError("esta versão do laboratório exige o contêiner v0.14 conferido")
    snapshots = json.loads((core / "data/skeleton_snapshot_channels.json").read_text())
    observations = snapshots["observations"]
    profiles = snapshots["skeleton_profiles"]
    if len(observations) != 132 or len(profiles) != 1:
        raise ValueError("referências de esqueleto não suportadas")
    parents = catalogue["parents"]
    if len(parents) != 19 or any(p >= i or p < -1 or (i and p < 0) for i, p in enumerate(parents)):
        raise ValueError("hierarquia inválida")
    translations = next(iter(profiles.values()))["nonroot_translation_bits"]
    if len(translations) != 18 or any(len(t) != 4 for t in translations):
        raise ValueError("translações de referência inválidas")
    if any(obs["parents"] != parents or obs["translation_bits"][1:] != translations for obs in observations):
        raise ValueError("referências de esqueleto divergentes")
    profile_hash = hashlib.sha256(b"".join(struct.pack("<4I", *t) for t in translations)).hexdigest()
    if profile_hash != next(iter(profiles)):
        raise ValueError("hash das referências de esqueleto divergente")
    metadata = {"bundle_sha256": inventory["sha256"], "parents": parents,
                "bind_bits": [[0, 0, 0, 0x3f800000]] + translations,
                "clips": [{"clip": e["clip"], "source": e["source"],
                           "block_sha256": e["block_sha256"], "source_offset": e["source_offset"]}
                          for e in catalogue["entries"]],
                "scope": "Verified local interpolation; diagnostic standard FK, no original final transforms or gameplay."}
    safe_json = json.dumps(metadata, ensure_ascii=True, separators=(",", ":")).replace("</", "<\\/")
    motion = (tool / "motion.js").read_text()
    template = (tool / "lab.html").read_text()
    for marker in ["__PES3_MOTION__", "__PES3_METADATA__", "__PES3_BUNDLE__"]:
        if template.count(marker) != 1:
            raise ValueError("template incompleto")
    html = template.replace("__PES3_MOTION__", motion).replace("__PES3_METADATA__", safe_json)
    html = html.replace("__PES3_BUNDLE__", base64.b64encode(data).decode("ascii"))
    instructions = (
        "PES 3 - Laboratório de animações\n\n"
        "Extraia o ZIP e abra abrir-laboratorio.html com Edge ou Chrome no Windows 11.\n"
        "Funciona sem internet e sem instalar Python, Node ou outro Windows.\n\n"
        "Escolha o ID, use Reproduzir/Pausar e a barra de tempo. Arraste a visão para\n"
        "girar; a roda do mouse ajusta o zoom. Anterior/Próxima chave percorrem os\n"
        "tempos originais. A velocidade da prévia não é a taxa de simulação do PES.\n\n"
        "Você pode marcar candidatos a caminhada, corrida, passes etc. Exportar\n"
        "catálogo baixa um JSON com suas anotações. Marcações são candidatos visuais;\n"
        "não comprovam contato, apoio, retargeting ou seleção física no treino.\n\n"
        "As marcações ficam nesta aba: exporte o catálogo antes de fechar.\n\n"
        "Este laboratório mostra 1.105 clips e 19 articulações. A interpolação local\n"
        "foi comparada em bits com os vetores v0.14; a composição da hierarquia para\n"
        "desenho é diagnóstica. Mistura, espelhamento e saída final do PES ainda\n"
        "exigem validação. Não é uma atualização do executável de treinamento.\n"
    )
    manifest = {k: v for k, v in inventory.items() if k != "entries"}
    manifest.update(html_sha256=hashlib.sha256(html.encode()).hexdigest(),
                    motion_js_sha256=hashlib.sha256(motion.encode()).hexdigest(),
                    skeleton_profile_sha256=profile_hash, scope=metadata["scope"])
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("abrir-laboratorio.html", html)
        archive.writestr("LEIA-ME.txt", instructions)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Empacotar o laboratório offline do PES 3")
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build(args.core, args.output)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        parser.exit(1, str(exc) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
