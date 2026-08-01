-- ============================================================
-- doTERRA AI Bot — Схема бази даних контенту v2
-- Сумісно з PostgreSQL (основна) та SQLite (з адаптацією)
-- Оновлено: додано поля для наукових досліджень та рекомендацій
-- ============================================================

-- Для PostgreSQL: увімкнути розширення для UUID
-- CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ------------------------------------------------------------
-- Основна таблиця продуктів
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id                  SERIAL PRIMARY KEY,
    slug                VARCHAR(100)    UNIQUE NOT NULL,  -- унікальний ключ, напр. 'frankincense'
    name_ua             VARCHAR(200)    NOT NULL,          -- 'Ладан'
    name_en             VARCHAR(200)    NOT NULL,          -- 'Frankincense'
    type                VARCHAR(50)     NOT NULL           -- 'single' | 'blend' | 'supplement'
                        CHECK (type IN ('single', 'blend', 'supplement')),

    -- Базові поля
    tags                TEXT,   -- JSON: ["#ролер","#БАД"]
    product_variants    TEXT,   -- JSON: [{"name":"","url":""}]
    short_description   TEXT,   -- JSON: ["рядок 1","рядок 2","рядок 3"]
    physical_effects    TEXT,   -- JSON: ["ефект 1","ефект 2"]
    emotional_effects   TEXT,   -- JSON: {"removes":[],"develops":[]}
    usage               TEXT,   -- JSON: {"aromatic":[],"topical":[],"internal":""}
    indications         TEXT,   -- JSON: [{"title":"","description":""}]
    origin              TEXT,   -- JSON: {"description":[],"composition":{"compounds":[],"description":""}}
    beauty_skincare     TEXT,   -- JSON: [{"title":"","description":""}]
    interesting_facts   TEXT,   -- JSON: ["факт 1","факт 2"]
    diffuser_blends     TEXT,   -- JSON: [{"name":"","drops":[{"oil":"","amount":0}]}]
    additional_info     TEXT,   -- Розширений текст (емоційний / духовний)
    precautions         TEXT,   -- JSON: ["застереження 1","застереження 2"]
    disclaimer          TEXT,   -- Стандартний дисклеймер

    -- ✅ НОВІ ПОЛЯ: Наукові дослідження та медичні рекомендації
    research            TEXT,   -- JSON: [{"title":"","source":"","year":2024,"summary":"","url":""}]
    expert_quotes       TEXT,   -- JSON: [{"author":"","title":"","quote":"","source":""}]
    drug_interactions   TEXT,   -- JSON: ["взаємодія 1","взаємодія 2"]
    dosage_guide        TEXT,   -- JSON: {"aromatic":"","topical":"","internal":"","children":"","notes":""}
    contraindications   TEXT,   -- JSON: ["протипоказання 1","протипоказання 2"] (медичні, суворіші за precautions)

    is_active           BOOLEAN     DEFAULT TRUE,
    created_at          TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- Індекси для швидкого пошуку
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_products_slug     ON products(slug);
CREATE INDEX IF NOT EXISTS idx_products_type     ON products(type);
CREATE INDEX IF NOT EXISTS idx_products_name_ua  ON products(name_ua);
CREATE INDEX IF NOT EXISTS idx_products_active   ON products(is_active);

-- ------------------------------------------------------------
-- Таблиця FAQ (окремі питання-відповіді для бота)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS faq (
    id              SERIAL PRIMARY KEY,
    product_slug    VARCHAR(100)    REFERENCES products(slug) ON DELETE CASCADE,
    question        TEXT            NOT NULL,
    answer          TEXT            NOT NULL,
    tags            TEXT,           -- JSON-масив тегів для пошуку
    is_active       BOOLEAN         DEFAULT TRUE,
    created_at      TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_faq_product ON faq(product_slug);

-- ------------------------------------------------------------
-- Таблиця протоколів застосування
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS protocols (
    id              SERIAL PRIMARY KEY,
    title           VARCHAR(300)    NOT NULL,
    description     TEXT,
    products_used   TEXT,           -- JSON-масив slug продуктів
    steps           TEXT,           -- JSON-масив кроків
    category        VARCHAR(100),   -- 'sleep', 'immunity', 'stress', 'beauty' тощо
    source          TEXT,           -- звідки протокол (книга, лікар, дослідження)
    is_active       BOOLEAN         DEFAULT TRUE,
    created_at      TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- Структура JSON-полів (документація)
-- ============================================================
--
-- research:
--   [{ "title": "Протизапальні властивості босвелієвої кислоти",
--      "source": "Journal of Ethnopharmacology",
--      "year": 2019,
--      "summary": "Дослідження підтвердило...",
--      "url": "https://pubmed.ncbi.nlm.nih.gov/..." }]
--
-- expert_quotes:
--   [{ "author": "Dr. David Hill",
--      "title": "Chief Medical Advisor, doTERRA",
--      "quote": "Ладан є одним з найбільш вивчених...",
--      "source": "doTERRA Science Blog" }]
--
-- drug_interactions:
--   ["Може посилювати дію антикоагулянтів (варфарин)",
--    "Взаємодіє з імунодепресантами — проконсультуйтеся з лікарем"]
--
-- dosage_guide:
--   { "aromatic": "15-30 хв у дифузорі, 2-3 рази на день",
--     "topical":  "1-2 краплі, розведені 1:3 з базовою олією",
--     "internal": "1-2 краплі 1-3 рази на день з водою або в капсулі",
--     "children": "Лише ароматичний метод для дітей до 6 років",
--     "notes":    "Не перевищуйте 10 крапель на день" }
--
-- contraindications:
--   ["Епілепсія (у великих дозах)",
--    "Гострий гепатит — уникати внутрішнього застосування"]
--
-- ============================================================
-- PostgreSQL: автоматичне оновлення updated_at
-- ============================================================
-- CREATE OR REPLACE FUNCTION update_updated_at_column()
-- RETURNS TRIGGER AS $$
-- BEGIN
--     NEW.updated_at = NOW();
--     RETURN NEW;
-- END;
-- $$ language 'plpgsql';
--
-- CREATE TRIGGER update_products_updated_at
--     BEFORE UPDATE ON products
--     FOR EACH ROW
--     EXECUTE PROCEDURE update_updated_at_column();
