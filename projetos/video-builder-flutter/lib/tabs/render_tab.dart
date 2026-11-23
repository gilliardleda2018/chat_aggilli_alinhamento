import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/edit_plan.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Aba 7 · Render: envia o roteiro ao servidor e acompanha os trabalhos.
class RenderTab extends StatefulWidget {
  const RenderTab({super.key});
  @override
  State<RenderTab> createState() => _RenderTabState();
}

class _RenderTabState extends State<RenderTab> {
  Map<String, dynamic>? _job;
  List<Map<String, dynamic>> _jobs = [];
  Map<String, dynamic>? _account;
  Timer? _timer;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refreshAll());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _refreshAll() async {
    final app = AppScope.read(context);
    if (!app.serverLoggedIn) return;
    await runWithFeedback(context, () async {
      final mcp = app.requireMcp();
      final acc = await mcp.call('vb_account');
      final list = await mcp.call('vb_jobs_list', {'limit': 10});
      _account = acc.data;
      _jobs = ((list['jobs'] as List?) ?? const []).map((e) => Map<String, dynamic>.from(e as Map)).toList();
      if (app.lastJobId != null) await _poll(app.lastJobId!);
    });
    if (mounted) setState(() {});
  }

  Future<void> _poll(String jobId) async {
    final app = AppScope.read(context);
    final r = await app.requireMcp().call('vb_job_status', {'job_id': jobId});
    _job = r.data;
    final status = _job?['status'];
    _timer?.cancel();
    if (status == 'na_fila' || status == 'rodando') {
      _timer = Timer(const Duration(seconds: 5), () async {
        if (!mounted) return;
        try {
          await _poll(jobId);
        } catch (_) {}
        if (mounted) setState(() {});
      });
    }
  }

  Future<void> _start() async {
    final app = AppScope.read(context);
    setState(() => _busy = true);
    await runWithFeedback(context, () async {
      final r = await app.requireMcp().call('vb_render_start', {'plan': app.plan.toJson()});
      final id = r['job_id'] as String?;
      if (id == null) throw Exception(r.text);
      app.lastJobId = id;
      await app.save();
      await _poll(id);
    }, success: 'Render enviado ao servidor.');
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final tl = computeTimeline(app.plan);
    final o = app.plan.output;
    return RefreshIndicator(
      onRefresh: _refreshAll,
      child: ListView(children: [
        if (!app.serverLoggedIn)
          const Section(title: 'Servidor', children: [Text('Entre no servidor em Configurações para renderizar.')]),
        Section(title: 'Resumo do roteiro', children: [
          Text('${o.name}.mp4 · ${o.aspect} · ${o.height}p · ${o.fps} fps · encaixe ${o.fit}'),
          Text('${app.plan.clips.length} clipes · ${app.plan.texts.length} textos · duração ${fmtSeconds(tl.total)}'),
          Text('Trilha: ${app.plan.music == null ? 'nenhuma' : baseName(app.plan.music!.source)} · '
              'Legenda: ${app.plan.subtitles == null ? 'nenhuma' : baseName(app.plan.subtitles!.source)}'),
          for (final p in tl.problems)
            Text('⚠️ $p', style: TextStyle(color: Theme.of(context).colorScheme.error)),
          const SizedBox(height: 8),
          FilledButton.icon(
            icon: const Icon(Icons.rocket_launch),
            label: const Text('Renderizar no servidor'),
            onPressed: _busy || app.plan.clips.isEmpty || !app.serverLoggedIn ? null : _start,
          ),
          TextButton(
            onPressed: () => showDialog<void>(
              context: context,
              builder: (c) => AlertDialog(
                title: const Text('Roteiro (JSON)'),
                content: SingleChildScrollView(
                    child: SelectableText(const JsonEncoder.withIndent('  ').convert(app.plan.toJson()),
                        style: const TextStyle(fontSize: 11))),
                actions: [TextButton(onPressed: () => Navigator.pop(c), child: const Text('Fechar'))],
              ),
            ),
            child: const Text('Ver roteiro enviado'),
          ),
        ]),
        if (_job != null) _jobCard(_job!, current: true),
        if (_account != null)
          Section(title: 'Plano', children: [
            Text(_accountText(_account!)),
            if (_account!['link'] is String)
              TextButton(
                  onPressed: () => launchUrl(Uri.parse(_account!['link'] as String), mode: LaunchMode.externalApplication),
                  child: const Text('Gerenciar assinatura')),
          ]),
        Section(
          title: 'Trabalhos recentes',
          trailing: IconButton(icon: const Icon(Icons.refresh), onPressed: _refreshAll),
          children: [
            if (_jobs.isEmpty) const Text('Nenhum trabalho ainda.'),
            for (final j in _jobs)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Icon(_statusIcon(j['status'] as String?)),
                title: Text('${j['kind'] ?? ''} · ${_statusLabel(j['status'] as String?)}'),
                subtitle: Text('${j['summary'] ?? j['message'] ?? ''}', maxLines: 2, overflow: TextOverflow.ellipsis),
                onTap: () async {
                  await runWithFeedback(context, () => _poll(j['job_id'] as String));
                  if (mounted) setState(() {});
                },
              ),
          ],
        ),
      ]),
    );
  }

  Widget _jobCard(Map<String, dynamic> j, {bool current = false}) {
    final status = j['status'] as String?;
    final pct = (j['progress_percent'] as num?)?.toInt() ?? 0;
    final result = j['result'] is Map ? Map<String, dynamic>.from(j['result'] as Map) : null;
    final link = result?['web_link'] as String?;
    return Section(title: 'Trabalho ${j['job_id']}', children: [
      Text('${_statusLabel(status)} · $pct%'),
      if (status == 'rodando' || status == 'na_fila') ...[
        const SizedBox(height: 6),
        LinearProgressIndicator(value: pct / 100),
        if (j['message'] != null) Text('${j['message']}'),
        Align(
          alignment: Alignment.centerRight,
          child: TextButton(
            onPressed: () async {
              await runWithFeedback(context,
                  () => AppScope.read(context).requireMcp().call('vb_job_cancel', {'job_id': j['job_id']}),
                  success: 'Cancelamento pedido.');
              await _poll(j['job_id'] as String);
              if (mounted) setState(() {});
            },
            child: const Text('Cancelar'),
          ),
        ),
      ],
      if (j['error'] != null)
        Text('Erro: ${j['error']}', style: TextStyle(color: Theme.of(context).colorScheme.error)),
      if (result != null) ...[
        if (result['path'] != null) Text('Arquivo: ${result['path']}'),
        if (result['duration'] != null) Text('Duração: ${result['duration']} s'),
      ],
      if (link != null)
        FilledButton.icon(
            icon: const Icon(Icons.play_circle),
            label: const Text('Abrir o vídeo no Nextcloud'),
            onPressed: () => launchUrl(Uri.parse(link), mode: LaunchMode.externalApplication)),
    ]);
  }
}

String _accountText(Map<String, dynamic> a) {
  const labels = {
    'plan': 'Plano',
    'status': 'Situação',
    'minutes_used': 'Minutos usados',
    'minutes_left': 'Restantes',
    'minutes_included': 'Incluídos',
    'period_end': 'Renova em',
    'note': 'Obs.',
  };
  final parts = <String>[];
  labels.forEach((k, label) {
    if (a[k] != null) parts.add('$label: ${a[k]}');
  });
  return parts.isEmpty ? a.toString() : parts.join(' · ');
}

String _statusLabel(String? s) => switch (s) {
      'na_fila' => 'Na fila',
      'rodando' => 'Renderizando',
      'concluido' => 'Concluído',
      'falhou' => 'Falhou',
      'cancelado' => 'Cancelado',
      'interrompido' => 'Interrompido',
      _ => s ?? '?',
    };

IconData _statusIcon(String? s) => switch (s) {
      'concluido' => Icons.check_circle,
      'falhou' => Icons.error,
      'rodando' || 'na_fila' => Icons.timelapse,
      _ => Icons.circle_outlined,
    };
