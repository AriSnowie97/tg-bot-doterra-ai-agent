import styles from "./DotInfo.module.css";


const DotInfo = ({name, icon, href}) => {
    return (
        <a href={href} target="_blank" rel="noopener noreferrer" className={styles.wrapper}>
            {icon && <span className={styles.icon}>{icon}</span>}
            <p>{name}</p>
        </a>
    );
}

export {DotInfo};