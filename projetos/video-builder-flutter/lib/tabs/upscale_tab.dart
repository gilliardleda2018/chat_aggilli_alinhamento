import 'package:flutter/material.dart';

import '../state/app_state.dart';
import '../widgets/common.dart';

/// Aba 14 · Upscale AI: hoje, resolução de saída até 4K por escala do FFmpeg; Real-ESRGAN aguarda o servidor.
class UpscaleTab extends StatelessWidget {
  const UpscaleTab({super.key});

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final o = app.plan.output;
    return ListView(children: [
      Section(title: 'Resolução de saída', children: [
        RadioGroup<int>(
          groupValue: o.height,
          onChanged: (v) {
            if (v == null) return;
            o.height = v;
            app.touch();
          },
          child: const Column(children: [
            RadioListTile<int>(contentPadding: EdgeInsets.zero, value: 720, title: Text('720p (HD)'),
                subtitle: Text('Arquivo menor, render mais rápido')),
            RadioListTile<int>(contentPadding: EdgeInsets.zero, value: 1080, title: Text('1080p (Full HD)'),
                subtitle: Text('Padrão das redes')),
            RadioListTile<int>(contentPadding: EdgeInsets.zero, value: 1440, title: Text('1440p (2K)')),
            RadioListTile<int>(contentPadding: EdgeInsets.zero, value: 2160, title: Text('2160p (4K)'),
                subtitle: Text('Gasta mais minutos do plano')),
          ]),
        ),
        const Text('A escala do servidor (FFmpeg) aumenta o tamanho, mas não cria detalhe que não existe no original.',
            style: TextStyle(fontSize: 12)),
      ]),
      const ServerPendingCard(
        feature: 'Upscale com IA (Real-ESRGAN)',
        needs: 'ferramenta de upscale com GPU no servidor (instância com GPU sob demanda).',
      ),
    ]);
  }
}
