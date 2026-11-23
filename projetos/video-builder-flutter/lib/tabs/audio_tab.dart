import 'package:flutter/material.dart';

import '../models/edit_plan.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Aba 5 · Áudio: trilha, loudness e fades do vídeo inteiro.
class AudioTab extends StatelessWidget {
  const AudioTab({super.key});

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final o = app.plan.output;
    final m = app.plan.music;
    void set(void Function() f) {
      f();
      app.touch();
    }

    return ListView(children: [
      Section(title: 'Trilha sonora', children: [
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.music_note),
          title: Text(m == null ? 'Sem trilha' : baseName(m.source)),
          subtitle: m == null ? const Text('Escolha um áudio seu no Nextcloud (aba Enviar para mandar do celular).') : Text(m.source),
          trailing: m == null
              ? null
              : IconButton(icon: const Icon(Icons.delete_outline), onPressed: () => set(() => app.plan.music = null)),
        ),
        OutlinedButton.icon(
          icon: const Icon(Icons.library_music),
          label: Text(m == null ? 'Escolher música' : 'Trocar música'),
          onPressed: () async {
            final p = await pickNextcloudFile(context, filter: kAudioExt, title: 'Escolher música');
            if (p != null) set(() => app.plan.music = Music(source: p));
          },
        ),
        if (m != null) ...[
          SliderRow(label: 'Volume', value: m.volume, min: 0, max: 2, divisions: 40,
              format: (v) => '${(v * 100).round()}%', onChanged: (v) => set(() => m.volume = _r(v))),
          NumberField(label: 'Começar a música em (s)', value: m.start, onChanged: (v) => set(() => m.start = v ?? 0)),
          SwitchListTile(contentPadding: EdgeInsets.zero, title: const Text('Ducking'),
              subtitle: const Text('Abaixa a trilha quando há fala'), value: m.ducking,
              onChanged: (v) => set(() => m.ducking = v)),
          SwitchListTile(contentPadding: EdgeInsets.zero, title: const Text('Repetir se for mais curta'),
              value: m.loop, onChanged: (v) => set(() => m.loop = v)),
          Wrap(spacing: 8, children: [
            ActionChip(label: const Text('Com fala (25%, ducking)'),
                onPressed: () => set(() {
                      m.volume = 0.25;
                      m.ducking = true;
                    })),
            ActionChip(label: const Text('Só música (80%)'),
                onPressed: () => set(() {
                      m.volume = 0.8;
                      m.ducking = false;
                    })),
          ]),
        ],
      ]),
      Section(title: 'Acabamento', children: [
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Normalizar volume (loudness)'),
          value: o.loudness != null,
          onChanged: (v) => set(() => o.loudness = v ? -14 : null),
        ),
        if (o.loudness != null)
          SliderRow(label: 'LUFS', value: o.loudness!, min: -30, max: -8, divisions: 22,
              format: (v) => v.toStringAsFixed(0), onChanged: (v) => set(() => o.loudness = v.roundToDouble())),
        const Text('−14 redes sociais e YouTube; −16 podcast/fala calma.', style: TextStyle(fontSize: 12)),
        SliderRow(label: 'Fade abertura', value: o.fadeIn, min: 0, max: 5, divisions: 50,
            format: (v) => '${v.toStringAsFixed(1)} s', onChanged: (v) => set(() => o.fadeIn = _r(v))),
        SliderRow(label: 'Fade final', value: o.fadeOut, min: 0, max: 5, divisions: 50,
            format: (v) => '${v.toStringAsFixed(1)} s', onChanged: (v) => set(() => o.fadeOut = _r(v))),
      ]),
    ]);
  }
}

double _r(double v) => double.parse(v.toStringAsFixed(2));
