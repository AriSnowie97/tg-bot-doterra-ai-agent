import { Link } from "react-router-dom";
import styles from "./SimpleLink.module.css";


const SimpleLink = ({to, text, another=false}) => {
    return (
        <>
            <Link to={to}>
                <div
                className={`${styles.wrapper} ${another ? styles.another : ""}`}
                >
                    <h3>{text}<code>{" -->"}</code></h3>
                </div>
            </Link>
        </>
    );
}

export {SimpleLink};