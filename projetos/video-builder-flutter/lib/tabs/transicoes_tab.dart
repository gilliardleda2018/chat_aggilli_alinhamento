import 'package:flutter/material.dart';

import '../models/edit_plan.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Aba 9 · Transições: catálogo das 40 transições do servidor (xfade do FFmpeg).
class TransicoesTab extends StatefulWidget {
  const TransicoesTab({super.key});
  @override
  State<TransicoesTab> createState() => _TransicoesTabState();
}

const _groups = {
  'Suaves (recomendadas)': ['fade', 'dissolve', 'fadeblack', 'fadewhite', 'fadegrays', 'hblur'],
  'Cortinas': ['wipeleft', 'wiperight', 'wipeup', 'wipedown'],
  'Deslizar': ['slideleft', 'slideright', 'slideup', 'slidedown', 'smoothleft', 'smoothright', 'smoothup', 'smoothdown'],
  'Formas': ['circleopen', 'circleclose', 'circlecrop', 'rectcrop', 'radial', 'vertopen', 'vertclose', 'horzopen',
      'horzclose', 'diagtl', 'diagtr', 'diagbl', 'diagbr'],
  'Efeitos': ['distance', 'pixelize', 'zoomin', 'squeezeh', 'squeezev', 'hlslice', 'hrslice', 'vuslice', 'vdslice'],
};

class _TransicoesTabState extends State<TransicoesTab> {
  String _type = 'fade';
  double _dur = 0.5;

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final clips = app.plan.clips;
    void applyTo(Iterable<int> idx) {
      for (final i in idx) {
        clips[i].transition = Transition(type: _type, duration: _dur);
      }
      app.touch();
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Transição "$_type" aplicada.')));
    }

    return ListView(children: [
      Section(title: 'Escolha', children: [
        for (final g in _groups.entries) ...[
          Padding(padding: const EdgeInsets.only(top: 6, bottom: 4), child: Text(g.key)),
          Wrap(spacing: 6, runSpacing: 6, children: [
            for (final t in g.value)
              ChoiceChip(label: Text(t), selected: _type == t, onSelected: (_) => setState(() => _type = t)),
          ]),
        ],
        SliderRow(label: 'Duração', value: _dur, min: 0.1, max: 3, divisions: 29,
            format: (v) => '${v.toStringAsFixed(1)} s',
            onChanged: (v) => setState(() => _dur = double.parse(v.toStringAsFixed(1)))),
        const Text('Dica: corte seco é o padrão profissional. Fusão 0,3–0,6 s para passagem de tempo; '
            'fadeblack 0,5–1 s para mudar de assunto.', style: TextStyle(fontSize: 12)),
      ]),
      Section(title: 'Aplicar', children: [
        Wrap(spacing: 8, children: [
          FilledButton(
              onPressed: clips.length < 2 ? null : () => applyTo(List.generate(clips.length - 1, (i) => i + 1)),
              child: const Text('Em todos os cortes')),
          OutlinedButton(
              onPressed: clips.length < 2
                  ? null
                  : () {
                      for (final c in clips) {
                        c.transition = null;
                      }
                      app.touch();
                    },
              child: const Text('Tirar todas (corte seco)')),
        ]),
        for (var i = 1; i < clips.length; i++)
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text('Entre $i e ${i + 1}: ${baseName(clips[i].source)}', maxLines: 1, overflow: TextOverflow.ellipsis),
            subtitle: Text(clips[i].transition == null
                ? 'corte seco'
                : '${clips[i].transition!.type} · ${clips[i].transition!.duration.toStringAsFixed(1)} s'),
            trailing: TextButton(onPressed: () => applyTo([i]), child: const Text('Aplicar')),
          ),
      ]),
    ]);
  }
}
