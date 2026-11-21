import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';

/// Login OAuth 2.1 com registro dinâmico + PKCE e retorno em loopback (ADR-F02).
class OAuthResult {
  final String accessToken;
  final String? refreshToken;
  final String tokenEndpoint;
  final String clientId;
  OAuthResult(this.accessToken, this.refreshToken, this.tokenEndpoint, this.clientId);
}

class OAuthException implements Exception {
  final String message;
  OAuthException(this.message);
  @override
  String toString() => message;
}

String _random(int bytes) {
  final r = Random.secure();
  return base64UrlEncode(List<int>.generate(bytes, (_) => r.nextInt(256))).replaceAll('=', '');
}

class _Endpoints {
  final String authorize, token, register;
  _Endpoints(this.authorize, this.token, this.register);
}

Future<_Endpoints> _discover(String base, http.Client client) async {
  try {
    final r = await client
        .get(Uri.parse('$base/.well-known/oauth-authorization-server'))
        .timeout(const Duration(seconds: 15));
    if (r.statusCode == 200) {
      final j = jsonDecode(r.body) as Map<String, dynamic>;
      return _Endpoints(
        (j['authorization_endpoint'] ?? '$base/authorize') as String,
        (j['token_endpoint'] ?? '$base/token') as String,
        (j['registration_endpoint'] ?? '$base/register') as String,
      );
    }
  } catch (_) {
    // usa os caminhos padrão do servidor
  }
  return _Endpoints('$base/authorize', '$base/token', '$base/register');
}

/// Faz o login completo. [base] é o endereço do servidor, ex.: https://video.aggillintelligence.com.br
Future<OAuthResult> loginWithBrowser(String base, {Duration timeout = const Duration(minutes: 10)}) async {
  final client = http.Client();
  final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
  try {
    final ep = await _discover(base, client);
    final redirect = 'http://127.0.0.1:${server.port}/callback';

    final reg = await client.post(
      Uri.parse(ep.register),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'client_name': 'Video Builder (Android)',
        'redirect_uris': [redirect],
        'grant_types': ['authorization_code', 'refresh_token'],
        'response_types': ['code'],
        'token_endpoint_auth_method': 'none',
        'scope': 'videobuilder',
      }),
    );
    if (reg.statusCode >= 300) {
      throw OAuthException('O servidor recusou o registro do app (${reg.statusCode}): ${reg.body}');
    }
    final clientId = (jsonDecode(reg.body) as Map<String, dynamic>)['client_id'] as String;

    final verifier = _random(48);
    final challenge = base64UrlEncode(sha256.convert(ascii.encode(verifier)).bytes).replaceAll('=', '');
    final state = _random(24);
    final authUrl = Uri.parse(ep.authorize).replace(queryParameters: {
      'response_type': 'code',
      'client_id': clientId,
      'redirect_uri': redirect,
      'code_challenge': challenge,
      'code_challenge_method': 'S256',
      'state': state,
      'scope': 'videobuilder',
      'resource': '$base/mcp',
    });

    final codeFuture = _waitForCode(server, state).timeout(timeout,
        onTimeout: () => throw OAuthException('O login não foi concluído em ${timeout.inMinutes} minutos.'));
    if (!await launchUrl(authUrl, mode: LaunchMode.externalApplication)) {
      throw OAuthException('Não foi possível abrir o navegador.');
    }
    final code = await codeFuture;

    final tok = await client.post(Uri.parse(ep.token), body: {
      'grant_type': 'authorization_code',
      'code': code,
      'redirect_uri': redirect,
      'client_id': clientId,
      'code_verifier': verifier,
      'resource': '$base/mcp',
    });
    if (tok.statusCode >= 300) {
      throw OAuthException('Falha ao obter o token (${tok.statusCode}): ${tok.body}');
    }
    final t = jsonDecode(tok.body) as Map<String, dynamic>;
    return OAuthResult(t['access_token'] as String, t['refresh_token'] as String?, ep.token, clientId);
  } finally {
    await server.close(force: true);
    client.close();
  }
}

Future<String> _waitForCode(HttpServer server, String state) async {
  await for (final req in server) {
    if (req.uri.path != '/callback') {
      req.response.statusCode = 404;
      await req.response.close();
      continue;
    }
    final q = req.uri.queryParameters;
    final ok = q['code'] != null && q['state'] == state;
    req.response.headers.contentType = ContentType.html;
    req.response.write('<html><body style="font-family:sans-serif;text-align:center;padding-top:20vh">'
        '<h2>${ok ? 'Pronto! Volte para o Video Builder.' : 'Login não concluído.'}</h2>'
        '<p>${ok ? 'Você já pode fechar esta aba.' : htmlEscape.convert(q['error_description'] ?? q['error'] ?? '')}</p>'
        '</body></html>');
    await req.response.close();
    if (ok) return q['code']!;
    throw OAuthException('Login recusado: ${q['error_description'] ?? q['error'] ?? 'state inválido'}');
  }
  throw OAuthException('Login interrompido.');
}

/// Renova o token. Devolve null se o refresh token não vale mais.
Future<OAuthResult?> refreshToken(String tokenEndpoint, String clientId, String refresh) async {
  final r = await http.post(Uri.parse(tokenEndpoint), body: {
    'grant_type': 'refresh_token',
    'refresh_token': refresh,
    'client_id': clientId,
  });
  if (r.statusCode >= 300) return null;
  final t = jsonDecode(r.body) as Map<String, dynamic>;
  return OAuthResult(t['access_token'] as String, (t['refresh_token'] as String?) ?? refresh, tokenEndpoint, clientId);
}
