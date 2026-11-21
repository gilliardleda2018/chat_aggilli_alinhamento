import 'package:flutter/material.dart';

import '../models/edit_plan.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Aba 12 · Legendas AI: hoje embute legenda pronta (.srt/.vtt/.ass); geração automática aguarda Whisper no servidor.
class LegendasTab extends StatelessWidget {
  const LegendasTab({super.key});

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final s = app.plan.subtitles;
    return ListView(children: [
      Section(title: 'Legenda embutida', children: [
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.subtitles),
          title: Text(s == null ? 'Sem legenda' : baseName(s.source)),
          subtitle: Text(s?.source ?? 'Arquivo .srt, .vtt ou .ass no Nextcloud, com os tempos do vídeo FINAL.'),
          trailing: s == null
              ? null
              : IconButton(
                  icon: const Icon(Icons.delete_outline),
                  onPressed: () {
                    app.plan.subtitles = null;
                    app.touch();
                  }),
        ),
        OutlinedButton.icon(
          icon: const Icon(Icons.folder_open),
          label: Text(s == null ? 'Escolher legenda' : 'Trocar legenda'),
          onPressed: () async {
            final p = await pickNextcloudFile(context, filter: kSubtitleExt, title: 'Escolher legenda');
            if (p != null) {
              app.plan.subtitles = Subtitles(source: p);
              app.touch();
            }
          },
        ),
        if (s != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'normal', label: Text('Normal')),
                ButtonSegment(value: 'large', label: Text('Grande')),
              ],
              selected: {s.size},
              onSelectionChanged: (v) {
                s.size = v.first;
                app.touch();
              },
            ),
          ),
      ]),
      const ServerPendingCard(
        feature: 'Legenda automática (Whisper)',
        needs: 'ferramenta vb_transcribe_start (faster-whisper) que gere o .srt no Nextcloud.',
        meanwhile: 'gere o .srt em outro app ou no desktop, envie pela aba Enviar / Importar e escolha aqui.',
      ),
    ]);
  }
}
