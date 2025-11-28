import flet as ft
import os
import time
from threading import Thread

# 默认安卓下载路径
ANDROID_DOWNLOAD_DIR = "/storage/emulated/0/Download"

def main(page: ft.Page):
    # 全局错误捕获，防止白屏
    try:
        setup_ui(page)
    except Exception as e:
        # 如果还是报错，会显示在这里
        page.add(ft.Text(f"启动错误: {e}", color="red", size=20))
        page.update()

def setup_ui(page: ft.Page):
    page.title = "音频切割大师"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.scroll = "AUTO"
    
    # --- 状态变量 ---
    selected_file_path = ft.Ref[ft.Text]()
    process_status = ft.Ref[ft.Text]()
    loading_ring = ft.Ref[ft.ProgressRing]()
    
    # --- 核心逻辑函数 ---

    def save_last_file(path):
        try:
            page.client_storage.set("last_selected_file", path)
        except:
            pass 

    def load_last_file():
        try:
            last = page.client_storage.get("last_selected_file")
            if last and os.path.exists(last):
                selected_file_path.current.value = last
                selected_file_path.current.update()
        except:
            pass

    def parse_time_str(t_str):
        t_str = t_str.strip().lower()
        multiplier = 60 * 1000 
        if t_str.endswith("s"):
            t_str = t_str[:-1]
            multiplier = 1000 
        if ":" in t_str:
            parts = t_str.split(":")
            if len(parts) == 2:
                m = int(parts[0])
                s = int(parts[1])
                return (m * 60 + s) * 1000
        try:
            val = float(t_str)
            return int(val * multiplier)
        except:
            return 0

    def parse_range(range_str):
        if "-" not in range_str:
            return None, None
        parts = range_str.split("-")
        start = parse_time_str(parts[0])
        end = parse_time_str(parts[1])
        return start, end

    def pick_files_result(e: ft.FilePickerResultEvent):
        if e.files:
            path = e.files[0].path
            selected_file_path.current.value = path
            selected_file_path.current.update()
            save_last_file(path)

    # --- 任务逻辑 ---
    def run_cutting_task(file_path, time_range, quality):
        try:
            loading_ring.current.visible = True
            process_status.current.value = "正在初始化..."
            page.update()

            # 延迟导入，防止启动崩
            try:
                from pydub import AudioSegment
            except ImportError:
                raise Exception("无法加载pydub库")
            except Exception as import_err:
                raise Exception(f"库加载失败: {import_err}")

            process_status.current.value = "正在加载音频..."
            page.update()

            if not os.path.exists(file_path):
                raise Exception("找不到源文件")

            try:
                audio = AudioSegment.from_file(file_path)
            except Exception as e:
                raise Exception(f"解码失败(安卓需FFmpeg): {e}")

            start_ms, end_ms = parse_range(time_range)
            if start_ms is None or end_ms is None:
                raise Exception("时间格式错误 (例: 1-2)")
            
            cut_audio = audio[start_ms:end_ms]

            filename = os.path.basename(file_path)
            name, ext = os.path.splitext(filename)
            
            output_dir = ANDROID_DOWNLOAD_DIR
            if not os.path.exists(output_dir):
                output_dir = os.path.dirname(file_path)

            final_path = os.path.join(output_dir, f"{name}_cut{ext}")

            process_status.current.value = "正在导出..."
            page.update()

            bitrate_map = {"高 (320k)": "320k", "中 (128k)": "128k", "低 (64k)": "64k"}
            target_bitrate = bitrate_map.get(quality, "192k")
            
            cut_audio.export(final_path, format=ext.replace(".", ""), bitrate=target_bitrate)

            process_status.current.value = f"✅ 成功!\n{final_path}"
            process_status.current.color = "green"
            
        except Exception as e:
            process_status.current.value = f"❌ 错误: {str(e)}"
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
        qual = quality_dropdown.value
        
        t = Thread(target=run_cutting_task, args=(path, t_range, qual))
        t.start()

    # --- UI 组件 (全部换成字符串) ---
    file_picker = ft.FilePicker(on_result=pick_files_result)
    page.overlay.append(file_picker)

    header = ft.Container(
        content=ft.Column([
            # 这里的 ft.icons.AUDIO_FILE 改成了 "audio_file"
            ft.Icon(name="audio_file", size=50, color="blue"), 
            ft.Text("音频切割大师", size=24, weight="bold"),
        ], horizontal_alignment="center"),
        alignment=ft.alignment.center,
        margin=ft.margin.only(bottom=20)
    )

    file_section = ft.Container(
        content=ft.Column([
            ft.ElevatedButton("选择文件", icon="folder_open", 
                             on_click=lambda _: file_picker.pick_files()),
            ft.Text(ref=selected_file_path, value="未选择", size=12),
        ]),
        padding=10, border=ft.border.all(1, "grey"), border_radius=10
    )

    time_input = ft.TextField(
        label="区间 (如 0-1)", 
        value="0-1",
        prefix_icon="timer" # 字符串图标
    )
    
    quality_dropdown = ft.Dropdown(
        label="质量", value="中 (128k)",
        options=[ft.dropdown.Option("高 (320k)"), ft.dropdown.Option("中 (128k)")],
        prefix_icon="compress" # 字符串图标
    )

    action_btn = ft.ElevatedButton(
        "开始切割", icon="cut", width=300, bgcolor="blue", color="white",
        on_click=start_processing
    )

    page.add(
        header, 
        file_section, 
        ft.Container(height=10),
        time_input, 
        quality_dropdown,
        ft.Container(height=20),
        ft.Column([action_btn, ft.ProgressRing(ref=loading_ring, visible=False), ft.Text(ref=process_status)], horizontal_alignment="center")
    )

    load_last_file()

ft.app(target=main)
