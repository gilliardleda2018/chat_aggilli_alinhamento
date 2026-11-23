import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:videobuilder/main.dart';
import 'package:videobuilder/screens/home.dart';
import 'package:videobuilder/state/app_state.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('abre na aba Projeto e lista as 20 abas no menu', (tester) async {
    await tester.pumpWidget(VideoBuilderApp(state: AppState()));
    await tester.pump();
    expect(find.text('Saída'), findsOneWidget);
    expect(kTabs.length, 20);

    await tester.tap(find.byTooltip('Open navigation menu'));
    await tester.pumpAndSettle();
    expect(find.text('Núcleo'), findsOneWidget);
    expect(find.text('Cor'), findsWidgets);
  });

  testWidgets('cada aba constrói sem erro', (tester) async {
    final state = AppState();
    for (final tab in kTabs) {
      await tester.pumpWidget(AppScope(
        state: state,
        child: MaterialApp(home: Scaffold(body: Builder(builder: tab.builder))),
      ));
      await tester.pump();
      expect(tester.takeException(), isNull, reason: 'aba ${tab.title}');
    }
  });
}
