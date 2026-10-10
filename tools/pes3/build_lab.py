#!/usr/bin/env python3
"""Build a self-contained, offline research viewer from the user's PES data."""
import argparse
import base64
import gzip
import hashlib
import json
import struct
import zipfile
from pathlib import Path

from fpsa import EXPECTED_BUNDLE_SHA256, read_bundle


def build(core, output, actions=None, validation=None, replay=None, pose=None):
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
    action_document = action_validation = None
    if actions:
        if validation is None:
            raise ValueError("informe a validação do roteamento com --validation")
        action_document = json.loads((actions / "actions.json").read_text())
        action_validation = json.loads(validation.read_text())
        if (action_validation.get("result") != "passed"
                or action_validation["sources"] != action_document["sources"]
                or action_validation["actions_file_sha256"] != hashlib.sha256((actions / "actions.json").read_bytes()).hexdigest()):
            raise ValueError("mapa de ações não corresponde à validação")
        metadata["actions"] = {"summary": action_document["summary"], "sources": action_document["sources"],
            "action_codes": sorted(c["value"] for c in action_document["routing"]["actions"]["cases"]),
            "action1_substate_codes": sorted(c["value"] for c in action_document["routing"]["action1_substates"]["cases"]),
            "clips": action_document["clips"], "scope": action_document["scope"]}
    replay_document = None
    if replay:
        if action_document is None:
            raise ValueError("a reexecução requer o mapa de ações")
        replay_document = json.loads((replay / "replay-validation.json").read_text())
        if (replay_document["result"] != "passed"
                or replay_document["sources"] != action_document["sources"]
                or replay_document["analysis_sha256"] != action_validation["actions_file_sha256"]
                or replay_document["summary"]["native_function_comparisons"] != replay_document["summary"]["original_function_calls"]):
            raise ValueError("reexecução não corresponde à análise validada")
        for name, expected in replay_document["native_files_sha256"].items():
            if hashlib.sha256((replay / "native" / name).read_bytes()).hexdigest() != expected:
                raise ValueError("reescrita C++ diverge da reexecução validada")
        metadata["replay"] = {"state_sha256": replay_document["state"]["sha256"],
            "pcsx2_version": replay_document["state"]["pcsx2_version"],
            "summary": replay_document["summary"], "scope": replay_document["scope"],
            "scenarios": [{k: c[k] for k in ("id", "actor", "input_kind", "edits", "transitions", "output_actor")}
                          for c in replay_document["scenarios"]]}
    pose_document = pose_evidence = retarget = None
    if pose:
        if action_document is None:
            raise ValueError("poses requerem a análise dos binários")
        pose_document = json.loads((pose / "pose-validation.json").read_text())
        pose_evidence = json.loads((pose / "pose-evidence.json").read_text())
        if (pose_document["result"] != "passed" or pose_document["sources"] != action_document["sources"]
                or pose_document["analysis_sha256"] != action_validation["actions_file_sha256"]
                or pose_document["pose_evidence_sha256"] != hashlib.sha256((pose / "pose-evidence.json").read_bytes()).hexdigest()
                or pose_document["summary"]["original_function_calls"] != pose_document["summary"]["native_function_comparisons"]
                or pose_document["state"]["sha256"] != pose_evidence["state_sha256"]
                or (replay_document and replay_document["state"]["sha256"] != pose_evidence["state_sha256"])):
            raise ValueError("poses não correspondem à execução validada")
        for name, expected in pose_document["native_files_sha256"].items():
            if hashlib.sha256((pose / "native" / name).read_bytes()).hexdigest() != expected:
                raise ValueError("caminhos de pose C++ alterados")
        for name, expected in pose_document["semantic_pose_operations"]["files_sha256"].items():
            if hashlib.sha256((pose / "semantic" / name).read_bytes()).hexdigest() != expected:
                raise ValueError("helpers semânticos de pose alterados")
        from retarget import prepare
        retarget = prepare(pose_evidence, tool.parents[1] / "data/media/objects/players/player.object")
        def compact_buffer(buffer):
            return {k: buffer[k] for k in ("instance", "instance_flags", "local_rotation_bits",
                                          "local_translation_bits", "composed_translation_bits")}
        def compact_output(record):
            return {"selected_buffer": record["selected_buffer"],
                    "buffers": [compact_buffer(b) for b in record["buffers"]]}
        metadata["pose"] = {"summary": pose_document["summary"], "scope": pose_document["scope"],
            "state_sha256": pose_evidence["state_sha256"], "parents": pose_evidence["parents"],
            "mirror_pairs": pose_evidence["mirror_pairs"],
            "captured_actors": [dict(actor=a["actor"], **compact_output(a)) for a in pose_evidence["captured_actors"]],
            "scenarios": [{k: s[k] for k in ("id", "actor", "input_kind", "edits", "function_calls", "output_actor")}
                          | {"pose_output": compact_output(s["pose_output"])} for s in pose_evidence["scenarios"]]}
        metadata["scope"] = ("Verified local clip interpolation with diagnostic standard FK; "
                             "separate captured and host-model reexecuted composed poses. "
                             "No resumed PS2 frame, whole gameplay or native game integration.")
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
        "Este laboratório mostra 1.105 clips e 19 articulações. Na reprodução de\n"
        "clips, a interpolação local foi comparada em bits com os vetores v0.14;\n"
        "o desenho usa uma composição diagnóstica da hierarquia. A correspondência\n"
        "integral com os quadros finais do PES continua pendente. O laboratório\n"
        "não atualiza o executável de treinamento.\n"
    )
    if actions:
        instructions += (
            "\nEsta edição inclui o mapa automático de referências de animação no código.\n"
            "Use Contexto de ação/Subestado para filtrar e escolher clips relacionados.\n"
            "Os números são estados do PES; não foram inventados nomes de passe/chute.\n"
            "Exportar mapa do código baixa o índice gerado, sem marcação manual.\n\n"
            "actions.json.gz contém grafos, chamadas, condições e listagens de origem.\n"
            "action_dispatch.hpp/.js são reescritas do roteamento, com testes contra\n"
            "instruções originais. Os endereços identificam blocos; não são ponteiros\n"
            "executáveis no Windows. Corpos completos de ações e gates físicos ainda\n"
            "precisam ser reescritos/validados para integrar os clips ao nosso treino.\n"
        )
    if replay:
        instructions += (
            "\nSeleção reexecutada no treino mostra caminhos registrados com o save state.\n"
            "Memória alterada para teste identifica comandos/estados artificiais.\n"
            "Escolha um cenário e uma transição; a prévia mostra o clip selecionado.\n"
            "Exportar reexecução preserva as condições do teste e a origem do estado.\n"
            "São chamadas isoladas com registradores iniciais definidos, sem retomar\n"
            "o quadro salvo. A prévia não reproduz a mistura ou os contatos finais.\n\n"
            "replay-validation.json.gz guarda os testes contra as instruções originais.\n"
            "native/ contém a recompilação estática dos caminhos alcançados em C++.\n"
            "Essa API usa cópias da memória EE/scratch e o modelo aritmético selecionado;\n"
            "não foi integrada ao executável do centro de treinamento.\n"
        )
    if pose:
        instructions += (
            "\nEsta edição acrescenta Poses do treino PES. Abra esse painel e escolha\n"
            "Pose capturada no PES ou Pose reexecutada em C++. Escolha o atleta/cenário\n"
            "e o buffer. O desenho usa os pontos compostos registrados, sem repetir\n"
            "a composição diagnóstica do clip. São poses estáticas, não quadros gravados.\n"
            "Mudar o ID de animação volta à reprodução do clip isolado.\n\n"
            "Exportar pose preserva os bits e a origem da seleção. pose-evidence.json.gz\n"
            "conserva também matrizes/caches e as chamadas com argumentos explícitos.\n"
            "pose-native/ contém os caminhos de montagem recompilados; pose-semantic/\n"
            "contém multiplicação, matriz, rotação e mistura NLERP sem memória do PS2.\n"
            "retarget-plan.json registra relações candidatas; eixos, lados, escala e\n"
            "contatos permanecem pendentes. Não habilita animações no jogo Windows.\n"
            "A pose local recalculada ainda diverge dos campos finais gravados no save.\n"
        )
    manifest = {k: v for k, v in inventory.items() if k != "entries"}
    manifest.update(html_sha256=hashlib.sha256(html.encode()).hexdigest(),
                    motion_js_sha256=hashlib.sha256(motion.encode()).hexdigest(),
                    skeleton_profile_sha256=profile_hash, scope=metadata["scope"])
    if actions:
        manifest["action_analysis"] = action_document["summary"]
        manifest["actions_file_sha256"] = action_validation["actions_file_sha256"]
        manifest["action_validation_sha256"] = hashlib.sha256(validation.read_bytes()).hexdigest()
    if replay:
        manifest["replay_analysis"] = replay_document["summary"]
        manifest["replay_validation_sha256"] = hashlib.sha256((replay / "replay-validation.json").read_bytes()).hexdigest()
    if pose:
        manifest["pose_analysis"] = pose_document["summary"]
        manifest["pose_validation_sha256"] = hashlib.sha256((pose / "pose-validation.json").read_bytes()).hexdigest()
        manifest["pose_evidence_sha256"] = pose_document["pose_evidence_sha256"]
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("abrir-laboratorio.html", html)
        archive.writestr("LEIA-ME.txt", instructions)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
        if actions:
            archive.writestr("animation-actions.json", json.dumps(metadata["actions"], separators=(",", ":")) + "\n")
            archive.writestr("actions.json.gz", gzip.compress((actions / "actions.json").read_bytes(), compresslevel=9, mtime=0))
            for name in ("action_dispatch.hpp", "action_dispatch.js"):
                archive.writestr(name, (actions / name).read_bytes())
            archive.writestr("actions-validation.json", validation.read_bytes())
        if replay:
            archive.writestr("replay-evidence.json", json.dumps(metadata["replay"], separators=(",", ":")) + "\n")
            archive.writestr("replay-validation.json.gz", gzip.compress((replay / "replay-validation.json").read_bytes(), compresslevel=9, mtime=0))
            archive.writestr("instruction-words.json", (replay / "instruction_words.json").read_bytes())
            for name in ("lifted_program.cpp", "lift_api.hpp", "lift_runtime.hpp"):
                archive.writestr("native/" + name, (replay / "native" / name).read_bytes())
        if pose:
            for name in ("pose-evidence.json", "pose-validation.json"):
                archive.writestr(name + ".gz", gzip.compress((pose / name).read_bytes(), compresslevel=9, mtime=0))
            archive.writestr("pose-instruction-words.json", (pose / "instruction_words.json").read_bytes())
            for name in ("lifted_program.cpp", "lift_api.hpp", "lift_runtime.hpp"):
                archive.writestr("pose-native/" + name, (pose / "native" / name).read_bytes())
            for name in ("pose_ops.hpp", "pose_ops.cpp", "pose-ops-validation.json"):
                archive.writestr("pose-semantic/" + name, (pose / "semantic" / name).read_bytes())
            archive.writestr("pose-semantic/pose-ops-vectors.json.gz",
                             gzip.compress((pose / "semantic/pose-ops-vectors.json").read_bytes(), compresslevel=9, mtime=0))
            archive.writestr("retarget-plan.json", json.dumps(retarget, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Empacotar o laboratório offline do PES 3")
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--actions", type=Path)
    parser.add_argument("--validation", type=Path)
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--pose", type=Path)
    args = parser.parse_args()
    try:
        result = build(args.core, args.output, args.actions, args.validation, args.replay, args.pose)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        parser.exit(1, str(exc) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
