import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/edit_plan.dart';
import '../services/claude_api.dart';
import '../services/secure_store.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import 'timeline_tab.dart';

/// Aba 6 · IA: mesmos botões do desktop (ClaudeEngine), com a chave do próprio usuário.
class IaTab extends StatefulWidget {
  const IaTab({super.key});
  @override
  State<IaTab> createState() => _IaTabState();
}

const _system = 'Você é um editor de vídeo e roteirista brasileiro experiente. Responda em português do Brasil, '
    'direto ao ponto, pronto para usar.';

final Map<String, String> _prompts = {
  'Roteiro': 'Escreva um roteiro de vídeo curto (30 a 60 s) sobre o tema abaixo: gancho nos 3 primeiros segundos, '
      'cenas numeradas com a duração de cada uma, texto na tela e fala.',
  'Títulos': 'Sugira 10 títulos chamativos (até 60 caracteres) para um vídeo sobre:',
  'Descrição YouTube': 'Escreva uma descrição otimizada para YouTube (SEO), com resumo, tópicos e chamada para ação, '
      'para um vídeo sobre:',
  'Capítulos': 'Proponha capítulos no formato 00:00 Título para um vídeo sobre:',
  'Hashtags': 'Liste 20 hashtags relevantes (mistura de amplas e de nicho) para um vídeo sobre:',
  'Melhorar texto': 'Reescreva o texto abaixo para ficar mais claro, curto e envolvente, mantendo o sentido:',
  'Gancho para a tela': 'Escreva 5 opções de texto de gancho para os primeiros 3 segundos do vídeo, com no máximo '
      '6 palavras cada, uma por linha, sem numeração e sem aspas, sobre:',
};

class _IaTabState extends State<IaTab> {
  final _theme = TextEditingController();
  String _result = '';
  bool _busy = false;

  @override
  void dispose() {
    _theme.dispose();
    super.dispose();
  }

  Future<void> _run(String key) async {
    final app = AppScope.read(context);
    final apiKey = await app.secure.read(SecureStore.claudeKey);
    if (!mounted) return;
    if (apiKey == null || apiKey.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Cadastre a chave da API do Claude em Configurações.')));
      return;
    }
    if (_theme.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Escreva o tema ou o texto.')));
      return;
    }
    final model = await app.secure.read(SecureStore.claudeModel);
    if (!mounted) return;
    setState(() => _busy = true);
    final r = await runWithFeedback(
        context, () => ClaudeApi(apiKey, model: model).generate('${_prompts[key]}\n\n${_theme.text.trim()}', system: _system));
    if (mounted) {
      setState(() {
        _busy = false;
        if (r != null) _result = r;
      });
    }
  }

  void _useAsText() {
    final app = AppScope.read(context);
    final first = _result.split('\n').map((l) => l.trim()).firstWhere((l) => l.isNotEmpty, orElse: () => '');
    if (first.isEmpty) return;
    final t = TextOverlay(text: first.length > 200 ? first.substring(0, 200) : first, start: 0.2, end: 2.7,
        position: 'top', size: 'large');
    app.plan.texts.add(t);
    app.touch();
    editText(context, t);
  }

  @override
  Widget build(BuildContext context) {
    return ListView(children: [
      Section(title: 'Assistente (Claude)', children: [
        TextField(
          controller: _theme,
          minLines: 2,
          maxLines: 6,
          decoration: const InputDecoration(labelText: 'Tema ou texto', border: OutlineInputBorder()),
        ),
        const SizedBox(height: 8),
        Wrap(spacing: 8, runSpacing: 8, children: [
          for (final k in _prompts.keys) FilledButton.tonal(onPressed: _busy ? null : () => _run(k), child: Text(k)),
        ]),
        if (_busy) const Padding(padding: EdgeInsets.only(top: 12), child: LinearProgressIndicator()),
      ]),
      if (_result.isNotEmpty)
        Section(title: 'Resultado', children: [
          SelectableText(_result),
          const SizedBox(height: 8),
          Wrap(spacing: 8, children: [
            OutlinedButton.icon(
              icon: const Icon(Icons.copy),
              label: const Text('Copiar'),
              onPressed: () {
                Clipboard.setData(ClipboardData(text: _result));
                ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Copiado.')));
              },
            ),
            OutlinedButton.icon(
                icon: const Icon(Icons.title), label: const Text('Usar 1ª linha como texto na tela'), onPressed: _useAsText),
          ]),
        ]),
    ]);
  }
}
