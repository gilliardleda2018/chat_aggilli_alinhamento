import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/edit_plan.dart';

/// Projetos salvos no aparelho (equivalente ao arquivo .vbp do desktop).
/// Cada projeto é o JSON do EditPlan + metadados. Chave: "projeto:<id>".
class SavedProject {
  final String id;
  final String name;
  final DateTime updated;
  SavedProject(this.id, this.name, this.updated);
}

class ProjectStore {
  static const _prefix = 'projeto:';
  static const _lastKey = 'projeto_atual';

  Future<List<SavedProject>> list() async {
    final p = await SharedPreferences.getInstance();
    final out = <SavedProject>[];
    for (final k in p.getKeys().where((k) => k.startsWith(_prefix))) {
      try {
        final j = jsonDecode(p.getString(k)!) as Map<String, dynamic>;
        out.add(SavedProject(k.substring(_prefix.length), j['name'] as String,
            DateTime.tryParse(j['updated'] as String? ?? '') ?? DateTime(2000)));
      } catch (_) {}
    }
    out.sort((a, b) => b.updated.compareTo(a.updated));
    return out;
  }

  Future<void> save(String id, String name, EditPlan plan) async {
    final p = await SharedPreferences.getInstance();
    await p.setString('$_prefix$id',
        jsonEncode({'name': name, 'updated': DateTime.now().toIso8601String(), 'plan': plan.toStorage()}));
    await p.setString(_lastKey, id);
  }

  Future<(String, EditPlan)?> load(String id) async {
    final p = await SharedPreferences.getInstance();
    final s = p.getString('$_prefix$id');
    if (s == null) return null;
    final j = jsonDecode(s) as Map<String, dynamic>;
    await p.setString(_lastKey, id);
    return (j['name'] as String, EditPlan.fromJson(Map<String, dynamic>.from(j['plan'] as Map)));
  }

  Future<String?> lastId() async => (await SharedPreferences.getInstance()).getString(_lastKey);

  Future<void> delete(String id) async {
    final p = await SharedPreferences.getInstance();
    await p.remove('$_prefix$id');
    if (p.getString(_lastKey) == id) await p.remove(_lastKey);
  }

  Future<String?> getSetting(String key) async => (await SharedPreferences.getInstance()).getString('cfg:$key');
  Future<void> setSetting(String key, String value) async =>
      (await SharedPreferences.getInstance()).setString('cfg:$key', value);
}
