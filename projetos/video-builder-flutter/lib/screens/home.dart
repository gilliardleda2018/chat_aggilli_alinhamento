import 'package:flutter/material.dart';

import '../models/edit_plan.dart';
import '../state/app_state.dart';
import '../tabs/audio_tab.dart';
import '../tabs/auto_edicao_tab.dart';
import '../tabs/auto_suite_tab.dart';
import '../tabs/cor_tab.dart';
import '../tabs/enviar_tab.dart';
import '../tabs/face_restore_tab.dart';
import '../tabs/ia_tab.dart';
import '../tabs/legendas_tab.dart';
import '../tabs/legendas_turbo_tab.dart';
import '../tabs/luts_tab.dart';
import '../tabs/midia_tab.dart';
import '../tabs/projeto_tab.dart';
import '../tabs/qc_tab.dart';
import '../tabs/render_tab.dart';
import '../tabs/stems_tab.dart';
import '../tabs/timeline_tab.dart';
import '../tabs/transicoes_tab.dart';
import '../tabs/upscale_tab.dart';
import '../tabs/vertical_tab.dart';
import '../tabs/whisperx_tab.dart';
import 'settings_screen.dart';

/// As 20 abas do desktop v7.6, na mesma ordem (docs/MAPA-DAS-ABAS.md).
class TabDef {
  final String title;
  final IconData icon;
  final String group;
  final bool pending; // depende de ferramenta que o servidor ainda não tem
  final WidgetBuilder builder;
  const TabDef(this.title, this.icon, this.group, this.builder, {this.pending = false});
}

final List<TabDef> kTabs = [
  TabDef('Projeto', Icons.folder_special, 'Núcleo', (_) => const ProjetoTab()),
  TabDef('Mídia', Icons.perm_media, 'Núcleo', (_) => const MidiaTab()),
  TabDef('Timeline', Icons.view_timeline, 'Núcleo', (_) => const TimelineTab()),
  TabDef('Cor', Icons.palette, 'Núcleo', (_) => const CorTab()),
  TabDef('Áudio', Icons.graphic_eq, 'Núcleo', (_) => const AudioTab()),
  TabDef('IA', Icons.auto_awesome, 'Núcleo', (_) => const IaTab()),
  TabDef('Render', Icons.movie_creation, 'Núcleo', (_) => const RenderTab()),
  TabDef('QC', Icons.fact_check, 'Núcleo', (_) => const QcTab()),
  TabDef('Transições GL', Icons.compare, 'Professional Suite', (_) => const TransicoesTab()),
  TabDef('LUTs Avançadas', Icons.filter, 'Professional Suite', (_) => const LutsTab()),
  TabDef('Auto-Edição', Icons.content_cut, 'Professional Suite', (_) => const AutoEdicaoTab()),
  TabDef('Legendas AI', Icons.subtitles, 'Professional Suite', (_) => const LegendasTab()),
  TabDef('Vertical', Icons.stay_current_portrait, 'Professional Suite', (_) => const VerticalTab()),
  TabDef('Upscale AI', Icons.high_quality, 'AI Power', (_) => const UpscaleTab()),
  TabDef('Audio Stems', Icons.call_split, 'AI Power', (_) => const StemsTab(), pending: true),
  TabDef('Legendas Turbo', Icons.speed, 'AI Power', (_) => const LegendasTurboTab(), pending: true),
  TabDef('Enviar / Importar', Icons.upload_file, 'Content Tools', (_) => const EnviarTab()),
  TabDef('Face Restore', Icons.face_retouching_natural, 'Content Tools', (_) => const FaceRestoreTab(),
      pending: true),
  TabDef('WhisperX', Icons.karaoke, 'Content Tools', (_) => const WhisperxTab(), pending: true),
  TabDef('Auto-Edit Suite', Icons.dashboard_customize, 'Content Tools', (_) => const AutoSuiteTab()),
];

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _index = 0;
  // Barra de baixo: as 5 abas de uso diário. As outras ficam no menu lateral.
  static const _bottom = [0, 1, 2, 4, 6];

  void _go(int i) => setState(() => _index = i);

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final tab = kTabs[_index];
    final total = computeTimeline(app.plan).total;
    final bottomIndex = _bottom.indexOf(_index);
    return Scaffold(
      appBar: AppBar(
        title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(tab.title),
          Text('${app.projectName}${app.dirty ? ' •' : ''}  ·  ${app.plan.clips.length} clipes  ·  ${fmtSeconds(total)}',
              style: Theme.of(context).textTheme.bodySmall),
        ]),
        actions: [
          IconButton(
            tooltip: 'Salvar projeto',
            icon: const Icon(Icons.save),
            onPressed: () async {
              await app.save();
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Projeto salvo.')));
              }
            },
          ),
          IconButton(
            tooltip: 'Configurações e conexões',
            icon: Badge(isLabelVisible: !app.serverLoggedIn || app.nextcloud == null, child: const Icon(Icons.settings)),
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const SettingsScreen())),
          ),
        ],
      ),
      drawer: NavigationDrawer(
        selectedIndex: _index,
        onDestinationSelected: (i) {
          Navigator.of(context).pop();
          _go(i);
        },
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(28, 20, 16, 8),
            child: Text('Video Builder · Aggilli', style: Theme.of(context).textTheme.titleLarge),
          ),
          for (var i = 0; i < kTabs.length; i++) ...[
            if (i == 0 || kTabs[i].group != kTabs[i - 1].group)
              Padding(
                padding: const EdgeInsets.fromLTRB(28, 12, 16, 4),
                child: Text(kTabs[i].group, style: Theme.of(context).textTheme.labelLarge),
              ),
            NavigationDrawerDestination(
              icon: Icon(kTabs[i].icon),
              label: Text(kTabs[i].pending ? '${kTabs[i].title}  ⏳' : kTabs[i].title),
            ),
          ],
          const SizedBox(height: 16),
        ],
      ),
      body: KeyedSubtree(key: ValueKey(_index), child: tab.builder(context)),
      bottomNavigationBar: NavigationBar(
        selectedIndex: bottomIndex < 0 ? 0 : bottomIndex,
        indicatorColor: bottomIndex < 0 ? Colors.transparent : null,
        onDestinationSelected: (i) => _go(_bottom[i]),
        destinations: [
          for (final i in _bottom) NavigationDestination(icon: Icon(kTabs[i].icon), label: kTabs[i].title),
        ],
      ),
    );
  }
}
