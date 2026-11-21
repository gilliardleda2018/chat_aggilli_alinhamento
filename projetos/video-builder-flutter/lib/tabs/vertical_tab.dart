import 'package:flutter/material.dart';

import '../state/app_state.dart';
import '../widgets/common.dart';

/// Aba 13 · Vertical 9:16: converte o projeto para Reels/TikTok/Shorts.
class VerticalTab extends StatelessWidget {
  const VerticalTab({super.key});

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final o = app.plan.output;
    final isVertical = o.aspect == '9:16';
    return ListView(children: [
      Section(title: 'Formato vertical', children: [
        Text(isVertical ? '✅ O projeto já está em 9:16.' : 'Formato atual: ${o.aspect}.'),
        const SizedBox(height: 8),
        const Text('Como encaixar vídeos horizontais:'),
        RadioGroup<String>(
          groupValue: o.fit,
          onChanged: (v) {
            if (v == null) return;
            o.fit = v;
            app.touch();
          },
          child: const Column(children: [
            RadioListTile<String>(
                contentPadding: EdgeInsets.zero,
                value: 'blur',
                title: Text('Fundo desfocado'),
                subtitle: Text('Mostra o quadro inteiro (mais seguro)')),
            RadioListTile<String>(
                contentPadding: EdgeInsets.zero,
                value: 'crop',
                title: Text('Cortar as bordas'),
                subtitle: Text('Preenche a tela; o assunto precisa estar no centro')),
            RadioListTile<String>(
                contentPadding: EdgeInsets.zero, value: 'pad', title: Text('Tarjas pretas')),
          ]),
        ),
        FilledButton.icon(
          icon: const Icon(Icons.stay_current_portrait),
          label: const Text('Converter para 9:16 (1080x1920, 30 fps)'),
          onPressed: () {
            o.aspect = '9:16';
            o.height = 1080;
            o.fps = 30;
            o.loudness ??= -14;
            app.touch();
            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Projeto em 9:16.')));
          },
        ),
      ]),
      Section(title: 'Zona segura das redes', children: [
        SizedBox(
          height: 320,
          child: Center(child: AspectRatio(
            aspectRatio: 9 / 16,
            child: Container(
              decoration: BoxDecoration(border: Border.all(color: Theme.of(context).colorScheme.outline)),
              child: Column(children: [
                Expanded(flex: 15, child: Container(color: Colors.red.withValues(alpha: 0.25),
                    child: const Center(child: Text('15% topo: evite', style: TextStyle(fontSize: 11))))),
                const Expanded(flex: 65, child: Center(child: Text('Área livre'))),
                Expanded(flex: 20, child: Container(color: Colors.red.withValues(alpha: 0.25),
                    child: const Center(child: Text('20% base: interface', style: TextStyle(fontSize: 11))))),
              ]),
            ),
          )),
        ),
        const SizedBox(height: 8),
        const Text('Textos "Embaixo" já respeitam a zona segura no servidor. Use "Topo" para gancho e "Centro" '
            'para destaque.'),
      ]),
    ]);
  }
}
