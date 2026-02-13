"""
Inaba Meguru 立繪組裝腳本 - 生產版本
基於視覺校準的身體+表情圖層組裝系統
"""
from PIL import Image
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

# ==================== 配置區 ====================

# 每個身體的基準偏移量（已校準）
BODY_FACE_OFFSETS = {
    1442: {"offset_x": -96, "offset_y": 168, "name": "部屋着腕差分（叉腰）"},
    1445: {"offset_x": -58, "offset_y": 168, "name": "部屋着（站姿）"},
    1444: {"offset_x": -89, "offset_y": 145, "name": "制服腕差分（校服叉腰）"},
    1438: {"offset_x": -96, "offset_y": 149, "name": "私服腕差分"},
    1446: {"offset_x": -89, "offset_y": 142, "name": "制服"},
}

# 特定表情的額外微調（針對個別組合的精細調整）
FACE_SPECIFIC_ADJUSTMENTS = {
    (1442, 1727): {"offset_x": 0, "offset_y": -8},
    (1442, 1762): {"offset_x": 2, "offset_y": 0},
    (1445, 1762): {"offset_x": 4, "offset_y": 0},
    (1442, 1486): {"offset_x": 0, "offset_y": -10},
    (1442, 1497): {"offset_x": 0, "offset_y": -10},
    (1444, 1486): {"offset_x": 0, "offset_y": -5},
    (1444, 1497): {"offset_x": 0, "offset_y": -5},
    (1445, 1486): {"offset_x": 0, "offset_y": -5},
    (1445, 1497): {"offset_x": 0, "offset_y": -10},
}

# ==================== 配置區結束 ====================

def parse_layer_data(txt_file):
    """解析 .txt 檔案，提取圖層座標資訊"""
    encodings = ['utf-16-le', 'utf-16', 'utf-8', 'shift-jis', 'cp932']
    lines = None
    
    for encoding in encodings:
        try:
            with open(txt_file, 'r', encoding=encoding) as f:
                lines = f.readlines()
            print(f"✅ 成功使用 {encoding} 編碼讀取檔案")
            break
        except:
            continue
    
    if lines is None:
        return {}, (2500, 3542)
    
    canvas_size = (2500, 3542)
    if len(lines) > 1:
        parts = lines[1].split()
        numbers = [int(p) for p in parts if p.isdigit()]
        if len(numbers) >= 2:
            canvas_size = (numbers[0], numbers[1])
    
    layers = {}
    for line in lines[2:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split('\t')
        if len(parts) < 10:
            continue
        try:
            layer_id = int(parts[9])
            layers[layer_id] = {
                "left": int(parts[2]),
                "top": int(parts[3]),
                "width": int(parts[4]),
                "height": int(parts[5]),
                "name": parts[1]
            }
        except:
            continue
    
    return layers, canvas_size

def assemble_sprite(layer_ids, layers_data, image_folder, image_prefix):
    """組裝身體+表情立繪"""
    body_layers = [lid for lid in layer_ids if lid in BODY_FACE_OFFSETS]
    if not body_layers:
        print(f"  ❌ 沒有找到身體圖層")
        return None
    
    body_id = body_layers[0]
    if body_id not in layers_data:
        print(f"  ❌ 身體圖層 {body_id} 沒有座標資料")
        return None
    
    body_coords = layers_data[body_id]
    base_offset = BODY_FACE_OFFSETS.get(body_id, {"offset_x": -66, "offset_y": 161})
    
    canvas = Image.new('RGBA', (body_coords['width'], body_coords['height']), (0, 0, 0, 0))
    
    for layer_id in layer_ids:
        layer_path = os.path.join(image_folder, f"{image_prefix}{layer_id}.png")
        if not os.path.exists(layer_path):
            print(f"  ⚠️  找不到：{layer_path}")
            continue
        
        try:
            layer_img = Image.open(layer_path).convert('RGBA')
            
            if layer_id not in BODY_FACE_OFFSETS:  # 表情圖層
                offset_x = (body_coords['width'] - layer_img.width) // 2 + base_offset["offset_x"]
                offset_y = base_offset["offset_y"]
                
                # 應用表情特定微調（如果有）
                adjustment_key = (body_id, layer_id)
                if adjustment_key in FACE_SPECIFIC_ADJUSTMENTS:
                    adjustment = FACE_SPECIFIC_ADJUSTMENTS[adjustment_key]
                    offset_x += adjustment["offset_x"]
                    offset_y += adjustment["offset_y"]
                
                position = (offset_x, offset_y)
            else:  # 身體圖層
                position = (0, 0)
            
            canvas.paste(layer_img, position, layer_img)
            
        except Exception as e:
            print(f"  ❌ 處理圖層 {layer_id} 時出錯：{e}")
            continue
    
    return canvas

def auto_crop(image):
    """自動裁切透明邊框"""
    bbox = image.getbbox()
    return image.crop(bbox) if bbox else image

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"📂 工作目錄：{script_dir}\n")
    
    # 讀取配置檔
    config_file = "sprite_config_batch.json"
    if not os.path.exists(config_file):
        print(f"❌ 找不到配置檔：{config_file}")
        return
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    layer_data_file = config['layer_data_file']
    image_folder = config['image_folder']
    image_prefix = config['image_prefix']
    output_folder = config['output_folder']
    combinations = config['combinations']
    
    # 解析圖層資料
    print(f"📖 正在讀取圖層資料：{layer_data_file}")
    layers_data, canvas_size = parse_layer_data(layer_data_file)
    print(f"✅ 已解析 {len(layers_data)} 個圖層座標\n")
    
    # 顯示配置
    print("=" * 80)
    print(f"📊 配置：{len(BODY_FACE_OFFSETS)} 個身體基準，{len(FACE_SPECIFIC_ADJUSTMENTS)} 個表情微調")
    print("=" * 80 + "\n")
    
    # 建立輸出資料夾
    os.makedirs(output_folder, exist_ok=True)
    
    # 批次處理
    total_count = len(combinations)
    success_count = 0
    
    print(f"🎨 開始生成 {total_count} 個立繪...\n")
    
    for i, combo in enumerate(combinations, 1):
        name = combo['name']
        layer_ids = combo['layer_ids']
        
        print(f"[{i}/{total_count}] {name}")
        
        sprite = assemble_sprite(layer_ids, layers_data, image_folder, image_prefix)
        if sprite is None:
            print(f"  ❌ 失敗\n")
            continue
        
        sprite_cropped = auto_crop(sprite)
        output_path = os.path.join(output_folder, f"{name}.png")
        sprite_cropped.save(output_path, 'PNG')
        print(f"  ✅ 完成\n")
        success_count += 1
    
    # 完成總結
    print("=" * 80)
    print(f"✅ 完成！成功生成 {success_count}/{total_count} 個立繪")
    print(f"📁 輸出位置：{output_folder}/")
    print("=" * 80)

if __name__ == "__main__":
    main()
