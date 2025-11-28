import flet as ft
import os
import time
from pydub import AudioSegment
from threading import Thread

# 默认安卓下载路径
ANDROID_DOWNLOAD_DIR = "/storage/emulated/0/Download"

def main(page: ft.Page):
    page.title = "音频切割大师"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.scroll = "AUTO"
    page.window_width = 400
    page.window_height = 700

    # --- 状态变量 ---
    selected_file_path = ft.Ref[ft.Text]()
    process_status = ft.Ref[ft.Text]()
    loading_ring = ft.Ref[ft.ProgressRing]()
    
    # --- 核心逻辑函数 ---

    def save_last_file(path):
        """保存上次选中的文件路径到本地存储"""
        page.client_storage.set("last_selected_file", path)

    def load_last_file():
        """读取上次选中的文件"""
        last = page.client_storage.get("last_selected_file")
        if last and os.path.exists(last):
            selected_file_path.current.value = last
            selected_file_path.current.update()
            return last
        return None

    def parse_time_str(t_str):
        """
        解析单个时间点，支持 '1.5'(分), '1:30'(分:秒), '90s'(秒)
        返回毫秒数
        """
        t_str = t_str.strip().lower()
        multiplier = 60 * 1000 # 默认当作分钟
        
        if t_str.endswith("s"):
            t_str = t_str[:-1]
            multiplier = 1000 # 如果带s，则是秒
            
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
        """解析 '1-2' 或 '1:30-2:00' 这种格式"""
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
            save_last_file(path) # 记忆路径
        else:
            "Cancelled!"

    def run_cutting_task(file_path, time_range, quality, output_path_custom):
        try:
            loading_ring.current.visible = True
            process_status.current.value = "正在加载音频..."
            process_status.current.color = ft.colors.BLUE
            page.update()

            # 1. 加载音频
            # 注意：pydub 依赖 ffmpeg，在未安装 ffmpeg 的安卓环境可能会失败
            try:
                audio = AudioSegment.from_file(file_path)
            except Exception as e:
                raise Exception(f"加载失败，可能缺少FFmpeg组件。\n错误: {str(e)}")

            # 2. 解析时间
            start_ms, end_ms = parse_range(time_range)
            if start_ms is None or end_ms is None:
                raise Exception("时间格式错误，请使用如 '1-2' (表示1分到2分)")
            
            if start_ms >= len(audio) or end_ms > len(audio) or start_ms >= end_ms:
                 raise Exception("时间范围超出音频长度或无效。")

            process_status.current.value = f"正在切割 ({start_ms//1000}s - {end_ms//1000}s)..."
            page.update()

            # 3. 切割
            cut_audio = audio[start_ms:end_ms]

            # 4. 确定输出路径
            filename = os.path.basename(file_path)
            name, ext = os.path.splitext(filename)
            
            # 确定输出文件夹
            output_dir = ANDROID_DOWNLOAD_DIR
            if not os.path.exists(output_dir):
                # 如果不是安卓或路径不存在，保存在原文件同级目录
                output_dir = os.path.dirname(file_path)

            final_path = os.path.join(output_dir, f"{name}_cut{ext}")

            process_status.current.value = "正在导出并压缩..."
            page.update()

            # 5. 导出 (压缩逻辑)
            bitrate_map = {
                "高 (320k)": "320k",
                "中 (128k)": "128k",
                "低 (64k)": "64k"
            }
            target_bitrate = bitrate_map.get(quality, "192k")
            
            cut_audio.export(final_path, format=ext.replace(".", ""), bitrate=target_bitrate)

            process_status.current.value = f"✅ 成功! 文件已保存至:\n{final_path}"
            process_status.current.color = ft.colors.GREEN
            
        except Exception as e:
            process_status.current.value = f"❌ 错误: {str(e)}"
            process_status.current.color = ft.colors.RED
        finally:
            loading_ring.current.visible = False
            page.update()

    def start_processing(e):
        if not selected_file_path.current.value:
            process_status.current.value = "请先选择一个文件！"
            process_status.current.color = ft.colors.RED
            page.update()
            return
            
        path = selected_file_path.current.value
        t_range = time_input.value
        qual = quality_dropdown.value
        
        # 使用线程避免卡死UI
        t = Thread(target=run_cutting_task, args=(path, t_range, qual, None))
        t.start()

    # --- UI 组件构建 ---

    file_picker = ft.FilePicker(on_result=pick_files_result)
    page.overlay.append(file_picker)

    # 1. 标题区
    header = ft.Container(
        content=ft.Column([
            ft.Icon(ft.icons.AUDIO_FILE, size=50, color=ft.colors.BLUE),
            ft.Text("音频切割大师", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("简单 · 快速 · 压缩", size=14, color=ft.colors.GREY),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        alignment=ft.alignment.center,
        margin=ft.margin.only(bottom=20)
    )

    # 2. 文件选择区
    file_section = ft.Container(
        content=ft.Column([
            ft.Text("第一步：选择音频", weight=ft.FontWeight.BOLD),
            ft.Row([
                ft.ElevatedButton(
                    "浏览文件", 
                    icon=ft.icons.FOLDER_OPEN,
                    on_click=lambda _: file_picker.pick_files(allow_multiple=False, allowed_extensions=["mp3", "wav", "m4a", "flac"])
                ),
            ]),
            ft.Text("当前文件:", size=12, color=ft.colors.GREY),
            ft.Text(ref=selected_file_path, value="未选择", size=12, no_wrap=False),
        ]),
        padding=15,
        border=ft.border.all(1, ft.colors.GREY_300),
        border_radius=10,
        bgcolor=ft.colors.BLUE_50,
    )

    # 3. 设置区
    time_input = ft.TextField(
        label="切割区间 (例如 1-2 或 1:30-2:00)",
        hint_text="输入如: 0:30-1:30",
        value="0-1", # 默认值
        prefix_icon=ft.icons.TIMER
    )
    
    quality_dropdown = ft.Dropdown(
        label="压缩质量 (影响文件大小)",
        value="中 (128k)",
        options=[
            ft.dropdown.Option("高 (320k)"),
            ft.dropdown.Option("中 (128k)"),
            ft.dropdown.Option("低 (64k)"),
        ],
        prefix_icon=ft.icons.COMPRESS
    )

    settings_section = ft.Container(
        content=ft.Column([
            ft.Text("第二步：切割设置", weight=ft.FontWeight.BOLD),
            time_input,
            ft.Text("输入说明: '1-2' 表示第1分钟到第2分钟", size=10, color=ft.colors.GREY),
            ft.Divider(height=10, color=ft.colors.TRANSPARENT),
            quality_dropdown,
        ]),
        padding=15,
        margin=ft.margin.only(top=10),
        border=ft.border.all(1, ft.colors.GREY_300),
        border_radius=10,
    )

    # 4. 执行区
    action_section = ft.Container(
        content=ft.Column([
            ft.ElevatedButton(
                "开始切割 & 压缩",
                icon=ft.icons.CUT,
                style=ft.ButtonStyle(
                    color=ft.colors.WHITE,
                    bgcolor=ft.colors.BLUE,
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=15
                ),
                width=400, # 撑满
                on_click=start_processing
            ),
            ft.Row([
                ft.ProgressRing(ref=loading_ring, visible=False, width=20, height=20),
                ft.Text(ref=process_status, value="准备就绪", size=14)
            ], alignment=ft.MainAxisAlignment.CENTER)
        ]),
        margin=ft.margin.only(top=20)
    )

    # 初始化检查记忆
    last_file = load_last_file()

    page.add(
        header,
        file_section,
        settings_section,
        action_section
    )

ft.app(target=main)
