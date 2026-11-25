import { Link } from "react-router-dom";
import styles from "./SimpleLink.module.css";
import { isExternalUrl, openExternalLink } from "../../../../../utils/openLink";


const SimpleLink = ({to, text, another=false}) => {
    const content = (
        <div className={`${styles.wrapper} ${another ? styles.another : ""}`}>
            <div className={styles.text}>
                <h3>{text}</h3>
            </div>
            <div className={styles.arrow}>
                <p>→</p>
            </div>
        </div>
    );

    if (isExternalUrl(to)) {
        return (
            <a
                href={to}
                target="_blank"
                rel="noopener noreferrer"
                style={{ textDecoration: 'none' }}
                onClick={(e) => {
                    e.preventDefault();
                    openExternalLink(to);
                }}
            >
                {content}
            </a>
        );
    }

    return (
        <Link to={to} style={{ textDecoration: 'none' }}>
            {content}
        </Link>
    );
}

export {SimpleLink};