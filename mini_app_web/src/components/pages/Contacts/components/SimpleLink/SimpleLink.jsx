import { Link } from "react-router-dom";
import styles from "./SimpleLink.module.css";


const SimpleLink = ({to, text, another=false}) => {
    return (
        <Link to={to} style={{ textDecoration: 'none' }}>
            <div className={`${styles.wrapper} ${another ? styles.another : ""}`}>
                <div className={styles.text}>
                    <h3>{text}</h3>
                </div>
                <div className={styles.arrow}>
                    <p>→</p>
                </div>
            </div>
        </Link>
    );
}

export {SimpleLink};