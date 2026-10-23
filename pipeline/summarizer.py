import os
import shlex
import subprocess
import sys
from pathlib import Path

# agy 1.4.2 實測（docs/notes/2026-10-19-agy-findings.md）：
# - 預設不設逾時，必須明確指定 --print-timeout
# - 不會把 stdin 當作提示詞內容，逐字稿只能放進提示詞（argv）
# - --mode plan 會產出實作計畫檔而不是摘要，不使用
AGY_PRINT_TIMEOUT = "5m"
AGY_PRINT_TIMEOUT_SEC = 300

# Linux 單一命令列參數上限為 128KiB；保留餘裕
MAX_PROMPT_BYTES = 100_000

_SUBPROCESS_GRACE_SEC = 30
_CLI_PATH = Path(__file__).resolve().parents[1] / "meeting_pipeline.py"


def build_agy_prompt(transcript_text: str) -> str:
    return (
        "你是專業的會議記錄助理。以下是一份會議逐字稿，"
        "每段以 **[開始 - 結束] [說話者]** 標示時間與說話者。"
        "請只根據逐字稿內容，不要使用任何工具，以繁體中文 Markdown 輸出以下三個章節，不要輸出其他前言或結語：\n\n"
        "## 會議核心摘要\n3 至 5 點濃縮重點。\n\n"
        "## 關鍵決議事項 (Decisions)\n會議中拍板定案的結論；若無，寫「無」。\n\n"
        "## 待辦事項清單 (Action Items)\n"
        "以 Markdown 表格呈現，欄位依序為："
        "| 負責人 (Owner) | 待辦任務內容 (Task) | 預計完成期限 (Deadline) | 來源時間戳記 (Timestamp) |。\n"
        "負責人請寫逐字稿中的說話者，並依上下文在括號內推論其姓名或角色；"
        "期限未提及時寫「未指定」；來源時間戳記必須是逐字稿中對應段落的開始時間。\n\n"
        "=== 逐字稿開始 ===\n"
        f"{transcript_text}\n"
        "=== 逐字稿結束 ==="
    )


def build_agy_command(transcript_text: str, agy_model: str | None = None) -> list[str]:
    cmd = ["agy", "-p", build_agy_prompt(transcript_text), "--print-timeout", AGY_PRINT_TIMEOUT]
    if agy_model:
        cmd += ["--model", agy_model]
    return cmd


def format_rerun_command(transcript_path: Path, agy_model: str | None = None) -> str:
    cmd = [sys.executable, str(_CLI_PATH), "--summarize-only", str(transcript_path.resolve())]
    if agy_model:
        cmd += ["--agy-model", agy_model]
    return shlex.join(cmd)


def generate_meeting_summary(
    transcript_path: Path, summary_path: Path, agy_model: str | None = None
) -> bool:
    transcript_text = transcript_path.read_text(encoding="utf-8")
    cmd = build_agy_command(transcript_text, agy_model)
    prompt_bytes = len(cmd[2].encode("utf-8"))
    if prompt_bytes > MAX_PROMPT_BYTES:
        return _fail(
            f"逐字稿過長（提示詞 {prompt_bytes} bytes，上限 {MAX_PROMPT_BYTES}）；請將逐字稿分段後各別總結",
            transcript_path,
            agy_model,
        )
    try:
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,  # agy 會嘗試讀 stdin；關掉以免被拒絕或卡住
            capture_output=True,
            text=True,
            timeout=AGY_PRINT_TIMEOUT_SEC + _SUBPROCESS_GRACE_SEC,
        )
    except FileNotFoundError:
        return _fail("找不到 agy 執行檔，請確認 Antigravity CLI 已安裝並在 PATH 中", transcript_path, agy_model)
    except subprocess.TimeoutExpired:
        return _fail("agy 執行逾時", transcript_path, agy_model)
    except OSError as exc:
        return _fail(f"無法啟動 agy：{exc}", transcript_path, agy_model)
    if result.returncode != 0:
        return _fail(
            f"agy 結束碼 {result.returncode}（可能未登入或模型名稱無效）：{(result.stderr or '').strip()}",
            transcript_path,
            agy_model,
        )
    summary = (result.stdout or "").strip()
    if not summary:
        detail = (result.stderr or "").strip()
        return _fail(
            "agy 沒有輸出任何內容" + (f"：{detail}" if detail else ""), transcript_path, agy_model
        )
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
