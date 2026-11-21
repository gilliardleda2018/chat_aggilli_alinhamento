import 'package:flutter/material.dart';

import '../widgets/common.dart';
import 'pending_flow.dart';

/// Aba 18 · Face Restore (GFPGAN): tela pronta, aguarda ferramenta no servidor.
class FaceRestoreTab extends StatelessWidget {
  const FaceRestoreTab({super.key});

  @override
  Widget build(BuildContext context) => ListView(children: const [
        ServerPendingCard(
          feature: 'Restauração de rostos (GFPGAN)',
          needs: 'ferramenta com GPU no servidor que processe o vídeo quadro a quadro e grave o resultado no Nextcloud.',
        ),
        PendingFlow(steps: [
          'Escolher um vídeo antigo ou de baixa qualidade',
          'Escolher a intensidade da restauração',
          'Servidor processa (pode levar vários minutos)',
          'Novo vídeo no Nextcloud, pronto para entrar na Timeline',
        ]),
      ]);
}
