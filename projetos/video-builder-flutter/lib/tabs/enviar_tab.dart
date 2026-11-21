import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/edit_plan.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Aba 17 · Enviar / Importar (substitui a aba Download do desktop; ADR-F04).
/// Envia arquivos do celular para o Nextcloud. Não baixa de YouTube nem de outras plataformas.
class EnviarTab extends StatefulWidget {
  const EnviarTab({super.key});
  @override
  State<EnviarTab> createState() => _EnviarTabState();
}

class _EnviarTabState extends State<EnviarTab> {
  final _musicFolder = TextEditingController(text: 'Musicas');
  final _otherFolder = TextEditingController(text: 'Video Builder/Envios');
  bool _addToProject = true;
  String? _status;
  double? _progress;
  final List<String> _sent = [];

  @override
  void dispose() {
    _musicFolder.dispose();
    _otherFolder.dispose();
    super.dispose();
  }

  Future<void> _pickAndSend() async {
    final app = AppScope.read(context);
    final picked = await FilePicker.platform.pickFiles(allowMultiple: true, type: FileType.any);
    if (picked == null || !mounted) return;
    await runWithFeedback(context, () async {
      final nc = app.requireNextcloud();
      for (final f in picked.files) {
        if (f.path == null) continue;
        final isAudio = kAudioExt.contains(extOf(f.name));
        final folder = (isAudio ? _musicFolder.text : _otherFolder.text).trim();
        setState(() {
          _status = 'Enviando ${f.name}…';
          _progress = 0;
        });
        final path = await nc.upload(folder, f.name, File(f.path!), onProgress: (p) {
          if (mounted) setState(() => _progress = p);
        });
        _sent.insert(0, path);
        if (_addToProject) app.addMedia(path);
      }
    }, success: 'Envio concluído.');
    if (mounted) {
      setState(() {
        _status = null;
        _progress = null;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    return ListView(children: [
      Section(title: 'Enviar do celular para o Nextcloud', children: [
        const Text('Músicas, vídeos, fotos e legendas suas. Nada é sobrescrito: nomes repetidos ganham " (2)".'),
        TextField(controller: _musicFolder, decoration: const InputDecoration(labelText: 'Pasta para áudios')),
        TextField(controller: _otherFolder, decoration: const InputDecoration(labelText: 'Pasta para o resto')),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Já adicionar ao projeto'),
          subtitle: const Text('Áudio vira trilha, legenda vira legenda, vídeo/foto vai para a timeline'),
          value: _addToProject,
          onChanged: (v) => setState(() => _addToProject = v),
        ),
        FilledButton.icon(
          icon: const Icon(Icons.upload),
          label: const Text('Escolher arquivos e enviar'),
          onPressed: _status != null || app.nextcloud == null ? null : _pickAndSend,
        ),
        if (app.nextcloud == null) const Text('Conecte o Nextcloud em Configurações.'),
        if (_status != null) ...[
          const SizedBox(height: 8),
          LinearProgressIndicator(value: _progress),
          Text(_status!),
        ],
        for (final s in _sent) ListTile(dense: true, leading: const Icon(Icons.check), title: Text(s)),
      ]),
      Section(title: 'Músicas liberadas para usar em vídeos', children: [
        const Text('Baixe pelo navegador e depois envie aqui. Confira a licença de cada faixa (algumas pedem crédito).'),
        _link('Biblioteca de Áudio do YouTube (YouTube Studio)', 'https://studio.youtube.com/channel/UC/music'),
        _link('Pixabay Music', 'https://pixabay.com/music/'),
        _link('Free Music Archive', 'https://freemusicarchive.org/'),
      ]),
      const Section(title: 'Por que não baixar do YouTube?', children: [
        Text('Os termos do YouTube não permitem baixar vídeos e músicas fora dos recursos dele, e a maioria das '
            'músicas tem direitos autorais (o vídeo publicado pode ser silenciado ou removido). Um app que faz '
            'isso também é recusado na Google Play. Para músicas famosas, adicione-as pelo próprio Instagram ou '
            'TikTok na hora de postar.'),
      ]),
    ]);
  }

  Widget _link(String label, String url) => ListTile(
        contentPadding: EdgeInsets.zero,
        leading: const Icon(Icons.open_in_new),
        title: Text(label),
        onTap: () => launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication),
      );
}
