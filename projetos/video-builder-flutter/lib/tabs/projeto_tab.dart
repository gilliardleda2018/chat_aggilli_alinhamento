import 'package:flutter/material.dart';

import '../models/edit_plan.dart';
import '../services/project_store.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Aba 1 · Projeto: formato de saída e projetos salvos (equivale ao .vbp do desktop).
class ProjetoTab extends StatefulWidget {
  const ProjetoTab({super.key});
  @override
  State<ProjetoTab> createState() => _ProjetoTabState();
}

class _ProjetoTabState extends State<ProjetoTab> {
  Future<List<SavedProject>>? _list;

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final o = app.plan.output;
    _list ??= app.projects.list();
    return ListView(children: [
      Section(title: 'Projeto aberto', children: [
        TextFormField(
          key: ValueKey('nome-${app.projectId}'),
          initialValue: app.projectName,
          decoration: const InputDecoration(labelText: 'Nome do projeto'),
          onChanged: (v) {
            app.projectName = v;
            app.touch();
          },
        ),
        Wrap(spacing: 8, children: [
          FilledButton.icon(
              icon: const Icon(Icons.save),
              label: const Text('Salvar'),
              onPressed: () async {
                await app.save();
                setState(() => _list = null);
              }),
          OutlinedButton.icon(
              icon: const Icon(Icons.copy),
              label: const Text('Duplicar'),
              onPressed: () async {
                await app.duplicate();
                setState(() => _list = null);
              }),
          OutlinedButton.icon(
              icon: const Icon(Icons.add),
              label: const Text('Novo'),
              onPressed: () {
                app.newProject();
                setState(() => _list = null);
              }),
        ]),
      ]),
      Section(title: 'Saída', children: [
        TextFormField(
          key: ValueKey('arq-${app.projectId}'),
          initialValue: o.name,
          decoration: const InputDecoration(labelText: 'Nome do arquivo (sem .mp4)'),
          onChanged: (v) {
            o.name = v.trim().isEmpty ? 'video' : v.trim();
            app.touch();
          },
        ),
        TextFormField(
          key: ValueKey('pasta-${app.projectId}'),
          initialValue: o.folder ?? '',
          decoration: const InputDecoration(
              labelText: 'Pasta no Nextcloud', hintText: 'Vazio = pasta padrão "Video Builder/Renders"'),
          onChanged: (v) {
            o.folder = v.trim().isEmpty ? null : v.trim();
            app.touch();
          },
        ),
        const SizedBox(height: 8),
        Row(children: [
          Expanded(
              child: Choice<String>(
                  label: 'Formato',
                  value: o.aspect,
                  options: kAspects,
                  display: _aspectLabel,
                  onChanged: (v) {
                    o.aspect = v;
                    app.touch();
                  })),
          const SizedBox(width: 12),
          Expanded(
              child: Choice<int>(
                  label: 'Resolução',
                  value: o.height,
                  options: kHeights,
                  display: (h) => h == 2160 ? '2160 (4K)' : '${h}p',
                  onChanged: (v) {
                    o.height = v;
                    app.touch();
                  })),
        ]),
        const SizedBox(height: 8),
        Row(children: [
          Expanded(
              child: Choice<int>(
                  label: 'Quadros/s',
                  value: o.fps,
                  options: kFps,
                  onChanged: (v) {
                    o.fps = v;
                    app.touch();
                  })),
          const SizedBox(width: 12),
          Expanded(
              child: Choice<String>(
                  label: 'Encaixe',
                  value: o.fit,
                  options: kFits,
                  display: (f) => {'crop': 'Cortar bordas', 'blur': 'Fundo desfocado', 'pad': 'Tarjas pretas'}[f]!,
                  onChanged: (v) {
                    o.fit = v;
                    app.touch();
                  })),
        ]),
      ]),
      Section(
        title: 'Projetos salvos no aparelho',
        children: [
          FutureBuilder<List<SavedProject>>(
            future: _list,
            builder: (_, snap) {
              final items = snap.data ?? const [];
              if (items.isEmpty) return const Text('Nenhum projeto salvo ainda.');
              return Column(children: [
                for (final p in items)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(p.id == app.projectId ? Icons.radio_button_checked : Icons.movie_outlined),
                    title: Text(p.name),
                    subtitle: Text('Alterado em ${_date(p.updated)}'),
                    onTap: () async {
                      await app.open(p.id);
                      setState(() => _list = null);
                    },
                    trailing: IconButton(
                      icon: const Icon(Icons.delete_outline),
                      tooltip: 'Apagar do aparelho',
                      onPressed: () async {
                        final ok = await showDialog<bool>(
                          context: context,
                          builder: (c) => AlertDialog(
                            title: const Text('Apagar projeto?'),
                            content: Text('"${p.name}" será apagado deste aparelho. Vídeos já renderizados no '
                                'Nextcloud não são afetados.'),
                            actions: [
                              TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Cancelar')),
                              FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Apagar')),
                            ],
                          ),
                        );
                        if (ok == true) {
                          await app.projects.delete(p.id);
                          setState(() => _list = null);
                        }
                      },
                    ),
                  ),
              ]);
            },
          ),
        ],
      ),
    ]);
  }
}

String _aspectLabel(String a) => switch (a) {
      '16:9' => '16:9 YouTube',
      '9:16' => '9:16 Reels/TikTok',
      '1:1' => '1:1 Feed',
      '4:5' => '4:5 Feed',
      _ => a,
    };

String _date(DateTime d) =>
    '${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year} '
    '${d.hour.toString().padLeft(2, '0')}:${d.minute.toString().padLeft(2, '0')}';
