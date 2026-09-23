# Пользовательские вложения

`AttachmentService` — единая точка валидации и извлечения. Он возвращает `AttachmentResult` с именем файла, проверенным MIME type, типом документа, текстом, таблицами, предупреждениями и metadata. Результат не передаётся в LLM на этом этапе.

## API

`POST /api/attachments` принимает multipart поле `file` и возвращает извлечённый результат. Файл читается потоково чанками по 64 KiB, ограничивается до `ATTACHMENT_MAX_BYTES` и закрывается в `finally`. Файлы на постоянное или временное хранилище сервис не записывает, поэтому после обработки удалять нечего.

Поддерживаются только PDF, DOCX, XLSX, JPEG/JPG и PNG. `.doc` и `.xls` дают ответ `415 unsupported_attachment`.

Проверка состоит из трёх частей: безопасное имя/разрешённое расширение, declared MIME type от multipart и фактический формат по сигнатуре/контейнеру. Совпадения только по расширению недостаточно. PDF проверяется по `%PDF-`, DOCX/XLSX — по OOXML ZIP-контейнеру, изображения — через Pillow verify.

## Pipeline форматов

### PDF

`PdfExtractor` открывает документ через `pypdf.PdfReader`, извлекает текст по страницам и возвращает page count. PDF с очень коротким текстом получает warning `pdf_may_require_ocr`; пустой или сканированный PDF — `empty_document`. OCR PDF намеренно не выполняется в первой версии.

### DOCX

`DocxExtractor` использует `python-docx`: объединяет непустые абзацы в `text`, а таблицы возвращает как массив `ExtractedTable`. Повреждённый ZIP/документ даёт контролируемую ошибку обработки.

### XLSX

`XlsxExtractor` сначала ограничивает ZIP-контейнер по числу entries и суммарному распакованному размеру, затем использует `openpyxl.load_workbook(read_only=True, data_only=True)`. Лимиты листов, строк и колонок задаются environment variables. Если лист обрезан, результат содержит warning `xlsx_sheet_truncated:<sheet>`.

### JPEG и PNG

`ImageOcrExtractor` проверяет изображение Pillow, ограничивает число пикселей и вызывает `pytesseract.image_to_string`. При недоступном или ошибочном Tesseract возвращается корректный результат с `ocr_failed`; endpoint не падает. В runtime-образе для реального OCR должен быть установлен системный пакет `tesseract-ocr` и языковые данные.

## Environment variables

- `ATTACHMENT_MAX_BYTES` — максимальный размер загрузки; по умолчанию 10 MiB.
- `ATTACHMENT_MAX_XLSX_SHEETS` — максимум листов; по умолчанию 20.
- `ATTACHMENT_MAX_XLSX_ROWS` — максимум строк на лист; по умолчанию 10 000.
- `ATTACHMENT_MAX_XLSX_COLUMNS` — максимум колонок на лист; по умолчанию 100.
# Вложения

Нормализованный результат, привязанный к chat session, хранится не дольше `ATTACHMENT_TTL_SECONDS` (по умолчанию 24 часа). Исходные байты файлов не сохраняются. Для удаления истёкших данных используйте `python -m app.maintenance`.
