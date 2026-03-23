"""
MAX (VK Teams) bot — stub.

Общая бизнес-логика (call_parse, call_export, format_summary) находится
в bots/common.py. При реализации MAX-бота достаточно подключить
нужный транспорт и вызвать те же функции.
"""

# TODO: импортировать max-botapi-python или maxapi после верификации ООО
# TODO: считать MAX_TOKEN из bots.config
# TODO: реализовать обработчик /start — отправить приветствие и get_export_help_text()
# TODO: реализовать обработчик фото — скачать файл, вызвать call_parse, показать format_summary
# TODO: добавить инлайн-кнопки для экспорта (xlsx / csv / help)
# TODO: реализовать callback-обработчики экспорта через call_export
# TODO: добавить fallback-обработчик для текстовых сообщений
