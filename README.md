# Project Inaba (MurasamePet-Inaba-clean)

[English](#english) | [中文說明](#chinese)

---

<a name="english"></a>
## 🇬🇧 English

This is a clean, refactored version based on [MurasamePet](https://github.com/LemonQu-GIT/MurasamePet), featuring a **PyQt5** frontend GUI. It implements head-pat interactions, bilingual text generation, and API services. The project provides a complete backend API, desktop pet frontend, health check scripts, and automated tests for quick setup and testing on Windows.

### ⚠️ Development Status (Prototype)

This software is currently in the **Early Access / MVP** stage.
*   You may encounter bugs, unexpected crashes, or unused legacy files.
*   Features and API structures are subject to change without notice.
*   Feedback is welcome, but please use it with a "testing" mindset.

### 🤖 AI Models

This project integrates multi-modal AI capabilities for richer interactions:

*   **Thinking & Chat Model**: Currently powered by **InabaV1 (Qwen 2.5 7B based)** (via Ollama), with plans to upgrade to **Qwen 3 8B** for better reasoning and role-play capabilities.
*   **Visual Recognition**: Upcoming integration with **Qwen 3 VL 4B**, allowing Inaba to "see" and react to on-screen content.
*   **Speech Synthesis**: Uses a custom TTS solution (VoiceVox dependency has been removed).

### Features Overview

*   **/qwen3**: Proxy for local Ollama chat interface, returning chat responses and history.
*   **/reply_bi**: Generates bilingual (Chinese/Japanese) responses.
*   **/tts**: Text-to-Speech synthesis service.
*   **/say**: Generates speech from text and returns subtitles, chaining `/qwen3` and `/tts` internally.
*   **/pat**: Simulates head-pat interaction, triggering `/say` to generate a short phrase with voice and subtitles.
*   **Desktop Pet Frontend**: `pet.py` uses PyQt5 to display the character, listens for mouse interactions on the head area, and plays voice/subtitles upon double-click triggers.

### 📥 Model Setup (Required)

Because the model file is large (~4.7GB), it is not included in the main download. You must download and import it into Ollama manually.

1.  **Install Ollama**: Download from [ollama.com](https://ollama.com).
2.  **Download Model Files**:
    *   Download `meguru_q4_k_m.gguf` and `Modelfile` from Hugging Face:
    *   [https://huggingface.co/wallouo/InabaV1/tree/main](https://huggingface.co/wallouo/InabaV1/tree/main)
3.  **Import to Ollama**:
    Open PowerShell in the folder where you downloaded the files and run:
    ```powershell
    ollama create meguru -f Modelfile
    ```
4.  **Verify**: Run `ollama list` to confirm that `meguru` is available.

### Installation & Prerequisites

1.  **Python 3.9.x** or higher is recommended.
2.  Ensure **Ollama** is running and the `meguru` model is created (see step above).

### 🚀 How to Run

This project includes a one-click startup script that handles dependency installation and environment setup automatically.

**Steps:**
1.  Right-click on the `run_local.ps1` file.
2.  Select **"Run with PowerShell"**.

The script will automatically:
*   Create a virtual environment.
*   Install necessary packages.
*   Start the backend API server.
*   Launch the frontend desktop pet application.

### Health Check & Testing

If you are a developer, you can use the following scripts for debugging:

*   **Health Check**: Run `scripts/healthcheck.py` to verify Ollama service status.
*   **Unit Tests**: Run `python -m unittest discover -v` in the root directory to test API functionality.

---

<a name="chinese"></a>
## 🇹🇼 中文說明

這是一個基於 [MurasamePet](https://github.com/LemonQu-GIT/MurasamePet) 重構的乾淨版本，使用 **PyQt5** 作為前端 GUI，實現摸頭互動、雙語生成與 API 服務。專案提供完整的後端 API、前端桌寵、健康檢查腳本和自動化測試，方便在 Windows 本機快速搭建和測試。

### ⚠️ 開發中版本 (Prototype)

本程式目前處於 **早期開發階段 (MVP)**。
*   可能會遇到 Bug、未預期的崩潰或無用的殘留檔案。
*   功能與 API 結構可能隨時變動。
*   歡迎反饋問題，但請以「測試版」的心態使用。

### 🤖 模型架構

本專案整合了多模態 AI 能力，以實現更豐富的互動：

*   **思考與對話模型**：目前使用 **InabaV1 (基於 Qwen 2.5 7B)** (Ollama)，計畫升級至 **Qwen 3 8B** 以獲得更強的邏輯與角色扮演能力。
*   **視覺識別模型**：即將整合 **Qwen 3 VL 4B**，讓 Inaba 能夠「看見」螢幕上的內容並做出反應。
*   **語音合成**：使用自定義的 TTS 方案 (不再依賴 VoiceVox)。

### 功能概述

*   **/qwen3**：代理本地 Ollama 的聊天接口，返回聊天回應和歷史。
*   **/reply_bi**：生成中日雙語回覆。
*   **/tts**：語音合成服務。
*   **/say**：根據文字生成語音並返回字幕，內部串接 `/qwen3` 和 `/tts`。
*   **/pat**：模擬摸頭互動，調用 `/say` 產生一句短句並返回語音與字幕。
*   **前端桌寵**：`pet.py` 使用 PyQt5 顯示角色立繪，監聽頭部區域滑鼠操作或雙擊以觸發 `/pat`，播放語音並顯示字幕。

### 📥 模型設置 (必要步驟)

由於模型檔案較大 (~4.7GB)，未包含在主程式下載中。你需要手動下載並匯入 Ollama。

1.  **安裝 Ollama**：請至 [ollama.com](https://ollama.com) 下載並安裝。
2.  **下載模型檔案**：
    *   從 Hugging Face 下載 `meguru_q4_k_m.gguf` 和 `Modelfile`：
    *   [https://huggingface.co/wallouo/InabaV1/tree/main](https://huggingface.co/wallouo/InabaV1/tree/main)
3.  **匯入 Ollama**：
    在下載檔案的資料夾開啟 PowerShell，執行以下指令：
    ```powershell
    ollama create meguru -f Modelfile
    ```
4.  **驗證**：執行 `ollama list` 確認列表中有 `meguru` 模型。

### 安裝與準備

1.  建議使用 **Python 3.9.x** 或更高版本。
2.  請確保 **Ollama** 正在運行，並且已建立 `meguru` 模型（見上一步驟）。

### 🚀 啟動方式

本專案提供了一鍵啟動腳本，會自動處理依賴安裝與環境設置。

**步驟：**
1.  在 `run_local.ps1` 檔案上點擊 **右鍵**。
2.  選擇 **「使用 PowerShell 執行」 (Run with PowerShell)**。

腳本將會自動：
*   建立虛擬環境
*   安裝必要套件
*   啟動後端 API 伺服器
*   啟動前端桌寵程式

### 健康檢查與測試

如果你是開發者，可以使用以下腳本進行除錯：

*   **健康檢查**：運行 `scripts/healthcheck.py` 以檢查 Ollama 服務狀態。
*   **單元測試**：在根目錄運行 `python -m unittest discover -v` 進行 API 功能測試。
