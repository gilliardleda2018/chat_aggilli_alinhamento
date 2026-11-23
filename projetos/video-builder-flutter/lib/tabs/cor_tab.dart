import 'package:flutter/material.dart';

import '../models/edit_plan.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Aba 4 · Cor: ajuste aplicado ao vídeo inteiro (ColorGrade do servidor).
class CorTab extends StatelessWidget {
  const CorTab({super.key});

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final g = app.plan.color ??= ColorGrade();
    void set(void Function() f) {
      f();
      app.touch();
    }

    return ListView(children: [
      Section(title: 'Ajuste de cor', trailing: TextButton(
        onPressed: () => set(() => app.plan.color = ColorGrade()),
        child: const Text('Zerar'),
      ), children: [
        SliderRow(label: 'Brilho', value: g.brightness, min: -0.3, max: 0.3, divisions: 60,
            onChanged: (v) => set(() => g.brightness = _r(v))),
        SliderRow(label: 'Contraste', value: g.contrast, min: 0.5, max: 1.6, divisions: 110,
            onChanged: (v) => set(() => g.contrast = _r(v))),
        SliderRow(label: 'Saturação', value: g.saturation, min: 0, max: 2, divisions: 100,
            onChanged: (v) => set(() => g.saturation = _r(v))),
        SliderRow(label: 'Temperatura', value: g.warmth, min: -1, max: 1, divisions: 100,
            onChanged: (v) => set(() => g.warmth = _r(v))),
      ]),
      Section(title: 'Sugestões rápidas', children: [
        Wrap(spacing: 8, runSpacing: 8, children: [
          ActionChip(label: const Text('Viagem / verão'), onPressed: () => set(() =>
              app.plan.color = ColorGrade(warmth: 0.3, saturation: 1.15, contrast: 1.05))),
          ActionChip(label: const Text('Corporativo'), onPressed: () => set(() =>
              app.plan.color = ColorGrade(contrast: 1.05))),
          ActionChip(label: const Text('Noite / frio'), onPressed: () => set(() =>
              app.plan.color = ColorGrade(warmth: -0.2, contrast: 1.05))),
        ]),
        const SizedBox(height: 8),
        const Text('Ajuste leve e consistente fica mais profissional que filtro pesado. '
            'Mais looks na aba LUTs Avançadas.'),
      ]),
    ]);
  }
}

double _r(double v) => double.parse(v.toStringAsFixed(2));
