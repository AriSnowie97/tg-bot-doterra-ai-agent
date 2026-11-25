import { useEffect, useMemo, useState } from "react";
import { useLang } from "../../../contexts/LangContext";
import { get_articles, get_whats_new } from "../../../api/articles";
import { Article } from "../Articles/components/Article";
import styles from "./WhatsNew.module.css";

const WhatsNew = () => {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState("all");
    const [search, setSearch] = useState("");
    const { t, lang } = useLang();

    useEffect(() => {
        let cancelled = false;
        const fetchUpdates = async () => {
            try {
                setLoading(true);
                let data = [];
                const response = await get_whats_new(lang);
                if (response.ok) {
                    data = await response.json();
                } else {
                    // Fallback якщо бекенд ще перезапускається
                    const fallback = await get_articles(lang);
                    if (fallback.ok) {
                        const all = await fallback.json();
                        data = all.filter((a) => a.update_type === "new" || a.update_type === "returned");
                    }
                }
                if (!cancelled) {
                    setItems(Array.isArray(data) ? data : []);
                }
            } catch (err) {
                console.error("Failed to load whats new", err);
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        };
        fetchUpdates();
        return () => {
            cancelled = true;
        };
    }, [lang]);

    const counts = useMemo(() => {
        let newCount = 0;
        let returnedCount = 0;
        for (const item of items) {
            if (item.update_type === "returned") returnedCount += 1;
            else if (item.update_type === "new") newCount += 1;
        }
        return { all: items.length, new: newCount, returned: returnedCount };
    }, [items]);

    const filteredItems = useMemo(() => {
        const q = search.trim().toLowerCase();
        return items.filter((item) => {
            const matchType = filter === "all" || item.update_type === filter;
            if (!matchType) return false;
            if (!q) return true;
            const inTitle = item.title && item.title.toLowerCase().includes(q);
            const inShort = item.short && item.short.toLowerCase().includes(q);
            const inTag = item.tag && item.tag.toLowerCase().includes(q);
            const inMarkets = Array.isArray(item.markets) && item.markets.some((m) => m.toLowerCase().includes(q));
            return inTitle || inShort || inTag || inMarkets;
        });
    }, [items, filter, search]);

    const filterTabs = [
        { key: "all", label: t("whats_new_filter_all"), count: counts.all },
        { key: "new", label: `✨ ${t("whats_new_filter_new")}`, count: counts.new },
        { key: "returned", label: `♻️ ${t("whats_new_filter_returned")}`, count: counts.returned },
    ];

    return (
        <div className={styles.wrapper}>
            <div className={styles.header}>
                <h1 className={styles.pageTitle}>{t("whats_new_title")}</h1>
                <p className={styles.subtitle}>{t("whats_new_subtitle")}</p>
            </div>

            <input
                className={styles.input}
                type="text"
                name="whats_new_search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t("whats_new_search_placeholder")}
            />

            <div className={styles.filters}>
                {filterTabs.map((tab) => (
                    <button
                        key={tab.key}
                        type="button"
                        className={`${styles.filterBtn} ${filter === tab.key ? styles.activeFilter : ""}`}
                        onClick={() => setFilter(tab.key)}
                    >
                        {tab.label} ({tab.count})
                    </button>
                ))}
            </div>

            <div className={styles.slider}>
                <div className={styles.list}>
                    {loading ? (
                        <div className={styles.emptyState}>{t("loading")}</div>
                    ) : filteredItems.length > 0 ? (
                        filteredItems.map((item) => (
                            <Article data={item} key={item.slug} />
                        ))
                    ) : filter === "returned" && counts.returned === 0 && !search.trim() ? (
                        <div className={styles.infoCard}>
                            <span className={styles.infoIcon}>♻️</span>
                            <p>{t("whats_new_empty_returned")}</p>
                        </div>
                    ) : (
                        <div className={styles.emptyState}>{t("nothing_found")}</div>
                    )}
                </div>
            </div>
        </div>
    );
};

export { WhatsNew };
