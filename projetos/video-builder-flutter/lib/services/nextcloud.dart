import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';

/// Acesso direto ao Nextcloud por WebDAV com senha de app do Login Flow v2 (ADR-F03).

class NcEntry {
  final String path; // relativo à raiz do usuário, sem barra inicial
  final bool isDir;
  final int size;
  final DateTime? modified;
  NcEntry(this.path, this.isDir, this.size, this.modified);

  String get name {
    final p = path.endsWith('/') ? path.substring(0, path.length - 1) : path;
    final i = p.lastIndexOf('/');
    return i < 0 ? p : p.substring(i + 1);
  }
}

class NcCredentials {
  final String server, user, appPassword;
  NcCredentials(this.server, this.user, this.appPassword);
}

class NextcloudException implements Exception {
  final String message;
  NextcloudException(this.message);
  @override
  String toString() => message;
}

String _trimSlash(String s) => s.replaceAll(RegExp(r'/+$'), '');

/// Login Flow v2: abre o navegador e espera a pessoa autorizar (até 20 min).
Future<NcCredentials> ncLoginFlow(String server) async {
  final base = _trimSlash(server.trim());
  final start = await http.post(Uri.parse('$base/index.php/login/v2'),
      headers: {'User-Agent': 'Video Builder (Android)'});
  if (start.statusCode != 200) {
    throw NextcloudException('Este endereço não parece um Nextcloud (${start.statusCode}).');
  }
  final j = jsonDecode(start.body) as Map<String, dynamic>;
  final poll = j['poll'] as Map<String, dynamic>;
  if (!await launchUrl(Uri.parse(j['login'] as String), mode: LaunchMode.externalApplication)) {
    throw NextcloudException('Não foi possível abrir o navegador.');
  }
  final deadline = DateTime.now().add(const Duration(minutes: 20));
  while (DateTime.now().isBefore(deadline)) {
    await Future<void>.delayed(const Duration(seconds: 2));
    final r = await http.post(Uri.parse(poll['endpoint'] as String), body: {'token': poll['token']});
    if (r.statusCode == 200) {
      final c = jsonDecode(r.body) as Map<String, dynamic>;
      return NcCredentials(_trimSlash(c['server'] as String), c['loginName'] as String, c['appPassword'] as String);
    }
  }
  throw NextcloudException('O login no Nextcloud não foi concluído a tempo.');
}

class NextcloudClient {
  final NcCredentials cred;
  final http.Client _http = http.Client();
  NextcloudClient(this.cred);

  String get _davRoot => '${cred.server}/remote.php/dav/files/${Uri.encodeComponent(cred.user)}';

  Map<String, String> get _auth =>
      {'Authorization': 'Basic ${base64Encode(utf8.encode('${cred.user}:${cred.appPassword}'))}'};

  Uri _uri(String path) {
    final parts = path.split('/').where((p) => p.isNotEmpty).map(Uri.encodeComponent);
    return Uri.parse('$_davRoot/${parts.join('/')}');
  }

  Future<List<NcEntry>> list(String folder) async {
    final req = http.Request('PROPFIND', _uri(folder))
      ..headers.addAll({..._auth, 'Depth': '1', 'Content-Type': 'application/xml'})
      ..body = '<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype/>'
          '<d:getcontentlength/><d:getlastmodified/></d:prop></d:propfind>';
    final res = await http.Response.fromStream(await _http.send(req).timeout(const Duration(seconds: 30)));
    if (res.statusCode == 401) throw NextcloudException('Senha de app do Nextcloud inválida. Entre de novo.');
    if (res.statusCode != 207) throw NextcloudException('Nextcloud respondeu ${res.statusCode}.');
    return _parse(utf8.decode(res.bodyBytes), folder);
  }

  List<NcEntry> _parse(String xml, String folder) {
    final prefix = Uri.decodeComponent(Uri.parse(_davRoot).path);
    final out = <NcEntry>[];
    final responses = RegExp(r'<[a-zA-Z]*:?response\b.*?</[a-zA-Z]*:?response>', dotAll: true).allMatches(xml);
    String? tag(String block, String name) {
      final m = RegExp('<[a-zA-Z]*:?$name[^>]*>(.*?)</[a-zA-Z]*:?$name>', dotAll: true).firstMatch(block);
      return m?.group(1);
    }

    final self = folder.split('/').where((p) => p.isNotEmpty).join('/');
    for (final m in responses) {
      final block = m.group(0)!;
      final href = Uri.decodeComponent(tag(block, 'href') ?? '');
      var rel = href.startsWith(prefix) ? href.substring(prefix.length) : href;
      rel = rel.replaceAll(RegExp(r'^/+'), '');
      final isDir = RegExp(r'<[a-zA-Z]*:?collection\s*/>').hasMatch(block);
      final clean = rel.replaceAll(RegExp(r'/+$'), '');
      if (clean == self) continue; // a própria pasta
      final size = int.tryParse(tag(block, 'getcontentlength') ?? '') ?? 0;
      DateTime? mod;
      final lm = tag(block, 'getlastmodified');
      if (lm != null) {
        try {
          mod = HttpDate.parse(lm);
        } catch (_) {}
      }
      out.add(NcEntry(clean, isDir, size, mod));
    }
    out.sort((a, b) => a.isDir != b.isDir ? (a.isDir ? -1 : 1) : a.name.toLowerCase().compareTo(b.name.toLowerCase()));
    return out;
  }

  Future<bool> exists(String path) async {
    final req = http.Request('PROPFIND', _uri(path))..headers.addAll({..._auth, 'Depth': '0'});
    final res = await _http.send(req);
    await res.stream.drain<void>();
    return res.statusCode == 207;
  }

  Future<void> mkdirs(String folder) async {
    var acc = '';
    for (final part in folder.split('/').where((p) => p.isNotEmpty)) {
      acc = acc.isEmpty ? part : '$acc/$part';
      final req = http.Request('MKCOL', _uri(acc))..headers.addAll(_auth);
      final res = await _http.send(req);
      await res.stream.drain<void>();
      if (res.statusCode != 201 && res.statusCode != 405) {
        throw NextcloudException('Não foi possível criar a pasta "$acc" (${res.statusCode}).');
      }
    }
  }

  /// Envia sem sobrescrever: se já existir, acrescenta " (2)", " (3)"... Devolve o caminho final.
  Future<String> upload(String folder, String fileName, File file, {void Function(double)? onProgress}) async {
    await mkdirs(folder);
    final dot = fileName.lastIndexOf('.');
    final stem = dot > 0 ? fileName.substring(0, dot) : fileName;
    final ext = dot > 0 ? fileName.substring(dot) : '';
    var name = fileName;
    for (var n = 2; await exists('$folder/$name'); n++) {
      name = '$stem ($n)$ext';
    }
    final target = '${folder.replaceAll(RegExp(r'/+$'), '')}/$name';
    final total = await file.length();
    var sent = 0;
    final req = http.StreamedRequest('PUT', _uri(target))
      ..headers.addAll({..._auth, 'Content-Type': 'application/octet-stream'})
      ..contentLength = total;
    final done = _http.send(req);
    await for (final chunk in file.openRead()) {
      req.sink.add(chunk);
      sent += chunk.length;
      onProgress?.call(total == 0 ? 1 : sent / total);
    }
    await req.sink.close();
    final res = await done;
    await res.stream.drain<void>();
    if (res.statusCode >= 300) throw NextcloudException('Envio falhou (${res.statusCode}).');
    return target.replaceAll(RegExp(r'^/+'), '');
  }

  Uri webUrlFor(String folder) =>
      Uri.parse('${cred.server}/apps/files/?dir=/${folder.split('/').where((p) => p.isNotEmpty).join('/')}');

  void close() => _http.close();
}
