# -*- coding: utf-8 -*-
"""
Screen Change Monitor - 螢幕變化監控模組
使用 MSE (Mean Squared Error) 檢測畫面變化，觸發視覺分析
適用於 RTX 4060 8GB VRAM 環境
"""

import time
import numpy as np
from typing import Optional, Tuple, Dict
from dataclasses import dataclass
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker
import mss
import cv2


@dataclass
class MonitorConfig:
    """監控配置"""
    check_interval: float = 1.0  # 檢查間隔（秒）
    threshold: float = 0.15  # 變化閾值 (0-1)
    capture_width: int = 640  # 低解析度寬度
    capture_height: int = 360  # 低解析度高度
    force_check_interval: int = 45  # 強制檢查間隔（秒）


class ScreenChangeMonitor(QThread):
    """
    螢幕變化監控器 (QThread)
    
    Signals:
        scene_changed: 當檢測到場景突變時發射 (float: 變化分數)
        force_check_triggered: 當強制檢查觸發時發射
        error_occurred: 當發生錯誤時發射 (str: 錯誤訊息)
    """
    
    # 訊號定義
    scene_changed = pyqtSignal(float)  # 發送變化分數
    force_check_triggered = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self, config: Optional[MonitorConfig] = None):
        super().__init__()
        self.config = config or MonitorConfig()
        
        # 執行控制
        self._running = False
        self._paused = False
        self._mutex = QMutex()
        
        # 畫面快取
        self._previous_frame: Optional[np.ndarray] = None
        self._last_force_check = time.time()
        
        # mss 實例（每個執行緒獨立）
        self._sct: Optional[mss.mss] = None
        self._monitor: Optional[Dict] = None
    
    def set_region(self, x: int = 0, y: int = 0, 
                   width: Optional[int] = None, 
                   height: Optional[int] = None) -> None:
        """
        設定截圖區域
        
        Args:
            x, y: 左上角座標（預設 0, 0 為全螢幕）
            width, height: 區域大小（None 表示使用全螢幕）
        """
        with QMutexLocker(self._mutex):
            if width and height:
                self._monitor = {
                    "top": y, "left": x, 
                    "width": width, "height": height
                }
            else:
                self._monitor = None  # 使用全螢幕
    
    def pause_monitoring(self) -> None:
        """暫停監控（用於視覺分析期間）"""
        with QMutexLocker(self._mutex):
            self._paused = True
    
    def resume_monitoring(self) -> None:
        """恢復監控"""
        with QMutexLocker(self._mutex):
            self._paused = False
            self._previous_frame = None  # 重置基準幀
    
    def stop_monitoring(self) -> None:
        """停止監控執行緒"""
        self._running = False
        self.wait()  # 等待執行緒結束
    
    def _capture_screen(self) -> Optional[np.ndarray]:
        """
        截取螢幕並轉為灰階低解析度影像
        
        Returns:
            numpy.ndarray: 處理後的影像，失敗返回 None
        """
        try:
            # 懶初始化 mss（執行緒安全）
            if self._sct is None:
                self._sct = mss.mss()
            
            # 截圖
            monitor = self._monitor or self._sct.monitors[1]  # monitors[0] 是全部螢幕的總和
            screenshot = self._sct.grab(monitor)
            
            # 轉換為 numpy array (BGRA -> BGR)
            img = np.array(screenshot)[:, :, :3]
            
            # 調整大小並轉灰階
            img_resized = cv2.resize(
                img, 
                (self.config.capture_width, self.config.capture_height),
                interpolation=cv2.INTER_AREA
            )
            gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
            
            return gray
            
        except Exception as e:
            self.error_occurred.emit(f"截圖失敗: {str(e)}")
            return None
    
    def _calculate_mse(self, frame1: np.ndarray, frame2: np.ndarray) -> float:
        """
        計算兩幀之間的 Mean Squared Error
        
        Returns:
            float: 正規化的 MSE 值 (0-1)，值越大變化越大
        """
        mse = np.mean((frame1.astype(float) - frame2.astype(float)) ** 2)
        # 正規化到 0-1 範圍 (255^2 = 65025)
        return mse / 65025.0
    
    def run(self) -> None:
        """主執行迴圈 (QThread 的 run 方法)"""
        print("👀 ScreenChangeMonitor thread started!")  # Debug
        self._running = True
        
        while self._running:
            try:
                # 檢查暫停狀態
                with QMutexLocker(self._mutex):
                    if self._paused:
                        time.sleep(0.5)
                        continue
                
                # 截取當前畫面
                current_frame = self._capture_screen()
                if current_frame is None:
                    time.sleep(self.config.check_interval)
                    continue
                
                # 初始化基準幀
                if self._previous_frame is None:
                    self._previous_frame = current_frame
                    time.sleep(self.config.check_interval)
                    continue
                
                # 計算變化
                change_score = self._calculate_mse(self._previous_frame, current_frame)
                
                # 觸發條件 1: 場景突變
                if change_score > self.config.threshold:
                    self.scene_changed.emit(change_score)
                    self._previous_frame = current_frame
                    self._last_force_check = time.time()
                
                # 觸發條件 2: 定時強制檢查
                elif (time.time() - self._last_force_check) > self.config.force_check_interval:
                    self.force_check_triggered.emit()
                    self._previous_frame = current_frame
                    self._last_force_check = time.time()
                
                else:
                    # 更新基準幀（防止漸變累積）
                    self._previous_frame = current_frame
                
                # 等待下一次檢查
                time.sleep(self.config.check_interval)
                
            except Exception as e:
                self.error_occurred.emit(f"監控迴圈錯誤: {str(e)}")
                time.sleep(2)  # 錯誤後延遲
        
        # 清理資源
        if self._sct:
            self._sct.close()
            self._sct = None


# === 使用範例 ===
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # 建立監控器
    monitor = ScreenChangeMonitor(
        MonitorConfig(
            check_interval=1.0,
            threshold=0.12,
            force_check_interval=30
        )
    )
    
    # 連接訊號
    monitor.scene_changed.connect(
        lambda score: print(f"🔥 場景變化檢測！分數: {score:.3f}")
    )
    monitor.force_check_triggered.connect(
        lambda: print("⏰ 強制檢查觸發")
    )
    monitor.error_occurred.connect(
        lambda msg: print(f"❌ 錯誤: {msg}")
    )
    
    # 啟動監控
    monitor.start()
    print("監控已啟動，按 Ctrl+C 停止...")
    
    try:
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        monitor.stop_monitoring()
        print("\n監控已停止")
