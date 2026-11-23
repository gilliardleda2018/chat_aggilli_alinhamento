import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

/// Cliente MCP mínimo (JSON-RPC 2.0 por HTTP), para o servidor em modo stateless + json_response (ADR-F01).
/// Só usa tools/call: o servidor não guarda sessão entre chamadas.

class McpException implements Exception {
  final String message;
  final int? status;
  McpException(this.message, {this.status});
  bool get unauthorized => status == 401;
  @override
  String toString() => message;
}

/// Resultado de uma ferramenta: o JSON (se houver) e as imagens (ex.: vb_media_preview).
class ToolResult {
  final Map<String, dynamic>? data;
  final String text;
  final List<Uint8List> images;
  ToolResult(this.data, this.text, this.images);

  dynamic operator [](String key) => data?[key];
}

typedef TokenProvider = Future<String?> Function();
typedef TokenRefresher = Future<bool> Function();

class McpClient {
  final String baseUrl;
  final TokenProvider token;
  final TokenRefresher refresh;
  final http.Client _http = http.Client();
  int _id = 0;

  McpClient({required this.baseUrl, required this.token, required this.refresh});

  Uri get _endpoint => Uri.parse('$baseUrl/mcp');

  Future<http.Response> _post(Map<String, dynamic> body) async {
    final t = await token();
    return _http
        .post(
          _endpoint,
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
            'MCP-Protocol-Version': '2025-06-18',
            if (t != null) 'Authorization': 'Bearer $t',
          },
          body: jsonEncode(body),
        )
        .timeout(const Duration(seconds: 90));
  }

  Future<ToolResult> call(String name, [Map<String, dynamic> args = const {}]) async {
    final body = {
      'jsonrpc': '2.0',
      'id': ++_id,
      'method': 'tools/call',
      'params': {'name': name, 'arguments': args},
    };
    var r = await _post(body);
    if (r.statusCode == 401 && await refresh()) {
      r = await _post(body);
    }
    if (r.statusCode == 401) {
      throw McpException('Sessão do servidor expirada. Entre de novo em Configurações.', status: 401);
    }
    if (r.statusCode >= 300) {
      throw McpException('Servidor respondeu ${r.statusCode}: ${_short(r.body)}', status: r.statusCode);
    }
    final msg = _decode(r);
    if (msg['error'] != null) {
      final e = msg['error'] as Map<String, dynamic>;
      throw McpException('${e['message'] ?? 'Erro'}');
    }
    final result = Map<String, dynamic>.from(msg['result'] as Map);
    final content = (result['content'] as List? ?? const []).cast<Map>();
    final texts = <String>[];
    final images = <Uint8List>[];
    for (final c in content) {
      if (c['type'] == 'text') texts.add(c['text'] as String);
      if (c['type'] == 'image') images.add(base64Decode(c['data'] as String));
    }
    final text = texts.join('\n');
    if (result['isError'] == true) throw McpException(text.isEmpty ? 'A ferramenta $name falhou.' : text);

    Map<String, dynamic>? data;
    final structured = result['structuredContent'];
    if (structured is Map) {
      data = Map<String, dynamic>.from(structured);
      // O SDK embrulha retornos que não são dicionário em {"result": ...}.
      if (data.length == 1 && data['result'] is Map) data = Map<String, dynamic>.from(data['result'] as Map);
    }
    if (data == null) {
      for (final t in texts) {
        try {
          final j = jsonDecode(t);
          if (j is Map) {
            data = Map<String, dynamic>.from(j);
            break;
          }
        } catch (_) {}
      }
    }
    return ToolResult(data, text, images);
  }

  Map<String, dynamic> _decode(http.Response r) {
    final ct = r.headers['content-type'] ?? '';
    final body = utf8.decode(r.bodyBytes);
    if (ct.contains('text/event-stream')) {
      // Por garantia: se o servidor responder em SSE, pega o último "data:".
      final lines = body.split('\n').where((l) => l.startsWith('data:')).toList();
      if (lines.isEmpty) throw McpException('Resposta vazia do servidor.');
      return jsonDecode(lines.last.substring(5).trim()) as Map<String, dynamic>;
    }
    return jsonDecode(body) as Map<String, dynamic>;
  }

  String _short(String s) => s.length > 300 ? '${s.substring(0, 300)}…' : s;

  /// /healthz: diagnóstico embutido (não precisa de login).
  Future<String> health() async {
    final r = await _http.get(Uri.parse('$baseUrl/healthz')).timeout(const Duration(seconds: 15));
    return '${r.statusCode} ${_short(r.body)}';
  }

  void close() => _http.close();
}
