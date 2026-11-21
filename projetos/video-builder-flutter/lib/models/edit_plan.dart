// Roteiro de edição (EditPlan): espelho de mcp_videobuilder/src/videobuilder_mcp/edl.py.
// Os nomes dos campos JSON e os limites são os mesmos do servidor (docs/ROTEIRO.md).
// Se o servidor mudar o roteiro, atualize aqui e o teste test/edit_plan_test.dart.

const List<String> kAspects = ['16:9', '9:16', '1:1', '4:5'];
const List<int> kHeights = [720, 1080, 1440, 2160];
const List<int> kFps = [24, 25, 30, 50, 60];
const List<String> kFits = ['crop', 'blur', 'pad'];
const List<String> kPositions = ['top', 'center', 'bottom'];
const List<String> kSizes = ['small', 'medium', 'large'];
const List<String> kStyles = ['plain', 'box', 'shadow'];
const List<String> kFonts = [
  'classica', 'moderna', 'moderna-forte', 'geometrica', 'geometrica-forte',
  'futurista', 'elegante', 'elegante-italico', 'manuscrita',
];
const List<String> kTransitions = [
  'fade', 'dissolve', 'fadeblack', 'fadewhite', 'fadegrays', 'wipeleft', 'wiperight', 'wipeup', 'wipedown',
  'slideleft', 'slideright', 'slideup', 'slidedown', 'smoothleft', 'smoothright', 'smoothup', 'smoothdown',
  'circleopen', 'circleclose', 'circlecrop', 'rectcrop', 'radial', 'distance', 'vertopen', 'vertclose',
  'horzopen', 'horzclose', 'pixelize', 'hblur', 'zoomin', 'squeezeh', 'squeezev', 'diagtl', 'diagtr',
  'diagbl', 'diagbr', 'hlslice', 'hrslice', 'vuslice', 'vdslice',
];

const Set<String> kImageExt = {'jpg', 'jpeg', 'png', 'webp'};
const Set<String> kVideoExt = {'mp4', 'mov', 'm4v', 'mkv', 'avi', 'webm', '3gp'};
const Set<String> kAudioExt = {'mp3', 'm4a', 'aac', 'wav', 'ogg', 'opus', 'flac'};
const Set<String> kSubtitleExt = {'srt', 'vtt', 'ass'};

String extOf(String path) {
  final i = path.lastIndexOf('.');
  return i < 0 ? '' : path.substring(i + 1).toLowerCase();
}

String baseName(String path) {
  final p = path.endsWith('/') ? path.substring(0, path.length - 1) : path;
  final i = p.lastIndexOf('/');
  return i < 0 ? p : p.substring(i + 1);
}

double? _d(Object? v) => v == null ? null : (v as num).toDouble();

class Transition {
  String type;
  double duration;
  Transition({this.type = 'fade', this.duration = 0.5});

  Map<String, dynamic> toJson() => {'type': type, 'duration': duration};
  factory Transition.fromJson(Map<String, dynamic> j) =>
      Transition(type: (j['type'] ?? 'fade') as String, duration: _d(j['duration']) ?? 0.5);
}

class Clip {
  String source;
  double start;
  double? end;
  double? duration; // só fotos
  double speed;
  double volume;
  bool kenBurns;
  Transition? transition;
  // Duração do arquivo de origem (s), lida por vb_media_probe. Só no app; não vai para o servidor.
  double? sourceDuration;

  Clip({
    required this.source,
    this.start = 0,
    this.end,
    this.duration,
    this.speed = 1,
    this.volume = 1,
    this.kenBurns = false,
    this.transition,
    this.sourceDuration,
  });

  bool get isImage => kImageExt.contains(extOf(source));

  /// Duração do clipe na linha do tempo final (mesma conta de edl.clip_length). null = desconhecida.
  double? get length {
    if (isImage) return duration ?? 3.0;
    var e = end ?? sourceDuration;
    if (e == null) return null;
    if (sourceDuration != null && e > sourceDuration!) e = sourceDuration!;
    final l = (e - start) / speed;
    return l > 0 ? l : 0;
  }

  Map<String, dynamic> toJson() {
    final m = <String, dynamic>{'source': source};
    if (isImage) {
      m['duration'] = duration ?? 3.0;
      if (kenBurns) m['ken_burns'] = true;
    } else {
      if (start > 0) m['start'] = start;
      if (end != null) m['end'] = end;
      if (speed != 1) m['speed'] = speed;
    }
    if (volume != 1) m['volume'] = volume;
    if (transition != null) m['transition'] = transition!.toJson();
    return m;
  }

  Map<String, dynamic> toStorage() => {...toJson(), if (sourceDuration != null) '_source_duration': sourceDuration};

  factory Clip.fromJson(Map<String, dynamic> j) => Clip(
        source: j['source'] as String,
        start: _d(j['start']) ?? 0,
        end: _d(j['end']),
        duration: _d(j['duration']),
        speed: _d(j['speed']) ?? 1,
        volume: _d(j['volume']) ?? 1,
        kenBurns: (j['ken_burns'] ?? false) as bool,
        transition: j['transition'] == null ? null : Transition.fromJson(Map<String, dynamic>.from(j['transition'] as Map)),
        sourceDuration: _d(j['_source_duration']),
      );

  Clip copy() => Clip.fromJson(toStorage());
}

class TextOverlay {
  String text;
  double start;
  double end;
  String position;
  String size;
  String style;
  String font;
  String color;
  String animation;

  TextOverlay({
    required this.text,
    required this.start,
    required this.end,
    this.position = 'bottom',
    this.size = 'medium',
    this.style = 'box',
    this.font = 'classica',
    this.color = '#FFFFFF',
    this.animation = 'none',
  });

  Map<String, dynamic> toJson() => {
        'text': text,
        'start': start,
        'end': end,
        'position': position,
        'size': size,
        'style': style,
        'font': font,
        'color': color,
        'animation': animation,
      };

  factory TextOverlay.fromJson(Map<String, dynamic> j) => TextOverlay(
        text: j['text'] as String,
        start: _d(j['start']) ?? 0,
        end: _d(j['end']) ?? 2,
        position: (j['position'] ?? 'bottom') as String,
        size: (j['size'] ?? 'medium') as String,
        style: (j['style'] ?? 'box') as String,
        font: (j['font'] ?? 'classica') as String,
        color: (j['color'] ?? '#FFFFFF') as String,
        animation: (j['animation'] ?? 'none') as String,
      );
}

class Music {
  String source;
  double volume;
  double start;
  bool ducking;
  bool loop;
  Music({required this.source, this.volume = 0.25, this.start = 0, this.ducking = true, this.loop = true});

  Map<String, dynamic> toJson() =>
      {'source': source, 'volume': volume, 'start': start, 'ducking': ducking, 'loop': loop};
  factory Music.fromJson(Map<String, dynamic> j) => Music(
        source: j['source'] as String,
        volume: _d(j['volume']) ?? 0.25,
        start: _d(j['start']) ?? 0,
        ducking: (j['ducking'] ?? true) as bool,
        loop: (j['loop'] ?? true) as bool,
      );
}

class Subtitles {
  String source;
  String size;
  Subtitles({required this.source, this.size = 'normal'});
  Map<String, dynamic> toJson() => {'source': source, 'size': size};
  factory Subtitles.fromJson(Map<String, dynamic> j) =>
      Subtitles(source: j['source'] as String, size: (j['size'] ?? 'normal') as String);
}

class ColorGrade {
  double brightness;
  double contrast;
  double saturation;
  double warmth;
  ColorGrade({this.brightness = 0, this.contrast = 1, this.saturation = 1, this.warmth = 0});

  bool get isNeutral => brightness == 0 && contrast == 1 && saturation == 1 && warmth == 0;

  Map<String, dynamic> toJson() =>
      {'brightness': brightness, 'contrast': contrast, 'saturation': saturation, 'warmth': warmth};
  factory ColorGrade.fromJson(Map<String, dynamic> j) => ColorGrade(
        brightness: _d(j['brightness']) ?? 0,
        contrast: _d(j['contrast']) ?? 1,
        saturation: _d(j['saturation']) ?? 1,
        warmth: _d(j['warmth']) ?? 0,
      );
}

class Output {
  String name;
  String? folder;
  String aspect;
  int height;
  int fps;
  String fit;
  double? loudness;
  double fadeIn;
  double fadeOut;

  Output({
    this.name = 'video',
    this.folder,
    this.aspect = '16:9',
    this.height = 1080,
    this.fps = 30,
    this.fit = 'crop',
    this.loudness = -14,
    this.fadeIn = 0,
    this.fadeOut = 0,
  });

  Map<String, dynamic> toJson() => {
        'name': name,
        if (folder != null && folder!.trim().isNotEmpty) 'folder': folder!.trim(),
        'aspect': aspect,
        'height': height,
        'fps': fps,
        'fit': fit,
        'loudness': loudness,
        'fade_in': fadeIn,
        'fade_out': fadeOut,
      };

  factory Output.fromJson(Map<String, dynamic> j) => Output(
        name: (j['name'] ?? 'video') as String,
        folder: j['folder'] as String?,
        aspect: (j['aspect'] ?? '16:9') as String,
        height: (j['height'] ?? 1080) as int,
        fps: (j['fps'] ?? 30) as int,
        fit: (j['fit'] ?? 'crop') as String,
        loudness: j.containsKey('loudness') ? _d(j['loudness']) : -14,
        fadeIn: _d(j['fade_in']) ?? 0,
        fadeOut: _d(j['fade_out']) ?? 0,
      );
}

class EditPlan {
  Output output;
  List<Clip> clips;
  List<TextOverlay> texts;
  Music? music;
  Subtitles? subtitles;
  ColorGrade? color;

  EditPlan({Output? output, List<Clip>? clips, List<TextOverlay>? texts, this.music, this.subtitles, this.color})
      : output = output ?? Output(),
        clips = clips ?? [],
        texts = texts ?? [];

  /// JSON aceito por vb_render_start.
  Map<String, dynamic> toJson() => {
        'output': output.toJson(),
        'clips': clips.map((c) => c.toJson()).toList(),
        'texts': texts.map((t) => t.toJson()).toList(),
        if (music != null) 'music': music!.toJson(),
        if (subtitles != null) 'subtitles': subtitles!.toJson(),
        if (color != null && !color!.isNeutral) 'color': color!.toJson(),
      };

  /// JSON salvo no aparelho (inclui dados só do app, como a duração das mídias).
  Map<String, dynamic> toStorage() => {...toJson(), 'clips': clips.map((c) => c.toStorage()).toList(),
        if (color != null) 'color': color!.toJson()};

  factory EditPlan.fromJson(Map<String, dynamic> j) => EditPlan(
        output: j['output'] == null ? null : Output.fromJson(Map<String, dynamic>.from(j['output'] as Map)),
        clips: ((j['clips'] ?? []) as List).map((e) => Clip.fromJson(Map<String, dynamic>.from(e as Map))).toList(),
        texts: ((j['texts'] ?? []) as List)
            .map((e) => TextOverlay.fromJson(Map<String, dynamic>.from(e as Map)))
            .toList(),
        music: j['music'] == null ? null : Music.fromJson(Map<String, dynamic>.from(j['music'] as Map)),
        subtitles:
            j['subtitles'] == null ? null : Subtitles.fromJson(Map<String, dynamic>.from(j['subtitles'] as Map)),
        color: j['color'] == null ? null : ColorGrade.fromJson(Map<String, dynamic>.from(j['color'] as Map)),
      );
}

/// Resultado da conta da linha do tempo (mesma lógica de edl.timeline no servidor).
class TimelineInfo {
  final List<double?> starts;
  final double? total;
  final List<String> problems;
  TimelineInfo(this.starts, this.total, this.problems);
}

TimelineInfo computeTimeline(EditPlan plan) {
  final starts = <double?>[];
  final problems = <String>[];
  double? total = 0;
  for (var i = 0; i < plan.clips.length; i++) {
    final clip = plan.clips[i];
    final length = clip.length;
    double overlap = 0;
    if (i > 0 && clip.transition != null) {
      overlap = clip.transition!.duration;
      final prev = plan.clips[i - 1].length;
      if (prev != null && length != null) {
        final limit = (prev < length ? prev : length) - 0.1;
        if (overlap > limit) {
          problems.add('Transição antes do clipe ${i + 1} (${overlap.toStringAsFixed(1)} s) é maior que um dos '
              'clipes vizinhos.');
        }
      }
    }
    final next = i + 1 < plan.clips.length ? plan.clips[i + 1].transition : null;
    final both = overlap + (next?.duration ?? 0);
    if (length != null && both > length - 0.1) {
      problems.add('Clipe ${i + 1} (${length.toStringAsFixed(1)} s) é curto demais para as transições de entrada e '
          'saída (${both.toStringAsFixed(1)} s).');
    }
    if (!clip.isImage && clip.end != null && clip.end! <= clip.start) {
      problems.add('Clipe ${i + 1}: o fim precisa ser maior que o início.');
    }
    if (total == null || length == null) {
      starts.add(null);
      total = null;
      continue;
    }
    final s = total - overlap;
    starts.add(double.parse(s.toStringAsFixed(3)));
    total = s + length;
  }
  if (plan.clips.isEmpty) problems.add('Adicione pelo menos um clipe.');
  if (total != null) {
    for (final t in plan.texts) {
      if (t.end <= t.start) problems.add('Texto "${t.text}": o fim precisa ser maior que o início.');
      if (t.start >= total) problems.add('Texto "${t.text}" começa depois do fim do vídeo.');
    }
  }
  return TimelineInfo(starts, total == null ? null : double.parse(total.toStringAsFixed(3)), problems);
}

String fmtSeconds(double? s) {
  if (s == null) return '?';
  final m = s ~/ 60;
  final r = s - m * 60;
  return m > 0 ? '$m min ${r.toStringAsFixed(1)} s' : '${r.toStringAsFixed(1)} s';
}
