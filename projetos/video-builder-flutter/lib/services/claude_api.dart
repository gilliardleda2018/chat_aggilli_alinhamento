import 'dart:convert';

import 'package:http/http.dart' as http;

/// Aba IA: chamada direta à API do Claude com a chave do próprio usuário, como no desktop (ClaudeEngine da v7.x).
/// A chave fica só no cofre do aparelho.
class ClaudeApi {
  static const defaultModel = 'claude-haiku-5-5';

  final String apiKey;
  final String model;
  ClaudeApi(this.apiKey, {String? model}) : model = (model == null || model.isEmpty) ? defaultModel : model;

  Future<String> generate(String prompt, {String system = '', int maxTokens = 2000}) async {
    final r = await http
        .post(
          Uri.parse('https://api.anthropic.com/v1/messages'),
          headers: {
            'x-api-key': apiKey,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
          },
          body: jsonEncode({
            'model': model,
            'max_tokens': maxTokens,
            if (system.isNotEmpty) 'system': system,
            'messages': [
              {'role': 'user', 'content': prompt}
            ],
          }),
        )
        .timeout(const Duration(seconds: 120));
    final body = jsonDecode(utf8.decode(r.bodyBytes)) as Map<String, dynamic>;
    if (r.statusCode >= 300) {
      final err = body['error'] as Map<String, dynamic>?;
      throw Exception('Claude respondeu ${r.statusCode}: ${err?['message'] ?? r.body}');
    }
    return (body['content'] as List)
        .whereType<Map>()
        .where((c) => c['type'] == 'text')
        .map((c) => c['text'] as String)
        .join('\n')
        .trim();
  }
}
