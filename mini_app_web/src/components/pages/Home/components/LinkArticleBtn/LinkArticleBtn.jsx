import { useState } from "react";
import { Link } from "react-router-dom";

import styles from "./LinkArticleBtn.module.css";
import { useLang } from "../../../../../contexts/LangContext";

const LinkArticleBtn = ({data}) => {
    const [imgError, setImgError] = useState(false);
    const { t } = useLang();
    const cleanTitle = (data.title || "")
        .replace(/\s*\((?:чанк|chunk)\s*\d+\)/gi, "")
        .replace(/\s*--\s*/g, " — ")
        .trim();
    const cleanShort = (data.short || "")
        .replace(/^[👑▫️🔹💦•\-–—\s]+/u, "")
        .replace(/\*\*|__/g, "")
        .trim();

    return (
        <Link to={`/article/${data.slug}`} className={styles.linkToBtn}>
            <div className={styles.wrapper}>
                <div className={styles.img}>
                    {data.image && !imgError
                        ? <img src={data.image} alt={cleanTitle} onError={() => setImgError(true)} className={styles.imgEl} />
                        : <span style={{ fontSize: '28px' }}>🌿</span>
                    }
                </div>
                <div className={styles.body}>
                    <h4 className={styles.title}>{cleanTitle}</h4>
                    {cleanShort && <p className={styles.short}>{cleanShort}</p>}
                    <span className={styles.readMore}>{t("read_more")}</span>
                </div>
            </div>
        </Link>
    );
}

export {LinkArticleBtn};