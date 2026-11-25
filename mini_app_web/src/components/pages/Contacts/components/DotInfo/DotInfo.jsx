import styles from "./DotInfo.module.css";
import { openExternalLink } from "../../../../../utils/openLink";


const DotInfo = ({name, icon, href}) => {
    return (
        <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.wrapper}
            onClick={(e) => {
                e.preventDefault();
                openExternalLink(href);
            }}
        >
            {icon ? <span className={styles.icon}>{icon}</span> : name && <p>{name}</p>}
        </a>
    );
}

export {DotInfo};