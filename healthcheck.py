# -*- coding: utf-8 -*-
"""
健康檢查腳本。
檢查 Ollama 和 VITS 服務是否可用。若 VITS 不可達，會提示將 TTS 落回 mock 模式。
同時列印出可用的 API 端點。
"""

import os
import sys
import requests

def check_endpoint(url: str, path: str = "/") -> bool:
    try:
        resp = requests.get(f"{url}{path}", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False

def main() -> int:
    ollama = os.getenv('OLLAMA_ENDPOINT', 'http://127.0.0.1:11434')
    vits = os.getenv('VITS_ENDPOINT', 'http://127.0.0.1:23456')
    
    ok_ollama = check_endpoint(ollama, '/api/tags')
    ok_vits = check_endpoint(vits, '/')
    
    print("=" * 60)
    print("[HealthCheck] 系統服務狀態檢查")
    print("=" * 60)
    
    print(f"[LLM] Ollama ({ollama}/api/tags):", '✓ OK' if ok_ollama else '✗ FAIL')
    
    if ok_vits:
        print(f"[TTS] VITS ({vits}/): ✓ OK (因幡巡語音可用)")
    else:
        print(f"[TTS] VITS ({vits}/): ⚠ WARN -> 將使用 mock TTS 或預定義音頻")
    
    print("\n可用的 API 端點:")
    api_port = os.getenv('API_PORT', '5000')
    base = f"http://127.0.0.1:{api_port}"
    
    endpoints = [
        ("/qwen3", "聊天接口"),
        ("/reply_bi", "雙語回覆"),
        ("/tts", "語音合成"),
        ("/say", "一條龍說話"),
        ("/pat", "摸頭互動")
    ]
    
    for path, desc in endpoints:
        print(f"  {base}{path:<15} - {desc}")
    
    print("=" * 60)
    
    # 如果關鍵服務掛了，返回非零
    if not ok_ollama:
        print("\n⚠️  警告：Ollama 未運行，請先啟動 Ollama！")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
