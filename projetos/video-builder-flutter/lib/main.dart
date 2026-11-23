import 'package:flutter/material.dart';

import 'screens/home.dart';
import 'state/app_state.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final state = AppState();
  runApp(VideoBuilderApp(state: state));
  state.init();
}

class VideoBuilderApp extends StatelessWidget {
  final AppState state;
  const VideoBuilderApp({super.key, required this.state});

  @override
  Widget build(BuildContext context) {
    // Cores da marca Aggilli: azul-petróleo com destaque ciano.
    const seed = Color(0xFF0E7490);
    return AppScope(
      state: state,
      child: MaterialApp(
        title: 'Video Builder',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: seed), useMaterial3: true),
        darkTheme: ThemeData(
            colorScheme: ColorScheme.fromSeed(seedColor: seed, brightness: Brightness.dark), useMaterial3: true),
        home: const HomeScreen(),
      ),
    );
  }
}
