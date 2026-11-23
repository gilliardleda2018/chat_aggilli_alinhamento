import 'package:flutter/material.dart';

import '../widgets/common.dart';
import 'pending_flow.dart';

/// Aba 16 · Legendas Turbo (faster-whisper): tela pronta, aguarda ferramenta no servidor.
class LegendasTurboTab extends StatelessWidget {
  const LegendasTurboTab({super.key});

  @override
  Widget build(BuildContext context) => ListView(children: const [
        ServerPendingCard(
          feature: 'Legendas Turbo (faster-whisper)',
          needs: 'ferramenta vb_transcribe_start (faster-whisper, modelo small/medium em CPU).',
          meanwhile: 'use uma legenda pronta na aba Legendas AI.',
        ),
        PendingFlow(steps: [
          'Escolher o vídeo (ou o render final)',
          'Escolher idioma (português por padrão) e tamanho do modelo',
          'Servidor transcreve e grava o .srt no Nextcloud',
          'A legenda entra sozinha no roteiro',
        ]),
      ]);
}
