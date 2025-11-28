import flet as ft
import os
import math
from threading import Thread

# 默认安卓下载路径
ANDROID_DOWNLOAD_DIR = "/storage/emulated/0/Download"

def main(page: ft.Page):
    # 全局错误捕获
    try:
        setup_ui(page)
    except Exception as e:
        page.add(ft.Text(f"启动错误: {e}", color="red", size=20))
        page.update()

def setup_ui(page: ft.Page):
    page.title = "MP3无损切割"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.scroll = "AUTO"
    
    # --- 状态变量 ---
    selected_file_path = ft.Ref[ft.Text]()
    process_status = ft.Ref[ft.Text]()
    loading_ring = ft.Ref[ft.ProgressRing]()
    
    # --- 核心逻辑 ---
    
    def save_last_file(path):
        try: page.client_storage.set("last_selected_file", path)
        except: pass 

    def load_last_file():
        try:
            last = page.client_storage.get("last_selected_file")
            if last and os.path.exists(last):
                selected_file_path.current.value = last
                selected_file_path.current.update()
        except: pass

    def parse_time_str(t_str):
        # 返回秒数 (float)
        t_str = t_str.strip().lower()
        if t_str.endswith("s"): t_str = t_str[:-1]
        
        if ":" in t_str:
            parts = t_str.split(":")
            if len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
        try:
            return float(t_str) * 60 # 默认当做分钟
        except:
            return 0.0

    def parse_range(range_str):
        if "-" not in range_str: return None, None
        parts = range_str.split("-")
        return parse_time_str(parts[0]), parse_time_str(parts[1])

    # --- 纯Python切割核心逻辑 ---
    def cut_mp3_pure(file_path, start_sec, end_sec, output_path):
        from mutagen.mp3 import MP3
        
        # 1. 获取音频元数据
        audio = MP3(file_path)
        total_length = audio.info.length # 总时长(秒)
        bitrate = audio.info.bitrate # 码率 (bps)
        
        file_size = os.path.getsize(file_path)
        
        # 2. 简单的字节估算算法
        # MP3文件 = [Header/Metadata] + [Audio Data] + [ID3v1]
        # 这种算法对 CBR(固定码率) 很准，对 VBR(动态码率) 会有偏差，但这是纯Python的极限
        
        if start_sec < 0: start_sec = 0
        if end_sec > total_length: end_sec = total_length
        
        # 计算每秒的平均字节数
        bytes_per_sec = file_size / total_length
        
        start_byte = int(start_sec * bytes_per_sec)
        end_byte = int(end_sec * bytes_per_sec)
        length_byte = end_byte - start_byte
        
        # 3. 物理读写
        with open(file_path, 'rb') as src:
            src.seek(start_byte)
            data = src.read(length_byte)
            
            with open(output_path, 'wb') as dst:
                dst.write(data)

    def pick_files_result(e: ft.FilePickerResultEvent):
        if e.files:
            path = e.files[0].path
            selected_file_path.current.value = path
            selected_file_path.current.update()
            save_last_file(path)

    def run_cutting_task(file_path, time_range):
        try:
            loading_ring.current.visible = True
            process_status.current.value = "正在分析文件..."
            process_status.current.color = "blue"
            page.update()

            # 延迟导入 mutagen，防止启动报错
            try:
                import mutagen
            except ImportError:
                raise Exception("缺少 mutagen 库")

            # 检查格式
            if not file_path.lower().endswith(".mp3"):
                raise Exception("手机纯Python模式仅支持 .mp3 格式！\nM4A/WAV 需要FFmpeg支持。")

            start_sec, end_sec = parse_range(time_range)
            if start_sec is None or end_sec is None:
                raise Exception("时间格式错误 (例: 0-1)")

            filename = os.path.basename(file_path)
            name, ext = os.path.splitext(filename)
            
            # 路径处理
            output_dir = ANDROID_DOWNLOAD_DIR
            if not os.path.exists(output_dir):
                output_dir = os.path.dirname(file_path) # 回退到缓存目录(虽然可能看不见)

            final_path = os.path.join(output_dir, f"{name}_cut{ext}")

            process_status.current.value = "正在切割 (纯字节模式)..."
            page.update()
            
            # 执行切割
            cut_mp3_pure(file_path, start_sec, end_sec, final_path)

            process_status.current.value = f"✅ 成功! (可能有几秒误差)\n{final_path}"
            process_status.current.color = "green"
            
        except Exception as e:
            process_status.current.value = f"❌ 失败: {str(e)}"
            process_status.current.color = "red"
        finally:
            loading_ring.current.visible = False
            page.update()

    def start_processing(e):
        if not selected_file_path.current.value or selected_file_path.current.value == "未选择":
            process_status.current.value = "请先选择文件"
            page.update()
            return
            
        path = selected_file_path.current.value
        t_range = time_input.value
        
        t = Thread(target=run_cutting_task, args=(path, t_range))
        t.start()

    # --- UI ---
    file_picker = ft.FilePicker(on_result=pick_files_result)
    page.overlay.append(file_picker)

    header = ft.Container(
        content=ft.Column([
            ft.Icon(name="music_note", size=50, color="blue"), 
            ft.Text("MP3 极速切割", size=24, weight="bold"),
            ft.Text("纯 Python 版 - 仅支持 MP3", size=12, color="grey"),
        ], horizontal_alignment="center"),
        alignment=ft.alignment.center,
        margin=ft.margin.only(bottom=20)
    )

    file_section = ft.Container(
        content=ft.Column([
            ft.ElevatedButton("选择 MP3", icon="folder_open", 
                             on_click=lambda _: file_picker.pick_files(allowed_extensions=["mp3"])),
            ft.Text(ref=selected_file_path, value="未选择", size=12),
        ]),
        padding=10, border=ft.border.all(1, "grey"), border_radius=10
    )

    time_input = ft.TextField(
        label="区间 (如 0:30-1:30 或 0-1)", 
        value="0-1",
        prefix_icon="timer",
        hint_text="支持 分:秒 格式"
    )
    
    action_btn = ft.ElevatedButton(
        "执行切割", icon="content_cut", width=300, bgcolor="blue", color="white",
        on_click=start_processing
    )

    page.add(
        header, 
        file_section, 
        ft.Container(height=10),
        time_input, 
        ft.Container(height=20),
        ft.Column([action_btn, ft.ProgressRing(ref=loading_ring, visible=False), ft.Text(ref=process_status)], horizontal_alignment="center")
    )

    load_last_file()

ft.app(target=main)
