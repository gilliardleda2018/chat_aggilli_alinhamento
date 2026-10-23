#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V7.3 INTEGRATION - Video Builder Pro
Integra todos os novos modulos no app principal
"""

from pathlib import Path
from typing import Optional, List

# Imports com fallback
import sys
sys.path.insert(0, str(Path(__file__).parent))

from transitions_gl import GLTransitionsEngine, GLTransition, EasingType
from luts_manager import LUTManager
from auto_editor import AutoEditor, EditDecision
from subtitles_ai import SubtitlesAI, SubtitleSegment
from vertical_converter import VerticalConverter, CropMode
from gpu_encoder import GPUEncoder, GPUInfo, EncoderPreset, GPUType


class V73Integration:
    """Integra novos modulos ao Video Builder Pro"""

    def __init__(self, log_callback):
        self.log = log_callback

        # Inicializa engines
        self.transitions = GLTransitionsEngine(log_callback)
        self.luts = LUTManager(log_callback)
        self.auto_editor = AutoEditor(log_callback)
        self.subtitles = SubtitlesAI(log_callback)
        self.vertical = VerticalConverter(log_callback)
        self.gpu = GPUEncoder(log_callback)

        self.log("V7.3 Integration: Todos os modulos carregados")

    def renderizar_com_transicao_gl(self, clip1: Path, clip2: Path,
                                    tipo_transicao: str, duracao: float,
                                    easing: str, saida: Path) -> Path:
        """Renderiza transicao GL entre dois clips"""

        # Converte strings para enums
        easing_enum = EasingType[easing.upper()] if easing else EasingType.CUBIC

        # Cria transicao
        transicao = GLTransition(
            nome=tipo_transicao,
            duracao=duracao,
            easing=easing_enum
        )

        return self.transitions.renderizar_transicao(clip1, clip2, transicao, saida)

    def aplicar_lut_rapido(self, video: Path, nome_lut: str,
                          intensidade: float, saida: Path) -> Path:
        """Aplica LUT rapidamente"""
        return self.luts.aplicar_lut(video, nome_lut, saida, intensidade)

    def remover_silencios_auto(self, video: Path, saida: Path,
                               threshold_db: float = -35.0) -> Path:
        """Remove silencios automaticamente"""
        return self.auto_editor.remover_silencios_simples(
            video, saida, threshold_db
        )

    def gerar_legendas_video(self, video: Path, saida_srt: Path,
                            modelo: str = "base") -> Path:
        """Gera legendas para video"""
        return self.subtitles.gerar_legendas(video, "pt", modelo, "srt")

    def converter_vertical_rapido(self, video: Path, saida: Path,
                                  modo: str = "center") -> Path:
        """Converte para vertical rapidamente"""
        modo_enum = CropMode[modo.upper()] if modo else CropMode.CENTER
        return self.vertical.converter(video, saida, modo_enum)

    def obter_melhor_encoder(self) -> dict:
        """Retorna informacoes do melhor encoder"""
        gpu = self.gpu.obter_melhor_gpu()
        presets = self.gpu.obter_presets(gpu.tipo)

        return {
            "gpu": gpu.nome,
            "tipo": gpu.tipo.value,
            "encoder": gpu.encoder,
            "velocidade": self.gpu.estimar_velocidade(gpu.tipo),
            "presets": [
                {
                    "nome": p.nome,
                    "codec": p.codec,
                    "crf": p.crf,
                    "descricao": p.descricao
                }
                for p in presets
            ]
        }

    def listar_transicoes_gl(self) -> List[dict]:
        """Lista transicoes GL disponiveis"""
        return self.transitions.listar_transicoes()

    def listar_luts_disponiveis(self) -> List[dict]:
        """Lista LUTs disponiveis"""
        luts = self.luts.listar_luts()
        return [
            {
                "nome": l.nome,
                "tipo": l.tipo,
                "categoria": l.categoria,
                "descricao": l.descricao
            }
            for l in luts
        ]

    def listar_gpus(self) -> List[dict]:
        """Lista GPUs detectadas"""
        return [
            {
                "tipo": g.tipo.value,
                "nome": g.nome,
                "encoder": g.encoder,
                "disponivel": g.disponivel
            }
            for g in self.gpu.gpus_detectadas
        ]
