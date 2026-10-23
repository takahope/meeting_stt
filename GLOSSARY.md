# Meeting Pipeline

把一場錄製完成的會議錄音，轉成標註「誰在何時說了什麼」的字幕、逐字稿與會議總結。

## Language

### 聲音與時間軸

**Recording（錄音）**:
使用者提供的一場會議原始音訊或視訊檔，一次處理一份。
_Avoid_: 音檔、input、source

**Word（單字）**:
語音辨識產出的最小文字單位，帶有起訖時間；中文通常為單一字，英文為一個英文單字。
_Avoid_: token、詞

**Speaker Turn（說話區間）**:
說話者辨識判定「某位說話者正在發聲」的一段連續時間；不同說話者的區間可能重疊。
_Avoid_: segment、turn

### 說話者

**Speaker Label（說話者標籤）**:
說話者辨識自動給出的匿名代號（如 `SPEAKER_00`），只在單一錄音內有意義，同一真人可能被拆成多個標籤。
_Avoid_: speaker id、speaker

**Display Name（顯示名稱）**:
使用者為某個說話者標籤指定的真實姓名或職稱（如「王經理」），只出現在輸出物上，不參與對齊或切分。
_Avoid_: 實名、speaker name、alias

### 輸出物

**Cue（字幕條）**:
同一說話者標籤、時間連續的若干單字所組成的一條字幕，受字數單位與時長上限約束。
_Avoid_: subtitle block、字幕塊、segment

**Text Unit（字數單位）**:
衡量字幕長度的計量：一個中文字計 1，一個英文單字計 1.5，標點不計。
_Avoid_: 字數、character count

**Transcript（逐字稿）**:
依說話者分段、附時間戳記的完整會議文字，是總結的唯一輸入。
_Avoid_: 文字稿、記錄

**Summary（會議總結）**:
由線上模型根據逐字稿產出的摘要、決議事項與待辦事項；待辦事項必須能以時間戳記回溯到逐字稿。
_Avoid_: 會議記錄、report、minutes
