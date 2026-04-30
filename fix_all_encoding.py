#!/usr/bin/env python3
"""
一次性修复所有 Python 文件中的中文智能引号、括号等编码问题
直接在 /root/autodl-tmp/a22/code/fyfzsylxsRobot 目录下运行
"""
import os
from pathlib import Path

def fix_file_encoding(filepath):
    """修复单个文件的编码问题"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # 替换所有中文智能字符为 ASCII 等价物
        replacements = {
            # 中文双引号
            '"': '"',  # U+201C
            '"': '"',  # U+201D
            # 中文单引号
            ''': "'",  # U+2018
            ''': "'",  # U+2019
            # 中文方括号
            '【': '[',  # U+3010
            '】': ']',  # U+3011
            # 其他
            '·': '.',  # U+00B7
            '—': '--', # U+2014
        }

        for old_char, new_char in replacements.items():
            if old_char in content:
                content = content.replace(old_char, new_char)

        # 如果有改动，写回
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"  ERROR in {filepath}: {e}")
        return None

def main():
    """主函数"""
    base_dir = Path('/root/autodl-tmp/a22/code/fyfzsylxsRobot')

    if not base_dir.exists():
        print(f"ERROR: 基础目录不存在: {base_dir}")
        return

    print("=" * 70)
    print("开始全局修复所有 Python 文件的编码问题...")
    print("=" * 70)

    fixed_count = 0
    total_count = 0

    # 扫描 remote/orchestrator, shared, tests, raspirobot
    scan_paths = [
        base_dir / 'remote/orchestrator',
        base_dir / 'shared',
        base_dir / 'tests',
        base_dir / 'raspirobot',
        base_dir / 'remote/speech-service',
        base_dir / 'remote/vision-service',
    ]

    for scan_dir in scan_paths:
        if not scan_dir.exists():
            continue

        print(f"\n📁 处理: {scan_dir.relative_to(base_dir)}/")

        for py_file in scan_dir.rglob('*.py'):
            # 跳过特定目录
            if '__pycache__' in str(py_file) or '.pytest_cache' in str(py_file):
                continue

            total_count += 1
            fixed = fix_file_encoding(py_file)

            if fixed is True:
                fixed_count += 1
                rel_path = py_file.relative_to(base_dir)
                print(f"  ✓ 修复: {rel_path}")
            elif fixed is None:
                total_count -= 1  # 不计算出错的文件

    print("\n" + "=" * 70)
    print(f"✅ 修复完成!")
    print(f"  处理文件总数: {total_count}")
    print(f"  修复文件数: {fixed_count}")
    print("=" * 70)
    print("\n现在请再次运行编译检查:")
    print("  python -m compileall remote/orchestrator shared tests")
    print()

if __name__ == '__main__':
    main()
