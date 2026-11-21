import 'dart:convert';

import 'package:flutter/material.dart';

import '../models/edit_plan.dart';
import '../services/nextcloud.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Aba 2 · Mídia: navega no Nextcloud e adiciona ao projeto; informações e prévia vêm do servidor.
class MidiaTab extends StatelessWidget {
  const MidiaTab({super.key});

  @override
  Widget build(BuildContext context) {
    return NextcloudBrowser(
      onFileTap: (e) => showMediaActions(context, e.path),
      trailingFor: (e) => IconButton(
        icon: const Icon(Icons.add_circle_outline),
        tooltip: 'Adicionar ao projeto',
        onPressed: () => _add(context, e),
      ),
    );
  }

  void _add(BuildContext context, NcEntry e) {
    final app = AppScope.read(context);
    app.addMedia(e.path);
    final x = extOf(e.path);
    final where = kAudioExt.contains(x)
        ? 'como trilha sonora'
        : kSubtitleExt.contains(x)
            ? 'como legenda'
            : 'na timeline (clipe ${app.plan.clips.length})';
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('${e.name} adicionado $where.')));
    final clip = app.plan.clips.isNotEmpty ? app.plan.clips.last : null;
    if (clip != null && clip.source == e.path && !clip.isImage && app.serverLoggedIn) {
      app.probeClip(clip).catchError((_) {});
    }
  }
}

Future<void> showMediaActions(BuildContext context, String path) {
  final x = extOf(path);
  final isVideo = kVideoExt.contains(x);
  return showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    builder: (sheet) => SafeArea(
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        ListTile(title: Text(baseName(path)), subtitle: Text(path)),
        ListTile(
          leading: const Icon(Icons.add),
          title: const Text('Adicionar ao projeto'),
          onTap: () {
            Navigator.pop(sheet);
            AppScope.read(context).addMedia(path);
          },
        ),
        if (isVideo || kAudioExt.contains(x))
          ListTile(
            leading: const Icon(Icons.info_outline),
            title: const Text('Informações (duração, resolução, áudio)'),
            onTap: () {
              Navigator.pop(sheet);
              Navigator.of(context).push(MaterialPageRoute(builder: (_) => MediaInfoScreen(path: path)));
            },
          ),
        if (isVideo)
          ListTile(
            leading: const Icon(Icons.grid_view),
            title: const Text('Prévia (folha de quadros)'),
            onTap: () {
              Navigator.pop(sheet);
              Navigator.of(context).push(MaterialPageRoute(builder: (_) => MediaInfoScreen(path: path, preview: true)));
            },
          ),
      ]),
    ),
  );
}

class MediaInfoScreen extends StatefulWidget {
  final String path;
  final bool preview;
  const MediaInfoScreen({super.key, required this.path, this.preview = false});
  @override
  State<MediaInfoScreen> createState() => _MediaInfoScreenState();
}

class _MediaInfoScreenState extends State<MediaInfoScreen> {
  Future<Widget>? _future;

  Future<Widget> _load() async {
    final mcp = AppScope.read(context).requireMcp();
    if (widget.preview) {
      final r = await mcp.call('vb_media_preview', {'path': widget.path, 'frames': 12});
      return Column(children: [
        for (final img in r.images) InteractiveViewer(child: Image.memory(img)),
        if (r.text.isNotEmpty) Padding(padding: const EdgeInsets.all(12), child: Text(r.text)),
      ]);
    }
    final r = await mcp.call('vb_media_probe', {'path': widget.path});
    final d = r.data ?? {};
    final media = d;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      _row('Duração', media['duration'] is num ? fmtSeconds((media['duration'] as num).toDouble()) : '?'),
      _row('Resolução', '${media['width'] ?? '?'} x ${media['height'] ?? '?'}'),
      _row('Quadros/s', '${media['fps'] ?? '?'}'),
      _row('Tem áudio', media['has_audio'] == true ? 'sim' : 'não'),
      _row('Codecs', '${media['video_codec'] ?? '-'} / ${media['audio_codec'] ?? '-'}'),
      _row('Tamanho', '${media['size_mb'] ?? '?'} MB'),
      const Divider(),
      SelectableText(const JsonEncoder.withIndent('  ').convert(d), style: const TextStyle(fontSize: 11)),
    ]);
  }

  Widget _row(String k, String v) => ListTile(dense: true, title: Text(k), trailing: Text(v));

  @override
  Widget build(BuildContext context) {
    _future ??= _load();
    return Scaffold(
      appBar: AppBar(title: Text(baseName(widget.path))),
      body: FutureBuilder<Widget>(
        future: _future,
        builder: (_, s) {
          if (s.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (s.hasError) return Center(child: Padding(padding: const EdgeInsets.all(24), child: Text('${s.error}')));
          return SingleChildScrollView(padding: const EdgeInsets.all(12), child: s.data);
        },
      ),
    );
  }
}
