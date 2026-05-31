#!/usr/bin/env python3
"""
Xóa các file được LLM generate trong WPF projects
"""
import os
import shutil
from pathlib import Path

WPF_ROOT = Path("src/wpf")

# Các thư mục chứa file generated
GENERATED_DIRS = [
    # Avalonia
    WPF_ROOT / "vba_brain.UI.Avalonia/Views",
    WPF_ROOT / "vba_brain.UI.Avalonia/ViewModels",
    # WPF (cũ)
    WPF_ROOT / "vba_brain.UI.WPF/Views",
    WPF_ROOT / "vba_brain.UI.WPF/ViewModels",
    # Application
    WPF_ROOT / "vba_brain.Application/Services",
    WPF_ROOT / "vba_brain.Application/DTOs",
    WPF_ROOT / "vba_brain.Application/DTOs/Requests",
    WPF_ROOT / "vba_brain.Application/DTOs/Responses",
    WPF_ROOT / "vba_brain.Application/Interfaces",
    # Infrastructure
    WPF_ROOT / "vba_brain.Infrastructure/Repositories",
    WPF_ROOT / "vba_brain.Infrastructure/Persistence/Repositories",
    # Domain
    WPF_ROOT / "vba_brain.Domain/Entities",
    WPF_ROOT / "vba_brain.Domain/Interfaces",
]

def clean_generated_files():
    """Xóa tất cả file generated"""
    total_deleted = 0
    
    for dir_path in GENERATED_DIRS:
        if not dir_path.exists():
            print(f"⊘ {dir_path} không tồn tại")
            continue
        
        # Giữ lại các file cơ bản (không phải generated)
        keep_files = {".gitkeep", "README.md"}
        
        for file in dir_path.glob("*"):
            if file.name not in keep_files and file.is_file():
                try:
                    file.unlink()
                    print(f"✓ Xóa: {file.relative_to(WPF_ROOT)}")
                    total_deleted += 1
                except Exception as e:
                    print(f"✗ Lỗi xóa {file}: {e}")
    
    print(f"\n✓ Tổng cộng xóa {total_deleted} file")

if __name__ == "__main__":
    clean_generated_files()
