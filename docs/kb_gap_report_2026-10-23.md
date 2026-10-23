# Сверка базы знаний с каталогом doTERRA и книгами (23.10.2026)

Что проверялось: `src/content/products/` (328 карточек до сверки) против (1) книг в `src/content/books/`, «Symphony of the Cells» (`symphony_of_the_cells/`) и советов (`advice/`), и (2) официальных страниц doterra.com.
Критерий добавления: продукт **упомянут в книгах базы** и **подтверждён на doterra.com**.

## Главное

- Старый список `docs/doterra_missing_products.md` устарел: он написан для базы из 86 продуктов. Сейчас в базе 328 карточек, и почти всё из того списка уже закрыто (Touch-роллеры, линейка On Guard для дома, Veráge, spa, Yarrow|Pom, abōde, диффузоры, сезонные линии). Из заметного там осталось только abōde Liquid Dish Soap (в книгах не упоминается, поэтому не добавлялся).
- Реальные пробелы относительно книг: **14 продуктов**, плюс **On Guard Stick + Echinacea** и **Deep Blue Stick + Copaiba**, добавленные по запросу. Для каждого создана UA-карточка (`products/`) и EN-карточка (`products/en/`) по `product_template.md`, всего 32 файла.

## Добавлено

| Файл | Продукт | Где в книгах | Официальный источник | На что обратить внимание |
|---|---|---|---|---|
| `zendocrine` | Zendocrine® Detoxification Blend | «Емоції та ефірні олії» (тема «Обмеженість / застій»); Symphony: глоссарий, таблица замен, карточки систем (около десятка глав) | ZA | **Предыдущая формула**: RevitaZen™ в базе уже есть и назван её наследником (состав с имбирём). Карточка связывает оба названия, так как книги говорят «Zendocrine» |
| `zendocrine-detoxification-complex` | Zendocrine® Detoxification Complex (капсулы) | Symphony: карточки сердечно-сосудистой, пищеварительной и мочевой систем | IL (склад ЕС) | Состав на странице не раскрыт («proprietary blend»), дозировки нет. Не путать с RevitaZen+™ |
| `elevation` | Elevation™ Joyful Blend | «Емоції та ефірні олії» («пригніченість»); Symphony: глоссарий, замены, карточки систем | ZA | Страницы есть для ПАР, Бразилии, Австралии; наличие в вашем регионе уточнить |
| `white-fir` | White Fir | Symphony (замены в 5 протоколах и в таблице замен); «Modern Essentials» | doterra.com (блог Spotlight) | В карточку добавлены предупреждения из книги «Аромалогія» (почки, ЖКТ натощак) |
| `caraway` | Caraway | Symphony (замена Oregano в 3 протоколах) | IL (склад ЕС) | Данных мало: нет инструкции по применению. Продукт ЕС, «не для индивидуальной продажи» |
| `dill` | Dill | Symphony (замена Lemongrass в 8 протоколах, замены Fennel) | doterra.com (блог Spotlight) | **Лимитированный**, только по акциям |
| `cumin` | Cumin | Symphony (замена Oregano); «Modern Essentials»; «Ефірна абетка» («горячие» масла) | doterra.com (блог Spotlight) | **Лимитированный** (акция Sunsational Flavors Kit). Добавлено предупреждение о «горячем» масле |
| `kumquat` | Kumquat | «Modern Essentials» | RU (5 мл) | Описание с российского рынка; наличие в других регионах уточнить |
| `hinoki` | Hinoki | «Емоції та ефірні олії» («поспіх / хаос»); «Modern Essentials» | doterra.com | **Лимитированный** |
| `lemon-myrtle` | Lemon Myrtle | «Емоції та ефірні олії» («туман у голові», «ясність розуму»); входит в состав Elevation | doterra.com | **Лимитированный** |
| `manuka` | Manuka | «Modern Essentials» | NZ (5 мл) | Есть роллер Manuka Touch (10 мл), в базе его нет |
| `litsea` | Litsea | «Modern Essentials»; «Аромалогія» (фототоксичность) | doterra.com (блог Spotlight) | **Мало официальных данных**: нет размера, латинского названия, схемы применения. Карточка намеренно скромная |
| `palmarosa` | Palmarosa | «Аромалогія» (раздражение слизистой ЖКТ) | doterra.com | Страница не называет размер и не помечает масло лимитированным |
| `doterra-on-guard-stick-echinacea` | doTERRA On Guard® Stick + Echinacea (30 г) | Сам стик в книгах не упоминается (добавлен по запросу); смесь On Guard есть в «Емоції та ефірні олії» и Symphony | CH / PDF doTERRA (EU) | Описание со склада ЕС; полный состав и предостережения взяты с двух совпадающих источников |
| `deep-blue-stick-copaiba` | doTERRA Deep Blue® Stick + Copaiba (48 г) | Сам стик в книгах не упоминается (добавлен по запросу); упомянут в `deep-blue.md`; Deep Blue есть в книге 01 | US (PDF doTERRA + DailyMed) | Продукт OTC: на этикетке США ментол 10% как действующее вещество; добавлены предупреждения (салицилаты, антикоагулянты) |
| `deep-blue-rub` | doTERRA Deep Blue® Rub (крем 120 мл) | Книга 01 («Deep Blue blend/rub»); `deep-blue.md` уже упоминает Rub как часть линейки | IN | Состав содержит Wintergreen: добавлено предупреждение из «Ефірна абетка» про антикоагулянты |

## Упомянуто в книгах, но не добавлено

- **Star Anise (Бадьян)**: официальной страницы doTERRA найти не удалось.
- **Clementine**, **Cajeput (Каяпут)**, **Niaouli (Найолі)**, **Nutmeg (Мускатний горіх)**, **Benzoin (Бензоїн)** и другие: это масла из общих книг по ароматерапии. Наличие в каталоге doTERRA я не проверял и не подтверждал, поэтому не добавлял.
- **Yarrow** как отдельное масло: в Symphony это сочетание «Yarrow|Pom», которое в базе уже есть.

Из других книжных упоминаний все продукты, которые я сверил, в базе уже были (Balance, Immortelle/Salubelle, Serenity, DigestZen/ZenGest, Whisper Touch, Mito2Max, GX Assist, Terrazyme, LLV и т. д.).

## Что стоит подтвердить

1. Доступность Elevation, Zendocrine, Caraway, Kumquat, Manuka на целевом рынке: я опирался на страницы разных стран, ни одна из них не проверялась по региону клиента.
2. Лимитированные позиции (Dill, Cumin, Hinoki, Lemon Myrtle): решить, нужны ли они боту, если купить их можно только в акционные периоды.
3. Фото: во всех новых карточках стоит плейсхолдер из `product_template.md`, подставляется через `content_uploader_bot.py`.
4. После добавления файлов нужно обновить чанки (`data/all_chunks.json`) и БД штатным загрузчиком; я их не пересоздавал.

## Источники

- Zendocrine: https://www.doterra.com/ZA/en_ZA/p/zendocrine-oil · https://www.doterra.com/IL/en_IL/p/zendocrine-complex
- Elevation: https://www.doterra.com/ZA/en_ZA/p/elevation-oil
- White Fir: https://www.doterra.com/US/es/blog/spotlight-white-fir-oil
- Caraway: https://www.doterra.com/IL/en_IL/p/caraway-oil
- Dill: https://www.doterra.com/US/en/blog/spotlight-dill-oil
- Cumin: https://doterra.com/US/en/blog/spotlight-cumin-oil
- Kumquat: https://www.doterra.com/RU/ru_RU/p/kumquat-oil
- Hinoki: https://www.doterra.com/US/en/hinoki-oil
- Lemon Myrtle: https://www.doterra.com/US/en/lemon-myrtle-oil
- Manuka: https://www.doterra.com/NZ/en_NZ/p/manuka-oil
- Litsea: https://www.doterra.com/US/es/blog/spotlight-benefits-of-manuka-and-litsea-oils
- Palmarosa: https://www.doterra.com/US/en/palmarosa-oil
- Deep Blue Rub: https://www.doterra.com/IN/en_IN/p/doterra-deep-blue-rub
- Deep Blue Stick + Copaiba: https://media.doterra.com/us/en/pips/deep-blue-stick.pdf · https://dailymed.nlm.nih.gov/dailymed/getFile.cfm?setid=bdc48d22-c5f6-665e-e053-2995a90a9dbe&type=pdf
- On Guard Stick + Echinacea: https://media.doterra.com/eu/en/pips/on-guard-stick-plus-echinacea.pdf · https://shop.doterra.com/CH/en_CH/shop/onguard-and-echinacea-stick/
