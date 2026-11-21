import 'dart:math';

import 'package:flutter/widgets.dart';

import '../models/edit_plan.dart';
import '../services/mcp_client.dart';
import '../services/nextcloud.dart';
import '../services/oauth_loopback.dart';
import '../services/project_store.dart';
import '../services/secure_store.dart';

const kDefaultServer = 'https://video.aggillintelligence.com.br';
const kDefaultNextcloud = 'https://nuvem.aggillintelligence.com.br';

/// Estado único do app: projeto aberto + conexões. As abas leem e alteram por AppScope.of(context).
class AppState extends ChangeNotifier {
  final SecureStore secure = SecureStore();
  final ProjectStore projects = ProjectStore();

  EditPlan plan = EditPlan();
  String projectId = _newId();
  String projectName = 'Novo projeto';
  bool dirty = false;

  String serverUrl = kDefaultServer;
  bool serverLoggedIn = false;
  McpClient? mcp;

  NextcloudClient? nextcloud;
  String nextcloudUrl = kDefaultNextcloud;
  String ncFolder = '';

  /// job_id do último render iniciado neste aparelho.
  String? lastJobId;

  static String _newId() =>
      '${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(1 << 20).toRadixString(16)}';

  Future<void> init() async {
    serverUrl = (await secure.read(SecureStore.serverUrl)) ?? kDefaultServer;
    final hasToken = (await secure.read(SecureStore.accessToken)) != null ||
        (await secure.read(SecureStore.staticToken)) != null;
    serverLoggedIn = hasToken;
    _buildMcp();

    final ncServer = await secure.read(SecureStore.ncServer);
    final ncUser = await secure.read(SecureStore.ncUser);
    final ncPass = await secure.read(SecureStore.ncAppPassword);
    if (ncServer != null) nextcloudUrl = ncServer;
    if (ncServer != null && ncUser != null && ncPass != null) {
      nextcloud = NextcloudClient(NcCredentials(ncServer, ncUser, ncPass));
    }
    ncFolder = (await projects.getSetting('nc_folder')) ?? '';

    final last = await projects.lastId();
    if (last != null) {
      final loaded = await projects.load(last);
      if (loaded != null) {
        projectId = last;
        projectName = loaded.$1;
        plan = loaded.$2;
      }
    }
    notifyListeners();
  }

  void _buildMcp() {
    mcp?.close();
    mcp = McpClient(
      baseUrl: serverUrl,
      token: () async =>
          (await secure.read(SecureStore.staticToken)) ?? await secure.read(SecureStore.accessToken),
      refresh: _refresh,
    );
  }

  Future<bool> _refresh() async {
    if (await secure.read(SecureStore.staticToken) != null) return false;
    final rt = await secure.read(SecureStore.refreshToken);
    final te = await secure.read(SecureStore.tokenEndpoint);
    final cid = await secure.read(SecureStore.clientId);
    if (rt == null || te == null || cid == null) return false;
    final r = await refreshToken(te, cid, rt);
    if (r == null) {
      serverLoggedIn = false;
      notifyListeners();
      return false;
    }
    await secure.write(SecureStore.accessToken, r.accessToken);
    await secure.write(SecureStore.refreshToken, r.refreshToken);
    return true;
  }

  // ------------------------------------------------------------------ conexões

  Future<void> setServerUrl(String url) async {
    serverUrl = url.trim().replaceAll(RegExp(r'/+$'), '');
    await secure.write(SecureStore.serverUrl, serverUrl);
    _buildMcp();
    notifyListeners();
  }

  Future<void> loginServer() async {
    final r = await loginWithBrowser(serverUrl);
    await secure.write(SecureStore.accessToken, r.accessToken);
    await secure.write(SecureStore.refreshToken, r.refreshToken);
    await secure.write(SecureStore.tokenEndpoint, r.tokenEndpoint);
    await secure.write(SecureStore.clientId, r.clientId);
    serverLoggedIn = true;
    notifyListeners();
  }

  Future<void> setStaticToken(String? token) async {
    await secure.write(SecureStore.staticToken, token?.trim());
    serverLoggedIn = token != null && token.trim().isNotEmpty ||
        (await secure.read(SecureStore.accessToken)) != null;
    notifyListeners();
  }

  Future<void> logoutServer() async {
    await secure.deleteAll([
      SecureStore.accessToken, SecureStore.refreshToken, SecureStore.tokenEndpoint,
      SecureStore.clientId, SecureStore.staticToken,
    ]);
    serverLoggedIn = false;
    notifyListeners();
  }

  Future<void> loginNextcloud(String url) async {
    final c = await ncLoginFlow(url);
    await secure.write(SecureStore.ncServer, c.server);
    await secure.write(SecureStore.ncUser, c.user);
    await secure.write(SecureStore.ncAppPassword, c.appPassword);
    nextcloud?.close();
    nextcloud = NextcloudClient(c);
    nextcloudUrl = c.server;
    notifyListeners();
  }

  Future<void> logoutNextcloud() async {
    await secure.deleteAll([SecureStore.ncUser, SecureStore.ncAppPassword]);
    nextcloud?.close();
    nextcloud = null;
    notifyListeners();
  }

  Future<void> rememberFolder(String folder) async {
    ncFolder = folder;
    await projects.setSetting('nc_folder', folder);
  }

  McpClient requireMcp() {
    if (!serverLoggedIn || mcp == null) {
      throw McpException('Entre no servidor do Video Builder em Configurações.');
    }
    return mcp!;
  }

  NextcloudClient requireNextcloud() {
    final n = nextcloud;
    if (n == null) throw NextcloudException('Conecte o Nextcloud em Configurações.');
    return n;
  }

  // ------------------------------------------------------------------ projeto

  /// Chame depois de mudar qualquer coisa em [plan].
  void touch() {
    dirty = true;
    notifyListeners();
  }

  Future<void> save({String? name}) async {
    if (name != null && name.trim().isNotEmpty) projectName = name.trim();
    await projects.save(projectId, projectName, plan);
    dirty = false;
    notifyListeners();
  }

  void newProject() {
    plan = EditPlan();
    projectId = _newId();
    projectName = 'Novo projeto';
    dirty = false;
    notifyListeners();
  }

  Future<void> open(String id) async {
    final loaded = await projects.load(id);
    if (loaded == null) return;
    projectId = id;
    projectName = loaded.$1;
    plan = loaded.$2;
    dirty = false;
    notifyListeners();
  }

  Future<void> duplicate() async {
    final copy = EditPlan.fromJson(plan.toStorage());
    projectId = _newId();
    projectName = '$projectName (cópia)';
    plan = copy;
    await save();
  }

  /// Lê a duração de um vídeo no servidor (vb_media_probe) e guarda no clipe.
  Future<void> probeClip(Clip clip) async {
    if (clip.isImage) return;
    final r = await requireMcp().call('vb_media_probe', {'path': clip.source});
    final d = r['duration'];
    if (d is num) {
      clip.sourceDuration = d.toDouble();
      touch();
    }
  }

  void addMedia(String path) {
    final ext = extOf(path);
    if (kAudioExt.contains(ext)) {
      plan.music = Music(source: path);
    } else if (kSubtitleExt.contains(ext)) {
      plan.subtitles = Subtitles(source: path);
    } else {
      plan.clips.add(Clip(source: path, duration: kImageExt.contains(ext) ? 3.0 : null));
    }
    touch();
  }
}

class AppScope extends InheritedNotifier<AppState> {
  const AppScope({super.key, required AppState state, required super.child}) : super(notifier: state);

  static AppState of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<AppScope>()!.notifier!;

  static AppState read(BuildContext context) =>
      context.getInheritedWidgetOfExactType<AppScope>()!.notifier!;
}
