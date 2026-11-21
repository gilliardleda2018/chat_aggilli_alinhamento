import 'package:flutter/material.dart';

import '../widgets/common.dart';
import 'pending_flow.dart';

/// Aba 19 · WhisperX (legenda karaokê palavra por palavra): tela pronta, aguarda ferramenta no servidor.
class WhisperxTab extends StatelessWidget {
  const WhisperxTab({super.key});

  @override
  Widget build(BuildContext context) => ListView(children: const [
        ServerPendingCard(
          feature: 'Legenda karaokê (WhisperX)',
          needs: 'vb_transcribe_start com tempo por palavra, gerando .ass com destaque da palavra falada.',
          meanwhile: 'um .ass pronto (feito em outro app) já funciona: escolha-o na aba Legendas AI.',
        ),
        PendingFlow(steps: [
          'Escolher o vídeo com fala',
          'Escolher cor de destaque e posição',
          'Servidor gera o .ass com cada palavra sincronizada',
          'A legenda entra no roteiro e é embutida no render',
        ]),
      ]);
}
