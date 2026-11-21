import 'package:flutter/material.dart';

import '../models/edit_plan.dart';
import '../services/nextcloud.dart';
import '../state/app_state.dart';

/// Roda uma ação assíncrona mostrando erro (e, opcionalmente, sucesso) num aviso na parte de baixo.
Future<T?> runWithFeedback<T>(BuildContext context, Future<T> Function() action, {String? success}) async {
  final messenger = ScaffoldMessenger.of(context);
  try {
    final r = await action();
    if (success != null) messenger.showSnackBar(SnackBar(content: Text(success)));
    return r;
  } catch (e) {
    messenger.showSnackBar(SnackBar(content: Text('$e'), duration: const Duration(seconds: 6)));
    return null;
  }
}

class Section extends StatelessWidget {
  final String title;
  final List<Widget> children;
  final Widget? trailing;
  const Section({super.key, required this.title, required this.children, this.trailing});

  @override
  Widget build(BuildContext context) => Card(
        margin: const EdgeInsets.fromLTRB(12, 8, 12, 4),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Row(children: [
              Expanded(child: Text(title, style: Theme.of(context).textTheme.titleMedium)),
              if (trailing != null) trailing!,
            ]),
            const SizedBox(height: 8),
            ...children,
          ]),
        ),
      );
}

/// Controle deslizante com rótulo e valor.
class SliderRow extends StatelessWidget {
  final String label;
  final double value, min, max;
  final int? divisions;
  final String Function(double)? format;
  final ValueChanged<double> onChanged;
  const SliderRow({
    super.key,
    required this.label,
    required this.value,
    required this.min,
    required this.max,
    required this.onChanged,
    this.divisions,
    this.format,
  });

  @override
  Widget build(BuildContext context) => Row(children: [
        SizedBox(width: 110, child: Text(label)),
        Expanded(
          child: Slider(
            value: value.clamp(min, max).toDouble(),
            min: min,
            max: max,
            divisions: divisions,
            label: (format ?? (v) => v.toStringAsFixed(2))(value),
            onChanged: onChanged,
          ),
        ),
        SizedBox(width: 56, child: Text((format ?? (v) => v.toStringAsFixed(2))(value), textAlign: TextAlign.end)),
      ]);
}

/// Campo numérico (segundos etc.). Vazio = null.
class NumberField extends StatefulWidget {
  final String label;
  final double? value;
  final ValueChanged<double?> onChanged;
  final String? hint;
  const NumberField({super.key, required this.label, required this.value, required this.onChanged, this.hint});
  @override
  State<NumberField> createState() => _NumberFieldState();
}

class _NumberFieldState extends State<NumberField> {
  late final TextEditingController _c = TextEditingController(text: _fmt(widget.value));
  String _fmt(double? v) => v == null ? '' : (v == v.roundToDouble() ? v.toInt().toString() : v.toString());

  @override
  void didUpdateWidget(NumberField old) {
    super.didUpdateWidget(old);
    final parsed = double.tryParse(_c.text.replaceAll(',', '.'));
    if (parsed != widget.value) _c.text = _fmt(widget.value);
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => TextField(
        controller: _c,
        keyboardType: const TextInputType.numberWithOptions(decimal: true),
        decoration: InputDecoration(labelText: widget.label, hintText: widget.hint, isDense: true),
        onChanged: (t) => widget.onChanged(t.trim().isEmpty ? null : double.tryParse(t.replaceAll(',', '.'))),
      );
}

/// Seletor simples a partir de uma lista de opções.
class Choice<T> extends StatelessWidget {
  final String label;
  final T value;
  final List<T> options;
  final String Function(T)? display;
  final ValueChanged<T> onChanged;
  const Choice({super.key, required this.label, required this.value, required this.options, required this.onChanged,
      this.display});

  @override
  Widget build(BuildContext context) => DropdownButtonFormField<T>(
        key: ValueKey<Object?>('$label:$value'),
        initialValue: options.contains(value) ? value : options.first,
        isExpanded: true,
        decoration: InputDecoration(labelText: label, isDense: true),
        items: [
          for (final o in options) DropdownMenuItem<T>(value: o, child: Text(display?.call(o) ?? '$o')),
        ],
        onChanged: (v) {
          if (v != null) onChanged(v);
        },
      );
}

/// Aviso das abas que dependem de uma ferramenta que o servidor ainda não tem (MAPA-DAS-ABAS.md).
class ServerPendingCard extends StatelessWidget {
  final String feature;
  final String needs;
  final String? meanwhile;
  const ServerPendingCard({super.key, required this.feature, required this.needs, this.meanwhile});

  @override
  Widget build(BuildContext context) => Card(
        color: Theme.of(context).colorScheme.tertiaryContainer,
        margin: const EdgeInsets.fromLTRB(12, 8, 12, 4),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              const Icon(Icons.hourglass_top),
              const SizedBox(width: 8),
              Expanded(child: Text('$feature: aguardando o servidor', style: Theme.of(context).textTheme.titleSmall)),
            ]),
            const SizedBox(height: 8),
            Text('O processamento acontece no servidor do Video Builder, que ainda não tem esta ferramenta. '
                'Necessário: $needs'),
            if (meanwhile != null) ...[const SizedBox(height: 8), Text('Enquanto isso: $meanwhile')],
          ]),
        ),
      );
}

/// Navegador do Nextcloud para escolher um arquivo. [filter] limita pelas extensões (vazio = todos).
Future<String?> pickNextcloudFile(BuildContext context, {Set<String> filter = const {}, String title = 'Escolher'}) {
  return Navigator.of(context).push<String>(MaterialPageRoute(
    builder: (_) => NextcloudBrowser(filter: filter, title: title, pickMode: true),
  ));
}

class NextcloudBrowser extends StatefulWidget {
  final Set<String> filter;
  final String title;
  final bool pickMode;
  final void Function(NcEntry)? onFileTap;
  final Widget Function(NcEntry)? trailingFor;
  const NextcloudBrowser(
      {super.key, this.filter = const {}, this.title = 'Nextcloud', this.pickMode = false, this.onFileTap,
      this.trailingFor});

  @override
  State<NextcloudBrowser> createState() => _NextcloudBrowserState();
}

class _NextcloudBrowserState extends State<NextcloudBrowser> {
  String? _folder;
  Future<List<NcEntry>>? _future;

  void _load(AppState app, String folder) {
    _folder = folder;
    _future = app.requireNextcloud().list(folder);
    app.rememberFolder(folder);
  }

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    if (app.nextcloud == null) {
      return _wrap(const Center(
          child: Padding(
              padding: EdgeInsets.all(24),
              child: Text('Conecte o Nextcloud em Configurações (ícone de engrenagem).', textAlign: TextAlign.center))));
    }
    if (_future == null) _load(app, app.ncFolder);
    final parts = _folder!.split('/').where((p) => p.isNotEmpty).toList();
    final body = Column(children: [
      ListTile(
        dense: true,
        leading: const Icon(Icons.folder_open),
        title: Text(parts.isEmpty ? 'Raiz' : parts.join(' / ')),
        trailing: parts.isEmpty
            ? null
            : IconButton(
                icon: const Icon(Icons.arrow_upward),
                tooltip: 'Pasta acima',
                onPressed: () => setState(() => _load(app, parts.sublist(0, parts.length - 1).join('/'))),
              ),
      ),
      const Divider(height: 1),
      Expanded(
        child: FutureBuilder<List<NcEntry>>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
            if (snap.hasError) {
              return Center(
                  child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(mainAxisSize: MainAxisSize.min, children: [
                        Text('${snap.error}', textAlign: TextAlign.center),
                        TextButton(onPressed: () => setState(() => _load(app, '')), child: const Text('Ir para a raiz')),
                      ])));
            }
            final items = snap.data!
                .where((e) => e.isDir || widget.filter.isEmpty || widget.filter.contains(extOf(e.path)))
                .toList();
            if (items.isEmpty) return const Center(child: Text('Pasta vazia (ou sem arquivos deste tipo).'));
            return RefreshIndicator(
              onRefresh: () async => setState(() => _load(app, _folder!)),
              child: ListView.builder(
                itemCount: items.length,
                itemBuilder: (_, i) {
                  final e = items[i];
                  return ListTile(
                    leading: Icon(_iconFor(e)),
                    title: Text(e.name),
                    subtitle: e.isDir ? null : Text('${(e.size / 1048576).toStringAsFixed(1)} MB'),
                    trailing: e.isDir ? const Icon(Icons.chevron_right) : widget.trailingFor?.call(e),
                    onTap: () {
                      if (e.isDir) {
                        setState(() => _load(app, e.path));
                      } else if (widget.pickMode) {
                        Navigator.of(context).pop(e.path);
                      } else {
                        widget.onFileTap?.call(e);
                      }
                    },
                  );
                },
              ),
            );
          },
        ),
      ),
    ]);
    return _wrap(body);
  }

  Widget _wrap(Widget body) => widget.pickMode ? Scaffold(appBar: AppBar(title: Text(widget.title)), body: body) : body;
}

IconData _iconFor(NcEntry e) {
  if (e.isDir) return Icons.folder;
  final x = extOf(e.path);
  if (kVideoExt.contains(x)) return Icons.movie;
  if (kImageExt.contains(x)) return Icons.image;
  if (kAudioExt.contains(x)) return Icons.music_note;
  if (kSubtitleExt.contains(x)) return Icons.subtitles;
  return Icons.insert_drive_file;
}
