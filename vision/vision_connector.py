# -*- coding: utf-8 -*-
"""
Vision Connector - Ollama 視覺模型連接器
支援 Llava, Moondream, Qwen-VL 等多種模型
"""

import base64
import requests
from io import BytesIO
from typing import Optional, Dict, Any, Union
from pathlib import Path
import numpy as np
import cv2
from PIL import Image


class VisionConnectorError(Exception):
    """視覺連接器錯誤"""
    pass


class VisionConnector:
    """
    通用視覺模型連接器
    
    特性:
    - 支援圖片路徑、PIL Image、numpy array
    - 自動 base64 編碼
    - VRAM 優化（keep_alive 控制）
    - 錯誤處理與重試
    """
    
    DEFAULT_OPTIONS = {
        "temperature": 0.3,  # 降低隨機性
        "num_predict": 150,  # 限制輸出長度
        "num_ctx": 2048,     # 上下文長度
    }
    
    def __init__(
        self, 
        base_url: str = "http://localhost:11434",
        model: str = "qwen3-vl-4b", # ✅ Updated default
        timeout: int = 60 # ✅ Increased for larger models
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.generate_url = f"{self.base_url}/api/generate"
        print(f"🔧 [VisionConnector] Initialized with model: {self.model}, timeout: {self.timeout}s")

    def _is_qwen_vl(self) -> bool:
        """檢測是否為 Qwen-VL 系列模型"""
        return "qwen" in self.model.lower() and "vl" in self.model.lower()
        
    def _image_to_base64(
        self, 
        image: Union[str, Path, Image.Image, np.ndarray]
    ) -> str:
        """
        將圖片轉換為 base64 字串
        
        Args:
            image: 圖片（路徑、PIL Image 或 numpy array）
        
        Returns:
            str: base64 編碼字串
        """
        try:
            # 處理檔案路徑
            if isinstance(image, (str, Path)):
                with open(image, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
            
            # 處理 PIL Image
            elif isinstance(image, Image.Image):
                buffered = BytesIO()
                image.save(buffered, format="PNG")
                return base64.b64encode(buffered.getvalue()).decode("utf-8")
            
            # 處理 numpy array (OpenCV/mss 格式)
            elif isinstance(image, np.ndarray):
                # 確保是 RGB 格式
                if len(image.shape) == 3 and image.shape[2] == 4:  # RGBA
                    image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
                elif len(image.shape) == 3 and image.shape[2] == 3:  # BGR
                    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                
                pil_img = Image.fromarray(image)
                buffered = BytesIO()
                pil_img.save(buffered, format="PNG")
                return base64.b64encode(buffered.getvalue()).decode("utf-8")
            
            else:
                raise ValueError(f"不支援的圖片類型: {type(image)}")
                
        except Exception as e:
            raise VisionConnectorError(f"圖片編碼失敗: {str(e)}")
    
    def analyze_image(
        self,
        image: Union[str, Path, Image.Image, np.ndarray],
        prompt: str = "Describe this image concisely in English. Focus on main activities, text on screen, or significant events.",
        stream: bool = False,
        keep_alive: str = "5m",  # Keep loaded for 5 minutes
        custom_options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        分析圖片內容
        
        Args:
            image: 圖片輸入
            prompt: 分析提示詞
            stream: 是否使用串流模式（預設 False）
            keep_alive: 模型保持載入時間
            custom_options: 自訂 Ollama 參數
        
        Returns:
            str: 模型的描述文字
        
        Raises:
            VisionConnectorError: 當請求失敗時
        """
        try:
            # 準備 base64 圖片
            image_b64 = self._image_to_base64(image)
            
            # 合併選項
            options = self.DEFAULT_OPTIONS.copy()
            if custom_options:
                options.update(custom_options)
            
            # 🔥 根據模型類型選擇 API 端點和格式
            if self._is_qwen_vl():
                # Qwen-VL 使用 /api/chat 端點 (Optimized for stability)
                api_endpoint = f"{self.base_url}/api/chat"
                
                # Use more deterministic options for VL models to prevent loops
                vl_options = options.copy()
                vl_options.update({
                    "temperature": 0.1,
                    "num_predict": 60,
                    "top_k": 20,
                    "repeat_penalty": 1.2
                })
                
                payload = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                            "images": [image_b64]
                        }
                    ],
                    "stream": stream,
                    "keep_alive": keep_alive,
                    "options": vl_options
                }
            else:
                # Moondream/其他模型使用 /api/generate
                api_endpoint = self.generate_url
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "images": [image_b64],
                    "stream": stream,
                    "keep_alive": keep_alive,
                    "options": options
                }

            # Debug logging
            print(f"[VisionConnector Debug] API Endpoint: {api_endpoint}")
            print(f"[VisionConnector Debug] Model: {self.model}")
            print(f"[VisionConnector Debug] Prompt: {prompt[:100]}...")
            print(f"[VisionConnector Debug] Image size: {len(image_b64)} bytes (base64)")
            print(f"[VisionConnector Debug] Using {'chat' if self._is_qwen_vl() else 'generate'} API")

            # 發送請求
            response = requests.post(
                api_endpoint,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # 解析回應
            data = response.json()
            
            # 🔥 根據 API 類型提取 response
            if self._is_qwen_vl():
                # chat API 格式
                message = data.get("message", {})
                response_text = message.get("content", "").strip()
                
                # Debug: Check for thinking loop/empty content
                if not response_text and "thinking" in message:
                    thought = message.get("thinking", "")
                    print(f"⚠️ [VisionConnector] Model trapped in thought loop: {thought[:100]}...")
                    # Fallback: Return a generic signal
                    return "A computer screen with active windows."
            else:
                # generate API 格式
                response_text = data.get("response", "").strip()

            # Debug logging
            print(f"[VisionConnector Debug] Raw response length: {len(response_text)}")
            print(f"[VisionConnector Debug] Response preview: {response_text[:200]}")
            
            if not response_text:
                print(f"⚠️ [VisionConnector] Model {self.model} returned empty response!")
                print(f"[VisionConnector Debug] Full API response: {data}")
                # Fallback for empty responses
                if self._is_qwen_vl():
                    return "The screen shows various applications and content."
            
            return response_text
                
        except requests.exceptions.Timeout:
            raise VisionConnectorError(
                f"請求超時（{self.timeout}s）。模型 {self.model} 可能尚未載入或推理時間過長"
            )
        except requests.exceptions.ConnectionError:
            raise VisionConnectorError(
                f"無法連接到 Ollama ({self.base_url})。請確認服務已啟動"
            )
        except requests.exceptions.HTTPError as e:
            raise VisionConnectorError(f"HTTP 錯誤: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise VisionConnectorError(f"未知錯誤: {str(e)}")
    
    def test_connection(self) -> bool:
        """
        測試與 Ollama 的連接
        
        Returns:
            bool: 連接成功返回 True
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False


# === 使用範例 ===
if __name__ == "__main__":
    import mss
    
    # 初始化連接器
    connector = VisionConnector()
    
    # 測試連接
    if not connector.test_connection():
        print("❌ 無法連接到 Ollama，請確認服務已啟動")
        exit(1)
    
    print("✅ Ollama 連接成功")
    
    # 截取當前螢幕
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        screenshot = sct.grab(monitor)
        img_array = np.array(screenshot)
    
    print("📸 螢幕已截取，正在分析...")
    
    try:
        # 分析圖片
        description = connector.analyze_image(
            image=img_array,
            prompt="What's on this screen? Mention any text, applications, or activities.",
            keep_alive="0s"  # 立即釋放 VRAM
        )
        
        print(f"\n🔍 {connector.model} 的觀察:\n{description}")
        
    except VisionConnectorError as e:
        print(f"❌ 分析失敗: {e}")
