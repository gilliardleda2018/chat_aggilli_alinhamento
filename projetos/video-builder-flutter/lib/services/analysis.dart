import '../state/app_state.dart';

/// Análise de mídia no servidor (vb_analyze_start + vb_job_status). Usada pelas abas QC, Auto-Edição e Auto-Edit Suite.
class Segment {
  final double start, end;
  Segment(this.start, this.end);
  double get length => end - start;
}

class Analysis {
  final String path;
  final double? duration;
  final double? lufs;
  final List<double> scenes;
  final List<Segment> silences;
  final List<Segment> sound;
  Analysis(this.path, this.duration, this.lufs, this.scenes, this.silences, this.sound);

  factory Analysis.fromResult(String path, Map<String, dynamic> r) {
    final dur = (r['duration'] as num?)?.toDouble();
    List<Segment> segs(String key) => ((r[key] as List?) ?? const [])
        .whereType<Map>()
        .map((m) => Segment((m['start'] as num).toDouble(), ((m['end'] as num?) ?? dur ?? 0).toDouble()))
        .toList();
    final scenes = ((r['scene_changes'] as List?) ?? const [])
        .map((e) => e is num ? e.toDouble() : (e is Map && e['time'] is num ? (e['time'] as num).toDouble() : null))
        .whereType<double>()
        .toList();
    return Analysis(path, dur, (r['integrated_loudness_lufs'] as num?)?.toDouble(), scenes, segs('silences'),
        segs('sound_segments'));
  }
}

/// Inicia e espera a análise (até ~10 min). [onProgress] recebe 0–100 e a mensagem.
Future<Analysis> analyzeMedia(AppState app, String path,
    {double? sceneThreshold, void Function(int, String)? onProgress}) async {
  final mcp = app.requireMcp();
  final start = await mcp.call('vb_analyze_start', {
    'path': path,
    if (sceneThreshold != null) 'scene_threshold': sceneThreshold,
  });
  final id = start['job_id'] as String?;
  if (id == null) throw Exception(start.text);
  for (var i = 0; i < 200; i++) {
    await Future<void>.delayed(const Duration(seconds: 3));
    final s = await mcp.call('vb_job_status', {'job_id': id});
    final status = s['status'];
    onProgress?.call((s['progress_percent'] as num?)?.toInt() ?? 0, '${s['message'] ?? status}');
    if (status == 'concluido') {
      return Analysis.fromResult(path, Map<String, dynamic>.from(s['result'] as Map));
    }
    if (status == 'falhou' || status == 'cancelado' || status == 'interrompido') {
      throw Exception('Análise $status: ${s['error'] ?? ''}');
    }
  }
  throw Exception('A análise demorou demais. Veja em Render → Trabalhos recentes.');
}
