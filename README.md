# hermes-skill-video-summary

Скилл [Hermes Agent](https://hermes-agent.nousresearch.com/docs) «о чём видео»: по ссылке на YouTube (или любой сайт, поддерживаемый yt-dlp) скачивает аудио, транскрибирует его локально и возвращает плотный пересказ, начинающийся с исходной ссылки.

Это **оркестратор** над двумя другими скиллами, порядок строгий:

1. [`media/yt-dlp`](https://github.com/vokasug/hermes-skill-yt-dlp) — метаданные + скачивание аудио в `~/result-yt-dlp/`
2. [`media/mlx-whisper`](https://github.com/vokasug/hermes-skill-mlx-whisper) — локальная транскрибация (MLX Whisper + Silero VAD + коррекция терминов основной моделью) в `~/result-mlx-whisper/`

## Что делает

- **Метаданные до скачивания** — заголовок, автор, длительность, описание через `yt-dlp --skip-download --print`
- **Гейт языка** — язык определяется из заголовка/описания (или детектом на первых 30 с) ДО запуска транскрибации; источник языка называется явно. Дефолт «ru по привычке» запрещён — главный pitfall скилла (инцидент: 39-мин английское видео прогнали с `--language ru` → каша и полный перезапуск)
- **`--terms` из заголовка/описания** — имена и термины передаются в коррекцию mlx-whisper для канонического написания
- **Субтитры как «второе мнение»** — всегда пытается скачать субтитры контента (`--write-subs --write-auto-subs`); если есть, они идут в коррекцию mlx-whisper как второй ASR-текст + источник авто-терминов (чинит ослышки имён/терминов; числа защищены гейтом в коде)
- **Первая строка ответа — исходная ссылка** дословно, чтобы пересказ однозначно привязывался к присланному контенту
- **Пересказ по смысловым блокам** — короткие абзацы/список без таймкодов, живым языком; выводы автора отмечены отдельно от собственных; таймкоды — только в ответах на доп. вопросы (цитаты из транскрипта)
- **Честность по распознаванию** — если имена/термины в транскрипте ненадёжны, это сказано прямо с указанием затронутых фрагментов
- **Переиспользование артефактов** — mp3 и MD остаются на диске; доп. вопросы по видео позже отвечаются по сохранённому транскрипту без повторной транскрибации

## Установка на чистый Mac

### 1. Зависимости — оба скилла-компонента

Ставятся вместе со своими зависимостями (ffmpeg, node, uv-инструмент mlx-whisper, модель whisper-podlodka-turbo q8):

```bash
git clone https://github.com/vokasug/hermes-skill-yt-dlp ~/.hermes/skills/media/yt-dlp
git clone https://github.com/vokasug/hermes-skill-mlx-whisper ~/.hermes/skills/media/mlx-whisper
```

### 2. Этот скилл

```bash
git clone https://github.com/vokasug/hermes-skill-video-summary ~/.hermes/skills/video-summary
```

Hermes подхватывает скилл автоматически; проверить: `hermes skills list`.

### 3. Проверка

```bash
# метаданные должны вернуться без скачивания
~/.local/bin/yt-dlp --js-runtimes node --skip-download \
  --print "%(title)s | %(duration)s сек" "https://www.youtube.com/watch?v=VIDEO_ID"
```

Затем в Hermes: «о чём это видео? <ссылка>» — скилл сработает по триггеру.

## Использование

Ручной прогон полного пайплайна (если нужно без агента):

```bash
# 1. метаданные + детект языка
~/.local/bin/yt-dlp --js-runtimes node --skip-download \
  --print "%(title)s | %(uploader)s | %(duration)s сек | %(description).500B" <URL>

# 2. аудио в result-yt-dlp
python3 ~/.hermes/skills/media/yt-dlp/scripts/download_dated.py --audio <URL>

# 2b. субтитры (если есть — ручные или auto; не скачались — не страшно)
~/.local/bin/yt-dlp --js-runtimes node --skip-download --write-subs --write-auto-subs \
  --sub-langs "<lang>.*,<lang>" --sub-format "srt/vtt/best" \
  -o "/tmp/subs/%(title).100B.%(ext)s" --no-playlist <URL>

# 3. транскрибация в result-mlx-whisper (язык — из шага 1!)
~/.local/share/uv/tools/mlx-whisper/bin/python \
  ~/.hermes/skills/media/mlx-whisper/scripts/vad_transcribe.py "<mp3>" \
  --language <detected> --terms "<имена из заголовка/описания>" \
  --subs "/tmp/subs/<файл субтитров>.srt"   # если шаг 2b дал файл
```

Длинные файлы — через `terminal(background=true)` + `process wait` (~5 мин на 40-мин аудио). Если скрипт напечатал строку `PAYLOAD <путь>` — коррекция выполняется агентом: прочитать payload, записать исправленный `base_text` в `<имя>.corrected.txt`, затем `vad_transcribe.py --apply-corrections <payload> <corrected.txt>`.

## Настройка под себя

Скилл не содержит скриптов — только `SKILL.md` с процедурой. Пути `~/result-yt-dlp` / `~/result-mlx-whisper` и расположение моделей наследуются от скиллов-компонентов; на своём Mac настройте их по README тех репозиториев. Внешние API и ключи для коррекции не нужны — советчиком выступает основная модель агента.

## Структура репозитория

```
├── README.md     # этот файл
├── LICENSE       # MIT
└── SKILL.md      # скилл: frontmatter + процедура оркестрации для агента
```

## Лицензия

MIT — см. [LICENSE](LICENSE).
