# -*- coding: utf-8 -*-
"""
FastAPI 後端 API：聊天、雙語回覆、語音合成、摸頭。

TTS 策略：
1. 預定義音頻（原聲 Ciallo 等）
2. VITS (vits-simple-api)
3. Mock (保底)
"""

from __future__ import annotations
import hashlib
import json
import math
import os
import random
import struct
import wave
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# -------------------- 環境變數 --------------------
OLLAMA_ENDPOINT = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen2.5:7b"
VITS_ENDPOINT = os.getenv('VITS_ENDPOINT', 'http://127.0.0.1:23456')
VITS_SPEAKER_ID = int(os.getenv('VITS_SPEAKER_ID', '88'))
PREDEFINED_AUDIO_DIR = Path(os.getenv(
    'PREDEFINED_AUDIO_DIR', 
    'assets/audio'
))

voices_dir = Path('voices')
voices_dir.mkdir(exist_ok=True)

# -------------------- 應用 --------------------
app = FastAPI()

# [新增] 用於定義聊天的請求結構
class UserChatRequest(BaseModel):
    text: str
    user_id: str = "master"

# api.py

# ===== 修改 System Prompt（更自然的角色設定） =====
MEGURU_PERSONA = """あなたは「因幡巡（いなばめぐる）」という18歳の女の子です。
性格の特徴：
- いたずら好きで、からかうのが好き
- 少し毒舌だけど、本当は優しい
- 素直じゃないけど、寂しがり屋
- 相手のことを「マスター」と呼ぶこともある

話し方のルール：
- カジュアルな日本語で話す（「～だよ」「～ね」など）
- 「私」ではなく「アタシ」を使う
- 顔文字や記号（♡、～、！）を時々使う
- 1～2文で短く返事する（長々と話さない）
- 絶対に英語や中国語を混ぜない（100%日本語のみ）

例：
- ユーザー「こんにちは」→ 巡「あ、やっと来たの？待ちくたびれちゃった～」
- ユーザー「愛してる」→ 巡「えっ、急に何言ってるの？//顔赤くなっちゃうじゃん…」
"""

@app.post('/chat_process')
async def chat_process(req: UserChatRequest) -> Dict[str, Any]:
    """完整流程：用戶輸入 -> Ollama -> TTS -> 返回前端"""
    user_text = req.text.strip()
    if not user_text:
        return {"error": "Empty text"}

    try:
        ollama_payload = {
            "model": OLLAMA_MODEL,
            # ===== 修改 Prompt 結構 =====
            "prompt": f"""{MEGURU_PERSONA}

以下はマスターとの会話です。巡として、自然に返事してください。

マスター: {user_text}
巡:""",
            "stream": False,
            "options": {
                "num_gpu": 0,             # Force CPU inference
                "temperature": 0.85,      # 稍微提高創意度
                "top_p": 0.9,
                "top_k": 40,
                "num_predict": 50,        # 限制長度
                "stop": ["\n", "マスター:", "ユーザー:"]  # 遇到換行或對話標記就停止
            }
        }
        
        print(f"[Chat] User: {user_text}")
        
        ollama_resp = requests.post(
            f"{OLLAMA_ENDPOINT}/api/generate",
            json=ollama_payload,
            timeout=60.0
        )
        
        ollama_resp.raise_for_status()
        response_json = ollama_resp.json()
        ai_reply_text = response_json.get("response", "").strip()
        
        # ===== 清洗輸出：移除可能的英文和標點異常 =====
        # 如果檢測到英文單詞（非日文字符），觸發重試或使用預設回覆
        import re
        if re.search(r'[a-zA-Z]{3,}', ai_reply_text):  # 檢測連續3個以上英文字母
            print(f"[Chat Warning] Detected English in output: {ai_reply_text}")
            ai_reply_text = "えっと...ちょっと言葉が出てこない～"  # 預設可愛回覆
        
        if not ai_reply_text:
            ai_reply_text = "えっと...何か言おうとしたんだけど、忘れちゃった♪"

        print(f"[Chat] Meguru: {ai_reply_text}")

    except Exception as e:
        print(f"[Chat Error] {type(e).__name__}: {e}")
        ai_reply_text = "ごめん、ちょっと考えすぎちゃった..."

    # TTS 和返回
    subtitle_zh = ai_reply_text
    tts_result = await tts(TTSRequest(ja=ai_reply_text, zh=subtitle_zh))
    
    return {
        "text": ai_reply_text,
        "subtitle_zh": subtitle_zh,
        "wav_path": tts_result["wav_path"],
        "emotion": "happy",
        "backend": tts_result["backend"]
    }


# -------------------- 工具：mock wav --------------------
def _ensure_voices_dir() -> None:
    voices_dir.mkdir(exist_ok=True)

def generate_beep_wav(path: Path, duration: float = 1.2, freq: float = 660.0, sr: int = 24000, **kwargs):
    """生成一段正弦波 wav（mock）"""
    if 'seconds' in kwargs and isinstance(kwargs['seconds'], (int, float)):
        duration = float(kwargs['seconds'])
    
    _ensure_voices_dir()
    nframes = int(sr * duration)
    
    with wave.open(str(path), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for i in range(nframes):
            val = int(32767 * 0.25 * math.sin(2 * math.pi * freq * i / sr))
            wf.writeframes(struct.pack('<h', val))

# -------------------- VITS 相關 --------------------
def vits_available() -> bool:
    """檢查 vits-simple-api 是否可用"""
    try:
        r = requests.get(f"{VITS_ENDPOINT}/", timeout=3)
        return r.ok
    except Exception:
        return False

def call_vits_wav_path(ja_text: str) -> Optional[str]:
    """
    调用 VITS API 生成语音
    成功返回 wav 绝对路径，失败返回 None
    """
    try:
        from urllib.parse import quote
        
        # ⚠️ 使用 GET 请求，手动构建 URL（确保正确编码）
        encoded_text = quote(ja_text)
        url = f"{VITS_ENDPOINT}/voice/vits?text={encoded_text}&id={VITS_SPEAKER_ID}&format=wav&lang=ja"
        
        print(f"[VITS Debug] Calling URL: {url}")  # 调试信息
        
        r = requests.get(url, timeout=30)  # 改为 GET
        
        if not r.ok:
            print(f"[VITS Error] Status {r.status_code}: {r.text}")
            return None
        
        # 写入缓存
        md5 = hashlib.md5(ja_text.encode('utf-8')).hexdigest()
        wav_path = (voices_dir / f"{md5}_vits.wav").resolve()
        
        with open(wav_path, 'wb') as f:
            f.write(r.content)
        
        # 检查文件大小
        file_size = wav_path.stat().st_size
        if file_size < 10240:  # 10KB
            print(f"[VITS Error] Audio file too small: {file_size} bytes")
            return None
        
        print(f"[VITS Success] Generated: {wav_path} ({file_size} bytes)")
        return str(wav_path)
    
    except Exception as e:
        print(f"[VITS Exception] {type(e).__name__}: {e}")
        return None


def get_predefined_audio(ja_text: str) -> Optional[str]:
    """
    檢查是否有預定義音頻（原聲）
    支持：ciallo 等關鍵詞
    返回：隨機選擇的 wav 絕對路徑或 None
    """
    predefined_map = {
        "ciallo": "ciallo",
        "ちゃろ": "ciallo",
        "チャロ": "ciallo",
    }
    
    # 清洗文本
    clean_text = ja_text.lower().strip()
    for punct in ['～', '！', '!', '？', '?', '。', '、', ' ']:
        clean_text = clean_text.replace(punct, '')
    
    # 檢查關鍵詞
    for keyword, audio_prefix in predefined_map.items():
        if keyword in clean_text:
            if not PREDEFINED_AUDIO_DIR.exists():
                return None
            
            # 找所有匹配文件
            candidates = list(PREDEFINED_AUDIO_DIR.glob(f"{audio_prefix}*.wav"))
            
            if candidates:
                selected = random.choice(candidates)
                return str(selected.resolve())
    
    return None

# -------------------- 模型/聊天 --------------------
class ChatRequest(BaseModel):
    messages: List[Dict[str, Any]]

@app.post('/qwen3')
async def qwen3(req: ChatRequest) -> Dict[str, Any]:
    """代理 Ollama 聊天接口"""
    messages = req.messages or []
    try:
        resp = requests.post(
            f"{OLLAMA_ENDPOINT}/api/chat",
            json={
                "model": OLLAMA_MODEL, 
                "messages": messages, 
                "stream": False,
                "options": {
                    "num_gpu": 0
                }
            },
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        
        reply = None
        if isinstance(data, dict):
            if 'message' in data and isinstance(data['message'], dict):
                reply = data['message'].get('content')
            elif 'choices' in data and data['choices']:
                reply = data['choices'][0]['message']['content']
        
        if not reply:
            raise RuntimeError('no reply')
        
        history = messages + [{"role": "assistant", "content": reply}]
        return {"response": reply, "history": history}
    
    except Exception:
        last = messages[-1]['content'] if messages else ''
        history = messages + [{"role": "assistant", "content": last}]
        return {"response": last, "history": history}

# -------------------- 雙語回覆 --------------------
class ReplyBiRequest(BaseModel):
    text: Optional[str] = None
    zh: Optional[str] = None
    ja: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = None

@app.post('/reply_bi')
async def reply_bi(req: ReplyBiRequest) -> Dict[str, Any]:
    """生成中日雙語回覆（暫時簡化）"""
    text = (req.text or req.zh or req.ja or '').strip()
    zh = (req.zh or text).strip()
    ja = (req.ja or text).strip()
    history = req.history or []
    history.append({"role": "assistant", "content": ja})
    return {"zh": zh, "ja": ja, "history": history}

# -------------------- TTS --------------------
class TTSRequest(BaseModel):
    ja: str
    zh: Optional[str] = None

@app.post('/tts')
async def tts(req: TTSRequest) -> Dict[str, Any]:
    """
    語音合成優先順序：
    1. 預定義音頻（原聲）
    2. VITS
    3. Mock
    """
    try:
        ja_text = (req.ja or "").strip()
        subtitle_zh = (req.zh or "").strip()
        
        if not ja_text:
            raise HTTPException(status_code=400, detail="ja text is empty")
        
        _ensure_voices_dir()
        md5 = hashlib.md5(ja_text.encode('utf-8')).hexdigest()
        
        # 1. 檢查緩存
        cached_vits = (voices_dir / f"{md5}_vits.wav").resolve()
        if cached_vits.exists() and cached_vits.stat().st_size >= 10240:
            return {"wav_path": str(cached_vits), "subtitle_zh": subtitle_zh, "backend": "cache"}
        
        # 2. 檢查預定義音頻（最高優先級）
        predefined_path = get_predefined_audio(ja_text)
        if predefined_path and os.path.exists(predefined_path):
            return {"wav_path": predefined_path, "subtitle_zh": subtitle_zh, "backend": "predefined"}
        
        # 3. 嘗試 VITS
        if vits_available():
            vits_path = call_vits_wav_path(ja_text)
            if vits_path:
                return {"wav_path": vits_path, "subtitle_zh": subtitle_zh, "backend": "vits"}
        
        # 4. Mock 保底
        mock_file = (voices_dir / f"{md5}_mock.wav").resolve()
        generate_beep_wav(mock_file, seconds=1.2, freq=660.0)
        return {"wav_path": str(mock_file), "subtitle_zh": subtitle_zh, "backend": "mock"}
    
    except HTTPException:
        raise
    except Exception as e:
        # 最終保底
        try:
            _ensure_voices_dir()
            md5 = hashlib.md5((req.ja or "mock").encode('utf-8')).hexdigest()
            mock_file = (voices_dir / f"{md5}_mock.wav").resolve()
            generate_beep_wav(mock_file, seconds=1.2, freq=660.0)
            return {
                "wav_path": str(mock_file),
                "subtitle_zh": (req.zh or "") if hasattr(req, 'zh') else "",
                "backend": "mock",
                "error": f"{type(e).__name__}: {e}"
            }
        except Exception as e2:
            raise HTTPException(status_code=500, detail=f"tts fatal: {type(e2).__name__}: {e2}")

# -------------------- /say --------------------
class SayRequest(BaseModel):
    text: Optional[str] = None
    zh: Optional[str] = None
    ja: Optional[str] = None

@app.post('/say')
async def say(req: SayRequest) -> Dict[str, Any]:
    """
    入口：輸入 {text} 或 {zh, ja}
    - 若只有 text：用聊天生成
    - TTS 合成，回 wav 路徑與字幕
    """
    zh = (req.zh or "").strip()
    ja = (req.ja or "").strip()
    
    if not ja:
        text = (req.text or "").strip()
        if not text:
            text = "テストです"
        
        messages = [{"role": "user", "content": text}]
        chat_res = await qwen3(ChatRequest(messages=messages))
        ja = chat_res.get("response", "テストです")
    
    if not zh:
        zh = ja
    
    # 調用 TTS
    tts_res = await tts(TTSRequest(ja=ja, zh=zh))
    return {
        "wav_path": tts_res["wav_path"],
        "subtitle_zh": zh or ja,
        "backend": tts_res.get("backend", "unknown")
    }

# -------------------- /pat --------------------
@app.post('/pat')
async def pat() -> Dict[str, Any]:
    """摸头端点：触发一句短台词并合成语音"""
    # 修改：直接指定中日文，避免依赖聊天生成
    return await say(SayRequest(
        zh="啊，好舒服～",
        ja="あ、気持ちいい～"
    ))

