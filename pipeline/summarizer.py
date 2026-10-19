import os
import shlex
import subprocess
import sys
from pathlib import Path

# 以下三個常數依 Task 0 在 Mac 上 `agy --help` 的實測結果填寫
AGY_PRINT_TIMEOUT = "5m"
AGY_PRINT_TIMEOUT_SEC = 300
AGY_READONLY_ARGS: tuple[str, ...] = ("--mode", "plan")

_SUBPROCESS_GRACE_SEC = 30
_CLI_PATH = Path(__file__).resolve().parents[1] / "meeting_pipeline.py"


def build_agy_prompt() -> str:
    return (
        "你是專業的會議記錄助理。標準輸入（stdin）是一份會議逐字稿，"
        "每段以 **[開始 - 結束] [說話者]** 標示時間與說話者。"
        "請只根據逐字稿內容，以繁體中文 Markdown 輸出以下三個章節，不要輸出其他前言或結語：\n\n"
        "## 會議核心摘要\n3 至 5 點濃縮重點。\n\n"
        "## 關鍵決議事項 (Decisions)\n會議中拍板定案的結論；若無，寫「無」。\n\n"
        "## 待辦事項清單 (Action Items)\n"
        "以 Markdown 表格呈現，欄位依序為："
        "| 負責人 (Owner) | 待辦任務內容 (Task) | 預計完成期限 (Deadline) | 來源時間戳記 (Timestamp) |。\n"
        "負責人請寫逐字稿中的說話者，並依上下文在括號內推論其姓名或角色；"
        "期限未提及時寫「未指定」；來源時間戳記必須是逐字稿中對應段落的開始時間。"
    )


def build_agy_command(agy_model: str | None = None) -> list[str]:
    cmd = ["agy", "-p", build_agy_prompt(), "--print-timeout", AGY_PRINT_TIMEOUT, *AGY_READONLY_ARGS]
    if agy_model:
        cmd += ["--model", agy_model]
    return cmd


def format_rerun_command(transcript_path: Path, agy_model: str | None = None) -> str:
    cmd = ["python3", str(_CLI_PATH), "--summarize-only", str(transcript_path)]
    if agy_model:
        cmd += ["--agy-model", agy_model]
    return shlex.join(cmd)


def generate_meeting_summary(
    transcript_path: Path, summary_path: Path, agy_model: str | None = None
) -> bool:
    transcript_text = transcript_path.read_text(encoding="utf-8")
    try:
        result = subprocess.run(
            build_agy_command(agy_model),
            input=transcript_text,
            capture_output=True,
            text=True,
            timeout=AGY_PRINT_TIMEOUT_SEC + _SUBPROCESS_GRACE_SEC,
        )
    except FileNotFoundError:
        return _fail("找不到 agy 執行檔，請確認 Antigravity CLI 已安裝並在 PATH 中", transcript_path, agy_model)
    except subprocess.TimeoutExpired:
        return _fail("agy 執行逾時", transcript_path, agy_model)
    if result.returncode != 0:
        return _fail(
            f"agy 結束碼 {result.returncode}（可能未登入）：{(result.stderr or '').strip()}",
            transcript_path,
            agy_model,
        )
    summary = (result.stdout or "").strip()
    if not summary:
        return _fail("agy 沒有輸出任何內容", transcript_path, agy_model)
    temp_path = summary_path.with_name(summary_path.name + ".tmp")
    temp_path.write_text(summary + "\n", encoding="utf-8")
    os.replace(temp_path, summary_path)
    return True


def _fail(reason: str, transcript_path: Path, agy_model: str | None) -> bool:
    print(
        f"[summary] 會議總結失敗：{reason}\n"
        f"已保留字幕與逐字稿。修正後可執行以下指令只重新產生總結：\n"
        f"  {format_rerun_command(transcript_path, agy_model)}",
        file=sys.stderr,
    )
    return False
