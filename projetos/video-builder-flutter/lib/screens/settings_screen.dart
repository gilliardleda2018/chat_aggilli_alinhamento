import 'package:flutter/material.dart';

import '../services/secure_store.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

/// Conexões (servidor, Nextcloud, Claude) e diagnóstico embutido.
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _server;
  late final TextEditingController _nc;
  final _static = TextEditingController();
  final _claudeKey = TextEditingController();
  final _claudeModel = TextEditingController();
  bool _busy = false;
  String _diag = '';

  @override
  void initState() {
    super.initState();
    final app = AppScope.read(context);
    _server = TextEditingController(text: app.serverUrl);
    _nc = TextEditingController(text: app.nextcloudUrl);
    app.secure.read(SecureStore.claudeModel).then((v) => _claudeModel.text = v ?? '');
    app.secure.read(SecureStore.claudeKey).then((v) {
      if (v != null && mounted) setState(() => _claudeKey.text = '••••••••${v.length > 4 ? v.substring(v.length - 4) : ''}');
    });
  }

  @override
  void dispose() {
    for (final c in [_server, _nc, _static, _claudeKey, _claudeModel]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _do(Future<void> Function() f, {String? ok}) async {
    setState(() => _busy = true);
    await runWithFeedback(context, f, success: ok);
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _diagnose(AppState app) async {
    final lines = <String>[];
    try {
      lines.add('Servidor /healthz: ${await app.mcp!.health()}');
    } catch (e) {
      lines.add('Servidor /healthz: falhou ($e)');
    }
    if (app.serverLoggedIn) {
      try {
        final acc = await app.requireMcp().call('vb_account');
        lines.add('Conta: ${acc.data ?? acc.text}');
      } catch (e) {
        lines.add('Conta: $e');
      }
    } else {
      lines.add('Login no servidor: não feito');
    }
    if (app.nextcloud != null) {
      try {
        final n = await app.nextcloud!.list('');
        lines.add('Nextcloud: ok (${n.length} itens na raiz, usuário ${app.nextcloud!.cred.user})');
      } catch (e) {
        lines.add('Nextcloud: $e');
      }
    } else {
      lines.add('Nextcloud: não conectado');
    }
    setState(() => _diag = lines.join('\n'));
  }

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Configurações')),
      body: AbsorbPointer(
        absorbing: _busy,
        child: ListView(children: [
          if (_busy) const LinearProgressIndicator(),
          Section(title: 'Servidor do Video Builder', children: [
            TextField(controller: _server, decoration: const InputDecoration(labelText: 'Endereço do servidor')),
            const SizedBox(height: 8),
            Text(app.serverLoggedIn ? '✅ Conectado' : '⚠️ Não conectado'),
            Wrap(spacing: 8, children: [
              FilledButton.icon(
                icon: const Icon(Icons.login),
                label: const Text('Entrar com a conta do Nextcloud'),
                onPressed: () => _do(() async {
                  await app.setServerUrl(_server.text);
                  await app.loginServer();
                }, ok: 'Conectado ao servidor.'),
              ),
              if (app.serverLoggedIn)
                OutlinedButton(onPressed: () => _do(app.logoutServer, ok: 'Desconectado.'), child: const Text('Sair')),
            ]),
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              title: const Text('Alternativa: token fixo (MCP_STATIC_TOKENS)'),
              children: [
                TextField(
                    controller: _static,
                    obscureText: true,
                    decoration: const InputDecoration(labelText: 'Token (vazio = remover)')),
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: () => _do(() async {
                      await app.setServerUrl(_server.text);
                      await app.setStaticToken(_static.text);
                    }, ok: 'Token salvo.'),
                    child: const Text('Salvar token'),
                  ),
                ),
              ],
            ),
          ]),
          Section(title: 'Nextcloud (suas mídias)', children: [
            TextField(controller: _nc, decoration: const InputDecoration(labelText: 'Endereço do Nextcloud')),
            const SizedBox(height: 8),
            Text(app.nextcloud != null ? '✅ Conectado como ${app.nextcloud!.cred.user}' : '⚠️ Não conectado'),
            Wrap(spacing: 8, children: [
              FilledButton.icon(
                icon: const Icon(Icons.cloud),
                label: const Text('Conectar Nextcloud'),
                onPressed: () => _do(() => app.loginNextcloud(_nc.text), ok: 'Nextcloud conectado.'),
              ),
              if (app.nextcloud != null)
                OutlinedButton(onPressed: () => _do(app.logoutNextcloud), child: const Text('Desconectar')),
            ]),
            const Text('A senha de app pode ser revogada no Nextcloud: Configurações → Segurança → Dispositivos e sessões.',
                style: TextStyle(fontSize: 12)),
          ]),
          Section(title: 'Claude (aba IA)', children: [
            TextField(
                controller: _claudeKey,
                decoration: const InputDecoration(labelText: 'Chave da API (console.anthropic.com)')),
            TextField(
                controller: _claudeModel,
                decoration: const InputDecoration(labelText: 'Modelo (vazio = padrão)', hintText: 'claude-haiku-5-5')),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                onPressed: () => _do(() async {
                  if (!_claudeKey.text.startsWith('••')) await app.secure.write(SecureStore.claudeKey, _claudeKey.text.trim());
                  await app.secure.write(SecureStore.claudeModel, _claudeModel.text.trim());
                }, ok: 'Salvo no cofre do aparelho.'),
                child: const Text('Salvar'),
              ),
            ),
          ]),
          Section(title: 'Diagnóstico', children: [
            FilledButton.tonalIcon(
                icon: const Icon(Icons.health_and_safety),
                label: const Text('Testar conexões'),
                onPressed: () => _do(() => _diagnose(app))),
            if (_diag.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 8), child: SelectableText(_diag)),
          ]),
          const Padding(
            padding: EdgeInsets.all(16),
            child: Text('Video Builder 8.0 (app Flutter) · Aggilli Intelligence', textAlign: TextAlign.center),
          ),
        ]),
      ),
    );
  }
}
