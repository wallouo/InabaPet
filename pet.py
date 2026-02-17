# -*- coding: utf-8 -*-
"""
MurasamePet 前端（PyQt5）
- 無邊框、透明、置頂、右下角停靠的桌寵視窗
- 頭部滑動/雙擊 => 呼叫 /pat，顯示中文字幕並播放日文語音
- 根據 AI 回傳的情緒動態切換表情立繪
"""

import os
import sys
import json
import random
import requests
import numpy as np  # ✅ 新增
import mss  # ✅ 新增
from PyQt5 import QtCore, QtGui, QtWidgets, QtMultimedia
from vision.screen_monitor import ScreenChangeMonitor, MonitorConfig
from vision.vision_connector import VisionConnector

API_PORT = os.getenv("API_PORT", "5000")
API_URL = f"http://127.0.0.1:{API_PORT}"

class EmotionManager:
    """管理表情與情緒的映射"""
    
    def __init__(self, config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        self.emotion_categories = config.get("emotion_categories", {})
        self.default_body = config.get("default_body", "01")
        self.default_face = config.get("default_face", "01")
    
    def get_face_by_emotion(self, emotion_from_ai):
        """根據 AI 返回的情緒選擇 face ID"""
        emotion_mapping = {
            'happy': 'happy', 'joy': 'happy', 'excited': 'happy', 'cheerful': 'happy', 'delighted': 'happy',
            'sad': 'sad', 'depressed': 'sad', 'disappointed': 'sad', 'dejected': 'sad', 'down': 'sad',
            'angry': 'angry', 'annoyed': 'angry', 'frustrated': 'angry', 'upset': 'angry', 'mad': 'angry',
            'tired': 'tired', 'exhausted': 'tired', 'bored': 'tired', 'weary': 'tired', 'sighing': 'tired',
            'neutral': 'neutral', 'calm': 'neutral', 'normal': 'neutral'
        }
        
        internal_emotion = emotion_mapping.get(emotion_from_ai.lower(), 'neutral')
        face_ids = self.emotion_categories.get(internal_emotion, [self.default_face])
        return random.choice(face_ids)
    
    def get_sprite_path(self, body_id, emotion_from_ai, sprites_dir="assets/meguru"):
        """獲取完整立繪路徑"""
        face_id = self.get_face_by_emotion(emotion_from_ai)
        sprite_filename = f"body_{body_id}_face_{face_id}.png"
        sprite_path = os.path.join(sprites_dir, sprite_filename)
        
        if not os.path.exists(sprite_path):
            sprite_filename = f"body_{body_id}_face_{self.default_face}.png"
            sprite_path = os.path.join(sprites_dir, sprite_filename)
        
        return sprite_path


# === 新增：獨立字幕窗口類 ===
class SubtitleWindow(QtWidgets.QLabel):
    """獨立的字幕窗口 - 簡化版，確保可見"""
    def __init__(self):
        super().__init__(None)
        
        # 簡化的窗口設定（去掉 WindowTransparentForInput）
        self.setWindowFlags(
            QtCore.Qt.Tool | 
            QtCore.Qt.FramelessWindowHint | 
            QtCore.Qt.WindowStaysOnTopHint
        )
        
        # 暫時不用透明背景，改用半透明實色
        # self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        
        # 使用實色背景（更容易看到）
        self.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 230);  /* 幾乎不透明的黑底 */
                font-family: 'Microsoft YaHei', sans-serif;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 18px;
                border-radius: 10px;
                border: 3px solid #FF69B4;  /* 粗粉邊框 */
            }
        """)
        
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setWordWrap(True)
        self.setMaximumWidth(450)
        self.hide()
    
    def show_text(self, text, pet_window_geometry):
        """顯示字幕"""
        if not text:
            self.hide()
            return
            
        self.setText(text)
        self.adjustSize()
        
        # 計算位置
        pet_x = pet_window_geometry.x()
        pet_y = pet_window_geometry.y()
        pet_w = pet_window_geometry.width()
        pet_h = pet_window_geometry.height()
        
        subtitle_w = self.width()
        subtitle_h = self.height()
        
        # 獲取屏幕信息
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        
        # X 軸：水平居中對齊寵物
        x = pet_x + (pet_w - subtitle_w) // 2
        
        # Y 軸：直接從屏幕底部往上偏移（調整此數值控制高度）
        offset_from_bottom = 150  # 距離屏幕底部的像素數（改這個值！）
        y = screen.height() - subtitle_h - offset_from_bottom
        
        # 確保不超出螢幕左右邊界
        if x < 0:
            x = 10
        if x + subtitle_w > screen.width():
            x = screen.width() - subtitle_w - 10
        
        # 確保不超出螢幕上邊界
        if y < 0:
            y = 10
        
        self.setGeometry(x, y, subtitle_w, subtitle_h)
        self.show()
        self.raise_()
        self.activateWindow()  # 強制激活
        
        print(f"[Subtitle] Position: ({x}, {y}), Size: {subtitle_w}x{subtitle_h}")
        print(f"[Subtitle] Screen size: {screen.width()}x{screen.height()}")
        print(f"[Subtitle] Visible: {self.isVisible()}, Text: '{text}'")


class PetWindow(QtWidgets.QLabel):
    def __init__(self):
        super().__init__(None)
        
        # 初始化表情管理器
        config_path = os.path.join(os.path.dirname(__file__), "emotion_config.json")
        self.emotion_mgr = EmotionManager(config_path)
        self.current_body_id = self.emotion_mgr.default_body
        
        # 視窗外觀設定
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setMouseTracking(True)
        
        # 載入預設角色圖
        self._load_sprite(self.current_body_id, "neutral")
        
        # === 改用獨立字幕窗口 ===
        self.subtitle = SubtitleWindow()
        
        # === 聊天輸入框 ===
        self.chat_input = QtWidgets.QLineEdit(self)
        self.chat_input.setPlaceholderText("輸入訊息給巡...")
        self.chat_input.returnPressed.connect(self.send_chat_message)
        self.chat_input.hide()
        self._layout_chat_input()
        
        # 滑鼠交互狀態
        self._dragging_head = False
        self._drag_start_x = 0
        self._moved = False
        
        # 播放器初始化
        self._player = QtMultimedia.QMediaPlayer()
        self._player.setVolume(70)
        
        self._update_head_rect()

        # Initialize Vision System (Llava-Phi3)
        print("🔧 [Init] Initializing Vision System (Llava-Phi3)...")
        self.vision_connector = VisionConnector(model="llava-phi3")
        self.screen_monitor = ScreenChangeMonitor(
            MonitorConfig(
                threshold=0.20,           # Increased to 20% to reduce sensitivity
                force_check_interval=90,  # Increased to 90s
                check_interval=2.0        # Check every 2s to save CPU
            )
        )
        
        # Cooldown Mechanism
        self._last_vision_trigger = 0
        self._vision_cooldown = 30        # 30 seconds cooldown

        # Connect signals
        self.screen_monitor.scene_changed.connect(self.on_scene_changed)
        self.screen_monitor.force_check_triggered.connect(self.on_force_check)
        
        # Start monitoring
        self.screen_monitor.start()
        print("[Init] Vision System Started")

        # 置於右下角並顯示
        self._move_to_bottom_right(margin_x=20, margin_y=40)
        self.show()
        
        # 顯示啟動訊息
        self.subtitle.show_text("Inaba Meguru System Online", self.geometry())
    
    def _layout_chat_input(self):
        """佈局輸入框"""
        screen = QtWidgets.QApplication.primaryScreen()
        screen_geo = screen.availableGeometry()
        
        input_w = 250
        input_h = 35
        
        window_bottom = self.geometry().bottom()
        window_left = self.geometry().left()
        window_width = self.width()
        
        input_x = window_left + int((window_width - input_w) / 2)
        input_y = window_bottom - 60
        
        if input_y < screen_geo.top():
            input_y = screen_geo.top() + 10
        if input_y + input_h > screen_geo.bottom():
            input_y = screen_geo.bottom() - input_h - 10
        
        self.chat_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 250);
                border: 3px solid #FF69B4;
                border-radius: 12px;
                padding: 6px 12px;
                color: black;
                font-weight: bold;
                font-size: 13px;
                font-family: 'Microsoft YaHei', sans-serif;
            }
            QLineEdit:focus {
                border: 3px solid #FF1493;
                background-color: rgb(255, 255, 255);
            }
        """)
        
        self.chat_input.setParent(None)
        self.chat_input.setWindowFlags(
            QtCore.Qt.Tool | 
            QtCore.Qt.FramelessWindowHint | 
            QtCore.Qt.WindowStaysOnTopHint
        )
        self.chat_input.setGeometry(input_x, input_y, input_w, input_h)
    
    def toggle_chat_input(self):
        """顯示/隱藏輸入框"""
        if self.chat_input.isVisible():
            self.chat_input.hide()
        else:
            self._layout_chat_input()
            self.chat_input.show()
            self.chat_input.setFocus()
            self.chat_input.raise_()
            self.chat_input.activateWindow()
    
    def send_chat_message(self):
        """發送聊天訊息"""
        text = self.chat_input.text().strip()
        if not text:
            return
        
        self.chat_input.clear()
        self.chat_input.hide()
        
        # 顯示思考中
        self.subtitle.show_text("Thinking...", self.geometry())
        
        print(f"[Frontend] Sending chat: {text}")
        try:
            resp = requests.post(
                f"{API_URL}/chat_process",
                json={"text": text, "user_id": "master"},
                timeout=60
            )
            resp.raise_for_status()
            data = resp.json()
            self.handle_api_response(data)
        except Exception as e:
            print(f"[Frontend Error] {e}")
            self.subtitle.show_text(f"Error: {e}", self.geometry())
    
    def handle_api_response(self, data):
        """統一處理 API 回應"""
        subtitle_text = data.get("subtitle_zh") or data.get("text") or ""
        wav_path = data.get("wav_path")
        emotion = data.get("emotion", "neutral")
        
        print(f"[Debug] API Response - subtitle: {subtitle_text}, emotion: {emotion}")
        
        # 1. 更新立繪
        self.update_sprite(emotion)
        
        # 2. 更新字幕（使用獨立窗口）
        self.subtitle.show_text(subtitle_text, self.geometry())
        
        # 3. 播放語音
        if wav_path and os.path.exists(wav_path):
            print(f"[Debug] Playing audio: {wav_path}")
            url = QtCore.QUrl.fromLocalFile(os.path.abspath(wav_path))
            content = QtMultimedia.QMediaContent(url)
            self._player.setMedia(content)
            self._player.play()
    
    def contextMenuEvent(self, event):
        """右鍵選單"""
        menu = QtWidgets.QMenu(self)
        
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(40, 40, 40, 240);
                border: 2px solid #FF69B4;
                border-radius: 8px;
                padding: 5px;
            }
            QMenu::item {
                background-color: transparent;
                color: white;
                padding: 8px 25px;
                margin: 2px 5px;
                border-radius: 4px;
                font-weight: bold;
            }
            QMenu::item:selected {
                background-color: #FF69B4;
                color: white;
            }
        """)
        
        chat_action = menu.addAction("開啟對話 (Open Chat)")
        chat_action.triggered.connect(self.toggle_chat_input)
        
        pat_action = menu.addAction("摸頭 (Pat)")
        pat_action.triggered.connect(self.trigger_pat)
        
        quit_action = menu.addAction("退出 (Exit)")
        quit_action.triggered.connect(self.close_all_windows)
        
        # 顯示菜單前，確保字幕窗口在最前
        if self.subtitle.isVisible():
            self.subtitle.raise_()
            self.subtitle.activateWindow()
        
        menu.exec_(event.globalPos())
        
        # 菜單關閉後，再次確保字幕窗口在最前
        if self.subtitle.isVisible():
            self.subtitle.raise_()
            self.subtitle.activateWindow()
    
    def close_all_windows(self):
        """關閉所有窗口"""
        self.subtitle.close()
        self.chat_input.close()
        self.close()
        QtWidgets.qApp.quit()
    
    def _load_sprite(self, body_id, emotion="neutral"):
        """載入並顯示指定情緒的立繪"""
        sprite_path = self.emotion_mgr.get_sprite_path(body_id, emotion)
        
        if not os.path.exists(sprite_path):
            fallback_path = os.path.join(os.path.dirname(__file__), "assets", "character.png")
            if os.path.exists(fallback_path):
                sprite_path = fallback_path
            else:
                raise FileNotFoundError(f"立繪檔案不存在：{sprite_path}")
        
        base_pix = QtGui.QPixmap(sprite_path)
        target_w = min(420, base_pix.width())
        self.pixmap_now = base_pix.scaledToWidth(target_w, QtCore.Qt.SmoothTransformation)
        self.setPixmap(self.pixmap_now)
        self.resize(self.pixmap_now.size())
    
    def update_sprite(self, emotion="neutral", body_id=None):
        """更新立繪"""
        if body_id is not None:
            self.current_body_id = body_id
        self._load_sprite(self.current_body_id, emotion)
        self._update_head_rect()
        
        # 更新字幕位置（如果字幕正在顯示）
        if self.subtitle.isVisible():
            current_text = self.subtitle.text()
            self.subtitle.show_text(current_text, self.geometry())
    
    def _update_head_rect(self):
        """更新頭部檢測區域"""
        w, h = self.width(), self.height()
        self.head_rect = QtCore.QRect(
            int(w * 0.15),
            int(h * 0.0),
            int(w * 0.70),
            int(h * 0.35)
        )
        print(f"[Debug] Head rect: x={self.head_rect.x()}, y={self.head_rect.y()}, "
              f"w={self.head_rect.width()}, h={self.head_rect.height()}")
    
    def resizeEvent(self, event):
        """窗口大小改變時更新字幕位置"""
        super().resizeEvent(event)
        self._update_head_rect()
        if self.subtitle.isVisible():
            current_text = self.subtitle.text()
            self.subtitle.show_text(current_text, self.geometry())
    
    def _move_to_bottom_right(self, margin_x=20, margin_y=40):
        """移動到右下角"""
        screen = QtWidgets.QApplication.primaryScreen()
        geo = screen.availableGeometry()
        x = geo.right() - self.width() - margin_x
        y = geo.bottom() - self.height() - margin_y
        self.move(max(geo.left(), x), max(geo.top(), y))
    
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.head_rect.contains(event.pos()):
            self._dragging_head = True
            self._drag_start_x = event.x()
            self._moved = False
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if self._dragging_head:
            if abs(event.x() - self._drag_start_x) > 30:
                self._moved = True
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        if self._dragging_head:
            if self._moved:
                self.trigger_pat()
            self._dragging_head = False
        super().mouseReleaseEvent(event)
    
    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.head_rect.contains(event.pos()):
            self.trigger_pat()
        super().mouseDoubleClickEvent(event)
    
    def trigger_pat(self):
        """摸頭觸發"""
        print("[Debug] Pat triggered!")
        try:
            resp = requests.post(f"{API_URL}/pat", timeout=15)
            resp.raise_for_status()
            data = resp.json()
            self.handle_api_response(data)
        except Exception as e:
            print(f"[Debug] Error: {e}")
            import traceback
            traceback.print_exc()
            self.subtitle.show_text("(pat failed)", self.geometry())

    def on_scene_changed(self, score: float):
        """場景變化時觸發"""
        print(f"場景變化: {score:.2f}")
        self.analyze_screen_and_comment()

    def on_force_check(self):
        """定時檢查觸發"""
        print("定時檢查觸發")
        self.analyze_screen_and_comment()

    def analyze_screen_and_comment(self):
        """Capture Screen -> Moondream Analysis -> Qwen Comment -> TTS"""
        import time
        import re
        
        # Cooldown Check
        current_time = time.time()
        if current_time - self._last_vision_trigger < self._vision_cooldown:
            print(f"⏳ Vision Cooldown: wait {int(self._vision_cooldown - (current_time - self._last_vision_trigger))}s")
            return
            
        self._last_vision_trigger = current_time
        print("⚡ analyze_screen_and_comment Triggered!")

        # Save original position
        original_pos = self.pos()

        try:
            # 1. Pause Monitor
            self.screen_monitor.pause_monitoring()

            # 2. 🔥 HIDE SELF (Enhanced Timing) 🔥
            self.hide()
            self.subtitle.hide()
            if self.chat_input.isVisible():
                self.chat_input.hide()
            
            # CRITICAL: Ensure proper hide timing
            QtWidgets.QApplication.processEvents() # Process hide event
            time.sleep(0.5) # Increased to 500ms for stability
            QtWidgets.QApplication.processEvents() # Ensure background redraws

            # 3. Capture Screen
            with mss.mss() as sct:
                monitor_idx = 1 if len(sct.monitors) > 1 else 0
                screenshot = np.array(sct.grab(sct.monitors[monitor_idx]))

            # 4. 🔥 SHOW SELF IMMEDIATELY 🔥
            self.move(original_pos) # Restore position
            self.show()

            # 5. Moondream Analysis
            print("[Vision] Analyzing image...")
            description = self.vision_connector.analyze_image(
                screenshot,
                prompt="Describe the image in detail."
            )
            print(f"[Vision Debug] Model: {self.vision_connector.model}")
            print(f"[Vision Debug] Raw description length: {len(description) if description else 0}")
            print(f"[Vision] {self.vision_connector.model} observed: {description}")

            # 6. 🔥 ENHANCED VALIDATION 🔥
            # Check if description is empty or too short
            if not description:
                print("[Vision] Description is None or empty string, skipping.")
                return
            description = description.strip()
            if len(description) < 3: # Allow very short descriptions like "game", "code"
                print(f"[Vision] Description too short ('{description}'), skipping.")
                return
            
            # Check if output is mostly symbols/garbage
            symbol_ratio = len(re.findall(r'[^a-zA-Z0-9\s]', description)) / max(len(description), 1)
            if symbol_ratio > 0.5: # More than 50% symbols
                print(f"[Vision] Output appears corrupted (symbol ratio: {symbol_ratio:.2f}), skipping.")
                return

            # Check for boring keywords
            boring_keywords = ["desktop", "wallpaper", "empty", "blank", "nothing", "taskbar", "icons only"]
            if any(keyword in description.lower() for keyword in boring_keywords):
                print("[Vision] Boring scene detected, skipping comment.")
                return

            # 7. 🔥 SEND TO QWEN (ENFORCE CHINESE) 🔥
            qwen_prompt = f"""SYSTEM: You are Inaba Meguru (巡), a cute anime character observing the user's screen.
USER'S SCREEN: {description}
TASK: Make ONE short comment in TRADITIONAL CHINESE (繁體中文) about what you see.
RULES:
- MUST respond in Traditional Chinese (繁體中文) ONLY
- Maximum 15 characters
- React naturally, don't describe
- Be playful and cute
- Don't mention "screen" or "computer"
EXAMPLES:
- "哇，看起來好好玩～"
- "這個我也想試試！"
- "在忙什麼呢？"
- "好厲害喔～"
YOUR RESPONSE (Traditional Chinese only):"""

            resp = requests.post(
                f"{API_URL}/chat_process",
                json={"text": qwen_prompt, "user_id": "master"},
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()

            # 8. 🔥 LANGUAGE VALIDATION 🔥
            subtitle_text = data.get("subtitle_zh") or data.get("text") or ""
            
            # Check if response contains Chinese characters
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', subtitle_text))
            total_chars = len(subtitle_text.strip())
            
            if total_chars == 0:
                print("[Vision] Empty response from Qwen, skipping.")
                return
                
            if total_chars > 0 and chinese_chars / total_chars < 0.3: # Less than 30% Chinese
                print(f"[Vision] Response not in Chinese ('{subtitle_text}'), skipping.")
                return

            # 9. Handle Response
            self.handle_api_response(data)
            print(f"✅ [Vision] Successfully commented: {subtitle_text}")

        except Exception as e:
            print(f"❌ [Vision Error] {e}")
            import traceback
            traceback.print_exc()
            self.move(original_pos)
            self.show()

        finally:
            # 10. Resume Monitor
            self.screen_monitor.resume_monitoring()


def main():
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    win = PetWindow()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()