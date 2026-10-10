#!/usr/bin/env python3
"""Exercise the packaged inline viewer; this is not a Windows/file-URL test.

Requires Python Playwright and Chromium. Managed cloud browsers forbid file://,
so load the exact HTML bytes with set_content, without a local HTTP service.
"""
import argparse
import base64
import hashlib
import json
import math
import re
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


def run(package, browser, screenshot=None):
    checks = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    with zipfile.ZipFile(package) as archive:
        check("package_crc", archive.testzip() is None)
        check("package_contents", set(archive.namelist()) == {
            "abrir-laboratorio.html", "LEIA-ME.txt", "manifest.json"})
        html_bytes = archive.read("abrir-laboratorio.html")
        html = html_bytes.decode("utf-8")
        manifest = json.loads(archive.read("manifest.json"))
    check("html_manifest_hash", hashlib.sha256(html_bytes).hexdigest() == manifest["html_sha256"])
    encoded = re.search(r'<script id="bundle" type="application/octet-stream">([^<]+)</script>', html)
    check("embedded_bundle_hash", encoded is not None and hashlib.sha256(
        base64.b64decode(encoded.group(1), validate=True)).hexdigest() == manifest["sha256"])
    errors, requests = [], []
    with sync_playwright() as playwright:
        chromium = playwright.chromium.launch(executable_path=browser, headless=True)
        try:
            page = chromium.new_page(viewport={"width": 1320, "height": 940}, accept_downloads=True)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: requests.append(request.url))
            page.set_content(html, wait_until="load", timeout=60000)
            page.wait_for_function("window.pes3Lab && window.pes3Lab.snapshot().pose", timeout=60000)

            def snapshot():
                return page.evaluate("window.pes3Lab.snapshot()")

            def seek(value):
                page.eval_on_selector("#timeline", "(element,value)=>{element.value=value;"
                                      "element.dispatchEvent(new Event('input'));}", value)
                page.wait_for_function("value=>window.pes3Lab.snapshot().time===value", arg=value)
                page.evaluate("()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")

            def choose(clip):
                page.locator("#clip").fill(str(clip))
                page.locator("#clip").press("Tab")
                page.evaluate("()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")

            state = snapshot()
            check("clip_inventory", state["clipCount"] == 1105 and state["clip"] == 47)
            check("nineteen_finite_joints", len(state["pose"]) == len(state["world"]) == 19 and all(
                math.isfinite(v) for bone in state["pose"] for values in bone.values() for v in values))
            check("no_automatic_gesture_labels", state["annotationCount"] == 0)
            check("canvas_has_skeleton_pixels", page.eval_on_selector("#scene", "canvas=>{"
                  "const rgba=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;"
                  "let bright=0;for(let i=0;i<rgba.length;i+=4){"
                  "if(rgba[i]>210&&rgba[i+1]>210&&rgba[i+2]>210&&rgba[i+3]>200)bright++;}"
                  "return bright>100;}"))

            page.locator("#play").click()
            page.wait_for_function("window.pes3Lab.snapshot().time>1")
            check("playback_advances", snapshot()["playing"])
            page.locator("#play").click()
            check("pause_stops_playback", not snapshot()["playing"])

            choose(1022)
            seek(112)
            at_endpoint = snapshot()["pose"]
            seek(114)
            check("sentinel_is_not_a_new_pose", snapshot()["pose"] == at_endpoint
                  and float(page.locator("#timeline").get_attribute("max")) == 114)
            page.locator("#previous-key").click()
            check("previous_original_key", snapshot()["time"] == 112)
            page.locator("#next-key").click()
            check("next_endpoint", snapshot()["time"] == 114)
            seek(33.75)
            local_pose = snapshot()["pose"]
            page.locator("#follow").uncheck()
            page.evaluate("()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
            check("preview_follow_preserves_local_pose", snapshot()["pose"] == local_pose)
            page.locator("#follow").check()

            page.locator("#category").select_option("walk")
            check("manual_candidate_annotation", snapshot()["annotationCount"] == 1)
            with page.expect_download() as event:
                page.locator("#export").click()
            with tempfile.TemporaryDirectory(prefix="pes3-export-") as temp:
                destination = Path(temp) / event.value.suggested_filename
                event.value.save_as(destination)
                catalogue = json.loads(destination.read_text())
            entry = catalogue["entries"][0]
            check("export_retains_source_and_time", catalogue["bundle_sha256"] == manifest["sha256"]
                  and entry["clip"] == 1022 and entry["observed_time_original_units"] == 33.75
                  and len(entry["block_sha256"]) == 64 and entry["category"] == "walk")
            check("export_does_not_enable_gameplay", entry["classification_status"] == "visual_candidate"
                  and all(entry[key] is False for key in [
                      "retargeting_validated", "contact_validated", "runtime_enabled"]))
            page.locator("#category").select_option("")
            check("annotation_can_be_removed", snapshot()["annotationCount"] == 0)

            choose(1104)
            page.locator("#next-clip").click()
            check("last_to_first_clip", snapshot()["clip"] == 0)
            page.locator("#previous-clip").click()
            check("first_to_last_clip", snapshot()["clip"] == 1104)
            choose(-1)
            check("invalid_id_preserves_selection", snapshot()["clip"] == 1104
                  and page.locator("#clip").input_value() == "1104")
            choose(47)
            page.locator("#scene").focus()
            page.keyboard.press("ArrowRight")
            check("keyboard_clip_navigation", snapshot()["clip"] == 48)
            page.keyboard.press("Space")
            check("keyboard_playback", snapshot()["playing"])
            page.keyboard.press("Space")

            choose(47)
            page.locator("#fit").click()
            page.set_viewport_size({"width": 700, "height": 1000})
            page.evaluate("()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
            rectangle = page.locator("#scene").bounding_box()
            check("narrow_viewport_canvas_visible", rectangle is not None and rectangle["width"] > 300
                  and rectangle["x"] >= 0 and rectangle["x"] + rectangle["width"] <= 700)
            page.set_viewport_size({"width": 1320, "height": 940})
            page.evaluate("()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
            if screenshot:
                if screenshot.exists():
                    raise FileExistsError(screenshot)
                page.screenshot(path=str(screenshot), full_page=True)
            check("no_javascript_errors", not errors and not page.locator("#error").is_visible())
            check("no_network_requests", not requests)
        finally:
            chromium.close()
    return {"schema_version": 1, "result": "passed", "run_id": str(uuid.uuid4()),
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "package_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
            "html_sha256": manifest["html_sha256"], "checks": len(checks), "passed_checks": checks,
            "javascript_errors": errors, "network_requests": requests,
            "load_method": "set_content_exact_packaged_inline_html",
            "scope": "Chromium inline-document functional checks in cloud; file-URL opening and Windows Edge not executed."}


def main():
    parser = argparse.ArgumentParser(description="Verificar o laboratório empacotado em Chromium")
    parser.add_argument("package", type=Path)
    parser.add_argument("--browser", default=shutil.which("chromium"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    if not args.browser:
        parser.error("Chromium não encontrado; informe --browser")
    if args.output.exists():
        parser.error("escolha um arquivo de relatório novo")
    result = run(args.package, args.browser, args.screenshot)
    with args.output.open("x") as output:
        output.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
