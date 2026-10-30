---
description: Один раз подготовить базу разработки к работе агента (расширение mcp-1c, веб-публикация, YAxUnit, расширение с тестами)
---

Подготовь базу `dev` из `.v8-project.json` к конвейеру `/1c-task`. Выполняй шаги по порядку, после каждого коротко пиши результат. Если шаг уже сделан, проверь это и пропусти его. Перед шагами, которые меняют базу (3, 5, 6), попроси пользователя закрыть все сеансы этой базы и дождись подтверждения.

1. **Конфиги.** Проверь, что есть `.mcp.json`, `.v8-project.json` и `tools/metr.yml`. Если чего-то нет, остановись и попроси запустить `powershell -ExecutionPolicy Bypass -File setup\install.ps1`.

2. **Выгрузка.** Если в `src/cf` нет `Configuration.xml`, выгрузи конфигурацию навыком `/db-dump-xml dev`.

3. **Расширение mcp-1c** (HTTP-сервис, через который агент читает метаданные и выполняет запросы). Проверь в `/db-cfe-admin`, есть ли расширение `mcp-1c` в базе. Если нет, установи его:
   - файловая база: `tools\mcp-1c.exe --install "<path>" --platform "<v8path>\1cv8.exe"`;
   - серверная: `tools\mcp-1c.exe --install "<server>\<ref>" --server --db-user <user> --db-password <password> --platform "<v8path>\1cv8.exe"`.
   Значения возьми из `.v8-project.json`.

4. **Публикация.** Опубликуй базу навыком `/web-publish dev`. Имя публикации и порт возьми из `webUrl` в `.v8-project.json` (`http://localhost:<порт>/<имя>`). Проверь, что `<webUrl>/hs/mcp-1c` отвечает по HTTP (любой ответ, кроме ошибки соединения и 404 на уровне Apache).

5. **YAxUnit.** Если расширения `YAxUnit` в базе нет:
   - `/db-load-cf tools\yaxunit.cfe dev -Extension YAxUnit`;
   - `/db-update dev -Extension YAxUnit`;
   - `/db-cfe-admin set-properties dev -Name YAxUnit -SafeMode off -UnsafeActionProtection off`.

6. **Расширение с тестами.** Имя возьми из `testsExtension` в `config/radar.json` (по умолчанию `Tests`). Если в `src/cfe/<имя>` нет исходников:
   - создай расширение навыком `/cfe-init` в каталоге `src/cfe/<имя>` с префиксом `тст_`;
   - добавь общий модуль `тст_ПримерТестов` с одним тестом YAxUnit: регистрация в `ИсполняемыеСценарии()` и проверка `ЮТест.ОжидаетЧто(1 + 1).Равно(2)`;
   - загрузи его в базу: `/db-load-xml dev -Extension <имя>`, затем `/db-update dev -Extension <имя>`;
   - сними безопасный режим: `/db-cfe-admin set-properties dev -Name <имя> -SafeMode off -UnsafeActionProtection off`;
   - перегенерируй конфиги, чтобы тесты попали в METR: `powershell -ExecutionPolicy Bypass -File setup\install.ps1 -ConfigOnly`.

7. **Итог.** Напиши, что сделано и что не получилось. Попроси пользователя перезапустить Claude Code (MCP-серверы перечитают `.mcp.json`) и после перезапуска выполнить проверку связи:
   - `onec-base`: `get_configuration_info`;
   - `onec-help`: поиск `СтрНайти`;
   - `onec-tests`: `check_platform`, затем `run_all_tests` (должен пройти пример теста);
   - `bsl-check`: диагностика любого модуля из `src/cf`.
