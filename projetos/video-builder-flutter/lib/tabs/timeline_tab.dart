import 'package:flutter/material.dart';

import '../models/edit_plan.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Aba 3 · Timeline: clipes (ordem, corte, velocidade, volume, transição) e textos na tela.
class TimelineTab extends StatelessWidget {
  const TimelineTab({super.key});

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final plan = app.plan;
    final tl = computeTimeline(plan);
    return ListView(padding: const EdgeInsets.only(bottom: 24), children: [
      Section(
        title: 'Clipes (${plan.clips.length}) · ${fmtSeconds(tl.total)}',
        trailing: IconButton(
          tooltip: 'Adicionar do Nextcloud',
          icon: const Icon(Icons.add),
          onPressed: () async {
            final p = await pickNextcloudFile(context, filter: {...kVideoExt, ...kImageExt}, title: 'Adicionar clipe');
            if (p != null) {
              app.addMedia(p);
              final c = app.plan.clips.last;
              if (!c.isImage && app.serverLoggedIn) app.probeClip(c).catchError((_) {});
            }
          },
        ),
        children: [
          if (plan.clips.isEmpty) const Text('Toque em + ou vá na aba Mídia para adicionar vídeos e fotos.'),
          ReorderableListView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            buildDefaultDragHandles: false,
            itemCount: plan.clips.length,
            onReorderItem: (from, to) {
              final c = plan.clips.removeAt(from);
              plan.clips.insert(to, c);
              app.touch();
            },
            itemBuilder: (context, i) {
              final c = plan.clips[i];
              final start = tl.starts.length > i ? tl.starts[i] : null;
              return ListTile(
                key: ObjectKey(c),
                contentPadding: EdgeInsets.zero,
                leading: ReorderableDragStartListener(
                  index: i,
                  child: CircleAvatar(child: Text('${i + 1}')),
                ),
                title: Text(baseName(c.source), maxLines: 1, overflow: TextOverflow.ellipsis),
                subtitle: Text(_summary(c, start)),
                trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                  if (c.transition != null) const Icon(Icons.compare, size: 18),
                  IconButton(
                      icon: const Icon(Icons.delete_outline),
                      onPressed: () {
                        plan.clips.removeAt(i);
                        app.touch();
                      }),
                ]),
                onTap: () => _editClip(context, c, i),
              );
            },
          ),
          for (final p in tl.problems)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text('⚠️ $p', style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ),
        ],
      ),
      Section(
        title: 'Textos na tela (${plan.texts.length})',
        trailing: IconButton(
          icon: const Icon(Icons.add),
          tooltip: 'Novo texto',
          onPressed: () {
            final t = TextOverlay(text: 'Seu texto', start: 0, end: 2.5);
            plan.texts.add(t);
            app.touch();
            editText(context, t);
          },
        ),
        children: [
          if (plan.texts.isEmpty) const Text('Os tempos são da linha do tempo FINAL (já com cortes e transições).'),
          for (var i = 0; i < plan.texts.length; i++)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.title),
              title: Text(plan.texts[i].text, maxLines: 1, overflow: TextOverflow.ellipsis),
              subtitle: Text('${plan.texts[i].start.toStringAsFixed(1)}–${plan.texts[i].end.toStringAsFixed(1)} s · '
                  '${plan.texts[i].position} · ${plan.texts[i].font}'),
              trailing: IconButton(
                  icon: const Icon(Icons.delete_outline),
                  onPressed: () {
                    plan.texts.removeAt(i);
                    app.touch();
                  }),
              onTap: () => editText(context, plan.texts[i]),
            ),
        ],
      ),
    ]);
  }

  String _summary(Clip c, double? start) {
    final at = start == null ? '' : 'em ${start.toStringAsFixed(1)} s · ';
    if (c.isImage) return '${at}foto ${(c.duration ?? 3).toStringAsFixed(1)} s${c.kenBurns ? ' · Ken Burns' : ''}';
    final len = c.length;
    return '$at${c.start.toStringAsFixed(1)}–${c.end?.toStringAsFixed(1) ?? 'fim'} s'
        '${c.speed != 1 ? ' · ${c.speed}x' : ''}${c.volume == 0 ? ' · mudo' : ''}'
        ' · ${len == null ? 'duração ? (toque para ler)' : fmtSeconds(len)}';
  }

  void _editClip(BuildContext context, Clip c, int index) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => ClipEditor(clip: c, index: index),
    );
  }
}

class ClipEditor extends StatefulWidget {
  final Clip clip;
  final int index;
  const ClipEditor({super.key, required this.clip, required this.index});
  @override
  State<ClipEditor> createState() => _ClipEditorState();
}

class _ClipEditorState extends State<ClipEditor> {
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final c = widget.clip;
    void changed() {
      setState(() {});
      app.touch();
    }

    return Padding(
      padding: EdgeInsets.fromLTRB(16, 0, 16, MediaQuery.of(context).viewInsets.bottom + 16),
      child: SingleChildScrollView(
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Clipe ${widget.index + 1}: ${baseName(c.source)}', style: Theme.of(context).textTheme.titleMedium),
          if (!c.isImage) ...[
            Text(c.sourceDuration == null
                ? 'Duração do arquivo: desconhecida'
                : 'Duração do arquivo: ${fmtSeconds(c.sourceDuration)}'),
            if (c.sourceDuration == null)
              TextButton.icon(
                icon: const Icon(Icons.refresh),
                label: const Text('Ler duração no servidor'),
                onPressed: () => runWithFeedback(context, () => app.probeClip(c)).then((_) => setState(() {})),
              ),
            Row(children: [
              Expanded(child: NumberField(label: 'Início (s)', value: c.start, onChanged: (v) {
                c.start = v ?? 0;
                changed();
              })),
              const SizedBox(width: 12),
              Expanded(child: NumberField(label: 'Fim (s)', hint: 'vazio = até o fim', value: c.end, onChanged: (v) {
                c.end = v;
                changed();
              })),
            ]),
            SliderRow(
                label: 'Velocidade',
                value: c.speed,
                min: 0.25,
                max: 4,
                divisions: 15,
                format: (v) => '${v.toStringAsFixed(2)}x',
                onChanged: (v) {
                  c.speed = double.parse(v.toStringAsFixed(2));
                  changed();
                }),
          ] else ...[
            SliderRow(
                label: 'Na tela',
                value: c.duration ?? 3,
                min: 0.5,
                max: 15,
                divisions: 29,
                format: (v) => '${v.toStringAsFixed(1)} s',
                onChanged: (v) {
                  c.duration = double.parse(v.toStringAsFixed(1));
                  changed();
                }),
            SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Ken Burns (aproximação lenta)'),
                value: c.kenBurns,
                onChanged: (v) {
                  c.kenBurns = v;
                  changed();
                }),
          ],
          SliderRow(
              label: 'Volume',
              value: c.volume,
              min: 0,
              max: 2,
              divisions: 20,
              format: (v) => v == 0 ? 'mudo' : '${(v * 100).round()}%',
              onChanged: (v) {
                c.volume = double.parse(v.toStringAsFixed(2));
                changed();
              }),
          if (widget.index > 0) ...[
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Transição antes deste clipe'),
              subtitle: const Text('Desligado = corte seco (padrão profissional)'),
              value: c.transition != null,
              onChanged: (v) {
                c.transition = v ? Transition() : null;
                changed();
              },
            ),
            if (c.transition != null) ...[
              Choice<String>(
                  label: 'Efeito',
                  value: c.transition!.type,
                  options: kTransitions,
                  onChanged: (v) {
                    c.transition!.type = v;
                    changed();
                  }),
              SliderRow(
                  label: 'Duração',
                  value: c.transition!.duration,
                  min: 0.1,
                  max: 3,
                  divisions: 29,
                  format: (v) => '${v.toStringAsFixed(1)} s',
                  onChanged: (v) {
                    c.transition!.duration = double.parse(v.toStringAsFixed(1));
                    changed();
                  }),
            ],
          ],
          const SizedBox(height: 8),
          FilledButton(onPressed: () => Navigator.pop(context), child: const Text('Pronto')),
        ]),
      ),
    );
  }
}

/// Editor de texto na tela (usado também pela aba IA e pela Auto-Edit Suite).
Future<void> editText(BuildContext context, TextOverlay t) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => _TextEditor(t: t),
  );
}

class _TextEditor extends StatefulWidget {
  final TextOverlay t;
  const _TextEditor({required this.t});
  @override
  State<_TextEditor> createState() => _TextEditorState();
}

class _TextEditorState extends State<_TextEditor> {
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final t = widget.t;
    void changed() {
      setState(() {});
      app.touch();
    }

    return Padding(
      padding: EdgeInsets.fromLTRB(16, 0, 16, MediaQuery.of(context).viewInsets.bottom + 16),
      child: SingleChildScrollView(
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          TextFormField(
            initialValue: t.text,
            maxLength: 200,
            maxLines: 2,
            decoration: const InputDecoration(labelText: 'Texto (até ~6 palavras por linha)'),
            onChanged: (v) {
              t.text = v.trim().isEmpty ? ' ' : v;
              changed();
            },
          ),
          Row(children: [
            Expanded(child: NumberField(label: 'Início (s)', value: t.start, onChanged: (v) {
              t.start = v ?? 0;
              changed();
            })),
            const SizedBox(width: 12),
            Expanded(child: NumberField(label: 'Fim (s)', value: t.end, onChanged: (v) {
              t.end = v ?? t.start + 2;
              changed();
            })),
          ]),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: Choice<String>(label: 'Posição', value: t.position, options: kPositions,
                display: (p) => {'top': 'Topo', 'center': 'Centro', 'bottom': 'Embaixo'}[p]!, onChanged: (v) {
              t.position = v;
              changed();
            })),
            const SizedBox(width: 12),
            Expanded(child: Choice<String>(label: 'Tamanho', value: t.size, options: kSizes,
                display: (p) => {'small': 'Pequeno', 'medium': 'Médio', 'large': 'Grande'}[p]!, onChanged: (v) {
              t.size = v;
              changed();
            })),
          ]),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: Choice<String>(label: 'Estilo', value: t.style, options: kStyles,
                display: (p) => {'plain': 'Contorno', 'box': 'Tarja', 'shadow': 'Sombra'}[p]!, onChanged: (v) {
              t.style = v;
              changed();
            })),
            const SizedBox(width: 12),
            Expanded(child: Choice<String>(label: 'Fonte', value: t.font, options: kFonts, onChanged: (v) {
              t.font = v;
              changed();
            })),
          ]),
          const SizedBox(height: 8),
          Wrap(spacing: 8, children: [
            for (final hex in ['#FFFFFF', '#FACC15', '#22D3EE', '#F97316', '#000000'])
              ChoiceChip(
                label: Text(hex),
                selected: t.color.toUpperCase() == hex,
                avatar: CircleAvatar(backgroundColor: Color(int.parse('FF${hex.substring(1)}', radix: 16))),
                onSelected: (_) {
                  t.color = hex;
                  changed();
                },
              ),
          ]),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Surgir e sumir suavemente'),
            value: t.animation == 'fade',
            onChanged: (v) {
              t.animation = v ? 'fade' : 'none';
              changed();
            },
          ),
          FilledButton(onPressed: () => Navigator.pop(context), child: const Text('Pronto')),
        ]),
      ),
    );
  }
}
