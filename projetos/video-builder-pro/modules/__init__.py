"""Modulos Video Builder Pro v7.3
Imports com fallback para uso standalone (sem pacote).
"""

try:
    from modules.transitions_gl import GLTransitionsEngine, GLTransition, EasingType
    from modules.luts_manager import LUTManager, LUTInfo
    from modules.auto_editor import AutoEditor, EditDecision
    from modules.subtitles_ai import SubtitlesAI, SubtitleSegment
    from modules.vertical_converter import VerticalConverter, CropMode
    from modules.gpu_encoder import GPUEncoder, GPUInfo, EncoderPreset
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from transitions_gl import GLTransitionsEngine, GLTransition, EasingType
    from luts_manager import LUTManager, LUTInfo
    from auto_editor import AutoEditor, EditDecision
    from subtitles_ai import SubtitlesAI, SubtitleSegment
    from vertical_converter import VerticalConverter, CropMode
    from gpu_encoder import GPUEncoder, GPUInfo, EncoderPreset

__all__ = [
    "GLTransitionsEngine", "GLTransition", "EasingType",
    "LUTManager", "LUTInfo",
    "AutoEditor", "EditDecision",
    "SubtitlesAI", "SubtitleSegment",
    "VerticalConverter", "CropMode",
    "GPUEncoder", "GPUInfo", "EncoderPreset",
]
