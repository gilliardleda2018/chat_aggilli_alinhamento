import 'package:flutter/material.dart';

import '../widgets/common.dart';

/// Mostra o fluxo planejado de uma aba que aguarda o servidor (para a tela já nascer com o desenho final).
class PendingFlow extends StatelessWidget {
  final List<String> steps;
  const PendingFlow({super.key, required this.steps});

  @override
  Widget build(BuildContext context) => Section(title: 'Como vai funcionar', children: [
        for (var i = 0; i < steps.length; i++)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: CircleAvatar(radius: 14, child: Text('${i + 1}')),
            title: Text(steps[i]),
          ),
      ]);
}
