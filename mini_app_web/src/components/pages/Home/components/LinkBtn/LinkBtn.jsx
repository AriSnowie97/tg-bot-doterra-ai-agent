import { Link } from "react-router-dom";

import styles from "./LinkBtn.module.css";
import { useLang } from "../../../../../contexts/LangContext";
import { isExternalUrl, openExternalLink } from "../../../../../utils/openLink";


const LinkBtn = ({linkTo, Svg, subject, newStyles}) => {
    const { t } = useLang();

    const content = (
        <div className={`${styles.wrapper} ${newStyles.wrapper || ""}`}>
            <div className={`${styles.img} ${newStyles.img || ""}`}>
                <Svg className={styles.Svg} />
            </div>
            <div className={`${styles.text} ${newStyles.text || ""}`}>
                <h3>{t("link_btns")?.[subject]?.title ?? "title"}</h3>
                <p>{t("link_btns")?.[subject]?.description ?? "description"}</p>
            </div>
            <div className={`${styles.arrow} ${newStyles.arrow || ""}`}>
                <p>→</p>
            </div>
        </div>
    );

    if (isExternalUrl(linkTo)) {
        return (
            <a
                href={linkTo}
                target="_blank"
                rel="noopener noreferrer"
                className={`${styles.linkToBtn} ${newStyles.linkToBtn || ""}`}
                onClick={(e) => {
                    e.preventDefault();
                    openExternalLink(linkTo);
                }}
            >
                {content}
            </a>
        );
    }

    return (
        <Link to={linkTo} className={`${styles.linkToBtn} ${newStyles.linkToBtn || ""}`}>
            {content}
        </Link>
    );
}

export {LinkBtn};