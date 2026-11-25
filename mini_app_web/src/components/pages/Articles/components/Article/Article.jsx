import { useState } from "react";
import { Link } from "react-router-dom";
import styles from "./Article.module.css";
import { useLang } from "../../../../../contexts/LangContext";

const Article = ({data}) => {
    const [imgError, setImgError] = useState(false);
    const { t } = useLang();

    let imageUrl = data.image;
    if (imageUrl && imageUrl.includes("New-Default-Image")) {
        imageUrl = "";
    }

    const cleanTitle = (data.title || "").replace(/\s*\((?:чанк|chunk)\s*\d+\)/gi, "").trim();
    const markets = Array.isArray(data.markets) ? data.markets : [];
    const marketsLabel = markets.length > 3
        ? `${markets.slice(0, 3).join(", ")} +${markets.length - 3}`
        : markets.join(", ");

    return (
        <Link 
            to={`/article/${data.slug}`} 
            style={{ textDecoration: 'none', display: 'block', width: '100%', boxSizing: 'border-box' }}
        >
            <div className={styles.wrapper}>
                {imageUrl && !imgError ? (
                    <div className={styles.imgWrap}>
                        <img
                            src={imageUrl}
                            alt={cleanTitle}
                            className={styles.img}
                            onError={() => setImgError(true)}
                        />
                    </div>
                ) : (
                    <div className={styles.imgPlaceholder}>🌿</div>
                )}
                <div className={styles.description}>
                    <h3>{cleanTitle}</h3>
                    <span>{data.short}</span>
                    {(data.update_type || data.tag || marketsLabel) && (
                        <div className={styles.metaRow}>
                            {data.update_type === "holiday" && (
                                <div className={`${styles.statusBadge} ${styles.badgeHoliday}`}>
                                    🎄 {t("whats_new_badge_holiday")}
                                </div>
                            )}
                            {data.update_type === "new" && (
                                <div className={`${styles.statusBadge} ${styles.badgeNew}`}>
                                    ✨ {t("whats_new_badge_new")}
                                </div>
                            )}
                            {data.update_type === "returned" && (
                                <div className={`${styles.statusBadge} ${styles.badgeReturned}`}>
                                    ♻️ {t("whats_new_badge_returned")}
                                </div>
                            )}
                            {data.tag && (
                                <div className={styles.tag}>
                                    <p>#{data.tag}</p>
                                </div>
                            )}
                            {marketsLabel && (
                                <div className={styles.marketsBadge}>
                                    🌍 {marketsLabel}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </Link>
    );
}

export {Article};