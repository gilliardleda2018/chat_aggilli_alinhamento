import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Cofre do aparelho (Android Keystore). Guarda tokens, senha de app do Nextcloud e a chave da API do Claude.
/// Nada disso vai para o shared_preferences nem para os projetos salvos.
class SecureStore {
  static const _storage = FlutterSecureStorage(aOptions: AndroidOptions(encryptedSharedPreferences: true));

  static const serverUrl = 'server_url';
  static const accessToken = 'mcp_access_token';
  static const refreshToken = 'mcp_refresh_token';
  static const tokenEndpoint = 'mcp_token_endpoint';
  static const clientId = 'mcp_client_id';
  static const staticToken = 'mcp_static_token';
  static const ncServer = 'nc_server';
  static const ncUser = 'nc_user';
  static const ncAppPassword = 'nc_app_password';
  static const claudeKey = 'claude_api_key';
  static const claudeModel = 'claude_model';

  Future<String?> read(String key) => _storage.read(key: key);

  Future<void> write(String key, String? value) async {
    if (value == null || value.isEmpty) {
      await _storage.delete(key: key);
    } else {
      await _storage.write(key: key, value: value);
    }
  }

  Future<void> deleteAll(List<String> keys) async {
    for (final k in keys) {
      await _storage.delete(key: k);
    }
  }
}
