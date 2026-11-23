import 'dart:convert';

import 'package:flutter/material.dart';

import '../models/edit_plan.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import 'timeline_tab.dart';

/// Aba 20 · Auto-Edit Suite: status do sistema + ações em lote sobre o projeto.
class AutoSuiteTab extends StatefulWidget {
  const AutoSuiteTab({super.key});
  @override
  State<AutoSuiteTab> createState() => _AutoSuiteTabState();
}

class _AutoSuiteTabState extends State<AutoSuiteTab> {
  String? _caps;

  void _preset(AppState app, String name) {
    final o = app.plan.output;
    switch (name) {
      case 'Reels / TikTok / Shorts':
        o.aspect = '9:16';
        o.height = 1080;
        o.fps = 30;
        o.fit = 'blur';
        o.loudness = -14;
        o.fadeOut = 0.8;
      case 'YouTube':
        o.aspect = '16:9';
        o.height = 1080;
        o.fps = 30;
        o.fit = 'blur';
        o.loudness = -14;
        o.fadeOut = 1.0;
      case 'Feed 4:5':
        o.aspect = '4:5';
        o.height = 1080;
        o.fps = 30;
        o.fit = 'crop';
        o.loudness = -14;
      case 'Podcast / fala':
        o.loudness = -16;
    }
    app.touch();
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Formato "$name" aplicado.')));
  }

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final clips = app.plan.clips;
    return ListView(children: [
      Section(title: 'Status', children: [
        _status('Servidor do Video Builder', app.serverLoggedIn, app.serverUrl),
        _status('Nextcloud', app.nextcloud != null, app.nextcloud?.cred.user ?? app.nextcloudUrl),
        OutlinedButton.icon(
          icon: const Icon(Icons.list_alt),
          label: const Text('Ver capacidades do servidor'),
          onPressed: !app.serverLoggedIn
              ? null
              : () async {
                  final r = await runWithFeedback(context, () => app.requireMcp().call('vb_capabilities'));
                  if (r != null && mounted) {
                    setState(() => _caps =
                        r.data == null ? r.text : const JsonEncoder.withIndent('  ').convert(r.data));
                  }
                },
        ),
        if (_caps != null) SelectableText(_caps!, style: const TextStyle(fontSize: 11)),
      ]),
      Section(title: 'Formato da rede (um toque)', children: [
        Wrap(spacing: 8, runSpacing: 8, children: [
          for (final n in ['Reels / TikTok / Shorts', 'YouTube', 'Feed 4:5', 'Podcast / fala'])
            ActionChip(label: Text(n), onPressed: () => _preset(app, n)),
        ]),
      ]),
      Section(title: 'Ações em lote', children: [
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.content_cut),
          title: const Text('Tirar o tremido das pontas'),
          subtitle: const Text('Corta 0,4 s do início e do fim de cada vídeo de celular'),
          onTap: clips.isEmpty
              ? null
              : () {
                  var n = 0;
                  for (final c in clips.where((c) => !c.isImage)) {
                    final len = c.length;
                    if (len == null || len < 1.5) continue;
                    c.start = double.parse((c.start + 0.4).toStringAsFixed(2));
                    final end = c.end ?? c.sourceDuration;
                    if (end != null) c.end = double.parse((end - 0.4).toStringAsFixed(2));
                    n++;
                  }
                  app.touch();
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                      content: Text(n == 0
                          ? 'Nenhum clipe ajustado (leia as durações na Timeline primeiro).'
                          : '$n clipes ajustados.')));
                },
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.compare),
          title: const Text('Fusão suave em todos os cortes (0,4 s)'),
          onTap: clips.length < 2
              ? null
              : () {
                  for (var i = 1; i < clips.length; i++) {
                    clips[i].transition = Transition(type: 'fade', duration: 0.4);
                  }
                  app.touch();
                },
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.photo),
          title: const Text('Fotos com Ken Burns (2,5 s)'),
          onTap: () {
            for (final c in clips.where((c) => c.isImage)) {
              c.kenBurns = true;
              c.duration = 2.5;
            }
            app.touch();
          },
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.title),
          title: const Text('Texto de gancho nos primeiros 2,5 s'),
          onTap: () {
            final t = TextOverlay(text: 'Escreva o gancho', start: 0.2, end: 2.7, position: 'top', size: 'large');
            app.plan.texts.insert(0, t);
            app.touch();
            editText(context, t);
          },
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.volume_off),
          title: const Text('Silenciar o áudio dos clipes (vídeo só com música)'),
          onTap: () {
            for (final c in clips) {
              c.volume = 0;
            }
            app.plan.music?.ducking = false;
            app.plan.music?.volume = 0.8;
            app.touch();
          },
        ),
      ]),
    ]);
  }

  Widget _status(String label, bool ok, String detail) => ListTile(
        contentPadding: EdgeInsets.zero,
        leading: Icon(ok ? Icons.check_circle : Icons.error_outline, color: ok ? Colors.green : Colors.orange),
        title: Text(label),
        subtitle: Text(detail),
      );
}
