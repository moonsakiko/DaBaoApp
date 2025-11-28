import flet as ft
import os
import wave
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
    page.title = "全能音频切割"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.scroll = "AUTO"
    
    # --- 状态变量 ---
    selected_file_path = ft.Ref[ft.Text]()
    process_status = ft.Ref[ft.Text]()
    loading_ring = ft.Ref[ft.ProgressRing]()
    
    # --- 辅助函数 ---
    
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
        t_str = t_str.strip().lower()
        if t_str.endswith("s"): t_str = t_str[:-1]
        if ":" in t_str:
            parts = t_str.split(":")
            if len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
        try:
            return float(t_str) * 60 # 默认输入数字为分钟
        except:
            return 0.0

    def parse_range(range_str):
        if "-" not in range_str: return None, None
        parts = range_str.split("-")
        return parse_time_str(parts[0]), parse_time_str(parts[1])

    # --- 核心切割逻辑 ---

    # 1. 完美切割 WAV (标准库支持，100% 精确)
    def cut_wav_perfect(file_path, start_sec, end_sec, output_path):
        with wave.open(file_path, "rb") as infile:
            # 获取参数
            nchannels = infile.getnchannels()
            sampwidth = infile.getsampwidth()
            framerate = infile.getframerate()
            
            # 计算帧位置
            start_frame = int(start_sec * framerate)
            end_frame = int(end_sec * framerate)
            total_frames = infile.getnframes()
            
            if end_frame > total_frames: end_frame = total_frames
            frames_to_read = end_frame - start_frame
            
            # 定位并读取
            infile.setpos(start_frame)
            data = infile.readframes(frames_to_read)
            
            # 写入新文件
            with wave.open(output_path, "wb") as outfile:
                outfile.setnchannels(nchannels)
                outfile.setsampwidth(sampwidth)
                outfile.setframerate(framerate)
                outfile.writeframes(data)

    # 2. 改进版 MP3 切割 (物理切割)
    def cut_mp3_improved(file_path, start_sec, end_sec, output_path):
        from mutagen.mp3 import MP3
        
        audio = MP3(file_path)
        length = audio.info.length
        file_size = os.path.getsize(file_path)
        
        # 估算位置
        start_byte = int((start_sec / length) * file_size)
        end_byte = int((end_sec / length) * file_size)
        
        # 【修正】读取一点点头部，尝试找到帧同步头，避免切坏第一帧
        # 这是一个简单的对齐尝试，虽然不如 FFmpeg 完美，但比直接切好
        with open(file_path, 'rb') as src:
            src.seek(start_byte)
            # 尝试向后找 0xFF (MP3 帧头通常是 0xFFF...)
            # 限制寻找范围 2048 字节，找不到就算了
            header_search = src.read(2048)
            sync_offset = 0
            for i in range(len(header_search)-1):
                if header_search[i] == 0xFF and (header_search[i+1] & 0xE0) == 0xE0:
                    sync_offset = i
                    break
            
            # 重新定位到同步头
            real_start = start_byte + sync_offset
            real_len = end_byte - real_start
            
            src.seek(real_start)
            data = src.read(real_len)
            
            with open(output_path, 'wb') as dst:
                dst.write(data)

    def run_cutting_task(file_path, time_range):
        try:
            loading_ring.current.visible = True
            process_status.current.value = "正在分析..."
            process_status.current.color = "blue"
            page.update()

            start_sec, end_sec = parse_range(time_range)
            if start_sec is None: raise Exception("时间格式错误")

            filename = os.path.basename(file_path)
            name, ext = os.path.splitext(filename)
            ext_lower = ext.lower()

            # 路径处理
            output_dir = ANDROID_DOWNLOAD_DIR
            if not os.path.exists(output_dir):
                output_dir = os.path.dirname(file_path)
            final_path = os.path.join(output_dir, f"{name}_cut{ext}")

            # 分流处理
            if ext_lower == ".wav":
                process_status.current.value = "WAV 模式: 正在完美切割..."
                page.update()
                cut_wav_perfect(file_path, start_sec, end_sec, final_path)
                
            elif ext_lower == ".mp3":
                try: import mutagen 
                except: raise Exception("缺少 mutagen 库")
                
                process_status.current.value = "MP3 模式: 正在物理切割..."
                page.update()
                cut_mp3_improved(file_path, start_sec, end_sec, final_path)
                
            else:
                raise Exception(f"暂不支持 {ext} 格式。\n请先转换为 WAV 或 MP3。")

            process_status.current.value = f"✅ 成功! \n{final_path}"
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
    file_picker = ft.FilePicker(on_result=lambda e: (
        selected_file_path.current.update(),
        save_last_file(e.files[0].path) if e.files else None,
        setattr(selected_file_path.current, 'value', e.files[0].path) if e.files else None
    ))
    page.overlay.append(file_picker)

    header = ft.Container(
        content=ft.Column([
            ft.Icon(name="multitrack_audio", size=50, color="blue"), 
            ft.Text("全能音频切割", size=24, weight="bold"),
            ft.Text("推荐使用 WAV 格式以获得完美效果", size=12, color="grey"),
        ], horizontal_alignment="center"),
        alignment=ft.alignment.center,
        margin=ft.margin.only(bottom=20)
    )

    file_section = ft.Container(
        content=ft.Column([
            ft.ElevatedButton("选择音频 (MP3/WAV)", icon="folder_open", 
                             on_click=lambda _: file_picker.pick_files(allowed_extensions=["mp3", "wav"])),
            ft.Text(ref=selected_file_path, value="未选择", size=12),
        ]),
        padding=10, border=ft.border.all(1, "grey"), border_radius=10
    )

    time_input = ft.TextField(label="区间 (如 0:30-1:00)", value="0-1", prefix_icon="timer")
    
    action_btn = ft.ElevatedButton(
        "开始切割", icon="cut", width=300, bgcolor="blue", color="white",
        on_click=start_processing
    )

    page.add(
        header, file_section, ft.Container(height=10), time_input, ft.Container(height=20),
        ft.Column([action_btn, ft.ProgressRing(ref=loading_ring, visible=False), ft.Text(ref=process_status)], horizontal_alignment="center")
    )
    load_last_file()

ft.app(target=main)
