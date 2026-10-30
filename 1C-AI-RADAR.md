# 1С × ИИ: радар инструментов

Срез на 30.10.2026. Что облегчает работу 1С-разработчика с LLM: MCP-серверы, skills и правила для агентов, официальные сервисы, бенчмарки, статьи, курсы, сообщества.

Статусы и звёзды в разделах MCP и skills взяты из каталога [Untru/1c-mcp](https://github.com/Untru/1c-mcp). Лицензии и актуальность каждого репозитория отдельно не проверялись: перед внедрением откройте README.

---

## С чего начать: рабочая связка

| Задача | Что взять |
|---|---|
| Агент | Claude Code, Cursor или Codex (по бенчмаркам 2026 лидируют модели Claude Opus) |
| Знания о 1С для агента | [cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills) или [ai_rules_1c](https://github.com/comol/ai_rules_1c) |
| Справка платформы (чтобы не выдумывал методы) | [mcp-bsl-platform-context](https://github.com/alkoleft/mcp-bsl-platform-context) |
| Код и метаданные конфигурации | [mcp-1c](https://github.com/feenlace/mcp-1c); для огромных конфигураций [rlm-tools-bsl](https://github.com/Dach-Coin/rlm-tools-bsl) |
| Проверка кода | [bsl-analyzer](https://github.com/itrous/bsl-analyzer) или [mcp-bsl-lsp-bridge](https://github.com/SteelMorgan/mcp-bsl-lsp-bridge) |
| Сборка и тесты | [mcp-onec-test-runner](https://github.com/alkoleft/mcp-onec-test-runner) (YAxUnit, синтакс-контроль) |
| Работа в EDT | [EDT-MCP](https://github.com/DitriXNew/EDT-MCP) |

Связку рекомендует каталог Untru. Её подтверждает опыт на Хабре: MCP со справкой и метаданными убирает грубые ошибки агента ([статья](https://habr.com/ru/articles/1012680/)).

---

## Каталоги-агрегаторы

- [Untru/1c-mcp](https://github.com/Untru/1c-mcp): главный awesome-список MCP и AI-инструментов для 1С, около 65 позиций, CC0. Здесь лучше всего следить за новинками.

## Официальное от фирмы «1С»

- **1С:Напарник для разработки**: ИИ-ассистент в 1С:EDT (генерация, ревью, рефакторинг, агентный режим). [Страница на портале ИТС](https://portal.1c.ru/applications/1C-Second-Pilot). Срок бесплатного доступа для ИТС источники называют по-разному: до 1.10.2026 или до 1.12.2026. Проверьте на ИТС.
- **1С:Напарник ИТС**: ответы по материалам its.1c.ru.
- Прикладные ИИ-сервисы: 1С:Распознавание первичных документов, распознавание и синтез речи, 1С:Универсальное прогнозирование, 1С:Прогнозирование продаж ([обзор](https://www.klerk.ru/blogs/rgsoft/710394/)).
- В Конфигураторе официального ИИ-помощника нет. Встроенный LLM-механизм в платформе 8.5 официально не подтверждён.

## Помощники в Конфигураторе и IDE

- [Confaster](https://confaster.ru/): ИИ-агент прямо в Конфигураторе, сам открывает модуль и правит код ([инструкция](https://infostart.ru/public/2735405/)).
- [mini-ai-1c](https://github.com/hawkxtreme/mini-ai-1c): десктопный помощник для Конфигуратора, чат и анализ BSL.
- [CodePilot1C](https://github.com/ondysss/codepilot1c-edt): ассистент внутри EDT, агентный режим и MCP Host.
- [BslEdit](https://github.com/alonehobo/BslEdit): лёгкий редактор BSL с MCP для агента (Windows).
- [1C: Platform Tools MCP](https://github.com/yellow-hammer/mcp-1c-platform-tools) и [Skills](https://marketplace.visualstudio.com/items?itemName=yellow-hammer.1c-platform-tools) для VS Code.
- Интеграции с 1C:EDT: [EDT-MCP](https://github.com/DitriXNew/EDT-MCP), [edt-bridge](https://github.com/keyfire/edt-bridge), [AI-EDT](https://github.com/Desko77/ai-edt), [1C_EDT_MCP_PUBLIC](https://github.com/fedukhin-sys/1C_EDT_MCP_PUBLIC) (106 инструментов, без лицензии).

## Skills, правила, субагенты

- [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills): полный цикл: обработки, отчёты, формы, роли, XML-форматы, тесты через веб-клиент. Claude Code, Cursor, Codex. Это оригинал, у проекта много форков.
- [comol/ai_rules_1c](https://github.com/comol/ai_rules_1c): правила, 13 субагентов, skills для 11+ агентов.
- [Desko77/claude-code-skills-1c](https://github.com/Desko77/claude-code-skills-1c): 117+ skills, генерация исходников 1С из JSON без Конфигуратора. Версия для Cursor: [cursor-1c-skills](https://github.com/Desko77/cursor-1c-skills).
- [IngvarConsulting/unica](https://github.com/IngvarConsulting/unica): плагин для Claude Code и Codex, skills и свой MCP runtime.
- [Pradushkoai/1c-ai-dev-env](https://github.com/Pradushkoai/1c-ai-dev-env): 261 правило стандартов, AGENTS.md, MCP.
- [SandersNeo/cursor_rules_1c](https://github.com/SandersNeo/cursor_rules_1c): правила и роли для Cursor.

## MCP: код и метаданные конфигурации

- [feenlace/mcp-1c](https://github.com/feenlace/mcp-1c): один Go-бинарник, живая база и поиск по выгрузке, 19 инструментов ([статья](https://infostart.ru/1c/articles/2635907/)).
- [Dach-Coin/rlm-tools-bsl](https://github.com/Dach-Coin/rlm-tools-bsl): токен-эффективный анализ огромных конфигураций, SQLite-индекс, CF/EDT/CFE.
- [Regsorm/code-index-mcp](https://github.com/Regsorm/code-index-mcp): быстрый индекс на Rust, 32 инструмента.
- [Arman-Kudaibergenov/bsl-atlas](https://github.com/Arman-Kudaibergenov/bsl-atlas): векторный и структурный поиск, граф вызовов.
- [axel-avb/mcp-1c-metadata](https://github.com/axel-avb/mcp-1c-metadata): семантический поиск, граф вызовов, досье объектов.
- [gyrfalcon](https://github.com/aleksandrgradoboev-svg/gyrfalcon): детерминированный индекс конфигурации.
- [ROCTUP/1c-mcp-metacode](https://github.com/ROCTUP/1c-mcp-metacode): конфигурация как граф в Neo4j.
- [alkoleft/bsl-graph](https://github.com/alkoleft/bsl-graph): граф знаний в NebulaGraph.
- Старее, давно не обновлялись: [mcp-1c-v1](https://github.com/FSerg/mcp-1c-v1), [1C_MCP_metadata](https://github.com/artesk/1C_MCP_metadata).
- Шаблоны кода: [1c-templates-mcp](https://github.com/Desko77/1c-templates-mcp), 2200+ шаблонов BSL с семантическим поиском.

## MCP: справка платформы (синтакс-помощник)

- [alkoleft/mcp-bsl-platform-context](https://github.com/alkoleft/mcp-bsl-platform-context): нечёткий поиск по типам и методам из установленной платформы.
- [Desko77/mcp-bsl-platform-help-context](https://github.com/Desko77/mcp-bsl-platform-help-context): Python-порт с гибридным поиском и стандартами.
- [rzateev/onec-help-mcp](https://github.com/rzateev/onec-help-mcp): несколько версий платформы, BM25 и семантический поиск.
- [Regsorm/bsl-context](https://github.com/Regsorm/bsl-context): справка и проверка существования методов.
- [sergeyfedyakov/v8help-mcp](https://github.com/sergeyfedyakov/v8help-mcp): индекс .hbk, конвертация в Markdown.
- [Antonio1C/1c-syntax-helper-mcp](https://github.com/Antonio1C/1c-syntax-helper-mcp): справка на Elasticsearch для всей команды.
- [lyzhenko/mcp-1c](https://github.com/lyzhenko/mcp-1c): справка API и разбор выгрузки.

## Проверка кода и тесты

- [itrous/bsl-analyzer](https://github.com/itrous/bsl-analyzer): линтер, LSP и MCP на Rust, 180 диагностик.
- [SteelMorgan/mcp-bsl-lsp-bridge](https://github.com/SteelMorgan/mcp-bsl-lsp-bridge): мост к BSL Language Server (навигация, диагностики, рефакторинг).
- [phsin/mcp-bsl-ls](https://github.com/phsin/mcp-bsl-ls), [fserg/1c-lsp-mcp-skill](https://github.com/fserg/1c-lsp-mcp-skill), [SteelMorgan/bsl-syntax-checker](https://github.com/SteelMorgan/bsl-syntax-checker).
- [alkoleft/mcp-onec-test-runner](https://github.com/alkoleft/mcp-onec-test-runner): сборка ИБ (DESIGNER/IBCMD), YAxUnit, выгрузка конфигурации.
- UI-тесты: [ROCTUP/1c-testpilot](https://github.com/ROCTUP/1c-testpilot) (агент кликает по интерфейсу через клиент тестирования), [qa-mcp](https://github.com/vlikhobabin/qa-mcp-public) (эксперимент).
- ИИ-ревью PR: [rdv-team/ai-review](https://github.com/rdv-team/ai-review) (BSL-модули и запросы СКД); схемы для CI: [ReVu](https://habr.com/en/articles/954860), [ИИ-ревьюер в CI](https://habr.com/ru/articles/1045272/).

## MCP к живой базе и данным

- [vladimir-kharin/1c_mcp](https://github.com/vladimir-kharin/1c_mcp): фреймворк MCP-сервера внутри базы (расширение .cfe).
- [ROCTUP/1c-mcp-toolkit](https://github.com/ROCTUP/1c-mcp-toolkit): HTTP-сервер во внешней обработке, без изменения конфигурации.
- [onec-client-mcp-devkit](https://github.com/1c-neurofish/onec-client-mcp-devkit), [v8-session-manager](https://github.com/1c-neurofish/v8-session-manager).
- [theYahia/aprovodka](https://github.com/theYahia/aprovodka): чтение и запись учёта через OData, 34 инструмента.
- [prepod2003/mcp-rsv-data](https://github.com/prepod2003/mcp-rsv-data): вопросы на естественном языке к рабочей базе, только чтение, обезличивание.
- [infaton/MCP35](https://github.com/infaton/MCP35): MCP на стороне 1С:ERP, 90+ инструментов.

## 1С:Напарник из сторонних агентов

- [Desko77/1c-ai-mcp](https://github.com/Desko77/1c-ai-mcp): Напарник как MCP (ревью, переписывание, поиск по ИТС), нужна подписка ИТС.
- [ROCTUP/1c-buddy](https://github.com/ROCTUP/1c-buddy): веб-чат, MCP и OpenAI-совместимый шлюз к Напарнику.
- [SteelMorgan/spring-mcp-1c-copilot](https://github.com/SteelMorgan/spring-mcp-1c-copilot).

## Вызов LLM из кода 1С (ИИ в самой базе)

- [andromanpro/1c-ai-connector](https://github.com/andromanpro/1c-ai-connector) (ИИкона): OpenAI, Anthropic, Gemini, YandexGPT, GigaChat; function calling, RAG, MCP, MIT.
- [SgonnovDmGit/lensa-assistant-1c](https://github.com/SgonnovDmGit/lensa-assistant-1c): ассистент в базе, бесплатная .epf.
- [SalavatovNabiulla/GigaChat_SDK_1C](https://github.com/SalavatovNabiulla/GigaChat_SDK_1C): библиотека для GigaChat.
- [vbondarevsky/Connector](https://github.com/vbondarevsky/Connector): HTTP-клиент для 1С, на нём легко написать обёртку под любой API.
- Локальные модели через Ollama ([пример подключения](https://infostart.ru/1c/articles/2358590/)). [Дообучение Qwen под 1С](https://infostart.ru/1c/articles/2753290/).

## Инфраструктура

- [alkoleft/v8-runner-rust](https://github.com/alkoleft/v8-runner-rust): сборка, ИБ и тесты по одному YAML.
- [SteelMorgan/1c-log-checker](https://github.com/SteelMorgan/1c-log-checker): журнал регистрации и ТЖ в ClickHouse и Grafana для агента.
- [SteelMorgan/1c-ai-sandbox-client-server](https://github.com/SteelMorgan/1c-ai-sandbox-client-server): Docker-песочница 1С для экспериментов агента.
- [pravets/compose4mcp](https://github.com/pravets/compose4mcp): Docker Compose для набора MCP-серверов.

## 1C:Element (неофициальное)

- [keyfire/elemctl](https://github.com/keyfire/elemctl), [keyfire/xbsl](https://github.com/keyfire/xbsl) (линтер, LSP и MCP для XBSL), [korolevpavel/xbsl-ai-skills](https://github.com/korolevpavel/xbsl-ai-skills).

## Коммерческое

| Продукт | Что это |
|---|---|
| [one-s-mcp](https://onesmcp.ru) | Десктоп-приложение с MCP, локально, бета бесплатно |
| [OneMCP](https://onemcp.ru) | SaaS-поиск по метаданным и коду для команды, бета |
| [OneRPA MCP Suite](https://docs.onerpa.ru/mcp-servery-1c) | Набор Docker-серверов: справка, метаданные, формы |
| [Pilot 1C](https://infostart.ru/marketplace/2787345/) | Помощник от Инфостарта, тесты в Vanessa Automation, от 18 300 ₽/мес |
| [Codex для 1С](https://infostart.ru/journal/news/mir-1s/codex-dlya-1s-ii-pomoshchnik-nauchili-rabotat-s-dannymi-informatsionnykh-baz_2754724/) | Агент по данным нескольких ИБ |
| [My1cMCP](https://infostart.ru/public/2782550/) | MCP на 22 функции, 2 500 ₽ |
| [ARQA MCP](https://arqa.cc/ru/mcp-server) | On-premise MCP для бизнес-задач |

## Бенчмарки: какая модель лучше пишет на 1С

- [PRISM](https://prism.genlab-1c.ru/) ([репозиторий](https://github.com/genlab-1c/prism)): исполняемый бенчмарк, 65 моделей, 4 оси оценки.
- [1C Code Bench](https://1cbench.github.io/): от Sber AI (GigaCode R&D). [Статья «спустя 5 месяцев»](https://habr.com/ru/companies/sberbank/articles/1038352/).
- [Бенчмарк v2 vibecoding1c](https://habr.com/ru/articles/1063244/), серия на Хабре [«Лучшие нейросети для вайбкодинга на 1С»](https://habr.com/ru/articles/971106/).
- [ИИ-инструменты на исполняемом бенчмарке, 35 задач](https://infostart.ru/1c/articles/2794367/): Напарник решил 31 из 35.
- [Методика выбора LLM для 1С](https://infostart.ru/1c/articles/2518237/).

## Базовый тулчейн (без него агенту тяжело)

- [BSL Language Server](https://github.com/1c-syntax/bsl-language-server), [Language 1C (BSL) для VS Code](https://github.com/1c-syntax/vsc-language-1c-bsl).
- [OneScript](https://github.com/EvilBeaver/OneScript), [gitsync](https://github.com/oscript-library/gitsync).
- [YAxUnit](https://github.com/bia-technologies/yaxunit), [Vanessa Automation](https://github.com/Pr-Mex/vanessa-automation).

## Статьи, которые стоит прочитать

- [Полный cookbook «Разработка в 1С на ИИ-агентах»](https://infostart.ru/public/2773406/)
- [Вайбкодинг в 1С: ускорение в 4–6 раз (Claude Code + MCP)](https://habr.com/ru/articles/1012680/)
- [Как использовать ИИ 1С-разработчику в июле 2026](https://infostart.ru/1c/articles/2737253/)
- [Влияние ИИ на разработку 1С: что изменилось к 2026](https://infostart.ru/1c/articles/2727152/)
- [Как собрать агента, который выгружает конфигурацию, правит код и запускает проверку](https://infostart.ru/public/2662176/)
- [ИИ-агенты в 1С без магии](https://infostart.ru/1c/articles/2732103/)
- [Claude Code с бесплатными моделями через Claude Code Router](https://infostart.ru/1c/articles/2650687/)
- [Бесплатный вайбкодинг через MCP](https://infostart.ru/1c/articles/2605838/)
- [1С:Напарник. Стоит он того?](https://habr.com/ru/articles/1092738/), [Связка EDT и Напарника для начинающих](https://infostart.ru/1c/articles/2561318/)
- [От задачи до автотеста: ИИ и Vanessa Automation](https://infostart.ru/journal/news/mir-1s/ot-zadachi-do-rabotayushchego-avtotesta-otvety-eksperta-o-roli-ii-i-vanessa-automation_2776269/)
- [Пять вопросов пользователей к ИИ-агенту в 1С](https://infostart.ru/1c/articles/2805175/)

## Курсы и вебинары

- [Курс Инфостарта «Разработка в 1С с ИИ-агентами»](https://infostart.ru/edu/2781275/) (старт 19.10.2026: skills, MCP, YAxUnit).
- [Вебинар «ИИ и 1С: практика применения MCP»](https://infostart.ru/journal/news/mir-1s/itogi-vebinara-ii-i-1s-praktika-primeneniya-mcp-v-razrabotke-i-avtomatizatsii_2446503/), [доклад «AI-агенты для 1С» (Косолапов)](https://infostart.ru/video/w2509445/).
- [Секция ИИ на INFOSTART TEAM EVENT 2026](https://infostart.ru/journal/news/mir-1s/sektsiya-integratsiya-ii-prompt-inzhiniring-ispolzovanie-ii-v-razrabotke-i-proektakh-na-infostart-te_2634326/), [лучшие доклады TECH EVENT 2026](https://habr.com/ru/companies/infostart/articles/1097146/).

## Сообщества и обсуждения

- Telegram: [«1С × ИИ: инженерный цех»](https://t.me/ceh_1c_ai), «Желтый вайб» (автор vibecoding1c и 1c_mcp).
- [Хабр, хаб 1С](https://habr.com/ru/hub/1C/); раздел [нейросети на Инфостарте](https://infostart.ru/public/all/integraciya_i_obmen_dannymi/neyroseti_integraciya/).
- Форум Инфостарта: [«Подскажите ИИ-ресурс для 1С»](https://forum.infostart.ru/forum9/topic330385/), [«Курсы по Claude Code и 1С»](https://forum.infostart.ru/forum9/topic342308/message3283468/), [«ИИ для менеджеров и бухгалтеров»](https://forum.infostart.ru/forum6/topic341861/message3281217/).

## Чего не нашлось

- Открытого датасета BSL-кода или открытой модели, дообученной на 1С (есть только эксперименты с Qwen).
- Плагина GigaCode или SourceCraft для 1С: на апрель 2026 GigaCode для 1С был только анонсирован.
- Официально подтверждённого встроенного LLM в платформе 8.5.
- Свежих тредов на mista.ru по ИИ: поисковики их почти не индексируют, искать лучше на самом форуме.
