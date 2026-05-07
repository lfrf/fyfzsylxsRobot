#!/usr/bin/env python3
"""
唤醒词功能测试脚本
用于验证 sherpa-onnx 唤醒词引擎是否正常工作
"""
import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))


def test_imports():
    """测试依赖库是否安装"""
    print("=" * 60)
    print("测试 1: 检查依赖库")
    print("=" * 60)
    
    try:
        import sherpa_onnx
        print("✅ sherpa_onnx 已安装")
        print(f"   版本: {getattr(sherpa_onnx, '__version__', 'unknown')}")
    except ImportError as e:
        print(f"❌ sherpa_onnx 未安装: {e}")
        print("   请运行: pip install sherpa-onnx")
        return False
    
    try:
        import sounddevice as sd
        print("✅ sounddevice 已安装")
        print(f"   版本: {sd.__version__}")
    except ImportError as e:
        print(f"❌ sounddevice 未安装: {e}")
        print("   请运行: pip install sounddevice")
        return False
    
    try:
        import numpy as np
        print("✅ numpy 已安装")
        print(f"   版本: {np.__version__}")
    except ImportError as e:
        print(f"❌ numpy 未安装: {e}")
        print("   请运行: pip install numpy")
        return False
    
    print()
    return True


def test_audio_devices():
    """测试音频设备"""
    print("=" * 60)
    print("测试 2: 检查音频设备")
    print("=" * 60)
    
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        print(f"找到 {len(devices)} 个音频设备:\n")
        
        for i, device in enumerate(devices):
            device_type = []
            if device['max_input_channels'] > 0:
                device_type.append("输入")
            if device['max_output_channels'] > 0:
                device_type.append("输出")
            
            print(f"设备 {i}: {device['name']}")
            print(f"  类型: {', '.join(device_type)}")
            print(f"  输入通道: {device['max_input_channels']}")
            print(f"  输出通道: {device['max_output_channels']}")
            print(f"  采样率: {device['default_samplerate']} Hz")
            print()
        
        default_input = sd.query_devices(kind='input')
        print(f"默认输入设备: {default_input['name']}")
        print()
        return True
    except Exception as e:
        print(f"❌ 检查音频设备失败: {e}")
        return False


def test_model_files():
    """测试模型文件是否存在"""
    print("=" * 60)
    print("测试 3: 检查模型文件")
    print("=" * 60)
    
    model_dir = project_root / "models" / "sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20"
    
    if not model_dir.exists():
        print(f"❌ 模型目录不存在: {model_dir}")
        return False
    
    print(f"✅ 模型目录存在: {model_dir}\n")
    
    required_files = [
        "encoder-epoch-13-avg-2-chunk-8-left-64.onnx",
        "decoder-epoch-13-avg-2-chunk-8-left-64.onnx",
        "joiner-epoch-13-avg-2-chunk-8-left-64.onnx",
        "tokens.txt",
        "keywords.txt",
    ]
    
    all_exist = True
    for filename in required_files:
        filepath = model_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size
            print(f"✅ {filename} ({size:,} bytes)")
        else:
            print(f"❌ {filename} 不存在")
            all_exist = False
    
    print()
    
    # 读取关键词文件
    keywords_file = model_dir / "keywords.txt"
    if keywords_file.exists():
        try:
            content = keywords_file.read_text(encoding="utf-8").strip()
            print(f"关键词文件内容:\n{content}\n")
        except Exception as e:
            print(f"⚠️  读取关键词文件失败: {e}\n")
    
    return all_exist


def test_wake_word_provider():
    """测试唤醒词引擎"""
    print("=" * 60)
    print("测试 4: 测试唤醒词引擎")
    print("=" * 60)
    
    try:
        from raspirobot.audio.wake_word_sherpa import (
            SherpaOnnxWakeWordConfig,
            SherpaOnnxWakeWordProvider,
        )
        
        config = SherpaOnnxWakeWordConfig(
            model_dir="models/sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20",
            keywords_file="models/sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20/keywords.txt",
            expected_keyword="你好小星",
            device=1,  # 根据你的设备调整
        )
        
        print("创建唤醒词引擎...")
        provider = SherpaOnnxWakeWordProvider(config)
        
        print("✅ 唤醒词引擎创建成功")
        print(f"   模型目录: {config.model_dir}")
        print(f"   关键词文件: {config.keywords_file}")
        print(f"   期望关键词: {config.expected_keyword}")
        print(f"   音频设备: {config.device}")
        print()
        
        print("启动唤醒词检测...")
        provider.start()
        
        # 等待一下，看是否有初始化错误
        time.sleep(2)
        
        if not provider._running:
            print("❌ 唤醒词引擎启动失败（后台线程未运行）")
            print("   请检查日志中的错误信息")
            return False
        
        print("✅ 唤醒词引擎启动成功")
        print()
        print("=" * 60)
        print("现在请说唤醒词: '你好小星'")
        print("按 Ctrl+C 停止测试")
        print("=" * 60)
        print()
        
        try:
            while True:
                if provider.poll():
                    print(f"🎉 检测到唤醒词！时间: {time.strftime('%H:%M:%S')}")
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\n测试被用户中断")
        finally:
            print("停止唤醒词引擎...")
            provider.stop()
            print("✅ 唤醒词引擎已停止")
        
        return True
        
    except Exception as e:
        import traceback
        print(f"❌ 测试失败: {e}")
        print("\n详细错误信息:")
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "唤醒词功能测试脚本" + " " * 15 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    # 测试 1: 依赖库
    if not test_imports():
        print("\n❌ 依赖库测试失败，请先安装缺失的库")
        return 1
    
    # 测试 2: 音频设备
    if not test_audio_devices():
        print("\n⚠️  音频设备测试失败，但可以继续")
    
    # 测试 3: 模型文件
    if not test_model_files():
        print("\n❌ 模型文件测试失败，请确保模型已下载")
        return 1
    
    # 测试 4: 唤醒词引擎
    if not test_wake_word_provider():
        print("\n❌ 唤醒词引擎测试失败")
        return 1
    
    print("\n")
    print("=" * 60)
    print("✅ 所有测试通过！唤醒词功能正常")
    print("=" * 60)
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
