import 'package:flutter/material.dart';

import '../models/edit_plan.dart';
import '../services/analysis.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Aba 11 · Auto-Edição: analisa um vídeo no servidor e monta os clipes sozinho.
/// Modo "Remover silêncios": usa sound_segments. Modo "Por cenas": corta nas trocas de cena.
class AutoEdicaoTab extends StatefulWidget {
  const AutoEdicaoTab({super.key});
  @override
  State<AutoEdicaoTab> createState() => _AutoEdicaoTabState();
}

class _AutoEdicaoTabState extends State<AutoEdicaoTab> {
  String? _path;
  String _mode = 'som';
  double _minLen = 1.0;
  double _maxLen = 6.0;
  double _pad = 0.15;
  bool _replace = false;
  String? _progress;
  Analysis? _a;

  Future<void> _run() async {
    final app = AppScope.read(context);
    if (_path == null) return;
    setState(() => _progress = 'Analisando…');
    final a = _a?.path == _path
        ? _a
        : await runWithFeedback(context, () => analyzeMedia(app, _path!, onProgress: (p, m) {
              if (mounted) setState(() => _progress = '$p% · $m');
            }));
    if (!mounted) return;
    setState(() => _progress = null);
    if (a == null) return;
    _a = a;
    final clips = buildClips(a, mode: _mode, minLen: _minLen, maxLen: _maxLen, pad: _pad);
    if (clips.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Nenhum trecho encontrado com esses limites.')));
      return;
    }
    if (_replace) app.plan.clips.clear();
    app.plan.clips.addAll(clips);
    app.touch();
    final total = clips.fold<double>(0, (s, c) => s + (c.length ?? 0));
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('${clips.length} clipes criados (${fmtSeconds(total)} de ${fmtSeconds(a.duration)}). '
            'Revise na Timeline.')));
  }

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final videos = app.plan.clips.where((c) => !c.isImage).map((c) => c.source).toSet().toList();
    return ListView(children: [
      Section(title: '1. Vídeo de origem', children: [
        Wrap(spacing: 8, runSpacing: 8, children: [
          for (final v in videos)
            ChoiceChip(label: Text(baseName(v)), selected: _path == v, onSelected: (_) => setState(() => _path = v)),
          ActionChip(
            avatar: const Icon(Icons.folder_open, size: 18),
            label: const Text('Escolher no Nextcloud'),
            onPressed: () async {
              final p = await pickNextcloudFile(context, filter: kVideoExt);
              if (p != null) setState(() => _path = p);
            },
          ),
        ]),
        if (_path != null) Padding(padding: const EdgeInsets.only(top: 6), child: Text(_path!)),
      ]),
      Section(title: '2. Como cortar', children: [
        SegmentedButton<String>(
          segments: const [
            ButtonSegment(value: 'som', label: Text('Remover silêncios'), icon: Icon(Icons.record_voice_over)),
            ButtonSegment(value: 'cenas', label: Text('Por cenas'), icon: Icon(Icons.burst_mode)),
          ],
          selected: {_mode},
          onSelectionChanged: (s) => setState(() => _mode = s.first),
        ),
        SliderRow(label: 'Mín. por clipe', value: _minLen, min: 0.5, max: 5, divisions: 9,
            format: (v) => '${v.toStringAsFixed(1)} s', onChanged: (v) => setState(() => _minLen = v)),
        SliderRow(label: 'Máx. por clipe', value: _maxLen, min: 2, max: 30, divisions: 28,
            format: (v) => '${v.toStringAsFixed(0)} s', onChanged: (v) => setState(() => _maxLen = v)),
        if (_mode == 'som')
          SliderRow(label: 'Folga', value: _pad, min: 0, max: 0.5, divisions: 10,
              format: (v) => '${v.toStringAsFixed(2)} s', onChanged: (v) => setState(() => _pad = v)),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Substituir os clipes atuais'),
          subtitle: const Text('Desligado = acrescenta no fim da timeline'),
          value: _replace,
          onChanged: (v) => setState(() => _replace = v),
        ),
        FilledButton.icon(
          icon: const Icon(Icons.auto_fix_high),
          label: const Text('Analisar e montar'),
          onPressed: _path == null || _progress != null || !app.serverLoggedIn ? null : _run,
        ),
        if (_progress != null) ...[const SizedBox(height: 8), const LinearProgressIndicator(), Text(_progress!)],
      ]),
    ]);
  }
}

/// Regras de montagem automática (testadas em test/edit_plan_test.dart).
List<Clip> buildClips(Analysis a, {required String mode, double minLen = 1, double maxLen = 6, double pad = 0.15}) {
  final dur = a.duration;
  final ranges = <Segment>[];
  if (mode == 'som') {
    ranges.addAll(a.sound.map((s) => Segment((s.start - pad).clamp(0.0, double.infinity),
        dur == null ? s.end + pad : (s.end + pad).clamp(0.0, dur))));
  } else {
    final cuts = [0.0, ...a.scenes, if (dur != null) dur];
    for (var i = 0; i + 1 < cuts.length; i++) {
      ranges.add(Segment(cuts[i], cuts[i + 1]));
    }
  }
  final out = <Clip>[];
  for (final r in ranges) {
    var s = r.start;
    while (r.end - s >= minLen) {
      final e = (s + maxLen < r.end) ? s + maxLen : r.end;
      out.add(Clip(
          source: a.path,
          start: double.parse(s.toStringAsFixed(2)),
          end: double.parse(e.toStringAsFixed(2)),
          sourceDuration: dur));
      s = e;
    }
  }
  return out;
}
