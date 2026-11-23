import 'package:flutter_test/flutter_test.dart';
import 'package:videobuilder/models/edit_plan.dart';
import 'package:videobuilder/services/analysis.dart';
import 'package:videobuilder/tabs/auto_edicao_tab.dart';

void main() {
  group('EditPlan → JSON do servidor', () {
    test('foto leva duration e ken_burns; vídeo leva start/end/speed', () {
      final plan = EditPlan(clips: [
        Clip(source: 'A/x.mp4', start: 2, end: 6, speed: 2),
        Clip(source: 'A/y.jpg', duration: 2.5, kenBurns: true, transition: Transition(type: 'fade', duration: 0.5)),
      ]);
      final j = plan.toJson();
      final clips = j['clips'] as List;
      expect(clips[0], {'source': 'A/x.mp4', 'start': 2.0, 'end': 6.0, 'speed': 2.0});
      expect(clips[1]['duration'], 2.5);
      expect(clips[1]['ken_burns'], true);
      expect(clips[1]['transition'], {'type': 'fade', 'duration': 0.5});
      expect(j.containsKey('color'), false, reason: 'cor neutra não é enviada');
    });

    test('dados só do app (duração da origem) não vão para o servidor, mas voltam do armazenamento', () {
      final plan = EditPlan(clips: [Clip(source: 'x.mp4', sourceDuration: 12)]);
      expect((plan.toJson()['clips'] as List).first.containsKey('_source_duration'), false);
      final back = EditPlan.fromJson(plan.toStorage());
      expect(back.clips.first.sourceDuration, 12);
    });
  });

  group('linha do tempo (igual a edl.timeline)', () {
    test('desconta a sobreposição das transições', () {
      final plan = EditPlan(clips: [
        Clip(source: 'a.mp4', start: 0, end: 4),
        Clip(source: 'b.mp4', start: 0, end: 4, transition: Transition(duration: 1)),
        Clip(source: 'c.jpg', duration: 3),
      ]);
      final tl = computeTimeline(plan);
      expect(tl.starts, [0.0, 3.0, 7.0]);
      expect(tl.total, 10.0);
      expect(tl.problems, isEmpty);
    });

    test('velocidade encurta o clipe', () {
      final plan = EditPlan(clips: [Clip(source: 'a.mp4', start: 0, end: 10, speed: 2)]);
      expect(computeTimeline(plan).total, 5.0);
    });

    test('acusa transição maior que o clipe', () {
      final plan = EditPlan(clips: [
        Clip(source: 'a.mp4', start: 0, end: 1),
        Clip(source: 'b.mp4', start: 0, end: 4, transition: Transition(duration: 2)),
      ]);
      expect(computeTimeline(plan).problems, isNotEmpty);
    });

    test('duração desconhecida deixa o total em aberto', () {
      final plan = EditPlan(clips: [Clip(source: 'a.mp4')]);
      expect(computeTimeline(plan).total, isNull);
    });
  });

  group('auto-edição', () {
    final a = Analysis('v.mp4', 20, -18, [5, 12], [Segment(3, 6)], [Segment(0, 3), Segment(6, 20)]);

    test('remover silêncios respeita mínimo e máximo', () {
      final clips = buildClips(a, mode: 'som', minLen: 1, maxLen: 6, pad: 0);
      expect(clips.map((c) => [c.start, c.end]).toList(), [
        [0.0, 3.0],
        [6.0, 12.0],
        [12.0, 18.0],
        [18.0, 20.0],
      ]);
    });

    test('por cenas corta nas trocas', () {
      final clips = buildClips(a, mode: 'cenas', minLen: 1, maxLen: 30);
      expect(clips.map((c) => [c.start, c.end]).toList(), [
        [0.0, 5.0],
        [5.0, 12.0],
        [12.0, 20.0],
      ]);
    });
  });
}
