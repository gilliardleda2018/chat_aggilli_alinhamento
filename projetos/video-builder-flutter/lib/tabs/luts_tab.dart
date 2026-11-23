import 'package:flutter/material.dart';

import '../models/edit_plan.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Aba 10 · LUTs: looks do desktop (modules/luts_manager.py) convertidos para o ColorGrade do servidor.
/// É uma aproximação: o servidor aplica brilho/contraste/saturação/temperatura, ainda não arquivos .cube.
class Look {
  final String name, description;
  final ColorGrade Function() grade;
  const Look(this.name, this.description, this.grade);
}

final List<Look> kLooks = [
  Look('Cinematic', 'Contraste alto, saturação reduzida',
      () => ColorGrade(contrast: 1.15, saturation: 0.85, brightness: -0.02, warmth: -0.05)),
  Look('Orange & Teal', 'Quente nas luzes, frio nas sombras (aprox.)',
      () => ColorGrade(contrast: 1.1, saturation: 1.1, warmth: 0.25)),
  Look('Film Noir', 'Preto e branco com alto contraste',
      () => ColorGrade(saturation: 0, contrast: 1.3, brightness: -0.05)),
  Look('Vibrant', 'Cores vivas e saturadas', () => ColorGrade(contrast: 1.2, saturation: 1.4, brightness: 0.05)),
  Look('Warm', 'Tons quentes, aconchegantes', () => ColorGrade(contrast: 1.1, saturation: 1.1, warmth: 0.3)),
  Look('Cold', 'Tons frios, azulados', () => ColorGrade(contrast: 1.05, saturation: 0.9, warmth: -0.3)),
  Look('Bleach Bypass', 'Alto contraste, baixa saturação', () => ColorGrade(contrast: 1.3, saturation: 0.6)),
  Look('Vintage', 'Desbotado e quente', () => ColorGrade(contrast: 0.9, saturation: 0.75, warmth: 0.2, brightness: 0.03)),
  Look('Natural', 'Correção leve, sem cara de filtro', () => ColorGrade(contrast: 1.05, saturation: 1.05)),
];

class LutsTab extends StatelessWidget {
  const LutsTab({super.key});

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    return ListView(children: [
      for (final l in kLooks)
        Card(
          margin: const EdgeInsets.fromLTRB(12, 6, 12, 0),
          child: ListTile(
            leading: _Swatch(l.grade()),
            title: Text(l.name),
            subtitle: Text(l.description),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {
              app.plan.color = l.grade();
              app.touch();
              ScaffoldMessenger.of(context)
                  .showSnackBar(SnackBar(content: Text('Look "${l.name}" aplicado. Ajuste fino na aba Cor.')));
            },
          ),
        ),
      const ServerPendingCard(
        feature: 'LUT de arquivo (.cube)',
        needs: 'campo "lut" no ColorGrade, aplicado com o filtro lut3d do FFmpeg a partir de um .cube no Nextcloud.',
        meanwhile: 'os looks acima reproduzem os do desktop com os ajustes que o servidor já aplica.',
      ),
    ]);
  }
}

/// Amostra aproximada da cor (céu, pele, sombra) com o look aplicado.
class _Swatch extends StatelessWidget {
  final ColorGrade g;
  const _Swatch(this.g);

  Color _apply(Color c) {
    var r = c.r, gg = c.g, b = c.b;
    final l = 0.299 * r + 0.587 * gg + 0.114 * b;
    r = l + (r - l) * g.saturation;
    gg = l + (gg - l) * g.saturation;
    b = l + (b - l) * g.saturation;
    r = (r - 0.5) * g.contrast + 0.5 + g.brightness + g.warmth * 0.08;
    gg = (gg - 0.5) * g.contrast + 0.5 + g.brightness;
    b = (b - 0.5) * g.contrast + 0.5 + g.brightness - g.warmth * 0.08;
    return Color.from(alpha: 1, red: r.clamp(0.0, 1.0), green: gg.clamp(0.0, 1.0), blue: b.clamp(0.0, 1.0));
  }

  @override
  Widget build(BuildContext context) => SizedBox(
        width: 48,
        height: 40,
        child: Row(children: [
          for (final c in const [Color(0xFF5DA9E9), Color(0xFFE0A47A), Color(0xFF2F3B2F)])
            Expanded(child: Container(color: _apply(c))),
        ]),
      );
}
