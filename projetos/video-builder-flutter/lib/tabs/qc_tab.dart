import 'package:flutter/material.dart';

import '../models/edit_plan.dart';
import '../services/analysis.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Aba 8 · QC: checagem do roteiro (local) + análise de mídia no servidor (LUFS, silêncios, cenas).
class QcTab extends StatefulWidget {
  const QcTab({super.key});
  @override
  State<QcTab> createState() => _QcTabState();
}

class _QcTabState extends State<QcTab> {
  Analysis? _a;
  String? _progress;

  Future<void> _analyze(String path) async {
    final app = AppScope.read(context);
    setState(() => _progress = 'Iniciando…');
    final r = await runWithFeedback(context,
        () => analyzeMedia(app, path, onProgress: (p, m) {
              if (mounted) setState(() => _progress = '$p% · $m');
            }));
    if (mounted) {
      setState(() {
        _progress = null;
        if (r != null) _a = r;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final checks = _planChecks(app.plan);
    return ListView(children: [
      Section(title: 'Checagem do roteiro', children: [
        if (checks.isEmpty) const Text('✅ Nenhum problema encontrado.'),
        for (final c in checks) Text(c),
      ]),
      Section(title: 'Análise de mídia (servidor)', children: [
        const Text('Mede volume (LUFS), silêncios, trocas de cena e trechos com som.'),
        const SizedBox(height: 8),
        Wrap(spacing: 8, runSpacing: 8, children: [
          for (final c in app.plan.clips.where((c) => !c.isImage).map((c) => c.source).toSet())
            ActionChip(
                label: Text(baseName(c)), onPressed: _progress == null ? () => _analyze(c) : null),
          ActionChip(
            avatar: const Icon(Icons.folder_open, size: 18),
            label: const Text('Outro arquivo…'),
            onPressed: _progress != null
                ? null
                : () async {
                    final p = await pickNextcloudFile(context, filter: {...kVideoExt, ...kAudioExt});
                    if (p != null) _analyze(p);
                  },
          ),
        ]),
        if (_progress != null) ...[const SizedBox(height: 8), const LinearProgressIndicator(), Text(_progress!)],
      ]),
      if (_a != null) _result(_a!),
      const ServerPendingCard(
        feature: 'QC do vídeo final (true peak, quadros pretos, checksums)',
        needs: 'ferramenta vb_qc_start sobre o MP4 renderizado.',
        meanwhile: 'a análise acima funciona também com o arquivo final: escolha-o em "Outro arquivo…" '
            '(pasta Video Builder/Renders).',
      ),
    ]);
  }

  Widget _result(Analysis a) {
    final lufs = a.lufs;
    String lufsNote = '';
    if (lufs != null) {
      lufsNote = (lufs - -14).abs() <= 1.5 ? '✅ bom para redes (−14)' : '⚠️ distante de −14 (o render normaliza)';
    }
    final silent = a.silences.fold<double>(0, (s, x) => s + x.length);
    return Section(title: 'Resultado: ${baseName(a.path)}', children: [
      Text('Duração: ${fmtSeconds(a.duration)}'),
      Text('Loudness: ${lufs?.toStringAsFixed(1) ?? '—'} LUFS $lufsNote'),
      Text('Silêncios: ${a.silences.length} (${fmtSeconds(silent)} no total)'),
      Text('Trechos com som: ${a.sound.length}'),
      Text('Trocas de cena: ${a.scenes.length}'),
      if (a.scenes.isNotEmpty)
        Text('Cenas em: ${a.scenes.take(30).map((s) => s.toStringAsFixed(1)).join(', ')}${a.scenes.length > 30 ? '…' : ''}',
            style: const TextStyle(fontSize: 12)),
    ]);
  }
}

List<String> _planChecks(EditPlan plan) {
  final out = <String>[];
  final tl = computeTimeline(plan);
  out.addAll(tl.problems.map((p) => '⚠️ $p'));
  for (var i = 0; i < plan.clips.length; i++) {
    final c = plan.clips[i];
    final l = c.length;
    if (l == null) out.add('ℹ️ Clipe ${i + 1}: duração desconhecida (abra o clipe na Timeline e leia no servidor).');
    if (l != null && l < 0.8) out.add('⚠️ Clipe ${i + 1} muito curto (${l.toStringAsFixed(2)} s).');
    if (!c.isImage && l != null && l > 8 && plan.output.aspect == '9:16') {
      out.add('ℹ️ Clipe ${i + 1} com ${l.toStringAsFixed(1)} s: em Reels, trechos acima de 4 s perdem ritmo.');
    }
  }
  if (plan.music != null && plan.music!.volume > 0.5 && plan.music!.ducking) {
    out.add('ℹ️ Trilha alta com ducking: com fala, 15–30% costuma ficar melhor.');
  }
  final total = tl.total;
  if (total != null && plan.output.aspect == '9:16' && total > 90) {
    out.add('ℹ️ Vídeo vertical com ${fmtSeconds(total)}: Reels/Shorts rendem mais com 15–60 s.');
  }
  for (final t in plan.texts) {
    final words = t.text.trim().split(RegExp(r'\s+')).length;
    final need = (words / 3).clamp(1.5, 99);
    if (t.end - t.start < need) {
      out.add('ℹ️ Texto "${t.text}" fica pouco tempo (precisa de ~${need.toStringAsFixed(1)} s para ser lido).');
    }
  }
  return out;
}
