# -*- coding: utf-8 -*-
"""
Moondream 狀態診斷工具
檢查模型安裝、VRAM 使用、連接狀態
"""

import requests
import subprocess
import json
from typing import Dict, List, Optional


class OllamaDiagnostics:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")
    
    def check_server_status(self) -> bool:
        """檢查 Ollama 服務是否運行"""
        print("🔍 檢查 Ollama 服務狀態...")
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if response.status_code == 200:
                print("✅ Ollama 服務正常運行")
                return True
            else:
                print(f"❌ 服務異常 (HTTP {response.status_code})")
                return False
        except requests.exceptions.ConnectionError:
            print("❌ 無法連接到 Ollama 服務")
            print("   請執行: ollama serve")
            return False
        except Exception as e:
            print(f"❌ 錯誤: {e}")
            return False
    
    def list_installed_models(self) -> List[Dict]:
        """列出已安裝的模型"""
        print("\n📦 已安裝的模型:")
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            data = response.json()
            models = data.get("models", [])
            
            if not models:
                print("   ⚠️  沒有已安裝的模型")
                return []
            
            for model in models:
                name = model.get("name", "unknown")
                size = model.get("size", 0) / (1024**3)  # 轉為 GB
                modified = model.get("modified_at", "unknown")
                print(f"   - {name} ({size:.2f} GB) | 更新: {modified}")
            
            return models
        except Exception as e:
            print(f"   ❌ 無法取得模型列表: {e}")
            return []
    
    def check_running_models(self) -> List[Dict]:
        """檢查當前運行中的模型"""
        print("\n🚀 當前運行中的模型:")
        try:
            response = requests.get(f"{self.base_url}/api/ps", timeout=5)
            data = response.json()
            models = data.get("models", [])
            
            if not models:
                print("   ⚠️  沒有模型正在運行")
                return []
            
            for model in models:
                name = model.get("name", "unknown")
                size = model.get("size", 0) / (1024**3)
                size_vram = model.get("size_vram", 0) / (1024**3)
                print(f"   - {name}")
                print(f"     總大小: {size:.2f} GB | VRAM 佔用: {size_vram:.2f} GB")
            
            return models
        except Exception as e:
            print(f"   ❌ 無法取得運行狀態: {e}")
            return []
    
    def check_moondream_installation(self, models: List[Dict]) -> bool:
        """檢查 Moondream 是否已安裝"""
        print("\n🌙 檢查 Moondream 安裝狀態:")
        moondream_found = any("moondream" in m.get("name", "").lower() for m in models)
        
        if moondream_found:
            print("   ✅ Moondream 已安裝")
            return True
        else:
            print("   ❌ Moondream 未安裝")
            print("   請執行: ollama pull moondream")
            return False
    
    def test_moondream_inference(self) -> bool:
        """測試 Moondream 推理（無圖片測試）"""
        print("\n🧪 測試 Moondream 推理能力...")
        try:
            payload = {
                "model": "moondream",
                "prompt": "Test connection. Reply with 'OK'.",
                "stream": False,
                "keep_alive": "1m",  # 保持 1 分鐘以便後續測試
                "options": {
                    "num_predict": 10
                }
            }
            
            print("   ⏳ 等待模型載入（首次可能需要 30-60 秒）...")
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=90  # 延長超時時間
            )
            
            if response.status_code == 200:
                data = response.json()
                result = data.get("response", "")
                print(f"   ✅ 推理成功! 回應: {result.strip()}")
                return True
            else:
                print(f"   ❌ 推理失敗 (HTTP {response.status_code})")
                print(f"   錯誤: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            print("   ❌ 推理超時（90秒）")
            print("   可能原因:")
            print("      1. VRAM 不足，模型載入到系統記憶體")
            print("      2. 其他程式佔用過多 VRAM")
            print("      3. 模型損壞，需重新下載")
            return False
        except Exception as e:
            print(f"   ❌ 錯誤: {e}")
            return False
    
    def get_gpu_info(self) -> None:
        """嘗試取得 GPU 資訊"""
        print("\n🎮 GPU 狀態:")
        try:
            # 嘗試執行 nvidia-smi
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free", 
                 "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                for i, line in enumerate(lines):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 4:
                        name, total, used, free = parts[:4]
                        used_pct = (float(used) / float(total)) * 100
                        print(f"   GPU {i}: {name}")
                        print(f"   總 VRAM: {total} MB | 已用: {used} MB ({used_pct:.1f}%) | 可用: {free} MB")
            else:
                print("   ⚠️  無法取得 GPU 資訊（nvidia-smi 不可用）")
        except FileNotFoundError:
            print("   ⚠️  nvidia-smi 未安裝或不在 PATH 中")
        except Exception as e:
            print(f"   ⚠️  無法取得 GPU 資訊: {e}")
    
    def run_full_diagnostics(self) -> None:
        """執行完整診斷"""
        print("=" * 60)
        print("🔧 Moondream 診斷工具")
        print("=" * 60)
        
        # 1. 檢查服務
        if not self.check_server_status():
            return
        
        # 2. 列出模型
        models = self.list_installed_models()
        
        # 3. 檢查運行中模型
        running = self.check_running_models()
        
        # 4. 檢查 Moondream
        moondream_installed = self.check_moondream_installation(models)
        
        # 5. GPU 資訊
        self.get_gpu_info()
        
        # 6. 推理測試（僅當 Moondream 已安裝）
        if moondream_installed:
            self.test_moondream_inference()
        
        print("\n" + "=" * 60)
        print("📋 診斷完成")
        print("=" * 60)


if __name__ == "__main__":
    diagnostics = OllamaDiagnostics()
    diagnostics.run_full_diagnostics()
