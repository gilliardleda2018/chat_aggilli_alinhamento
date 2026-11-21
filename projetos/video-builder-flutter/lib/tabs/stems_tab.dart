import 'package:flutter/material.dart';

import '../widgets/common.dart';
import 'pending_flow.dart';

/// Aba 15 · Audio Stems (Demucs): tela pronta, aguarda ferramenta no servidor.
class StemsTab extends StatelessWidget {
  const StemsTab({super.key});

  @override
  Widget build(BuildContext context) => ListView(children: const [
        ServerPendingCard(
          feature: 'Separar voz e instrumental (Demucs)',
          needs: 'ferramenta vb_stems_start com GPU, que grave voz.wav e instrumental.wav no Nextcloud.',
          meanwhile: 'baixe o volume do clipe (Timeline → Volume) e use uma trilha própria na aba Áudio.',
        ),
        PendingFlow(steps: [
          'Escolher um vídeo ou áudio do Nextcloud',
          'Servidor separa em voz, bateria, baixo e outros',
          'Arquivos voltam para o Nextcloud',
          'Usar a voz isolada ou o instrumental como trilha',
        ]),
      ]);
}
