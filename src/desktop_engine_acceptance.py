"""One-match acceptance against the selected local FM27 native engine."""
from pathlib import Path

from fm27_batch import BatchRunner


def run_smoke(root, output_dir, timeout=190):
    """Run the bundled baseline fixture through the real native match host.

    Success requires BatchRunner's full native log, natural-finish, statistics,
    compatibility, and session-cleanup checks. A process start alone is not
    considered an acceptance result.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    log_path = output_dir / "native-match.jsonl"
    runner = BatchRunner(root, workers=1, retries=0, timeout=timeout)
    result = runner.one({
        "key": "local-engine-acceptance",
        "seed": None,
        "variant": "native-engine-acceptance",
        "path": str(log_path),
    })
    if result.get("failed") or not result.get("verified"):
        return {
            "ok": False,
            "stage": result.get("failure_phase", "native_match_validation"),
            "errors": result.get("errors", ["原生比赛未通过完整验收"]),
            "attempts": result.get("attempts", 1),
            "log": str(log_path.resolve()),
        }

    missing = []
    if not result.get("result", {}).get("full_match_completed"):
        missing.append("natural_match_finished")
    if not result.get("statistics"):
        missing.append("native_match_statistics")
    if not result.get("timings"):
        missing.append("native_timings")
    if missing:
        return {
            "ok": False,
            "stage": "acceptance_evidence",
            "errors": ["缺少验收证据：" + ", ".join(missing)],
            "log": str(log_path.resolve()),
        }

    return {
        "ok": True,
        "stage": "native_match_completed",
        "match": result["result"],
        "statistics": result["statistics"],
        "timings": result["timings"],
        "engine_compatibility": result.get("engine_compatibility"),
        "engine_dll_sha256": result.get("engine_dll_sha256"),
        "elapsed_seconds": result.get("elapsed_seconds"),
        "log": str(log_path.resolve()),
    }
