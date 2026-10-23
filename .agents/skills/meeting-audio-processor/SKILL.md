---
name: meeting-audio-processor
description: >-
  Use this skill automatically whenever the user provides, attaches, mentions, or points to an audio or video recording file (e.g., .m4a, .mp3, .wav, .aac, .flac, .ogg, .mp4, .mov, .webm, .mkv, .avi, .m4v), or requests meeting audio processing, even without any prompt or explicit instructions. If a video is provided, automatically extracts the audio track via ffmpeg first. Prompts the user with an interactive checklist (ask_question) to select desired output documents (up to 9 documents: 4 source, 4 translated, 1 bilingual timeline transcript), then natively processes the audio using multimodal LLM understanding without external tools or models, generating only the requested documents.
---

# 會議影音零提示詞互動處理 Skill (Zero-Prompt Interactive Meeting Processor)

當使用者（或同事）提供任何會議**音訊**或**影片**檔案時，**本技能會自動觸發**。

「零提示詞」的定義為：使用者上傳檔案時**無需輸入任何複雜提示詞或指令**（例如僅發送檔案路徑、錄音檔名或空白提示）。但代理人**絕對不可**採取全自動端到端盲目輸出，而**必須先停下來彈出互動勾選表單**，讓使用者自主決定本次欲輸出的文件種類後，才精準執行生成。

---

## 核心約束與原則

1. **強制阻塞式互動閘門（Mandatory Blocking Execution Gate）**：
   > [!CAUTION] 強制阻塞規範 (Blocking Gate)
   > 代理人在接收到影音檔案並完成必要的影片音訊抽取後，**首要動作【必須】是調用 `ask_question` 彈出多選勾選表單，並【立即結束當前回合】等待使用者勾選**！
   > 嚴禁在未收到使用者勾選提交結果之前，逕自調用 `write_file` 預先生成任何逐字稿或會議報告！

2. **轉錄總結零外部模型依賴**：
   - 轉錄與語意分析環節**嚴禁調用外部 ASR/分軌模型**（如 Whisper、pyannote、PyTorch 等）。
   - 直接使用 `read_file` 載入音訊檔案進行原生多模態音訊聆聽與分析。

3. **影片自動輕量化抽取**：
   - 若輸入為影片檔（如 `.mp4`、`.mov` 等），使用系統內建 `ffmpeg` 快速剝離影像軌（`-vn`），轉出體積小且品質清晰的 `.m4a` 音訊檔，保證低於 100 MB 上限。

4. **精準依勾選動態生成**：
   - 嚴格依照使用者在表單中勾選的項目進行生成（最多 9 份），未勾選之項目一律不產生，節省時間與 Context。

5. **專屬資料夾隔離**：
   - 所有產出檔案與萃取之音訊一律寫入工作目錄下的 `./minutes_<主檔名>/`，避免散落污染根目錄。

---

## 執行流程（Step-by-Step）

### 步驟 0：檔案類型檢測與影片自動轉檔（Video-to-Audio Pre-processing）

1. 識別輸入檔案路徑，取得主檔名 `<stem>` 與副檔名 `<ext>`。
2. 建立目標輸出資料夾：`./minutes_<stem>/`。
3. **檢查副檔名**：
   - **若是影片格式**（`.mp4`, `.mov`, `.webm`, `.mkv`, `.avi`, `.m4v` 等）：
     - 執行 `ffmpeg` 快速剝離影像軌並抽取為 128kbps AAC 純音訊：
       ```bash
       ffmpeg -y -i "<輸入影片路徑>" -vn -c:a aac -b:a 128k "./minutes_<stem>/<stem>_extracted.m4a"
       ```
     - 萃取完成後，將目標音訊路徑設為 `./minutes_<stem>/<stem>_extracted.m4a`。
   - **若是純音訊格式**（`.m4a`, `.mp3`, `.wav`, `.aac`, `.flac`, `.ogg` 等）：
     - 直接將目標音訊路徑設為輸入檔案路徑。

---

### 步驟 1：【強制阻塞閘門】彈出互動多選表單 (`ask_question`)

**本步驟為強制中斷點！代理人必須在此停止，等待使用者作答。**

1. **例外判斷**：
   - 只有在使用者**一開始的對話輸入中已明確指名特定文件種類**時（例如：「請只幫我整理待辦事項」或「只要時間線雙語逐字稿」），才可跳過此步驟並僅生成指定項目。
   - 凡是一般輸入（例如僅提供檔案路徑、或說「這是一段會議錄音」、「幫我整理」），**一律強制執行 `ask_question`**。

2. **調用 `ask_question`**：
   ```json
   {
     "questions": [
       {
         "question": "已就緒！請勾選本次會議您希望輸出的文件種類：",
         "is_multi_select": true,
         "options": [
           "(Recommended) 全選所有 9 份完整文件套裝",
           "01. 原文逐字稿 (01_transcript_[orig].md)",
           "02. 原文決策摘要 (02_decisions_[orig].md)",
           "03. 原文待辦事項清單 (03_action_items_[orig].md)",
           "04. 原文專業會議報告 (04_meeting_minutes_[orig].md)",
           "05. 翻譯版逐字稿 (01_transcript_[trans].md)",
           "06. 翻譯版決策摘要 (02_decisions_[trans].md)",
           "07. 翻譯版待辦事項清單 (03_action_items_[trans].md)",
           "08. 翻譯版專業會議報告 (04_meeting_minutes_[trans].md)",
           "09. 時間線中英雙語對照逐字稿 (05_bilingual_timeline_transcript.md)"
         ]
       }
     ]
   }
   ```
3. **結束輪次**：
   - 呼叫完 `ask_question` 後，**立即停止呼叫其他工具**，將控制權交還給使用者，等待勾選結果回傳。

---

### 步驟 2：解析使用者勾選並載入音訊

當接收到使用者勾選的回覆後：
1. **解析勾選項**：
   - 若勾選包含「全選所有 9 份完整文件套裝」，則將 01～09 全數納入生成清單。
   - 否則，僅將使用者勾選的項目代號加入清單。
2. **音訊載入**：
   - 調用 `read_file` 載入目標音訊檔進入模型多模態 Context。
3. **多模態聲學與語意分析**：
   - 判定主要語言（英文 ➔ 繁中 zh-TW；中文 ➔ 專業英文 en）。
   - 區分說話者聲學特徵與稱謂對應（`[說話者 1 / 王經理]`）。
   - 提取時間軸區間標籤 `[MM:SS - MM:SS]`。

---

### 步驟 3：生成已勾選之原文核心文件 (Original Documents)

參照 [標準樣板規範](./resources/templates.md)，**僅針對有勾選的項目調用 `write_file`** 存於 `./minutes_<stem>/`：

- **若包含 01** ➔ **`01_transcript_[orig].md`（原文完整逐字稿）**：說話者角色分段、過濾贅詞。
- **若包含 02** ➔ **`02_decisions_[orig].md`（原文決策摘要）**：定案決策、被否決/保留方案及原因。
- **若包含 03** ➔ **`03_action_items_[orig].md`（原文待辦事項清單）**：標準 Markdown 表格（ID、任務、負責人、截止日、優先級、驗收標準）。
- **若包含 04** ➔ **`04_meeting_minutes_[orig].md`（原文專業會議報告）**：Executive Summary、議程深入討論、決策總覽、風險與里程碑。

---

### 步驟 4：術語對齊與生成已勾選之翻譯文件 (Translated Documents)

**僅在勾選項包含 05、06、07、08 任一項時執行**：

1. **專有名詞與術語對齊（Glossary Consistency）**：統一專案名詞、技術術語與人員職稱。
2. **翻譯原則**：英文 ➔ 繁體中文（zh-TW）；中文 ➔ 專業商務英文（en）。
3. **依勾選生成**：
   - **若包含 05** ➔ **`01_transcript_[trans].md`**
   - **若包含 06** ➔ **`02_decisions_[trans].md`**
   - **若包含 07** ➔ **`03_action_items_[trans].md`**
   - **若包含 08** ➔ **`04_meeting_minutes_[trans].md`**

---

### 步驟 5：生成時間線雙語對照逐字稿（若勾選）

**若勾選包含 09** ➔ 調用 `write_file` 寫入 **`05_bilingual_timeline_transcript.md`**：
- 將時間軸切片、說話者標籤、原文逐字內容與上下文翻譯整合在同一段落區塊（區塊引言並列排版）：

```markdown
### [00:01:15 - 00:01:45] 說話者 A / Speaker A (王經理)
> **原文 (zh-TW)**：今天主要要敲定 Q4 產品發布的時程，尤其是前端畫面重構與後端 API 對接的進度。
>
> **翻譯 (en)**: Today's main objective is to finalize the Q4 product release schedule, particularly the frontend refactoring and backend API integration progress.
```

---

### 步驟 6：回覆與呈現產出文件導覽

所有勾選檔案寫入完成後，向使用者輸出總覽清單：
1. 標示會議主檔名、輸入類型（音訊或由影片萃取）、主要語言、辨識說話者人數。
2. **僅列出本次實際勾選並生成的文件清單**，附上相對 Markdown 連結與簡述。
3. 簡短列出會議最重要的 3~5 項關鍵決策與待辦摘要。
