from typing import List
from pathlib import Path
from os.path import sep as seperator
from pywheels.asker import get_string_input


try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False


def render_html_to_pdf(
    html_file_path: Path, 
    pdf_output_path: Path,
) -> None:
    
    if not WEASYPRINT_AVAILABLE:
        print("[ERROR] 依赖缺失: WeasyPrint 库未安装。无法渲染。")
        print("        请运行 pip install weasyprint")
        return

    print(f"  -> Rendering: {html_file_path.name}")
    
    # WeasyPrint 核心逻辑
    try:
        html_document = HTML(filename=str(html_file_path), encoding="utf-8") # type: ignore
        html_document.write_pdf(target=str(pdf_output_path))
        print(f"  [SUCCESS] PDF Saved: {pdf_output_path.name}")
        
    except Exception as error:
        print(f"  [FAILURE] Render failed for {html_file_path.name}: {error}")


def find_and_render_missing_pdfs(
    target_directory: str,
) -> None:
    
    directory_path = Path(target_directory)
    
    if not directory_path.is_dir():
        print(f"[ERROR] 指定路径不是一个有效的文件夹: {target_directory}")
        return

    print(f"扫描目录: {target_directory}")
    
    # 查找所有 .html 文件
    html_file_paths: List[Path] = list(directory_path.rglob('*.html'))
    
    if not html_file_paths:
        print("未找到任何 .html 文件。")
        return

    missing_count: int = 0
    
    # 遍历所有 HTML 文件并检查对应的 PDF
    for html_path in html_file_paths:
        # 构造预期的 PDF 文件路径
        pdf_path: Path = html_path.with_suffix('.pdf')
        
        if pdf_path.exists():
            # print(f"  [SKIP] PDF 已存在: {pdf_path.name}")
            continue

        # PDF 文件缺失，开始渲染
        missing_count += 1
        render_html_to_pdf(html_path, pdf_path)

    if missing_count == 0:
        print("所有 .html 文件均已匹配到对应的 .pdf 文件。无需渲染。")
    else:
        print(f"--- 渲染完成。共处理了 {missing_count} 个缺失文件。 ---")


def main():
    
    target_directory = get_string_input(
        prompt = "请输入要扫描的目录：",
        default = f"documents{seperator}problems{seperator}answer_sheets",
    )
    
    find_and_render_missing_pdfs(
        target_directory = target_directory,
    )
    
    print("Program OK.")


if __name__ == "__main__":
    
    main()